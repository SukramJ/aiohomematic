# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Module with base class for custom data points."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from enum import IntEnum, StrEnum
import logging
import re
from typing import Any, Final, cast

from aiohomematic import i18n
from aiohomematic.const import (
    BIDCOS_DEVICE_CHANNEL_DUMMY,
    CDPD,
    INIT_DATETIME,
    CallSource,
    DataPointCategory,
    DataPointKey,
    DataPointUsage,
    DeviceProfile,
    Field,
    ParamsetKey,
)
from aiohomematic.decorators import inspector
from aiohomematic.exceptions import ClientException, ValidationException
from aiohomematic.model import device as hmd
from aiohomematic.model.custom import definition as hmed
from aiohomematic.model.custom.support import CustomConfig
from aiohomematic.model.data_point import BaseDataPoint
from aiohomematic.model.generic import DpDummy, data_point as hmge
from aiohomematic.model.support import (
    DataPointNameData,
    DataPointPathData,
    PathData,
    check_channel_is_the_only_primary_channel,
    get_custom_data_point_name,
)
from aiohomematic.property_decorators import state_property
from aiohomematic.support import get_channel_address
from aiohomematic.type_aliases import DataPointUpdatedCallback, UnregisterCallback

_LOGGER: Final = logging.getLogger(__name__)


