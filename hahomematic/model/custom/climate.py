"""Module for data points implemented using the climate category."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from enum import IntEnum, StrEnum
import logging
from typing import Any, Final, cast

from hahomematic.const import (
    SCHEDULER_PROFILE_PATTERN,
    SCHEDULER_TIME_PATTERN,
    DataPointCategory,
    Parameter,
    ParamsetKey,
    ProductGroup,
)
from hahomematic.decorators import inspector
from hahomematic.exceptions import ClientException, ValidationException
from hahomematic.model import device as hmd
from hahomematic.model.custom import definition as hmed
from hahomematic.model.custom.const import DeviceProfile, Field
from hahomematic.model.custom.data_point import CustomDataPoint
from hahomematic.model.custom.support import CustomConfig
from hahomematic.model.data_point import CallParameterCollector, bind_collector
from hahomematic.model.decorators import config_property, state_property
from hahomematic.model.generic import DpAction, DpBinarySensor, DpFloat, DpInteger, DpSelect, DpSensor, DpSwitch

_LOGGER: Final = logging.getLogger(__name__)

_CLOSED_LEVEL: Final = 0.0
_DEFAULT_TEMPERATURE_STEP: Final = 0.5
_MAX_SCHEDULER_TIME: Final = "24:00"
_MIN_SCHEDULER_TIME: Final = "00:00"
_OFF_TEMPERATURE: Final = 4.5
_PARTY_DATE_FORMAT: Final = "%Y_%m_%d %H:%M"
_PARTY_INIT_DATE: Final = "2000_01_01 00:00"
_RAW_SCHEDULE_DICT = dict[str, float | int]
_TEMP_CELSIUS: Final = "°C"
PROFILE_PREFIX: Final = "week_program_"
SCHEDULE_SLOT_RANGE: Final = range(1, 13)
SCHEDULE_SLOT_IN_RANGE: Final = range(1, 14)
SCHEDULE_TIME_RANGE: Final = range(1441)


class _ModeHm(StrEnum):
    """Enum with the HM modes."""

    AUTO = "AUTO-MODE"  # 0
    AWAY = "PARTY-MODE"  # 2
    BOOST = "BOOST-MODE"  # 3
    MANU = "MANU-MODE"  # 1


class _ModeHmIP(IntEnum):
    """Enum with the HmIP modes."""

    AUTO = 0
    AWAY = 2
    MANU = 1


class _StateChangeArg(StrEnum):
    """Enum with climate state change arguments."""

    MODE = "mode"
    PROFILE = "profile"
    TEMPERATURE = "temperature"


class ClimateActivity(StrEnum):
    """Enum with the climate activities."""

    COOL = "cooling"
    HEAT = "heating"
    IDLE = "idle"
    OFF = "off"


class ClimateHeatingValveType(StrEnum):
    """Enum with the climate heating valve types."""

    NORMALLY_CLOSE = "NORMALLY_CLOSE"
    NORMALLY_OPEN = "NORMALLY_OPEN"


class ClimateMode(StrEnum):
    """Enum with the thermostat modes."""

    AUTO = "auto"
    COOL = "cool"
    HEAT = "heat"
    OFF = "off"


class ClimateProfile(StrEnum):
    """Enum with profiles."""

    AWAY = "away"
    BOOST = "boost"
    COMFORT = "comfort"
    ECO = "eco"
    NONE = "none"
    WEEK_PROGRAM_1 = "week_program_1"
    WEEK_PROGRAM_2 = "week_program_2"
    WEEK_PROGRAM_3 = "week_program_3"
    WEEK_PROGRAM_4 = "week_program_4"
    WEEK_PROGRAM_5 = "week_program_5"
    WEEK_PROGRAM_6 = "week_program_6"


_HM_WEEK_PROFILE_POINTERS_TO_NAMES: Final = {
    0: "WEEK PROGRAM 1",
    1: "WEEK PROGRAM 2",
    2: "WEEK PROGRAM 3",
    3: "WEEK PROGRAM 4",
    4: "WEEK PROGRAM 5",
    5: "WEEK PROGRAM 6",
}
_HM_WEEK_PROFILE_POINTERS_TO_IDX: Final = {v: k for k, v in _HM_WEEK_PROFILE_POINTERS_TO_NAMES.items()}


class ScheduleSlotType(StrEnum):
    """Enum for climate item type."""

    ENDTIME = "ENDTIME"
    STARTTIME = "STARTTIME"
    TEMPERATURE = "TEMPERATURE"


RELEVANT_SLOT_TYPES: Final = (ScheduleSlotType.ENDTIME, ScheduleSlotType.TEMPERATURE)


class ScheduleProfile(StrEnum):
    """Enum for climate profiles."""

    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"
    P5 = "P5"
    P6 = "P6"


class ScheduleWeekday(StrEnum):
    """Enum for climate week days."""

    MONDAY = "MONDAY"
    TUESDAY = "TUESDAY"
    WEDNESDAY = "WEDNESDAY"
    THURSDAY = "THURSDAY"
    FRIDAY = "FRIDAY"
    SATURDAY = "SATURDAY"
    SUNDAY = "SUNDAY"


SIMPLE_WEEKDAY_LIST = list[dict[ScheduleSlotType, str | float]]
SIMPLE_PROFILE_DICT = dict[ScheduleWeekday, SIMPLE_WEEKDAY_LIST]
WEEKDAY_DICT = dict[int, dict[ScheduleSlotType, str | float]]
PROFILE_DICT = dict[ScheduleWeekday, WEEKDAY_DICT]
_SCHEDULE_DICT = dict[ScheduleProfile, PROFILE_DICT]


class BaseCustomDpClimate(CustomDataPoint):
    """Base HomeMatic climate data_point."""

    _category = DataPointCategory.CLIMATE
    _supports_schedule = False

    def _init_data_point_fields(self) -> None:
        """Init the data_point fields."""
        super()._init_data_point_fields()
        self._dp_humidity: DpSensor[int | None] = self._get_data_point(
            field=Field.HUMIDITY, data_point_type=DpSensor[int | None]
        )
        self._dp_min_max_value_not_relevant_for_manu_mode: DpBinarySensor = self._get_data_point(
            field=Field.MIN_MAX_VALUE_NOT_RELEVANT_FOR_MANU_MODE, data_point_type=DpBinarySensor
        )
        self._dp_setpoint: DpFloat = self._get_data_point(field=Field.SETPOINT, data_point_type=DpFloat)
        self._dp_temperature: DpSensor[float | None] = self._get_data_point(
            field=Field.TEMPERATURE, data_point_type=DpSensor[float | None]
        )
        self._dp_temperature_maximum: DpFloat = self._get_data_point(
            field=Field.TEMPERATURE_MAXIMUM, data_point_type=DpFloat
        )
        self._dp_temperature_minimum: DpFloat = self._get_data_point(
            field=Field.TEMPERATURE_MINIMUM, data_point_type=DpFloat
        )

    @state_property
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        return self._dp_humidity.value

    @state_property
    def current_temperature(self) -> float | None:
        """Return current temperature."""
        return self._dp_temperature.value

    @state_property
    def activity(self) -> ClimateActivity | None:
        """Return the current activity."""
        return None

    @state_property
    def mode(self) -> ClimateMode:
        """Return current operation mode."""
        return ClimateMode.HEAT

    @state_property
    def modes(self) -> tuple[ClimateMode, ...]:
        """Return the available operation modes."""
        return (ClimateMode.HEAT,)

    @state_property
    def min_max_value_not_relevant_for_manu_mode(self) -> bool:
        """Return the maximum temperature."""
        if self._dp_min_max_value_not_relevant_for_manu_mode.value is not None:
            return self._dp_min_max_value_not_relevant_for_manu_mode.value
        return False

    @state_property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        if self._dp_temperature_minimum.value is not None:
            min_temp = float(self._dp_temperature_minimum.value)
        else:
            min_temp = self._dp_setpoint.min

        if min_temp == _OFF_TEMPERATURE:
            return min_temp + _DEFAULT_TEMPERATURE_STEP
        return min_temp

    @state_property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        if self._dp_temperature_maximum.value is not None:
            return float(self._dp_temperature_maximum.value)
        return cast(float, self._dp_setpoint.max)

    @state_property
    def profile(self) -> ClimateProfile:
        """Return the current profile."""
        return ClimateProfile.NONE

    @state_property
    def profiles(self) -> tuple[ClimateProfile, ...]:
        """Return available profiles."""
        return (ClimateProfile.NONE,)

    @state_property
    def target_temperature(self) -> float | None:
        """Return target temperature."""
        return self._dp_setpoint.value

    @config_property
    def target_temperature_step(self) -> float:
        """Return the supported step of target temperature."""
        return _DEFAULT_TEMPERATURE_STEP

    @property
    def schedule_channel_address(self) -> str:
        """Return schedule channel address."""
        return (
            self._channel.address
            if self._channel.device.product_group in (ProductGroup.HMIP, ProductGroup.HMIPW)
            else self._device.address
        )

    @property
    def supports_profiles(self) -> bool:
        """Flag if climate supports profiles."""
        return False

    @config_property
    def temperature_unit(self) -> str:
        """Return temperature unit."""
        return _TEMP_CELSIUS

    @property
    def _min_or_target_temperature(self) -> float:
        """Return the min or target temperature."""
        if (temperature := self.target_temperature or self.min_temp) < self.min_temp:
            return self.min_temp
        return temperature

    @property
    def schedule_profile_nos(self) -> int:
        """Return the number of supported profiles."""
        return 0

    @bind_collector()
    async def set_temperature(
        self,
        temperature: float,
        collector: CallParameterCollector | None = None,
        do_validate: bool = True,
    ) -> None:
        """Set new target temperature."""
        if not self.is_state_change(temperature=temperature):
            return

        if do_validate and self.mode == ClimateMode.HEAT and self.min_max_value_not_relevant_for_manu_mode:
            do_validate = False

        if do_validate and not (self.min_temp <= temperature <= self.max_temp):
            raise ValueError(
                f"SET_TEMPERATURE failed: Invalid temperature: {temperature} (min: {self.min_temp}, max: {self.max_temp})"
            )

        await self._dp_setpoint.send_value(value=temperature, collector=collector, do_validate=do_validate)

    @bind_collector()
    async def set_mode(self, mode: ClimateMode, collector: CallParameterCollector | None = None) -> None:
        """Set new target mode."""

    @bind_collector()
    async def set_profile(self, profile: ClimateProfile, collector: CallParameterCollector | None = None) -> None:
        """Set new profile."""

    @inspector()
    async def enable_away_mode_by_calendar(self, start: datetime, end: datetime, away_temperature: float) -> None:
        """Enable the away mode by calendar on thermostat."""

    @inspector()
    async def enable_away_mode_by_duration(self, hours: int, away_temperature: float) -> None:
        """Enable the away mode by duration on thermostat."""

    @inspector()
    async def disable_away_mode(self) -> None:
        """Disable the away mode on thermostat."""

    def is_state_change(self, **kwargs: Any) -> bool:
        """Check if the state changes due to kwargs."""
        if (
            temperature := kwargs.get(_StateChangeArg.TEMPERATURE)
        ) is not None and temperature != self.target_temperature:
            return True
        if (mode := kwargs.get(_StateChangeArg.MODE)) is not None and mode != self.mode:
            return True
        if (profile := kwargs.get(_StateChangeArg.PROFILE)) is not None and profile != self.profile:
            return True
        return super().is_state_change(**kwargs)

    @inspector()
    async def copy_schedule(self, target_climate_data_point: BaseCustomDpClimate) -> None:
        """Copy schedule to target device."""

        if self.schedule_profile_nos != target_climate_data_point.schedule_profile_nos:
            raise ValidationException("Copy schedule profile is only: No of schedule profile must be identical")
        raw_schedule = await self._get_raw_schedule()
        await self._client.put_paramset(
            channel_address=target_climate_data_point.schedule_channel_address,
            paramset_key_or_link_address=ParamsetKey.MASTER,
            values=raw_schedule,
        )

    @inspector()
    async def copy_schedule_profile(
        self,
        source_profile: ScheduleProfile,
        target_profile: ScheduleProfile,
        target_climate_data_point: BaseCustomDpClimate | None = None,
    ) -> None:
        """Copy schedule profile to target device."""
        same_device = False
        if not self._supports_schedule:
            raise ValidationException(f"Schedule is not supported by device {self._device.name}")
        if target_climate_data_point is None:
            target_climate_data_point = self
        if self is target_climate_data_point:
            same_device = True

        if same_device and (source_profile == target_profile or (source_profile is None or target_profile is None)):
            raise ValidationException(
                "Copy schedule profile on same device is only possible with defined and different source/target profiles"
            )

        if (source_profile_data := await self.get_schedule_profile(profile=source_profile)) is None:
            raise ValidationException(f"Source profile {source_profile} could not be loaded.")
        await self._set_schedule_profile(
            target_channel_address=target_climate_data_point.schedule_channel_address,
            profile=target_profile,
            profile_data=source_profile_data,
            do_validate=False,
        )

    @inspector()
    async def get_schedule_profile(self, profile: ScheduleProfile) -> PROFILE_DICT:
        """Return a schedule by climate profile."""
        if not self._supports_schedule:
            raise ValidationException(f"Schedule is not supported by device {self._device.name}")
        schedule_data = await self._get_schedule_profile(profile=profile)
        return schedule_data.get(profile, {})

    @inspector()
    async def get_schedule_profile_weekday(self, profile: ScheduleProfile, weekday: ScheduleWeekday) -> WEEKDAY_DICT:
        """Return a schedule by climate profile."""
        if not self._supports_schedule:
            raise ValidationException(f"Schedule is not supported by device {self._device.name}")
        schedule_data = await self._get_schedule_profile(profile=profile, weekday=weekday)
        return schedule_data.get(profile, {}).get(weekday, {})

    async def _get_raw_schedule(self) -> _RAW_SCHEDULE_DICT:
        """Return the raw schedule."""
        try:
            raw_data = await self._client.get_paramset(
                address=self.schedule_channel_address,
                paramset_key=ParamsetKey.MASTER,
            )
            raw_schedule = {key: value for key, value in raw_data.items() if SCHEDULER_PROFILE_PATTERN.match(key)}
        except ClientException as cex:
            self._supports_schedule = False
            raise ValidationException(f"Schedule is not supported by device {self._device.name}") from cex
        return raw_schedule

    async def _get_schedule_profile(
        self, profile: ScheduleProfile | None = None, weekday: ScheduleWeekday | None = None
    ) -> _SCHEDULE_DICT:
        """Get the schedule."""
        schedule_data: _SCHEDULE_DICT = {}
        raw_schedule = await self._get_raw_schedule()
        for slot_name, slot_value in raw_schedule.items():
            slot_name_tuple = slot_name.split("_")
            if len(slot_name_tuple) != 4:
                continue
            profile_name, slot_type, slot_weekday, slot_no = slot_name_tuple
            _profile = ScheduleProfile(profile_name)
            if profile and profile != _profile:
                continue
            _slot_type = ScheduleSlotType(slot_type)
            _weekday = ScheduleWeekday(slot_weekday)
            if weekday and weekday != _weekday:
                continue
            _slot_no = int(slot_no)

            _add_to_schedule_data(
                schedule_data=schedule_data,
                profile=_profile,
                weekday=_weekday,
                slot_no=_slot_no,
                slot_type=_slot_type,
                slot_value=slot_value,
            )

        return schedule_data

    @inspector()
    async def set_schedule_profile(
        self, profile: ScheduleProfile, profile_data: PROFILE_DICT, do_validate: bool = True
    ) -> None:
        """Set a profile to device."""
        await self._set_schedule_profile(
            target_channel_address=self.schedule_channel_address,
            profile=profile,
            profile_data=profile_data,
            do_validate=do_validate,
        )

    async def _set_schedule_profile(
        self,
        target_channel_address: str,
        profile: ScheduleProfile,
        profile_data: PROFILE_DICT,
        do_validate: bool,
    ) -> None:
        """Set a profile to device."""
        if do_validate:
            self._validate_schedule_profile(profile=profile, profile_data=profile_data)
        schedule_data: _SCHEDULE_DICT = {}
        for weekday, weekday_data in profile_data.items():
            for slot_no, slot in weekday_data.items():
                for slot_type, slot_value in slot.items():
                    _add_to_schedule_data(
                        schedule_data=schedule_data,
                        profile=profile,
                        weekday=weekday,
                        slot_no=slot_no,
                        slot_type=slot_type,
                        slot_value=slot_value,
                    )
        await self._client.put_paramset(
            channel_address=target_channel_address,
            paramset_key_or_link_address=ParamsetKey.MASTER,
            values=_get_raw_schedule_paramset(schedule_data=schedule_data),
        )

    @inspector()
    async def set_simple_schedule_profile(
        self,
        profile: ScheduleProfile,
        base_temperature: float,
        simple_profile_data: SIMPLE_PROFILE_DICT,
    ) -> None:
        """Set a profile to device."""
        profile_data = self._validate_and_convert_simple_to_profile(
            base_temperature=base_temperature, simple_profile_data=simple_profile_data
        )
        await self.set_schedule_profile(profile=profile, profile_data=profile_data)

    @inspector()
    async def set_schedule_profile_weekday(
        self,
        profile: ScheduleProfile,
        weekday: ScheduleWeekday,
        weekday_data: WEEKDAY_DICT,
        do_validate: bool = True,
    ) -> None:
        """Store a profile to device."""
        if do_validate:
            self._validate_schedule_profile_weekday(profile=profile, weekday=weekday, weekday_data=weekday_data)
        schedule_data: _SCHEDULE_DICT = {}
        for slot_no, slot in weekday_data.items():
            for slot_type, slot_value in slot.items():
                _add_to_schedule_data(
                    schedule_data=schedule_data,
                    profile=profile,
                    weekday=weekday,
                    slot_no=slot_no,
                    slot_type=slot_type,
                    slot_value=slot_value,
                )
        await self._client.put_paramset(
            channel_address=self.schedule_channel_address,
            paramset_key_or_link_address=ParamsetKey.MASTER,
            values=_get_raw_schedule_paramset(schedule_data=schedule_data),
        )

    @inspector()
    async def set_simple_schedule_profile_weekday(
        self,
        profile: ScheduleProfile,
        weekday: ScheduleWeekday,
        base_temperature: float,
        simple_weekday_list: SIMPLE_WEEKDAY_LIST,
    ) -> None:
        """Store a simple weekday profile to device."""
        weekday_data = self._validate_and_convert_simple_to_profile_weekday(
            base_temperature=base_temperature, simple_weekday_list=simple_weekday_list
        )
        await self.set_schedule_profile_weekday(profile=profile, weekday=weekday, weekday_data=weekday_data)

    def _validate_and_convert_simple_to_profile(
        self, base_temperature: float, simple_profile_data: SIMPLE_PROFILE_DICT
    ) -> PROFILE_DICT:
        """Convert simple profile dict to profile dict."""
        profile_dict: PROFILE_DICT = {}
        for day, simple_weekday_list in simple_profile_data.items():
            profile_dict[day] = self._validate_and_convert_simple_to_profile_weekday(
                base_temperature=base_temperature, simple_weekday_list=simple_weekday_list
            )
        return profile_dict

    def _validate_and_convert_simple_to_profile_weekday(
        self, base_temperature: float, simple_weekday_list: SIMPLE_WEEKDAY_LIST
    ) -> WEEKDAY_DICT:
        """Convert simple weekday list to weekday dict."""
        if not self.min_temp <= base_temperature <= self.max_temp:
            raise ValidationException(
                f"VALIDATE_PROFILE: Base temperature {base_temperature} not in valid range (min: {self.min_temp}, "
                f"max: {self.max_temp})"
            )

        weekday_data: WEEKDAY_DICT = {}
        sorted_simple_weekday_list = _sort_simple_weekday_list(simple_weekday_list=simple_weekday_list)
        previous_endtime = _MIN_SCHEDULER_TIME
        slot_no = 1
        for slot in sorted_simple_weekday_list:
            if (starttime := slot.get(ScheduleSlotType.STARTTIME)) is None:
                raise ValidationException("VALIDATE_PROFILE: STARTTIME is missing.")
            if (endtime := slot.get(ScheduleSlotType.ENDTIME)) is None:
                raise ValidationException("VALIDATE_PROFILE: ENDTIME is missing.")
            if (temperature := slot.get(ScheduleSlotType.TEMPERATURE)) is None:
                raise ValidationException("VALIDATE_PROFILE: TEMPERATURE is missing.")

            if _convert_time_str_to_minutes(str(starttime)) >= _convert_time_str_to_minutes(str(endtime)):
                raise ValidationException(
                    f"VALIDATE_PROFILE: Start time {starttime} must lower than end time {endtime}"
                )

            if _convert_time_str_to_minutes(str(starttime)) < _convert_time_str_to_minutes(previous_endtime):
                raise ValidationException(
                    f"VALIDATE_PROFILE: Timespans are overlapping with a previous slot for start time: {starttime} / end time: {endtime}"
                )

            if not self.min_temp <= float(temperature) <= self.max_temp:
                raise ValidationException(
                    f"VALIDATE_PROFILE: Temperature {temperature} not in valid range (min: {self.min_temp}, "
                    f"max: {self.max_temp}) for start time: {starttime} / end time: {endtime}"
                )

            if _convert_time_str_to_minutes(str(starttime)) > _convert_time_str_to_minutes(previous_endtime):
                weekday_data[slot_no] = {
                    ScheduleSlotType.ENDTIME: starttime,
                    ScheduleSlotType.TEMPERATURE: base_temperature,
                }
                slot_no += 1

            weekday_data[slot_no] = {
                ScheduleSlotType.ENDTIME: endtime,
                ScheduleSlotType.TEMPERATURE: temperature,
            }
            previous_endtime = str(endtime)
            slot_no += 1

        return _fillup_weekday_data(base_temperature=base_temperature, weekday_data=weekday_data)

    def _validate_schedule_profile(self, profile: ScheduleProfile, profile_data: PROFILE_DICT) -> None:
        """Validate the profile."""
        for weekday, weekday_data in profile_data.items():
            self._validate_schedule_profile_weekday(profile=profile, weekday=weekday, weekday_data=weekday_data)

    def _validate_schedule_profile_weekday(
        self,
        profile: ScheduleProfile,
        weekday: ScheduleWeekday,
        weekday_data: WEEKDAY_DICT,
    ) -> None:
        """Validate the profile weekday."""
        previous_endtime = 0
        if len(weekday_data) != 13:
            raise ValidationException(
                f"VALIDATE_PROFILE: {'Too many' if len(weekday_data) > 13 else 'Too few'} slots in profile: {profile} / week day: {weekday}"
            )
        for no in SCHEDULE_SLOT_RANGE:
            if no not in weekday_data:
                raise ValidationException(
                    f"VALIDATE_PROFILE: slot no {no} is missing in profile: {profile} / week day: {weekday}"
                )
            slot = weekday_data[no]
            for slot_type in RELEVANT_SLOT_TYPES:
                if slot_type not in slot:
                    raise ValidationException(
                        f"VALIDATE_PROFILE: slot type {slot_type} is missing in profile: "
                        f"{profile} / week day: {weekday} / slot no: {no}"
                    )
                temperature = float(weekday_data[no][ScheduleSlotType.TEMPERATURE])
                if not self.min_temp <= temperature <= self.max_temp:
                    raise ValidationException(
                        f"VALIDATE_PROFILE: Temperature {temperature} not in valid range (min: {self.min_temp}, "
                        f"max: {self.max_temp}) for profile: {profile} / week day: {weekday} / slot no: {no}"
                    )

                endtime_str = str(weekday_data[no][ScheduleSlotType.ENDTIME])
                if endtime := _convert_time_str_to_minutes(time_str=endtime_str):
                    if endtime not in SCHEDULE_TIME_RANGE:
                        raise ValidationException(
                            f"VALIDATE_PROFILE: Time {endtime_str} must be between {_convert_minutes_to_time_str(minutes=SCHEDULE_TIME_RANGE.start)} and "
                            f"{_convert_minutes_to_time_str(minutes=SCHEDULE_TIME_RANGE.stop - 1)} for profile: {profile} / week day: {weekday} / slot no: {no}"
                        )
                    if endtime < previous_endtime:
                        raise ValidationException(
                            f"VALIDATE_PROFILE: Time sequence must be rising. {endtime_str} is lower than the previous "
                            f"value {_convert_minutes_to_time_str(minutes=previous_endtime)} for profile: {profile} / week day: {weekday} / slot no: {no}"
                        )
                previous_endtime = endtime


class CustomDpSimpleRfThermostat(BaseCustomDpClimate):
    """Simple classic HomeMatic thermostat HM-CC-TC."""


class CustomDpRfThermostat(BaseCustomDpClimate):
    """Classic HomeMatic thermostat like HM-CC-RT-DN."""

    _supports_schedule = True

    def _init_data_point_fields(self) -> None:
        """Init the data_point fields."""
        super()._init_data_point_fields()
        self._dp_boost_mode: DpAction = self._get_data_point(field=Field.BOOST_MODE, data_point_type=DpAction)
        self._dp_auto_mode: DpAction = self._get_data_point(field=Field.AUTO_MODE, data_point_type=DpAction)
        self._dp_manu_mode: DpAction = self._get_data_point(field=Field.MANU_MODE, data_point_type=DpAction)
        self._dp_comfort_mode: DpAction = self._get_data_point(field=Field.COMFORT_MODE, data_point_type=DpAction)
        self._dp_lowering_mode: DpAction = self._get_data_point(field=Field.LOWERING_MODE, data_point_type=DpAction)
        self._dp_control_mode: DpSensor[str | None] = self._get_data_point(
            field=Field.CONTROL_MODE, data_point_type=DpSensor[str | None]
        )
        self._dp_temperature_offset: DpSelect = self._get_data_point(
            field=Field.TEMPERATURE_OFFSET, data_point_type=DpSelect
        )
        self._dp_valve_state: DpSensor[int | None] = self._get_data_point(
            field=Field.VALVE_STATE, data_point_type=DpSensor[int | None]
        )
        self._dp_week_program_pointer: DpSelect = self._get_data_point(
            field=Field.WEEK_PROGRAM_POINTER, data_point_type=DpSelect
        )

    @state_property
    def activity(self) -> ClimateActivity | None:
        """Return the current activity."""
        if self._dp_valve_state.value is None:
            return None
        if self.mode == ClimateMode.OFF:
            return ClimateActivity.OFF
        if self._dp_valve_state.value and self._dp_valve_state.value > 0:
            return ClimateActivity.HEAT
        return ClimateActivity.IDLE

    @state_property
    def mode(self) -> ClimateMode:
        """Return current operation mode."""
        if self.target_temperature and self.target_temperature <= _OFF_TEMPERATURE:
            return ClimateMode.OFF
        if self._dp_control_mode.value == _ModeHm.MANU:
            return ClimateMode.HEAT
        return ClimateMode.AUTO

    @state_property
    def modes(self) -> tuple[ClimateMode, ...]:
        """Return the available operation modes."""
        return (ClimateMode.AUTO, ClimateMode.HEAT, ClimateMode.OFF)

    @state_property
    def profile(self) -> ClimateProfile:
        """Return the current profile."""
        if self._dp_control_mode.value is None:
            return ClimateProfile.NONE
        if self._dp_control_mode.value == _ModeHm.BOOST:
            return ClimateProfile.BOOST
        if self._dp_control_mode.value == _ModeHm.AWAY:
            return ClimateProfile.AWAY
        if self.mode == ClimateMode.AUTO:
            return self._current_profile_name if self._current_profile_name else ClimateProfile.NONE
        return ClimateProfile.NONE

    @state_property
    def profiles(self) -> tuple[ClimateProfile, ...]:
        """Return available profile."""
        control_modes = [ClimateProfile.BOOST, ClimateProfile.COMFORT, ClimateProfile.ECO, ClimateProfile.NONE]
        if self.mode == ClimateMode.AUTO:
            control_modes.extend(self._profile_names)
        return tuple(control_modes)

    @property
    def supports_profiles(self) -> bool:
        """Flag if climate supports profiles."""
        return True

    @state_property
    def temperature_offset(self) -> str | None:
        """Return the maximum temperature."""
        return self._dp_temperature_offset.value

    @bind_collector()
    async def set_mode(self, mode: ClimateMode, collector: CallParameterCollector | None = None) -> None:
        """Set new mode."""
        if not self.is_state_change(mode=mode):
            return
        if mode == ClimateMode.AUTO:
            await self._dp_auto_mode.send_value(value=True, collector=collector)
        elif mode == ClimateMode.HEAT:
            await self._dp_manu_mode.send_value(value=self._min_or_target_temperature, collector=collector)
        elif mode == ClimateMode.OFF:
            await self._dp_manu_mode.send_value(value=self.target_temperature, collector=collector)
            # Disable validation here to allow setting a value,
            # that is out of the validation range.
            await self.set_temperature(temperature=_OFF_TEMPERATURE, collector=collector, do_validate=False)

    @bind_collector()
    async def set_profile(self, profile: ClimateProfile, collector: CallParameterCollector | None = None) -> None:
        """Set new profile."""
        if not self.is_state_change(profile=profile):
            return
        if profile == ClimateProfile.BOOST:
            await self._dp_boost_mode.send_value(value=True, collector=collector)
        elif profile == ClimateProfile.COMFORT:
            await self._dp_comfort_mode.send_value(value=True, collector=collector)
        elif profile == ClimateProfile.ECO:
            await self._dp_lowering_mode.send_value(value=True, collector=collector)
        elif profile in self._profile_names:
            if self.mode != ClimateMode.AUTO:
                await self.set_mode(mode=ClimateMode.AUTO, collector=collector)
                await self._dp_boost_mode.send_value(value=False, collector=collector)
            if (profile_idx := self._profiles.get(profile)) is not None:
                await self._dp_week_program_pointer.send_value(
                    value=_HM_WEEK_PROFILE_POINTERS_TO_NAMES[profile_idx], collector=collector
                )

    @inspector()
    async def enable_away_mode_by_calendar(self, start: datetime, end: datetime, away_temperature: float) -> None:
        """Enable the away mode by calendar on thermostat."""
        await self._client.set_value(
            channel_address=self._channel.address,
            paramset_key=ParamsetKey.VALUES,
            parameter=Parameter.PARTY_MODE_SUBMIT,
            value=_party_mode_code(start=start, end=end, away_temperature=away_temperature),
        )

    @inspector()
    async def enable_away_mode_by_duration(self, hours: int, away_temperature: float) -> None:
        """Enable the away mode by duration on thermostat."""
        start = datetime.now() - timedelta(minutes=10)
        end = datetime.now() + timedelta(hours=hours)
        await self.enable_away_mode_by_calendar(start=start, end=end, away_temperature=away_temperature)

    @inspector()
    async def disable_away_mode(self) -> None:
        """Disable the away mode on thermostat."""
        start = datetime.now() - timedelta(hours=11)
        end = datetime.now() - timedelta(hours=10)

        await self._client.set_value(
            channel_address=self._channel.address,
            paramset_key=ParamsetKey.VALUES,
            parameter=Parameter.PARTY_MODE_SUBMIT,
            value=_party_mode_code(start=start, end=end, away_temperature=12.0),
        )

    @property
    def _profile_names(self) -> tuple[ClimateProfile, ...]:
        """Return a collection of profile names."""
        return tuple(self._profiles.keys())

    @property
    def _current_profile_name(self) -> ClimateProfile | None:
        """Return a profile index by name."""
        inv_profiles = {v: k for k, v in self._profiles.items()}
        if self._dp_week_program_pointer.value is not None:
            idx = (
                int(self._dp_week_program_pointer.value)
                if self._dp_week_program_pointer.value.isnumeric()
                else _HM_WEEK_PROFILE_POINTERS_TO_IDX[self._dp_week_program_pointer.value]
            )
            return inv_profiles.get(idx)
        return None

    @property
    def _profiles(self) -> Mapping[ClimateProfile, int]:
        """Return the profile groups."""
        profiles: dict[ClimateProfile, int] = {}
        if self._dp_week_program_pointer.min is not None and self._dp_week_program_pointer.max is not None:
            for i in range(int(self._dp_week_program_pointer.min) + 1, int(self._dp_week_program_pointer.max) + 2):
                profiles[ClimateProfile(f"{PROFILE_PREFIX}{i}")] = i - 1

        return profiles


def _party_mode_code(start: datetime, end: datetime, away_temperature: float) -> str:
    """
    Create the party mode code.

    e.g. 21.5,1200,20,10,16,1380,20,10,16
    away_temperature,start_minutes_of_day, day(2), month(2), year(2), end_minutes_of_day, day(2), month(2), year(2)
    """
    return f"{away_temperature:.1f},{start.hour * 60 + start.minute},{start.strftime('%d,%m,%y')},{end.hour * 60 + end.minute},{end.strftime('%d,%m,%y')}"


class CustomDpIpThermostat(BaseCustomDpClimate):
    """HomematicIP thermostat like HmIP-eTRV-B."""

    _supports_schedule = True

    def _init_data_point_fields(self) -> None:
        """Init the data_point fields."""
        super()._init_data_point_fields()
        self._dp_active_profile: DpInteger = self._get_data_point(field=Field.ACTIVE_PROFILE, data_point_type=DpInteger)
        self._dp_boost_mode: DpSwitch = self._get_data_point(field=Field.BOOST_MODE, data_point_type=DpSwitch)
        self._dp_control_mode: DpAction = self._get_data_point(field=Field.CONTROL_MODE, data_point_type=DpAction)
        self._dp_heating_mode: DpSelect = self._get_data_point(field=Field.HEATING_COOLING, data_point_type=DpSelect)
        self._dp_heating_valve_type: DpSelect = self._get_data_point(
            field=Field.HEATING_VALVE_TYPE, data_point_type=DpSelect
        )
        self._dp_level: DpFloat = self._get_data_point(field=Field.LEVEL, data_point_type=DpFloat)
        self._dp_optimum_start_stop: DpBinarySensor = self._get_data_point(
            field=Field.OPTIMUM_START_STOP, data_point_type=DpBinarySensor
        )
        self._dp_party_mode: DpBinarySensor = self._get_data_point(
            field=Field.PARTY_MODE, data_point_type=DpBinarySensor
        )
        self._dp_set_point_mode: DpInteger = self._get_data_point(field=Field.SET_POINT_MODE, data_point_type=DpInteger)
        self._dp_state: DpBinarySensor = self._get_data_point(field=Field.STATE, data_point_type=DpBinarySensor)
        self._dp_temperature_offset: DpFloat = self._get_data_point(
            field=Field.TEMPERATURE_OFFSET, data_point_type=DpFloat
        )

    @property
    def _is_heating_mode(self) -> bool:
        """Return the heating_mode of the device."""
        if self._dp_heating_mode.value is not None:
            return str(self._dp_heating_mode.value) == "HEATING"
        return True

    @state_property
    def activity(self) -> ClimateActivity | None:
        """Return the current activity."""
        if self._dp_state.value is None and self._dp_level.value is None:
            return None
        if self.mode == ClimateMode.OFF:
            return ClimateActivity.OFF
        if self._dp_level.value and self._dp_level.value > _CLOSED_LEVEL:
            return ClimateActivity.HEAT
        if (self._dp_heating_valve_type.value is None and self._dp_state.value is True) or (
            self._dp_heating_valve_type.value
            and (
                (
                    self._dp_state.value is True
                    and self._dp_heating_valve_type.value == ClimateHeatingValveType.NORMALLY_CLOSE
                )
                or (
                    self._dp_state.value is False
                    and self._dp_heating_valve_type.value == ClimateHeatingValveType.NORMALLY_OPEN
                )
            )
        ):
            return ClimateActivity.HEAT if self._is_heating_mode else ClimateActivity.COOL
        return ClimateActivity.IDLE

    @state_property
    def mode(self) -> ClimateMode:
        """Return current operation mode."""
        if self.target_temperature and self.target_temperature <= _OFF_TEMPERATURE:
            return ClimateMode.OFF
        if self._dp_set_point_mode.value == _ModeHmIP.MANU:
            return ClimateMode.HEAT if self._is_heating_mode else ClimateMode.COOL
        if self._dp_set_point_mode.value == _ModeHmIP.AUTO:
            return ClimateMode.AUTO
        return ClimateMode.AUTO

    @state_property
    def modes(self) -> tuple[ClimateMode, ...]:
        """Return the available operation modes."""
        return (
            ClimateMode.AUTO,
            ClimateMode.HEAT if self._is_heating_mode else ClimateMode.COOL,
            ClimateMode.OFF,
        )

    @state_property
    def profile(self) -> ClimateProfile:
        """Return the current control mode."""
        if self._dp_boost_mode.value:
            return ClimateProfile.BOOST
        if self._dp_set_point_mode.value == _ModeHmIP.AWAY:
            return ClimateProfile.AWAY
        if self.mode == ClimateMode.AUTO:
            return self._current_profile_name if self._current_profile_name else ClimateProfile.NONE
        return ClimateProfile.NONE

    @state_property
    def profiles(self) -> tuple[ClimateProfile, ...]:
        """Return available control modes."""
        control_modes = [ClimateProfile.BOOST, ClimateProfile.NONE]
        if self.mode == ClimateMode.AUTO:
            control_modes.extend(self._profile_names)
        return tuple(control_modes)

    @property
    def optimum_start_stop(self) -> bool | None:
        """Return if optimum_start_stop is enabled."""
        return self._dp_optimum_start_stop.value

    @property
    def supports_profiles(self) -> bool:
        """Flag if climate supports control modes."""
        return True

    @state_property
    def temperature_offset(self) -> float | None:
        """Return the maximum temperature."""
        return self._dp_temperature_offset.value

    @bind_collector()
    async def set_mode(self, mode: ClimateMode, collector: CallParameterCollector | None = None) -> None:
        """Set new target mode."""
        if not self.is_state_change(mode=mode):
            return
        # if switching mode then disable boost_mode
        if self._dp_boost_mode.value:
            await self.set_profile(profile=ClimateProfile.NONE, collector=collector)

        if mode == ClimateMode.AUTO:
            await self._dp_control_mode.send_value(value=_ModeHmIP.AUTO, collector=collector)
        elif mode in (ClimateMode.HEAT, ClimateMode.COOL):
            await self._dp_control_mode.send_value(value=_ModeHmIP.MANU, collector=collector)
            await self.set_temperature(temperature=self._min_or_target_temperature, collector=collector)
        elif mode == ClimateMode.OFF:
            await self._dp_control_mode.send_value(value=_ModeHmIP.MANU, collector=collector)
            await self.set_temperature(temperature=_OFF_TEMPERATURE, collector=collector, do_validate=False)

    @bind_collector()
    async def set_profile(self, profile: ClimateProfile, collector: CallParameterCollector | None = None) -> None:
        """Set new control mode."""
        if not self.is_state_change(profile=profile):
            return
        if profile == ClimateProfile.BOOST:
            await self._dp_boost_mode.send_value(value=True, collector=collector)
        elif profile == ClimateProfile.NONE:
            await self._dp_boost_mode.send_value(value=False, collector=collector)
        elif profile in self._profile_names:
            if self.mode != ClimateMode.AUTO:
                await self.set_mode(mode=ClimateMode.AUTO, collector=collector)
                await self._dp_boost_mode.send_value(value=False, collector=collector)
            if profile_idx := self._profiles.get(profile):
                await self._dp_active_profile.send_value(value=profile_idx, collector=collector)

    @inspector()
    async def enable_away_mode_by_calendar(self, start: datetime, end: datetime, away_temperature: float) -> None:
        """Enable the away mode by calendar on thermostat."""
        await self._client.put_paramset(
            channel_address=self._channel.address,
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                Parameter.SET_POINT_MODE: _ModeHmIP.AWAY,
                Parameter.SET_POINT_TEMPERATURE: away_temperature,
                Parameter.PARTY_TIME_START: start.strftime(_PARTY_DATE_FORMAT),
                Parameter.PARTY_TIME_END: end.strftime(_PARTY_DATE_FORMAT),
            },
        )

    @inspector()
    async def enable_away_mode_by_duration(self, hours: int, away_temperature: float) -> None:
        """Enable the away mode by duration on thermostat."""
        start = datetime.now() - timedelta(minutes=10)
        end = datetime.now() + timedelta(hours=hours)
        await self.enable_away_mode_by_calendar(start=start, end=end, away_temperature=away_temperature)

    @inspector()
    async def disable_away_mode(self) -> None:
        """Disable the away mode on thermostat."""
        await self._client.put_paramset(
            channel_address=self._channel.address,
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                Parameter.SET_POINT_MODE: _ModeHmIP.AWAY,
                Parameter.PARTY_TIME_START: _PARTY_INIT_DATE,
                Parameter.PARTY_TIME_END: _PARTY_INIT_DATE,
            },
        )

    @property
    def _profile_names(self) -> tuple[ClimateProfile, ...]:
        """Return a collection of profile names."""
        return tuple(self._profiles.keys())

    @property
    def _current_profile_name(self) -> ClimateProfile | None:
        """Return a profile index by name."""
        inv_profiles = {v: k for k, v in self._profiles.items()}
        if self._dp_active_profile.value is not None:
            return inv_profiles.get(int(self._dp_active_profile.value))
        return None

    @property
    def _profiles(self) -> Mapping[ClimateProfile, int]:
        """Return the profile groups."""
        profiles: dict[ClimateProfile, int] = {}
        if self._dp_active_profile.min and self._dp_active_profile.max:
            for i in range(self._dp_active_profile.min, self._dp_active_profile.max + 1):
                profiles[ClimateProfile(f"{PROFILE_PREFIX}{i}")] = i

        return profiles

    @property
    def schedule_profile_nos(self) -> int:
        """Return the number of supported profiles."""
        return len(self._profiles)


def _convert_minutes_to_time_str(minutes: Any) -> str:
    """Convert minutes to a time string."""
    if not isinstance(minutes, int):
        return _MAX_SCHEDULER_TIME
    time_str = f"{minutes // 60:0=2}:{minutes % 60:0=2}"
    if SCHEDULER_TIME_PATTERN.match(time_str) is None:
        raise ValidationException(
            f"Time {time_str} is not valid. Format must be hh:mm with min: {_MIN_SCHEDULER_TIME} and max: {_MAX_SCHEDULER_TIME}"
        )
    return time_str


def _convert_time_str_to_minutes(time_str: str) -> int:
    """Convert minutes to a time string."""
    if SCHEDULER_TIME_PATTERN.match(time_str) is None:
        raise ValidationException(
            f"Time {time_str} is not valid. Format must be hh:mm with min: {_MIN_SCHEDULER_TIME} and max: {_MAX_SCHEDULER_TIME}"
        )
    try:
        h, m = time_str.split(":")
        return (int(h) * 60) + int(m)
    except Exception as ex:
        raise ValidationException(f"Failed to convert time {time_str}. Format must be hh:mm.") from ex


def _sort_simple_weekday_list(simple_weekday_list: SIMPLE_WEEKDAY_LIST) -> SIMPLE_WEEKDAY_LIST:
    """Sort simple weekday list."""
    simple_weekday_dict = sorted(
        {
            _convert_time_str_to_minutes(str(slot[ScheduleSlotType.STARTTIME])): slot for slot in simple_weekday_list
        }.items()
    )
    return [slot[1] for slot in simple_weekday_dict]


def _fillup_weekday_data(base_temperature: float, weekday_data: WEEKDAY_DICT) -> WEEKDAY_DICT:
    """Fillup weekday data."""
    for slot_no in SCHEDULE_SLOT_IN_RANGE:
        if slot_no not in weekday_data:
            weekday_data[slot_no] = {
                ScheduleSlotType.ENDTIME: _MAX_SCHEDULER_TIME,
                ScheduleSlotType.TEMPERATURE: base_temperature,
            }

    return weekday_data


def _get_raw_schedule_paramset(schedule_data: _SCHEDULE_DICT) -> _RAW_SCHEDULE_DICT:
    """Return the raw paramset."""
    raw_paramset: _RAW_SCHEDULE_DICT = {}
    for profile, profile_data in schedule_data.items():
        for weekday, weekday_data in profile_data.items():
            for slot_no, slot in weekday_data.items():
                for slot_type, slot_value in slot.items():
                    raw_profile_name = f"{str(profile)}_{str(slot_type)}_{str(weekday)}_{slot_no}"
                    if SCHEDULER_PROFILE_PATTERN.match(raw_profile_name) is None:
                        raise ValidationException(f"Not a valid profile name: {raw_profile_name}")
                    raw_value: float | int = cast(float | int, slot_value)
                    if slot_type == ScheduleSlotType.ENDTIME and isinstance(slot_value, str):
                        raw_value = _convert_time_str_to_minutes(slot_value)
                    raw_paramset[raw_profile_name] = raw_value
    return raw_paramset


def _add_to_schedule_data(
    schedule_data: _SCHEDULE_DICT,
    profile: ScheduleProfile,
    weekday: ScheduleWeekday,
    slot_no: int,
    slot_type: ScheduleSlotType,
    slot_value: str | float,
) -> None:
    """Add or update schedule slot."""
    if profile not in schedule_data:
        schedule_data[profile] = {}
    if weekday not in schedule_data[profile]:
        schedule_data[profile][weekday] = {}
    if slot_no not in schedule_data[profile][weekday]:
        schedule_data[profile][weekday][slot_no] = {}
    if slot_type not in schedule_data[profile][weekday][slot_no]:
        if slot_type == ScheduleSlotType.ENDTIME and isinstance(slot_value, int):
            slot_value = _convert_minutes_to_time_str(slot_value)
        schedule_data[profile][weekday][slot_no][slot_type] = slot_value


def make_simple_thermostat(
    channel: hmd.Channel,
    custom_config: CustomConfig,
) -> None:
    """Create SimpleRfThermostat data point."""
    hmed.make_custom_data_point(
        channel=channel,
        data_point_class=CustomDpSimpleRfThermostat,
        device_profile=DeviceProfile.SIMPLE_RF_THERMOSTAT,
        custom_config=custom_config,
    )


def make_thermostat(
    channel: hmd.Channel,
    custom_config: CustomConfig,
) -> None:
    """Create RfThermostat data point."""
    hmed.make_custom_data_point(
        channel=channel,
        data_point_class=CustomDpRfThermostat,
        device_profile=DeviceProfile.RF_THERMOSTAT,
        custom_config=custom_config,
    )


def make_thermostat_group(
    channel: hmd.Channel,
    custom_config: CustomConfig,
) -> None:
    """Create RfThermostat group data point."""
    hmed.make_custom_data_point(
        channel=channel,
        data_point_class=CustomDpRfThermostat,
        device_profile=DeviceProfile.RF_THERMOSTAT_GROUP,
        custom_config=custom_config,
    )


def make_ip_thermostat(
    channel: hmd.Channel,
    custom_config: CustomConfig,
) -> None:
    """Create IPThermostat data point."""
    hmed.make_custom_data_point(
        channel=channel,
        data_point_class=CustomDpIpThermostat,
        device_profile=DeviceProfile.IP_THERMOSTAT,
        custom_config=custom_config,
    )


def make_ip_thermostat_group(
    channel: hmd.Channel,
    custom_config: CustomConfig,
) -> None:
    """Create IPThermostat group data point."""
    hmed.make_custom_data_point(
        channel=channel,
        data_point_class=CustomDpIpThermostat,
        device_profile=DeviceProfile.IP_THERMOSTAT_GROUP,
        custom_config=custom_config,
    )


# Case for device model is not relevant.
# HomeBrew (HB-) devices are always listed as HM-.
DEVICES: Mapping[str, CustomConfig | tuple[CustomConfig, ...]] = {
    "ALPHA-IP-RBG": CustomConfig(make_ce_func=make_ip_thermostat),
    "BC-RT-TRX-CyG": CustomConfig(make_ce_func=make_thermostat),
    "BC-RT-TRX-CyN": CustomConfig(make_ce_func=make_thermostat),
    "BC-TC-C-WM": CustomConfig(make_ce_func=make_thermostat),
    "HM-CC-RT-DN": CustomConfig(make_ce_func=make_thermostat, channels=(4,)),
    "HM-CC-TC": CustomConfig(make_ce_func=make_simple_thermostat),
    "HM-CC-VG-1": CustomConfig(make_ce_func=make_thermostat_group),
    "HM-TC-IT-WM-W-EU": CustomConfig(make_ce_func=make_thermostat, channels=(2,)),
    "HmIP-BWTH": CustomConfig(make_ce_func=make_ip_thermostat),
    "HmIP-HEATING": CustomConfig(make_ce_func=make_ip_thermostat_group),
    "HmIP-STH": CustomConfig(make_ce_func=make_ip_thermostat),
    "HmIP-WTH": CustomConfig(make_ce_func=make_ip_thermostat),
    "HmIP-eTRV": CustomConfig(make_ce_func=make_ip_thermostat),
    "HmIPW-SCTHD": CustomConfig(make_ce_func=make_ip_thermostat),
    "HmIPW-STH": CustomConfig(make_ce_func=make_ip_thermostat),
    "HmIPW-WTH": CustomConfig(make_ce_func=make_ip_thermostat),
    "Thermostat AA": CustomConfig(make_ce_func=make_ip_thermostat),
    "ZEL STG RM FWT": CustomConfig(make_ce_func=make_simple_thermostat),
}
hmed.ALL_DEVICES[DataPointCategory.CLIMATE] = DEVICES
BLACKLISTED_DEVICES: tuple[str, ...] = ("HmIP-STHO",)
hmed.ALL_BLACKLISTED_DEVICES.append(BLACKLISTED_DEVICES)
