# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
CCU backend implementation.

Uses XML-RPC for device operations and JSON-RPC for metadata/programs/sysvars.

Public API
----------
- CcuBackend: Backend for CCU3/CCU2 systems
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import datetime
import logging
from typing import TYPE_CHECKING, Any, Final, cast

from aiohomematic.client.backends.base import BaseBackend
from aiohomematic.client.backends.capabilities import CCU_CAPABILITIES
from aiohomematic.client.circuit_breaker import CircuitBreaker
from aiohomematic.const import (
    INTERFACES_SUPPORTING_FIRMWARE_UPDATES,
    INTERFACES_SUPPORTING_RPC_CALLBACK,
    LINKABLE_INTERFACES,
    Backend,
    BackupData,
    BackupStatus,
    CircuitState,
    CommandRxMode,
    DescriptionMarker,
    DeviceDescription,
    DeviceDetail,
    InboxDeviceData,
    Interface,
    ParameterData,
    ParamsetKey,
    ProgramData,
    ServiceMessageData,
    ServiceMessageType,
    SystemUpdateData,
    SystemVariableData,
)
from aiohomematic.exceptions import BaseHomematicException
from aiohomematic.schemas import normalize_device_description
from aiohomematic.support import extract_exc_args

if TYPE_CHECKING:
    from aiohomematic.client.json_rpc import AioJsonRpcAioHttpClient
    from aiohomematic.client.rpc_proxy import BaseRpcProxy

__all__ = ["CcuBackend"]

_LOGGER: Final = logging.getLogger(__name__)


