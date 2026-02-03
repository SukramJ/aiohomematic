# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
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

1. ClimateScheduleDictInternal (Complete Schedule)
   Structure: dict[ScheduleProfile, ClimateProfileScheduleDictInternal]

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

2. ClimateProfileScheduleDictInternal (Single Profile)
   Structure: dict[WeekdayStr, ClimateWeekdayScheduleDictInternal]

   Contains all weekdays for a single profile (e.g., P1).

Example:
   {
       "MONDAY": {
           1: {"endtime": "06:00", "temperature": 18.0},
           2: {"endtime": "22:00", "temperature": 21.0},
           3: {"endtime": "24:00", "temperature": 18.0},
           ...
       },
       "TUESDAY": {...},
       ...
   }

3. ClimateWeekdayScheduleDictInternal (Single Weekday)
   Structure: dict[int, ScheduleSlot]

   Contains 13 time slots for a single weekday. Each slot is a ScheduleSlot TypedDict with
   "endtime" and "temperature" keys. Slots define periods where the thermostat maintains
   a specific temperature until the endtime is reached.

   ScheduleSlot TypedDict:
       endtime: str      # End time in "HH:MM" format
       temperature: float  # Target temperature in Celsius

Example:
   {
       1: {"endtime": "06:00", "temperature": 18.0},
       2: {"endtime": "08:00", "temperature": 21.0},
       3: {"endtime": "17:00", "temperature": 18.0},
       4: {"endtime": "22:00", "temperature": 21.0},
       5: {"endtime": "24:00", "temperature": 18.0},
       6-13: {"endtime": "24:00", "temperature": 18.0}
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
redundant 24:00 slots. The base temperature is automatically identified or can be
specified as part of the data structure. Uses Pydantic models for validation.

ClimateWeekdaySchedule (Pydantic model):
    A model containing:
    - base_temperature (float): The temperature used for periods not explicitly defined
    - periods (list[ClimateSchedulePeriod]): Temperature periods with starttime, endtime, temperature

Example:
ClimateWeekdaySchedule(
    base_temperature=18.0,
    periods=[
        ClimateSchedulePeriod(starttime="06:00", endtime="08:00", temperature=21.0),
        ClimateSchedulePeriod(starttime="17:00", endtime="22:00", temperature=21.0),
    ]
)

ClimateProfileSchedule (Pydantic RootModel):
    Structure: dict[str, ClimateWeekdaySchedule]

    Maps weekday names to their weekday data (base temp + periods).

ClimateSchedule (Pydantic RootModel):
    Structure: dict[str, ClimateProfileSchedule]

    Maps profiles (P1-P6) to their profile data.

The system automatically:
- Identifies base_temperature when converting from full format (using identify_base_temperature())
- Fills gaps with base_temperature when converting to full format
- Converts to full 13-slot format
- Sorts by time
- Validates ranges


SCHEDULE SERVICES
=================

Climate Schedule API (Pydantic Models):
----------------------------------------

All climate schedule methods use Pydantic models for validation and type safety.
These methods provide automatic conversion between simple user format and internal 13-slot format.

get_schedule(*, force_load: bool = False) -> ClimateSchedule
    Retrieves complete schedule in Pydantic model format from cache or device.
    Automatically identifies base_temperature for each weekday.
    Returns ClimateSchedule Pydantic model (all profiles P1-P6).

get_schedule_profile(*, profile: ScheduleProfile, force_load: bool = False) -> ClimateProfileSchedule
    Retrieves single profile in Pydantic model format from cache or device.
    Automatically identifies base_temperature for each weekday.
    Returns ClimateProfileSchedule Pydantic model (all weekdays for specified profile).

get_schedule_weekday(*, profile: ScheduleProfile, weekday: WeekdayStr, force_load: bool = False) -> ClimateWeekdaySchedule
    Retrieves single weekday in Pydantic model format from cache or device.
    Automatically identifies base_temperature.
    Returns ClimateWeekdaySchedule with base_temperature and periods list.

set_schedule(*, schedule_data: ClimateSchedule) -> None
    Persists complete schedule using Pydantic model to device.
    Converts simple format (base_temperature + periods) to full 13-slot format automatically.
    Updates cache and publishes change events.

set_schedule_profile(*, profile: ScheduleProfile, profile_data: ClimateProfileSchedule) -> None
    Persists single profile using Pydantic model to device.
    Converts simple format to full 13-slot format automatically.
    Validates, updates cache, and publishes change events.

set_schedule_weekday(*, profile: ScheduleProfile, weekday: WeekdayStr, weekday_data: ClimateWeekdaySchedule) -> None
    Persists single weekday using Pydantic model to device.
    Converts simple format (base_temperature + periods) to full 13-slot format automatically.
    Normalizes to 13 slots, validates, updates cache.

Non-Climate Schedule API (SimpleSchedule):
-------------------------------------------

Non-climate devices (switches, lights, covers, valves) use SimpleSchedule Pydantic model.

get_schedule(*, force_load: bool = False) -> SimpleSchedule
    Retrieves schedule in Pydantic model format from cache or device.
    Returns SimpleSchedule with entries containing weekdays, time, level, duration, etc.

set_schedule(*, schedule_data: SimpleSchedule) -> None
    Persists schedule using Pydantic model to device.
    Converts to CCU raw format automatically.
    Updates cache and publishes change events.

Utility Methods:
~~~~~~~~~~~~~~~~

copy_schedule(*, target_climate_data_point: BaseCustomDpClimate | None = None) -> None
    Copies entire schedule from this device to another.

copy_profile(*, source_profile: ScheduleProfile, target_profile: ScheduleProfile, target_climate_data_point: BaseCustomDpClimate | None = None) -> None
    Copies single profile to another profile/device.


DATA PROCESSING PIPELINE
=========================

Filtering (Output - Removes Redundancy):
-----------------------------------------
Applied when reading schedules to present clean data to users.

_filter_schedule_entries(schedule_data) -> ClimateScheduleDictInternal
    Filters all profiles in a complete schedule.

_filter_profile_entries(profile_data) -> ClimateProfileScheduleDictInternal
    Filters all weekdays in a profile.

_filter_weekday_entries(weekday_data) -> ClimateWeekdayScheduleDictInternal
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

_normalize_weekday_data(weekday_data) -> ClimateWeekdayScheduleDictInternal
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

Reading a Schedule (Internal/Low-level):
----------------------------------------
1. User calls _get_weekday_internal(profile=P1, weekday="MONDAY")
2. System retrieves from cache or device (13 slots in TypedDict format)
3. _filter_weekday_entries removes redundant 24:00 slots
4. User receives clean data (e.g., 3-5 meaningful slots in TypedDict format)

Reading a Schedule (Public API):
---------------------------------
1. User calls get_schedule_weekday(profile=P1, weekday="MONDAY")
2. System retrieves from cache or device (13 slots)
3. System converts to Pydantic model:
   - Identifies base_temperature
   - Extracts periods (non-base-temp slots)
4. User receives ClimateWeekdaySchedule(base_temperature=18.0, periods=[...])

Setting a Schedule:
-------------------
1. User provides schedule data (may be incomplete, unsorted)
2. System calls _normalize_weekday_data to:
   - Sort by time
   - Fill to exactly 13 slots
3. System validates (temperature ranges, time ranges, sequence)
4. System persists to device
5. Cache is updated, events are published

Using Pydantic Models (Climate):
---------------------------------
1. User calls set_schedule_weekday with:
   - profile: ScheduleProfile.P1
   - weekday: WeekdayStr.MONDAY
   - weekday_data: ClimateWeekdaySchedule(
         base_temperature=18.0,
         periods=[
             ClimateSchedulePeriod(starttime="07:00", endtime="22:00", temperature=21.0)
         ]
     )
2. System converts to full 13-slot format:
   - Slot 1: ENDTIME: "07:00", TEMP: 18.0 (base_temperature before start)
   - Slot 2: ENDTIME: "22:00", TEMP: 21.0 (user's period)
   - Slots 3-13: ENDTIME: "24:00", TEMP: 18.0 (base_temperature after end)
3. System validates and persists to CCU
4. Cache is updated, data_point_updated event is published

Using Pydantic Models (Non-Climate):
-------------------------------------
1. User calls set_schedule with:
   - schedule_data: SimpleSchedule([
         SimpleScheduleEntry(
             weekdays=[Weekday.MONDAY],
             time="07:00",
             level=100,  # For switches: on/off, for lights: brightness, etc.
             duration=60
         )
     ])
2. System converts to CCU raw format with bitwise weekday encoding
3. System validates and persists to CCU
4. Cache is updated, data_point_updated event is published

Reading Pydantic Format (Climate):
-----------------------------------
1. User calls get_schedule_weekday(profile=P1, weekday="MONDAY")
2. System retrieves full schedule from cache (13 slots in TypedDict format)
3. System identifies base_temperature using identify_base_temperature()
   - Analyzes time durations for each temperature
   - Returns temperature used for most minutes of the day
4. System filters out base_temperature periods and returns ClimateWeekdaySchedule:
   (18.0, [{STARTTIME: "07:00", ENDTIME: "22:00", TEMPERATURE: 21.0}])
   ^^^^^ identified base_temperature + list of non-base periods

DATA FLOW SUMMARY
=================

Device → Python (Reading):
    Raw Paramset → convert_raw_to_dict_schedule() → Cache (13 slots) →
    _filter_*_entries() → User (clean, minimal slots)

Python → Device (Writing):
    User Data → _normalize_weekday_data() → Full 13 slots → Validation →
    convert_dict_to_raw_schedule() → Raw Paramset → Device

Simple → Full Format (Writing):
    Simple Tuple (base_temp, list) → _validate_and_convert_simple_to_weekday() →
    Full 13 slots → Normal writing flow

Full → Simple Format (Reading):
    Full 13 slots → identify_base_temperature() (analyzes time durations) →
    _validate_and_convert_weekday_to_simple() →
    Simple Tuple (base_temp, non-base temperature periods only)

"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import IntEnum
import logging
from typing import TYPE_CHECKING, Any, Final, TypedDict, cast

from aiohomematic import i18n
from aiohomematic.const import (
    BIDCOS_DEVICE_CHANNEL_DUMMY,
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
    ScheduleDict,
    ScheduleField,
    ScheduleProfile,
    TimeBase,
    WeekdayInt,
    WeekdayStr,
)
from aiohomematic.decorators import inspector
from aiohomematic.exceptions import ClientException, ValidationException
from aiohomematic.interfaces import CustomDataPointProtocol, WeekProfileProtocol
from aiohomematic.model.schedule_models import (
    SCHEDULE_DOMAIN_CONTEXT_KEY,
    ClimateProfileSchedule,
    ClimateSchedule,
    ClimateSchedulePeriod,
    ClimateWeekdaySchedule,
    SimpleSchedule,
    SimpleScheduleEntry,
    convert_raw_group_to_simple_entry,
    convert_simple_entry_to_raw_group,
)

if TYPE_CHECKING:
    from aiohomematic.model.custom import BaseCustomDpClimate

_LOGGER: Final = logging.getLogger(__name__)

# =============================================================================
# Internal Schedule Types (13-Slot Structure)
# =============================================================================
# These types represent the internal 13-slot schedule structure used by CCU devices.
# They are ONLY used internally for CCU communication and normalization.
# Public APIs use Pydantic models (ClimateSchedule, ClimateProfileSchedule, etc.)


class _ScheduleSlot(TypedDict):
    """
    A single time slot in the internal 13-slot climate schedule structure.

    Each slot defines when a temperature period ends and what temperature to maintain.
    Climate devices use 13 slots per weekday, with unused slots filled with "24:00".

    This is an INTERNAL type used only for CCU communication and normalization.
    Public APIs use ClimateSchedulePeriod (Pydantic model) instead.

    Attributes:
        endtime: End time as string in "HH:MM" format (e.g., "06:00", "24:00")
                 or as integer minutes since midnight (e.g., 360 for "06:00").
                 The CCU always returns integers, but internal conversion may use strings.
        temperature: Target temperature in degrees Celsius

    Example:
        {"endtime": "06:00", "temperature": 18.0}
        {"endtime": 360, "temperature": 18.0}

    """

    endtime: str | int
    temperature: float


_ClimateWeekdayScheduleDictInternal = dict[int, _ScheduleSlot]
"""Internal 13-slot schedule structure for a single weekday, keyed by slot number (1-13)."""

_ClimateProfileScheduleDictInternal = dict[WeekdayStr, _ClimateWeekdayScheduleDictInternal]
"""Internal 13-slot schedule structure for all weekdays in a profile."""

_ClimateScheduleDictInternal = dict[ScheduleProfile, _ClimateProfileScheduleDictInternal]
"""Internal 13-slot schedule structure with all profiles (P1-P6)."""

# =============================================================================
# Internal Schedule Constants
# =============================================================================
# These constants are used internally for schedule processing and CCU communication.

_CLIMATE_MAX_SCHEDULER_TIME: Final = "24:00"
"""Maximum time value for schedule slots (end of day)."""

_CLIMATE_MIN_SCHEDULER_TIME: Final = "00:00"
"""Minimum time value for schedule slots (start of day)."""

_CLIMATE_SCHEDULE_SLOT_IN_RANGE: Final = range(1, 14)
"""Range for all 13 schedule slots per weekday (1-13 inclusive)."""


class WeekProfile[SCHEDULE_DICT_T](ABC, WeekProfileProtocol[SCHEDULE_DICT_T]):
    """Handle the device week profile."""

    __slots__ = (
        "_client",
        "_data_point",
        "_device",
        "_schedule_cache",
        "_schedule_channel_no",
    )

    def __init__(self, *, data_point: CustomDataPointProtocol) -> None:
        """Initialize the device schedule."""
        self._data_point = data_point
        self._device: Final = data_point.device
        self._client: Final = data_point.device.client
        self._schedule_channel_no: Final[int | None] = self._data_point.device_config.schedule_channel_no
        self._schedule_cache: SCHEDULE_DICT_T = self._create_empty_schedule()

    @staticmethod
    @abstractmethod
    def _create_empty_schedule() -> SCHEDULE_DICT_T:
        """Create an empty schedule instance."""

    @staticmethod
    @abstractmethod
    def convert_dict_to_raw_schedule(*, schedule_data: SCHEDULE_DICT_T) -> RAW_SCHEDULE_DICT:
        """Convert dictionary to raw schedule."""

    @staticmethod
    @abstractmethod
    def convert_raw_to_dict_schedule(*, raw_schedule: RAW_SCHEDULE_DICT) -> SCHEDULE_DICT_T:
        """Convert raw schedule to dictionary format."""

    @property
    def has_schedule(self) -> bool:
        """Flag if climate supports schedule."""
        return self.schedule_channel_address is not None

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

    @abstractmethod
    async def get_schedule(self, *, force_load: bool = False) -> SCHEDULE_DICT_T:
        """Return the schedule dictionary."""

    @abstractmethod
    async def reload_and_cache_schedule(self, *, force: bool = False) -> None:
        """Reload schedule entries and update cache."""

    @abstractmethod
    async def set_schedule(self, *, schedule_data: SCHEDULE_DICT_T) -> None:
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
                    key="exception.model.week_profile.schedule.unsupported",
                    address=self._device.name,
                )
            )
        return sca


