# Migration Guide: Simple Schedule TypedDict Format

**Date**: December 2025
**Version**: 2025.12+
**Breaking Change**: Yes

## Overview

The simple schedule data structures used by climate thermostats have been completely refactored to use **TypedDict-based structures with lowercase string keys** instead of the legacy **tuple-based format with ScheduleSlotType enum keys**.

This change provides:

- ✅ Full JSON serialization support (enabling Home Assistant custom cards)
- ✅ Better type safety with TypedDict
- ✅ Cleaner, more intuitive API
- ✅ Reduced memory overhead (no enum objects)

## Breaking Changes

### 1. Simple Weekday Schedule Format

**Old Format (Legacy)**:

```python
# Tuple format with enum keys
simple_weekday = (
    18.0,  # base_temperature
    [
        {
            ScheduleSlotType.STARTTIME: "06:00",
            ScheduleSlotType.ENDTIME: "08:00",
            ScheduleSlotType.TEMPERATURE: 21.0,
        },
        {
            ScheduleSlotType.STARTTIME: "17:00",
            ScheduleSlotType.ENDTIME: "22:00",
            ScheduleSlotType.TEMPERATURE: 20.0,
        },
    ]
)
```

**New Format (TypedDict)**:

```python
# Dictionary format with string keys
simple_weekday = {
    "base_temperature": 18.0,
    "periods": [
        {
            "starttime": "06:00",
            "endtime": "08:00",
            "temperature": 21.0,
        },
        {
            "starttime": "17:00",
            "endtime": "22:00",
            "temperature": 20.0,
        },
    ]
}
```

### 2. Type Definitions

**Old Type Aliases**:

```python
# Removed
CLIMATE_SIMPLE_WEEKDAY_LIST = list
CLIMATE_SIMPLE_WEEKDAY_DATA = tuple[float, CLIMATE_SIMPLE_WEEKDAY_LIST]
CLIMATE_SIMPLE_PROFILE_DICT = dict[WeekdayStr, CLIMATE_SIMPLE_WEEKDAY_DATA]
CLIMATE_SIMPLE_SCHEDULE_DICT = dict[ScheduleProfile, CLIMATE_SIMPLE_PROFILE_DICT]
```

**New Type Definitions**:

```python
# New TypedDict classes
class SimpleSchedulePeriod(TypedDict):
    starttime: str
    endtime: str
    temperature: float

class SimpleWeekdaySchedule(TypedDict):
    base_temperature: float
    periods: list[SimpleSchedulePeriod]

# Type aliases
SimpleProfileSchedule = dict[WeekdayStr, SimpleWeekdaySchedule]
SimpleScheduleDict = dict[ScheduleProfile, SimpleProfileSchedule]
```

### 3. Accessing Schedule Data

**Old Access Pattern**:

```python
# Tuple unpacking
base_temperature, periods = simple_weekday
for period in periods:
    start = period[ScheduleSlotType.STARTTIME]
    end = period[ScheduleSlotType.ENDTIME]
    temp = period[ScheduleSlotType.TEMPERATURE]

# Profile access
profile_schedule = schedule_dict[ScheduleProfile.P1][WeekdayStr.MONDAY]
base_temp, _ = profile_schedule  # Tuple unpacking
```

**New Access Pattern**:

```python
# Dictionary access
base_temperature = simple_weekday["base_temperature"]
for period in simple_weekday["periods"]:
    start = period["starttime"]
    end = period["endtime"]
    temp = period["temperature"]

# Profile access
profile_schedule = schedule_dict[ScheduleProfile.P1][WeekdayStr.MONDAY]
base_temp = profile_schedule["base_temperature"]
periods = profile_schedule["periods"]
```

### 4. Climate Device API Changes

**ClimateWeekProfile Method Signatures**:

```python
# Old
async def get_schedule_simple_weekday(
    self, *, profile: ScheduleProfile, weekday: WeekdayStr
) -> tuple[float, list[dict[str, Any]]]:
    ...

# New
async def get_schedule_simple_weekday(
    self, *, profile: ScheduleProfile, weekday: WeekdayStr
) -> SimpleWeekdaySchedule:
    ...
```

**CustomDpClimate Method Signatures**:

```python
# Old
async def set_simple_schedule_weekday(
    self,
    *,
    profile: ScheduleProfile,
    weekday: WeekdayStr,
    simple_weekday_data: tuple[float, list[dict[str, Any]]],
) -> None:
    ...

# New
async def set_simple_schedule_weekday(
    self,
    *,
    profile: ScheduleProfile,
    weekday: WeekdayStr,
    simple_weekday_data: SimpleWeekdaySchedule,
) -> None:
    ...
```

## Migration Steps for Downstream Projects

### Step 1: Update Type Imports

```python
# Old
from aiohomematic.const import (
    CLIMATE_SIMPLE_SCHEDULE_DICT,
    CLIMATE_SIMPLE_WEEKDAY_DATA,
)

# New
from aiohomematic.const import (
    SimpleScheduleDict,
    SimpleWeekdaySchedule,
    SimpleSchedulePeriod,
    SimpleProfileSchedule,
)
```

### Step 2: Update Data Structure Creation

**Before**:

```python
simple_schedule = (
    18.0,
    [
        {
            ScheduleSlotType.STARTTIME: "06:00",
            ScheduleSlotType.ENDTIME: "10:00",
            ScheduleSlotType.TEMPERATURE: 21.0,
        }
    ]
)
```

**After**:

```python
simple_schedule = {
    "base_temperature": 18.0,
    "periods": [
        {
            "starttime": "06:00",
            "endtime": "10:00",
            "temperature": 21.0,
        }
    ]
}
```

