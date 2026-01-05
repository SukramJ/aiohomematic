# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Backend capabilities dataclass.

Consolidates all supports_* flags into a single immutable structure,
replacing the 20+ properties spread across client classes.

Public API
----------
- BackendCapabilities: Frozen dataclass with capability flags
- CCU_CAPABILITIES: Default capabilities for CCU backend
- JSON_CCU_CAPABILITIES: Default capabilities for CCU-Jack backend
- HOMEGEAR_CAPABILITIES: Default capabilities for Homegear backend
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

__all__ = [
    "BackendCapabilities",
    "CCU_CAPABILITIES",
    "HOMEGEAR_CAPABILITIES",
    "JSON_CCU_CAPABILITIES",
]


@dataclass(frozen=True, slots=True)
class BackendCapabilities:
    """
    Immutable capability flags for a backend.

    Consolidates the supports_* properties from ClientCCU, ClientJsonCCU,
    and ClientHomegear into a single dataclass. Backends declare their
    capabilities at initialization; clients expose them via the
    `capabilities` property.
    """

    # Device Operations
    supports_device_firmware_update: bool = False
    supports_firmware_update_trigger: bool = False
    supports_firmware_updates: bool = False
    supports_linking: bool = False
    supports_value_usage_reporting: bool = False

    # Metadata Operations
    supports_functions: bool = False
    supports_rooms: bool = False
    supports_metadata: bool = False
    supports_rename: bool = False
    supports_rega_id_lookup: bool = False
    supports_service_messages: bool = False
    supports_system_update_info: bool = False
    supports_inbox_devices: bool = False
    supports_install_mode: bool = False

    # Programs & System Variables
    supports_programs: bool = False

    # Backup
    supports_backup: bool = False

    # Connection
    supports_ping_pong: bool = False
    supports_push_updates: bool = True
    supports_rpc_callback: bool = True


# Default capability sets for each backend type.
# These can be adjusted at runtime based on interface type or system info.

CCU_CAPABILITIES: Final = BackendCapabilities(
    supports_device_firmware_update=True,
    supports_firmware_update_trigger=True,
    supports_firmware_updates=True,
    supports_linking=True,
    supports_value_usage_reporting=True,
    supports_functions=True,
    supports_rooms=True,
    supports_metadata=True,
    supports_rename=True,
    supports_rega_id_lookup=True,
    supports_service_messages=True,
    supports_system_update_info=True,
    supports_inbox_devices=True,
    supports_install_mode=True,
    supports_programs=True,
    supports_backup=True,
    supports_ping_pong=True,
    supports_push_updates=True,
    supports_rpc_callback=True,
)

JSON_CCU_CAPABILITIES: Final = BackendCapabilities(
    supports_device_firmware_update=False,
    supports_firmware_update_trigger=False,
    supports_firmware_updates=False,
    supports_linking=False,
    supports_value_usage_reporting=False,
    supports_functions=False,
    supports_rooms=False,
    supports_metadata=False,
    supports_rename=False,
    supports_rega_id_lookup=False,
    supports_service_messages=False,
    supports_system_update_info=False,
    supports_inbox_devices=False,
    supports_install_mode=False,
    supports_programs=False,
    supports_backup=False,
    supports_ping_pong=False,
    supports_push_updates=True,
    supports_rpc_callback=False,
)

HOMEGEAR_CAPABILITIES: Final = BackendCapabilities(
    supports_device_firmware_update=False,
    supports_firmware_update_trigger=False,
    supports_firmware_updates=False,
    supports_linking=False,
    supports_value_usage_reporting=False,
    supports_functions=False,
    supports_rooms=False,
    supports_metadata=False,
    supports_rename=False,
    supports_rega_id_lookup=False,
    supports_service_messages=False,
    supports_system_update_info=False,
    supports_inbox_devices=False,
    supports_install_mode=False,
    supports_programs=False,
    supports_backup=False,
    supports_ping_pong=False,
    supports_push_updates=True,
    supports_rpc_callback=True,
)
