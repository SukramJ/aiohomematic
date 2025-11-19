"""
Protocol interfaces for reducing CentralUnit coupling.

This module defines protocol interfaces that components can depend on
instead of directly depending on CentralUnit. This allows for:
- Better testability (mock implementations)
- Clearer dependencies (only expose what's needed)
- Reduced coupling (components don't access full CentralUnit API)
"""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable, Collection, Mapping
from typing import Any, Protocol, runtime_checkable

from aiohomematic.const import BackendSystemEvent, DeviceFirmwareState, EventType, SystemInformation


@runtime_checkable
class ParameterVisibilityProvider(Protocol):
    """Protocol for accessing parameter visibility information."""

    @abstractmethod
    def parameter_is_hidden(
        self,
        *,
        channel: Any,
        paramset_key: str,
        parameter: str,
    ) -> bool:
        """Check if a parameter is hidden."""

    @abstractmethod
    def parameter_is_un_ignored(
        self,
        *,
        channel: Any,
        paramset_key: str,
        parameter: str,
        custom_only: bool = False,
    ) -> bool:
        """Check if a parameter is un-ignored (visible)."""


@runtime_checkable
class EventEmitter(Protocol):
    """Protocol for emitting events to the system."""

    @abstractmethod
    def emit_backend_system_callback(
        self,
        *,
        system_event: BackendSystemEvent,
        **kwargs: Any,
    ) -> None:
        """Emit a backend system callback event."""

    @abstractmethod
    def emit_homematic_callback(
        self,
        *,
        event_type: EventType,
        event_data: dict[Any, Any],
    ) -> None:
        """Emit a Homematic callback event."""


@runtime_checkable
class DeviceDetailsProvider(Protocol):
    """Protocol for accessing device details."""

    @abstractmethod
    def get_address_id(self, *, address: str) -> int:
        """Get numeric ID for an address."""

    @abstractmethod
    def get_channel_rooms(self, *, channel_address: str) -> tuple[str, ...]:
        """Get rooms for a channel."""

    @abstractmethod
    def get_function_text(self, *, address: str) -> str | None:
        """Get function text for an address."""


@runtime_checkable
class DeviceDescriptionProvider(Protocol):
    """Protocol for accessing device descriptions."""

    @abstractmethod
    def get_device_description(
        self,
        *,
        interface_id: str,
        device_address: str,
    ) -> dict[str, Any]:
        """Get device description."""

    @abstractmethod
    def get_device_with_channels(
        self,
        *,
        interface_id: str,
        device_address: str,
    ) -> dict[str, dict[str, Any]]:
        """Get device with all channel descriptions."""


@runtime_checkable
class ParamsetDescriptionProvider(Protocol):
    """Protocol for accessing paramset descriptions."""

    @abstractmethod
    def get_channel_paramset_descriptions(
        self,
        *,
        interface_id: str,
        channel_address: str,
    ) -> Mapping[str, Mapping[str, Any]]:
        """Get all paramset descriptions for a channel."""

    @abstractmethod
    def get_parameter_data(
        self,
        *,
        interface_id: str,
        channel_address: str,
        paramset_key: str,
        parameter: str,
    ) -> dict[str, Any] | None:
        """Get parameter data from paramset description."""


@runtime_checkable
class EventSubscriptionManager(Protocol):
    """Protocol for managing event subscriptions."""

    @abstractmethod
    def add_event_subscription(
        self,
        *,
        data_point: Any,  # Avoid circular import
    ) -> None:
        """Add an event subscription for a data point."""

    @abstractmethod
    def remove_event_subscription(
        self,
        *,
        data_point: Any,  # Avoid circular import
    ) -> None:
        """Remove an event subscription for a data point."""


@runtime_checkable
class HubDataPointManager(Protocol):
    """Protocol for managing hub-level data points (programs/sysvars)."""

    @property
    @abstractmethod
    def program_data_points(self) -> Collection[Any]:
        """Get all program data points."""

    @property
    @abstractmethod
    def sysvar_data_points(self) -> Collection[Any]:
        """Get all system variable data points."""

    @abstractmethod
    def add_program_data_point(self, *, program_dp: Any) -> None:
        """Add a program data point."""

    @abstractmethod
    def add_sysvar_data_point(self, *, sysvar_data_point: Any) -> None:
        """Add a system variable data point."""

    @abstractmethod
    def get_program_data_point(self, *, pid: str) -> Any | None:
        """Get a program data point by ID."""

    @abstractmethod
    def get_sysvar_data_point(self, *, vid: str) -> Any | None:
        """Get a system variable data point by ID."""

    @abstractmethod
    def remove_program_button(self, *, pid: str) -> None:
        """Remove a program button."""

    @abstractmethod
    def remove_sysvar_data_point(self, *, vid: str) -> None:
        """Remove a system variable data point."""


