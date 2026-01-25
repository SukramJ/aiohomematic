# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Central unit protocol interfaces.

This module defines protocol interfaces for CentralUnit operations,
allowing components to depend on central functionality without coupling
to the full CentralUnit implementation.
"""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Protocol, Unpack, runtime_checkable

from aiohttp import ClientSession

from aiohomematic.const import (
    BackupData,
    CentralState,
    ClientState,
    DescriptionMarker,
    DeviceFirmwareState,
    DeviceTriggerEventType,
    EventData,
    FailureReason,
    Interface,
    OptionalSettings,
    ParamsetKey,
    ScheduleTimerConfig,
    SystemEventType,
    SystemInformation,
    TimeoutConfig,
)
from aiohomematic.metrics._protocols import DeviceProviderForMetricsProtocol, HubDataPointManagerForMetricsProtocol

if TYPE_CHECKING:
    from aiohomematic.central.coordinators import (
        ClientCoordinator,
        DeviceCoordinator,
        EventCoordinator,
        SystemEventArgs,
    )
    from aiohomematic.central.events import EventBus
    from aiohomematic.client import InterfaceConfig
    from aiohomematic.interfaces import (
        CallbackDataPointProtocol,
        ChannelProtocol,
        GenericDataPointProtocolAny,
        GenericSysvarDataPointProtocol,
    )
    from aiohomematic.metrics import MetricsObserver
    from aiohomematic.model.hub import ProgramDpType
    from aiohomematic.store import StorageFactoryProtocol


@runtime_checkable
class CentralConfigProtocol(Protocol):
    """
    Protocol for CentralConfig interface.

    This protocol defines the configuration interface required by CentralUnit,
    enabling dependency inversion to eliminate circular imports between
    config.py and central_unit.py.

    Implemented by CentralConfig.
    """

    @property
    @abstractmethod
    def callback_host(self) -> str | None:
        """Return the callback host address."""

    @property
    @abstractmethod
    def callback_port_xml_rpc(self) -> int | None:
        """Return the callback port for XML-RPC."""

    @property
    @abstractmethod
    def central_id(self) -> str:
        """Return the central ID."""

    @property
    @abstractmethod
    def client_session(self) -> ClientSession | None:
        """Return the aiohttp client session."""

    @property
    @abstractmethod
    def connection_check_port(self) -> int:
        """Return the connection check port."""

    @property
    @abstractmethod
    def default_callback_port_xml_rpc(self) -> int:
        """Return the default callback port for XML-RPC."""

    @property
    @abstractmethod
    def delay_new_device_creation(self) -> bool:
        """Return if new device creation should be delayed."""

    @property
    @abstractmethod
    def enable_device_firmware_check(self) -> bool:
        """Return if device firmware check is enabled."""

    @property
    @abstractmethod
    def enable_program_scan(self) -> bool:
        """Return if program scanning is enabled."""

    @property
    @abstractmethod
    def enable_sysvar_scan(self) -> bool:
        """Return if system variable scanning is enabled."""

    @property
    @abstractmethod
    def enable_xml_rpc_server(self) -> bool:
        """Return if XML-RPC server should be enabled."""

    @property
    @abstractmethod
    def enabled_interface_configs(self) -> frozenset[InterfaceConfig]:
        """Return the enabled interface configurations."""

    @property
    @abstractmethod
    def host(self) -> str:
        """Return the host address."""

    @property
    @abstractmethod
    def ignore_custom_device_definition_models(self) -> frozenset[str]:
        """Return the set of device models to ignore for custom definitions."""

    @property
    @abstractmethod
    def interfaces_requiring_periodic_refresh(self) -> frozenset[Interface]:
        """Return the set of interfaces requiring periodic refresh."""

    @property
    @abstractmethod
    def json_port(self) -> int | None:
        """Return the JSON-RPC port."""

    @property
    @abstractmethod
    def listen_ip_addr(self) -> str | None:
        """Return the listen IP address."""

    @property
    @abstractmethod
    def listen_port_xml_rpc(self) -> int | None:
        """Return the listen port for XML-RPC."""

    @property
    @abstractmethod
    def locale(self) -> str:
        """Return the locale setting."""

    @property
    @abstractmethod
    def max_read_workers(self) -> int:
        """Return the maximum number of read workers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the central name."""

    @property
    @abstractmethod
    def optional_settings(self) -> frozenset[OptionalSettings | str]:
        """Return the optional settings."""

    @property
    @abstractmethod
    def password(self) -> str:
        """Return the password."""

    @property
    @abstractmethod
    def program_markers(self) -> tuple[DescriptionMarker | str, ...]:
        """Return the program markers for filtering."""

    @property
    @abstractmethod
    def schedule_timer_config(self) -> ScheduleTimerConfig:
        """Return the schedule timer configuration."""

    @property
    @abstractmethod
    def session_recorder_randomize_output(self) -> bool:
        """Return if session recorder should randomize output."""

    @property
    @abstractmethod
    def session_recorder_start(self) -> bool:
        """Return if session recorder should start."""

    @property
    @abstractmethod
    def session_recorder_start_for_seconds(self) -> int:
        """Return the session recorder start duration in seconds."""

    @property
    @abstractmethod
    def start_direct(self) -> bool:
        """Return if direct start mode is enabled."""

    @property
    @abstractmethod
    def storage_directory(self) -> str:
        """Return the storage directory path."""

    @property
    @abstractmethod
    def storage_factory(self) -> StorageFactoryProtocol | None:
        """Return the storage factory."""

    @property
    @abstractmethod
    def sysvar_markers(self) -> tuple[DescriptionMarker | str, ...]:
        """Return the system variable markers for filtering."""

    @property
    @abstractmethod
    def timeout_config(self) -> TimeoutConfig:
        """Return the timeout configuration."""

    @property
    @abstractmethod
    def tls(self) -> bool:
        """Return if TLS is enabled."""

    @property
    @abstractmethod
    def un_ignore_list(self) -> frozenset[str]:
        """Return the un-ignore list."""

    @property
    @abstractmethod
    def use_caches(self) -> bool:
        """Return if caches should be used."""

    @property
    @abstractmethod
    def use_group_channel_for_cover_state(self) -> bool:
        """Return if group channel should be used for cover state."""

    @property
    @abstractmethod
    def username(self) -> str:
        """Return the username."""

    @property
    @abstractmethod
    def verify_tls(self) -> bool:
        """Return if TLS verification is enabled."""

    @abstractmethod
    def create_central_url(self) -> str:
        """Create and return the central URL."""


@runtime_checkable
class CentralInfoProtocol(Protocol):
    """
    Protocol for accessing central system information.

    Implemented by CentralUnit.
    """

    @property
    @abstractmethod
    def available(self) -> bool:
        """Check if central is available."""

    @property
    @abstractmethod
    def info_payload(self) -> Mapping[str, Any]:
        """Return the info payload."""

    @property
    @abstractmethod
    def model(self) -> str | None:
        """Get backend model."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Get central name."""

    @property
    @abstractmethod
    def state(self) -> CentralState:
        """Return the current central state from the state machine."""


