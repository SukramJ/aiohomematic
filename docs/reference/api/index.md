# API Reference

This section provides automatically generated API documentation from the aiohomematic source code.

## Quick Links

| Module                      | Description             |
| --------------------------- | ----------------------- |
| [CentralUnit](central.md)   | Core orchestrator class |
| [CentralConfig](config.md)  | Configuration and setup |
| [Exceptions](exceptions.md) | Error handling          |
| [Constants](const.md)       | Enums and constants     |

## Module Structure

```
aiohomematic/
├── central/        # Central unit and coordinators
├── client/         # Protocol adapters (XML-RPC, JSON-RPC)
├── model/          # Device, Channel, DataPoint classes
├── interfaces/     # Protocol interfaces for DI
├── store/          # Caching and persistence
├── exceptions.py   # Exception hierarchy
└── const.py        # Constants and enums
```

## Usage Patterns

### Layer 1: CentralConfig + CentralUnit (Recommended Entry Point)

```python
from aiohomematic.central import CentralConfig

config = CentralConfig.for_ccu(host="...", username="...", password="...")
central = await config.create_central()
await central.start()

devices = central.device_coordinator.devices
```

### Layer 2: Protocol Interfaces (Dependency Injection)

```python
from aiohomematic.interfaces import DeviceProviderProtocol, EventBusProviderProtocol

class MyComponent:
    def __init__(self, *, device_provider: DeviceProviderProtocol): ...
```
