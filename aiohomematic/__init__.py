# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
AioHomematic: async Python library for Homematic and HomematicIP backends.

Overview
--------
This package provides a comprehensive async library for interacting with Homematic CCU
and HomematicIP systems. It enables device discovery, data point manipulation, event
handling, and management of programs and system variables.

The library is designed for integration with Home Assistant but can be used standalone.
It features automatic entity discovery, flexible customization through device-specific
implementations, and fast startup through intelligent caching.

Architecture
------------
The library is organized into four main layers:

- **aiohomematic.central**: Central orchestration managing client lifecycles, device
  creation, event handling, and background tasks.
- **aiohomematic.client**: Protocol adapters (JSON-RPC/XML-RPC) for backend communication.
- **aiohomematic.model**: Runtime representation of devices, channels, and data points
  with generic, custom, calculated, and hub entity types.
- **aiohomematic.store**: Persistence layer for device descriptions, paramsets, and
  runtime caches.

Public API
----------
- `__version__`: Library version string.

The primary entry point is `CentralConfig` and `CentralUnit` from `aiohomematic.central`.

Quick start
-----------
Typical usage pattern:

    from aiohomematic.central import CentralConfig
    from aiohomematic.client import InterfaceConfig, Interface

    config = CentralConfig(
        name="ccu-main",
        host="192.168.1.100",
        username="admin",
        password="secret",
        central_id="unique-id",
        interface_configs={
            InterfaceConfig(
                central_name="ccu-main",
                interface=Interface.HMIP_RF,
                port=2010,
            ),
        },
    )

    central = config.create_central()
    await central.start()

    # Access devices and data points
    device = central.device_coordinator.get_device_by_address("VCU0000001")

    await central.stop()

Notes
-----
Public API at the top-level package is defined by `__all__`.

"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
import threading
from typing import Final

from aiohomematic import central as hmcu, i18n, validator as _ahm_validator
from aiohomematic.const import VERSION

if sys.stdout.isatty():
    logging.basicConfig(level=logging.INFO)

__version__: Final = VERSION
_LOGGER: Final = logging.getLogger(__name__)


# pylint: disable=unused-argument
# noinspection PyUnusedLocal
def signal_handler(sig, frame):  # type: ignore[no-untyped-def]
    """Handle signal to shut down central."""
    _LOGGER.info(i18n.tr("log.core.signal.shutdown", sig=str(sig)))
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    for central in hmcu.CENTRAL_INSTANCES.values():
        asyncio.run_coroutine_threadsafe(central.stop(), asyncio.get_running_loop())


# Perform lightweight startup validation once on import
try:
    _ahm_validator.validate_startup()
except Exception as _exc:  # pragma: no cover
    # Fail-fast with a clear message if validation fails during import
    raise RuntimeError(i18n.tr("exception.startup.validation_failed", reason=_exc)) from _exc

if threading.current_thread() is threading.main_thread() and sys.stdout.isatty():
    signal.signal(signal.SIGINT, signal_handler)

# Define public API for the top-level package
__all__ = ["__version__"]
