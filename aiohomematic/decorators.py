# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Common Decorators used within aiohomematic.

Public API of this module is defined by __all__.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
import inspect
import logging
from time import monotonic
from typing import Any, Final, cast, overload
from weakref import WeakKeyDictionary

from aiohomematic.context import IN_SERVICE_VAR
from aiohomematic.exceptions import BaseHomematicException
from aiohomematic.support import LogContextMixin, log_boundary_error
from aiohomematic.type_aliases import CallableAny, ServiceMethodMap

_LOGGER_PERFORMANCE: Final = logging.getLogger(f"{__package__}.performance")

# Cache for per-class service call method names to avoid repeated scans.
# Structure: {cls: (method_name1, method_name2, ...)}
_SERVICE_CALLS_CACHE: WeakKeyDictionary[type, tuple[str, ...]] = WeakKeyDictionary()


@overload
def inspector[**P, R](
    func: Callable[P, R],
    /,
    *,
    log_level: int = ...,
    re_raise: bool = ...,
    no_raise_return: Any = ...,
    measure_performance: bool = ...,
) -> Callable[P, R]: ...


@overload
def inspector[**P, R](
    func: None = ...,
    /,
    *,
    log_level: int = ...,
    re_raise: bool = ...,
    no_raise_return: Any = ...,
    measure_performance: bool = ...,
) -> Callable[[Callable[P, R]], Callable[P, R]]: ...


def inspector[**P, R](  # noqa: C901
    func: Callable[P, R] | None = None,
    /,
    *,
    log_level: int = logging.ERROR,
    re_raise: bool = True,
    no_raise_return: Any = None,
    measure_performance: bool = False,
) -> Callable[[Callable[P, R]], Callable[P, R]] | Callable[P, R]:
    """
    Support with exception handling and performance measurement.

    A decorator that works for both synchronous and asynchronous functions,
    providing common functionality such as exception handling and performance measurement.

    Can be used both with and without parameters:
      - @inspector
      - @inspector(log_level=logging.ERROR, re_raise=True, ...)

    Args:
        func: The function to decorate when used without parameters.
        log_level: Logging level for exceptions.
        re_raise: Whether to re-raise exceptions.
        no_raise_return: Value to return when an exception is caught and not re-raised.
        measure_performance: Whether to measure function execution time.

    Returns:
        Either the decorated function (when used without parameters) or
        a decorator that wraps sync or async functions (when used with parameters).

    """

    def create_wrapped_decorator(func: Callable[P, R]) -> Callable[P, R]:  # noqa: C901
        """
        Decorate function for wrapping sync or async functions.

        Args:
            func: The function to decorate.

        Returns:
            The decorated function.

        """

        def handle_exception(
            exc: Exception,
            func: CallableAny,
            is_sub_service_call: bool,
            is_homematic: bool,
            context_obj: Any | None,
        ) -> R:
            """Handle exceptions for decorated functions with structured logging."""
            if not is_sub_service_call and log_level > logging.NOTSET:
                logger = logging.getLogger(func.__module__)
                log_context = context_obj.log_context if isinstance(context_obj, LogContextMixin) else None
                # Reuse centralized boundary logging to ensure consistent 'extra' structure
                log_boundary_error(
                    logger=logger,
                    boundary="service",
                    action=func.__name__,
                    err=exc,
                    level=log_level,
                    log_context=log_context,
                )
            if re_raise or not is_homematic:
                raise exc
            return cast(R, no_raise_return)

        @wraps(func)
        def wrap_sync_function(*args: P.args, **kwargs: P.kwargs) -> R:
            """Wrap sync functions with minimized per-call overhead."""

            # Fast-path: avoid logger check and time call unless explicitly enabled
            start_needed = measure_performance and _LOGGER_PERFORMANCE.isEnabledFor(level=logging.DEBUG)
            start = monotonic() if start_needed else None

            # Avoid repeated ContextVar.get() calls; only set/reset when needed
            was_in_service = IN_SERVICE_VAR.get()
            token = IN_SERVICE_VAR.set(True) if not was_in_service else None
            context_obj = args[0] if args else None
            try:
                return_value: R = func(*args, **kwargs)
            except BaseHomematicException as bhexc:
                if token is not None:
                    IN_SERVICE_VAR.reset(token)
                return handle_exception(
                    exc=bhexc,
                    func=func,
                    is_sub_service_call=was_in_service,
                    is_homematic=True,
                    context_obj=context_obj,
                )
            except Exception as exc:
                if token is not None:
                    IN_SERVICE_VAR.reset(token)
                return handle_exception(
                    exc=exc,
                    func=func,
                    is_sub_service_call=was_in_service,
                    is_homematic=False,
                    context_obj=context_obj,
                )
            else:
                if token is not None:
                    IN_SERVICE_VAR.reset(token)
                return return_value
            finally:
                if start is not None:
                    _log_performance_message(func, start, *args, **kwargs)

        @wraps(func)
        async def wrap_async_function(*args: P.args, **kwargs: P.kwargs) -> R:
            """Wrap async functions with minimized per-call overhead."""

            start_needed = measure_performance and _LOGGER_PERFORMANCE.isEnabledFor(level=logging.DEBUG)
            start = monotonic() if start_needed else None

            was_in_service = IN_SERVICE_VAR.get()
            token = IN_SERVICE_VAR.set(True) if not was_in_service else None
            context_obj = args[0] if args else None
            try:
                return_value = await func(*args, **kwargs)  # type: ignore[misc]
            except BaseHomematicException as bhexc:
                if token is not None:
                    IN_SERVICE_VAR.reset(token)
                return handle_exception(
                    exc=bhexc,
                    func=func,
                    is_sub_service_call=was_in_service,
                    is_homematic=True,
                    context_obj=context_obj,
                )
            except Exception as exc:
                if token is not None:
                    IN_SERVICE_VAR.reset(token)
                return handle_exception(
                    exc=exc,
                    func=func,
                    is_sub_service_call=was_in_service,
                    is_homematic=False,
                    context_obj=context_obj,
                )
            else:
                if token is not None:
                    IN_SERVICE_VAR.reset(token)
                return cast(R, return_value)
            finally:
                if start is not None:
                    _log_performance_message(func, start, *args, **kwargs)

        # Check if the function is a coroutine or not and select the appropriate wrapper
        if inspect.iscoroutinefunction(func):
            setattr(wrap_async_function, "ha_service", True)
            return wrap_async_function  # type: ignore[return-value]
        setattr(wrap_sync_function, "ha_service", True)
        return wrap_sync_function

    # If used without parameters: @inspector
    if func is not None:
        return create_wrapped_decorator(func)

    # If used with parameters: @inspector(...)
    return create_wrapped_decorator