@runtime_checkable
class ConfigProviderProtocol(Protocol):
    """
    Protocol for accessing configuration.

    Implemented by CentralUnit.
    """

    @property
    @abstractmethod
    def config(self) -> CentralConfigProtocol:
        """Get central configuration."""


@runtime_checkable
class SystemInfoProviderProtocol(Protocol):
    """
    Protocol for accessing system information.

    Implemented by CentralUnit.
    """

    @property
    @abstractmethod
    def system_information(self) -> SystemInformation:
        """Get system information."""


@runtime_checkable
class BackupProviderProtocol(Protocol):
    """
    Protocol for backup operations.

    Implemented by CentralUnit.
    """

    @abstractmethod
    async def create_backup_and_download(self) -> BackupData | None:
        """Create a backup on the CCU and download it."""


@runtime_checkable
class DeviceManagementProtocol(Protocol):
    """
    Protocol for device management operations.

    Provides methods for managing devices on the CCU including
    accepting inbox devices, renaming devices/channels, and install mode.
    Implemented by CentralUnit.
    """

    @abstractmethod
    async def accept_device_in_inbox(self, *, device_address: str) -> bool:
        """Accept a device from the CCU inbox."""

    @abstractmethod
    async def get_install_mode(self) -> int:
        """Return the remaining time in install mode."""

    @abstractmethod
    async def rename_device(self, *, device_address: str, name: str, include_channels: bool = False) -> bool:
        """Rename a device on the CCU."""

    @abstractmethod
    async def set_install_mode(
        self,
        *,
        on: bool = True,
        time: int = 60,
        mode: int = 1,
        device_address: str | None = None,
    ) -> bool:
        """
        Set the install mode on the backend.

        Args:
            on: Enable or disable install mode.
            time: Duration in seconds (default 60).
            mode: Mode 1=normal, 2=set all ROAMING devices into install mode.
            device_address: Optional device address to limit pairing.

        Returns:
            True if successful.

        """


