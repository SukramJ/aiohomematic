# ADR 0021: Blind Command Processing Lock and Target Preservation

## Status

Accepted (2026-02-04)

---

## Context

### Problem

Homematic blind/cover devices exhibit a firmware bug: sending new positioning commands while the device is physically in motion causes undefined behavior. Commands may be silently ignored, the blind may stop at an incorrect position, or tilt adjustments may fail to apply.

This creates a critical race condition in Home Assistant, where users commonly issue separate level and tilt commands in rapid succession or change tilt while the blind is still moving to a target level.

### Scenario

```
T=0s:   User sends set_position(level=50%)
        Device starts moving (takes ~5 seconds)

T=2s:   User sends set_tilt(tilt=30°) while blind is still moving
        Without protection: Command may be ignored or corrupt the level movement
```

### Expected Behavior

The blind must reach **both** targets:

- **Level**: 50% (from the first command)
- **Tilt**: 30% (from the second command)

Movement should not produce incorrect final positions, even when commands overlap.

### Device Variants

The problem applies specifically to blind actors (devices with both level and tilt control). Simple covers (level only), window drives, and garage doors are not affected because they have only a single axis of movement.

| Class                 | Level | Tilt | Lock Required   |
| --------------------- | ----- | ---- | --------------- |
| `CustomDpCover`       | Yes   | No   | No              |
| `CustomDpWindowDrive` | Yes   | No   | No              |
| `CustomDpBlind`       | Yes   | Yes  | Yes             |
| `CustomDpIpBlind`     | Yes   | Yes  | Yes (inherited) |
| `CustomDpGarage`      | Yes   | No   | No              |

---

## Decision

Implement a per-instance `asyncio.Lock` (`_command_processing_lock`) in `CustomDpBlind` that serializes command processing and preserves pending targets when new commands arrive during movement. The mechanism uses a stop-then-resend strategy to work around the device firmware bug.

### Core Mechanism

The `_set_level()` method in `CustomDpBlind` implements a three-phase protocol:

**Phase 1 -- Lock Acquisition**

Acquire the per-instance lock with a 5-second timeout (`_COMMAND_LOCK_TIMEOUT`). If the timeout expires, proceed without the lock and log a warning. This prevents deadlocks while accepting a small risk of race conditions in edge cases.

**Phase 2 -- Target Resolution**

For each axis (level and tilt), determine the target value using a three-tier fallback:

1. **Explicit value**: If the caller provides a value, use it
2. **Pending target**: If a previous command is still unconfirmed (`_target_level` / `_target_tilt_level`), reuse that target and mark `currently_moving = True`
3. **Current position**: If the device is at standstill, use the confirmed position (`_group_level` / `_group_tilt_level`)

**Phase 3 -- Stop and Resend**

If `currently_moving` is detected, stop the device first via `_stop()`, then send a combined command with both the preserved level and the new tilt (or vice versa). This works around the firmware bug by ensuring the device is stationary before receiving new coordinates.

```
_set_level(level=None, tilt_level=0.3)
    |
    ├─ level=None → check _target_level
    │   └─ _target_level=0.5 (pending!) → _level=0.5, currently_moving=True
    │
    ├─ tilt_level=0.3 (explicit) → _tilt_level=0.3
    │
    ├─ currently_moving=True → _stop()
    │
    └─ _send_level(level=0.5, tilt_level=0.3)  ← combined command
```

### Target Detection

The `_target_level` and `_target_tilt_level` properties detect pending (unconfirmed) commands using a two-tier approach:

1. **Optimistic value** (preferred): Check if the data point has an optimistic value set (from the optimistic updates system in ADR 0020)
2. **CommandTracker fallback**: Query `unconfirmed_last_value_send` from the command tracker when optimistic updates are disabled

A target is cleared when the CCU confirms the value via an event, at which point the optimistic value is resolved and the command tracker entry expires.

### Command Transmission

Homematic blind devices support two transmission modes, selected automatically:

- **Combined parameter** (`LEVEL_COMBINED`): A single RPC call encoding both level and tilt as a hex-encoded combined value (e.g., `0xa2,0x26`). Used by BidCos-RF devices that expose a `COMBINED_PARAMETER` data point.
- **Separate parameters**: Two sequential RPC calls for `LEVEL_SLATS` (tilt) followed by `LEVEL`. Used when no combined parameter is available.

The combined parameter path bypasses the collector to ensure atomic delivery.

### Lock Scope

The lock protects three operations:

| Operation      | Method         | Lock Held             |
| -------------- | -------------- | --------------------- |
| Set level/tilt | `_set_level()` | Yes                   |
| Stop           | `stop()`       | Yes                   |
| Internal stop  | `_stop()`      | Caller must hold lock |

All public entry points (`set_position`, `open`, `close`, `open_tilt`, `close_tilt`, `stop`) route through either `_set_level()` or `stop()`, both of which acquire the lock.

---

## Use Cases

### Use Case 1: Tilt Change During Level Movement

```
T=0.0s:  set_position(position=50)
         → Lock acquired, _send_level(level=0.5, tilt=current)
         → _target_level = 0.5 (unconfirmed)
         → Device starts moving
         → Lock released

T=2.0s:  set_position(tilt_position=30)  [device still moving]
         → Lock acquired
         → level=None → _target_level=0.5 exists → reuse, currently_moving=True
         → tilt_level=0.3 (explicit)
         → _stop() called (firmware bug workaround)
         → _send_level(level=0.5, tilt_level=0.3) ← both targets
         → Lock released

T=7.0s:  Device reaches level=50%, tilt=30%
         → CCU confirms via events
```

Result: Both targets reached correctly.

### Use Case 2: Parallel Level and Tilt Calls

```
T=0.0s:  asyncio.gather(
             set_position(position=81),
             set_position(tilt_position=19),
         )

         → Call 1 acquires lock first
         → _send_level(level=0.81, tilt=current)
         → _target_level = 0.81 (unconfirmed)
         → Lock released

         → Call 2 acquires lock
         → level=None → _target_level=0.81 → reuse, currently_moving=True
         → tilt_level=0.19 (explicit)
         → _stop()
         → _send_level(level=0.81, tilt_level=0.19) ← combined
         → Lock released
```

Result: Combined command sent with both targets. Tested with 10 iterations to detect race conditions.

### Use Case 3: Lock Timeout

```
T=0.0s:  set_position(position=50)
         → Lock acquired, network delay causes slow RPC

T=0.1s:  set_position(tilt_position=30)
         → Waiting for lock...

T=5.1s:  Timeout after 5s
         → Warning logged
         → Proceeds WITHOUT lock
         → Commands may race, but CCU-side queuing mitigates
```

Result: Degraded but functional. The CCU queues commands server-side, limiting the impact.

---

## Implementation

**File**: `aiohomematic/model/custom/cover.py`

**Key Components:**

| Component                  | Location                             | Purpose                                        |
| -------------------------- | ------------------------------------ | ---------------------------------------------- |
| `_command_processing_lock` | `CustomDpCover.__slots__` (line 106) | Per-instance asyncio.Lock                      |
| `_COMMAND_LOCK_TIMEOUT`    | Module constant (line 31)            | 5.0 second timeout                             |
| `_set_level()`             | `CustomDpBlind` (line 468)           | Lock-protected target resolution and send      |
| `_stop()`                  | `CustomDpBlind` (line 520)           | Internal stop, must be called with lock held   |
| `stop()`                   | `CustomDpBlind` (line 412)           | Public stop with lock acquisition              |
| `_target_level`            | `CustomDpBlind` (line 292)           | Pending level detection (optimistic + tracker) |
| `_target_tilt_level`       | `CustomDpBlind` (line 311)           | Pending tilt detection (optimistic + tracker)  |
| `_send_level()`            | `CustomDpBlind` (line 449)           | Combined or separate parameter transmission    |
| `_group_level`             | `CustomDpCover` (line 122)           | Confirmed level fallback                       |
| `_group_tilt_level`        | `CustomDpBlind` (line 281)           | Confirmed tilt fallback                        |

