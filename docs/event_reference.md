# Event Reference

This document provides a complete reference of all events in aiohomematic and how to subscribe to them.

## Overview

aiohomematic uses a type-safe, async-first EventBus for decoupled event handling. Events are immutable dataclasses that carry information about state changes in the system.

**Key concepts:**

- **Event types**: Strongly-typed dataclasses inheriting from `Event`
- **Event key**: Each event has a `key` property for filtering subscriptions
- **Handlers**: Can be sync or async functions
- **Unsubscribe**: All subscriptions return an unsubscribe callable

## Quick Reference

| Event Type                        | Category        | Key               | Description                         |
| --------------------------------- | --------------- | ----------------- | ----------------------------------- |
| `DataPointValueReceivedEvent`     | Data Point      | `DataPointKey`    | Value updated from backend          |
| `DataPointStatusReceivedEvent`    | Data Point      | `DataPointKey`    | Status parameter updated            |
| `DataPointStateChangedEvent`      | Data Point      | `unique_id`       | External callback notification      |
| `RpcParameterReceivedEvent`       | Backend         | `DataPointKey`    | Re-published raw parameter from RPC |
| `SysvarStateChangedEvent`         | System Variable | `state_path`      | Sysvar value changed                |
| `DeviceStateChangedEvent`         | Device          | `device_address`  | Device state updated                |
| `DeviceRemovedEvent`              | Device          | `unique_id`       | Device/data point removed           |
| `FirmwareStateChangedEvent`       | Device          | `device_address`  | Firmware info updated               |
| `LinkPeerChangedEvent`            | Device          | `channel_address` | Link peers changed                  |
| `ConnectionStageChangedEvent`     | Connection      | `interface_id`    | Reconnection stage                  |
| `ConnectionHealthChangedEvent`    | Connection      | `interface_id`    | Health status change                |
| `CacheInvalidatedEvent`           | Cache           | `scope`           | Cache entries cleared               |
| `CircuitBreakerStateChangedEvent` | Circuit Breaker | `interface_id`    | State transition                    |
| `CircuitBreakerTrippedEvent`      | Circuit Breaker | `interface_id`    | Breaker tripped                     |
| `HealthRecordedEvent`             | Health          | `interface_id`    | Health status recorded              |
| `ClientStateChangedEvent`         | State Machine   | `interface_id`    | Client state change                 |
| `CentralStateChangedEvent`        | State Machine   | `central_name`    | Central state change                |
| `DataRefreshTriggeredEvent`       | Data Refresh    | `interface_id`    | Refresh started                     |
| `DataRefreshCompletedEvent`       | Data Refresh    | `interface_id`    | Refresh completed                   |
| `ProgramExecutedEvent`            | Hub             | `program_id`      | Program executed                    |
| `RequestCoalescedEvent`           | Optimization    | `interface_id`    | Requests merged                     |
| `SystemStatusChangedEvent`        | Integration     | `None`            | System status (HA)                  |
| `DeviceLifecycleEvent`            | Integration     | `None`            | Device lifecycle (HA)               |
| `DataPointsCreatedEvent`          | Integration     | `None`            | Data points created (HA)            |
| `DeviceTriggerEvent`              | Integration     | `None`            | Device trigger (HA)                 |

---

## Data Point Events

### DataPointValueReceivedEvent

Fired when a data point value is updated from the backend.

```python
from aiohomematic.central.event_bus import DataPointValueReceivedEvent
```

| Field         | Type           | Description                              |
| ------------- | -------------- | ---------------------------------------- |
| `timestamp`   | `datetime`     | When the event was created               |
| `dpk`         | `DataPointKey` | Unique identifier for the data point     |
| `value`       | `Any`          | The new value                            |
| `received_at` | `datetime`     | When the value was received from backend |

**Key:** `DataPointKey`

