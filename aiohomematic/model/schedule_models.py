# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Pydantic models for human-readable device schedules.

This module provides validated, human-readable schedule formats for non-climate devices
(switches, lights, covers, valves). The models use Pydantic for automatic validation
with clear error messages.

The schedule system converts between:
- **Raw format**: CCU paramset values (e.g., `{"01_WP_WEEKDAY": 127, "01_WP_FIXED_HOUR": 7}`)
- **Simple format**: Human-readable Pydantic models (e.g., `{"weekdays": ["MONDAY"], "time": "07:30"}`)

Example:
```python
from aiohomematic.model.schedule_models import SimpleScheduleEntry, SimpleSchedule

# Create a validated schedule entry
entry = SimpleScheduleEntry(
    weekdays=["MONDAY", "TUESDAY"],
    time="07:30",
    target_channels=["1_1"],
    level=1.0,
    duration="10s",
)

# Validation errors are raised automatically
entry = SimpleScheduleEntry(
    weekdays=["INVALID"],  # ValidationError: Invalid weekday
    time="25:00",          # ValidationError: Invalid time format
    level=1.5,             # ValidationError: Level must be <= 1.0
)
```

"""

from __future__ import annotations

import re
from typing import Annotated, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aiohomematic import i18n
from aiohomematic.const import AstroType, ScheduleActorChannel, ScheduleCondition, ScheduleField, TimeBase, WeekdayInt

__all__ = [
    "SimpleSchedule",
    "SimpleScheduleEntry",
]

# Valid weekday literals for validation
WeekdayLiteral = Literal["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]

# Valid condition literals
ConditionLiteral = Literal[
    "fixed_time",
    "astro",
    "fixed_if_before_astro",
    "astro_if_before_fixed",
    "fixed_if_after_astro",
    "astro_if_after_fixed",
    "earliest",
    "latest",
]

# Valid astro type literals
AstroTypeLiteral = Literal["sunrise", "sunset"]

# Mapping from string to enum for conditions
_CONDITION_STR_TO_ENUM: Final[dict[str, ScheduleCondition]] = {
    "fixed_time": ScheduleCondition.FIXED_TIME,
    "astro": ScheduleCondition.ASTRO,
    "fixed_if_before_astro": ScheduleCondition.FIXED_IF_BEFORE_ASTRO,
    "astro_if_before_fixed": ScheduleCondition.ASTRO_IF_BEFORE_FIXED,
    "fixed_if_after_astro": ScheduleCondition.FIXED_IF_AFTER_ASTRO,
    "astro_if_after_fixed": ScheduleCondition.ASTRO_IF_AFTER_FIXED,
    "earliest": ScheduleCondition.EARLIEST_OF_FIXED_AND_ASTRO,
    "latest": ScheduleCondition.LATEST_OF_FIXED_AND_ASTRO,
}

_CONDITION_ENUM_TO_STR: Final[dict[ScheduleCondition, str]] = {v: k for k, v in _CONDITION_STR_TO_ENUM.items()}

# Mapping from string to enum for astro types
_ASTRO_STR_TO_ENUM: Final[dict[str, AstroType]] = {
    "sunrise": AstroType.SUNRISE,
    "sunset": AstroType.SUNSET,
}

_ASTRO_ENUM_TO_STR: Final[dict[AstroType, str]] = {v: k for k, v in _ASTRO_STR_TO_ENUM.items()}

# Mapping from string to enum for weekdays
_WEEKDAY_STR_TO_INT: Final[dict[str, WeekdayInt]] = {
    "SUNDAY": WeekdayInt.SUNDAY,
    "MONDAY": WeekdayInt.MONDAY,
    "TUESDAY": WeekdayInt.TUESDAY,
    "WEDNESDAY": WeekdayInt.WEDNESDAY,
    "THURSDAY": WeekdayInt.THURSDAY,
    "FRIDAY": WeekdayInt.FRIDAY,
    "SATURDAY": WeekdayInt.SATURDAY,
}

_WEEKDAY_INT_TO_STR: Final[dict[WeekdayInt, str]] = {v: k for k, v in _WEEKDAY_STR_TO_INT.items()}

# Channel pattern: X_Y where X=1-8, Y=1-3
_CHANNEL_PATTERN: Final = re.compile(r"^[1-8]_[1-3]$")

# Time pattern: HH:MM (00:00 - 23:59)
_TIME_PATTERN: Final = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")

# Duration pattern: number + unit (ms, s, min, h)
_DURATION_PATTERN: Final = re.compile(r"^(\d+)\s*(ms|s|min|h)$")

# Channel string to enum mapping
_CHANNEL_STR_TO_ENUM: Final[dict[str, ScheduleActorChannel]] = {
    "1_1": ScheduleActorChannel.CHANNEL_1_1,
    "1_2": ScheduleActorChannel.CHANNEL_1_2,
    "1_3": ScheduleActorChannel.CHANNEL_1_3,
    "2_1": ScheduleActorChannel.CHANNEL_2_1,
    "2_2": ScheduleActorChannel.CHANNEL_2_2,
    "2_3": ScheduleActorChannel.CHANNEL_2_3,
    "3_1": ScheduleActorChannel.CHANNEL_3_1,
    "3_2": ScheduleActorChannel.CHANNEL_3_2,
    "3_3": ScheduleActorChannel.CHANNEL_3_3,
    "4_1": ScheduleActorChannel.CHANNEL_4_1,
    "4_2": ScheduleActorChannel.CHANNEL_4_2,
    "4_3": ScheduleActorChannel.CHANNEL_4_3,
    "5_1": ScheduleActorChannel.CHANNEL_5_1,
    "5_2": ScheduleActorChannel.CHANNEL_5_2,
    "5_3": ScheduleActorChannel.CHANNEL_5_3,
    "6_1": ScheduleActorChannel.CHANNEL_6_1,
    "6_2": ScheduleActorChannel.CHANNEL_6_2,
    "6_3": ScheduleActorChannel.CHANNEL_6_3,
    "7_1": ScheduleActorChannel.CHANNEL_7_1,
    "7_2": ScheduleActorChannel.CHANNEL_7_2,
    "7_3": ScheduleActorChannel.CHANNEL_7_3,
    "8_1": ScheduleActorChannel.CHANNEL_8_1,
    "8_2": ScheduleActorChannel.CHANNEL_8_2,
    "8_3": ScheduleActorChannel.CHANNEL_8_3,
}

_CHANNEL_ENUM_TO_STR: Final[dict[ScheduleActorChannel, str]] = {v: k for k, v in _CHANNEL_STR_TO_ENUM.items()}


class SimpleScheduleEntry(BaseModel):
    """
    Human-readable schedule entry with automatic validation.

    This model represents a single schedule slot for non-climate devices (switches,
    lights, covers, valves). All fields use human-readable formats instead of
    raw CCU values.

    Attributes:
        weekdays: Days when the schedule triggers (e.g., ["MONDAY", "TUESDAY"])
        time: Trigger time in HH:MM format (e.g., "07:30")
        condition: Trigger condition type (default: "fixed_time")
        astro_type: Astro event type ("sunrise" or "sunset"), required for astro conditions
        astro_offset_minutes: Offset from astro event in minutes (-720 to 720)
        target_channels: Target actor channels (e.g., ["1_1", "2_1"])
        level: Output level 0.0-1.0 (0=off, 1=on for switches, dimmer level for lights)
        level_2: Secondary level for covers (slat position), optional
        duration: On-duration in human format (e.g., "10s", "5min"), optional
        ramp_time: Ramp time for dimmers (e.g., "500ms", "2s"), optional

    Example:
        >>> entry = SimpleScheduleEntry(
        ...     weekdays=["MONDAY", "FRIDAY"],
        ...     time="07:30",
        ...     target_channels=["1_1"],
        ...     level=1.0,
        ...     duration="10s",
        ... )

    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    # When to trigger
    weekdays: Annotated[
        list[WeekdayLiteral],
        Field(min_length=1, description="Days when schedule triggers"),
    ]
    time: Annotated[
        str,
        Field(description="Trigger time in HH:MM format (00:00 - 23:59)"),
    ]

    # Trigger condition
    condition: Annotated[
        ConditionLiteral,
        Field(default="fixed_time", description="Trigger condition type"),
    ]
    astro_type: Annotated[
        AstroTypeLiteral | None,
        Field(default=None, description="Astro event type (sunrise/sunset)"),
    ]
    astro_offset_minutes: Annotated[
        int,
        Field(default=0, ge=-720, le=720, description="Offset from astro event in minutes"),
    ]

    # What to control
    target_channels: Annotated[
        list[str],
        Field(min_length=1, description="Target channels like '1_1', '2_1'"),
    ]
    level: Annotated[
        float,
        Field(ge=0.0, le=1.0, description="Output level 0.0-1.0"),
    ]

    # Optional category-specific fields
    level_2: Annotated[
        float | None,
        Field(default=None, ge=0.0, le=1.0, description="Secondary level for covers (slat position)"),
    ]
    duration: Annotated[
        str | None,
        Field(default=None, description="On-duration like '10s', '5min', '1h'"),
    ]
    ramp_time: Annotated[
        str | None,
        Field(default=None, description="Ramp time like '500ms', '2s'"),
    ]

    @field_validator("target_channels")
    @classmethod
    def validate_channels(cls, v: list[str]) -> list[str]:  # kwonly: disable
        """Validate channel format X_Y where X=1-8, Y=1-3."""
        for ch in v:
            if not _CHANNEL_PATTERN.match(ch):
                raise ValueError(i18n.tr(key="exception.model.schedule.invalid_channel_format", channel=ch))
        return v

    @field_validator("duration", "ramp_time")
    @classmethod
    def validate_duration_format(cls, v: str | None) -> str | None:  # kwonly: disable
        """Validate duration format like '10s', '5min', '1h'."""
        if v is None:
            return None
        if not _DURATION_PATTERN.match(v):
            raise ValueError(i18n.tr(key="exception.model.schedule.invalid_duration_format", duration=v))
        return v

    @field_validator("time")
    @classmethod
    def validate_time(cls, v: str) -> str:  # kwonly: disable
        """Validate time format HH:MM."""
        if not _TIME_PATTERN.match(v):
            raise ValueError(i18n.tr(key="exception.model.schedule.invalid_time_format", time=v))
        return v

    @model_validator(mode="after")
    def validate_astro_fields(self) -> SimpleScheduleEntry:
        """Ensure astro_type is set when condition uses astro."""
        if self.condition != "fixed_time" and self.astro_type is None:
            raise ValueError(i18n.tr(key="exception.model.schedule.astro_type_required", condition=self.condition))
        return self


