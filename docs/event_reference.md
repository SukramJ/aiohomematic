# Event Reference

This document provides a complete reference of all events in aiohomematic and how to subscribe to them.

## Overview

aiohomematic uses a type-safe, async-first EventBus for decoupled event handling. Events are immutable dataclasses that carry information about state changes in the system.

**Key concepts:**

- **Event types**: Strongly-typed dataclasses inheriting from `Event`
- **Event key**: Each event has a `key` property for filtering subscriptions
- **Handlers**: Can be sync or async functions
- **Unsubscribe**: All subscriptions return an unsubscribe callable

## Event Types

### Data Point Events

#### DataPointUpdatedEvent

Fired when a data point value is updated from the backend.

| Field         | Type           | Description                              |
| ------------- | -------------- | ---------------------------------------- |
| `timestamp`   | `datetime`     | When the event was created               |
| `dpk`         | `DataPointKey` | Unique identifier for the data point     |
| `value`       | `Any`          | The new value                            |
| `received_at` | `datetime`     | When the value was received from backend |

**Key:** `DataPointKey`

```python
from aiohomematic.central.event_bus import DataPointUpdatedEvent

async def handler(*, event: DataPointUpdatedEvent) -> None:
    print(f"DataPoint {event.dpk.parameter} = {event.value}")

unsubscribe = central.event_bus.subscribe(
    event_type=DataPointUpdatedEvent,
    event_key=None,  # All data points, or specific DataPointKey
    handler=handler,
)
```

#### DataPointUpdatedCallbackEvent

Callback event for external integrations (e.g., Home Assistant entities).

| Field       | Type             | Description                          |
| ----------- | ---------------- | ------------------------------------ |
| `timestamp` | `datetime`       | When the event was created           |
| `unique_id` | `str`            | Unique identifier of the data point  |
| `custom_id` | `str`            | Custom identifier for the subscriber |
| `kwargs`    | `dict[str, Any]` | Additional callback arguments        |

**Key:** `unique_id`

---

### Backend Events

#### BackendParameterEvent

Raw parameter update event from the backend (re-published from RPC callbacks).

| Field             | Type       | Description                              |
| ----------------- | ---------- | ---------------------------------------- |
| `timestamp`       | `datetime` | When the event was created               |
| `interface_id`    | `str`      | Interface identifier (e.g., "BidCos-RF") |
| `channel_address` | `str`      | Channel address (e.g., "VCU0000001:1")   |
| `parameter`       | `str`      | Parameter name (e.g., "STATE")           |
| `value`           | `Any`      | The parameter value                      |

**Key:** `DataPointKey` (constructed from fields)

#### DataPointStatusUpdatedEvent

Data point status (availability) changed.

| Field       | Type           | Description                          |
| ----------- | -------------- | ------------------------------------ |
| `timestamp` | `datetime`     | When the event was created           |
| `dpk`       | `DataPointKey` | Unique identifier for the data point |
| `available` | `bool`         | Whether the data point is available  |

**Key:** `DataPointKey`

---

### System Variable Events

#### SysvarUpdatedEvent

System variable value was updated.

| Field         | Type       | Description                            |
| ------------- | ---------- | -------------------------------------- |
| `timestamp`   | `datetime` | When the event was created             |
| `state_path`  | `str`      | Path/identifier of the system variable |
| `value`       | `Any`      | The new value                          |
| `received_at` | `datetime` | When the value was received            |

**Key:** `state_path`

---

### Device Events

#### DeviceUpdatedEvent

Device state has been updated.

| Field            | Type       | Description                |
| ---------------- | ---------- | -------------------------- |
| `timestamp`      | `datetime` | When the event was created |
| `device_address` | `str`      | Address of the device      |

**Key:** `device_address`

#### DeviceRemovedEvent

Device or data point has been removed.

| Field       | Type       | Description                             |
| ----------- | ---------- | --------------------------------------- |
| `timestamp` | `datetime` | When the event was created              |
| `unique_id` | `str`      | Unique identifier of the removed entity |

**Key:** `unique_id`

#### FirmwareUpdatedEvent

Device firmware information has been updated.

| Field            | Type       | Description                |
| ---------------- | ---------- | -------------------------- |
| `timestamp`      | `datetime` | When the event was created |
| `device_address` | `str`      | Address of the device      |

**Key:** `device_address`

#### LinkPeerChangedEvent

Channel link peer addresses have changed.

| Field             | Type       | Description                |
| ----------------- | ---------- | -------------------------- |
| `timestamp`       | `datetime` | When the event was created |
| `channel_address` | `str`      | Address of the channel     |

**Key:** `channel_address`

---

### Integration Events

These events are defined in `aiohomematic/central/integration_events.py` and are primarily used for Home Assistant integration.

#### SystemStatusEvent

System status changes for integration consumers.

| Field          | Type                    | Description                     |
| -------------- | ----------------------- | ------------------------------- |
| `timestamp`    | `datetime`              | When the event was created      |
| `status_type`  | `SystemStatusEventType` | Type of status event            |
| `central_name` | `str`                   | Name of the central             |
| `available`    | `bool \| None`          | Whether the system is available |

**Key:** `None` (global event)

#### DeviceLifecycleEvent

Device lifecycle events (created, removed, availability).

| Field                  | Type                       | Description                         |
| ---------------------- | -------------------------- | ----------------------------------- |
| `timestamp`            | `datetime`                 | When the event was created          |
| `event_type`           | `DeviceLifecycleEventType` | Type of lifecycle event             |
| `availability_changes` | `tuple`                    | Tuple of (address, available) pairs |