@runtime_checkable
class TaskScheduler(Protocol):
    """Protocol for scheduling async tasks."""

    @abstractmethod
    def async_add_executor_job(
        self,
        target: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Add a job to be executed in the executor pool."""

    @abstractmethod
    def create_task(
        self,
        *,
        target: Any,
        name: str,
    ) -> None:
        """Create and schedule an async task."""


@runtime_checkable
class CentralInfo(Protocol):
    """Protocol for accessing central system information."""

    @property
    @abstractmethod
    def available(self) -> bool:
        """Check if central is available."""

    @property
    @abstractmethod
    def model(self) -> str | None:
        """Get backend model."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Get central name."""


@runtime_checkable
class PrimaryClientProvider(Protocol):
    """Protocol for accessing primary client."""

    @property
    @abstractmethod
    def primary_client(self) -> Any:  # Avoid circular import
        """Get primary client."""


@runtime_checkable
class EventRegistry(Protocol):
    """Protocol for registering event handlers."""

    @abstractmethod
    def add_event_handler(
        self,
        *,
        event_type: EventType,
        handler: Callable[[Any], None],
    ) -> None:
        """Add an event handler."""

    @abstractmethod
    def remove_event_handler(
        self,
        *,
        event_type: EventType,
        handler: Callable[[Any], None],
    ) -> None:
        """Remove an event handler."""


# Coordinator-specific interfaces


@runtime_checkable
class ClientProvider(Protocol):
    """Protocol for accessing client instances."""

    @property
    @abstractmethod
    def clients(self) -> tuple[Any, ...]:  # Avoid circular import
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
    def get_client(self, *, interface_id: str) -> Any:  # Avoid circular import
        """Get client for the given interface."""

    @abstractmethod
    def has_client(self, *, interface_id: str) -> bool:
        """Check if a client exists for the given interface."""


@runtime_checkable
class CoordinatorProvider(Protocol):
    """Protocol for accessing coordinator instances."""

    @property
    @abstractmethod
    def cache_coordinator(self) -> Any:  # Avoid circular import
        """Get cache coordinator."""

    @property
    @abstractmethod
    def client_coordinator(self) -> Any:  # Avoid circular import
        """Get client coordinator."""

    @property
    @abstractmethod
    def device_coordinator(self) -> Any:  # Avoid circular import
        """Get device coordinator."""

    @property
    @abstractmethod
    def device_registry(self) -> Any:  # Avoid circular import
        """Get device registry."""

    @property
    @abstractmethod
    def event_coordinator(self) -> Any:  # Avoid circular import
        """Get event coordinator."""

    @property
    @abstractmethod
    def hub_coordinator(self) -> Any:  # Avoid circular import
        """Get hub coordinator."""


@runtime_checkable
class ConfigProvider(Protocol):
    """Protocol for accessing configuration."""

    @property
    @abstractmethod
    def config(self) -> Any:  # Avoid circular import
        """Get central configuration."""


@runtime_checkable
class SystemInfoProvider(Protocol):
    """Protocol for accessing system information."""

    @property
    @abstractmethod
    def system_information(self) -> SystemInformation:
        """Get system information."""


@runtime_checkable
class EventBusProvider(Protocol):
    """Protocol for accessing event bus."""

    @property
    @abstractmethod
    def event_bus(self) -> Any:  # Avoid circular import
        """Get event bus instance."""


@runtime_checkable
class DataPointProvider(Protocol):
    """Protocol for accessing data points."""

    @abstractmethod
    def get_readable_generic_data_points(
        self,
        *,
        paramset_key: Any = None,  # Avoid circular import
        interface: Any = None,  # Avoid circular import
    ) -> tuple[Any, ...]:  # Avoid circular import
        """Get readable generic data points."""


@runtime_checkable
class DeviceProvider(Protocol):
    """Protocol for accessing devices."""

    @property
    @abstractmethod
    def devices(self) -> tuple[Any, ...]:  # Avoid circular import
        """Get all devices."""

    @property
    @abstractmethod
    def interfaces(self) -> tuple[Any, ...]:  # Avoid circular import
        """Get all interfaces."""


@runtime_checkable
class ChannelLookup(Protocol):
    """Protocol for looking up channels."""

    @abstractmethod
    def get_channel(self, *, channel_address: str) -> Any | None:  # Avoid circular import
        """Get channel by address."""


@runtime_checkable
class FileOperations(Protocol):
    """Protocol for file save operations."""

    @abstractmethod
    async def save_files(
        self,
        *,
        save_device_descriptions: bool = False,
        save_paramset_descriptions: bool = False,
    ) -> None:
        """Save persistent files to disk."""


@runtime_checkable
class DeviceDataRefresher(Protocol):
    """Protocol for refreshing device data."""

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


@runtime_checkable
class HubDataFetcher(Protocol):
    """Protocol for fetching hub data."""

    @abstractmethod
    async def fetch_program_data(self, *, scheduled: bool) -> None:
        """Fetch program data from the backend."""

    @abstractmethod
    async def fetch_sysvar_data(self, *, scheduled: bool) -> None:
        """Fetch system variable data from the backend."""


@runtime_checkable
class ClientCoordination(Protocol):
    """Protocol for client coordination operations."""

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
    def poll_clients(self) -> tuple[Any, ...] | None:
        """Get clients that require polling."""

    @abstractmethod
    def get_client(self, *, interface_id: str) -> Any:
        """Get client by interface ID."""

    @abstractmethod
    async def load_and_refresh_data_point_data(self, *, interface: Any) -> None:
        """Load and refresh data point data for an interface."""

    @abstractmethod
    async def restart_clients(self) -> None:
        """Restart all clients."""

    @abstractmethod
    def set_last_event_seen_for_interface(self, *, interface_id: str) -> None:
        """Set the last event seen time for an interface."""


@runtime_checkable
class CentralUnitStateProvider(Protocol):
    """Protocol for accessing central unit state."""

    @property
    @abstractmethod
    def state(self) -> Any:  # Avoid circular import
        """Get current central state."""
