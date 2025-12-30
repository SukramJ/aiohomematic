# ADR 0006: Event System Priorities and Batching

## Status

Accepted (Implemented)

## Context

The EventBus system handles all internal event communication. Two enhancements were proposed:

1. **Event Priorities**: Allow handlers to specify execution order
2. **Event Batching**: Optimize bulk event publishing (e.g., during device discovery)

## Decision

Implement both features as backward-compatible additions to EventBus.

### Event Priorities

Added `EventPriority` enum with four levels:

```python
class EventPriority(IntEnum):
    """Priority levels for event handlers."""
    LOW = 0        # Cleanup, notifications
    NORMAL = 50    # Standard application logic (default)
    HIGH = 100     # Critical state updates
    CRITICAL = 200 # Logging/metrics, must run first
```

**Usage**:

```python
bus.subscribe(
    event_type=DataPointUpdatedEvent,
    event_key=None,
    handler=my_handler,
    priority=EventPriority.HIGH,  # Called before NORMAL handlers
)
```

**Execution order**:

- Higher priority handlers execute first (CRITICAL > HIGH > NORMAL > LOW)
- Within same priority, handlers execute in subscription order (FIFO)
- Default priority is NORMAL for backward compatibility

### Event Batching

Added `EventBatch` class for efficient bulk publishing:

```python
class EventBatch:
    """Collects events for batched publishing."""

    def __init__(self, *, bus: EventBus) -> None:
        self._bus = bus
        self._events: list[Event] = []

    def add(self, *, event: Event) -> None:
        self._events.append(event)

    async def flush(self) -> None:
        # Group events by type for efficient handler lookup
        await self._bus.publish_batch(events=self._events)
        self._events.clear()
```

**Usage**:

```python
# Context manager for automatic flush
async with EventBatch(bus=event_bus) as batch:
    batch.add(event=DeviceStateChangedEvent(...))
    batch.add(event=DeviceStateChangedEvent(...))
    # Events published when context exits

# Or manual usage
batch = EventBatch(bus=event_bus)
batch.add(event=event1)
batch.add_all(events=[event2, event3])
await batch.flush()
```

## Consequences

### Advantages

- **Backward compatible**: Existing code works unchanged (default NORMAL priority)
- **Flexible ordering**: Critical handlers (logging, metrics) can run first
- **Performance optimization**: Batching reduces handler lookup overhead during bulk operations
- **Clean API**: Context manager pattern ensures events are always flushed

### Disadvantages

- **Slightly more complex EventBus**: Priority sorting and batch handling add code
- **Potential for misuse**: Overuse of CRITICAL priority could cause unexpected behavior

### Use Cases

**Event Priorities**:

- CRITICAL: Logging handlers that must capture all events
- HIGH: Security-related state updates
- NORMAL: Standard application logic
- LOW: Analytics, cleanup operations

**Event Batching**:

- Device discovery (many DeviceCreatedEvents)
- Bulk value updates
- System startup/shutdown sequences

## Alternatives Considered

### 1. Middleware/Interceptor Pattern for Priorities

**Rejected**: More complex than simple priority ordering. Overkill for the use case.

### 2. Separate High-Priority Event Bus

**Rejected**: Would split event handling logic. Single bus with priorities is cleaner.

### 3. Async Queue with Worker Pool for Batching

**Rejected**: Adds complexity. Simple batch collection and flush is sufficient.

## References

- `aiohomematic/central/events/bus.py` - EventBus implementation
- `docs/architecture.md` - "Event System Enhancements: Implemented" section

---

_Created: 2025-12-10_
_Author: Architecture Review_
