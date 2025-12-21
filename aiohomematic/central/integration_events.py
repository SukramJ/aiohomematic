# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Integration-level events for Home Assistant and other consumers.

Overview
--------
This module provides focused integration events that aggregate multiple internal
events into consumer-friendly structures. These events are designed for:

- Home Assistant integration (control_unit.py, generic_entity.py)
- Third-party integrations
- Monitoring and debugging tools

Event Hierarchy
---------------
Integration Events (this module):
    - SystemStatusEvent: Infrastructure + lifecycle changes
    - DeviceLifecycleEvent: Device creation, removal, availability
    - DataPointsCreatedEvent: data point discovery
    - DeviceTriggerEvent: Device triggers (button press, etc.)

Data Point-Level Events (event_bus.py):
    - DataPointUpdatedEvent: High-frequency value updates (per-data point subscription)

Design Philosophy
-----------------
- Each event has a clear, single responsibility
- Immutable dataclasses (frozen=True, slots=True) for safety and performance
- Minimal payload - only relevant fields are populated
- Targeted registration - subscribe only to what you need

Example Usage
-------------
    from aiohomematic.central.integration_events import (
        SystemStatusEvent,
        DeviceLifecycleEvent,
        DataPointsCreatedEvent,
        DeviceTriggerEvent,
    )

    # Subscribe to system status changes
    central.event_bus.subscribe(
        event_type=SystemStatusEvent,
        event_key=None,
        handler=on_system_status,
    )

    # Subscribe to device lifecycle events
    central.event_bus.subscribe(
        event_type=DeviceLifecycleEvent,
        event_key=None,
        handler=on_device_lifecycle,
    )
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Literal

from aiohomematic.central.event_bus import Event
from aiohomematic.const import CentralState, ClientState, DataPointCategory, DeviceTriggerEventType, FailureReason

if TYPE_CHECKING:
    from aiohomematic.interfaces.model import CallbackDataPointProtocol


__all__ = [
    "DataPointsCreatedEvent",
    "DeviceLifecycleEvent",
    "DeviceLifecycleEventType",
    "DeviceTriggerEvent",
    "IntegrationIssue",
    "SystemStatusEvent",
]


@dataclass(frozen=True, slots=True)
class IntegrationIssue:
    """
    Issue that should be presented to user via integration's UI.

    Used to communicate problems that require user attention
    (e.g., connection failures, configuration errors).
    """

    severity: Literal["error", "warning"]
    """Issue severity level."""

    issue_id: str
    """Unique identifier for this issue (for tracking/deduplication)."""

    translation_key: str
    """Translation key for issue message."""

    translation_placeholders: tuple[tuple[str, str], ...] = ()
    """Placeholders for translation interpolation as tuple of (key, value) pairs."""


@dataclass(frozen=True, slots=True)
class SystemStatusEvent(Event):
    """
    System infrastructure and lifecycle status event.

    Aggregates: CentralStateChangedEvent, ConnectionStateChangedEvent,
    ClientStateChangedEvent, CallbackStateChangedEvent, FetchDataFailedEvent,
    PingPongMismatchEvent.

    **HA Registration Point**: `control_unit.py`

    Example:
        ```python
        async def on_system_status(*, event: SystemStatusEvent) -> None:
            if event.central_state == CentralState.FAILED:
                if event.failure_reason == FailureReason.AUTH:
                    async_create_issue(..., translation_key="auth_failed")
                elif event.failure_reason == FailureReason.NETWORK:
                    async_create_issue(..., translation_key="connection_failed")

            elif event.central_state == CentralState.DEGRADED:
                # Show status per degraded interface
                for iface_id, reason in (event.degraded_interfaces or {}).items():
                    _LOGGER.warning("Interface %s degraded: %s", iface_id, reason)

            for issue in event.issues:
                async_create_issue(...)

        central.event_bus.subscribe(
            event_type=SystemStatusEvent,
            event_key=None,
            handler=on_system_status,
        )
        ```

    """

    # Lifecycle
    central_state: CentralState | None = None
    """Central unit state change (STARTING, INITIALIZING, RUNNING, DEGRADED, RECOVERING, FAILED, STOPPED)."""

    # Failure details (populated when central_state is FAILED)
    failure_reason: FailureReason | None = None
    """
    Categorized reason for the failure.

    Only set when central_state is FAILED. Enables integrations to distinguish
    between different error types (AUTH, NETWORK, INTERNAL, etc.) and show
    appropriate user-facing messages.
    """

    failure_interface_id: str | None = None
    """Interface ID that caused the failure, if applicable."""

    # Degraded details (populated when central_state is DEGRADED)
    degraded_interfaces: Mapping[str, FailureReason] | None = None
    """
    Interfaces that are degraded with their failure reasons.

    Only set when central_state is DEGRADED. Maps interface_id to its
    FailureReason, enabling integrations to show detailed status per interface.
    Example: {"ccu-HmIP-RF": FailureReason.NETWORK, "ccu-BidCos-RF": FailureReason.AUTH}
    """

    # Infrastructure
    connection_state: tuple[str, bool] | None = None
    """Connection state change: (interface_id, connected)."""

    client_state: tuple[str, ClientState, ClientState] | None = None
    """Client state change: (interface_id, old_state, new_state)."""

    callback_state: tuple[str, bool] | None = None
    """Callback server state change: (interface_id, alive)."""

    # Issues
    issues: tuple[IntegrationIssue, ...] = ()
    """Issues that should be presented to user (errors, warnings)."""

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return None


