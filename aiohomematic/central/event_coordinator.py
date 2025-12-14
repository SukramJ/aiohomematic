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
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from aiohomematic.model.data_point import BaseDataPoint

from aiohomematic.async_support import loop_check
from aiohomematic.central.decorators import callback_event
from aiohomematic.central.event_bus import BackendParameterEvent, DataPointUpdatedEvent, EventBus
from aiohomematic.central.integration_events import (
    DataPointsCreatedEvent,
    DeviceLifecycleEvent,
    DeviceLifecycleEventType,
    DeviceTriggerEvent,
)
from aiohomematic.const import (
    BackendSystemEvent,
    DataPointCategory,
    DataPointKey,
    EventKey,
    EventType,
    Parameter,
    ParamsetKey,
)
from aiohomematic.interfaces.central import EventBusProvider, EventPublisher
from aiohomematic.interfaces.client import ClientProvider, LastEventTracker
from aiohomematic.interfaces.model import BaseParameterDataPointProtocol, GenericDataPointProtocol, GenericEventProtocol
from aiohomematic.interfaces.operations import TaskScheduler

_LOGGER: Final = logging.getLogger(__name__)
_LOGGER_EVENT: Final = logging.getLogger(f"{__package__}.event")


class EventCoordinator(EventBusProvider, EventPublisher, LastEventTracker):
    """Coordinator for event subscription and handling."""

    __slots__ = (
        "_client_provider",
        "_event_bus",
        "_last_event_seen_for_interface",
        "_task_scheduler",
    )

    def __init__(
        self,
        *,
        client_provider: ClientProvider,
        task_scheduler: TaskScheduler,
    ) -> None:
        """
        Initialize the event coordinator.

        Args:
        ----
            client_provider: Provider for client access
            task_scheduler: Provider for task scheduling

        """
        self._client_provider: Final = client_provider
        self._task_scheduler: Final = task_scheduler

        # Initialize event bus with task scheduler for proper task lifecycle management
        self._event_bus: Final = EventBus(
            enable_event_logging=_LOGGER.isEnabledFor(logging.DEBUG),
            task_scheduler=task_scheduler,
        )

        # Store last event seen datetime by interface_id
        self._last_event_seen_for_interface: Final[dict[str, datetime]] = {}

    @property
    def event_bus(self) -> EventBus:
        """
        Return the EventBus for event subscription.

        The EventBus provides a type-safe API for subscribing to events.

        Example:
        -------
            central.event_coordinator.event_bus.subscribe(DataPointUpdatedEvent, my_handler)

        """
        return self._event_bus

    def add_data_point_subscription(self, *, data_point: BaseParameterDataPointProtocol) -> None:
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

        dpk = DataPointKey(
            interface_id=interface_id,
            channel_address=channel_address,
            paramset_key=ParamsetKey.VALUES,
            parameter=parameter,
        )

        received_at = datetime.now()

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
    def publish_backend_system_event(self, *, system_event: BackendSystemEvent, **kwargs: Any) -> None:
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
        if system_event == BackendSystemEvent.DEVICES_CREATED:
            self._emit_devices_created_events(timestamp=timestamp, **kwargs)
        elif system_event == BackendSystemEvent.DELETE_DEVICES:
            self._emit_device_removed_event(timestamp=timestamp, **kwargs)
        elif system_event == BackendSystemEvent.HUB_REFRESHED:
            self._emit_hub_refreshed_event(timestamp=timestamp, **kwargs)

    @loop_check
    def publish_homematic_event(self, *, event_type: EventType, event_data: dict[EventKey, Any]) -> None:
        """
        Publish device trigger event for Homematic callbacks.

        Events like KEYPRESS, IMPULSE, etc. are converted to DeviceTriggerEvent.

        Args:
        ----
            event_type: Type of Homematic event (unused, kept for interface compatibility)
            event_data: Event data dictionary containing interface_id, address, parameter, value

        """
        timestamp = datetime.now()
        interface_id = str(event_data.get(EventKey.INTERFACE_ID, ""))
        channel_address = str(event_data.get(EventKey.ADDRESS, ""))
        parameter = str(event_data.get(EventKey.PARAMETER, ""))
        value = event_data.get(EventKey.VALUE, "")

        if not (interface_id and channel_address and parameter):
            return

        async def _publish_device_trigger_event() -> None:
            """Publish a device trigger event to the event bus."""
            await self._event_bus.publish(
                event=DeviceTriggerEvent(
                    timestamp=timestamp,
                    interface_id=interface_id,
                    channel_address=channel_address,
                    parameter=parameter,
                    value=value,
                )
            )

        # Publish to EventBus using partial to defer coroutine creation
        # and avoid lambda closure capturing variables
        self._task_scheduler.create_task(
            target=partial(_publish_device_trigger_event),
            name=f"event-bus-device-trigger-{channel_address}-{parameter}",
        )

    def set_last_event_seen_for_interface(self, *, interface_id: str) -> None:
        """
        Set the last event seen timestamp for an interface.

        Args:
        ----
            interface_id: Interface identifier

        """
        self._last_event_seen_for_interface[interface_id] = datetime.now()

    def _emit_device_removed_event(self, *, timestamp: datetime, **kwargs: Any) -> None:
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

    def _emit_devices_created_events(self, *, timestamp: datetime, **kwargs: Any) -> None:
        """Emit DeviceLifecycleEvent and DataPointsCreatedEvent for DEVICES_CREATED."""
        new_data_points: Mapping[DataPointCategory, Any] = kwargs.get("new_data_points", {})

        # Extract device addresses from data points
        device_addresses: set[str] = set()
        for dps in new_data_points.values():
            for dp in dps:
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

            # Emit DataPointsCreatedEvent for entity discovery
            if new_data_points:
                # Convert Mapping to tuple of (category, data_points) pairs
                data_points_tuples = tuple((category, tuple(dps)) for category, dps in new_data_points.items() if dps)
                if data_points_tuples:
                    await self._event_bus.publish(
                        event=DataPointsCreatedEvent(
                            timestamp=timestamp,
                            new_data_points=data_points_tuples,
                        )
                    )

        self._task_scheduler.create_task(
            target=partial(_publish_events),
            name="event-bus-devices-created",
        )

    def _emit_hub_refreshed_event(self, *, timestamp: datetime, **kwargs: Any) -> None:
        """Emit DataPointsCreatedEvent for HUB_REFRESHED."""
        new_data_points: tuple[tuple[DataPointCategory, tuple[BaseDataPoint, ...]], ...] = kwargs.get(
            "new_data_points", ()
        )

        if not new_data_points:
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
