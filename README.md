# AIO Homematic (hahomematic)

A lightweight Python 3 library that powers Home Assistant integrations for controlling and monitoring [HomeMatic](https://www.eq-3.com/products/homematic.html) and [HomematicIP](https://www.homematic-ip.com/en/start.html) devices. Some third‑party devices/gateways (e.g., Bosch, Intertechno) may be supported as well.

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

## Installation (with Home Assistant)

Install via the custom component: [custom_homematic](https://github.com/sukramj/custom_homematic).

Follow the installation guide: https://github.com/sukramj/custom_homematic/wiki/Installation

## Requirements

Due to a bug in earlier CCU2/CCU3 firmware, aiohomematic requires at least the following versions when used with HomematicIP devices:

- CCU2: 2.53.27
- CCU3: 3.53.26

See details here: https://github.com/jens-maus/RaspberryMatic/issues/843. Other CCU‑like platforms using the buggy HmIPServer version are not supported.

## Useful links

- Examples: see example.py in this repository.
- Changelog: see changelog.md.
- Source code and documentation: this repository (docs/ directory may contain additional information).
