# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Module for AioHomematicExceptions.

Public API of this module is defined by __all__.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
import inspect
import logging
from typing import Any, Final, cast

_LOGGER: Final = logging.getLogger(__name__)


class BaseHomematicException(Exception):
    """aiohomematic base exception."""

    def __init__(self, name: str, *args: Any) -> None:
        """Init the AioHomematicException."""
        if args and isinstance(args[0], BaseException):
            self.name = args[0].__class__.__name__
            args = _reduce_args(args=args[0].args)
        else:
            self.name = name
        super().__init__(_reduce_args(args=args))


class ClientException(BaseHomematicException):
    """aiohomematic Client exception."""

    def __init__(self, *args: Any) -> None:
        """Init the ClientException."""
        super().__init__("ClientException", *args)


class UnsupportedException(BaseHomematicException):
    """aiohomematic unsupported exception."""

    def __init__(self, *args: Any) -> None:
        """Init the UnsupportedException."""
        super().__init__("UnsupportedException", *args)


class ValidationException(BaseHomematicException):
    """aiohomematic validation exception."""

    def __init__(self, *args: Any) -> None:
        """Init the ValidationException."""
        super().__init__("ValidationException", *args)


class NoConnectionException(BaseHomematicException):
    """aiohomematic NoConnectionException exception."""

    def __init__(self, *args: Any) -> None:
        """Init the NoConnection."""
        super().__init__("NoConnectionException", *args)


class NoClientsException(BaseHomematicException):
    """aiohomematic NoClientsException exception."""

    def __init__(self, *args: Any) -> None:
        """Init the NoClientsException."""
        super().__init__("NoClientsException", *args)


class AuthFailure(BaseHomematicException):
    """aiohomematic AuthFailure exception."""

    def __init__(self, *args: Any) -> None:
        """Init the AuthFailure."""
        super().__init__("AuthFailure", *args)


class AioHomematicException(BaseHomematicException):
    """aiohomematic AioHomematicException exception."""

    def __init__(self, *args: Any) -> None:
        """Init the AioHomematicException."""
        super().__init__("AioHomematicException", *args)


class AioHomematicConfigException(BaseHomematicException):
    """aiohomematic AioHomematicConfigException exception."""

    def __init__(self, *args: Any) -> None:
        """Init the AioHomematicConfigException."""
        super().__init__("AioHomematicConfigException", *args)


class InternalBackendException(BaseHomematicException):
    """aiohomematic InternalBackendException exception."""

    def __init__(self, *args: Any) -> None:
        """Init the InternalBackendException."""
        super().__init__("InternalBackendException", *args)


def _reduce_args(*, args: tuple[Any, ...]) -> tuple[Any, ...] | Any:
    """Return the first arg, if there is only one arg."""
    return args[0] if len(args) == 1 else args


def log_exception[**P, R](
    *,
    exc_type: type[BaseException],
    logger: logging.Logger = _LOGGER,
    level: int = logging.ERROR,
    extra_msg: str = "",
    re_raise: bool = False,
    exc_return: Any = None,
) -> Callable[[Callable[P, R | Awaitable[R]]], Callable[P, R | Awaitable[R]]]:
    """Decorate methods for exception logging."""

    def decorator_log_exception(
        func: Callable[P, R | Awaitable[R]],
    ) -> Callable[P, R | Awaitable[R]]:
        """Decorate log exception method."""

        function_name = func.__name__

        @wraps(func)
        async def async_wrapper_log_exception(*args: P.args, **kwargs: P.kwargs) -> R:
            """Wrap async methods."""
            try:
                return_value = cast(R, await func(*args, **kwargs))  # type: ignore[misc]
            except exc_type as exc:
                message = (
                    f"{function_name.upper()} failed: {exc_type.__name__} [{_reduce_args(args=exc.args)}] {extra_msg}"
                )
                logger.log(level, message)
                if re_raise:
                    raise
                return cast(R, exc_return)
            return return_value

        @wraps(func)
        def wrapper_log_exception(*args: P.args, **kwargs: P.kwargs) -> R:
            """Wrap sync methods."""
            return cast(R, func(*args, **kwargs))

        if inspect.iscoroutinefunction(func):
            return async_wrapper_log_exception
        return wrapper_log_exception

    return decorator_log_exception


# Define public API for this module
__all__ = tuple(
    sorted(
        name
        for name, obj in globals().items()
        if not name.startswith("_")
        and (name.isupper() or inspect.isclass(obj) or inspect.isfunction(obj))
        and getattr(obj, "__module__", __name__) == __name__
    )
)