class CcuBackend(BaseBackend):
    """
    Backend for CCU3/CCU2 systems.

    Communication:
    - XML-RPC: Device operations (setValue, getValue, putParamset, listDevices, etc.)
    - JSON-RPC: Metadata, programs, system variables, rooms, functions
    """

    __slots__ = ("_device_details_provider", "_json_rpc", "_proxy", "_proxy_read")

    def __init__(
        self,
        *,
        interface: Interface,
        interface_id: str,
        proxy: BaseRpcProxy,
        proxy_read: BaseRpcProxy,
        json_rpc: AioJsonRpcAioHttpClient,
        device_details_provider: Mapping[str, int],
        has_push_updates: bool,
    ) -> None:
        """Initialize the CCU backend."""
        # Build capabilities based on interface and config
        capabilities = CCU_CAPABILITIES.model_copy(
            update={
                "firmware_updates": interface in INTERFACES_SUPPORTING_FIRMWARE_UPDATES,
                "linking": interface in LINKABLE_INTERFACES,
                "ping_pong": interface in INTERFACES_SUPPORTING_RPC_CALLBACK,
                "push_updates": has_push_updates,
                "rpc_callback": interface in INTERFACES_SUPPORTING_RPC_CALLBACK,
            }
        )
        super().__init__(
            interface=interface,
            interface_id=interface_id,
            capabilities=capabilities,
        )
        self._proxy: Final = proxy
        self._proxy_read: Final = proxy_read
        self._json_rpc: Final = json_rpc
        self._device_details_provider: Final = device_details_provider

    @property
    def all_circuit_breakers_closed(self) -> bool:
        """Return True if all circuit breakers are in closed state."""
        if self._proxy.circuit_breaker.state != CircuitState.CLOSED:
            return False
        # Check proxy_read only if it's a different object
        if self._proxy_read is not self._proxy and self._proxy_read.circuit_breaker.state != CircuitState.CLOSED:
            return False
        return self._json_rpc.circuit_breaker.state == CircuitState.CLOSED

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        """Return the primary circuit breaker for metrics access."""
        return self._proxy.circuit_breaker

    @property
    def model(self) -> str:
        """Return the backend model name."""
        return Backend.CCU

    async def accept_device_in_inbox(self, *, device_address: str) -> bool:
        """Accept device from inbox."""
        return await self._json_rpc.accept_device_in_inbox(device_address=device_address)

    async def add_link(
        self,
        *,
        sender_address: str,
        receiver_address: str,
        name: str,
        description: str,
    ) -> None:
        """Add a link."""
        await self._proxy.addLink(sender_address, receiver_address, name, description)

    async def check_connection(self, *, handle_ping_pong: bool, caller_id: str | None = None) -> bool:
        """Check if connection is alive via ping."""
        try:
            # Use caller_id with token for ping-pong tracking, or interface_id for simple ping
            await self._proxy.ping(caller_id or self._interface_id)
        except BaseHomematicException:
            return False
        return True

    async def create_backup_and_download(
        self,
        *,
        max_wait_time: float = 300.0,
        poll_interval: float = 5.0,
    ) -> BackupData | None:
        """
        Create and download backup with polling.

        Start the backup process in the background and poll for completion.
        This avoids blocking the ReGa scripting engine during backup creation.
        """
        # Start backup in background
        if not await self._json_rpc.create_backup_start():
            _LOGGER.warning("CREATE_BACKUP: Failed to start backup")  # i18n-log: ignore
            return None

        # Poll for completion
        elapsed = 0.0
        while elapsed < max_wait_time:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
            status_data = await self._json_rpc.create_backup_status()

            if status_data.status == BackupStatus.COMPLETED:
                _LOGGER.info(  # i18n-log: ignore
                    "CREATE_BACKUP: Completed - %s (%s bytes)",
                    status_data.filename,
                    status_data.size,
                )
                if (content := await self._json_rpc.download_backup()) is None:
                    return None
                return BackupData(
                    filename=self._generate_backup_filename(),
                    content=content,
                )

            if status_data.status == BackupStatus.FAILED:
                _LOGGER.warning("CREATE_BACKUP: Backup failed")  # i18n-log: ignore
                return None

            if status_data.status == BackupStatus.IDLE:
                _LOGGER.warning("CREATE_BACKUP: Unexpected idle status")  # i18n-log: ignore
                return None

            _LOGGER.debug("CREATE_BACKUP: Running (elapsed: %.1fs)", elapsed)

        _LOGGER.warning("CREATE_BACKUP: Timeout after %.1fs", max_wait_time)  # i18n-log: ignore
        return None

    async def deinit_proxy(self, *, init_url: str) -> None:
        """De-initialize the proxy."""
        await self._proxy.init(init_url)

    async def delete_system_variable(self, *, name: str) -> bool:
        """Delete a system variable."""
        return await self._json_rpc.delete_system_variable(name=name)

    async def execute_program(self, *, pid: str) -> bool:
        """Execute a program."""
        return await self._json_rpc.execute_program(pid=pid)

    async def get_all_device_data(self, *, interface: Interface) -> dict[str, Any] | None:
        """Return all device data via JSON-RPC."""
        return dict(await self._json_rpc.get_all_device_data(interface=interface))

    async def get_all_functions(self) -> dict[str, set[str]]:
        """Return all functions with their assigned channel addresses."""
        functions: dict[str, set[str]] = {}
        rega_ids_function = await self._json_rpc.get_all_channel_rega_ids_function()
        for address, rega_id in self._device_details_provider.items():
            if (sections := rega_ids_function.get(rega_id)) is not None:
                if address not in functions:
                    functions[address] = set()
                functions[address].update(sections)
        return functions

    async def get_all_programs(self, *, markers: tuple[DescriptionMarker | str, ...]) -> tuple[ProgramData, ...]:
        """Return all programs."""
        return await self._json_rpc.get_all_programs(markers=markers)

    async def get_all_rooms(self) -> dict[str, set[str]]:
        """Return all rooms with their assigned channel addresses."""
        rooms: dict[str, set[str]] = {}
        rega_ids_room = await self._json_rpc.get_all_channel_rega_ids_room()
        for address, rega_id in self._device_details_provider.items():
            if (names := rega_ids_room.get(rega_id)) is not None:
                if address not in rooms:
                    rooms[address] = set()
                rooms[address].update(names)
        return rooms

    async def get_all_system_variables(
        self, *, markers: tuple[DescriptionMarker | str, ...]
    ) -> tuple[SystemVariableData, ...] | None:
        """Return all system variables."""
        return await self._json_rpc.get_all_system_variables(markers=markers)

    async def get_device_description(self, *, address: str) -> DeviceDescription | None:
        """Return device description for an address."""
        try:
            return cast(
                DeviceDescription | None,
                await self._proxy_read.getDeviceDescription(address),
            )
        except BaseHomematicException as bhexc:
            _LOGGER.warning(  # i18n-log: ignore
                "GET_DEVICE_DESCRIPTION failed: %s [%s]",
                bhexc.name,
                extract_exc_args(exc=bhexc),
            )
            return None

    async def get_device_details(self, *, addresses: tuple[str, ...] | None = None) -> list[DeviceDetail] | None:
        """
        Return device names, interfaces, and rega IDs via JSON-RPC.

        Note: The addresses parameter is ignored for CCU backend as JSON-RPC
        returns all device details in a single call.
        """
        return list(await self._json_rpc.get_device_details())

    async def get_inbox_devices(self) -> tuple[InboxDeviceData, ...]:
        """Return inbox devices."""
        return await self._json_rpc.get_inbox_devices()

    async def get_install_mode(self) -> int:
        """Return remaining install mode time."""
        return cast(int, await self._proxy.getInstallMode())

    async def get_link_peers(self, *, channel_address: str) -> tuple[str, ...]:
        """Return link peers."""
        return tuple(await self._proxy_read.getLinkPeers(channel_address))

    async def get_links(self, *, channel_address: str, flags: int) -> dict[str, Any]:
        """Return links."""
        return cast(
            dict[str, Any],
            await self._proxy_read.getLinks(channel_address, flags),
        )

    async def get_metadata(self, *, address: str, data_id: str) -> dict[str, Any]:
        """Return metadata for an address."""
        return cast(
            dict[str, Any],
            await self._proxy_read.getMetadata(address, data_id),
        )

    async def get_paramset(self, *, channel_address: str, paramset_key: ParamsetKey | str) -> dict[str, Any]:
        """Return a paramset."""
        return cast(
            dict[str, Any],
            await self._proxy_read.getParamset(channel_address, paramset_key),
        )

    async def get_paramset_description(
        self, *, channel_address: str, paramset_key: ParamsetKey
    ) -> dict[str, ParameterData] | None:
        """Return paramset description."""
        try:
            return cast(
                dict[str, ParameterData],
                await self._proxy_read.getParamsetDescription(channel_address, paramset_key),
            )
        except BaseHomematicException as bhexc:
            _LOGGER.debug(
                "GET_PARAMSET_DESCRIPTION failed: %s [%s] for %s/%s",
                bhexc.name,
                extract_exc_args(exc=bhexc),
                channel_address,
                paramset_key,
            )
            return None

    async def get_rega_id_by_address(self, *, address: str) -> int | None:
        """Return ReGa ID for an address."""
        return await self._json_rpc.get_rega_id_by_address(address=address)

    async def get_service_messages(
        self, *, message_type: ServiceMessageType | None = None
    ) -> tuple[ServiceMessageData, ...]:
        """Return service messages."""
        return await self._json_rpc.get_service_messages(message_type=message_type)

    async def get_system_update_info(self) -> SystemUpdateData | None:
        """Return system update info."""
        return await self._json_rpc.get_system_update_info()

    async def get_system_variable(self, *, name: str) -> Any:
        """Return system variable value."""
        return await self._json_rpc.get_system_variable(name=name)

    async def get_value(self, *, channel_address: str, parameter: str) -> Any:
        """Return a parameter value."""
        return await self._proxy_read.getValue(channel_address, parameter)

    async def has_program_ids(self, *, rega_id: int) -> bool:
        """Check if channel has program IDs."""
        return await self._json_rpc.has_program_ids(rega_id=rega_id)

    async def init_proxy(self, *, init_url: str, interface_id: str) -> None:
        """Initialize the proxy with callback URL."""
        await self._proxy.init(init_url, interface_id)

    async def initialize(self) -> None:
        """Initialize the backend by fetching system information."""
        self._system_information = await self._json_rpc.get_system_information()
        # Update capabilities based on system info
        if not self._system_information.has_backup:
            self._capabilities = self._capabilities.model_copy(update={"backup": False})
        if not self._system_information.has_system_update:
            self._capabilities = self._capabilities.model_copy(update={"firmware_update_trigger": False})

    async def list_devices(self) -> tuple[DeviceDescription, ...] | None:
        """Return all device descriptions (normalized)."""
        try:
            raw_descriptions = await self._proxy_read.listDevices()
            return tuple(normalize_device_description(device_description=desc) for desc in raw_descriptions)
        except BaseHomematicException as bhexc:
            _LOGGER.debug(
                "LIST_DEVICES failed: %s [%s]",
                bhexc.name,
                extract_exc_args(exc=bhexc),
            )
            return None

    async def put_paramset(
        self,
        *,
        channel_address: str,
        paramset_key: ParamsetKey | str,
        values: dict[str, Any],
        rx_mode: CommandRxMode | None = None,
    ) -> None:
        """Set paramset values."""
        if rx_mode:
            await self._proxy.putParamset(channel_address, paramset_key, values, rx_mode)
        else:
            await self._proxy.putParamset(channel_address, paramset_key, values)

    async def remove_link(self, *, sender_address: str, receiver_address: str) -> None:
        """Remove a link."""
        await self._proxy.removeLink(sender_address, receiver_address)

    async def rename_channel(self, *, rega_id: int, new_name: str) -> bool:
        """Rename a channel."""
        return await self._json_rpc.rename_channel(rega_id=rega_id, new_name=new_name)

    async def rename_device(self, *, rega_id: int, new_name: str) -> bool:
        """Rename a device."""
        return await self._json_rpc.rename_device(rega_id=rega_id, new_name=new_name)

    async def report_value_usage(self, *, channel_address: str, value_id: str, ref_counter: int) -> bool:
        """Report value usage to the backend."""
        return bool(await self._proxy.reportValueUsage(channel_address, value_id, ref_counter))

    def reset_circuit_breakers(self) -> None:
        """Reset all circuit breakers to closed state."""
        self._proxy.circuit_breaker.reset()
        # Reset proxy_read only if it's a different object
        if self._proxy_read is not self._proxy:
            self._proxy_read.circuit_breaker.reset()
        self._json_rpc.circuit_breaker.reset()

    async def set_install_mode(
        self,
        *,
        on: bool = True,
        time: int = 60,
        mode: int = 1,
        device_address: str | None = None,
    ) -> bool:
        """Set install mode."""
        if device_address:
            await self._proxy.setInstallMode(on, time, mode, device_address)
        else:
            await self._proxy.setInstallMode(on, time, mode)
        return True

    async def set_metadata(self, *, address: str, data_id: str, value: dict[str, Any]) -> dict[str, Any]:
        """Set metadata for an address."""
        await self._proxy.setMetadata(address, data_id, value)
        return value

    async def set_program_state(self, *, pid: str, state: bool) -> bool:
        """Set program state."""
        return await self._json_rpc.set_program_state(pid=pid, state=state)

    async def set_system_variable(self, *, name: str, value: Any) -> bool:
        """Set system variable value."""
        return await self._json_rpc.set_system_variable(legacy_name=name, value=value)

    async def set_value(
        self,
        *,
        channel_address: str,
        parameter: str,
        value: Any,
        rx_mode: CommandRxMode | None = None,
    ) -> None:
        """Set a parameter value."""
        if rx_mode:
            await self._proxy.setValue(channel_address, parameter, value, rx_mode)
        else:
            await self._proxy.setValue(channel_address, parameter, value)

    async def stop(self) -> None:
        """Stop the backend and release resources."""
        await self._proxy.stop()
        await self._proxy_read.stop()

    async def trigger_firmware_update(self) -> bool:
        """Trigger system firmware update."""
        return await self._json_rpc.trigger_firmware_update()

    async def update_device_firmware(self, *, device_address: str) -> bool:
        """
        Update device firmware via XML-RPC.

        Tries installFirmware first (HmIP/HmIPW), falls back to updateFirmware (BidCos).
        """
        try:
            # Try installFirmware first (for HmIP/HmIPW devices)
            result = await self._proxy.installFirmware(device_address)
            return bool(result) if isinstance(result, bool) else bool(result[0])
        except BaseHomematicException:
            # Fall back to updateFirmware (for BidCos devices)
            try:
                result = await self._proxy.updateFirmware(device_address)
                return bool(result) if isinstance(result, bool) else bool(result[0])
            except BaseHomematicException as bhexc:
                _LOGGER.debug(
                    "UPDATE_DEVICE_FIRMWARE failed: %s [%s]",
                    bhexc.name,
                    extract_exc_args(exc=bhexc),
                )
                return False

    def _generate_backup_filename(self) -> str:
        """Generate backup filename with hostname, version, and timestamp."""
        hostname = self._system_information.hostname or "CCU"
        version = self._system_information.version or "unknown"
        timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
        return f"{hostname}-{version}-{timestamp}.sbk"
