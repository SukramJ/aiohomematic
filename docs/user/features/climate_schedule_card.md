# Climate Schedule Card

The **HomematicIP Local Climate Schedule Card** is a custom Lovelace card for displaying and editing thermostat schedules directly in the Home Assistant dashboard.

---

## Features

- **Visual week schedule**: See the entire week at a glance with color-coded temperature blocks
- **Interactive editing**: Click any day to open the editor with time and temperature controls
- **Profile switching**: Switch between schedule profiles (P1–P6) via dropdown
- **Active profile indicator**: The currently active profile on the device is marked with an asterisk (\*)
- **Multi-entity support**: Switch between multiple thermostats in a single card
- **Custom profile names**: Assign meaningful names to profiles (e.g. "Comfort", "Eco", "Away")
- **Responsive design**: Works on desktop and mobile
- **Visual configuration**: Configure via the UI editor — no YAML required
- **Bilingual**: English and German

---

## Installation

The card is automatically available when the HomematicIP Local integration is loaded — no manual installation required. It appears in the Lovelace card picker under **HomematicIP Local Climate Schedule Card**.

!!! note "Migrating from HACS"
If you previously installed this card via HACS, the integration-bundled version detects this and skips duplicate registration. You can remove the HACS card resource at your convenience: **HACS** → **Frontend** → remove the climate schedule card. Both versions coexist without conflicts during the transition.

---

## Device Support

This card works with all Homematic devices that have week profile support and multiple profiles:

- HomematicIP thermostats (e.g. HmIP-eTRV, HmIP-eTRV-2, HmIP-BWTH, HmIP-WTH)
- Homematic thermostats via thermostat groups (HM-CC-RT-DN only via group)

---

## Configuration

### Basic

```yaml
type: custom:homematicip-local-climate-schedule-card
entity: climate.living_room_thermostat
```

### Multiple Entities

```yaml
type: custom:homematicip-local-climate-schedule-card
entities:
  - climate.living_room
  - climate.bedroom
  - climate.office
```

When multiple entities are defined, a dropdown appears in the card header to switch between them.

### Custom Names and Profile Names

```yaml
type: custom:homematicip-local-climate-schedule-card
entities:
  - entity: climate.living_room
    name: "Living Room"
    profile_names:
      P1: "Comfort"
      P2: "Eco"
      P3: "Night"
  - entity: climate.bedroom
    name: "Bedroom"
    profile_names:
      P1: "Normal"
      P2: "Away"
  - climate.office # Uses friendly_name from HA
```

### All Options

| Option                  | Type              | Default        | Description                              |
| ----------------------- | ----------------- | -------------- | ---------------------------------------- |
| `entity`                | string            | —              | Single climate entity                    |
| `entities`              | string[] or array | —              | List of climate entities                 |
| `name`                  | string            | Entity name    | Custom card header name                  |
| `profile`               | string            | Active profile | Force display of a specific profile      |
| `show_profile_selector` | boolean           | `true`         | Show/hide the profile dropdown           |
| `editable`              | boolean           | `true`         | Enable/disable editing                   |
| `show_temperature`      | boolean           | `true`         | Show temperature values on blocks        |
| `show_gradient`         | boolean           | `false`        | Show color gradient between temperatures |
| `temperature_unit`      | string            | `°C`           | Temperature unit display                 |
| `hour_format`           | string            | `24`           | Time format: `12` or `24` hour           |
| `language`              | string            | Auto-detect    | Force language: `en` or `de`             |

#### Entity Options

Each entity in the `entities` array can be a string or an object:

| Option          | Type             | Description                                      |
| --------------- | ---------------- | ------------------------------------------------ |
| `entity`        | string           | Climate entity ID (required)                     |
| `name`          | string           | Custom display name for the dropdown             |
| `profile_names` | Record\<string\> | Custom names for profiles (e.g. `P1: "Comfort"`) |

---

## Usage

### Viewing Schedules

The card displays the weekly schedule as color-coded temperature blocks:

| Color Range  | Temperature | Description |
| ------------ | ----------- | ----------- |
| Blue         | < 10°C      | Cold        |
| Light Blue   | 10–14°C     | Cool        |
| Cyan         | 14–17°C     | Mild Cool   |
| Green        | 17–19°C     | Comfort Low |
| Light Green  | 19–21°C     | Comfort     |
| Light Orange | 21–23°C     | Warm        |
| Orange       | 23–25°C     | Warmer      |
| Deep Orange  | >= 25°C     | Hot         |

Hover over a block to see the exact time range and temperature.

### Editing Schedules

1. Click on any **day row** in the week view
2. The editor opens showing all time slots for that day
3. Adjust the **base temperature** at the top of the editor (background temperature for uncovered times)
4. Modify **end times** and **temperatures** for each block
5. Click **+ Add Time Block** to add a heating period
6. Click the **trash icon** to remove a block
7. Click **Save** to apply changes to the thermostat

!!! info "Automatic Block Merging"
Consecutive time blocks with the same temperature are automatically merged when saving. For example, 06:00–08:00 at 22°C followed by 08:00–10:00 at 22°C becomes a single 06:00–10:00 block at 22°C.

### Profile Switching

Use the profile dropdown to switch between P1–P6. The currently active profile on the device is marked with an asterisk (\*).

!!! note "Viewing vs. Activating"
The profile dropdown in the card is for **viewing and editing** different profiles. To change the active profile on the device, use the `homematicip_local.set_current_schedule_profile` action or the [Device Configuration Panel](config_panel.md).

### Schedule Format

The card uses the **Simple Format**: a base temperature plus explicit heating periods. Only periods that differ from the base temperature are stored.

**Example**: Base 17°C with one heating period:

| Time          | Temperature | Source           |
| ------------- | ----------- | ---------------- |
| 00:00 – 06:00 | 17.0°C      | Base temperature |
| 06:00 – 22:00 | 21.0°C      | Heating period   |
| 22:00 – 24:00 | 17.0°C      | Base temperature |

See [Week Profiles](week_profile.md) for the full schedule data format and all available actions.

---

## Permissions

By default, only admin users can edit schedules. To allow non-admin household members to edit schedules, enable this in the integration options under **Schedule editing**. See [Schedule Editing for Non-Admin Users](config_panel.md#non-admin-schedules) for details.

---

## Troubleshooting

### Card not appearing

1. Clear browser cache (Ctrl+F5)
2. Ensure the HomematicIP Local integration is loaded and running
3. Check Home Assistant logs for frontend registration errors

### Entity not found

1. Verify the climate entity ID is correct
2. Ensure the entity has schedule attributes from the HomematicIP Local integration
3. Check Home Assistant logs for errors

### Changes not saving

1. Check Home Assistant logs for WebSocket errors
2. Ensure the CCU and thermostat are reachable
3. Wait for CONFIG_PENDING to clear on the device

---

## See Also

- [Week Profiles](week_profile.md) — Schedule data format, actions, and examples
- [Schedule Card](schedule_card.md) — Schedule card for switches, lights, covers, and valves
- [Status Cards](status_cards.md) — System health, device status, and messages cards
- [Device Configuration Panel](config_panel.md) — Full device configuration UI
