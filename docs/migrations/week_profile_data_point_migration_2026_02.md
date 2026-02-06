# Migration Guide: WeekProfileDataPoint (Schedule Migration)

## Overview

In version 2026.2.6, schedule operations have been moved from climate custom data points
(`BaseCustomDpClimate`) to dedicated device-level data points (`WeekProfileDataPoint` /
`ClimateWeekProfileDataPoint`). This separation of concerns makes schedule data accessible
as a first-class data point on `device.week_profile_data_point`.

## Breaking Changes

### 1. Schedule methods removed from `BaseCustomDpClimate`

The following methods and properties are no longer available on climate custom data points:

**Properties removed:**

- `available_schedule_profiles` -> Use `device.week_profile_data_point.available_schedule_profiles`
- `schedule` -> Use `device.week_profile_data_point.schedule`

**Methods removed:**

- `get_schedule()` -> Use `device.week_profile_data_point.get_schedule()`
- `set_schedule()` -> Use `device.week_profile_data_point.set_schedule()`
- `get_schedule_profile()` -> Use `device.week_profile_data_point.get_schedule_profile()`
- `set_schedule_profile()` -> Use `device.week_profile_data_point.set_schedule_profile()`
- `get_schedule_weekday()` -> Use `device.week_profile_data_point.get_schedule_weekday()`
- `set_schedule_weekday()` -> Use `device.week_profile_data_point.set_schedule_weekday()`
- `copy_schedule()` -> Use `device.week_profile_data_point.copy_schedule()`
- `copy_schedule_profile()` -> Use `device.week_profile_data_point.copy_schedule_profile()`

### 2. Schedule methods removed from `CustomDataPointProtocol`

The following methods and properties are no longer part of the `CustomDataPointProtocol`:

- `has_schedule` (property)
- `schedule` (property)
- `get_schedule()`
- `set_schedule()`

### 3. Copy method parameter rename

The `copy_schedule` and `copy_schedule_profile` methods now accept `target_data_point`
(a `ClimateWeekProfileDataPointProtocol`) instead of `target_climate_data_point`
(a `BaseCustomDpClimate`).

## Migration Steps

### Step 1: Access schedule via `device.week_profile_data_point`

**Before:**

```python
climate_dp: BaseCustomDpClimate = ...
schedule = climate_dp.schedule
await climate_dp.get_schedule(force_load=True)
await climate_dp.set_schedule(schedule_data=data)
```

**After:**

```python
climate_dp: BaseCustomDpClimate = ...
wp_dp = climate_dp.device.week_profile_data_point
# wp_dp is typed as WeekProfileDataPointProtocol | None
if wp_dp is not None:
    schedule = wp_dp.schedule
    await wp_dp.get_schedule(force_load=True)
    await wp_dp.set_schedule(schedule_data=data)
```

### Step 2: Access climate-specific operations via cast

For climate-specific operations (profile/weekday level), cast to the climate protocol:

```python
from aiohomematic.interfaces import ClimateWeekProfileDataPointProtocol

wp_dp = climate_dp.device.week_profile_data_point
if isinstance(wp_dp, ClimateWeekProfileDataPointProtocol):
    profiles = wp_dp.available_schedule_profiles
    await wp_dp.get_schedule_profile(profile=profile, force_load=True)
    await wp_dp.set_schedule_weekday(
        profile=profile, weekday=weekday, weekday_data=data
    )
```

### Step 3: Update copy operations

**Before:**

```python
await climate_dp.copy_schedule(target_climate_data_point=other_climate_dp)
await climate_dp.copy_schedule_profile(
    source_profile=p1,
    target_profile=p2,
    target_climate_data_point=other_climate_dp,
)
```

**After:**

```python
wp_dp = climate_dp.device.week_profile_data_point
other_wp_dp = other_climate_dp.device.week_profile_data_point
if isinstance(wp_dp, ClimateWeekProfileDataPointProtocol):
    await wp_dp.copy_schedule(target_data_point=other_wp_dp)
    await wp_dp.copy_schedule_profile(
        source_profile=p1,
        target_profile=p2,
        target_data_point=other_wp_dp,
    )
```

### Step 4: Update `has_schedule` checks

**Before:**

```python
if custom_dp.has_schedule:
    schedule = custom_dp.schedule
```

**After:**

```python
if device.week_profile_data_point is not None:
    schedule = device.week_profile_data_point.schedule
```

## Search-and-Replace Patterns

| Old Pattern                              | New Pattern                                                  |
| ---------------------------------------- | ------------------------------------------------------------ |
| `climate_dp.schedule`                    | `device.week_profile_data_point.schedule`                    |
| `climate_dp.get_schedule(`               | `device.week_profile_data_point.get_schedule(`               |
| `climate_dp.set_schedule(`               | `device.week_profile_data_point.set_schedule(`               |
| `climate_dp.get_schedule_profile(`       | `device.week_profile_data_point.get_schedule_profile(`       |
| `climate_dp.set_schedule_profile(`       | `device.week_profile_data_point.set_schedule_profile(`       |
| `climate_dp.get_schedule_weekday(`       | `device.week_profile_data_point.get_schedule_weekday(`       |
| `climate_dp.set_schedule_weekday(`       | `device.week_profile_data_point.set_schedule_weekday(`       |
| `climate_dp.copy_schedule(`              | `device.week_profile_data_point.copy_schedule(`              |
| `climate_dp.copy_schedule_profile(`      | `device.week_profile_data_point.copy_schedule_profile(`      |
| `climate_dp.available_schedule_profiles` | `device.week_profile_data_point.available_schedule_profiles` |
| `target_climate_data_point=`             | `target_data_point=`                                         |
| `custom_dp.has_schedule`                 | `device.week_profile_data_point is not None`                 |

## Compatibility Notes

- `device.week_profile_data_point` may be `None` for devices without schedule support.
  Always check for `None` before accessing schedule operations.
- `ClimateWeekProfileDataPoint` inherits from `WeekProfileDataPoint`, so all base
  schedule operations (`get_schedule`, `set_schedule`, etc.) are available on both types.
- Non-climate devices (e.g., switches with `WEEK_PROFILE` channels) use
  `WeekProfileDataPoint` (not the climate subclass).
- The `schedule_profile_nos` property remains on `CustomDpRfThermostat` (for internal
  use) but is also available on `ClimateWeekProfileDataPoint`.
