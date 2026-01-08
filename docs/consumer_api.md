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
device = central.get_device_by_address("VCU0000001")

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

For subscribing to specific data point updates:

```python
# Subscribe to a specific data point
def on_dp_updated(**kwargs):
    print(f"Data point updated: {kwargs}")

unsubscribe = data_point.subscribe_to_data_point_updated(
    handler=on_dp_updated,
    custom_id="my-integration",
)

# Subscribe to device updates
def on_device_updated():
    print("Device state changed")

unsubscribe = device.subscribe_to_device_updated(handler=on_device_updated)
```

---

## Availability Information

aiohomematic provides bundled availability information through `AvailabilityInfo`.

### Using AvailabilityInfo

```python
from aiohomematic.model import AvailabilityInfo

# Get availability for a device
device = central.get_device_by_address("VCU0000001")
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
    CustomDpClimate,
    CustomDpCover,
    CustomDpLock,
)

# Check if device has specific functionality
for cdp in device.custom_data_points:
    if isinstance(cdp, CustomDpDimmer):
        # Dimmer-specific operations
        await cdp.set_level(level=0.5)  # 50%

    elif isinstance(cdp, CustomDpClimate):
        # Climate-specific operations
        await cdp.set_temperature(temperature=21.5)

    elif isinstance(cdp, CustomDpCover):
        # Cover-specific operations
        await cdp.set_level(level=0.0)  # Fully open
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

- [Architecture Overview](architecture.md)
- [Event Bus Documentation](event_bus.md)
- [Extension Points](extension_points.md)
- [Home Assistant Lifecycle](homeassistant_lifecycle.md)
