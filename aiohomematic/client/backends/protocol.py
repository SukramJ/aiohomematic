# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
# pylint: disable=unnecessary-ellipsis
"""
Backend operations protocol.

Defines the interface for all backend-specific RPC operations,
abstracting transport-layer differences between CCU, CCU-Jack, and Homegear.

Public API
----------
-  : Protocol for backend implementations
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from aiohomematic.client.backends.capabilities import BackendCapabilities
    from aiohomematic.client.circuit_breaker import CircuitBreaker
    from aiohomematic.const import (
        BackupData,
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
        SystemInformation,
        SystemUpdateData,
        SystemVariableData,
    )

__all__ = ["BackendOperationsProtocol"]


@runtime_checkable
class BackendOperationsProtocol(Protocol):
    """
    Protocol for backend-specific RPC operations.

    This protocol abstracts all transport-layer differences between backends:
    - CCU: XML-RPC for device ops, JSON-RPC for metadata
    - CCU-Jack: JSON-RPC exclusively
    - Homegear: XML-RPC with Homegear-specific methods

    Implementations handle the actual RPC calls; handlers contain business logic.
    """

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def all_circuit_breakers_closed(self) -> bool:
        """Return True if all circuit breakers are in closed state."""
        ...

    @property
    def capabilities(self) -> BackendCapabilities:
        """Return the capability flags for this backend."""
        ...

    @property
    def circuit_breaker(self) -> CircuitBreaker | None:
        """Return the primary circuit breaker for metrics access."""
        ...

    @property
    def interface(self) -> Interface:
        """Return the interface type."""
        ...

    @property
    def interface_id(self) -> str:
        """Return the interface identifier."""
        ...

    @property
    def model(self) -> str:
        """Return the backend model name (CCU, Homegear, pydevccu)."""
        ...

    @property
    def system_information(self) -> SystemInformation:
        """Return system information retrieved during initialization."""
        ...

    async def accept_device_in_inbox(self, *, device_address: str) -> bool:
        """Accept a device from the inbox."""
        ...

    async def add_link(
        self,
        *,
        sender_address: str,
        receiver_address: str,
        name: str,
        description: str,
    ) -> None:
        """Add a link between two devices."""
        ...

    async def check_connection(self, *, handle_ping_pong: bool, caller_id: str | None = None) -> bool:
        """Check if the connection to the backend is alive."""
        ...

    async def create_backup_and_download(
        self,
        *,
        max_wait_time: float = 300.0,
        poll_interval: float = 5.0,
    ) -> BackupData | None:
        """Create a backup and download it."""
        ...

    async def deinit_proxy(self, *, init_url: str) -> None:
        """De-initialize the proxy to stop receiving callbacks."""
        ...

    async def delete_system_variable(self, *, name: str) -> bool:
        """Delete a system variable."""
        ...

    async def execute_program(self, *, pid: str) -> bool:
        """Execute a program by ID."""
        ...

    async def get_all_device_data(self, *, interface: Interface) -> dict[str, Any] | None:
        """Return all current values for devices on an interface."""
        ...

    async def get_all_functions(self) -> dict[str, set[str]]:
        """Return all functions with their assigned channel addresses."""
        ...

    async def get_all_programs(self, *, markers: tuple[DescriptionMarker | str, ...]) -> tuple[ProgramData, ...]:
        """Return all programs matching markers."""
        ...

    async def get_all_rooms(self) -> dict[str, set[str]]:
        """Return all rooms with their assigned channel addresses."""
        ...

    async def get_all_system_variables(
        self, *, markers: tuple[DescriptionMarker | str, ...]
    ) -> tuple[SystemVariableData, ...] | None:
        """Return all system variables matching markers."""
        ...

    async def get_device_description(self, *, address: str) -> DeviceDescription | None:
        """Return device description for a single address."""
        ...

    async def get_device_details(self, *, addresses: tuple[str, ...] | None = None) -> list[DeviceDetail] | None:
        """
        Return device names, interfaces, and rega IDs.

        Args:
            addresses: Optional tuple of device addresses to fetch details for.
                       Used by Homegear backend which requires explicit addresses.
                       CCU backend ignores this parameter (uses JSON-RPC).

        """
        ...

    async def get_inbox_devices(self) -> tuple[InboxDeviceData, ...]:
        """Return devices in the inbox (not yet configured)."""
        ...

    async def get_install_mode(self) -> int:
        """Return remaining time in install mode (seconds)."""
        ...

    async def get_link_peers(self, *, channel_address: str) -> tuple[str, ...]:
        """Return link peers for a channel address."""
        ...

    async def get_links(self, *, channel_address: str, flags: int) -> dict[str, Any]:
        """Return links for a channel address."""
        ...

    async def get_metadata(self, *, address: str, data_id: str) -> dict[str, Any]:
        """Return metadata for an address."""
        ...

    async def get_paramset(self, *, channel_address: str, paramset_key: ParamsetKey | str) -> dict[str, Any]:
        """Return a paramset from the backend."""
        ...

    async def get_paramset_description(
        self, *, channel_address: str, paramset_key: ParamsetKey
    ) -> dict[str, ParameterData] | None:
        """Return paramset description for a channel address and paramset key."""
        ...

    async def get_rega_id_by_address(self, *, address: str) -> int | None:
        """Return the ReGa ID for an address."""
        ...

    async def get_service_messages(
        self, *, message_type: ServiceMessageType | None = None
    ) -> tuple[ServiceMessageData, ...]:
        """Return active service messages."""
        ...

    async def get_system_update_info(self) -> SystemUpdateData | None:
        """Return system update information."""
        ...

    async def get_system_variable(self, *, name: str) -> Any:
        """Return the value of a system variable."""
        ...

    async def get_value(self, *, channel_address: str, parameter: str) -> Any:
        """Return a single parameter value."""
        ...

    async def has_program_ids(self, *, rega_id: int) -> bool:
        """Check if a channel has associated program IDs."""
        ...

    async def init_proxy(self, *, init_url: str, interface_id: str) -> None:
        """Initialize the proxy with callback URL."""
        ...

    async def initialize(self) -> None:
        """Initialize the backend (fetch system info, create proxies)."""
        ...

    async def list_devices(self) -> tuple[DeviceDescription, ...] | None:
        """Return all device descriptions from the backend."""
        ...

    async def put_paramset(
        self,
        *,
        channel_address: str,
        paramset_key: ParamsetKey | str,
        values: dict[str, Any],
        rx_mode: CommandRxMode | None = None,
    ) -> None:
        """Set multiple values in a paramset."""
        ...

    async def remove_link(self, *, sender_address: str, receiver_address: str) -> None:
        """Remove a link between two devices."""
        ...

    async def rename_channel(self, *, rega_id: int, new_name: str) -> bool:
        """Rename a channel."""
        ...

    async def rename_device(self, *, rega_id: int, new_name: str) -> bool:
        """Rename a device."""
        ...

    async def report_value_usage(self, *, channel_address: str, value_id: str, ref_counter: int) -> bool:
        """Report value usage to the backend."""
        ...

    def reset_circuit_breakers(self) -> None:
        """Reset all circuit breakers."""
        ...

    async def set_install_mode(
        self,
        *,
        on: bool = True,
        time: int = 60,
        mode: int = 1,
        device_address: str | None = None,
    ) -> bool:
        """Enable or disable install mode."""
        ...

    async def set_metadata(self, *, address: str, data_id: str, value: dict[str, Any]) -> dict[str, Any]:
        """Set metadata for an address."""
        ...

    async def set_program_state(self, *, pid: str, state: bool) -> bool:
        """Enable or disable a program."""
        ...

    async def set_system_variable(self, *, name: str, value: Any) -> bool:
        """Set the value of a system variable."""
        ...

    async def set_value(
        self,
        *,
        channel_address: str,
        parameter: str,
        value: Any,
        rx_mode: CommandRxMode | None = None,
    ) -> None:
        """Set a single parameter value."""
        ...

    async def stop(self) -> None:
        """Stop the backend and release resources."""
        ...

    async def trigger_firmware_update(self) -> bool:
        """Trigger system firmware update."""
        ...

    async def update_device_firmware(self, *, device_address: str) -> bool:
        """Update firmware on a device."""
        ...
