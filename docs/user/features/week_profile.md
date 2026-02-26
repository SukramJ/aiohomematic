# Week Profile / Schedule Management

This guide explains how to manage heating schedules (week profiles) and device schedules in Home Assistant using the Homematic(IP) Local integration.

## Overview

Homematic devices with week profile support expose a **Week Profile sensor** entity that shows the number of active schedule entries and provides schedule metadata as attributes.

All schedule services are **device-based** — they target a device by `device_id` or `device_address`, not by entity.

### Climate Devices

Homematic thermostats support up to **6 schedule profiles** (P1-P6), each containing a weekly schedule with individual settings for each day.

| Feature      | Description                                                    |
| ------------ | -------------------------------------------------------------- |
| **Profiles** | P1 through P6 (6 independent schedules)                        |
| **Days**     | MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY, SATURDAY, SUNDAY |
| **Format**   | Simple format with base temperature and heating periods        |

### Non-Climate Devices (Switch, Light, Cover, Valve)

Devices with week profile capability support a single schedule with up to 24 entries.

| Feature     | Description                                       |
| ----------- | ------------------------------------------------- |
| **Entries** | Up to 24 schedule entries                         |
| **Format**  | Generic schedule_data dict with time/level/target |

### Week Profile Sensor Value

The **Week Profile sensor** entity exposes a numeric `value` (integer) that represents the **total number of active schedule entries** configured on the device. This gives a quick indication of whether a schedule is configured and how comprehensive it is.

How the value is computed depends on the device type:

| Device Type  | Counting Logic                                                                                               |
| ------------ | ------------------------------------------------------------------------------------------------------------ |
| **Climate**  | Sum of all temperature periods across all profiles and weekdays (e.g. 2 periods × 7 days × 1 profile = 14)  |
| **Non-Climate** | Number of schedule entries that have at least one target channel assigned                                  |

**Examples:**

- A thermostat with **1 active profile** and **2 heating periods per day** → value = **14** (2 × 7 days)
- A thermostat with **no schedule configured** → value = **0**
- A switch with **3 schedule entries** (each targeting a channel) → value = **3**

This value is useful for:

- **Quick status check**: Value `0` means no schedule is configured.
- **Automations**: Trigger actions based on whether a schedule exists (value > 0) or has changed.

---

## Device Identification

All schedule services accept either `device_id` or `device_address` to identify the device:

```yaml
# Option 1: By device_id (from HA device registry)
data:
  device_id: abcdefg...

# Option 2: By device_address (Homematic address)
data:
  device_address: "001F58A9876543"
```

---

## Climate Schedule Format

The simple format is designed for easy schedule management. Instead of defining every time slot, you specify:

1. **Base Temperature** - The default temperature when no heating period is active
2. **Periods** - Only the times when you want a _different_ temperature

### Structure

```yaml
base_temperature: 17.0
periods:
  - starttime: "06:00"
    endtime: "08:00"
    temperature: 21.0
  - starttime: "17:00"
    endtime: "22:00"
    temperature: 21.0
```

### How It Works

The system automatically fills gaps with the base temperature:

| Time          | Temperature | Source                        |
| ------------- | ----------- | ----------------------------- |
| 00:00 - 06:00 | 17.0°C      | base_temperature              |
| 06:00 - 08:00 | 21.0°C      | period 1                      |
| 08:00 - 17:00 | 17.0°C      | base_temperature (gap filled) |
| 17:00 - 22:00 | 21.0°C      | period 2                      |
| 22:00 - 24:00 | 17.0°C      | base_temperature              |

---

## Climate Schedule Actions

### Set Complete Profile

Set the schedule for all weekdays of a profile:

```yaml
action: homematicip_local.set_schedule_profile
data:
  device_id: abcdefg...
  profile: P1
  simple_profile_data:
    MONDAY:
      base_temperature: 17.0
      periods:
        - starttime: "06:00"
          endtime: "08:00"
          temperature: 21.0
        - starttime: "17:00"
          endtime: "22:00"
          temperature: 21.0
    TUESDAY:
      base_temperature: 17.0
      periods:
        - starttime: "06:00"
          endtime: "08:00"
          temperature: 21.0
        - starttime: "17:00"
          endtime: "22:00"
          temperature: 21.0
    # ... add other weekdays
```