**Key:** `None` (global event)

**DeviceLifecycleEventType values:**

- `AVAILABILITY_CHANGED` - Device availability changed
- `DATA_POINTS_CREATED` - Data points were created

#### DeviceTriggerEvent

Device trigger events (button press, etc.).

| Field            | Type                     | Description                |
| ---------------- | ------------------------ | -------------------------- |
| `timestamp`      | `datetime`               | When the event was created |
| `event_type`     | `DeviceTriggerEventType` | Type of trigger event      |
| `device_address` | `str`                    | Address of the device      |
| `channel_no`     | `int`                    | Channel number             |
| `parameter`      | `str`                    | Parameter name             |
| `value`          | `Any`                    | Parameter value            |

**Key:** `None` (global event)

**DeviceTriggerEventType values:**

- `KEYPRESS` - Button press event
- `KEYPRESS_LONG_START` - Long press start event
- `IMPULSE` - Impulse event

```python
from aiohomematic.central.integration_events import DeviceTriggerEvent
from aiohomematic.const import DeviceTriggerEventType

async def handler(*, event: DeviceTriggerEvent) -> None:
    if event.event_type == DeviceTriggerEventType.KEYPRESS:
        print(f"Button press on {event.device_address}:{event.channel_no}: {event.parameter}")

# Subscribe via integration callback, not directly via EventBus
```

---

## Subscription Methods on Model Classes

For convenience, model classes provide typed subscription methods:

### DataPoint

```python
# Subscribe to value updates
unsubscribe = data_point.subscribe_to_data_point_updated(
    handler=my_handler,
    custom_id="my-integration",
)

# Subscribe to device removal
unsubscribe = data_point.subscribe_to_device_removed(
    handler=my_removal_handler,
)
```

### Device

```python
# Subscribe to device state updates
unsubscribe = device.subscribe_to_device_updated(
    handler=my_handler,
)

# Subscribe to firmware updates
unsubscribe = device.subscribe_to_firmware_updated(
    handler=my_firmware_handler,
)
```

### Channel

```python
# Subscribe to link peer changes
unsubscribe = channel.subscribe_to_link_peer_changed(
    handler=my_handler,
)
```

---

## EventBus API

### Direct Subscription

```python
from aiohomematic.central.event_bus import EventBus, DataPointUpdatedEvent

# Subscribe to all events of a type
unsubscribe = event_bus.subscribe(
    event_type=DataPointUpdatedEvent,
    event_key=None,
    handler=my_handler,
)

# Subscribe to events with a specific key
unsubscribe = event_bus.subscribe(
    event_type=DataPointUpdatedEvent,
    event_key=my_data_point_key,
    handler=my_handler,
)

# Unsubscribe when done
unsubscribe()
```

### Handler Priorities

```python
from aiohomematic.central.event_bus import EventPriority

# High priority handler (runs before normal handlers)
unsubscribe = event_bus.subscribe(
    event_type=DataPointUpdatedEvent,
    event_key=None,
    handler=my_critical_handler,
    priority=EventPriority.HIGH,
)
```

**Priority levels:**

| Priority   | Value | Use Case                           |
| ---------- | ----- | ---------------------------------- |
| `CRITICAL` | 200   | Logging, metrics (runs first)      |
| `HIGH`     | 100   | Important handlers                 |
| `NORMAL`   | 50    | Default for most handlers          |
| `LOW`      | 0     | Cleanup, notifications (runs last) |

### Batch Publishing

For performance when publishing multiple events:

```python
from aiohomematic.central.event_bus import EventBatch

async with EventBatch(bus=event_bus) as batch:
    batch.add(event=event1)
    batch.add(event=event2)
    batch.add(event=event3)
    # All events published when context exits
```

---

## Best Practices

### 1. Use Specific Event Types

```python
# Good - type-safe, IDE autocomplete works
async def handler(*, event: DataPointUpdatedEvent) -> None:
    print(event.dpk, event.value)

# Bad - loses type information
async def handler(*, event: Event) -> None:
    print(event.timestamp)  # Only base fields available
```

### 2. Keep Handlers Lightweight

```python
# Good - quick handler, offloads heavy work
async def handler(*, event: DataPointUpdatedEvent) -> None:
    asyncio.create_task(process_update(event))

# Avoid - blocks other handlers
async def handler(*, event: DataPointUpdatedEvent) -> None:
    await slow_database_operation(event)  # Blocks for seconds
```

### 3. Always Unsubscribe

```python
class MyIntegration:
    def __init__(self, event_bus: EventBus) -> None:
        self._unsubscribe = event_bus.subscribe(
            event_type=DataPointUpdatedEvent,
            event_key=None,
            handler=self._handler,
        )

    def cleanup(self) -> None:
        self._unsubscribe()
```

### 4. Handle Errors Gracefully

The EventBus isolates handler errors - one failing handler won't affect others. However, you should still handle expected errors:

```python
async def handler(*, event: DataPointUpdatedEvent) -> None:
    try:
        await process(event)
    except ExpectedError:
        _LOGGER.warning("Could not process event: %s", event.dpk)
```

---

## Related Documentation

- [EventBus Architecture](event_bus.md) - Internal architecture and design decisions
- [Architecture Overview](architecture.md) - Overall system architecture
- [Data Flow](data_flow.md) - How data flows through the system