class CustomDataPoint(BaseDataPoint):
    """Base class for custom data point."""

    __slots__ = (
        "_allow_undefined_generic_data_points",
        "_custom_config",
        "_custom_data_point_def",
        "_data_points",
        "_device_def",
        "_device_profile",
        "_extended",
        "_group_no",
        "_schedule_cache",
        "_schedule_channel_no",
        "_unregister_callbacks",
    )

    def __init__(
        self,
        *,
        channel: hmd.Channel,
        unique_id: str,
        device_profile: DeviceProfile,
        device_def: Mapping[str, Any],
        custom_data_point_def: Mapping[int | tuple[int, ...], tuple[str, ...]],
        group_no: int,
        custom_config: CustomConfig,
    ) -> None:
        """Initialize the data point."""
        self._unregister_callbacks: list[UnregisterCallback] = []
        self._device_profile: Final = device_profile
        # required for name in BaseDataPoint
        self._device_def: Final = device_def
        self._custom_data_point_def: Final = custom_data_point_def
        self._group_no: int = group_no
        self._custom_config: Final = custom_config
        self._extended: Final = custom_config.extended
        self._schedule_channel_no: Final[int | None] = custom_config.schedule_channel_no
        self._schedule_cache: SCHEDULE_DICT = {}
        super().__init__(
            channel=channel,
            unique_id=unique_id,
            is_in_multiple_channels=hmed.is_multi_channel_device(model=channel.device.model, category=self.category),
        )
        self._allow_undefined_generic_data_points: Final[bool] = self._device_def[CDPD.ALLOW_UNDEFINED_GENERIC_DPS]
        self._data_points: Final[dict[Field, hmge.GenericDataPointAny]] = {}
        self._init_data_points()
        self._init_data_point_fields()
        self._post_init_data_point_fields()

    @staticmethod
    def _filter_schedule_entries(*, values: Mapping[str, Any]) -> RAW_SCHEDULE:
        """Return only the WP entries from a raw paramset dictionary."""
        schedule: RAW_SCHEDULE = {}
        for key, value in values.items():
            if not SCHEDULE_PATTERN.match(key):
                continue
            # The CCU reports ints/floats; cast to float for completeness
            if isinstance(value, (int, float)):
                schedule[key] = float(value) if isinstance(value, float) else value
        return schedule

    @property
    def _readable_data_points(self) -> tuple[hmge.GenericDataPointAny, ...]:
        """Returns the list of readable data points."""
        return tuple(dp for dp in self._data_points.values() if dp.is_readable)

    @property
    def _relevant_data_points(self) -> tuple[hmge.GenericDataPointAny, ...]:
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
    def schedule(self) -> SCHEDULE_DICT:
        """Return cached schedule entries."""
        return self._schedule_cache

    @property
    def schedule_channel_address(self) -> str | None:
        """Return schedule channel address."""
        if self._schedule_channel_no == BIDCOS_DEVICE_CHANNEL_DUMMY:
            return self._device.address
        if self._schedule_channel_no is not None:
            return f"{self._device.address}:{self._schedule_channel_no}"
        if (sca := self._device.schedule_channel_address) is not None:
            return sca
        return None

    @property
    def state_uncertain(self) -> bool:
        """Return, if the state is uncertain."""
        return any(dp.state_uncertain for dp in self._relevant_data_points)

    @property
    def supports_schedule(self) -> bool:
        """Flag if climate supports schedule."""
        return self.schedule_channel_address is not None

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

    @inspector
    async def get_schedule(self, *, force_load: bool = False) -> SCHEDULE_DICT:
        """Return the raw schedule dictionary."""
        if not self.supports_schedule:
            raise ValidationException(
                i18n.tr(
                    "exception.model.custom.data_point.schedule.unsupported",
                    address=self._device.name,
                )
            )
        await self.reload_and_cache_schedule(force=force_load)
        return self._schedule_cache

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

    async def load_data_point_value(self, *, call_source: CallSource, direct_call: bool = False) -> None:
        """Init the data point values."""
        for dp in self._readable_data_points:
            await dp.load_data_point_value(call_source=call_source, direct_call=direct_call)
        await self.reload_and_cache_schedule()
        self.emit_data_point_updated_event()

    async def on_config_changed(self) -> None:
        """Handle configuration changes."""
        await super().on_config_changed()
        await self.reload_and_cache_schedule(force=True)

    async def reload_and_cache_schedule(self, *, force: bool = False) -> None:
        """Reload schedule entries and update cache."""
        if not force and not self.supports_schedule:
            return

        try:
            new_raw_schedule = await self._get_raw_schedule()
        except ValidationException:
            return

        old_schedule = self._schedule_cache
        self._schedule_cache = raw_schedule_to_dict(raw_schedule=new_raw_schedule)
        if old_schedule != self._schedule_cache:
            self.emit_data_point_updated_event()

    @inspector
    async def set_schedule(self, *, schedule_dict: SCHEDULE_DICT) -> None:
        """Persist the provided raw schedule dictionary."""
        if (sca := self.schedule_channel_address) is None:
            raise ValidationException(
                i18n.tr(
                    "exception.model.custom.data_point.schedule.unsupported",
                    address=self._device.name,
                )
            )

        old_schedule = self._schedule_cache
        self._schedule_cache = schedule_dict
        if old_schedule != schedule_dict:
            self.emit_data_point_updated_event()

        await self._client.put_paramset(
            channel_address=sca,
            paramset_key_or_link_address=ParamsetKey.MASTER,
            values=self._filter_schedule_entries(values=dict_to_raw_schedule(schedule_dict=schedule_dict)),
        )

    def _add_data_point(
        self,
        *,
        field: Field,
        data_point: hmge.GenericDataPointAny | None,
        is_visible: bool | None = None,
    ) -> None:
        """Add data point to collection and register callback."""
        if not data_point:
            return
        if is_visible is True and data_point.is_forced_sensor is False:
            data_point.force_usage(forced_usage=DataPointUsage.CDP_VISIBLE)
        elif is_visible is False and data_point.is_forced_sensor is False:
            data_point.force_usage(forced_usage=DataPointUsage.NO_CREATE)

        self._unregister_callbacks.append(
            data_point.register_internal_data_point_updated_callback(cb=self.emit_data_point_updated_event)
        )
        self._data_points[field] = data_point

    def _add_data_points(self, *, field_dict_name: CDPD, is_visible: bool | None = None) -> None:
        """Add data points to custom data point."""
        fields = self._device_def.get(field_dict_name, {})
        for channel_no, channel in fields.items():
            for field, parameter in channel.items():
                channel_address = get_channel_address(device_address=self._device.address, channel_no=channel_no)
                if dp := self._device.get_generic_data_point(channel_address=channel_address, parameter=parameter):
                    self._add_data_point(field=field, data_point=dp, is_visible=is_visible)

    def _get_data_point[DataPointT: hmge.GenericDataPointAny](
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
            device_def=self._device_def,
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
        if self._channel.no in self._custom_config.channels:
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

    async def _get_raw_schedule(self) -> RAW_SCHEDULE:
        """Return the raw schedule dictionary filtered to WP entries."""
        try:
            if (sca := self.schedule_channel_address) is None:
                raise ValidationException(
                    i18n.tr(
                        "exception.model.custom.data_point.schedule.unsupported",
                        address=self._device.name,
                    )
                )
            raw_data = await self._client.get_paramset(
                address=sca,
                paramset_key=ParamsetKey.MASTER,
            )
        except ClientException as cex:
            raise ValidationException(
                i18n.tr(
                    "exception.model.custom.data_point.schedule.unsupported",
                    name=self._device.name,
                )
            ) from cex

        if not (schedule := self._filter_schedule_entries(values=raw_data)):
            raise ValidationException(
                i18n.tr(
                    "exception.model.custom.data_point.schedule.unsupported",
                    name=self._device.name,
                )
            )
        return schedule

    def _get_signature(self) -> str:
        """Return the signature of the data_point."""
        return f"{self._category}/{self._channel.device.model}/{self.data_point_name_postfix}"

    def _init_data_point_fields(self) -> None:
        """Init the data point fields."""
        _LOGGER.debug(
            "INIT_DATA_POINT_FIELDS: Initialising the data point fields for %s",
            self.full_name,
        )

    def _init_data_points(self) -> None:
        """Init data point collection."""
        # Add repeating fields
        for field_name, parameter in self._device_def.get(CDPD.REPEATABLE_FIELDS, {}).items():
            if dp := self._device.get_generic_data_point(channel_address=self._channel.address, parameter=parameter):
                self._add_data_point(field=field_name, data_point=dp, is_visible=False)

        # Add visible repeating fields
        for field_name, parameter in self._device_def.get(CDPD.VISIBLE_REPEATABLE_FIELDS, {}).items():
            if dp := self._device.get_generic_data_point(channel_address=self._channel.address, parameter=parameter):
                self._add_data_point(field=field_name, data_point=dp, is_visible=True)

        if self._extended:
            if fixed_channels := self._extended.fixed_channels:
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

        # Add device fields
        self._add_data_points(
            field_dict_name=CDPD.FIELDS,
        )
        # Add visible device fields
        self._add_data_points(
            field_dict_name=CDPD.VISIBLE_FIELDS,
            is_visible=True,
        )

        # Add default device data points
        self._mark_data_points(custom_data_point_def=self._custom_data_point_def)
        # add default data points
        if hmed.get_include_default_data_points(device_profile=self._device_profile):
            self._mark_data_points(custom_data_point_def=hmed.get_default_data_points())

    def _mark_data_point(self, *, channel_no: int | None, parameters: tuple[str, ...]) -> None:
        """Mark data point to be created, even though a custom data point is present."""
        channel_address = get_channel_address(device_address=self._device.address, channel_no=channel_no)

        for parameter in parameters:
            if dp := self._device.get_generic_data_point(channel_address=channel_address, parameter=parameter):
                dp.force_usage(forced_usage=DataPointUsage.DATA_POINT)

    def _mark_data_points(self, *, custom_data_point_def: Mapping[int | tuple[int, ...], tuple[str, ...]]) -> None:
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

    def _unregister_data_point_updated_callback(self, *, cb: DataPointUpdatedCallback, custom_id: str) -> None:
        """Unregister update callback."""
        for unregister in self._unregister_callbacks:
            if unregister is not None:
                unregister()

        super()._unregister_data_point_updated_callback(cb=cb, custom_id=custom_id)


class ScheduleField(StrEnum):
    """Enum for switch schedule field names."""

    ASTRO_OFFSET = "ASTRO_OFFSET"
    ASTRO_TYPE = "ASTRO_TYPE"
    CONDITION = "CONDITION"
    DURATION_BASE = "DURATION_BASE"
    DURATION_FACTOR = "DURATION_FACTOR"
    FIXED_HOUR = "FIXED_HOUR"
    FIXED_MINUTE = "FIXED_MINUTE"
    LEVEL = "LEVEL"
    LEVEL_2 = "LEVEL_2"
    RAMP_TIME_BASE = "RAMP_TIME_BASE"
    RAMP_TIME_FACTOR = "RAMP_TIME_FACTOR"
    TARGET_CHANNELS = "TARGET_CHANNELS"
    WEEKDAY = "WEEKDAY"


class AstroType(IntEnum):
    """Enum for astro event types."""

    SUNRISE = 0
    SUNSET = 1


class ScheduleCondition(IntEnum):
    """Enum for schedule trigger conditions."""

    FIXED_TIME = 0
    ASTRO = 1


class TimeBase(IntEnum):
    """Enum for duration base units."""

    MS_100 = 0  # 100 milliseconds
    SEC_1 = 1  # 1 second
    SEC_5 = 2  # 5 seconds
    SEC_10 = 3  # 10 seconds
    MIN_1 = 4  # 1 minute
    MIN_5 = 5  # 5 minutes
    MIN_10 = 6  # 10 minutes
    HOUR_1 = 7  # 1 hour


class Weekday(IntEnum):
    """Enum for weekdays (bitwise)."""

    SUNDAY = 1
    MONDAY = 2
    TUESDAY = 4
    WEDNESDAY = 8
    THURSDAY = 16
    FRIDAY = 32
    SATURDAY = 64


class ScheduleActorChannel(IntEnum):
    """Enum for target actor channels (bitwise)."""

    CHANNEL_1_1 = 1
    CHANNEL_1_2 = 2
    CHANNEL_1_3 = 4
    CHANNEL_2_1 = 8
    CHANNEL_2_2 = 16
    CHANNEL_2_3 = 32
    CHANNEL_3_1 = 64
    CHANNEL_3_2 = 128
    CHANNEL_3_3 = 256
    CHANNEL_4_1 = 512
    CHANNEL_4_2 = 1024
    CHANNEL_4_3 = 2048
    CHANNEL_5_1 = 4096
    CHANNEL_5_2 = 8192
    CHANNEL_5_3 = 16384
    CHANNEL_6_1 = 32768
    CHANNEL_6_2 = 65536
    CHANNEL_6_3 = 131072
    CHANNEL_7_1 = 262144
    CHANNEL_7_2 = 524288
    CHANNEL_7_3 = 1048576
    CHANNEL_8_1 = 2097152
    CHANNEL_8_2 = 4194304
    CHANNEL_8_3 = 8388608


# Schedule conversion functions
SCHEDULE_PATTERN: Final = re.compile(r"^\d+_WP_")

# Type aliases for switch schedules
RAW_SCHEDULE = dict[str, float | int]
SCHEDULE_GROUP = dict[ScheduleField, Any]
SCHEDULE_DICT = dict[int, SCHEDULE_GROUP]


def _bitwise_to_list(*, value: int, enum_class: type[IntEnum]) -> list[IntEnum]:
    """
    Convert bitwise integer to list of enum values.

    Example:
        _bitwise_to_list(127, Weekday) -> [SUNDAY, MONDAY, ..., SATURDAY]
        _bitwise_to_list(7, Channel) -> [CHANNEL_1, CHANNEL_2, CHANNEL_3]

    """
    if value == 0:
        return []

    return [item for item in enum_class if value & item.value]


def _list_to_bitwise(*, items: list[IntEnum]) -> int:
    """
    Convert list of enum values to bitwise integer.

    Example:
        _list_to_bitwise([Weekday.MONDAY, Weekday.FRIDAY]) -> 34
        _list_to_bitwise([Channel.CHANNEL_1, Channel.CHANNEL_3]) -> 5

    """
    if not items:
        return 0

    result = 0
    for item in items:
        result |= item.value
    return result


def raw_schedule_to_dict(*, raw_schedule: RAW_SCHEDULE) -> SCHEDULE_DICT:
    """
    Convert raw paramset schedule to structured dictionary.

    Args:
        raw_schedule: Raw schedule from CCU (e.g., {"01_WP_WEEKDAY": 127, ...})

    Returns:
        Structured dictionary grouped by schedule number

    Example:
        Input: {"01_WP_WEEKDAY": 127, "01_WP_LEVEL": 1, ...}
        Output: {1: {SwitchScheduleField.WEEKDAY: [Weekday.SUNDAY, ...], ...}}

    """
    schedule_dict: SCHEDULE_DICT = {}

    for key, value in raw_schedule.items():
        # Expected format: "01_WP_WEEKDAY"
        parts = key.split("_", 2)
        if len(parts) != 3 or parts[1] != "WP":
            continue

        try:
            group_no = int(parts[0])
            field_name = parts[2]
            field = ScheduleField[field_name]
        except (ValueError, KeyError):
            # Skip invalid entries
            continue

        if group_no not in schedule_dict:
            schedule_dict[group_no] = {}

        # Convert value based on field type
        int_value = int(value)

        if field == ScheduleField.ASTRO_TYPE:
            schedule_dict[group_no][field] = AstroType(int_value)
        elif field == ScheduleField.CONDITION:
            schedule_dict[group_no][field] = ScheduleCondition(int_value)
        elif field in (ScheduleField.DURATION_BASE, ScheduleField.RAMP_TIME_BASE):
            schedule_dict[group_no][field] = TimeBase(int_value)
        elif field == ScheduleField.LEVEL:
            schedule_dict[group_no][field] = int_value if isinstance(value, int) else float(value)
        elif field == ScheduleField.LEVEL_2:
            schedule_dict[group_no][field] = float(value)
        elif field == ScheduleField.WEEKDAY:
            schedule_dict[group_no][field] = _bitwise_to_list(value=int_value, enum_class=Weekday)
        elif field == ScheduleField.TARGET_CHANNELS:
            schedule_dict[group_no][field] = _bitwise_to_list(value=int_value, enum_class=ScheduleActorChannel)
        else:
            # ASTRO_OFFSET, DURATION_FACTOR, FIXED_HOUR, FIXED_MINUTE, RAMP_TIME_FACTOR
            schedule_dict[group_no][field] = int_value

    return schedule_dict


def dict_to_raw_schedule(*, schedule_dict: SCHEDULE_DICT) -> RAW_SCHEDULE:
    """
    Convert structured dictionary to raw paramset schedule.

    Args:
        schedule_dict: Structured schedule dictionary

    Returns:
        Raw schedule for CCU

    Example:
        Input: {1: {SwitchScheduleField.WEEKDAY: [Weekday.SUNDAY, ...], ...}}
        Output: {"01_WP_WEEKDAY": 127, "01_WP_LEVEL": 1, ...}

    """
    raw_schedule: RAW_SCHEDULE = {}

    for group_no, group_data in schedule_dict.items():
        for field, value in group_data.items():
            # Build parameter name: "01_WP_WEEKDAY"
            key = f"{group_no:02d}_WP_{field.value}"

            # Convert value based on field type
            if field in (
                ScheduleField.ASTRO_TYPE,
                ScheduleField.CONDITION,
                ScheduleField.DURATION_BASE,
                ScheduleField.RAMP_TIME_BASE,
            ):
                raw_schedule[key] = int(value.value)
            elif field in (ScheduleField.WEEKDAY, ScheduleField.TARGET_CHANNELS):
                raw_schedule[key] = _list_to_bitwise(items=value)
            elif field == ScheduleField.LEVEL:
                raw_schedule[key] = int(value.value) if isinstance(value, IntEnum) else float(value)
            elif field == ScheduleField.LEVEL_2:
                raw_schedule[key] = float(value)
            else:
                # ASTRO_OFFSET, DURATION_FACTOR, FIXED_HOUR, FIXED_MINUTE, RAMP_TIME_FACTOR
                raw_schedule[key] = int(value)

    return raw_schedule


def is_schedule_active(group_data: SCHEDULE_GROUP) -> bool:
    """
    Check if a schedule group is active (not all zeros).

    Args:
        group_data: Schedule group data

    Returns:
        True if schedule is active, False if deactivated

    Example:
        Deactivated: all values are 0
        Active: at least one non-zero value

    """
    # Check critical fields
    weekday = group_data.get(ScheduleField.WEEKDAY, [])
    target_channels = group_data.get(ScheduleField.TARGET_CHANNELS, [])

    # If weekday or target_channels are empty, schedule is inactive
    return not (not weekday or not target_channels)


def create_empty_schedule_group(category: DataPointCategory | None = None) -> SCHEDULE_GROUP:
    """
    Create an empty/deactivated schedule group with all zeros.

    Returns:
        Schedule group with all fields set to inactive state

    """
    empty_schedule_group = {
        ScheduleField.ASTRO_OFFSET: 0,
        ScheduleField.ASTRO_TYPE: AstroType.SUNRISE,
        ScheduleField.CONDITION: ScheduleCondition.FIXED_TIME,
        ScheduleField.FIXED_HOUR: 0,
        ScheduleField.FIXED_MINUTE: 0,
        ScheduleField.TARGET_CHANNELS: [],
        ScheduleField.WEEKDAY: [],
    }
    if category == DataPointCategory.COVER:
        empty_schedule_group.update(
            {
                ScheduleField.LEVEL: 0.0,
                ScheduleField.LEVEL_2: 0.0,
            }
        )
    if category == DataPointCategory.SWITCH:
        empty_schedule_group.update(
            {
                ScheduleField.DURATION_BASE: TimeBase.MS_100,
                ScheduleField.DURATION_FACTOR: 0,
                ScheduleField.LEVEL: 0,
            }
        )
    if category == DataPointCategory.LIGHT:
        empty_schedule_group.update(
            {
                ScheduleField.DURATION_BASE: TimeBase.MS_100,
                ScheduleField.DURATION_FACTOR: 0,
                ScheduleField.RAMP_TIME_BASE: TimeBase.MS_100,
                ScheduleField.RAMP_TIME_FACTOR: 0,
                ScheduleField.LEVEL: 0.0,
            }
        )
    if category == DataPointCategory.VALVE:
        empty_schedule_group.update(
            {
                ScheduleField.LEVEL: 0.0,
            }
        )
    return empty_schedule_group
