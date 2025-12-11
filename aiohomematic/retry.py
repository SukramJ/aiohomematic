# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Retry logic with exponential backoff for transient network errors.

Overview
--------
This module provides a RetryStrategy class that implements configurable retry
behavior with exponential backoff for operations that may fail due to transient
network issues.

Key features
------------
- Configurable retry count, initial delay, max delay, and backoff multiplier
- Automatic identification of retryable vs. permanent errors
- Integration with the codebase's exception hierarchy
- Async-first design for use with aiohttp and RPC operations

Usage
-----
    from aiohomematic.retry import RetryStrategy, with_retry

    # Using the decorator
    @with_retry
    async def my_rpc_call():
        ...

    # Using the context manager
    strategy = RetryStrategy()
    async with strategy.execute():
        await my_rpc_call()

"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import errno
from functools import wraps
import logging
from typing import Any, Final, TypeVar, overload
from xmlrpc.client import Fault as XmlRpcFault

from aiohttp import ClientConnectorCertificateError, ClientConnectorError, ServerDisconnectedError, ServerTimeoutError

from aiohomematic.const import (
    RETRY_BACKOFF_MULTIPLIER,
    RETRY_INITIAL_BACKOFF_SECONDS,
    RETRY_MAX_ATTEMPTS,
    RETRY_MAX_BACKOFF_SECONDS,
)
from aiohomematic.exceptions import (
    AuthFailure,
    BaseHomematicException,
    CircuitBreakerOpenException,
    InternalBackendException,
    NoConnectionException,
    UnsupportedException,
    ValidationException,
)

_LOGGER: Final = logging.getLogger(__name__)

# Type variable for return type of decorated functions
T = TypeVar("T")

# OS error codes that indicate transient network issues
_TRANSIENT_OS_ERROR_CODES: Final[frozenset[int]] = frozenset(
    {
        errno.ECONNREFUSED,  # Connection refused
        errno.EHOSTUNREACH,  # No route to host
        errno.ENETUNREACH,  # Network is unreachable
        errno.ETIMEDOUT,  # Connection timed out
        errno.ECONNRESET,  # Connection reset by peer
        errno.EPIPE,  # Broken pipe
        errno.ECONNABORTED,  # Connection aborted
    }
)

# Exception types that indicate permanent failures - never retry these
_PERMANENT_EXCEPTION_TYPES: Final[tuple[type[BaseException], ...]] = (
    AuthFailure,
    CircuitBreakerOpenException,  # Circuit breaker has its own recovery mechanism
    ClientConnectorCertificateError,  # TLS/SSL certificate errors won't resolve with retry
    InternalBackendException,  # Server-side errors typically need manual intervention
    UnsupportedException,
    ValidationException,
    TypeError,
    XmlRpcFault,
)


def is_retryable_exception(exc: BaseException) -> bool:
    """
    Determine if an exception is retryable.

    Returns True for transient network errors, False for permanent failures.
    """
    # Never retry permanent exceptions
    if isinstance(exc, _PERMANENT_EXCEPTION_TYPES):
        return False

    # NoConnectionException is retryable if caused by transient network issues
    if isinstance(exc, NoConnectionException):
        return True

    # OSError with transient error codes
    if isinstance(exc, OSError) and exc.errno in _TRANSIENT_OS_ERROR_CODES:
        return True

    # TimeoutError is always retryable
    if isinstance(exc, TimeoutError | asyncio.TimeoutError):
        return True

    # ConnectionError and subclasses (ConnectionRefusedError, etc.) are retryable
    if isinstance(exc, ConnectionError):
        return True

    # aiohttp server errors that indicate transient issues
    if isinstance(exc, ServerTimeoutError | ServerDisconnectedError):
        return True

    # aiohttp ClientConnectorError may wrap transient OS errors
    # Check the underlying os_error for transient error codes
    if isinstance(exc, ClientConnectorError):
        return (os_error := exc.os_error) is not None and os_error.errno in _TRANSIENT_OS_ERROR_CODES

    # Other BaseHomematicException types might be retryable
    # (except permanent ones already handled above)
    # Check if the original cause was transient
    return (
        isinstance(exc, BaseHomematicException) and exc.__cause__ is not None and is_retryable_exception(exc.__cause__)
    )


