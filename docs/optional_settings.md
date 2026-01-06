# Optional Settings (Experimental Features)

## Overview

Optional Settings are feature flags that allow you to test new, experimental implementations in the Homematic(IP) Local integration. These settings are configured through the Home Assistant integration options.

**Important**: These are experimental features. They are not enabled by default and should only be activated if you are willing to provide feedback and can tolerate potential instability.

**Current Status**: All experimental features have passed comprehensive unit and integration tests. They have also been tested by developers with real hardware (CCU3, OpenCCU). The next step is field testing by users with diverse setups to ensure compatibility across all environments before general release.

---

## Why Do These Settings Exist?

### The Challenge

The Homematic(IP) Local integration supports a wide variety of backend systems:

- **CCU3/CCU2** - Original eQ-3 Homematic central units
- **OpenCCU** - Community-based CCU for Raspberry Pi and other platforms
- **Homegear** - Open-source Homematic backend
- **CCU-Jack** - JSON-RPC bridge for CCU
- **debmatic** - Homematic on Debian-based systems

Each of these systems has subtle differences in behavior. When we develop new, improved implementations of core components, we cannot simply replace the existing code overnight—doing so would risk breaking systems for thousands of users.

### The Solution: Opt-In Testing

Instead of forcing new code on everyone, we use feature flags:

1. **You choose** whether to try the new implementation
2. **Old and new code coexist** side by side
3. **Easy rollback** - just disable the setting if something goes wrong
4. **Your feedback** helps us identify problems before general release

This approach allows us to thoroughly test new architectures in real-world environments before making them the default for everyone.

---

## Available Settings

### Async RPC Server

