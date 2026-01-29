# Why Debug Logs and Diagnostics Matter

## The Problem We Face

When you report an issue, we cannot see your system. We don't know:

- Which devices you have
- How they are configured
- What communication happens between Home Assistant and your CCU
- What state your devices were in when the problem occurred

**Debug logs and diagnostics are our eyes into your system.** Without them, we are essentially trying to fix a car engine while blindfolded.

---

## What Diagnostics Contain

When you download diagnostics from Home Assistant (**Settings** → **Devices & Services** → find **Homematic(IP) Local** → click **⋮** on the integration card → **Download diagnostics**), you get a snapshot of your system that includes:

### Configuration

- Integration settings (host, interfaces, optional features)
- CCU/backend type and version
- Credentials are automatically redacted

### Device Models

- List of device model types in your system (e.g., "HmIP-eTRV-2", "HmIP-SWDO")
- Helps identify which device types are affected by an issue

### System Health

- Connection status per interface (HmIP-RF, BidCos-RF, etc.)
- Client state (connected, reconnecting, failed)
- Circuit breaker states
- Health scores and availability status

### Metrics Snapshot

- RPC communication statistics (request counts, failure rates, latencies)
- Event processing statistics
- Cache hit rates and sizes
- Recovery attempt statistics
- Device/channel/data point counts

### Incident History

- Recent diagnostic incidents (last 7 days)
- Ping-pong mismatches, connection losses, RPC errors
- Timestamps and context for each incident

**This data is automatically anonymized** - serial numbers and authentication credentials are redacted.

### Why This Matters

Without diagnostics, we would need to ask you dozens of questions:

- "What CCU type are you using?"
- "Which interfaces are enabled?"
- "Is the connection healthy or degraded?"
- "Have there been any recent connection issues?"
- "What device models do you have?"

Diagnostics answer all these questions instantly, saving hours of back-and-forth.

---

## What Debug Logs Contain

Debug logs capture the real-time communication and decision-making of the integration:

### RPC Communication

- Every request sent to your CCU
- Every response received
- Every event pushed from your CCU to Home Assistant

### State Changes

- When values change and why
- How the integration interprets incoming data
- Entity state transitions

### Error Context

- What was happening before an error occurred
- The exact error message and stack trace
- What the system tried to do and why it failed

### Timing Information

- When events occurred (timestamps)
- How long operations took
- Sequence of events leading to an issue

---

## Why Complete Logs Are Essential

### The Story Matters

Issues are rarely caused by a single event. They usually result from a sequence of events:

```
10:00:01 - Device sends value update
10:00:02 - Integration processes update
10:00:03 - State calculation runs
10:00:04 - Entity state becomes incorrect  ← You notice this
```

If you only provide logs starting at 10:00:04, we see the symptom but not the cause. We need the complete story.

### Partial Logs Hide the Truth

Consider this scenario:

**What you report**: "My thermostat shows wrong temperature"

**What partial logs show**:

```
Entity climate.living_room state updated to 21.5°C
```

**What complete logs show**:

```
Received event: ACTUAL_TEMPERATURE = 23.5 for channel ABC123:1
Processing value for climate entity...
WARNING: Channel ABC123:1 not found in device registry
Falling back to cached value: 21.5°C
Entity climate.living_room state updated to 21.5°C
```

The complete log reveals the actual problem: a channel lookup failure causing stale data to be displayed.

### Truncated Logs Lose Critical Information

If logging was enabled too late or disabled too early:

- We miss the initialization sequence that may have failed
- We miss the first occurrence of an error (often the most informative)
- We miss periodic background operations that might be related

---

## How to Provide Useful Debug Logs

### Step 1: Enable Debug Logging BEFORE Reproducing

**Via Home Assistant UI (Recommended)**:

