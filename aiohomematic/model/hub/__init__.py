# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Hub (backend) data points for AioHomematic.

Overview
- This module reflects the state and capabilities of the backend
  at the hub level. It exposes backend programs and system variables as data
  points that can be observed and acted upon by higher layers (e.g.,
  integrations).

Responsibilities
- Fetch current lists of programs and system variables from the central unit.
- Create and maintain concrete hub data point instances for those items.
- Keep hub data points in sync with the backend (update values, add/remove).
- Notify the system about newly created hub data points via backend events.

Public API (selected)
- Hub: Orchestrates scanning and synchronization of hub-level data points.
- ProgramDpButton / ProgramDpSwitch: Represent a backend program as an
  invocable button or a switch-like control, respectively.
- Sysvar data points: Map system variables to appropriate types:
  - SysvarDpSensor, SysvarDpBinarySensor, SysvarDpSelect, SysvarDpNumber,
    SysvarDpSwitch, SysvarDpText.
- __all__: Exposes the classes and types intended for external consumption.

Lifecycle and Flow
1. fetch_program_data / fetch_sysvar_data (async) are scheduled or triggered
   manually depending on configuration and availability of the central unit.
2. On fetch:
   - The module retrieves program/sysvar lists from the primary client.
   - It identifies removed items and cleans up corresponding data points.
   - It updates existing data points or creates new ones as needed.
3. For newly created hub data points, a BackendSystemEvent.HUB_REFRESHED event
   is emitted with a categorized mapping of the new points for consumers.

Type Mapping for System Variables
- Based on SysvarType and the extended_sysvar flag, system variables are
  represented by the most suitable hub data point class. For example:
  - ALARM/LOGIC → binary_sensor or switch (if extended)
  - LIST (extended) → select
  - FLOAT/INTEGER (extended) → number
  - STRING (extended) → text
  - Any other case → generic sensor

Concurrency and Reliability
- Fetch operations are protected by semaphores to avoid concurrent updates of
  the same kind (programs or sysvars).
- The inspector decorator helps ensure exceptions do not propagate unexpectedly
  when fetching; errors are logged and the system continues operating.

Backend Specifics and Cleanup
- For CCU backends, certain internal variables (e.g., legacy "OldVal*",
  "pcCCUID") are filtered out to avoid exposing irrelevant state.

Categories and New Data Point Discovery
- Newly created hub data points are grouped into HUB_CATEGORIES and returned as
  a mapping, so subscribers can register and present them appropriately.

Related Modules
- aiohomematic.model.hub.data_point: Base types for hub-level data points.
- aiohomematic.central: Central unit coordination and backend communication.
- aiohomematic.const: Shared constants, enums, and data structures.

Example:
- Typical usage occurs inside the central unit scheduling:
    hub = Hub(central)
    await hub.fetch_program_data(scheduled=True)
    await hub.fetch_sysvar_data(scheduled=True)

This module complements device/channel data points by reflecting control center
state and enabling automations at the backend level.

