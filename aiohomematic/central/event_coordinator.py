# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Event coordinator for managing event subscriptions and handling.

This module provides centralized event subscription management and coordinates
event handling between data points, system variables, and the EventBus.

The EventCoordinator provides:
- Data point event subscription management
- System variable event subscription management
- Event routing and coordination
- Integration with EventBus for modern event handling
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from functools import partial
import logging
from typing import TYPE_CHECKING, Any, Final, TypedDict, Unpack

from aiohomematic.interfaces.operations import TaskSchedulerProtocol
from aiohomematic.property_decorators import DelegatedProperty

if TYPE_CHECKING:
    from aiohomematic.model.data_point import BaseDataPoint  # noqa: F401

from aiohomematic.async_support import loop_check
from aiohomematic.central.decorators import callback_event
from aiohomematic.central.event_bus import (
    BackendParameterEvent,
    DataPointStatusUpdatedEvent,
    DataPointUpdatedEvent,
    EventBus,
)
from aiohomematic.central.integration_events import (
    DataPointsCreatedEvent,
    DeviceLifecycleEvent,
    DeviceLifecycleEventType,
    DeviceTriggerEvent,
)
from aiohomematic.const import (
    DataPointCategory,
    DataPointKey,
    DeviceTriggerEventType,
    EventData,
    Parameter,
    ParamsetKey,
    SystemEventType,
)
from aiohomematic.interfaces.central import EventBusProviderProtocol, EventPublisherProtocol, HealthTrackerProtocol
from aiohomematic.interfaces.client import ClientProviderProtocol, LastEventTrackerProtocol
from aiohomematic.interfaces.model import (
    BaseParameterDataPointProtocolAny,
    GenericDataPointProtocol,
    GenericEventProtocol,
)

_LOGGER: Final = logging.getLogger(__name__)
_LOGGER_EVENT: Final = logging.getLogger(f"{__package__}.event")


class SystemEventArgs(TypedDict, total=False):
    """Arguments for all system events (DEVICES_CREATED, DELETE_DEVICES, HUB_REFRESHED)."""

    # DEVICES_CREATED / HUB_REFRESHED - accepts various mapping types with different value types
    new_data_points: Any

    # DELETE_DEVICES / DEVICES_DELAYED
    addresses: tuple[str, ...]
    new_addresses: tuple[str, ...]

    # Additional fields used by various event callers
    source: Any
    interface_id: str


# Type aliases for specific event argument types (for internal documentation)
DevicesCreatedEventArgs = SystemEventArgs
DeviceRemovedEventArgs = SystemEventArgs
HubRefreshedEventArgs = SystemEventArgs


