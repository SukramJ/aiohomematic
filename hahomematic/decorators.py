"""Common Decorators used within hahomematic."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextvars import Token
from datetime import datetime
from functools import wraps
import logging
from typing import Any, Final, ParamSpec, TypeVar, cast

from hahomematic.context import IN_SERVICE_VAR
from hahomematic.exceptions import BaseHomematicException
from hahomematic.support import reduce_args

P = ParamSpec("P")
T = TypeVar("T")

_LOGGER: Final = logging.getLogger(__name__)


def service(
    log_level: int = logging.ERROR,
    re_raise: bool = True,
    no_raise_return: Any = None,
    measure_performance: bool = False,
) -> Callable:
    """Mark function as service call and log exceptions."""

    def service_decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        """Decorate service."""

        do_measure_performance = measure_performance and _LOGGER.isEnabledFor(level=logging.DEBUG)

        @wraps(func)
        async def service_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            """Wrap service to log exception."""
            if do_measure_performance:
                start = datetime.now()

            token: Token | None = None
            if not IN_SERVICE_VAR.get():
                token = IN_SERVICE_VAR.set(True)
            try:
                return_value = await func(*args, **kwargs)
            except BaseHomematicException as bhe:
                if token:
                    IN_SERVICE_VAR.reset(token)
                if not IN_SERVICE_VAR.get() and log_level > logging.NOTSET:
                    message = f"{func.__name__.upper()} failed: {reduce_args(args=bhe.args)}"
                    logging.getLogger(args[0].__module__).log(
                        level=log_level,
                        msg=message,
                    )
                if re_raise:
                    raise
                return cast(T, no_raise_return)
            else:
                if token:
                    IN_SERVICE_VAR.reset(token)
                return return_value
            finally:
                if do_measure_performance:
                    _log_performance_message(func, start, *args, **kwargs)

        setattr(service_wrapper, "ha_service", True)
        return service_wrapper

    return service_decorator


def _log_performance_message(func: Callable, start: datetime, *args: P.args, **kwargs: P.kwargs) -> None:
    """Log the performance message."""
    delta = (datetime.now() - start).total_seconds()
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
    """Get all methods decorated with the "bind_collector" or "service_call"  decorator."""
    return {
        name: getattr(obj, name)
        for name in dir(obj)
        if not name.startswith("_") and callable(getattr(obj, name)) and hasattr(getattr(obj, name), "ha_service")
    }


def measure_execution_time[_CallableT: Callable[..., Any]](func: _CallableT) -> _CallableT:
    """Decorate function to measure the function execution time."""

    is_enabled = _LOGGER.isEnabledFor(level=logging.DEBUG)

    @wraps(func)
    async def async_measure_wrapper(*args: Any, **kwargs: Any) -> Any:
        """Wrap method."""
        if is_enabled:
            start = datetime.now()
        try:
            return await func(*args, **kwargs)
        finally:
            if is_enabled:
                _log_performance_message(func, start, *args, **kwargs)

    @wraps(func)
    def measure_wrapper(*args: Any, **kwargs: Any) -> Any:
        """Wrap method."""
        if is_enabled:
            start = datetime.now()
        try:
            return func(*args, **kwargs)
        finally:
            if is_enabled:
                _log_performance_message(func, start, *args, **kwargs)

    if asyncio.iscoroutinefunction(func):
        return async_measure_wrapper  # type: ignore[return-value]
    return measure_wrapper  # type: ignore[return-value]
