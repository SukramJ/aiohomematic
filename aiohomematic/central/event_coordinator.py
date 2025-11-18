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

from datetime import datetime
import logging
from typing import TYPE_CHECKING, Any, Final, cast

from aiohomematic.async_support import loop_check
from aiohomematic.central.event_bus import (
    BackendParameterEvent,
    BackendSystemEventData,
    DataPointUpdatedEvent,
    EventBus,
    HomematicEvent,
    SysvarUpdatedEvent,
)
from aiohomematic.const import (
    BackendSystemEvent,
    DataPointKey,
    EventKey,
    EventType,
    InterfaceEventType,
    Parameter,
    ParamsetKey,
)
from aiohomematic.model.event import GenericEvent
from aiohomematic.model.generic import GenericDataPoint
from aiohomematic.support import extract_exc_args
from aiohomematic.type_aliases import SysvarEventCallback

if TYPE_CHECKING:
    from aiohomematic.central import CentralUnit
    from aiohomematic.model.data_point import BaseParameterDataPointAny

_LOGGER: Final = logging.getLogger(__name__)
_LOGGER_EVENT: Final = logging.getLogger(f"{__package__}.event")


class EventCoordinator:
    """Coordinator for event subscription and handling."""

    __slots__ = (
        "_central",
        "_event_bus",
        "_last_event_seen_for_interface",
    )

    def __init__(self, *, central: CentralUnit) -> None:
        """
        Initialize the event coordinator.

        Args:
        ----
            central: The CentralUnit instance

        """
        self._central: Final = central

        # Initialize event bus
        self._event_bus: Final = EventBus(enable_event_logging=_LOGGER.isEnabledFor(logging.DEBUG))

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

    def add_data_point_subscription(self, *, data_point: BaseParameterDataPointAny) -> None:
        """
        Add data point to event subscription.

        This method subscribes the data point's event handler to the EventBus.

        Args:
        ----
            data_point: Data point to subscribe to events for

        """
        if isinstance(data_point, GenericDataPoint | GenericEvent) and (
            data_point.is_readable or data_point.supports_events
        ):
            # Subscribe data point's event method to EventBus using compatibility wrapper
            self._event_bus.subscribe_datapoint_event_callback(
                dpk=data_point.dpk,
                callback=data_point.event,
            )

    def add_sysvar_subscription(self, *, state_path: str, callback: SysvarEventCallback) -> None:
        """
        Add system variable to event subscription.

        DEPRECATED: This method is kept for backward compatibility but does nothing.
        System variables now subscribe directly to the EventBus.

        Args:
        ----
            state_path: State path of the system variable
            callback: Callback to invoke when system variable is updated

        """
        # No-op: System variables subscribe directly to EventBus

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

        if not self._central.has_client(interface_id=interface_id):
            return

        self.set_last_event_seen_for_interface(interface_id=interface_id)

        # Handle PONG response
        if parameter == Parameter.PONG:
            if "#" in value:
                v_interface_id, token = value.split("#")
                if (
                    v_interface_id == interface_id
                    and (client := self._central.get_client(interface_id=interface_id))
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

    def data_point_path_event(self, *, state_path: str, value: str) -> None:
        """
        Handle data point path event from MQTT or other sources.

        DEPRECATED: This method is kept for backward compatibility.
        Path-based events are now handled directly via EventBus.

        Args:
        ----
            state_path: State path of the data point
            value: New value

        """
        _LOGGER_EVENT.debug(
            "DATA_POINT_PATH_EVENT: topic = %s, payload = %s (method deprecated)",
            state_path,
            value,
        )

    def emit_backend_parameter_callback(
        self, *, interface_id: str, channel_address: str, parameter: str, value: Any
    ) -> None:
        """
        Emit backend parameter callback.

        Re-emitted events from the backend for parameter updates.

        Args:
        ----
            interface_id: Interface identifier
            channel_address: Channel address
            parameter: Parameter name
            value: New value

        """
        # Publish to EventBus asynchronously
        self._central.looper.create_task(
            target=lambda: self._event_bus.publish(
                event=BackendParameterEvent(
                    timestamp=datetime.now(),
                    interface_id=interface_id,
                    channel_address=channel_address,
                    parameter=parameter,
                    value=value,
                )
            ),
            name=f"event-bus-backend-param-{channel_address}-{parameter}",
        )

    @loop_check
    def emit_backend_system_callback(self, *, system_event: BackendSystemEvent, **kwargs: Any) -> None:
        """
        Emit system event callback.

        System-level events like DEVICES_CREATED, HUB_REFRESHED, etc.

        Args:
        ----
            system_event: Type of system event
            **kwargs: Additional event data

        """
        # Publish to EventBus (new system)
        self._central.looper.create_task(
            target=lambda: self._event_bus.publish(
                event=BackendSystemEventData(timestamp=datetime.now(), system_event=system_event, data=kwargs)
            ),
            name=f"event-bus-backend-system-{system_event}",
        )

    @loop_check
    def emit_homematic_callback(self, *, event_type: EventType, event_data: dict[EventKey, Any]) -> None:
        """
        Emit Homematic callback.

        Events like INTERFACE, KEYPRESS, etc.

        Args:
        ----
            event_type: Type of Homematic event
            event_data: Event data dictionary

        """
        # Publish to EventBus (new system)
        self._central.looper.create_task(
            target=lambda: self._event_bus.publish(
                event=HomematicEvent(timestamp=datetime.now(), event_type=event_type, event_data=event_data)
            ),
            name=f"event-bus-homematic-{event_type}",
        )

    @loop_check
    def emit_interface_event(
        self,
        *,
        interface_id: str,
        interface_event_type: InterfaceEventType,
        data: dict[str, Any],
    ) -> None:
        """
        Emit an event about the interface status.

        Args:
        ----
            interface_id: Interface identifier
            interface_event_type: Type of interface event
            data: Event data

        """
        # Import at runtime to avoid circular dependency
        from aiohomematic.central import INTERFACE_EVENT_SCHEMA  # noqa: PLC0415

        data = data or {}
        event_data: dict[str, Any] = {
            EventKey.INTERFACE_ID: interface_id,
            EventKey.TYPE: interface_event_type,
            EventKey.DATA: data,
        }

        self.emit_homematic_callback(
            event_type=EventType.INTERFACE,
            event_data=cast(dict[EventKey, Any], INTERFACE_EVENT_SCHEMA(event_data)),
        )

    def get_data_point_path(self) -> tuple[str, ...]:
        """
        Return the registered state paths.

        DEPRECATED: This method is kept for backward compatibility.
        Returns empty tuple as legacy path subscriptions are no longer used.

        Returns
        -------
            Tuple of registered state paths (always empty)

        """
        return ()

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

    def get_sysvar_data_point_path(self) -> tuple[str, ...]:
        """
        Return the registered sysvar state paths.

        DEPRECATED: This method is kept for backward compatibility.
        Returns empty tuple as legacy sysvar subscriptions are no longer used.

        Returns
        -------
            Tuple of registered sysvar state paths (always empty)

        """
        return ()

    def remove_data_point_subscription(self, *, data_point: BaseParameterDataPointAny) -> None:
        """
        Remove data point event subscription.

        DEPRECATED: This method is kept for backward compatibility but does nothing.
        Data points now unsubscribe directly from the EventBus.

        Args:
        ----
            data_point: Data point to unsubscribe from events

        """
        # No-op: DataPoints unsubscribe directly from EventBus

    def remove_sysvar_subscription(self, *, state_path: str) -> None:
        """
        Remove system variable event subscription.

        DEPRECATED: This method is kept for backward compatibility but does nothing.
        System variables now unsubscribe directly from the EventBus.

        Args:
        ----
            state_path: State path of the system variable

        """
        # No-op: System variables unsubscribe directly from EventBus

    def set_last_event_seen_for_interface(self, *, interface_id: str) -> None:
        """
        Set the last event seen timestamp for an interface.

        Args:
        ----
            interface_id: Interface identifier

        """
        self._last_event_seen_for_interface[interface_id] = datetime.now()

    def sysvar_data_point_path_event(self, *, state_path: str, value: str) -> None:
        """
        Handle system variable path event.

        Args:
        ----
            state_path: State path of the system variable
            value: New value

        """
        _LOGGER_EVENT.debug(
            "SYSVAR_DATA_POINT_PATH_EVENT: topic = %s, payload = %s",
            state_path,
            value,
        )

        received_at = datetime.now()

        # Publish to EventBus
        try:
            self._central.looper.create_task(
                target=lambda: self._event_bus.publish(
                    event=SysvarUpdatedEvent(
                        timestamp=datetime.now(),
                        state_path=state_path,
                        value=value,
                        received_at=received_at,
                    )
                ),
                name=f"event-bus-sysvar-{state_path}",
            )
        except RuntimeError as rterr:
            _LOGGER_EVENT.debug(
                "EVENT: RuntimeError [%s]. Failed to publish to EventBus for: %s",
                extract_exc_args(exc=rterr),
                state_path,
            )
        except Exception as exc:  # pragma: no cover
            _LOGGER_EVENT.error(  # i18n-log: ignore
                "EVENT failed: Unable to publish to EventBus for: %s, %s",
                state_path,
                extract_exc_args(exc=exc),
            )
