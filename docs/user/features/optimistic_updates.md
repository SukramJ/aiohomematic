# Optimistic Updates & Rollback

When you switch a Homematic device in Home Assistant, the UI updates **immediately** — without waiting for the CCU to confirm the command. This is called an **optimistic update**. It makes the interface feel fast and responsive.

Behind the scenes, a safety timer starts. If the CCU does not confirm the command within **30 seconds**, Home Assistant assumes the command did not succeed and reverts the UI back to the previous state. This is called an **optimistic rollback**.

---

## How it works

```
You press "On"
    │
    ▼
UI shows "On" immediately          ← optimistic update
    │
    ├── CCU confirms within 30s    → state stays "On" ✅
    │
    └── No confirmation after 30s  → UI reverts to "Off" ⚠️  (rollback)
```

1. You switch a device (e.g., turn on a light)
2. Home Assistant shows the new state right away — you see instant feedback
3. The command is sent to the CCU via RPC
4. A 30-second timer starts
5. **If the CCU confirms**: The timer is cancelled, the state is confirmed — everything is fine
6. **If no confirmation arrives**: The state reverts to the previous value and a warning is logged

---

## Rollback reasons

When a rollback occurs, a warning message appears in the Home Assistant log. The message includes the **reason** for the rollback:

| Reason         | Meaning                                                                  |
| -------------- | ------------------------------------------------------------------------ |
| **timeout**    | The CCU did not confirm the command within 30 seconds                    |
| **send_error** | The command could not be sent to the CCU (e.g., connection lost)         |
| **mismatch**   | The CCU confirmed a different value than what was sent (logged as debug) |

### Example log message

```
Optimistic rollback for Power Galerie/STATE: False -> True (reason=timeout, age=30.0s)
```

This means:

- The device **Power Galerie** was switched to **On** (`True`)
- The CCU did not confirm within 30 seconds
- The UI reverted back to **Off** (`False`)

---

## Common causes for timeout rollbacks

A **timeout** rollback means the command was sent, but the CCU did not respond. Typical causes:

### Communication issues

- **Network problems** between Home Assistant and the CCU (e.g., after SSL certificate changes, firewall rules, or network reconfiguration)
- **CCU overloaded** — the CCU is busy and cannot process commands in time

### Radio (RF) issues

- **Duty cycle exhausted** — BidCos-RF has a 1% duty cycle limit. If many devices are switched simultaneously, the CCU may run out of send budget
- **Weak signal** — the device is too far from the CCU or a repeater
- **Interference** — other 868 MHz devices are causing radio collisions

### Device issues

- **Device unreachable** — the device is powered off, defective, or out of range
- **Battery empty** — battery-powered devices may not respond when the battery is low

---

## Troubleshooting

### Step 1: Verify the device works via CCU

1. Open the CCU web interface in your browser (e.g., `http://<CCU-IP>`)
2. Go to **Status und Bedienung → Geräte**
3. Find the affected device and switch it manually

If the device does **not** switch via the CCU either, the problem is on the CCU/RF side (not Home Assistant).

### Step 2: Check the CCU duty cycle

1. Open the CCU web interface
2. Go to **Einstellungen → Systemsteuerung → Funk-Schnittstellen**
3. Check the **Duty Cycle** percentage for BidCos-RF

If the duty cycle is above 90%, the CCU cannot send more commands. Wait for it to reset (resets every hour) or reduce the number of simultaneous commands.

### Step 3: Enable debug logging

1. In Home Assistant, go to **Settings → Devices & Services**
2. Find your **Homematic(IP) Local** integration and click on it
3. Click **"Enable debug logging"** (the bug icon at the top)
4. Trigger the automation that causes the rollback
5. Wait 30 seconds for the rollback to appear
6. Go to **Settings → System → Logs**
7. Click **"Download full log"** (top right)
8. Disable debug logging again (same path as step 2–3)

In the debug log, look for:

- `set_value` entries for the affected devices — confirms the command was sent
- `event` entries for the same devices — shows if the CCU sent a confirmation
- Any error messages related to the affected interface

### Step 4: Check for recent changes

Rollbacks that suddenly appear after a configuration change often point to:

- **SSL/TLS changes** — adding HTTPS to Home Assistant can affect the XML-RPC callback connection if the CCU cannot reach the new endpoint
- **Network changes** — new router, firewall, VLAN, or IP address changes
- **CCU firmware updates** — may change default settings or reset interface configurations

---

## Automatic Command Retry

When a command fails due to a **transient error**, the system automatically retries it before triggering a rollback. This significantly reduces false rollbacks caused by temporary issues.

### What gets retried

| Error Type                   | Retried?        | Example                                       |
| ---------------------------- | --------------- | --------------------------------------------- |
| Network timeout              | Yes             | CCU temporarily overloaded                    |
| Device unreachable (UNREACH) | Yes             | Battery device in deep sleep, RF interference |
| DutyCycle exhausted          | Yes (40s delay) | Too many commands sent on 868 MHz             |
| Transmission pending         | Yes (5s delay)  | CCU is already sending to the device          |
| Device out of range          | Yes             | Temporary RF problem                          |
| Authentication failure       | No              | Wrong credentials                             |
| Invalid parameter/value      | No              | Programming error                             |
| Unknown device               | No              | Device removed                                |

### Retry behavior

- **Up to 3 attempts** (configurable) with exponential backoff (2s → 4s → 8s)
- **Optimistic value stays active** during retries — the UI does not flicker
- **Rollback only after all retries are exhausted** — you get a single clean rollback, not three
- **New command cancels pending retry** — if you change the value again while a retry is pending, the old retry is cancelled

### What is NOT retried

- **Button presses** and **actions** (fire-and-forget commands) — these are inherently non-idempotent
- **Cover stop commands** — safety-critical, must execute immediately or not at all

### Configuring retry

The maximum number of retry attempts can be configured in the integration:

1. Go to **Settings → Devices & Services → Homematic(IP) Local**
2. Click **Configure**
3. Select **Advanced Settings**
4. Adjust **Command retry attempts** (default: 3, range: 0–10)
5. Set to **0** to disable retry entirely

### Disabling retry per call

To disable retry for a specific automation call, set `retry: false` on the `set_device_value` or `put_paramset` action:

```yaml
action: homematicip_local.set_device_value
data:
  device_id: abcdefg...
  channel: 1
  parameter: STATE
  value: "true"
  value_type: boolean
  retry: false
```

---

## Configuration

The rollback timeout is configured via `TimeoutConfig.optimistic_update_timeout` (default: **30 seconds**). This is not configurable through the Home Assistant UI — it is a library-level setting that applies to all devices.

The 30-second default is chosen to balance:

- **Fast feedback** — users are notified within 30 seconds if a command failed
- **Tolerance for slow devices** — battery-powered devices and busy networks may need several seconds to respond
