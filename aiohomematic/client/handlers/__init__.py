"""
Handler classes for ClientCCU operations.

This package provides specialized handler classes that encapsulate specific
domains of client operations. Each handler focuses on a single responsibility,
reducing the complexity of the main client classes.

Handler classes
---------------
- DeviceOperationsHandler: Value read/write, paramset operations
- LinkManagementHandler: Device linking operations
- FirmwareHandler: Device and system firmware updates
- SystemVariableHandler: System variables CRUD
- ProgramHandler: Program execution and state management
- BackupHandler: Backup creation and download
- MetadataHandler: Metadata, renaming, rooms, functions, install mode
"""

from __future__ import annotations

from aiohomematic.client.handlers.backup import BackupHandler
from aiohomematic.client.handlers.device_ops import DeviceOperationsHandler
from aiohomematic.client.handlers.firmware import FirmwareHandler
from aiohomematic.client.handlers.link_mgmt import LinkManagementHandler
from aiohomematic.client.handlers.metadata import MetadataHandler
from aiohomematic.client.handlers.programs import ProgramHandler
from aiohomematic.client.handlers.sysvars import SystemVariableHandler

__all__ = [
    "BackupHandler",
    "DeviceOperationsHandler",
    "FirmwareHandler",
    "LinkManagementHandler",
    "MetadataHandler",
    "ProgramHandler",
    "SystemVariableHandler",
]
