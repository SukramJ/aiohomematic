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
- [x] Migration guide created
- [ ] Home Assistant integration migrated (external dependency)

## Context

aiohomematic currently has two parallel event systems for connection/interface status:

1. **Legacy System**: `InterfaceEventType` published via `HomematicEvent` with `EventType.INTERFACE`
2. **Modern System**: State-based events (`CentralStateChangedEvent`, `ClientStateChangedEvent`, `ConnectionStateChangedEvent`)

This creates redundancy and potential confusion for consumers.

## Current State

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

```python
# Published when device availability changes
self.central.publish_interface_event(
    interface_id=self.interface_id,
    interface_event_type=InterfaceEventType.PROXY,
    data={EventKey.AVAILABLE: available},
)
```

**ClientStateChangedEvent:**

```python
# Published on state transitions
event_bus.publish_sync(
    event=ClientStateChangedEvent(
        interface_id=self.interface_id,
        old_state=old_state,
        new_state=new_state,
    )
)
```

**Mapping:**
| ClientState | PROXY equivalent |
|-------------|------------------|
| `CONNECTED` | `{AVAILABLE: true}` |
| `DISCONNECTED` | `{AVAILABLE: false}` |
| `FAILED` | `{AVAILABLE: false}` |

**Conclusion:** PROXY can be derived from ClientStateChangedEvent.

#### CALLBACK vs ConnectionStateChangedEvent

**CALLBACK:**

```python
# Published based on seconds_since_last_event threshold
publish_interface_event(
    interface_event_type=InterfaceEventType.CALLBACK,
    data={
        EventKey.AVAILABLE: False,
        EventKey.SECONDS_SINCE_LAST_EVENT: 120,
    },
)
```

**ConnectionStateChangedEvent:**

```python
# Published when connection issues change
event=ConnectionStateChangedEvent(
    interface_id=interface_id,
    connected=connected,
)
```

**Difference:** CALLBACK provides `SECONDS_SINCE_LAST_EVENT` which ConnectionStateChangedEvent does not.

**Conclusion:** Partial overlap. CALLBACK has additional diagnostic data.

#### PENDING_PONG / UNKNOWN_PONG

These have no modern equivalent. They provide unique diagnostic information about PING/PONG health.

**Conclusion:** No consolidation possible. These should remain.

## Decision

### Phase 1: Document and Deprecate (Non-Breaking)

1. Mark legacy events as deprecated in documentation
2. Add deprecation warnings to `publish_interface_event()` for PROXY
3. Update Home Assistant integration to use modern events

### Phase 2: Migration Path

For each legacy event, provide migration guidance:

#### PROXY Migration

**Before:**

```python
def on_interface_event(event_type, event_data):
    if event_data[EventKey.TYPE] == InterfaceEventType.PROXY:
        available = event_data[EventKey.DATA][EventKey.AVAILABLE]
        update_availability(available)
```

**After:**

```python
def on_client_state_changed(*, event: ClientStateChangedEvent):
    available = event.new_state == ClientState.CONNECTED
    update_availability(available)

event_bus.subscribe(
    event_type=ClientStateChangedEvent,
    event_key=interface_id,  # Filter by interface
    handler=on_client_state_changed,
)
```

#### CALLBACK Migration

**Before:**

```python
def on_interface_event(event_type, event_data):
    if event_data[EventKey.TYPE] == InterfaceEventType.CALLBACK:
        available = event_data[EventKey.DATA][EventKey.AVAILABLE]
        seconds = event_data[EventKey.DATA].get(EventKey.SECONDS_SINCE_LAST_EVENT)
```

**After (Option A - Use ConnectionStateChangedEvent):**

```python
def on_connection_changed(*, event: ConnectionStateChangedEvent):
    # Note: loses SECONDS_SINCE_LAST_EVENT information
    update_callback_status(event.connected)
```

**After (Option B - Create new CallbackStateChangedEvent):**

```python
@dataclass(frozen=True, slots=True)
class CallbackStateChangedEvent(Event):
    interface_id: str
    alive: bool
    seconds_since_last_event: int | None
```

### Phase 3: Consolidation (Breaking Change)

After migration period:

1. Remove PROXY from InterfaceEventType
2. Keep CALLBACK (or replace with CallbackStateChangedEvent)
3. Keep FETCH_DATA (unique purpose)
4. Keep PENDING_PONG / UNKNOWN_PONG (diagnostic)

## Recommended Actions

### aiohomematic Library ✅ COMPLETED

1. ~~**Add `CallbackStateChangedEvent`** to preserve `seconds_since_last_event` information~~ ✅ Done
2. ~~**Update event_reference.md** with migration guidance~~ ✅ Done
3. ~~**Add `FetchDataFailedEvent`** to replace `FETCH_DATA`~~ ✅ Done
4. ~~**Add `PingPongMismatchEvent`** to replace `PENDING_PONG` and `UNKNOWN_PONG`~~ ✅ Done
5. ~~**Add `DeviceAvailabilityChangedEvent`** for device availability changes~~ ✅ Done
6. ~~**Remove legacy `InterfaceEvent` dataclass**~~ ✅ Done
7. ~~**Remove legacy `InterfaceEventType` enum**~~ ✅ Done
8. ~~**Remove legacy `publish_interface_event()` method**~~ ✅ Done

### Home Assistant Integration (External)

## Summary Table

| Legacy Event   | Action      | Replacement                 | Status  |
| -------------- | ----------- | --------------------------- | ------- |
| `PROXY`        | **Removed** | `ClientStateChangedEvent`   | ✅ Done |
| `CALLBACK`     | **Removed** | `CallbackStateChangedEvent` | ✅ Done |
| `FETCH_DATA`   | **Removed** | `FetchDataFailedEvent`      | ✅ Done |
| `PENDING_PONG` | **Removed** | `PingPongMismatchEvent`     | ✅ Done |
| `UNKNOWN_PONG` | **Removed** | `PingPongMismatchEvent`     | ✅ Done |

**Note:** The entire legacy `InterfaceEvent` system (dataclass, enum, publish method) has been removed.

## Consequences

### Positive

- Cleaner, more consistent event API
- Type-safe events with proper dataclasses
- Better IDE support and documentation
- Reduced duplication

### Negative

- Breaking change for existing consumers
- Migration effort required
- Temporary complexity during transition

### Neutral

- Home Assistant integration must be updated
- Documentation must be maintained for both systems during transition

## References

- [Event Reference](../event_reference.md)
- [EventBus Architecture](../event_bus.md)
- [ADR-0006: Event System Priorities](0006-event-system-priorities-and-batching.md)
