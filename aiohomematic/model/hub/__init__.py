# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Hub (backend) data points for AioHomematic.

This package reflects the state and capabilities of the backend at the hub
level. It exposes backend programs, system variables, install mode, metrics,
and system updates as data points that can be observed and acted upon by
higher layers (e.g., Home Assistant integration).

Package structure
-----------------
- hub.py: Hub orchestrator class and container types (ProgramDpType, MetricsDpType)
- data_point.py: Base classes (GenericHubDataPoint, GenericProgramDataPoint, GenericSysvarDataPoint)
- button.py, switch.py: Program data points (ProgramDpButton, ProgramDpSwitch)
- sensor.py, binary_sensor.py, select.py, number.py, text.py: Sysvar data points
- install_mode.py: Install mode button and sensor
- metrics.py: System health, connection latency, event age sensors
- inbox.py: Inbox device sensor
- update.py: System update sensor

Public API
----------
- Hub: Main orchestrator for hub-level data point lifecycle
- Program data points: ProgramDpButton, ProgramDpSwitch, ProgramDpType
- Sysvar data points: SysvarDpSensor, SysvarDpBinarySensor, SysvarDpSelect,
  SysvarDpNumber, SysvarDpSwitch, SysvarDpText
- Install mode: InstallModeDpButton, InstallModeDpSensor, InstallModeDpType
- Metrics: HmSystemHealthSensor, HmConnectionLatencySensor, HmLastEventAgeSensor, MetricsDpType
- Other: HmInboxSensor, HmUpdate
- Base types: GenericHubDataPoint, GenericProgramDataPoint, GenericSysvarDataPoint

Sysvar type mapping
-------------------
System variables are mapped to data point types based on SysvarType:
- ALARM/LOGIC → SysvarDpBinarySensor (or SysvarDpSwitch if extended)
- LIST (extended) → SysvarDpSelect
- FLOAT/INTEGER (extended) → SysvarDpNumber
- STRING (extended) → SysvarDpText
- Other → SysvarDpSensor

Related modules
---------------
- aiohomematic.central: Central unit coordination
- aiohomematic.const: HUB_CATEGORIES, SystemEventType.HUB_REFRESHED

"""

from __future__ import annotations

from aiohomematic.model.hub.binary_sensor import SysvarDpBinarySensor
from aiohomematic.model.hub.button import ProgramDpButton
from aiohomematic.model.hub.data_point import GenericHubDataPoint, GenericProgramDataPoint, GenericSysvarDataPoint
from aiohomematic.model.hub.hub import Hub, MetricsDpType, ProgramDpType
from aiohomematic.model.hub.inbox import HmInboxSensor
from aiohomematic.model.hub.install_mode import InstallModeDpButton, InstallModeDpSensor, InstallModeDpType
from aiohomematic.model.hub.metrics import HmConnectionLatencySensor, HmLastEventAgeSensor, HmSystemHealthSensor
from aiohomematic.model.hub.number import SysvarDpNumber
from aiohomematic.model.hub.select import SysvarDpSelect
from aiohomematic.model.hub.sensor import SysvarDpSensor
from aiohomematic.model.hub.switch import ProgramDpSwitch, SysvarDpSwitch
from aiohomematic.model.hub.text import SysvarDpText
from aiohomematic.model.hub.update import HmUpdate

__all__ = [
    # Base
    "GenericHubDataPoint",
    "GenericProgramDataPoint",
    "GenericSysvarDataPoint",
    # Hub
    "Hub",
    # Inbox
    "HmInboxSensor",
    # Install mode
    "InstallModeDpButton",
    "InstallModeDpSensor",
    "InstallModeDpType",
    # Metrics
    "HmConnectionLatencySensor",
    "HmLastEventAgeSensor",
    "HmSystemHealthSensor",
    "MetricsDpType",
    # Program
    "ProgramDpButton",
    "ProgramDpSwitch",
    "ProgramDpType",
    # Sysvar
    "SysvarDpBinarySensor",
    "SysvarDpNumber",
    "SysvarDpSelect",
    "SysvarDpSensor",
    "SysvarDpSwitch",
    "SysvarDpText",
    # Update
    "HmUpdate",
]