class EventCoordinator(EventBusProviderProtocol, EventPublisherProtocol, LastEventTrackerProtocol):
    """Coordinator for event subscription and handling."""

    __slots__ = (
        "_client_provider",
        "_event_bus",
        "_health_tracker",
        "_last_event_seen_for_interface",
        "_task_scheduler",
    )

    def __init__(
        self,
        *,
        client_provider: ClientProviderProtocol,
        event_bus: EventBus,
        health_tracker: HealthTrackerProtocol,
        task_scheduler: TaskSchedulerProtocol,
    ) -> None:
        """
        Initialize the event coordinator.

        Args:
        ----
            client_provider: Provider for client access
            event_bus: EventBus for event subscription and publishing
            health_tracker: Health tracker for recording events
            task_scheduler: Provider for task scheduling

        """
        self._client_provider: Final = client_provider
        self._event_bus: Final = event_bus
        self._health_tracker: Final = health_tracker
        self._task_scheduler: Final = task_scheduler

        # Store last event seen datetime by interface_id
        self._last_event_seen_for_interface: Final[dict[str, datetime]] = {}

    event_bus: Final = DelegatedProperty[EventBus](path="_event_bus")

    def add_data_point_subscription(self, *, data_point: BaseParameterDataPointProtocolAny) -> None:
        """
        Add data point to event subscription.

        This method subscribes the data point's event handler to the EventBus.

        Args:
        ----
            data_point: Data point to subscribe to events for

        """
        if isinstance(data_point, GenericDataPointProtocol | GenericEventProtocol) and (
            data_point.is_readable or data_point.supports_events
        ):
            # Subscribe data point's event method to EventBus with filtering

            async def event_handler(*, event: DataPointUpdatedEvent) -> None:
                """Filter and handle data point events."""
                if event.dpk == data_point.dpk:
                    await data_point.event(value=event.value, received_at=event.received_at)

            self._event_bus.subscribe(event_type=DataPointUpdatedEvent, event_key=data_point.dpk, handler=event_handler)

        # Also subscribe for status events if applicable
        self._add_status_subscription(data_point=data_point)

    @callback_event
    async def data_point_event(self, *, interface_id: str, channel_address: str, parameter: str, value: Any) -> None:
        """
        Handle data point event from backend.

        Args:
        ----
            interface_id: Interface identifier
            channel_address: Channel address
            parameter: Parameter name
            value: New value

        """
        _LOGGER_EVENT.debug(
            "EVENT: interface_id = %s, channel_address = %s, parameter = %s, value = %s",
            interface_id,
            channel_address,
            parameter,
            str(value),
        )

        if not self._client_provider.has_client(interface_id=interface_id):
            return

        self.set_last_event_seen_for_interface(interface_id=interface_id)

        # Handle PONG response
        if parameter == Parameter.PONG:
            if "#" in value:
                v_interface_id, token = value.split("#")
                if (
                    v_interface_id == interface_id
                    and (client := self._client_provider.get_client(interface_id=interface_id))
                    and client.supports_ping_pong
                ):
                    client.ping_pong_cache.handle_received_pong(pong_token=token)
            return

        received_at = datetime.now()

        # Check if this is a STATUS parameter (e.g., LEVEL_STATUS)
        # If so, also publish a status event to the main parameter
        if parameter.endswith("_STATUS"):
            main_param = parameter[:-7]  # Remove "_STATUS" suffix
            main_dpk = DataPointKey(
                interface_id=interface_id,
                channel_address=channel_address,
                paramset_key=ParamsetKey.VALUES,
                parameter=main_param,
            )
            # Publish status update event to main parameter (if subscribed)
            await self._event_bus.publish(
                event=DataPointStatusUpdatedEvent(
                    timestamp=datetime.now(),
                    dpk=main_dpk,
                    status_value=value,
                    received_at=received_at,
                )
            )

        # Always publish normal parameter event (for the parameter itself)
        dpk = DataPointKey(
            interface_id=interface_id,
            channel_address=channel_address,
            paramset_key=ParamsetKey.VALUES,
            parameter=parameter,
        )

        # Publish to EventBus (await directly for synchronous event processing)
        await self._event_bus.publish(
            event=DataPointUpdatedEvent(
                timestamp=datetime.now(),
                dpk=dpk,
                value=value,
                received_at=received_at,
            )
        )

    def get_last_event_seen_for_interface(self, *, interface_id: str) -> datetime | None:
        """
        Return the last event seen for an interface.

        Args:
        ----
            interface_id: Interface identifier

        Returns:
        -------
            Datetime of last event or None if no event seen yet

        """
        return self._last_event_seen_for_interface.get(interface_id)

    def publish_backend_parameter_event(
        self, *, interface_id: str, channel_address: str, parameter: str, value: Any
    ) -> None:
        """
        Publish backend parameter callback.

        Re-published events from the backend for parameter updates.

        Args:
        ----
            interface_id: Interface identifier
            channel_address: Channel address
            parameter: Parameter name
            value: New value

        """

        async def _publish_backend_parameter_event() -> None:
            """Publish a backend parameter event to the event bus."""
            await self._event_bus.publish(
                event=BackendParameterEvent(
                    timestamp=datetime.now(),
                    interface_id=interface_id,
                    channel_address=channel_address,
                    parameter=parameter,
                    value=value,
                )
            )

        # Publish to EventBus asynchronously using partial to defer coroutine creation
        # and avoid lambda closure capturing variables
        self._task_scheduler.create_task(
            target=partial(_publish_backend_parameter_event),
            name=f"event-bus-backend-param-{channel_address}-{parameter}",
        )

    @loop_check
    def publish_device_trigger_event(self, *, trigger_type: DeviceTriggerEventType, event_data: EventData) -> None:
        """
        Publish device trigger event for Homematic callbacks.

        Events like KEYPRESS, IMPULSE, etc. are converted to DeviceTriggerEvent.

        Args:
        ----
            trigger_type: Type of Homematic event
            event_data: Typed event data containing interface_id, address, parameter, value

        """
        timestamp = datetime.now()

        if not (event_data.interface_id and event_data.device_address and event_data.parameter):
            return

        async def _publish_device_trigger_event() -> None:
            """Publish a device trigger event to the event bus."""
            await self._event_bus.publish(
                event=DeviceTriggerEvent(
                    timestamp=timestamp,
                    trigger_type=trigger_type,
                    model=event_data.model,
                    interface_id=event_data.interface_id,
                    device_address=event_data.device_address,
                    channel_no=event_data.channel_no,
                    parameter=event_data.parameter,
                    value=event_data.value,
                )
            )

        # Publish to EventBus using partial to defer coroutine creation
        # and avoid lambda closure capturing variables
        self._task_scheduler.create_task(
            target=partial(_publish_device_trigger_event),
            name=f"event-bus-device-trigger-{event_data.device_address}-{event_data.channel_no}-{event_data.parameter}",
        )

    @loop_check
    def publish_system_event(self, *, system_event: SystemEventType, **kwargs: Unpack[SystemEventArgs]) -> None:
        """
        Publish system event handlers.

        System-level events like DEVICES_CREATED, HUB_REFRESHED, etc.
        Converts legacy system events to focused integration events.

        Args:
        ----
            system_event: Type of system event
            **kwargs: Additional event data

        """
        timestamp = datetime.now()

        # Handle device lifecycle events
        if system_event == SystemEventType.DEVICES_CREATED:
            self._emit_devices_created_events(timestamp=timestamp, **kwargs)
        elif system_event == SystemEventType.DELETE_DEVICES:
            self._emit_device_removed_event(timestamp=timestamp, **kwargs)
        elif system_event == SystemEventType.HUB_REFRESHED:
            self._emit_hub_refreshed_event(timestamp=timestamp, **kwargs)

    def set_last_event_seen_for_interface(self, *, interface_id: str) -> None:
        """
        Set the last event seen timestamp for an interface.

        Args:
        ----
            interface_id: Interface identifier

        """
        self._last_event_seen_for_interface[interface_id] = datetime.now()

        # Update health tracker with event received
        self._health_tracker.record_event_received(interface_id=interface_id)

    def _add_status_subscription(self, *, data_point: BaseParameterDataPointProtocolAny) -> None:
        """
        Add status parameter event subscription for a data point.

        This method subscribes the data point to receive STATUS parameter events
        if the data point has a paired STATUS parameter.

        Args:
        ----
            data_point: Data point to subscribe for status events

        """
        if not hasattr(data_point, "status_dpk") or data_point.status_dpk is None:
            return

        async def status_event_handler(*, event: DataPointStatusUpdatedEvent) -> None:
            """Filter and handle status events."""
            if event.dpk == data_point.dpk:
                data_point.update_status(status_value=event.status_value)

        self._event_bus.subscribe(
            event_type=DataPointStatusUpdatedEvent,
            event_key=data_point.dpk,
            handler=status_event_handler,
        )

    def _emit_device_removed_event(self, *, timestamp: datetime, **kwargs: Unpack[DeviceRemovedEventArgs]) -> None:
        """Emit DeviceLifecycleEvent for DELETE_DEVICES."""
        if not (device_addresses := kwargs.get("addresses", ())):
            return

        async def _publish_event() -> None:
            """Publish device removed event."""
            await self._event_bus.publish(
                event=DeviceLifecycleEvent(
                    timestamp=timestamp,
                    event_type=DeviceLifecycleEventType.REMOVED,
                    device_addresses=device_addresses,
                )
            )

        self._task_scheduler.create_task(
            target=partial(_publish_event),
            name="event-bus-devices-removed",
        )

    def _emit_devices_created_events(self, *, timestamp: datetime, **kwargs: Unpack[DevicesCreatedEventArgs]) -> None:
        """Emit DeviceLifecycleEvent and DataPointsCreatedEvent for DEVICES_CREATED."""
        new_data_points: Mapping[DataPointCategory, Any] = kwargs.get("new_data_points", {})

        # Extract device addresses from data points
        device_addresses: set[str] = set()

        for category, data_points in new_data_points.items():
            if category == DataPointCategory.EVENT:
                continue
            for dp in data_points:
                device_addresses.add(dp.device.address)

        async def _publish_events() -> None:
            """Publish device lifecycle and data points created events."""
            # Emit DeviceLifecycleEvent for device creation
            if device_addresses:
                await self._event_bus.publish(
                    event=DeviceLifecycleEvent(
                        timestamp=timestamp,
                        event_type=DeviceLifecycleEventType.CREATED,
                        device_addresses=tuple(sorted(device_addresses)),
                    )
                )

            # Emit DataPointsCreatedEvent for data point discovery
            if new_data_points:
                await self._event_bus.publish(
                    event=DataPointsCreatedEvent(
                        timestamp=timestamp,
                        new_data_points=new_data_points,
                    )
                )

        self._task_scheduler.create_task(
            target=partial(_publish_events),
            name="event-bus-devices-created",
        )

    def _emit_hub_refreshed_event(self, *, timestamp: datetime, **kwargs: Unpack[HubRefreshedEventArgs]) -> None:
        """Emit DataPointsCreatedEvent for HUB_REFRESHED."""
        new_data_points: Any
        if not (new_data_points := kwargs.get("new_data_points", {})):
            return

        async def _publish_event() -> None:
            """Publish data points created event."""
            await self._event_bus.publish(
                event=DataPointsCreatedEvent(
                    timestamp=timestamp,
                    new_data_points=new_data_points,
                )
            )

        self._task_scheduler.create_task(
            target=partial(_publish_event),
            name="event-bus-hub-refreshed",
        )
