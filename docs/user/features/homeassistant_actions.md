# Actions Reference

This page documents all custom actions provided by the Homematic(IP) Local for OpenCCU integration.

---

## Device Value Operations

### homematicip_local.get_device_value

Get a device parameter via the XML-RPC interface.

### homematicip_local.set_device_value

Set a device parameter via the XML-RPC interface.

!!! warning "Storage Warning"
Too much writing to the device MASTER paramset could damage your device's storage.

**Example - Turn on a switch:**

```yaml
action: homematicip_local.set_device_value
data:
  device_id: abcdefg...
  channel: 1
  parameter: STATE
  value: "true"
  value_type: boolean
```

**Example - Set thermostat temperature:**

```yaml
action: homematicip_local.set_device_value
data:
  device_id: abcdefg...
  channel: 4
  parameter: SET_TEMPERATURE
  value: "23.0"
  value_type: double
```

---

## Paramset Operations

### homematicip_local.get_paramset

Call `getParamset` on the XML-RPC interface. Returns a paramset.

### homematicip_local.put_paramset

Call `putParamset` on the XML-RPC interface.

!!! warning "Storage Warning"
Too much writing to the device MASTER paramset could damage your device's storage.

**Example - Set week program:**

```yaml
action: homematicip_local.put_paramset
data:
  device_id: abcdefg...
  paramset_key: MASTER
  paramset:
    WEEK_PROGRAM_POINTER: 1
```

**Example with rx_mode (BidCos-RF only):**

```yaml
action: homematicip_local.put_paramset
data:
  device_id: abcdefg...
  paramset_key: MASTER
  rx_mode: WAKEUP
  paramset:
    WEEK_PROGRAM_POINTER: 1
```

!!! note "rx_mode Options" - `BURST` (default): Wakes all devices immediately (uses battery) - `WAKEUP`: Sends data after device reports (saves battery, ~3 min delay)

### homematicip_local.get_link_paramset

Call `getParamset` for direct connections on the XML-RPC interface.

### homematicip_local.put_link_paramset

Call `putParamset` for direct connections on the XML-RPC interface.

---

## Link Operations

### homematicip_local.add_link

Call `addLink` on the XML-RPC interface. Creates a direct connection.

### homematicip_local.remove_link

Call `removeLink` on the XML-RPC interface. Removes a direct connection.

### homematicip_local.get_link_peers

Call `getLinkPeers` on the XML-RPC interface. Returns a dict of direct connection partners.

### homematicip_local.create_central_links

Creates a central link from a device to the backend. Required for RF devices to enable button-press events.

### homematicip_local.remove_central_links

Removes a central link from the backend. Disables button-press events.

---

## Climate Schedule Operations

!!! warning "Storage Warning"
Too much writing to the device could damage your device's storage.

### homematicip_local.set_schedule_simple_profile

Sends a complete schedule for a climate profile using a **simplified format**.

**How it works:**

- Each weekday has a `base_temperature` and a list of `periods`
- Specify only active heating periods with `starttime`, `endtime`, and `temperature`
- Gaps are automatically filled with `base_temperature`
- System converts to required 13-slot format

**Example:**

```yaml
action: homematicip_local.set_schedule_simple_profile
target:
  entity_id: climate.living_room_thermostat
data:
  profile: P1
  simple_profile_data:
    MONDAY:
      base_temperature: 16.0
      periods:
        - starttime: "05:00"
          endtime: "06:00"
          temperature: 17.0
        - starttime: "09:00"
          endtime: "15:00"
          temperature: 17.0
        - starttime: "19:00"
          endtime: "22:00"
          temperature: 22.0
    TUESDAY:
      base_temperature: 16.0
      periods:
        - starttime: "05:00"
          endtime: "06:00"
          temperature: 17.0
        - starttime: "19:00"
          endtime: "22:00"
          temperature: 22.0
    # Add other weekdays as needed
```

### homematicip_local.set_schedule_simple_weekday

Sends schedule for a single weekday using simplified format.

**Example:**

```yaml
action: homematicip_local.set_schedule_simple_weekday
target:
  entity_id: climate.living_room_thermostat
data:
  profile: P3
  weekday: MONDAY
  base_temperature: 16
  simple_weekday_list:
    - starttime: "05:00"
      endtime: "06:00"
      temperature: 17.0
    - starttime: "09:00"
      endtime: "15:00"
      temperature: 17.0
    - starttime: "19:00"
      endtime: "22:00"
      temperature: 22.0
```

**Result:**

- 00:00-05:00: 16°C (base_temperature)
- 05:00-06:00: 17°C (period 1)
- 06:00-09:00: 16°C (base fills gap)
- 09:00-15:00: 17°C (period 2)
- 15:00-19:00: 16°C (base fills gap)
- 19:00-22:00: 22°C (period 3)
- 22:00-24:00: 16°C (base_temperature)

