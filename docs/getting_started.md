# Getting Started with aiohomematic

This guide provides everything you need to start using aiohomematic as a standalone Python library for controlling Homematic and HomematicIP devices.

> **Tip:** For definitions of terms like Backend, Interface, Device, Channel, and Parameter, see the [Glossary](glossary.md).

## Installation

```bash
pip install aiohomematic
```

## Quick Start

### Using the Simplified API (Recommended)

The easiest way to get started is with the `HomematicAPI` facade using the async context manager:

```python
import asyncio
from aiohomematic.api import HomematicAPI

async def main():
    # Connect using the async context manager (recommended)
    async with HomematicAPI.connect(
        host="192.168.1.100",
        username="Admin",
        password="your-password",
    ) as api:
        # List all devices
        for device in api.list_devices():
            print(f"{device.address}: {device.name} ({device.model})")

        # Read a value
        state = await api.read_value(
            channel_address="VCU0000001:1",
            parameter="STATE",
        )
        print(f"Current state: {state}")

        # Write a value
        await api.write_value(
            channel_address="VCU0000001:1",
            parameter="STATE",
            value=True,
        )

    # Connection is automatically closed when exiting the context

asyncio.run(main())
```

#### Connection Options

The `connect()` method supports several options:

```python
# CCU with TLS
async with HomematicAPI.connect(
    host="192.168.1.100",
    username="Admin",
    password="secret",
    tls=True,
    verify_tls=False,  # Set to True in production
) as api:
    ...

# Homegear backend
async with HomematicAPI.connect(
    host="192.168.1.100",
    username="Admin",
    password="secret",
    backend="homegear",
) as api:
    ...

# Custom central ID
async with HomematicAPI.connect(
    host="192.168.1.100",
    username="Admin",
    password="secret",
    central_id="my-living-room-ccu",
) as api:
    ...
```

### Manual Lifecycle Management

For more control over the lifecycle, you can manage start/stop manually:

```python
import asyncio
from aiohomematic.api import HomematicAPI
from aiohomematic.central import CentralConfig

async def main():
    config = CentralConfig.for_ccu(
        name="my-ccu",
        host="192.168.1.100",
        username="Admin",
        password="your-password",
        central_id="my-ccu",
    )

    api = HomematicAPI(config=config)
    await api.start()

    try:
        for device in api.list_devices():
            print(f"{device.address}: {device.name}")
    finally:
        await api.stop()

asyncio.run(main())
```

### Using CentralUnit Directly

For more control, use `CentralUnit` directly:

```python
import asyncio
from aiohomematic.central import CentralConfig
from aiohomematic.client import InterfaceConfig
from aiohomematic.const import Interface

async def main():
    # Define interfaces manually
    interface_configs = {
        InterfaceConfig(
            central_name="my-ccu",
            interface=Interface.HMIP_RF,
            port=2010,
        ),
        InterfaceConfig(
            central_name="my-ccu",
            interface=Interface.BIDCOS_RF,
            port=2001,
        ),
    }

    # Create configuration
    config = CentralConfig(
        name="my-ccu",
        host="192.168.1.100",
        username="Admin",
        password="your-password",
        central_id="unique-id",
        interface_configs=interface_configs,
    )

    # Create and start central unit
    central = config.create_central()
    await central.start()

    try:
        # Access devices
        for device in central.devices:
            print(f"{device.address}: {device.name}")

    finally:
        await central.stop()

asyncio.run(main())
```

## Configuration Presets

aiohomematic provides convenient factory methods for common backend types:

### CCU3/CCU2

```python
from aiohomematic.central import CentralConfig

# Basic setup with HmIP-RF and BidCos-RF
config = CentralConfig.for_ccu(
    host="192.168.1.100",
    username="Admin",
    password="secret",
)

# With TLS and additional interfaces
config = CentralConfig.for_ccu(
    host="192.168.1.100",
    username="Admin",
    password="secret",
    tls=True,
    enable_bidcos_wired=True,
    enable_virtual_devices=True,
)
```

### Homegear

```python
from aiohomematic.central import CentralConfig

config = CentralConfig.for_homegear(
    host="192.168.1.50",
    username="homegear",
    password="secret",
)
```

## Common Patterns

### Device Discovery

```python
# List all devices
for device in api.list_devices():
    print(f"Device: {device.address}")
    print(f"  Name: {device.name}")
    print(f"  Model: {device.model}")
    print(f"  Channels: {len(device.channels)}")

    # List channels and their data points
    for channel in device.channels.values():
        print(f"  Channel {channel.channel_no}:")
        for dp in channel.data_points.values():
            print(f"    - {dp.parameter}: {dp.value}")
```

### Reading Values

```python
# Read from a specific channel and parameter
value = await api.read_value(
    channel_address="VCU0000001:1",
    parameter="STATE",
)

# Read from device data points directly
device = api.get_device(address="VCU0000001")
if device:
    channel = device.channels.get(1)
    if channel:
        state_dp = channel.data_points.get("STATE")
        if state_dp:
            print(f"State: {state_dp.value}")
```

### Writing Values

```python
# Turn on a switch
await api.write_value(
    channel_address="VCU0000001:1",
    parameter="STATE",
    value=True,
)

# Set dimmer level (0.0 to 1.0)
await api.write_value(
    channel_address="VCU0000002:1",
    parameter="LEVEL",
    value=0.5,
)

# Set thermostat temperature
await api.write_value(
    channel_address="VCU0000003:1",
    parameter="SET_POINT_TEMPERATURE",
    value=21.5,
)
```

