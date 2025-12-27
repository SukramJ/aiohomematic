# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Central unit and core orchestration for Homematic CCU and compatible backends.

Overview
--------
This package provides the central coordination layer for aiohomematic. It models a
Homematic CCU (or compatible backend such as Homegear) and orchestrates
interfaces, devices, channels, data points, events, and background jobs.

The central unit ties together the various submodules: store, client adapters
(JSON-RPC/XML-RPC), device and data point models, and visibility/description store.
It exposes high-level APIs to query and manipulate the backend state while
encapsulating transport and scheduling details.

Public API (selected)
---------------------
- CentralUnit: The main coordination class. Manages client creation/lifecycle,
  connection state, device and channel discovery, data point and event handling,
  sysvar/program access, cache loading/saving, and dispatching handlers.
- CentralConfig: Configuration builder/holder for CentralUnit instances, including
  connection parameters, feature toggles, and cache behavior.
- CentralConnectionState: Tracks connection issues per transport/client.

Internal helpers
----------------
- BackgroundScheduler: Asyncio-based scheduler for periodic tasks such as connection
  health checks, data refreshes, and firmware status updates.

Quick start
-----------
Typical usage is to create a CentralConfig, build a CentralUnit, then start it.

Example (simplified):

    from aiohomematic.central import CentralConfig
    from aiohomematic import client as hmcl

    iface_cfgs = {
        hmcl.InterfaceConfig(interface=hmcl.Interface.HMIP, port=2010, enabled=True),
        hmcl.InterfaceConfig(interface=hmcl.Interface.BIDCOS_RF, port=2001, enabled=True),
    }

    cfg = CentralConfig(
        central_id="ccu-main",
        host="ccu.local",
        interface_configs=iface_cfgs,
        name="MyCCU",
        password="secret",
        username="admin",
    )

    central = cfg.create_central()
    central.start()           # start XML-RPC server, create/init clients, load store
    # ... interact with devices / data points via central ...
    central.stop()

Notes
-----
- The central module is thread-aware and uses an internal Looper to schedule async tasks.
- For advanced scenarios, see xml_rpc_server and decorators modules in this package.

"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Set as AbstractSet
from datetime import datetime
from functools import partial
import logging
from typing import Any, Final

from aiohttp import ClientSession

from aiohomematic import client as hmcl, i18n
from aiohomematic.async_support import Looper
from aiohomematic.central import rpc_server as rpc
from aiohomematic.central.cache_coordinator import CacheCoordinator
from aiohomematic.central.client_coordinator import ClientCoordinator
from aiohomematic.central.config_builder import CentralConfigBuilder, ValidationError
from aiohomematic.central.device_coordinator import DeviceCoordinator
from aiohomematic.central.device_registry import DeviceRegistry
from aiohomematic.central.event_bus import EventBatch, EventBus, EventPriority
from aiohomematic.central.event_coordinator import EventCoordinator
from aiohomematic.central.health import (  # noqa: F401 - ConnectionHealth used for re-export
    CentralHealth,
    ConnectionHealth,
    HealthTracker,
)
from aiohomematic.central.hub_coordinator import HubCoordinator
from aiohomematic.central.integration_events import SystemStatusEvent
from aiohomematic.central.metrics import (  # noqa: F401 - Metric types used for re-export
    CacheMetrics,
    EventMetrics,
    HealthMetrics,
    MetricsAggregator,
    MetricsSnapshot,
    ModelMetrics,
    RecoveryMetrics,
    RpcMetrics,
)
from aiohomematic.central.recovery import (  # noqa: F401 - RecoveryResult used for re-export
    RecoveryCoordinator,
    RecoveryResult,
)
from aiohomematic.central.scheduler import BackgroundScheduler, SchedulerJob as _SchedulerJob
from aiohomematic.central.state_machine import CentralStateMachine
from aiohomematic.client import AioJsonRpcAioHttpClient, BaseRpcProxy
from aiohomematic.const import (
    CATEGORIES,
    DATA_POINT_EVENTS,
    DEFAULT_DELAY_NEW_DEVICE_CREATION,
    DEFAULT_ENABLE_DEVICE_FIRMWARE_CHECK,
    DEFAULT_ENABLE_PROGRAM_SCAN,
    DEFAULT_ENABLE_SYSVAR_SCAN,
    DEFAULT_IGNORE_CUSTOM_DEVICE_DEFINITION_MODELS,
    DEFAULT_INTERFACES_REQUIRING_PERIODIC_REFRESH,
    DEFAULT_LOCALE,
    DEFAULT_MAX_READ_WORKERS,
    DEFAULT_OPTIONAL_SETTINGS,
    DEFAULT_PROGRAM_MARKERS,
    DEFAULT_SCHEDULE_TIMER_CONFIG,
    DEFAULT_SESSION_RECORDER_START_FOR_SECONDS,
    DEFAULT_STORAGE_DIRECTORY,
    DEFAULT_SYSVAR_MARKERS,
    DEFAULT_TIMEOUT_CONFIG,
    DEFAULT_TLS,
    DEFAULT_UN_IGNORES,
    DEFAULT_USE_GROUP_CHANNEL_FOR_COVER_STATE,
    DEFAULT_VERIFY_TLS,
    IDENTIFIER_SEPARATOR,
    IGNORE_FOR_UN_IGNORE_PARAMETERS,
    IP_ANY_V4,
    LOCAL_HOST,
    PORT_ANY,
    PRIMARY_CLIENT_CANDIDATE_INTERFACES,
    UN_IGNORE_WILDCARD,
    BackupData,
    CentralState,
    ClientState,
    DataPointCategory,
    DescriptionMarker,
    DeviceTriggerEventType,
    FailureReason,
    Interface,
    Operations,
    OptionalSettings,
    ParamsetKey,
    RpcServerType,
    ScheduleTimerConfig,
    SourceOfDeviceCreation,
    SystemInformation,
    TimeoutConfig,
    get_interface_default_port,
    get_json_rpc_default_port,
)
from aiohomematic.decorators import inspector
from aiohomematic.exceptions import (
    AioHomematicConfigException,
    AioHomematicException,
    BaseHomematicException,
    NoClientsException,
)
from aiohomematic.interfaces.central import CentralProtocol, EventBusProviderProtocol
from aiohomematic.interfaces.client import ClientProtocol
from aiohomematic.interfaces.model import (
    CallbackDataPointProtocol,
    CustomDataPointProtocol,
    DeviceProtocol,
    GenericDataPointProtocol,
    GenericDataPointProtocolAny,
    GenericEventProtocolAny,
)
from aiohomematic.model.hub import InstallModeDpType
from aiohomematic.property_decorators import DelegatedProperty, Kind, info_property
from aiohomematic.support import (
    LogContextMixin,
    PayloadMixin,
    check_or_create_directory,
    check_password,
    extract_exc_args,
    get_channel_no,
    get_device_address,
    get_ip_addr,
    is_host,
    is_ipv4_address,
    is_port,
)

__all__ = [
    "CentralConfig",
    "CentralConfigBuilder",
    "CentralUnit",
    "DeviceRegistry",
    "EventBatch",
    "EventPriority",
    "ValidationError",
    "_SchedulerJob",
]

_LOGGER: Final = logging.getLogger(__name__)
_LOGGER_EVENT: Final = logging.getLogger(f"{__package__}.event")

# {central_name, central}
CENTRAL_INSTANCES: Final[dict[str, CentralUnit]] = {}
ConnectionProblemIssuer = AioJsonRpcAioHttpClient | BaseRpcProxy


