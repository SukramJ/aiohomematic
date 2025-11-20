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
import asyncio
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from aiohomematic.const import (
    BackendSystemEvent,
    CentralUnitState,
    DeviceDescription,
    DeviceFirmwareState,
    EventKey,
    EventType,
    Interface,
    ParameterData,
    ParamsetKey,
    SystemInformation,
)
from aiohomematic.type_aliases import AsyncTaskFactoryAny, CoroutineAny

if TYPE_CHECKING:
    from aiohomematic.central import CentralConfig
    from aiohomematic.central.cache_coordinator import CacheCoordinator
    from aiohomematic.central.client_coordinator import ClientCoordinator
    from aiohomematic.central.device_coordinator import DeviceCoordinator
    from aiohomematic.central.device_registry import DeviceRegistry
    from aiohomematic.central.event_bus import EventBus
    from aiohomematic.central.event_coordinator import EventCoordinator
    from aiohomematic.central.hub_coordinator import HubCoordinator
    from aiohomematic.client import Client
    from aiohomematic.model.data_point import BaseParameterDataPointAny
    from aiohomematic.model.device import Channel, Device
    from aiohomematic.model.generic import GenericDataPointAny
    from aiohomematic.model.hub import GenericProgramDataPoint, GenericSysvarDataPoint, ProgramDpType


@runtime_checkable
class ParameterVisibilityProvider(Protocol):
    """
    Protocol for accessing parameter visibility information.

    Implemented by ParameterVisibilityCache
    """

    @abstractmethod
    def is_relevant_paramset(self, *, channel: Channel, paramset_key: ParamsetKey) -> bool:
        """
        Return if a paramset is relevant.

        Required to load MASTER paramsets, which are not initialized by default.
        """

    @abstractmethod
    def model_is_ignored(self, *, model: str) -> bool:
        """Check if a model should be ignored for custom data points."""

    @abstractmethod
    def parameter_is_hidden(self, *, channel: Channel, paramset_key: ParamsetKey, parameter: str) -> bool:
        """Check if a parameter is hidden."""

    @abstractmethod
    def parameter_is_un_ignored(
        self, *, channel: Channel, paramset_key: ParamsetKey, parameter: str, custom_only: bool = False
    ) -> bool:
        """Check if a parameter is un-ignored (visible)."""

    @abstractmethod
    def should_skip_parameter(
        self, *, channel: Channel, paramset_key: ParamsetKey, parameter: str, parameter_is_un_ignored: bool
    ) -> bool:
        """Determine if a parameter should be skipped."""


@runtime_checkable
class EventEmitter(Protocol):
    """
    Protocol for emitting events to the system.

    Implemented by CentralUnit
    """

    @abstractmethod
    def emit_backend_system_callback(self, *, system_event: BackendSystemEvent, **kwargs: Any) -> None:
        """Emit a backend system callback event."""

    @abstractmethod
    def emit_homematic_callback(self, *, event_type: EventType, event_data: dict[EventKey, Any]) -> None:
        """Emit a Homematic callback event."""


@runtime_checkable
class DeviceDetailsProvider(Protocol):
    """
    Protocol for accessing device details.

    Implemented by DeviceDescriptionCache
    """

    @abstractmethod
    def get_address_id(self, *, address: str) -> str:
        """Get numeric ID for an address."""

    @abstractmethod
    def get_channel_rooms(self, *, channel_address: str) -> set[str]:
        """Get rooms for a channel."""

    @abstractmethod
    def get_device_rooms(self, *, device_address: str) -> set[str]:
        """Get rooms for a device."""

    @abstractmethod
    def get_function_text(self, *, address: str) -> str | None:
        """Get function text for an address."""

    @abstractmethod
    def get_interface(self, *, address: str) -> Interface:
        """Get interface for an address."""

    @abstractmethod
    def get_name(self, *, address: str) -> str | None:
        """Get name for an address."""


@runtime_checkable
class DeviceDescriptionProvider(Protocol):
    """
    Protocol for accessing device descriptions.

    Implemented by DeviceDescriptionCache
    """

    @abstractmethod
    def get_device_description(self, *, interface_id: str, address: str) -> DeviceDescription:
        """Get device description."""

    @abstractmethod
    def get_device_with_channels(self, *, interface_id: str, device_address: str) -> Mapping[str, DeviceDescription]:
        """Get device with all channel descriptions."""