### Subscribing to Events

```python
from typing import Any

def on_value_changed(address: str, parameter: str, value: Any) -> None:
    print(f"Update: {address}.{parameter} = {value}")

# Subscribe to all data point updates
unsubscribe = api.subscribe_to_updates(callback=on_value_changed)

# ... your application logic ...

# Unsubscribe when done
unsubscribe()
```

### Using the EventBus Directly

For more control over event handling:

```python
from aiohomematic.central.events import DataPointValueReceivedEvent, DeviceStateChangedEvent

async def on_datapoint_update(*, event: DataPointValueReceivedEvent) -> None:
    print(f"DataPoint {event.dpk} = {event.value}")

async def on_device_update(*, event: DeviceStateChangedEvent) -> None:
    print(f"Device updated: {event.device_address}")

# Subscribe to specific events
central.event_bus.subscribe(
    event_type=DataPointValueReceivedEvent,
    event_key=None,
    handler=on_datapoint_update,
)

central.event_bus.subscribe(
    event_type=DeviceStateChangedEvent,
    event_key=None,
    handler=on_device_update,
)
```

## Error Handling

### Common Exceptions

```python
from aiohomematic.exceptions import (
    AioHomematicException,      # Base exception
    ClientException,            # Client/connection errors
    NoConnectionException,      # No connection to backend
    AuthFailure,                # Authentication failed
    ValidationException,        # Value validation failed
)

try:
    await api.write_value(
        channel_address="VCU0000001:1",
        parameter="LEVEL",
        value=1.5,  # Invalid: must be 0.0-1.0
    )
except ValidationException as e:
    print(f"Validation error: {e}")
except NoConnectionException as e:
    print(f"Connection lost: {e}")
except AioHomematicException as e:
    print(f"General error: {e}")
```

### Connection Recovery

The library automatically handles connection recovery. You can monitor connection state:

```python
# Check connection status
if api.is_connected:
    print("Connected to backend")
else:
    print("Not connected")

# Subscribe to device availability changes
from aiohomematic.central.events import DeviceStateChangedEvent

async def on_device_updated(*, event: DeviceStateChangedEvent) -> None:
    print(f"Device {event.device_address} was updated")

unsubscribe = central.event_bus.subscribe(
    event_type=DeviceStateChangedEvent,
    event_key=None,
    handler=on_device_updated,
)
```

## Working with Specific Device Types

### Switches

```python
# Get switch state
state = await api.read_value(
    channel_address="VCU0000001:1",
    parameter="STATE",
)

# Toggle switch
await api.write_value(
    channel_address="VCU0000001:1",
    parameter="STATE",
    value=not state,
)
```

### Dimmers

```python
# Get current level (0.0-1.0)
level = await api.read_value(
    channel_address="VCU0000002:1",
    parameter="LEVEL",
)

# Set to 75%
await api.write_value(
    channel_address="VCU0000002:1",
    parameter="LEVEL",
    value=0.75,
)
```

### Thermostats

```python
# Read current temperature
current_temp = await api.read_value(
    channel_address="VCU0000003:1",
    parameter="ACTUAL_TEMPERATURE",
)

# Read set point
set_point = await api.read_value(
    channel_address="VCU0000003:1",
    parameter="SET_POINT_TEMPERATURE",
)

# Set new temperature
await api.write_value(
    channel_address="VCU0000003:1",
    parameter="SET_POINT_TEMPERATURE",
    value=22.0,
)
```

### Blinds/Covers

```python
# Get current position (0.0=closed, 1.0=open)
position = await api.read_value(
    channel_address="VCU0000004:1",
    parameter="LEVEL",
)

# Open blinds fully
await api.write_value(
    channel_address="VCU0000004:1",
    parameter="LEVEL",
    value=1.0,
)

# Stop movement
await api.write_value(
    channel_address="VCU0000004:1",
    parameter="STOP",
    value=True,
)
```

## Programs and System Variables

### Running Programs

```python
# Access programs through the hub
for program in central.hub.programs:
    print(f"Program: {program.name}")

# Execute a program
program = central.get_program_by_name("MyProgram")
if program:
    await program.execute()
```

### System Variables

```python
# Read system variable
for sysvar in central.hub.sysvars:
    print(f"{sysvar.name}: {sysvar.value}")

# Update system variable
sysvar = central.get_sysvar_by_name("MySysVar")
if sysvar:
    await sysvar.set_value(42)
```

## Best Practices

1. **Always use async context**: All network operations are asynchronous.

2. **Clean up properly**: Always call `stop()` to clean up resources.

3. **Handle disconnections**: The library auto-reconnects, but your code should handle temporary disconnections gracefully.

4. **Use keyword arguments**: All API methods use keyword-only parameters for clarity.

5. **Validate before writing**: Check parameter constraints before writing values to avoid validation errors.

6. **Subscribe to events**: Use event subscriptions instead of polling for real-time updates.

## Next Steps

- See [Common Operations](common_operations.md) for more detailed examples
- Check the [Architecture](architecture.md) documentation for advanced usage
- Review the [API Reference](api_reference.md) for complete method documentation
