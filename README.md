[![Release][releasebadge]][release]
[![License][license-shield]](LICENSE)
[![Python][pythonbadge]][release]
[![GitHub Sponsors][sponsorsbadge]][sponsors]

# aiohomematic

A modern, async Python library for controlling and monitoring [Homematic](https://www.eq-3.com/products/homematic.html) and [HomematicIP](https://www.homematic-ip.com/en/start.html) devices. Powers the Home Assistant integration "Homematic(IP) Local". Some third-party devices/gateways (e.g., Bosch, Intertechno) may be supported as well.

This project is the modern successor to [pyhomematic](https://github.com/danielperna84/pyhomematic), focusing on automatic entity creation, fewer manual device definitions, and faster startups.

## Key Features

- **Automatic entity discovery** from device/channel parameters
- **Extensible** via custom entity classes for complex devices (thermostats, lights, covers, locks, sirens)
- **Fast startups** through caching of paramsets
- **Robust operation** with automatic reconnection after CCU restarts
- **Fully typed** with strict mypy compliance
- **Async/await** based on asyncio

## How It Works

Unlike pyhomematic, which required manual device mappings, aiohomematic automatically creates entities for each relevant parameter on every device channel (unless blacklisted). To achieve this it:

- Fetches and caches device paramsets (VALUES) for fast successive startups
- Provides hooks for custom entity classes where complex behavior is needed
- Includes helpers for robust operation, such as automatic reconnection after CCU restarts

## Requirements

### Python

- Python 3.13 or higher

### CCU Firmware

Due to a bug in earlier CCU2/CCU3 firmware, aiohomematic requires at least the following versions when used with HomematicIP devices:

| Platform | Minimum Version |
| -------- | --------------- |
| CCU2     | 2.53.27         |
| CCU3     | 3.53.26         |

See details: [OpenCCU Issue #843](https://github.com/OpenCCU/OpenCCU/issues/843)

## Installation

### For Home Assistant Users

Use the Home Assistant custom integration "Homematic(IP) Local", which is powered by aiohomematic:

1. **Prerequisites**

   - Latest version of Home Assistant
   - A CCU3, OpenCCU, or Homegear instance reachable from Home Assistant
   - For HomematicIP devices, ensure CCU firmware meets the minimum versions listed above

2. **Install the integration**

   - Add the custom repository: https://github.com/sukramj/homematicip_local
   - Follow the [installation guide](https://github.com/sukramj/homematicip_local/wiki/Installation)

3. **Configure via Home Assistant UI**

   - Settings → Devices & Services → Add Integration → "Homematic(IP) Local"
   - Enter CCU/Homegear host (IP or hostname)
   - Enable TLS if using HTTPS (skip verification for self-signed certificates)
   - Enter credentials
   - Choose interfaces: HM (2001), HmIP (2010), Virtual (9292)

4. **Network callbacks**
   - Ensure Home Assistant is reachable from the CCU (no NAT/firewall blocking)

> **New to Homematic?** See the [Glossary](docs/glossary.md) for definitions of terms like Backend, Interface, Device, Channel.

### For Developers

```bash
pip install aiohomematic
```

Or install from source:

```bash
git clone https://github.com/sukramj/aiohomematic.git
cd aiohomematic
pip install -r requirements.txt
```

## Quick Start

```python
from aiohomematic.central import CentralConfig
from aiohomematic.client import InterfaceConfig, Interface

config = CentralConfig(
    central_id="ccu-main",
    host="ccu.local",
    username="admin",
    password="secret",
    default_callback_port=43439,
    interface_configs={
        InterfaceConfig(interface=Interface.HMIP, port=2010, enabled=True)
    },
)

central = config.create_central()
await central.start()

# Access devices
for device in central.devices:
    print(f"{device.name}: {device.device_address}")

await central.stop()
```

## Public API

The public API is explicitly defined via `__all__` in each module:

| Module                    | Contents                                           |
| ------------------------- | -------------------------------------------------- |
| `aiohomematic.central`    | `CentralUnit`, `CentralConfig` and related schemas |
| `aiohomematic.client`     | `Client`, `InterfaceConfig`, `Interface`           |
| `aiohomematic.model`      | Device/channel/data point abstractions             |
| `aiohomematic.exceptions` | Library exception types                            |
| `aiohomematic.const`      | Constants and enums                                |

Import from specific submodules for stable imports:

```python
from aiohomematic.central import CentralConfig, CentralUnit
from aiohomematic.client import InterfaceConfig, Interface
from aiohomematic.exceptions import ClientException
```

## Documentation

### For Users

- [Changelog](changelog.md) - Release history and latest changes
- [Calculated data points](docs/calculated_data_points.md) - Derived metrics
- [Naming conventions](docs/naming.md) - How names are created
- [Input select helper](docs/input_select_helper.md) - Using input select helpers
- [Troubleshooting](docs/homeassistant_troubleshooting.md) - Common issues and debugging
- [Unignore mechanism](docs/unignore.md) - Unignoring default-ignored devices

### For Developers

- [Architecture overview](docs/architecture.md) - Library architecture
- [Data flow](docs/data_flow.md) - How data flows through the library
- [Extension points](docs/extension_points.md) - Adding custom device profiles
- [Home Assistant lifecycle](docs/homeassistant_lifecycle.md) - Integration internals
- [Sequence diagrams](docs/sequence_diagrams.md) - Interaction flows
- [RSSI fix](docs/rssi_fix.md) - RSSI value handling

## Contributing

Contributions are welcome! Please read our [Contributing Guide](.github/CONTRIBUTING.md) for details on:

- Development environment setup
- Code standards and type annotations
- Pull request process
- Testing guidelines

See [CLAUDE.md](CLAUDE.md) for comprehensive development guidelines.

## Related Projects

- [Homematic(IP) Local](https://github.com/sukramj/homematicip_local) - Home Assistant integration

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

[![GitHub Sponsors][sponsorsbadge]][sponsors]

If you find this project useful, consider [sponsoring](https://github.com/sponsors/SukramJ) the development.

[license-shield]: https://img.shields.io/github/license/SukramJ/aiohomematic.svg?style=for-the-badge
[pythonbadge]: https://img.shields.io/badge/Python-3.13+-blue?style=for-the-badge&logo=python&logoColor=white
[release]: https://github.com/SukramJ/aiohomematic/releases
[releasebadge]: https://img.shields.io/github/v/release/SukramJ/aiohomematic?style=for-the-badge
[sponsorsbadge]: https://img.shields.io/github/sponsors/SukramJ?style=for-the-badge&label=Sponsors&color=ea4aaa
[sponsors]: https://github.com/sponsors/SukramJ