@runtime_checkable
class EventBusProviderProtocol(Protocol):
    """
    Protocol for accessing event bus.

    Implemented by CentralUnit.
    """

    @property
    @abstractmethod
    def event_bus(self) -> EventBus:
        """Get event bus instance."""


@runtime_checkable
class EventPublisherProtocol(Protocol):
    """
    Protocol for publishing events to the system.

    Implemented by EventCoordinator.
    """

    @abstractmethod
    def publish_device_trigger_event(self, *, trigger_type: DeviceTriggerEventType, event_data: EventData) -> None:
        """Publish a Homematic event."""

    @abstractmethod
    def publish_system_event(self, *, system_event: SystemEventType, **kwargs: Unpack[SystemEventArgs]) -> None:
        """Publish a backend system event."""


@runtime_checkable
class DataPointProviderProtocol(Protocol):
    """
    Protocol for accessing data points.

    Implemented by CentralUnit.
    """

    @abstractmethod
    def get_data_point_by_custom_id(self, *, custom_id: str) -> CallbackDataPointProtocol | None:
        """Return Homematic data_point by custom_id."""

    @abstractmethod
    def get_readable_generic_data_points(
        self,
        *,
        paramset_key: ParamsetKey | None = None,
        interface: Interface | None = None,
    ) -> tuple[GenericDataPointProtocolAny, ...]:
        """Get readable generic data points."""


@runtime_checkable
class DeviceProviderProtocol(DeviceProviderForMetricsProtocol, Protocol):
    """
    Protocol for accessing devices.

    Extends DeviceProviderForMetricsProtocol with additional properties.
    Implemented by CentralUnit.
    """

    @property
    @abstractmethod
    def interfaces(self) -> frozenset[Interface]:
        """Get all interfaces."""


@runtime_checkable
class ChannelLookupProtocol(Protocol):
    """
    Protocol for looking up channels.

    Implemented by CentralUnit.
    """

    @abstractmethod
    def get_channel(self, *, channel_address: str) -> ChannelProtocol | None:
        """Get channel by address."""

    @abstractmethod
    def identify_channel(self, *, text: str) -> ChannelProtocol | None:
        """Identify a channel within a text string."""


@runtime_checkable
class FileOperationsProtocol(Protocol):
    """
    Protocol for file save operations.

    Implemented by CentralUnit.
    """

    @abstractmethod
    async def save_files(
        self, *, save_device_descriptions: bool = False, save_paramset_descriptions: bool = False
    ) -> None:
        """Save persistent files to disk."""


@runtime_checkable
class FirmwareDataRefresherProtocol(Protocol):
    """
    Protocol for refreshing firmware data.

    Implemented by DeviceCoordinator.
    """

    @abstractmethod
    async def refresh_firmware_data(self, *, device_address: str | None = None) -> None:
        """Refresh device firmware data."""

    @abstractmethod
    async def refresh_firmware_data_by_state(
        self,
        *,
        device_firmware_states: tuple[DeviceFirmwareState, ...],
    ) -> None:
        """Refresh device firmware data for devices in specific states."""


class DeviceDataRefresherProtocol(Protocol):
    """
    Protocol for refreshing device data.

    Implemented by CentralUnit.
    """

    @abstractmethod
    async def load_and_refresh_data_point_data(self, *, interface: Interface) -> None:
        """Load and refresh data point data for an interface."""


@runtime_checkable
class DataCacheProviderProtocol(Protocol):
    """
    Protocol for accessing data cache.

    Implemented by CentralDataCache.
    """

    @abstractmethod
    def get_data(self, *, interface: Interface, channel_address: str, parameter: str) -> Any:
        """Get cached data for a parameter."""


