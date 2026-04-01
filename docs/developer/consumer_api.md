# Consumer API Guide

This guide explains how to use aiohomematic from external applications like Home Assistant integrations, Matter bridges, or custom automation tools.

## API Layers Overview

aiohomematic provides three API layers for different use cases:

```
┌─────────────────────────────────────────────────────┐
│  Layer 1: HomematicAPI Facade (Simplest)           │
│  - Quick start for basic operations                │
│  - Context manager support                         │
└─────────────────────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────┐
│  Layer 2: CentralConfig + CentralUnit (Full Control)│
│  - Complete lifecycle management                    │
│  - Multi-interface support                         │
│  - Event system access                             │
└─────────────────────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────┐
│  Layer 3: Protocol Interfaces (Dependency Injection)│
│  - Minimal coupling                                │
│  - Testable components                             │
│  - Fine-grained dependencies                       │
└─────────────────────────────────────────────────────┘
```

---

## Layer 1: HomematicAPI Facade

The simplest way to interact with aiohomematic. Best for quick scripts and simple integrations.

```python
from aiohomematic.api import HomematicAPI

async def main():
    async with HomematicAPI.connect(
        host="192.168.1.100",
        username="Admin",
        password="secret",
    ) as api:
        # List all devices
        devices = api.list_devices()
        for device in devices:
            print(f"{device.name}: {device.model}")

        # Read a value
        value = await api.read_value(
            channel_address="VCU0000001:1",
            parameter="STATE",
        )

        # Write a value
        await api.write_value(
            channel_address="VCU0000001:1",
            parameter="STATE",
            value=True,
        )

        # Subscribe to updates
        def on_update(event):
            print(f"Update: {event}")

        api.subscribe_to_updates(callback=on_update)
```

---

## Layer 2: CentralConfig + CentralUnit

For applications needing full control over lifecycle, multiple interfaces, and the event system.

### Basic Setup

```python
from aiohomematic.central import CentralConfig
from aiohomematic.client import InterfaceConfig
from aiohomematic.const import Interface

# Create configuration
config = CentralConfig(
    name="my-central",
    host="192.168.1.100",
    username="admin",
    password="secret",
    central_id="unique-id-123",
    interface_configs={
        InterfaceConfig(
            central_name="my-central",
            interface=Interface.HMIP_RF,
            port=2010,
        ),
        InterfaceConfig(
            central_name="my-central",
            interface=Interface.BIDCOS_RF,
            port=2001,
        ),
    },
)

# Create and start
central = config.create_central()
await central.start()

try:
    # Work with devices
    for device in central.devices.values():
        print(f"{device.address}: {device.name}")
finally:
    await central.stop()
```

### Simplified Setup Methods

```python
# For CCU3/CCU2
config = CentralConfig.for_ccu(
    name="ccu",
    host="192.168.1.100",
    username="admin",
    password="secret",
)

# For Homegear
config = CentralConfig.for_homegear(
    name="homegear",
    host="192.168.1.100",
    username="admin",
    password="secret",
)
```

### Accessing Devices and Data Points

```python
# Get device by address
device = api.get_device(address="VCU0000001")

# Get channel
channel = device.get_channel(channel_address="VCU0000001:1")

# Get data points
for dp in channel.get_data_points():
    print(f"{dp.name}: {dp.value}")

# Get specific data point
state_dp = channel.get_generic_data_point(parameter="STATE")
if state_dp:
    print(f"Current state: {state_dp.value}")
    await state_dp.send_value(value=True)
```

---

## Event System

aiohomematic uses an EventBus for all event communication.

### Subscribing to Events

