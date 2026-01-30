# API Reference

This section provides automatically generated API documentation from the aiohomematic source code.

## Quick Links

| Module                      | Description                       |
| --------------------------- | --------------------------------- |
| [HomematicAPI](api.md)      | High-level facade for quick start |
| [CentralUnit](central.md)   | Core orchestrator class           |
| [CentralConfig](config.md)  | Configuration and setup           |
| [Exceptions](exceptions.md) | Error handling                    |
| [Constants](const.md)       | Enums and constants               |

## Module Structure

```
aiohomematic/
├── api.py          # HomematicAPI facade
├── central/        # Central unit and coordinators
├── client/         # Protocol adapters (XML-RPC, JSON-RPC)
├── model/          # Device, Channel, DataPoint classes
├── interfaces/     # Protocol interfaces for DI
├── store/          # Caching and persistence
├── exceptions.py   # Exception hierarchy
└── const.py        # Constants and enums
```

## Usage Patterns

### Layer 1: HomematicAPI (Simplest)

```python
from aiohomematic.api import HomematicAPI

async with HomematicAPI.connect(host="...", username="...", password="...") as api:
    devices = api.list_devices()
```

### Layer 2: CentralConfig + CentralUnit (Full Control)

```python
from aiohomematic.central import CentralConfig

config = CentralConfig.for_ccu(host="...", username="...", password="...")
central = config.create_central()
await central.start()
```

### Layer 3: Protocol Interfaces (Dependency Injection)

```python
from aiohomematic.interfaces import DeviceProviderProtocol, EventBusProviderProtocol

class MyComponent:
    def __init__(self, *, device_provider: DeviceProviderProtocol): ...
```
