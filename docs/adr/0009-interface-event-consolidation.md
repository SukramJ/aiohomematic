# ADR-0009: Interface Event Consolidation

## Status

**Completed** (2025-12-26)

- [x] `CallbackStateChangedEvent` added
- [x] Legacy `CALLBACK` event removed from enum and code
- [x] Legacy `PROXY` event removed from enum and code
- [x] `FetchDataFailedEvent` added (replaces `FETCH_DATA`)
- [x] `PingPongMismatchEvent` added (replaces `PENDING_PONG` and `UNKNOWN_PONG`)
- [x] `DeviceAvailabilityChangedEvent` added (new)
- [x] Legacy `InterfaceEvent` dataclass removed
- [x] Legacy `InterfaceEventType` enum removed
- [x] Legacy `publish_interface_event()` method removed
- [ ] Home Assistant integration migrated (external dependency)

---

## Context

aiohomematic had two parallel event systems for connection/interface status:

1. **Legacy System**: `InterfaceEventType` published via `HomematicEvent` with `EventType.INTERFACE`
2. **Modern System**: State-based events (`CentralStateChangedEvent`, `ClientStateChangedEvent`, `ConnectionStateChangedEvent`)

This created redundancy and potential confusion for consumers.

### Legacy InterfaceEventType Events

Published via `publish_interface_event()` → `HomematicEvent(EventType.INTERFACE)`:

| Type           | Trigger                                  | Data                                               | Purpose                      |
| -------------- | ---------------------------------------- | -------------------------------------------------- | ---------------------------- |
| `PROXY`        | `mark_all_devices_forced_availability()` | `{AVAILABLE: bool}`                                | Device availability changed  |
| `CALLBACK`     | Callback alive/dead detection            | `{AVAILABLE: bool, SECONDS_SINCE_LAST_EVENT: int}` | CCU callback channel status  |
| `FETCH_DATA`   | Device data fetch failure                | `{AVAILABLE: false}`                               | Data refresh failed          |
| `PENDING_PONG` | PING without PONG                        | `{MISMATCH_COUNT: int}`                            | PING/PONG mismatch indicator |
| `UNKNOWN_PONG` | PONG without matching PING               | `{MISMATCH_COUNT: int}`                            | Unexpected PONG received     |

### Modern State Events

Published directly via `EventBus.publish()`:

| Event                         | Trigger                          | Data                                            | Purpose                        |
| ----------------------------- | -------------------------------- | ----------------------------------------------- | ------------------------------ |
| `CentralStateChangedEvent`    | Central state machine transition | `old_state, new_state, reason`                  | Overall system state           |
| `ClientStateChangedEvent`     | Client state machine transition  | `interface_id, old_state, new_state`            | Per-interface connection state |
| `ConnectionStateChangedEvent` | Connection issue added/removed   | `interface_id, connected`                       | Interface connectivity         |
| `CallbackStateChangedEvent`   | Callback alive/dead detection    | `interface_id, alive, seconds_since_last_event` | CCU callback channel status    |

---

## Analysis

### Overlap Matrix

| Legacy Event   | Related Modern Event        | Overlap      | Notes                                |
| -------------- | --------------------------- | ------------ | ------------------------------------ |
| `PROXY`        | `ClientStateChangedEvent`   | **High**     | Both indicate interface availability |
| `CALLBACK`     | `CallbackStateChangedEvent` | **Complete** | ✅ Direct replacement implemented    |
| `FETCH_DATA`   | `ClientStateChangedEvent`   | **Low**      | Fetch failure is more specific       |
| `PENDING_PONG` | None                        | **None**     | Unique diagnostic information        |
| `UNKNOWN_PONG` | None                        | **None**     | Unique diagnostic information        |

### Detailed Comparison

#### PROXY vs ClientStateChangedEvent

**PROXY:**

- Published when device availability changes
- Data: `{AVAILABLE: bool}`

**ClientStateChangedEvent:**

- Published on state transitions
- Data: `interface_id, old_state, new_state`

**Mapping:**
| ClientState | PROXY equivalent |
| -------------- | ----------------------- |
| `CONNECTED` | `{AVAILABLE: true}` |
| `DISCONNECTED` | `{AVAILABLE: false}` |
| `FAILED` | `{AVAILABLE: false}` |

**Conclusion:** PROXY can be derived from ClientStateChangedEvent.

#### CALLBACK vs CallbackStateChangedEvent

**Difference:** CALLBACK provides `SECONDS_SINCE_LAST_EVENT` which ConnectionStateChangedEvent does not.

**Solution:** Created `CallbackStateChangedEvent` to preserve this diagnostic data.

#### PENDING_PONG / UNKNOWN_PONG

These have no modern equivalent. They provide unique diagnostic information about PING/PONG health.

**Solution:** Created `PingPongMismatchEvent` to replace both.

---

## Decision

**Consolidate all interface events into typed event classes**, removing the legacy `InterfaceEvent` system entirely.

### Phase 1: Document and Deprecate (Non-Breaking) ✅ COMPLETE

Marked legacy events as deprecated in documentation and added new typed events.

### Phase 2: Migration Path ✅ COMPLETE