```python
from aiohomematic.central.events import (
    DataPointStateChangedEvent,
    DataPointValueReceivedEvent,
    DeviceLifecycleEvent,
    DeviceLifecycleEventType,
)

# Subscribe to value changes (external consumer pattern)
async def on_state_changed(event: DataPointStateChangedEvent) -> None:
    print(f"Data point {event.unique_id} changed")
    print(f"  Old value: {event.old_value}")
    print(f"  New value: {event.new_value}")

unsubscribe = central.event_bus.subscribe(
    event_type=DataPointStateChangedEvent,
    handler=on_state_changed,
)

# Later: unsubscribe
unsubscribe()

# Subscribe to device lifecycle events
async def on_device_lifecycle(event: DeviceLifecycleEvent) -> None:
    if event.event_type == DeviceLifecycleEventType.CREATED:
        print(f"New devices: {event.device_addresses}")
    elif event.event_type == DeviceLifecycleEventType.AVAILABILITY_CHANGED:
        print(f"Availability changed: {event.device_addresses}")

central.event_bus.subscribe(
    event_type=DeviceLifecycleEvent,
    handler=on_device_lifecycle,
)
```

### Data Point Subscription Pattern

For subscribing to specific data point updates, use the EventBus with an event key:

```python
from aiohomematic.central.events import DataPointStateChangedEvent

# Subscribe to a specific data point's state changes
async def on_dp_changed(*, event: DataPointStateChangedEvent) -> None:
    print(f"Data point {event.unique_id} changed: {event.old_value} -> {event.new_value}")

unsubscribe = central.event_bus.subscribe(
    event_type=DataPointStateChangedEvent,
    event_key=data_point.unique_id,
    handler=on_dp_changed,
)

# Later: unsubscribe
unsubscribe()
```

To track entity registration with Home Assistant, use `register()` / `unregister()` on data points instead of the removed `custom_id` property.

### SubscriptionGroup Pattern

When a consumer manages many subscriptions (e.g., a bridge or integration), tracking individual unsubscribe callbacks becomes error-prone. `SubscriptionGroup` collects subscriptions and provides a single `unsubscribe_all()` call for cleanup.

```python
from aiohomematic.central.events import (
    DataPointStateChangedEvent,
    DeviceLifecycleEvent,
    DeviceRemovedEvent,
)

# Create a named group via the EventBus factory
group = central.event_bus.create_subscription_group(name="my-bridge")

# Subscribe to a specific data point's state changes
group.subscribe(
    event_type=DataPointStateChangedEvent,
    event_key=data_point.unique_id,
    handler=on_dp_update,
)

# Subscribe to removal of a specific device
group.subscribe(
    event_type=DeviceRemovedEvent,
    event_key=data_point.unique_id,
    handler=on_removed,
)

# Subscribe to all device lifecycle events (event_key=None)
group.subscribe(
    event_type=DeviceLifecycleEvent,
    event_key=None,  # all devices
    handler=on_lifecycle,
)

# Check how many subscriptions are tracked
print(group.subscription_count)  # 3

# Cleanup: unsubscribe all at once
group.unsubscribe_all()
```

Each `group.subscribe()` call also returns an individual `UnsubscribeCallback`, so you can remove a single subscription early if needed. The `event_key` parameter scopes the handler to a specific entity; pass `None` to receive all events of that type.

---

## Data Point Registration

Data points support a `register()` / `unregister()` lifecycle to indicate that an external consumer (e.g., a Home Assistant entity) is actively using them. This controls the `is_registered` property, which query methods can filter on.

```python
# Claim data point for your integration
data_point.register()
assert data_point.is_registered is True

# Release when entity is removed
data_point.unregister()
assert data_point.is_registered is False
```

Registration has no effect on event delivery or value updates -- it is purely a bookkeeping mechanism. Use it to track which data points have corresponding entities in your integration and to filter queries with the `registered` parameter:

```python
# Get only registered data points
registered_dps = central.query_facade.get_data_points(registered=True)
```

---

## Type-Safe Data Point Queries

`get_data_points_by_type()` returns data points filtered by their concrete class with a precise return type, eliminating the need for manual `isinstance()` checks or casts.

```python
from aiohomematic.model.generic.data_point import GenericDataPoint

# Get only generic data points -- the return type is tuple[GenericDataPoint, ...]
for dp in central.query_facade.get_data_points_by_type(
    data_point_class=GenericDataPoint,
):
    print(dp.unique_id, dp.value)
```

