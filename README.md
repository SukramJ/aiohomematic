[![releasebadge]][release]
[![License][license-shield]](LICENSE.md)
[![GitHub Sponsors][sponsorsbadge]][sponsors]

# AIO Homematic (hahomematic)

A lightweight Python 3 library that powers Home Assistant integrations for controlling and monitoring [Homematic](https://www.eq-3.com/products/homematic.html) and [HomematicIP](https://www.homematic-ip.com/en/start.html) devices. Some third‑party devices/gateways (e.g., Bosch, Intertechno) may be supported as well.

This project is the modern successor to [pyhomematic](https://github.com/danielperna84/pyhomematic), focusing on automatic entity creation, fewer manual device definitions, and faster startups.

## How it works

Unlike pyhomematic, which required manual device mappings, aiohomematic automatically creates entities for each relevant parameter on every device channel (unless blacklisted). To achieve this it:

- Fetches and caches device paramsets (VALUES) for fast successive startups.
- Provides hooks for custom entity classes where complex behavior is needed (e.g., thermostats, lights, covers, climate, locks, sirens).
- Includes helpers for robust operation, such as automatic reconnection after CCU restarts.

## Key features

- Automatic entity discovery from device/channel parameters.
- Extensible via custom entity classes for complex devices.
- Caching of paramsets to speed up restarts.
- Designed to integrate with Home Assistant.

## Quickstart for Home Assistant

Use the Home Assistant custom integration "Homematic(IP) Local", which is powered by aiohomematic.

1. Prerequisites
   - Use latest version of Home Assistant.
   - A CCU3, OpenCCU, or Homegear instance reachable from Home Assistant.
   - For HomematicIP devices, ensure CCU firmware meets the minimum versions listed below.
2. Install the integration
   - Add the custom repository and install: https://github.com/sukramj/homematicip_local
   - Follow the installation guide: https://github.com/sukramj/homematicip_local/wiki/Installation
3. Configure via Home Assistant UI
   - In Home Assistant: Settings → Devices & Services → Add Integration → search for "Homematic(IP) Local".
   - Enter the CCU/Homegear host (IP or hostname). If you use HTTPS on the CCU, enable TLS and don't use verify if self‑signed.
   - Always enter credentials.
   - Choose which interfaces to enable (HM, HmIP, Virtual). Default ports are typically 2001 (HM), 2010 (HmIP), 9292 (Virtual).
4. Network callbacks
   - The integration needs to receive XML‑RPC callbacks from the CCU. Make sure Home Assistant is reachable from the CCU (no NAT/firewall blocking). Callbacks are only required for special network setups.
5. Verify
   - After setup, devices should appear under Devices & Services → Homematic(IP) Local. Discovery may take a few seconds after the first connection while paramsets are fetched and cached for faster restarts.

If you need to use aiohomematic directly in Python, see the Public API and example below.

## Requirements

Due to a bug in earlier CCU2/CCU3 firmware, aiohomematic requires at least the following versions when used with HomematicIP devices:

- CCU2: 2.53.27
- CCU3: 3.53.26

See details here: https://github.com/OpenCCU/OpenCCU/issues/843. Other CCU‑like platforms using the buggy HmIPServer version are not supported.

## Public API and imports

- The public API of aiohomematic is explicitly defined via **all** in each module and subpackage.
- Backwards‑compatible imports should target these modules:
  - aiohomematic.central: CentralUnit, CentralConfig and related schemas
  - aiohomematic.central.event: display received events from the backend
  - aiohomematic.client: Client, InterfaceConfig, create_client, get_client
  - aiohomematic.model: device/data point abstractions (see subpackages for details)
  - aiohomematic.exceptions: library exception types intended for consumers
  - aiohomematic.const: constants and enums (stable subset; see module **all**)
  - aiohomematic.performance: display some performance metrics (enabled when DEBUG is enabled)
- The top‑level package only exposes **version** to avoid import cycles and keep startup lean. Prefer importing from the specific submodules listed above.

Example:

    from aiohomematic.central import CentralConfig
    from aiohomematic import client as hmcl

    cfg = CentralConfig(
        central_id="ccu-main",
        host="ccu.local",
        username="admin",
        password="secret",
        default_callback_port=43439,
        interface_configs={hmcl.InterfaceConfig(interface=hmcl.Interface.HMIP, port=2010, enabled=True)},
    )
    central = cfg.create_central()

## Useful links

- Changelog: [see](changelog.md) for release history and latest changes.
- Definition of calculated data points: [see](docs/calculated_data_points.md)
- Naming: [see](docs/naming.md) for how device, channel and data point names are created.
- Homematic(IP) Local integration: https://github.com/sukramj/homematicip_local
- Input select helper: [see](docs/input_select_helper.md) for an overview of how to use the input select helper.
- Troubleshooting with Home Assistant: [see](docs/homeassistant_troubleshooting.md) for common issues and how to debug them.
- Unignore mechanism: [see](docs/unignore.md) for how to unignore devices that are ignored by default.

## Useful developer links

- Architecture overview: [see](docs/architecture.md) for an overview of the architecture of the library.
- Data flow: [see](docs/data_flow.md) for an overview of how data flows through the library.
- Extending the model: [see](docs/extension_points.md) for adding custom device profiles and calculated data points.
- Home Assistant lifecycle (discovery, updates, teardown): [see](docs/homeassistant_lifecycle.md) for details on how the integration works and how to debug issues.
- RSSI fix: [see](docs/rssi_fix.md) for how RSSI values are fixed for Home Assistant.
- Sequence diagrams: [see](docs/sequence_diagrams.md) for a sequence diagram of how the library works.

[license-shield]: https://img.shields.io/github/license/SukramJ/aiohomematic.svg?style=for-the-badge
[release]: https://github.com/SukramJ/aiohomematic/releases
[releasebadge]: https://img.shields.io/github/v/release/SukramJ/aiohomematic?style=for-the-badge
[sponsorsbadge]: https://img.shields.io/github/sponsors/SukramJ?style=for-the-badge&label=GitHub%20Sponsors&color=green
[sponsors]: https://github.com/sponsors/SukramJ