```python
async def handler(*, event: DataPointValueReceivedEvent) -> None:
    print(f"DataPoint {event.dpk.parameter} = {event.value}")

unsubscribe = central.event_bus.subscribe(
    event_type=DataPointValueReceivedEvent,
    event_key=None,  # All data points, or specific DataPointKey
    handler=handler,
)
```

### DataPointStatusReceivedEvent

Fired when a STATUS parameter value is updated (e.g., LEVEL_STATUS).

```python
from aiohomematic.central.event_bus import DataPointStatusReceivedEvent
```

| Field          | Type           | Description                            |
| -------------- | -------------- | -------------------------------------- |
| `timestamp`    | `datetime`     | When the event was created             |
| `dpk`          | `DataPointKey` | Key of the MAIN parameter (not STATUS) |
| `status_value` | `int \| str`   | The status value                       |
| `received_at`  | `datetime`     | When the value was received            |

**Key:** `DataPointKey` (of the main parameter)

### DataPointStateChangedEvent

Callback event for external integrations (e.g., Home Assistant entities).

```python
from aiohomematic.central.event_bus import DataPointStateChangedEvent
```

| Field       | Type       | Description                          |
| ----------- | ---------- | ------------------------------------ |
| `timestamp` | `datetime` | When the event was created           |
| `unique_id` | `str`      | Unique identifier of the data point  |
| `custom_id` | `str`      | Custom identifier for the subscriber |

**Key:** `unique_id`

---

## Backend Events

### RpcParameterReceivedEvent

Raw parameter update event from the backend (re-published from RPC callbacks).

```python
from aiohomematic.central.event_bus import RpcParameterReceivedEvent
```

| Field             | Type       | Description                              |
| ----------------- | ---------- | ---------------------------------------- |
| `timestamp`       | `datetime` | When the event was created               |
| `interface_id`    | `str`      | Interface identifier (e.g., "BidCos-RF") |
| `channel_address` | `str`      | Channel address (e.g., "VCU0000001:1")   |
| `parameter`       | `str`      | Parameter name (e.g., "STATE")           |
| `value`           | `Any`      | The parameter value                      |

**Key:** `DataPointKey` (constructed from fields)

---

## System Variable Events

### SysvarStateChangedEvent

System variable value was updated.

```python
from aiohomematic.central.event_bus import SysvarStateChangedEvent
```

| Field         | Type       | Description                            |
| ------------- | ---------- | -------------------------------------- |
| `timestamp`   | `datetime` | When the event was created             |
| `state_path`  | `str`      | Path/identifier of the system variable |
| `value`       | `Any`      | The new value                          |
| `received_at` | `datetime` | When the value was received            |

**Key:** `state_path`

---

## Device Events

### DeviceStateChangedEvent

Device state has been updated.

```python
from aiohomematic.central.event_bus import DeviceStateChangedEvent
```

| Field            | Type       | Description                |
| ---------------- | ---------- | -------------------------- |
| `timestamp`      | `datetime` | When the event was created |
| `device_address` | `str`      | Address of the device      |

**Key:** `device_address`

### DeviceRemovedEvent

Device or data point has been removed.

```python
from aiohomematic.central.event_bus import DeviceRemovedEvent
```

| Field       | Type       | Description                             |
| ----------- | ---------- | --------------------------------------- |
| `timestamp` | `datetime` | When the event was created              |
| `unique_id` | `str`      | Unique identifier of the removed entity |

**Key:** `unique_id`

### FirmwareStateChangedEvent

Device firmware information has been updated.

```python
from aiohomematic.central.event_bus import FirmwareStateChangedEvent
```

| Field            | Type       | Description                |
| ---------------- | ---------- | -------------------------- |
| `timestamp`      | `datetime` | When the event was created |
| `device_address` | `str`      | Address of the device      |

**Key:** `device_address`

### LinkPeerChangedEvent

Channel link peer addresses have changed.

```python
from aiohomematic.central.event_bus import LinkPeerChangedEvent
```

