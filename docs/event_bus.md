# EventBus Architecture

## Overview

The EventBus is a type-safe, async-first event handling system that replaces the scattered callback dictionaries previously used throughout the codebase. It provides a clean, decoupled way to handle events in aiohomematic.

## Motivation

### Problems with Previous Approach

The previous implementation had several issues:

1. **Multiple Callback Dictionaries**: Different event types used different storage patterns:

   - `_backend_system_handlers: set[BackendSystemCallback]`
   - `_backend_parameter_callbacks: set[BackendParameterCallback]`
   - `_homematic_callbacks: set[HomematicCallback]`
   - `_data_point_key_event_subscriptions: dict[DataPointKey, list[DataPointEventCallback]]`
   - `_sysvar_data_point_event_subscriptions: dict[str, SysvarEventCallback]`

2. **Complex Registration Logic**: Each event type required different registration code
3. **Tight Coupling**: CentralUnit was responsible for managing all callback storage
4. **Hard to Test**: Mocking callbacks required complex setup
5. **No Type Safety**: Callbacks were stored as generic sets/lists
6. **Error Propagation**: Exception in one callback could affect others

### EventBus Solution

The new EventBus provides:

1. **Unified API**: Single `subscribe()` and `publish()` interface
2. **Type Safety**: Events are strongly-typed dataclasses
3. **Decoupling**: CentralUnit delegates to EventBus
4. **Error Isolation**: Exceptions in one handler don't affect others
5. **Async-First**: Native async/await support with concurrent handler execution
6. **Easy Testing**: Simple mocking and verification

## Architecture

### Event Types

All events inherit from the base `Event` class:

```python
@dataclass(frozen=True, slots=True)
class Event:
    """Base class for all events."""
    timestamp: datetime
```

Key event types:

- **DataPointUpdatedEvent**: Data point value changed
- **BackendParameterEvent**: Raw parameter update from backend
- **BackendSystemEventData**: System events (devices created, deleted, etc.)
- **HomematicEvent**: Homematic-specific events (KEYPRESS, INTERFACE, etc.)
- **SysvarUpdatedEvent**: System variable changed
- **InterfaceEvent**: Interface-level events (connection state, etc.)

### EventBus Class

```python
class EventBus:
    """Type-safe, async event bus."""

    def subscribe(
        self,
        event_type: type[T_Event],
        handler: Callable[[T_Event], None] | Callable[[T_Event], Coroutine],
    ) -> UnsubscribeCallback:
        """Subscribe to events of a specific type."""

    async def publish(self, event: Event) -> None:
        """Publish an event to all subscribers."""
```

## Usage Examples

### Basic Subscription

```python
from aiohomematic.central.event_bus import EventBus, DataPointUpdatedEvent
from aiohomematic.const import DataPointKey, ParamsetKey

bus = EventBus()

# Sync handler
def on_update(event: DataPointUpdatedEvent) -> None:
    print(f"Value changed: {event.value}")

unsubscribe = bus.subscribe(event_type=DataPointUpdatedEvent, handler=on_update)

# Publish event
await bus.publish(event=DataPointUpdatedEvent(
    timestamp=datetime.now(),
    dpk=DataPointKey(
        interface_id="BidCos-RF",
        channel_address="VCU0000001:1",
        paramset_key=ParamsetKey.VALUES,
        parameter="STATE",
    ),
    value=True,
    received_at=datetime.now(),
))

# Later...
unsubscribe()
```

### Async Handler

```python
async def on_update_async(event: DataPointUpdatedEvent) -> None:
    await some_async_operation()
    print(f"Processed: {event.value}")

bus.subscribe(event_type=DataPointUpdatedEvent, handler=on_update_async)
```

### Multiple Event Types

```python
def on_datapoint(event: DataPointUpdatedEvent) -> None:
    print(f"DataPoint: {event.dpk} = {event.value}")

def on_system(event: BackendSystemEventData) -> None:
    print(f"System: {event.system_event}")

bus.subscribe(event_type=DataPointUpdatedEvent, handler=on_datapoint)
bus.subscribe(event_type=BackendSystemEventData, handler=on_system)
```

## Integration with CentralUnit

