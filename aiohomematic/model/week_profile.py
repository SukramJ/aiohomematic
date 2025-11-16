"""
Module for handling week profiles.

This module provides scheduling functionality for HomeMatic devices, supporting both
climate devices (thermostats) and non-climate devices (switches, lights, covers, valves).

SCHEDULE SYSTEM OVERVIEW
========================

The schedule system manages weekly time-based automation for HomeMatic devices. It handles
conversion between CCU raw paramset format and structured Python dictionaries, providing
validation, filtering, and normalization of schedule data.

Two main implementations:
- ClimeateWeekProfile: Manages climate device schedules (thermostats)
- DefaultWeekProfile: Manages non-climate device schedules (switches, lights, covers, valves)


CLIMATE SCHEDULE DATA STRUCTURES
=================================

Climate schedules use a hierarchical structure with three levels:

1. CLIMATE_SCHEDULE_DICT (Complete Schedule)
   Structure: dict[ScheduleProfile, CLIMATE_PROFILE_DICT]

   Contains all profiles (P1-P6) for a thermostat device.

Example:
   {
       ScheduleProfile.P1: {
           "MONDAY": {1: {...}, 2: {...}, ...},
           "TUESDAY": {1: {...}, 2: {...}, ...},
           ...
       },
       ScheduleProfile.P2: {...},
       ...
   }

2. CLIMATE_PROFILE_DICT (Single Profile)
   Structure: dict[WeekdayStr, CLIMATE_WEEKDAY_DICT]

   Contains all weekdays for a single profile (e.g., P1).

Example:
   {
       "MONDAY": {
           1: {ScheduleSlotType.ENDTIME: "06:00", ScheduleSlotType.TEMPERATURE: 18.0},
           2: {ScheduleSlotType.ENDTIME: "22:00", ScheduleSlotType.TEMPERATURE: 21.0},
           3: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
           ...
       },
       "TUESDAY": {...},
       ...
   }

3. CLIMATE_WEEKDAY_DICT (Single Weekday)
   Structure: dict[int, dict[ScheduleSlotType, str | float]]

   Contains 13 time slots for a single weekday. Each slot has an ENDTIME and TEMPERATURE.
   Slots define periods where the thermostat maintains a specific temperature until the
   ENDTIME is reached.

Example:
   {
       1: {ScheduleSlotType.ENDTIME: "06:00", ScheduleSlotType.TEMPERATURE: 18.0},
       2: {ScheduleSlotType.ENDTIME: "08:00", ScheduleSlotType.TEMPERATURE: 21.0},
       3: {ScheduleSlotType.ENDTIME: "17:00", ScheduleSlotType.TEMPERATURE: 18.0},
       4: {ScheduleSlotType.ENDTIME: "22:00", ScheduleSlotType.TEMPERATURE: 21.0},
       5: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
       6-13: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0}
   }

   Note: Always contains exactly 13 slots. Unused slots are filled with 24:00 entries.


RAW SCHEDULE FORMAT
===================

CCU devices store schedules in a flat paramset format:

Example (Climate):
{
    "P1_TEMPERATURE_MONDAY_1": 18.0,
    "P1_ENDTIME_MONDAY_1": 360,      # 06:00 in minutes
    "P1_TEMPERATURE_MONDAY_2": 21.0,
    "P1_ENDTIME_MONDAY_2": 480,      # 08:00 in minutes
    ...
}

Example (Switch):
{
    "01_WP_WEEKDAY": 127,            # Bitwise: all days (0b1111111)
    "01_WP_LEVEL": 1,                # On/Off state
    "01_WP_FIXED_HOUR": 7,
    "01_WP_FIXED_MINUTE": 30,
    ...
}


SIMPLE SCHEDULE FORMAT
======================

A simplified format for easy user input, focusing on temperature periods without
redundant 24:00 slots:

CLIMATE_SIMPLE_WEEKDAY_LIST:
[
    {
        ScheduleSlotType.STARTTIME: "06:00",
        ScheduleSlotType.ENDTIME: "08:00",
        ScheduleSlotType.TEMPERATURE: 21.0
    },
    {
        ScheduleSlotType.STARTTIME: "17:00",
        ScheduleSlotType.ENDTIME: "22:00",
        ScheduleSlotType.TEMPERATURE: 21.0
    }
]

The system automatically:
- Fills gaps with base_temperature
- Converts to full 13-slot format
- Sorts by time
- Validates ranges


SCHEDULE SERVICES
=================

Core Operations:
----------------

get_schedule() -> CLIMATE_SCHEDULE_DICT
    Retrieves complete schedule from cache or device.
    Returns filtered data (redundant 24:00 slots removed).

get_schedule_profile(profile) -> CLIMATE_PROFILE_DICT
    Retrieves single profile (e.g., P1) from cache or device.
    Returns filtered data for the specified profile.

get_schedule_profile_weekday(profile, weekday) -> CLIMATE_WEEKDAY_DICT
    Retrieves single weekday schedule from a profile.
    Returns filtered data for the specified weekday.

set_schedule(schedule_dict)
    Persists complete schedule to device.
    Updates cache and emits change events.

set_schedule_profile(profile, profile_data)
    Persists single profile to device.
    Validates, updates cache, and emits change events.

set_schedule_profile_weekday(profile, weekday, weekday_data)
    Persists single weekday schedule to device.
    Normalizes to 13 slots, validates, updates cache.

set_simple_schedule_profile(profile, base_temperature, simple_profile_data)
    Convenience method for setting schedules using simplified format.
    Converts simple format to full 13-slot format automatically.

copy_schedule(target_climate_data_point)
    Copies entire schedule from this device to another.

copy_schedule_profile(source_profile, target_profile, target_climate_data_point)
    Copies single profile to another profile/device.


DATA PROCESSING PIPELINE
=========================

Filtering (Output - Removes Redundancy):
-----------------------------------------
Applied when reading schedules to present clean data to users.

_filter_schedule_entries(schedule_data) -> CLIMATE_SCHEDULE_DICT
    Filters all profiles in a complete schedule.

_filter_profile_entries(profile_data) -> CLIMATE_PROFILE_DICT
    Filters all weekdays in a profile.

_filter_weekday_entries(weekday_data) -> CLIMATE_WEEKDAY_DICT
    Filters redundant 24:00 slots from a weekday schedule:
    - Processes slots in slot-number order
    - Keeps all slots up to and including the first 24:00
    - Stops at the first occurrence of 24:00 (ignores all subsequent slots)
    - Renumbers remaining slots sequentially (1, 2, 3, ...)

Example:
    Input:  {1: {ENDTIME: "06:00"}, 2: {ENDTIME: "12:00"}, 3: {ENDTIME: "24:00"}, 4: {ENDTIME: "18:00"}, ..., 13: {ENDTIME: "24:00"}}
    Output: {1: {ENDTIME: "06:00"}, 2: {ENDTIME: "12:00"}, 3: {ENDTIME: "24:00"}}


Normalization (Input - Ensures Valid Format):
----------------------------------------------
Applied when setting schedules to ensure data meets device requirements.

_normalize_weekday_data(weekday_data) -> CLIMATE_WEEKDAY_DICT
    Normalizes weekday schedule data:
    - Converts string keys to integers
    - Sorts slots chronologically by ENDTIME
    - Renumbers slots sequentially (1-N)
    - Fills missing slots (N+1 to 13) with 24:00 entries
    - Always returns exactly 13 slots

Example:
    Input:  {"2": {ENDTIME: "12:00"}, "1": {ENDTIME: "06:00"}}
    Output: {
        1: {ENDTIME: "06:00", TEMPERATURE: 20.0},
        2: {ENDTIME: "12:00", TEMPERATURE: 21.0},
        3-13: {ENDTIME: "24:00", TEMPERATURE: 21.0}  # Filled automatically
    }


TYPICAL WORKFLOW EXAMPLES
==========================

Reading a Schedule:
-------------------
1. User calls get_schedule_profile_weekday(P1, "MONDAY")
2. System retrieves from cache or device (13 slots)
3. _filter_weekday_entries removes redundant 24:00 slots
4. User receives clean data (e.g., 3-5 meaningful slots)

Setting a Schedule:
-------------------
1. User provides schedule data (may be incomplete, unsorted)
2. System calls _normalize_weekday_data to:
   - Sort by time
   - Fill to exactly 13 slots
3. System validates (temperature ranges, time ranges, sequence)
4. System persists to device
5. Cache is updated, events are emitted

Using Simple Format:
--------------------
1. User calls set_simple_schedule_profile_weekday with:
   - base_temperature: 18.0
   - simple_weekday_list: [{STARTTIME: "07:00", ENDTIME: "22:00", TEMPERATURE: 21.0}]
2. System converts to full format:
   - Slot 1: ENDTIME: "07:00", TEMP: 18.0 (base_temperature before start)
   - Slot 2: ENDTIME: "22:00", TEMP: 21.0 (user's period)
   - Slots 3-13: ENDTIME: "24:00", TEMP: 18.0 (base_temperature after end)
3. System validates and persists

DATA FLOW SUMMARY
=================

Device → Python (Reading):
    Raw Paramset → convert_raw_to_dict_schedule() → Cache (13 slots) →
    _filter_*_entries() → User (clean, minimal slots)

Python → Device (Writing):
    User Data → _normalize_weekday_data() → Full 13 slots → Validation →
    convert_dict_to_raw_schedule() → Raw Paramset → Device

Simple → Full Format:
    Simple List → _validate_and_convert_simple_to_profile_weekday() →
    Full 13 slots → Normal writing flow

"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import IntEnum
import logging
from typing import Any, Final, cast

from aiohomematic import i18n
from aiohomematic.const import (
    BIDCOS_DEVICE_CHANNEL_DUMMY,
    CLIMATE_MAX_SCHEDULER_TIME,
    CLIMATE_MIN_SCHEDULER_TIME,
    CLIMATE_PROFILE_DICT,
    CLIMATE_RELEVANT_SLOT_TYPES,
    CLIMATE_SCHEDULE_DICT,
    CLIMATE_SCHEDULE_SLOT_IN_RANGE,
    CLIMATE_SCHEDULE_SLOT_RANGE,
    CLIMATE_SCHEDULE_TIME_RANGE,
    CLIMATE_SIMPLE_PROFILE_DICT,
    CLIMATE_SIMPLE_WEEKDAY_LIST,
    CLIMATE_WEEKDAY_DICT,
    DEFAULT_CLIMATE_FILL_TEMPERATURE,
    DEFAULT_SCHEDULE_DICT,
    DEFAULT_SCHEDULE_GROUP,
    RAW_SCHEDULE_DICT,
    SCHEDULE_PATTERN,
    SCHEDULER_PROFILE_PATTERN,
    SCHEDULER_TIME_PATTERN,
    AstroType,
    DataPointCategory,
    ParamsetKey,
    ScheduleActorChannel,
    ScheduleCondition,
    ScheduleField,
    ScheduleProfile,
    ScheduleSlotType,
    TimeBase,
    WeekdayInt,
    WeekdayStr,
)
from aiohomematic.decorators import inspector
from aiohomematic.exceptions import ClientException, ValidationException
from aiohomematic.model.custom import BaseCustomDpClimate, data_point as cdp

_LOGGER = logging.getLogger(__name__)


class WeekProfile[SCHEDULE_DICT_T: dict[Any, Any]](ABC):
    """Handle the device week profile."""

    __slots__ = (
        "_client",
        "_data_point",
        "_device",
        "_schedule_cache",
        "_schedule_channel_no",
    )

    def __init__(self, *, data_point: cdp.CustomDataPoint) -> None:
        """Init the device schedule."""
        self._data_point = data_point
        self._device: Final = data_point.device
        self._client: Final = data_point.device.client
        self._schedule_channel_no: Final[int | None] = self._data_point.custom_config.schedule_channel_no
        self._schedule_cache: SCHEDULE_DICT_T = cast(SCHEDULE_DICT_T, {})

    @staticmethod
    @abstractmethod
    def convert_dict_to_raw_schedule(*, schedule_dict: SCHEDULE_DICT_T) -> RAW_SCHEDULE_DICT:
        """Convert dictionary to raw schedule."""

    @staticmethod
    @abstractmethod
    def convert_raw_to_dict_schedule(*, raw_schedule: RAW_SCHEDULE_DICT) -> SCHEDULE_DICT_T:
        """Convert raw schedule to dictionary format."""

    @property
    def schedule(self) -> SCHEDULE_DICT_T:
        """Return the schedule cache."""
        return self._schedule_cache

    @property
    def schedule_channel_address(self) -> str | None:
        """Return schedule channel address."""
        if self._schedule_channel_no == BIDCOS_DEVICE_CHANNEL_DUMMY:
            return self._device.address
        if self._schedule_channel_no is not None:
            return f"{self._device.address}:{self._schedule_channel_no}"
        if (
            self._device.default_schedule_channel
            and (dsca := self._device.default_schedule_channel.address) is not None
        ):
            return dsca
        return None

    @property
    def supports_schedule(self) -> bool:
        """Flag if climate supports schedule."""
        return self.schedule_channel_address is not None

    @abstractmethod
    async def get_schedule(self, *, force_load: bool = False) -> SCHEDULE_DICT_T:
        """Return the schedule dictionary."""

    @abstractmethod
    async def reload_and_cache_schedule(self, *, force: bool = False) -> None:
        """Reload schedule entries and update cache."""

    @abstractmethod
    async def set_schedule(self, *, schedule_dict: SCHEDULE_DICT_T) -> None:
        """Persist the provided schedule dictionary."""

    def _filter_schedule_entries(self, *, schedule_data: SCHEDULE_DICT_T) -> SCHEDULE_DICT_T:
        """Filter schedule entries by removing invalid/not relevant entries."""
        return schedule_data

    def _validate_and_get_schedule_channel_address(self) -> str:
        """
        Validate that schedule is supported and return the channel address.

        Returns:
            The schedule channel address

        Raises:
            ValidationException: If schedule is not supported

        """
        if (sca := self.schedule_channel_address) is None:
            raise ValidationException(
                i18n.tr(
                    "exception.model.week_profile.schedule.unsupported",
                    address=self._device.name,
                )
            )
        return sca


class DefaultWeekProfile(WeekProfile[DEFAULT_SCHEDULE_DICT]):
    """
    Handle device week profiles for switches, lights, covers, and valves.

    This class manages the weekly scheduling functionality for non-climate devices,
    converting between CCU raw paramset format and structured Python dictionaries.
    """

    @staticmethod
    def _convert_schedule_entries(*, values: RAW_SCHEDULE_DICT) -> RAW_SCHEDULE_DICT:
        """
        Extract only week profile (WP) entries from a raw paramset dictionary.

        Filters paramset values to include only keys matching the pattern XX_WP_FIELDNAME.
        """
        schedule: RAW_SCHEDULE_DICT = {}
        for key, value in values.items():
            if not SCHEDULE_PATTERN.match(key):
                continue
            # The CCU reports ints/floats; cast to float for completeness
            if isinstance(value, (int, float)):
                schedule[key] = float(value) if isinstance(value, float) else value
        return schedule

    @staticmethod
    def convert_dict_to_raw_schedule(*, schedule_dict: DEFAULT_SCHEDULE_DICT) -> RAW_SCHEDULE_DICT:
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
        raw_schedule: RAW_SCHEDULE_DICT = {}

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

    @staticmethod
    def convert_raw_to_dict_schedule(*, raw_schedule: RAW_SCHEDULE_DICT) -> DEFAULT_SCHEDULE_DICT:
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
        schedule_dict: DEFAULT_SCHEDULE_DICT = {}

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
                schedule_dict[group_no][field] = _bitwise_to_list(value=int_value, enum_class=WeekdayInt)
            elif field == ScheduleField.TARGET_CHANNELS:
                schedule_dict[group_no][field] = _bitwise_to_list(value=int_value, enum_class=ScheduleActorChannel)
            else:
                # ASTRO_OFFSET, DURATION_FACTOR, FIXED_HOUR, FIXED_MINUTE, RAMP_TIME_FACTOR
                schedule_dict[group_no][field] = int_value

        # Return all schedule groups, even if incomplete
        # Filtering can be done by callers using is_schedule_active() if needed
        return schedule_dict

    def empty_schedule_group(self) -> DEFAULT_SCHEDULE_GROUP:
        """Return an empty schedule dictionary."""
        if not self.supports_schedule:
            return create_empty_schedule_group(category=self._data_point.category)
        return {}

    @inspector
    async def get_schedule(self, *, force_load: bool = False) -> DEFAULT_SCHEDULE_DICT:
        """Return the raw schedule dictionary."""
        if not self.supports_schedule:
            raise ValidationException(
                i18n.tr(
                    "exception.model.week_profile.schedule.unsupported",
                    address=self._device.name,
                )
            )
        await self.reload_and_cache_schedule(force=force_load)
        return self._schedule_cache

    async def reload_and_cache_schedule(self, *, force: bool = False) -> None:
        """Reload schedule entries and update cache."""
        if not force and not self.supports_schedule:
            return

        try:
            new_raw_schedule = await self._get_raw_schedule()
        except ValidationException:
            return
        old_schedule = self._schedule_cache
        new_schedule_dict = self.convert_raw_to_dict_schedule(raw_schedule=new_raw_schedule)
        self._schedule_cache = {
            no: group_data for no, group_data in new_schedule_dict.items() if is_schedule_active(group_data=group_data)
        }
        if old_schedule != self._schedule_cache:
            self._data_point.emit_data_point_updated_event()

    @inspector
    async def set_schedule(self, *, schedule_dict: DEFAULT_SCHEDULE_DICT) -> None:
        """Persist the provided raw schedule dictionary."""
        sca = self._validate_and_get_schedule_channel_address()

        old_schedule = self._schedule_cache
        self._schedule_cache.update(schedule_dict)
        if old_schedule != self._schedule_cache:
            self._data_point.emit_data_point_updated_event()

        await self._client.put_paramset(
            channel_address=sca,
            paramset_key_or_link_address=ParamsetKey.MASTER,
            values=self._convert_schedule_entries(
                values=self.convert_dict_to_raw_schedule(schedule_dict=schedule_dict)
            ),
        )

    async def _get_raw_schedule(self) -> RAW_SCHEDULE_DICT:
        """Return the raw schedule dictionary filtered to WP entries."""
        try:
            sca = self._validate_and_get_schedule_channel_address()
            raw_data = await self._client.get_paramset(
                address=sca,
                paramset_key=ParamsetKey.MASTER,
            )
        except ClientException as cex:
            raise ValidationException(
                i18n.tr(
                    "exception.model.week_profile.schedule.unsupported",
                    name=self._device.name,
                )
            ) from cex

        if not (schedule := self._convert_schedule_entries(values=raw_data)):
            raise ValidationException(
                i18n.tr(
                    "exception.model.week_profile.schedule.unsupported",
                    name=self._device.name,
                )
            )
        return schedule


class ClimeateWeekProfile(WeekProfile[CLIMATE_SCHEDULE_DICT]):
    """
    Handle climate device week profiles (thermostats).

    This class manages heating/cooling schedules with time slots and temperature settings.
    Supports multiple profiles (P1-P6) with 13 time slots per weekday.
    Provides both raw and simplified schedule interfaces for easy temperature programming.
    """

    _data_point: BaseCustomDpClimate
    __slots__ = (
        "_min_temp",
        "_max_temp",
    )

    def __init__(self, *, data_point: cdp.CustomDataPoint) -> None:
        """Init the climate week profile."""
        super().__init__(data_point=data_point)
        self._min_temp: Final[float] = self._data_point.min_temp
        self._max_temp: Final[float] = self._data_point.max_temp

    @staticmethod
    def convert_dict_to_raw_schedule(*, schedule_dict: CLIMATE_SCHEDULE_DICT) -> RAW_SCHEDULE_DICT:
        """
        Convert structured climate schedule to raw paramset format.

        Args:
            schedule_dict: Structured schedule with profiles, weekdays, and time slots

        Returns:
            Raw schedule dictionary for CCU transmission

        Example:
            Input: {ScheduleProfile.P1: {"MONDAY": {1: {ScheduleSlotType.TEMPERATURE: 20.0, ScheduleSlotType.ENDTIME: "06:00"}}}}
            Output: {"P1_TEMPERATURE_MONDAY_1": 20.0, "P1_ENDTIME_MONDAY_1": 360}

        """
        raw_paramset: RAW_SCHEDULE_DICT = {}
        for profile, profile_data in schedule_dict.items():
            for weekday, weekday_data in profile_data.items():
                for slot_no, slot in weekday_data.items():
                    for slot_type, slot_value in slot.items():
                        raw_profile_name = f"{str(profile)}_{str(slot_type)}_{str(weekday)}_{slot_no}"
                        if SCHEDULER_PROFILE_PATTERN.match(raw_profile_name) is None:
                            raise ValidationException(
                                i18n.tr(
                                    "exception.model.week_profile.validate.profile_name_invalid",
                                    profile_name=raw_profile_name,
                                )
                            )
                        raw_value: float | int = cast(float | int, slot_value)
                        if slot_type == ScheduleSlotType.ENDTIME and isinstance(slot_value, str):
                            raw_value = _convert_time_str_to_minutes(time_str=slot_value)
                        raw_paramset[raw_profile_name] = raw_value
        return raw_paramset

    @staticmethod
    def convert_raw_to_dict_schedule(*, raw_schedule: RAW_SCHEDULE_DICT) -> CLIMATE_SCHEDULE_DICT:
        """
        Convert raw CCU schedule to structured dictionary format.

        Args:
            raw_schedule: Raw schedule from CCU paramset

        Returns:
            Structured schedule grouped by profile, weekday, and slot

        Example:
            Input: {"P1_TEMPERATURE_MONDAY_1": 20.0, "P1_ENDTIME_MONDAY_1": 360}
            Output: {ScheduleProfile.P1: {"MONDAY": {1: {ScheduleSlotType.TEMPERATURE: 20.0, ScheduleSlotType.ENDTIME: "06:00"}}}}

        """
        schedule_data: CLIMATE_SCHEDULE_DICT = {}

        # Process each schedule entry
        for slot_name, slot_value in raw_schedule.items():
            # Split string only once, use maxsplit for micro-optimization
            # Expected format: "P1_TEMPERATURE_MONDAY_1"
            parts = slot_name.split("_", 3)  # maxsplit=3 limits splits
            if len(parts) != 4:
                continue

            profile_name, slot_type_name, slot_weekday_name, slot_no_str = parts

            try:
                _profile = ScheduleProfile(profile_name)
                _slot_type = ScheduleSlotType(slot_type_name)
                _weekday = WeekdayStr(slot_weekday_name)
                _slot_no = int(slot_no_str)
            except (ValueError, KeyError):
                # Gracefully skip invalid entries instead of crashing
                continue

            if _profile not in schedule_data:
                schedule_data[_profile] = {}
            if _weekday not in schedule_data[_profile]:
                schedule_data[_profile][_weekday] = {}
            if _slot_no not in schedule_data[_profile][_weekday]:
                schedule_data[_profile][_weekday][_slot_no] = {}

            # Convert ENDTIME from minutes to time string if needed
            final_value: str | float = slot_value
            if _slot_type == ScheduleSlotType.ENDTIME and isinstance(slot_value, int):
                final_value = _convert_minutes_to_time_str(slot_value)

            schedule_data[_profile][_weekday][_slot_no][_slot_type] = final_value

        return schedule_data

    @property
    def available_schedule_profiles(self) -> tuple[ScheduleProfile, ...]:
        """Return the available schedule profiles."""
        return tuple(self._schedule_cache.keys())

    @property
    def schedule(self) -> CLIMATE_SCHEDULE_DICT:
        """Return the schedule cache."""
        return _filter_schedule_entries(schedule_data=self._schedule_cache)

    @inspector
    async def copy_schedule(self, *, target_climate_data_point: BaseCustomDpClimate) -> None:
        """Copy schedule to target device."""

        if self._data_point.schedule_profile_nos != target_climate_data_point.schedule_profile_nos:
            raise ValidationException(i18n.tr("exception.model.week_profile.copy_schedule.profile_count_mismatch"))
        raw_schedule = await self._get_raw_schedule()
        if not target_climate_data_point.device.supports_week_profile:
            raise ValidationException(
                i18n.tr(
                    "exception.model.week_profile.schedule.unsupported",
                    address=self._device.name,
                )
            )
        if (
            self._data_point.device.week_profile
            and (sca := self._data_point.device.week_profile.schedule_channel_address) is not None
        ):
            await self._client.put_paramset(
                channel_address=sca,
                paramset_key_or_link_address=ParamsetKey.MASTER,
                values=raw_schedule,
            )

    @inspector
    async def copy_schedule_profile(
        self,
        *,
        source_profile: ScheduleProfile,
        target_profile: ScheduleProfile,
        target_climate_data_point: BaseCustomDpClimate | None = None,
    ) -> None:
        """Copy schedule profile to target device."""
        same_device = False
        if not self.supports_schedule:
            raise ValidationException(
                i18n.tr(
                    "exception.model.week_profile.schedule.unsupported",
                    name=self._device.name,
                )
            )
        if target_climate_data_point is None:
            target_climate_data_point = self._data_point
        if self._data_point is target_climate_data_point:
            same_device = True

        if same_device and (source_profile == target_profile or (source_profile is None or target_profile is None)):
            raise ValidationException(i18n.tr("exception.model.week_profile.copy_schedule.same_device_invalid"))

        if (source_profile_data := await self.get_schedule_profile(profile=source_profile)) is None:
            raise ValidationException(
                i18n.tr(
                    "exception.model.week_profile.source_profile.not_loaded",
                    source_profile=source_profile,
                )
            )
        if not target_climate_data_point.device.supports_week_profile:
            raise ValidationException(
                i18n.tr(
                    "exception.model.week_profile.schedule.unsupported",
                    address=self._device.name,
                )
            )
        if (
            target_climate_data_point.device.week_profile
            and (sca := target_climate_data_point.device.week_profile.schedule_channel_address) is not None
        ):
            await self._set_schedule_profile(
                target_channel_address=sca,
                profile=target_profile,
                profile_data=source_profile_data,
                do_validate=False,
            )

    @inspector
    async def get_schedule(self, *, force_load: bool = False) -> CLIMATE_SCHEDULE_DICT:
        """Return the complete schedule dictionary."""
        if not self.supports_schedule:
            raise ValidationException(
                i18n.tr(
                    "exception.model.week_profile.schedule.unsupported",
                    name=self._device.name,
                )
            )
        if force_load or not self._schedule_cache:
            await self.reload_and_cache_schedule()
        return _filter_schedule_entries(schedule_data=self._schedule_cache)

    @inspector
    async def get_schedule_profile(self, *, profile: ScheduleProfile, force_load: bool = False) -> CLIMATE_PROFILE_DICT:
        """Return a schedule by climate profile."""
        if not self.supports_schedule:
            raise ValidationException(
                i18n.tr(
                    "exception.model.week_profile.schedule.unsupported",
                    name=self._device.name,
                )
            )
        if force_load or not self._schedule_cache:
            await self.reload_and_cache_schedule()
        return _filter_profile_entries(profile_data=self._schedule_cache.get(profile, {}))

    @inspector
    async def get_schedule_profile_weekday(
        self, *, profile: ScheduleProfile, weekday: WeekdayStr, force_load: bool = False
    ) -> CLIMATE_WEEKDAY_DICT:
        """Return a schedule by climate profile."""
        if not self.supports_schedule:
            raise ValidationException(
                i18n.tr(
                    "exception.model.week_profile.schedule.unsupported",
                    name=self._device.name,
                )
            )
        if force_load or not self._schedule_cache:
            await self.reload_and_cache_schedule()
        return _filter_weekday_entries(weekday_data=self._schedule_cache.get(profile, {}).get(weekday, {}))

    async def reload_and_cache_schedule(self, *, force: bool = False) -> None:
        """Reload schedules from CCU and update cache, emit callbacks if changed."""
        if not self.supports_schedule:
            return

        try:
            new_schedule = await self._get_schedule_profile()
        except ValidationException:
            _LOGGER.debug(
                "RELOAD_AND_CACHE_SCHEDULE: Failed to reload schedules for %s",
                self._device.name,
            )
            return

        # Compare old and new schedules
        old_schedule = self._schedule_cache
        # Update cache with new schedules
        self._schedule_cache = new_schedule

        if old_schedule != new_schedule:
            _LOGGER.debug(
                "RELOAD_AND_CACHE_SCHEDULE: Schedule changed for %s, emitting callbacks",
                self._device.name,
            )
            # Emit data point updated event to trigger callbacks
            self._data_point.emit_data_point_updated_event()

    @inspector
    async def set_schedule(self, *, schedule_dict: CLIMATE_SCHEDULE_DICT) -> None:
        """Set the complete schedule dictionary to device."""
        sca = self._validate_and_get_schedule_channel_address()

        # Update cache and emit event
        old_schedule = self._schedule_cache
        self._schedule_cache.update(schedule_dict)
        if old_schedule != self._schedule_cache:
            self._data_point.emit_data_point_updated_event()

        # Write to device
        await self._client.put_paramset(
            channel_address=sca,
            paramset_key_or_link_address=ParamsetKey.MASTER,
            values=self.convert_dict_to_raw_schedule(schedule_dict=schedule_dict),
        )

    @inspector
    async def set_schedule_profile(
        self, *, profile: ScheduleProfile, profile_data: CLIMATE_PROFILE_DICT, do_validate: bool = True
    ) -> None:
        """Set a profile to device."""
        sca = self._validate_and_get_schedule_channel_address()
        await self._set_schedule_profile(
            target_channel_address=sca,
            profile=profile,
            profile_data=profile_data,
            do_validate=do_validate,
        )

    @inspector
    async def set_schedule_profile_weekday(
        self,
        *,
        profile: ScheduleProfile,
        weekday: WeekdayStr,
        weekday_data: CLIMATE_WEEKDAY_DICT,
        do_validate: bool = True,
    ) -> None:
        """Store a profile to device."""
        # Normalize weekday_data: convert string keys to int and sort by ENDTIME
        weekday_data = _normalize_weekday_data(weekday_data=weekday_data)

        if do_validate:
            self._validate_schedule_profile_weekday(profile=profile, weekday=weekday, weekday_data=weekday_data)

        if weekday_data != self._schedule_cache.get(profile, {}).get(weekday, {}):
            if profile not in self._schedule_cache:
                self._schedule_cache[profile] = {}
            self._schedule_cache[profile][weekday] = weekday_data
            self._data_point.emit_data_point_updated_event()

        sca = self._validate_and_get_schedule_channel_address()
        await self._client.put_paramset(
            channel_address=sca,
            paramset_key_or_link_address=ParamsetKey.MASTER,
            values=self.convert_dict_to_raw_schedule(schedule_dict={profile: {weekday: weekday_data}}),
        )

    @inspector
    async def set_simple_schedule_profile(
        self,
        *,
        profile: ScheduleProfile,
        base_temperature: float,
        simple_profile_data: CLIMATE_SIMPLE_PROFILE_DICT,
    ) -> None:
        """Set a profile to device."""
        profile_data = self._validate_and_convert_simple_to_profile(
            base_temperature=base_temperature, simple_profile_data=simple_profile_data
        )
        await self.set_schedule_profile(profile=profile, profile_data=profile_data)

    @inspector
    async def set_simple_schedule_profile_weekday(
        self,
        *,
        profile: ScheduleProfile,
        weekday: WeekdayStr,
        base_temperature: float,
        simple_weekday_list: CLIMATE_SIMPLE_WEEKDAY_LIST,
    ) -> None:
        """Store a simple weekday profile to device."""
        weekday_data = self._validate_and_convert_simple_to_profile_weekday(
            base_temperature=base_temperature, simple_weekday_list=simple_weekday_list
        )
        await self.set_schedule_profile_weekday(profile=profile, weekday=weekday, weekday_data=weekday_data)

    async def _get_raw_schedule(self) -> RAW_SCHEDULE_DICT:
        """Return the raw schedule."""
        try:
            sca = self._validate_and_get_schedule_channel_address()
            raw_data = await self._client.get_paramset(
                address=sca,
                paramset_key=ParamsetKey.MASTER,
            )
            raw_schedule = {key: value for key, value in raw_data.items() if SCHEDULER_PROFILE_PATTERN.match(key)}
        except ClientException as cex:
            raise ValidationException(
                i18n.tr(
                    "exception.model.week_profile.schedule.unsupported",
                    name=self._device.name,
                )
            ) from cex
        return raw_schedule

    async def _get_schedule_profile(self) -> CLIMATE_SCHEDULE_DICT:
        """Get the schedule."""
        # Get raw schedule data from device
        raw_schedule = await self._get_raw_schedule()
        return self.convert_raw_to_dict_schedule(raw_schedule=raw_schedule)

    async def _set_schedule_profile(
        self,
        *,
        target_channel_address: str,
        profile: ScheduleProfile,
        profile_data: CLIMATE_PROFILE_DICT,
        do_validate: bool,
    ) -> None:
        """Set a profile to device."""
        # Normalize weekday_data: convert string keys to int and sort by ENDTIME
        profile_data = {
            weekday: _normalize_weekday_data(weekday_data=weekday_data)
            for weekday, weekday_data in profile_data.items()
        }
        if do_validate:
            self._validate_schedule_profile(profile=profile, profile_data=profile_data)
        if profile_data != self._schedule_cache.get(profile, {}):
            self._schedule_cache[profile] = profile_data
            self._data_point.emit_data_point_updated_event()

        await self._client.put_paramset(
            channel_address=target_channel_address,
            paramset_key_or_link_address=ParamsetKey.MASTER,
            values=self.convert_dict_to_raw_schedule(schedule_dict={profile: profile_data}),
        )

    def _validate_and_convert_simple_to_profile(
        self, *, base_temperature: float, simple_profile_data: CLIMATE_SIMPLE_PROFILE_DICT
    ) -> CLIMATE_PROFILE_DICT:
        """Convert simple profile dict to profile dict."""
        profile_dict: CLIMATE_PROFILE_DICT = {}
        for day, simple_weekday_list in simple_profile_data.items():
            profile_dict[day] = self._validate_and_convert_simple_to_profile_weekday(
                base_temperature=base_temperature, simple_weekday_list=simple_weekday_list
            )
        return profile_dict

    def _validate_and_convert_simple_to_profile_weekday(
        self, *, base_temperature: float, simple_weekday_list: CLIMATE_SIMPLE_WEEKDAY_LIST
    ) -> CLIMATE_WEEKDAY_DICT:
        """Convert simple weekday list to weekday dict."""
        if not self._min_temp <= base_temperature <= self._max_temp:
            raise ValidationException(
                i18n.tr(
                    "exception.model.week_profile.validate.base_temperature_out_of_range",
                    base_temperature=base_temperature,
                    min=self._min_temp,
                    max=self._max_temp,
                )
            )

        weekday_data: CLIMATE_WEEKDAY_DICT = {}

        # Validate required fields before sorting
        for slot in simple_weekday_list:
            if (starttime := slot.get(ScheduleSlotType.STARTTIME)) is None:
                raise ValidationException(i18n.tr("exception.model.week_profile.validate.starttime_missing"))
            if (endtime := slot.get(ScheduleSlotType.ENDTIME)) is None:
                raise ValidationException(i18n.tr("exception.model.week_profile.validate.endtime_missing"))
            if (temperature := slot.get(ScheduleSlotType.TEMPERATURE)) is None:
                raise ValidationException(i18n.tr("exception.model.week_profile.validate.temperature_missing"))

        sorted_simple_weekday_list = _sort_simple_weekday_list(simple_weekday_list=simple_weekday_list)
        previous_endtime = CLIMATE_MIN_SCHEDULER_TIME
        slot_no = 1
        for slot in sorted_simple_weekday_list:
            starttime = slot[ScheduleSlotType.STARTTIME]
            endtime = slot[ScheduleSlotType.ENDTIME]
            temperature = slot[ScheduleSlotType.TEMPERATURE]

            if _convert_time_str_to_minutes(time_str=str(starttime)) >= _convert_time_str_to_minutes(
                time_str=str(endtime)
            ):
                raise ValidationException(
                    i18n.tr(
                        "exception.model.week_profile.validate.start_before_end",
                        start=starttime,
                        end=endtime,
                    )
                )

            if _convert_time_str_to_minutes(time_str=str(starttime)) < _convert_time_str_to_minutes(
                time_str=previous_endtime
            ):
                raise ValidationException(
                    i18n.tr(
                        "exception.model.week_profile.validate.overlap",
                        start=starttime,
                        end=endtime,
                    )
                )

            if not self._min_temp <= float(temperature) <= self._max_temp:
                raise ValidationException(
                    i18n.tr(
                        "exception.model.week_profile.validate.temperature_out_of_range_for_times",
                        temperature=temperature,
                        min=self._min_temp,
                        max=self._max_temp,
                        start=starttime,
                        end=endtime,
                    )
                )

            if _convert_time_str_to_minutes(time_str=str(starttime)) > _convert_time_str_to_minutes(
                time_str=previous_endtime
            ):
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

    def _validate_schedule_profile(self, *, profile: ScheduleProfile, profile_data: CLIMATE_PROFILE_DICT) -> None:
        """Validate the profile."""
        for weekday, weekday_data in profile_data.items():
            self._validate_schedule_profile_weekday(profile=profile, weekday=weekday, weekday_data=weekday_data)

    def _validate_schedule_profile_weekday(
        self,
        *,
        profile: ScheduleProfile,
        weekday: WeekdayStr,
        weekday_data: CLIMATE_WEEKDAY_DICT,
    ) -> None:
        """Validate the profile weekday."""
        previous_endtime = 0
        if len(weekday_data) != 13:
            if len(weekday_data) > 13:
                raise ValidationException(
                    i18n.tr(
                        "exception.model.week_profile.validate.too_many_slots",
                        profile=profile,
                        weekday=weekday,
                    )
                )
            raise ValidationException(
                i18n.tr(
                    "exception.model.week_profile.validate.too_few_slots",
                    profile=profile,
                    weekday=weekday,
                )
            )
        for no in CLIMATE_SCHEDULE_SLOT_RANGE:
            if no not in weekday_data:
                raise ValidationException(
                    i18n.tr(
                        "exception.model.week_profile.validate.slot_missing",
                        no=no,
                        profile=profile,
                        weekday=weekday,
                    )
                )
            slot = weekday_data[no]
            for slot_type in CLIMATE_RELEVANT_SLOT_TYPES:
                if slot_type not in slot:
                    raise ValidationException(
                        i18n.tr(
                            "exception.model.week_profile.validate.slot_type_missing",
                            slot_type=slot_type,
                            profile=profile,
                            weekday=weekday,
                            no=no,
                        )
                    )

            # Validate temperature
            temperature = float(weekday_data[no][ScheduleSlotType.TEMPERATURE])
            if not self._min_temp <= temperature <= self._max_temp:
                raise ValidationException(
                    i18n.tr(
                        "exception.model.week_profile.validate.temperature_out_of_range_for_profile_slot",
                        temperature=temperature,
                        min=self._min_temp,
                        max=self._max_temp,
                        profile=profile,
                        weekday=weekday,
                        no=no,
                    )
                )

            # Validate endtime
            endtime_str = str(weekday_data[no][ScheduleSlotType.ENDTIME])
            if endtime := _convert_time_str_to_minutes(time_str=endtime_str):
                if endtime not in CLIMATE_SCHEDULE_TIME_RANGE:
                    raise ValidationException(
                        i18n.tr(
                            "exception.model.week_profile.validate.time_out_of_bounds_profile_slot",
                            time=endtime_str,
                            min_time=_convert_minutes_to_time_str(minutes=CLIMATE_SCHEDULE_TIME_RANGE.start),
                            max_time=_convert_minutes_to_time_str(minutes=CLIMATE_SCHEDULE_TIME_RANGE.stop - 1),
                            profile=profile,
                            weekday=weekday,
                            no=no,
                        )
                    )
                if endtime < previous_endtime:
                    raise ValidationException(
                        i18n.tr(
                            "exception.model.week_profile.validate.sequence_rising",
                            time=endtime_str,
                            previous=_convert_minutes_to_time_str(minutes=previous_endtime),
                            profile=profile,
                            weekday=weekday,
                            no=no,
                        )
                    )
            previous_endtime = endtime


def create_week_profile(*, data_point: cdp.CustomDataPoint) -> WeekProfile[dict[Any, Any]]:
    """Create a week profile from a custom data point."""
    if data_point.category == DataPointCategory.CLIMATE:
        return ClimeateWeekProfile(data_point=data_point)
    return DefaultWeekProfile(data_point=data_point)


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


def _filter_profile_entries(*, profile_data: CLIMATE_PROFILE_DICT) -> CLIMATE_PROFILE_DICT:
    """Filter profile data to remove redundant 24:00 slots."""
    if not profile_data:
        return profile_data

    filtered_data = {}
    for weekday, weekday_data in profile_data.items():
        if filtered_weekday := _filter_weekday_entries(weekday_data=weekday_data):
            filtered_data[weekday] = filtered_weekday

    return filtered_data


def _filter_schedule_entries(*, schedule_data: CLIMATE_SCHEDULE_DICT) -> CLIMATE_SCHEDULE_DICT:
    """Filter schedule data to remove redundant 24:00 slots."""
    if not schedule_data:
        return schedule_data

    result: CLIMATE_SCHEDULE_DICT = {}
    for profile, profile_data in schedule_data.items():
        if filtered_profile := _filter_profile_entries(profile_data=profile_data):
            result[profile] = filtered_profile
    return result


def _filter_weekday_entries(*, weekday_data: CLIMATE_WEEKDAY_DICT) -> CLIMATE_WEEKDAY_DICT:
    """
    Filter weekday data to remove redundant 24:00 slots.

    Processes slots in slot-number order and stops at the first occurrence of 24:00.
    Any slots after the first 24:00 are ignored, regardless of their endtime.
    This matches the behavior of homematicip_local_climate_scheduler_card.
    """
    if not weekday_data:
        return weekday_data

    # Sort slots by slot number only (not by endtime)
    sorted_slots = sorted(weekday_data.items(), key=lambda item: item[0])

    filtered_slots = []

    for _slot_num, slot in sorted_slots:
        endtime = slot.get(ScheduleSlotType.ENDTIME, "")

        # Add this slot to the filtered list
        filtered_slots.append(slot)

        # Stop at the first occurrence of 24:00 - ignore all subsequent slots
        if endtime == CLIMATE_MAX_SCHEDULER_TIME:
            break

    # Renumber slots to be sequential (1, 2, 3, ...)
    if filtered_slots:
        return dict(enumerate(filtered_slots, start=1))
    return {}


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


def is_schedule_active(group_data: DEFAULT_SCHEDULE_GROUP) -> bool:
    """
    Check if a schedule group will actually execute (not deactivated).

    Args:
        group_data: Schedule group data

    Returns:
        True if schedule has both weekdays and target channels configured,
        False if deactivated or incomplete

    Note:
        A schedule is considered active only if it has both:
        - At least one weekday selected (when to run)
        - At least one target channel selected (what to control)
        Without both, the schedule won't execute, so it's filtered as inactive.

    """
    # Check critical fields needed for execution
    weekday = group_data.get(ScheduleField.WEEKDAY, [])
    target_channels = group_data.get(ScheduleField.TARGET_CHANNELS, [])

    # Schedule is active only if both fields are non-empty
    return bool(weekday and target_channels)


def create_empty_schedule_group(category: DataPointCategory | None = None) -> DEFAULT_SCHEDULE_GROUP:
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


# climate


def _convert_minutes_to_time_str(minutes: Any) -> str:
    """Convert minutes to a time string."""
    if not isinstance(minutes, int):
        return CLIMATE_MAX_SCHEDULER_TIME
    time_str = f"{minutes // 60:0=2}:{minutes % 60:0=2}"
    if SCHEDULER_TIME_PATTERN.match(time_str) is None:
        raise ValidationException(
            i18n.tr(
                "exception.model.week_profile.validate.time_invalid_format",
                time=time_str,
                min=CLIMATE_MIN_SCHEDULER_TIME,
                max=CLIMATE_MAX_SCHEDULER_TIME,
            )
        )
    return time_str


def _convert_time_str_to_minutes(*, time_str: str) -> int:
    """Convert minutes to a time string."""
    if SCHEDULER_TIME_PATTERN.match(time_str) is None:
        raise ValidationException(
            i18n.tr(
                "exception.model.week_profile.validate.time_invalid_format",
                time=time_str,
                min=CLIMATE_MIN_SCHEDULER_TIME,
                max=CLIMATE_MAX_SCHEDULER_TIME,
            )
        )
    try:
        h, m = time_str.split(":")
        return (int(h) * 60) + int(m)
    except Exception as exc:
        raise ValidationException(
            i18n.tr(
                "exception.model.week_profile.validate.time_convert_failed",
                time=time_str,
            )
        ) from exc


def _sort_simple_weekday_list(*, simple_weekday_list: CLIMATE_SIMPLE_WEEKDAY_LIST) -> CLIMATE_SIMPLE_WEEKDAY_LIST:
    """Sort simple weekday list."""
    simple_weekday_dict = sorted(
        {
            _convert_time_str_to_minutes(time_str=str(slot[ScheduleSlotType.STARTTIME])): slot
            for slot in simple_weekday_list
        }.items()
    )
    return [slot[1] for slot in simple_weekday_dict]


def _fillup_weekday_data(*, base_temperature: float, weekday_data: CLIMATE_WEEKDAY_DICT) -> CLIMATE_WEEKDAY_DICT:
    """Fillup weekday data."""
    for slot_no in CLIMATE_SCHEDULE_SLOT_IN_RANGE:
        if slot_no not in weekday_data:
            weekday_data[slot_no] = {
                ScheduleSlotType.ENDTIME: CLIMATE_MAX_SCHEDULER_TIME,
                ScheduleSlotType.TEMPERATURE: base_temperature,
            }

    return weekday_data


def _normalize_weekday_data(*, weekday_data: CLIMATE_WEEKDAY_DICT | dict[str, Any]) -> CLIMATE_WEEKDAY_DICT:
    """
    Normalize climate weekday schedule data.

    Ensures slot keys are integers (not strings) and slots are sorted chronologically
    by ENDTIME. Re-indexes slots from 1-13 in temporal order. Fills missing slots
    at the end with 24:00 entries.

    Args:
        weekday_data: Weekday schedule data (possibly with string keys)

    Returns:
        Normalized weekday schedule with integer keys 1-13 sorted by time

    Example:
        Input: {"2": {ENDTIME: "12:00"}, "1": {ENDTIME: "06:00"}}
        Output: {1: {ENDTIME: "06:00"}, 2: {ENDTIME: "12:00"}, 3: {ENDTIME: "24:00", TEMPERATURE: ...}, ...}

    """
    # Convert string keys to int if necessary
    normalized_data: CLIMATE_WEEKDAY_DICT = {}
    for key, value in weekday_data.items():
        int_key = int(key) if isinstance(key, str) else key
        normalized_data[int_key] = value

    # Sort by ENDTIME and reassign slot numbers 1-13
    sorted_slots = sorted(
        normalized_data.items(),
        key=lambda item: _convert_time_str_to_minutes(time_str=str(item[1][ScheduleSlotType.ENDTIME])),
    )

    # Reassign slot numbers from 1 to N (where N is number of existing slots)
    result: CLIMATE_WEEKDAY_DICT = {}
    for new_slot_no, (_, slot_data) in enumerate(sorted_slots, start=1):
        result[new_slot_no] = slot_data

    # Fill up missing slots (from N+1 to 13) with 24:00 entries
    if result:
        # Get the temperature from the last existing slot
        last_slot = result[len(result)]
        fill_temperature = last_slot.get(ScheduleSlotType.TEMPERATURE, DEFAULT_CLIMATE_FILL_TEMPERATURE)

        # Fill missing slots
        for slot_no in range(len(result) + 1, 14):
            result[slot_no] = {
                ScheduleSlotType.ENDTIME: CLIMATE_MAX_SCHEDULER_TIME,
                ScheduleSlotType.TEMPERATURE: fill_temperature,
            }

    return result
