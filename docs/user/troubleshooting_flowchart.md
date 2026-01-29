# Troubleshooting Flowchart

Use this visual guide to diagnose and resolve common issues with the Homematic(IP) Local integration.

## Quick Diagnosis

```mermaid
flowchart TD
    START([Problem Detected]) --> Q1{Integration<br/>loads?}

    Q1 -->|No| AUTH[Check Authentication]
    Q1 -->|Yes| Q2{Devices<br/>appear?}

    AUTH --> A1[Verify CCU credentials]
    AUTH --> A2[Check CCU firewall]
    AUTH --> A3[Test network connectivity]

    Q2 -->|No| DISC[Check Discovery]
    Q2 -->|Yes| Q3{Entities<br/>update?}

    DISC --> D1[Reload integration]
    DISC --> D2[Check CCU device list]
    DISC --> D3[Verify interface config]

    Q3 -->|No| EVENTS[Check Events]
    Q3 -->|Yes| Q4{Actions<br/>work?}

    EVENTS --> E1[Enable debug logging]
    EVENTS --> E2[Check callback server]
    EVENTS --> E3[Verify XML-RPC ports]

    Q4 -->|No| ACTIONS[Check Actions]
    Q4 -->|Yes| DONE([System OK])

    ACTIONS --> C1[Check entity state]
    ACTIONS --> C2[Verify device reachable]
    ACTIONS --> C3[Check CCU programs]
```

## Connection Issues

```mermaid
flowchart TD
    CONN([Connection Problem]) --> Q1{Can ping<br/>CCU IP?}

    Q1 -->|No| NET[Network Issue]
    Q1 -->|Yes| Q2{CCU WebUI<br/>accessible?}

    NET --> N1[Check IP address]
    NET --> N2[Check network/VLAN]
    NET --> N3[Check firewall rules]

    Q2 -->|No| CCU[CCU Issue]
    Q2 -->|Yes| Q3{Integration<br/>connects?}

    CCU --> C1[Restart CCU]
    CCU --> C2[Check CCU services]
    CCU --> C3[Check CCU logs]

    Q3 -->|No| PORTS[Port Issue]
    Q3 -->|Yes| DONE([Connection OK])

    PORTS --> P1[Check ports 2001/2010]
    PORTS --> P2[Check HA firewall]
    PORTS --> P3[Try different interface]
```

## Entity Update Issues

```mermaid
flowchart TD
    UPDATE([Entities Not Updating]) --> Q1{Which<br/>interface?}

    Q1 -->|HmIP-RF/BidCos| XML[XML-RPC Check]
    Q1 -->|CUxD/CCU-Jack| JSON[JSON-RPC Check]

    XML --> X1{Callback<br/>server OK?}
    X1 -->|No| X2[Check HA network config]
    X1 -->|Yes| X3{Events<br/>in logs?}
    X3 -->|No| X4[Check CCU callback registration]
    X3 -->|Yes| X5[Check entity subscription]

    JSON --> J1{Polling<br/>active?}
    J1 -->|No| J2[Check integration config]
    J1 -->|Yes| J3{MQTT<br/>enabled?}
    J3 -->|No| J4[Updates may be delayed - normal]
    J3 -->|Yes| J5[Check MQTT broker]
```

## Device-Specific Issues

```mermaid
flowchart TD
    DEVICE([Device Problem]) --> Q1{Device in<br/>CCU WebUI?}

    Q1 -->|No| PAIR[Pairing Issue]
    Q1 -->|Yes| Q2{Device in<br/>Home Assistant?}

    PAIR --> PA1[Re-pair device to CCU]
    PAIR --> PA2[Check CCU inbox]
    PAIR --> PA3[Factory reset device]

    Q2 -->|No| DISC[Discovery Issue]
    Q2 -->|Yes| Q3{Correct<br/>entity type?}

    DISC --> DI1[Reload integration]
    DISC --> DI2[Check device exclusions]
    DISC --> DI3[Export device definition]

    Q3 -->|No| TYPE[Entity Type Issue]
    Q3 -->|Yes| Q4{Values<br/>correct?}

    TYPE --> T1[Check custom mapping]
    TYPE --> T2[Report on GitHub]

    Q4 -->|No| VALUE[Value Issue]
    Q4 -->|Yes| DONE([Device OK])

    VALUE --> V1[Check parameter visibility]
    VALUE --> V2[Compare with CCU WebUI]
```