| Field             | Type       | Description                |
| ----------------- | ---------- | -------------------------- |
| `timestamp`       | `datetime` | When the event was created |
| `channel_address` | `str`      | Address of the channel     |

**Key:** `channel_address`

---

## Connection Events

### ConnectionStageChangedEvent

Connection reconnection stage progression during recovery.

```python
from aiohomematic.central.event_bus import ConnectionStageChangedEvent
from aiohomematic.const import ConnectionStage
```

| Field                           | Type              | Description                 |
| ------------------------------- | ----------------- | --------------------------- |
| `timestamp`                     | `datetime`        | When the event was created  |
| `interface_id`                  | `str`             | Interface identifier        |
| `stage`                         | `ConnectionStage` | Current stage               |
| `previous_stage`                | `ConnectionStage` | Previous stage              |
| `duration_in_previous_stage_ms` | `float`           | Time in previous stage (ms) |

**Key:** `interface_id`

**ConnectionStage values:**

- `LOST` - Connection lost
- `TCP_AVAILABLE` - TCP connection established
- `RPC_AVAILABLE` - RPC calls working
- `WARMUP` - Waiting for stable connection
- `ESTABLISHED` - Fully connected

```python
async def handler(*, event: ConnectionStageChangedEvent) -> None:
    print(f"{event.interface_id}: {event.previous_stage} -> {event.stage}")

unsubscribe = central.event_bus.subscribe(
    event_type=ConnectionStageChangedEvent,
    event_key=None,
    handler=handler,
)
```

### ConnectionHealthChangedEvent

Connection health status update.

```python
from aiohomematic.central.event_bus import ConnectionHealthChangedEvent
```

| Field                     | Type                    | Description                    |
| ------------------------- | ----------------------- | ------------------------------ |
| `timestamp`               | `datetime`              | When the event was created     |
| `interface_id`            | `str`                   | Interface identifier           |
| `is_healthy`              | `bool`                  | Whether connection is healthy  |
| `failure_reason`          | `FailureReason \| None` | Reason for unhealthy state     |
| `consecutive_failures`    | `int`                   | Number of consecutive failures |
| `last_successful_contact` | `datetime \| None`      | Last successful communication  |

**Key:** `interface_id`

---

## Cache Events

### CacheInvalidatedEvent

Cache invalidation notification.

```python
from aiohomematic.central.event_bus import CacheInvalidatedEvent
from aiohomematic.const import CacheType, CacheInvalidationReason
```

| Field              | Type                      | Description                                   |
| ------------------ | ------------------------- | --------------------------------------------- |
| `timestamp`        | `datetime`                | When the event was created                    |
| `cache_type`       | `CacheType`               | Type of cache affected                        |
| `reason`           | `CacheInvalidationReason` | Why cache was invalidated                     |
| `scope`            | `str \| None`             | Scope (device_address, interface_id, or None) |
| `entries_affected` | `int`                     | Number of entries invalidated                 |

**Key:** `scope`

**CacheType values:**

- `DEVICE_DESCRIPTIONS` - Device description cache
- `PARAMSET_DESCRIPTIONS` - Paramset description cache
- `DATA_CACHE` - Runtime data cache

---

## Circuit Breaker Events

### CircuitBreakerStateChangedEvent

Circuit breaker state transition.

```python
from aiohomematic.central.event_bus import CircuitBreakerStateChangedEvent
from aiohomematic.client.circuit_breaker import CircuitState
```

| Field               | Type               | Description                |
| ------------------- | ------------------ | -------------------------- |
| `timestamp`         | `datetime`         | When the event was created |
| `interface_id`      | `str`              | Interface identifier       |
| `old_state`         | `CircuitState`     | Previous state             |
| `new_state`         | `CircuitState`     | New state                  |
| `failure_count`     | `int`              | Current failure count      |
| `success_count`     | `int`              | Current success count      |
| `last_failure_time` | `datetime \| None` | Last failure timestamp     |

**Key:** `interface_id`

**CircuitState values:**