class CentralUnit(
    PayloadMixin,
    LogContextMixin,
    CentralProtocol,
):
    """Central unit that collects everything to handle communication from/to the backend."""

    def __init__(self, *, central_config: CentralConfig) -> None:
        """Initialize the central unit."""
        # Keep the config for the central
        self._config: Final = central_config
        # Apply locale for translations
        try:
            i18n.set_locale(locale=self._config.locale)
        except Exception:  # pragma: no cover - keep init robust
            i18n.set_locale(locale=DEFAULT_LOCALE)
        self._url: Final = self._config.create_central_url()
        self._model: str | None = None
        self._looper = Looper()
        self._xml_rpc_server: rpc.XmlRpcServer | None = None
        self._json_rpc_client: AioJsonRpcAioHttpClient | None = None

        # Initialize event bus and state machine early (needed by coordinators)
        self._event_bus: Final = EventBus(
            enable_event_logging=_LOGGER.isEnabledFor(logging.DEBUG),
            task_scheduler=self.looper,
        )
        self._central_state_machine: Final = CentralStateMachine(
            central_name=self._config.name,
            event_bus=self._event_bus,
        )
        self._health_tracker: Final = HealthTracker(
            central_name=self._config.name,
            state_machine=self._central_state_machine,
        )

        # Initialize coordinators
        self._client_coordinator: Final = ClientCoordinator(
            client_factory=self,
            central_info=self,
            config_provider=self,
            coordinator_provider=self,
            health_tracker=self._health_tracker,
            system_info_provider=self,
        )
        self._cache_coordinator: Final = CacheCoordinator(
            central_info=self,
            client_provider=self._client_coordinator,
            config_provider=self,
            data_point_provider=self,
            device_provider=self,
            primary_client_provider=self._client_coordinator,
            session_recorder_active=self.config.session_recorder_start,
            task_scheduler=self.looper,
        )
        self._event_coordinator: Final = EventCoordinator(
            client_provider=self._client_coordinator,
            event_bus=self._event_bus,
            health_tracker=self._health_tracker,
            task_scheduler=self.looper,
        )

        self._connection_state: Final = CentralConnectionState(event_bus_provider=self)
        self._device_registry: Final = DeviceRegistry(
            central_info=self,
            client_provider=self._client_coordinator,
        )
        self._device_coordinator: Final = DeviceCoordinator(
            central_info=self,
            client_provider=self._client_coordinator,
            config_provider=self,
            coordinator_provider=self,
            data_cache_provider=self._cache_coordinator.data_cache,
            data_point_provider=self,
            device_description_provider=self._cache_coordinator.device_descriptions,
            device_details_provider=self._cache_coordinator.device_details,
            event_bus_provider=self,
            event_publisher=self._event_coordinator,
            event_subscription_manager=self._event_coordinator,
            file_operations=self,
            parameter_visibility_provider=self._cache_coordinator.parameter_visibility,
            paramset_description_provider=self._cache_coordinator.paramset_descriptions,
            task_scheduler=self.looper,
        )
        self._hub_coordinator: Final = HubCoordinator(
            central_info=self,
            channel_lookup=self._device_coordinator,
            client_provider=self._client_coordinator,
            config_provider=self,
            event_bus_provider=self,
            event_publisher=self._event_coordinator,
            metrics_provider=self,
            parameter_visibility_provider=self._cache_coordinator.parameter_visibility,
            paramset_description_provider=self._cache_coordinator.paramset_descriptions,
            primary_client_provider=self._client_coordinator,
            task_scheduler=self.looper,
        )

        CENTRAL_INSTANCES[self.name] = self
        self._scheduler: Final = BackgroundScheduler(
            central_info=self,
            config_provider=self,
            client_coordinator=self._client_coordinator,
            connection_state_provider=self,
            device_data_refresher=self,
            firmware_data_refresher=self._device_coordinator,
            event_coordinator=self._event_coordinator,
            hub_data_fetcher=self._hub_coordinator,
            event_bus_provider=self,
            json_rpc_client_provider=self,
            state_provider=self,
        )

        self._recovery_coordinator: Final = RecoveryCoordinator(
            central_name=self._config.name,
            state_machine=self._central_state_machine,
            health_tracker=self._health_tracker,
            client_provider=self._client_coordinator,
        )

        # Metrics aggregator for observability
        self._metrics_aggregator: Final = MetricsAggregator(
            central_name=self.name,
            client_provider=self._client_coordinator,
            device_provider=self._device_registry,
            event_bus=self._event_bus,
            health_tracker=self._health_tracker,
            data_cache=self._cache_coordinator.data_cache,
            hub_data_point_manager=self._hub_coordinator,
            recovery_coordinator=self._recovery_coordinator,
        )

        # Subscribe to system status events to update central state machine
        self.event_bus.subscribe(
            event_type=SystemStatusEvent,
            event_key=None,  # Subscribe to all system status events
            handler=self._on_system_status_event,
        )

        self._version: str | None = None
        self._rpc_callback_ip: str = IP_ANY_V4
        self._listen_ip_addr: str = IP_ANY_V4
        self._listen_port_xml_rpc: int = PORT_ANY

    def __str__(self) -> str:
        """Provide some useful information."""
        return f"central: {self.name}"

    available: Final = DelegatedProperty[bool](path="_client_coordinator.available")
    cache_coordinator: Final = DelegatedProperty[CacheCoordinator](path="_cache_coordinator")
    callback_ip_addr: Final = DelegatedProperty[str](path="_rpc_callback_ip")
    central_state_machine: Final = DelegatedProperty[CentralStateMachine](path="_central_state_machine")
    client_coordinator: Final = DelegatedProperty[ClientCoordinator](path="_client_coordinator")
    config: Final = DelegatedProperty["CentralConfig"](path="_config")
    connection_state: Final = DelegatedProperty["CentralConnectionState"](path="_connection_state")
    device_coordinator: Final = DelegatedProperty[DeviceCoordinator](path="_device_coordinator")
    device_registry: Final = DelegatedProperty[DeviceRegistry](path="_device_registry")
    devices: Final = DelegatedProperty[tuple[DeviceProtocol, ...]](path="_device_registry.devices")
    event_bus: Final = DelegatedProperty[EventBus](path="_event_bus")
    event_coordinator: Final = DelegatedProperty[EventCoordinator](path="_event_coordinator")
    health: Final = DelegatedProperty[CentralHealth](path="_health_tracker.health")
    health_tracker: Final = DelegatedProperty[HealthTracker](path="_health_tracker")
    hub_coordinator: Final = DelegatedProperty[HubCoordinator](path="_hub_coordinator")
    interfaces: Final = DelegatedProperty[frozenset[Interface]](path="_client_coordinator.interfaces")
    listen_ip_addr: Final = DelegatedProperty[str](path="_listen_ip_addr")
    listen_port_xml_rpc: Final = DelegatedProperty[int](path="_listen_port_xml_rpc")
    looper: Final = DelegatedProperty[Looper](path="_looper")
    metrics: Final = DelegatedProperty[MetricsAggregator](path="_metrics_aggregator")
    name: Final = DelegatedProperty[str](path="_config.name", kind=Kind.INFO, log_context=True)
    recovery_coordinator: Final = DelegatedProperty[RecoveryCoordinator](path="_recovery_coordinator")
    state: Final = DelegatedProperty[CentralState](path="_central_state_machine.state")
    url: Final = DelegatedProperty[str](path="_url", kind=Kind.INFO, log_context=True)

    @property
    def _has_active_threads(self) -> bool:
        """Return if active sub threads are alive."""
        # BackgroundScheduler is async-based, not a thread
        # Only check XML-RPC server thread
        return bool(
            self._xml_rpc_server and self._xml_rpc_server.no_central_assigned and self._xml_rpc_server.is_alive()
        )

    @property
    def json_rpc_client(self) -> AioJsonRpcAioHttpClient:
        """Return the json rpc client."""
        if not self._json_rpc_client:
            self._json_rpc_client = self._config.create_json_rpc_client(
                central=self,
                health_record_callback=self._client_coordinator.on_health_record,
            )
        return self._json_rpc_client

    @property
    def supports_ping_pong(self) -> bool:
        """Return the backend supports ping pong."""
        if primary_client := self._client_coordinator.primary_client:
            return primary_client.supports_ping_pong
        return False

    @property
    def system_information(self) -> SystemInformation:
        """Return the system_information of the backend."""
        if client := self._client_coordinator.primary_client:
            return client.system_information
        return SystemInformation()

    @info_property(log_context=True)
    def model(self) -> str | None:
        """Return the model of the backend."""
        if not self._model and (client := self._client_coordinator.primary_client):
            self._model = client.model
        return self._model

    @info_property
    def version(self) -> str | None:
        """Return the version of the backend."""
        if self._version is None:
            versions = [client.version for client in self._client_coordinator.clients if client.version]
            self._version = max(versions) if versions else None
        return self._version

    async def accept_device_in_inbox(self, *, device_address: str) -> bool:
        """
        Accept a device from the CCU inbox.

        Args:
            device_address: The address of the device to accept.

        Returns:
            True if the device was successfully accepted, False otherwise.

        """
        if not (client := self._client_coordinator.primary_client):
            _LOGGER.warning(
                i18n.tr(
                    key="log.central.accept_device_in_inbox.no_client", device_address=device_address, name=self.name
                )
            )
            return False

        result = await client.accept_device_in_inbox(device_address=device_address)
        return bool(result)

    async def create_backup_and_download(self) -> BackupData | None:
        """
        Create a backup on the CCU and download it.

        Returns:
            BackupData with filename and content, or None if backup creation or download failed.

        """
        if client := self._client_coordinator.primary_client:
            return await client.create_backup_and_download()
        return None

    async def create_client_instance(
        self,
        *,
        interface_config: hmcl.InterfaceConfig,
        health_record_callback: hmcl.HealthRecordCallbackProtocol | None = None,
    ) -> ClientProtocol:
        """
        Create a client for the given interface configuration.

        This method implements the ClientFactoryProtocol protocol to enable
        dependency injection without requiring the full CentralUnit.

        Args:
        ----
            interface_config: Configuration for the interface
            health_record_callback: Optional callback for health tracking

        Returns:
        -------
            Client instance for the interface

        """
        return await hmcl.create_client(
            client_deps=self,
            interface_config=interface_config,
            health_record_callback=health_record_callback,
        )

    def get_custom_data_point(self, *, address: str, channel_no: int) -> CustomDataPointProtocol | None:
        """Return the hm custom_data_point."""
        if device := self._device_coordinator.get_device(address=address):
            return device.get_custom_data_point(channel_no=channel_no)
        return None

    def get_data_point_by_custom_id(self, *, custom_id: str) -> CallbackDataPointProtocol | None:
        """Return Homematic data_point by custom_id."""
        for dp in self.get_data_points(registered=True):
            if dp.custom_id == custom_id:
                return dp
        return None

    def get_data_points(
        self,
        *,
        category: DataPointCategory | None = None,
        interface: Interface | None = None,
        exclude_no_create: bool = True,
        registered: bool | None = None,
    ) -> tuple[CallbackDataPointProtocol, ...]:
        """Return all externally registered data points."""
        all_data_points: list[CallbackDataPointProtocol] = []
        for device in self._device_registry.devices:
            if interface and interface != device.interface:
                continue
            all_data_points.extend(
                device.get_data_points(category=category, exclude_no_create=exclude_no_create, registered=registered)
            )
        return tuple(all_data_points)

    def get_event(
        self, *, channel_address: str | None = None, parameter: str | None = None, state_path: str | None = None
    ) -> GenericEventProtocolAny | None:
        """Return the hm event."""
        if channel_address is None:
            for dev in self._device_registry.devices:
                if event := dev.get_generic_event(parameter=parameter, state_path=state_path):
                    return event
            return None

        if device := self._device_coordinator.get_device(address=channel_address):
            return device.get_generic_event(channel_address=channel_address, parameter=parameter, state_path=state_path)
        return None

    def get_events(
        self, *, event_type: DeviceTriggerEventType, registered: bool | None = None
    ) -> tuple[tuple[GenericEventProtocolAny, ...], ...]:
        """Return all channel event data points."""
        hm_channel_events: list[tuple[GenericEventProtocolAny, ...]] = []
        for device in self._device_registry.devices:
            for channel_events in device.get_events(event_type=event_type).values():
                if registered is None or (channel_events[0].is_registered == registered):
                    hm_channel_events.append(channel_events)
                    continue
        return tuple(hm_channel_events)

    def get_generic_data_point(
        self,
        *,
        channel_address: str | None = None,
        parameter: str | None = None,
        paramset_key: ParamsetKey | None = None,
        state_path: str | None = None,
    ) -> GenericDataPointProtocolAny | None:
        """Get data_point by channel_address and parameter."""
        if channel_address is None:
            for dev in self._device_registry.devices:
                if dp := dev.get_generic_data_point(
                    parameter=parameter, paramset_key=paramset_key, state_path=state_path
                ):
                    return dp
            return None

        if device := self._device_coordinator.get_device(address=channel_address):
            return device.get_generic_data_point(
                channel_address=channel_address, parameter=parameter, paramset_key=paramset_key, state_path=state_path
            )
        return None

    async def get_install_mode(self, *, interface: Interface) -> int:
        """
        Return the remaining time in install mode for an interface.

        Args:
            interface: The interface to query (HMIP_RF or BIDCOS_RF).

        Returns:
            Remaining time in seconds, or 0 if not in install mode.

        """
        try:
            client = self._client_coordinator.get_client(interface=interface)
            return await client.get_install_mode()
        except AioHomematicException:
            return 0

    def get_parameters(
        self,
        *,
        paramset_key: ParamsetKey,
        operations: tuple[Operations, ...],
        full_format: bool = False,
        un_ignore_candidates_only: bool = False,
        use_channel_wildcard: bool = False,
    ) -> tuple[str, ...]:
        """
        Return all parameters from VALUES paramset.

        Performance optimized to minimize repeated lookups and computations
        when iterating over all channels and parameters.
        """
        parameters: set[str] = set()

        # Precompute operations mask to avoid repeated checks in the inner loop
        op_mask: int = 0
        for op in operations:
            op_mask |= int(op)

        raw_psd = self._cache_coordinator.paramset_descriptions.raw_paramset_descriptions
        ignore_set = IGNORE_FOR_UN_IGNORE_PARAMETERS

        # Prepare optional helpers only if needed
        get_model = self._cache_coordinator.device_descriptions.get_model if full_format else None
        model_cache: dict[str, str | None] = {}
        channel_no_cache: dict[str, int | None] = {}

        for channels in raw_psd.values():
            for channel_address, channel_paramsets in channels.items():
                # Resolve model lazily and cache per device address when full_format is requested
                model: str | None = None
                if get_model is not None:
                    dev_addr = get_device_address(address=channel_address)
                    if (model := model_cache.get(dev_addr)) is None:
                        model = get_model(device_address=dev_addr)
                        model_cache[dev_addr] = model

                if (paramset := channel_paramsets.get(paramset_key)) is None:
                    continue

                for parameter, parameter_data in paramset.items():
                    # Fast bitmask check: ensure all requested ops are present
                    if (int(parameter_data["OPERATIONS"]) & op_mask) != op_mask:
                        continue

                    if un_ignore_candidates_only:
                        # Cheap check first to avoid expensive dp lookup when possible
                        if parameter in ignore_set:
                            continue
                        dp = self.get_generic_data_point(
                            channel_address=channel_address,
                            parameter=parameter,
                            paramset_key=paramset_key,
                        )
                        if dp and dp.enabled_default and not dp.is_un_ignored:
                            continue

                    if not full_format:
                        parameters.add(parameter)
                        continue

                    if use_channel_wildcard:
                        channel_repr: int | str | None = UN_IGNORE_WILDCARD
                    elif channel_address in channel_no_cache:
                        channel_repr = channel_no_cache[channel_address]
                    else:
                        channel_repr = get_channel_no(address=channel_address)
                        channel_no_cache[channel_address] = channel_repr

                    # Build the full parameter string
                    if channel_repr is None:
                        parameters.add(f"{parameter}:{paramset_key}@{model}:")
                    else:
                        parameters.add(f"{parameter}:{paramset_key}@{model}:{channel_repr}")

        return tuple(parameters)

    def get_readable_generic_data_points(
        self, *, paramset_key: ParamsetKey | None = None, interface: Interface | None = None
    ) -> tuple[GenericDataPointProtocolAny, ...]:
        """Return the readable generic data points."""
        return tuple(
            ge
            for ge in self.get_data_points(interface=interface)
            if (
                isinstance(ge, GenericDataPointProtocol)
                and ge.is_readable
                and ((paramset_key and ge.paramset_key == paramset_key) or paramset_key is None)
            )
        )

    def get_state_paths(self, *, rpc_callback_supported: bool | None = None) -> tuple[str, ...]:
        """Return the data point paths."""
        data_point_paths: list[str] = []
        for device in self._device_registry.devices:
            if rpc_callback_supported is None or device.client.supports_rpc_callback == rpc_callback_supported:
                data_point_paths.extend(device.data_point_paths)
        data_point_paths.extend(self.hub_coordinator.data_point_paths)
        return tuple(data_point_paths)

    def get_un_ignore_candidates(self, *, include_master: bool = False) -> list[str]:
        """Return the candidates for un_ignore."""
        candidates = sorted(
            # 1. request simple parameter list for values parameters
            self.get_parameters(
                paramset_key=ParamsetKey.VALUES,
                operations=(Operations.READ, Operations.EVENT),
                un_ignore_candidates_only=True,
            )
            # 2. request full_format parameter list with channel wildcard for values parameters
            + self.get_parameters(
                paramset_key=ParamsetKey.VALUES,
                operations=(Operations.READ, Operations.EVENT),
                full_format=True,
                un_ignore_candidates_only=True,
                use_channel_wildcard=True,
            )
            # 3. request full_format parameter list for values parameters
            + self.get_parameters(
                paramset_key=ParamsetKey.VALUES,
                operations=(Operations.READ, Operations.EVENT),
                full_format=True,
                un_ignore_candidates_only=True,
            )
        )
        if include_master:
            # 4. request full_format parameter list for master parameters
            candidates += sorted(
                self.get_parameters(
                    paramset_key=ParamsetKey.MASTER,
                    operations=(Operations.READ,),
                    full_format=True,
                    un_ignore_candidates_only=True,
                )
            )
        return candidates

    async def init_install_mode(self) -> Mapping[Interface, InstallModeDpType]:
        """
        Initialize install mode data points (internal use - use hub_coordinator for external access).

        Creates data points, fetches initial state from backend, and publishes refresh event.
        Returns a dict of InstallModeDpType by Interface.
        """
        return await self._hub_coordinator.init_install_mode()

    @inspector(measure_performance=True)
    async def load_and_refresh_data_point_data(
        self,
        *,
        interface: Interface,
        paramset_key: ParamsetKey | None = None,
        direct_call: bool = False,
    ) -> None:
        """Refresh data_point data."""
        if paramset_key != ParamsetKey.MASTER:
            await self._cache_coordinator.data_cache.load(interface=interface)
        await self._cache_coordinator.data_cache.refresh_data_point_data(
            paramset_key=paramset_key, interface=interface, direct_call=direct_call
        )

    async def rename_device(self, *, device_address: str, name: str, include_channels: bool = False) -> bool:
        """
        Rename a device on the CCU.

        Args:
            device_address: The address of the device to rename.
            name: The new name for the device.
            include_channels: If True, also rename all channels using the format "name:channel_no".

        Returns:
            True if the device was successfully renamed, False otherwise.

        """
        if (device := self._device_coordinator.get_device(address=device_address)) is None:
            _LOGGER.warning(
                i18n.tr(key="log.central.rename_device.not_found", device_address=device_address, name=self.name)
            )
            return False

        if not await device.client.rename_device(rega_id=device.rega_id, new_name=name):
            return False

        if include_channels:
            for channel in device.channels.values():
                if channel.no is not None:
                    channel_name = f"{name}:{channel.no}"
                    await device.client.rename_channel(rega_id=channel.rega_id, new_name=channel_name)

        return True

    async def save_files(
        self,
        *,
        save_device_descriptions: bool = False,
        save_paramset_descriptions: bool = False,
    ) -> None:
        """Save files (internal use - use cache_coordinator for external access)."""
        await self._cache_coordinator.save_all(
            save_device_descriptions=save_device_descriptions,
            save_paramset_descriptions=save_paramset_descriptions,
        )

    async def set_install_mode(
        self,
        *,
        interface: Interface,
        on: bool = True,
        time: int = 60,
        mode: int = 1,
        device_address: str | None = None,
    ) -> bool:
        """
        Set the install mode on the backend for a specific interface.

        Args:
            interface: The interface to set install mode on (HMIP_RF or BIDCOS_RF).
            on: Enable or disable install mode.
            time: Duration in seconds (default 60).
            mode: Mode 1=normal, 2=set all ROAMING devices into install mode.
            device_address: Optional device address to limit pairing.

        Returns:
            True if successful.

        """
        try:
            client = self._client_coordinator.get_client(interface=interface)
            return await client.set_install_mode(on=on, time=time, mode=mode, device_address=device_address)
        except AioHomematicException:
            return False

    async def start(self) -> None:
        """Start processing of the central unit."""
        _LOGGER.debug("START: Central %s is %s", self.name, self.state)
        if self.state == CentralState.INITIALIZING:
            _LOGGER.debug("START: Central %s already starting", self.name)
            return

        if self.state == CentralState.RUNNING:
            _LOGGER.debug("START: Central %s already started", self.name)
            return

        # Transition central state machine to INITIALIZING
        if self._central_state_machine.can_transition_to(target=CentralState.INITIALIZING):
            self._central_state_machine.transition_to(
                target=CentralState.INITIALIZING,
                reason="start() called",
            )

        if self._config.session_recorder_start:
            await self._cache_coordinator.recorder.deactivate(
                delay=self._config.session_recorder_start_for_seconds,
                auto_save=True,
                randomize_output=self._config.session_recorder_randomize_output,
                use_ts_in_file_name=False,
            )
            _LOGGER.debug("START: Starting Recorder for %s seconds", self._config.session_recorder_start_for_seconds)

        _LOGGER.debug("START: Initializing Central %s", self.name)
        if self._config.enabled_interface_configs and (
            ip_addr := await self._identify_ip_addr(port=self._config.connection_check_port)
        ):
            self._rpc_callback_ip = ip_addr
            self._listen_ip_addr = self._config.listen_ip_addr if self._config.listen_ip_addr else ip_addr

        port_xml_rpc: int = (
            self._config.listen_port_xml_rpc
            if self._config.listen_port_xml_rpc
            else self._config.callback_port_xml_rpc or self._config.default_callback_port_xml_rpc
        )
        try:
            if (
                xml_rpc_server := rpc.create_xml_rpc_server(ip_addr=self._listen_ip_addr, port=port_xml_rpc)
                if self._config.enable_xml_rpc_server
                else None
            ):
                self._xml_rpc_server = xml_rpc_server
                self._listen_port_xml_rpc = xml_rpc_server.listen_port
                self._xml_rpc_server.add_central(central=self, looper=self.looper)
        except OSError as oserr:  # pragma: no cover - environment/OS-specific socket binding failures are not reliably reproducible in CI
            if self._central_state_machine.can_transition_to(target=CentralState.FAILED):
                self._central_state_machine.transition_to(
                    target=CentralState.FAILED,
                    reason=f"XML-RPC server failed: {extract_exc_args(exc=oserr)}",
                    failure_reason=FailureReason.INTERNAL,
                )
            raise AioHomematicException(
                i18n.tr(
                    key="exception.central.start.failed",
                    name=self.name,
                    reason=extract_exc_args(exc=oserr),
                )
            ) from oserr

        if self._config.start_direct:
            if await self._client_coordinator.start_clients():
                for client in self._client_coordinator.clients:
                    await self._device_coordinator.refresh_device_descriptions_and_create_missing_devices(
                        client=client,
                        refresh_only_existing=False,
                    )
        else:
            if await self._client_coordinator.start_clients() and (
                new_device_addresses := self._device_coordinator.check_for_new_device_addresses()
            ):
                await self._device_coordinator.create_devices(
                    new_device_addresses=new_device_addresses,
                    source=SourceOfDeviceCreation.CACHE,
                )
            if self._config.enable_xml_rpc_server:
                self._start_scheduler()

        # Transition central state machine based on client status
        clients = self._client_coordinator.clients
        _LOGGER.debug(
            "START: Central %s is %s, clients: %s",
            self.name,
            self.state,
            {c.interface_id: c.state.value for c in clients},
        )
        # Note: all() returns True for empty iterables, so we must check clients exist
        all_connected = bool(clients) and all(client.state == ClientState.CONNECTED for client in clients)
        any_connected = any(client.state == ClientState.CONNECTED for client in clients)
        if all_connected and self._central_state_machine.can_transition_to(target=CentralState.RUNNING):
            self._central_state_machine.transition_to(
                target=CentralState.RUNNING,
                reason="all clients connected",
            )
        elif (
            any_connected
            and not all_connected
            and self._central_state_machine.can_transition_to(target=CentralState.DEGRADED)
        ):
            # Build map of disconnected interfaces with their failure reasons
            degraded_interfaces: dict[str, FailureReason] = {
                client.interface_id: (
                    reason
                    if (reason := client.state_machine.failure_reason) != FailureReason.NONE
                    else FailureReason.UNKNOWN
                )
                for client in clients
                if client.state != ClientState.CONNECTED
            }
            self._central_state_machine.transition_to(
                target=CentralState.DEGRADED,
                reason=f"clients not connected: {', '.join(degraded_interfaces.keys())}",
                degraded_interfaces=degraded_interfaces,
            )
        elif not any_connected and self._central_state_machine.can_transition_to(target=CentralState.FAILED):
            self._central_state_machine.transition_to(
                target=CentralState.FAILED,
                reason="no clients connected",
                failure_reason=self._client_coordinator.last_failure_reason,
                failure_interface_id=self._client_coordinator.last_failure_interface_id,
            )

    async def stop(self) -> None:
        """Stop processing of the central unit."""
        _LOGGER.debug("STOP: Central %s is %s", self.name, self.state)
        if self.state == CentralState.STOPPED:
            _LOGGER.debug("STOP: Central %s is already stopped", self.name)
            return

        # Transition to STOPPED directly (no intermediate STOPPING state in CentralState)
        _LOGGER.debug("STOP: Stopping Central %s", self.name)

        await self.save_files(save_device_descriptions=True, save_paramset_descriptions=True)
        await self._stop_scheduler()
        await self._client_coordinator.stop_clients()
        if self._json_rpc_client and self._json_rpc_client.is_activated:
            await self._json_rpc_client.logout()
            await self._json_rpc_client.stop()

        if self._xml_rpc_server:
            # un-register this instance from XmlRPC-Server
            self._xml_rpc_server.remove_central(central=self)
            # un-register and stop XmlRPC-Server, if possible
            if self._xml_rpc_server.no_central_assigned:
                self._xml_rpc_server.stop()
            _LOGGER.debug("STOP: XmlRPC-Server stopped")
        else:
            _LOGGER.debug("STOP: shared XmlRPC-Server NOT stopped. There is still another central instance registered")

        _LOGGER.debug("STOP: Removing instance")
        if self.name in CENTRAL_INSTANCES:
            del CENTRAL_INSTANCES[self.name]

        # Log any leaked subscriptions before clearing (only when debug logging is enabled)
        if _LOGGER.isEnabledFor(logging.DEBUG):
            self._event_coordinator.event_bus.log_leaked_subscriptions()

        # Clear EventBus subscriptions to prevent memory leaks
        self._event_coordinator.event_bus.clear_subscriptions()
        _LOGGER.debug("STOP: EventBus subscriptions cleared")

        # Clear all in-memory caches (device_details, data_cache, parameter_visibility)
        self._cache_coordinator.clear_on_stop()
        _LOGGER.debug("STOP: In-memory caches cleared")

        # Clear client-level caches (command cache, ping-pong cache)
        for client in self._client_coordinator.clients:
            client.last_value_send_cache.clear()
            client.ping_pong_cache.clear()
        _LOGGER.debug("STOP: Client caches cleared")

        # cancel outstanding tasks to speed up teardown
        self.looper.cancel_tasks()
        # wait until tasks are finished (with wait_time safeguard)
        await self.looper.block_till_done(wait_time=5.0)

        # Wait briefly for any auxiliary threads to finish without blocking forever
        max_wait_seconds = 5.0
        interval = 0.05
        waited = 0.0
        while self._has_active_threads and waited < max_wait_seconds:
            await asyncio.sleep(interval)
            waited += interval
        _LOGGER.debug("STOP: Central %s is %s", self.name, self.state)

        # Transition central state machine to STOPPED
        if self._central_state_machine.can_transition_to(target=CentralState.STOPPED):
            self._central_state_machine.transition_to(
                target=CentralState.STOPPED,
                reason="stop() completed",
            )

    async def validate_config_and_get_system_information(self) -> SystemInformation:
        """Validate the central configuration."""
        if len(self._config.enabled_interface_configs) == 0:
            raise NoClientsException(i18n.tr(key="exception.central.validate_config.no_clients"))

        system_information = SystemInformation()
        for interface_config in self._config.enabled_interface_configs:
            try:
                client = await hmcl.create_client(client_deps=self, interface_config=interface_config)
            except BaseHomematicException as bhexc:
                _LOGGER.error(
                    i18n.tr(
                        key="log.central.validate_config_and_get_system_information.client_failed",
                        interface=str(interface_config.interface),
                        reason=extract_exc_args(exc=bhexc),
                    )
                )
                raise
            if client.interface in PRIMARY_CLIENT_CANDIDATE_INTERFACES and not system_information.serial:
                system_information = client.system_information
        return system_information

    async def _identify_ip_addr(self, *, port: int) -> str:
        ip_addr: str | None = None
        while ip_addr is None:
            try:
                ip_addr = await self.looper.async_add_executor_job(
                    partial(get_ip_addr, host=self._config.host, port=port),
                    name="get_ip_addr",
                )
            except AioHomematicException:
                ip_addr = LOCAL_HOST
            if ip_addr is None:
                schedule_cfg = self._config.schedule_timer_config
                timeout_cfg = self._config.timeout_config
                _LOGGER.warning(  # i18n-log: ignore
                    "GET_IP_ADDR: Waiting for %.1f s,", schedule_cfg.connection_checker_interval
                )
                await asyncio.sleep(timeout_cfg.rpc_timeout / 10)
        return ip_addr

    def _on_system_status_event(self, *, event: SystemStatusEvent) -> None:
        """Handle system status events and update central state machine accordingly."""
        # Only handle client state changes
        if event.client_state is None:
            return

        interface_id, old_state, new_state = event.client_state

        # Update health tracker with new client state
        self._health_tracker.update_client_health(
            interface_id=interface_id,
            old_state=old_state,
            new_state=new_state,
        )

        # Determine overall central state based on all client states
        clients = self._client_coordinator.clients
        # Note: all() returns True for empty iterables, so we must check clients exist
        all_connected = bool(clients) and all(client.state == ClientState.CONNECTED for client in clients)
        any_connected = any(client.state == ClientState.CONNECTED for client in clients)

        # Only transition if central is in a state that allows it
        if (current_state := self._central_state_machine.state) not in (CentralState.STARTING, CentralState.STOPPED):
            if all_connected and self._central_state_machine.can_transition_to(target=CentralState.RUNNING):
                self._central_state_machine.transition_to(
                    target=CentralState.RUNNING,
                    reason=f"all clients connected (triggered by {interface_id})",
                )
            elif (
                any_connected
                and not all_connected
                and current_state == CentralState.RUNNING
                and self._central_state_machine.can_transition_to(target=CentralState.DEGRADED)
            ):
                # Only transition to DEGRADED from RUNNING when some (but not all) clients connected
                degraded_interfaces: dict[str, FailureReason] = {
                    client.interface_id: (
                        reason
                        if (reason := client.state_machine.failure_reason) != FailureReason.NONE
                        else FailureReason.UNKNOWN
                    )
                    for client in clients
                    if client.state != ClientState.CONNECTED
                }
                self._central_state_machine.transition_to(
                    target=CentralState.DEGRADED,
                    reason=f"clients not connected: {', '.join(degraded_interfaces.keys())}",
                    degraded_interfaces=degraded_interfaces,
                )
            elif (
                not any_connected
                and current_state in (CentralState.RUNNING, CentralState.DEGRADED)
                and self._central_state_machine.can_transition_to(target=CentralState.FAILED)
            ):
                # All clients failed - get failure reason from first failed client
                failure_reason = FailureReason.NETWORK  # Default for disconnection
                failure_interface_id: str | None = None
                for client in clients:
                    if client.state_machine.is_failed and client.state_machine.failure_reason != FailureReason.NONE:
                        failure_reason = client.state_machine.failure_reason
                        failure_interface_id = client.interface_id
                        break
                self._central_state_machine.transition_to(
                    target=CentralState.FAILED,
                    reason="all clients disconnected",
                    failure_reason=failure_reason,
                    failure_interface_id=failure_interface_id,
                )

    def _start_scheduler(self) -> None:
        """Start the background scheduler."""
        _LOGGER.debug(
            "START_SCHEDULER: Starting scheduler for %s",
            self.name,
        )
        # Schedule async start() method via looper
        self._looper.create_task(
            target=self._scheduler.start(),
            name=f"start_scheduler_{self.name}",
        )

    async def _stop_scheduler(self) -> None:
        """Stop the background scheduler."""
        await self._scheduler.stop()
        _LOGGER.debug(
            "STOP_SCHEDULER: Stopped scheduler for %s",
            self.name,
        )


