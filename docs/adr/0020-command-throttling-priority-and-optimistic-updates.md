# ADR 0020: Command Throttling with Priority Queue, Queue Purge, and Optimistic Updates

## Status

Accepted (2026-02-04)

---

## Context

### Problem

Version 2026.2.4 introduced basic command throttling (`CommandThrottle`) to to ensure smooth operation and prevent packet loss during bulk operations by delaying consecutive commands to the same interface. The initial implementation used a simple FIFO queue with `asyncio.Lock`, which exposed four problems:

1. **Missing Prioritization**: All commands were treated equally. When opening 15 covers with `command_throttle_interval=1.0`, a subsequent security-critical command (e.g., door lock/unlock) was delayed by up to 15 seconds behind the cover commands.

2. **No Queue Purge**: Even after CRITICAL commands bypassed the queue, their queued predecessors remained. Example: A user opens a cover (queued), then presses STOP -- the STOP bypassed the queue, but the queued OPEN command was still processed afterward, restarting the cover movement.

3. **Missing UI Feedback**: During throttle delays, Home Assistant received no status updates. The UI showed stale states (e.g., covers displayed "closed" even though "open" had been sent), causing users to send duplicate commands.

4. **Inconsistency with Polling Interfaces**: CUxD (polling) already had an "opportunistic write" mechanism in the command tracker. Push-based interfaces (HmIP-RF, BidCos-RF) lacked any equivalent.

### Existing Mechanisms

- **CommandTracker** (`aiohomematic/store/dynamic/command.py`): Stored sent commands with timestamps, enabling query via `unconfirmed_last_value_send`. Already used in `CustomDataPointCover` for UI feedback, but required manual fallback logic in each custom data point.

- **CommandThrottle** (`aiohomematic/client/command_throttle.py`): Simple FIFO queue with `asyncio.Lock`. No prioritization, no optimization.

---

## Decision

Extend the command throttling system with four capabilities:

1. **Priority Queue** replacing the FIFO queue, with three priority levels
2. **Queue Purge** cancelling obsolete queued commands when a CRITICAL command arrives
3. **Optimistic State Updates** for immediate UI feedback
4. **Automatic Rollback** on timeout or error

### 1. Priority Queue

Replace the FIFO `CommandThrottle` with a priority-aware rate limiter using `heapq`.

**Priority Levels:**

| Priority   | Value | Behavior          | Use Case                            |
| ---------- | ----- | ----------------- | ----------------------------------- |
| `CRITICAL` | 0     | Bypasses throttle | Locks, sirens, alarms, child safety |
| `HIGH`     | 1     | Normal throttle   | Interactive user commands (default) |
| `LOW`      | 2     | Normal throttle   | Bulk operations, automations        |

**Rules:**

- `CRITICAL` commands bypass both the queue and the throttle interval entirely, and purge related pending commands (see Queue Purge below)
- `HIGH` commands are throttled but prioritized before `LOW`
- `LOW` commands are throttled and can be overtaken by `HIGH`/`CRITICAL`
- When `interval=0.0` (default), throttling is disabled for all priorities

**Priority Declaration** via `@bind_collector(priority=...)`:

Service methods on custom data points declare their command priority via the `@bind_collector` decorator. The priority is set as a floor on the `CallParameterCollector` at creation time. Individual data points added to the collector can still elevate the priority higher (lower numeric value), but never below the floor.

```python
@bind_collector(priority=CommandPriority.CRITICAL)
async def lock(self, *, collector: CallParameterCollector | None = None) -> None:
    """Lock the lock."""
```

This is the single source of truth for CRITICAL priority. All safety-critical service methods declare `priority=CommandPriority.CRITICAL`:

- `BaseCustomDpLock`: `lock()`, `open()`, `unlock()`
- `BaseCustomDpSiren`: `turn_on()`, `turn_off()` (except `CustomDpSoundPlayer` -- not safety-critical)
- `BaseCustomDpCover`: `stop()` (emergency stop must cancel pending movement commands)

When `@bind_collector` sets CRITICAL priority, it also auto-detects the channel group addresses from `CustomDataPoint.get_channel_group_addresses()` and stores them as `purge_addresses` in the `RequestContext`. This enables the queue purge mechanism described below.

**Data-point-level detection** in `get_command_priority()` handles the remaining two levels:

- Bulk operations (detected via `RequestContext`) get `LOW` priority
- Everything else defaults to `HIGH`

### 2. Queue Purge

When a CRITICAL command arrives, it cancels all pending queued commands for the same **channel group**. This prevents obsolete commands from executing after the CRITICAL command completes.