📢 **Feedback Discussion**: [#2727](https://github.com/SukramJ/aiohomematic/discussions/2727)

**What it does**: Replaces the traditional thread-based XML-RPC server with a modern, asynchronous implementation.

**Why it exists**: The original RPC server uses a separate thread to receive events from your CCU. While this works reliably, it doesn't integrate optimally with Home Assistant's async architecture. The new async server runs entirely within Home Assistant's event loop, potentially improving resource usage and event handling.

**What to expect**:
- Similar functionality to the current implementation
- A new health check endpoint for diagnostics
- Built-in metrics collection

**Potential issues**:
- Under very high event load, some events might be delayed
- If you notice devices not updating, disable this setting

---

### Interface Client

📢 **Feedback Discussion**: [#2728](https://github.com/SukramJ/aiohomematic/discussions/2728)

**What it does**: Uses a completely redesigned client architecture for communicating with your CCU.

**Why it exists**: The original code has three separate client implementations (one for CCU, one for Homegear, one for JSON-based CCU). This led to code duplication and made maintenance difficult. The new "Interface Client" uses a single, unified client with interchangeable backends—cleaner code that's easier to test and extend.

**What to expect**:
- Identical functionality from a user perspective
- Better error messages when things go wrong
- Foundation for future improvements

**Potential issues**:
- Some edge cases in paramset operations might behave differently
- If device configuration fails, disable this setting

---

### Linked Entity Climate Activity

📢 **Feedback Discussion**: [#2729](https://github.com/SukramJ/aiohomematic/discussions/2729)

**What it does**: Enables activity state detection for thermostats by checking linked switch actuators.

**Why it exists**: Some Homematic IP thermostats (like HmIP-STHD) don't report their heating activity directly. Instead, they control linked floor heating actuators (like HmIP-FAL230-C10) that do have activity state information. Without this feature, the "Current action" (hvac_action) in Home Assistant shows as unavailable for these thermostats.

When enabled, the integration looks at devices linked to your thermostat and uses their activity state to determine whether the thermostat is actively heating or idle.

**Who needs this**:
- Users with HmIP-STHD wall thermostats controlling floor heating actuators
- Users who see "Unknown" or missing activity state on their climate entities
- Anyone with thermostats that control heating through linked actuators rather than built-in valves

**What to expect**:
- Climate entities show correct "Heating" or "Idle" status
- Activity state updates when linked actuators change state
- No changes for thermostats that already report activity directly

**Potential issues**:
- Slightly increased processing when link peers change
- If activity state appears incorrect, verify your device links in the CCU

---

### Developer/Debugging Settings

The following settings are **not intended for regular users**. They exist solely for debugging purposes and should only be enabled when specifically requested by a developer to help diagnose an issue.

| Setting | Purpose |
|---------|---------|
| **SR_RECORD_SYSTEM_INIT** | Records all communication during startup for debugging |
| **SR_DISABLE_RANDOMIZE_OUTPUT** | Makes recorded data deterministic for test creation |

**Do not enable these settings unless a developer asks you to.** They generate additional data, may impact performance, and provide no benefit during normal operation.

---

## Who Should Use These Settings?

| If you are... | Recommendation |
|---------------|----------------|
| A regular user who just wants things to work | ❌ Leave all settings at default |
| Curious about new features but need stability | ❌ Wait for general release |
| Willing to test and report issues | ✅ Try one setting at a time |
| Experiencing a specific issue a developer asked you to debug | ✅ Enable only the requested setting |

---

## How to Provide Feedback

If you test an experimental feature, your feedback is invaluable. Here's what helps us most:

### What Worked

- "Enabled Async RPC Server, running for 3 days without issues"
- "Interface Client working fine with OpenCCU 3.x"

### What Didn't Work

Please include:
1. **Which setting** you enabled
2. **Your backend type** (CCU3, OpenCCU, Homegear, etc.)
3. **What happened** (error messages, unexpected behavior)
4. **Home Assistant logs** with debug logging enabled (see below)

### How to Enable Debug Logging

**Option 1: Via Home Assistant UI**
1. Go to **Settings** → **Devices & Services**
2. Find **Homematic(IP) Local** and click on it
3. Click **Enable debug logging**
4. Reproduce the issue
5. Click **Disable debug logging** - this will download the log file automatically

**Option 2: Via configuration.yaml**
```yaml
logger:
  logs:
    aiohomematic: debug
```
After adding this, restart Home Assistant and check the logs under **Settings** → **System** → **Logs**.

### Where to Report

- **GitHub Issues**: https://github.com/SukramJ/hahomematic/issues
- Use the tag `experimental-feature` when reporting

---

## Risks and Recommendations

### Before Enabling Any Experimental Setting

1. **Create a backup** of your CCU
2. **Note your current configuration** in case you need to revert
3. **Enable debug logging** so you have data if something goes wrong

### After Enabling

1. **Restart Home Assistant** for the setting to take effect
2. **Test your devices** - check that switches, sensors, thermostats respond correctly
3. **Monitor for 24-48 hours** before considering it stable

### If Something Goes Wrong

1. **Disable the experimental setting** in the integration options
2. **Restart Home Assistant**
3. **Report the issue** with your logs

The beauty of feature flags is that reverting is always just a toggle away.

---

## Roadmap

| Setting | Current Status | Future |
|---------|----------------|--------|
| Async RPC Server | Testing | Will become default if testing is successful |
| Interface Client | Testing | Will become default if testing is successful |
| Linked Entity Climate Activity | Testing | Will become default if testing is successful |
| Debugging settings (SR_*) | Developer tools | Will remain opt-in permanently |

Once an experimental feature has been thoroughly tested across different backend types and receives positive feedback, it will be promoted to the default implementation. At that point, the old implementation will be deprecated and eventually removed.

---

## Summary

- **Experimental settings** let you preview upcoming improvements
- **Your feedback** directly influences whether features are released
- **Easy to revert** if anything goes wrong
- **Not for everyone** - only enable if you're willing to report issues
- **Debugging settings** are developer tools, not user features

Thank you for helping improve Homematic(IP) Local!