class CentralConfig:
    """Configuration for CentralUnit initialization and behavior."""

    def __init__(
        self,
        *,
        central_id: str,
        host: str,
        interface_configs: AbstractSet[hmcl.InterfaceConfig],
        name: str,
        password: str,
        username: str,
        client_session: ClientSession | None = None,
        callback_host: str | None = None,
        callback_port_xml_rpc: int | None = None,
        default_callback_port_xml_rpc: int = PORT_ANY,
        delay_new_device_creation: bool = DEFAULT_DELAY_NEW_DEVICE_CREATION,
        enable_device_firmware_check: bool = DEFAULT_ENABLE_DEVICE_FIRMWARE_CHECK,
        enable_program_scan: bool = DEFAULT_ENABLE_PROGRAM_SCAN,
        enable_sysvar_scan: bool = DEFAULT_ENABLE_SYSVAR_SCAN,
        ignore_custom_device_definition_models: frozenset[str] = DEFAULT_IGNORE_CUSTOM_DEVICE_DEFINITION_MODELS,
        interfaces_requiring_periodic_refresh: frozenset[Interface] = DEFAULT_INTERFACES_REQUIRING_PERIODIC_REFRESH,
        json_port: int | None = None,
        listen_ip_addr: str | None = None,
        listen_port_xml_rpc: int | None = None,
        max_read_workers: int = DEFAULT_MAX_READ_WORKERS,
        optional_settings: tuple[OptionalSettings | str, ...] = DEFAULT_OPTIONAL_SETTINGS,
        program_markers: tuple[DescriptionMarker | str, ...] = DEFAULT_PROGRAM_MARKERS,
        schedule_timer_config: ScheduleTimerConfig = DEFAULT_SCHEDULE_TIMER_CONFIG,
        start_direct: bool = False,
        storage_directory: str = DEFAULT_STORAGE_DIRECTORY,
        sysvar_markers: tuple[DescriptionMarker | str, ...] = DEFAULT_SYSVAR_MARKERS,
        timeout_config: TimeoutConfig = DEFAULT_TIMEOUT_CONFIG,
        tls: bool = DEFAULT_TLS,
        un_ignore_list: frozenset[str] = DEFAULT_UN_IGNORES,
        use_group_channel_for_cover_state: bool = DEFAULT_USE_GROUP_CHANNEL_FOR_COVER_STATE,
        verify_tls: bool = DEFAULT_VERIFY_TLS,
        locale: str = DEFAULT_LOCALE,
    ) -> None:
        """Initialize the central configuration."""
        self._interface_configs: Final = interface_configs
        self._optional_settings: Final = frozenset(optional_settings or ())
        self.requires_xml_rpc_server: Final = any(
            ic for ic in interface_configs if ic.rpc_server == RpcServerType.XML_RPC
        )
        self.callback_host: Final = callback_host
        self.callback_port_xml_rpc: Final = callback_port_xml_rpc
        self.central_id: Final = central_id
        self.client_session: Final = client_session
        self.default_callback_port_xml_rpc: Final = default_callback_port_xml_rpc
        self.delay_new_device_creation: Final = delay_new_device_creation
        self.enable_device_firmware_check: Final = enable_device_firmware_check
        self.enable_program_scan: Final = enable_program_scan
        self.enable_sysvar_scan: Final = enable_sysvar_scan
        self.host: Final = host
        self.ignore_custom_device_definition_models: Final = frozenset(ignore_custom_device_definition_models or ())
        self.interfaces_requiring_periodic_refresh: Final = frozenset(interfaces_requiring_periodic_refresh or ())
        self.json_port: Final = json_port
        self.listen_ip_addr: Final = listen_ip_addr
        self.listen_port_xml_rpc: Final = listen_port_xml_rpc
        self.max_read_workers = max_read_workers
        self.name: Final = name
        self.password: Final = password
        self.program_markers: Final = program_markers
        self.start_direct: Final = start_direct
        self.session_recorder_randomize_output = (
            OptionalSettings.SR_DISABLE_RANDOMIZE_OUTPUT not in self._optional_settings
        )
        self.session_recorder_start_for_seconds: Final = (
            DEFAULT_SESSION_RECORDER_START_FOR_SECONDS
            if OptionalSettings.SR_RECORD_SYSTEM_INIT in self._optional_settings
            else 0
        )
        self.session_recorder_start = self.session_recorder_start_for_seconds > 0
        self.schedule_timer_config: Final = schedule_timer_config
        self.storage_directory: Final = storage_directory
        self.sysvar_markers: Final = sysvar_markers
        self.timeout_config: Final = timeout_config
        self.tls: Final = tls
        self.un_ignore_list: Final = un_ignore_list
        self.use_group_channel_for_cover_state: Final = use_group_channel_for_cover_state
        self.username: Final = username
        self.verify_tls: Final = verify_tls
        self.locale: Final = locale

    @classmethod
    def for_ccu(
        cls,
        *,
        host: str,
        username: str,
        password: str,
        name: str = "ccu",
        central_id: str | None = None,
        tls: bool = False,
        enable_hmip: bool = True,
        enable_bidcos_rf: bool = True,
        enable_bidcos_wired: bool = False,
        enable_virtual_devices: bool = False,
        **kwargs: Any,
    ) -> CentralConfig:
        """
        Create a CentralConfig preset for CCU3/CCU2 backends.

        This factory method simplifies configuration for CCU backends by
        automatically setting up common interfaces with their default ports.

        Args:
            host: Hostname or IP address of the CCU.
            username: CCU username for authentication.
            password: CCU password for authentication.
            name: Name identifier for the central unit.
            central_id: Unique identifier for the central. Auto-generated if not provided.
            tls: Enable TLS encryption for connections.
            enable_hmip: Enable HomematicIP wireless interface (port 2010/42010).
            enable_bidcos_rf: Enable BidCos RF interface (port 2001/42001).
            enable_bidcos_wired: Enable BidCos wired interface (port 2000/42000).
            enable_virtual_devices: Enable virtual devices interface (port 9292/49292).
            **kwargs: Additional arguments passed to CentralConfig constructor.

        Returns:
            Configured CentralConfig instance ready for create_central().

        Example:
            config = CentralConfig.for_ccu(
                host="192.168.1.100",
                username="Admin",
                password="secret",
            )
            central = config.create_central()

        """
        interface_configs: set[hmcl.InterfaceConfig] = set()

        if enable_hmip and (port := get_interface_default_port(interface=Interface.HMIP_RF, tls=tls)):
            interface_configs.add(
                hmcl.InterfaceConfig(
                    central_name=name,
                    interface=Interface.HMIP_RF,
                    port=port,
                )
            )

        if enable_bidcos_rf and (port := get_interface_default_port(interface=Interface.BIDCOS_RF, tls=tls)):
            interface_configs.add(
                hmcl.InterfaceConfig(
                    central_name=name,
                    interface=Interface.BIDCOS_RF,
                    port=port,
                )
            )

        if enable_bidcos_wired and (port := get_interface_default_port(interface=Interface.BIDCOS_WIRED, tls=tls)):
            interface_configs.add(
                hmcl.InterfaceConfig(
                    central_name=name,
                    interface=Interface.BIDCOS_WIRED,
                    port=port,
                )
            )

        if enable_virtual_devices and (
            port := get_interface_default_port(interface=Interface.VIRTUAL_DEVICES, tls=tls)
        ):
            interface_configs.add(
                hmcl.InterfaceConfig(
                    central_name=name,
                    interface=Interface.VIRTUAL_DEVICES,
                    port=port,
                    remote_path="/groups",
                )
            )

        return cls(
            central_id=central_id or f"{name}-{host}",
            host=host,
            username=username,
            password=password,
            name=name,
            interface_configs=interface_configs,
            json_port=get_json_rpc_default_port(tls=tls),
            tls=tls,
            **kwargs,
        )

    @classmethod
    def for_homegear(
        cls,
        *,
        host: str,
        username: str,
        password: str,
        name: str = "homegear",
        central_id: str | None = None,
        tls: bool = False,
        port: int | None = None,
        **kwargs: Any,
    ) -> CentralConfig:
        """
        Create a CentralConfig preset for Homegear backends.

        This factory method simplifies configuration for Homegear backends
        with the BidCos-RF interface.

        Args:
            host: Hostname or IP address of the Homegear server.
            username: Homegear username for authentication.
            password: Homegear password for authentication.
            name: Name identifier for the central unit.
            central_id: Unique identifier for the central. Auto-generated if not provided.
            tls: Enable TLS encryption for connections.
            port: Custom port for BidCos-RF interface. Uses default (2001/42001) if not set.
            **kwargs: Additional arguments passed to CentralConfig constructor.

        Returns:
            Configured CentralConfig instance ready for create_central().

        Example:
            config = CentralConfig.for_homegear(
                host="192.168.1.50",
                username="homegear",
                password="secret",
            )
            central = config.create_central()

        """
        interface_port = port or get_interface_default_port(interface=Interface.BIDCOS_RF, tls=tls) or 2001

        interface_configs: set[hmcl.InterfaceConfig] = {
            hmcl.InterfaceConfig(
                central_name=name,
                interface=Interface.BIDCOS_RF,
                port=interface_port,
            )
        }

        return cls(
            central_id=central_id or f"{name}-{host}",
            host=host,
            username=username,
            password=password,
            name=name,
            interface_configs=interface_configs,
            tls=tls,
            **kwargs,
        )

    optional_settings: Final = DelegatedProperty[frozenset[OptionalSettings | str]](path="_optional_settings")

    @property
    def connection_check_port(self) -> int:
        """Return the connection check port."""
        if used_ports := tuple(ic.port for ic in self._interface_configs if ic.port is not None):
            return used_ports[0]
        if self.json_port:
            return self.json_port
        return 443 if self.tls else 80

    @property
    def enable_xml_rpc_server(self) -> bool:
        """Return if server and connection checker should be started."""
        return self.requires_xml_rpc_server and self.start_direct is False

    @property
    def enabled_interface_configs(self) -> frozenset[hmcl.InterfaceConfig]:
        """Return the interface configs."""
        return frozenset(ic for ic in self._interface_configs if ic.enabled is True)

    @property
    def load_un_ignore(self) -> bool:
        """Return if un_ignore should be loaded."""
        return self.start_direct is False

    @property
    def use_caches(self) -> bool:
        """Return if store should be used."""
        return self.start_direct is False

    def check_config(self) -> None:
        """Check config. Throws BaseHomematicException on failure."""
        if config_failures := check_config(
            central_name=self.name,
            host=self.host,
            username=self.username,
            password=self.password,
            storage_directory=self.storage_directory,
            callback_host=self.callback_host,
            callback_port_xml_rpc=self.callback_port_xml_rpc,
            json_port=self.json_port,
            interface_configs=self._interface_configs,
        ):
            failures = ", ".join(config_failures)
            # Localized exception message
            msg = i18n.tr(key="exception.config.invalid", failures=failures)
            raise AioHomematicConfigException(msg)

    def create_central(self) -> CentralUnit:
        """Create the central. Throws BaseHomematicException on validation failure."""
        try:
            self.check_config()
            return CentralUnit(central_config=self)
        except BaseHomematicException as bhexc:  # pragma: no cover
            raise AioHomematicException(
                i18n.tr(
                    key="exception.create_central.failed",
                    reason=extract_exc_args(exc=bhexc),
                )
            ) from bhexc

    def create_central_url(self) -> str:
        """Return the required url."""
        url = "https://" if self.tls else "http://"
        url = f"{url}{self.host}"
        if self.json_port:
            url = f"{url}:{self.json_port}"
        return f"{url}"

    def create_json_rpc_client(
        self,
        *,
        central: CentralUnit,
        health_record_callback: hmcl.HealthRecordCallbackProtocol | None = None,
    ) -> AioJsonRpcAioHttpClient:
        """Create a json rpc client."""
        return AioJsonRpcAioHttpClient(
            username=self.username,
            password=self.password,
            device_url=central.url,
            connection_state=central.connection_state,
            client_session=self.client_session,
            tls=self.tls,
            verify_tls=self.verify_tls,
            session_recorder=central.cache_coordinator.recorder,
            health_record_callback=health_record_callback,
        )


