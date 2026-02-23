# Schedule Card

The **HomematicIP Local Schedule Card** is a custom Lovelace card for displaying and editing event-based schedules for Homematic switches, lights, covers, and valves.

---

## Features

- **Event-based scheduling**: Manage individual schedule events with precise control
- **Multi-device support**: Works with switches, lights, covers, and valves
- **Flexible timing**: Fixed time or astronomical events (sunrise/sunset) with offset
- **8 condition types**: Fixed time, astro, earliest/latest combinations
- **Category-specific UI**: Adapted controls per device type (dimming, slat position, duration, etc.)
- **Visual configuration**: Configure via the UI editor — no YAML required
- **Bilingual**: English and German

---

## Supported Device Types

| Domain   | Description                                    | Special Fields          |
| -------- | ---------------------------------------------- | ----------------------- |
| `switch` | On/Off devices                                 | Level: 0.0 or 1.0 only  |
| `light`  | Lights with dimming support                    | Level + ramp time       |
| `cover`  | Blinds/shutters with position and slat control | Level + level_2 (slats) |
| `valve`  | Heating valves                                 | Level + duration        |

---

## Installation

### HACS (Recommended)

1. In HACS, go to **Frontend**
2. Click the three-dot menu → **Custom repositories**
3. Add: `https://github.com/SukramJ/homematicip_local_schedule_card`
4. Select category **Lovelace**
5. Click **Install**
6. Restart Home Assistant

### Manual

1. Download `homematicip-local-schedule-card.js` from the [latest release](https://github.com/SukramJ/homematicip_local_schedule_card/releases)
2. Copy to `config/www/`
3. Add resource: **Settings** → **Dashboards** → **Resources** → **Add Resource**
   - URL: `/local/homematicip-local-schedule-card.js`
   - Type: JavaScript Module

---

## Configuration

### Basic

```yaml
type: custom:homematicip-local-schedule-card
entity: switch.garden_lights
```

### Multiple Entities

```yaml
type: custom:homematicip-local-schedule-card
entities:
  - switch.garden_lights
  - light.hallway_dimmer
  - cover.living_room_blinds
```

When multiple entities are defined, a dropdown appears to switch between them.

### All Options

| Option              | Type     | Default     | Description                      |
| ------------------- | -------- | ----------- | -------------------------------- |
| `entity`            | string   | —           | Single entity ID                 |
| `entities`          | string[] | —           | List of entity IDs               |
| `name`              | string   | Entity name | Custom card header name          |
| `editable`          | boolean  | `true`      | Enable/disable editing           |
| `hour_format`       | string   | `24`        | Time format: `12` or `24` hour   |
| `language`          | string   | Auto-detect | Force language: `en` or `de`     |
| `time_step_minutes` | number   | `15`        | Time picker step size in minutes |

---

## Usage

### Schedule Events

Each schedule event defines when and how a device should be controlled. A device supports up to **24 schedule events**.

An event consists of:

- **Weekdays**: Which days the event is active
- **Time**: When the event triggers (fixed or astronomical)
- **Target channels**: Which device channels to control
- **Level**: Output level (0.0–1.0)
- **Duration**: How long to keep the output active (optional)
- **Ramp time**: Transition time for dimmers (optional, lights only)

### Condition Types

Events can use different timing conditions:

| Condition               | Description                                           |
| ----------------------- | ----------------------------------------------------- |
| `fixed_time`            | Trigger at the specified time                         |
| `astro`                 | Trigger at sunrise or sunset (with optional offset)   |
| `fixed_if_before_astro` | Use fixed time if it is before the astro event        |
| `astro_if_before_fixed` | Use astro event if it is before the fixed time        |
| `fixed_if_after_astro`  | Use fixed time if it is after the astro event         |
| `astro_if_after_fixed`  | Use astro event if it is after the fixed time         |
| `earliest`              | Use whichever comes first (fixed time or astro event) |
| `latest`                | Use whichever comes last (fixed time or astro event)  |

Astronomical events support an offset of up to +/- 720 minutes (12 hours) from sunrise or sunset.

### Editing

1. Click **Add Event** to create a new schedule event
2. Select the **weekdays** for the event
3. Choose a **condition type** and set the trigger time
4. Select **target channels** for the device
5. Set the **level** and optional parameters (duration, ramp time)
6. Click **Save** to write the schedule to the device

### Domain-Specific Controls

The card adapts its UI based on the device type:

- **Switch**: Simple on/off toggle (level 0.0 or 1.0)
- **Light**: Brightness slider (0–100%) with optional ramp time for smooth dimming
- **Cover**: Position slider (0–100%) with optional slat position (level_2)
- **Valve**: Opening slider (0–100%) with optional duration

---

## Schedule Data Format

The schedule data follows the same format as the `homematicip_local.set_schedule` action. See [Week Profiles — Non-Climate Schedule Actions](week_profile.md#non-climate-schedule-actions) for the complete field reference and examples.

### Quick Example

```yaml
schedule_data:
  "1":
    weekdays: [MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY]
    time: "06:30"
    condition: fixed_time
    target_channels: ["1_1"]
    level: 0.8
    duration: 1min
  "2":
    weekdays: [SATURDAY, SUNDAY]
    time: "08:00"
    condition: astro
    astro_type: sunrise
    astro_offset_minutes: 30
    target_channels: ["1_1"]
    level: 0.5
    duration: 30min
```

---

## Troubleshooting

### Card not appearing

1. Clear browser cache (Ctrl+F5)
2. Verify the resource is added: **Settings** → **Dashboards** → **Resources**
3. Check the file is accessible at `/local/homematicip-local-schedule-card.js`

### Entity not listed

1. Verify the entity has schedule support (check for a Week Profile sensor entity on the device)
2. Ensure the entity domain is supported (switch, light, cover, or valve)

### Changes not saving

1. Check Home Assistant logs for service call errors
2. Ensure the CCU and device are reachable
3. Wait for CONFIG_PENDING to clear on the device

---

## See Also

- [Week Profiles](week_profile.md) — Schedule data format, actions, and examples
- [Climate Schedule Card](climate_schedule_card.md) — Schedule card for thermostats
- [Device Configuration Panel](config_panel.md) — Full device configuration UI
