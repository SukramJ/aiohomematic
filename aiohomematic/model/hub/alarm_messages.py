# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Module for hub alarm messages sensor."""

from datetime import datetime
import logging
from typing import Any, Final, override

from slugify import slugify

from aiohomematic.const import HUB_ADDRESS, AlarmMessageData, DataPointCategory, HubValueType
from aiohomematic.interfaces import (
    CentralInfoProtocol,
    ChannelProtocol,
    ConfigProviderProtocol,
    EventBusProviderProtocol,
    EventPublisherProtocol,
    HubSensorDataPointProtocol,
    ParameterVisibilityProviderProtocol,
    ParamsetDescriptionProviderProtocol,
    TaskSchedulerProtocol,
)
from aiohomematic.model.data_point import CallbackDataPoint
from aiohomematic.model.support import HubPathData, PathData, generate_unique_id, get_hub_data_point_name_data
from aiohomematic.property_decorators import DelegatedProperty, Kind, config_property, state_property
from aiohomematic.support.mixins import PayloadMixin

_LOGGER: Final = logging.getLogger(__name__)

_ALARM_MESSAGES_SENSOR_NAME: Final = "alarm_messages"
_ALARM_MESSAGES: Final = "ALARM_MESSAGES"


class HmAlarmMessagesSensor(CallbackDataPoint, HubSensorDataPointProtocol, PayloadMixin):
    """Class for a Homematic alarm messages sensor."""

    __slots__ = (
        "_alarms",
        "_cached_alarm_count",
        "_name_data",
        "_state_uncertain",
    )

    _category = DataPointCategory.HUB_SENSOR
    _enabled_default = True

    def __init__(
        self,
        *,
        config_provider: ConfigProviderProtocol,
        central_info: CentralInfoProtocol,
        event_bus_provider: EventBusProviderProtocol,
        event_publisher: EventPublisherProtocol,
        task_scheduler: TaskSchedulerProtocol,
        paramset_description_provider: ParamsetDescriptionProviderProtocol,
        parameter_visibility_provider: ParameterVisibilityProviderProtocol,
    ) -> None:
        """Initialize the data_point."""
        PayloadMixin.__init__(self)
        unique_id: Final = generate_unique_id(
            config_provider=config_provider,
            address=HUB_ADDRESS,
            parameter=slugify(_ALARM_MESSAGES_SENSOR_NAME),
        )
        self._name_data: Final = get_hub_data_point_name_data(
            channel=None,
            legacy_name=_ALARM_MESSAGES_SENSOR_NAME,
            central_name=central_info.name,
        )
        super().__init__(
            unique_id=unique_id,
            central_info=central_info,
            event_bus_provider=event_bus_provider,
            event_publisher=event_publisher,
            task_scheduler=task_scheduler,
            paramset_description_provider=paramset_description_provider,
            parameter_visibility_provider=parameter_visibility_provider,
        )
        self._state_uncertain: bool = True
        self._alarms: tuple[AlarmMessageData, ...] = ()
        self._cached_alarm_count: int = 0

    alarms: Final = DelegatedProperty[tuple[AlarmMessageData, ...]](path="_alarms", kind=Kind.STATE)
    available: Final = DelegatedProperty[bool](path="_central_info.available", kind=Kind.STATE)
    enabled_default: Final = DelegatedProperty[bool](path="_enabled_default")
    full_name: Final = DelegatedProperty[str](path="_name_data.full_name")
    name: Final = DelegatedProperty[str](path="_name_data.name", kind=Kind.CONFIG)
    state_uncertain: Final = DelegatedProperty[bool](path="_state_uncertain")

    @property
    def channel(self) -> ChannelProtocol | None:
        """Return the identified channel."""
        return None

    @property
    def data_type(self) -> HubValueType | None:
        """Return the data type of the system variable."""
        return HubValueType.INTEGER

    @property
    def description(self) -> str | None:
        """Return data point description."""
        return None

    @property
    def legacy_name(self) -> str | None:
        """Return the original name."""
        return None

    @property
    def translation_key(self) -> str:
        """Return translation key for Home Assistant."""
        return "alarm_messages"

    @config_property
    def unit(self) -> str | None:
        """Return the unit of the data_point."""
        return None

    @state_property
    def additional_information(self) -> dict[str, Any]:
        """Return additional information about the data point."""
        ainfo = super().additional_information
        if self._alarms:
            ainfo[_ALARM_MESSAGES] = [
                f"{m.device_name}: {m.display_name}" if m.device_name else m.display_name for m in self._alarms
            ]
        return ainfo

    @state_property
    def value(self) -> int:
        """Return the count of active alarm messages."""
        return len(self._alarms)

    def update_data(self, *, alarms: tuple[AlarmMessageData, ...], write_at: datetime) -> None:
        """Update the data point with new alarm messages."""
        new_count = len(alarms)
        if self._cached_alarm_count != new_count or self._alarms != alarms:
            self._cached_alarm_count = new_count
            self._alarms = alarms
            self._set_modified_at(modified_at=write_at)
        else:
            self._set_refreshed_at(refreshed_at=write_at)
        self._state_uncertain = False
        self.publish_data_point_updated_event()

    @override
    def _get_path_data(self) -> PathData:
        """Return the path data of the data_point."""
        return HubPathData(name=slugify(_ALARM_MESSAGES_SENSOR_NAME))

    @override
    def _get_signature(self) -> str:
        """Return the signature of the data_point."""
        return f"{self._category}/{self.name}"
