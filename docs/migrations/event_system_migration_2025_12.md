# Event System Migration Guide

This guide covers migrating from legacy `InterfaceEvent` types to modern EventBus events in Home Assistant integration.

## Overview

aiohomematic has transitioned from legacy `HomematicEvent` with `InterfaceEventType` to typed EventBus events. This provides:

- Type-safe event handling
- Better IDE support
- Cleaner separation of concerns
- Improved testability

## Status

**As of 2025-12-26:**

The legacy `InterfaceEvent` system has been **completely removed**. All interface events now use typed EventBus events:

| Removed Legacy Event              | Modern Replacement               |
| --------------------------------- | -------------------------------- |
| `InterfaceEventType.CALLBACK`     | `CallbackStateChangedEvent`      |
| `InterfaceEventType.PROXY`        | `ClientStateChangedEvent`        |
| `InterfaceEventType.FETCH_DATA`   | `FetchDataFailedEvent`           |
| `InterfaceEventType.PENDING_PONG` | `PingPongMismatchEvent`          |
| `InterfaceEventType.UNKNOWN_PONG` | `PingPongMismatchEvent`          |
| N/A                               | `DeviceAvailabilityChangedEvent` |

The following have been removed:

- `InterfaceEvent` dataclass
- `InterfaceEventType` enum
- `publish_interface_event()` method on CentralUnit

## Migration Steps

### 1. CallbackStateChangedEvent (replaces InterfaceEventType.CALLBACK)

**Before (Legacy):**

```python
from aiohomematic.const import EventKey, DeviceTriggerEventType, InterfaceEventType


def _async_on_homematic_event(
        event_type: DeviceTriggerEventType,
        event_data: dict[EventKey, Any],
) -> None:
    if event_type != DeviceTriggerEventType.INTERFACE:
        return

    data = event_data.get(EventKey.DATA, {})
    iface_type = event_data.get(EventKey.TYPE)

    if iface_type == InterfaceEventType.CALLBACK:
        interface_id = event_data.get(EventKey.INTERFACE_ID)
        available = data.get(EventKey.AVAILABLE, True)
        seconds = data.get(EventKey.SECONDS_SINCE_LAST_EVENT)

        if not available:
            _LOGGER.warning(
                "No events from %s for %s seconds",
                interface_id,
                seconds,
            )


# Registration
central.register_homematic_callback(callback=_async_on_homematic_event)
```

**After (Modern):**

```python
from aiohomematic.central.event_bus import CallbackStateChangedEvent

async def _on_callback_state_changed(*, event: CallbackStateChangedEvent) -> None:
    if not event.alive:
        _LOGGER.warning(
            "No events from %s for %s seconds",
            event.interface_id,
            event.seconds_since_last_event,
        )

# Registration
unsubscribe = central.event_bus.subscribe(
    event_type=CallbackStateChangedEvent,
    event_key=None,  # All interfaces, or specific interface_id
    handler=_on_callback_state_changed,
)

# Cleanup (on unload)
unsubscribe()
```

### 2. ClientStateChangedEvent (replaces InterfaceEventType.PROXY)

**Before (Legacy):**

```python
def _async_on_homematic_event(
    event_type: EventType,
    event_data: dict[EventKey, Any],
) -> None:
    if event_type != EventType.INTERFACE:
        return

    data = event_data.get(EventKey.DATA, {})
    iface_type = event_data.get(EventKey.TYPE)

    if iface_type == InterfaceEventType.PROXY:
        interface_id = event_data.get(EventKey.INTERFACE_ID)
        available = data.get(EventKey.AVAILABLE, True)

        # Update entity availability
        for entity in get_entities_for_interface(interface_id):
            entity.set_available(available)
```

**After (Modern):**

```python
from aiohomematic.central.event_bus import ClientStateChangedEvent
from aiohomematic.const import ClientState

async def _on_client_state_changed(*, event: ClientStateChangedEvent) -> None:
    available = event.new_state == ClientState.CONNECTED

    # Update entity availability
    for entity in get_entities_for_interface(event.interface_id):
        entity.set_available(available)

# Registration
unsubscribe = central.event_bus.subscribe(
    event_type=ClientStateChangedEvent,
    event_key=None,
    handler=_on_client_state_changed,
)
```

### 3. CentralStateChangedEvent (new)

Monitor overall system state:

```python
from aiohomematic.central.event_bus import CentralStateChangedEvent
from aiohomematic.const import CentralState

async def _on_central_state_changed(*, event: CentralStateChangedEvent) -> None:
    _LOGGER.info(
        "Central state: %s -> %s (%s)",
        event.old_state,
        event.new_state,
        event.reason,
    )

    if event.new_state == CentralState.RUNNING:
        # System fully operational
        pass
    elif event.new_state == CentralState.RECOVERING:
        # System recovering from connection loss
        pass
    elif event.new_state == CentralState.FAILED:
        # System failed
        pass

unsubscribe = central.event_bus.subscribe(
    event_type=CentralStateChangedEvent,
    event_key=None,
    handler=_on_central_state_changed,
)
```

