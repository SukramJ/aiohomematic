# Device Configuration Panel

The Homematic Device Configuration Panel is a sidebar panel in Home Assistant for editing device parameters, managing direct links between devices, and configuring schedules — directly from the Home Assistant UI.

!!! note "Admin Only"
The configuration panel is only visible to admin users.

---

## Enabling the Panel

1. Go to **Settings** → **Devices & Services**
2. Find **Homematic(IP) Local for OpenCCU** and click **Configure**
3. Select **Advanced Options**
4. Enable **Device Configuration Panel**
5. Click **Submit**

The panel appears in the Home Assistant sidebar as **HM Device Configuration** (or **HM Gerätekonfiguration** in German).

---

## Device Overview

The panel shows all configurable devices grouped by interface (HmIP-RF, BidCos-RF, BidCos-Wired). Each device entry displays:

| Information         | Description                               |
| ------------------- | ----------------------------------------- |
| **Device name**     | Name as configured on the CCU             |
| **Model**           | Device model number (e.g. HmIP-eTRV-2)    |
| **Reachability**    | Whether the device is currently reachable |
| **Signal strength** | RSSI values for device and peer           |
| **Firmware**        | Current firmware version                  |
| **Low battery**     | Battery status indicator                  |
| **Duty cycle**      | RF duty cycle usage                       |
| **Config pending**  | Whether a configuration change is waiting |

---

## Editing Device Parameters

The panel provides a form-based editor for device MASTER parameters — the configuration values stored on the device itself (not runtime state values).

### Workflow

1. Select a device from the device list
2. Choose a channel to configure
3. The panel auto-generates a form with appropriate controls:
   - **Sliders** for numeric parameters (e.g. temperature offset)
   - **Toggles** for boolean parameters (e.g. button lock)
   - **Dropdowns** for enum parameters (e.g. display mode)
4. Adjust values as needed
5. Click **Save** to write changes to the device via the CCU

!!! warning "Device Storage"
Writing to device MASTER parameters uses the device's internal storage. Excessive writes can degrade the device's EEPROM. The panel is designed for configuration changes, not for frequent state updates.

### Session Management

Changes are tracked in an in-memory session with undo/redo support:

- **Undo**: Revert the last parameter change
- **Redo**: Re-apply a reverted change
- **Save**: Write all pending changes to the device
- **Discard**: Discard all pending changes without writing

### Parameter Filtering

The panel shows only parameters that have a known CCU translation — matching the behavior of the CCU WebUI's easymode. Technical internal parameters without human-readable names are hidden.

---

## Export / Import

### Export

Export the current paramset configuration of a channel as a JSON file. This serves as a backup or as a template for other devices.

### Import

Import a previously exported JSON configuration into a channel of the **same device model**. Only writable parameters that exist on the target channel are applied.

### Copy Paramset

Copy parameter values from one channel to another channel on the same device model. The panel automatically filters to writable parameters present on the target.

---

## Direct Links (Direktverknüpfungen)

Direct links (also called peerings) connect two device channels for direct communication without CCU involvement — for example, linking a wall switch to a light actuator.

### Browsing Links

Select a device to see all existing direct links grouped by channel. Each link shows:

- Linked partner device and channel
- Link direction (sender/receiver)
- Channel type labels

### Creating Links

1. Click **Add Link** on a channel
2. The wizard shows compatible channels based on role filtering
3. Select the partner device and channel
4. Confirm to create the link on the CCU

### Configuring Links

Click on an existing link to edit its parameters:

- **SHORT/LONG keypress tabs**: Configure behavior for short and long button presses separately
- **Profile selection**: Choose from predefined easymode profiles (e.g. Dimmer on/off, Staircase light, Toggle)
- **Time parameters**: Combined time selectors for TIME_BASE/TIME_FACTOR pairs
- **Level parameters**: Percent sliders with "Last value" support

### Removing Links

Select a link and click **Remove** to delete the direct link from the CCU.

---

## Schedule Management

The panel integrates schedule management for devices with week profile support. See [Week Profiles](week_profile.md) for the schedule data format and available actions.

### Climate Schedules

For thermostat devices:

- View and edit climate schedules per profile (P1–P6) and weekday
- Switch the active profile
- Visual schedule editor with temperature and time controls

### Device Schedules

For non-climate devices (switches, lights, covers, valves):

- View and edit event-based schedules
- Configure timing, target channels, and levels

!!! tip "Schedule Cards"
For a more visual schedule editing experience, use the dedicated Lovelace cards:

    - [Climate Schedule Card](climate_schedule_card.md) for thermostats
    - [Schedule Card](schedule_card.md) for switches, lights, covers, and valves

---

## Change History

The panel keeps a persistent log of all paramset changes (manual edits, imports, copies) with:

- Timestamp of the change
- Device and channel affected
- Old and new values for each parameter
- Source of the change (manual, import, copy)

The history is stored via Home Assistant's storage system with a 500-entry FIFO limit per config entry.

---

## Deep-Linking

Navigate directly to a specific device, channel, or link view via URL hash parameters. The panel supports browser back/forward navigation for seamless browsing.

---

## Troubleshooting

### Panel not visible in sidebar

1. Verify the panel is enabled in Advanced Options
2. Confirm you are logged in as an admin user
3. Reload the browser (Ctrl+F5)

### Parameters not saving

1. Check that the device is reachable (not UNREACH)
2. Check Home Assistant logs for XML-RPC errors
3. Wait for CONFIG_PENDING to clear on the device

### Empty parameter list for a channel

- The channel may not have visible MASTER parameters
- Parameters without CCU translations are filtered out (matching CCU WebUI behavior)

---

## See Also

- [Week Profiles](week_profile.md) — Schedule data format and actions
- [Climate Schedule Card](climate_schedule_card.md) — Visual thermostat schedule editor
- [Schedule Card](schedule_card.md) — Visual device schedule editor
- [Actions Reference](homeassistant_actions.md) — All available service actions
