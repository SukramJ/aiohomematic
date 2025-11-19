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
  sysvar/program access, cache loading/saving, and dispatching callbacks.
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
import logging
from typing import Any, Final

from aiohttp import ClientSession
import voluptuous as vol

from aiohomematic import client as hmcl, i18n
from aiohomematic.async_support import Looper, loop_check
from aiohomematic.central import rpc_server as rpc
from aiohomematic.central.cache_coordinator import CacheCoordinator
from aiohomematic.central.client_coordinator import ClientCoordinator
from aiohomematic.central.decorators import callback_backend_system, callback_event
from aiohomematic.central.device_coordinator import DeviceCoordinator
from aiohomematic.central.device_registry import DeviceRegistry
from aiohomematic.central.event_bus import EventBus
from aiohomematic.central.event_coordinator import EventCoordinator
from aiohomematic.central.hub_coordinator import HubCoordinator
from aiohomematic.central.scheduler import BackgroundScheduler, SchedulerJob as _SchedulerJob
from aiohomematic.client import AioJsonRpcAioHttpClient, BaseRpcProxy
from aiohomematic.const import (
    CATEGORIES,
    CONNECTION_CHECKER_INTERVAL,
    DATA_POINT_EVENTS,
    DEFAULT_DELAY_NEW_DEVICE_CREATION,
    DEFAULT_ENABLE_DEVICE_FIRMWARE_CHECK,
    DEFAULT_ENABLE_PROGRAM_SCAN,
    DEFAULT_ENABLE_SYSVAR_SCAN,
    DEFAULT_HM_MASTER_POLL_AFTER_SEND_INTERVALS,
    DEFAULT_IGNORE_CUSTOM_DEVICE_DEFINITION_MODELS,
    DEFAULT_INTERFACES_REQUIRING_PERIODIC_REFRESH,
    DEFAULT_LOCALE,
    DEFAULT_MAX_READ_WORKERS,
    DEFAULT_OPTIONAL_SETTINGS,
    DEFAULT_PERIODIC_REFRESH_INTERVAL,
    DEFAULT_PROGRAM_MARKERS,
    DEFAULT_SESSION_RECORDER_START_FOR_SECONDS,
    DEFAULT_STORAGE_DIRECTORY,
    DEFAULT_SYS_SCAN_INTERVAL,
    DEFAULT_SYSVAR_MARKERS,
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
    TIMEOUT,
    UN_IGNORE_WILDCARD,
    BackendSystemEvent,
    CentralUnitState,
    DataPointCategory,
    DescriptionMarker,
    DeviceDescription,
    DeviceFirmwareState,
    EventKey,
    EventType,
    Interface,
    InterfaceEventType,
    Operations,
    OptionalSettings,
    ParamsetKey,
    RpcServerType,
    SourceOfDeviceCreation,
    SystemInformation,
)
from aiohomematic.decorators import inspector
from aiohomematic.exceptions import (
    AioHomematicConfigException,
    AioHomematicException,
    BaseHomematicException,
    NoClientsException,
)
from aiohomematic.model.custom import CustomDataPoint
from aiohomematic.model.data_point import BaseParameterDataPointAny, CallbackDataPoint
from aiohomematic.model.device import Channel, Device
from aiohomematic.model.event import GenericEvent
from aiohomematic.model.generic import GenericDataPoint, GenericDataPointAny
from aiohomematic.model.hub import GenericHubDataPoint, GenericProgramDataPoint, GenericSysvarDataPoint, ProgramDpType
from aiohomematic.property_decorators import info_property
from aiohomematic.store import (
    CentralDataCache,
    DeviceDescriptionCache,
    DeviceDetailsCache,
    ParameterVisibilityCache,
    ParamsetDescriptionCache,
    SessionRecorder,
)
from aiohomematic.support import (
    LogContextMixin,
    PayloadMixin,
    check_or_create_directory,
    check_password,
    extract_exc_args,
    get_channel_no,
    get_device_address,
    get_ip_addr,
    is_hostname,
    is_ipv4_address,
    is_port,
)

# No longer needed - types are in coordinators

__all__ = ["CentralConfig", "CentralUnit", "DeviceRegistry", "INTERFACE_EVENT_SCHEMA", "_SchedulerJob"]

_LOGGER: Final = logging.getLogger(__name__)
_LOGGER_EVENT: Final = logging.getLogger(f"{__package__}.event")

# {central_name, central}
CENTRAL_INSTANCES: Final[dict[str, CentralUnit]] = {}
ConnectionProblemIssuer = AioJsonRpcAioHttpClient | BaseRpcProxy