class DefaultWeekProfile(WeekProfile[SimpleSchedule]):
    """
    Handle device week profiles for switches, lights, covers, and valves.

    This class manages the weekly scheduling functionality for non-climate devices,
    converting between CCU raw paramset format and human-readable Pydantic models.

    The schedule cache stores data in a human-readable SimpleSchedule format:

    Example:
        {
            1: {
                "weekdays": ["MONDAY", "TUESDAY"],
                "time": "07:30",
                "condition": "fixed_time",
                "target_channels": ["1_1"],
                "level": 1.0,
                "duration": "10s",
            }
        }

    """

    def __init__(self, *, data_point: CustomDataPointProtocol) -> None:
        """Initialize the default week profile with empty SimpleSchedule."""
        super().__init__(data_point=data_point)
        self._schedule_cache: SimpleSchedule = SimpleSchedule(entries={})

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
    def _create_empty_schedule() -> SimpleSchedule:
        """Create an empty SimpleSchedule."""
        return SimpleSchedule(entries={})

    @staticmethod
    def convert_dict_to_raw_schedule(*, schedule_data: SimpleSchedule) -> RAW_SCHEDULE_DICT:
        """
        Convert SimpleSchedule to raw paramset schedule.

        Args:
            schedule_data: SimpleSchedule with human-readable entries

        Returns:
            Raw schedule for CCU

        Example:
            Input: SimpleSchedule(entries={1: SimpleScheduleEntry(weekdays=["MONDAY"], ...)})
            Output: {"01_WP_WEEKDAY": 2, "01_WP_FIXED_HOUR": 7, ...}

        """
        raw_schedule: RAW_SCHEDULE_DICT = {}

        for group_no, entry in schedule_data.entries.items():
            # Convert SimpleScheduleEntry to raw group format
            group_data = convert_simple_entry_to_raw_group(entry=entry)

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
                    # These are IntEnum values
                    enum_value = cast(IntEnum, value)
                    raw_schedule[key] = int(enum_value.value)
                elif field in (ScheduleField.WEEKDAY, ScheduleField.TARGET_CHANNELS):
                    # These are lists of IntEnum
                    list_value = cast(list[IntEnum], value)
                    raw_schedule[key] = _list_to_bitwise(items=list_value)
                elif field == ScheduleField.LEVEL:
                    if isinstance(value, IntEnum):
                        raw_schedule[key] = int(value.value)
                    elif isinstance(value, (int, float)):
                        raw_schedule[key] = float(value)
                    else:
                        raw_schedule[key] = 0.0
                elif field == ScheduleField.LEVEL_2:
                    if isinstance(value, (int, float)):
                        raw_schedule[key] = float(value)
                    else:
                        raw_schedule[key] = 0.0
                # ASTRO_OFFSET, DURATION_FACTOR, FIXED_HOUR, FIXED_MINUTE, RAMP_TIME_FACTOR
                elif isinstance(value, (int, float)):
                    raw_schedule[key] = int(value)
                else:
                    raw_schedule[key] = 0

        return raw_schedule

    @staticmethod
    def convert_raw_to_dict_schedule(*, raw_schedule: RAW_SCHEDULE_DICT) -> SimpleSchedule:
        """
        Convert raw paramset schedule to SimpleSchedule.

        Args:
            raw_schedule: Raw schedule from CCU (e.g., {"01_WP_WEEKDAY": 127, ...})

        Returns:
            SimpleSchedule with human-readable entries

        Example:
            Input: {"01_WP_WEEKDAY": 3, "01_WP_FIXED_HOUR": 7, "01_WP_FIXED_MINUTE": 30, ...}
            Output: SimpleSchedule(entries={1: SimpleScheduleEntry(weekdays=["MONDAY", "SUNDAY"], time="07:30", ...)})

        """
        # First, parse raw schedule into intermediate group format
        intermediate_data: DEFAULT_SCHEDULE_DICT = {}

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

            if group_no not in intermediate_data:
                intermediate_data[group_no] = {}

            # Convert value based on field type
            int_value = int(value)

            if field == ScheduleField.ASTRO_TYPE:
                try:
                    intermediate_data[group_no][field] = AstroType(int_value)
                except ValueError:
                    intermediate_data[group_no][field] = int_value
            elif field == ScheduleField.CONDITION:
                try:
                    intermediate_data[group_no][field] = ScheduleCondition(int_value)
                except ValueError:
                    intermediate_data[group_no][field] = int_value
            elif field in (ScheduleField.DURATION_BASE, ScheduleField.RAMP_TIME_BASE):
                try:
                    intermediate_data[group_no][field] = TimeBase(int_value)
                except ValueError:
                    intermediate_data[group_no][field] = int_value
            elif field == ScheduleField.LEVEL:
                intermediate_data[group_no][field] = int_value if isinstance(value, int) else float(value)
            elif field == ScheduleField.LEVEL_2:
                intermediate_data[group_no][field] = float(value)
            elif field == ScheduleField.WEEKDAY:
                intermediate_data[group_no][field] = _bitwise_to_list(value=int_value, enum_class=WeekdayInt)
            elif field == ScheduleField.TARGET_CHANNELS:
                intermediate_data[group_no][field] = _bitwise_to_list(value=int_value, enum_class=ScheduleActorChannel)
            else:
                # ASTRO_OFFSET, DURATION_FACTOR, FIXED_HOUR, FIXED_MINUTE, RAMP_TIME_FACTOR
                intermediate_data[group_no][field] = int_value

        # Convert intermediate format to SimpleSchedule
        entries: dict[int, SimpleScheduleEntry] = {}
        for group_no, group_data in intermediate_data.items():
            if is_schedule_active(group_data=group_data):
                try:
                    entries[group_no] = convert_raw_group_to_simple_entry(group_data=group_data)
                except (ValueError, KeyError) as ex:
                    _LOGGER.debug(
                        "CONVERT_RAW_TO_DICT_SCHEDULE: Failed to convert group %d: %s",
                        group_no,
                        ex,
                    )
                    continue

        return SimpleSchedule(entries=entries)

    def empty_schedule_entry(self) -> SimpleScheduleEntry:
        """Return an empty (minimal) schedule entry."""
        return SimpleScheduleEntry(
            weekdays=["MONDAY"],
            time="00:00",
            condition="fixed_time",
            astro_type=None,
            astro_offset_minutes=0,
            target_channels=["1_1"],
            level=0.0,
            level_2=None,
            duration=None,
            ramp_time=None,
        )

    @inspector
    async def get_schedule(self, *, force_load: bool = False) -> SimpleSchedule:
        """Return the schedule in human-readable SimpleSchedule format."""
        if not self.has_schedule:
            raise ValidationException(
                i18n.tr(
                    key="exception.model.week_profile.schedule.unsupported",
                    address=self._device.name,
                )
            )
        await self.reload_and_cache_schedule(force=force_load)
        return self._schedule_cache

    async def reload_and_cache_schedule(self, *, force: bool = False) -> None:
        """Reload schedule entries from CCU and update cache with SimpleSchedule format."""
        if not force and not self.has_schedule:
            return

        try:
            new_raw_schedule = await self._get_raw_schedule()
        except ValidationException:
            return

        old_schedule = self._schedule_cache
        new_schedule = self.convert_raw_to_dict_schedule(raw_schedule=new_raw_schedule)
        self._schedule_cache = new_schedule

        if old_schedule != new_schedule:
            self._data_point.publish_data_point_updated_event()

    @inspector
    async def set_schedule(self, *, schedule_data: SimpleSchedule) -> None:
        """
        Persist the provided SimpleSchedule to device.

        Args:
            schedule_data: SimpleSchedule with human-readable entries (Pydantic-validated)

        Raises:
            ValidationError: If schedule_data violates domain-specific constraints

        Note:
            The cache is NOT updated optimistically. The cache will be refreshed
            from CCU when CONFIG_PENDING = False is received, ensuring consistency
            between cache and CCU state.

            Domain-specific validation is applied based on the device category:
            - SWITCH: level must be 0.0 or 1.0, no level_2, no ramp_time
            - LIGHT: no level_2
            - COVER: no ramp_time, no duration
            - VALVE: no level_2, no ramp_time

        """
        sca = self._validate_and_get_schedule_channel_address()

        # Re-validate with domain context to enforce domain-specific constraints
        # The context passes the device category to enable domain-aware validation
        SimpleSchedule.model_validate(
            schedule_data.model_dump(),
            context={SCHEDULE_DOMAIN_CONTEXT_KEY: self._data_point.category},
        )

        # Write to device - cache will be updated via CONFIG_PENDING event
        await self._client.put_paramset(
            channel_address=sca,
            paramset_key_or_link_address=ParamsetKey.MASTER,
            values=self._convert_schedule_entries(
                values=self.convert_dict_to_raw_schedule(schedule_data=schedule_data)
            ),
        )

    async def _get_raw_schedule(self) -> RAW_SCHEDULE_DICT:
        """Return the raw schedule dictionary filtered to WP entries."""
        try:
            sca = self._validate_and_get_schedule_channel_address()
            raw_data = await self._client.get_paramset(
                channel_address=sca,
                paramset_key=ParamsetKey.MASTER,
                convert_from_pd=True,
            )
        except ClientException as cex:
            raise ValidationException(
                i18n.tr(
                    key="exception.model.week_profile.schedule.unsupported",
                    name=self._device.name,
                )
            ) from cex

        if not (schedule := self._convert_schedule_entries(values=raw_data)):
            raise ValidationException(
                i18n.tr(
                    key="exception.model.week_profile.schedule.unsupported",
                    name=self._device.name,
                )
            )
        return schedule