@runtime_checkable
class ParamsetDescriptionProvider(Protocol):
    """
    Protocol for accessing paramset descriptions.

    Implemented by ParamsetDescriptionCache
    """

    @abstractmethod
    def get_channel_paramset_descriptions(
        self, *, interface_id: str, channel_address: str
    ) -> Mapping[ParamsetKey, Mapping[str, ParameterData]]:
        """Get all paramset descriptions for a channel."""

    @abstractmethod
    def get_parameter_data(
        self, *, interface_id: str, channel_address: str, paramset_key: ParamsetKey, parameter: str
    ) -> ParameterData | None:
        """Get parameter data from paramset description."""

    @abstractmethod
    def is_in_multiple_channels(self, *, channel_address: str, parameter: str) -> bool:
        """Check if parameter is in multiple channels per device."""


@runtime_checkable
class EventSubscriptionManager(Protocol):
    """
    Protocol for managing event subscriptions.

    Implemented by CentralUnit
    """

    @abstractmethod
    def add_event_subscription(self, *, data_point: BaseParameterDataPointAny) -> None:
        """Add an event subscription for a data point."""

    @abstractmethod
    def remove_event_subscription(self, *, data_point: BaseParameterDataPointAny) -> None:
        """Remove an event subscription for a data point."""


@runtime_checkable
class HubDataPointManager(Protocol):
    """
    Protocol for managing hub-level data points (programs/sysvars).

    Implemented by CentralUnit
    """

    @property
    @abstractmethod
    def program_data_points(self) -> tuple[GenericProgramDataPoint, ...]:
        """Get all program data points."""

    @property
    @abstractmethod
    def sysvar_data_points(self) -> tuple[GenericSysvarDataPoint, ...]:
        """Get all system variable data points."""

    @abstractmethod
    def add_program_data_point(self, *, program_dp: ProgramDpType) -> None:
        """Add a program data point."""

    @abstractmethod
    def add_sysvar_data_point(self, *, sysvar_data_point: GenericSysvarDataPoint) -> None:
        """Add a system variable data point."""

    @abstractmethod
    def get_program_data_point(self, *, pid: str) -> ProgramDpType | None:
        """Get a program data point by ID."""

    @abstractmethod
    def get_sysvar_data_point(self, *, vid: str) -> GenericSysvarDataPoint | None:
        """Get a system variable data point by ID."""

    @abstractmethod
    def remove_program_button(self, *, pid: str) -> None:
        """Remove a program button."""

    @abstractmethod
    def remove_sysvar_data_point(self, *, vid: str) -> None:
        """Remove a system variable data point."""


@runtime_checkable
class TaskScheduler(Protocol):
    """
    Protocol for scheduling async tasks.

    Implemented by Looper
    """

    @abstractmethod
    def async_add_executor_job[T](
        self, target: Callable[..., T], *args: Any, name: str, executor: ThreadPoolExecutor | None = None
    ) -> asyncio.Future[T]:
        """Add an executor job from within the event_loop."""

    @abstractmethod
    def create_task(self, *, target: CoroutineAny | AsyncTaskFactoryAny, name: str) -> None:
        """Create and schedule an async task."""


