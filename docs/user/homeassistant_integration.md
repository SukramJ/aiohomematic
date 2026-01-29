# Homematic(IP) Local for OpenCCU

This is the comprehensive user guide for the **Homematic(IP) Local for OpenCCU** Home Assistant integration, which uses aiohomematic as its core library.

## Quick Start

- **Installation**: Via HACS (recommended) or manual
- **Documentation**: This guide + [aiohomematic docs](../index.md)
- **Issues**: [GitHub Issues](https://github.com/sukramj/aiohomematic/issues)
- **Discussions**: [GitHub Discussions](https://github.com/sukramj/aiohomematic/discussions)

## At a Glance

- Local Home Assistant integration for Homematic(IP) hubs (CCU2/3, OpenCCU, Debmatic, Homegear)
- No cloud required - fully local communication
- XML-RPC for control and push state updates; JSON-RPC for names and rooms
- Auto-discovery supported for CCU and compatible hubs
- Minimum requirements: Home Assistant 2025.10.0+

## Related Integrations

| Integration                                                                         | Use Case                               |
| ----------------------------------------------------------------------------------- | -------------------------------------- |
| **Homematic(IP) Local for OpenCCU**                                                 | Local control via CCU/OpenCCU/Homegear |
| [Homematic(IP) Cloud](https://www.home-assistant.io/integrations/homematicip_cloud) | Cloud control via Access Point         |
| [Homematic IP Local (HCU)](https://github.com/Ediminator/hacs-homematicip-hcu)      | Local control via HmIP-HCU1            |

---

## Installation

### HACS (Recommended)

1. In Home Assistant, go to **HACS** → **Integrations** → **Explore & Download Repositories**
2. Search for "Homematic(IP) Local for OpenCCU"
3. Install and restart Home Assistant when prompted

### Manual Installation

1. Copy `custom_components/homematicip_local` to your Home Assistant `config/custom_components` directory
2. Restart Home Assistant

!!! warning "Manual installation does not support automatic updates"

---

## Requirements

### Hardware

This integration works with any CCU-compatible Homematic hub:

- CCU2/CCU3
- OpenCCU (formerly RaspberryMatic)
- Debmatic
- Homegear
- Home Assistant OS/Supervised with suitable add-on + communication device

**Minimum CCU Firmware for HomematicIP:**

- CCU2: 2.53.27
- CCU3: 3.53.26

### Firewall and Ports

| Interface       | Purpose                  | Default Port | TLS Port |
| --------------- | ------------------------ | ------------ | -------- |
| BidCos-RF       | Classic wireless devices | 2001         | 42001    |
| HomematicIP     | HmIP wireless and wired  | 2010         | 42010    |
| BidCos-Wired    | Classic wired devices    | 2000         | 42000    |
| Virtual Devices | Thermostat groups        | 9292         | 49292    |
| JSON-RPC        | Names and rooms          | 80           | 443      |

!!! note "XML-RPC Callback"
The integration starts a local XML-RPC server within Home Assistant. The CCU must be able to connect to this server for state updates.

    **Docker users**: Use `network_mode: host` or configure `callback_host` and `callback_port_xml_rpc` in Advanced Options.

### Authentication

- Authentication is **always** passed to the Homematic hub
- **Recommended**: Enable authentication for XML-RPC communication on CCU (Settings → Control Panel → Security → Authentication)
- The account **must have admin privileges**
- Allowed password characters: `A-Z`, `a-z`, `0-9`, and `.!$():;#-`

!!! warning "Special characters"
Characters like `ÄäÖöÜüß` work in the CCU WebUI but are **not supported** by XML-RPC servers.

---

## Configuration

### Adding the Integration

[Add Integration](https://my.home-assistant.io/redirect/config_flow_start?domain=homematicip_local){ .md-button .md-button--primary }

Or manually:

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for "Homematic(IP) Local for OpenCCU"

### Configuration Flow

```
Step 1: CCU Connection → Backend Detection → Step 2: TLS & Interfaces → Finish or Configure Advanced
```

#### Step 1: CCU Connection

| Setting           | Description                             | Example           |
| ----------------- | --------------------------------------- | ----------------- |
| **Instance Name** | Unique identifier (lowercase, a-z, 0-9) | `ccu3`            |
| **Host**          | CCU hostname or IP address              | `192.168.1.50`    |
| **Username**      | Admin username (case-sensitive)         | `Admin`           |
| **Password**      | Admin password (case-sensitive)         | `MySecurePass123` |

!!! warning "Instance Name"
The instance name is a unique identifier for your HA installation when communicating with the CCU.

    - It has **no relation** to the CCU's hostname
    - You **can change** the CCU's IP address anytime
    - You **must not change** the instance name after setup (entities will be recreated, losing history)

#### Automatic Backend Detection

After entering credentials, the integration automatically detects:

- Backend type (CCU2, CCU3, OpenCCU, Debmatic, Homegear)
- Available interfaces (HmIP-RF, BidCos-RF, BidCos-Wired, Virtual Devices, CUxD, CCU-Jack)
- TLS configuration

#### Step 2: TLS & Interfaces

| Setting        | Default       | Description                                          |
| -------------- | ------------- | ---------------------------------------------------- |
| **Use TLS**    | Auto-detected | Enable if CCU uses HTTPS                             |
| **Verify TLS** | `false`       | Enable only with valid (non-self-signed) certificate |

**Interface Selection:**

| Interface             | Enable If You Have...                 |
| --------------------- | ------------------------------------- |
| HomematicIP (HmIP-RF) | HomematicIP wireless or wired devices |
| Homematic (BidCos-RF) | Classic Homematic wireless devices    |
| BidCos-Wired          | Classic Homematic wired devices       |
| Heating Groups        | Thermostat groups configured in CCU   |
| CUxD                  | CUxD add-on installed                 |
| CCU-Jack              | CCU-Jack software installed           |

---

## Advanced Options

Access via **Configure advanced options** during setup or **Configure** after setup.

### Callback Settings (Docker/Network)

| Setting                     | Purpose                             |
| --------------------------- | ----------------------------------- |
| **Callback Host**           | IP address the CCU uses to reach HA |
| **Callback Port (XML-RPC)** | Port for state updates from CCU     |

!!! tip "Docker Users"
**Recommended**: Use `network_mode: host`

    **Alternative**: Set Callback Host to your Docker host's IP and configure port forwarding

### System Variables & Programs

| Setting                         | Default | Description                      |
| ------------------------------- | ------- | -------------------------------- |
| **Enable System Variable Scan** | `true`  | Fetch system variables from CCU  |
| **System Variable Markers**     | All     | Filter which variables to import |
| **Enable Program Scan**         | `true`  | Fetch programs from CCU          |
| **Scan Interval**               | 30s     | How often to poll for changes    |

**Markers:**

- **HAHM** - Creates writable entities (switch, select, number, text)
- **MQTT** - Enables push updates via MQTT (requires CCU-Jack)
- **HX** - Custom marker for your own filtering
- **INTERNAL** - Includes CCU-internal variables/programs

### MQTT Integration

| Setting         | Default   | Description                                  |
| --------------- | --------- | -------------------------------------------- |
| **Enable MQTT** | `false`   | Enable for CCU-Jack and CUxD callback events |
| **MQTT Prefix** | _(empty)_ | MQTT prefix used for CCU-Jack bridge         |

### Device Behavior

| Setting                               | Default | Description                                       |
| ------------------------------------- | ------- | ------------------------------------------------- |
| **Enable Sub-Devices**                | `false` | Split devices with multiple channel groups        |
| **Use Group Channel for Cover State** | `true`  | Use group channel for cover position              |
| **Restore Last Brightness**           | `false` | Lights turn on at last brightness instead of 100% |

---

## System Variables & Programs

### Entity Types by Variable Type

| CCU Type         | Default Entity       | With HAHM Marker     |
| ---------------- | -------------------- | -------------------- |
| Character String | `sensor` (read-only) | `text` (editable)    |
| List of Values   | `sensor` (read-only) | `select` (dropdown)  |
| Number           | `sensor` (read-only) | `number` (slider)    |
| Logic Value      | `binary_sensor`      | `switch` (togglable) |
| Alarm            | `binary_sensor`      | `switch` (togglable) |

### Making Variables Writable

Add `HAHM` to the variable's description field in CCU:

1. In CCU, edit your system variable
2. In "Description", add `HAHM` (uppercase)
3. Save and reload the integration in HA

### Filtering with Markers

Without markers, all variables are imported as **disabled** entities. With markers configured in Advanced Options, only marked variables are imported as **enabled** entities.

---

## Device Support

Devices are integrated by automatically detecting available parameters and creating suitable entities. For complex devices (thermostats, covers), custom mappings provide better representation.

### Deactivated Entities

Many entities are created **disabled** initially. Enable them in the entity's advanced settings if needed.

### Missing Device Support

If a new device model doesn't have proper custom entities:

1. Verify the device is working in CCU
2. Report at [aiohomematic Issues](https://github.com/sukramj/aiohomematic/issues)
3. Include device export (use `homematicip_local.export_device_definition` action)

---

## Adding New Devices (Pairing)

### Install Mode

The integration provides buttons to activate install mode:

- **Activate Install Mode HmIP-RF** - For HomematicIP devices
- **Activate Install Mode BidCos-RF** - For classic Homematic devices

Duration sensors show remaining pairing time.

### Repair Notification Process

When you pair a new device:

1. **Pair device** with CCU (via CCU interface)
2. **(Recommended) Name device** in CCU with a meaningful name
3. **Check HA Repairs** - Settings → System → Repairs
4. **Confirm or name** the device in the repair dialog
5. Device and entities are created with proper names

!!! tip "Naming Strategy"
Name devices in CCU first. The integration uses CCU names, and you get clean entity IDs like `sensor.living_room_thermostat_temperature` instead of `sensor.vcu1234567_temperature`.

### Inbox Sensor

The **Inbox** sensor shows devices waiting in the CCU inbox.

---

## Button Devices & Events

### Why No Button Entities?

Physical buttons don't have persistent state. Button presses are handled as **events**, not entities.

### Using Buttons in Automations

1. Create an automation
2. Trigger type: **Device**
3. Select your button device
4. Choose the trigger: "Button 1 pressed", "Button 2 long pressed", etc.

### Enabling Button Events (HomematicIP)

For HomematicIP remotes (WRC2, WRC6, SPDR, KRC4, HM-PBI-4-FM):

**Option A - Action:**

```yaml
action: homematicip_local.create_central_links
target:
  device_id: YOUR_DEVICE_ID
```

**Option B - CCU Interface:**

1. CCU → Settings → Devices
2. Click "+" next to your remote
3. Click the button channel → "activate"

**To disable:** Use `homematicip_local.remove_central_links`

---

## Events

### homematic.keypress

Fired when a key is pressed. Use with device triggers or event entities.

### homematic.device_availability

Fired when a device becomes unavailable or available again. Useful with the persistent notification blueprint.

### homematic.device_error

Fired when a device is in an error state.

---

## Actions Reference

See [Actions](features/homeassistant_actions.md) for the complete action reference including:

- Device value operations (`get_device_value`, `set_device_value`)
- Paramset operations (`get_paramset`, `put_paramset`)
- Climate scheduling (`set_schedule_simple_profile`, `copy_schedule`)
- Siren control (`turn_on_siren`, `play_sound`)
- System variables (`get_variable_value`, `set_variable_value`)
- And more...

---

## CUxD & CCU-Jack

### Communication Methods

| Device Type | Default                | With MQTT           |
| ----------- | ---------------------- | ------------------- |
| CUxD        | JSON-RPC polling (15s) | MQTT push (instant) |
| CCU-Jack    | JSON-RPC polling (15s) | MQTT push (instant) |

### Setting Up MQTT

**Prerequisites:**

1. CCU-Jack installed on CCU
2. HA connected to MQTT broker
3. MQTT integration configured in HA

**Configuration:**

1. Advanced Options → Enable MQTT: `true`
2. MQTT Prefix: _(leave empty for direct connection)_

!!! note "Support Policy"
CUxD/CCU-Jack differences from original hardware behavior are **not considered bugs**. Use HA templates to adapt if needed.

---

## Troubleshooting

### Quick Checklist

| Check            | How to Verify                                          |
| ---------------- | ------------------------------------------------------ |
| HA logs reviewed | Settings → System → Logs → Filter: `homematicip_local` |
| Ports open       | Test with ping, telnet to port 2010                    |
| CCU reachable    | CCU web interface accessible                           |
| Admin user       | User has administrator privileges                      |
| Valid password   | Only allowed characters used                           |

### Docker Issues

| Problem                     | Solution                              |
| --------------------------- | ------------------------------------- |
| No state updates            | Set `callback_host` to Docker host IP |
| Connection refused          | Use `network_mode: host`              |
| Multiple instances conflict | Ensure unique `instance_name`         |

### Getting Help

1. Read the [full troubleshooting guide](troubleshooting/homeassistant_troubleshooting.md)
2. Search [existing issues](https://github.com/sukramj/aiohomematic/issues)
3. Ask in [discussions](https://github.com/sukramj/aiohomematic/discussions)
4. Open an issue with: HA version, integration version, CCU type/firmware, logs, steps to reproduce

---

## FAQ

**Q: Entity shows "unavailable"**

The entity might be disabled. Go to Settings → Entities → find the entity → Enable.

**Q: Button presses don't trigger automation**

HomematicIP buttons need central links. See [Enabling Button Events](#enabling-button-events-homematicip).

**Q: New device added to CCU but doesn't appear in HA**

Check **Settings → System → Repairs** for the device notification.

**Q: How do I change a device name?**

| Goal                 | Method                                 |
| -------------------- | -------------------------------------- |
| Change in HA only    | Settings → Devices → Edit name         |
| Sync from CCU        | Rename in CCU → Reload integration     |
| Change entity ID too | Delete device → Rename in CCU → Reload |

**Q: My CCU has many system variables but I only see a few**

System variables are imported as disabled entities. Enable them in Settings → Entities → Show disabled, or use markers to auto-enable.

---

## See Also

- [Actions Reference](features/homeassistant_actions.md)
- [Naming Conventions](advanced/homeassistant_naming.md)
- [Troubleshooting Guide](troubleshooting/homeassistant_troubleshooting.md)
- [Calculated Climate Sensors](features/calculated_climate_sensors.md)