### 4. FetchDataFailedEvent (replaces InterfaceEventType.FETCH_DATA)

**Before (Legacy):**

```python
def _async_on_homematic_event(
    event_type: EventType,
    event_data: dict[EventKey, Any],
) -> None:
    if event_type != EventType.INTERFACE:
        return

    data = event_data.get(EventKey.DATA, {})
    iface_type = event_data.get(EventKey.TYPE)

    if iface_type == InterfaceEventType.FETCH_DATA:
        interface_id = event_data.get(EventKey.INTERFACE_ID)
        available = data.get(EventKey.AVAILABLE, True)

        if not available:
            _LOGGER.warning("Data fetch failed for %s", interface_id)
```

**After (Modern):**

```python
from aiohomematic.central.event_bus import FetchDataFailedEvent

async def _on_fetch_data_failed(*, event: FetchDataFailedEvent) -> None:
    _LOGGER.warning("Data fetch failed for %s", event.interface_id)

# Registration
unsubscribe = central.event_bus.subscribe(
    event_type=FetchDataFailedEvent,
    event_key=None,
    handler=_on_fetch_data_failed,
)
```

### 5. PingPongMismatchEvent (replaces PENDING_PONG and UNKNOWN_PONG)

The `PENDING_PONG` and `UNKNOWN_PONG` events have been unified into a single `PingPongMismatchEvent` with a `mismatch_type` field.

**Before (Legacy):**

```python
def _async_on_homematic_event(
    event_type: EventType,
    event_data: dict[EventKey, Any],
) -> None:
    if event_type != EventType.INTERFACE:
        return

    data = event_data.get(EventKey.DATA, {})
    iface_type = event_data.get(EventKey.TYPE)

    if iface_type == InterfaceEventType.PENDING_PONG:
        interface_id = event_data.get(EventKey.INTERFACE_ID)
        mismatch_count = data.get(EventKey.MISMATCH_COUNT, 0)
        _LOGGER.warning(
            "Pending PONG mismatch on %s: %d", interface_id, mismatch_count
        )
    elif iface_type == InterfaceEventType.UNKNOWN_PONG:
        interface_id = event_data.get(EventKey.INTERFACE_ID)
        mismatch_count = data.get(EventKey.MISMATCH_COUNT, 0)
        _LOGGER.warning(
            "Unknown PONG on %s: %d", interface_id, mismatch_count
        )
```

**After (Modern):**

```python
from aiohomematic.central.event_bus import PingPongMismatchEvent
from aiohomematic.const import PingPongMismatchType

async def _on_pingpong_mismatch(*, event: PingPongMismatchEvent) -> None:
    if event.mismatch_type == PingPongMismatchType.PENDING:
        _LOGGER.warning(
            "Pending PONG mismatch on %s: %d",
            event.interface_id,
            event.mismatch_count,
        )
    elif event.mismatch_type == PingPongMismatchType.UNKNOWN:
        _LOGGER.warning(
            "Unknown PONG on %s: %d",
            event.interface_id,
            event.mismatch_count,
        )

# Registration
unsubscribe = central.event_bus.subscribe(
    event_type=PingPongMismatchEvent,
    event_key=None,
    handler=_on_pingpong_mismatch,
)
```

**Event Fields:**

| Field            | Type                   | Description                                |
| ---------------- | ---------------------- | ------------------------------------------ |
| `timestamp`      | `datetime`             | When the event was created                 |
| `interface_id`   | `str`                  | Interface identifier                       |
| `mismatch_type`  | `PingPongMismatchType` | `PENDING` or `UNKNOWN`                     |
| `mismatch_count` | `int`                  | Current count of mismatched PINGs/PONGs    |
| `acceptable`     | `bool`                 | Whether mismatch count is within threshold |

### 6. DeviceAvailabilityChangedEvent (new)

This is a new event that is published when device availability changes (UN_REACH or STICKY_UN_REACH parameter changes).

**Usage:**

```python
from aiohomematic.central.event_bus import DeviceAvailabilityChangedEvent

async def _on_device_availability_changed(
    *, event: DeviceAvailabilityChangedEvent
) -> None:
    if event.available:
        _LOGGER.info("Device %s is now available", event.device_address)
    else:
        _LOGGER.warning("Device %s is now unavailable", event.device_address)

# Registration
unsubscribe = central.event_bus.subscribe(
    event_type=DeviceAvailabilityChangedEvent,
    event_key=None,  # All devices, or specific device_address
    handler=_on_device_availability_changed,
)
```

