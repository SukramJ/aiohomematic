"""
Client protocol interfaces.

This module defines protocol interfaces for client operations,
allowing components to depend on client functionality without coupling
to specific implementations (ClientCCU, ClientJsonCCU, ClientHomegear).

Protocol Hierarchy
------------------

Client protocols are organized following the Interface Segregation Principle:

**Core Protocols (4):**
    - `ClientIdentity`: Basic identification (interface, interface_id, model, version)
    - `ClientConnection`: Connection state management (available, is_connected, reconnect)
    - `ClientLifecycle`: Lifecycle operations (init_client, stop, proxy management)
    - `ClientCapabilities`: Feature support flags (all supports_* properties)

**Handler-Based Protocols (9):**
    - `DeviceDiscoveryOperations`: Device discovery (list_devices, get_device_description)
    - `ParamsetOperations`: Paramset operations (get_paramset, put_paramset, fetch)
    - `ValueOperations`: Value operations (get_value, set_value, report_value_usage)
    - `LinkOperations`: Device linking (add_link, remove_link, get_link_peers)
    - `FirmwareOperations`: Firmware updates (update_device_firmware, trigger_firmware_update)
    - `SystemVariableOperations`: System variables (get/set/delete_system_variable)
    - `ProgramOperations`: Program execution (get_all_programs, execute_program)
    - `BackupOperations`: Backup creation (create_backup_and_download)
    - `MetadataOperations`: Metadata, rooms, functions, install mode, inbox, service messages

**Composite Protocol:**
    - `ClientProtocol`: Combines all sub-protocols for complete client access
"""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Mapping
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from aiohomematic.const import (
    BackupData,
    CallSource,
    CentralState,
    ClientState,
    DataPointKey,
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
from aiohomematic.interfaces.operations import TaskScheduler

if TYPE_CHECKING:
    from aiohomematic.central import CentralConfig, CentralConnectionState
    from aiohomematic.central.cache_coordinator import CacheCoordinator
    from aiohomematic.central.device_coordinator import DeviceCoordinator
    from aiohomematic.central.device_registry import DeviceRegistry
    from aiohomematic.central.event_bus import EventBus
    from aiohomematic.central.event_coordinator import EventCoordinator
    from aiohomematic.client import AioJsonRpcAioHttpClient, InterfaceConfig
    from aiohomematic.interfaces.model import DeviceProtocol
    from aiohomematic.store import SessionRecorder


# =============================================================================
# Client Sub-Protocol Interfaces
# =============================================================================


class ClientIdentity(Protocol):
    """
    Protocol for client identification.

    Provides basic identity information for a client.
    """

    __slots__ = ()

    @property
    def central(self) -> ClientDependencies:
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
    def model(self) -> str:
        """Return the model of the backend."""

    @property
    def system_information(self) -> SystemInformation:
        """Return the system_information of the client."""

    @property
    def version(self) -> str:
        """Return the version id of the client."""


class ClientConnection(Protocol):
    """
    Protocol for client connection state management.

    Provides connection state and health check operations.
    """

    __slots__ = ()

    @property
    def all_circuit_breakers_closed(self) -> bool:
        """Return True if all circuit breakers are in closed state."""

    @property
    def available(self) -> bool:
        """Return the availability of the client."""

    @property
    def modified_at(self) -> datetime:
        """Return the last update datetime value."""

    @modified_at.setter
    def modified_at(self, value: datetime) -> None:
        """Write the last update datetime value."""

    @property
    def state(self) -> ClientState:
        """Return the current client state."""

    async def check_connection_availability(self, *, handle_ping_pong: bool) -> bool:
        """Check if proxy is still initialized."""

    def is_callback_alive(self) -> bool:
        """Return if XmlRPC-Server is alive based on received events for this client."""

    async def is_connected(self) -> bool:
        """Perform actions required for connectivity check."""

    async def reconnect(self) -> bool:
        """Re-init all RPC clients."""

    def reset_circuit_breakers(self) -> None:
        """Reset all circuit breakers to closed state."""


class ClientLifecycle(Protocol):
    """
    Protocol for client lifecycle operations.

    Provides initialization and shutdown operations.
    """

    __slots__ = ()

    async def deinitialize_proxy(self) -> ProxyInitState:
        """De-init to stop the backend from sending events for this remote."""

    async def init_client(self) -> None:
        """Initialize the client."""

    async def initialize_proxy(self) -> ProxyInitState:
        """Initialize the proxy has to tell the backend where to send the events."""

    async def reinitialize_proxy(self) -> ProxyInitState:
        """Reinit Proxy."""

    async def stop(self) -> None:
        """Stop depending services."""


class ClientCapabilities(Protocol):
    """
    Protocol for client capability flags.

    Provides access to feature support flags indicating backend capabilities.
    """

    __slots__ = ()

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


class DeviceDiscoveryOperations(Protocol):
    """
    Protocol for device discovery operations.

    Provides methods for listing and discovering devices from the backend.
    Implemented by DeviceOperationsHandler.
    """

    __slots__ = ()

    async def fetch_all_device_data(self) -> None:
        """Fetch all device data from the backend."""

    async def fetch_device_details(self) -> None:
        """Get all names via JSON-RPC and store in data."""

    async def get_all_device_descriptions(self, *, device_address: str) -> tuple[DeviceDescription, ...]:
        """Get all device descriptions from the backend."""

    async def get_device_description(self, *, address: str) -> DeviceDescription | None:
        """Get device descriptions from the backend."""

    async def list_devices(self) -> tuple[DeviceDescription, ...] | None:
        """List devices of the backend."""


class ParamsetOperations(Protocol):
    """
    Protocol for paramset operations.

    Provides methods for reading and writing paramsets and paramset descriptions.
    Implemented by DeviceOperationsHandler.
    """

    __slots__ = ()

    async def fetch_paramset_description(self, *, channel_address: str, paramset_key: ParamsetKey) -> None:
        """Fetch a specific paramset and add it to the known ones."""

    async def fetch_paramset_descriptions(self, *, device_description: DeviceDescription) -> None:
        """Fetch paramsets for provided device description."""

    async def get_all_paramset_descriptions(
        self, *, device_descriptions: tuple[DeviceDescription, ...]
    ) -> dict[str, dict[ParamsetKey, dict[str, ParameterData]]]:
        """Get all paramset descriptions for provided device descriptions."""

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

    async def update_paramset_descriptions(self, *, device_address: str) -> None:
        """Update paramsets descriptions for provided device_address."""


class ValueOperations(Protocol):
    """
    Protocol for value read/write operations.

    Provides methods for reading and writing single parameter values.
    Implemented by DeviceOperationsHandler.
    """

    __slots__ = ()

    async def get_value(
        self,
        *,
        channel_address: str,
        paramset_key: ParamsetKey,
        parameter: str,
        call_source: CallSource = CallSource.MANUAL_OR_SCHEDULED,
    ) -> Any:
        """Return a value from the backend."""

    async def report_value_usage(self, *, address: str, value_id: str, ref_counter: int) -> bool:
        """Report value usage."""

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


class LinkOperations(Protocol):
    """
    Protocol for device linking operations.

    Provides methods for creating and managing direct links between devices.
    Implemented by LinkManagementHandler.
    """

    __slots__ = ()

    async def add_link(self, *, sender_address: str, receiver_address: str, name: str, description: str) -> None:
        """Add a link between two devices."""

    async def get_link_peers(self, *, address: str) -> tuple[str, ...]:
        """Return a list of link peers."""

    async def get_links(self, *, address: str, flags: int) -> dict[str, Any]:
        """Return a list of links."""

    async def remove_link(self, *, sender_address: str, receiver_address: str) -> None:
        """Remove a link between two devices."""


class FirmwareOperations(Protocol):
    """
    Protocol for firmware update operations.

    Provides methods for updating device and system firmware.
    Implemented by FirmwareHandler.
    """

    __slots__ = ()

    async def trigger_firmware_update(self) -> bool:
        """Trigger the CCU firmware update process."""

    async def update_device_firmware(self, *, device_address: str) -> bool:
        """Update the firmware of a Homematic device."""


class SystemVariableOperations(Protocol):
    """
    Protocol for system variable operations.

    Provides methods for managing CCU system variables.
    Implemented by SystemVariableHandler.
    """

    __slots__ = ()

    async def delete_system_variable(self, *, name: str) -> bool:
        """Delete a system variable from the backend."""

    async def get_all_system_variables(self, *, markers: tuple[Any, ...]) -> tuple[Any, ...] | None:
        """Get all system variables from the backend."""

    async def get_system_variable(self, *, name: str) -> Any:
        """Get single system variable from the backend."""

    async def set_system_variable(self, *, legacy_name: str, value: Any) -> bool:
        """Set a system variable on the backend."""


class ProgramOperations(Protocol):
    """
    Protocol for program operations.

    Provides methods for managing CCU programs.
    Implemented by ProgramHandler.
    """

    __slots__ = ()

    async def execute_program(self, *, pid: str) -> bool:
        """Execute a program on the backend."""

    async def get_all_programs(self, *, markers: tuple[Any, ...]) -> tuple[ProgramData, ...]:
        """Get all programs, if available."""

    async def has_program_ids(self, *, rega_id: int) -> bool:
        """Return if a channel has program ids."""

    async def set_program_state(self, *, pid: str, state: bool) -> bool:
        """Set the program state on the backend."""


class BackupOperations(Protocol):
    """
    Protocol for backup operations.

    Provides methods for creating and downloading CCU backups.
    Implemented by ClientCCU.
    """

    __slots__ = ()

    async def create_backup_and_download(
        self,
        *,
        max_wait_time: float = ...,
        poll_interval: float = ...,
    ) -> BackupData | None:
        """Create a backup on the CCU and download it."""


class MetadataOperations(Protocol):
    """
    Protocol for metadata and system operations.

    Provides methods for metadata, rooms, functions, install mode, inbox devices,
    service messages, and other system-level operations.
    Implemented by MetadataHandler.
    """

    __slots__ = ()

    async def accept_device_in_inbox(self, *, device_address: str) -> bool:
        """Accept a device from the CCU inbox."""

    async def get_all_functions(self) -> dict[str, set[str]]:
        """Get all functions from the backend."""

    async def get_all_rooms(self) -> dict[str, set[str]]:
        """Get all rooms from the backend."""

    async def get_inbox_devices(self) -> tuple[InboxDeviceData, ...]:
        """Get all devices in the inbox (not yet configured)."""

    async def get_install_mode(self) -> int:
        """Return the remaining time in install mode."""

    async def get_metadata(self, *, address: str, data_id: str) -> dict[str, Any]:
        """Return the metadata for an object."""

    async def get_rega_id_by_address(self, *, address: str) -> int | None:
        """Get the ReGa ID for a device or channel address."""

    async def get_service_messages(self, *, message_type: Any | None = None) -> tuple[Any, ...]:
        """Get all active service messages from the backend."""

    async def get_system_update_info(self) -> Any | None:
        """Get system update information from the backend."""

    async def rename_channel(self, *, rega_id: int, new_name: str) -> bool:
        """Rename a channel on the CCU."""

    async def rename_device(self, *, rega_id: int, new_name: str) -> bool:
        """Rename a device on the CCU."""

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


class ClientSupport(Protocol):
    """
    Protocol for client support operations.

    Provides utility methods and caches that are implemented directly by ClientCCU
    rather than by handlers.
    """

    __slots__ = ()

    @property
    def last_value_send_cache(self) -> CommandCacheProtocol:
        """Return the last value send cache."""

    @property
    def ping_pong_cache(self) -> PingPongCacheProtocol:
        """Return the ping pong cache."""

    def get_product_group(self, *, model: str) -> ProductGroup:
        """Return the product group."""

    def get_virtual_remote(self) -> DeviceProtocol | None:
        """Get the virtual remote for the Client."""


# =============================================================================
# Client Combined Sub-Protocol Interfaces
# =============================================================================


@runtime_checkable
class ValueAndParamsetOperations(ValueOperations, ParamsetOperations, Protocol):
    """
    Combined protocol for value and paramset operations.

    Used by components that need to send values to the backend,
    either individually (set_value) or in batches (put_paramset).
    Reduces coupling compared to using full ClientProtocol.

    Implemented by: ClientCCU, ClientJsonCCU, ClientHomegear
    """

    __slots__ = ()


@runtime_checkable
class DeviceDiscoveryWithIdentity(DeviceDiscoveryOperations, ClientIdentity, Protocol):
    """
    Combined protocol for device discovery with client identity.

    Used by components that need to discover devices and access
    basic client identification (interface_id, interface).
    Reduces coupling compared to using full ClientProtocol.

    Implemented by: ClientCCU, ClientJsonCCU, ClientHomegear
    """

    __slots__ = ()


@runtime_checkable
class DeviceDiscoveryAndMetadata(DeviceDiscoveryOperations, MetadataOperations, Protocol):
    """
    Combined protocol for device discovery and metadata operations.

    Used by components that need to discover devices and perform
    metadata operations like renaming devices/channels.
    Reduces coupling compared to using full ClientProtocol.

    Implemented by: ClientCCU, ClientJsonCCU, ClientHomegear
    """

    __slots__ = ()


# =============================================================================
# Client Composite Protocol Interface
# =============================================================================


@runtime_checkable
class ClientProtocol(
    ClientIdentity,
    ClientConnection,
    ClientLifecycle,
    ClientCapabilities,
    DeviceDiscoveryOperations,
    ParamsetOperations,
    ValueOperations,
    LinkOperations,
    FirmwareOperations,
    SystemVariableOperations,
    ProgramOperations,
    BackupOperations,
    MetadataOperations,
    ClientSupport,
    Protocol,
):
    """
    Composite protocol for complete Homematic client operations.

    Combines all client sub-protocols into a single interface providing full
    access to backend communication, device management, and system operations.
    Implemented by ClientCCU, ClientJsonCCU, and ClientHomegear.

    Sub-protocols:
        - ClientIdentity: Basic identification
        - ClientConnection: Connection state management
        - ClientLifecycle: Lifecycle operations
        - ClientCapabilities: Feature support flags
        - DeviceDiscoveryOperations: Device discovery
        - ParamsetOperations: Paramset operations
        - ValueOperations: Value read/write
        - LinkOperations: Device linking
        - FirmwareOperations: Firmware updates
        - SystemVariableOperations: System variables
        - ProgramOperations: Program execution
        - BackupOperations: Backup creation
        - MetadataOperations: Metadata and system operations
        - ClientSupport: Utility methods and caches
    """

    __slots__ = ()


# =============================================================================
# Client-Related Protocols
# =============================================================================


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
    def clients(self) -> tuple[ClientProtocol, ...]:
        """Get all clients as a tuple (snapshot for safe iteration)."""

    @property
    @abstractmethod
    def interface_ids(self) -> frozenset[str]:
        """Get all interface IDs."""

    @property
    @abstractmethod
    def poll_clients(self) -> tuple[ClientProtocol, ...] | None:
        """Get clients that require polling."""

    @abstractmethod
    def get_client(self, *, interface_id: str | None = None, interface: Interface | None = None) -> ClientProtocol:
        """Get client by interface_id or interface type."""

    @abstractmethod
    async def restart_clients(self) -> None:
        """Restart all clients."""


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


@runtime_checkable
class LastEventTracker(Protocol):
    """
    Protocol for tracking last event times per interface.

    Implemented by CentralUnit.
    """

    @abstractmethod
    def get_last_event_seen_for_interface(self, *, interface_id: str) -> datetime | None:
        """Get the last event timestamp for an interface."""


@runtime_checkable
class DeviceLookup(Protocol):
    """
    Protocol for looking up devices and data points.

    Implemented by CentralUnit.
    """

    @abstractmethod
    def get_device(self, *, address: str) -> DeviceProtocol | None:
        """Get device by address."""

    @abstractmethod
    def get_generic_data_point(
        self,
        *,
        channel_address: str,
        parameter: str,
        paramset_key: ParamsetKey,
    ) -> Any | None:
        """Get generic data point."""


@runtime_checkable
class NewDeviceHandler(Protocol):
    """
    Protocol for handling new device registration.

    Implemented by CentralUnit.
    """

    @abstractmethod
    async def add_new_devices(
        self,
        *,
        interface_id: str,
        device_descriptions: tuple[DeviceDescription, ...],
    ) -> None:
        """Add new devices from the backend."""


@runtime_checkable
class DataCacheWriter(Protocol):
    """
    Protocol for writing data to the central data cache.

    Implemented by CentralDataCache.
    """

    @abstractmethod
    def add_data(self, *, interface: Interface, all_device_data: Mapping[str, Any]) -> None:
        """Add all device data to the cache."""


@runtime_checkable
class ParamsetDescriptionWriter(Protocol):
    """
    Protocol for writing paramset descriptions.

    Implemented by ParamsetDescriptionCache.
    """

    @abstractmethod
    def add(
        self,
        *,
        interface_id: str,
        channel_address: str,
        paramset_key: ParamsetKey,
        paramset_description: dict[str, Any],
    ) -> None:
        """Add a paramset description."""


@runtime_checkable
class DeviceDetailsWriter(Protocol):
    """
    Protocol for writing device details.

    Implemented by DeviceDetailsCache.
    """

    @property
    @abstractmethod
    def device_channel_rega_ids(self) -> Mapping[str, int]:
        """Return the device channel ReGa IDs."""

    @abstractmethod
    def add_address_rega_id(self, *, address: str, rega_id: int) -> None:
        """Add a ReGa ID for an address."""

    @abstractmethod
    def add_interface(self, *, address: str, interface: Interface) -> None:
        """Add an interface for an address."""

    @abstractmethod
    def add_name(self, *, address: str, name: str) -> None:
        """Add a name for an address."""


@runtime_checkable
class DeviceDescriptionsAccess(Protocol):
    """
    Protocol for accessing device descriptions from cache.

    Implemented by DeviceDescriptionCache.
    """

    @abstractmethod
    def find_device_description(
        self,
        *,
        interface_id: str,
        device_address: str,
    ) -> DeviceDescription | None:
        """Find a device description."""

    @abstractmethod
    def get_device_descriptions(self, *, interface_id: str) -> Mapping[str, DeviceDescription]:
        """Get all device descriptions for an interface."""


@runtime_checkable
class ConnectionStateProvider(Protocol):
    """
    Protocol for accessing connection state.

    Implemented by CentralUnit.
    """

    @property
    @abstractmethod
    def connection_state(self) -> CentralConnectionState:
        """Get connection state."""


@runtime_checkable
class SessionRecorderProvider(Protocol):
    """
    Protocol for accessing session recorder.

    Implemented by CentralUnit.
    """

    @property
    @abstractmethod
    def recorder(self) -> SessionRecorder:
        """Get session recorder."""


@runtime_checkable
class JsonRpcClientProvider(Protocol):
    """
    Protocol for accessing JSON-RPC client.

    Implemented by CentralUnit.
    """

    @property
    @abstractmethod
    def json_rpc_client(self) -> AioJsonRpcAioHttpClient:
        """Get JSON-RPC client."""


@runtime_checkable
class CallbackAddressProvider(Protocol):
    """
    Protocol for accessing callback address information.

    Implemented by CentralUnit.
    """

    @property
    @abstractmethod
    def callback_ip_addr(self) -> str:
        """Get callback IP address."""

    @property
    @abstractmethod
    def listen_port_xml_rpc(self) -> int:
        """Get XML-RPC listen port."""


@runtime_checkable
class CommandCacheProtocol(Protocol):
    """Protocol for command cache operations."""

    @abstractmethod
    def add_put_paramset(
        self, *, channel_address: str, paramset_key: ParamsetKey, values: dict[str, Any]
    ) -> set[tuple[DataPointKey, Any]]:
        """Add data from put paramset command."""

    @abstractmethod
    def add_set_value(
        self,
        *,
        channel_address: str,
        parameter: str,
        value: Any,
    ) -> set[tuple[DataPointKey, Any]]:
        """Add data from set value command."""

    @abstractmethod
    def clear(self) -> None:
        """Clear all cached command entries."""

    @abstractmethod
    def get_last_value_send(self, *, dpk: DataPointKey, max_age: int = ...) -> Any:
        """Return the last send value."""

    @abstractmethod
    def remove_last_value_send(
        self,
        *,
        dpk: DataPointKey,
        value: Any = None,
        max_age: int = ...,
    ) -> None:
        """Remove the last send value."""


@runtime_checkable
class PingPongCacheProtocol(Protocol):
    """Protocol for ping/pong cache operations."""

    @abstractmethod
    def clear(self) -> None:
        """Clear the cache."""

    @abstractmethod
    def handle_received_pong(self, *, pong_token: str) -> None:
        """Handle received pong token."""

    @abstractmethod
    def handle_send_ping(self, *, ping_token: str) -> None:
        """Handle send ping token."""


@runtime_checkable
class ClientDependencies(Protocol):
    """
    Composite protocol for all dependencies required by Client classes.

    This protocol combines all the individual protocols needed by ClientCCU,
    ClientConfig, and related classes. CentralUnit implements this protocol.

    Using a composite protocol allows clients to depend on a single interface
    instead of many individual protocols, while still maintaining decoupling
    from the full CentralUnit implementation.
    """

    # CentralInfo
    @property
    @abstractmethod
    def available(self) -> bool:
        """Check if central is available."""

    @property
    @abstractmethod
    def cache_coordinator(self) -> CacheCoordinator:
        """Get cache coordinator."""

    @property
    @abstractmethod
    def callback_ip_addr(self) -> str:
        """Return callback IP address."""

    @property
    @abstractmethod
    def config(self) -> CentralConfig:
        """Return central configuration."""

    @property
    @abstractmethod
    def connection_state(self) -> CentralConnectionState:
        """Return connection state."""

    @property
    @abstractmethod
    def device_coordinator(self) -> DeviceCoordinator:
        """Return the device coordinator."""

    @property
    @abstractmethod
    def device_registry(self) -> DeviceRegistry:
        """Return the device registry."""

    @property
    @abstractmethod
    def event_bus(self) -> EventBus:
        """Return the event bus."""

    @property
    @abstractmethod
    def event_coordinator(self) -> EventCoordinator:
        """Return the event coordinator for publishing events."""

    @property
    @abstractmethod
    def info_payload(self) -> Mapping[str, Any]:
        """Return the info payload."""

    @property
    @abstractmethod
    def json_rpc_client(self) -> AioJsonRpcAioHttpClient:
        """Return JSON-RPC client."""

    @property
    @abstractmethod
    def listen_port_xml_rpc(self) -> int:
        """Return XML-RPC listen port."""

    @property
    @abstractmethod
    def looper(self) -> TaskScheduler:
        """Return task scheduler/looper."""

    @property
    @abstractmethod
    def model(self) -> str | None:
        """Return backend model."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return central name."""

    @property
    @abstractmethod
    def state(self) -> CentralState:
        """Return the current central state from the state machine."""

    @abstractmethod
    def get_generic_data_point(
        self,
        *,
        channel_address: str,
        parameter: str,
        paramset_key: ParamsetKey,
    ) -> Any | None:
        """Return generic data point."""

    @abstractmethod
    async def save_files(
        self,
        *,
        save_device_descriptions: bool = False,
        save_paramset_descriptions: bool = False,
    ) -> None:
        """Save persistent files to disk."""