### homematicip_local.get_schedule_simple_profile

Returns the schedule of a climate profile in simplified format.

The service analyzes the schedule and determines `base_temperature` as the most frequently used temperature. Only periods that deviate are returned.

### homematicip_local.get_schedule_simple_weekday

Returns the schedule for a specific weekday in simplified format.

### homematicip_local.copy_schedule

Copies the complete schedule (all profiles P1-P6, all weekdays) from one climate device to another.

**Requirements:**

- Both devices must support schedules
- Both devices must support the same number of profiles

### homematicip_local.copy_schedule_profile

Copies a single schedule profile from one device to another (or to a different profile on the same device).

**Use cases:**

- Copy P1 from Device A to P2 on Device A
- Copy P1 from Device A to P1 on Device B
- Copy P3 from Device A to P1 on Device B

### Raw Schedule Operations

The following actions work with the raw 13-slot schedule format used internally by Homematic devices. For most users, the simplified format above is easier to use.

#### homematicip_local.get_schedule_profile

Returns the complete schedule of a climate profile in raw format (all 13 slots per weekday).

#### homematicip_local.get_schedule_weekday

Returns the schedule for a specific weekday in raw format.

#### homematicip_local.set_schedule_profile

Sets the complete schedule for a climate profile using raw format.

!!! warning "Advanced Use"
The raw format requires all 13 time slots per weekday. Consider using `set_schedule_simple_profile` instead.

#### homematicip_local.set_schedule_weekday

Sets the schedule for a specific weekday using raw format.

---

## Climate Away Mode

### homematicip_local.enable_away_mode_by_calendar

Enable away mode by specifying start and end date/time.

!!! note "HomematicIP only"

### homematicip_local.enable_away_mode_by_duration

Enable away mode immediately with duration in hours.

!!! note "HomematicIP only"

### homematicip_local.disable_away_mode

Disable away mode for climate devices.

!!! note "HomematicIP only"

---

## System Variables

### homematicip_local.get_variable_value

Get the value of a variable from your Homematic hub.

### homematicip_local.set_variable_value

Set the value of a variable on your Homematic hub.

**Value lists:** Accept 0-based position or the value as input.

**Booleans:**

- `true`, `on`, `1`, 1 → True
- `false`, `off`, `0`, 0 → False

**Example:**

```yaml
action: homematicip_local.set_variable_value
data:
  entity_id: sensor.ccu2
  name: Variable name
  value: true
```

### homematicip_local.fetch_system_variables

Fetch system variables on demand, independent of the default 30s schedule.

!!! warning "Use sparingly - frequent calls may affect CCU stability"

---

## Siren & Sound Operations

### homematicip_local.turn_on_siren

Turn siren on. Can be disabled with `siren.turn_off`.

!!! note "Automatic Select Entities"
Since version 2.0.0, the integration automatically creates **Select entities** for siren tone and light pattern selection:

    - **Siren Tone** (`select.<device>_acoustic_alarm_selection`)
    - **Siren Light Pattern** (`select.<device>_optical_alarm_selection`)

    These selections persist across restarts and are automatically used when calling siren services.

### homematicip_local.play_sound

Play a sound on HmIP-MP3P sound player devices.

| Field         | Required | Description                                              |
| ------------- | -------- | -------------------------------------------------------- |
| `soundfile`   | No       | Sound file (e.g., `SOUNDFILE_001`, `INTERNAL_SOUNDFILE`) |
| `volume`      | No       | Volume (0.0 to 1.0)                                      |
| `on_time`     | No       | Duration in seconds                                      |
| `ramp_time`   | No       | Volume fade time in seconds                              |
| `repetitions` | No       | Repetitions (0=none, 1-18=count, -1=infinite)            |

### homematicip_local.stop_sound

Stop sound playback on HmIP-MP3P devices.

### homematicip_local.set_sound_led

Set LED color and brightness on HmIP-MP3P devices.

| Field         | Required | Description                                                                          |
| ------------- | -------- | ------------------------------------------------------------------------------------ |
| `color`       | No       | LED color: `black`, `blue`, `green`, `turquoise`, `red`, `purple`, `yellow`, `white` |
| `brightness`  | No       | Brightness (0 to 255)                                                                |
| `on_time`     | No       | Duration in seconds                                                                  |
| `ramp_time`   | No       | Fade time in seconds                                                                 |
| `repetitions` | No       | Repetitions                                                                          |
| `flash_time`  | No       | Flash duration in ms (0 to 5000)                                                     |

---

## Cover Operations

### homematicip_local.set_cover_combined_position

Move a blind to a specific position and tilt position simultaneously.

---

## Light & Switch On-Time

### homematicip_local.light_set_on_time

Set on time for a light entity. Must be followed by `light.turn_on`. Use 0 to reset.

### homematicip_local.switch_set_on_time

