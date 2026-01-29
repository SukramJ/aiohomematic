# CUxD and CCU-Jack Setup Guide

This guide explains how to set up and troubleshoot CUxD and CCU-Jack interfaces with the Homematic(IP) Local integration.

## What Are CUxD and CCU-Jack?

**CUxD** (CUx Daemon) and **CCU-Jack** are add-on interfaces for the Homematic CCU that provide extended functionality:

- **CUxD**: Enables integration of non-Homematic devices (FS20, EnOcean, etc.)
- **CCU-Jack**: Provides an alternative HTTP API for CCU access

Both use a fundamentally different communication protocol than standard Homematic interfaces.

## Key Differences from Standard Interfaces

| Aspect         | Standard (HmIP-RF, BidCos-RF) | CUxD / CCU-Jack          |
| -------------- | ----------------------------- | ------------------------ |
| **Protocol**   | XML-RPC                       | JSON-RPC                 |
| **Ports**      | 2001, 2010, etc.              | 80 (HTTP) or 443 (HTTPS) |
| **Events**     | Push (CCU sends to HA)        | Polling or MQTT          |
| **Keep-alive** | Ping/Pong mechanism           | Not supported            |

**Important**: CUxD and CCU-Jack devices may update less frequently than standard devices because they rely on polling rather than push notifications.

## Setup in Home Assistant

### Prerequisites

1. CUxD or CCU-Jack add-on installed and running on your CCU
2. Homematic(IP) Local integration configured in Home Assistant

### Configuration

CUxD and CCU-Jack must be **manually enabled** in the integration configuration:

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration** → **Homematic(IP) Local**
3. Enter your CCU's IP address and credentials
4. In the interface configuration, **enable CUxD or CCU-Jack** checkbox

**Note**: Only standard interfaces (HmIP-RF, BidCos-RF, etc.) are auto-detected. CUxD and CCU-Jack require explicit configuration.

**No special port configuration is required** - these interfaces use standard HTTP ports (80/443).

### Verifying the Setup

After configuration, check:

1. **Devices & Services** → **Homematic(IP) Local** → **Configure**
2. You should see CUxD/CCU-Jack listed under interfaces
3. Devices should appear with their entities

## Event Updates

### Default Behavior (Polling)

By default, CUxD and CCU-Jack devices are polled periodically for updates. This means:

- Device states may take longer to update (polling interval)
- No instant push notifications from these devices
- Connection health is monitored via periodic checks

### Optional: MQTT Integration

For faster updates, you can set up CCU-Jack's MQTT bridge to forward events to Home Assistant:

**Note**: CCU-Jack includes its own MQTT broker. To integrate with Home Assistant, you configure a bridge to forward events.

1. **Install CCU-Jack** on your CCU (if not already installed)
2. **Set up an MQTT broker** in Home Assistant (e.g., Mosquitto add-on)
3. **Configure CCU-Jack MQTT Bridge** to forward events:
   - In `ccu-jack.cfg`, set `"MQTT.Bridge.Enable": true`
   - Configure the remote broker address (your HA Mosquitto)
   - Define outgoing topics to forward CCU data points
   - See [CCU-Jack MQTT Bridge documentation](https://github.com/mdzio/ccu-jack/wiki/MQTT-Bridge) for details
4. **Enable MQTT** in the Homematic(IP) Local integration settings

With the MQTT bridge configured, events from CCU-Jack devices are forwarded to Home Assistant for near-instant updates instead of relying on polling.

## Troubleshooting

### Devices Not Found

| Symptom                | Possible Cause           | Solution                                      |
| ---------------------- | ------------------------ | --------------------------------------------- |
| No CUxD devices appear | CUxD add-on not running  | Check CCU WebUI → System → Add-ons            |
| "Connection refused"   | Interface not accessible | Verify CUxD/CCU-Jack is started on CCU        |
| Authentication failure | Wrong credentials        | Check username/password in integration config |

### Devices Never Update

| Symptom              | Possible Cause              | Solution                                  |
| -------------------- | --------------------------- | ----------------------------------------- |
| State never changes  | Polling not reaching device | Check CCU logs for errors                 |
| Updates very delayed | Normal for CUxD             | Consider enabling MQTT for faster updates |

### Debug Logging

**Easiest method** - Enable via Home Assistant UI:

1. Go to **Settings** → **Devices & Services** → **Homematic(IP) Local**
2. Click **Configure** → **Enable debug logging**
3. Reproduce the problem
4. Click **Disable debug logging** - the debug log will be offered as a file download

**Alternative** - Via YAML configuration:

```yaml
logger:
  default: info
  logs:
    aiohomematic: debug
    custom_components.homematicip_local: debug
```

Check the logs for:

- Interface connection status
- Device discovery messages
- Event processing

### Testing Connectivity

From your Home Assistant host, test HTTP connectivity:

```bash
# Test basic HTTP connectivity to CCU
curl -v http://YOUR_CCU_IP/

# Should return the CCU web interface, not "Connection refused"
```

## Limitations

CUxD and CCU-Jack have some limitations compared to standard interfaces:

| Feature              | Supported         |
| -------------------- | ----------------- |
| Device control       | Yes               |
| State reading        | Yes               |
| Push events          | No (polling only) |
| Ping/Pong keep-alive | No                |
| Firmware updates     | No                |
| Device linking       | No                |
| System variables     | No                |

## Best Practices

1. **Don't expect instant updates** - CUxD devices update via polling
2. **Use automation timers** - Build in delays for state verification
3. **Enable MQTT if available** - Provides faster event delivery
4. **Monitor logs** - Watch for connection issues in debug logs

## Common Misconceptions

- **Wrong**: "I need to configure a special port for CUxD"

  - **Correct**: CUxD uses HTTP port 80/443, no special config needed

- **Wrong**: "CUxD should send instant updates like HmIP-RF"

  - **Correct**: CUxD uses polling by default, updates may be delayed

- **Wrong**: "Connection timeout warnings mean CUxD is broken"
  - **Correct**: CUxD has no ping/pong; the integration handles this correctly

## See Also

- [Troubleshooting Guide](../homeassistant_troubleshooting.md)
- [Actions Reference](homeassistant_actions.md) - For manual device control