### Step 3: Update Data Access Patterns

**Before**:

```python
# Tuple unpacking
base_temp, period_list = simple_schedule
for period in period_list:
    print(period[ScheduleSlotType.STARTTIME])
```

**After**:

```python
# Dictionary access
base_temp = simple_schedule["base_temperature"]
for period in simple_schedule["periods"]:
    print(period["starttime"])
```

### Step 4: Update Method Calls

**Before**:

```python
await climate.set_simple_schedule_weekday(
    profile=ScheduleProfile.P1,
    weekday=WeekdayStr.MONDAY,
    simple_weekday_data=(18.0, [period_data])
)
```

**After**:

```python
await climate.set_simple_schedule_weekday(
    profile=ScheduleProfile.P1,
    weekday=WeekdayStr.MONDAY,
    simple_weekday_data={
        "base_temperature": 18.0,
        "periods": [period_data]
    }
)
```

### Step 5: Update Assertions and Tests

**Before**:

```python
assert len(schedule[1]) == 2  # Tuple index
assert schedule[0] == 18.0    # First element
```

**After**:

```python
assert len(schedule["periods"]) == 2  # Dictionary access
assert schedule["base_temperature"] == 18.0
```

## JSON Serialization

A key benefit of this migration is JSON compatibility:

```python
import json
from aiohomematic.const import SimpleWeekdaySchedule

schedule: SimpleWeekdaySchedule = {
    "base_temperature": 18.0,
    "periods": [
        {"starttime": "06:00", "endtime": "10:00", "temperature": 21.0},
        {"starttime": "17:00", "endtime": "22:00", "temperature": 20.0},
    ]
}

# Can now be directly serialized to JSON
json_str = json.dumps(schedule)
# Output: {"base_temperature": 18.0, "periods": [...]}

# And deserialized back
restored = json.loads(json_str)
```

## Search and Replace Patterns

For automated migration of large codebases:

### Replace Enum Keys

```bash
# In strings/dict literals
sed -i 's/ScheduleSlotType\.STARTTIME/"starttime"/g' files
sed -i 's/ScheduleSlotType\.ENDTIME/"endtime"/g' files
sed -i 's/ScheduleSlotType\.TEMPERATURE/"temperature"/g' files
```

### Fix Tuple Unpacking

```bash
# pattern:  base, periods = schedule
# replace:  base = schedule["base_temperature"]; periods = schedule["periods"]
```

### Fix Type References

```bash
# CLIMATE_SIMPLE_WEEKDAY_DATA -> SimpleWeekdaySchedule
# CLIMATE_SIMPLE_SCHEDULE_DICT -> SimpleScheduleDict
# CLIMATE_SIMPLE_PROFILE_DICT -> SimpleProfileSchedule
```

## Compatibility Notes

### No Backward Compatibility

This is a **breaking change** with **no deprecation period**. The old tuple-based format is completely removed.

### Clean Slate Approach

- All old type aliases have been removed
- No conversion utilities provided
- Projects must update to the new format directly

### Benefits of Complete Refactoring

- No legacy code in library
- Simpler codebase maintenance
- Full type safety with TypedDict
- JSON serialization support

## Normal Schedule Type Aliases Renamed

In addition to the Simple Schedule TypedDict migration, the normal schedule type aliases have also been renamed for consistency:

### Type Alias Changes

**Old Names** (UPPER_SNAKE_CASE):

```python
from aiohomematic.const import (
    CLIMATE_WEEKDAY_DICT,    # dict[int, ScheduleSlot]
    CLIMATE_PROFILE_DICT,    # dict[WeekdayStr, CLIMATE_WEEKDAY_DICT]
    CLIMATE_SCHEDULE_DICT,   # dict[ScheduleProfile, CLIMATE_PROFILE_DICT]
)
```

**New Names** (PascalCase):

```python
from aiohomematic.const import (
    ClimateWeekdaySchedule,  # dict[int, ScheduleSlot]
    ClimateProfileSchedule,  # dict[WeekdayStr, ClimateWeekdaySchedule]
    ClimateScheduleDict,     # dict[ScheduleProfile, ClimateProfileSchedule]
)
```

### New ScheduleSlot TypedDict

A new `ScheduleSlot` TypedDict was added for type-safe slot definitions:

```python
from aiohomematic.const import ScheduleSlot

# Type definition
class ScheduleSlot(TypedDict):
    endtime: str       # "HH:MM" format (e.g., "06:00", "24:00")
    temperature: float # Target temperature in Celsius

# Example usage
slot: ScheduleSlot = {"endtime": "06:00", "temperature": 18.0}
```

### Migration Steps

**Update imports**:

```python
# Old
from aiohomematic.const import CLIMATE_SCHEDULE_DICT

# New
from aiohomematic.const import ClimateScheduleDict, ScheduleSlot
```

**Update type annotations**:

```python
# Old
def process_schedule(schedule: CLIMATE_SCHEDULE_DICT) -> None: ...

# New
def process_schedule(schedule: ClimateScheduleDict) -> None: ...
```

## Related Changes

- **const.py**: New TypedDict classes (SimpleSchedulePeriod, SimpleWeekdaySchedule, ScheduleSlot), renamed type aliases
- **week_profile.py**: Updated conversion methods use string keys and new type names
- **climate.py**: Updated method signatures use new types
- **Tests**: All test data migrated to new format

## Questions and Support

For questions or issues regarding this migration:

1. Check the examples in the docs directory
2. Review updated test cases in `tests/test_model_week_profile.py`
3. Reference the type definitions in `aiohomematic/const.py`
4. Open an issue on GitHub with migration questions
