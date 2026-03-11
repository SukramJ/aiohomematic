# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Coordinator sub-package for central orchestration components.

This package contains the coordinator classes that manage specific aspects
of the central unit's functionality:

- CacheCoordinator: Cache management (device descriptions, paramsets, data)
- ClientCoordinator: Client lifecycle and connection management
- ConfigurationCoordinator: Device configuration facade (paramset read/write)
- ConnectionRecoveryCoordinator: Unified connection recovery and retry management
- DeviceCoordinator: Device discovery and creation
- EventCoordinator: Event handling and system event processing
- HubCoordinator: Hub-level entities (programs, sysvars, install mode)
- LinkCoordinator: Device link management facade (listing, discovery, creation, removal)

Public API of this module is defined by __all__.
"""

from aiohomematic.central.coordinators.cache import CacheCoordinator
from aiohomematic.central.coordinators.client import ClientCoordinator
from aiohomematic.central.coordinators.configuration import (
    ConfigurableDevice,
    ConfigurableDeviceChannel,
    ConfigurationCoordinator,
    CopyParamsetResult,
    MaintenanceData,
)
from aiohomematic.central.coordinators.connection_recovery import ConnectionRecoveryCoordinator
from aiohomematic.central.coordinators.device import DeviceCoordinator
from aiohomematic.central.coordinators.event import EventCoordinator, SystemEventArgs
from aiohomematic.central.coordinators.hub import HubCoordinator
from aiohomematic.central.coordinators.link import DeviceLink, LinkableChannel, LinkCoordinator

__all__ = [
    # Coordinators
    "CacheCoordinator",
    "ClientCoordinator",
    "ConfigurableDevice",
    "ConfigurableDeviceChannel",
    "ConfigurationCoordinator",
    "ConnectionRecoveryCoordinator",
    "CopyParamsetResult",
    "DeviceCoordinator",
    "EventCoordinator",
    "HubCoordinator",
    "LinkCoordinator",
    "MaintenanceData",
    # Types
    "DeviceLink",
    "LinkableChannel",
    "SystemEventArgs",
]
