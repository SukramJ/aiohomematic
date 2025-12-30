# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Central unit orchestration for Homematic CCU and compatible backends.

This module provides the CentralUnit class that orchestrates interfaces, devices,
channels, data points, events, and background jobs for a Homematic CCU.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Set as AbstractSet
from functools import partial
import logging
from typing import TYPE_CHECKING, Final

from aiohomematic import client as hmcl, i18n
from aiohomematic.async_support import Looper
from aiohomematic.central import rpc_server as rpc
from aiohomematic.central.connection_state import CentralConnectionState
from aiohomematic.central.coordinators import (
    CacheCoordinator,
    ClientCoordinator,
    ConnectionRecoveryCoordinator,
    DeviceCoordinator,
    EventCoordinator,
    HubCoordinator,
)
from aiohomematic.central.device_registry import DeviceRegistry
from aiohomematic.central.events import EventBus, SystemStatusChangedEvent
from aiohomematic.central.health import CentralHealth, HealthTracker
from aiohomematic.central.scheduler import BackgroundScheduler
from aiohomematic.central.state_machine import CentralStateMachine
from aiohomematic.client import AioJsonRpcAioHttpClient
from aiohomematic.const import (
    CATEGORIES,
    DATA_POINT_EVENTS,
    DEFAULT_LOCALE,
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
    DeviceTriggerEventType,
    FailureReason,
    Interface,
    Operations,
    ParamsetKey,
    SourceOfDeviceCreation,
    SystemInformation,
)
from aiohomematic.decorators import inspector
from aiohomematic.exceptions import AioHomematicException, BaseHomematicException, NoClientsException
from aiohomematic.interfaces.central import CentralProtocol
from aiohomematic.interfaces.client import ClientProtocol
from aiohomematic.interfaces.model import (
    CallbackDataPointProtocol,
    CustomDataPointProtocol,
    DeviceProtocol,
    GenericDataPointProtocol,
    GenericDataPointProtocolAny,
    GenericEventProtocolAny,
)
from aiohomematic.metrics import MetricsAggregator, MetricsObserver
from aiohomematic.model.hub import InstallModeDpType
from aiohomematic.property_decorators import DelegatedProperty, Kind, info_property
from aiohomematic.support import (
    LogContextMixin,
    PayloadMixin,
    extract_exc_args,
    get_channel_no,
    get_device_address,
    get_ip_addr,
)

if TYPE_CHECKING:
    from aiohomematic.central.config import CentralConfig

_LOGGER: Final = logging.getLogger(__name__)

# {central_name, central}
CENTRAL_INSTANCES: Final[dict[str, CentralUnit]] = {}


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
            event_bus=self._event_bus,
        )

        # Initialize coordinators
        self._client_coordinator: Final = ClientCoordinator(
            client_factory=self,
            central_info=self,
            config_provider=self,
            coordinator_provider=self,
            event_bus_provider=self,
            health_tracker=self._health_tracker,
            system_info_provider=self,
        )
        self._cache_coordinator: Final = CacheCoordinator(
            central_info=self,
            client_provider=self._client_coordinator,
            config_provider=self,
            data_point_provider=self,
            device_provider=self,
            event_bus_provider=self,
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
            state_provider=self,
        )

        # Unified connection recovery coordinator (event-driven)
        self._connection_recovery_coordinator: Final = ConnectionRecoveryCoordinator(
            central_info=self,
            config_provider=self,
            client_provider=self._client_coordinator,
            coordinator_provider=self,
            device_data_refresher=self,
            event_bus=self._event_bus,
            task_scheduler=self.looper,
            state_machine=self._central_state_machine,
        )

        # Metrics observer for event-driven metrics (single source of truth)
        self._metrics_observer: Final = MetricsObserver(event_bus=self._event_bus)

        # Metrics aggregator for detailed observability (queries observer + components)
        self._metrics_aggregator: Final = MetricsAggregator(
            central_name=self.name,
            client_provider=self._client_coordinator,
            device_provider=self._device_registry,
            event_bus=self._event_bus,
            health_tracker=self._health_tracker,
            data_cache=self._cache_coordinator.data_cache,
            observer=self._metrics_observer,
            hub_data_point_manager=self._hub_coordinator,
        )

        # Subscribe to system status events to update central state machine
        self.event_bus.subscribe(
            event_type=SystemStatusChangedEvent,
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
    connection_recovery_coordinator: Final = DelegatedProperty[ConnectionRecoveryCoordinator](
        path="_connection_recovery_coordinator"
    )
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
    metrics: Final = DelegatedProperty[MetricsObserver](path="_metrics_observer")
    metrics_aggregator: Final = DelegatedProperty[MetricsAggregator](path="_metrics_aggregator")
    name: Final = DelegatedProperty[str](path="_config.name", kind=Kind.INFO, log_context=True)
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
            # Use primary client's interface_id for health tracking
            primary_interface_id = (
                self._client_coordinator.primary_client.interface_id
                if self._client_coordinator.primary_client
                else None
            )
            self._json_rpc_client = self._config.create_json_rpc_client(
                central=self,
                interface_id=primary_interface_id,
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
    ) -> ClientProtocol:
        """
        Create a client for the given interface configuration.

        This method implements the ClientFactoryProtocol protocol to enable
        dependency injection without requiring the full CentralUnit.

        Args:
        ----
            interface_config: Configuration for the interface

        Returns:
        -------
            Client instance for the interface

        """
        return await hmcl.create_client(
            client_deps=self,
            interface_config=interface_config,
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
        self._metrics_observer.stop()
        self._connection_recovery_coordinator.stop()
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

    def _on_system_status_event(self, *, event: SystemStatusChangedEvent) -> None:
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
            # Don't transition to RUNNING if recovery is still in progress for any interface.
            # The ConnectionRecoveryCoordinator will handle the transition when all recoveries complete.
            if (
                all_connected
                and not self._connection_recovery_coordinator.in_recovery
                and self._central_state_machine.can_transition_to(target=CentralState.RUNNING)
            ):
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
