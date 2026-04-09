# Status Cards

The **HomematicIP Local Status Cards** are a set of three Lovelace cards for monitoring the health, device status, and messages of your Homematic system directly on your Home Assistant dashboard.

---

## Installation

The cards are automatically available when the HomematicIP Local integration is loaded — no manual installation required. They appear in the Lovelace card picker.

---

## Cards Overview

| Card              | Element Name                     | Purpose                                             |
| ----------------- | -------------------------------- | --------------------------------------------------- |
| **System Health** | `homematicip-system-health-card` | Integration health, device statistics, DC/CS levels |
| **Device Status** | `homematicip-device-status-card` | Device problem overview with filtering              |
| **Messages**      | `homematicip-messages-card`      | Service messages and alarms with acknowledgment     |

All cards require an `entry_id` which identifies your HomematicIP Local config entry. The card editors provide a dropdown to select the entry.

---

## System Health Card {#system-health}

Displays the overall health of your Homematic system at a glance.

### What it shows

- **Health Score**: Percentage (0–100%) indicating integration health. 100% = all interfaces connected.
- **Device Statistics**: Total devices, unreachable devices (red if > 0), firmware-updatable devices (orange if > 0).
- **Duty Cycle / Carrier Sense**: Per radio module, HAP, or LAN gateway. These values come from `DUTY_CYCLE_LEVEL` and `CARRIER_SENSE_LEVEL` sensor entities.
- **Incidents** (optional): Recent communication events between the integration and the CCU.

### Duty Cycle and Carrier Sense

**Duty Cycle (DC)** indicates how much of the available radio transmission time has been used. Regulatory limits restrict each device to 1% transmission time per hour.

| DC Level | Color  | Meaning                                   |
| -------- | ------ | ----------------------------------------- |
| < 60%    | Normal | Plenty of transmission capacity remaining |
| 60–79%   | Orange | Getting close to the limit                |
| ≥ 80%    | Red    | Near capacity — reduce radio traffic      |

**Carrier Sense (CS)** measures how much radio activity is detected on the frequency band — including interference from other devices (neighbors, Wi-Fi, etc.).

| CS Level | Color  | Meaning                                           |
| -------- | ------ | ------------------------------------------------- |
| < 10%    | Normal | Clean radio environment                           |
| ≥ 10%    | Red    | Significant interference — may affect reliability |

!!! tip
High Carrier Sense values indicate external radio interference. Consider relocating your radio module or HAP away from interference sources (Wi-Fi routers, USB 3.0 devices, microwave ovens).

### Configuration

```yaml
type: custom:homematicip-system-health-card
entry_id: <your-config-entry-id>
```

| Option           | Type    | Default         | Description                            |
| ---------------- | ------- | --------------- | -------------------------------------- |
| `entry_id`       | string  | — (required)    | HomematicIP Local config entry ID      |
| `title`          | string  | "System Health" | Custom card title                      |
| `show_incidents` | boolean | `false`         | Show incidents list                    |
| `max_incidents`  | number  | `5`             | Maximum number of incidents to display |
| `poll_interval`  | number  | `30`            | Polling interval in seconds            |

The polling interval is adaptive: 5 seconds when the system is not stable, the configured interval (minimum 30s) when running normally.

---

## Device Status Card {#device-status}

Shows which devices have problems — unreachable, low battery, or pending configuration.

### What it shows

- **Problem count badge**: Red badge showing number of devices with issues (or green "OK" if none).
- **Device list**: Each problem device with icon, name, model, and issue description.
- **Summary**: Count of remaining OK devices (when filtering by problems).

### Filter modes

| Filter           | Shows                                                     |
| ---------------- | --------------------------------------------------------- |
| `problems`       | Only devices with any issue (default)                     |
| `all`            | All devices — problems first, then healthy devices with ✓ |
| `unreachable`    | Only unreachable devices                                  |
| `low_battery`    | Only devices with low battery                             |
| `config_pending` | Only devices with pending configuration                   |

### Configuration

```yaml
type: custom:homematicip-device-status-card
entry_id: <your-config-entry-id>
filter: problems
max_devices: 10
```

| Option             | Type    | Default      | Description                                |
| ------------------ | ------- | ------------ | ------------------------------------------ |
| `entry_id`         | string  | — (required) | HomematicIP Local config entry ID          |
| `title`            | string  | Auto         | Custom card title                          |
| `filter`           | string  | `"problems"` | Filter mode (see table above)              |
| `show_model`       | boolean | `true`       | Show device model in secondary text        |
| `max_devices`      | number  | `10`         | Maximum devices to display (0 = unlimited) |
| `poll_interval`    | number  | `60`         | Polling interval in seconds                |
| `interface_filter` | string  | —            | Only show devices from this interface      |

---

## Messages Card {#messages}

Displays service messages and alarm messages from the CCU with the ability to acknowledge them.

### What it shows

- **Alarm messages** (red): Critical notifications like sabotage detection or sensor errors. Each shows the device name, description, counter, and timestamp.
- **Service messages** (orange): System notifications like unreachable devices, low battery, or config pending. Shows message code and counter.
- **Badges**: Alarm count (red), service message count (orange), or "OK" (green) when empty.

### Acknowledging messages

- **Alarm messages**: Always have an acknowledge button.
- **Service messages**: Only show an acknowledge button if the message is quittable (the CCU determines this).

After acknowledging, the message is removed from the list immediately. The next polling cycle confirms the change.

### Configuration

```yaml
type: custom:homematicip-messages-card
entry_id: <your-config-entry-id>
```

| Option           | Type    | Default      | Description                          |
| ---------------- | ------- | ------------ | ------------------------------------ |
| `entry_id`       | string  | — (required) | HomematicIP Local config entry ID    |
| `title`          | string  | Auto         | Custom card title                    |
| `show_alarms`    | boolean | `true`       | Show alarm messages section          |
| `show_service`   | boolean | `true`       | Show service messages section        |
| `max_messages`   | number  | `10`         | Maximum messages to display per type |
| `show_timestamp` | boolean | `true`       | Show message timestamps              |
| `poll_interval`  | number  | `30`         | Polling interval in seconds          |

---

## Dashboard Example

A typical monitoring setup uses all three cards:

```yaml
# System health overview
type: custom:homematicip-system-health-card
entry_id: <your-entry-id>

# Problem devices
type: custom:homematicip-device-status-card
entry_id: <your-entry-id>
filter: problems
max_devices: 5

# Active messages
type: custom:homematicip-messages-card
entry_id: <your-entry-id>
```

---

## Troubleshooting

### Cards not appearing

1. Clear browser cache (Ctrl+F5)
2. Ensure the HomematicIP Local integration is loaded and running
3. Check Home Assistant logs for frontend registration errors

### No data displayed

1. Verify the `entry_id` is correct (use the editor dropdown to select it)
2. Check that the integration is fully started (central state should be "RUNNING")
3. Check Home Assistant logs for WebSocket errors

### Duty Cycle / Carrier Sense not showing

1. Ensure your radio module, HAP, or LAN gateway exposes `DUTY_CYCLE_LEVEL` and `CARRIER_SENSE_LEVEL` sensor entities
2. Check that these entities are enabled in Home Assistant (they are diagnostic entities, enabled by default)
3. Verify the entities belong to the same config entry selected in the card

---

## See Also

- [Device Configuration Panel](config_panel.md) — Full device configuration UI with detailed dashboard
- [Climate Schedule Card](climate_schedule_card.md) — Thermostat schedule editor
- [Schedule Card](schedule_card.md) — Device schedule editor
