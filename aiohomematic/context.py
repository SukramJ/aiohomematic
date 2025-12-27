# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Context variables for request tracking and implicit context propagation.

This module provides context variables that flow through async call chains
without explicit parameter passing, enabling request correlation, tracing,
and cross-cutting concerns.

Key features:
- RequestContext for tracking operations with correlation IDs
- Automatic propagation through async call chains
- Context manager for scoped context setting
- Service call detection via is_in_service()

Example:
    async with request_context(operation="set_value", device_address="ABC123"):
        await device.send_value(...)  # Context propagates automatically

    # Access context anywhere in the call chain
    ctx = get_request_context()
    request_id = get_request_id()

Public API of this module is defined by __all__.

"""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import uuid


@dataclass(frozen=True, slots=True)
class RequestContext:
    """
    Context for a single request/operation.

    Automatically propagates through async call chains via context variables.
    Immutable to prevent accidental modification; use with_* methods to create
    modified copies.

    Attributes:
        request_id: Unique identifier for this request (8 chars from UUID).
        operation: Name of the operation being performed.
        device_address: Address of the device being operated on, if applicable.
        interface_id: ID of the interface being used, if applicable.
        started_at: Timestamp when the request started.
        extra: Additional context-specific attributes.

    """

    request_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    operation: str = ""
    device_address: str | None = None
    interface_id: str | None = None
    started_at: datetime = field(default_factory=datetime.now)
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def elapsed_ms(self) -> float:
        """Return milliseconds since request started."""
        return (datetime.now() - self.started_at).total_seconds() * 1000

    def with_device(self, *, device_address: str) -> RequestContext:
        """
        Create new context with updated device address.

        Args:
            device_address: The device address to set.

        Returns:
            New RequestContext with updated device, preserving other fields.

        """
        return RequestContext(
            request_id=self.request_id,
            operation=self.operation,
            device_address=device_address,
            interface_id=self.interface_id,
            started_at=self.started_at,
            extra=self.extra,
        )

    def with_extra(self, **kwargs: Any) -> RequestContext:
        """
        Create new context with additional extra attributes.

        Args:
            **kwargs: Additional attributes to merge into extra.

        Returns:
            New RequestContext with merged extra attributes.

        """
        return RequestContext(
            request_id=self.request_id,
            operation=self.operation,
            device_address=self.device_address,
            interface_id=self.interface_id,
            started_at=self.started_at,
            extra={**self.extra, **kwargs},
        )

    def with_operation(self, *, operation: str) -> RequestContext:
        """
        Create new context with updated operation.

        Args:
            operation: The new operation name.

        Returns:
            New RequestContext with updated operation, preserving other fields.

        """
        return RequestContext(
            request_id=self.request_id,
            operation=operation,
            device_address=self.device_address,
            interface_id=self.interface_id,
            started_at=self.started_at,
            extra=self.extra,
        )


# Context variable for request tracking
_request_context: ContextVar[RequestContext | None] = ContextVar(
    "request_context",
    default=None,
)


def get_request_context() -> RequestContext | None:
    """
    Get the current request context.

    Returns:
        The current RequestContext, or None if no context is set.

    """
    return _request_context.get()


def get_request_id() -> str:
    """
    Get the current request ID or a default value.

    Returns:
        The current request ID, or "anonymous" if no context is set.

    """
    ctx = _request_context.get()
    return ctx.request_id if ctx else "anonymous"


class request_context:  # noqa: N801
    """
    Context manager for request tracking.

    Sets a RequestContext for the duration of the block, automatically
    propagating through async call chains.

    Example:
        async with request_context(operation="set_value", device_address="ABC123"):
            await device.send_value(...)  # Context propagates automatically

        # Synchronous usage also supported
        with request_context(operation="validate"):
            validate_config()

    """

    __slots__ = ("_ctx", "_token")

    def __init__(
        self,
        *,
        operation: str = "",
        device_address: str | None = None,
        interface_id: str | None = None,
        **extra: Any,
    ) -> None:
        """
        Initialize request context.

        Args:
            operation: Name of the operation being performed.
            device_address: Address of the device being operated on.
            interface_id: ID of the interface being used.
            **extra: Additional context-specific attributes.

        """
        self._ctx = RequestContext(
            operation=operation,
            device_address=device_address,
            interface_id=interface_id,
            extra=extra,
        )
        self._token: Token[RequestContext | None] | None = None

    async def __aenter__(self) -> RequestContext:
        """Async enter - delegates to sync enter."""
        return self.__enter__()

    async def __aexit__(self, *args: object) -> None:
        """Async exit - delegates to sync exit."""
        self.__exit__()

    def __enter__(self) -> RequestContext:
        """Enter context and set the request context."""
        self._token = _request_context.set(self._ctx)
        return self._ctx

    def __exit__(self, *args: object) -> None:
        """Exit context and reset the request context."""
        if self._token is not None:
            _request_context.reset(self._token)


def set_request_context(*, ctx: RequestContext) -> Token[RequestContext | None]:
    """
    Manually set the request context.

    Returns a token that must be used with reset_request_context().
    Prefer using the request_context context manager instead.

    Args:
        ctx: The RequestContext to set.

    Returns:
        Token for resetting the context.

    """
    return _request_context.set(ctx)


def reset_request_context(*, token: Token[RequestContext | None]) -> None:
    """
    Reset the request context using a token from set_request_context().

    Args:
        token: Token returned from set_request_context().

    """
    _request_context.reset(token)


def is_in_service() -> bool:
    """
    Check if currently executing within a service call.

    A service call is identified by having a RequestContext with an operation
    that starts with "service:".

    Returns:
        True if currently inside a service call, False otherwise.

    """
    ctx = _request_context.get()
    return ctx is not None and ctx.operation.startswith("service:")


# Define public API for this module
__all__ = [
    "RequestContext",
    "get_request_context",
    "get_request_id",
    "is_in_service",
    "request_context",
    "reset_request_context",
    "set_request_context",
]