Set on time for a switch entity. Must be followed by `switch.turn_on`. Use 0 to reset.

### homematicip_local.valve_set_on_time

Set on time for a valve entity. Must be followed by `valve.open`. Use 0 to reset.

---

## Text Display

### homematicip_local.send_text_display

Send text to a notify entity (text display devices like HmIP-WRCD).

| Field              | Required | Description                                                                                                                                        |
| ------------------ | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `entity_id`        | Yes      | Notify entity ID (domain: `notify`)                                                                                                                |
| `text`             | Yes      | Text to display                                                                                                                                    |
| `icon`             | No       | Display icon (see options below)                                                                                                                   |
| `background_color` | No       | Background color: `white`, `black`                                                                                                                 |
| `text_color`       | No       | Text color: `white`, `black`                                                                                                                       |
| `alignment`        | No       | Text alignment: `left`, `center`, `right`                                                                                                          |
| `display_id`       | No       | Display ID (1-5) for multi-display devices                                                                                                         |
| `sound`            | No       | Sound: `disarmed`, `externally_armed`, `internally_armed`, `delayed_externally_armed`, `delayed_internally_armed`, `event`, `error`, `low_battery` |
| `repeat`           | No       | Repeat count (0-15)                                                                                                                                |

**Available icons:**

`no_icon`, `sun`, `moon`, `cloud`, `cloud_and_sun`, `cloud_and_mooon`, `cloud_sun_and_rain`, `rain`, `raindrop`, `drizzle`, `snow`, `snowflake`, `wind`, `thunderstorm`, `bell`, `clock`, `eco`, `flame`, `lamp_on`, `lamp_off`, `padlock_open`, `padlock_closed`, `error`, `everything_okay`, `information`, `new_message`, `service_message`, `shutters`, `window_open`, `external_protection`, `internal_protection`, `protection_deactivated`

**Example:**

```yaml
action: homematicip_local.send_text_display
target:
  entity_id: notify.display_living_room
data:
  text: "Hello World"
  icon: sun
  background_color: white
  text_color: black
  alignment: center
  sound: event
```

### homematicip_local.clear_text_display

Clear text on a notify entity (text display).

---

## Device Management

### homematicip_local.export_device_definition

Exports a device definition as a ZIP file to:
`{HA_config}/homematicip_local/{device_model}.zip`

The ZIP contains:

- `device_descriptions/{device_model}.json`
- `paramset_descriptions/{device_model}.json`

Upload to [pydevccu](https://github.com/sukramj/pydevccu) to support development of new devices.

### homematicip_local.reload_device_config

Reload device configuration from CCU. Refreshes paramset descriptions and values.

### homematicip_local.reload_channel_config

Reload configuration for a specific channel from CCU.

### homematicip_local.force_device_availability

Reactivate a device in HA that was made unavailable by an UNREACH event.

!!! warning "Not a fix for communication problems"
This only overrides availability status in HA. No communication with the backend occurs.

### homematicip_local.confirm_all_delayed_devices

Confirms all delayed devices (CCU inbox) at once and adds them to Home Assistant without custom names.

---

## System Operations

### homematicip_local.clear_cache

Clears the cache for a central unit from Home Assistant. Requires restart.

### homematicip_local.record_session

Records a session for debugging (max 10 minutes). Output saved to:
`{HA_config}/homematicip_local/session/`

### homematicip_local.create_ccu_backup

Create and download a system backup from CCU.

!!! note "OpenCCU only"
This feature is only available for OpenCCU (formerly RaspberryMatic). Not supported on CCU2, CCU3, Debmatic, or piVCCU.

Backup saved to: `{HA_storage}/homematicip_local/backup/`

**Returns:**

```yaml
success: true
path: "/config/.storage/homematicip_local/backup/ccu_backup_raspberrymatic_20251203_143022.sbk"
filename: "ccu_backup_raspberrymatic_20251203_143022.sbk"
size: 12345678
```

**Automation Example - Weekly Backup:**

```yaml
automation:
  - alias: "Weekly OpenCCU Backup"
    trigger:
      - platform: time
        at: "03:00:00"
    condition:
      - condition: time
        weekday:
          - sun
    action:
      - action: homematicip_local.create_ccu_backup
        data:
          entry_id: YOUR_ENTRY_ID
```

---

## Home Assistant Built-in Actions

### homeassistant.update_entity

Update entity value (limited to once per 60 seconds).

!!! note "Use sparingly"
99.9% of entities update automatically. Use only for edge cases (e.g., RSSI values of some HM devices).

    - Battery devices: Values from backend cache
    - Non-battery devices: Values from device (impacts duty cycle)

### homematicip_local.update_device_firmware_data

Update firmware data for all devices.

---

## See Also

- [Integration Guide](../homeassistant_integration.md)
- [Troubleshooting](../troubleshooting/homeassistant_troubleshooting.md)