### Set Single Weekday

Set the schedule for one specific day:

```yaml
action: homematicip_local.set_schedule_weekday
data:
  device_id: abcdefg...
  profile: P1
  weekday: MONDAY
  base_temperature: 17.0
  simple_weekday_list:
    - starttime: "06:00"
      endtime: "08:00"
      temperature: 21.0
    - starttime: "17:00"
      endtime: "22:00"
      temperature: 21.0
```

### Read Schedule

Get the current schedule:

```yaml
# Get complete schedule (all profiles)
action: homematicip_local.get_schedule
data:
  device_id: abcdefg...

# Get single profile
action: homematicip_local.get_schedule_profile
data:
  device_id: abcdefg...
  profile: P1

# Get single weekday
action: homematicip_local.get_schedule_weekday
data:
  device_id: abcdefg...
  profile: P1
  weekday: MONDAY
```

### Copy Schedules

Copy schedules between devices or profiles:

```yaml
# Copy complete schedule (all profiles) from source to target device
action: homematicip_local.copy_schedule
data:
  device_id: abcdefg...
  target_device_id: hijklmn...

# Copy single profile (within same device or to another)
action: homematicip_local.copy_schedule_profile
data:
  device_id: abcdefg...
  source_profile: P1
  target_profile: P2
  target_device_id: hijklmn...  # Optional: omit if copying within same device
```

---

## Non-Climate Schedule Actions

Non-climate devices (switch, light, cover, valve) use the unified `get_schedule` and `set_schedule` services.

### Set Schedule

Set a week schedule for devices that support scheduling:

```yaml
action: homematicip_local.set_schedule
data:
  device_id: abcdefg...
  schedule_data:
    "1": # Entry 1
      weekdays:
        - SUNDAY
        - MONDAY
        - TUESDAY
        - WEDNESDAY
        - THURSDAY
        - FRIDAY
      time: "06:00"
      condition: fixed_time
      target_channels:
        - "1_1"
      level: 0.5 # 50% brightness
      duration: 1min
      ramp_time: 10s
    "2": # Entry 2
      weekdays:
        - SATURDAY
      time: "08:00"
      condition: fixed_time
      target_channels:
        - "1_1"
      level: 0.3 # 30% brightness
      duration: 1min
      ramp_time: 10s
```

### Get Schedule

Get the current week schedule from a device:

```yaml
action: homematicip_local.get_schedule
data:
  device_id: abcdefg...
response_variable: current_schedule
```

The service returns the schedule data in the same format as used by the set_schedule service:

```yaml
# Response example stored in current_schedule
{
  "1":
    {
      "weekdays":
        ["SUNDAY", "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"],
      "time": "06:00",
      "condition": "fixed_time",
      "astro_type": null,
      "astro_offset_minutes": 0,
      "target_channels": ["1_1"],
      "level": 0.5,
      "level_2": null,
      "duration": "1min",
      "ramp_time": "10s",
    },
  "2":
    {
      "weekdays": ["SATURDAY"],
      "time": "08:00",
      "condition": "fixed_time",
      "astro_type": null,
      "astro_offset_minutes": 0,
      "target_channels": ["1_1"],
      "level": 0.3,
      "level_2": null,
      "duration": "1min",
      "ramp_time": "10s",
    },
}
```

### Supported Domains and Field Restrictions

Each domain supports different fields. Using unsupported fields will result in a validation error.

| Field       |        Switch        |    Light     |       Cover        |    Valve     |
| ----------- | :------------------: | :----------: | :----------------: | :----------: |
| `level`     | ✅ (0.0 or 1.0 only) | ✅ (0.0-1.0) |    ✅ (0.0-1.0)    | ✅ (0.0-1.0) |
| `level_2`   |          ❌          |      ❌      | ✅ (slat position) |      ❌      |
| `duration`  |          ✅          |      ✅      |         ❌         |      ✅      |
| `ramp_time` |          ❌          |      ✅      |         ❌         |      ❌      |

**Important restrictions:**

- **Switch**: The `level` field only accepts `0.0` (off) or `1.0` (on). Intermediate values like `0.5` are not allowed.
- **Light**: Supports `ramp_time` for smooth dimming transitions. Does not support `level_2`.
- **Cover**: Supports `level_2` for slat/blind position. Does not support `duration` or `ramp_time`.
- **Valve**: Does not support `level_2` or `ramp_time`.