class SimpleSchedule(BaseModel):
    """
    Complete schedule containing multiple entries.

    This model represents a complete device schedule with multiple time-based
    trigger entries. Each entry is identified by a group number (1-24).

    Attributes:
        entries: Dictionary mapping group numbers (1-24) to schedule entries

    Example:
        >>> schedule = SimpleSchedule(entries={
        ...     1: SimpleScheduleEntry(
        ...         weekdays=["MONDAY"],
        ...         time="07:00",
        ...         target_channels=["1_1"],
        ...         level=1.0,
        ...     ),
        ...     2: SimpleScheduleEntry(
        ...         weekdays=["MONDAY"],
        ...         time="22:00",
        ...         target_channels=["1_1"],
        ...         level=0.0,
        ...     ),
        ... })

    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    entries: Annotated[
        dict[int, SimpleScheduleEntry],
        Field(default_factory=dict, description="Schedule entries keyed by group number (1-24)"),
    ]

    @field_validator("entries")
    @classmethod
    def validate_entry_keys(  # kwonly: disable
        cls, v: dict[int, SimpleScheduleEntry]
    ) -> dict[int, SimpleScheduleEntry]:
        """Validate group numbers are in valid range 1-24."""
        for key in v:
            if not 1 <= key <= 24:
                raise ValueError(i18n.tr(key="exception.model.schedule.group_number_out_of_range", group=key))
        return v


# =============================================================================
# Conversion functions: Simple <-> Raw format
# =============================================================================


def convert_time_to_hour_minute(*, time_str: str) -> tuple[int, int]:
    """
    Convert time string to hour and minute integers.

    Args:
        time_str: Time in HH:MM format

    Returns:
        Tuple of (hour, minute)

    """
    if not (match := _TIME_PATTERN.match(time_str)):
        raise ValueError(i18n.tr(key="exception.model.schedule.invalid_time_format", time=time_str))
    return int(match.group(1)), int(match.group(2))


def convert_hour_minute_to_time(*, hour: int, minute: int) -> str:
    """
    Convert hour and minute to time string.

    Args:
        hour: Hour (0-23)
        minute: Minute (0-59)

    Returns:
        Time string in HH:MM format

    """
    return f"{hour:02d}:{minute:02d}"


def convert_duration_to_base_factor(*, duration_str: str) -> tuple[TimeBase, int]:
    """
    Convert human-readable duration to TimeBase enum and factor.

    Args:
        duration_str: Duration like "10s", "5min", "1h", "500ms"

    Returns:
        Tuple of (TimeBase, factor)

    Example:
        >>> convert_duration_to_base_factor(duration_str="10s")
        (TimeBase.SEC_1, 10)
        >>> convert_duration_to_base_factor(duration_str="5min")
        (TimeBase.MIN_1, 5)

    """
    if not (match := _DURATION_PATTERN.match(duration_str)):
        raise ValueError(i18n.tr(key="exception.model.schedule.invalid_duration_format", duration=duration_str))

    value = int(match.group(1))
    unit = match.group(2)

    # Map unit to appropriate TimeBase
    unit_to_base: dict[str, TimeBase] = {
        "ms": TimeBase.MS_100,
        "s": TimeBase.SEC_1,
        "min": TimeBase.MIN_1,
        "h": TimeBase.HOUR_1,
    }

    base = unit_to_base[unit]

    # For milliseconds, factor needs adjustment (base is 100ms)
    if unit == "ms":
        value = value // 100

    return base, value


def convert_base_factor_to_duration(*, base: TimeBase, factor: int) -> str:
    """
    Convert TimeBase enum and factor to human-readable duration.

    Args:
        base: TimeBase enum value
        factor: Multiplier for the base unit

    Returns:
        Duration string like "10s", "5min"

    """
    base_to_unit: dict[TimeBase, tuple[str, int]] = {
        TimeBase.MS_100: ("ms", 100),
        TimeBase.SEC_1: ("s", 1),
        TimeBase.SEC_5: ("s", 5),
        TimeBase.SEC_10: ("s", 10),
        TimeBase.MIN_1: ("min", 1),
        TimeBase.MIN_5: ("min", 5),
        TimeBase.MIN_10: ("min", 10),
        TimeBase.HOUR_1: ("h", 1),
    }

    unit, multiplier = base_to_unit.get(base, ("s", 1))
    total_value = factor * multiplier

    return f"{total_value}{unit}"


def convert_weekdays_to_list(*, weekday_enums: list[WeekdayInt]) -> list[str]:
    """Convert list of WeekdayInt enums to list of weekday strings."""
    return [_WEEKDAY_INT_TO_STR[w] for w in weekday_enums]


def convert_list_to_weekdays(*, weekday_strs: list[str]) -> list[WeekdayInt]:
    """Convert list of weekday strings to list of WeekdayInt enums."""
    return [_WEEKDAY_STR_TO_INT[w] for w in weekday_strs]


def convert_channels_to_list(*, channel_enums: list[ScheduleActorChannel]) -> list[str]:
    """Convert list of ScheduleActorChannel enums to list of channel strings."""
    return [_CHANNEL_ENUM_TO_STR[c] for c in channel_enums]


def convert_list_to_channels(*, channel_strs: list[str]) -> list[ScheduleActorChannel]:
    """Convert list of channel strings to list of ScheduleActorChannel enums."""
    return [_CHANNEL_STR_TO_ENUM[c] for c in channel_strs]


def convert_condition_to_str(*, condition: ScheduleCondition) -> str:
    """Convert ScheduleCondition enum to string."""
    return _CONDITION_ENUM_TO_STR.get(condition, "fixed_time")


def convert_str_to_condition(*, condition_str: str) -> ScheduleCondition:
    """Convert string to ScheduleCondition enum."""
    return _CONDITION_STR_TO_ENUM.get(condition_str, ScheduleCondition.FIXED_TIME)


def convert_astro_to_str(*, astro: AstroType) -> str:
    """Convert AstroType enum to string."""
    return _ASTRO_ENUM_TO_STR.get(astro, "sunrise")


def convert_str_to_astro(*, astro_str: str) -> AstroType:
    """Convert string to AstroType enum."""
    return _ASTRO_STR_TO_ENUM.get(astro_str, AstroType.SUNRISE)


def convert_raw_group_to_simple_entry(
    *,
    group_data: dict[ScheduleField, object],
) -> SimpleScheduleEntry:
    """
    Convert a raw schedule group to a SimpleScheduleEntry.

    Args:
        group_data: Raw schedule group data from CCU

    Returns:
        Validated SimpleScheduleEntry

    """
    # Extract weekdays - cast to WeekdayInt list for type safety
    weekday_enums_raw = group_data.get(ScheduleField.WEEKDAY, [])
    weekday_enums: list[WeekdayInt] = list(weekday_enums_raw) if isinstance(weekday_enums_raw, list) else []
    weekdays_str = convert_weekdays_to_list(weekday_enums=weekday_enums) if weekday_enums else ["MONDAY"]
    # Cast to literal type - values are validated by convert_weekdays_to_list
    weekdays = cast(list[WeekdayLiteral], weekdays_str)

    # Extract time
    hour_raw = group_data.get(ScheduleField.FIXED_HOUR, 0)
    minute_raw = group_data.get(ScheduleField.FIXED_MINUTE, 0)
    hour = int(hour_raw) if isinstance(hour_raw, (int, float)) else 0
    minute = int(minute_raw) if isinstance(minute_raw, (int, float)) else 0
    time_str = convert_hour_minute_to_time(hour=hour, minute=minute)

    # Extract condition
    condition_enum_raw = group_data.get(ScheduleField.CONDITION, ScheduleCondition.FIXED_TIME)
    if isinstance(condition_enum_raw, int):
        condition_enum = ScheduleCondition(condition_enum_raw)
    elif isinstance(condition_enum_raw, ScheduleCondition):
        condition_enum = condition_enum_raw
    else:
        condition_enum = ScheduleCondition.FIXED_TIME
    condition_str = convert_condition_to_str(condition=condition_enum)
    # Cast to literal type - value is validated by convert_condition_to_str
    condition = cast(ConditionLiteral, condition_str)

    # Extract astro type
    astro_enum_raw = group_data.get(ScheduleField.ASTRO_TYPE, AstroType.SUNRISE)
    if isinstance(astro_enum_raw, int):
        astro_enum = AstroType(astro_enum_raw)
    elif isinstance(astro_enum_raw, AstroType):
        astro_enum = astro_enum_raw
    else:
        astro_enum = AstroType.SUNRISE
    astro_type: AstroTypeLiteral | None = (
        cast(AstroTypeLiteral, convert_astro_to_str(astro=astro_enum)) if condition != "fixed_time" else None
    )

    # Extract astro offset
    astro_offset_raw = group_data.get(ScheduleField.ASTRO_OFFSET, 0)
    astro_offset = int(astro_offset_raw) if isinstance(astro_offset_raw, (int, float)) else 0

    # Extract target channels - cast to ScheduleActorChannel list for type safety
    channel_enums_raw = group_data.get(ScheduleField.TARGET_CHANNELS, [])
    channel_enums: list[ScheduleActorChannel] = list(channel_enums_raw) if isinstance(channel_enums_raw, list) else []
    target_channels = convert_channels_to_list(channel_enums=channel_enums) if channel_enums else ["1_1"]

    # Extract level
    level_raw = group_data.get(ScheduleField.LEVEL, 0)
    level = float(level_raw) if isinstance(level_raw, (int, float)) else 0.0
    # Clamp to valid range
    level = max(0.0, min(1.0, level))

    # Extract optional level_2 (for covers)
    level_2_raw = group_data.get(ScheduleField.LEVEL_2)
    level_2 = float(level_2_raw) if isinstance(level_2_raw, (int, float)) else None

    # Extract optional duration
    duration: str | None = None
    duration_base_raw = group_data.get(ScheduleField.DURATION_BASE)
    duration_factor_raw = group_data.get(ScheduleField.DURATION_FACTOR)
    if duration_base_raw is not None and isinstance(duration_factor_raw, (int, float)):
        if isinstance(duration_base_raw, int):
            duration_base = TimeBase(duration_base_raw)
        elif isinstance(duration_base_raw, TimeBase):
            duration_base = duration_base_raw
        else:
            duration_base = TimeBase.MS_100
        duration = convert_base_factor_to_duration(base=duration_base, factor=int(duration_factor_raw))

    # Extract optional ramp_time
    ramp_time: str | None = None
    ramp_base_raw = group_data.get(ScheduleField.RAMP_TIME_BASE)
    ramp_factor_raw = group_data.get(ScheduleField.RAMP_TIME_FACTOR)
    if ramp_base_raw is not None and isinstance(ramp_factor_raw, (int, float)):
        if isinstance(ramp_base_raw, int):
            ramp_base = TimeBase(ramp_base_raw)
        elif isinstance(ramp_base_raw, TimeBase):
            ramp_base = ramp_base_raw
        else:
            ramp_base = TimeBase.MS_100
        ramp_time = convert_base_factor_to_duration(base=ramp_base, factor=int(ramp_factor_raw))

    return SimpleScheduleEntry(
        weekdays=weekdays,
        time=time_str,
        condition=condition,
        astro_type=astro_type,
        astro_offset_minutes=astro_offset,
        target_channels=target_channels,
        level=level,
        level_2=level_2,
        duration=duration,
        ramp_time=ramp_time,
    )


def convert_simple_entry_to_raw_group(
    *,
    entry: SimpleScheduleEntry,
) -> dict[ScheduleField, object]:
    """
    Convert a SimpleScheduleEntry to raw schedule group format.

    Args:
        entry: Validated SimpleScheduleEntry

    Returns:
        Raw schedule group data for CCU

    """
    # Convert weekdays
    weekday_enums = convert_list_to_weekdays(weekday_strs=list(entry.weekdays))

    # Convert time
    hour, minute = convert_time_to_hour_minute(time_str=entry.time)

    # Convert condition
    condition_enum = convert_str_to_condition(condition_str=entry.condition)

    # Convert astro type
    astro_enum = convert_str_to_astro(astro_str=entry.astro_type) if entry.astro_type else AstroType.SUNRISE

    # Convert target channels
    channel_enums = convert_list_to_channels(channel_strs=entry.target_channels)

    # Build raw group
    raw_group: dict[ScheduleField, object] = {
        ScheduleField.WEEKDAY: weekday_enums,
        ScheduleField.FIXED_HOUR: hour,
        ScheduleField.FIXED_MINUTE: minute,
        ScheduleField.CONDITION: condition_enum,
        ScheduleField.ASTRO_TYPE: astro_enum,
        ScheduleField.ASTRO_OFFSET: entry.astro_offset_minutes,
        ScheduleField.TARGET_CHANNELS: channel_enums,
        ScheduleField.LEVEL: entry.level,
    }

    # Add optional fields
    if entry.level_2 is not None:
        raw_group[ScheduleField.LEVEL_2] = entry.level_2

    if entry.duration is not None:
        base, factor = convert_duration_to_base_factor(duration_str=entry.duration)
        raw_group[ScheduleField.DURATION_BASE] = base
        raw_group[ScheduleField.DURATION_FACTOR] = factor

    if entry.ramp_time is not None:
        base, factor = convert_duration_to_base_factor(duration_str=entry.ramp_time)
        raw_group[ScheduleField.RAMP_TIME_BASE] = base
        raw_group[ScheduleField.RAMP_TIME_FACTOR] = factor

    return raw_group