@runtime_checkable
class HubFetchOperationsProtocol(Protocol):
    """
    Base protocol for hub fetch operations.

    Defines the common fetch methods shared between HubDataFetcherProtocol and HubProtocol.
    This eliminates duplication of fetch method signatures.
    """

    @abstractmethod
    def fetch_connectivity_data(self, *, scheduled: bool) -> None:
        """Refresh connectivity binary sensors with current values."""

    @abstractmethod
    async def fetch_inbox_data(self, *, scheduled: bool) -> None:
        """Fetch inbox data from the backend."""

    @abstractmethod
    def fetch_metrics_data(self, *, scheduled: bool) -> None:
        """Refresh metrics hub sensors with current values."""

    @abstractmethod
    async def fetch_program_data(self, *, scheduled: bool) -> None:
        """Fetch program data from the backend."""

    @abstractmethod
    async def fetch_system_update_data(self, *, scheduled: bool) -> None:
        """Fetch system update data from the backend."""

    @abstractmethod
    async def fetch_sysvar_data(self, *, scheduled: bool) -> None:
        """Fetch system variable data from the backend."""


@runtime_checkable
class HubDataFetcherProtocol(HubFetchOperationsProtocol, Protocol):
    """
    Protocol for fetching hub data.

    Extends HubFetchOperationsProtocol with program execution and state management.
    Implemented by HubCoordinator.
    """

    @abstractmethod
    async def execute_program(self, *, pid: str) -> bool:
        """Execute a program on the backend."""

    @abstractmethod
    async def set_program_state(self, *, pid: str, state: bool) -> bool:
        """Set program state on the backend."""


@runtime_checkable
class HubDataPointManagerProtocol(HubDataPointManagerForMetricsProtocol, Protocol):
    """
    Protocol for managing hub-level data points (programs/sysvars).

    Extends HubDataPointManagerForMetricsProtocol with management methods.
    Implemented by CentralUnit.
    """

    @abstractmethod
    def add_program_data_point(self, *, program_dp: ProgramDpType) -> None:
        """Add a program data point."""

    @abstractmethod
    def add_sysvar_data_point(self, *, sysvar_data_point: GenericSysvarDataPointProtocol) -> None:
        """Add a system variable data point."""

    @abstractmethod
    def get_program_data_point(self, *, pid: str) -> ProgramDpType | None:
        """Get a program data point by ID."""

    @abstractmethod
    def get_sysvar_data_point(self, *, vid: str) -> GenericSysvarDataPointProtocol | None:
        """Get a system variable data point by ID."""

    @abstractmethod
    def remove_program_button(self, *, pid: str) -> None:
        """Remove a program button."""

    @abstractmethod
    def remove_sysvar_data_point(self, *, vid: str) -> None:
        """Remove a system variable data point."""


@runtime_checkable
class EventSubscriptionManagerProtocol(Protocol):
    """
    Protocol for managing event subscriptions.

    Implemented by EventCoordinator.
    """

    @abstractmethod
    def add_data_point_subscription(self, *, data_point: Any) -> None:
        """Add an event subscription for a data point."""


@runtime_checkable
class RpcServerCentralProtocol(Protocol):
    """
    Protocol for CentralUnit operations required by RpcServer.

    This protocol defines the minimal interface needed by the XML-RPC server
    to interact with a central unit, avoiding direct coupling to CentralUnit.

    Implemented by CentralUnit.
    """

    @property
    @abstractmethod
    def client_coordinator(self) -> ClientCoordinator:
        """Return the client coordinator."""

    @property
    @abstractmethod
    def device_coordinator(self) -> DeviceCoordinator:
        """Return the device coordinator."""

    @property
    @abstractmethod
    def event_coordinator(self) -> EventCoordinator:
        """Return the event coordinator."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the central name."""


# =============================================================================
# Central State Machine Protocol
# =============================================================================