## Step-by-Step Diagnosis

### Step 1: Verify Basic Connectivity

1. **Ping the CCU**:

   ```bash
   ping YOUR_CCU_IP
   ```

2. **Access CCU WebUI**: Open `http://YOUR_CCU_IP` in browser

3. **Check HA logs** for connection errors:
   ```yaml
   logger:
     logs:
       aiohomematic: debug
   ```

### Step 2: Check Interface Status

In Home Assistant:

1. Go to **Settings** → **Devices & Services**
2. Click **Homematic(IP) Local** → **Configure**
3. Check interface status (connected/disconnected)

### Step 3: Verify Events Flow

Enable debug logging and look for:

```
# Good - Events arriving
Received event: interface=HmIP-RF channel=XXXX:1 parameter=STATE value=True

# Bad - No events
No events received for 180 seconds
```

### Step 4: Test Actions

Try a simple action in Developer Tools → Services:

```yaml
action: homematicip_local.set_device_value
data:
  device_id: YOUR_DEVICE_ID
  channel: 1
  parameter: STATE
  value: "true"
  value_type: boolean
```

## Common Issues Quick Reference

| Symptom                     | Likely Cause           | Solution                      |
| --------------------------- | ---------------------- | ----------------------------- |
| "Connection refused"        | CCU not reachable      | Check network, firewall       |
| "Authentication failed"     | Wrong credentials      | Verify username/password      |
| Entities show "unavailable" | Connection lost        | Check CCU, reload integration |
| No entity updates           | Callback not working   | Check HA network config       |
| Wrong entity type           | Missing custom mapping | Report on GitHub              |
| CUxD devices slow           | Normal for polling     | Consider MQTT setup           |

## Debug Log Levels

| Level     | What It Shows                  | When to Use           |
| --------- | ------------------------------ | --------------------- |
| `warning` | Errors and warnings            | Normal operation      |
| `info`    | Connection status, events      | Basic troubleshooting |
| `debug`   | All RPC calls, full event data | Detailed diagnosis    |

### Enable Debug Logging

**Easiest method** - Enable via Home Assistant UI:

1. Go to **Settings** → **Devices & Services** → **Homematic(IP) Local**
2. Click **Configure** → **Enable debug logging**
3. Reproduce the problem
4. Click **Disable debug logging** - the debug log will be offered as a file download

**Alternative** - Via YAML configuration:

```yaml
logger:
  default: warning
  logs:
    aiohomematic: debug
    custom_components.homematicip_local: debug
```

## When to Open an Issue

Open a GitHub issue if:

1. **Bug**: Unexpected behavior after following troubleshooting steps
2. **Missing Device Support**: Device works in CCU but not in HA
3. **Wrong Entity Type**: Device creates wrong entity (sensor vs. switch)

**Include in your issue**:

- [ ] Home Assistant version
- [ ] aiohomematic version
- [ ] CCU type and firmware
- [ ] Debug logs (redact sensitive info)
- [ ] Device definition export (for device issues)

### Export Device Definition

```yaml
action: homematicip_local.export_device_definition
data:
  device_id: YOUR_DEVICE_ID
```

## See Also

- [Troubleshooting Guide](../homeassistant_troubleshooting.md) - Detailed troubleshooting
- [CUxD and CCU-Jack](cuxd_ccu_jack.md) - Special interface handling
- [Device Support](device_support.md) - How devices are supported
