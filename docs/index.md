# aiohomematic

[![PyPI version](https://badge.fury.io/py/aiohomematic.svg)](https://badge.fury.io/py/aiohomematic)
[![Python versions](https://img.shields.io/pypi/pyversions/aiohomematic.svg)](https://pypi.org/project/aiohomematic/)
[![License](https://img.shields.io/github/license/sukramj/aiohomematic)](https://github.com/sukramj/aiohomematic/blob/master/LICENSE)

**Modern async Python library for Homematic and HomematicIP devices.**

aiohomematic powers the [Homematic(IP) Local](https://github.com/sukramj/homematicip_local) integration for Home Assistant, enabling local control of Homematic devices without cloud dependency.

---

## Features

- **Async-first**: Built on `asyncio` for non-blocking I/O operations
- **Type-safe**: Fully typed with strict `mypy` enforcement
- **Auto-discovery**: Automatic entity creation from device parameters
- **Extensible**: Custom entity classes for device-specific features
- **Fast startup**: Paramset caching for quick initialization
- **Multi-backend**: Supports CCU3, CCU2, Homegear, and RaspberryMatic

## Quick Start

### Installation

```bash
pip install aiohomematic
```

### Basic Usage

```python
import asyncio
from aiohomematic.central import CentralConfig
from aiohomematic.client import InterfaceConfig
from aiohomematic.const import Interface

async def main():
    # Configure the central unit
    config = CentralConfig(
        name="my-ccu",
        host="192.168.1.100",
        username="Admin",
        password="your-password",
        central_id="my-central",
        interface_configs={
            InterfaceConfig(
                central_name="my-ccu",
                interface=Interface.HMIP_RF,
                port=2010,
            ),
        },
    )

    # Create and start the central
    central = config.create_central()
    await central.start()

    # Access devices
    for address, device in central.devices.items():
        print(f"Device: {device.name} ({address})")

    # Stop the central
    await central.stop()

asyncio.run(main())
```

## Documentation Overview

### For Users

- [Getting Started](getting_started.md) - Installation and first steps
- [Glossary](reference/glossary.md) - Terminology reference
- [Troubleshooting](user/troubleshooting/homeassistant_troubleshooting.md) - Common issues and solutions

### For Developers

- [Architecture](architecture.md) - System design overview
- [Extension Points](developer/extension_points.md) - How to add device support
- [Consumer API](developer/consumer_api.md) - API reference for integrations
- [Event System](architecture/events/event_bus.md) - Event handling patterns

### For Contributors

- [Docstring Standards](contributor/coding/docstring_standards.md) - Code documentation guidelines
- [Naming Conventions](contributor/coding/naming.md) - Naming patterns and rules
- [ADRs](adr/0001-circuit-breaker-and-connection-state.md) - Architecture decisions

## Supported Devices

aiohomematic supports a wide range of Homematic and HomematicIP devices:

| Category    | Examples                          |
| ----------- | --------------------------------- |
| **Climate** | HmIP-eTRV, HmIP-BWTH, HM-CC-RT-DN |
| **Cover**   | HmIP-BROLL, HmIP-FBL, HM-LC-Bl1   |
| **Light**   | HmIP-BDT, HmIP-BSL, HM-LC-Dim1T   |
| **Lock**    | HmIP-DLD, HM-Sec-Key              |
| **Switch**  | HmIP-PS, HmIP-BSM, HM-LC-Sw1      |
| **Sensor**  | HmIP-SRH, HmIP-SWSD, HmIP-SMI     |
| **Siren**   | HmIP-ASIR, HmIP-MP3P              |

For a complete list, see the [Extension Points](developer/extension_points.md) documentation.

## Integration with Home Assistant

aiohomematic is designed to work seamlessly with the **Homematic(IP) Local** integration:

```
Home Assistant
     │
     ▼
Homematic(IP) Local Integration
     │
     ▼
aiohomematic Library
     │
     ▼
CCU3 / RaspberryMatic / Homegear
     │
     ▼
Homematic Devices
```

See [Home Assistant Lifecycle](developer/homeassistant_lifecycle.md) for detailed integration flow.

## Links

- **GitHub**: [sukramj/aiohomematic](https://github.com/sukramj/aiohomematic)
- **PyPI**: [aiohomematic](https://pypi.org/project/aiohomematic/)
- **Issues**: [Report a bug](https://github.com/sukramj/aiohomematic/issues)
- **Discussions**: [Ask questions](https://github.com/sukramj/aiohomematic/discussions)
- **HA Integration**: [homematicip_local](https://github.com/sukramj/homematicip_local)

## License

MIT License - see [LICENSE](https://github.com/sukramj/aiohomematic/blob/master/LICENSE) for details.