def _log_performance_message[**P](func: Callable[P, Any], start: float, *args: P.args, **kwargs: P.kwargs) -> None:
    delta = monotonic() - start
    caller = str(args[0]) if len(args) > 0 else ""

    iface: str = ""
    if interface := str(kwargs.get("interface", "")):
        iface = f"interface: {interface}"
    if interface_id := kwargs.get("interface_id", ""):
        iface = f"interface_id: {interface_id}"

    message = f"Execution of {func.__name__.upper()} took {delta}s from {caller}"
    if iface:
        message += f"/{iface}"

    _LOGGER_PERFORMANCE.info(message)


def get_service_calls(obj: object) -> ServiceMethodMap:
    """
    Get all methods decorated with the service decorator (ha_service attribute).

    To reduce overhead, we cache the discovered method names per class using a WeakKeyDictionary.
    """
    cls = obj.__class__

    # Try cache first
    if (names := _SERVICE_CALLS_CACHE.get(cls)) is None:
        # Compute method names using class attributes to avoid creating bound methods during checks
        exclusions = {"service_methods", "service_method_names"}
        computed: list[str] = []
        for name in dir(cls):
            if name.startswith("_") or name in exclusions:
                continue
            try:
                # Check the attribute on the class (function/descriptor)
                attr = getattr(cls, name)
            except Exception:
                continue
            # Only consider callables exposed on the instance and marked with ha_service on the function/wrapper
            if callable(getattr(obj, name, None)) and hasattr(attr, "ha_service"):
                computed.append(name)
        names = tuple(computed)
        _SERVICE_CALLS_CACHE[cls] = names

    # Return a mapping of bound methods for this instance
    return {name: getattr(obj, name) for name in names}


def measure_execution_time[CallableT: CallableAny](func: CallableT) -> CallableT:
    """Decorate function to measure the function execution time."""

    @wraps(func)
    async def async_measure_wrapper(*args: Any, **kwargs: Any) -> Any:
        """Wrap method."""

        start = monotonic() if _LOGGER_PERFORMANCE.isEnabledFor(level=logging.DEBUG) else None
        try:
            return await func(*args, **kwargs)
        finally:
            if start:
                _log_performance_message(func, start, *args, **kwargs)

    @wraps(func)
    def measure_wrapper(*args: Any, **kwargs: Any) -> Any:
        """Wrap method."""

        start = monotonic() if _LOGGER_PERFORMANCE.isEnabledFor(level=logging.DEBUG) else None
        try:
            return func(*args, **kwargs)
        finally:
            if start:
                _log_performance_message(func, start, *args, **kwargs)

    if inspect.iscoroutinefunction(func):
        return cast(CallableT, async_measure_wrapper)
    return cast(CallableT, measure_wrapper)


# Define public API for this module
__all__ = tuple(
    sorted(
        name
        for name, obj in globals().items()
        if not name.startswith("_")
        and (inspect.isfunction(obj) or inspect.isclass(obj))
        and getattr(obj, "__module__", __name__) == __name__
    )
)
