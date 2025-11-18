# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Shared typing aliases for callbacks and common callable shapes.

This module centralizes `Callable[...]` type aliases to avoid repeating
signatures across the code base and to satisfy mypy strict rules.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine, Mapping
from datetime import datetime
from typing import Any, Protocol, TypeAlias

type ParamType = bool | int | float | str | None

# Generic zero-argument callback that returns nothing
ZeroArgCallback: TypeAlias = Callable[[], None]

# Unregister callbacks used throughout the project either return a zero-arg
# callback to unregister or None when registration did not occur.
UnregisterCallback: TypeAlias = ZeroArgCallback | None

# Device- and channel-scoped callbacks
DeviceRemovedCallback: TypeAlias = ZeroArgCallback
DeviceUpdatedCallback: TypeAlias = ZeroArgCallback
FirmwareUpdateCallback: TypeAlias = ZeroArgCallback
LinkPeerChangedCallback: TypeAlias = ZeroArgCallback

# Data point update callbacks may accept various keyword arguments depending on
# the data point type, hence we keep them variadic.
DataPointUpdatedCallback: TypeAlias = Callable[..., None]

# Common async/sync callable shapes
# Factory that returns a coroutine that resolves to None
AsyncTaskFactory: TypeAlias = Callable[[], Coroutine[Any, Any, None]]
# Factory that returns a coroutine with arbitrary result type
AsyncTaskFactoryAny: TypeAlias = Callable[[], Coroutine[Any, Any, Any]]
# Coroutine with any send/throw types and arbitrary result
CoroutineAny: TypeAlias = Coroutine[Any, Any, Any]
# Generic sync callable that returns Any
CallableAny: TypeAlias = Callable[..., Any]
# Generic sync callable that returns None
CallableNone: TypeAlias = Callable[..., None]

# Service method callable and mapping used by DataPoints and decorators
ServiceMethod: TypeAlias = Callable[..., Any]
ServiceMethodMap: TypeAlias = Mapping[str, ServiceMethod]

# Factory used by custom data point creation (make_ce_func)
CustomDataPointFactory: TypeAlias = Callable[..., None]


class DataPointEventCallback(Protocol):
    """Protocol for backend parameter callback."""

    async def __call__(self, *, value: Any, received_at: datetime) -> None: ...  # noqa: D102


# Sysvar event callbacks (hub/sysvar) vary by implementation; keep variadic
SysvarEventCallback: TypeAlias = Callable[..., Coroutine[Any, Any, None]]
