# Quick Start

Get aiohomematic running in 5 minutes.

## How It Works

```mermaid
sequenceDiagram
    participant App as Your Application
    participant API as HomematicAPI
    participant CCU as CCU/Homegear

    App->>API: connect()
    API->>CCU: Authenticate
    CCU-->>API: OK
    API->>CCU: List devices
    CCU-->>API: Device descriptions
    API-->>App: Ready

    App->>API: read_value()
    API->>CCU: getValue()
    CCU-->>API: Value
    API-->>App: Result

    Note over CCU,API: Events pushed via callback
    CCU->>API: Event (value changed)
    API->>App: Handler called
```

## Prerequisites

- Python 3.13+
- A Homematic backend (CCU3, OpenCCU, Homegear, etc.)
- Network access to your backend

## Install

```bash
pip install aiohomematic
```

## Connect and List Devices

```python
import asyncio
from aiohomematic.api import HomematicAPI


async def main():
    # Use async context manager for automatic cleanup
    async with HomematicAPI.connect(
        host="192.168.1.100",     # (1)!
        username="Admin",         # (2)!
        password="your-password", # (3)!
    ) as api:
        # Iterate over all discovered devices
        for device in api.list_devices():
            print(f"{device.address}: {device.name} ({device.model})")
        # Connection automatically closed when exiting context


asyncio.run(main())
```

1. Replace with your CCU's IP address or hostname
2. Case-sensitive! Use exactly as shown in CCU
3. See [Security](user/advanced/security.md) for password requirements

**Output:**

```
VCU0000001: Living Room Light (HmIP-BSM)
VCU0000002: Hallway Switch (HmIP-PS)
VCU0000003: Bedroom Thermostat (HmIP-eTRV-2)
```

## Read a Value

```python
async with HomematicAPI.connect(...) as api:
    # Read switch state
    state = await api.read_value(
        channel_address="VCU0000001:3",
        parameter="STATE",
    )
    print(f"Switch is {'ON' if state else 'OFF'}")
```

## Write a Value

```python
async with HomematicAPI.connect(...) as api:
    # Turn on a switch
    await api.write_value(
        channel_address="VCU0000001:3",
        parameter="STATE",
        value=True,
    )
    print("Switch turned ON")
```

## Subscribe to Events

```python
from typing import Any


def on_update(address: str, parameter: str, value: Any) -> None:
    print(f"{address}.{parameter} = {value}")


async with HomematicAPI.connect(...) as api:
    # Subscribe to all value changes
    unsubscribe = api.subscribe_to_updates(callback=on_update)

    # Keep running to receive events
    await asyncio.sleep(60)

    # Stop receiving events
    unsubscribe()
```

## Complete Example

```python
"""Complete aiohomematic quick start example."""

import asyncio
from typing import Any

from aiohomematic.api import HomematicAPI


def on_update(address: str, parameter: str, value: Any) -> None:
    """Handle value updates."""
    print(f"UPDATE: {address}.{parameter} = {value}")


async def main() -> None:
    """Main entry point."""
    async with HomematicAPI.connect(
        host="192.168.1.100",
        username="Admin",
        password="your-password",
    ) as api:
        # 1. List devices
        print("=== Devices ===")
        for device in api.list_devices():
            print(f"  {device.address}: {device.name}")

        # 2. Find a specific device
        device = api.get_device(address="VCU0000001")
        if device:
            print(f"\n=== Device Details ===")
            print(f"  Model: {device.model}")
            print(f"  Firmware: {device.firmware}")

            # 3. List channels and data points
            for channel_no, channel in device.channels.items():
                print(f"\n  Channel {channel_no}:")
                for param, dp in channel.data_points.items():
                    print(f"    {param}: {dp.value}")

        # 4. Subscribe to updates
        unsubscribe = api.subscribe_to_updates(callback=on_update)

        # 5. Toggle a switch (if exists)
        try:
            current = await api.read_value(
                channel_address="VCU0000001:3",
                parameter="STATE",
            )
            await api.write_value(
                channel_address="VCU0000001:3",
                parameter="STATE",
                value=not current,
            )
            print(f"\nToggled switch from {current} to {not current}")
        except Exception as e:
            print(f"\nCould not toggle switch: {e}")

        # 6. Wait for some events
        print("\nWaiting for events (10 seconds)...")
        await asyncio.sleep(10)

        unsubscribe()
        print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
```

## Next Steps

- [Getting Started](getting_started.md) - Detailed setup guide
- [Common Operations](reference/common_operations.md) - More code examples
- [Consumer API](developer/consumer_api.md) - Full API documentation
- [FAQ](faq.md) - Common questions answered
