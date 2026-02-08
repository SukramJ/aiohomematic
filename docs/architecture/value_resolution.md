# Value Resolution: Three-Tier Update Model

This document describes the three-tier value resolution mechanism used by `BaseParameterDataPoint` (channel-bound parameters) and `GenericSysvarDataPoint` (hub system variables). The mechanism provides immediate UI feedback, tolerates transport delays, and automatically recovers from unconfirmed writes.

Audience: Contributors who need to understand how data point values are stored, prioritised, and resolved.

---

## Overview

Every writable data point maintains up to three value tiers. When a consumer reads the value, the tiers are evaluated top-down; the first non-empty tier wins.

| Tier | Field                | Set by                      | Cleared by                        | Purpose                                           |
| ---- | -------------------- | --------------------------- | --------------------------------- | ------------------------------------------------- |
| 1    | `_optimistic_value`  | `apply_optimistic_value()`  | CCU event / timeout / send error  | Instant UI feedback **before** RPC call completes |
| 2    | `_unconfirmed_value` | `write_unconfirmed_value()` | Next `write_value()` or `event()` | Polling fallback **after** RPC call completes     |
| 3    | `_current_value`     | `write_value()` / `event()` | Never (overwritten)               | CCU-confirmed ground truth                        |

### Value resolution chain

```python
# BaseParameterDataPoint._get_value()
def _get_value(self) -> ParameterT | None:
    if self._optimistic_value is not None:
        return self._optimistic_value          # Tier 1
    return self._value                          # Tier 2 or 3

# BaseParameterDataPoint._value (property)
@property
def _value(self) -> ParameterT | None:
    if self._unconfirmed_refreshed_at > self._refreshed_at:
        return self._unconfirmed_value          # Tier 2
    return self._current_value                  # Tier 3
```

The `_value` property compares timestamps to decide whether the unconfirmed value is still more recent than the last confirmed value. Once a CCU event arrives, `write_value()` resets the unconfirmed timestamps and updates `_current_value`, so `_value` naturally falls through to Tier 3.

---

## Tier 1: Optimistic Value

**When:** Set immediately in `send_value()` **before** the RPC call is dispatched. This gives the UI instant feedback (< 1 ms).

**Where:** `BaseParameterDataPoint.apply_optimistic_value()`

**Lifecycle:**

```
send_value()
  ├── apply_optimistic_value(value)     ← Tier 1 active
  │     ├── Save _optimistic_previous_value (first send in burst only)
  │     ├── Set _optimistic_value = value
  │     ├── publish_data_point_updated_event()   → UI updates instantly
  │     └── Schedule rollback timer (default 30 s)
  │
  ├── client.set_value(...)             ← RPC call in flight
  │
  └── Three possible outcomes:
        │
        ├── event(value)                ← CCU confirms
        │     ├── Cancel rollback timer
        │     ├── Clear _optimistic_value, _optimistic_previous_value
        │     └── write_value() updates _current_value   → Tier 3 active
        │
        ├── Timeout (30 s)              ← No CCU event
        │     ├── _rollback_optimistic_value()
        │     ├── Clear _optimistic_value
        │     ├── Clear _unconfirmed_value  ← prevents Tier 2 override
        │     ├── Restore _current_value from _optimistic_previous_value
        │     └── Publish OptimisticRollbackEvent   → UI reverts
        │
        └── Send error                  ← RPC call fails
              └── Same as Timeout (immediate rollback)
```

**Burst handling:** Rapid successive sends (e.g., dimmer slider drag) increment `_optimistic_pending_sends`. Only the first send captures `_optimistic_previous_value`. Each CCU confirmation event decrements the counter; only the final confirmation clears optimistic state.

---

## Tier 2: Unconfirmed Value

**When:** Written by `InterfaceClient` **after** the RPC call succeeds, but **only** for data points where `requires_polling` is True (BidCos MASTER paramsets, CUxD/CCU-Jack interfaces).

**Where:** `InterfaceClient._write_unconfirmed_value()` → `BaseParameterDataPoint.write_unconfirmed_value()`

**Why it exists:** Polling data points never receive push events from the CCU. Without Tier 2, the value would remain stale until the next polling cycle (potentially minutes). The unconfirmed value bridges this gap.

**Lifecycle:**

```
InterfaceClient.set_value() / put_paramset()
  ├── backend.set_value(...)            ← RPC call succeeds
  │
  ├── _write_unconfirmed_value(dpk_values)
  │     └── For each data_point where requires_polling:
  │           ├── _reset_unconfirmed_value()   ← Clear previous
  │           ├── Set _unconfirmed_value = value
  │           ├── Set _unconfirmed_modified_at = now
  │           ├── _state_uncertain = True
  │           └── publish_data_point_updated_event()  → UI updates
  │
  └── Cleared when:
        ├── write_value()    ← polling cycle fetches confirmed value
        ├── event()          ← push event (unexpected but possible)
        └── _rollback_optimistic_value()  ← Tier 1 timeout/error
```

**Timestamp-based resolution:** The `_value` property returns `_unconfirmed_value` only when `_unconfirmed_refreshed_at > _refreshed_at`. As soon as `write_value()` calls `_set_refreshed_at()` or `_set_modified_at()`, the confirmed timestamps advance past the unconfirmed timestamps, and `_value` falls through to `_current_value`.