### Schedule Data Format

The `schedule_data` is a dictionary where:

- **Key**: String representing the entry number ("1" to "24")
- **Value**: Dictionary with schedule entry details (`SimpleScheduleEntry` fields)

Each entry is validated by the `SimpleScheduleEntry` Pydantic model and contains the following fields:

#### Required Fields

##### weekdays

- **Type**: List of strings
- **Description**: Days when this schedule triggers
- **Valid values**: `"MONDAY"`, `"TUESDAY"`, `"WEDNESDAY"`, `"THURSDAY"`, `"FRIDAY"`, `"SATURDAY"`, `"SUNDAY"`
- **Constraint**: At least one weekday required
- **Example**: `["MONDAY", "FRIDAY"]` or `["SUNDAY", "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY"]`

##### time

- **Type**: String
- **Description**: Trigger time in 24-hour format
- **Format**: `"HH:MM"` (hours: 00-23, minutes: 00-59)
- **Example**: `"07:30"`, `"22:00"`, `"00:00"`

##### target_channels

- **Type**: List of strings
- **Description**: Target actor channels to control
- **Format**: Each channel as `"X_Y"` where X=1-8 (device channel), Y=1-3 (actor channel)
- **Constraint**: At least one channel required
- **Example**: `["1_1"]`, `["1_1", "2_1"]`

##### level

- **Type**: Float
- **Description**: Output level for the target device
- **Range**: 0.0 to 1.0
- **Meaning by device type**:
  - **Switch**: `0.0` = off, `1.0` = on
  - **Light (dimmable)**: `0.0` = off, `1.0` = 100% brightness, `0.5` = 50% brightness
  - **Cover**: `0.0` = closed, `1.0` = open
  - **Valve**: `0.0` = closed, `1.0` = open
- **Example**: `0.0`, `0.5`, `1.0`

#### Optional Fields

##### condition

- **Type**: String
- **Description**: Trigger condition type
- **Valid values**:
  - `"fixed_time"` (default) - Trigger at specified time
  - `"astro"` - Trigger at astro event (sunrise/sunset)
  - `"fixed_if_before_astro"` - Trigger at time if before astro event, otherwise at astro event
  - `"fixed_if_after_astro"` - Trigger at time if after astro event, otherwise at astro event
- **Default**: `"fixed_time"`
- **Note**: When using astro conditions, `astro_type` must be set

##### astro_type

- **Type**: String or null
- **Description**: Astronomical event type for astro-based conditions
- **Valid values**: `"sunrise"`, `"sunset"`, `null`
- **Default**: `null`
- **Required when**: `condition` is not `"fixed_time"`

##### astro_offset_minutes

- **Type**: Integer
- **Description**: Offset in minutes from the astronomical event
- **Range**: -720 to 720 (-12 hours to +12 hours)
- **Default**: `0`
- **Example**: `30` (30 minutes after), `-60` (60 minutes before)

##### level_2

- **Type**: Float or null
- **Description**: Secondary level for devices with dual outputs (e.g., cover slat position)
- **Range**: 0.0 to 1.0
- **Default**: `null`
- **Used by**: Cover devices (for slat/blind position)

##### duration

- **Type**: String or null
- **Description**: How long to keep the output active
- **Format**: Number followed by unit: `"Xs"` (seconds), `"Xmin"` (minutes), `"Xh"` (hours)
- **Default**: `null` (permanent/until next schedule)
- **Examples**: `"10s"`, `"5min"`, `"1h"`, `"30min"`

##### ramp_time

- **Type**: String or null
- **Description**: Transition/ramp time for dimmer devices
- **Format**: Number followed by unit: `"Xms"` (milliseconds), `"Xs"` (seconds)
- **Default**: `null` (instant change)
- **Examples**: `"500ms"`, `"2s"`, `"10s"`
- **Used by**: Dimmable lights

#### Field Summary Table

