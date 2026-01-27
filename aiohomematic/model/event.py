# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Event model for AioHomematic.

This module defines the event data point hierarchy used to expose Homematic
button presses, device errors, and impulse notifications to applications.

Included classes:
- GenericEvent: Base event that integrates with the common data point API
  (category, usage, names/paths, subscriptions) and provides publish_event handling.
- ClickEvent: Represents key press events (EventType.KEYPRESS).
- DeviceErrorEvent: Represents device error signaling with special value change
  semantics before publishing an event (EventType.DEVICE_ERROR).
- ImpulseEvent: Represents impulse events (EventType.IMPULSE).

Factory helpers:
- create_event_and_append_to_channel: Determines the appropriate event type for
  a given parameter description and attaches an instance to the channel.

Typical flow:
1) During device initialization, model.create_data_points_and_events inspects
   paramset descriptions.
2) For parameters that support Operations.EVENT and match known event names
   (CLICK_EVENTS, DEVICE_ERROR_EVENTS, IMPULSE_EVENTS), an event data point is
   created and registered on the channel.
"""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any, Final, override

from aiohomematic import i18n, support as hms
from aiohomematic.async_support import loop_check
from aiohomematic.const import (
    CLICK_EVENTS,
    DATA_POINT_EVENTS,
    DEVICE_ERROR_EVENTS,
    IMPULSE_EVENTS,
    DataPointCategory,
    DataPointUsage,
    DeviceTriggerEventType,
    Operations,
    ParameterData,
    ParamsetKey,
    ServiceScope,
)
from aiohomematic.decorators import inspector
from aiohomematic.exceptions import AioHomematicException
from aiohomematic.interfaces import ChannelProtocol, DeviceProtocol, GenericEventProtocolAny
from aiohomematic.interfaces.model import ChannelEventGroupProtocol
from aiohomematic.model.data_point import BaseParameterDataPointAny, CallbackDataPoint
from aiohomematic.model.support import (
    DataPointNameData,
    DataPointPathData,
    PathData,
    generate_translation_key,
    get_event_name,
)
from aiohomematic.property_decorators import DelegatedProperty
from aiohomematic.type_aliases import DataPointUpdatedHandler, UnsubscribeCallback

__all__ = [
    "ChannelEventGroup",
    "ClickEvent",
    "DeviceErrorEvent",
    "GenericEvent",
    "ImpulseEvent",
    "create_event_and_append_to_channel",
]


_LOGGER: Final = logging.getLogger(__name__)


class GenericEvent(BaseParameterDataPointAny, GenericEventProtocolAny):
    """Base class for events."""

    __slots__ = ("_device_trigger_event_type",)

    _category = DataPointCategory.EVENT
    _device_trigger_event_type: DeviceTriggerEventType

    def __init__(
        self,
        *,
        channel: ChannelProtocol,
        parameter: str,
        parameter_data: ParameterData,
    ) -> None:
        """Initialize the event handler."""
        super().__init__(
            channel=channel,
            paramset_key=ParamsetKey.VALUES,
            parameter=parameter,
            parameter_data=parameter_data,
            unique_id_prefix=f"event_{channel.device.central_info.name}",
        )

    event_type: Final = DelegatedProperty[DeviceTriggerEventType](path="_device_trigger_event_type")

    @property
    def usage(self) -> DataPointUsage:
        """Return the data_point usage."""
        if (forced_by_com := self._enabled_by_channel_operation_mode) is None:
            return self._get_data_point_usage()
        return DataPointUsage.EVENT if forced_by_com else DataPointUsage.NO_CREATE

    async def event(self, *, value: Any, received_at: datetime) -> None:
        """Handle event for which this handler has subscribed."""
        if self.event_type in DATA_POINT_EVENTS:
            self.publish_data_point_updated_event()
        self._set_modified_at(modified_at=received_at)
        self.publish_event(value=value)

    @loop_check
    def publish_event(self, *, value: Any) -> None:
        """Do what is needed to publish an event."""
        self._event_publisher.publish_device_trigger_event(
            trigger_type=self.event_type, event_data=self.get_event_data(value=value)
        )

    def _get_data_point_name(self) -> DataPointNameData:
        """Create the name for the data_point."""
        return get_event_name(
            channel=self._channel,
            parameter=self._parameter,
        )

    def _get_data_point_usage(self) -> DataPointUsage:
        """Generate the usage for the data_point."""
        return DataPointUsage.EVENT


class ClickEvent(GenericEvent):
    """class for handling click events."""

    __slots__ = ()

    _device_trigger_event_type = DeviceTriggerEventType.KEYPRESS


class DeviceErrorEvent(GenericEvent):
    """class for handling device error events."""

    __slots__ = ()

    _device_trigger_event_type = DeviceTriggerEventType.DEVICE_ERROR

    async def event(self, *, value: Any, received_at: datetime) -> None:
        """Handle event for which this handler has subscribed."""
        old_value, new_value = self.write_value(value=value, write_at=received_at)

        if (
            isinstance(new_value, bool)
            and ((old_value is None and new_value is True) or (isinstance(old_value, bool) and old_value != new_value))
        ) or (
            isinstance(new_value, int)
            and ((old_value is None and new_value > 0) or (isinstance(old_value, int) and old_value != new_value))
        ):
            self.publish_event(value=new_value)


class ImpulseEvent(GenericEvent):
    """class for handling impulse events."""

    __slots__ = ()

    _device_trigger_event_type = DeviceTriggerEventType.IMPULSE


class ChannelEventGroup(CallbackDataPoint, ChannelEventGroupProtocol):
    """
    Virtual data point aggregating events of the same type for a single channel.

    Created during Channel.finalize_init() for each DeviceTriggerEventType
    present in the channel. A channel can have multiple event groups
    (e.g., one for KEYPRESS, one for IMPULSE).

    Internally subscribes to all GenericEvents of the same type and forwards
    triggers to external subscribers via the standard subscription API.

    Provides unified access to channel events with:
    - Pre-computed event_types list (parameter names)
    - Device trigger event type for the group
    - Last triggered event tracking
    - Standard CallbackDataPointProtocol subscription pattern
    - Translation key derivation

    Used by Home Assistant to create one EventEntity per event group.
    """

    __slots__ = (
        "_channel",
        "_device_trigger_event_type",
        "_events",
        "_event_types",
        "_last_triggered_event",
        "_name_data",
        "_internal_unsubscribe_callbacks",
    )

    _category = DataPointCategory.EVENT_GROUP

    def __init__(
        self,
        *,
        channel: ChannelProtocol,
        device_trigger_event_type: DeviceTriggerEventType,
        events: tuple[GenericEventProtocolAny, ...],
    ) -> None:
        """Initialize the channel event group."""
        if not events:
            raise ValueError(i18n.tr(key="exception.model.event.channel_event_group.no_events"))

        # Validate all events have the same event_type
        for event in events:
            if event.event_type != device_trigger_event_type:
                raise ValueError(
                    i18n.tr(
                        key="exception.model.event.channel_event_group.mixed_event_types",
                        expected=device_trigger_event_type,
                        actual=event.event_type,
                    )
                )

        self._channel: Final = channel
        self._device_trigger_event_type: Final = device_trigger_event_type
        self._events: Final = events
        self._event_types: Final = tuple(event.parameter.lower() for event in events)
        self._last_triggered_event: GenericEventProtocolAny | None = None
        self._internal_unsubscribe_callbacks: list[UnsubscribeCallback] = []
        self._name_data: Final = get_event_name(channel=channel, parameter=device_trigger_event_type.short)

        # Initialize CallbackDataPoint - get providers from channel.device
        super().__init__(
            unique_id=f"event_group_{device_trigger_event_type.short}_{channel.unique_id}",
            central_info=channel.device.central_info,
            event_bus_provider=channel.device.event_bus_provider,
            event_publisher=channel.device.event_publisher,
            task_scheduler=channel.device.task_scheduler,
            paramset_description_provider=channel.device.paramset_description_provider,
            parameter_visibility_provider=channel.device.parameter_visibility_provider,
        )

    available: Final = DelegatedProperty[bool](path="_channel.device.available")
    channel: Final = DelegatedProperty[ChannelProtocol](path="_channel")
    device: Final = DelegatedProperty[DeviceProtocol](path="_channel.device")
    device_trigger_event_type: Final = DelegatedProperty[DeviceTriggerEventType](path="_device_trigger_event_type")
    event_types: Final = DelegatedProperty[tuple[str, ...]](path="_event_types")
    events: Final = DelegatedProperty[tuple[GenericEventProtocolAny, ...]](path="_events")
    full_name: Final = DelegatedProperty[str](path="_name_data.full_name")
    name: Final = DelegatedProperty[str](path="_name_data.channel_name")

    @property
    def last_triggered_event(self) -> GenericEventProtocolAny | None:
        """Return the last event that was triggered."""
        return self._last_triggered_event

    @property
    def translation_key(self) -> str:
        """Return translation key for Home Assistant."""
        return generate_translation_key(name=self._device_trigger_event_type)

    @property
    def usage(self) -> DataPointUsage:
        """Return the data point usage."""
        return DataPointUsage.EVENT

    def cleanup_subscriptions(self) -> None:
        """Clean up internal subscriptions."""
        for unsub in self._internal_unsubscribe_callbacks:
            unsub()
        self._internal_unsubscribe_callbacks.clear()
        super().cleanup_subscriptions()

    async def finalize_init(self) -> None:
        """Set up internal subscriptions after channel events are ready."""
        self._setup_internal_subscriptions()

    @override
    def _get_path_data(self) -> PathData:
        """Return the path data."""
        return DataPointPathData(
            interface=self._channel.device.client.interface,
            address=self._channel.device.address,
            channel_no=self._channel.no,
            kind="event_group",
        )

    @override
    def _get_signature(self) -> str:
        """Return the signature of the event group."""
        return f"{self._category}/{self._channel.device.model}/event_group"

    def _setup_internal_subscriptions(self) -> None:
        """Subscribe to all events internally."""
        for event in self._events:

            def make_handler(ev: GenericEventProtocolAny) -> DataPointUpdatedHandler:
                def handler(*, data_point: Any, custom_id: str) -> None:
                    self._last_triggered_event = ev
                    self._set_modified_at(modified_at=ev.modified_at)
                    self.publish_data_point_updated_event()

                return handler

            self._internal_unsubscribe_callbacks.append(
                event.subscribe_to_internal_data_point_updated(handler=make_handler(event))
            )


@inspector(scope=ServiceScope.INTERNAL)
def create_event_and_append_to_channel(
    *, channel: ChannelProtocol, parameter: str, parameter_data: ParameterData
) -> None:
    """Create action event data_point."""
    _LOGGER.debug(
        "CREATE_EVENT_AND_APPEND_TO_DEVICE: Creating event for %s, %s, %s",
        channel.address,
        parameter,
        channel.device.interface_id,
    )
    if (event_t := _determine_event_type(parameter=parameter, parameter_data=parameter_data)) and (
        event := _safe_create_event(
            event_t=event_t, channel=channel, parameter=parameter, parameter_data=parameter_data
        )
    ):
        channel.add_data_point(data_point=event)


def _determine_event_type(*, parameter: str, parameter_data: ParameterData) -> type[GenericEvent] | None:
    event_t: type[GenericEvent] | None = None
    if parameter_data["OPERATIONS"] & Operations.EVENT:
        if parameter in CLICK_EVENTS:
            event_t = ClickEvent
        if parameter.startswith(DEVICE_ERROR_EVENTS):
            event_t = DeviceErrorEvent
        if parameter in IMPULSE_EVENTS:
            event_t = ImpulseEvent
    return event_t


def _safe_create_event(
    *,
    event_t: type[GenericEvent],
    channel: ChannelProtocol,
    parameter: str,
    parameter_data: ParameterData,
) -> GenericEvent:
    """Safely create a event and handle exceptions."""
    try:
        return event_t(
            channel=channel,
            parameter=parameter,
            parameter_data=parameter_data,
        )
    except Exception as exc:
        raise AioHomematicException(
            i18n.tr(
                key="exception.model.event.create_event.failed",
                reason=hms.extract_exc_args(exc=exc),
            )
        ) from exc
