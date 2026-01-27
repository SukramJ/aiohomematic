# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Backend capabilities dataclass.

Consolidates all capability flags into a single immutable structure,
replacing the 20+ properties spread across client classes.

Public API
----------
- BackendCapabilities: Frozen dataclass with capability flags
- CCU_CAPABILITIES: Default capabilities for CCU backend
- JSON_CCU_CAPABILITIES: Default capabilities for CCU-Jack backend
- HOMEGEAR_CAPABILITIES: Default capabilities for Homegear backend
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict

__all__ = [
    "BackendCapabilities",
    "CCU_CAPABILITIES",
    "HOMEGEAR_CAPABILITIES",
    "JSON_CCU_CAPABILITIES",
]


class BackendCapabilities(BaseModel):
    """
    Immutable capability flags for a backend.

    Consolidates the capability properties from ClientCCU, ClientJsonCCU,
    and ClientHomegear into a single dataclass. Backends declare their
    capabilities at initialization; clients expose them via the
    `capabilities` property.
    """

    model_config = ConfigDict(frozen=True)

    # Device Operations
    device_firmware_update: bool = False
    firmware_update_trigger: bool = False
    firmware_updates: bool = False
    linking: bool = False
    value_usage_reporting: bool = False

    # Metadata Operations
    functions: bool = False
    rooms: bool = False
    metadata: bool = False
    rename: bool = False
    rega_id_lookup: bool = False
    service_messages: bool = False
    system_update_info: bool = False
    inbox_devices: bool = False
    install_mode: bool = False

    # Programs & System Variables
    programs: bool = False

    # Backup
    backup: bool = False

    # Connection
    ping_pong: bool = False
    push_updates: bool = True
    rpc_callback: bool = True


# Default capability sets for each backend type.
# These can be adjusted at runtime based on interface type or system info.

CCU_CAPABILITIES: Final = BackendCapabilities(
    device_firmware_update=True,
    firmware_update_trigger=True,
    firmware_updates=True,
    linking=True,
    value_usage_reporting=True,
    functions=True,
    rooms=True,
    metadata=True,
    rename=True,
    rega_id_lookup=True,
    service_messages=True,
    system_update_info=True,
    inbox_devices=True,
    install_mode=True,
    programs=True,
    backup=True,
    ping_pong=True,
    push_updates=True,
    rpc_callback=True,
)

JSON_CCU_CAPABILITIES: Final = BackendCapabilities(
    device_firmware_update=False,
    firmware_update_trigger=False,
    firmware_updates=False,
    linking=False,
    value_usage_reporting=False,
    functions=False,
    rooms=False,
    metadata=False,
    rename=False,
    rega_id_lookup=False,
    service_messages=False,
    system_update_info=False,
    inbox_devices=False,
    install_mode=False,
    programs=False,
    backup=False,
    ping_pong=False,
    push_updates=True,
    rpc_callback=False,
)

HOMEGEAR_CAPABILITIES: Final = BackendCapabilities(
    device_firmware_update=False,
    firmware_update_trigger=False,
    firmware_updates=False,
    linking=False,
    value_usage_reporting=False,
    functions=False,
    rooms=False,
    metadata=False,
    rename=False,
    rega_id_lookup=False,
    service_messages=False,
    system_update_info=False,
    inbox_devices=False,
    install_mode=False,
    programs=False,
    backup=False,
    ping_pong=False,
    push_updates=True,
    rpc_callback=True,
)
