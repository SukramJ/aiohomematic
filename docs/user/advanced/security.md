# Security Best Practices

This guide covers security considerations for aiohomematic and the Homematic(IP) Local integration.

## Overview

aiohomematic communicates with your Homematic backend (CCU/Homegear) using XML-RPC and JSON-RPC protocols. Securing this communication protects your smart home from unauthorized access.

!!! warning "Backend Security is Critical"
CCU, OpenCCU (RaspberryMatic), and Homegear have had **serious security vulnerabilities** in the past, including unauthenticated remote code execution. **Never expose your backend to the internet** and keep firmware updated.

## Known Backend Vulnerabilities

### Critical: Never Expose to Internet

Homematic backends (CCU2, CCU3, OpenCCU, Homegear) are **not designed for internet exposure**. Historical vulnerabilities include:

| Year | Affected               | Issue                                                                                                                                                  | Severity |
| ---- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | -------- |
| 2024 | RaspberryMatic ≤3.73.9 | [Unauthenticated RCE via ZipSlip](https://mogwailabs.de/en/advisories/mlsa-2024-001/)                                                                  | Critical |
| 2020 | CCU2/CCU3 WebUI        | [Unauthenticated RCE as root](https://www.cvedetails.com/vulnerability-list/vendor_id-17729/product_id-58075/opec-1/Eq-3-Homematic-Ccu3-Firmware.html) | Critical |
| 2019 | CCU3                   | [Local File Inclusion (CVE-2019-9726)](https://pentest-tools.com/vulnerabilities-exploits/homematic-ccu3-local-file-inclusion_2766)                    | High     |
| 2019 | CCU2/CCU3 + XML-API    | Unauthenticated RCE via exec.cgi                                                                                                                       | Critical |
| 2019 | CCU2/CCU3              | Session fixation, password hash disclosure                                                                                                             | High     |
| 2019 | CCU2/CCU3 + CUxD       | Admin operations without authentication                                                                                                                | Critical |

### Required Actions

1. **Keep firmware updated** - Install security patches immediately
2. **Never port-forward CCU ports** - Use VPN for remote access
3. **Isolate on separate VLAN** - Limit blast radius of potential compromise
4. **Enable authentication** - Even on internal network
5. **Remove unused add-ons** - XML-API, CUxD have had vulnerabilities

### Checking Your Version

**CCU/OpenCCU:**

1. CCU WebUI → Settings → Control Panel → System
2. Check firmware version
3. Compare with [latest OpenCCU release](https://github.com/OpenCCU/OpenCCU/releases)

**Homegear:**

```bash
homegear -v
```

### Security Advisories

Monitor these sources for new vulnerabilities:

- [OpenCCU Security Advisories](https://github.com/OpenCCU/OpenCCU/security/advisories)
- [eQ-3 CVE List](https://www.cvedetails.com/vulnerability-list/vendor_id-17729/Eq-3.html)
- [Homegear GitHub](https://github.com/Homegear/Homegear)

## Authentication

### CCU Authentication

**Always enable authentication** on your CCU:

1. CCU WebUI → **Settings** → **Control Panel** → **Security**
2. Enable **Authentication**
3. Create a dedicated user for Home Assistant

### User Requirements

| Requirement    | Details                                     |
| -------------- | ------------------------------------------- |
| **Privileges** | Administrator role required                 |
| **Username**   | Case-sensitive, use exactly as shown in CCU |
| **Password**   | See allowed characters below                |

### Password Requirements

Only these characters are supported in passwords:

```
A-Z  a-z  0-9  . ! $ ( ) : ; # -
```

**Not supported:**

- Umlauts: `Ä ä Ö ö Ü ü ß`
- Other special characters: `@ & * % ^ ~`
- Unicode characters

These work in CCU WebUI but **fail** via XML-RPC.

## TLS Configuration

### Enabling TLS

1. **Enable TLS on CCU first:**

   - CCU WebUI → Settings → Control Panel → Security
   - Enable HTTPS

2. **Configure integration:**
   - Enable "Use TLS" in integration settings
   - Set "Verify TLS" based on certificate type

### Certificate Types

| Certificate Type      | Verify TLS Setting | Notes                              |
| --------------------- | ------------------ | ---------------------------------- |
| Self-signed (default) | `false`            | CCU default, no chain verification |
| Let's Encrypt         | `true`             | Valid chain, full verification     |
| Custom CA             | `true`             | Must add CA to system trust store  |

### TLS Ports

| Interface       | Plain Port | TLS Port |
| --------------- | ---------- | -------- |
| HmIP-RF         | 2010       | 42010    |
| BidCos-RF       | 2001       | 42001    |
| BidCos-Wired    | 2000       | 42000    |
| Virtual Devices | 9292       | 49292    |
| JSON-RPC        | 80         | 443      |

## Network Security

### Firewall Configuration

**Inbound to CCU** (from Home Assistant):

| Port       | Protocol | Service                          |
| ---------- | -------- | -------------------------------- |
| 80/443     | TCP      | JSON-RPC (names, rooms, sysvars) |
| 2001/42001 | TCP      | BidCos-RF                        |
| 2010/42010 | TCP      | HmIP-RF                          |
| 2000/42000 | TCP      | BidCos-Wired (if used)           |
| 9292/49292 | TCP      | Virtual Devices (if used)        |

**Inbound to Home Assistant** (from CCU):

| Port          | Protocol | Service                          |
| ------------- | -------- | -------------------------------- |
| Callback port | TCP      | XML-RPC callbacks (configurable) |

### Network Segmentation

Recommended network architecture:

```
Internet
    │
    ▼
┌─────────────────┐
│  Router/FW      │  ← No inbound from internet
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌───────┐  ┌───────┐
│  IoT  │  │ Main  │
│ VLAN  │  │ LAN   │
│       │  │       │
│ CCU   │  │  HA   │  ← Allow CCU ↔ HA only
│       │  │       │
└───────┘  └───────┘
```

### Docker Security

For Docker installations:

**Recommended:** Use `network_mode: host`

**Alternative (Bridge Network):**

1. Set `callback_host` to Docker host IP
2. Only expose callback port (not all CCU ports)
3. Use internal Docker network where possible

```yaml
services:
  homeassistant:
    network_mode: host # Recommended for callback support
    # OR with bridge:
    ports:
      - "8123:8123" # HA UI
      - "43439:43439" # Callback port only
```

## Secrets Management

### Never Commit Credentials

Exclude from version control:

```gitignore
# .gitignore
*.env
secrets.yaml
credentials.json
```

### Home Assistant Secrets

Use `secrets.yaml`:

```yaml
# secrets.yaml (not in version control)
ccu_password: your-secure-password

# configuration.yaml
homematic:
  password: !secret ccu_password
```

### Environment Variables

For standalone library use:

```python
import os
from aiohomematic.api import HomematicAPI

async with HomematicAPI.connect(
    host=os.environ["CCU_HOST"],
    username=os.environ["CCU_USER"],
    password=os.environ["CCU_PASSWORD"],
) as api:
    ...
```

## Access Control

### Principle of Least Privilege

- Create dedicated CCU user for Home Assistant
- Don't use main admin account
- Disable CCU user when not in use (maintenance)

### Network Access

- Restrict CCU management interface to trusted IPs
- Use VPN for remote access (not port forwarding)
- Monitor CCU access logs

## Security Checklist

| Check                                 | Status |
| ------------------------------------- | ------ |
| CCU authentication enabled            | [ ]    |
| Dedicated user for HA created         | [ ]    |
| Password uses only allowed characters | [ ]    |
| TLS enabled (if possible)             | [ ]    |
| Firewall rules configured             | [ ]    |
| No CCU ports exposed to internet      | [ ]    |
| secrets.yaml for credentials          | [ ]    |
| Regular CCU firmware updates          | [ ]    |

## Common Security Issues

### Issue: "Authentication failed"

**Causes:**

- Wrong username/password
- Password contains unsupported characters
- User lacks admin privileges

**Solution:**

1. Verify credentials in CCU WebUI
2. Check password for special characters
3. Verify user role is Administrator

### Issue: Callbacks not working

**Causes:**

- Firewall blocking CCU → HA
- Incorrect callback_host setting

**Solution:**

1. Ensure CCU can reach HA on callback port
2. Set callback_host to HA's IP (not localhost)
3. Check Docker network configuration

## Reporting Security Issues

Report security vulnerabilities privately:

1. **Do not** open public GitHub issues for security bugs
2. Contact maintainers directly via GitHub security advisories
3. Allow time for fix before public disclosure

## Related Documentation

- [Troubleshooting](../../troubleshooting/index.md) - Connection issues
- [CUxD and CCU-Jack](cuxd_ccu_jack.md) - MQTT security
- [User Guide](../homeassistant_integration.md) - Configuration
