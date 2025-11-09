# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Decorators for central used within aiohomematic."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from functools import wraps
import inspect
import logging
from typing import Any, Final, cast

from aiohomematic import central as hmcu, client as hmcl, i18n
from aiohomematic.central import rpc_server as rpc
from aiohomematic.const import BackendSystemEvent
from aiohomematic.exceptions import AioHomematicException
from aiohomematic.support import extract_exc_args
from aiohomematic.type_aliases import CallableAny, CallableNone

_LOGGER: Final = logging.getLogger(__name__)
_INTERFACE_ID: Final = "interface_id"
_CHANNEL_ADDRESS: Final = "channel_address"
_PARAMETER: Final = "parameter"
_VALUE: Final = "value"


def callback_backend_system(system_event: BackendSystemEvent) -> Callable[[CallableAny], CallableAny]:
    """Check if backend_system_callback is set and call it AFTER original function."""

    def decorator_backend_system_callback[**P, R](
        func: Callable[P, R | Awaitable[R]],
    ) -> Callable[P, R | Awaitable[R]]:
        """Decorate callback system events."""

        @wraps(func)
        async def async_wrapper_backend_system_callback(*args: P.args, **kwargs: P.kwargs) -> R:
            """Wrap async callback system events."""
            return_value = cast(R, await func(*args, **kwargs))  # type: ignore[misc]
            await _exec_backend_system_callback(*args, **kwargs)
            return return_value

        @wraps(func)
        def wrapper_backend_system_callback(*args: P.args, **kwargs: P.kwargs) -> R:
            """Wrap callback system events."""
            return_value = cast(R, func(*args, **kwargs))
            try:
                unit = args[0]
                central: hmcu.CentralUnit | None = None
                if isinstance(unit, hmcu.CentralUnit):
                    central = unit
                if central is None and isinstance(unit, rpc.RPCFunctions):
                    central = unit.get_central(interface_id=str(args[1]))
                if central:
                    central.looper.create_task(
                        target=lambda: _exec_backend_system_callback(*args, **kwargs),
                        name="wrapper_backend_system_callback",
                    )
            except Exception as exc:
                _LOGGER.warning(
                    i18n.tr(
                        "exception.central.decorators.backend_system_callback.identify_central_failed",
                        reason=extract_exc_args(exc=exc),
                    )
                )
            return return_value

        async def _exec_backend_system_callback(*args: Any, **kwargs: Any) -> None:
            """Execute the callback for a system event."""

            if not ((len(args) > 1 and not kwargs) or (len(args) == 1 and kwargs)):
                _LOGGER.error(  # i18n-log: ignore
                    "EXEC_BACKEND_SYSTEM_CALLBACK failed: *args not supported for callback_system_event"
                )
            try:
                args = args[1:]
                interface_id: str = args[0] if len(args) > 0 else str(kwargs[_INTERFACE_ID])
                if client := hmcl.get_client(interface_id=interface_id):
                    client.modified_at = datetime.now()
                    client.central.emit_backend_system_callback(system_event=system_event, **kwargs)
            except Exception as exc:  # pragma: no cover
                _LOGGER.error(  # i18n-log: ignore
                    "EXEC_BACKEND_SYSTEM_CALLBACK failed: Unable to reduce kwargs for backend_system_callback"
                )
                raise AioHomematicException(
                    i18n.tr(
                        "exception.central.decorators.backend_system_callback.args_exception",
                        reason=extract_exc_args(exc=exc),
                    )
                ) from exc

        if inspect.iscoroutinefunction(func):
            return async_wrapper_backend_system_callback
        return wrapper_backend_system_callback

    return decorator_backend_system_callback


def callback_event[**P, R](func: Callable[P, R]) -> Callable[P, R | Awaitable[R]]:
    """Check if event_callback is set and call it AFTER original function."""

    def _exec_event_callback(*args: Any, **kwargs: Any) -> None:
        """Execute the callback for a data_point event."""
        try:
            # Expected signature: (self, interface_id, channel_address, parameter, value)
            interface_id: str
            if len(args) > 1:
                interface_id = cast(str, args[1])
                channel_address = cast(str, args[2])
                parameter = cast(str, args[3])
                value = args[4] if len(args) > 4 else kwargs.get(_VALUE)
            else:
                interface_id = cast(str, kwargs[_INTERFACE_ID])
                channel_address = cast(str, kwargs[_CHANNEL_ADDRESS])
                parameter = cast(str, kwargs[_PARAMETER])
                value = kwargs[_VALUE]

            if client := hmcl.get_client(interface_id=interface_id):
                client.modified_at = datetime.now()
                client.central.emit_backend_parameter_callback(
                    interface_id=interface_id, channel_address=channel_address, parameter=parameter, value=value
                )
        except Exception as exc:  # pragma: no cover
            _LOGGER.error(  # i18n-log: ignore
                "EXEC_DATA_POINT_EVENT_CALLBACK failed: Unable to process args/kwargs for event_callback"
            )
            raise AioHomematicException(
                i18n.tr(
                    "exception.central.decorators.event_callback.args_exception",
                    reason=extract_exc_args(exc=exc),
                )
            ) from exc

    def _schedule_or_exec(*args: Any, **kwargs: Any) -> None:
        """Schedule event callback on central looper when possible, else execute inline."""
        try:
            # Prefer scheduling on the CentralUnit looper when available to avoid blocking hot path
            unit = args[0]
            if isinstance(unit, hmcu.CentralUnit):
                unit.looper.create_task(
                    target=lambda: _async_wrap_sync(_exec_event_callback, *args, **kwargs),
                    name="wrapper_event_callback",
                )
                return
        except Exception:
            # Fall through to inline execution on any error
            pass
        _exec_event_callback(*args, **kwargs)

    @wraps(func)
    async def async_wrapper_event_callback(*args: P.args, **kwargs: P.kwargs) -> R:
        """Wrap async callback events."""
        return_value = cast(R, await func(*args, **kwargs))  # type: ignore[misc]
        _schedule_or_exec(*args, **kwargs)
        return return_value

    @wraps(func)
    def wrapper_event_callback(*args: P.args, **kwargs: P.kwargs) -> R:
        """Wrap sync callback events."""
        return_value = func(*args, **kwargs)
        _schedule_or_exec(*args, **kwargs)
        return return_value

    # Helper to create a trivial coroutine from a sync callable
    async def _async_wrap_sync(cb: CallableNone, *a: Any, **kw: Any) -> None:
        cb(*a, **kw)

    if inspect.iscoroutinefunction(func):
        return async_wrapper_event_callback
    return wrapper_event_callback