- `CLOSED` - Normal operation (requests allowed)
- `OPEN` - Circuit tripped (requests blocked)
- `HALF_OPEN` - Testing recovery (limited requests)

```python
async def handler(*, event: CircuitBreakerStateChangedEvent) -> None:
    if event.new_state == CircuitState.OPEN:
        print(f"Circuit breaker OPEN for {event.interface_id}")

unsubscribe = central.event_bus.subscribe(
    event_type=CircuitBreakerStateChangedEvent,
    event_key=None,
    handler=handler,
)
```

### CircuitBreakerTrippedEvent

Circuit breaker tripped (opened due to repeated failures).

```python
from aiohomematic.central.event_bus import CircuitBreakerTrippedEvent
```

| Field                 | Type          | Description                         |
| --------------------- | ------------- | ----------------------------------- |
| `timestamp`           | `datetime`    | When the event was created          |
| `interface_id`        | `str`         | Interface identifier                |
| `failure_count`       | `int`         | Number of failures that caused trip |
| `last_failure_reason` | `str \| None` | Reason for last failure             |
| `cooldown_seconds`    | `float`       | Seconds until recovery attempt      |

**Key:** `interface_id`

---

## Health Events

### HealthRecordedEvent

Emitted by CircuitBreaker when a request succeeds or fails, enabling decoupled health tracking.

```python
from aiohomematic.central.event_bus import HealthRecordedEvent
```

| Field          | Type       | Description                        |
| -------------- | ---------- | ---------------------------------- |
| `timestamp`    | `datetime` | When the event was created         |
| `interface_id` | `str`      | Interface identifier               |
| `success`      | `bool`     | Whether the request was successful |

**Key:** `interface_id`

This event is used by `ClientCoordinator` to track health metrics for each interface. It replaces the previous callback-based health recording pattern.

```python
async def handler(*, event: HealthRecordedEvent) -> None:
    status = "success" if event.success else "failure"
    print(f"{event.interface_id}: {status}")

unsubscribe = central.event_bus.subscribe(
    event_type=HealthRecordedEvent,
    event_key=None,
    handler=handler,
)
```

---

## State Machine Events

### ClientStateChangedEvent

Client state machine transition.

```python
from aiohomematic.central.event_bus import ClientStateChangedEvent
```

| Field          | Type          | Description                        |
| -------------- | ------------- | ---------------------------------- |
| `timestamp`    | `datetime`    | When the event was created         |
| `interface_id` | `str`         | Interface identifier               |
| `old_state`    | `str`         | Previous state (ClientState value) |
| `new_state`    | `str`         | New state (ClientState value)      |
| `trigger`      | `str \| None` | What triggered the transition      |

**Key:** `interface_id`

**ClientState values:**

- `INIT` - Initial state
- `CONNECTING` - Establishing connection
- `CONNECTED` - Fully connected
- `RECONNECTING` - Attempting reconnection
- `DISCONNECTED` - Disconnected
- `FAILED` - Permanent failure

### CentralStateChangedEvent

Central unit state machine transition.

```python
from aiohomematic.central.event_bus import CentralStateChangedEvent
```

| Field          | Type          | Description                         |
| -------------- | ------------- | ----------------------------------- |
| `timestamp`    | `datetime`    | When the event was created          |
| `central_name` | `str`         | Name of the central unit            |
| `old_state`    | `str`         | Previous state (CentralState value) |
| `new_state`    | `str`         | New state (CentralState value)      |
| `trigger`      | `str \| None` | What triggered the transition       |

**Key:** `central_name`

**CentralState values:**

- `STARTING` - Starting up
- `INITIALIZING` - Initializing clients
- `RUNNING` - Normal operation
- `DEGRADED` - Some clients unavailable
- `RECOVERING` - Attempting recovery
- `FAILED` - All clients failed
- `STOPPED` - Shut down

