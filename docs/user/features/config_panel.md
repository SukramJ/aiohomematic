# Device Configuration Panel

The Homematic Device Configuration Panel is a sidebar panel in Home Assistant for editing device parameters, managing direct links between devices, and configuring schedules — directly from the Home Assistant UI.

!!! note "Admin Only"
The configuration panel is only visible to Home Assistant admin users. Non-admin users can edit device schedules via the [Climate Schedule Card](climate_schedule_card.md) and [Schedule Card](schedule_card.md) when enabled in the integration options (see [Schedule Editing for Non-Admin Users](#non-admin-schedules)).

---

## Enabling the Panel

1. Go to **Settings** → **Devices & Services**
2. Find **Homematic(IP) Local for OpenCCU** and click **Configure**
3. Select **Advanced Options**
4. Enable **Device Configuration Panel**
5. Click **Submit**

The panel appears in the Home Assistant sidebar as **HM Device Configuration** (or **HM Gerätekonfiguration** in German).

---

## Panel Structure {#panel-structure}

The panel is organized into three main tabs:

| Tab             | Purpose                                                |
| --------------- | ------------------------------------------------------ |
| **Devices**     | Browse, configure, and manage your Homematic devices   |
| **Integration** | Monitor integration health, performance, and incidents |
| **OpenCCU**     | Manage the CCU hardware, RF interfaces, and firmware   |

---

## Devices Tab {#devices}

### Device List {#device-list}

The device list shows all configurable devices grouped by their RF interface (HmIP-RF, BidCos-RF, BidCos-Wired). Use the search bar to filter by name, address, or model.

Each device entry displays:

| Information     | Description                              |
| --------------- | ---------------------------------------- |
| **Device name** | Name as configured on the CCU            |
| **Model**       | Device model number (e.g. HmIP-eTRV-2)   |
| **Address**     | Unique hardware identifier of the device |
| **Channels**    | Number of functional units on the device |

**Status icons** indicate the device's current state:

| Icon                                | Meaning               |
| ----------------------------------- | --------------------- |
| :material-check-circle:{ .green }   | Device is reachable   |
| :material-close-circle:{ .red }     | Device is unreachable |
| :material-battery-alert:{ .orange } | Low battery           |
| :material-clock-alert:{ .orange }   | Configuration pending |

!!! tip "What is an interface?"
An interface is the radio protocol used by the device. **HmIP-RF** is used by modern HomematicIP devices, **BidCos-RF** by classic Homematic devices, and **BidCos-Wired** by wired devices. The interface determines how the CCU communicates with the device.

Click on a device to open the [Device Detail](#device-detail) view.

---

### Device Detail {#device-detail}

The device detail view shows all information about a single device and provides access to its channels.

**Device information:**

| Field        | Description                                 |
| ------------ | ------------------------------------------- |
| **Model**    | Device type (e.g. HmIP-eTRV-2)              |
| **Firmware** | Software version installed on the device    |
| **Address**  | Hardware identifier (e.g. `001FD9499D7856`) |

**Available actions:**

- **Direct Links** — Manage peer-to-peer connections to other devices ([more info](#direct-links))
- **Schedules** — Edit time-based automation schedules ([more info](#schedules))
- **Change History** — View a log of past configuration changes ([more info](#change-history))

#### Channels {#channels}

A device consists of one or more **channels**. Each channel represents a distinct function of the device — for example, a two-button switch has separate channels for each button.

| Channel                     | Purpose                                                                |
| --------------------------- | ---------------------------------------------------------------------- |
| **Device Config**           | Device-wide settings (e.g. display backlight, button lock)             |
| **Channel 0 (Maintenance)** | Health data: signal strength (RSSI), battery, reachability, duty cycle |
| **Channel 1, 2, ...**       | Functional channels (e.g. relay, dimmer, sensor, thermostat)           |

Each channel shows its **type** (e.g. SWITCH, DIMMER, CLIMATECONTROL_REGULATOR) and offers **Configure**, **Export**, and **Import** buttons.

##### Maintenance Channel {#maintenance}

Channel 0 is a special maintenance channel present on every device. It shows:

| Field              | Meaning                                                                                                                                                                                                        |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **RSSI Device**    | Signal strength from the CCU to the device (in dBm). Values closer to 0 are better. Typical range: -40 (excellent) to -100 (poor).                                                                             |
| **RSSI Peer**      | Signal strength from the device to its communication partner. Shows "—" if no direct links exist.                                                                                                              |
| **DC Limit**       | Whether the device has reached its [duty cycle](https://en.wikipedia.org/wiki/Duty_cycle) limit. If "Yes", the device temporarily cannot send radio commands (regulatory limit to prevent radio interference). |
| **Low Battery**    | Whether the battery needs replacement.                                                                                                                                                                         |
| **Reachable**      | Whether the CCU can communicate with the device.                                                                                                                                                               |
| **Config Pending** | Whether a configuration change is waiting to be applied to the device (the device may be in sleep mode).                                                                                                       |

---

### Editing Parameters {#editing-parameters}

The parameter editor provides a form-based interface for editing device configuration values (MASTER paramset).

#### Workflow

1. Select a device from the device list
2. Choose a channel to configure
3. The panel auto-generates a form with appropriate controls:
   - **Sliders** for numeric parameters (e.g. temperature offset)
   - **Toggles** for boolean parameters (e.g. button lock)
   - **Dropdowns** for enum parameters (e.g. display mode)
   - **Presets** for common value combinations (e.g. time intervals)
4. Adjust values as needed
5. Click **Save** to write changes to the device via the CCU

!!! warning "Device Storage"
Writing to device MASTER parameters uses the device's internal storage. Excessive writes can degrade the device's EEPROM. The panel is designed for configuration changes, not for frequent state updates.

#### What is a Paramset? {#paramset}

A **paramset** is a collection of configuration parameters stored on the device. The **MASTER** paramset contains device settings that persist across restarts — for example, the temperature offset of a thermostat or the LED brightness of a switch. These are not runtime values (like the current temperature), but configuration values that change the device's behavior.

#### Session Management {#session}

Changes are tracked in an in-memory session with undo/redo support:

- **Undo**: Revert the last parameter change
- **Redo**: Re-apply a reverted change
- **Reset to Defaults**: Restore factory default values for all parameters
- **Discard**: Discard all pending changes without writing
- **Save**: Opens a confirmation dialog showing all changes (old → new values) before applying

#### Easymode {#easymode}

The panel uses **Easymode** to simplify the parameter editor:

- **Conditional visibility**: Some parameters are only shown when relevant (e.g. a threshold parameter only appears when the related feature is enabled)
- **Preset dropdowns**: Common value combinations are offered as a dropdown (e.g. selecting a "Staircase light" mode applies multiple parameters at once)
- **Grouped parameters**: Related parameters are combined into a single control

These simplifications match the behavior of the CCU WebUI — only parameters with human-readable names are shown.

#### Parameter Validation {#validation}

The panel validates your changes in real-time:

- **Range checks**: Values must be within the allowed min/max range
- **Cross-validation**: Related parameters are checked together (e.g. maximum must be greater than minimum)
- Invalid fields are highlighted with an error message

---

### Export / Import {#export-import}

#### Export

Export the current paramset configuration of a channel as a JSON file. This serves as a backup or as a template for other devices of the same model.

#### Import

Import a previously exported JSON configuration into a channel of the **same device model**. Only writable parameters that exist on the target channel are applied.

---

### Direct Links {#direct-links}

Direct links (also called **peerings** or **Direktverknüpfungen**) connect two device channels for direct peer-to-peer communication — without the CCU as intermediary.

!!! example "Typical use case"
A wall switch directly controls a light actuator. When you press the switch, the command goes directly to the light via radio — even if the CCU is offline.

#### Advantages of Direct Links

- **Fast response**: No detour through the CCU
- **Reliable**: Works even when the CCU is temporarily unavailable
- **Configurable**: Different behavior for short and long button presses

#### Browsing Links

Select a device to see all existing direct links grouped by channel. Each link shows:

- **Direction**: Whether the device is the sender or receiver
- **Partner**: The linked device, model, and channel
- **Link name**: Optional user-provided label

#### Creating Links

1. Click **Add Link** on a device
2. Select the channel on your device
3. Choose whether this device is the **sender** or **receiver**
4. Search and select the partner device and channel (only compatible channels are shown)
5. Optionally enter a link name
6. Confirm to create the link

#### Configuring Links {#link-config}

Click on an existing link to edit its parameters:

- **Profile selection**: Choose from predefined easymode profiles (e.g. "Dimmer on/off", "Staircase light", "Toggle") — each profile pre-configures parameters for a common use case
- **Short/Long keypress tabs**: Configure different behavior for short and long button presses
- **Time parameters**: Combined time selectors for delays and durations
- **Level parameters**: Percent sliders with "Last value" support (use the value that was last set)

#### Removing Links

Select a link and click **Delete** to remove the direct link from the CCU.

---

### Schedules {#schedules}

The panel integrates schedule management for devices with week profile support.

#### Climate Schedules {#climate-schedules}

For thermostat devices (e.g. HmIP-eTRV, HmIP-WTH):

- **Visual weekly grid**: Color-coded temperature blocks for each day of the week
- **Profile selection**: Switch between up to 6 schedule profiles (P1–P6)
- **Active profile**: Set which profile the thermostat actually follows
- **Per-day editing**: Click a day to add, move, or delete temperature blocks
- **Copy/Paste**: Copy a day's schedule to other days
- **Undo/Redo**: Revert or re-apply changes
- **Import/Export**: Save and restore schedules as JSON

!!! info "Profiles"
A **profile** is a complete weekly schedule. Most thermostats support multiple profiles (e.g. "Normal", "Energy saving", "Holiday"). The **active profile** is the one the device currently follows. Selecting a different profile in the dropdown loads its data for viewing/editing and activates it on the device.

#### Device Schedules {#device-schedules}

For non-climate devices (switches, lights, covers, valves):

- **Event list**: Shows all scheduled events grouped by weekday
- **Event editor**: Configure each event with:
  - **Time**: Fixed time (e.g. 06:00) or astronomical (relative to sunrise/sunset)
  - **Weekdays**: Which days the event applies to
  - **Level**: Target state (On/Off for switches, 0–100% for dimmers/covers)
  - **Duration**: How long the action lasts (optional)
  - **Ramp time**: Gradual transition time for lights (optional)
  - **Target channels**: Which channels to control (for multi-channel devices)

!!! tip "Schedule Cards"
For a more visual schedule editing experience, use the dedicated Lovelace cards:

    - [Climate Schedule Card](climate_schedule_card.md) for thermostats
    - [Schedule Card](schedule_card.md) for switches, lights, covers, and valves

---

### Change History {#change-history}

The change history keeps a persistent log of all parameter changes made through the panel.

Each entry shows:

| Field          | Description                                      |
| -------------- | ------------------------------------------------ |
| **Timestamp**  | When the change was made                         |
| **Device**     | Device name and model                            |
| **Channel**    | Channel address that was modified                |
| **Parameters** | Number of parameters changed                     |
| **Source**     | How the change was made: Manual, Import, or Copy |

Click an entry to expand the details and see each parameter's old and new value.

!!! info "Storage"
The history is stored via Home Assistant's storage system with a 500-entry limit per config entry. When the limit is reached, the oldest entries are removed automatically.

The **Clear History** button permanently deletes all entries (with confirmation).

---

## Integration Tab {#integration}

The Integration dashboard monitors the health and performance of the Homematic(IP) Local integration.

### System Health {#system-health}

Shows the current state of the integration:

| Field             | Description                                                                                                                                                                                         |
| ----------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Central State** | The integration's connection status. "RUNNING" means everything is operational. Other states like "STARTUP" or "RECONNECT" indicate the integration is initializing or recovering.                  |
| **Health Score**  | A percentage (0–100%) indicating overall device communication quality. 100% means all devices are reachable and communicating normally. A lower score means some devices have communication issues. |

### Device Statistics {#device-statistics}

A quick overview of your device fleet:

| Field                  | Description                                                |
| ---------------------- | ---------------------------------------------------------- |
| **Total Devices**      | Number of devices managed by this integration              |
| **Unreachable**        | Devices currently not responding (shown as warning if > 0) |
| **Firmware Updatable** | Devices with available firmware updates                    |

### Command Throttle {#command-throttle}

The **command throttle** is a protective mechanism that limits how fast commands are sent to the CCU.

!!! question "Why is this needed?"
Homematic devices communicate via radio. If too many commands are sent in quick succession, they can interfere with each other — causing missed commands or delayed responses. The throttle ensures commands are spaced out, especially during automations or scenes that control many devices at once.

| Field           | Description                                                                        |
| --------------- | ---------------------------------------------------------------------------------- |
| **Enabled**     | Whether the throttle is active                                                     |
| **Interval**    | Minimum time between commands (in seconds)                                         |
| **Queue Size**  | Number of commands currently waiting to be sent                                    |
| **Throttled**   | Whether commands are currently being delayed                                       |
| **Burst Count** | Number of commands that can be sent in quick succession before throttling kicks in |

Under normal operation, the queue is empty and "Throttled" shows "No". If the queue grows or throttling is active, it means many commands are being processed — this is expected during scenes or large automations.

### Incidents {#incidents}

**Incidents** are logged communication events that occurred between the integration and the CCU or devices. These are **not bugs** and typically **do not require any action** from you.

!!! warning "Incidents are not errors"
An incident does **not** mean something is broken. It is a normal diagnostic log entry — similar to a flight recorder. Common incidents include:

    - A device temporarily not responding (e.g. battery-powered device in sleep mode)
    - A brief communication timeout during heavy radio traffic
    - A device reconnecting after a power cycle

    These events are automatically resolved and logged for informational purposes only. **Do not open a GitHub issue** because of incidents — they are expected behavior in a wireless environment.

If the incident list is empty, that's ideal — it means no communication irregularities were recorded.

The **Clear Incidents** button removes all logged incidents.

### Cache Management {#cache}

The integration caches device metadata (parameter descriptions, channel information) to speed up startup. If you suspect the cache is outdated (e.g. after a CCU firmware update), you can clear it:

- **Clear Cache**: Purges all cached device data. The integration will re-fetch everything from the CCU on the next restart.

!!! note
Clearing the cache does not affect your device configurations or automations. It only forces the integration to re-read device metadata from the CCU.

---

## OpenCCU Tab {#openccu}

The OpenCCU dashboard provides direct access to CCU system administration features. It is organized into sub-tabs.

### System Information {#system-info}

Shows details about the connected CCU hardware:

| Field            | Description                                |
| ---------------- | ------------------------------------------ |
| **Name**         | CCU system name                            |
| **Model**        | Hardware model (e.g. CCU3, RaspberryMatic) |
| **Version**      | CCU firmware version                       |
| **Serial**       | Hardware serial number                     |
| **Hostname**     | Network hostname                           |
| **Interfaces**   | Configured radio interfaces                |
| **Auth Enabled** | Whether CCU authentication is active       |

**Actions:**

- **Create Backup**: Downloads a CCU configuration backup file. Shows progress and reports filename and size on completion.

### Messages {#messages}

The Messages sub-tab shows three categories of system notifications. A badge on the tab indicates the total number of active messages.

#### Inbox {#inbox}

New devices that have been detected but not yet accepted into the system. Click **Accept** to add a device — you'll be asked to confirm and optionally provide a name.

#### Service Messages {#service-messages}

Service messages are system notifications from the CCU about device states that may need attention:

| Type               | Meaning                                                 |
| ------------------ | ------------------------------------------------------- |
| **Generic**        | General notification                                    |
| **Sticky**         | Persistent notification that remains until acknowledged |
| **Config Pending** | A device is waiting for a configuration to be applied   |
| **Alarm**          | A warning condition (e.g. low battery, sabotage)        |
| **Update Pending** | A firmware update is available                          |
| **Communication**  | A communication issue was detected                      |

Each message shows the device name, address, message type, description, timestamp, and a counter (how often it occurred). **Quittable** messages can be acknowledged with the **Acknowledge** button.

!!! tip
Most service messages resolve themselves (e.g. a battery-powered device reconnects after waking up). The messages are informational — they don't necessarily require immediate action.

#### Alarm Messages {#alarm-messages}

Alarm messages are critical notifications that indicate a condition requiring attention (e.g. sabotage detection, sensor errors). Each alarm shows:

- Device name and description
- Last trigger time
- Occurrence counter
- **Acknowledge** button to clear the alarm

### Signal Quality {#signal-quality}

A sortable and filterable table showing the radio signal quality of all devices:

| Column        | Description                                   |
| ------------- | --------------------------------------------- |
| **Device**    | Device name                                   |
| **Model**     | Device model                                  |
| **Interface** | Radio protocol (HmIP-RF, BidCos-RF)           |
| **Reachable** | Whether the device is currently responding    |
| **RSSI**      | Signal strength in dBm (closer to 0 = better) |
| **Battery**   | Battery status (OK or Low)                    |

Use the filter bar (shown when more than 10 devices) to search by name/model or filter by interface, reachability, or battery status.

!!! info "Understanding RSSI values"
| Range | Quality |
| ----- | ------- |
| -40 to 0 dBm | Excellent |
| -60 to -40 dBm | Good |
| -80 to -60 dBm | Acceptable |
| -100 to -80 dBm | Poor — consider moving the device closer or adding a repeater |
| Below -100 dBm | Very poor — communication problems likely |

    For more details, see [About RSSI values](../troubleshooting/rssi_fix.md).

### Firmware {#firmware}

A sortable and filterable table showing firmware status for all devices:

| Column           | Description                                |
| ---------------- | ------------------------------------------ |
| **Device**       | Device name and model                      |
| **Current FW**   | Installed firmware version                 |
| **Available FW** | Latest available firmware version          |
| **Status**       | Update state (up-to-date, updatable, etc.) |

Click **Refresh Firmware Data** to fetch the latest firmware information from the CCU.

!!! note
Firmware updates are managed by the CCU, not by this integration. The panel shows the status for informational purposes. To perform updates, use the CCU WebUI or the device's own update mechanism.

### Install Mode {#install-mode}

Install mode puts the CCU into **pairing mode**, allowing new devices to join the network.

- Click **Activate** next to the desired interface (HmIP-RF or BidCos-RF)
- The CCU enters pairing mode for 60 seconds (a countdown is shown)
- Put your new device into pairing mode during this time (see the device's manual)
- Once paired, the device appears in the [Inbox](#inbox)

!!! tip
Only interfaces that are actually configured in the integration are shown. If you don't see an interface, check your integration configuration.

---

## Schedule Editing for Non-Admin Users {#non-admin-schedules}

By default, only admin users can edit device schedules. You can allow non-admin household members to edit schedules via the HACS schedule cards ([Climate Schedule Card](climate_schedule_card.md) and [Schedule Card](schedule_card.md)).

### Enabling

1. Go to **Settings** → **Devices & Services**
2. Find **Homematic(IP) Local for OpenCCU** and click **Configure**
3. Select **Schedule editing**
4. Enable **Allow non-admin users to edit schedules**
5. Click **Submit**

### How it works

- Non-admin users can edit schedules through the Lovelace schedule cards
- The backend enforces permissions — if a non-admin user tries to edit a schedule without this option enabled, the card shows an "insufficient permissions" error
- All other operations (device configuration, direct links, system administration) remain admin-only
- Read operations (viewing schedules, device parameters) are always available to all authenticated users

!!! note
The configuration panel itself remains admin-only. This setting only affects the schedule cards on dashboards.

---

## Deep-Linking {#deep-linking}

Navigate directly to a specific device, channel, or link view via URL hash parameters. The panel supports browser back/forward navigation for seamless browsing.

---

## Troubleshooting {#troubleshooting}

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

## See Also {#see-also}

- [Week Profiles](week_profile.md) — Schedule data format and actions
- [Climate Schedule Card](climate_schedule_card.md) — Visual thermostat schedule editor
- [Schedule Card](schedule_card.md) — Visual device schedule editor
- [Actions Reference](homeassistant_actions.md) — All available service actions
- [About RSSI values](../troubleshooting/rssi_fix.md) — Understanding signal strength