Optional filters narrow the results further:

```python
from aiohomematic.const import DataPointCategory, Interface

# Generic data points on HmIP-RF, registered only
dps = central.query_facade.get_data_points_by_type(
    data_point_class=GenericDataPoint,
    category=DataPointCategory.SENSOR,
    interface=Interface.HMIP_RF,
    registered=True,
)
```

This method is the recommended alternative to `get_data_points()` followed by `isinstance()` filtering.

---

## Event Tiers

The event system distinguishes between public and internal events:

- **Public events** are listed in `__all__` of `aiohomematic.central.events`. They form the stable API that external consumers (integrations, bridges) can safely depend on. Examples: `DataPointStateChangedEvent`, `DeviceLifecycleEvent`, `SystemStatusChangedEvent`.

- **Internal events** live in `aiohomematic.central.events.internal` and are used for coordinator-to-coordinator communication within aiohomematic itself. They are re-exported from the events package for backward compatibility, but they are **not** part of the stable public API. External consumers should not subscribe to them -- their signatures and semantics may change without notice.

When writing a new integration, import only from `aiohomematic.central.events` and check `__all__` to confirm an event is public before depending on it.

---

## Command Throttling

All commands sent through `InterfaceClient` are automatically throttled by `CommandThrottle` to protect the RF duty cycle of the Homematic wireless bus. The throttle uses three priority levels:

```python
from aiohomematic.client.command_throttle import CommandPriority

# CRITICAL (priority 0) -- security and access control commands.
#   Bypasses the throttle queue entirely for immediate execution.

# HIGH (priority 1) -- interactive user commands.
#   Queued and dispatched respecting the configured throttle interval.

# LOW (priority 2) -- bulk operations and automations.
#   Queued behind HIGH commands; dispatched when capacity allows.
```

Consumers do not need to interact with the throttle directly. Priority is determined automatically based on the command context (e.g., lock/unlock commands use `CRITICAL`). The throttle also tracks burst activity and downgrades commands when the burst threshold is exceeded within the configured time window.

---

## Availability Information

aiohomematic provides bundled availability information through `AvailabilityInfo`.

### Using AvailabilityInfo

```python
from aiohomematic.model import AvailabilityInfo

# Get availability for a device
device = api.get_device(address="VCU0000001")
availability = device.availability

# Check reachability
if not availability.is_reachable:
    print(f"Device unreachable!")

# Check battery
if availability.has_battery:
    if availability.low_battery:
        print(f"Low battery! Level: {availability.battery_level}%")
    elif availability.battery_level is not None:
        print(f"Battery: {availability.battery_level}%")

# Check signal strength
if availability.has_signal_info:
    print(f"Signal strength: {availability.signal_strength} dBm")

# Last update time
if availability.last_updated:
    print(f"Last seen: {availability.last_updated}")
```

### AvailabilityInfo Fields

| Field             | Type               | Description                              |
| ----------------- | ------------------ | ---------------------------------------- |
| `is_reachable`    | `bool`             | Device is reachable (inverse of UNREACH) |
| `last_updated`    | `datetime \| None` | Most recent data point modification      |
| `battery_level`   | `int \| None`      | Battery percentage (0-100)               |
| `low_battery`     | `bool \| None`     | LOW_BAT indicator                        |
| `signal_strength` | `int \| None`      | RSSI in dBm (negative values)            |

### Helper Properties

```python
# Check if battery info is available
if availability.has_battery:
    # Either battery_level or low_battery is set
    ...

# Check if signal info is available
if availability.has_signal_info:
    # signal_strength is set
    ...
```

---

## Layer 3: Protocol Interfaces

For advanced use cases requiring minimal coupling and maximum testability.

### Key Protocols

```python
from aiohomematic.interfaces import (
    # Central access
    CentralInfoProtocol,
    ConfigProviderProtocol,
    EventBusProviderProtocol,

    # Device access
    DeviceProtocol,
    DeviceProviderProtocol,
    ChannelProtocol,

    # Data point access
    GenericDataPointProtocol,
    CustomDataPointProtocol,
    DataPointProviderProtocol,
)
```