@runtime_checkable
class CentralInfo(Protocol):
    """
    Protocol for accessing central system information.

    Implemented by CentralUnit
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


@runtime_checkable
class PrimaryClientProvider(Protocol):
    """
    Protocol for accessing primary client.

    Implemented by CentralUnit
    """

    @property
    @abstractmethod
    def primary_client(self) -> Client | None:
        """Get primary client."""


# Coordinator-specific interfaces


@runtime_checkable
class ClientProvider(Protocol):
    """
    Protocol for accessing client instances.

    Implemented by CentralUnit
    """

    @property
    @abstractmethod
    def clients(self) -> tuple[Client, ...]:  # Avoid circular import
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
    def get_client(self, *, interface_id: str) -> Client:
        """Get client for the given interface."""

    @abstractmethod
    def has_client(self, *, interface_id: str) -> bool:
        """Check if a client exists for the given interface."""


@runtime_checkable
class CoordinatorProvider(Protocol):
    """
    Protocol for accessing coordinator instances.

    Implemented by CentralUnit
    """

    @property
    @abstractmethod
    def cache_coordinator(self) -> CacheCoordinator:
        """Get cache coordinator."""

    @property
    @abstractmethod
    def client_coordinator(self) -> ClientCoordinator:
        """Get client coordinator."""

    @property
    @abstractmethod
    def device_coordinator(self) -> DeviceCoordinator:
        """Get device coordinator."""

    @property
    @abstractmethod
    def device_registry(self) -> DeviceRegistry:
        """Get device registry."""

    @property
    @abstractmethod
    def event_coordinator(self) -> EventCoordinator:
        """Get event coordinator."""

    @property
    @abstractmethod
    def hub_coordinator(self) -> HubCoordinator:
        """Get hub coordinator."""


@runtime_checkable
class ConfigProvider(Protocol):
    """
    Protocol for accessing configuration.

    Implemented by CentralUnit
    """

    @property
    @abstractmethod
    def config(self) -> CentralConfig:  # Avoid circular import
        """Get central configuration."""


@runtime_checkable
class SystemInfoProvider(Protocol):
    """
    Protocol for accessing system information.

    Implemented by CentralUnit
    """

    @property
    @abstractmethod
    def system_information(self) -> SystemInformation:
        """Get system information."""


@runtime_checkable
class EventBusProvider(Protocol):
    """
    Protocol for accessing event bus.

    Implemented by CentralUnit
    """

    @property
    @abstractmethod
    def event_bus(self) -> EventBus:
        """Get event bus instance."""


@runtime_checkable
class DataPointProvider(Protocol):
    """
    Protocol for accessing data points.

    Implemented by CentralUnit
    """

    @abstractmethod
    def get_readable_generic_data_points(
        self,
        *,
        paramset_key: ParamsetKey | None = None,
        interface: Interface | None = None,
    ) -> tuple[GenericDataPointAny, ...]:
        """Get readable generic data points."""


@runtime_checkable
class DeviceProvider(Protocol):
    """
    Protocol for accessing devices.

    Implemented by CentralUnit
    """

    @property
    @abstractmethod
    def devices(self) -> tuple[Device, ...]:
        """Get all devices."""

    @property
    @abstractmethod
    def interfaces(self) -> frozenset[Interface]:
        """Get all interfaces."""


@runtime_checkable
class ChannelLookup(Protocol):
    """
    Protocol for looking up channels.

    Implemented by CentralUnit
    """

    @abstractmethod
    def get_channel(self, *, channel_address: str) -> Channel | None:
        """Get channel by address."""

    @abstractmethod
    def identify_channel(self, *, text: str) -> Channel | None:  # Avoid circular import
        """Identify a channel within a text string."""


@runtime_checkable
class FileOperations(Protocol):
    """
    Protocol for file save operations.

    Implemented by CentralUnit
    """

    @abstractmethod
    async def save_files(
        self, *, save_device_descriptions: bool = False, save_paramset_descriptions: bool = False
    ) -> None:
        """Save persistent files to disk."""


@runtime_checkable
class DeviceDataRefresher(Protocol):
    """
    Protocol for refreshing device data.

    Implemented by CentralUnit
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


@runtime_checkable
class HubDataFetcher(Protocol):
    """
    Protocol for fetching hub data.

    Implemented by CentralUnit
    """

    @abstractmethod
    async def execute_program(self, *, pid: str) -> bool:
        """Execute a program on the backend."""

    @abstractmethod
    async def fetch_program_data(self, *, scheduled: bool) -> None:
        """Fetch program data from the backend."""

    @abstractmethod
    async def fetch_sysvar_data(self, *, scheduled: bool) -> None:
        """Fetch system variable data from the backend."""

    @abstractmethod
    async def set_program_state(self, *, pid: str, state: bool) -> bool:
        """Set program state on the backend."""


@runtime_checkable
class ClientCoordination(Protocol):
    """
    Protocol for client coordination operations.

    Implemented by CentralUnit
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
    def poll_clients(self) -> tuple[Client, ...] | None:
        """Get clients that require polling."""

    @abstractmethod
    def get_client(self, *, interface_id: str) -> Client:
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
class CentralUnitStateProvider(Protocol):
    """
    Protocol for accessing central unit state.

    Implemented by CentralUnit
    """

    @property
    @abstractmethod
    def state(self) -> CentralUnitState:
        """Get current central state."""


@runtime_checkable
class DataCacheProvider(Protocol):
    """
    Protocol for accessing data cache.

    Implemented by CentralDataCache
    """

    @abstractmethod
    def get_data(self, *, interface: Interface, channel_address: str, parameter: str) -> Any:
        """Get cached data for a parameter."""