class CentralConnectionState:
    """
    Track connection status for the central unit.

    Manages connection issues per transport (JSON-RPC and XML-RPC proxies),
    publishing SystemStatusEvent via EventBus for state changes.
    """

    def __init__(self, *, event_bus_provider: EventBusProviderProtocol | None = None) -> None:
        """Initialize the CentralConnectionStatus."""
        self._json_issues: Final[list[str]] = []
        self._rpc_proxy_issues: Final[list[str]] = []
        self._event_bus_provider = event_bus_provider

    @property
    def has_any_issue(self) -> bool:
        """Return True if any connection issue exists."""
        return len(self._json_issues) > 0 or len(self._rpc_proxy_issues) > 0

    @property
    def issue_count(self) -> int:
        """Return total number of connection issues."""
        return len(self._json_issues) + len(self._rpc_proxy_issues)

    @property
    def json_issue_count(self) -> int:
        """Return number of JSON-RPC connection issues."""
        return len(self._json_issues)

    @property
    def rpc_proxy_issue_count(self) -> int:
        """Return number of XML-RPC proxy connection issues."""
        return len(self._rpc_proxy_issues)

    def add_issue(self, *, issuer: ConnectionProblemIssuer, iid: str) -> bool:
        """Add issue to collection and publish event."""
        added = False
        if isinstance(issuer, AioJsonRpcAioHttpClient) and iid not in self._json_issues:
            self._json_issues.append(iid)
            _LOGGER.debug("add_issue: add issue  [%s] for JsonRpcAioHttpClient", iid)
            added = True
        elif isinstance(issuer, BaseRpcProxy) and iid not in self._rpc_proxy_issues:
            self._rpc_proxy_issues.append(iid)
            _LOGGER.debug("add_issue: add issue [%s] for RpcProxy", iid)
            added = True

        if added:
            self._publish_state_change(interface_id=iid, connected=False)
        return added

    def clear_all_issues(self) -> int:
        """
        Clear all tracked connection issues.

        Returns the number of issues cleared.
        """
        if (count := self.issue_count) > 0:
            all_iids = list(self._json_issues) + list(self._rpc_proxy_issues)
            self._json_issues.clear()
            self._rpc_proxy_issues.clear()
            for iid in all_iids:
                self._publish_state_change(interface_id=iid, connected=True)
            return count
        return 0

    def handle_exception_log(
        self,
        *,
        issuer: ConnectionProblemIssuer,
        iid: str,
        exception: Exception,
        logger: logging.Logger = _LOGGER,
        level: int = logging.ERROR,
        extra_msg: str = "",
        multiple_logs: bool = True,
    ) -> None:
        """Handle Exception and derivates logging."""
        exception_name = exception.name if hasattr(exception, "name") else exception.__class__.__name__
        if self.has_issue(issuer=issuer, iid=iid) and multiple_logs is False:
            logger.debug(
                "%s failed: %s [%s] %s",
                iid,
                exception_name,
                extract_exc_args(exc=exception),
                extra_msg,
            )
        else:
            self.add_issue(issuer=issuer, iid=iid)
            logger.log(
                level,
                "%s failed: %s [%s] %s",
                iid,
                exception_name,
                extract_exc_args(exc=exception),
                extra_msg,
            )

    def has_issue(self, *, issuer: ConnectionProblemIssuer, iid: str) -> bool:
        """Check if issue exists for the given issuer and interface id."""
        if isinstance(issuer, AioJsonRpcAioHttpClient):
            return iid in self._json_issues
        # issuer is BaseRpcProxy (exhaustive union coverage)
        return iid in self._rpc_proxy_issues

    def has_rpc_proxy_issue(self, *, interface_id: str) -> bool:
        """Return True if XML-RPC proxy has a known connection issue for interface_id."""
        return interface_id in self._rpc_proxy_issues

    def remove_issue(self, *, issuer: ConnectionProblemIssuer, iid: str) -> bool:
        """Remove issue from collection and publish event."""
        removed = False
        if isinstance(issuer, AioJsonRpcAioHttpClient) and iid in self._json_issues:
            self._json_issues.remove(iid)
            _LOGGER.debug("remove_issue: removing issue [%s] for JsonRpcAioHttpClient", iid)
            removed = True
        elif isinstance(issuer, BaseRpcProxy) and iid in self._rpc_proxy_issues:
            self._rpc_proxy_issues.remove(iid)
            _LOGGER.debug("remove_issue: removing issue [%s] for RpcProxy", iid)
            removed = True

        if removed:
            self._publish_state_change(interface_id=iid, connected=True)
        return removed

    def _publish_state_change(self, *, interface_id: str, connected: bool) -> None:
        """Publish SystemStatusEvent via EventBus."""
        if self._event_bus_provider is None:
            return
        event = SystemStatusEvent(
            timestamp=datetime.now(),
            connection_state=(interface_id, connected),
        )
        self._event_bus_provider.event_bus.publish_sync(event=event)


