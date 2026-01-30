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

## Troubleshooting

### Schedule Not Applied

1. **Check CONFIG_PENDING** - Wait for the device to confirm the change
2. **Verify profile selection** - Ensure the correct profile (P1-P6) is active on the device
3. **Check time format** - Use `"HH:MM"` format (24-hour, with quotes in YAML)

### Reading Returns Empty

- The device may not support schedules
- Try reloading the device configuration

### Copy Fails

- Both devices must support schedules
- Both devices must have the same number of profiles
- Check that devices are reachable

## See Also

- [Actions Reference](homeassistant_actions.md#climate-schedule-operations)
- [Climate Entities](../homeassistant_integration.md)