**Inheritance:**

```
CustomDataPoint
  └─ CustomDpCover          (level only, lock slot declared, no lock logic)
      ├─ CustomDpWindowDrive (level only, no lock logic)
      └─ CustomDpBlind       (level + tilt, lock initialized and used)
          └─ CustomDpIpBlind (inherits lock, adds COMBINED_PARAMETER and L=N,L2=N format)
```

The lock slot is declared in `CustomDpCover` but only initialized and used in `CustomDpBlind._post_init()`. This allows the blind subclass to own the lock lifecycle while keeping the slot in the common base class.

**Test Coverage:**

| Test                                          | File                      | What It Verifies                           |
| --------------------------------------------- | ------------------------- | ------------------------------------------ |
| `test_ceblind_separate_level_and_tilt_change` | `test_model_cover.py:445` | Parallel set_position calls, 10 iterations |

---

## Consequences

### Positive

- Blind devices reliably reach both level and tilt targets regardless of command timing
- The firmware bug is completely transparent to consumers (Home Assistant)
- The lock timeout prevents deadlocks in degraded network conditions
- Target preservation eliminates the need for callers to track and re-send previous targets

### Negative

- The 5-second lock timeout introduces a maximum latency for queued commands
- On lock timeout, a brief race condition window exists (mitigated by CCU-side command queuing)
- The stop-then-resend approach adds one extra RPC call when commands overlap during movement

### Interaction with Command Throttling (ADR 0020)

The command processing lock operates **above** the throttle layer. Sequence when both are active:

```
set_position()
  → _set_level() acquires _command_processing_lock
    → _stop() sends STOP via client (throttle may delay)
    → _send_level() sends LEVEL_COMBINED via client (throttle may delay)
  → _command_processing_lock released
```

Cover commands use `HIGH` priority by default. The lock timeout (5s) must be larger than the expected throttle delay to avoid spurious timeouts.

### Interaction with Optimistic Updates (ADR 0020)

The `_target_level` and `_target_tilt_level` properties integrate with both the optimistic update system and the legacy command tracker:

1. When optimistic updates are enabled: `is_optimistic` is checked first, providing immediate target awareness
2. When disabled: `unconfirmed_last_value_send` from CommandTracker serves the same purpose

This hybrid approach ensures the lock mechanism works correctly regardless of the optimistic updates feature flag.

---

## Alternatives Considered

### No Lock, Rely on CCU Command Queuing

Let the CCU handle concurrent commands natively without client-side serialization.

**Rejected:** The CCU does queue commands, but the firmware bug in blind actors causes incorrect behavior when commands arrive during physical movement. Client-side stop-then-resend is necessary.

### Lock Without Target Preservation

Serialize commands but always use the current confirmed position as fallback for unspecified axes.

**Rejected:** This loses the pending target. If a user sends `level=50%` and then `tilt=30%` during movement, the second command would use the current (mid-movement) level rather than the intended target of 50%.

### Per-Axis Locks

Use separate locks for level and tilt to allow independent concurrent changes.

**Rejected:** The device firmware bug affects the device as a whole, not individual axes. Both axes must be stopped and resent together. A single lock correctly models this constraint.

### Longer or No Timeout

Increase the lock timeout or remove it entirely.

**Rejected:** A 5-second timeout balances deadlock prevention against command latency. With network issues, an indefinite lock could block all cover commands permanently. The current timeout allows degraded operation with a logged warning.

---

## References

- `aiohomematic/model/custom/cover.py` -- Cover and blind implementation
- ADR 0020: Command Throttling with Priority Queue and Optimistic Updates
- `tests/test_model_cover.py:445` -- Race condition test (`test_ceblind_separate_level_and_tilt_change`)

---

_Created: 2026-02-04_
_Author: Architecture Review_
