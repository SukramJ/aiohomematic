# Common Issues and Troubleshooting (Home Assistant)

This document helps you quickly analyze and resolve typical problems when using aiohomematic with Home Assistant (integration: Homematic(IP) Local). The notes apply to CCU (CCU2/3, OpenCCU, piVCCU) and Homegear unless stated otherwise.

Contents:

- Quick symptom mapping (at a glance)
- Step-by-step diagnostics
- Common issues with causes and solutions
- Network/ports/container specifics
- Capturing logs and debug information
- When to open an issue – required information

---

## 1) Quick symptom mapping

This section provides a quick overview of common symptoms and their most likely causes. Use it to quickly identify the area of the problem before diving into the detailed diagnostics below.

| Symptom                                                | Most likely cause                                                                                                       | See section                                                          |
| ------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| No devices/entities visible after setup                | Connection details wrong (host/IP, ports, auth), CCU not reachable, or callback not reachable from CCU                  | [3A](#a-no-entities-after-setup)                                     |
| New devices not detected or incompletely recognized    | Outdated cache data in Home Assistant                                                                                   | [3H](#h-new-devices-not-detected-or-devices-incompletely-recognized) |
| Entities present but without state changes             | Event callbacks not arriving (firewall/NAT/Docker), XML-RPC blocked, or invalid session                                 | [3B](#b-entities-have-no-updates-only-initial-values-or-none)        |
| Individual devices "unavailable" or stuck on old value | Device availability issue (UN_REACH/STICKY_UN_REACH), radio problems, battery device sleeping, or CONFIG_PENDING active | [3C](#c-individual-devices-are-unavailable)                          |
| Writing values doesn't work                            | Permissions/auth problem, invalid parameter, validation error, wrong channel/parameter, or device unavailable           | [3D](#d-writing-fails-service-call-fails)                            |
| HmIP devices missing                                   | HmIP service on CCU not active, wrong ports, or session/token issue                                                     | [3E](#e-hmip-devices-missing-or-not-updating)                        |
| After CCU/Home Assistant restart no updates arrive     | Callback not re-registered, port blocked, or reverse proxy/SSL terminator blocking internal connection                  | [3F](#f-no-events-after-restart)                                     |

---

## 2) Step-by-step diagnostics

If you're experiencing issues, follow these steps systematically to identify the root cause:

### Step 1: Basic connectivity checks

Before investigating integration-specific issues, verify basic connectivity:

- **CCU/Homegear accessibility**: Can you access the CCU WebUI in your browser? If not, the CCU itself may have a problem.
- **Time and date**: Is the time/date on the CCU correct? Incorrect time can cause authentication issues.
- **Resources**: Does the CCU have sufficient CPU/RAM? Check the CCU's system diagnostics.
- **Network connectivity**: Can Home Assistant reach the CCU? Try pinging the CCU IP from the Home Assistant host:
  ```bash
  # From Home Assistant terminal or SSH
  ping <CCU-IP-Address>
  ```
- **Port accessibility**: Are the required ports open? See the [Network and Ports](#4-network-ports-and-containers) section for details.

### Step 2: Verify integration configuration

Check your Home Assistant integration settings:

- **Host/IP address**: Use an IP address rather than a hostname to avoid DNS/mDNS resolution issues.
- **Protocol selection**: Ensure you've selected the correct protocol for your devices:
  - BidCos-RF for classic Homematic wireless devices
  - BidCos-Wired for wired Homematic devices
  - HmIP-RF for HomematicIP devices
- **Credentials**: Verify username and password are correct (if authentication is enabled on the CCU).

### Step 3: Verify callback reachability

This is crucial: The CCU must be able to reach Home Assistant's callback port. The communication is bidirectional:

```
Home Assistant → CCU:  Commands, queries (you initiate)
CCU → Home Assistant:  Events, state changes (CCU initiates via callback)
```

To test callback reachability:

1. Note the callback port shown in the integration's diagnostics (default: dynamically assigned)
2. From the CCU (if you have SSH access) or another device on the CCU's network, test connectivity:
   ```bash
   nc -zv <Home-Assistant-IP> <callback-port>
   ```
3. If this fails, check your firewall rules and Docker/container networking (see [Network section](#4-network-ports-and-containers)).

### Step 4: Enable debug logging

Enable detailed logging to see what's happening:

1. Add to your `configuration.yaml`:
   ```yaml
   logger:
     default: info
     logs:
       aiohomematic: debug
       custom_components.homematicip_local: debug
   ```
2. Restart Home Assistant
3. Reproduce the problem
4. Check the logs in **Settings** → **System** → **Logs**

See the [Logging section](#5-logging-and-debug) for details on interpreting log messages.

### Step 5: Check device status on the CCU

In the CCU WebUI, verify the status of problematic devices:

- **Device reachable?**: Check if the device shows as reachable in the CCU
- **UN_REACH/STICKY_UN_REACH**: Look for these parameters in the device's MAINTENANCE channel
- **CONFIG_PENDING**: Is this parameter `true`? If so, the device configuration is incomplete

### Step 6: Cache and restart

After making changes:

1. If device information seems outdated, use the `homematicip_local.clear_cache` service
2. Restart Home Assistant
3. In some cases, also restart the CCU (especially after firmware updates or significant configuration changes)

---

## 3) Common issues, causes, and solutions

### A) No entities after setup

**Symptoms:**

- After setting up the integration, no devices or entities appear in Home Assistant
- The integration shows as "loaded" but the device count is zero

**Possible causes:**

1. Wrong host/IP address or CCU port configuration
2. Authentication failed (wrong username/password)
3. Required CCU services not started
4. RPC methods unavailable on the CCU

**Diagnostic steps:**

1. Check the Home Assistant logs for error messages (look for "connection refused", "timeout", "401", "403", "404")
2. Verify you can access the CCU WebUI at the same IP address
3. Try accessing the CCU's XML-RPC port directly: `http://<CCU-IP>:2001/` should show an XML-RPC response

**Solutions:**

- Verify the host/IP address is correct and reachable
- Double-check credentials (or try without authentication if it's disabled on the CCU)
- Restart the CCU to ensure all services are running
- Remove and re-add the integration in Home Assistant

### B) Entities have no updates (only initial values or none)

**Symptoms:**

- Devices appear in Home Assistant but their states never change
- Sensor values are stuck on their initial reading
- Button presses or switch toggles on physical devices don't update Home Assistant

**Possible causes:**

1. Event callback from CCU to Home Assistant is blocked
2. Firewall blocking incoming connections to Home Assistant
3. NAT/Docker networking preventing CCU from reaching the callback port
4. Callback IP address is incorrect (e.g., internal Docker IP instead of host IP)

**Why this happens:**

The CCU sends state changes as "events" to Home Assistant via a callback connection. If this callback is blocked, Home Assistant can still query the CCU (so initial values work), but it won't receive updates.

**Diagnostic steps:**

1. Check logs for "Registering callback" or "Subscribed" messages
2. From the CCU's network, verify the callback port is reachable (see Step 3 in diagnostics)
3. Check your firewall rules (ufw, iptables, Windows Firewall)

**Solutions:**

- **Docker users**: Use host networking mode (`network_mode: host`) or correctly publish the callback port
- **Firewall**: Allow incoming connections on the callback port from the CCU's IP
- **Check callback IP**: In the integration configuration, ensure the callback IP is one that the CCU can actually reach
- **Avoid IP changes**: Use static IPs or DHCP reservations for both Home Assistant and CCU

### C) Individual devices are "unavailable"

**Symptoms:**

- One or more devices show as "unavailable" in Home Assistant
- The device was working before but suddenly became unavailable
- The CCU WebUI might show the device as "reachable" but Home Assistant shows it as unavailable

**Understanding device availability:**

The integration marks devices as unavailable based on **UNREACH events** received from the CCU. This is important to understand:

1. **How it works**: When a device fails to respond to the CCU's communication attempts, the CCU sets the `UN_REACH` parameter to `true` and sends this information to Home Assistant via an event
2. **The integration reacts to this event** by marking all entities of that device as "unavailable" in Home Assistant
3. **This is intentional behavior**: It ensures Home Assistant accurately reflects communication problems between the CCU and the device

**Why the CCU WebUI might show different status:**

The CCU WebUI may display device status differently than Home Assistant. However, **the integration only reacts to the UNREACH events** it receives from the CCU. It does not try to interpret or second-guess the CCU's behavior. If the CCU sends an UNREACH event, the integration marks the device as unavailable.

**Possible causes:**

1. **Radio/wireless issues**: Device is out of range, interference, or weak signal
2. **Battery-powered devices**: Device is in sleep mode and missed the CCU's query
3. **Device physically unreachable**: Power loss, device failure, or device removed
4. **STICKY_UNREACH**: A previous communication failure that hasn't been cleared
5. **CONFIG_PENDING**: Device configuration is incomplete

**Diagnostic steps:**

1. In the CCU WebUI, check the device's MAINTENANCE channel for:
   - `UNREACH`: Currently unreachable
   - `STICKY_UNREACH`: Was unreachable at some point (needs manual reset)
   - `CONFIG_PENDING`: Configuration not yet applied
2. Check the physical device (batteries, power, location)
3. Try triggering the device manually (press a button) to force communication

**Solutions:**

- **Improve radio range**: Move device closer or add a repeater (any mains-powered Homematic device acts as repeater)
- **Replace batteries**: Even if the device still works, low batteries can cause intermittent communication issues
- **Reset STICKY_UNREACH**: In the CCU WebUI, set `STICKY_UNREACH` to `false` for the device
- **Wait for CONFIG_PENDING**: After pairing or configuration changes, wait until `CONFIG_PENDING` becomes `false`
- **Re-pair the device**: As a last resort, remove and re-pair the device with the CCU

**Alternative behavior (force availability):**

If you prefer to have devices remain available in Home Assistant despite UNREACH events (similar to how some interpret the CCU WebUI behavior), you have two options:

1. **Service call**: Use the `homematicip_local.force_device_availability` service to manually force a device to be marked as available. See the [integration documentation](https://github.com/SukramJ/homematicip_local?tab=readme-ov-file#homematicip_localforce_device_availability) for details.

2. **Automation with Blueprint**: Use the "Reactivate" blueprints to automatically restore device availability after UNREACH events. These blueprints monitor for UNREACH events and automatically call the force availability service. See the [Reactivate Blueprints](https://github.com/SukramJ/homematicip_local?tab=readme-ov-file#blueprints) in the integration documentation.

**Note:** Using these options means Home Assistant will show the device as available even when communication with the CCU is impaired. Use with caution, as this may hide actual device problems.

### D) Writing fails (service call fails)

**Symptoms:**

- Service calls to control devices fail with an error
- Switches don't toggle, lights don't turn on, thermostats don't change temperature
- Error messages appear in the Home Assistant log

**Possible causes:**

1. **Validation error**: Wrong parameter name, type, or value range
2. **Device unavailable**: The device is marked as unavailable (see section C)
3. **Wrong channel**: The parameter exists on a different channel than expected
4. **Permission issue**: CCU user doesn't have write permissions
5. **Device busy**: The device is processing another command

**Diagnostic steps:**

1. Check the Home Assistant logs for the specific error message
2. Verify the device is available (not showing as unavailable)
3. In the CCU WebUI, check the Paramset description for valid values

**Common validation errors and solutions:**

| Error                | Cause                | Solution                                       |
| -------------------- | -------------------- | ---------------------------------------------- |
| "Value out of range" | Number too high/low  | Check the parameter's MIN/MAX values           |
| "Invalid parameter"  | Wrong parameter name | Verify the exact parameter name in CCU         |
| "Invalid channel"    | Wrong channel number | Find the correct channel for this parameter    |
| "Invalid type"       | Wrong data type      | Use correct type (number vs string vs boolean) |

**Solutions:**

- Check the entity attributes in Home Assistant to see valid value ranges
- Use the CCU WebUI to test if the parameter can be set there
- Verify the user configured in the integration has write permissions
- Ensure the device is available before sending commands

### E) HmIP devices missing or not updating

**Symptoms:**

- HomematicIP (HmIP) devices don't appear in Home Assistant
- HmIP devices appear but don't update or respond to commands
- Classic Homematic devices work fine, but HmIP devices don't

**Possible causes:**

1. HmIP service on the CCU not running or not properly paired
2. Wrong port configuration (HmIP uses different ports than classic Homematic)
3. JSON-RPC session/token expired or invalid
4. CCU's HmIP radio module not functioning

**Diagnostic steps:**

1. In the CCU WebUI, check **Settings** → **System Control** → verify HmIP service is running
2. Check if HmIP devices work in the CCU WebUI itself
3. Look for JSON-RPC related errors in the Home Assistant logs
4. Verify port 2010 (or 42010 for TLS) is accessible

**Solutions:**

- Restart the CCU to restart all services including HmIP
- Check the CCU's system diagnostics for HmIP radio module status
- Restart the Home Assistant integration (or restart Home Assistant entirely)
- If problems persist, re-pair the HmIP devices in the CCU

### F) No events after restart

**Symptoms:**

- After restarting Home Assistant or the CCU, devices show initial values but don't update
- Everything was working before the restart
- Logs show the integration started successfully

**Possible causes:**

1. Callback registration after reconnect failed
2. The callback port is now blocked or in use by another process
3. A reverse proxy or SSL terminator is interfering with the callback connection
4. The CCU hasn't re-established the callback subscription

**Diagnostic steps:**

1. Check logs for "Registering callback" messages after restart
2. Verify the callback port is still available and not used by another service
3. If using a reverse proxy, check it allows the callback connection

**Solutions:**

- Restart the integration from **Settings** → **Devices & Services** → Homematic(IP) Local → **Reload**
- If using Docker with bridge networking, ensure port mappings are still correct
- For persistent issues, try host networking mode in Docker
- Check if any recent network changes might have affected connectivity

### G) CONFIG_PENDING stays True

**Symptoms:**

- A device's `CONFIG_PENDING` parameter stays `true` indefinitely
- The device might work partially but seems incomplete
- Some features or parameters are missing

**Understanding CONFIG_PENDING:**

`CONFIG_PENDING` indicates that the device has configuration that needs to be transmitted but hasn't been fully applied yet. This is common:

- After initial pairing
- After changing device settings in the CCU
- For battery-powered devices that need to wake up to receive configuration

**Possible causes:**

1. Battery-powered device is asleep and hasn't woken up to receive configuration
2. Device is out of radio range
3. Configuration process was interrupted
4. Device has a problem preventing configuration completion

**Solutions:**

- **Battery devices**: Press a button on the device to wake it up and trigger configuration transfer
- **Wait**: Some devices may take several hours to complete configuration (especially battery-powered ones)
- **Check range**: Ensure the device is within radio range of the CCU or a repeater
- **Re-pair**: If nothing else works, remove the device from the CCU and pair it again
- **Note**: aiohomematic automatically refreshes MASTER parameters once `CONFIG_PENDING` becomes `false`

### H) New devices not detected or devices incompletely recognized

**Symptoms:**

- You added a new device to the CCU but it doesn't appear in Home Assistant
- A device appears but is missing channels or entities
- Device was working before but after a CCU update it's incomplete

**Possible causes:**

1. Home Assistant's cache contains outdated device information
2. The device wasn't fully paired when the cache was last built
3. CCU has new device information but Home Assistant hasn't fetched it
4. Device configuration changed but cache wasn't invalidated

**Understanding the cache:**

aiohomematic caches device descriptions and parameter information for faster startup. This cache is normally updated automatically, but in some situations it can become outdated.

**Solutions:**

1. **Clear the cache**: Use the `homematicip_local.clear_cache` service:
   - Go to **Developer Tools** → **Services** in Home Assistant
   - Search for `homematicip_local.clear_cache`
   - Select your integration instance
   - Click **Call Service**
2. **Restart Home Assistant** after clearing the cache
3. This forces a fresh discovery of all devices and their parameters

See the [integration documentation](https://github.com/SukramJ/homematicip_local?tab=readme-ov-file#homematicip_localclear_cache) for more details about the clear_cache service.

### I) Unifi Firewall alerts: "ET EXPLOIT HTTP POST with Common Ruby RCE Technique in Body"

**Symptoms:**

- Unifi firewall shows security alerts for traffic between Home Assistant and CCU
- Alert message mentions "Ruby RCE" or similar exploit detection
- Homematic communication might be blocked or intermittent

**Understanding this alert:**

This is a **false positive**. The Unifi Firewall uses Suricata IDS (Intrusion Detection System) which incorrectly identifies XML-RPC communication as a potential exploit. Here's why:

- XML-RPC uses tags like `<methodCall>`, `<methodName>`, and `<params>`
- These tags resemble patterns found in Ruby marshal data
- Suricata rule SID 2019401 triggers on these patterns, assuming it's a Ruby code injection attempt
- **The traffic is completely legitimate** Homematic communication

**Solutions:**

1. **Create an IDS suppression rule** (recommended):

   - In Unifi Network Console, go to **Settings** → **Security** → **Threat Management**
   - Under **Suppression**, add an exception:
     - Source IP: Your Home Assistant IP
     - Destination IP: Your CCU IP
     - Or suppress signature ID `2019401` for traffic between these hosts

2. **Use TLS-encrypted ports** (alternative):
   - Configure the integration to use encrypted ports (e.g., 42001 instead of 2001)
   - This prevents the IDS from inspecting the payload content

**Note:** This alert is harmless for legitimate CCU communication and can be safely suppressed.

---

## 4) Network, ports, and containers

### Required ports

| Protocol     | Standard Port | TLS Port | Description                         |
| ------------ | ------------- | -------- | ----------------------------------- |
| BidCos-RF    | 2001          | 42001    | Classic Homematic wireless          |
| BidCos-Wired | 2000          | 42000    | Classic Homematic wired             |
| HmIP-RF      | 2010          | 42010    | HomematicIP                         |
| Groups       | 9292          | 49292    | Heating groups (virtual thermostat) |
| JSON-RPC     | 80/443        | -        | CCU WebUI API (used for HmIP)       |

### Callback connection

The callback is the **reverse connection** from the CCU to Home Assistant:

```
┌─────────────────┐                      ┌─────────────────┐
│  Home Assistant │ ◄──── Callback ───── │       CCU       │
│   (port XXXXX)  │                      │                 │
└─────────────────┘                      └─────────────────┘
```

- Home Assistant opens a port and tells the CCU: "Send events to this IP and port"
- The CCU then connects to Home Assistant when events occur
- **This port must be reachable from the CCU's network**

### Docker and container networking

**Host networking (recommended for simplicity):**

```yaml
# docker-compose.yml
services:
  homeassistant:
    network_mode: host
    # No port mappings needed - container uses host's network directly
```

- CCU can reach Home Assistant on the host's IP
- No port mapping complications
- Callback works automatically

**Bridge networking (requires careful configuration):**

```yaml
# docker-compose.yml
services:
  homeassistant:
    ports:
      - "8123:8123" # Home Assistant web interface
      # Callback port is dynamically assigned - may need to configure a static port
```

- You must ensure the callback port is published
- The callback IP must be the Docker host's IP, not the container's internal IP
- Consider using a static callback port in the integration configuration

### Firewall considerations

Common firewalls that might block the callback:

| Firewall                | Check command                  | Configuration location    |
| ----------------------- | ------------------------------ | ------------------------- |
| ufw (Ubuntu)            | `sudo ufw status`              | `/etc/ufw/user.rules`     |
| firewalld (Fedora/RHEL) | `sudo firewall-cmd --list-all` | `firewall-cmd` commands   |
| iptables                | `sudo iptables -L`             | `/etc/iptables/rules.v4`  |
| Windows Firewall        | `Get-NetFirewallRule`          | Windows Security settings |
| NAS firewalls           | Varies                         | NAS admin interface       |

**Example: Allow callback port with ufw:**

```bash
sudo ufw allow from <CCU-IP> to any port <callback-port> proto tcp
```

---

## 5) Logging and debug

### Enabling debug logging

Add to your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    # Main integration logging
    aiohomematic: debug
    custom_components.homematicip_local: debug
```

For more targeted logging, you can enable debug for specific modules:

```yaml
logger:
  default: info
  logs:
    # Specific modules for targeted debugging
    aiohomematic.caches: debug # Cache operations
    aiohomematic.central: debug # Central unit operations
    aiohomematic.central_events: debug # Event handling
    aiohomematic.client: debug # Client communication
    aiohomematic.model: debug # Device/entity model
```

After changing logging configuration, restart Home Assistant.

### Interpreting common log messages

| Log message             | Meaning                                      | Action                          |
| ----------------------- | -------------------------------------------- | ------------------------------- |
| "Registering callback…" | Integration is setting up event subscription | Normal - good sign              |
| "Subscribed…"           | Callback registration successful             | Normal - events should work     |
| "Connection refused"    | Cannot connect to CCU                        | Check CCU IP/port/firewall      |
| "Connection timeout"    | CCU not responding                           | Check CCU status and network    |
| "401 Unauthorized"      | Wrong username/password                      | Verify credentials              |
| "403 Forbidden"         | User lacks permissions                       | Check CCU user permissions      |
| "404 Not Found"         | Wrong endpoint/port                          | Verify port configuration       |
| "Validation error"      | Invalid parameter value                      | Check parameter name/type/range |

### Downloading diagnostics

The integration provides a diagnostics download feature:

1. Go to **Settings** → **Devices & Services**
2. Find the Homematic(IP) Local integration
3. Click the three dots menu (⋮)
4. Select **Download diagnostics**

This file contains useful connectivity and configuration data for troubleshooting.

---

## 6) When opening an issue, please provide

When reporting issues on GitHub, include the following information to help with diagnosis:

### Environment information

- **CCU type and firmware version**: CCU3 firmware 3.x.x, piVCCU version, Homegear version, etc.
- **Home Assistant version**: Core version (e.g., 2024.1.0)
- **Integration version**: Homematic(IP) Local version
- **Python version** (if relevant): Usually matches Home Assistant's Python

### Network setup

- **Installation type**: Docker, Home Assistant OS, supervised, etc.
- **Networking mode**: Host networking, bridge networking, specific port mappings
- **Proxy/VPN**: Any reverse proxy, VPN, or special network configuration
- **VLANs/Subnets**: Are Home Assistant and CCU on the same network segment?

### Problem description

- **Exact symptoms**: What exactly isn't working?
- **What works**: What still functions correctly?
- **When did it start**: After an update? After a configuration change? Randomly?
- **Steps to reproduce**: How can the problem be triggered?

### Logs and diagnostics

- **Debug logs**: From Home Assistant startup to the first error (at debug level)
- **Diagnostics file**: Download from the integration
- **Affected devices**: List of device types and addresses that are affected
- **Device types**: Which are HmIP vs. classic Homematic?

---

## 7) References

- [Lifecycle documentation](../docs/homeassistant_lifecycle.md) - Understand how devices and data points are managed
- [README](../README.md) - Quickstart guide and configuration notes
- [Integration repository](https://github.com/SukramJ/homematicip_local) - Homematic(IP) Local integration for Home Assistant
- [Integration documentation](https://github.com/SukramJ/homematicip_local?tab=readme-ov-file#services) - Available services and their usage
- [Blueprints](https://github.com/SukramJ/homematicip_local?tab=readme-ov-file#blueprints) - Automation blueprints including Reactivate