```python
async def handler(*, event: CentralStateChangedEvent) -> None:
    if event.new_state == "DEGRADED":
        print(f"Central {event.central_name} is degraded")

unsubscribe = central.event_bus.subscribe(
    event_type=CentralStateChangedEvent,
    event_key=None,
    handler=handler,
)
```

---

## Data Refresh Events

### DataRefreshTriggeredEvent

Data refresh operation triggered.

```python
from aiohomematic.central.event_bus import DataRefreshTriggeredEvent
```

| Field          | Type          | Description                                                   |
| -------------- | ------------- | ------------------------------------------------------------- |
| `timestamp`    | `datetime`    | When the event was created                                    |
| `refresh_type` | `str`         | Type: "client_data", "program", "sysvar", "inbox", "firmware" |
| `interface_id` | `str \| None` | Interface (None for hub-level)                                |
| `scheduled`    | `bool`        | Whether this was a scheduled refresh                          |

**Key:** `interface_id`

### DataRefreshCompletedEvent

Data refresh operation completed.

```python
from aiohomematic.central.event_bus import DataRefreshCompletedEvent
```

| Field             | Type          | Description                    |
| ----------------- | ------------- | ------------------------------ |
| `timestamp`       | `datetime`    | When the event was created     |
| `refresh_type`    | `str`         | Type of refresh                |
| `interface_id`    | `str \| None` | Interface (None for hub-level) |
| `success`         | `bool`        | Whether refresh succeeded      |
| `duration_ms`     | `float`       | Duration in milliseconds       |
| `items_refreshed` | `int`         | Number of items refreshed      |
| `error_message`   | `str \| None` | Error message if failed        |

**Key:** `interface_id`

```python
async def handler(*, event: DataRefreshCompletedEvent) -> None:
    if event.success:
        print(f"Refreshed {event.items_refreshed} items in {event.duration_ms}ms")
    else:
        print(f"Refresh failed: {event.error_message}")

unsubscribe = central.event_bus.subscribe(
    event_type=DataRefreshCompletedEvent,
    event_key=None,
    handler=handler,
)
```

---

## Hub Events

### ProgramExecutedEvent

Backend program was executed.

```python
from aiohomematic.central.event_bus import ProgramExecutedEvent
```

| Field          | Type       | Description                                       |
| -------------- | ---------- | ------------------------------------------------- |
| `timestamp`    | `datetime` | When the event was created                        |
| `program_id`   | `str`      | Program identifier                                |
| `program_name` | `str`      | Program name                                      |
| `triggered_by` | `str`      | Trigger source: "user", "scheduler", "automation" |
| `success`      | `bool`     | Whether execution succeeded                       |

**Key:** `program_id`

---

## Optimization Events

### RequestCoalescedEvent

Multiple requests were coalesced into one.

```python
from aiohomematic.central.event_bus import RequestCoalescedEvent
```

| Field             | Type       | Description                      |
| ----------------- | ---------- | -------------------------------- |
| `timestamp`       | `datetime` | When the event was created       |
| `request_key`     | `str`      | Key identifying the request type |
| `coalesced_count` | `int`      | Number of requests merged        |
| `interface_id`    | `str`      | Interface identifier             |

**Key:** `interface_id`

---

## Integration Events

These events are defined in `aiohomematic/central/integration_events.py` and are designed for Home Assistant and other consumers.

### SystemStatusChangedEvent

Aggregated system status changes for integration consumers.

```python
from aiohomematic.central.integration_events import SystemStatusChangedEvent
from aiohomematic.const import CentralState, FailureReason
```

| Field                  | Type                                           | Description                   |
| ---------------------- | ---------------------------------------------- | ----------------------------- |
| `timestamp`            | `datetime`                                     | When the event was created    |
| `central_state`        | `CentralState \| None`                         | Central state change          |
| `failure_reason`       | `FailureReason \| None`                        | Failure reason (when FAILED)  |
| `failure_interface_id` | `str \| None`                                  | Interface that caused failure |
| `degraded_interfaces`  | `Mapping[str, FailureReason] \| None`          | Degraded interfaces           |
| `connection_state`     | `tuple[str, bool] \| None`                     | Connection change             |
| `client_state`         | `tuple[str, ClientState, ClientState] \| None` | Client state change           |
| `callback_state`       | `tuple[str, bool] \| None`                     | Callback server state         |
| `issues`               | `tuple[IntegrationIssue, ...]`                 | Issues for user display       |