@runtime_checkable
class CentralStateMachineProtocol(Protocol):
    """
    Protocol for the central state machine.

    Provides access to the overall system state and state transitions.
    Implemented by CentralStateMachine.
    """

    @property
    @abstractmethod
    def degraded_interfaces(self) -> Mapping[str, FailureReason]:
        """Return the interfaces that are degraded with their failure reasons."""

    @property
    @abstractmethod
    def failure_interface_id(self) -> str | None:
        """Return the interface ID that caused the failure, if applicable."""

    @property
    @abstractmethod
    def failure_message(self) -> str:
        """Return human-readable failure message."""

    @property
    @abstractmethod
    def failure_reason(self) -> FailureReason:
        """Return the reason for the failed state."""

    @property
    @abstractmethod
    def is_degraded(self) -> bool:
        """Return True if system is in degraded state."""

    @property
    @abstractmethod
    def is_failed(self) -> bool:
        """Return True if system is in failed state."""

    @property
    @abstractmethod
    def is_operational(self) -> bool:
        """Return True if system is operational (RUNNING or DEGRADED)."""

    @property
    @abstractmethod
    def is_recovering(self) -> bool:
        """Return True if recovery is in progress."""

    @property
    @abstractmethod
    def is_running(self) -> bool:
        """Return True if system is fully running."""

    @property
    @abstractmethod
    def is_stopped(self) -> bool:
        """Return True if system is stopped."""

    @property
    @abstractmethod
    def state(self) -> CentralState:
        """Return the current state."""

    @abstractmethod
    def can_transition_to(self, *, target: CentralState) -> bool:
        """Check if transition to target state is valid."""

    @abstractmethod
    def transition_to(
        self,
        *,
        target: CentralState,
        reason: str = "",
        force: bool = False,
        failure_reason: FailureReason = FailureReason.NONE,
        failure_interface_id: str | None = None,
        degraded_interfaces: Mapping[str, FailureReason] | None = None,
    ) -> None:
        """Transition to a new state."""


@runtime_checkable
class CentralStateMachineProviderProtocol(Protocol):
    """
    Protocol for accessing the central state machine.

    Implemented by CentralUnit.
    """

    @property
    @abstractmethod
    def central_state_machine(self) -> CentralStateMachineProtocol:
        """Return the central state machine."""


# =============================================================================
# Health Tracking Protocols
# =============================================================================


@runtime_checkable
class ConnectionHealthProtocol(Protocol):
    """
    Protocol for per-client connection health.

    Implemented by ConnectionHealth.
    """

    @property
    @abstractmethod
    def client_state(self) -> ClientState:
        """Return the client state."""

    @property
    @abstractmethod
    def health_score(self) -> float:
        """Calculate a numeric health score (0.0 - 1.0)."""

    @property
    @abstractmethod
    def interface(self) -> Interface:
        """Return the interface type."""

    @property
    @abstractmethod
    def interface_id(self) -> str:
        """Return the interface ID."""

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if client is available for operations."""

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if client is in connected state."""

    @property
    @abstractmethod
    def is_degraded(self) -> bool:
        """Check if client is in degraded state."""

    @property
    @abstractmethod
    def is_failed(self) -> bool:
        """Check if client is in failed state."""


@runtime_checkable
class CentralHealthProtocol(Protocol):
    """
    Protocol for aggregated central health.

    Implemented by CentralHealth.
    """

    @property
    @abstractmethod
    def all_clients_healthy(self) -> bool:
        """Check if all clients are fully healthy."""

    @property
    @abstractmethod
    def any_client_healthy(self) -> bool:
        """Check if at least one client is healthy."""

    @property
    @abstractmethod
    def degraded_clients(self) -> list[str]:
        """Return list of interface IDs with degraded health."""

    @property
    @abstractmethod
    def failed_clients(self) -> list[str]:
        """Return list of interface IDs that have failed."""

    @property
    @abstractmethod
    def healthy_clients(self) -> list[str]:
        """Return list of healthy interface IDs."""

    @property
    @abstractmethod
    def overall_health_score(self) -> float:
        """Calculate weighted average health score across all clients."""

    @property
    @abstractmethod
    def primary_client_healthy(self) -> bool:
        """Check if the primary client is healthy."""

    @property
    @abstractmethod
    def state(self) -> CentralState:
        """Return current central state."""

    @abstractmethod
    def get_client_health(self, *, interface_id: str) -> ConnectionHealthProtocol | None:
        """Get health for a specific client."""

    @abstractmethod
    def should_be_degraded(self) -> bool:
        """Determine if central should be in DEGRADED state."""

    @abstractmethod
    def should_be_running(self) -> bool:
        """Determine if central should be in RUNNING state."""