**Event Fields:**

| Field             | Type       | Description                             |
| ----------------- | ---------- | --------------------------------------- |
| `timestamp`       | `datetime` | When the event was created              |
| `device_address`  | `str`      | Device address (e.g., "VCU0000001")     |
| `channel_address` | `str`      | Channel address (e.g., "VCU0000001:0")  |
| `parameter`       | `str`      | Parameter that changed (UN_REACH, etc.) |
| `available`       | `bool`     | Whether the device is available         |

## Event Mapping Reference

| Legacy Event                      | Modern Event                     | Key Differences                                   |
| --------------------------------- | -------------------------------- | ------------------------------------------------- |
| `InterfaceEventType.CALLBACK`     | `CallbackStateChangedEvent`      | Type-safe, `alive` instead of `AVAILABLE`         |
| `InterfaceEventType.PROXY`        | `ClientStateChangedEvent`        | Provides state transitions, not just availability |
| `InterfaceEventType.FETCH_DATA`   | `FetchDataFailedEvent`           | Type-safe, no `AVAILABLE` wrapper                 |
| `InterfaceEventType.PENDING_PONG` | `PingPongMismatchEvent`          | Unified with `mismatch_type=PENDING`              |
| `InterfaceEventType.UNKNOWN_PONG` | `PingPongMismatchEvent`          | Unified with `mismatch_type=UNKNOWN`              |
| N/A                               | `CentralStateChangedEvent`       | New - overall system state                        |
| N/A                               | `ConnectionStateChangedEvent`    | New - connection issue tracking                   |
| N/A                               | `DeviceAvailabilityChangedEvent` | New - device availability (UN_REACH)              |

## Subscribing to Multiple Events

```python
from aiohomematic.central.event_bus import (
    CallbackStateChangedEvent,
    ClientStateChangedEvent,
    CentralStateChangedEvent,
    DeviceAvailabilityChangedEvent,
    FetchDataFailedEvent,
    PingPongMismatchEvent,
)

class HMIPLocalCoordinator:
    def __init__(self, central: CentralUnit) -> None:
        self._central = central
        self._unsubscribes: list[Callable[[], None]] = []

    async def async_setup(self) -> None:
        """Set up event subscriptions."""
        self._unsubscribes.extend([
            self._central.event_bus.subscribe(
                event_type=CallbackStateChangedEvent,
                event_key=None,
                handler=self._on_callback_state,
            ),
            self._central.event_bus.subscribe(
                event_type=ClientStateChangedEvent,
                event_key=None,
                handler=self._on_client_state,
            ),
            self._central.event_bus.subscribe(
                event_type=CentralStateChangedEvent,
                event_key=None,
                handler=self._on_central_state,
            ),
        ])

    async def async_unload(self) -> None:
        """Clean up subscriptions."""
        for unsubscribe in self._unsubscribes:
            unsubscribe()
        self._unsubscribes.clear()

    async def _on_callback_state(self, *, event: CallbackStateChangedEvent) -> None:
        """Handle callback state changes."""
        ...

    async def _on_client_state(self, *, event: ClientStateChangedEvent) -> None:
        """Handle client state changes."""
        ...

    async def _on_central_state(self, *, event: CentralStateChangedEvent) -> None:
        """Handle central state changes."""
        ...
```

## Filtering by Interface

Subscribe to events from a specific interface:

```python
# Subscribe only to events from HmIP-RF interface
unsubscribe = central.event_bus.subscribe(
    event_type=ClientStateChangedEvent,
    event_key="HmIP-RF",  # Filter by interface_id
    handler=handler,
)
```

## Handler Priority

For critical handlers that must run first:

```python
from aiohomematic.central.event_bus import EventPriority

unsubscribe = central.event_bus.subscribe(
    event_type=ClientStateChangedEvent,
    event_key=None,
    handler=critical_handler,
    priority=EventPriority.HIGH,
)
```

## Testing

Test handlers with mock events:

```python
import pytest
from datetime import datetime
from aiohomematic.central.event_bus import CallbackStateChangedEvent

@pytest.mark.asyncio
async def test_callback_state_handler():
    received = []

    async def handler(*, event: CallbackStateChangedEvent) -> None:
        received.append(event)

    # Create test event
    event = CallbackStateChangedEvent(
        timestamp=datetime.now(),
        interface_id="HmIP-RF",
        alive=False,
        seconds_since_last_event=120,
    )

    # Call handler
    await handler(event=event)

    assert len(received) == 1
    assert received[0].alive is False
    assert received[0].seconds_since_last_event == 120
```

## Related Documentation

- [Event Reference](../event_reference.md) - Complete event type documentation
- [EventBus Architecture](../event_bus.md) - Internal design
- [ADR-0009](../adr/0009-interface-event-consolidation.md) - Decision record
