# Week Profile / Schedule Management

This guide explains how to manage heating schedules (week profiles) for climate devices in Home Assistant using the Homematic(IP) Local integration.

## Overview

Homematic thermostats support up to **6 schedule profiles** (P1-P6), each containing a weekly schedule with individual settings for each day.

| Feature      | Description                                                    |
| ------------ | -------------------------------------------------------------- |
| **Profiles** | P1 through P6 (6 independent schedules)                        |
| **Days**     | MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY, SATURDAY, SUNDAY |
| **Format**   | Simple format with base temperature and heating periods        |

## Simple Format

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

## Actions

### Set Complete Profile

Set the schedule for all weekdays of a profile:

```yaml
action: homematicip_local.set_schedule_simple_profile
target:
  entity_id: climate.living_room_thermostat
data:
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
action: homematicip_local.set_schedule_simple_weekday
target:
  entity_id: climate.living_room_thermostat
data:
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

Get the current schedule in simple format:

```yaml
# Get complete profile
action: homematicip_local.get_schedule_simple_profile
target:
  entity_id: climate.living_room_thermostat
data:
  profile: P1

# Get single weekday
action: homematicip_local.get_schedule_simple_weekday
target:
  entity_id: climate.living_room_thermostat
data:
  profile: P1
  weekday: MONDAY
```

### Copy Schedules

Copy schedules between devices or profiles:

```yaml
# Copy complete schedule (all profiles) from source to target device
action: homematicip_local.copy_schedule
target:
  entity_id: climate.target_thermostat
data:
  source_entity_id: climate.source_thermostat

# Copy single profile (within same device or to another)
action: homematicip_local.copy_schedule_profile
target:
  entity_id: climate.target_thermostat
data:
  source_entity_id: climate.source_thermostat  # Optional: omit if copying within same device
  source_profile: P1
  target_profile: P2
```

## Common Schedules

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
3. **Verify after copying** - Use `get_schedule_simple_profile` to confirm

## Automation Example

Set a weekend schedule every Friday evening:

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
      - action: homematicip_local.set_schedule_simple_weekday
        target:
          entity_id: climate.living_room_thermostat
        data:
          profile: P1
          weekday: SATURDAY
          base_temperature: 17.0
          simple_weekday_list:
            - starttime: "08:00"
              endtime: "23:00"
              temperature: 21.0
```

## Non-Climate Devices (Switch, Light, Cover, Valve) (Work in progress)

For devices other than climate (thermostats), a generic schedule service is available that supports switches, lights, covers, and valves with week profile capability.

### Set Schedule

Set a week schedule for devices that support scheduling:

```yaml
action: homematicip_local.set_schedule
target:
  entity_id: light.kitchen_spotlight
data:
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
      level_2: null
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
      level_2: null
      duration: 1min
      ramp_time: 10s
```

### Get Schedule

Get the current week schedule from a device:

```yaml
action: homematicip_local.get_schedule
target:
  entity_id: light.kitchen_spotlight
response_variable: current_schedule
```

The service returns the schedule data in the same format as used by `set_schedule`:

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

### Supported Domains

- **switch** - Timed on/off schedules
- **light** - Timed on/off or dimmer schedules
- **cover** - Position schedules
- **valve** - Open/close schedules

### Schedule Data Format

The `schedule_data` is a dictionary where:

- **Key**: String representing the entry number (e.g., "1", "2", "3")
- **Value**: Dictionary with schedule entry details

Each entry contains the following fields:

#### Common Fields

- **weekdays**: List of weekdays when this schedule applies
  - Valid values: `SUNDAY`, `MONDAY`, `TUESDAY`, `WEDNESDAY`, `THURSDAY`, `FRIDAY`, `SATURDAY`
- **time**: Start time in "HH:MM" format (24-hour)
- **condition**: Trigger condition
  - `fixed_time` - Trigger at specified time
  - `astro_sunrise` - Trigger at sunrise (with optional offset)
  - `astro_sunset` - Trigger at sunset (with optional offset)
- **astro_type**: Astronomical event type (null for fixed_time)
- **astro_offset_minutes**: Offset in minutes from astronomical event (0 for fixed_time)
- **target_channels**: List of device channels to control (e.g., ["1_1"])
- **duration**: How long to apply the setting (e.g., "1min", "5min")
- **ramp_time**: Transition time for changes (e.g., "10s", "30s")

#### Device-Specific Fields

