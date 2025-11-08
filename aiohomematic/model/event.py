# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Event model for AioHomematic.

This module defines the event data point hierarchy used to expose Homematic
button presses, device errors, and impulse notifications to applications.

Included classes:
- GenericEvent: Base event that integrates with the common data point API
  (category, usage, names/paths, callbacks) and provides emit_event handling.
- ClickEvent: Represents key press events (EventType.KEYPRESS).
- DeviceErrorEvent: Represents device error signaling with special value change
  semantics before emitting an event (EventType.DEVICE_ERROR).
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
from typing import Any, Final

from aiohomematic import i18n, support as hms
from aiohomematic.async_support import loop_check
from aiohomematic.const import (
    CLICK_EVENTS,
    DATA_POINT_EVENTS,
    DEVICE_ERROR_EVENTS,
    IMPULSE_EVENTS,
    DataPointCategory,
    DataPointUsage,
    EventType,
    Operations,
    ParameterData,
    ParamsetKey,
)
from aiohomematic.decorators import inspector
from aiohomematic.exceptions import AioHomematicException
from aiohomematic.model import device as hmd
from aiohomematic.model.data_point import BaseParameterDataPointAny
from aiohomematic.model.support import DataPointNameData, get_event_name

__all__ = [
    "ClickEvent",
    "DeviceErrorEvent",
    "GenericEvent",
    "ImpulseEvent",
    "create_event_and_append_to_channel",
]

_LOGGER: Final = logging.getLogger(__name__)


class GenericEvent(BaseParameterDataPointAny):
    """Base class for events."""

    __slots__ = ("_event_type",)

    _category = DataPointCategory.EVENT
    _event_type: EventType

    def __init__(
        self,
        *,
        channel: hmd.Channel,
        parameter: str,
        parameter_data: ParameterData,
    ) -> None:
        """Initialize the event handler."""
        super().__init__(
            channel=channel,
            paramset_key=ParamsetKey.VALUES,
            parameter=parameter,
            parameter_data=parameter_data,
            unique_id_prefix=f"event_{channel.central.name}",
        )

    @property
    def event_type(self) -> EventType:
        """Return the event_type of the event."""
        return self._event_type

    @property
    def usage(self) -> DataPointUsage:
        """Return the data_point usage."""
        if (forced_by_com := self._enabled_by_channel_operation_mode) is None:
            return self._get_data_point_usage()
        return DataPointUsage.EVENT if forced_by_com else DataPointUsage.NO_CREATE  # pylint: disable=using-constant-test

    @loop_check
    def emit_event(self, *, value: Any) -> None:
        """Do what is needed to emit an event."""
        self._central.emit_homematic_callback(event_type=self.event_type, event_data=self.get_event_data(value=value))

    async def event(self, *, value: Any, received_at: datetime) -> None:
        """Handle event for which this handler has subscribed."""
        if self.event_type in DATA_POINT_EVENTS:
            self.emit_data_point_updated_event()
        self._set_modified_at(modified_at=received_at)
        self.emit_event(value=value)

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

    _event_type = EventType.KEYPRESS


class DeviceErrorEvent(GenericEvent):
    """class for handling device error events."""

    __slots__ = ()

    _event_type = EventType.DEVICE_ERROR

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
            self.emit_event(value=new_value)


class ImpulseEvent(GenericEvent):
    """class for handling impulse events."""

    __slots__ = ()

    _event_type = EventType.IMPULSE


@inspector
def create_event_and_append_to_channel(channel: hmd.Channel, parameter: str, parameter_data: ParameterData) -> None:
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


def _determine_event_type(parameter: str, parameter_data: ParameterData) -> type[GenericEvent] | None:
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
    event_t: type[GenericEvent],
    channel: hmd.Channel,
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
                "exception.model.event.create_event.failed",
                reason=hms.extract_exc_args(exc=exc),
            )
        ) from exc
