# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Shared typing aliases for handlers and common callable shapes.

This module centralizes `Callable[...]` type aliases to avoid repeating
signatures across the code base and to satisfy mypy strict rules.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine, Mapping
from typing import Any, TypeAlias

type ParamType = bool | int | float | str | None

# Generic zero-argument handler that returns nothing
ZeroArgHandler: TypeAlias = Callable[[], None]

# Unsubscribe callback - used as return type for subscription methods
# Single source of truth (formerly duplicated in api.py, central/__init__.py, event_bus.py)
UnsubscribeCallback: TypeAlias = ZeroArgHandler

# Device- and channel-scoped handlers
DeviceRemovedHandler: TypeAlias = ZeroArgHandler
DeviceUpdatedHandler: TypeAlias = ZeroArgHandler
FirmwareUpdateHandler: TypeAlias = ZeroArgHandler
LinkPeerChangedHandler: TypeAlias = ZeroArgHandler

# Data point update handlers may accept various keyword arguments depending on
# the data point type, hence we keep them variadic.
DataPointUpdatedHandler: TypeAlias = Callable[..., None]

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