---

## Tier 3: Current Value (CCU-confirmed)

**When:** Set by `write_value()` when a CCU event arrives or a polling read returns data.

**Where:** `BaseParameterDataPoint.write_value()`

**Behaviour:** Always resets unconfirmed state first (`_reset_unconfirmed_value()`), then compares old vs. new value to decide between `_set_refreshed_at` (same value) or `_set_modified_at` (changed value). Sets `_state_uncertain = False`.

This is the only tier that updates `_previous_value` (via `_last_non_default_value`).

---

## Interaction Between Tiers

### Push data points (most interfaces)

For data points with `requires_polling = False`:

```
send_value()
  → Tier 1 active (optimistic, instant)
  → RPC call completes
  → Tier 2 skipped (requires_polling is False)
  → CCU event arrives → write_value()
  → Tier 1 cleared, Tier 3 updated
```

Only Tier 1 and Tier 3 participate. The UI sees the optimistic value immediately, then the confirmed value when the CCU responds (typically < 1 s).

### Polling data points (BidCos MASTER, CUxD/CCU-Jack)

For data points with `requires_polling = True`:

```
send_value()
  → Tier 1 active (optimistic, instant)
  → RPC call completes
  → Tier 2 active (unconfirmed, post-RPC)
  → Value held in both Tier 1 and Tier 2 simultaneously
  → Tier 1 timeout (30 s) → rollback clears both Tier 1 and Tier 2
  OR
  → Polling cycle → write_value() clears Tier 2, Tier 1 timeout fires harmlessly
```

Both Tier 1 and Tier 2 hold the sent value. This is intentional: Tier 1 provides instant feedback before the RPC call, Tier 2 persists the value after the optimistic timeout expires (if polling confirms it).

### Rollback clears both tiers

When `_rollback_optimistic_value()` fires (timeout or send error), it clears **both** Tier 1 and Tier 2:

```python
# Clear optimistic state (Tier 1)
self._optimistic_value = None
# ...

# Clear unconfirmed value (Tier 2) — prevents override of restored value
self._reset_unconfirmed_value()

# Restore previous confirmed value (Tier 3)
self._current_value = self._optimistic_previous_value
```

Without clearing Tier 2, the unconfirmed value would survive the rollback and the `_value` property would still return the rolled-back value through the timestamp comparison — undermining the rollback entirely.

---

## Hub System Variables (GenericSysvarDataPoint)

Hub system variables use the same Tier 2 / Tier 3 pattern but without Tier 1 (no optimistic updates for sysvars):

| Tier | Field                | Set by                                           |
| ---- | -------------------- | ------------------------------------------------ |
| 2    | `_unconfirmed_value` | `send_variable()` → `_write_unconfirmed_value()` |
| 3    | `_current_value`     | `write_value()` (CCU-confirmed)                  |

The `_value` property uses the same timestamp comparison:

```python
@property
def _value(self) -> Any | None:
    return self._unconfirmed_value if self._unconfirmed_refreshed_at > self._refreshed_at else self._current_value
```

`send_variable()` calls `_write_unconfirmed_value()` after sending the value to the CCU. When the hub coordinator fetches fresh sysvar data, `write_value()` resets the unconfirmed state and updates `_current_value`.

---

## Summary Table

| Aspect              | Tier 1 (Optimistic)       | Tier 2 (Unconfirmed)                         | Tier 3 (Confirmed)                   |
| ------------------- | ------------------------- | -------------------------------------------- | ------------------------------------ |
| **Timing**          | Before RPC call           | After RPC call                               | On CCU event/poll                    |
| **Latency**         | < 1 ms                    | ~50-200 ms (RPC round-trip)                  | ~0.5-2 s (event) or polling interval |
| **Scope**           | All writable data points  | Polling data points + sysvars                | All data points                      |
| **State uncertain** | No (confident prediction) | Yes (`_state_uncertain = True`)              | No (`_state_uncertain = False`)      |
| **Auto-rollback**   | Yes (30 s timeout)        | No (cleared by next confirmed write)         | N/A                                  |
| **Implementation**  | `BaseParameterDataPoint`  | `BaseParameterDataPoint` + `InterfaceClient` | `BaseParameterDataPoint`             |

---

## Where to look in code

- Value resolution: `aiohomematic/model/data_point.py` — `_get_value()`, `_value` property
- Optimistic updates: `aiohomematic/model/data_point.py` — `apply_optimistic_value()`, `_rollback_optimistic_value()`, `_schedule_optimistic_rollback()`
- Unconfirmed writes: `aiohomematic/model/data_point.py` — `write_unconfirmed_value()`, `_reset_unconfirmed_value()`
- Confirmed writes: `aiohomematic/model/data_point.py` — `write_value()`
- Client-side unconfirmed trigger: `aiohomematic/client/interface_client.py` — `_write_unconfirmed_value()`
- Hub sysvars: `aiohomematic/model/hub/data_point.py` — `GenericSysvarDataPoint._write_unconfirmed_value()`
- Send flow: `aiohomematic/model/generic/data_point.py` — `send_value()`
- ADR: `docs/adr/0020-command-throttling-priority-and-optimistic-updates.md`