**Key:** `None` (global event)

```python
async def handler(*, event: SystemStatusChangedEvent) -> None:
    if event.central_state == CentralState.FAILED:
        if event.failure_reason == FailureReason.AUTH:
            print("Authentication failed!")
    elif event.central_state == CentralState.DEGRADED:
        for iface_id, reason in (event.degraded_interfaces or {}).items():
            print(f"Interface {iface_id} degraded: {reason}")

unsubscribe = central.event_bus.subscribe(
    event_type=SystemStatusChangedEvent,
    event_key=None,
    handler=handler,
)
```

### DeviceLifecycleEvent

Device lifecycle events (created, removed, availability).

```python
from aiohomematic.central.integration_events import (
    DeviceLifecycleEvent,
    DeviceLifecycleEventType,
)
```

| Field                      | Type                           | Description                      |
| -------------------------- | ------------------------------ | -------------------------------- |
| `timestamp`                | `datetime`                     | When the event was created       |
| `event_type`               | `DeviceLifecycleEventType`     | Type of lifecycle event          |
| `device_addresses`         | `tuple[str, ...]`              | Affected device addresses        |
| `availability_changes`     | `tuple[tuple[str, bool], ...]` | Availability changes             |
| `includes_virtual_remotes` | `bool`                         | Whether virtual remotes included |

**Key:** `None` (global event)

**DeviceLifecycleEventType values:**

- `CREATED` - Device created
- `UPDATED` - Device updated
- `REMOVED` - Device removed
- `AVAILABILITY_CHANGED` - Device availability changed

```python
async def handler(*, event: DeviceLifecycleEvent) -> None:
    if event.event_type == DeviceLifecycleEventType.CREATED:
        for address in event.device_addresses:
            print(f"New device: {address}")
    elif event.event_type == DeviceLifecycleEventType.AVAILABILITY_CHANGED:
        for address, available in event.availability_changes:
            print(f"{address}: {'available' if available else 'unavailable'}")

unsubscribe = central.event_bus.subscribe(
    event_type=DeviceLifecycleEvent,
    event_key=None,
    handler=handler,
)
```

### DataPointsCreatedEvent

New data points created event.

```python
from aiohomematic.central.integration_events import DataPointsCreatedEvent
from aiohomematic.const import DataPointCategory
```

| Field             | Type                                | Description                |
| ----------------- | ----------------------------------- | -------------------------- |
| `timestamp`       | `datetime`                          | When the event was created |
| `new_data_points` | `Mapping[DataPointCategory, tuple]` | Data points by category    |

**Key:** `None` (global event)

### DeviceTriggerEvent

Device trigger events (button press, motion, etc.).

```python
from aiohomematic.central.integration_events import DeviceTriggerEvent
from aiohomematic.const import DeviceTriggerEventType
```

| Field            | Type                     | Description                |
| ---------------- | ------------------------ | -------------------------- |
| `timestamp`      | `datetime`               | When the event was created |
| `trigger_type`   | `DeviceTriggerEventType` | Type of trigger            |
| `model`          | `str`                    | Device model               |
| `interface_id`   | `str`                    | Interface identifier       |
| `device_address` | `str`                    | Device address             |
| `channel_no`     | `int \| None`            | Channel number             |
| `parameter`      | `str`                    | Parameter name             |
| `value`          | `Any`                    | Trigger value              |

**Key:** `None` (global event)

**DeviceTriggerEventType values:**

