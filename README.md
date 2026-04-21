[![Release][releasebadge]][release]
[![License][license-shield]](LICENSE)
[![Python][pythonbadge]][release]
[![GitHub Sponsors][sponsorsbadge]][sponsors]

# aiohomematic

A modern, async Python library for controlling and monitoring [Homematic](https://www.eq-3.com/products/homematic.html) and [HomematicIP](https://www.homematic-ip.com/en/start.html) devices. Powers the Home Assistant integration "Homematic(IP) Local".

This project is the modern successor to [pyhomematic](https://github.com/danielperna84/pyhomematic), focusing on automatic entity creation, fewer manual device definitions, and faster startups.

## Key Features

- **Automatic entity discovery** from device/channel parameters
- **Broad backend support**: CCU3, OpenCCU, Homegear, CUxD, CCU-Jack, and [pydevccu](https://github.com/danielperna84/pydevccu) for testing
- **Multiple transport protocols**: XML-RPC (standard interfaces) and JSON-RPC (CUxD / CCU-Jack), with MQTT event forwarding via Homematic(IP) Local
- **Extensible** via custom entity classes for complex devices (climate, cover, light, lock, siren, valve, …)
- **Hub entities** for CCU programs, system variables, inbox messages, install mode, and service messages
- **Event-driven architecture** with a unified `EventBus` for lifecycle, state, and diagnostic events
- **Fast startups** through paramset and description caching
- **Robust operation** with circuit breaker, command retry/throttling, and automatic reconnection after CCU restarts
- **Fully typed** (mypy strict mode) and **async/await** based on asyncio

## Documentation

**Full documentation:** [sukramj.github.io/aiohomematic](https://sukramj.github.io/aiohomematic/)

| Section                                                                               | Description                                        |
| ------------------------------------------------------------------------------------- | -------------------------------------------------- |
| [Getting Started](https://sukramj.github.io/aiohomematic/getting_started/)            | Installation and first steps                       |
| [User Guide](https://sukramj.github.io/aiohomematic/user/homeassistant_integration/)  | Home Assistant integration and device topics       |
| [Developer Guide](https://sukramj.github.io/aiohomematic/developer/consumer_api/)     | API reference for library consumers                |
| [Contributor Guide](https://sukramj.github.io/aiohomematic/contributor/contributing/) | Dev environment, coding standards, release process |
| [Architecture & ADRs](https://sukramj.github.io/aiohomematic/architecture/)           | System design and decision records                 |

Additional entry points in this repository: [`CLAUDE.md`](CLAUDE.md) (AI assistant / contributor quick-reference) and [`changelog.md`](changelog.md).

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
│  │  • MQTT bridge for CUxD / CCU-Jack events          │ │
│  └────────────────────────┬───────────────────────────┘ │
└───────────────────────────┼─────────────────────────────┘
                            │
                            │ uses
                            ▼
┌───────────────────────────────────────────────────────────┐
│                      aiohomematic                         │
│                                                           │
│  • Protocol adapters (XML-RPC, JSON-RPC)                  │
│  • Device model and data point abstraction                │
│  • Connection management and reconnection                 │
│  • EventBus for lifecycle / state / diagnostic events     │
│  • Caching (paramset, device descriptions, sessions)      │
└───────────────────────────────────────────────────────────┘
                            │
                            │ communicates with
                            ▼
┌────────────────────────────────────────────────────────────┐
│     CCU3 / OpenCCU / Homegear / CUxD / CCU-Jack            │
└────────────────────────────────────────────────────────────┘
```

CUxD and CCU-Jack use JSON-RPC and receive events via MQTT forwarded by the Home Assistant integration — see [CUxD and CCU-Jack](https://sukramj.github.io/aiohomematic/user/advanced/cuxd_ccu_jack/) for details.

### Why Two Projects?

| Aspect           | aiohomematic                                            | Homematic(IP) Local                                               |
| ---------------- | ------------------------------------------------------- | ----------------------------------------------------------------- |
| **Purpose**      | Python library for Homematic protocol                   | Home Assistant integration                                        |
| **Scope**        | Protocol, devices, data points                          | HA entities, UI, services                                         |
| **Dependencies** | Standalone (aiohttp, orjson)                            | Requires Home Assistant                                           |
| **Reusability**  | Any Python project                                      | Home Assistant only                                               |
| **Repository**   | [aiohomematic](https://github.com/SukramJ/aiohomematic) | [homematicip_local](https://github.com/SukramJ/homematicip_local) |

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
5. **aiohomematic** receives events from the CCU (XML-RPC callbacks or MQTT bridge for CUxD/CCU-Jack) and notifies subscribers via the `EventBus`
6. **Homematic(IP) Local** translates events into Home Assistant state updates

## For Home Assistant Users

Use the Home Assistant custom integration **Homematic(IP) Local**:

1. Install **HACS** in your Home Assistant instance (see [HACS documentation](https://hacs.xyz/)).
2. In HACS, add `https://github.com/SukramJ/homematicip_local` as a **custom repository** (category: Integration).
3. Install **Homematic(IP) Local** via HACS and restart Home Assistant.
4. Configure the integration under **Settings** → **Devices & Services** → **Add Integration**.

See the [Integration Guide](https://sukramj.github.io/aiohomematic/user/homeassistant_integration/) for detailed instructions.

## For Developers

```bash
pip install aiohomematic
```

### Quick Start

```python
import asyncio

from aiohomematic.central import CentralConfig
from aiohomematic.client import InterfaceConfig
from aiohomematic.const import Interface


async def main() -> None:
    config = CentralConfig(
        central_id="ccu-main",
        name="ccu-main",
        host="ccu.local",
        username="admin",
        password="secret",
        interface_configs={
            InterfaceConfig(central_name="ccu-main", interface=Interface.HMIP_RF, port=2010),
        },
    )

    central = await config.create_central()
    await central.start()

    for device in central.devices:
        print(f"{device.name}: {device.address}")

    await central.stop()


asyncio.run(main())
```

For a more complete example (multiple interfaces, event subscriptions, `.env` loading) see [`example.py`](example.py). For API usage patterns see the [Consumer API guide](https://sukramj.github.io/aiohomematic/developer/consumer_api/).

### Contributing

- **Development environment**: [`docs/contributor/dev-environment.md`](https://sukramj.github.io/aiohomematic/contributor/dev-environment/)
- **Contract tests** (protocol / capability invariants, incl. CUxD / CCU-Jack): [`tests/contract/`](tests/contract/)
- **Benchmarks**: [`tests/benchmarks/`](tests/benchmarks/)
- **AI assistant / contributor quick-reference**: [`CLAUDE.md`](CLAUDE.md)

## Requirements

- **Python**: 3.14+
- **CCU firmware**: CCU3 ≥ 3.61.x recommended; CCU2 ≥ 2.61.x is best-effort (see backend support below)
- No active testing is performed to identify the minimum required firmware versions — stay on a current release.

### Backend Support

- **Primary test targets** (continuously tested in CI):
  - OpenCCU with current firmware
  - `pydevccu` (virtual CCU used in the automated test suite)
- **Supported, best-effort** (expected to work, not continuously tested):
  - CCU3 with current firmware
  - CUxD (via JSON-RPC)
  - CCU-Jack (via JSON-RPC)
- **Legacy / unsupported**:
  - CCU2 — works with recent firmware but is not actively tested
  - Homegear — not actively tested

Running outdated firmware or untested backends (CCU2, Homegear) is at your own risk.

**Recommendation:** keep your CCU firmware up to date. Outdated versions may lack bug fixes, security patches, and compatibility improvements that this library relies on.

## Related Projects

| Project                                                             | Description                                        |
| ------------------------------------------------------------------- | -------------------------------------------------- |
| [Homematic(IP) Local](https://github.com/SukramJ/homematicip_local) | Home Assistant integration built on aiohomematic   |
| [pydevccu](https://github.com/danielperna84/pydevccu)               | Virtual CCU used as a test target                  |
| [pyhomematic](https://github.com/danielperna84/pyhomematic)         | Predecessor project (no longer actively developed) |

## Contributing

Contributions are welcome! See the [Contributing Guide](https://sukramj.github.io/aiohomematic/contributor/contributing/) and the in-repo [`CLAUDE.md`](CLAUDE.md) for coding standards and the refactoring checklist.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Support

[![GitHub Sponsors][sponsorsbadge]][sponsors]

If you find this project useful, consider [sponsoring](https://github.com/sponsors/SukramJ) the development.

[license-shield]: https://img.shields.io/github/license/SukramJ/aiohomematic.svg?style=for-the-badge
[pythonbadge]: https://img.shields.io/badge/Python-3.14+-blue?style=for-the-badge&logo=python&logoColor=white
[release]: https://github.com/SukramJ/aiohomematic/releases
[releasebadge]: https://img.shields.io/github/v/release/SukramJ/aiohomematic?style=for-the-badge
[sponsorsbadge]: https://img.shields.io/github/sponsors/SukramJ?style=for-the-badge&label=Sponsors&color=ea4aaa
[sponsors]: https://github.com/sponsors/SukramJ
