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

#### BackendSystemEventData

System-level events from the backend.

| Field          | Type                 | Description                |
| -------------- | -------------------- | -------------------------- |
| `timestamp`    | `datetime`           | When the event was created |
| `system_event` | `BackendSystemEvent` | Type of system event       |
| `data`         | `dict[str, Any]`     | Event-specific data        |

**Key:** `None` (global event)

**BackendSystemEvent values:**

- `DEVICES_CREATED` - New devices were created
- `DEVICES_DELETED` - Devices were deleted
- `DELETE_DEVICES` - Request to delete devices
- `ERROR` - System error occurred
- `HUB_REFRESHED` - Hub data was refreshed
- `LIST_DEVICES` - Device list updated
- `NEW_DEVICES` - New devices discovered
- `RE_ADDED_DEVICE` - Device was re-added
- `REPLACE_DEVICE` - Device was replaced
- `UPDATE_DEVICE` - Device was updated

```python
from aiohomematic.central.event_bus import BackendSystemEventData
from aiohomematic.const import BackendSystemEvent

async def handler(*, event: BackendSystemEventData) -> None:
    if event.system_event == BackendSystemEvent.DEVICES_CREATED:
        print(f"New devices: {event.data}")

unsubscribe = central.event_bus.subscribe(
    event_type=BackendSystemEventData,
    event_key=None,
    handler=handler,
)
```

---

### Homematic Events

#### HomematicEvent

Homematic-specific events (button presses, interface events, etc.).

| Field        | Type                  | Description                |
| ------------ | --------------------- | -------------------------- |
| `timestamp`  | `datetime`            | When the event was created |
| `event_type` | `EventType`           | Type of Homematic event    |
| `event_data` | `dict[EventKey, Any]` | Event-specific data        |

**Key:** `None` (global event)

**EventType values:**

- `KEYPRESS` - Button press event
- `IMPULSE` - Impulse event
- `INTERFACE` - Interface event

**EventKey values (in event_data):**

- `CHANNEL_ADDRESS` - Channel that triggered the event
- `INTERFACE_ID` - Interface identifier
- `PARAMETER` - Parameter name
- `VALUE` - Parameter value

```python
from aiohomematic.central.event_bus import HomematicEvent
from aiohomematic.const import DeviceTriggerEventType, EventKey


async def handler(*, event: HomematicEvent) -> None:
    if event.event_type == DeviceTriggerEventType.KEYPRESS:
        channel = event.event_data[EventKey.CHANNEL_ADDRESS]
        param = event.event_data[EventKey.PARAMETER]
        print(f"Button press on {channel}: {param}")


unsubscribe = central.event_bus.subscribe(
    event_type=HomematicEvent,
    event_key=None,
    handler=handler,
)
```

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

### Connection Events

#### FetchDataFailedEvent

Data fetch operation failed for an interface.

| Field          | Type       | Description                |
| -------------- | ---------- | -------------------------- |
| `timestamp`    | `datetime` | When the event was created |
| `interface_id` | `str`      | Interface identifier       |

**Key:** `interface_id`

```python
from aiohomematic.central.event_bus import FetchDataFailedEvent

async def handler(*, event: FetchDataFailedEvent) -> None:
    print(f"Data fetch failed for {event.interface_id}")

unsubscribe = central.event_bus.subscribe(
    event_type=FetchDataFailedEvent,
    event_key=None,
    handler=handler,
)
```

#### PingPongMismatchEvent

PING/PONG mismatch detected for an interface. Published when:

- `PENDING`: A PING was sent but no PONG was received in time
- `UNKNOWN`: A PONG was received without a matching PING

| Field            | Type                   | Description                                |
| ---------------- | ---------------------- | ------------------------------------------ |
| `timestamp`      | `datetime`             | When the event was created                 |
| `interface_id`   | `str`                  | Interface identifier                       |
| `mismatch_type`  | `PingPongMismatchType` | `PENDING` or `UNKNOWN`                     |
| `mismatch_count` | `int`                  | Current count of mismatched PINGs/PONGs    |
| `acceptable`     | `bool`                 | Whether mismatch count is within threshold |

**Key:** `interface_id`

```python
from aiohomematic.central.event_bus import PingPongMismatchEvent
from aiohomematic.const import PingPongMismatchType

async def handler(*, event: PingPongMismatchEvent) -> None:
    if event.mismatch_type == PingPongMismatchType.PENDING:
        print(f"Pending PONG mismatch on {event.interface_id}: {event.mismatch_count}")
    elif event.mismatch_type == PingPongMismatchType.UNKNOWN:
        print(f"Unknown PONG on {event.interface_id}: {event.mismatch_count}")

unsubscribe = central.event_bus.subscribe(
    event_type=PingPongMismatchEvent,
    event_key=None,
    handler=handler,
)
```

