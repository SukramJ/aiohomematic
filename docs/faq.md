# Frequently Asked Questions

This page answers common questions about aiohomematic and the Homematic(IP) Local integration for Home Assistant.

---

## General Questions

### What is aiohomematic?

aiohomematic is a modern, async Python library for controlling Homematic and HomematicIP devices. It handles the low-level communication with CCU/Homegear backends via XML-RPC and JSON-RPC protocols.

### What is the difference between aiohomematic and Homematic(IP) Local?

| Aspect                     | aiohomematic                                            | Homematic(IP) Local                                               |
| -------------------------- | ------------------------------------------------------- | ----------------------------------------------------------------- |
| **Type**                   | Python library                                          | Home Assistant integration                                        |
| **Purpose**                | Protocol implementation                                 | HA entity mapping                                                 |
| **Can be used standalone** | Yes                                                     | No (requires HA)                                                  |
| **Repository**             | [aiohomematic](https://github.com/sukramj/aiohomematic) | [homematicip_local](https://github.com/sukramj/homematicip_local) |

### Which backends are supported?

- CCU3 / CCU2
- OpenCCU (formerly RaspberryMatic)
- piVCCU / Debmatic
- Homegear

### What are the minimum requirements?

- **Python**: 3.13+ (for standalone library use)
- **Home Assistant**: 2025.10.0+ (for integration)
- **CCU Firmware**: CCU2 ≥2.53.27, CCU3 ≥3.53.26 (for HomematicIP devices)

---

## Installation & Configuration

### How do I install the integration?

**Via HACS (Recommended):**

1. Open HACS in Home Assistant
2. Search for "Homematic(IP) Local for OpenCCU"
3. Install and restart Home Assistant
4. Add integration via Settings → Devices & Services

**Manual:**

1. Copy `custom_components/homematicip_local` to your HA config directory
2. Restart Home Assistant

### Can I use this alongside the official Homematic integration?

There are multiple Homematic-related integrations:

| Integration                                                                            | Type        | Backend              | Status          |
| -------------------------------------------------------------------------------------- | ----------- | -------------------- | --------------- |
| **[Homematic](https://www.home-assistant.io/integrations/homematic/)**                 | HA Core     | CCU (local)          | ⚠️ Unmaintained |
| **[HomematicIP Cloud](https://www.home-assistant.io/integrations/homematicip_cloud/)** | HA Core     | Access Point (cloud) | Active          |
| **Homematic(IP) Local**                                                                | HACS Custom | CCU (local)          | ✅ Active       |

**Why is the Homematic core integration unmaintained?**

The official Homematic integration is based on [pyhomematic](https://github.com/danielperna84/pyhomematic), which is no longer maintained. aiohomematic is the modern successor to pyhomematic, offering async support, better typing, and active development. Since pyhomematic is not being developed further, neither is the Homematic core integration.

**Should I use Homematic or Homematic(IP) Local?**

Use **Homematic(IP) Local**. It offers more features, supports newer devices, and receives regular updates. You should **not** configure the same devices in both integrations simultaneously.

### Why does the integration need admin credentials?

The CCU requires admin privileges for:

- Fetching device configurations
- Reading and writing parameters
- Executing programs
- Managing system variables

### What password characters are allowed?

Only these characters are supported: `A-Z`, `a-z`, `0-9`, `.!$():;#-`

Special characters like `ÄäÖöÜüß` work in CCU WebUI but **not** via XML-RPC.

---

## Devices & Entities

### Why are some entities disabled by default?

Many parameters exist on devices but are rarely needed (diagnostic values, internal counters, etc.). To keep the UI clean, these are created as disabled entities. Enable them via:

1. Settings → Entities
2. Show disabled entities
3. Find and enable the entity you need

### Entity shows "unavailable" - what now?

Common causes:

1. **Entity is disabled** → Enable in entity settings
2. **Device offline** → Check device battery/power and radio range
3. **Interface not enabled** → Check if correct interface (HmIP-RF, BidCos-RF) is enabled
4. **Connection lost** → Check integration status and logs

### New device not appearing in Home Assistant?

1. Verify device is successfully paired in CCU WebUI
2. Check **Settings → System → Repairs** for device notification
3. Reload the integration
4. Check logs for errors

### How do I rename a device?

| Goal                   | Method                                       |
| ---------------------- | -------------------------------------------- |
| Change name in HA only | Settings → Devices → Edit name               |
| Sync name from CCU     | Rename in CCU → Reload integration           |
| Change entity ID too   | Delete device in HA → Rename in CCU → Reload |

### Why don't button presses trigger automations?

**For HomematicIP remotes (WRC2, WRC6, etc.):**

Central links must be created first:

```yaml
action: homematicip_local.create_central_links
target:
  device_id: YOUR_DEVICE_ID
```

**For classic Homematic buttons:**

Should work automatically. If not, check if device is paired correctly.

---

## System Variables & Programs

### Why do I only see a few system variables?

System variables are imported as **disabled** entities by default. To see all:

1. Settings → Entities
2. Enable "Show disabled entities"
3. Enable the variables you need

Or use markers (add `HAHM` to variable description in CCU) to auto-enable.

### How do I make a system variable writable?

Add `HAHM` to the variable's description field in CCU:

1. In CCU, edit the system variable
2. In "Description" field, add `HAHM` (uppercase)
3. Save and reload the integration

The entity type changes from `sensor` (read-only) to editable (`number`, `select`, `text`, or `switch`).

### How do I run a CCU program from Home Assistant?

Programs appear as button entities. Press the button or use in automation:

```yaml
action: button.press
target:
  entity_id: button.my_program
```

---

## Connection & Network

### What ports need to be open?

| Interface       | Port | TLS Port |
| --------------- | ---- | -------- |
| HmIP-RF         | 2010 | 42010    |
| BidCos-RF       | 2001 | 42001    |
| BidCos-Wired    | 2000 | 42000    |
| Virtual Devices | 9292 | 49292    |
| JSON-RPC        | 80   | 443      |

Plus: CCU must be able to reach Home Assistant on the callback port.

### Docker: Events not received?

For Docker installations:

**Recommended:** Use `network_mode: host`

**Alternative:**

1. Set `callback_host` to your Docker host IP in advanced options
2. Configure port forwarding for callback port

### How do I enable TLS?

1. Enable TLS on your CCU first
2. In integration configuration, enable "Use TLS"
3. Set "Verify TLS" to `false` for self-signed certificates

---

## CUxD & CCU-Jack

### How do CUxD/CCU-Jack devices get updates?

By default: JSON-RPC polling every 15 seconds.

For instant updates: Enable MQTT in advanced options (requires CCU-Jack with MQTT bridge configured).

### Why is my CUxD device behaving differently?

CUxD and CCU-Jack devices may behave slightly differently from original Homematic hardware. This is **not considered a bug** in the integration. Use Home Assistant templates to adapt if needed.

---

## Library Usage (Developers)

### How do I use aiohomematic standalone?

```python
from aiohomematic.api import HomematicAPI

async with HomematicAPI.connect(
    host="192.168.1.100",
    username="Admin",
    password="secret",
) as api:
    for device in api.list_devices():
        print(f"{device.name}: {device.model}")
```

### How do I subscribe to events?

```python
from aiohomematic.central.events import DataPointUpdatedEvent

async def on_update(*, event: DataPointUpdatedEvent) -> None:
    print(f"{event.dpk}: {event.value}")

unsubscribe = central.event_bus.subscribe(
    event_type=DataPointUpdatedEvent,
    handler=on_update,
)

# Later: unsubscribe()
```

### How do I add support for a new device?

See the [Extension Points](developer/extension_points.md) documentation for detailed instructions on registering device profiles.

---

## Troubleshooting

### Where do I find logs?

**Home Assistant:**

Settings → System → Logs → Filter for `homematicip_local` or `aiohomematic`

**Enable debug logging:**

```yaml
# configuration.yaml
logger:
  logs:
    aiohomematic: debug
    custom_components.homematicip_local: debug
```

### How do I download diagnostics?

1. Settings → Devices & Services
2. Find Homematic(IP) Local
3. Click three dots → Download Diagnostics

Always attach diagnostics when reporting issues.

### Where do I report bugs?

- **Library issues (aiohomematic):** [aiohomematic Issues](https://github.com/sukramj/aiohomematic/issues)
- **Integration issues (Homematic(IP) Local):** Same repository
- **Discussions/Questions:** [GitHub Discussions](https://github.com/sukramj/aiohomematic/discussions)

---

## See Also

- [Troubleshooting Guide](troubleshooting/index.md)
- [Getting Started](getting_started.md)
- [User Guide](user/homeassistant_integration.md)
- [Glossary](reference/glossary.md)
