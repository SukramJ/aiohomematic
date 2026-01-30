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

### For Users (Home Assistant)

- [User Guide](user/homeassistant_integration.md) - Complete integration guide
- [Troubleshooting](troubleshooting/index.md) - Common issues and solutions
- [FAQ](faq.md) - Frequently asked questions
- [Glossary](reference/glossary.md) - Terminology reference

### For Developers (Library Usage)

- [Quick Start](quickstart.md) - Get running in 5 minutes
- [Getting Started](getting_started.md) - Detailed setup guide
- [Consumer API](developer/consumer_api.md) - API patterns for integrations
- [API Reference](reference/api/index.md) - Auto-generated API docs
- [Architecture](architecture.md) - System design overview

### For Contributors

- [Contributing](contributor/contributing.md) - How to contribute
- [Coding Standards](contributor/coding/naming.md) - Naming and style conventions
- [ADRs](adr/0001-circuit-breaker-and-connection-state.md) - Architecture decisions
- [Changelog](changelog.md) - Version history

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

## Two Projects, One Ecosystem

This documentation covers **two related but separate projects**:

| Project                 | Type           | Purpose                               | Repository                                                        |
| ----------------------- | -------------- | ------------------------------------- | ----------------------------------------------------------------- |
| **aiohomematic**        | Python Library | Protocol implementation, device model | [aiohomematic](https://github.com/sukramj/aiohomematic)           |
| **Homematic(IP) Local** | HA Integration | Home Assistant entities, UI, services | [homematicip_local](https://github.com/sukramj/homematicip_local) |

### Which documentation do I need?

- **Home Assistant user?** → Start with the [User Guide](user/homeassistant_integration.md)
- **Building a Python application?** → See [Quick Start](quickstart.md) and [Consumer API](developer/consumer_api.md)
- **Contributing code?** → Check the [Contributor Guide](contributor/contributing.md)

### Architecture Overview

```
Home Assistant
     │
     ▼
Homematic(IP) Local Integration    ← HA-specific: entities, services, UI
     │
     ▼
aiohomematic Library               ← Standalone: protocol, devices, events
     │
     ▼
CCU3 / OpenCCU / Homegear          ← Backend hardware/software
     │
     ▼
Homematic Devices                  ← Physical devices
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
