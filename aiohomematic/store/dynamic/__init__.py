# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Dynamic store used at runtime by the central unit and clients.

This package provides short-lived, in-memory stores that support robust and efficient
communication with Homematic interfaces.

Package structure
-----------------
- command: CommandTracker for tracking sent commands
- details: DeviceDetailsCache for device metadata
- data: CentralDataCache for parameter values
- ping_pong: PingPongTracker for connection health monitoring

Key behaviors
-------------
- Stores are intentionally ephemeral and cleared/aged according to rules
- Memory footprint is kept predictable while improving responsiveness

Public API
----------
- CommandTracker: Tracks recently sent commands per data point
- DeviceDetailsCache: Device names, rooms, functions, interfaces
- CentralDataCache: Stores recently fetched parameter values
- PingPongTracker: Connection health monitoring via ping/pong
"""

from __future__ import annotations

from aiohomematic.store.dynamic.command import CommandTracker
from aiohomematic.store.dynamic.data import CentralDataCache
from aiohomematic.store.dynamic.details import DeviceDetailsCache
from aiohomematic.store.dynamic.ping_pong import PingPongTracker

__all__ = [
    # Caches
    "CentralDataCache",
    "DeviceDetailsCache",
    # Trackers
    "CommandTracker",
    "PingPongTracker",
]
