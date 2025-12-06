"""
Client protocol interfaces.

This module defines protocol interfaces for client operations,
allowing components to depend on client functionality without coupling
to specific implementations (ClientCCU, ClientJsonCCU, ClientHomegear).
"""

from __future__ import annotations

from abc import abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from aiohomematic.const import (
    CallSource,
    DeviceDescription,
    InboxDeviceData,
    Interface,
    ParameterData,
    ParamsetKey,
    ProductGroup,
    ProgramData,
    ProxyInitState,
    SystemInformation,
)

if TYPE_CHECKING:
    from aiohomematic.client import InterfaceConfig
    from aiohomematic.interfaces.model import DeviceProtocol


@runtime_checkable
class ClientProtocol(Protocol):
    """
    Protocol for Homematic client operations.

    Provides access to backend communication, device management, and
    system operations. Implemented by ClientCCU, ClientJsonCCU, and ClientHomegear.
    """

    __slots__ = ()

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def available(self) -> bool:
        """Return the availability of the client."""

    @property
    def central(self) -> Any:
        """Return the central of the client."""

    @property
    def interface(self) -> Interface:
        """Return the interface of the client."""

    @property
    def interface_id(self) -> str:
        """Return the interface id of the client."""

    @property
    def is_initialized(self) -> bool:
        """Return if interface is initialized."""

    @property
    def last_value_send_cache(self) -> Any:
        """Return the last value send cache."""

    @property
    def model(self) -> str:
        """Return the model of the backend."""

    @property
    def modified_at(self) -> datetime:
        """Return the last update datetime value."""

    @modified_at.setter
    def modified_at(self, value: datetime) -> None:
        """Write the last update datetime value."""

    @property
    def ping_pong_cache(self) -> Any:
        """Return the ping pong cache."""

    @property
    def supports_backup(self) -> bool:
        """Return if the backend supports backup creation and download."""

    @property
    def supports_device_firmware_update(self) -> bool:
        """Return if the backend supports device firmware updates."""

    @property
    def supports_firmware_update_trigger(self) -> bool:
        """Return if the backend supports triggering system firmware updates."""

    @property
    def supports_firmware_updates(self) -> bool:
        """Return the supports_firmware_updates info of the backend."""

    @property
    def supports_functions(self) -> bool:
        """Return if interface supports functions."""

    @property
    def supports_inbox_devices(self) -> bool:
        """Return if the backend supports inbox device queries."""

    @property
    def supports_install_mode(self) -> bool:
        """Return if the backend supports install mode operations."""

    @property
    def supports_linking(self) -> bool:
        """Return if the backend supports device linking operations."""

    @property
    def supports_metadata(self) -> bool:
        """Return if the backend supports metadata operations."""

    @property
    def supports_ping_pong(self) -> bool:
        """Return the supports_ping_pong info of the backend."""

    @property
    def supports_programs(self) -> bool:
        """Return if interface supports programs."""

    @property
    def supports_push_updates(self) -> bool:
        """Return if the client supports push updates."""

    @property
    def supports_rega_id_lookup(self) -> bool:
        """Return if the backend supports ReGa ID lookups."""

    @property
    def supports_rename(self) -> bool:
        """Return if the backend supports renaming devices and channels."""

    @property
    def supports_rooms(self) -> bool:
        """Return if interface supports rooms."""

    @property
    def supports_rpc_callback(self) -> bool:
        """Return if interface supports rpc callback."""

    @property
    def supports_service_messages(self) -> bool:
        """Return if the backend supports service messages."""

    @property
    def supports_system_update_info(self) -> bool:
        """Return if the backend supports system update information."""

    @property
    def supports_value_usage_reporting(self) -> bool:
        """Return if the backend supports value usage reporting."""

    @property
    def system_information(self) -> SystemInformation:
        """Return the system_information of the client."""

    @property
    def version(self) -> str:
        """Return the version id of the client."""

    async def accept_device_in_inbox(self, *, device_address: str) -> bool:
        """Accept a device from the CCU inbox."""

    async def add_link(self, *, sender_address: str, receiver_address: str, name: str, description: str) -> None:
        """Add a link between two devices."""

    async def check_connection_availability(self, *, handle_ping_pong: bool) -> bool:
        """Check if proxy is still initialized."""

    async def create_backup_and_download(self) -> bytes | None:
        """Create a backup on the CCU and download it."""

    async def deinitialize_proxy(self) -> ProxyInitState:
        """De-init to stop the backend from sending events for this remote."""

    async def delete_system_variable(self, *, name: str) -> bool:
        """Delete a system variable from the backend."""

    async def execute_program(self, *, pid: str) -> bool:
        """Execute a program on the backend."""

    async def fetch_all_device_data(self) -> None:
        """Fetch all device data from the backend."""

    async def fetch_device_details(self) -> None:
        """Get all names via JSON-RPC and store in data."""

    async def fetch_paramset_description(self, *, channel_address: str, paramset_key: ParamsetKey) -> None:
        """Fetch a specific paramset and add it to the known ones."""

    async def fetch_paramset_descriptions(self, *, device_description: DeviceDescription) -> None:
        """Fetch paramsets for provided device description."""

    async def get_all_device_descriptions(self, *, device_address: str) -> tuple[DeviceDescription, ...]:
        """Get all device descriptions from the backend."""

    async def get_all_functions(self) -> dict[str, set[str]]:
        """Get all functions from the backend."""

    async def get_all_paramset_descriptions(
        self, *, device_descriptions: tuple[DeviceDescription, ...]
    ) -> dict[str, dict[ParamsetKey, dict[str, ParameterData]]]:
        """Get all paramset descriptions for provided device descriptions."""

    async def get_all_programs(self, *, markers: tuple[Any, ...]) -> tuple[ProgramData, ...]:
        """Get all programs, if available."""

    async def get_all_rooms(self) -> dict[str, set[str]]:
        """Get all rooms from the backend."""

    async def get_all_system_variables(self, *, markers: tuple[Any, ...]) -> tuple[Any, ...] | None:
        """Get all system variables from the backend."""

    async def get_device_description(self, *, address: str) -> DeviceDescription | None:
        """Get device descriptions from the backend."""

    async def get_inbox_devices(self) -> tuple[InboxDeviceData, ...]:
        """Get all devices in the inbox (not yet configured)."""

    async def get_install_mode(self) -> int:
        """Return the remaining time in install mode."""

    async def get_link_peers(self, *, address: str) -> tuple[str, ...]:
        """Return a list of link peers."""

    async def get_links(self, *, address: str, flags: int) -> dict[str, Any]:
        """Return a list of links."""

    async def get_metadata(self, *, address: str, data_id: str) -> dict[str, Any]:
        """Return the metadata for an object."""

    async def get_paramset(
        self,
        *,
        address: str,
        paramset_key: ParamsetKey | str,
        call_source: CallSource = CallSource.MANUAL_OR_SCHEDULED,
    ) -> dict[str, Any]:
        """Return a paramset from the backend."""

    async def get_paramset_descriptions(
        self, *, device_description: DeviceDescription
    ) -> dict[str, dict[ParamsetKey, dict[str, ParameterData]]]:
        """Get paramsets for provided device description."""

    def get_product_group(self, *, model: str) -> ProductGroup:
        """Return the product group."""

    async def get_rega_id_by_address(self, *, address: str) -> int | None:
        """Get the ReGa ID for a device or channel address."""

    async def get_service_messages(self, *, message_type: Any | None = None) -> tuple[Any, ...]:
        """Get all active service messages from the backend."""

    async def get_system_update_info(self) -> Any | None:
        """Get system update information from the backend."""

    async def get_system_variable(self, *, name: str) -> Any:
        """Get single system variable from the backend."""

    async def get_value(
        self,
        *,
        channel_address: str,
        paramset_key: ParamsetKey,
        parameter: str,
        call_source: CallSource = CallSource.MANUAL_OR_SCHEDULED,
    ) -> Any:
        """Return a value from the backend."""

    def get_virtual_remote(self) -> DeviceProtocol | None:
        """Get the virtual remote for the Client."""

    async def has_program_ids(self, *, rega_id: int) -> bool:
        """Return if a channel has program ids."""

    async def init_client(self) -> None:
        """Initialize the client."""

    async def initialize_proxy(self) -> ProxyInitState:
        """Initialize the proxy has to tell the backend where to send the events."""

    def is_callback_alive(self) -> bool:
        """Return if XmlRPC-Server is alive based on received events for this client."""

    async def is_connected(self) -> bool:
        """Perform actions required for connectivity check."""

    async def list_devices(self) -> tuple[DeviceDescription, ...] | None:
        """List devices of the backend."""

    async def put_paramset(
        self,
        *,
        channel_address: str,
        paramset_key_or_link_address: ParamsetKey | str,
        values: dict[str, Any],
        wait_for_callback: int | None = None,
        rx_mode: Any | None = None,
        check_against_pd: bool = False,
    ) -> set[Any]:
        """Set paramsets manually."""

    async def reconnect(self) -> bool:
        """Re-init all RPC clients."""

    async def reinitialize_proxy(self) -> ProxyInitState:
        """Reinit Proxy."""

    async def remove_link(self, *, sender_address: str, receiver_address: str) -> None:
        """Remove a link between two devices."""

    async def rename_channel(self, *, rega_id: int, new_name: str) -> bool:
        """Rename a channel on the CCU."""

    async def rename_device(self, *, rega_id: int, new_name: str) -> bool:
        """Rename a device on the CCU."""

    async def report_value_usage(self, *, address: str, value_id: str, ref_counter: int) -> bool:
        """Report value usage."""

    async def set_install_mode(
        self,
        *,
        on: bool = True,
        time: int = 60,
        mode: int = 1,
        device_address: str | None = None,
    ) -> bool:
        """Set the install mode on the backend."""

    async def set_metadata(self, *, address: str, data_id: str, value: dict[str, Any]) -> dict[str, Any]:
        """Write the metadata for an object."""

    async def set_program_state(self, *, pid: str, state: bool) -> bool:
        """Set the program state on the backend."""

    async def set_system_variable(self, *, legacy_name: str, value: Any) -> bool:
        """Set a system variable on the backend."""

    async def set_value(
        self,
        *,
        channel_address: str,
        paramset_key: ParamsetKey,
        parameter: str,
        value: Any,
        wait_for_callback: int | None = None,
        rx_mode: Any | None = None,
        check_against_pd: bool = False,
    ) -> set[Any]:
        """Set single value on paramset VALUES."""

    async def stop(self) -> None:
        """Stop depending services."""

    async def trigger_firmware_update(self) -> bool:
        """Trigger the CCU firmware update process."""

    async def update_device_firmware(self, *, device_address: str) -> bool:
        """Update the firmware of a Homematic device."""

    async def update_paramset_descriptions(self, *, device_address: str) -> None:
        """Update paramsets descriptions for provided device_address."""


