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
   is published with a categorized mapping of the new points for consumers.

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
  a mapping, so subscribers can subscribe and present them appropriately.

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

from aiohomematic.const import (
    HUB_CATEGORIES,
    Backend,
    BackendSystemEvent,
    DataPointCategory,
    HubValueType,
    InstallModeData,
    Interface,
    ProgramData,
    ServiceScope,
    SystemVariableData,
)
from aiohomematic.decorators import inspector
from aiohomematic.interfaces.central import (
    CentralInfo,
    ChannelLookup,
    ConfigProvider,
    EventBusProvider,
    EventPublisher,
    HubDataFetcher,
    HubDataPointManager,
)
from aiohomematic.interfaces.client import ClientProvider, PrimaryClientProvider
from aiohomematic.interfaces.model import GenericHubDataPointProtocol, HubProtocol
from aiohomematic.interfaces.operations import ParameterVisibilityProvider, ParamsetDescriptionProvider, TaskScheduler
from aiohomematic.model.hub.binary_sensor import SysvarDpBinarySensor
from aiohomematic.model.hub.button import ProgramDpButton
from aiohomematic.model.hub.data_point import GenericHubDataPoint, GenericProgramDataPoint, GenericSysvarDataPoint
from aiohomematic.model.hub.inbox import HmInboxSensor
from aiohomematic.model.hub.install_mode import InstallModeDpButton, InstallModeDpSensor, InstallModeDpType
from aiohomematic.model.hub.number import SysvarDpNumber
from aiohomematic.model.hub.select import SysvarDpSelect
from aiohomematic.model.hub.sensor import SysvarDpSensor
from aiohomematic.model.hub.switch import ProgramDpSwitch, SysvarDpSwitch
from aiohomematic.model.hub.text import SysvarDpText
from aiohomematic.model.hub.update import HmUpdate