**Note**: This is planned for Phase 2 of the refactoring.

The EventBus will be integrated into CentralUnit as follows:

```python
class CentralUnit:
    def __init__(self, ...):
        self._event_bus = EventBus(enable_event_logging=debug_mode)

    # Legacy compatibility layer
    def register_backend_system_callback(
        self,
        callback: BackendSystemCallback,
    ) -> UnregisterCallback:
        """Register callback for system events (legacy API)."""
        def adapter(event: BackendSystemEventData) -> None:
            callback(system_event=event.system_event, **event.data)
        return self._event_bus.subscribe(event_type=BackendSystemEventData, handler=adapter)
```

## Migration Strategy

### Phase 1: EventBus Implementation ✅ COMPLETED

- [x] Create EventBus class
- [x] Define event types
- [x] Write comprehensive tests
- [x] Document API

### Phase 2: CentralUnit Integration ✅ COMPLETED

- [x] Add `_event_bus: EventBus` field to CentralUnit
- [x] Create adapter methods for legacy callback APIs
- [x] Migrate internal event publishing to use EventBus
- [x] Update tests to verify both old and new APIs work
- [x] Introduce `subscribe_to_*` API methods on DataPoint, Device, and Channel classes

### Phase 3: Modern API Adoption ✅ COMPLETED

- [x] EventBus is now the primary event mechanism
- [x] `subscribe_to_data_point_updated`, `subscribe_to_device_updated` and similar methods provide the recommended API
- [x] Legacy callback methods remain for backward compatibility
- [x] Home Assistant integration uses EventBus-based APIs

## Performance Considerations

### Concurrent Handler Execution

Handlers are executed concurrently via `asyncio.gather`:

```python
async def publish(self, event: Event) -> None:
    handlers = self._subscriptions.get(type(event), [])
    tasks = [self._safe_call_handler(h, event) for h in handlers]
    await asyncio.gather(*tasks, return_exceptions=True)
```

**Benefits**:

- Fast handlers don't wait for slow handlers
- Better throughput for high-frequency events
- Natural async/await flow

**Considerations**:

- Handlers should be idempotent
- No guaranteed execution order
- Use locking if handlers share mutable state

### Memory Usage

Events are **frozen dataclasses with slots**:

```python
@dataclass(frozen=True, slots=True)
class DataPointUpdatedEvent(Event):
    dpk: DataPointKey
    value: Any
    # ...
```

**Benefits**:

- ~20-40% less memory than regular dataclasses
- Immutable (thread-safe)
- Fast attribute access

## Error Handling

### Exception Isolation

Each handler is wrapped in error isolation:

```python
async def _safe_call_handler(self, handler: EventHandler, event: Event) -> None:
    try:
        result = handler(event)
        if asyncio.iscoroutine(result):
            await result
    except Exception:
        _LOGGER.exception(
            "Error in event handler %s for event %s",
            handler.__name__,
            type(event).__name__,
        )
```

**Guarantees**:

- Exception in one handler doesn't affect others
- All handlers are called even if some fail
- Errors are logged with full context

## Testing

### Unit Testing

```python
async def test_event_handling():
    bus = EventBus()
    received = []

    def handler(event: DataPointUpdatedEvent) -> None:
        received.append(event)

    bus.subscribe(event_type=DataPointUpdatedEvent, handler=handler)

    event = DataPointUpdatedEvent(...)
    await bus.publish(event=event)

    assert len(received) == 1
    assert received[0] == event
```

### Integration Testing

```python
async def test_with_central():
    central = CentralUnit(...)
    received_events = []

    async def handler(event: BackendSystemEventData) -> None:
        received_events.append(event)

    central.event_bus.subscribe(event_type=BackendSystemEventData, handler=handler)

    # Trigger device creation
    await central.create_devices(...)

    # Verify event was published
    assert len(received_events) > 0
    assert received_events[0].system_event == BackendSystemEvent.DEVICES_CREATED
```

## Best Practices

### 1. Use Specific Event Types

```python
# ✅ Good - type-safe, IDE autocomplete works
def handler(event: DataPointUpdatedEvent) -> None:
    print(event.dpk, event.value)

# ❌ Bad - loses type information
def handler(event: Event) -> None:
    print(event.timestamp)  # Only has base fields
```