class RetryStrategy:
    """
    Configurable retry strategy with exponential backoff.

    Attributes:
        max_attempts: Maximum number of retry attempts (default: 3).
        initial_backoff: Initial delay in seconds before first retry (default: 0.5).
        max_backoff: Maximum delay in seconds between retries (default: 30.0).
        backoff_multiplier: Multiplier for exponential backoff (default: 2.0).

    """

    __slots__ = (
        "_backoff_multiplier",
        "_current_attempt",
        "_current_backoff",
        "_initial_backoff",
        "_max_attempts",
        "_max_backoff",
    )

    def __init__(
        self,
        *,
        max_attempts: int = RETRY_MAX_ATTEMPTS,
        initial_backoff: float = RETRY_INITIAL_BACKOFF_SECONDS,
        max_backoff: float = RETRY_MAX_BACKOFF_SECONDS,
        backoff_multiplier: float = RETRY_BACKOFF_MULTIPLIER,
    ) -> None:
        """Initialize the retry strategy."""
        self._max_attempts: Final = max_attempts
        self._initial_backoff: Final = initial_backoff
        self._max_backoff: Final = max_backoff
        self._backoff_multiplier: Final = backoff_multiplier
        self._current_attempt: int = 0
        self._current_backoff: float = initial_backoff

    @property
    def attempts_remaining(self) -> int:
        """Return the number of attempts remaining."""
        return max(0, self._max_attempts - self._current_attempt)

    @property
    def current_attempt(self) -> int:
        """Return the current attempt number (1-indexed)."""
        return self._current_attempt

    async def execute(
        self,
        *,
        operation: Callable[[], Awaitable[T]],
        operation_name: str = "operation",
    ) -> T:
        """
        Execute an operation with retry logic.

        Args:
            operation: Async callable to execute.
            operation_name: Name for logging purposes.

        Returns:
            The result of the operation.

        Raises:
            The last exception if all retries are exhausted.

        """
        self.reset()
        last_exception: BaseException | None = None

        while self._current_attempt < self._max_attempts:
            await self.wait_before_retry()
            self.record_attempt()

            try:
                return await operation()
            except BaseException as exc:
                last_exception = exc

                if not is_retryable_exception(exc):
                    _LOGGER.debug(
                        "Retry: %s failed with non-retryable exception: %s",
                        operation_name,
                        type(exc).__name__,
                    )
                    raise

                if self._current_attempt >= self._max_attempts:
                    _LOGGER.debug(
                        "Retry: %s exhausted all %d attempts with %s",
                        operation_name,
                        self._max_attempts,
                        type(exc).__name__,
                    )
                    raise

                _LOGGER.debug(
                    "Retry: %s attempt %d/%d failed: %s. Retrying in %.2fs",
                    operation_name,
                    self._current_attempt,
                    self._max_attempts,
                    type(exc).__name__,
                    self._current_backoff,
                )

        # All retries exhausted (shouldn't reach here normally as we raise in the loop)
        if last_exception:
            _LOGGER.debug(
                "Retry: %s exhausted all %d attempts",
                operation_name,
                self._max_attempts,
            )
            raise last_exception

        # This should never happen, but satisfy type checker
        msg = "No attempts were made"
        raise RuntimeError(msg)

    def record_attempt(self) -> None:
        """Record that an attempt was made."""
        self._current_attempt += 1

    def reset(self) -> None:
        """Reset the retry state for a new operation."""
        self._current_attempt = 0
        self._current_backoff = self._initial_backoff

    def should_retry(self, *, exc: BaseException) -> bool:
        """
        Determine if the operation should be retried.

        Returns True if the exception is retryable and attempts remain.
        """
        if self._current_attempt >= self._max_attempts:
            return False
        return is_retryable_exception(exc)

    async def wait_before_retry(self) -> None:
        """Wait for the appropriate backoff period before retrying."""
        if self._current_attempt > 0:
            await asyncio.sleep(self._current_backoff)
            # Increase backoff for next retry (exponential backoff)
            self._current_backoff = min(
                self._current_backoff * self._backoff_multiplier,
                self._max_backoff,
            )


@overload
def with_retry(  # noqa: UP047
    func: Callable[..., Awaitable[T]],
) -> Callable[..., Awaitable[T]]: ...


@overload
def with_retry(
    func: None = None,
    *,
    max_attempts: int = ...,
    initial_backoff: float = ...,
    max_backoff: float = ...,
    backoff_multiplier: float = ...,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]: ...


def with_retry(  # noqa: UP047
    func: Callable[..., Awaitable[T]] | None = None,
    *,
    max_attempts: int = RETRY_MAX_ATTEMPTS,
    initial_backoff: float = RETRY_INITIAL_BACKOFF_SECONDS,
    max_backoff: float = RETRY_MAX_BACKOFF_SECONDS,
    backoff_multiplier: float = RETRY_BACKOFF_MULTIPLIER,
) -> Callable[..., Awaitable[T]] | Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """
    Add retry logic to an async function.

    Can be used with or without parentheses:

        @with_retry
        async def fetch_data():
            ...

        @with_retry
        async def fetch_data():
            ...

        @with_retry(max_attempts=5)
        async def fetch_data():
            ...

    Args:
        func: The function to decorate (when used without parentheses).
        max_attempts: Maximum number of retry attempts.
        initial_backoff: Initial delay in seconds before first retry.
        max_backoff: Maximum delay in seconds between retries.
        backoff_multiplier: Multiplier for exponential backoff.

    Returns:
        Decorated function with retry logic.

    """

    def decorator(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            strategy = RetryStrategy(
                max_attempts=max_attempts,
                initial_backoff=initial_backoff,
                max_backoff=max_backoff,
                backoff_multiplier=backoff_multiplier,
            )
            return await strategy.execute(
                operation=lambda: fn(*args, **kwargs),
                operation_name=fn.__name__,
            )

        return wrapper

    # Called as @with_retry without parentheses
    if func is not None:
        return decorator(func)

    # Called as @with_retry or @with_retry(max_attempts=5)
    return decorator