def check_config(
    *,
    central_name: str,
    host: str,
    username: str,
    password: str,
    storage_directory: str,
    callback_host: str | None,
    callback_port_xml_rpc: int | None,
    json_port: int | None,
    interface_configs: AbstractSet[hmcl.InterfaceConfig] | None = None,
) -> list[str]:
    """Check config. Throws BaseHomematicException on failure."""
    config_failures: list[str] = []
    if central_name and IDENTIFIER_SEPARATOR in central_name:
        config_failures.append(i18n.tr(key="exception.config.check.instance_name.separator", sep=IDENTIFIER_SEPARATOR))

    if not (is_host(host=host) or is_ipv4_address(address=host)):
        config_failures.append(i18n.tr(key="exception.config.check.host.invalid"))
    if not username:
        config_failures.append(i18n.tr(key="exception.config.check.username.empty"))
    if not password:
        config_failures.append(i18n.tr(key="exception.config.check.password.required"))
    if not check_password(password=password):
        config_failures.append(i18n.tr(key="exception.config.check.password.invalid"))
    try:
        check_or_create_directory(directory=storage_directory)
    except BaseHomematicException as bhexc:
        config_failures.append(extract_exc_args(exc=bhexc)[0])
    if callback_host and not (is_host(host=callback_host) or is_ipv4_address(address=callback_host)):
        config_failures.append(i18n.tr(key="exception.config.check.callback_host.invalid"))
    if callback_port_xml_rpc and not is_port(port=callback_port_xml_rpc):
        config_failures.append(i18n.tr(key="exception.config.check.callback_port_xml_rpc.invalid"))
    if json_port and not is_port(port=json_port):
        config_failures.append(i18n.tr(key="exception.config.check.json_port.invalid"))
    if interface_configs and not _has_primary_client(interface_configs=interface_configs):
        config_failures.append(
            i18n.tr(
                key="exception.config.check.primary_interface.missing",
                interfaces=", ".join(PRIMARY_CLIENT_CANDIDATE_INTERFACES),
            )
        )

    return config_failures