| Field                | Type        | Required | Range/Format           | Default      |
| -------------------- | ----------- | -------- | ---------------------- | ------------ |
| weekdays             | list[str]   | ✅       | MONDAY-SUNDAY          | -            |
| time                 | str         | ✅       | HH:MM (00:00-23:59)    | -            |
| target_channels      | list[str]   | ✅       | ["X_Y"]                | -            |
| level                | float       | ✅       | 0.0-1.0                | -            |
| condition            | str         | ❌       | fixed_time, astro, ... | "fixed_time" |
| astro_type           | str \| null | ❌       | sunrise, sunset, null  | null         |
| astro_offset_minutes | int         | ❌       | -720 to 720            | 0            |
| level_2              | float\|null | ❌       | 0.0-1.0 or null        | null         |
| duration             | str \| null | ❌       | "10s", "5min", "1h"    | null         |
| ramp_time            | str \| null | ❌       | "500ms", "2s"          | null         |

#### Complete Example

```yaml
schedule_data:
  "1": # Workday morning (fixed time)
    weekdays: [MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY]
    time: "06:30"
    condition: fixed_time
    target_channels: ["1_1"]
    level: 0.8 # 80% brightness
    duration: 1min
    ramp_time: 10s
    astro_type: null
    astro_offset_minutes: 0
    level_2: null
  "2": # Weekend morning (sunrise-based)
    weekdays: [SATURDAY, SUNDAY]
    time: "08:00" # Fallback time
    condition: fixed_if_after_astro # Use 08:00 if after sunrise, else sunrise
    astro_type: sunrise
    astro_offset_minutes: 30 # 30 minutes after sunrise
    target_channels: ["1_1"]
    level: 0.5 # 50% brightness
    duration: 30min
    ramp_time: 5s
    level_2: null
```

---

## Common Climate Schedules

### Workday Schedule

```yaml
base_temperature: 17.0
periods:
  - starttime: "06:00"
    endtime: "07:30"
    temperature: 21.0
  - starttime: "17:00"
    endtime: "22:00"
    temperature: 21.0
```

### Weekend Schedule

```yaml
base_temperature: 17.0
periods:
  - starttime: "08:00"
    endtime: "23:00"
    temperature: 21.0
```

### Home Office Schedule

```yaml
base_temperature: 17.0
periods:
  - starttime: "07:00"
    endtime: "22:00"
    temperature: 21.0
```

### Night Setback Only

```yaml
base_temperature: 21.0
periods:
  - starttime: "23:00"
    endtime: "06:00"
    temperature: 17.0
```

## Tips

### Base Temperature Selection

The `base_temperature` should be:

- The temperature you want most of the time
- Usually your "setback" or "economy" temperature
- Typically 16-18°C for energy savings

### Period Design

- **Keep periods simple** - 2-4 periods per day is usually sufficient
- **Avoid tiny gaps** - If two periods are close, consider merging them
- **Round times** - Use 15 or 30 minute increments for easier management

### Copying Best Practices

1. **Create a template device** - Set up one thermostat perfectly, then copy to others
2. **Copy profiles, not devices** - Use `copy_schedule_profile` for more control
3. **Verify after copying** - Use `get_schedule_profile` to confirm

---

## Automation Examples

### Switch climate profile on Friday evening

```yaml
automation:
  - alias: "Switch to weekend schedule"
    trigger:
      - platform: time
        at: "18:00"
    condition:
      - condition: time
        weekday:
          - fri
    action:
      - action: homematicip_local.set_schedule_weekday
        data:
          device_id: abcdefg...
          profile: P1
          weekday: SATURDAY
          base_temperature: 17.0
          simple_weekday_list:
            - starttime: "08:00"
              endtime: "23:00"
              temperature: 21.0
```

### Example: Switch Schedule

```yaml
action: homematicip_local.set_schedule
data:
  device_id: abcdefg...
  schedule_data:
    "1": # Weekday evening
      weekdays: [MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY]
      time: "18:00"
      condition: fixed_time
      target_channels: ["1_1"]
      level: 1.0 # On (only 0.0 or 1.0 allowed!)
      duration: 4h
    "2": # Weekend evening
      weekdays: [SATURDAY, SUNDAY]
      time: "17:00"
      condition: fixed_time
      target_channels: ["1_1"]
      level: 1.0 # On
      duration: 6h
```

### Example: Garden Irrigation Valve