1. Go to **Settings** → **Devices & Services**
2. Find **Homematic(IP) Local**
3. Click the three dots menu (**⋮**) on the integration card
4. Select **Enable debug logging**
5. **Wait** - let the system run for a moment
6. Reproduce the issue
7. Click the three dots menu (**⋮**) again → **Disable debug logging**
8. The log file downloads automatically

**Via configuration.yaml**:

```yaml
logger:
  logs:
    aiohomematic: debug
    custom_components.homematicip_local: debug
```

After adding this, restart Home Assistant completely. Logs are then available in **Settings** → **System** → **Logs**.

### Step 2: Reproduce the Issue

- Trigger the exact action that causes the problem
- Note the exact time when the issue occurred
- If possible, reproduce it 2-3 times

### Step 3: Capture the Complete Log

- Don't filter or truncate the log
- Include everything from when logging was enabled
- If the file is large, compress it (ZIP) before uploading

---

## Common Mistakes That Make Logs Useless

### "I only included the error lines"

**Problem**: Error messages without context are often meaningless. The lines before the error explain what led to it.

**Solution**: Include at least 50-100 lines before any error, preferably the complete log.

### "I summarized what the log said"

**Problem**: Human interpretation filters out details that seem unimportant but are actually crucial.

**Solution**: Always provide the raw, unedited log file.

### "I enabled logging after the issue occurred"

**Problem**: The cause happened before you started logging. You only captured the aftermath.

**Solution**: Enable logging, wait a moment, then reproduce the issue.

### "The log was too big so I cut out parts"

**Problem**: You might have removed the exact information we need.

**Solution**: Compress the file (ZIP) and upload it completely. GitHub accepts files up to 25MB.

---

## What We Can Diagnose With Good Data

With complete logs and diagnostics, we can:

| Issue Type                | What We Learn                                                                      |
| ------------------------- | ---------------------------------------------------------------------------------- |
| Entity shows wrong value  | Logs: The actual value received vs. what was displayed                             |
| Device not responding     | Logs: Whether commands are sent/received; Diagnostics: Device model, health status |
| Entity not created        | Logs: Why the entity was skipped during discovery                                  |
| Automation not triggering | Logs: Whether state changes were detected and processed                            |
| Connection drops          | Logs: Network errors; Diagnostics: Incident history, reconnect attempts            |
| Performance issues        | Logs: Slow operations; Diagnostics: Latency metrics, cache hit rates               |

---

## What We Cannot Diagnose Without Data

Without logs and diagnostics, we can only guess:

- "It might be a network issue" (we can't verify)
- "Maybe try restarting" (we don't know what's actually wrong)
- "This could be a known bug" (we can't confirm without seeing your specific situation)

This leads to:

- Longer resolution times
- Multiple rounds of "try this, try that"
- Frustration for everyone
- Issues that remain unresolved

---

## Privacy and Security

### What Is Automatically Redacted

The diagnostics download automatically removes:

- CCU serial number (replaced with `**REDACTED**`)
- Username and password

### What Remains Visible

- CCU hostname/IP address (needed for network troubleshooting)
- Device model types (e.g., "HmIP-eTRV-2")
- Interface configurations and ports
- Connection health status and metrics
- Incident timestamps and error messages

### If You Have Concerns

- You can review the diagnostics JSON file before sharing
- You can send sensitive logs directly to a developer via private message
- You can redact specific values manually if needed

---

## Summary

| Data Type       | Purpose                                         | How to Provide                  |
| --------------- | ----------------------------------------------- | ------------------------------- |
| **Diagnostics** | System snapshot - devices, configuration, state | Download from integration menu  |
| **Debug Logs**  | Real-time communication and decisions           | Enable before reproducing issue |

### The Golden Rule

**Enable logging → Wait → Reproduce → Download → Share completely**

Your debug data is not just helpful - it's essential. A well-documented issue with complete logs can be resolved in hours. An issue without data can take weeks of back-and-forth, or may never be resolved at all.

Thank you for taking the time to provide complete information. It makes a real difference.
