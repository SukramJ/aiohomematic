# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025 Daniel Perna, SukramJ
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
from typing import Any, Final, ParamSpec, TypeVar, cast
from weakref import WeakKeyDictionary

from aiohomematic.context import IN_SERVICE_VAR
from aiohomematic.exceptions import BaseHomematicException
from aiohomematic.support import build_log_context_from_obj, extract_exc_args

P = ParamSpec("P")
R = TypeVar("R")

_LOGGER: Final = logging.getLogger(__name__)

# Cache for per-class service call method names to avoid repeated scans.
# Structure: {cls: (method_name1, method_name2, ...)}
_SERVICE_CALLS_CACHE: WeakKeyDictionary[type, tuple[str, ...]] = WeakKeyDictionary()


def inspector(  # noqa: C901
    log_level: int = logging.ERROR,
    re_raise: bool = True,
    no_raise_return: Any = None,
    measure_performance: bool = False,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Support with exception handling and performance measurement.

    A decorator that works for both synchronous and asynchronous functions,
    providing common functionality such as exception handling and performance measurement.

    Args:
        log_level: Logging level for exceptions.
        re_raise: Whether to re-raise exceptions.
        no_raise_return: Value to return when an exception is caught and not re-raised.
        measure_performance: Whether to measure function execution time.

    Returns:
        A decorator that wraps sync or async functions.

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
            exc: Exception, func: Callable, is_sub_service_call: bool, is_homematic: bool, context_obj: Any | None
        ) -> R:
            """Handle exceptions for decorated functions with structured logging."""
            if not is_sub_service_call and log_level > logging.NOTSET:
                logger = logging.getLogger(func.__module__)
                extra = {
                    "err_type": exc.__class__.__name__,
                    "err": extract_exc_args(exc=exc),
                    "function": func.__name__,
                    **build_log_context_from_obj(context_obj),
                }
                if log_level >= logging.ERROR:
                    logger.exception("service_error", extra=extra)
                else:
                    logger.log(level=log_level, msg="service_error", extra=extra)
            if re_raise or not is_homematic:
                raise exc
            return cast(R, no_raise_return)

        @wraps(func)
        def wrap_sync_function(*args: P.args, **kwargs: P.kwargs) -> R:
            """Wrap sync functions."""

            start = monotonic() if measure_performance and _LOGGER.isEnabledFor(level=logging.DEBUG) else None
            token = IN_SERVICE_VAR.set(True) if not IN_SERVICE_VAR.get() else None
            try:
                return_value: R = func(*args, **kwargs)
            except BaseHomematicException as bhexc:
                if token:
                    IN_SERVICE_VAR.reset(token)
                return handle_exception(
                    exc=bhexc,
                    func=func,
                    is_sub_service_call=IN_SERVICE_VAR.get(),
                    is_homematic=True,
                    context_obj=(args[0] if args else None),
                )
            except Exception as exc:
                if token:
                    IN_SERVICE_VAR.reset(token)
                return handle_exception(
                    exc=exc,
                    func=func,
                    is_sub_service_call=IN_SERVICE_VAR.get(),
                    is_homematic=False,
                    context_obj=(args[0] if args else None),
                )
            else:
                if token:
                    IN_SERVICE_VAR.reset(token)
                return return_value
            finally:
                if start:
                    _log_performance_message(func, start, *args, **kwargs)

        @wraps(func)
        async def wrap_async_function(*args: P.args, **kwargs: P.kwargs) -> R:
            """Wrap async functions."""

            start = monotonic() if measure_performance and _LOGGER.isEnabledFor(level=logging.DEBUG) else None
            token = IN_SERVICE_VAR.set(True) if not IN_SERVICE_VAR.get() else None
            try:
                return_value = await func(*args, **kwargs)  # type: ignore[misc]  # Await the async call
            except BaseHomematicException as bhexc:
                if token:
                    IN_SERVICE_VAR.reset(token)
                return handle_exception(
                    exc=bhexc,
                    func=func,
                    is_sub_service_call=IN_SERVICE_VAR.get(),
                    is_homematic=True,
                    context_obj=(args[0] if args else None),
                )
            except Exception as exc:
                if token:
                    IN_SERVICE_VAR.reset(token)
                return handle_exception(
                    exc=exc,
                    func=func,
                    is_sub_service_call=IN_SERVICE_VAR.get(),
                    is_homematic=False,
                    context_obj=(args[0] if args else None),
                )
            else:
                if token:
                    IN_SERVICE_VAR.reset(token)
                return cast(R, return_value)
            finally:
                if start:
                    _log_performance_message(func, start, *args, **kwargs)

        # Check if the function is a coroutine or not and select the appropriate wrapper
        if inspect.iscoroutinefunction(func):
            setattr(wrap_async_function, "ha_service", True)
            return wrap_async_function  # type: ignore[return-value]
        setattr(wrap_sync_function, "ha_service", True)
        return wrap_sync_function

    return create_wrapped_decorator


def _log_performance_message(func: Callable, start: float, *args: P.args, **kwargs: P.kwargs) -> None:  # type: ignore[valid-type]
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

    _LOGGER.info(message)


def get_service_calls(obj: object) -> dict[str, Callable]:
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


def measure_execution_time[CallableT: Callable[..., Any]](func: CallableT) -> CallableT:
    """Decorate function to measure the function execution time."""

    @wraps(func)
    async def async_measure_wrapper(*args: Any, **kwargs: Any) -> Any:
        """Wrap method."""

        start = monotonic() if _LOGGER.isEnabledFor(level=logging.DEBUG) else None
        try:
            return await func(*args, **kwargs)
        finally:
            if start:
                _log_performance_message(func, start, *args, **kwargs)

    @wraps(func)
    def measure_wrapper(*args: Any, **kwargs: Any) -> Any:
        """Wrap method."""

        start = monotonic() if _LOGGER.isEnabledFor(level=logging.DEBUG) else None
        try:
            return func(*args, **kwargs)
        finally:
            if start:
                _log_performance_message(func, start, *args, **kwargs)

    if inspect.iscoroutinefunction(func):
        return async_measure_wrapper  # type: ignore[return-value]
    return measure_wrapper  # type: ignore[return-value]


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
