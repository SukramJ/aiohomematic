# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Dynamic store used at runtime by the central unit and clients.

This package provides short-lived, in-memory caches that support robust and efficient
communication with Homematic interfaces.

Package structure
-----------------
- command: CommandCache for tracking sent commands
- details: DeviceDetailsCache for device metadata
- data: CentralDataCache for parameter values
- ping_pong: PingPongCache for connection health monitoring

Key behaviors
-------------
- Caches are intentionally ephemeral and cleared/aged according to rules
- Memory footprint is kept predictable while improving responsiveness

Public API
----------
- CommandCache: Tracks recently sent commands per data point
- DeviceDetailsCache: Device names, rooms, functions, interfaces
- CentralDataCache: Stores recently fetched parameter values
- PingPongCache: Connection health monitoring via ping/pong
"""

from __future__ import annotations

from aiohomematic.store.dynamic.command import CommandCache
from aiohomematic.store.dynamic.data import CentralDataCache
from aiohomematic.store.dynamic.details import DeviceDetailsCache
from aiohomematic.store.dynamic.ping_pong import PingPongCache

__all__ = [
    "CentralDataCache",
    "CommandCache",
    "DeviceDetailsCache",
    "PingPongCache",
]
