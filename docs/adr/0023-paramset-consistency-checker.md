# ADR-0023: Paramset Consistency Checker

## Status

Implemented

## Date

2026-02-09

## Context

### The HmIPServer Staleness Problem

The Homematic XML-RPC API exposes two complementary endpoints for device configuration:

- **`getParamsetDescription()`** returns the _schema_ - which parameters a device channel
  supports, their types, ranges, and access flags.
- **`getParamset()`** returns the _values_ - the actual stored configuration data for those
  parameters.

These two endpoints should always be consistent: every parameter described in the schema
should have a corresponding value in the data. However, a
[bug in the HmIPServer (crRFD)](https://homematic-forum.de/forum/viewtopic.php?t=77531),
documented by jmaus (RaspberryMatic developer), breaks this invariant.

After a device firmware update, the HmIPServer updates its schema (`.dev` files) to
reflect new parameters but does **not** re-read the actual parameter values from the
device. The result is a _phantom parameter_ - described in the schema, absent from the
data.

**Example:** An HmIP-FSM16 with firmware 1.22.8 introduces `CHANNEL_OPERATION_MODE` on
channel 5 (to switch between consumption and feed-in metering). The schema correctly
lists the parameter, but the data endpoint returns it as if it doesn't exist. The
parameter is invisible to all clients.

### Impact on aiohomematic

aiohomematic creates data points based on the schema (`getParamsetDescription()`). When a
parameter exists in the schema but not in the data, the resulting data point is technically
valid but functionally broken - it has no value, cannot be read, and cannot be written.
This manifests as:

1. **Phantom entities in Home Assistant** that appear in the UI but always show
   "unavailable" or stale defaults.
2. **Silent failure** - no indication to the user why a feature that should be available
   after a firmware update is missing.
3. **Recurring support requests** across multiple device types: HmIP-FSM16, HmIP-SPI,
   HmIP-SMO, HmIPW-WTH, HMIP-SWDO, and potentially others.

### What We Can and Cannot Do

Only eQ-3 can fix the root cause (the HmIPServer should re-read device parameters after
firmware updates). The only user-side remedy is a **factory reset** of the affected device
on the CCU, which forces the HmIPServer to re-read all parameters from scratch.

aiohomematic's role is limited to **detection and notification**.

## Decision

Add a consistency check that compares schema (cached `getParamsetDescription()`) against
data (`getParamset()` via RPC) for MASTER paramsets after device creation, and surfaces
discrepancies to the user via the existing reporting infrastructure.

### Core Concept: Schema-vs-Data Comparison

The check exploits a simple invariant:

```
For every parameter P in getParamsetDescription(channel, MASTER)
  where P.OPERATIONS > 0:
    P must also appear as a key in getParamset(channel, MASTER)
```

A violation of this invariant indicates the HmIPServer staleness bug.

The `OPERATIONS > 0` filter is essential: parameters with `OPERATIONS = 0` are internal
metadata that may legitimately be absent from `getParamset()` responses.

### Design Principles

1. **Detection only** - We cannot repair the data; we can only tell the user what's wrong
   and how to fix it (factory reset).

2. **Non-blocking** - The check runs as a background task after device creation. Devices
   are immediately available; the consistency check is purely advisory and must never delay
   startup or block the device creation pipeline.

3. **MASTER paramsets only** - The bug manifests exclusively in MASTER (configuration)
   paramsets. VALUES paramsets are volatile runtime data and are not affected.

4. **HmIP scope only** - The HmIPServer (crRFD) is the only backend component affected.
   BidCos-RF devices (managed by rfd) and Homegear devices are not subject to this bug.
   The check filters by `ProductGroup.HMIP` and `ProductGroup.HMIPW`.

5. **Dual reporting** - Discrepancies are reported through two channels:

   - **IncidentStore** (persistent diagnostics, survives restarts, visible in
     diagnostics export)
   - **IntegrationIssue via SystemStatusChangedEvent** (surfaced as HA Repair issue,
     immediately actionable by the user)

6. **Idempotent** - Running the check multiple times with unchanged data produces
   identical results.

### When the Check Runs

The check is triggered after `create_devices()` completes during the `_add_new_devices()`
flow. This is the natural point: paramset descriptions are freshly cached, devices are
just created, and the schema-data comparison can be performed while the system is already
communicating with the CCU.

```
_add_new_devices()
  │
  ├─ fetch paramset descriptions
  ├─ create_devices()          ← Devices available immediately
  │
  └─ schedule background task  ← Consistency check (non-blocking)
      └─ for each HmIP device + channel:
           compare schema keys vs. data keys
```

### Reporting Strategy

The checker aggregates all missing parameters per device (across all channels) into a
single report. This avoids noise: a device with 3 missing parameters across 2 channels
produces one incident and one integration issue, not six.

Missing parameters are identified in `{channel_address}:{parameter_name}` format (e.g.,
`VCU0000001:5:CHANNEL_OPERATION_MODE`) to allow precise attribution.

### Error Handling Philosophy

The consistency check is advisory - it must never cause harm:

- If a device is temporarily unreachable during `get_paramset()`, the channel is
  silently skipped. No false positive is generated.
- If the `IncidentRecorderProtocol` is unavailable (optional dependency), the check
  still reports via `IntegrationIssue`.
- If no inconsistencies are found, nothing is reported (no "all clear" noise).

## Architecture

### Data Flow

```
┌─────────────────────────┐     ┌──────────────────────┐
│ ParamsetDescription     │     │ InterfaceClient      │
│ Registry (cached)       │     │ get_paramset()       │
│                         │     │                      │
│ "What SHOULD exist"     │     │ "What DOES exist"    │
└────────────┬────────────┘     └──────────┬───────────┘
             │ expected params             │ actual params
             └──────────┬─────────────────-┘
                        │ set difference
                        ▼
                ┌───────────────┐
                │ Missing any?  │
                └───────┬───────┘
                        │ yes
             ┌──────────┴──────────┐
             ▼                     ▼
  ┌──────────────────┐  ┌────────────────────┐
  │  IncidentStore   │  │  SystemStatus      │
  │  (diagnostics)   │  │  ChangedEvent      │
  │                  │  │  (IntegrationIssue) │
  └──────────────────┘  └─────────┬──────────┘
                                  │
                                  ▼
                        ┌────────────────────┐
                        │  Home Assistant     │
                        │  Repair Issue       │
                        └────────────────────┘
```

### Integration Points

The checker integrates into existing infrastructure without introducing new abstractions:

- **DeviceCoordinator** hosts the check logic (consistent with its role as device
  lifecycle manager).
- **IncidentRecorderProtocol** provides persistent diagnostics recording (optional
  dependency via DI).
- **SystemStatusChangedEvent + IntegrationIssue** is the established pattern for
  surfacing actionable issues to Home Assistant (same as `PING_PONG_MISMATCH` and
  `INCOMPLETE_DEVICE_DATA`).
- **i18n.tr()** provides localized log messages (English and German).

## Risks and Mitigations

| Risk                         | Likelihood | Impact | Mitigation                                                |
| ---------------------------- | ---------- | ------ | --------------------------------------------------------- |
| RPC calls slow startup       | Low        | Low    | Background task; devices available before check runs      |
| Device unreachable mid-check | Medium     | Low    | Per-channel try/except; other devices still checked       |
| False positives              | Low        | Medium | OPERATIONS > 0 filter; HmIP-only scope                    |
| CCU rate limiting            | Low        | Low    | Existing request coalescing handles deduplication         |
| User fatigue from warnings   | Medium     | Low    | WARNING severity; includes actionable fix (factory reset) |

## Deferred Work

### CONFIG_PENDING Re-Check

After a factory reset, the CCU sends `CONFIG_PENDING = False`. This would be an ideal
trigger to re-verify that the inconsistency is resolved. Deferred because:

- The initial device creation check covers the primary discovery scenario
- CONFIG_PENDING handling requires model-layer changes
- Can be added incrementally without breaking changes

### Periodic Re-Verification

A periodic background check (e.g., weekly) could catch inconsistencies that develop
after initial device creation (e.g., firmware updates during runtime). Deferred because
the startup check covers the most important case and periodic checks add RPC overhead.

## Alternatives Considered

### 1. Hub-Level Diagnostic Sensor

Expose a sensor with the count of inconsistent devices. Rejected because it provides no
device-specific information, requires periodic polling, and adds permanent UI clutter for
a condition that affects few users.

### 2. Automatic Paramset Repair

Call `putParamset()` with default values for missing parameters. Rejected because it could
cause unintended device behavior, may not work (HmIPServer might reject writes to
parameters it doesn't track), and violates the detection-only principle.

### 3. Startup-Blocking Validation

Run the check synchronously during startup and refuse to create data points for
inconsistent parameters. Rejected because it delays device availability and removes
entities that are technically valid (they just have no current value).

## References

- [Forum discussion by jmaus](https://homematic-forum.de/forum/viewtopic.php?t=77531) -
  original analysis of the HmIPServer staleness bug
- [HmIP XML-RPC API Addendum](https://www.eq-3.de/downloads/download/homematic/hm_web_ui_doku/HMIP_XmlRpc_API_Addendum.pdf) -
  eQ-3 API documentation for `getParamsetDescription()` and `getParamset()`
- [Troubleshooting guide](../troubleshooting/paramset_inconsistency.md) - end-user
  documentation for this feature