@runtime_checkable
class HealthTrackerProtocol(Protocol):
    """
    Protocol for the health tracker.

    Implemented by HealthTracker.
    """

    @property
    @abstractmethod
    def health(self) -> CentralHealthProtocol:
        """Return the aggregated central health."""

    @abstractmethod
    def get_client_health(self, *, interface_id: str) -> ConnectionHealthProtocol | None:
        """Get health for a specific client."""

    @abstractmethod
    def record_event_received(self, *, interface_id: str) -> None:
        """Record that an event was received for an interface."""

    @abstractmethod
    def record_failed_request(self, *, interface_id: str) -> None:
        """Record a failed RPC request for an interface."""

    @abstractmethod
    def record_successful_request(self, *, interface_id: str) -> None:
        """Record a successful RPC request for an interface."""

    @abstractmethod
    def register_client(self, *, interface_id: str, interface: Interface) -> ConnectionHealthProtocol:
        """Register a client for health tracking."""

    @abstractmethod
    def set_primary_interface(self, *, interface: Interface) -> None:
        """Set the primary interface for health tracking."""

    @abstractmethod
    def unregister_client(self, *, interface_id: str) -> None:
        """Unregister a client from health tracking."""


@runtime_checkable
class MetricsProviderProtocol(Protocol):
    """
    Protocol for accessing the metrics observer.

    Implemented by CentralUnit.
    """

    @property
    @abstractmethod
    def metrics(self) -> MetricsObserver:
        """Return the metrics observer."""


# =============================================================================
# CentralProtocol Composite
# =============================================================================

# Import protocols from other interface modules for CentralProtocol composition.
# These imports are placed here (after all local protocols are defined) to avoid
# circular import issues while allowing proper inheritance.
from aiohomematic.interfaces.client import (  # noqa: E402
    CallbackAddressProviderProtocol,
    ClientDependenciesProtocol,
    ClientFactoryProtocol,
    ConnectionStateProviderProtocol,
    JsonRpcClientProviderProtocol,
)
from aiohomematic.interfaces.coordinators import CoordinatorProviderProtocol  # noqa: E402


@runtime_checkable
class CentralProtocol(
    # From interfaces/central.py (this module)
    BackupProviderProtocol,
    CentralInfoProtocol,
    ConfigProviderProtocol,
    DataPointProviderProtocol,
    DeviceDataRefresherProtocol,
    DeviceProviderProtocol,
    EventBusProviderProtocol,
    FileOperationsProtocol,
    SystemInfoProviderProtocol,
    # From interfaces/client.py
    CallbackAddressProviderProtocol,
    ClientDependenciesProtocol,
    ClientFactoryProtocol,
    ConnectionStateProviderProtocol,
    JsonRpcClientProviderProtocol,
    # From interfaces/coordinators.py
    CoordinatorProviderProtocol,
    Protocol,
):
    """
    Composite protocol for CentralUnit.

    Combines all sub-protocols that CentralUnit implements, providing a single
    protocol for complete central unit access while maintaining the ability to
    depend on specific sub-protocols when only partial functionality is needed.

    Sub-protocols are organized into categories:

    **Identity & Configuration:**
        - CentralInfoProtocol: Central system identification (includes state)
        - ConfigProviderProtocol: Configuration access
        - SystemInfoProviderProtocol: Backend system information

    **Event System:**
        - EventBusProviderProtocol: Access to the central event bus

    **Cache & Data Access:**
        - DataPointProviderProtocol: Find data points
        - DeviceProviderProtocol: Access device registry (internal use)
        - FileOperationsProtocol: File I/O operations

    **Device Operations:**
        - DeviceDataRefresherProtocol: Refresh device data from backend
        - BackupProviderProtocol: Backup operations

    **Hub Operations:**
        - HubDataFetcherProtocol: Fetch hub data
        - HubDataPointManagerProtocol: Manage hub data points

    **Client Management (via CoordinatorProviderProtocol.client_coordinator):**
        - ClientFactoryProtocol: Create new client instances
        - ClientDependenciesProtocol: Dependencies for clients
        - JsonRpcClientProviderProtocol: JSON-RPC client access
        - ConnectionStateProviderProtocol: Connection state information
        - CallbackAddressProviderProtocol: Callback address management
        - SessionRecorderProviderProtocol: Session recording access

    **Coordinators:**
        - CoordinatorProviderProtocol: Access to coordinators (client_coordinator, event_coordinator, etc.)
    """

    __slots__ = ()
