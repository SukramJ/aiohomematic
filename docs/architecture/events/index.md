# Event System

aiohomematic uses a type-safe, async-first EventBus for decoupled event handling throughout the system.

## At a Glance

```python
from aiohomematic.central.events import DataPointValueReceivedEvent

async def on_update(*, event: DataPointValueReceivedEvent) -> None:
    print(f"{event.dpk.parameter} = {event.value}")

unsubscribe = central.event_bus.subscribe(
    event_type=DataPointValueReceivedEvent,
    event_key=None,
    handler=on_update,
)

# Later: unsubscribe()
```

## Key Concepts

| Concept         | Description                                                 |
| --------------- | ----------------------------------------------------------- |
| **Event**       | Immutable dataclass carrying state change information       |
| **EventBus**    | Central hub for publishing and subscribing to events        |
| **Handler**     | Sync or async function called when event is published       |
| **Unsubscribe** | Callable returned by `subscribe()` to stop receiving events |

## Most Common Events

| Event                         | When to Use                                |
| ----------------------------- | ------------------------------------------ |
| `DataPointValueReceivedEvent` | Track value changes from devices           |
| `DeviceStateChangedEvent`     | Monitor device state updates               |
| `DeviceLifecycleEvent`        | React to device add/remove/availability    |
| `SystemStatusChangedEvent`    | Monitor system health (for HA integration) |
| `DeviceTriggerEvent`          | Handle button presses and triggers         |

## Subscription Patterns

### Via EventBus (Recommended for integrations)

```python
# Subscribe to all events of a type
unsubscribe = central.event_bus.subscribe(
    event_type=DataPointValueReceivedEvent,
    event_key=None,
    handler=my_handler,
)
```

### Via Model Classes (Convenient shortcuts)

```python
# Subscribe to a specific data point
unsubscribe = data_point.subscribe_to_data_point_updated(
    handler=my_handler,
    custom_id="my-app",
)

# Subscribe to device updates
unsubscribe = device.subscribe_to_device_updated(
    handler=my_device_handler,
)
```

## Documentation

| Document                                                                    | Content                                                   |
| --------------------------------------------------------------------------- | --------------------------------------------------------- |
| **[Event Reference](event_reference.md)**                                   | Complete list of all event types with fields and examples |
| **[EventBus Architecture](event_bus.md)**                                   | Internal design, performance, error handling              |
| **[Event-Driven Metrics](../event_driven_metrics.md)**                      | How metrics are collected via events                      |
| **[Testing with Events](../../contributor/testing/testing_with_events.md)** | How to test event-based code                              |

## Quick Examples

### React to Device Value Changes

```python
from aiohomematic.central.events import DataPointValueReceivedEvent

async def on_value_changed(*, event: DataPointValueReceivedEvent) -> None:
    if event.dpk.parameter == "STATE":
        print(f"Switch {event.dpk.channel_address} is now {event.value}")

unsubscribe = central.event_bus.subscribe(
    event_type=DataPointValueReceivedEvent,
    event_key=None,
    handler=on_value_changed,
)
```

### Monitor System Health

```python
from aiohomematic.central.events import SystemStatusChangedEvent
from aiohomematic.const import CentralState

async def on_status_changed(*, event: SystemStatusChangedEvent) -> None:
    if event.central_state == CentralState.DEGRADED:
        print("System degraded - some interfaces unavailable")
    elif event.central_state == CentralState.FAILED:
        print(f"System failed: {event.failure_reason}")

unsubscribe = central.event_bus.subscribe(
    event_type=SystemStatusChangedEvent,
    event_key=None,
    handler=on_status_changed,
)
```

### Handle Button Presses

```python
from aiohomematic.central.events import DeviceTriggerEvent
from aiohomematic.const import DeviceTriggerEventType

async def on_button_press(*, event: DeviceTriggerEvent) -> None:
    if event.trigger_type == DeviceTriggerEventType.KEYPRESS:
        print(f"Button {event.parameter} pressed on {event.device_address}")

unsubscribe = central.event_bus.subscribe(
    event_type=DeviceTriggerEvent,
    event_key=None,
    handler=on_button_press,
)
```

## Best Practices

1. **Always unsubscribe** when your component is destroyed
2. **Keep handlers lightweight** - offload heavy work to tasks
3. **Use specific event types** for type safety and IDE support
4. **Filter in handlers** if you only need specific events

See [Event Reference](event_reference.md) for the complete event catalog.