class DeviceLifecycleEventType(StrEnum):
    """Type of device lifecycle event."""

    CREATED = "created"
    UPDATED = "updated"
    REMOVED = "removed"
    AVAILABILITY_CHANGED = "availability_changed"


@dataclass(frozen=True, slots=True)
class DeviceLifecycleEvent(Event):
    """
    Device lifecycle and availability event.

    Aggregates: SystemEventTypeData (DEVICES_CREATED, DEVICE_REMOVED),
    DeviceAvailabilityChangedEvent.

    **HA Registration Points**:
    - `control_unit.py`: Device registry updates, virtual remotes
    - `generic_entity.py`: Data point availability updates (optional)

    Example:
        ```python
        async def on_device_lifecycle(*, event: DeviceLifecycleEvent) -> None:
            if event.event_type == DeviceLifecycleEventType.CREATED:
                # Add to device registry
                for device_address in event.device_addresses:
                    device_registry.async_get_or_create(...)

            elif event.event_type == DeviceLifecycleEventType.AVAILABILITY_CHANGED:
                # Update data point availability
                for address, available in event.availability_changes:
                    ...

        central.event_bus.subscribe(
            event_type=DeviceLifecycleEvent,
            event_key=None,
            handler=on_device_lifecycle,
        )
        ```

    """

    event_type: DeviceLifecycleEventType
    """Type of device lifecycle event."""

    # For CREATED/UPDATED/REMOVED
    device_addresses: tuple[str, ...] = ()
    """Affected device addresses."""

    # For AVAILABILITY_CHANGED
    availability_changes: tuple[tuple[str, bool], ...] = ()
    """Availability changes: tuple of (device_address, is_available)."""

    # For CREATED - includes virtual remotes flag
    includes_virtual_remotes: bool = False
    """Whether virtual remotes are included in this creation event."""

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return None


@dataclass(frozen=True, slots=True)
class DataPointsCreatedEvent(Event):
    """
    New data points created event.

    Emitted when new data points are created (device addition, config reload).
    Data points are grouped by category for platform-specific handling.

    **HA Registration Point**: `control_unit.py`
    (Dispatches to platform async_add_entities functions)

    Example:
        ```python
        async def on_data_points_created(*, event: DataPointsCreatedEvent) -> None:
            for category, data_points in event.new_data_points:
                async_dispatcher_send(
                    hass,
                    signal_new_data_point(entry_id=entry_id, platform=category),
                    data_points,
                )

        central.event_bus.subscribe(
            event_type=DataPointsCreatedEvent,
            event_key=None,
            handler=on_data_points_created,
        )
        ```

    """

    new_data_points: Mapping[DataPointCategory, tuple[CallbackDataPointProtocol, ...]]
    """
    New data points grouped by category.

    Tuple of (category, data_points) pairs.
    Only includes data points that should be exposed to integrations.
    """

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return None


@dataclass(frozen=True, slots=True)
class DeviceTriggerEvent(Event):
    """
    Device trigger event (button press, sensor trigger, etc.).

    Forwarded to Home Assistant's event bus for automations.

    **HA Registration Point**: `control_unit.py`
    (Fires HA event on homematicip_local.event)

    Example:
        ```python
        async def on_device_trigger(*, event: DeviceTriggerEvent) -> None:
            hass.bus.async_fire(
                event_type=f"{DOMAIN}.event",
                event_data={
                    "trigger_type": event.trigger_type,
                    "model": event.model,
                    "interface_id": event.interface_id,
                    "device_address": event.device_address,
                    "channel_no": event.channel_no,
                    "parameter": event.parameter,
                    "value": event.value,
                },
            )

        central.event_bus.subscribe(
            event_type=DeviceTriggerEvent,
            event_key=None,
            handler=on_device_trigger,
        )
        ```

    """

    trigger_type: DeviceTriggerEventType
    """Type of device trigger event."""

    model: str
    """Model of the device."""

    interface_id: str
    """Interface ID where event occurred."""

    device_address: str
    """Device address of the device."""

    channel_no: int | None
    """Channel number of the device."""

    parameter: str
    """Parameter name (e.g., PRESS_SHORT, MOTION)."""

    value: str | int | float | bool
    """Event value."""

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return None
