"""Functions for event creation."""

from __future__ import annotations

import logging
from typing import Any, Final

from hahomematic.async_support import loop_check
from hahomematic.const import (
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
from hahomematic.model import device as hmd
from hahomematic.model.data_point import BaseParameterDataPoint
from hahomematic.model.support import DataPointNameData, get_event_name

__all__ = [
    "ClickEvent",
    "DeviceErrorEvent",
    "GenericEvent",
    "ImpulseEvent",
    "create_event_and_append_to_channel",
]

_LOGGER: Final = logging.getLogger(__name__)


class GenericEvent(BaseParameterDataPoint[Any, Any]):
    """Base class for events."""

    _category = DataPointCategory.EVENT
    _event_type: EventType

    def __init__(
        self,
        channel: hmd.Channel,
        parameter: str,
        parameter_data: ParameterData,
    ) -> None:
        """Initialize the event handler."""
        self._unique_id_prefix = f"event_{channel.central.name}"
        super().__init__(
            channel=channel,
            paramset_key=ParamsetKey.VALUES,
            parameter=parameter,
            parameter_data=parameter_data,
        )

    @property
    def usage(self) -> DataPointUsage:
        """Return the data_point usage."""
        if (forced_by_com := self._enabled_by_channel_operation_mode) is None:
            return self._get_data_point_usage()
        return DataPointUsage.EVENT if forced_by_com else DataPointUsage.NO_CREATE

    @property
    def event_type(self) -> EventType:
        """Return the event_type of the event."""
        return self._event_type

    async def event(self, value: Any) -> None:
        """Handle event for which this handler has subscribed."""
        if self.event_type in DATA_POINT_EVENTS:
            self.fire_data_point_updated_callback(parameter=self.parameter.lower())
        self._set_modified_at()
        self.fire_event(value)

    @loop_check
    def fire_event(self, value: Any) -> None:
        """Do what is needed to fire an event."""
        self._central.fire_homematic_callback(event_type=self.event_type, event_data=self.get_event_data(value=value))

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

    _event_type = EventType.KEYPRESS


class DeviceErrorEvent(GenericEvent):
    """class for handling device error events."""

    _event_type = EventType.DEVICE_ERROR

    async def event(self, value: Any) -> None:
        """Handle event for which this handler has subscribed."""

        old_value, new_value = self.write_value(value=value)

        if (
            isinstance(new_value, bool)
            and ((old_value is None and new_value is True) or (isinstance(old_value, bool) and old_value != new_value))
        ) or (
            isinstance(new_value, int)
            and ((old_value is None and new_value > 0) or (isinstance(old_value, int) and old_value != new_value))
        ):
            self.fire_event(value=new_value)


class ImpulseEvent(GenericEvent):
    """class for handling impulse events."""

    _event_type = EventType.IMPULSE


def create_event_and_append_to_channel(channel: hmd.Channel, parameter: str, parameter_data: ParameterData) -> None:
    """Create action event data_point."""
    _LOGGER.debug(
        "CREATE_EVENT_AND_APPEND_TO_DEVICE: Creating event for %s, %s, %s",
        channel.address,
        parameter,
        channel.device.interface_id,
    )
    event_t: type[GenericEvent] | None = None
    if parameter_data["OPERATIONS"] & Operations.EVENT:
        if parameter in CLICK_EVENTS:
            event_t = ClickEvent
        if parameter.startswith(DEVICE_ERROR_EVENTS):
            event_t = DeviceErrorEvent
        if parameter in IMPULSE_EVENTS:
            event_t = ImpulseEvent
    if event_t:
        event = event_t(
            channel=channel,
            parameter=parameter,
            parameter_data=parameter_data,
        )
        channel.add_data_point(event)