### 2. Keep Handlers Lightweight

```python
# ✅ Good - quick handler, offloads work
async def handler(event: DataPointUpdatedEvent) -> None:
    asyncio.create_task(process_update(event))

# ⚠️ Avoid - blocks other handlers
async def handler(event: DataPointUpdatedEvent) -> None:
    await slow_database_operation(event)  # Blocks for seconds
```

### 3. Unsubscribe When Done

```python
class MyIntegration:
    def __init__(self, bus: EventBus):
        self._unsubscribe = bus.subscribe(event_type=DataPointUpdatedEvent, handler=self._handler)

    def cleanup(self) -> None:
        self._unsubscribe()

    async def _handler(self, event: DataPointUpdatedEvent) -> None:
        ...
```

### 4. Use Event Logging for Debugging

```python
# Enable detailed event logging
bus = EventBus(enable_event_logging=True)

# Logs every publish:
# DEBUG: Publishing DataPointUpdatedEvent to 3 handler(s) [count: 42]
```

## Comparison: Before vs After

### Before (Multiple Callback Dictionaries)

```python
class CentralUnit:
    def __init__(self):
        self._backend_system_handlers: set[BackendSystemHandler] = set()
        self._backend_parameter_callbacks: set[BackendParameterHandler] = set()
        self._homematic_callbacks: set[HomematicHandler] = set()

    def register_backend_system_event(self, handler: BackendSystemHandler):
        self._backend_system_handlers.add(cb)

    def publish_backend_system_event(self, system_event: BackendSystemEvent, **kwargs):
        for callback in self._backend_system_handlers:
            try:
                callback(system_event=system_event, **kwargs)
            except Exception as exc:
                _LOGGER.error("Callback failed: %s", exc)
```

### After (Unified EventBus)

```python
class CentralUnit:
    def __init__(self):
        self._event_bus = EventBus()

    def register_backend_system_callback(self, cb: BackendSystemCallback):
        """Legacy compatibility wrapper."""
        def adapter(event: BackendSystemEventData) -> None:
            cb(system_event=event.system_event, **event.data)
        return self._event_bus.subscribe(event_type=BackendSystemEventData, handler=adapter)

    async def publish_backend_system_event(self, event: BackendSystemEvent, **data):
        await self._event_bus.publish(event=BackendSystemEventData(
            timestamp=datetime.now(),
            system_event=event,
            data=data,
        ))
```

## Future Enhancements

### 1. Event Filtering

```python
# Subscribe only to specific device events (filter manually in handler)
def filtered_handler(event: DataPointUpdatedEvent) -> None:
    if event.dpk.channel_address.startswith("VCU0000001"):
        handler(event)

bus.subscribe(event_type=DataPointUpdatedEvent, handler=filtered_handler)
```

### 2. Event History/Replay

```python
# Keep last N events for debugging
bus = EventBus(history_size=100)

# Replay events
for event in bus.get_event_history(DataPointUpdatedEvent):
    print(event)
```

### 3. Metrics and Monitoring

```python
# Built-in metrics
stats = bus.get_metrics()
print(f"Events published: {stats['total_events']}")
print(f"Average handlers per event: {stats['avg_handlers']}")
print(f"Failed handlers: {stats['failed_handlers']}")
```

## Related Documentation

- [Architecture Overview](architecture.md)
- [Extension Points](extension_points.md)
- [Testing Guidelines](../CLAUDE.md#testing-guidelines)

## Changelog

### 2025-12-07 - Documentation Update

- Updated migration strategy to reflect completed phases
- All phases now marked as completed

### 2025-11-23 - Full Integration

- Completed CentralUnit integration
- Added `subscribe_to_*` methods to DataPoint, Device, and Channel classes
- EventBus now primary event mechanism throughout the codebase

### 2025-11-18 - Initial Implementation

- Created EventBus class with type-safe subscription/publishing
- Defined core event types (DataPoint, Backend, Homematic, Sysvar, Interface)
- Implemented async-first design with concurrent handler execution
- Added comprehensive test coverage (100%)
- Documented API and migration strategy