__all__ = [
    "GenericHubDataPoint",
    "GenericProgramDataPoint",
    "GenericSysvarDataPoint",
    "HmInboxSensor",
    "HmUpdate",
    "Hub",
    "InstallModeDpButton",
    "InstallModeDpSensor",
    "InstallModeDpType",
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


class Hub(HubProtocol):
    """The Homematic hub."""

    __slots__ = (
        "_central_info",
        "_channel_lookup",
        "_client_provider",
        "_config_provider",
        "_event_bus_provider",
        "_event_publisher",
        "_hub_data_fetcher",
        "_hub_data_point_manager",
        "_inbox_dp",
        "_install_mode_dps",
        "_parameter_visibility_provider",
        "_paramset_description_provider",
        "_primary_client_provider",
        "_sema_fetch_inbox",
        "_sema_fetch_programs",
        "_sema_fetch_sysvars",
        "_sema_fetch_update",
        "_task_scheduler",
        "_update_dp",
    )

    def __init__(
        self,
        *,
        config_provider: ConfigProvider,
        central_info: CentralInfo,
        client_provider: ClientProvider,
        hub_data_point_manager: HubDataPointManager,
        primary_client_provider: PrimaryClientProvider,
        event_publisher: EventPublisher,
        event_bus_provider: EventBusProvider,
        task_scheduler: TaskScheduler,
        paramset_description_provider: ParamsetDescriptionProvider,
        parameter_visibility_provider: ParameterVisibilityProvider,
        channel_lookup: ChannelLookup,
        hub_data_fetcher: HubDataFetcher,
    ) -> None:
        """Initialize Homematic hub."""
        self._sema_fetch_sysvars: Final = asyncio.Semaphore()
        self._sema_fetch_programs: Final = asyncio.Semaphore()
        self._sema_fetch_update: Final = asyncio.Semaphore()
        self._sema_fetch_inbox: Final = asyncio.Semaphore()
        self._config_provider: Final = config_provider
        self._central_info: Final = central_info
        self._client_provider: Final = client_provider
        self._hub_data_point_manager: Final = hub_data_point_manager
        self._primary_client_provider: Final = primary_client_provider
        self._event_publisher: Final = event_publisher
        self._event_bus_provider: Final = event_bus_provider
        self._task_scheduler: Final = task_scheduler
        self._paramset_description_provider: Final = paramset_description_provider
        self._parameter_visibility_provider: Final = parameter_visibility_provider
        self._channel_lookup: Final = channel_lookup
        self._hub_data_fetcher: Final = hub_data_fetcher
        self._update_dp: HmUpdate | None = None
        self._inbox_dp: HmInboxSensor | None = None
        self._install_mode_dps: dict[Interface, InstallModeDpType] = {}

    @property
    def inbox_dp(self) -> HmInboxSensor | None:
        """Return the inbox data point."""
        return self._inbox_dp

    @property
    def install_mode_dps(self) -> Mapping[Interface, InstallModeDpType]:
        """Return the install mode data points by interface."""
        return self._install_mode_dps

    @property
    def update_dp(self) -> HmUpdate | None:
        """Return the system update data point."""
        return self._update_dp

    def create_install_mode_dps(self) -> Mapping[Interface, InstallModeDpType]:
        """
        Create install mode data points for all supported interfaces.

        Returns a dict of InstallModeDpType by Interface.
        """
        if self._install_mode_dps:
            return self._install_mode_dps

        # Check which interfaces support install mode
        for interface in (Interface.BIDCOS_RF, Interface.HMIP_RF):
            if self._create_install_mode_dp_for_interface(interface=interface):
                _LOGGER.debug(
                    "CREATE_INSTALL_MODE_DPS: Created install mode data points for %s",
                    interface,
                )

        return self._install_mode_dps

    @inspector(re_raise=False, scope=ServiceScope.INTERNAL)
    async def fetch_inbox_data(self, *, scheduled: bool) -> None:
        """Fetch inbox data for the hub."""
        if self._central_info.model is not Backend.CCU:
            return
        _LOGGER.debug(
            "FETCH_INBOX_DATA: %s fetching of inbox for %s",
            "Scheduled" if scheduled else "Manual",
            self._central_info.name,
        )
        async with self._sema_fetch_inbox:
            if self._central_info.available:
                await self._update_inbox_data_point()

    @inspector(re_raise=False, scope=ServiceScope.INTERNAL)
    async def fetch_install_mode_data(self, *, scheduled: bool) -> None:
        """Fetch install mode data from the backend for all interfaces."""
        if not self._install_mode_dps:
            return
        _LOGGER.debug(
            "FETCH_INSTALL_MODE_DATA: %s fetching of install mode for %s",
            "Scheduled" if scheduled else "Manual",
            self._central_info.name,
        )
        if not self._central_info.available:
            return

        # Fetch install mode for each interface using the appropriate client
        for interface, install_mode_dp in self._install_mode_dps.items():
            try:
                client = self._client_provider.get_client(interface=interface)
                remaining_seconds = await client.get_install_mode()
                install_mode_dp.sensor.sync_from_backend(remaining_seconds=remaining_seconds)
            except Exception:  # noqa: BLE001
                _LOGGER.debug(
                    "FETCH_INSTALL_MODE_DATA: No client available for interface %s",
                    interface,
                )

    @inspector(re_raise=False)
    async def fetch_program_data(self, *, scheduled: bool) -> None:
        """Fetch program data for the hub."""
        if self._config_provider.config.enable_program_scan:
            _LOGGER.debug(
                "FETCH_PROGRAM_DATA: %s fetching of programs for %s",
                "Scheduled" if scheduled else "Manual",
                self._central_info.name,
            )
            async with self._sema_fetch_programs:
                if self._central_info.available:
                    await self._update_program_data_points()

    @inspector(re_raise=False, scope=ServiceScope.INTERNAL)
    async def fetch_system_update_data(self, *, scheduled: bool) -> None:
        """Fetch system update data for the hub."""
        if self._central_info.model is not Backend.CCU:
            return
        _LOGGER.debug(
            "FETCH_SYSTEM_UPDATE_DATA: %s fetching of system update info for %s",
            "Scheduled" if scheduled else "Manual",
            self._central_info.name,
        )
        async with self._sema_fetch_update:
            if self._central_info.available:
                await self._update_system_update_data_point()

    @inspector(re_raise=False)
    async def fetch_sysvar_data(self, *, scheduled: bool) -> None:
        """Fetch sysvar data for the hub."""
        if self._config_provider.config.enable_sysvar_scan:
            _LOGGER.debug(
                "FETCH_SYSVAR_DATA: %s fetching of system variables for %s",
                "Scheduled" if scheduled else "Manual",
                self._central_info.name,
            )
            async with self._sema_fetch_sysvars:
                if self._central_info.available:
                    await self._update_sysvar_data_points()

    async def init_install_mode(self) -> Mapping[Interface, InstallModeDpType]:
        """
        Initialize install mode data points for all supported interfaces.

        Creates data points, fetches initial state from backend, and publishes refresh event.
        Returns a dict of InstallModeDpType by Interface.
        """
        if not (install_mode_dps := self.create_install_mode_dps()):
            return {}

        # Fetch initial state from backend
        await self.fetch_install_mode_data(scheduled=False)

        # Publish refresh event to notify consumers
        self.publish_install_mode_refreshed()

        return install_mode_dps

    def publish_install_mode_refreshed(self) -> None:
        """Publish HUB_REFRESHED event for install mode data points."""
        if not self._install_mode_dps:
            return
        data_points: list[GenericHubDataPointProtocol] = []
        for install_mode_dp in self._install_mode_dps.values():
            data_points.append(install_mode_dp.button)
            data_points.append(install_mode_dp.sensor)

        self._event_publisher.publish_backend_system_event(
            system_event=BackendSystemEvent.HUB_REFRESHED,
            new_data_points=_get_new_hub_data_points(data_points=data_points),
        )

    def _create_install_mode_dp_for_interface(self, *, interface: Interface) -> InstallModeDpType | None:
        """Create install mode data points for a specific interface."""
        if interface in self._install_mode_dps:
            return self._install_mode_dps[interface]

        # Check if a client exists for this specific interface and supports install mode
        client = next(
            (c for c in self._client_provider.clients if c.interface == interface and c.supports_install_mode),
            None,
        )
        if not client:
            return None

        # Create interface-specific parameter names (used for unique_id generation)
        # The unique_id will be: install_mode_<suffix> where INSTALL_MODE_ADDRESS is the base
        interface_suffix = "hmip" if interface == Interface.HMIP_RF else "bidcos"
        sensor_parameter = interface_suffix
        button_parameter = f"{interface_suffix}_button"

        sensor = InstallModeDpSensor(
            data=InstallModeData(name=sensor_parameter, interface=interface),
            central_info=self._central_info,
            channel_lookup=self._channel_lookup,
            config_provider=self._config_provider,
            event_bus_provider=self._event_bus_provider,
            event_publisher=self._event_publisher,
            parameter_visibility_provider=self._parameter_visibility_provider,
            paramset_description_provider=self._paramset_description_provider,
            primary_client_provider=self._primary_client_provider,
            task_scheduler=self._task_scheduler,
        )
        button = InstallModeDpButton(
            sensor=sensor,
            data=InstallModeData(name=button_parameter, interface=interface),
            central_info=self._central_info,
            channel_lookup=self._channel_lookup,
            config_provider=self._config_provider,
            event_bus_provider=self._event_bus_provider,
            event_publisher=self._event_publisher,
            parameter_visibility_provider=self._parameter_visibility_provider,
            paramset_description_provider=self._paramset_description_provider,
            primary_client_provider=self._primary_client_provider,
            task_scheduler=self._task_scheduler,
        )

        install_mode_dp = InstallModeDpType(button=button, sensor=sensor)
        self._install_mode_dps[interface] = install_mode_dp
        return install_mode_dp

    def _create_program_dp(self, *, data: ProgramData) -> ProgramDpType:
        """Create program as data_point."""
        program_dp = ProgramDpType(
            pid=data.pid,
            button=ProgramDpButton(
                config_provider=self._config_provider,
                central_info=self._central_info,
                event_bus_provider=self._event_bus_provider,
                event_publisher=self._event_publisher,
                task_scheduler=self._task_scheduler,
                paramset_description_provider=self._paramset_description_provider,
                parameter_visibility_provider=self._parameter_visibility_provider,
                channel_lookup=self._channel_lookup,
                primary_client_provider=self._primary_client_provider,
                hub_data_fetcher=self._hub_data_fetcher,
                data=data,
            ),
            switch=ProgramDpSwitch(
                config_provider=self._config_provider,
                central_info=self._central_info,
                event_bus_provider=self._event_bus_provider,
                event_publisher=self._event_publisher,
                task_scheduler=self._task_scheduler,
                paramset_description_provider=self._paramset_description_provider,
                parameter_visibility_provider=self._parameter_visibility_provider,
                channel_lookup=self._channel_lookup,
                primary_client_provider=self._primary_client_provider,
                hub_data_fetcher=self._hub_data_fetcher,
                data=data,
            ),
        )
        self._hub_data_point_manager.add_program_data_point(program_dp=program_dp)
        return program_dp

    def _create_system_variable(self, *, data: SystemVariableData) -> GenericSysvarDataPoint:
        """Create system variable as data_point."""
        sysvar_dp = self._create_sysvar_data_point(data=data)
        self._hub_data_point_manager.add_sysvar_data_point(sysvar_data_point=sysvar_dp)
        return sysvar_dp

    def _create_sysvar_data_point(self, *, data: SystemVariableData) -> GenericSysvarDataPoint:
        """Create sysvar data_point."""
        data_type = data.data_type
        extended_sysvar = data.extended_sysvar
        # Common protocol interfaces for all sysvar data points
        protocols = {
            "config_provider": self._config_provider,
            "central_info": self._central_info,
            "event_bus_provider": self._event_bus_provider,
            "event_publisher": self._event_publisher,
            "task_scheduler": self._task_scheduler,
            "paramset_description_provider": self._paramset_description_provider,
            "parameter_visibility_provider": self._parameter_visibility_provider,
            "channel_lookup": self._channel_lookup,
            "primary_client_provider": self._primary_client_provider,
            "data": data,
        }
        if data_type:
            if data_type in (HubValueType.ALARM, HubValueType.LOGIC):
                if extended_sysvar:
                    return SysvarDpSwitch(**protocols)  # type: ignore[arg-type]
                return SysvarDpBinarySensor(**protocols)  # type: ignore[arg-type]
            if data_type == HubValueType.LIST and extended_sysvar:
                return SysvarDpSelect(**protocols)  # type: ignore[arg-type]
            if data_type in (HubValueType.FLOAT, HubValueType.INTEGER) and extended_sysvar:
                return SysvarDpNumber(**protocols)  # type: ignore[arg-type]
            if data_type == HubValueType.STRING and extended_sysvar:
                return SysvarDpText(**protocols)  # type: ignore[arg-type]

        return SysvarDpSensor(**protocols)  # type: ignore[arg-type]

    def _identify_missing_program_ids(self, *, programs: tuple[ProgramData, ...]) -> set[str]:
        """Identify missing programs."""
        return {
            dp.pid for dp in self._hub_data_point_manager.program_data_points if dp.pid not in [x.pid for x in programs]
        }

    def _identify_missing_variable_ids(self, *, variables: tuple[SystemVariableData, ...]) -> set[str]:
        """Identify missing variables."""
        variable_ids: dict[str, bool] = {x.vid: x.extended_sysvar for x in variables}
        missing_variable_ids: list[str] = []
        for dp in self._hub_data_point_manager.sysvar_data_points:
            if dp.data_type == HubValueType.STRING:
                continue
            if (vid := dp.vid) is not None and (
                vid not in variable_ids or (dp.is_extended is not variable_ids.get(vid))
            ):
                missing_variable_ids.append(vid)
        return set(missing_variable_ids)

    def _remove_program_data_point(self, *, ids: set[str]) -> None:
        """Remove sysvar data_point from hub."""
        for pid in ids:
            self._hub_data_point_manager.remove_program_button(pid=pid)

    def _remove_sysvar_data_point(self, *, del_data_point_ids: set[str]) -> None:
        """Remove sysvar data_point from hub."""
        for vid in del_data_point_ids:
            self._hub_data_point_manager.remove_sysvar_data_point(vid=vid)

    async def _update_inbox_data_point(self) -> None:
        """Retrieve inbox devices and update the data point."""
        if not (client := self._primary_client_provider.primary_client):
            return

        devices = await client.get_inbox_devices()
        is_new = False

        if self._inbox_dp is None:
            self._inbox_dp = HmInboxSensor(
                config_provider=self._config_provider,
                central_info=self._central_info,
                event_bus_provider=self._event_bus_provider,
                event_publisher=self._event_publisher,
                task_scheduler=self._task_scheduler,
                paramset_description_provider=self._paramset_description_provider,
                parameter_visibility_provider=self._parameter_visibility_provider,
            )
            is_new = True

        self._inbox_dp.update_data(devices=devices, write_at=datetime.now())

        if is_new:
            self._event_publisher.publish_backend_system_event(
                system_event=BackendSystemEvent.HUB_REFRESHED,
                new_data_points=_get_new_hub_data_points(data_points=[self._inbox_dp]),
            )

    async def _update_program_data_points(self) -> None:
        """Retrieve all program data and update program values."""
        if not (client := self._primary_client_provider.primary_client):
            return
        if not (programs := await client.get_all_programs(markers=self._config_provider.config.program_markers)):
            _LOGGER.debug("UPDATE_PROGRAM_DATA_POINTS: Unable to retrieve programs for %s", self._central_info.name)
            return

        _LOGGER.debug(
            "UPDATE_PROGRAM_DATA_POINTS: %i programs received for %s",
            len(programs),
            self._central_info.name,
        )

        if missing_program_ids := self._identify_missing_program_ids(programs=programs):
            self._remove_program_data_point(ids=missing_program_ids)

        new_programs: list[GenericProgramDataPoint] = []

        for program_data in programs:
            if program_dp := self._hub_data_point_manager.get_program_data_point(pid=program_data.pid):
                program_dp.button.update_data(data=program_data)
                program_dp.switch.update_data(data=program_data)
            else:
                program_dp = self._create_program_dp(data=program_data)
                new_programs.append(program_dp.button)
                new_programs.append(program_dp.switch)

        if new_programs:
            self._event_publisher.publish_backend_system_event(
                system_event=BackendSystemEvent.HUB_REFRESHED,
                new_data_points=_get_new_hub_data_points(data_points=new_programs),
            )

    async def _update_system_update_data_point(self) -> None:
        """
        Retrieve system update info and update the data point.

        Only supported on OpenCCU.
        """
        if not (client := self._primary_client_provider.primary_client):
            return

        # Only supported on OpenCCU
        if not client.system_information.supports_backup:
            return

        if (update_data := await client.get_system_update_info()) is None:
            _LOGGER.debug(
                "UPDATE_SYSTEM_UPDATE_DATA_POINT: Unable to retrieve system update info for %s",
                self._central_info.name,
            )
            return

        is_new = False

        if self._update_dp is None:
            self._update_dp = HmUpdate(
                config_provider=self._config_provider,
                central_info=self._central_info,
                event_bus_provider=self._event_bus_provider,
                event_publisher=self._event_publisher,
                task_scheduler=self._task_scheduler,
                paramset_description_provider=self._paramset_description_provider,
                parameter_visibility_provider=self._parameter_visibility_provider,
                primary_client_provider=self._primary_client_provider,
            )
            is_new = True

        self._update_dp.update_data(data=update_data, write_at=datetime.now())

        if is_new:
            self._event_publisher.publish_backend_system_event(
                system_event=BackendSystemEvent.HUB_REFRESHED,
                new_data_points=_get_new_hub_data_points(data_points=[self._update_dp]),
            )

    async def _update_sysvar_data_points(self) -> None:
        """Retrieve all variable data and update hmvariable values."""
        if not (client := self._primary_client_provider.primary_client):
            return
        if (
            variables := await client.get_all_system_variables(markers=self._config_provider.config.sysvar_markers)
        ) is None:
            _LOGGER.debug("UPDATE_SYSVAR_DATA_POINTS: Unable to retrieve sysvars for %s", self._central_info.name)
            return

        _LOGGER.debug(
            "UPDATE_SYSVAR_DATA_POINTS: %i sysvars received for %s",
            len(variables),
            self._central_info.name,
        )

        # remove some variables in case of CCU backend
        # - OldValue(s) are for internal calculations
        if self._central_info.model is Backend.CCU:
            variables = _clean_variables(variables=variables)

        if missing_variable_ids := self._identify_missing_variable_ids(variables=variables):
            self._remove_sysvar_data_point(del_data_point_ids=missing_variable_ids)

        new_sysvars: list[GenericSysvarDataPoint] = []

        for sysvar in variables:
            if dp := self._hub_data_point_manager.get_sysvar_data_point(vid=sysvar.vid):
                dp.write_value(value=sysvar.value, write_at=datetime.now())
            else:
                new_sysvars.append(self._create_system_variable(data=sysvar))

        if new_sysvars:
            self._event_publisher.publish_backend_system_event(
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
    data_points: Collection[GenericHubDataPointProtocol],
) -> Mapping[DataPointCategory, AbstractSet[GenericHubDataPointProtocol]]:
    """Return data points as category dict."""
    hub_data_points: dict[DataPointCategory, set[GenericHubDataPointProtocol]] = {}
    for hub_category in HUB_CATEGORIES:
        hub_data_points[hub_category] = set()

    for dp in data_points:
        if dp.is_registered is False:
            hub_data_points[dp.category].add(dp)

    return hub_data_points