**Motivating Example:**

A user opens a cover (`set_level(1.0)` → queued as HIGH), then immediately presses STOP. Without queue purge, the STOP command bypasses the queue and executes immediately, but the queued OPEN command is still processed afterward by the background worker, restarting the cover movement -- directly contradicting the user's intent.

**Channel Group Scope:**

Purging operates at the channel group level, not the device level. A device with multiple channel groups (e.g., a 2-channel blind actuator with channels 3+4 and channels 7+8) purges only commands for the affected group. STOP on group 1 (channels 3+4) does **not** cancel commands for group 2 (channels 7+8).

Channel group addresses are determined by `CustomDataPoint.get_channel_group_addresses()`, which collects all channel addresses from the `RebasedChannelGroupConfig` (primary channel, secondary channels, state channel, channel fields, fixed channel fields) and formats them as `"{device_address}:{channel_no}"`.

**Data Flow:**

```
1. @bind_collector(priority=CRITICAL) on stop()
   |
2. Decorator sets RequestContext with:
   - command_priority = CRITICAL
   - purge_addresses = frozenset({"VCU:3", "VCU:4"})  ← from channel group
   |
3. stop() body calls send_value()
   |
4. send_value() reads from RequestContext:
   - priority → CRITICAL
   - purge_addresses → frozenset({"VCU:3", "VCU:4"})
   |
5. client.set_value(priority=CRITICAL, purge_addresses=frozenset(...))
   |
6. CommandThrottle.acquire(priority=CRITICAL, purge_addresses=frozenset(...))
   |
7. Throttle: _purge_commands() cancels matching futures → bypass queue → return
```

**Purge Mechanics:**

- `_purge_commands()` iterates the priority queue and matches `cmd.device_address in purge_addresses`
- Matching commands have their futures rejected with `CommandSupersededError`
- The caller (`InterfaceClient.set_value`) catches `CommandSupersededError` and returns silently (empty result set) -- no error propagated to the user
- After purging, the queue is rebuilt via `heapq.heapify()`
- Commands already being processed by the background worker (popped from queue, waiting on throttle delay) cannot be purged -- they are "in flight"

**Design Constraint -- `CommandPriority.CRITICAL = 0` is falsy:**

Because `CRITICAL` has numeric value `0`, expressions like `priority or CommandPriority.HIGH` silently treat CRITICAL as falsy and downgrade to HIGH. All priority propagation code uses explicit `None` checks: `priority if priority is not None else CommandPriority.HIGH`.

### 3. Optimistic State Updates

Data points update their value locally **before** the command is sent to the CCU.

**Flow:**

```
1. send_value() called
   |
2. Store previous value for rollback
   |
3. Set _optimistic_value immediately
   |
4. Publish data_point_updated event  --> Home Assistant UI updates instantly
   |
5. Schedule rollback timer (default 30s)
   |
6. Detect command priority and purge addresses from RequestContext
   |  Note: CRITICAL + purge_addresses are set by @bind_collector(priority=...)
   |  on the collector. HIGH/LOW are detected by get_command_priority().
   |
7. Call client.set_value(priority=..., purge_addresses=...)
   |  --> CRITICAL: purge matching queue entries, bypass throttle
   |  --> HIGH/LOW: enqueue, may be throttled
   |
8a. CCU confirms (event received)    --> Clear optimistic state
8b. Timeout fires                    --> Rollback to previous value
8c. Send error                       --> Immediate rollback
```

**Value Resolution** in `_get_value()`:

1. Return `_optimistic_value` if set (pending confirmation)
2. Fall back to confirmed value from `DataCache`

**Properties exposed:**

- `is_optimistic: bool` -- True if current value is optimistic
- `optimistic_age: float | None` -- Age in seconds since optimistic value was set

### 4. Rollback Mechanism

Three rollback triggers:

| Trigger        | Timing       | Action                                         |
| -------------- | ------------ | ---------------------------------------------- |
| Send error     | Immediate    | Restore previous value, publish rollback event |
| Timeout        | 30s default  | Restore previous value, publish rollback event |
| Value mismatch | On CCU event | Log warning (CCU value takes precedence)       |

Rollback publishes an `OptimisticRollbackEvent` for Home Assistant notification and restores the previous confirmed value, triggering a `data_point_updated` event so the UI reverts.

### Key Design Choices

