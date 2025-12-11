# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Hub coordinator for managing programs and system variables.

This module provides centralized management of system-level entities like
programs and system variables that are exposed through the Hub.

The HubCoordinator provides:
- Program data point management
- System variable data point management
- Hub data refresh coordination
- Program execution and state management
"""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any, Final

from aiohomematic import i18n
from aiohomematic.central.event_bus import SysvarUpdatedEvent
from aiohomematic.const import DataPointCategory, Interface
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
from aiohomematic.interfaces.model import GenericProgramDataPointProtocol, GenericSysvarDataPointProtocol
from aiohomematic.interfaces.operations import ParameterVisibilityProvider, ParamsetDescriptionProvider, TaskScheduler
from aiohomematic.model.hub import Hub, InstallModeDpType, ProgramDpType

_LOGGER: Final = logging.getLogger(__name__)


class HubCoordinator(HubDataFetcher, HubDataPointManager):
    """Coordinator for hub-level entities (programs and system variables)."""

    __slots__ = (
        "_central_info",
        "_event_bus_provider",
        "_hub",
        "_primary_client_provider",
        "_program_data_points",
        "_state_path_to_name",
        "_sysvar_data_points",
    )

    def __init__(
        self,
        *,
        central_info: CentralInfo,
        channel_lookup: ChannelLookup,
        client_provider: ClientProvider,
        config_provider: ConfigProvider,
        event_bus_provider: EventBusProvider,
        event_publisher: EventPublisher,
        parameter_visibility_provider: ParameterVisibilityProvider,
        paramset_description_provider: ParamsetDescriptionProvider,
        primary_client_provider: PrimaryClientProvider,
        task_scheduler: TaskScheduler,
    ) -> None:
        """
        Initialize the hub coordinator.

        Args:
        ----
            central_info: Provider for central system information
            channel_lookup: Provider for channel lookup operations
            client_provider: Provider for client access by interface
            config_provider: Provider for configuration access
            event_bus_provider: Provider for event bus access
            event_publisher: Provider for event emission
            parameter_visibility_provider: Provider for parameter visibility rules
            paramset_description_provider: Provider for paramset descriptions
            primary_client_provider: Provider for primary client access
            task_scheduler: Scheduler for async tasks

        """
        self._central_info: Final = central_info
        self._event_bus_provider: Final = event_bus_provider
        self._primary_client_provider: Final = primary_client_provider

        # {sysvar_name, sysvar_data_point}
        self._sysvar_data_points: Final[dict[str, GenericSysvarDataPointProtocol]] = {}
        # {program_name, program_button}
        self._program_data_points: Final[dict[str, ProgramDpType]] = {}
        self._state_path_to_name: Final[dict[str, str]] = {}

        # Create Hub with protocol interfaces
        self._hub: Final = Hub(
            central_info=central_info,
            channel_lookup=channel_lookup,
            client_provider=client_provider,
            config_provider=config_provider,
            event_bus_provider=event_bus_provider,
            event_publisher=event_publisher,
            hub_data_fetcher=self,
            hub_data_point_manager=self,
            parameter_visibility_provider=parameter_visibility_provider,
            paramset_description_provider=paramset_description_provider,
            primary_client_provider=primary_client_provider,
            task_scheduler=task_scheduler,
        )

    @property
    def data_point_paths(self) -> tuple[str, ...]:
        """Return the data point paths."""
        return tuple(self._state_path_to_name.keys())

    @property
    def install_mode_dps(self) -> Mapping[Interface, InstallModeDpType]:
        """Return the install mode data points by interface."""
        return self._hub.install_mode_dps

    @property
    def program_data_points(self) -> tuple[GenericProgramDataPointProtocol, ...]:
        """Return the program data points (both buttons and switches)."""
        return tuple(
            [x.button for x in self._program_data_points.values()]
            + [x.switch for x in self._program_data_points.values()]
        )

    @property
    def sysvar_data_points(self) -> tuple[GenericSysvarDataPointProtocol, ...]:
        """Return the sysvar data points."""
        return tuple(self._sysvar_data_points.values())

    def add_program_data_point(self, *, program_dp: ProgramDpType) -> None:
        """
        Add new program data point.

        Args:
        ----
            program_dp: Program data point to add

        """
        self._program_data_points[program_dp.pid] = program_dp
        self._state_path_to_name[program_dp.button.state_path] = program_dp.pid
        _LOGGER.debug(
            "ADD_PROGRAM_DATA_POINT: Added program %s to %s",
            program_dp.pid,
            self._central_info.name,
        )

    def add_sysvar_data_point(self, *, sysvar_data_point: GenericSysvarDataPointProtocol) -> None:
        """
        Add new system variable data point.

        Args:
        ----
            sysvar_data_point: System variable data point to add

        """
        if (vid := sysvar_data_point.vid) is not None:
            self._sysvar_data_points[vid] = sysvar_data_point
            _LOGGER.debug(
                "ADD_SYSVAR_DATA_POINT: Added sysvar %s to %s",
                vid,
                self._central_info.name,
            )

            self._state_path_to_name[sysvar_data_point.state_path] = sysvar_data_point.vid

            # Add event subscription for this sysvar via EventBus with filtering
            async def event_handler(*, event: SysvarUpdatedEvent) -> None:
                """Filter and handle sysvar events."""
                if event.state_path == sysvar_data_point.state_path:
                    await sysvar_data_point.event(value=event.value, received_at=event.received_at)

            self._event_bus_provider.event_bus.subscribe(
                event_type=SysvarUpdatedEvent, event_key=sysvar_data_point.state_path, handler=event_handler
            )

    def create_install_mode_dps(self) -> Mapping[Interface, InstallModeDpType]:
        """
        Create install mode data points for all supported interfaces.

        Returns a dict of InstallModeDpType by Interface.
        """
        return self._hub.create_install_mode_dps()

    async def execute_program(self, *, pid: str) -> bool:
        """
        Execute a program on the backend.

        Args:
        ----
            pid: Program identifier

        Returns:
        -------
            True if execution succeeded, False otherwise

        """
        if client := self._primary_client_provider.primary_client:
            return await client.execute_program(pid=pid)
        return False

    @inspector(re_raise=False)
    async def fetch_inbox_data(self, *, scheduled: bool) -> None:
        """
        Fetch inbox data from the backend.

        Args:
        ----
            scheduled: Whether this is a scheduled refresh

        """
        await self._hub.fetch_inbox_data(scheduled=scheduled)

    @inspector(re_raise=False)
    async def fetch_install_mode_data(self, *, scheduled: bool) -> None:
        """
        Fetch install mode data from the backend.

        Args:
        ----
            scheduled: Whether this is a scheduled refresh

        """
        await self._hub.fetch_install_mode_data(scheduled=scheduled)

    @inspector(re_raise=False)
    async def fetch_program_data(self, *, scheduled: bool) -> None:
        """
        Fetch program data from the backend.

        Args:
        ----
            scheduled: Whether this is a scheduled refresh

        """
        await self._hub.fetch_program_data(scheduled=scheduled)

    @inspector(re_raise=False)
    async def fetch_system_update_data(self, *, scheduled: bool) -> None:
        """
        Fetch system update data from the backend.

        Args:
        ----
            scheduled: Whether this is a scheduled refresh

        """
        await self._hub.fetch_system_update_data(scheduled=scheduled)

    @inspector(re_raise=False)
    async def fetch_sysvar_data(self, *, scheduled: bool) -> None:
        """
        Fetch system variable data from the backend.

        Args:
        ----
            scheduled: Whether this is a scheduled refresh

        """
        await self._hub.fetch_sysvar_data(scheduled=scheduled)

    def get_hub_data_points(
        self, *, category: DataPointCategory | None = None, registered: bool | None = None
    ) -> tuple[GenericProgramDataPointProtocol | GenericSysvarDataPointProtocol, ...]:
        """
        Return the hub data points (programs and sysvars) filtered by category and registration.

        Args:
        ----
            category: Optional category to filter by
            registered: Optional registration status to filter by

        Returns:
        -------
            Tuple of matching hub data points

        """
        return tuple(
            he
            for he in (self.program_data_points + self.sysvar_data_points)
            if (category is None or he.category == category) and (registered is None or he.is_registered == registered)
        )

    def get_program_data_point(
        self, *, pid: str | None = None, legacy_name: str | None = None, state_path: str | None = None
    ) -> ProgramDpType | None:
        """
        Return a program data point by ID or legacy name.

        Args:
        ----
            pid: Program identifier
            legacy_name: Legacy name of the program
            state_path: State path of the program

        Returns:
        -------
            Program data point or None if not found

        """
        if state_path and (pid := self._state_path_to_name.get(state_path)):
            return self.get_program_data_point(pid=pid)

        if pid and (program := self._program_data_points.get(pid)):
            return program
        if legacy_name:
            for program in self._program_data_points.values():
                if legacy_name in (program.button.legacy_name, program.switch.legacy_name):
                    return program
        return None

    async def get_system_variable(self, *, legacy_name: str) -> Any | None:
        """
        Get system variable value from the backend.

        Args:
        ----
            legacy_name: Legacy name of the system variable

        Returns:
        -------
            Current value of the system variable or None

        """
        if client := self._primary_client_provider.primary_client:
            return await client.get_system_variable(name=legacy_name)
        return None

    def get_sysvar_data_point(
        self, *, vid: str | None = None, legacy_name: str | None = None, state_path: str | None = None
    ) -> GenericSysvarDataPointProtocol | None:
        """
        Return a system variable data point by ID or legacy name.

        Args:
        ----
            vid: System variable identifier
            legacy_name: Legacy name of the system variable
            state_path: State path of the system variable

        Returns:
        -------
            System variable data point or None if not found

        """
        if state_path and (vid := self._state_path_to_name.get(state_path)):
            return self.get_sysvar_data_point(vid=vid)

        if vid and (sysvar := self._sysvar_data_points.get(vid)):
            return sysvar
        if legacy_name:
            for sysvar in self._sysvar_data_points.values():
                if sysvar.legacy_name == legacy_name:
                    return sysvar
        return None

    async def init_hub(self) -> None:
        """Initialize the hub by fetching program, sysvar, and install mode data."""
        _LOGGER.debug("INIT_HUB: Initializing hub for %s", self._central_info.name)
        await self._hub.fetch_program_data(scheduled=True)
        await self._hub.fetch_sysvar_data(scheduled=True)
        await self._hub.init_install_mode()

    async def init_install_mode(self) -> Mapping[Interface, InstallModeDpType]:
        """
        Initialize install mode data points for all supported interfaces.

        Creates data points, fetches initial state from backend, and publishes refresh event.
        Returns a dict of InstallModeDpType by Interface.
        """
        return await self._hub.init_install_mode()

    def publish_install_mode_refreshed(self) -> None:
        """Publish HUB_REFRESHED event for install mode data points."""
        self._hub.publish_install_mode_refreshed()

    def remove_program_button(self, *, pid: str) -> None:
        """
        Remove a program button.

        Args:
        ----
            pid: Program identifier

        """
        if (program_dp := self.get_program_data_point(pid=pid)) is not None:
            program_dp.button.publish_device_removed_event()
            program_dp.switch.publish_device_removed_event()
            self._program_data_points.pop(pid, None)
            self._state_path_to_name.pop(program_dp.button.state_path, None)
            _LOGGER.debug(
                "REMOVE_PROGRAM_BUTTON: Removed program %s from %s",
                pid,
                self._central_info.name,
            )

    def remove_sysvar_data_point(self, *, vid: str) -> None:
        """
        Remove a system variable data point.

        Args:
        ----
            vid: System variable identifier

        """
        if (sysvar_dp := self.get_sysvar_data_point(vid=vid)) is not None:
            sysvar_dp.publish_device_removed_event()
            self._sysvar_data_points.pop(vid, None)
            self._state_path_to_name.pop(sysvar_dp.state_path, None)

            # Event subscription will be automatically cleaned up when sysvar_dp is deleted

            _LOGGER.debug(
                "REMOVE_SYSVAR_DATA_POINT: Removed sysvar %s from %s",
                vid,
                self._central_info.name,
            )

    async def set_program_state(self, *, pid: str, state: bool) -> bool:
        """
        Set program state on the backend.

        Args:
        ----
            pid: Program identifier
            state: New program state

        Returns:
        -------
            True if setting succeeded, False otherwise

        """
        if client := self._primary_client_provider.primary_client:
            return await client.set_program_state(pid=pid, state=state)
        return False

    async def set_system_variable(self, *, legacy_name: str, value: Any) -> None:
        """
        Set system variable value on the backend.

        Args:
        ----
            legacy_name: Legacy name of the system variable
            value: New value

        """
        if dp := self.get_sysvar_data_point(legacy_name=legacy_name):
            await dp.send_variable(value=value)
        else:
            _LOGGER.error(
                i18n.tr(
                    "log.central.set_system_variable.not_found",
                    legacy_name=legacy_name,
                    name=self._central_info.name,
                )
            )