def _has_primary_client(*, interface_configs: AbstractSet[hmcl.InterfaceConfig]) -> bool:
    """Check if all configured clients exists in central."""
    for interface_config in interface_configs:
        if interface_config.interface in PRIMARY_CLIENT_CANDIDATE_INTERFACES:
            return True
    return False


def _get_new_data_points(
    *,
    new_devices: set[DeviceProtocol],
) -> Mapping[DataPointCategory, AbstractSet[CallbackDataPointProtocol]]:
    """Return new data points by category."""
    data_points_by_category: dict[DataPointCategory, set[CallbackDataPointProtocol]] = {
        category: set() for category in CATEGORIES if category != DataPointCategory.EVENT
    }

    for device in new_devices:
        for category, data_points in data_points_by_category.items():
            data_points.update(device.get_data_points(category=category, exclude_no_create=True, registered=False))

    return data_points_by_category


def _get_new_channel_events(*, new_devices: set[DeviceProtocol]) -> tuple[tuple[GenericEventProtocolAny, ...], ...]:
    """Return new channel events by category."""
    channel_events: list[tuple[GenericEventProtocolAny, ...]] = []

    for device in new_devices:
        for event_type in DATA_POINT_EVENTS:
            if (hm_channel_events := list(device.get_events(event_type=event_type, registered=False).values())) and len(
                hm_channel_events
            ) > 0:
                channel_events.append(hm_channel_events)  # type: ignore[arg-type] # noqa:PERF401

    return tuple(channel_events)