**Decorator-based CRITICAL priority, not parameter-set-based:** An earlier iteration used a `CRITICAL_PRIORITY_PARAMETERS` frozenset in `const.py` that detected CRITICAL priority at the data-point level based on parameter names. This was removed because all lock/siren commands flow through service methods decorated with `@bind_collector(priority=CommandPriority.CRITICAL)`, making the parameter set redundant. The decorator is the single source of truth -- explicit, local to the service method, and requires no maintenance when parameters change.

**Service-method-level, not device-type-based:** The original proposal included a `CRITICAL_PRIORITY_DEVICE_TYPES` frozenset for device-model-based priority. This was dropped because priority is a property of the operation (lock/unlock/alarm), not the device model.

**No bulk operation detection:** The original proposal included LOW priority for bulk operations (scenes, automations) detected via a `bulk_operation` flag in `RequestContext.extra`. This was removed because the HA integration never sets this flag, making it dead code. The command throttle's built-in burst detection already downgrades commands to LOW priority when burst thresholds are exceeded, providing automatic protection without requiring explicit context flags.

**Optimistic updates always active:** Optimistic updates are an integral part of the command throttling system, providing immediate UI feedback while commands are queued. There is no separate feature flag.

**Centralized in BaseParameterDataPoint:** Optimistic value tracking lives in `BaseParameterDataPoint`, not in custom data point subclasses. Custom data points automatically benefit because their properties read from the underlying generic data points, which return optimistic values transparently.

---

## Implementation

**Files Created:**

- `aiohomematic/client/command_throttle.py` -- `CommandThrottle`, `CommandPriority`, `PrioritizedCommand`
- `aiohomematic/exceptions.py` -- `CommandSupersededError` (raised when a queued command is purged)

**Files Modified:**

- `aiohomematic/model/data_point.py` -- `CallParameterCollector` accepts `priority` floor, `bind_collector` accepts `priority` parameter and auto-detects `purge_addresses` for CRITICAL commands, `get_command_priority()`, `_get_value()`, `_rollback_optimistic_value()`, `_schedule_optimistic_rollback()`, optimistic state slots, `CONTEXT_KEY_PRIORITY` and `CONTEXT_KEY_PURGE_ADDRESSES` constants
- `aiohomematic/model/generic/data_point.py` -- `send_value()` with optimistic update, priority detection, and purge address propagation phases
- `aiohomematic/model/custom/data_point.py` -- `get_channel_group_addresses()` on `CustomDataPoint` for channel group scope detection
- `aiohomematic/model/custom/lock.py` -- `@bind_collector(priority=CommandPriority.CRITICAL)` on all lock service methods
- `aiohomematic/model/custom/siren.py` -- `@bind_collector(priority=CommandPriority.CRITICAL)` on siren turn_on/turn_off (except `CustomDpSoundPlayer`)
- `aiohomematic/model/custom/cover.py` -- `@bind_collector(priority=CommandPriority.CRITICAL)` on `stop()`
- `aiohomematic/client/interface_client.py` -- `set_value()` and `put_paramset()` accept `priority` and `purge_addresses` parameters, catch `CommandSupersededError`
- `aiohomematic/interfaces/client.py` -- `ValueOperationsProtocol`, `ParamsetOperationsProtocol`, and `CommandThrottleProtocol` include `priority` and `purge_addresses` parameters

**Tests:**

- `tests/test_command_throttle.py` -- Unit tests for throttle behavior, queue purge, and end-to-end integration (cover STOP purging queued movement commands, channel group isolation)
- `tests/test_priority_detection.py` -- Priority detection unit tests
- `tests/test_priority_integration.py` -- End-to-end priority and throttle integration
- `tests/test_optimistic_updates.py` -- Optimistic update and rollback tests
- `tests/contract/test_command_priority_contract.py` -- Stability contracts for priority API
- `tests/contract/test_optimistic_updates_contract.py` -- Stability contracts for optimistic updates

---

## Consequences

### Positive

- Security-critical commands (locks, alarms) bypass throttle entirely (<100ms)
- CRITICAL commands cancel obsolete pending commands for the same channel group, preventing contradictory actions (e.g., cover STOP followed by queued OPEN)
- Per-channel-group purge scope ensures independent channel groups on multi-channel devices are not affected
- Immediate UI feedback via always-active optimistic updates
- Simplified custom data point implementations (no manual `unconfirmed_last_value_send` tracking needed)
- Single source of truth for value resolution in `BaseParameterDataPoint`
- Backward compatible: throttling disabled by default (`interval=0.0`)

### Negative