#### DeviceAvailabilityChangedEvent

Device availability has changed. Published when UN_REACH or STICKY_UN_REACH parameter changes.

| Field             | Type       | Description                             |
| ----------------- | ---------- | --------------------------------------- |
| `timestamp`       | `datetime` | When the event was created              |
| `device_address`  | `str`      | Device address (e.g., "VCU0000001")     |
| `channel_address` | `str`      | Channel address (e.g., "VCU0000001:0")  |
| `parameter`       | `str`      | Parameter that changed (UN_REACH, etc.) |
| `available`       | `bool`     | Whether the device is available         |

**Key:** `device_address`

```python
from aiohomematic.central.event_bus import DeviceAvailabilityChangedEvent

async def handler(*, event: DeviceAvailabilityChangedEvent) -> None:
    if event.available:
        print(f"Device {event.device_address} is now available")
    else:
        print(f"Device {event.device_address} is now unavailable")

unsubscribe = central.event_bus.subscribe(
    event_type=DeviceAvailabilityChangedEvent,
    event_key=None,  # All devices, or specific device_address
    handler=handler,
)
```

#### ConnectionStateChangedEvent

Connection state has changed for an interface.

| Field          | Type       | Description                        |
| -------------- | ---------- | ---------------------------------- |
| `timestamp`    | `datetime` | When the event was created         |
| `interface_id` | `str`      | Interface identifier               |
| `connected`    | `bool`     | Whether the interface is connected |

**Key:** `interface_id`

#### CallbackStateChangedEvent

Callback channel state has changed for an interface. This is the modern replacement for `InterfaceEvent` with `InterfaceEventType.CALLBACK`.

| Field                      | Type       | Description                           |
| -------------------------- | ---------- | ------------------------------------- | ------------------------------------------ |
| `timestamp`                | `datetime` | When the event was created            |
| `interface_id`             | `str`      | Interface identifier                  |
| `alive`                    | `bool`     | Whether the callback channel is alive |
| `seconds_since_last_event` | `int       | None`                                 | Seconds since last event (None when alive) |

**Key:** `interface_id`

The callback channel is considered alive when events are received from the CCU. If no events are received for the configured timeout period (`callback_warn_interval`), it is considered dead.

```python
from aiohomematic.central.event_bus import CallbackStateChangedEvent

async def handler(*, event: CallbackStateChangedEvent) -> None:
    if not event.alive:
        print(f"Callback dead for {event.interface_id}, "
              f"no events for {event.seconds_since_last_event}s")
    else:
        print(f"Callback alive for {event.interface_id}")

unsubscribe = central.event_bus.subscribe(
    event_type=CallbackStateChangedEvent,
    event_key=None,
    handler=handler,
)
```

#### ClientStateChangedEvent

Client state machine state has changed.

| Field          | Type          | Description                |
| -------------- | ------------- | -------------------------- |
| `timestamp`    | `datetime`    | When the event was created |
| `interface_id` | `str`         | Interface identifier       |
| `old_state`    | `ClientState` | Previous state             |
| `new_state`    | `ClientState` | New state                  |

**Key:** `interface_id`

**ClientState values:**

- `INIT` - Initial state
- `CONNECTING` - Connecting to backend
- `CONNECTED` - Connected and operational
- `RECONNECTING` - Attempting to reconnect
- `DISCONNECTED` - Disconnected from backend
- `ERROR` - Error state

#### CentralStateChangedEvent

Central state machine state has changed.

| Field       | Type           | Description                 |
| ----------- | -------------- | --------------------------- |
| `timestamp` | `datetime`     | When the event was created  |
| `old_state` | `CentralState` | Previous state              |
| `new_state` | `CentralState` | New state                   |
| `reason`    | `str`          | Reason for the state change |

**Key:** `None` (global event)

**CentralState values:**

- `INIT` - Initial state
- `STARTING` - System is starting
- `RUNNING` - System is running normally
- `RECONNECTING` - Reconnecting after connection loss
- `STOPPING` - System is stopping
- `STOPPED` - System has stopped
- `ERROR` - Error state

```python
from aiohomematic.central.event_bus import CentralStateChangedEvent
from aiohomematic.const import CentralState

async def handler(*, event: CentralStateChangedEvent) -> None:
    print(f"Central state: {event.old_state} -> {event.new_state}")
    if event.new_state == CentralState.RUNNING:
        print("System is ready!")

unsubscribe = central.event_bus.subscribe(
    event_type=CentralStateChangedEvent,
    event_key=None,
    handler=handler,
)
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
