"""Module for HaHomematic hub data points."""

from __future__ import annotations

import asyncio
from collections.abc import Collection, Mapping, Set as AbstractSet
import logging
from typing import Final, NamedTuple

from hahomematic import central as hmcu
from hahomematic.const import (
    HUB_CATEGORIES,
    Backend,
    BackendSystemEvent,
    DataPointCategory,
    ProgramData,
    SystemVariableData,
    SysvarType,
)
from hahomematic.decorators import service
from hahomematic.model.hub.binary_sensor import SysvarDpBinarySensor
from hahomematic.model.hub.button import ProgramDpButton
from hahomematic.model.hub.data_point import GenericHubDataPoint, GenericProgramDataPoint, GenericSysvarDataPoint
from hahomematic.model.hub.number import SysvarDpNumber
from hahomematic.model.hub.select import SysvarDpSelect
from hahomematic.model.hub.sensor import SysvarDpSensor
from hahomematic.model.hub.switch import ProgramDpSwitch, SysvarDpSwitch
from hahomematic.model.hub.text import SysvarDpText

__all__ = [
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
    """The HomeMatic hub. (CCU/HomeGear)."""

    def __init__(self, central: hmcu.CentralUnit) -> None:
        """Initialize HomeMatic hub."""
        self._sema_fetch_sysvars: Final = asyncio.Semaphore()
        self._sema_fetch_programs: Final = asyncio.Semaphore()
        self._central: Final = central
        self._config: Final = central.config

    @service(re_raise=False)
    async def fetch_sysvar_data(self, scheduled: bool) -> None:
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

    @service(re_raise=False)
    async def fetch_program_data(self, scheduled: bool) -> None:
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

    async def _update_program_data_points(self) -> None:
        """Retrieve all program data and update program values."""
        programs: tuple[ProgramData, ...] = ()
        if not (client := self._central.primary_client):
            return
        programs = await client.get_all_programs(markers=self._config.program_markers)

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
            self._central.fire_backend_system_callback(
                system_event=BackendSystemEvent.HUB_REFRESHED,
                new_hub_data_points=_get_new_hub_data_points(data_points=new_programs),
            )

    async def _update_sysvar_data_points(self) -> None:
        """Retrieve all variable data and update hmvariable values."""
        variables: tuple[SystemVariableData, ...] = ()
        if not (client := self._central.primary_client):
            return
        variables = await client.get_all_system_variables(markers=self._config.sysvar_markers)

        _LOGGER.debug(
            "UPDATE_SYSVAR_DATA_POINTS: %i sysvars received for %s",
            len(variables),
            self._central.name,
        )

        # remove some variables in case of CCU Backend
        # - OldValue(s) are for internal calculations
        if self._central.model is Backend.CCU:
            variables = _clean_variables(variables)

        if missing_variable_names := self._identify_missing_variable_names(variables=variables):
            self._remove_sysvar_data_point(del_data_points=missing_variable_names)

        new_sysvars: list[GenericSysvarDataPoint] = []

        for sysvar in variables:
            name = sysvar.name
            value = sysvar.value

            if dp := self._central.get_sysvar_data_point(name=name):
                dp.write_value(value)
            else:
                new_sysvars.append(self._create_system_variable(data=sysvar))

        if new_sysvars:
            self._central.fire_backend_system_callback(
                system_event=BackendSystemEvent.HUB_REFRESHED,
                new_hub_data_points=_get_new_hub_data_points(data_points=new_sysvars),
            )

    def _create_program_dp(self, data: ProgramData) -> ProgramDpType:
        """Create program as data_point."""
        program_dp = ProgramDpType(
            pid=data.pid,
            button=ProgramDpButton(central=self._central, data=data),
            switch=ProgramDpSwitch(central=self._central, data=data),
        )
        self._central.add_program_data_point(program_dp=program_dp)
        return program_dp

    def _create_system_variable(self, data: SystemVariableData) -> GenericSysvarDataPoint:
        """Create system variable as data_point."""
        sysvar_dp = self._create_sysvar_data_point(data=data)
        self._central.add_sysvar_data_point(sysvar_data_point=sysvar_dp)
        return sysvar_dp

    def _create_sysvar_data_point(self, data: SystemVariableData) -> GenericSysvarDataPoint:
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

    def _remove_program_data_point(self, ids: set[str]) -> None:
        """Remove sysvar data_point from hub."""
        for pid in ids:
            self._central.remove_program_button(pid=pid)

    def _remove_sysvar_data_point(self, del_data_points: set[str]) -> None:
        """Remove sysvar data_point from hub."""
        for name in del_data_points:
            self._central.remove_sysvar_data_point(name=name)

    def _identify_missing_program_ids(self, programs: tuple[ProgramData, ...]) -> set[str]:
        """Identify missing programs."""
        return {
            program_dp.pid
            for program_dp in self._central.program_data_points
            if program_dp.pid not in [x.pid for x in programs]
        }

    def _identify_missing_variable_names(self, variables: tuple[SystemVariableData, ...]) -> set[str]:
        """Identify missing variables."""
        variable_names: dict[str, bool] = {x.name: x.extended_sysvar for x in variables}
        missing_variables: list[str] = []
        for sysvar_data_point in self._central.sysvar_data_points:
            if sysvar_data_point.data_type == SysvarType.STRING:
                continue
            if (name := sysvar_data_point.name) is not None and (
                name not in variable_names or (sysvar_data_point.is_extended is not variable_names.get(name))
            ):
                missing_variables.append(name)
        return set(missing_variables)


def _is_excluded(variable: str, excludes: list[str]) -> bool:
    """Check if variable is excluded by exclude_list."""
    return any(marker in variable for marker in excludes)


def _clean_variables(variables: tuple[SystemVariableData, ...]) -> tuple[SystemVariableData, ...]:
    """Clean variables by removing excluded."""
    return tuple(sv for sv in variables if not _is_excluded(sv.name, _EXCLUDED))


def _get_new_hub_data_points(
    data_points: Collection[GenericHubDataPoint],
) -> Mapping[DataPointCategory, AbstractSet[GenericHubDataPoint]]:
    """Return data points as category dict."""
    hub_data_points: dict[DataPointCategory, set[GenericHubDataPoint]] = {}
    for hub_category in HUB_CATEGORIES:
        hub_data_points[hub_category] = set()

    for data_point in data_points:
        if data_point.is_registered is False:
            hub_data_points[data_point.category].add(data_point)

    return hub_data_points