- Additional complexity in `BaseParameterDataPoint` (optimistic state tracking, rollback timer)
- Optimistic values may briefly diverge from CCU state
- Rollback events can cause UI flicker if CCU rejects commands frequently
- Commands already popped from the queue by the background worker ("in flight") cannot be purged

### Risks and Mitigations

| Risk                           | Mitigation                                                               |
| ------------------------------ | ------------------------------------------------------------------------ |
| Optimistic value never cleared | Automatic rollback timer (30s default)                                   |
| Priority starvation for LOW    | LOW commands still processed in FIFO order within their level            |
| CCU rejects optimistic value   | Rollback restores confirmed value, event notifies HA                     |
| In-flight command not purged   | At most one command in flight; throttle interval limits actual execution |
| Purge scope too broad          | Per-channel-group matching via `get_channel_group_addresses()`           |

---

## Alternatives Considered

### Parameter-Set-Based CRITICAL Detection

Maintain a `CRITICAL_PRIORITY_PARAMETERS` frozenset in `const.py` containing parameter names (e.g., `LOCK_TARGET_LEVEL`, `ACOUSTIC_ALARM_ACTIVE`) that should get CRITICAL priority. `get_command_priority()` on each data point would check membership in this set.

**Rejected:** Redundant with the decorator approach. All lock/siren commands flow through service methods, so the decorator is sufficient. The parameter set was defense-in-depth for direct `send_value()` calls, but in practice no consumer bypasses the service layer for these parameters. Removing it simplifies the codebase and eliminates a second source of truth.

### Device-Type-Based Priority Detection

Maintain a `CRITICAL_PRIORITY_DEVICE_TYPES` frozenset mapping device models to CRITICAL priority.

**Rejected:** High maintenance burden as new device models are released. Priority is a property of the operation (lock/unlock/alarm), not the device model.

### Optimistic Updates in Custom Data Points

Implement optimistic value tracking separately in each custom data point subclass (cover, lock, climate, etc.).

**Rejected:** Leads to duplicated logic across subclasses. Custom data points aggregate from generic data points, so placing optimistic tracking in `BaseParameterDataPoint` provides automatic propagation without duplication.

### Keep FIFO Queue with Priority Override

Allow callers to pass a "skip queue" flag for critical commands while keeping the FIFO structure.

**Rejected:** Does not solve priority ordering between HIGH and LOW. A proper priority queue with `heapq` handles all three levels cleanly with minimal additional complexity.

### Per-Device Queue Purge

Purge all pending commands for the entire device when a CRITICAL command arrives, rather than scoping to the channel group.

**Rejected:** A device with multiple independent channel groups (e.g., a 2-channel blind actuator) would have unrelated commands cancelled. STOP on channel group 1 would cancel commands for channel group 2, which is incorrect behavior. Per-channel-group purging is the correct granularity because it matches the physical actuator boundaries.

### No Queue Purge (Bypass Only)

Let CRITICAL commands bypass the queue but leave pending commands intact.

**Rejected:** This was the initial implementation and caused the cover STOP problem described in the Context section. Without purging, queued movement commands execute after STOP, contradicting the user's intent.

### Per-Channel Throttling

Throttle commands per channel instead of per interface.

**Rejected:** Too granular and provides little benefit. Per-interface throttling matches RF channel boundaries, which is the actual physical constraint being managed.

---

## References

- `aiohomematic/client/command_throttle.py` -- CommandThrottle, CommandPriority, queue purge (`_purge_commands`)
- `aiohomematic/model/data_point.py` -- `bind_collector(priority=...)`, `CallParameterCollector`, optimistic state management, `CONTEXT_KEY_PRIORITY`, `CONTEXT_KEY_PURGE_ADDRESSES`
- `aiohomematic/model/generic/data_point.py` -- `send_value()` with optimistic update and purge address propagation phases
- `aiohomematic/model/custom/data_point.py` -- `get_channel_group_addresses()` for channel group scope
- `aiohomematic/model/custom/lock.py` -- Lock service methods with `priority=CommandPriority.CRITICAL`
- `aiohomematic/model/custom/siren.py` -- Siren service methods with `priority=CommandPriority.CRITICAL`
- `aiohomematic/model/custom/cover.py` -- Cover `stop()` with `priority=CommandPriority.CRITICAL`
- `aiohomematic/exceptions.py` -- `CommandSupersededError`
- `aiohomematic/store/dynamic/command.py` -- CommandTracker (predecessor mechanism)
- ADR 0001: Circuit Breaker and Connection State (related error handling)

---

_Created: 2026-02-04_
_Updated: 2026-02-05 -- Added queue purge capability_
_Author: Architecture Review_
