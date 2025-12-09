# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Base implementation for custom device-specific data points.

Public API of this module is defined by __all__.
"""

from __future__ import annotations

from collections.abc import Mapping
import contextlib
from datetime import datetime
import logging
from typing import Any, Final, cast

from aiohomematic.const import INIT_DATETIME, CallSource, DataPointKey, DataPointUsage, DeviceProfile, Field, Parameter
from aiohomematic.decorators import inspector
from aiohomematic.interfaces.model import ChannelProtocol, CustomDataPointProtocol, GenericDataPointProtocol
from aiohomematic.model.custom import definition as hmed
from aiohomematic.model.custom.profile import RebasedChannelGroup
from aiohomematic.model.custom.registry import DeviceConfig
from aiohomematic.model.data_point import BaseDataPoint
from aiohomematic.model.generic import DpDummy
from aiohomematic.model.support import (
    DataPointNameData,
    DataPointPathData,
    PathData,
    check_channel_is_the_only_primary_channel,
    get_custom_data_point_name,
)
from aiohomematic.property_decorators import state_property
from aiohomematic.support import get_channel_address
from aiohomematic.type_aliases import UnsubscribeCallback

_LOGGER: Final = logging.getLogger(__name__)


class CustomDataPoint(BaseDataPoint, CustomDataPointProtocol):
    """Base class for custom data point."""

    __slots__ = (
        "_allow_undefined_generic_data_points",
        "_channel_group",
        "_custom_data_point_def",
        "_data_points",
        "_device_config",
        "_device_profile",
        "_extended",
        "_group_no",
        "_schedule_channel_no",
        "_unsubscribe_callbacks",
    )

    def __init__(
        self,
        *,
        channel: ChannelProtocol,
        unique_id: str,
        device_profile: DeviceProfile,
        channel_group: RebasedChannelGroup,
        custom_data_point_def: Mapping[int | tuple[int, ...], tuple[Parameter, ...]],
        group_no: int | None,
        device_config: DeviceConfig,
    ) -> None:
        """Initialize the data point."""
        self._unsubscribe_callbacks: list[UnsubscribeCallback] = []
        self._device_profile: Final = device_profile
        self._channel_group: Final = channel_group
        self._custom_data_point_def: Final = custom_data_point_def
        self._group_no: int | None = group_no
        self._device_config: Final = device_config
        self._extended: Final = device_config.extended
        super().__init__(
            channel=channel,
            unique_id=unique_id,
            is_in_multiple_channels=hmed.is_multi_channel_device(model=channel.device.model, category=self.category),
        )
        self._allow_undefined_generic_data_points: Final[bool] = channel_group.allow_undefined_generic_data_points
        self._data_points: Final[dict[Field, GenericDataPointProtocol]] = {}
        self._init_data_points()
        self._init_data_point_fields()
        self._post_init_data_point_fields()
        if self.usage == DataPointUsage.CDP_PRIMARY:
            self._device.init_week_profile(data_point=self)

    def __del__(self) -> None:
        """Clean up subscriptions when the object is garbage collected."""
        with contextlib.suppress(Exception):
            self.unsubscribe_from_data_point_updated()

    @property
    def _readable_data_points(self) -> tuple[GenericDataPointProtocol, ...]:
        """Returns the list of readable data points."""
        return tuple(dp for dp in self._data_points.values() if dp.is_readable)

    @property
    def _relevant_data_points(self) -> tuple[GenericDataPointProtocol, ...]:
        """Returns the list of relevant data points. To be overridden by subclasses."""
        return self._readable_data_points

    @property
    def allow_undefined_generic_data_points(self) -> bool:
        """Return if undefined generic data points of this device are allowed."""
        return self._allow_undefined_generic_data_points

    @property
    def data_point_name_postfix(self) -> str:
        """Return the data point name postfix."""
        return ""

    @property
    def device_config(self) -> DeviceConfig:
        """Return the device config."""
        return self._device_config

    @property
    def group_no(self) -> int | None:
        """Return the base channel no of the data point."""
        return self._group_no

    @property
    def has_data_points(self) -> bool:
        """Return if there are data points."""
        return len(self._data_points) > 0

    @property
    def is_valid(self) -> bool:
        """Return if the state is valid."""
        return all(dp.is_valid for dp in self._relevant_data_points)

    @property
    def schedule(self) -> dict[Any, Any]:
        """Return cached schedule entries from device week profile."""
        if self._device.week_profile:
            return self._device.week_profile.schedule
        return {}

    @property
    def state_uncertain(self) -> bool:
        """Return, if the state is uncertain."""
        return any(dp.state_uncertain for dp in self._relevant_data_points)

    @property
    def supports_schedule(self) -> bool:
        """Flag if device supports schedule."""
        if self._device.week_profile:
            return self._device.week_profile.supports_schedule
        return False

    @property
    def unconfirmed_last_values_send(self) -> Mapping[Field, Any]:
        """Return the unconfirmed values send for the data point."""
        unconfirmed_values: dict[Field, Any] = {}
        for field, dp in self._data_points.items():
            if (unconfirmed_value := dp.unconfirmed_last_value_send) is not None:
                unconfirmed_values[field] = unconfirmed_value
        return unconfirmed_values

    @state_property
    def modified_at(self) -> datetime:
        """Return the latest last update timestamp."""
        modified_at: datetime = INIT_DATETIME
        for dp in self._readable_data_points:
            if (data_point_modified_at := dp.modified_at) and data_point_modified_at > modified_at:
                modified_at = data_point_modified_at
        return modified_at

    @state_property
    def refreshed_at(self) -> datetime:
        """Return the latest last refresh timestamp."""
        refreshed_at: datetime = INIT_DATETIME
        for dp in self._readable_data_points:
            if (data_point_refreshed_at := dp.refreshed_at) and data_point_refreshed_at > refreshed_at:
                refreshed_at = data_point_refreshed_at
        return refreshed_at

    async def get_schedule(self, *, force_load: bool = False) -> dict[Any, Any]:
        """Get schedule from device week profile."""
        if self._device.week_profile:
            return await self._device.week_profile.get_schedule(force_load=force_load)
        return {}

    def has_data_point_key(self, *, data_point_keys: set[DataPointKey]) -> bool:
        """Return if a data_point with one of the data points is part of this data_point."""
        result = [dp for dp in self._data_points.values() if dp.dpk in data_point_keys]
        return len(result) > 0

    def is_state_change(self, **kwargs: Any) -> bool:
        """
        Check if the state changes due to kwargs.

        If the state is uncertain, the state should also marked as changed.
        """
        if self.state_uncertain:
            return True
        _LOGGER.debug("NO_STATE_CHANGE: %s", self.name)
        return False

    @inspector(re_raise=False)
    async def load_data_point_value(self, *, call_source: CallSource, direct_call: bool = False) -> None:
        """Initialize the data point values."""
        for dp in self._readable_data_points:
            await dp.load_data_point_value(call_source=call_source, direct_call=direct_call)
        if self._device.week_profile and self.usage == DataPointUsage.CDP_PRIMARY:
            await self._device.week_profile.reload_and_cache_schedule()
        self.publish_data_point_updated_event()

    async def set_schedule(self, *, schedule_data: dict[Any, Any]) -> None:
        """Set schedule on device week profile."""
        if self._device.week_profile:
            await self._device.week_profile.set_schedule(schedule_data=schedule_data)

    def unsubscribe_from_data_point_updated(self) -> None:
        """Unregister all internal update handlers."""
        for unreg in self._unsubscribe_callbacks:
            if unreg is not None:
                unreg()
        self._unsubscribe_callbacks.clear()

    def _add_channel_data_points(
        self,
        *,
        channel_fields: Mapping[int | None, Mapping[Field, Parameter]],
        is_visible: bool | None = None,
    ) -> None:
        """Add channel-specific data points to custom data point."""
        for channel_no, fields in channel_fields.items():
            for field, parameter in fields.items():
                channel_address = get_channel_address(device_address=self._device.address, channel_no=channel_no)
                if dp := self._device.get_generic_data_point(channel_address=channel_address, parameter=parameter):
                    self._add_data_point(field=field, data_point=dp, is_visible=is_visible)

    def _add_data_point(
        self,
        *,
        field: Field,
        data_point: GenericDataPointProtocol | None,
        is_visible: bool | None = None,
    ) -> None:
        """Add data point to collection and subscribed handler."""
        if not data_point:
            return
        if is_visible is True and data_point.is_forced_sensor is False:
            data_point.force_usage(forced_usage=DataPointUsage.CDP_VISIBLE)
        elif is_visible is False and data_point.is_forced_sensor is False:
            data_point.force_usage(forced_usage=DataPointUsage.NO_CREATE)

        self._unsubscribe_callbacks.append(
            data_point.subscribe_to_internal_data_point_updated(handler=self.publish_data_point_updated_event)
        )
        self._data_points[field] = data_point

    def _get_data_point[DataPointT: GenericDataPointProtocol](
        self, *, field: Field, data_point_type: type[DataPointT]
    ) -> DataPointT:
        """Get data point."""
        if dp := self._data_points.get(field):
            if type(dp).__name__ != data_point_type.__name__:
                # not isinstance(data_point, data_point_type): # does not work with generic type
                _LOGGER.debug(  # pragma: no cover
                    "GET_DATA_POINT: type mismatch for requested sub data_point: "
                    "expected: %s, but is %s for field name %s of data_point %s",
                    data_point_type.name,
                    type(dp),
                    field,
                    self.name,
                )
            return cast(data_point_type, dp)  # type: ignore[valid-type]
        return cast(
            data_point_type,  # type:ignore[valid-type]
            DpDummy(channel=self._channel, param_field=field),
        )

    def _get_data_point_name(self) -> DataPointNameData:
        """Create the name for the data point."""
        is_only_primary_channel = check_channel_is_the_only_primary_channel(
            current_channel_no=self._channel.no,
            primary_channel=self._channel_group.primary_channel,
            device_has_multiple_channels=self.is_in_multiple_channels,
        )
        return get_custom_data_point_name(
            channel=self._channel,
            is_only_primary_channel=is_only_primary_channel,
            ignore_multiple_channels_for_name=self._ignore_multiple_channels_for_name,
            usage=self._get_data_point_usage(),
            postfix=self.data_point_name_postfix.replace("_", " ").title(),
        )

    def _get_data_point_usage(self) -> DataPointUsage:
        """Generate the usage for the data point."""
        if self._forced_usage:
            return self._forced_usage
        if self._channel.no in self._device_config.channels:
            return DataPointUsage.CDP_PRIMARY
        return DataPointUsage.CDP_SECONDARY

    def _get_path_data(self) -> PathData:
        """Return the path data of the data_point."""
        return DataPointPathData(
            interface=self._device.client.interface,
            address=self._device.address,
            channel_no=self._channel.no,
            kind=self._category,
        )

    def _get_signature(self) -> str:
        """Return the signature of the data_point."""
        return f"{self._category}/{self._channel.device.model}/{self.data_point_name_postfix}"

    def _init_data_point_fields(self) -> None:
        """Initialize the data point fields."""
        _LOGGER.debug(
            "INIT_DATA_POINT_FIELDS: Initialising the data point fields for %s",
            self.full_name,
        )

    def _init_data_points(self) -> None:
        """Initialize data point collection."""
        cg = self._channel_group

        # Add repeating fields
        for field_name, parameter in cg.repeating_fields.items():
            if dp := self._device.get_generic_data_point(channel_address=self._channel.address, parameter=parameter):
                self._add_data_point(field=field_name, data_point=dp, is_visible=False)

        # Add visible repeating fields
        for field_name, parameter in cg.visible_repeating_fields.items():
            if dp := self._device.get_generic_data_point(channel_address=self._channel.address, parameter=parameter):
                self._add_data_point(field=field_name, data_point=dp, is_visible=True)

        # Add extended config fields
        if self._extended:
            if fixed_channels := self._extended.fixed_channel_fields:
                for channel_no, mapping in fixed_channels.items():
                    for field_name, parameter in mapping.items():
                        channel_address = get_channel_address(
                            device_address=self._device.address, channel_no=channel_no
                        )
                        if dp := self._device.get_generic_data_point(
                            channel_address=channel_address, parameter=parameter
                        ):
                            self._add_data_point(field=field_name, data_point=dp)
            if additional_dps := self._extended.additional_data_points:
                self._mark_data_points(custom_data_point_def=additional_dps)

        # Add channel-specific fields
        self._add_channel_data_points(channel_fields=cg.channel_fields)

        # Add visible channel-specific fields
        self._add_channel_data_points(channel_fields=cg.visible_channel_fields, is_visible=True)

        # Add default device data points
        self._mark_data_points(custom_data_point_def=self._custom_data_point_def)

        # Add default data points
        if hmed.get_include_default_data_points(device_profile=self._device_profile):
            self._mark_data_points(custom_data_point_def=hmed.get_default_data_points())

    def _mark_data_point(self, *, channel_no: int | None, parameters: tuple[Parameter, ...]) -> None:
        """Mark data point to be created, even though a custom data point is present."""
        channel_address = get_channel_address(device_address=self._device.address, channel_no=channel_no)

        for parameter in parameters:
            if dp := self._device.get_generic_data_point(channel_address=channel_address, parameter=parameter):
                dp.force_usage(forced_usage=DataPointUsage.DATA_POINT)

    def _mark_data_points(
        self, *, custom_data_point_def: Mapping[int | tuple[int, ...], tuple[Parameter, ...]]
    ) -> None:
        """Mark data points to be created, even though a custom data point is present."""
        if not custom_data_point_def:
            return
        for channel_nos, parameters in custom_data_point_def.items():
            if isinstance(channel_nos, int):
                self._mark_data_point(channel_no=channel_nos, parameters=parameters)
            else:
                for channel_no in channel_nos:
                    self._mark_data_point(channel_no=channel_no, parameters=parameters)

    def _post_init_data_point_fields(self) -> None:
        """Post action after initialisation of the data point fields."""
        _LOGGER.debug(
            "POST_INIT_DATA_POINT_FIELDS: Post action after initialisation of the data point fields for %s",
            self.full_name,
        )