- **level**: Brightness level for lights, or valve position (0.0 to 1.0)
- **level_2**: Secondary level (used by some devices, typically null)

#### Example Entry

```yaml
schedule_data:
  "1":
    weekdays: [MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY]
    time: "06:30"
    condition: fixed_time
    astro_type: null
    astro_offset_minutes: 0
    target_channels: ["1_1"]
    level: 0.8 # 80% brightness
    level_2: null
    duration: 1min
    ramp_time: 10s
```

### Device Support Check

Not all devices support week profiles. Check the entity's attributes:

```yaml
# Example: Check if device supports schedules
{{ state_attr('switch.garden_pump', 'has_schedule') }}
```

### Differences from Climate Schedules

| Feature      | Climate Services                    | Generic set_schedule              |
| ------------ | ----------------------------------- | --------------------------------- |
| **Domains**  | climate only                        | switch, light, cover, valve       |
| **Format**   | Simple format with base_temperature | Generic schedule_data dict        |
| **Profiles** | P1-P6 profiles                      | Single schedule (device-specific) |
| **Services** | set_schedule_simple_profile/weekday | set_schedule                      |

### Example: Garden Irrigation Valve

```yaml
action: homematicip_local.set_schedule
target:
  entity_id: valve.garden_irrigation
data:
  schedule_data:
    "1": # Morning watering on weekdays
      weekdays: [MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY]
      time: "06:00"
      condition: fixed_time
      astro_type: null
      astro_offset_minutes: 0
      target_channels: ["1_1"]
      level: 1.0 # Fully open
      level_2: null
      duration: 30min
      ramp_time: 10s
    "2": # Evening watering on weekdays
      weekdays: [MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY]
      time: "18:00"
      condition: fixed_time
      astro_type: null
      astro_offset_minutes: 0
      target_channels: ["1_1"]
      level: 1.0 # Fully open
      level_2: null
      duration: 30min
      ramp_time: 10s
    "3": # Weekend watering
      weekdays: [SATURDAY, SUNDAY]
      time: "07:00"
      condition: fixed_time
      astro_type: null
      astro_offset_minutes: 0
      target_channels: ["1_1"]
      level: 1.0 # Fully open
      level_2: null
      duration: 45min
      ramp_time: 10s
```

### Example: Light Dimmer Schedule

```yaml
action: homematicip_local.set_schedule
target:
  entity_id: light.hallway_dimmer
data:
  schedule_data:
    "1": # Weekday morning
      weekdays: [MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY]
      time: "06:00"
      condition: fixed_time
      astro_type: null
      astro_offset_minutes: 0
      target_channels: ["1_1"]
      level: 0.3 # 30% brightness
      level_2: null
      duration: 2h
      ramp_time: 10s
    "2": # Weekday evening
      weekdays: [MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY]
      time: "17:00"
      condition: fixed_time
      astro_type: null
      astro_offset_minutes: 0
      target_channels: ["1_1"]
      level: 0.6 # 60% brightness
      level_2: null
      duration: 5h
      ramp_time: 10s
    "3": # Late night
      weekdays: [SUNDAY, MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY, SATURDAY]
      time: "22:00"
      condition: fixed_time
      astro_type: null
      astro_offset_minutes: 0
      target_channels: ["1_1"]
      level: 0.2 # 20% brightness
      level_2: null
      duration: 1h
      ramp_time: 10s
```

## Troubleshooting

### Schedule Not Applied

1. **Check CONFIG_PENDING** - Wait for the device to confirm the change
2. **Verify profile selection** - Ensure the correct profile (P1-P6) is active on the device (climate only)
3. **Check time format** - Use `"HH:MM"` format (24-hour, with quotes in YAML)
4. **Device support** - Verify the device supports schedules (check `has_schedule` attribute)

### Reading Returns Empty

- The device may not support schedules
- Try reloading the device configuration
- Check that the device has a week profile configured

### Copy Fails

- Both devices must support schedules
- Both devices must have the same number of profiles (climate only)
- Check that devices are reachable

### set_schedule Service Not Available

- Service is only available for switch, light, cover, and valve domains
- Climate devices use the `set_schedule_simple_profile` and `set_schedule_simple_weekday` services instead
- Check that the device actually supports week profiles

## See Also

- [Actions Reference](homeassistant_actions.md#climate-schedule-operations)
- [Climate Entities](../homeassistant_integration.md)
