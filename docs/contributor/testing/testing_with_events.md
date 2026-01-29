# Testing with Events

This guide shows how to use EventCapture for behavior-focused testing.

## Why Event-Based Testing?

Traditional tests often check internal state:

```python
# Fragile - depends on implementation details
async def test_circuit_breaker_trips_old():
    client = await create_client()

    for _ in range(5):
        with pytest.raises(ConnectionError):
            await client.call("method")

    # Checking internal state - breaks if implementation changes
    assert client._circuit_breaker._state == "open"
    assert client._circuit_breaker._failure_count == 5
```

Event-based tests verify behavior:

```python
# Robust - tests observable behavior
async def test_circuit_breaker_trips():
    from aiohomematic_test_support.event_capture import EventCapture
    from aiohomematic.central.events import CircuitBreakerTrippedEvent

    central = await create_central()
    capture = EventCapture()
    capture.subscribe_to(central.event_bus, CircuitBreakerTrippedEvent)

    for _ in range(5):
        with pytest.raises(ConnectionError):
            await central.clients["rf"].call("method")

    # Tests observable behavior via events
    capture.assert_event_emitted(
        event_type=CircuitBreakerTrippedEvent,
        failure_count=5,
    )
    capture.cleanup()
```

## EventCapture API

### Basic Usage

```python
from aiohomematic_test_support.event_capture import EventCapture
from aiohomematic.central.events import SomeEvent

capture = EventCapture()
capture.subscribe_to(event_bus, SomeEvent)

# ... perform test actions ...

capture.assert_event_emitted(event_type=SomeEvent, attr1="value1")
capture.cleanup()
```

### Subscribe to Multiple Types

```python
capture.subscribe_to(
    event_bus,
    CircuitBreakerTrippedEvent,
    CircuitBreakerStateChangedEvent,
    ConnectionStageChangedEvent,
)
```

### Assert Specific Count

```python
capture.assert_event_emitted(event_type=SomeEvent, count=3)
```

### Assert No Event

```python
capture.assert_no_event(event_type=SomeEvent)
```

### Get Events for Manual Inspection

```python
events = capture.get_events_of_type(event_type=SomeEvent)
assert events[0].some_attribute == expected_value
```

## EventSequenceAssertion

For verifying event ordering:

```python
from aiohomematic_test_support.event_capture import EventSequenceAssertion

sequence = EventSequenceAssertion(expected_sequence=[
    ConnectionStageChangedEvent,
    ClientStateChangedEvent,
    CentralStateChangedEvent,
])

event_bus.subscribe(event_type=Event, event_key=None, handler=sequence.on_event)

# ... perform actions ...

# Strict: exact sequence match
sequence.verify(strict=True)

# Non-strict: events appear in order (others may be interspersed)
sequence.verify(strict=False)
```

## Migration Examples

### Connection Health Test

Before:

```python
def test_connection_unhealthy():
    client._pong_tracker._consecutive_failures = 5
    assert client.health_status == "unhealthy"
```

After:

```python
async def test_connection_unhealthy():
    capture = EventCapture()
    capture.subscribe_to(event_bus, ConnectionHealthChangedEvent)

    # Trigger health events
    for _ in range(5):
        await client.ping()  # Fails

    events = capture.get_events_of_type(event_type=ConnectionHealthChangedEvent)
    unhealthy = [e for e in events if e.consecutive_pongs == 0]
    assert len(unhealthy) > 0
```

### State Machine Transition Test

Before:

```python
def test_state_transition():
    sm.transition_to(ClientState.CONNECTED)
    assert sm._current_state == ClientState.CONNECTED
```

After:

```python
def test_state_transition():
    capture = EventCapture()
    capture.subscribe_to(event_bus, ClientStateChangedEvent)

    sm.transition_to(ClientState.CONNECTED)

    capture.assert_event_emitted(
        event_type=ClientStateChangedEvent,
        new_state="connected",
    )
```

## Best Practices

1. **Always call cleanup()**: Use try/finally or the `event_capture` fixture
2. **Subscribe before action**: Events are not retroactively captured
3. **Test behavior, not implementation**: Focus on what events are emitted, not internal state
4. **Use sequence assertions sparingly**: Only when order matters for correctness

## Using the event_capture Fixture

The test suite provides a pytest fixture for automatic cleanup:

```python
def test_my_feature(event_capture):
    """Test with automatic cleanup."""
    event_capture.subscribe_to(event_bus, SomeEvent)

    # ... test actions ...

    event_capture.assert_event_emitted(event_type=SomeEvent)
    # No cleanup needed - fixture handles it
```
