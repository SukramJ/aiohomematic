# Common Operations Reference

This document covers the most frequently used operations in aiohomematic, with detailed examples and best practices.

> **Tip:** For definitions of terms like Device, Channel, Parameter, and System Variable, see the [Glossary](glossary.md).

## Table of Contents

1. [Connection Management](#connection-management)
2. [Device Operations](#device-operations)
3. [Value Operations](#value-operations)
4. [Event Handling](#event-handling)
5. [Programs and System Variables](#programs-and-system-variables)
6. [Cache Management](#cache-management)

---

## Connection Management

### Starting and Stopping

```python
from aiohomematic.api import HomematicAPI
from aiohomematic.central import CentralConfig

async def main():
    config = CentralConfig.for_ccu(
        host="192.168.1.100",
        username="Admin",
        password="secret",
    )

    api = HomematicAPI(config=config)

    # Start connection
    await api.start()

    # Your application logic here...

    # Clean shutdown
    await api.stop()
```

### Connection State Monitoring

```python
# Using HomematicAPI
if api.is_connected:
    print("Connected")

# Using CentralUnit for detailed state
from aiohomematic.central import CentralUnit
from aiohomematic.const import CentralState

central: CentralUnit = api.central

# Check overall system state
print(f"Central state: {central.state}")

# Different states indicate different system health:
if central.state == CentralState.RUNNING:
    print("✅ All interfaces connected")
elif central.state == CentralState.DEGRADED:
    print("⚠️ Some interfaces disconnected")
elif central.state == CentralState.FAILED:
    print("❌ System failed - max retries reached")

# Check connection health per interface
if central.connection_state.is_any_issue:
    print(f"Connection issues: {central.connection_state.issue_count}")

# Subscribe to device state changes
from aiohomematic.central.events import DeviceStateChangedEvent


async def on_device_updated(*, event: DeviceStateChangedEvent) -> None:
    """Handle device state changes."""
    print(f"Device updated: {event.device_address}")


unsubscribe_device = central.event_bus.subscribe(
    event_type=DeviceStateChangedEvent,
    event_key=None,
    handler=on_device_updated,
)

# Later: stop receiving notifications
unsubscribe_device()
```

### Reconnection Handling

The library automatically handles reconnection. To manually trigger:

```python
# Restart all clients
await central.client_coordinator.restart_clients()

# Or refresh data after reconnection
await api.refresh_data()
```

---

## Device Operations

### Listing All Devices

```python
# Simple listing
for device in api.list_devices():
    print(f"{device.address}: {device.name}")

# With details
for device in api.list_devices():
    print(f"\nDevice: {device.address}")
    print(f"  Name: {device.name}")
    print(f"  Model: {device.model}")
    print(f"  Type: {device.device_type}")
    print(f"  Interface: {device.interface}")
    print(f"  Firmware: {device.firmware}")
    print(f"  Available: {device.available}")
```

### Finding Devices

```python
# By address
device = api.get_device(address="VCU0000001")

# By name (filter through list)
device = next(
    (d for d in api.list_devices() if d.name == "Living Room Switch"),
    None,
)

# Filter by model
hmip_switches = [
    d for d in api.list_devices()
    if d.model.startswith("HmIP-PS")
]

# Filter by interface
from aiohomematic.const import Interface

hmip_devices = [
    d for d in api.list_devices()
    if d.interface == Interface.HMIP_RF
]
```

### Accessing Channels

```python
device = api.get_device(address="VCU0000001")
if device:
    # Get all channels
    for channel_no, channel in device.channels.items():
        print(f"Channel {channel_no}: {channel.channel_address}")

    # Get specific channel
    channel = device.channels.get(1)
    if channel:
        print(f"Channel address: {channel.channel_address}")
```

### Accessing Data Points

```python
device = api.get_device(address="VCU0000001")
if device:
    channel = device.channels.get(1)
    if channel:
        # List all data points
        for param_name, dp in channel.data_points.items():
            print(f"{param_name}: {dp.value} ({dp.unit})")

        # Get specific data point
        state_dp = channel.data_points.get("STATE")
        if state_dp:
            print(f"State value: {state_dp.value}")
            print(f"State unit: {state_dp.unit}")
            print(f"Writable: {state_dp.is_writable}")
```

---

## Value Operations

### Reading Values

```python
# Using HomematicAPI
value = await api.read_value(
    channel_address="VCU0000001:1",
    parameter="STATE",
)

# Reading from different paramsets
from aiohomematic.const import ParamsetKey

# VALUES paramset (runtime values) - default
state = await api.read_value(
    channel_address="VCU0000001:1",
    parameter="STATE",
    paramset_key=ParamsetKey.VALUES,
)

# MASTER paramset (configuration)
config_value = await api.read_value(
    channel_address="VCU0000001:0",
    parameter="CYCLIC_INFO_MSG",
    paramset_key=ParamsetKey.MASTER,
)
```

### Writing Values

```python
# Using HomematicAPI
await api.write_value(
    channel_address="VCU0000001:1",
    parameter="STATE",
    value=True,
)

# Using ConfigurationCoordinator for more control
await central.configuration.put_paramset(
    channel_address="VCU0000001:1",
    paramset_key_or_link_address=ParamsetKey.VALUES,
    values={
        "STATE": True,
        "ON_TIME": 300,  # 5 minutes
    },
)
```

### Value Types and Constraints

```python
# Check parameter constraints before writing
device = api.get_device(address="VCU0000001")
channel = device.channels.get(1)
level_dp = channel.data_points.get("LEVEL")

if level_dp:
    print(f"Min: {level_dp.min}")      # e.g., 0.0
    print(f"Max: {level_dp.max}")      # e.g., 1.0
    print(f"Default: {level_dp.default}")
    print(f"Type: {level_dp.type}")    # e.g., FLOAT

    # Safe write with validation
    new_value = 0.5
    if level_dp.min <= new_value <= level_dp.max:
        await api.write_value(
            channel_address=channel.channel_address,
            parameter="LEVEL",
            value=new_value,
        )
```

---

## Event Handling

### Simple Event Subscription

```python
from typing import Any

def on_update(address: str, parameter: str, value: Any) -> None:
    print(f"{address}.{parameter} = {value}")

# Subscribe
unsubscribe = api.subscribe_to_updates(callback=on_update)

# ... application runs ...

# Unsubscribe
unsubscribe()
```

### Typed Event Handling with EventBus

```python
from aiohomematic.central.events import (
    DataPointValueReceivedEvent,
    DeviceStateChangedEvent,
    FirmwareStateChangedEvent,
)

# Data point updates
async def on_datapoint_update(*, event: DataPointValueReceivedEvent) -> None:
    print(f"DataPointKey: {event.dpk}")
    print(f"Value: {event.value}")

central.event_bus.subscribe(
    event_type=DataPointValueReceivedEvent,
    event_key=None,
    handler=on_datapoint_update,
)

# Device events
async def on_device_event(*, event: DeviceStateChangedEvent) -> None:
    print(f"Device updated: {event.device_address}")

central.event_bus.subscribe(
    event_type=DeviceStateChangedEvent,
    event_key=None,
    handler=on_device_event,
)
```

### Filtering Events

```python
from aiohomematic.const import DataPointKey, ParamsetKey

# Subscribe to specific device by filtering in handler
async def on_specific_device(*, event: DataPointValueReceivedEvent) -> None:
    if event.dpk.channel_address.startswith("VCU0000001"):
        print(f"My device: {event.dpk.parameter} = {event.value}")

central.event_bus.subscribe(
    event_type=DataPointValueReceivedEvent,
    event_key=None,
    handler=on_specific_device,
)

# Subscribe with specific DataPointKey filter
specific_dpk = DataPointKey(
    interface_id="BidCos-RF",
    channel_address="VCU0000001:1",
    paramset_key=ParamsetKey.VALUES,
    parameter="STATE",
)
central.event_bus.subscribe(
    event_type=DataPointValueReceivedEvent,
    event_key=specific_dpk,
    handler=on_datapoint_update,
)
```

---

## Programs and System Variables

### Listing Programs

```python
# Through HubCoordinator
for program in central.hub_coordinator.program_data_points:
    print(f"Program: {program.name}")
    print(f"  ID: {program.unique_id}")
    print(f"  Active: {program.is_active}")
    print(f"  Internal: {program.is_internal}")
```

### Executing Programs

```python
# Find by name (filter through list)
program = next(
    (p for p in central.hub_coordinator.program_data_points if p.name == "Wake Up Lights"),
    None,
)
if program:
    await program.press()

# Or by PID
program = central.hub_coordinator.get_program_data_point(pid="12345")
if program:
    await program.press()
```

### Reading System Variables

```python
# List all
for sysvar in central.hub_coordinator.sysvar_data_points:
    print(f"{sysvar.name}: {sysvar.value}")

# Get specific variable (filter through list)
sysvar = next(
    (sv for sv in central.hub_coordinator.sysvar_data_points if sv.name == "Presence"),
    None,
)
if sysvar:
    print(f"Value: {sysvar.value}")
```

### Writing System Variables

```python
sysvar = next(
    (sv for sv in central.hub_coordinator.sysvar_data_points if sv.name == "AlarmActive"),
    None,
)
if sysvar:
    # Boolean variable
    await sysvar.send_variable(value=True)

# Number variable
sysvar = next(
    (sv for sv in central.hub_coordinator.sysvar_data_points if sv.name == "TargetTemperature"),
    None,
)
if sysvar:
    await sysvar.send_variable(value=21.5)

# String variable
sysvar = next(
    (sv for sv in central.hub_coordinator.sysvar_data_points if sv.name == "StatusMessage"),
    None,
)
if sysvar:
    await sysvar.send_variable(value="All systems normal")
```

---

## Cache Management

### Understanding Caches

aiohomematic uses several caches:

- **Device Description Cache**: Stores device metadata
- **Paramset Description Cache**: Stores parameter definitions
- **Data Cache**: Stores current runtime values

### Refreshing Data

```python
# Refresh all device data
await api.refresh_data()

# Refresh specific device
device = api.get_device(address="VCU0000001")
if device:
    await device.refresh_data()

# Refresh Hub data (programs, sysvars)
await central.hub_coordinator.fetch_program_data()
await central.hub_coordinator.fetch_sysvar_data()
```

### Cache Location

Caches are stored in the configured storage directory:

```python
config = CentralConfig.for_ccu(
    host="192.168.1.100",
    username="Admin",
    password="secret",
    storage_directory="/path/to/cache",  # Default: current directory
)
```

### Clearing Caches

Cache management is handled internally by aiohomematic. Caches are automatically
refreshed during startup and reconnection. To force a re-fetch of device data,
stop and restart the central unit.

---

## Advanced Operations

### Direct RPC Calls

For advanced use cases, you can access the clients directly:

```python
# Get client for specific interface
from aiohomematic.const import Interface

client = central.client_coordinator.get_client(interface=Interface.HMIP_RF)
if client:
    # Low-level RPC call
    result = await client.get_value(
        channel_address="VCU0000001:1",
        paramset_key="VALUES",
        parameter="STATE",
    )
```

### Device Firmware Updates

```python
# Check firmware status
for device in api.list_devices():
    if device.firmware_update_state:
        print(f"{device.name}: {device.firmware_update_state}")

# Trigger firmware update (via client)
client = central.client_coordinator.get_client(interface=Interface.HMIP_RF)
await client.update_device_firmware(device_address="VCU0000001")
```

### Link Peers (Direct Device Communication)

```python
# Get link peers for a device (via client)
client = central.client_coordinator.get_client(interface=Interface.HMIP_RF)
peers = await client.get_link_peers(channel_address="VCU0000001:1")
for peer in peers:
    print(f"Linked to: {peer}")

# Create link (via LinkCoordinator)
await central.link.add_link(
    sender_channel_address="VCU0000001:1",
    receiver_channel_address="VCU0000002:1",
    name="My Link",
    description="Button controls light",
)

# Remove link
await central.link.remove_link(
    sender_channel_address="VCU0000001:1",
    receiver_channel_address="VCU0000002:1",
)
```

---

## Error Reference

| Exception               | Description              | Common Causes                  |
| ----------------------- | ------------------------ | ------------------------------ |
| `NoConnectionException` | No connection to backend | Network issues, CCU offline    |
| `AuthFailure`           | Authentication failed    | Wrong credentials              |
| `ValidationException`   | Value validation failed  | Value out of range             |
| `ClientException`       | General client error     | RPC call failed                |
| `UnsupportedException`  | Operation not supported  | Backend doesn't support method |

```python
from aiohomematic.exceptions import (
    NoConnectionException,
    AuthFailure,
    ValidationException,
    ClientException,
)

try:
    await api.write_value(
        channel_address="VCU0000001:1",
        parameter="LEVEL",
        value=1.5,
    )
except ValidationException as e:
    print(f"Invalid value: {e}")
except NoConnectionException:
    print("Lost connection, will retry...")
except AuthFailure:
    print("Check your credentials")
except ClientException as e:
    print(f"RPC error: {e}")
```
