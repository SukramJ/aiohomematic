# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Module for hub inbox sensor."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any, Final

from slugify import slugify

from aiohomematic.const import HUB_ADDRESS, DataPointCategory, InboxDeviceData, SysvarType
from aiohomematic.interfaces import (
    CentralInfo,
    ChannelProtocol,
    ConfigProvider,
    EventBusProvider,
    EventPublisher,
    GenericSysvarDataPointProtocol,
    ParameterVisibilityProvider,
    ParamsetDescriptionProvider,
    TaskScheduler,
)
from aiohomematic.model.data_point import CallbackDataPoint
from aiohomematic.model.support import HubPathData, PathData, generate_unique_id, get_hub_data_point_name_data
from aiohomematic.property_decorators import config_property, state_property
from aiohomematic.support import PayloadMixin

_LOGGER: Final = logging.getLogger(__name__)

_INBOX_NAME: Final = "Inbox"


class HmInboxSensor(CallbackDataPoint, GenericSysvarDataPointProtocol, PayloadMixin):
    """Class for a Homematic inbox sensor."""

    __slots__ = (
        "_devices",
        "_name_data",
        "_previous_value",
        "_state_uncertain",
    )

    _category = DataPointCategory.HUB_SENSOR
    _enabled_default = True

    def __init__(
        self,
        *,
        config_provider: ConfigProvider,
        central_info: CentralInfo,
        event_bus_provider: EventBusProvider,
        event_publisher: EventPublisher,
        task_scheduler: TaskScheduler,
        paramset_description_provider: ParamsetDescriptionProvider,
        parameter_visibility_provider: ParameterVisibilityProvider,
    ) -> None:
        """Initialize the data_point."""
        PayloadMixin.__init__(self)
        unique_id: Final = generate_unique_id(
            config_provider=config_provider,
            address=HUB_ADDRESS,
            parameter=slugify(_INBOX_NAME),
        )
        self._name_data: Final = get_hub_data_point_name_data(
            channel=None, legacy_name=_INBOX_NAME, central_name=central_info.name
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
        self._devices: tuple[InboxDeviceData, ...] = ()
        self._previous_value: int = 0

    @property
    def channel(self) -> ChannelProtocol | None:
        """Return the identified channel."""
        return None

    @property
    def data_type(self) -> SysvarType | None:
        """Return the data type of the system variable."""
        return SysvarType.INTEGER

    @property
    def description(self) -> str | None:
        """Return data point description."""
        return None

    @property
    def enabled_default(self) -> bool:
        """Return if the data_point should be enabled."""
        return self._enabled_default

    @property
    def full_name(self) -> str:
        """Return the fullname of the data_point."""
        return self._name_data.full_name

    @property
    def is_extended(self) -> bool:
        """Return if the data point is an extended type."""
        return False

    @property
    def legacy_name(self) -> str | None:
        """Return the original name."""
        return None

    @property
    def max(self) -> float | int | None:
        """Return the max value."""
        return None

    @property
    def min(self) -> float | int | None:
        """Return the min value."""
        return None

    @property
    def previous_value(self) -> int:
        """Return the previous value."""
        return self._previous_value

    @property
    def state_uncertain(self) -> bool:
        """Return, if the state is uncertain."""
        return self._state_uncertain

    @property
    def unit(self) -> str | None:
        """Return the unit of the data point."""
        return None

    @property
    def values(self) -> tuple[str, ...] | None:
        """Return the value list."""
        return None

    @property
    def vid(self) -> str:
        """Return sysvar id."""
        return slugify(_INBOX_NAME)

    @config_property
    def name(self) -> str:
        """Return the name of the data_point."""
        return self._name_data.name

    @state_property
    def available(self) -> bool:
        """Return the availability of the device."""
        return self._central_info.available

    @state_property
    def devices(self) -> tuple[InboxDeviceData, ...]:
        """Return the inbox devices."""
        return self._devices

    @state_property
    def value(self) -> int:
        """Return the count of inbox devices."""
        return len(self._devices)

    async def event(self, *, value: Any, received_at: datetime) -> None:
        """Handle event for which this data point has subscribed."""

    async def send_variable(self, *, value: Any) -> None:
        """Set variable value on the backend."""

    def update_data(self, *, devices: tuple[InboxDeviceData, ...], write_at: datetime) -> None:
        """Update the data point with new inbox devices."""
        if self._devices != devices:
            self._previous_value = len(self._devices)
            self._devices = devices
            self._set_modified_at(modified_at=write_at)
        else:
            self._set_refreshed_at(refreshed_at=write_at)
        self._state_uncertain = False
        self.publish_data_point_updated_event()

    def write_value(self, *, value: Any, write_at: datetime) -> None:
        """Set variable value on the backend."""

    def _get_path_data(self) -> PathData:
        """Return the path data of the data_point."""
        return HubPathData(name=slugify(_INBOX_NAME))

    def _get_signature(self) -> str:
        """Return the signature of the data_point."""
        return f"{self._category}/{self.name}"