- `KEYPRESS` - Button press
- `KEYPRESS_LONG_START` - Long press started
- `IMPULSE` - Impulse trigger

```python
async def handler(*, event: DeviceTriggerEvent) -> None:
    if event.trigger_type == DeviceTriggerEventType.KEYPRESS:
        print(f"Button {event.parameter} pressed on {event.device_address}")

unsubscribe = central.event_bus.subscribe(
    event_type=DeviceTriggerEvent,
    event_key=None,
    handler=handler,
)
```

---

## Subscription Methods on Model Classes

Model classes provide convenience subscription methods:

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
from aiohomematic.central.event_bus import EventBus, DataPointValueReceivedEvent

# Subscribe to all events of a type
unsubscribe = event_bus.subscribe(
    event_type=DataPointValueReceivedEvent,
    event_key=None,
    handler=my_handler,
)

# Subscribe to events with a specific key
unsubscribe = event_bus.subscribe(
    event_type=DataPointValueReceivedEvent,
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
    event_type=DataPointValueReceivedEvent,
    event_key=None,
    handler=my_critical_handler,
    priority=EventPriority.HIGH,
)
```

| Priority   | Value | Use Case                           |
| ---------- | ----- | ---------------------------------- |
| `CRITICAL` | 200   | Logging, metrics (runs first)      |
| `HIGH`     | 100   | Important handlers                 |
| `NORMAL`   | 50    | Default for most handlers          |
| `LOW`      | 0     | Cleanup, notifications (runs last) |

### Batch Publishing

```python
from aiohomematic.central.event_bus import EventBatch

async with EventBatch(bus=event_bus) as batch:
    batch.add(event=event1)
    batch.add(event=event2)
    batch.add(event=event3)
    # All events published when context exits
```

---

## Testing with Events

Use `EventCapture` for behavior-focused testing:

```python
from aiohomematic_test_support.event_capture import EventCapture

capture = EventCapture()
capture.subscribe_to(event_bus, CircuitBreakerTrippedEvent)

# ... perform test actions ...

capture.assert_event_emitted(
    event_type=CircuitBreakerTrippedEvent,
    failure_count=5,
)
capture.cleanup()
```

See [Testing with Events](testing_with_events.md) for complete testing guide.

---

## Best Practices

### 1. Use Specific Event Types

```python
# Good - type-safe, IDE autocomplete works
async def handler(*, event: DataPointValueReceivedEvent) -> None:
    print(event.dpk, event.value)

# Bad - loses type information
async def handler(*, event: Event) -> None:
    print(event.timestamp)  # Only base fields available
```

### 2. Keep Handlers Lightweight

```python
# Good - quick handler, offloads heavy work
async def handler(*, event: DataPointValueReceivedEvent) -> None:
    asyncio.create_task(process_update(event))

# Avoid - blocks other handlers
async def handler(*, event: DataPointValueReceivedEvent) -> None:
    await slow_database_operation(event)  # Blocks for seconds
```

### 3. Always Unsubscribe

```python
class MyIntegration:
    def __init__(self, event_bus: EventBus) -> None:
        self._unsubscribe = event_bus.subscribe(
            event_type=DataPointValueReceivedEvent,
            event_key=None,
            handler=self._handler,
        )

    def cleanup(self) -> None:
        self._unsubscribe()
```

### 4. Handle Errors Gracefully

The EventBus isolates handler errors - one failing handler won't affect others:

```python
async def handler(*, event: DataPointValueReceivedEvent) -> None:
    try:
        await process(event)
    except ExpectedError:
        _LOGGER.warning("Could not process event: %s", event.dpk)
```

---

## Related Documentation

- [EventBus Architecture](event_bus.md) - Internal architecture and design decisions
- [Event-Driven Metrics](event_driven_metrics.md) - Metrics collected via events
- [Testing with Events](testing_with_events.md) - Event-based testing guide
- [Architecture Overview](architecture.md) - Overall system architecture
- [Data Flow](data_flow.md) - How data flows through the system
