# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Coordinator sub-package for central orchestration components.

This package contains the coordinator classes that manage specific aspects
of the central unit's functionality:

- CacheCoordinator: Cache management (device descriptions, paramsets, data)
- ClientCoordinator: Client lifecycle and connection management
- ConnectionRecoveryCoordinator: Unified connection recovery and retry management
- DeviceCoordinator: Device discovery and creation
- EventCoordinator: Event handling and system event processing
- HubCoordinator: Hub-level entities (programs, sysvars, install mode)

Public API of this module is defined by __all__.
"""

from __future__ import annotations

from aiohomematic.central.coordinators.cache import CacheCoordinator
from aiohomematic.central.coordinators.client import ClientCoordinator
from aiohomematic.central.coordinators.connection_recovery import ConnectionRecoveryCoordinator
from aiohomematic.central.coordinators.device import DeviceCoordinator
from aiohomematic.central.coordinators.event import EventCoordinator, SystemEventArgs
from aiohomematic.central.coordinators.hub import HubCoordinator

__all__ = [
    # Coordinators
    "CacheCoordinator",
    "ClientCoordinator",
    "ConnectionRecoveryCoordinator",
    "DeviceCoordinator",
    "EventCoordinator",
    "HubCoordinator",
    # Types
    "SystemEventArgs",
]