"""

from __future__ import annotations

import asyncio
from collections.abc import Collection, Mapping, Set as AbstractSet
from datetime import datetime
import logging
from typing import Final, NamedTuple

from aiohomematic import central as hmcu
from aiohomematic.const import (
    HUB_CATEGORIES,
    Backend,
    BackendSystemEvent,
    DataPointCategory,
    ProgramData,
    SystemVariableData,
    SysvarType,
)
from aiohomematic.decorators import inspector
from aiohomematic.model.hub.binary_sensor import SysvarDpBinarySensor
from aiohomematic.model.hub.button import ProgramDpButton
from aiohomematic.model.hub.data_point import GenericHubDataPoint, GenericProgramDataPoint, GenericSysvarDataPoint
from aiohomematic.model.hub.number import SysvarDpNumber
from aiohomematic.model.hub.select import SysvarDpSelect
from aiohomematic.model.hub.sensor import SysvarDpSensor
from aiohomematic.model.hub.switch import ProgramDpSwitch, SysvarDpSwitch
from aiohomematic.model.hub.text import SysvarDpText

__all__ = [
    "GenericHubDataPoint",
    "GenericProgramDataPoint",
    "GenericSysvarDataPoint",
    "Hub",
    "ProgramDpButton",
    "ProgramDpSwitch",
    "ProgramDpType",
    "SysvarDpBinarySensor",
    "SysvarDpNumber",
    "SysvarDpSelect",
    "SysvarDpSensor",
    "SysvarDpSwitch",
    "SysvarDpText",
]

_LOGGER: Final = logging.getLogger(__name__)

_EXCLUDED: Final = [
    "OldVal",
    "pcCCUID",
]


class ProgramDpType(NamedTuple):
    """Key for data points."""

    pid: str
    button: ProgramDpButton
    switch: ProgramDpSwitch


class Hub:
    """The Homematic hub."""

    __slots__ = (
        "_sema_fetch_sysvars",
        "_sema_fetch_programs",
        "_central",
        "_config",
    )

    def __init__(self, *, central: hmcu.CentralUnit) -> None:
        """Initialize Homematic hub."""
        self._sema_fetch_sysvars: Final = asyncio.Semaphore()
        self._sema_fetch_programs: Final = asyncio.Semaphore()
        self._central: Final = central
        self._config: Final = central.config

    @inspector(re_raise=False)
    async def fetch_program_data(self, *, scheduled: bool) -> None:
        """Fetch program data for the hub."""
        if self._config.enable_program_scan:
            _LOGGER.debug(
                "FETCH_PROGRAM_DATA: %s fetching of programs for %s",
                "Scheduled" if scheduled else "Manual",
                self._central.name,
            )
            async with self._sema_fetch_programs:
                if self._central.available:
                    await self._update_program_data_points()

    @inspector(re_raise=False)
    async def fetch_sysvar_data(self, *, scheduled: bool) -> None:
        """Fetch sysvar data for the hub."""
        if self._config.enable_sysvar_scan:
            _LOGGER.debug(
                "FETCH_SYSVAR_DATA: %s fetching of system variables for %s",
                "Scheduled" if scheduled else "Manual",
                self._central.name,
            )
            async with self._sema_fetch_sysvars:
                if self._central.available:
                    await self._update_sysvar_data_points()

    def _create_program_dp(self, *, data: ProgramData) -> ProgramDpType:
        """Create program as data_point."""
        program_dp = ProgramDpType(
            pid=data.pid,
            button=ProgramDpButton(central=self._central, data=data),
            switch=ProgramDpSwitch(central=self._central, data=data),
        )
        self._central.add_program_data_point(program_dp=program_dp)
        return program_dp

    def _create_system_variable(self, *, data: SystemVariableData) -> GenericSysvarDataPoint:
        """Create system variable as data_point."""
        sysvar_dp = self._create_sysvar_data_point(data=data)
        self._central.add_sysvar_data_point(sysvar_data_point=sysvar_dp)
        return sysvar_dp

    def _create_sysvar_data_point(self, *, data: SystemVariableData) -> GenericSysvarDataPoint:
        """Create sysvar data_point."""
        data_type = data.data_type
        extended_sysvar = data.extended_sysvar
        if data_type:
            if data_type in (SysvarType.ALARM, SysvarType.LOGIC):
                if extended_sysvar:
                    return SysvarDpSwitch(central=self._central, data=data)
                return SysvarDpBinarySensor(central=self._central, data=data)
            if data_type == SysvarType.LIST and extended_sysvar:
                return SysvarDpSelect(central=self._central, data=data)
            if data_type in (SysvarType.FLOAT, SysvarType.INTEGER) and extended_sysvar:
                return SysvarDpNumber(central=self._central, data=data)
            if data_type == SysvarType.STRING and extended_sysvar:
                return SysvarDpText(central=self._central, data=data)

        return SysvarDpSensor(central=self._central, data=data)

    def _identify_missing_program_ids(self, *, programs: tuple[ProgramData, ...]) -> set[str]:
        """Identify missing programs."""
        return {dp.pid for dp in self._central.program_data_points if dp.pid not in [x.pid for x in programs]}

    def _identify_missing_variable_ids(self, *, variables: tuple[SystemVariableData, ...]) -> set[str]:
        """Identify missing variables."""
        variable_ids: dict[str, bool] = {x.vid: x.extended_sysvar for x in variables}
        missing_variable_ids: list[str] = []
        for dp in self._central.sysvar_data_points:
            if dp.data_type == SysvarType.STRING:
                continue
            if (vid := dp.vid) is not None and (
                vid not in variable_ids or (dp.is_extended is not variable_ids.get(vid))
            ):
                missing_variable_ids.append(vid)
        return set(missing_variable_ids)

    def _remove_program_data_point(self, *, ids: set[str]) -> None:
        """Remove sysvar data_point from hub."""
        for pid in ids:
            self._central.remove_program_button(pid=pid)

    def _remove_sysvar_data_point(self, *, del_data_point_ids: set[str]) -> None:
        """Remove sysvar data_point from hub."""
        for vid in del_data_point_ids:
            self._central.remove_sysvar_data_point(vid=vid)

    async def _update_program_data_points(self) -> None:
        """Retrieve all program data and update program values."""
        if not (client := self._central.primary_client):
            return
        if (programs := await client.get_all_programs(markers=self._config.program_markers)) is None:
            _LOGGER.debug("UPDATE_PROGRAM_DATA_POINTS: Unable to retrieve programs for %s", self._central.name)
            return

        _LOGGER.debug(
            "UPDATE_PROGRAM_DATA_POINTS: %i programs received for %s",
            len(programs),
            self._central.name,
        )

        if missing_program_ids := self._identify_missing_program_ids(programs=programs):
            self._remove_program_data_point(ids=missing_program_ids)

        new_programs: list[GenericProgramDataPoint] = []

        for program_data in programs:
            if program_dp := self._central.get_program_data_point(pid=program_data.pid):
                program_dp.button.update_data(data=program_data)
                program_dp.switch.update_data(data=program_data)
            else:
                program_dp = self._create_program_dp(data=program_data)
                new_programs.append(program_dp.button)
                new_programs.append(program_dp.switch)

        if new_programs:
            self._central.emit_backend_system_callback(
                system_event=BackendSystemEvent.HUB_REFRESHED,
                new_data_points=_get_new_hub_data_points(data_points=new_programs),
            )

    async def _update_sysvar_data_points(self) -> None:
        """Retrieve all variable data and update hmvariable values."""
        if not (client := self._central.primary_client):
            return
        if (variables := await client.get_all_system_variables(markers=self._config.sysvar_markers)) is None:
            _LOGGER.debug("UPDATE_SYSVAR_DATA_POINTS: Unable to retrieve sysvars for %s", self._central.name)
            return

        _LOGGER.debug(
            "UPDATE_SYSVAR_DATA_POINTS: %i sysvars received for %s",
            len(variables),
            self._central.name,
        )

        # remove some variables in case of CCU backend
        # - OldValue(s) are for internal calculations
        if self._central.model is Backend.CCU:
            variables = _clean_variables(variables=variables)

        if missing_variable_ids := self._identify_missing_variable_ids(variables=variables):
            self._remove_sysvar_data_point(del_data_point_ids=missing_variable_ids)

        new_sysvars: list[GenericSysvarDataPoint] = []

        for sysvar in variables:
            if dp := self._central.get_sysvar_data_point(vid=sysvar.vid):
                dp.write_value(value=sysvar.value, write_at=datetime.now())
            else:
                new_sysvars.append(self._create_system_variable(data=sysvar))

        if new_sysvars:
            self._central.emit_backend_system_callback(
                system_event=BackendSystemEvent.HUB_REFRESHED,
                new_data_points=_get_new_hub_data_points(data_points=new_sysvars),
            )


def _is_excluded(*, variable: str, excludes: list[str]) -> bool:
    """Check if variable is excluded by exclude_list."""
    return any(marker in variable for marker in excludes)


def _clean_variables(*, variables: tuple[SystemVariableData, ...]) -> tuple[SystemVariableData, ...]:
    """Clean variables by removing excluded."""
    return tuple(sv for sv in variables if not _is_excluded(variable=sv.legacy_name, excludes=_EXCLUDED))


def _get_new_hub_data_points(
    *,
    data_points: Collection[GenericHubDataPoint],
) -> Mapping[DataPointCategory, AbstractSet[GenericHubDataPoint]]:
    """Return data points as category dict."""
    hub_data_points: dict[DataPointCategory, set[GenericHubDataPoint]] = {}
    for hub_category in HUB_CATEGORIES:
        hub_data_points[hub_category] = set()

    for dp in data_points:
        if dp.is_registered is False:
            hub_data_points[dp.category].add(dp)

    return hub_data_points