### Example: Protocol-Based Component

```python
from aiohomematic.interfaces import (
    CentralInfoProtocol,
    DeviceProviderProtocol,
    EventBusProviderProtocol,
)

class MyComponent:
    """Component that only depends on what it needs."""

    def __init__(
        self,
        *,
        central_info: CentralInfoProtocol,
        device_provider: DeviceProviderProtocol,
        event_bus_provider: EventBusProviderProtocol,
    ) -> None:
        self._central_info = central_info
        self._device_provider = device_provider
        self._event_bus = event_bus_provider.event_bus

    def list_devices(self) -> list[str]:
        """List all device addresses."""
        return list(self._device_provider.devices.keys())

# CentralUnit implements all protocols
component = MyComponent(
    central_info=central,
    device_provider=central,
    event_bus_provider=central,
)
```

---

## Common Patterns

### Device Discovery

```python
# Wait for devices to be discovered
await central.start()

# Devices are available after start
for address, device in central.devices.items():
    print(f"Found: {device.name} ({device.model})")

    # Check device type via custom data points
    for cdp in device.custom_data_points:
        print(f"  Custom: {type(cdp).__name__}")
```

### Reading and Writing Values

```python
# Read current value
value = data_point.value

# Send new value
await data_point.send_value(value=True)

# Read from backend (bypass cache)
value = await data_point.get_value()
```

### Handling Value Changes with Old/New Values

```python
from aiohomematic.central.events import DataPointStateChangedEvent

async def on_change(event: DataPointStateChangedEvent) -> None:
    # Access old and new values
    if event.old_value != event.new_value:
        print(f"Changed from {event.old_value} to {event.new_value}")

    # Values may be None during initial load
    if event.old_value is None:
        print("Initial value received")

central.event_bus.subscribe(
    event_type=DataPointStateChangedEvent,
    handler=on_change,
)
```

### Custom Data Point Types

```python
from aiohomematic.model.custom import (
    CustomDpSwitch,
    CustomDpDimmer,
    CustomDpIpThermostat,
    CustomDpCover,
    CustomDpGarage,
)

# Check if device has specific functionality
for cdp in device.custom_data_points:
    if isinstance(cdp, CustomDpDimmer):
        # Dimmer-specific operations
        await cdp.turn_on(brightness=128)

    elif isinstance(cdp, CustomDpIpThermostat):
        # Climate-specific operations
        await cdp.set_temperature(temperature=21.5)

    elif isinstance(cdp, (CustomDpCover, CustomDpGarage)):
        # Use capabilities instead of isinstance() for feature detection
        if cdp.capabilities.tilt:
            await cdp.set_position(position=80, tilt_position=50)
        else:
            await cdp.set_position(position=80)

        if cdp.capabilities.vent:
            await cdp.vent()  # Garage door ventilation
```

---

## Error Handling

```python
from aiohomematic.exceptions import (
    AioHomematicException,  # Base exception
    ClientException,        # Communication errors
    NoConnectionException,  # Connection lost
    ValidationException,    # Invalid input
)

try:
    await data_point.send_value(value=True)
except NoConnectionException:
    print("Lost connection to backend")
except ClientException as e:
    print(f"Communication error: {e}")
except AioHomematicException as e:
    print(f"General error: {e}")
```

---

## Best Practices

1. **Use context managers** when possible for automatic cleanup
2. **Subscribe to events** rather than polling for changes
3. **Check availability** before sending commands to devices
4. **Handle exceptions** gracefully, especially connection errors
5. **Use protocol interfaces** for testable, loosely-coupled code
6. **Unsubscribe** from events when no longer needed to prevent memory leaks

---

## See Also

- [Architecture Overview](../architecture.md)
- [Event Bus Documentation](../architecture/events/event_bus.md)
- [Extension Points](extension_points.md)
- [Home Assistant Lifecycle](homeassistant_lifecycle.md)