```yaml
action: homematicip_local.set_schedule
data:
  device_id: abcdefg...
  schedule_data:
    "1": # Morning watering on weekdays
      weekdays: [MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY]
      time: "06:00"
      condition: fixed_time
      target_channels: ["1_1"]
      level: 1.0 # Fully open
      duration: 30min
    "2": # Evening watering on weekdays
      weekdays: [MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY]
      time: "18:00"
      condition: fixed_time
      target_channels: ["1_1"]
      level: 1.0 # Fully open
      duration: 30min
    "3": # Weekend watering
      weekdays: [SATURDAY, SUNDAY]
      time: "07:00"
      condition: fixed_time
      target_channels: ["1_1"]
      level: 1.0 # Fully open
      duration: 45min
```

### Example: Light Dimmer Schedule

```yaml
action: homematicip_local.set_schedule
data:
  device_id: abcdefg...
  schedule_data:
    "1": # Weekday morning
      weekdays: [MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY]
      time: "06:00"
      condition: fixed_time
      target_channels: ["1_1"]
      level: 0.3 # 30% brightness
      duration: 2h
      ramp_time: 10s # Smooth transition (only for lights!)
    "2": # Weekday evening
      weekdays: [MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY]
      time: "17:00"
      condition: fixed_time
      target_channels: ["1_1"]
      level: 0.6 # 60% brightness
      duration: 5h
      ramp_time: 10s
    "3": # Late night
      weekdays: [SUNDAY, MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY, SATURDAY]
      time: "22:00"
      condition: fixed_time
      target_channels: ["1_1"]
      level: 0.2 # 20% brightness
      duration: 1h
      ramp_time: 10s
```

### Example: Cover/Blind Schedule

```yaml
action: homematicip_local.set_schedule
data:
  device_id: abcdefg...
  schedule_data:
    "1": # Morning - open blinds
      weekdays: [MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY, SATURDAY, SUNDAY]
      time: "07:00"
      condition: fixed_time
      target_channels: ["1_1"]
      level: 1.0 # Fully open
      level_2: 0.5 # Slats at 50% (only for covers!)
    "2": # Midday - partial shade
      weekdays: [MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY, SATURDAY, SUNDAY]
      time: "12:00"
      condition: fixed_time
      target_channels: ["1_1"]
      level: 0.7 # 70% open
      level_2: 0.3 # Slats at 30%
    "3": # Evening - close blinds
      weekdays: [MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY, SATURDAY, SUNDAY]
      time: "21:00"
      condition: fixed_time
      target_channels: ["1_1"]
      level: 0.0 # Closed
      level_2: 0.0 # Slats closed
```

---

## Differences: Climate vs. Non-Climate

| Feature      | Climate Services                            | Non-Climate Services           |
| ------------ | ------------------------------------------- | ------------------------------ |
| **Devices**  | Thermostats only                            | Switch, light, cover, valve    |
| **Format**   | Simple format with base_temperature         | Generic schedule_data dict     |
| **Profiles** | P1-P6 profiles                              | Single schedule (device-level) |
| **Services** | set_schedule_profile / set_schedule_weekday | set_schedule                   |

---

## Troubleshooting

### Schedule Not Applied

1. **Check CONFIG_PENDING** - Wait for the device to confirm the change
2. **Verify profile selection** - Ensure the correct profile (P1-P6) is active on the device (climate only)
3. **Check time format** - Use `"HH:MM"` format (24-hour, with quotes in YAML)
4. **Device support** - Verify the device supports schedules (check Week Profile sensor entity)

### Reading Returns Empty

- The device may not support schedules
- Try reloading the device configuration
- Check that the device has a week profile configured

### Copy Fails

- Both devices must support schedules
- Both devices must have the same number of profiles (climate only)
- Check that devices are reachable

### Validation Error: Unsupported Field

If you receive an error like "level_2 not supported for switch" or "ramp_time not supported for cover":

- Check the [field restrictions table](#supported-domains-and-field-restrictions) for your domain
- Remove unsupported fields from your schedule data
- For switches, ensure `level` is exactly `0.0` or `1.0` (not intermediate values)

## See Also

- [Actions Reference](homeassistant_actions.md#schedule-operations)
- [Climate Entities](../homeassistant_integration.md)
