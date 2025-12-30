# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Central unit and core orchestration for Homematic CCU and compatible backends.

Overview
--------
This package provides the central coordination layer for aiohomematic. It models a
Homematic CCU (or compatible backend such as Homegear) and orchestrates
interfaces, devices, channels, data points, events, and background jobs.

The central unit ties together the various submodules: store, client adapters
(JSON-RPC/XML-RPC), device and data point models, and visibility/description store.
It exposes high-level APIs to query and manipulate the backend state while
encapsulating transport and scheduling details.

Public API (selected)
---------------------
- CentralUnit: The main coordination class. Manages client creation/lifecycle,
  connection state, device and channel discovery, data point and event handling,
  sysvar/program access, cache loading/saving, and dispatching handlers.
- CentralConfig: Configuration builder/holder for CentralUnit instances, including
  connection parameters, feature toggles, and cache behavior.
- CentralConnectionState: Tracks connection issues per transport/client.

Internal helpers
----------------
- BackgroundScheduler: Asyncio-based scheduler for periodic tasks such as connection
  health checks, data refreshes, and firmware status updates.

Quick start
-----------
Typical usage is to create a CentralConfig, build a CentralUnit, then start it.

Example (simplified):

    from aiohomematic.central import CentralConfig
    from aiohomematic.client import InterfaceConfig
    from aiohomematic.const import Interface

    cfg = CentralConfig(
        name="MyCCU",
        host="ccu.local",
        username="admin",
        password="secret",
        central_id="ccu-main",
        interface_configs={
            InterfaceConfig(central_name="MyCCU", interface=Interface.HMIP_RF, port=2010),
            InterfaceConfig(central_name="MyCCU", interface=Interface.BIDCOS_RF, port=2001),
        },
    )

    central = cfg.create_central()
    await central.start()     # start XML-RPC server, create/init clients, load store
    # ... interact with devices / data points via central ...
    await central.stop()

Notes
-----
- The central module is thread-aware and uses an internal Looper to schedule async tasks.
- For advanced scenarios, see xml_rpc_server and decorators modules in this package.

"""

from __future__ import annotations

# Re-export public API from submodules (excluding sub-packages coordinators/ and events/)
# For coordinators, import from: aiohomematic.central.coordinators
# For events, import from: aiohomematic.central.events
from aiohomematic.central.central_unit import CENTRAL_INSTANCES, CentralUnit
from aiohomematic.central.config import CentralConfig, check_config
from aiohomematic.central.config_builder import CentralConfigBuilder, ValidationError
from aiohomematic.central.connection_state import CentralConnectionState, ConnectionProblemIssuer
from aiohomematic.central.decorators import callback_backend_system, callback_event
from aiohomematic.central.device_registry import DeviceRegistry
from aiohomematic.central.health import CentralHealth, ConnectionHealth, HealthTracker
from aiohomematic.central.scheduler import BackgroundScheduler, SchedulerJob

__all__ = [
    # Config
    "CentralConfig",
    "CentralConfigBuilder",
    "ValidationError",
    "check_config",
    # Connection
    "CentralConnectionState",
    "ConnectionProblemIssuer",
    # Core
    "CENTRAL_INSTANCES",
    "CentralUnit",
    # Decorators
    "callback_backend_system",
    "callback_event",
    # Health
    "CentralHealth",
    "ConnectionHealth",
    "HealthTracker",
    # Registry
    "DeviceRegistry",
    # Scheduler
    "BackgroundScheduler",
    "SchedulerJob",
]