class ClimateWeekProfile(WeekProfile[ClimateSchedule]):
    """
    Handle climate device week profiles (thermostats).

    This class manages heating/cooling schedules with time slots and temperature settings.
    Supports multiple profiles (P1-P6) with 13 time slots per weekday.
    Provides both raw and simplified schedule interfaces for easy temperature programming.
    """

    _data_point: BaseCustomDpClimate
    __slots__ = (
        "_max_temp",
        "_min_temp",
    )

    def __init__(self, *, data_point: CustomDataPointProtocol) -> None:
        """Initialize the climate week profile."""
        super().__init__(data_point=data_point)
        self._min_temp: Final[float] = self._data_point.min_temp
        self._max_temp: Final[float] = self._data_point.max_temp

    @staticmethod
    def _create_empty_schedule() -> ClimateSchedule:
        """Create an empty ClimateSchedule."""
        return ClimateSchedule({})

    @staticmethod
    def convert_dict_to_raw_schedule(  # type: ignore[override]
        *, schedule_data: _ClimateScheduleDictInternal
    ) -> RAW_SCHEDULE_DICT:
        """
        Convert structured climate schedule to raw paramset format.

        Note: This method uses _ClimateScheduleDictInternal (13-slot format) internally,
        not ClimateSchedule (simple format), hence the type override.

        Args:
            schedule_data: Structured schedule with profiles, weekdays, and time slots

        Returns:
            Raw schedule dictionary for CCU transmission

        Example:
            Input: {ScheduleProfile.P1: {"MONDAY": {1: {"temperature": 20.0, "endtime": "06:00"}}}}
            Output: {"P1_TEMPERATURE_MONDAY_1": 20.0, "P1_ENDTIME_MONDAY_1": 360}

        """
        raw_paramset: RAW_SCHEDULE_DICT = {}
        for profile, profile_data in schedule_data.items():
            for weekday, weekday_data in profile_data.items():
                for slot_no, slot in weekday_data.items():
                    for slot_type, slot_value in slot.items():
                        # Convert lowercase slot_type to uppercase for CCU format
                        raw_profile_name = f"{str(profile)}_{str(slot_type).upper()}_{str(weekday)}_{slot_no}"
                        if SCHEDULER_PROFILE_PATTERN.match(raw_profile_name) is None:
                            raise ValidationException(
                                i18n.tr(
                                    key="exception.model.week_profile.validate.profile_name_invalid",
                                    profile_name=raw_profile_name,
                                )
                            )
                        raw_value: float | int = cast(float | int, slot_value)
                        if slot_type == "endtime" and isinstance(slot_value, str):
                            raw_value = _convert_time_str_to_minutes(time_str=slot_value)
                        raw_paramset[raw_profile_name] = raw_value
        return raw_paramset

    @staticmethod
    def convert_raw_to_dict_schedule(*, raw_schedule: RAW_SCHEDULE_DICT) -> _ClimateScheduleDictInternal:  # type: ignore[override]
        """
        Convert raw CCU schedule to structured dictionary format.

        Args:
            raw_schedule: Raw schedule from CCU paramset

        Returns:
            Structured schedule grouped by profile, weekday, and slot

        Example:
            Input: {"P1_TEMPERATURE_MONDAY_1": 20.0, "P1_ENDTIME_MONDAY_1": 360}
            Output: {ScheduleProfile.P1: {"MONDAY": {1: {"temperature": 20.0, "endtime": "06:00"}}}}

        """
        # Use permissive type during incremental construction, final type is ClimateScheduleDictInternal
        schedule_data: dict[ScheduleProfile, dict[WeekdayStr, dict[int, dict[str, str | float]]]] = {}

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
                # Convert slot type to lowercase string instead of enum
                _slot_type = slot_type_name.lower()
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

            # Convert ENDTIME from minutes (int) to time string format
            # With convert_from_pd=True, ENDTIME is always int from client layer
            final_value: str | float = slot_value
            if _slot_type == "endtime" and isinstance(slot_value, int):
                final_value = _convert_minutes_to_time_str(minutes=slot_value)

            schedule_data[_profile][_weekday][_slot_no][_slot_type] = final_value

        # Cast to ClimateScheduleDictInternal since we built it with all required keys
        return cast(_ClimateScheduleDictInternal, schedule_data)

    @property
    def available_schedule_profiles(self) -> tuple[ScheduleProfile, ...]:
        """Return the available schedule profiles."""
        return tuple(ScheduleProfile(key) for key in self._schedule_cache)

    @property
    def schedule(self) -> ClimateSchedule:
        """Return schedule as Pydantic model for validation and easy access."""
        return self._schedule_cache

    @inspector
    async def copy_profile(
        self,
        *,
        source_profile: ScheduleProfile,
        target_profile: ScheduleProfile,
        target_climate_data_point: BaseCustomDpClimate | None = None,
    ) -> None:
        """Copy schedule profile to target device."""
        same_device = False
        if not self.has_schedule:
            raise ValidationException(
                i18n.tr(
                    key="exception.model.week_profile.schedule.unsupported",
                    name=self._device.name,
                )
            )
        if target_climate_data_point is None:
            target_climate_data_point = self._data_point
        if self._data_point is target_climate_data_point:
            same_device = True

        if same_device and (source_profile == target_profile or (source_profile is None or target_profile is None)):
            raise ValidationException(i18n.tr(key="exception.model.week_profile.copy_schedule.same_device_invalid"))

        # get_profile now returns Pydantic model
        source_profile_data = await self.get_profile(profile=source_profile)

        if not target_climate_data_point.device.has_week_profile:
            raise ValidationException(
                i18n.tr(
                    key="exception.model.week_profile.schedule.unsupported",
                    address=self._device.name,
                )
            )
        if target_climate_data_point.device.week_profile and isinstance(
            target_climate_data_point.device.week_profile, ClimateWeekProfile
        ):
            # Use the new set_profile API which accepts Pydantic models
            await target_climate_data_point.device.week_profile.set_profile(
                profile=target_profile,
                profile_data=source_profile_data,
            )

    @inspector
    async def copy_schedule(self, *, target_climate_data_point: BaseCustomDpClimate) -> None:
        """Copy schedule to target device."""
        if self._data_point.schedule_profile_nos != target_climate_data_point.schedule_profile_nos:
            raise ValidationException(i18n.tr(key="exception.model.week_profile.copy_schedule.profile_count_mismatch"))
        raw_schedule = await self._get_raw_schedule()
        if not target_climate_data_point.device.has_week_profile:
            raise ValidationException(
                i18n.tr(
                    key="exception.model.week_profile.schedule.unsupported",
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
    async def get_profile(self, *, profile: ScheduleProfile, force_load: bool = False) -> ClimateProfileSchedule:
        """Return schedule by climate profile as Pydantic model."""
        if not self.has_schedule:
            raise ValidationException(
                i18n.tr(
                    key="exception.model.week_profile.schedule.unsupported",
                    name=self._device.name,
                )
            )
        if force_load or not self._schedule_cache:
            await self.reload_and_cache_schedule()
        # _schedule_cache is now ClimateSchedule (Pydantic), return profile or empty
        result = self._schedule_cache.get(profile)
        return result if result is not None else ClimateProfileSchedule({})

    @inspector
    async def get_schedule(self, *, force_load: bool = False) -> ClimateSchedule:
        """Return the complete schedule as Pydantic model."""
        if not self.has_schedule:
            raise ValidationException(
                i18n.tr(
                    key="exception.model.week_profile.schedule.unsupported",
                    name=self._device.name,
                )
            )
        if force_load or not self._schedule_cache:
            await self.reload_and_cache_schedule()
        return self._schedule_cache

    @inspector
    async def get_weekday(
        self, *, profile: ScheduleProfile, weekday: WeekdayStr, force_load: bool = False
    ) -> ClimateWeekdaySchedule:
        """Return schedule by climate profile and weekday as Pydantic model."""
        if not self.has_schedule:
            raise ValidationException(
                i18n.tr(
                    key="exception.model.week_profile.schedule.unsupported",
                    name=self._device.name,
                )
            )
        if force_load or not self._schedule_cache:
            await self.reload_and_cache_schedule()
        # _schedule_cache is now ClimateSchedule (Pydantic), return weekday or empty
        if (profile_data := self._schedule_cache.get(profile)) is None:
            return ClimateWeekdaySchedule(base_temperature=20.0, periods=[])
        weekday_data = profile_data.get(weekday)
        return weekday_data if weekday_data is not None else ClimateWeekdaySchedule(base_temperature=20.0, periods=[])

    async def reload_and_cache_schedule(self, *, force: bool = False) -> None:
        """Reload schedules from CCU and update cache, publish events if changed."""
        if not self.has_schedule:
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
                "RELOAD_AND_CACHE_SCHEDULE: Schedule changed for %s, publishing events",
                self._device.name,
            )
            # Publish data point updated event to trigger handlers
            self._data_point.publish_data_point_updated_event()

    @inspector
    async def set_profile(
        self,
        *,
        profile: ScheduleProfile,
        profile_data: ScheduleDict | ClimateProfileSchedule,
    ) -> None:
        """
        Set a profile to device.

        Note:
            The cache is NOT updated optimistically. The cache will be refreshed
            from CCU when CONFIG_PENDING = False is received, ensuring consistency
            between cache and CCU state.

        """
        # Convert simple format to internal 13-slot format
        converted_profile_data = self._validate_and_convert_simple_to_profile(simple_profile_data=profile_data)
        sca = self._validate_and_get_schedule_channel_address()

        # Write to device - cache will be updated via CONFIG_PENDING event
        await self._client.put_paramset(
            channel_address=sca,
            paramset_key_or_link_address=ParamsetKey.MASTER,
            values=self.convert_dict_to_raw_schedule(schedule_data={profile: converted_profile_data}),
        )

    @inspector
    async def set_schedule(self, *, schedule_data: ScheduleDict | ClimateSchedule) -> None:
        """
        Set the complete schedule to device.

        Note:
            The cache is NOT updated optimistically. The cache will be refreshed
            from CCU when CONFIG_PENDING = False is received, ensuring consistency
            between cache and CCU state.

        """
        # Convert simple schedule to internal 13-slot format
        converted_schedule_data = self._validate_and_convert_simple_to_schedule(simple_schedule_data=schedule_data)
        sca = self._validate_and_get_schedule_channel_address()

        # Write to device - cache will be updated via CONFIG_PENDING event
        await self._client.put_paramset(
            channel_address=sca,
            paramset_key_or_link_address=ParamsetKey.MASTER,
            values=self.convert_dict_to_raw_schedule(schedule_data=converted_schedule_data),
        )

    @inspector
    async def set_weekday(
        self,
        *,
        profile: ScheduleProfile,
        weekday: WeekdayStr,
        weekday_data: ScheduleDict | ClimateWeekdaySchedule,
    ) -> None:
        """
        Store a weekday profile to device.

        Note:
            The cache is NOT updated optimistically. The cache will be refreshed
            from CCU when CONFIG_PENDING = False is received, ensuring consistency
            between cache and CCU state.

        """
        # Convert simple format to internal 13-slot format
        converted_weekday_data = self._validate_and_convert_simple_to_weekday(simple_weekday_data=weekday_data)
        sca = self._validate_and_get_schedule_channel_address()

        # Write to device - cache will be updated via CONFIG_PENDING event
        await self._client.put_paramset(
            channel_address=sca,
            paramset_key_or_link_address=ParamsetKey.MASTER,
            values=self.convert_dict_to_raw_schedule(schedule_data={profile: {weekday: converted_weekday_data}}),
            check_against_pd=True,
        )

    def _convert_raw_to_pydantic(self, *, raw_schedule: RAW_SCHEDULE_DICT) -> ClimateSchedule:
        """
        Convert raw CCU schedule directly to Pydantic model (optimized).

        This method combines the conversion steps for better performance.
        The intermediate DictInternal format is only used internally for
        normalization and validation logic.
        """
        # Convert to internal format (still needed for normalization logic)
        internal_schedule = self.convert_raw_to_dict_schedule(raw_schedule=raw_schedule)
        # Convert to Pydantic
        return self._validate_and_convert_schedule_to_simple(schedule_data=internal_schedule)

    async def _get_raw_schedule(self) -> RAW_SCHEDULE_DICT:
        """Return the raw schedule."""
        try:
            sca = self._validate_and_get_schedule_channel_address()
            raw_data = await self._client.get_paramset(
                channel_address=sca,
                paramset_key=ParamsetKey.MASTER,
                convert_from_pd=True,
            )
            raw_schedule = {key: value for key, value in raw_data.items() if SCHEDULER_PROFILE_PATTERN.match(key)}
        except ClientException as cex:
            raise ValidationException(
                i18n.tr(
                    key="exception.model.week_profile.schedule.unsupported",
                    name=self._device.name,
                )
            ) from cex
        return raw_schedule

    async def _get_schedule_profile(self) -> ClimateSchedule:
        """Get the schedule as Pydantic model."""
        # Get raw schedule data from device
        raw_schedule = await self._get_raw_schedule()
        # Convert directly to Pydantic (optimized path)
        return self._convert_raw_to_pydantic(raw_schedule=raw_schedule)

    def _validate_and_convert_profile_to_simple(
        self, *, profile_data: _ClimateProfileScheduleDictInternal
    ) -> ClimateProfileSchedule:
        """Convert a full climate profile to simplified Pydantic model."""
        simple_profile: dict[WeekdayStr, ClimateWeekdaySchedule] = {}
        for weekday, weekday_data in profile_data.items():
            simple_profile[weekday] = self._validate_and_convert_weekday_to_simple(weekday_data=weekday_data)
        # Convert enum keys to strings for RootModel
        return ClimateProfileSchedule({str(k): v for k, v in simple_profile.items()})

    def _validate_and_convert_schedule_to_simple(
        self, *, schedule_data: _ClimateScheduleDictInternal
    ) -> ClimateSchedule:
        """Convert a full schedule to simplified Pydantic model."""
        simple_schedule: dict[ScheduleProfile, ClimateProfileSchedule] = {}
        for profile, profile_data in schedule_data.items():
            simple_schedule[profile] = self._validate_and_convert_profile_to_simple(profile_data=profile_data)
        # Convert enum keys to strings for RootModel
        return ClimateSchedule({str(k): v for k, v in simple_schedule.items()})

    def _validate_and_convert_simple_to_profile(
        self, *, simple_profile_data: ScheduleDict | ClimateProfileSchedule
    ) -> _ClimateProfileScheduleDictInternal:
        """Convert simple profile to full profile dict."""
        # Validate with Pydantic
        try:
            validated_profile = ClimateProfileSchedule.model_validate(simple_profile_data)
        except ValueError as ex:
            raise ValidationException(str(ex)) from ex

        # Convert each weekday to full format
        # RootModel behaves like a dict, can iterate directly
        profile_data: _ClimateProfileScheduleDictInternal = {}
        for day, simple_weekday_data in validated_profile.root.items():
            # Cast string key to WeekdayStr enum for TypedDict
            profile_data[WeekdayStr(day)] = self._validate_and_convert_simple_to_weekday(
                simple_weekday_data=simple_weekday_data
            )
        return profile_data

    def _validate_and_convert_simple_to_schedule(
        self, *, simple_schedule_data: ScheduleDict | ClimateSchedule
    ) -> _ClimateScheduleDictInternal:
        """Convert simple schedule to full schedule dict."""
        # Validate with Pydantic
        try:
            validated_schedule = ClimateSchedule.model_validate(simple_schedule_data)
        except ValueError as ex:
            raise ValidationException(str(ex)) from ex

        # Convert each profile to full format
        # RootModel behaves like a dict, can iterate directly
        schedule_data: _ClimateScheduleDictInternal = {}
        for profile, profile_data in validated_schedule.root.items():
            # Cast string key to ScheduleProfile enum for TypedDict
            schedule_data[ScheduleProfile(profile)] = self._validate_and_convert_simple_to_profile(
                simple_profile_data=profile_data
            )
        return schedule_data

    def _validate_and_convert_simple_to_weekday(
        self, *, simple_weekday_data: ScheduleDict | ClimateWeekdaySchedule
    ) -> _ClimateWeekdayScheduleDictInternal:
        """Convert simple weekday to full weekday dict."""
        # Validate with Pydantic
        try:
            validated_weekday = ClimateWeekdaySchedule.model_validate(simple_weekday_data)
        except ValueError as ex:
            raise ValidationException(str(ex)) from ex

        base_temperature = validated_weekday.base_temperature
        _weekday_data: list[dict[str, str | float]] = [
            {
                "starttime": p.starttime,
                "endtime": p.endtime,
                "temperature": p.temperature,
            }
            for p in validated_weekday.periods
        ]

        if not self._min_temp <= base_temperature <= self._max_temp:
            raise ValidationException(
                i18n.tr(
                    key="exception.model.week_profile.validate.base_temperature_out_of_range",
                    base_temperature=base_temperature,
                    min=self._min_temp,
                    max=self._max_temp,
                )
            )

        weekday_data: _ClimateWeekdayScheduleDictInternal = {}

        # Pydantic already validated: required fields, time format, starttime < endtime
        # Only need to validate business logic: overlaps, temperature range, gaps
        sorted_periods = sorted(_weekday_data, key=lambda p: _convert_time_str_to_minutes(time_str=str(p["starttime"])))
        previous_endtime = _CLIMATE_MIN_SCHEDULER_TIME
        slot_no = 1
        for slot in sorted_periods:
            starttime = str(slot["starttime"])
            endtime = str(slot["endtime"])
            temperature = float(slot["temperature"])

            # Check for overlaps between periods
            if _convert_time_str_to_minutes(time_str=starttime) < _convert_time_str_to_minutes(
                time_str=previous_endtime
            ):
                raise ValidationException(
                    i18n.tr(
                        key="exception.model.week_profile.validate.overlap",
                        start=starttime,
                        end=endtime,
                    )
                )

            if not self._min_temp <= temperature <= self._max_temp:
                raise ValidationException(
                    i18n.tr(
                        key="exception.model.week_profile.validate.temperature_out_of_range_for_times",
                        temperature=temperature,
                        min=self._min_temp,
                        max=self._max_temp,
                        start=starttime,
                        end=endtime,
                    )
                )

            if _convert_time_str_to_minutes(time_str=starttime) > _convert_time_str_to_minutes(
                time_str=previous_endtime
            ):
                weekday_data[slot_no] = {
                    "endtime": starttime,
                    "temperature": base_temperature,
                }
                slot_no += 1

            weekday_data[slot_no] = {
                "endtime": endtime,
                "temperature": temperature,
            }
            previous_endtime = endtime
            slot_no += 1

        return _fillup_weekday_data(base_temperature=base_temperature, weekday_data=weekday_data)

    def _validate_and_convert_weekday_to_simple(
        self, *, weekday_data: _ClimateWeekdayScheduleDictInternal
    ) -> ClimateWeekdaySchedule:
        """
        Convert a full weekday (13 slots) to a simplified Pydantic model.

        Returns:
            ClimateWeekdaySchedule with base_temperature and periods list

        """
        base_temperature = identify_base_temperature(weekday_data=weekday_data)

        # filter out irrelevant entries
        filtered_data = _filter_weekday_entries(weekday_data=weekday_data)

        if not self._min_temp <= float(base_temperature) <= self._max_temp:
            raise ValidationException(
                i18n.tr(
                    key="exception.model.week_profile.validate.base_temperature_out_of_range",
                    base_temperature=base_temperature,
                    min=self._min_temp,
                    max=self._max_temp,
                )
            )

        # Normalize and perform basic validation using existing helper
        normalized = _normalize_weekday_data(weekday_data=filtered_data)

        # Build simple list by merging consecutive non-base temperature slots
        periods: list[ClimateSchedulePeriod] = []
        previous_end = _CLIMATE_MIN_SCHEDULER_TIME
        open_range: ClimateSchedulePeriod | None = None
        last_temp: float | None = None

        for no in sorted(normalized.keys()):
            slot = normalized[no]
            # Handle int (raw from CCU), time string (from cache), and numeric string (legacy cache)
            endtime_minutes = _endtime_to_minutes(endtime=slot["endtime"])
            endtime_str = _convert_minutes_to_time_str(minutes=endtime_minutes)
            temp = float(slot["temperature"])

            # If time decreases from previous, the weekday is invalid
            if _convert_time_str_to_minutes(time_str=endtime_str) < _convert_time_str_to_minutes(
                time_str=str(previous_end)
            ):
                raise ValidationException(
                    i18n.tr(
                        key="exception.model.week_profile.validate.time_out_of_bounds_profile_slot",
                        time=endtime_str,
                        min_time=_CLIMATE_MIN_SCHEDULER_TIME,
                        max_time=_CLIMATE_MAX_SCHEDULER_TIME,
                        profile="-",
                        weekday="-",
                        no=no,
                    )
                )

            # Ignore base temperature segments; track/merge non-base
            if temp != float(base_temperature):
                if open_range is None:
                    # start new range from previous_end
                    open_range = ClimateSchedulePeriod(
                        starttime=str(previous_end),
                        endtime=endtime_str,
                        temperature=temp,
                    )
                    last_temp = temp
                # extend if same temperature
                elif temp == last_temp:
                    open_range = ClimateSchedulePeriod(
                        starttime=open_range.starttime,
                        endtime=endtime_str,
                        temperature=temp,
                    )
                else:
                    # temperature changed: close previous and start new
                    periods.append(open_range)
                    open_range = ClimateSchedulePeriod(
                        starttime=str(previous_end),
                        endtime=endtime_str,
                        temperature=temp,
                    )
                    last_temp = temp

            # closing any open non-base range when hitting base segment
            elif open_range is not None:
                periods.append(open_range)
                open_range = None
                last_temp = None

            previous_end = endtime_str

        # After last slot, if we still have an open range, close it
        if open_range is not None:
            periods.append(open_range)

        # Sort by start time
        if periods:
            periods = sorted(periods, key=lambda p: _convert_time_str_to_minutes(time_str=p.starttime))

        return ClimateWeekdaySchedule(base_temperature=base_temperature, periods=periods)


def create_week_profile(*, data_point: CustomDataPointProtocol) -> ClimateWeekProfile | DefaultWeekProfile:
    """Create a week profile from a custom data point."""
    if data_point.category == DataPointCategory.CLIMATE:
        return ClimateWeekProfile(data_point=data_point)
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


def _filter_profile_entries(
    *, profile_data: _ClimateProfileScheduleDictInternal
) -> _ClimateProfileScheduleDictInternal:
    """Filter profile data to remove redundant 24:00 slots."""
    if not profile_data:
        return profile_data

    filtered_data = {}
    for weekday, weekday_data in profile_data.items():
        if filtered_weekday := _filter_weekday_entries(weekday_data=weekday_data):
            filtered_data[weekday] = filtered_weekday

    return filtered_data


def _filter_schedule_entries(*, schedule_data: _ClimateScheduleDictInternal) -> _ClimateScheduleDictInternal:
    """Filter schedule data to remove redundant 24:00 slots."""
    if not schedule_data:
        return schedule_data

    result: _ClimateScheduleDictInternal = {}
    for profile, profile_data in schedule_data.items():
        if filtered_profile := _filter_profile_entries(profile_data=profile_data):
            result[profile] = filtered_profile
    return result


def _filter_weekday_entries(
    *, weekday_data: _ClimateWeekdayScheduleDictInternal
) -> _ClimateWeekdayScheduleDictInternal:
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
        endtime = slot.get("endtime", "")

        # Add this slot to the filtered list
        filtered_slots.append(slot)

        # Stop at the first occurrence of 24:00 - ignore all subsequent slots
        if endtime == _CLIMATE_MAX_SCHEDULER_TIME:
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


def is_schedule_active(*, group_data: DEFAULT_SCHEDULE_GROUP) -> bool:
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


def create_empty_schedule_group(*, category: DataPointCategory | None = None) -> DEFAULT_SCHEDULE_GROUP:
    """
    Create an empty (deactivated) schedule group and tailor optional fields depending on the provided `category`.

    Base (category‑agnostic) fields that are always included:
    - `ScheduleField.ASTRO_OFFSET` → `0`
    - `ScheduleField.ASTRO_TYPE` → `AstroType.SUNRISE`
    - `ScheduleField.CONDITION` → `ScheduleCondition.FIXED_TIME`
    - `ScheduleField.FIXED_HOUR` → `0`
    - `ScheduleField.FIXED_MINUTE` → `0`
    - `ScheduleField.TARGET_CHANNELS` → `[]` (empty list)
    - `ScheduleField.WEEKDAY` → `[]` (empty list)

    Additional fields per `DataPointCategory`:
    - `DataPointCategory.COVER`:
      - `ScheduleField.LEVEL` → `0.0`
      - `ScheduleField.LEVEL_2` → `0.0`

    - `DataPointCategory.SWITCH`:
      - `ScheduleField.DURATION_BASE` → `TimeBase.MS_100`
      - `ScheduleField.DURATION_FACTOR` → `0`
      - `ScheduleField.LEVEL` → `0` (binary level)

    - `DataPointCategory.LIGHT`:
      - `ScheduleField.DURATION_BASE` → `TimeBase.MS_100`
      - `ScheduleField.DURATION_FACTOR` → `0`
      - `ScheduleField.RAMP_TIME_BASE` → `TimeBase.MS_100`
      - `ScheduleField.RAMP_TIME_FACTOR` → `0`
      - `ScheduleField.LEVEL` → `0.0`

    - `DataPointCategory.VALVE`:
      - `ScheduleField.LEVEL` → `0.0`

    Notes:
    - If `category` is `None` or not one of the above, only the base fields are
      included.
    - The created group is considered inactive by default (see
      `is_schedule_group_active`): it becomes active only after both
      `ScheduleField.WEEKDAY` and `ScheduleField.TARGET_CHANNELS` are non‑empty.

    Returns:
        A schedule group dictionary with fields initialized to their inactive
        defaults according to the given `category`.

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


def identify_base_temperature(*, weekday_data: _ClimateWeekdayScheduleDictInternal) -> float:
    """
    Identify base temperature from weekday data.

    Identify the temperature that is used for the most minutes of a day.
    """
    if not weekday_data:
        return DEFAULT_CLIMATE_FILL_TEMPERATURE

    # Track total minutes for each temperature
    temperature_minutes: dict[float, int] = {}
    previous_minutes = 0

    # Iterate through slots in order
    for slot_no in sorted(weekday_data.keys()):
        slot = weekday_data[slot_no]
        # Handle int (raw from CCU), time string (from cache), and numeric string (legacy cache)
        endtime_minutes = _endtime_to_minutes(endtime=slot["endtime"])
        temperature = float(slot["temperature"])

        # Calculate duration for this slot (from previous endtime to current endtime)
        duration = endtime_minutes - previous_minutes

        # Add duration to the total for this temperature
        if temperature not in temperature_minutes:
            temperature_minutes[temperature] = 0
        temperature_minutes[temperature] += duration

        previous_minutes = endtime_minutes

    # Return the temperature with the most minutes
    if not temperature_minutes:
        return DEFAULT_CLIMATE_FILL_TEMPERATURE

    return max(temperature_minutes, key=lambda temp: temperature_minutes[temp])


def _convert_minutes_to_time_str(*, minutes: Any) -> str:
    """Convert minutes to a time string."""
    if not isinstance(minutes, int):
        return _CLIMATE_MAX_SCHEDULER_TIME
    time_str = f"{minutes // 60:0=2}:{minutes % 60:0=2}"
    if SCHEDULER_TIME_PATTERN.match(time_str) is None:
        raise ValidationException(
            i18n.tr(
                key="exception.model.week_profile.validate.time_invalid_format",
                time=time_str,
                min=_CLIMATE_MIN_SCHEDULER_TIME,
                max=_CLIMATE_MAX_SCHEDULER_TIME,
            )
        )
    return time_str


def _convert_time_str_to_minutes(*, time_str: str) -> int:
    """Convert minutes to a time string."""
    if SCHEDULER_TIME_PATTERN.match(time_str) is None:
        raise ValidationException(
            i18n.tr(
                key="exception.model.week_profile.validate.time_invalid_format",
                time=time_str,
                min=_CLIMATE_MIN_SCHEDULER_TIME,
                max=_CLIMATE_MAX_SCHEDULER_TIME,
            )
        )
    try:
        h, m = time_str.split(":")
        return (int(h) * 60) + int(m)
    except Exception as exc:
        raise ValidationException(
            i18n.tr(
                key="exception.model.week_profile.validate.time_convert_failed",
                time=time_str,
            )
        ) from exc


def _endtime_to_minutes(*, endtime: int | str) -> int:
    """
    Convert endtime value to minutes, handling multiple formats.

    Handles three input formats:
    - int: Raw minutes from CCU (e.g., 360)
    - str "hh:mm": Time string format (e.g., "06:00")
    - str numeric: Legacy cached minutes as string (e.g., "360")

    Args:
        endtime: Endtime value in any supported format

    Returns:
        Minutes as integer

    """
    if isinstance(endtime, int):
        return endtime
    # String: check if it's numeric (legacy cache format) or time format
    if endtime.isdigit():
        return int(endtime)
    return _convert_time_str_to_minutes(time_str=endtime)


def _fillup_weekday_data(
    *, base_temperature: float, weekday_data: _ClimateWeekdayScheduleDictInternal
) -> _ClimateWeekdayScheduleDictInternal:
    """Fillup weekday data."""
    for slot_no in _CLIMATE_SCHEDULE_SLOT_IN_RANGE:
        if slot_no not in weekday_data:
            weekday_data[slot_no] = {
                "endtime": _CLIMATE_MAX_SCHEDULER_TIME,
                "temperature": base_temperature,
            }

    return weekday_data


def _normalize_weekday_data(
    *, weekday_data: _ClimateWeekdayScheduleDictInternal | ScheduleDict
) -> _ClimateWeekdayScheduleDictInternal:
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
    normalized_data: _ClimateWeekdayScheduleDictInternal = {}
    for key, value in weekday_data.items():
        int_key = int(key) if isinstance(key, str) else key
        normalized_data[int_key] = value

    # Sort by ENDTIME and reassign slot numbers 1-13
    # Handle int (raw from CCU), time string (from cache), and numeric string (legacy cache)
    sorted_slots = sorted(
        normalized_data.items(),
        key=lambda item: _endtime_to_minutes(endtime=item[1]["endtime"]),
    )

    # Reassign slot numbers from 1 to N (where N is number of existing slots)
    result: _ClimateWeekdayScheduleDictInternal = {}
    for new_slot_no, (_, slot_data) in enumerate(sorted_slots, start=1):
        result[new_slot_no] = slot_data

    # Fill up missing slots (from N+1 to 13) with 24:00 entries
    if result:
        # Get the temperature from the last existing slot
        last_slot = result[len(result)]
        fill_temperature = last_slot.get("temperature", DEFAULT_CLIMATE_FILL_TEMPERATURE)

        # Fill missing slots
        for slot_no in range(len(result) + 1, 14):
            result[slot_no] = {
                "endtime": _CLIMATE_MAX_SCHEDULER_TIME,
                "temperature": fill_temperature,
            }

    return result