INTERFACE_EVENT_SCHEMA = vol.Schema(
    {
        vol.Required(str(EventKey.INTERFACE_ID)): str,
        vol.Required(str(EventKey.TYPE)): InterfaceEventType,
        vol.Required(str(EventKey.DATA)): vol.Schema(
            {vol.Required(vol.Any(EventKey)): vol.Schema(vol.Any(str, int, bool))}
        ),
    }
)


class CentralUnit(LogContextMixin, PayloadMixin):
    """Central unit that collects everything to handle communication from/to the backend."""

    def __init__(self, *, central_config: CentralConfig) -> None:
        """Init the central unit."""
        self._state: CentralUnitState = CentralUnitState.NEW
        self._connection_state: Final = CentralConnectionState()
        self._tasks: Final[set[asyncio.Future[Any]]] = set()
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

        # Initialize coordinators
        self._cache_coordinator: Final = CacheCoordinator(
            central_info=self,
            device_provider=self,  # type: ignore[arg-type]
            client_provider=self,
            data_point_provider=self,
            primary_client_provider=self,
            config_provider=self,
            task_scheduler=self.looper,
            session_recorder_active=self.config.session_recorder_start,
        )
        self._event_coordinator: Final = EventCoordinator(
            client_provider=self,
            task_scheduler=self.looper,
        )
        self._device_registry: Final = DeviceRegistry(
            central_info=self,
            client_provider=self,
        )
        self._device_coordinator: Final = DeviceCoordinator(
            central=self,
            coordinator_provider=self,
            central_info=self,
            config_provider=self,
        )
        self._client_coordinator: Final = ClientCoordinator(
            central=self,  # Required for client factory
            config_provider=self,
            central_info=self,
            coordinator_provider=self,
            system_info_provider=self,
        )
        self._hub_coordinator: Final = HubCoordinator(
            central=self,  # Required for Hub construction
            central_info=self,
            event_bus_provider=self,
            primary_client_provider=self,
        )

        CENTRAL_INSTANCES[self.name] = self
        self._scheduler: Final = BackgroundScheduler(
            central_info=self,
            config_provider=self,
            client_coordination=self,
            device_data_refresher=self,
            hub_data_fetcher=self,
            event_bus_provider=self,
            state_provider=self,
        )
        self._version: str | None = None
        self._rpc_callback_ip: str = IP_ANY_V4
        self._listen_ip_addr: str = IP_ANY_V4
        self._listen_port_xml_rpc: int = PORT_ANY

    def __str__(self) -> str:
        """Provide some useful information."""
        return f"central: {self.name}"

    @property
    def _has_active_threads(self) -> bool:
        """Return if active sub threads are alive."""
        # BackgroundScheduler is async-based, not a thread
        # Only check XML-RPC server thread
        return bool(
            self._xml_rpc_server and self._xml_rpc_server.no_central_assigned and self._xml_rpc_server.is_alive()
        )

    @property
    def all_clients_active(self) -> bool:
        """Check if all configured clients exists in central."""
        return self._client_coordinator.all_clients_active

    @property
    def available(self) -> bool:
        """Return the availability of the central."""
        return self._client_coordinator.available

    @property
    def cache_coordinator(self) -> CacheCoordinator:
        """Return the cache coordinator."""
        return self._cache_coordinator

    @property
    def callback_ip_addr(self) -> str:
        """Return the xml rpc server callback ip address."""
        return self._rpc_callback_ip

    @property
    def client_coordinator(self) -> ClientCoordinator:
        """Return the client coordinator."""
        return self._client_coordinator

    @property
    def clients(self) -> tuple[hmcl.Client, ...]:
        """Return all clients."""
        return self._client_coordinator.clients

    @property
    def config(self) -> CentralConfig:
        """Return central config."""
        return self._config

    @property
    def connection_state(self) -> CentralConnectionState:
        """Return the connection state."""
        return self._connection_state

    @property
    def data_cache(self) -> CentralDataCache:
        """Return data_cache cache."""
        return self._cache_coordinator.data_cache

    @property
    def device_coordinator(self) -> DeviceCoordinator:
        """Return the device coordinator."""
        return self._device_coordinator

    @property
    def device_descriptions(self) -> DeviceDescriptionCache:
        """Return device_descriptions cache."""
        return self._cache_coordinator.device_descriptions

    @property
    def device_details(self) -> DeviceDetailsCache:
        """Return device_details cache."""
        return self._cache_coordinator.device_details

    @property
    def device_registry(self) -> DeviceRegistry:
        """Return the device registry."""
        return self._device_registry

    @property
    def devices(self) -> tuple[Device, ...]:
        """Return all devices."""
        return self._device_coordinator.devices

    @property
    def event_bus(self) -> EventBus:
        """
        Return the EventBus for event subscription.

        The EventBus provides a type-safe API for subscribing to events.

        Example:
        -------
            central.event_bus.subscribe(DataPointUpdatedEvent, my_handler)

        """
        return self._event_coordinator.event_bus

    @property
    def event_coordinator(self) -> EventCoordinator:
        """Return the event coordinator."""
        return self._event_coordinator

    @property
    def has_clients(self) -> bool:
        """Check if clients exists in central."""
        return self._client_coordinator.has_clients

    @property
    def hub_coordinator(self) -> HubCoordinator:
        """Return the hub coordinator."""
        return self._hub_coordinator

    @property
    def interface_ids(self) -> frozenset[str]:
        """Return all associated interface ids."""
        return self._client_coordinator.interface_ids

    @property
    def interfaces(self) -> frozenset[Interface]:
        """Return all associated interfaces."""
        return self._client_coordinator.interfaces

    @property
    def is_alive(self) -> bool:
        """Return if XmlRPC-Server is alive."""
        return self._client_coordinator.is_alive

    @property
    def json_rpc_client(self) -> AioJsonRpcAioHttpClient:
        """Return the json rpc client."""
        if not self._json_rpc_client:
            self._json_rpc_client = self._config.create_json_rpc_client(central=self)
        return self._json_rpc_client

    @property
    def listen_ip_addr(self) -> str:
        """Return the xml rpc server listening ip address."""
        return self._listen_ip_addr

    @property
    def listen_port_xml_rpc(self) -> int:
        """Return the xml rpc listening server port."""
        return self._listen_port_xml_rpc

    @property
    def looper(self) -> Looper:
        """Return the loop support."""
        return self._looper

    @property
    def parameter_visibility(self) -> ParameterVisibilityCache:
        """Return parameter_visibility cache."""
        return self._cache_coordinator.parameter_visibility

    @property
    def paramset_descriptions(self) -> ParamsetDescriptionCache:
        """Return paramset_descriptions cache."""
        return self._cache_coordinator.paramset_descriptions

    @property
    def poll_clients(self) -> tuple[hmcl.Client, ...]:
        """Return clients that need to poll data."""
        return self._client_coordinator.poll_clients

    @property
    def primary_client(self) -> hmcl.Client | None:
        """Return the primary client of the backend."""
        return self._client_coordinator.primary_client

    @property
    def program_data_points(self) -> tuple[GenericProgramDataPoint, ...]:
        """Return the program data points."""
        return self._hub_coordinator.program_data_points

    @property
    def recorder(self) -> SessionRecorder:
        """Return the session recorder."""
        return self._cache_coordinator.recorder

    @property
    def state(self) -> CentralUnitState:
        """Return the central state."""
        return self._state

    @property
    def supports_ping_pong(self) -> bool:
        """Return the backend supports ping pong."""
        if primary_client := self.primary_client:
            return primary_client.supports_ping_pong
        return False

    @property
    def system_information(self) -> SystemInformation:
        """Return the system_information of the backend."""
        if client := self.primary_client:
            return client.system_information
        return SystemInformation()

    @property
    def sysvar_data_points(self) -> tuple[GenericSysvarDataPoint, ...]:
        """Return the sysvar data points."""
        return self._hub_coordinator.sysvar_data_points

    @info_property(log_context=True)
    def model(self) -> str | None:
        """Return the model of the backend."""
        if not self._model and (client := self.primary_client):
            self._model = client.model
        return self._model

    @info_property(log_context=True)
    def name(self) -> str:
        """Return the name of the backend."""
        return self._config.name

    @info_property(log_context=True)
    def url(self) -> str:
        """Return the central url."""
        return self._url

    @info_property
    def version(self) -> str | None:
        """Return the version of the backend."""
        if self._version is None:
            versions = [client.version for client in self.clients if client.version]
            self._version = max(versions) if versions else None
        return self._version

    def add_event_subscription(self, *, data_point: BaseParameterDataPointAny) -> None:
        """Add data_point to central event subscription."""
        self._event_coordinator.add_data_point_subscription(data_point=data_point)

    async def add_new_device_manually(self, *, interface_id: str, address: str) -> None:
        """Add new devices manually triggered to central unit."""
        await self._device_coordinator.add_new_device_manually(interface_id=interface_id, address=address)

    @callback_backend_system(system_event=BackendSystemEvent.NEW_DEVICES)
    async def add_new_devices(self, *, interface_id: str, device_descriptions: tuple[DeviceDescription, ...]) -> None:
        """Add new devices to central unit."""
        await self._device_coordinator.add_new_devices(
            interface_id=interface_id, device_descriptions=device_descriptions
        )

    def add_program_data_point(self, *, program_dp: ProgramDpType) -> None:
        """Add new program button."""
        self._hub_coordinator.add_program_data_point(program_dp=program_dp)

    def add_sysvar_data_point(self, *, sysvar_data_point: GenericSysvarDataPoint) -> None:
        """Add new sysvar data point."""
        self._hub_coordinator.add_sysvar_data_point(sysvar_data_point=sysvar_data_point)

    async def clear_files(self) -> None:
        """Remove all stored files and caches."""
        await self._cache_coordinator.clear_all()

    @inspector
    async def create_central_links(self) -> None:
        """Create a central links to support press events on all channels with click events."""
        await self._device_coordinator.create_central_links()

    @callback_event
    async def data_point_event(self, *, interface_id: str, channel_address: str, parameter: str, value: Any) -> None:
        """If a device emits some sort event, we will handle it here."""
        await self._event_coordinator.data_point_event(
            interface_id=interface_id,
            channel_address=channel_address,
            parameter=parameter,
            value=value,
        )

    async def delete_device(self, *, interface_id: str, device_address: str) -> None:
        """Delete device from central."""
        await self._device_coordinator.delete_device(interface_id=interface_id, device_address=device_address)

    @callback_backend_system(system_event=BackendSystemEvent.DELETE_DEVICES)
    async def delete_devices(self, *, interface_id: str, addresses: tuple[str, ...]) -> None:
        """Delete devices from central."""
        await self._device_coordinator.delete_devices(interface_id=interface_id, addresses=addresses)

    @loop_check
    def emit_backend_parameter_callback(
        self, *, interface_id: str, channel_address: str, parameter: str, value: Any
    ) -> None:
        """
        Emit backend_parameter callback in central.

        Re-emitted events from the backend for parameter updates.
        """
        self._event_coordinator.emit_backend_parameter_callback(
            interface_id=interface_id,
            channel_address=channel_address,
            parameter=parameter,
            value=value,
        )

    @loop_check
    def emit_backend_system_callback(self, *, system_event: BackendSystemEvent, **kwargs: Any) -> None:
        """
        Emit system_event callback in central.

        e.g. DEVICES_CREATED, HUB_REFRESHED
        """
        self._event_coordinator.emit_backend_system_callback(system_event=system_event, **kwargs)

    @loop_check
    def emit_homematic_callback(self, *, event_type: EventType, event_data: dict[EventKey, Any]) -> None:
        """
        Emit homematic_callback in central.

        # Events like INTERFACE, KEYPRESS, ...
        """
        self._event_coordinator.emit_homematic_callback(event_type=event_type, event_data=event_data)

    @loop_check
    def emit_interface_event(
        self,
        *,
        interface_id: str,
        interface_event_type: InterfaceEventType,
        data: dict[str, Any],
    ) -> None:
        """Emit an event about the interface status."""
        self._event_coordinator.emit_interface_event(
            interface_id=interface_id,
            interface_event_type=interface_event_type,
            data=data,
        )

    async def execute_program(self, *, pid: str) -> bool:
        """Execute a program on the backend."""
        return await self._hub_coordinator.execute_program(pid=pid)

    @inspector(re_raise=False)
    async def fetch_program_data(self, *, scheduled: bool) -> None:
        """Fetch program data for the hub."""
        await self._hub_coordinator.fetch_program_data(scheduled=scheduled)

    @inspector(re_raise=False)
    async def fetch_sysvar_data(self, *, scheduled: bool) -> None:
        """Fetch sysvar data for the hub."""
        await self._hub_coordinator.fetch_sysvar_data(scheduled=scheduled)

    def get_channel(self, *, channel_address: str) -> Channel | None:
        """Return Homematic channel."""
        return self._device_coordinator.get_channel(channel_address=channel_address)

    def get_client(self, *, interface_id: str) -> hmcl.Client:
        """Return a client by interface_id."""
        return self._client_coordinator.get_client(interface_id=interface_id)

    def get_custom_data_point(self, *, address: str, channel_no: int) -> CustomDataPoint | None:
        """Return the hm custom_data_point."""
        if device := self.get_device(address=address):
            return device.get_custom_data_point(channel_no=channel_no)
        return None

    def get_data_point_by_custom_id(self, *, custom_id: str) -> CallbackDataPoint | None:
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
    ) -> tuple[CallbackDataPoint, ...]:
        """Return all externally registered data points."""
        all_data_points: list[CallbackDataPoint] = []
        for device in self._device_registry.devices:
            if interface and interface != device.interface:
                continue
            all_data_points.extend(
                device.get_data_points(category=category, exclude_no_create=exclude_no_create, registered=registered)
            )
        return tuple(all_data_points)

    def get_device(self, *, address: str) -> Device | None:
        """Return Homematic device."""
        return self._device_coordinator.get_device(address=address)

    def get_event(self, *, channel_address: str, parameter: str) -> GenericEvent | None:
        """Return the hm event."""
        if device := self.get_device(address=channel_address):
            return device.get_generic_event(channel_address=channel_address, parameter=parameter)
        return None

    def get_events(
        self, *, event_type: EventType, registered: bool | None = None
    ) -> tuple[tuple[GenericEvent, ...], ...]:
        """Return all channel event data points."""
        hm_channel_events: list[tuple[GenericEvent, ...]] = []
        for device in self.devices:
            for channel_events in device.get_events(event_type=event_type).values():
                if registered is None or (channel_events[0].is_registered == registered):
                    hm_channel_events.append(channel_events)
                    continue
        return tuple(hm_channel_events)

    def get_generic_data_point(
        self, *, channel_address: str, parameter: str, paramset_key: ParamsetKey | None = None
    ) -> GenericDataPointAny | None:
        """Get data_point by channel_address and parameter."""
        if device := self.get_device(address=channel_address):
            return device.get_generic_data_point(
                channel_address=channel_address, parameter=parameter, paramset_key=paramset_key
            )
        return None

    def get_hub_data_points(
        self, *, category: DataPointCategory | None = None, registered: bool | None = None
    ) -> tuple[GenericHubDataPoint, ...]:
        """Return the program data points."""
        return self._hub_coordinator.get_hub_data_points(category=category, registered=registered)

    def get_last_event_seen_for_interface(self, *, interface_id: str) -> datetime | None:
        """Return the last event seen for an interface."""
        return self._event_coordinator.get_last_event_seen_for_interface(interface_id=interface_id)

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

        raw_psd = self.paramset_descriptions.raw_paramset_descriptions
        ignore_set = IGNORE_FOR_UN_IGNORE_PARAMETERS

        # Prepare optional helpers only if needed
        get_model = self.device_descriptions.get_model if full_format else None
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

    def get_program_data_point(self, *, pid: str | None = None, legacy_name: str | None = None) -> ProgramDpType | None:
        """Return the program data points."""
        return self._hub_coordinator.get_program_data_point(pid=pid, legacy_name=legacy_name)

    def get_readable_generic_data_points(
        self, *, paramset_key: ParamsetKey | None = None, interface: Interface | None = None
    ) -> tuple[GenericDataPointAny, ...]:
        """Return the readable generic data points."""
        return tuple(
            ge
            for ge in self.get_data_points(interface=interface)
            if (
                isinstance(ge, GenericDataPoint)
                and ge.is_readable
                and ((paramset_key and ge.paramset_key == paramset_key) or paramset_key is None)
            )
        )

    async def get_system_variable(self, *, legacy_name: str) -> Any | None:
        """Get system variable from the backend."""
        return await self._hub_coordinator.get_system_variable(legacy_name=legacy_name)

    def get_sysvar_data_point(
        self, *, vid: str | None = None, legacy_name: str | None = None
    ) -> GenericSysvarDataPoint | None:
        """Return the sysvar data_point."""
        return self._hub_coordinator.get_sysvar_data_point(vid=vid, legacy_name=legacy_name)

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

    def get_virtual_remotes(self) -> tuple[Device, ...]:
        """Get the virtual remotes for all clients."""
        return self._device_coordinator.get_virtual_remotes()

    def has_client(self, *, interface_id: str) -> bool:
        """Check if client exists in central."""
        return self._client_coordinator.has_client(interface_id=interface_id)

    def identify_channel(self, *, text: str) -> Channel | None:
        """Identify channel within a text."""
        return self._device_coordinator.identify_channel(text=text)

    @callback_backend_system(system_event=BackendSystemEvent.LIST_DEVICES)
    def list_devices(self, *, interface_id: str) -> list[DeviceDescription]:
        """Return already existing devices to the backend."""
        return self._device_coordinator.list_devices(interface_id=interface_id)

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
            await self.data_cache.load(interface=interface)
        await self.data_cache.refresh_data_point_data(
            paramset_key=paramset_key, interface=interface, direct_call=direct_call
        )

    @inspector(re_raise=False)
    async def refresh_firmware_data(self, *, device_address: str | None = None) -> None:
        """Refresh device firmware data."""
        await self._device_coordinator.refresh_firmware_data(device_address=device_address)

    @inspector(re_raise=False)
    async def refresh_firmware_data_by_state(self, *, device_firmware_states: tuple[DeviceFirmwareState, ...]) -> None:
        """Refresh device firmware data for processing devices."""
        for device in [
            device_in_state
            for device_in_state in self.devices
            if device_in_state.firmware_update_state in device_firmware_states
        ]:
            await self.refresh_firmware_data(device_address=device.address)

    @inspector
    async def remove_central_links(self) -> None:
        """Remove central links."""
        await self._device_coordinator.remove_central_links()

    def remove_device(self, *, device: Device) -> None:
        """Remove device from central collections."""
        self._device_coordinator.remove_device(device=device)

    def remove_event_subscription(self, *, data_point: BaseParameterDataPointAny) -> None:
        """Remove event subscription from central collections."""
        # EventBus subscriptions are automatically cleaned up when data points are deleted

    def remove_program_button(self, *, pid: str) -> None:
        """Remove a program button."""
        self._hub_coordinator.remove_program_data_point(pid=pid)

    def remove_sysvar_data_point(self, *, vid: str) -> None:
        """Remove a sysvar data_point."""
        self._hub_coordinator.remove_sysvar_data_point(vid=vid)

    async def restart_clients(self) -> None:
        """Restart clients."""
        await self._client_coordinator.restart_clients()

    async def save_files(
        self,
        *,
        save_device_descriptions: bool = False,
        save_paramset_descriptions: bool = False,
    ) -> None:
        """Save persistent files to disk."""
        await self._cache_coordinator.save_all(
            save_device_descriptions=save_device_descriptions,
            save_paramset_descriptions=save_paramset_descriptions,
        )

    def set_last_event_seen_for_interface(self, *, interface_id: str) -> None:
        """Set the last event seen for an interface."""
        self._event_coordinator.set_last_event_seen_for_interface(interface_id=interface_id)

    async def set_program_state(self, *, pid: str, state: bool) -> bool:
        """Execute a program on the backend."""
        return await self._hub_coordinator.set_program_state(pid=pid, state=state)

    async def set_system_variable(self, *, legacy_name: str, value: Any) -> None:
        """Set variable value on the backend."""
        await self._hub_coordinator.set_system_variable(legacy_name=legacy_name, value=value)

    async def start(self) -> None:
        """Start processing of the central unit."""

        _LOGGER.debug("START: Central %s is %s", self.name, self._state)
        if self._state == CentralUnitState.INITIALIZING:
            _LOGGER.debug("START: Central %s already starting", self.name)
            return

        if self._state == CentralUnitState.RUNNING:
            _LOGGER.debug("START: Central %s already started", self.name)
            return

        if self._config.session_recorder_start:
            await self.recorder.deactivate(
                delay=self._config.session_recorder_start_for_seconds,
                auto_save=True,
                randomize_output=self._config.session_recorder_randomize_output,
                use_ts_in_file_name=False,
            )
            _LOGGER.debug("START: Starting Recorder for %s seconds", self._config.session_recorder_start_for_seconds)

        self._state = CentralUnitState.INITIALIZING
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
                self._xml_rpc_server.add_central(central=self)
        except OSError as oserr:  # pragma: no cover - environment/OS-specific socket binding failures are not reliably reproducible in CI
            self._state = CentralUnitState.STOPPED_BY_ERROR
            raise AioHomematicException(
                i18n.tr(
                    "exception.central.start.failed",
                    name=self.name,
                    reason=extract_exc_args(exc=oserr),
                )
            ) from oserr

        if self._config.start_direct:
            if await self._client_coordinator.start_clients():
                for client in self.clients:
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

        self._state = CentralUnitState.RUNNING
        _LOGGER.debug("START: Central %s is %s", self.name, self._state)

    async def stop(self) -> None:
        """Stop processing of the central unit."""
        _LOGGER.debug("STOP: Central %s is %s", self.name, self._state)
        if self._state == CentralUnitState.STOPPING:
            _LOGGER.debug("STOP: Central %s is already stopping", self.name)
            return
        if self._state == CentralUnitState.STOPPED:
            _LOGGER.debug("STOP: Central %s is already stopped", self.name)
            return
        if self._state != CentralUnitState.RUNNING:
            _LOGGER.debug("STOP: Central %s not started", self.name)
            return
        self._state = CentralUnitState.STOPPING
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
        self._state = CentralUnitState.STOPPED
        _LOGGER.debug("STOP: Central %s is %s", self.name, self._state)

    async def validate_config_and_get_system_information(self) -> SystemInformation:
        """Validate the central configuration."""
        if len(self._config.enabled_interface_configs) == 0:
            raise NoClientsException(i18n.tr("exception.central.validate_config.no_clients"))

        system_information = SystemInformation()
        for interface_config in self._config.enabled_interface_configs:
            try:
                client = await hmcl.create_client(central=self, interface_config=interface_config)
            except BaseHomematicException as bhexc:
                _LOGGER.error(
                    i18n.tr(
                        "log.central.validate_config_and_get_system_information.client_failed",
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
                    get_ip_addr, self._config.host, port, name="get_ip_addr"
                )
            except AioHomematicException:
                ip_addr = LOCAL_HOST
            if ip_addr is None:
                _LOGGER.warning(  # i18n-log: ignore
                    "GET_IP_ADDR: Waiting for %i s,", CONNECTION_CHECKER_INTERVAL
                )
                await asyncio.sleep(TIMEOUT / 10)
        return ip_addr

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
    """Config for a Client."""

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
        hm_master_poll_after_send_intervals: tuple[int, ...] = DEFAULT_HM_MASTER_POLL_AFTER_SEND_INTERVALS,
        ignore_custom_device_definition_models: frozenset[str] = DEFAULT_IGNORE_CUSTOM_DEVICE_DEFINITION_MODELS,
        interfaces_requiring_periodic_refresh: frozenset[Interface] = DEFAULT_INTERFACES_REQUIRING_PERIODIC_REFRESH,
        json_port: int | None = None,
        listen_ip_addr: str | None = None,
        listen_port_xml_rpc: int | None = None,
        max_read_workers: int = DEFAULT_MAX_READ_WORKERS,
        optional_settings: tuple[OptionalSettings | str, ...] = DEFAULT_OPTIONAL_SETTINGS,
        periodic_refresh_interval: int = DEFAULT_PERIODIC_REFRESH_INTERVAL,
        program_markers: tuple[DescriptionMarker | str, ...] = DEFAULT_PROGRAM_MARKERS,
        start_direct: bool = False,
        storage_directory: str = DEFAULT_STORAGE_DIRECTORY,
        sys_scan_interval: int = DEFAULT_SYS_SCAN_INTERVAL,
        sysvar_markers: tuple[DescriptionMarker | str, ...] = DEFAULT_SYSVAR_MARKERS,
        tls: bool = DEFAULT_TLS,
        un_ignore_list: frozenset[str] = DEFAULT_UN_IGNORES,
        use_group_channel_for_cover_state: bool = DEFAULT_USE_GROUP_CHANNEL_FOR_COVER_STATE,
        verify_tls: bool = DEFAULT_VERIFY_TLS,
        locale: str = DEFAULT_LOCALE,
    ) -> None:
        """Init the client config."""
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
        self.hm_master_poll_after_send_intervals: Final = hm_master_poll_after_send_intervals
        self.host: Final = host
        self.ignore_custom_device_definition_models: Final = frozenset(ignore_custom_device_definition_models or ())
        self.interfaces_requiring_periodic_refresh: Final = frozenset(interfaces_requiring_periodic_refresh or ())
        self.json_port: Final = json_port
        self.listen_ip_addr: Final = listen_ip_addr
        self.listen_port_xml_rpc: Final = listen_port_xml_rpc
        self.max_read_workers = max_read_workers
        self.name: Final = name
        self.password: Final = password
        self.periodic_refresh_interval = periodic_refresh_interval
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
        self.storage_directory: Final = storage_directory
        self.sys_scan_interval: Final = sys_scan_interval
        self.sysvar_markers: Final = sysvar_markers
        self.tls: Final = tls
        self.un_ignore_list: Final = un_ignore_list
        self.use_group_channel_for_cover_state: Final = use_group_channel_for_cover_state
        self.username: Final = username
        self.verify_tls: Final = verify_tls
        self.locale: Final = locale

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
    def optional_settings(self) -> frozenset[OptionalSettings | str]:
        """Return the optional settings."""
        return self._optional_settings

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
            msg = i18n.tr("exception.config.invalid", failures=failures)
            raise AioHomematicConfigException(msg)

    def create_central(self) -> CentralUnit:
        """Create the central. Throws BaseHomematicException on validation failure."""
        try:
            self.check_config()
            return CentralUnit(central_config=self)
        except BaseHomematicException as bhexc:  # pragma: no cover
            raise AioHomematicException(
                i18n.tr(
                    "exception.create_central.failed",
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

    def create_json_rpc_client(self, *, central: CentralUnit) -> AioJsonRpcAioHttpClient:
        """Create a json rpc client."""
        return AioJsonRpcAioHttpClient(
            username=self.username,
            password=self.password,
            device_url=central.url,
            connection_state=central.connection_state,
            client_session=self.client_session,
            tls=self.tls,
            verify_tls=self.verify_tls,
            session_recorder=central.recorder,
        )


class CentralConnectionState:
    """The central connection status."""

    def __init__(self) -> None:
        """Init the CentralConnectionStatus."""
        self._json_issues: Final[list[str]] = []
        self._rpc_proxy_issues: Final[list[str]] = []

    def add_issue(self, *, issuer: ConnectionProblemIssuer, iid: str) -> bool:
        """Add issue to collection."""
        if isinstance(issuer, AioJsonRpcAioHttpClient) and iid not in self._json_issues:
            self._json_issues.append(iid)
            _LOGGER.debug("add_issue: add issue  [%s] for JsonRpcAioHttpClient", iid)
            return True
        if isinstance(issuer, BaseRpcProxy) and iid not in self._rpc_proxy_issues:
            self._rpc_proxy_issues.append(iid)
            _LOGGER.debug("add_issue: add issue [%s] for RpcProxy", iid)
            return True
        return False

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
        """Add issue to collection."""
        if isinstance(issuer, AioJsonRpcAioHttpClient):
            return iid in self._json_issues
        if isinstance(issuer, BaseRpcProxy):
            return iid in self._rpc_proxy_issues

    def remove_issue(self, *, issuer: ConnectionProblemIssuer, iid: str) -> bool:
        """Add issue to collection."""
        if isinstance(issuer, AioJsonRpcAioHttpClient) and iid in self._json_issues:
            self._json_issues.remove(iid)
            _LOGGER.debug("remove_issue: removing issue [%s] for JsonRpcAioHttpClient", iid)
            return True
        if isinstance(issuer, BaseRpcProxy) and iid in self._rpc_proxy_issues:
            self._rpc_proxy_issues.remove(iid)
            _LOGGER.debug("remove_issue: removing issue [%s] for RpcProxy", iid)
            return True
        return False


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
        config_failures.append(i18n.tr("exception.config.check.instance_name.separator", sep=IDENTIFIER_SEPARATOR))

    if not (is_hostname(hostname=host) or is_ipv4_address(address=host)):
        config_failures.append(i18n.tr("exception.config.check.host.invalid"))
    if not username:
        config_failures.append(i18n.tr("exception.config.check.username.empty"))
    if not password:
        config_failures.append(i18n.tr("exception.config.check.password.required"))
    if not check_password(password=password):
        config_failures.append(i18n.tr("exception.config.check.password.invalid"))
    try:
        check_or_create_directory(directory=storage_directory)
    except BaseHomematicException as bhexc:
        config_failures.append(extract_exc_args(exc=bhexc)[0])
    if callback_host and not (is_hostname(hostname=callback_host) or is_ipv4_address(address=callback_host)):
        config_failures.append(i18n.tr("exception.config.check.callback_host.invalid"))
    if callback_port_xml_rpc and not is_port(port=callback_port_xml_rpc):
        config_failures.append(i18n.tr("exception.config.check.callback_port_xml_rpc.invalid"))
    if json_port and not is_port(port=json_port):
        config_failures.append(i18n.tr("exception.config.check.json_port.invalid"))
    if interface_configs and not _has_primary_client(interface_configs=interface_configs):
        config_failures.append(
            i18n.tr(
                "exception.config.check.primary_interface.missing",
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
    new_devices: set[Device],
) -> Mapping[DataPointCategory, AbstractSet[CallbackDataPoint]]:
    """Return new data points by category."""

    data_points_by_category: dict[DataPointCategory, set[CallbackDataPoint]] = {
        category: set() for category in CATEGORIES if category != DataPointCategory.EVENT
    }

    for device in new_devices:
        for category, data_points in data_points_by_category.items():
            data_points.update(device.get_data_points(category=category, exclude_no_create=True, registered=False))

    return data_points_by_category


def _get_new_channel_events(*, new_devices: set[Device]) -> tuple[tuple[GenericEvent, ...], ...]:
    """Return new channel events by category."""
    channel_events: list[tuple[GenericEvent, ...]] = []

    for device in new_devices:
        for event_type in DATA_POINT_EVENTS:
            if (hm_channel_events := list(device.get_events(event_type=event_type, registered=False).values())) and len(
                hm_channel_events
            ) > 0:
                channel_events.append(hm_channel_events)  # type: ignore[arg-type] # noqa:PERF401

    return tuple(channel_events)
