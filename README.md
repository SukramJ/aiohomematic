[![Release][releasebadge]][release]
[![License][license-shield]](LICENSE)
[![Python][pythonbadge]][release]
[![GitHub Sponsors][sponsorsbadge]][sponsors]

# aiohomematic

A modern, async Python library for controlling and monitoring [Homematic](https://www.eq-3.com/products/homematic.html) and [HomematicIP](https://www.homematic-ip.com/en/start.html) devices. Powers the Home Assistant integration "Homematic(IP) Local".

This project is the modern successor to [pyhomematic](https://github.com/danielperna84/pyhomematic), focusing on automatic entity creation, fewer manual device definitions, and faster startups.

## Key Features

- **Automatic entity discovery** from device/channel parameters
- **Extensible** via custom entity classes for complex devices (thermostats, lights, covers, locks, sirens)
- **Fast startups** through caching of paramsets
- **Robust operation** with automatic reconnection after CCU restarts
- **Fully typed** with strict mypy compliance
- **Async/await** based on asyncio

## Documentation

**Full documentation:** [sukramj.github.io/aiohomematic](https://sukramj.github.io/aiohomematic/)

| Section                                                                              | Description                      |
| ------------------------------------------------------------------------------------ | -------------------------------- |
| [Getting Started](https://sukramj.github.io/aiohomematic/getting_started/)           | Installation and first steps     |
| [User Guide](https://sukramj.github.io/aiohomematic/user/homeassistant_integration/) | Home Assistant integration guide |
| [Developer Guide](https://sukramj.github.io/aiohomematic/developer/consumer_api/)    | API reference for integrations   |
| [Architecture](https://sukramj.github.io/aiohomematic/architecture/)                 | System design overview           |
| [Glossary](https://sukramj.github.io/aiohomematic/reference/glossary/)               | Terminology reference            |

## How It Works

```
┌─────────────────────────────────────────────────────────┐
│                    Home Assistant                       │
│                                                         │
│  ┌────────────────────────────────────────────────────┐ │
│  │           Homematic(IP) Local Integration          │ │
│  │                                                    │ │
│  │  • Home Assistant entities (climate, light, etc.)  │ │
│  │  • UI configuration flows                          │ │
│  │  • Services and automations                        │ │
│  │  • Device/entity registry integration              │ │
│  └────────────────────────┬───────────────────────────┘ │
└───────────────────────────┼─────────────────────────────┘
                            │
                            │ uses
                            ▼
┌───────────────────────────────────────────────────────────┐
│                      aiohomematic                         │
│                                                           │
│  • Protocol implementation (XML-RPC, JSON-RPC)            │
│  • Device model and data point abstraction                │
│  • Connection management and reconnection                 │
│  • Event handling and callbacks                           │
│  • Caching for fast startups                              │
└───────────────────────────────────────────────────────────┘
                            │
                            │ communicates with
                            ▼
┌───────────────────────────────────────────────────────────┐
│              CCU3 / OpenCCU / Homegear                    │
└───────────────────────────────────────────────────────────┘
```

### Why Two Projects?

| Aspect           | aiohomematic                                            | Homematic(IP) Local                                               |
| ---------------- | ------------------------------------------------------- | ----------------------------------------------------------------- |
| **Purpose**      | Python library for Homematic protocol                   | Home Assistant integration                                        |
| **Scope**        | Protocol, devices, data points                          | HA entities, UI, services                                         |
| **Dependencies** | Standalone (aiohttp, orjson)                            | Requires Home Assistant                                           |
| **Reusability**  | Any Python project                                      | Home Assistant only                                               |
| **Repository**   | [aiohomematic](https://github.com/sukramj/aiohomematic) | [homematicip_local](https://github.com/sukramj/homematicip_local) |

**Benefits of this separation:**

- **Reusability**: aiohomematic can be used in any Python project, not just Home Assistant
- **Testability**: The library can be tested independently without Home Assistant
- **Maintainability**: Protocol changes don't affect HA-specific code and vice versa
- **Clear boundaries**: Each project has a focused responsibility

### How They Work Together

1. **Homematic(IP) Local** creates a `CentralUnit` via aiohomematic's API
2. **aiohomematic** connects to the CCU/Homegear and discovers devices
3. **aiohomematic** creates `Device`, `Channel`, and `DataPoint` objects
4. **Homematic(IP) Local** wraps these in Home Assistant entities
5. **aiohomematic** receives events from the CCU and notifies subscribers
6. **Homematic(IP) Local** translates events into Home Assistant state updates

## For Home Assistant Users

Use the Home Assistant custom integration **Homematic(IP) Local**:

1. Add the custom repository: https://github.com/sukramj/homematicip_local
2. Install via HACS
3. Configure via **Settings** → **Devices & Services** → **Add Integration**

See the [Integration Guide](https://sukramj.github.io/aiohomematic/user/homeassistant_integration/) for detailed instructions.

## For Developers

```bash
pip install aiohomematic
```

### Quick Start

```python
from aiohomematic.central import CentralConfig
from aiohomematic.client import InterfaceConfig
from aiohomematic.const import Interface

config = CentralConfig(
    central_id="ccu-main",
    host="ccu.local",
    username="admin",
    password="secret",
    default_callback_port=43439,
    interface_configs={
        InterfaceConfig(central_name="ccu-main", interface=Interface.HMIP_RF, port=2010)
    },
)

central = config.create_central()
await central.start()

for device in central.devices:
    print(f"{device.name}: {device.device_address}")

await central.stop()
```

See [Getting Started](https://sukramj.github.io/aiohomematic/getting_started/) for more examples.

## Requirements

- **Python**: 3.13+
- **CCU Firmware**: CCU2 ≥2.53.27, CCU3 ≥3.53.26 (for HomematicIP devices)

## Related Projects

| Project                                                               | Description                |
| --------------------------------------------------------------------- | -------------------------- |
| [Homematic(IP) Local](https://github.com/sukramj/homematicip_local)   | Home Assistant integration |
| [aiohomematic Documentation](https://sukramj.github.io/aiohomematic/) | Full documentation         |

## Contributing

Contributions are welcome! See the [Contributing Guide](https://sukramj.github.io/aiohomematic/contributor/contributing/) for details.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Support

[![GitHub Sponsors][sponsorsbadge]][sponsors]

If you find this project useful, consider [sponsoring](https://github.com/sponsors/SukramJ) the development.

[license-shield]: https://img.shields.io/github/license/SukramJ/aiohomematic.svg?style=for-the-badge
[pythonbadge]: https://img.shields.io/badge/Python-3.13+-blue?style=for-the-badge&logo=python&logoColor=white
[release]: https://github.com/SukramJ/aiohomematic/releases
[releasebadge]: https://img.shields.io/github/v/release/SukramJ/aiohomematic?style=for-the-badge
[sponsorsbadge]: https://img.shields.io/github/sponsors/SukramJ?style=for-the-badge&label=Sponsors&color=ea4aaa
[sponsors]: https://github.com/sponsors/SukramJ