Provided migration guidance for each legacy event.

### Phase 3: Consolidation (Breaking Change) ✅ COMPLETE

Removed entire legacy `InterfaceEvent` system (dataclass, enum, publish method).

---

## Migration Guide

### PROXY Migration

**Before:**

```python
# Legacy: Listen to PROXY event
if event_data[EventKey.TYPE] == InterfaceEventType.PROXY:
    available = event_data[EventKey.DATA][EventKey.AVAILABLE]
```

**After:**

```python
# Modern: Use ClientStateChangedEvent
def on_client_state_changed(*, event: ClientStateChangedEvent):
    available = event.new_state == ClientState.CONNECTED

event_bus.subscribe(
    event_type=ClientStateChangedEvent,
    event_key=interface_id,
    handler=on_client_state_changed,
)
```

### CALLBACK Migration

**Before:**

```python
# Legacy: CALLBACK event with seconds info
if event_data[EventKey.TYPE] == InterfaceEventType.CALLBACK:
    available = event_data[EventKey.DATA][EventKey.AVAILABLE]
    seconds = event_data[EventKey.DATA].get(EventKey.SECONDS_SINCE_LAST_EVENT)
```

**After:**

```python
# Modern: CallbackStateChangedEvent preserves all data
def on_callback_changed(*, event: CallbackStateChangedEvent):
    alive = event.alive
    seconds = event.seconds_since_last_event

event_bus.subscribe(
    event_type=CallbackStateChangedEvent,
    event_key=interface_id,
    handler=on_callback_changed,
)
```

### FETCH_DATA Migration

**After:**

```python
# Modern: FetchDataFailedEvent
def on_fetch_failed(*, event: FetchDataFailedEvent):
    _LOGGER.warning("Data fetch failed for %s", event.interface_id)

event_bus.subscribe(
    event_type=FetchDataFailedEvent,
    handler=on_fetch_failed,
)
```

### PENDING_PONG / UNKNOWN_PONG Migration

**After:**

```python
# Modern: PingPongMismatchEvent
def on_ping_pong_mismatch(*, event: PingPongMismatchEvent):
    if event.mismatch_type == "pending_pong":
        _LOGGER.warning("PING without PONG for %s", event.interface_id)
    else:
        _LOGGER.warning("Unexpected PONG for %s", event.interface_id)

event_bus.subscribe(
    event_type=PingPongMismatchEvent,
    handler=on_ping_pong_mismatch,
)
```

---

## Summary Table

| Legacy Event   | Action      | Replacement                 | Status  |
| -------------- | ----------- | --------------------------- | ------- |
| `PROXY`        | **Removed** | `ClientStateChangedEvent`   | ✅ Done |
| `CALLBACK`     | **Removed** | `CallbackStateChangedEvent` | ✅ Done |
| `FETCH_DATA`   | **Removed** | `FetchDataFailedEvent`      | ✅ Done |
| `PENDING_PONG` | **Removed** | `PingPongMismatchEvent`     | ✅ Done |
| `UNKNOWN_PONG` | **Removed** | `PingPongMismatchEvent`     | ✅ Done |

**Note:** The entire legacy `InterfaceEvent` system (dataclass, enum, publish method) has been removed.

---

## Consequences

### Positive

✅ **Cleaner API**: Type-safe events with proper dataclasses
✅ **Better IDE Support**: Autocomplete and type checking
✅ **Reduced Duplication**: Single event system
✅ **More Discoverable**: Events are explicit classes, not enum values
✅ **Consistent Patterns**: All events follow same subscribe API

### Negative

⚠️ **Breaking Change**: Existing consumers must update
⚠️ **Migration Effort**: Home Assistant integration needs updates
⚠️ **Temporary Documentation**: Both systems documented during transition

### Neutral

ℹ️ **Home Assistant Dependency**: Integration must be updated separately
ℹ️ **Backward Compatibility**: Not maintained for internal event system

---

## Implementation

**Status:** ✅ Completed in version 2025.12.26

### New Event Classes

**`aiohomematic/central/events/bus.py`:**

- `CallbackStateChangedEvent` - Callback alive/dead with seconds info
- `FetchDataFailedEvent` - Data fetch failures
- `PingPongMismatchEvent` - PING/PONG diagnostic events
- `DeviceAvailabilityChangedEvent` - Device availability changes

### Removed

**Legacy components completely removed:**

- `InterfaceEvent` dataclass
- `InterfaceEventType` enum
- `publish_interface_event()` method

### Updated

**Event publishers** updated to use new typed events:

- Callback monitoring → `CallbackStateChangedEvent`
- Device availability → `DeviceAvailabilityChangedEvent`
- Data fetch failures → `FetchDataFailedEvent`
- PING/PONG monitoring → `PingPongMismatchEvent`

---

## References

- [Event Reference](../architecture/events/event_reference.md) - Complete event catalog
- [EventBus Architecture](../architecture/events/event_bus.md) - Event system overview
- [ADR-0006: Event System Priorities](0006-event-system-priorities-and-batching.md) - Event batching strategy

---

_Created: 2025-12-26_
_Author: Architecture Review_
