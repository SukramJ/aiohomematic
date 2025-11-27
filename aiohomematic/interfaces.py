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
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from aiohomematic.const import (
    DP_KEY_VALUE,
    BackendSystemEvent,
    CallSource,
    CentralUnitState,
    DataPointCategory,
    DataPointKey,
    DataPointUsage,
    DeviceDescription,
    DeviceFirmwareState,
    EventKey,
    EventType,
    Interface,
    ParameterData,
    ParameterType,
    ParamsetKey,
    ProgramData,
    SystemInformation,
    SysvarType,
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
    from aiohomematic.client import Client, InterfaceConfig
    from aiohomematic.model.data_point import BaseParameterDataPointAny, CallbackDataPoint
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
class EventPublisher(Protocol):
    """
    Protocol for publishing events to the system.

    Implemented by CentralUnit
    """

    @abstractmethod
    def publish_backend_system_event(self, *, system_event: BackendSystemEvent, **kwargs: Any) -> None:
        """Publish a backend system event."""

    @abstractmethod
    def publish_homematic_event(self, *, event_type: EventType, event_data: dict[EventKey, Any]) -> None:
        """Publish a Homematic event."""


@runtime_checkable
class DeviceDetailsProvider(Protocol):
    """
    Protocol for accessing device details.

    Implemented by DeviceDescriptionCache
    """

    @abstractmethod
    def get_address_id(self, *, address: str) -> int:
        """Get an ID for an address."""

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
    def get_data_point_by_custom_id(self, *, custom_id: str) -> CallbackDataPoint | None:
        """Return Homematic data_point by custom_id."""

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
    async def fetch_inbox_data(self, *, scheduled: bool) -> None:
        """Fetch inbox data from the backend."""

    @abstractmethod
    async def fetch_program_data(self, *, scheduled: bool) -> None:
        """Fetch program data from the backend."""

    @abstractmethod
    async def fetch_system_update_data(self, *, scheduled: bool) -> None:
        """Fetch system update data from the backend."""

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


@runtime_checkable
class ClientFactory(Protocol):
    """
    Protocol for creating client instances.

    Implemented by CentralUnit
    """

    @abstractmethod
    async def create_client_instance(
        self,
        *,
        interface_config: InterfaceConfig,
    ) -> Client:
        """
        Create a client for the given interface configuration.

        Args:
        ----
            interface_config: Configuration for the interface

        Returns:
        -------
            Client instance for the interface

        """


# =============================================================================
# DataPoint Protocol Interfaces
# =============================================================================
# These protocols define the public interface for data point classes,
# allowing new classes outside the inheritance hierarchy to implement
# the required methods and properties.


@runtime_checkable
class CallbackDataPointProtocol(Protocol):
    """
    Protocol for callback-based data points.

    Base protocol for all data point types, providing event handling,
    subscription management, and timestamp tracking.
    """

    __slots__ = ()

    @property
    @abstractmethod
    def available(self) -> bool:
        """Return the availability of the device."""

    @property
    @abstractmethod
    def category(self) -> DataPointCategory:
        """Return the category of the data point."""

    @property
    @abstractmethod
    def custom_id(self) -> str | None:
        """Return the custom id."""

    @property
    @abstractmethod
    def enabled_default(self) -> bool:
        """Return if data point should be enabled based on usage attribute."""

    @property
    @abstractmethod
    def full_name(self) -> str:
        """Return the full name of the data point."""

    @property
    @abstractmethod
    def is_registered(self) -> bool:
        """Return if data point is registered externally."""

    @property
    @abstractmethod
    def is_valid(self) -> bool:
        """Return if the value of the data point is valid."""

    @property
    @abstractmethod
    def modified_at(self) -> datetime:
        """Return the last update datetime value."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of the data point."""

    @property
    @abstractmethod
    def published_event_at(self) -> datetime:
        """Return the data point updated published an event at."""

    @property
    @abstractmethod
    def refreshed_at(self) -> datetime:
        """Return the last refresh datetime value."""

    @property
    @abstractmethod
    def service_method_names(self) -> tuple[str, ...]:
        """Return all service method names."""

    @property
    @abstractmethod
    def service_methods(self) -> Mapping[str, Any]:
        """Return all service methods."""

    @property
    @abstractmethod
    def set_path(self) -> str:
        """Return the base set path of the data point."""

    @property
    @abstractmethod
    def signature(self) -> str:
        """Return the data point signature."""

    @property
    @abstractmethod
    def state_path(self) -> str:
        """Return the base state path of the data point."""

    @property
    @abstractmethod
    def unique_id(self) -> str:
        """Return the unique id."""

    @property
    @abstractmethod
    def usage(self) -> DataPointUsage:
        """Return the data point usage."""

    @abstractmethod
    def publish_data_point_updated_event(self, **kwargs: Any) -> None:
        """Publish a data point updated event."""

    @abstractmethod
    def publish_device_removed_event(self) -> None:
        """Publish a device removed event."""

    @abstractmethod
    def subscribe_to_data_point_updated(
        self, *, handler: Callable[..., None], custom_id: str
    ) -> Callable[[], None] | None:
        """Subscribe to data point updated event."""

    @abstractmethod
    def subscribe_to_device_removed(self, *, handler: Callable[[], None]) -> Callable[[], None] | None:
        """Subscribe to the device removed event."""


@runtime_checkable
class GenericHubDataPointProtocol(CallbackDataPointProtocol, Protocol):
    """
    Protocol for hub-level data points (programs, sysvars).

    Extends CallbackDataPointProtocol with properties specific to
    hub-level entities that are not bound to device channels.
    """

    __slots__ = ()

    @property
    @abstractmethod
    def channel(self) -> Channel | None:
        """Return the identified channel."""

    @property
    @abstractmethod
    def description(self) -> str | None:
        """Return data point description."""

    @property
    @abstractmethod
    def legacy_name(self) -> str | None:
        """Return the original name."""

    @property
    @abstractmethod
    def state_uncertain(self) -> bool:
        """Return if the state is uncertain."""


@runtime_checkable
class GenericSysvarDataPointProtocol(GenericHubDataPointProtocol, Protocol):
    """
    Protocol for system variable data points.

    Extends GenericHubDataPointProtocol with methods for reading
    and writing system variables.
    """

    __slots__ = ()

    @property
    @abstractmethod
    def data_type(self) -> SysvarType | None:
        """Return the data type of the system variable."""

    @property
    @abstractmethod
    def is_extended(self) -> bool:
        """Return if the data point is an extended type."""

    @property
    @abstractmethod
    def max(self) -> float | int | None:
        """Return the max value."""

    @property
    @abstractmethod
    def min(self) -> float | int | None:
        """Return the min value."""

    @property
    @abstractmethod
    def previous_value(self) -> Any:
        """Return the previous value."""

    @property
    @abstractmethod
    def unit(self) -> str | None:
        """Return the unit of the data point."""

    @property
    @abstractmethod
    def value(self) -> Any:
        """Return the value."""

    @property
    @abstractmethod
    def values(self) -> tuple[str, ...] | None:
        """Return the value list."""

    @property
    @abstractmethod
    def vid(self) -> str:
        """Return sysvar id."""

    @abstractmethod
    async def event(self, *, value: Any, received_at: datetime) -> None:
        """Handle event for which this data point has subscribed."""

    @abstractmethod
    async def send_variable(self, *, value: Any) -> None:
        """Set variable value on the backend."""

    @abstractmethod
    def write_value(self, *, value: Any, write_at: datetime) -> None:
        """Set variable value on the backend."""


@runtime_checkable
class GenericProgramDataPointProtocol(GenericHubDataPointProtocol, Protocol):
    """
    Protocol for program data points.

    Extends GenericHubDataPointProtocol with methods for managing
    CCU programs.
    """

    __slots__ = ()

    @property
    @abstractmethod
    def is_active(self) -> bool:
        """Return if the program is active."""

    @property
    @abstractmethod
    def is_internal(self) -> bool:
        """Return if the program is internal."""

    @property
    @abstractmethod
    def last_execute_time(self) -> str:
        """Return the last execute time."""

    @property
    @abstractmethod
    def pid(self) -> str:
        """Return the program id."""

    @abstractmethod
    def update_data(self, *, data: ProgramData) -> None:
        """Update program data from backend."""


@runtime_checkable
class BaseDataPointProtocol(CallbackDataPointProtocol, Protocol):
    """
    Protocol for channel-bound data points.

    Extends CallbackDataPointProtocol with channel/device associations
    and timer functionality.
    """

    __slots__ = ()

    @property
    @abstractmethod
    def device(self) -> Device:
        """Return the device of the data point."""

    @property
    @abstractmethod
    def function(self) -> str | None:
        """Return the function."""

    @property
    @abstractmethod
    def is_in_multiple_channels(self) -> bool:
        """Return if the parameter is in multiple channels."""

    @property
    @abstractmethod
    def room(self) -> str | None:
        """Return the room if only one exists."""

    @property
    @abstractmethod
    def rooms(self) -> set[str]:
        """Return the rooms assigned to the data point."""

    @property
    @abstractmethod
    def timer_on_time(self) -> float | None:
        """Return the on_time."""

    @property
    @abstractmethod
    def timer_on_time_running(self) -> bool:
        """Return if on_time is running."""

    @abstractmethod
    def force_usage(self, *, forced_usage: DataPointUsage) -> None:
        """Set the data point usage."""

    @abstractmethod
    async def load_data_point_value(self, *, call_source: CallSource, direct_call: bool = False) -> None:
        """Initialize the data point data."""

    @abstractmethod
    def reset_timer_on_time(self) -> None:
        """Reset the on_time."""

    @abstractmethod
    def set_timer_on_time(self, *, on_time: float) -> None:
        """Set the on_time."""


@runtime_checkable
class BaseParameterDataPointProtocol(BaseDataPointProtocol, Protocol):
    """
    Protocol for parameter-backed data points with typed values.

    Extends BaseDataPointProtocol with value handling, unit conversion,
    validation, and RPC communication for data points mapped to
    Homematic device parameters.
    """

    __slots__ = ()

    @property
    @abstractmethod
    def default(self) -> Any:
        """Return default value."""

    @property
    @abstractmethod
    def dpk(self) -> DataPointKey:
        """Return data point key value."""

    @property
    @abstractmethod
    def hmtype(self) -> ParameterType:
        """Return the Homematic type."""

    @property
    @abstractmethod
    def ignore_on_initial_load(self) -> bool:
        """Return if parameter should be ignored on initial load."""

    @property
    @abstractmethod
    def is_forced_sensor(self) -> bool:
        """Return if data point is forced to read only."""

    @property
    @abstractmethod
    def is_readable(self) -> bool:
        """Return if data point is readable."""

    @property
    @abstractmethod
    def is_un_ignored(self) -> bool:
        """Return if the parameter is un-ignored."""

    @property
    @abstractmethod
    def is_unit_fixed(self) -> bool:
        """Return if the unit is fixed."""

    @property
    @abstractmethod
    def is_writable(self) -> bool:
        """Return if data point is writable."""

    @property
    @abstractmethod
    def max(self) -> Any:
        """Return max value."""

    @property
    @abstractmethod
    def min(self) -> Any:
        """Return min value."""

    @property
    @abstractmethod
    def multiplier(self) -> float:
        """Return multiplier value."""

    @property
    @abstractmethod
    def parameter(self) -> str:
        """Return parameter name."""

    @property
    @abstractmethod
    def paramset_key(self) -> ParamsetKey:
        """Return paramset_key name."""

    @property
    @abstractmethod
    def previous_value(self) -> Any:
        """Return the previous value of the data point."""

    @property
    @abstractmethod
    def raw_unit(self) -> str | None:
        """Return raw unit value."""

    @property
    @abstractmethod
    def requires_polling(self) -> bool:
        """Return whether the data point requires polling."""

    @property
    @abstractmethod
    def service(self) -> bool:
        """Return if data point is relevant for service messages."""

    @property
    @abstractmethod
    def state_uncertain(self) -> bool:
        """Return if the state is uncertain."""

    @property
    @abstractmethod
    def supports_events(self) -> bool:
        """Return if data point supports events."""

    @property
    @abstractmethod
    def unconfirmed_last_value_send(self) -> Any:
        """Return the unconfirmed value send for the data point."""

    @property
    @abstractmethod
    def unit(self) -> str | None:
        """Return unit value."""

    @property
    @abstractmethod
    def value(self) -> Any:
        """Return the value of the data point."""

    @property
    @abstractmethod
    def values(self) -> tuple[str, ...] | None:
        """Return the values."""

    @property
    @abstractmethod
    def visible(self) -> bool:
        """Return if data point is visible in backend."""

    @abstractmethod
    async def event(self, *, value: Any, received_at: datetime) -> None:
        """Handle event for which this handler has subscribed."""

    @abstractmethod
    def force_to_sensor(self) -> None:
        """Change the category of the data point to sensor (read-only)."""

    @abstractmethod
    def get_event_data(self, *, value: Any = None) -> dict[EventKey, Any]:
        """Get the event data."""

    @abstractmethod
    def update_parameter_data(self) -> None:
        """Update parameter data."""

    @abstractmethod
    def write_temporary_value(self, *, value: Any, write_at: datetime) -> None:
        """Update the temporary value of the data point."""

    @abstractmethod
    def write_value(self, *, value: Any, write_at: datetime) -> tuple[Any, Any]:
        """Update value of the data point."""


@runtime_checkable
class GenericDataPointProtocol(BaseParameterDataPointProtocol, Protocol):
    """
    Protocol for generic parameter-backed data points.

    Extends BaseParameterDataPointProtocol with the usage property
    and send_value method specific to generic data points.
    """

    __slots__ = ()

    @property
    @abstractmethod
    def usage(self) -> DataPointUsage:
        """Return the data point usage."""

    @abstractmethod
    def is_state_change(self, *, value: Any) -> bool:
        """Check if the state/value changes."""

    @abstractmethod
    async def send_value(
        self,
        *,
        value: Any,
        collector: Any | None = None,
        collector_order: int = 50,
        do_validate: bool = True,
    ) -> set[DP_KEY_VALUE]:
        """Send value to CCU or use collector if set."""


@runtime_checkable
class CustomDataPointProtocol(BaseDataPointProtocol, Protocol):
    """
    Protocol for custom device-specific data points.

    Defines the interface for composite data points that aggregate
    multiple GenericDataPoints to represent complex devices.
    """

    __slots__ = ()

    @property
    @abstractmethod
    def allow_undefined_generic_data_points(self) -> bool:
        """Return if undefined generic data points are allowed."""

    @property
    @abstractmethod
    def custom_config(self) -> Any:
        """Return the custom config."""

    @property
    @abstractmethod
    def data_point_name_postfix(self) -> str:
        """Return the data point name postfix."""

    @property
    @abstractmethod
    def group_no(self) -> int | None:
        """Return the base channel no of the data point."""

    @property
    @abstractmethod
    def has_data_points(self) -> bool:
        """Return if there are data points."""

    @property
    @abstractmethod
    def schedule(self) -> dict[Any, Any]:
        """Return cached schedule entries from device week profile."""

    @property
    @abstractmethod
    def state_uncertain(self) -> bool:
        """Return if the state is uncertain."""

    @property
    @abstractmethod
    def supports_schedule(self) -> bool:
        """Return if device supports schedule."""

    @property
    @abstractmethod
    def unconfirmed_last_values_send(self) -> Mapping[Any, Any]:
        """Return the unconfirmed values send for the data point."""

    @abstractmethod
    async def get_schedule(self, *, force_load: bool = False) -> dict[Any, Any]:
        """Get schedule from device week profile."""

    @abstractmethod
    def has_data_point_key(self, *, data_point_keys: set[DataPointKey]) -> bool:
        """Return if a data point with one of the keys is part of this data point."""

    @abstractmethod
    def is_state_change(self, **kwargs: Any) -> bool:
        """Check if the state changes due to kwargs."""

    @abstractmethod
    async def set_schedule(self, *, schedule_data: dict[Any, Any]) -> None:
        """Set schedule on device week profile."""

    @abstractmethod
    def unsubscribe_from_data_point_updated(self) -> None:
        """Unregister all internal update handlers."""


@runtime_checkable
class CalculatedDataPointProtocol(BaseDataPointProtocol, Protocol):
    """
    Protocol for calculated data points.

    Defines the interface for data points that derive their values
    from other data points through calculations.
    """

    __slots__ = ()

    @staticmethod
    @abstractmethod
    def is_relevant_for_model(*, channel: Channel) -> bool:
        """Return if this calculated data point is relevant for the channel."""

    @property
    @abstractmethod
    def data_point_name_postfix(self) -> str:
        """Return the data point name postfix."""

    @property
    @abstractmethod
    def default(self) -> Any:
        """Return default value."""

    @property
    @abstractmethod
    def dpk(self) -> DataPointKey:
        """Return data point key value."""

    @property
    @abstractmethod
    def has_data_points(self) -> bool:
        """Return if there are data points."""

    @property
    @abstractmethod
    def hmtype(self) -> ParameterType:
        """Return the Homematic type."""

    @property
    @abstractmethod
    def is_readable(self) -> bool:
        """Return if data point is readable."""

    @property
    @abstractmethod
    def is_writable(self) -> bool:
        """Return if data point is writable."""

    @property
    @abstractmethod
    def max(self) -> Any:
        """Return max value."""

    @property
    @abstractmethod
    def min(self) -> Any:
        """Return min value."""

    @property
    @abstractmethod
    def multiplier(self) -> float:
        """Return multiplier value."""

    @property
    @abstractmethod
    def parameter(self) -> str:
        """Return parameter name."""

    @property
    @abstractmethod
    def paramset_key(self) -> ParamsetKey:
        """Return paramset_key name."""

    @property
    @abstractmethod
    def service(self) -> bool:
        """Return if data point is relevant for service messages."""

    @property
    @abstractmethod
    def state_uncertain(self) -> bool:
        """Return if the state is uncertain."""

    @property
    @abstractmethod
    def supports_events(self) -> bool:
        """Return if data point supports events."""

    @property
    @abstractmethod
    def unit(self) -> str | None:
        """Return unit value."""

    @property
    @abstractmethod
    def values(self) -> tuple[str, ...] | None:
        """Return the values."""

    @property
    @abstractmethod
    def visible(self) -> bool:
        """Return if data point is visible in backend."""

    @abstractmethod
    def is_state_change(self, **kwargs: Any) -> bool:
        """Check if the state changes due to kwargs."""

    @abstractmethod
    def unsubscribe_from_data_point_updated(self) -> None:
        """Unsubscribe from all internal update subscriptions."""
