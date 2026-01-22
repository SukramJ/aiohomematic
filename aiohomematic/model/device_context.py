# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Device context for dependency injection.

This module defines the DeviceContext dataclass that groups all 17 protocol
interfaces required by the Device class into a single immutable object.

Benefits of DeviceContext
-------------------------
- Reduces Device constructor parameters from 17 to 1
- Makes testing easier (single mock object)
- Improves IDE support and documentation
- Organizes dependencies into logical groups
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiohomematic.interfaces import (
        CentralInfoProtocol,
        ChannelLookupProtocol,
        ClientProviderProtocol,
        ConfigProviderProtocol,
        DataCacheProviderProtocol,
        DataPointProviderProtocol,
        DeviceDescriptionProviderProtocol,
        DeviceDetailsProviderProtocol,
        EventBusProviderProtocol,
        EventPublisherProtocol,
        EventSubscriptionManagerProtocol,
        FileOperationsProtocol,
        ParameterVisibilityProviderProtocol,
        ParamsetDescriptionProviderProtocol,
        TaskSchedulerProtocol,
    )
    from aiohomematic.interfaces.central import FirmwareDataRefresherProtocol


@dataclass(frozen=True, slots=True)
class DeviceContext:
    """
    Grouped dependency context for Device initialization.

    Organizes 17 protocol interfaces into a single immutable object.

    Sections
    --------
    **Identity (2 values):**
        - interface_id: Interface identifier (e.g., "HmIP-RF")
        - device_address: Device address (e.g., "VCU0000001")

    **System Context (4 protocols):**
        - central_info: Central system information
        - config_provider: Configuration access
        - file_operations: File I/O operations
        - device_data_refresher: Firmware data refresh operations

    **Registry & Description Access (4 protocols):**
        - device_description_provider: Device descriptions
        - device_details_provider: Device metadata (names, rooms)
        - paramset_description_provider: Paramset descriptions
        - parameter_visibility_provider: Parameter visibility rules

    **Event Handling (3 protocols):**
        - event_bus_provider: Event bus access
        - event_publisher: Event publishing
        - event_subscription_manager: Event subscription management

    **Task Scheduling (1 protocol):**
        - task_scheduler: Async task scheduling

    **Data Access (3 protocols):**
        - client_provider: Client lookup
        - data_cache_provider: Data cache access
        - data_point_provider: Data point lookup

    **Channel Discovery (1 protocol):**
        - channel_lookup: Channel lookup by address
    """

    # =========================================================================
    # Identity (2 scalar values)
    # =========================================================================
    interface_id: str
    device_address: str

    # =========================================================================
    # System Context (4 protocols)
    # =========================================================================
    central_info: CentralInfoProtocol
    config_provider: ConfigProviderProtocol
    file_operations: FileOperationsProtocol
    device_data_refresher: FirmwareDataRefresherProtocol

    # =========================================================================
    # Registry & Description Access (4 protocols)
    # =========================================================================
    device_description_provider: DeviceDescriptionProviderProtocol
    device_details_provider: DeviceDetailsProviderProtocol
    paramset_description_provider: ParamsetDescriptionProviderProtocol
    parameter_visibility_provider: ParameterVisibilityProviderProtocol

    # =========================================================================
    # Event Handling (3 protocols)
    # =========================================================================
    event_bus_provider: EventBusProviderProtocol
    event_publisher: EventPublisherProtocol
    event_subscription_manager: EventSubscriptionManagerProtocol

    # =========================================================================
    # Task Scheduling (1 protocol)
    # =========================================================================
    task_scheduler: TaskSchedulerProtocol

    # =========================================================================
    # Data Access (3 protocols)
    # =========================================================================
    client_provider: ClientProviderProtocol
    data_cache_provider: DataCacheProviderProtocol
    data_point_provider: DataPointProviderProtocol

    # =========================================================================
    # Channel Discovery (1 protocol)
    # =========================================================================
    channel_lookup: ChannelLookupProtocol
