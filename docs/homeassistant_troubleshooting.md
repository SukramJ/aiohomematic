# Common Issues and Troubleshooting (Home Assistant)

This document helps you quickly analyze and resolve typical problems when using aiohomematic with Home Assistant (integration: Homematic(IP) Local). The notes apply to CCU (CCU3, RaspberryMatic, piVCCU) and Homegear unless stated otherwise.

Contents:

- Quick symptom mapping (at a glance)
- Step-by-step diagnostics
- Common issues with causes and solutions
- Network/ports/container specifics
- Capturing logs and debug information
- When to open an issue – required information

---

## 1) Quick symptom mapping

- No devices/entities visible after setup
  - Check connection details (host/IP, ports, auth), CCU reachability, and callback reachability from the CCU’s perspective.
- Entities present but without state changes
  - Event callbacks not arriving (firewall/NAT/Docker port mapping), XML‑RPC blocked, invalid session.
- Individual devices "unavailable" or stuck on old value
  - Device availability (UN_REACH/STICKY_UN_REACH), radio issues, battery-powered devices are sleeping, CONFIG_PENDING still active.
- Writing values doesn’t work
  - Permissions/auth, invalid parameter, validation error, wrong channel/parameter, device unavailable.
- HmIP devices missing
  - HmIP service on the CCU not active, wrong ports, session/token issue.
- After CCU/Home Assistant restart no updates arrive
  - Callback not re-registered, port blocked, reverse proxy/SSL terminator prevents internal connection.

---

## 2) Step-by-step diagnostics

1. Basic checks
   - CCU/Homegear WebUI reachable? Time/date correct? Sufficient CPU/RAM?
   - Can Home Assistant reach the CCU host/IP (ping)? Are ports open (see Ports section)?
2. Check configuration (HA integration)
   - Correct host/IP (no mDNS/hostname problems)?
   - Correct protocol selection (classic Homematic vs. HmIP vs Wired; the important part is the correct CCU details).
3. Callback reachability
   - The CCU must be able to reach the callback port provided by Home Assistant (from the CCU’s point of view!).
   - Check container/firewall: port exposure, bridged vs. host networking.
4. Enable logs (see Logging section)
   - Verify connection setup, method checks, device list retrieval, and event subscription.
5. Check device status
   - In the CCU: devices reachable? UN_REACH/STICKY_UN_REACH? CONFIG_PENDING is False?
6. Cache/restart
   - After significant changes, restart CCU and Home Assistant; caches are used but subscriptions are renewed on reconnect.

---

## 3) Common issues, causes, and solutions

### A) No entities after setup

- Cause
  - Wrong host/IP or CCU ports; authentication failed; RPC methods unavailable; CCU services not started.
- Solution
  - Verify host/IP and reachability; restart CCU; re-check during HA integration setup; inspect logs for exceptions/401/403/404/connection refused.

### B) Entities have no updates (only initial values or none)

- Cause
  - Event callback from CCU to HA is blocked: firewall/NAT/container network; wrong callback address; port in use.
- Solution
  - Ensure CCU can reach the HA callback (see Ports). Use host networking in Docker or correctly publish the port; adjust local firewall rules; avoid IP changes.

### C) Individual devices are "unavailable"

- Cause
  - UN_REACH/STICKY_UN_REACH; battery device sleeping; radio range; device re-paired but old address/ID still visible in HA cache.
- Solution
  - Pair/verify device, improve range, after successful communication wait for CONFIG_PENDING to clear; in HA, availability follows Device.available events from aiohomematic.

### D) Writing fails (service call fails)

- Cause
  - Invalid parameter (validation), device/channel not writable, device unavailable, wrong data type/range, permission issue.
- Solution
  - Check the HA error message; review validation errors in logs; in CCU verify Paramset description/MASTER; use correct number format/enum.

### E) HmIP devices missing or not updating

- Cause
  - HmIP service/access point pairing on CCU disturbed; JSON‑RPC session/token invalid; rate limits.
- Solution
  - Restart CCU; check system diagnostics in WebUI; inspect logs for JSON‑RPC errors; if needed renew session (restart the integration/HA).

### F) No events after restart

- Cause
  - Callback registration after reconnect failed; port blocked; reverse proxy interferes with internal traffic.
- Solution
  - Check whether the integration logs callback registration; verify port availability/proxy bypass; try HA host network mode.

### G) CONFIG_PENDING stays True

- Cause
  - Device is in configuration/pairing mode; MASTER parameters not consistent yet.
- Solution
  - Complete configuration on device/CCU; wait until CONFIG_PENDING becomes False. aiohomematic will then automatically refresh MASTER parameters.

---

## 4) Network, ports, and containers

- classic Homematic:
  - Common: 2001/42001(TLS) (BidCos‑RF), 2000/42000(TLS) (BidCos‑Wired),
- HomematicIP:
  - Common 2010/42010(TLS)
- Heating groups
  - Common 9292/49292(TLS)
- CuxD
- Callback from Home Assistant:
  - Home Assistant opens an HTTP callback port that the CCU must actively contact. This port must be reachable from the CCU network.
- Docker/container notes:
  - Host networking simplifies reachability (CCU can directly reach the host IP).
  - With bridge networking: publish port and provide the correct external IP/hostname to the CCU.
  - Configure firewalls accordingly (ufw, Windows Defender, NAS firewalls).

---

## 5) Logging and debug

- Adjust Home Assistant logger (configuration.yaml):

```
  logger:
    default: info
    logs:
      aiohomematic: debug
      custom_components.homematicip_local: debug
```

- Typical log hints:

  - "Registering callback…" / "Subscribed…": callback registration successful.
  - "Connection refused/timeout": network/port problem.
  - "401/403": check auth/permissions.
  - Validation errors on send: verify parameter names/types.

- Additional diagnostics:
  - In the HA integration use "Download diagnostics" – contains connectivity data.
  - In aiohomematic you can enable debug for specific modules:
    - aiohomematic.caches: debug
    - aiohomematic.central: debug
    - aiohomematic.central_events: debug
    - aiohomematic.client: debug
    - aiohomematic.model: debug

---

## 6) When opening an issue, please provide

- Environment: CCU type/firmware or Homegear version, Home Assistant version, integration (Homematic(IP) Local) version.
- Network setup: Docker yes/no, host/bridge, proxy/reverse proxy, VLANs/firewall.
- Exact symptoms: what works, what doesn’t? Since when? Steps to reproduce.
- Relevant logs at debug level (see above) – from startup to the first error.
- List of affected devices/channels and whether HmIP/HM classic.

---

## 7) References

- [Lifecycle](../docs/homeassistant_lifecycle.md) of devices/datapoints
- [README](../README.md) for quickstart and configuration notes