@runtime_checkable
class ClientProvider(Protocol):
    """
    Protocol for accessing client instances.

    Implemented by CentralUnit.
    """

    @property
    @abstractmethod
    def clients(self) -> tuple[ClientProtocol, ...]:
        """Get all clients."""

    @property
    @abstractmethod
    def has_clients(self) -> bool:
        """Check if any clients exist."""

    @property
    @abstractmethod
    def interface_ids(self) -> frozenset[str]:
        """Get all interface IDs."""

    @abstractmethod
    def get_client(self, *, interface_id: str | None = None, interface: Interface | None = None) -> ClientProtocol:
        """Get client by interface_id or interface type."""

    @abstractmethod
    def has_client(self, *, interface_id: str) -> bool:
        """Check if a client exists for the given interface."""


@runtime_checkable
class ClientFactory(Protocol):
    """
    Protocol for creating client instances.

    Implemented by CentralUnit.
    """

    @abstractmethod
    async def create_client_instance(
        self,
        *,
        interface_config: InterfaceConfig,
    ) -> ClientProtocol:
        """
        Create a client for the given interface configuration.

        Args:
            interface_config: Configuration for the interface.

        Returns:
            Client instance for the interface.

        """


@runtime_checkable
class ClientCoordination(Protocol):
    """
    Protocol for client coordination operations.

    Implemented by CentralUnit.
    """

    @property
    @abstractmethod
    def all_clients_active(self) -> bool:
        """Check if all clients are active."""

    @property
    @abstractmethod
    def interface_ids(self) -> frozenset[str]:
        """Get all interface IDs."""

    @property
    @abstractmethod
    def poll_clients(self) -> tuple[ClientProtocol, ...] | None:
        """Get clients that require polling."""

    @abstractmethod
    def get_client(self, *, interface_id: str) -> ClientProtocol:
        """Get client by interface ID."""

    @abstractmethod
    async def load_and_refresh_data_point_data(self, *, interface: Interface) -> None:
        """Load and refresh data point data for an interface."""

    @abstractmethod
    async def restart_clients(self) -> None:
        """Restart all clients."""

    @abstractmethod
    def set_last_event_seen_for_interface(self, *, interface_id: str) -> None:
        """Set the last event seen time for an interface."""


@runtime_checkable
class PrimaryClientProvider(Protocol):
    """
    Protocol for accessing primary client.

    Implemented by CentralUnit.
    """

    @property
    @abstractmethod
    def primary_client(self) -> ClientProtocol | None:
        """Get primary client."""
