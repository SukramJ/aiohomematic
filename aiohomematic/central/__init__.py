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
- _Scheduler: Background thread that periodically checks connection health,
  refreshes data, and fetches firmware status according to configured intervals.

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
from datetime import datetime, timedelta
from functools import partial
import logging
from logging import DEBUG
import threading
from typing import Any, Final, cast

from aiohttp import ClientSession
import voluptuous as vol

from aiohomematic import client as hmcl, i18n
from aiohomematic.async_support import Looper, loop_check
from aiohomematic.central import rpc_server as rpc
from aiohomematic.central.decorators import callback_backend_system, callback_event
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
    DEVICE_FIRMWARE_CHECK_INTERVAL,
    DEVICE_FIRMWARE_DELIVERING_CHECK_INTERVAL,
    DEVICE_FIRMWARE_UPDATING_CHECK_INTERVAL,
    IDENTIFIER_SEPARATOR,
    IGNORE_FOR_UN_IGNORE_PARAMETERS,
    IP_ANY_V4,
    LOCAL_HOST,
    PORT_ANY,
    PRIMARY_CLIENT_CANDIDATE_INTERFACES,
    SCHEDULER_LOOP_SLEEP,
    SCHEDULER_NOT_STARTED_SLEEP,
    TIMEOUT,
    UN_IGNORE_WILDCARD,
    BackendSystemEvent,
    CentralUnitState,
    DataOperationResult,
    DataPointCategory,
    DataPointKey,
    DescriptionMarker,
    DeviceDescription,
    DeviceFirmwareState,
    EventKey,
    EventType,
    Interface,
    InterfaceEventType,
    Operations,
    OptionalSettings,
    Parameter,
    ParamsetKey,
    ProxyInitState,
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
    NoConnectionException,
)
from aiohomematic.model import create_data_points_and_events
from aiohomematic.model.custom import CustomDataPoint, create_custom_data_points
from aiohomematic.model.data_point import BaseParameterDataPointAny, CallbackDataPoint
from aiohomematic.model.device import Channel, Device
from aiohomematic.model.event import GenericEvent
from aiohomematic.model.generic import GenericDataPoint, GenericDataPointAny
from aiohomematic.model.hub import (
    GenericHubDataPoint,
    GenericProgramDataPoint,
    GenericSysvarDataPoint,
    Hub,
    ProgramDpType,
)
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
    extract_device_addresses_from_device_descriptions,
    extract_exc_args,
    get_channel_no,
    get_device_address,
    get_ip_addr,
    is_hostname,
    is_ipv4_address,
    is_port,
)
from aiohomematic.type_aliases import (
    AsyncTaskFactory,
    BackendParameterCallback,
    BackendSystemCallback,
    DataPointEventCallback,
    HomematicCallback,
    SysvarEventCallback,
    UnregisterCallback,
)

__all__ = ["CentralConfig", "CentralUnit", "INTERFACE_EVENT_SCHEMA"]

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
        self._clients_started: bool = False
        self._device_add_semaphore: Final = asyncio.Semaphore()
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

        # Caches for the backend data
        self._data_cache: Final = CentralDataCache(central=self)
        self._device_details: Final = DeviceDetailsCache(central=self)
        self._device_descriptions: Final = DeviceDescriptionCache(central=self)
        self._paramset_descriptions: Final = ParamsetDescriptionCache(central=self)
        self._parameter_visibility: Final = ParameterVisibilityCache(central=self)
        self._recorder: Final = SessionRecorder(
            central=self, ttl_seconds=600, active=central_config.session_recorder_start
        )
        self._primary_client: hmcl.Client | None = None
        # {interface_id, client}
        self._clients: Final[dict[str, hmcl.Client]] = {}
        self._data_point_key_event_subscriptions: Final[dict[DataPointKey, list[DataPointEventCallback]]] = {}
        self._data_point_path_event_subscriptions: Final[dict[str, DataPointKey]] = {}
        self._sysvar_data_point_event_subscriptions: Final[dict[str, SysvarEventCallback]] = {}
        # {device_address, device}
        self._devices: Final[dict[str, Device]] = {}
        # {sysvar_name, sysvar_data_point}
        self._sysvar_data_points: Final[dict[str, GenericSysvarDataPoint]] = {}
        # {sysvar_name, program_button}
        self._program_data_points: Final[dict[str, ProgramDpType]] = {}
        # Signature: (system_event, new_data_points, new_channel_events, **kwargs)
        # e.g. DEVICES_CREATED, HUB_REFRESHED
        self._backend_system_callbacks: Final[set[BackendSystemCallback]] = set()
        # Signature: (interface_id, channel_address, parameter, value)
        # Re-emitted events from the backend for parameter updates
        self._backend_parameter_callbacks: Final[set[BackendParameterCallback]] = set()
        # Signature: (event_type, event_data)
        # Events like INTERFACE, KEYPRESS, ...
        self._homematic_callbacks: Final[set[HomematicCallback]] = set()

        CENTRAL_INSTANCES[self.name] = self
        self._scheduler: Final = _Scheduler(central=self)
        self._hub: Hub = Hub(central=self)
        self._version: str | None = None
        # store last event received datetime by interface_id
        self._last_event_seen_for_interface: Final[dict[str, datetime]] = {}
        self._rpc_callback_ip: str = IP_ANY_V4
        self._listen_ip_addr: str = IP_ANY_V4
        self._listen_port_xml_rpc: int = PORT_ANY

    def __str__(self) -> str:
        """Provide some useful information."""
        return f"central: {self.name}"

    @property
    def _has_active_threads(self) -> bool:
        """Return if active sub threads are alive."""
        if self._scheduler.is_alive():
            return True
        return bool(
            self._xml_rpc_server and self._xml_rpc_server.no_central_assigned and self._xml_rpc_server.is_alive()
        )

    @property
    def all_clients_active(self) -> bool:
        """Check if all configured clients exists in central."""
        count_client = len(self._clients)
        return count_client > 0 and count_client == len(self._config.enabled_interface_configs)

    @property
    def available(self) -> bool:
        """Return the availability of the central."""
        return all(client.available for client in self._clients.values())

    @property
    def callback_ip_addr(self) -> str:
        """Return the xml rpc server callback ip address."""
        return self._rpc_callback_ip

    @property
    def clients(self) -> tuple[hmcl.Client, ...]:
        """Return all clients."""
        return tuple(self._clients.values())

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
        return self._data_cache

    @property
    def device_descriptions(self) -> DeviceDescriptionCache:
        """Return device_descriptions cache."""
        return self._device_descriptions

    @property
    def device_details(self) -> DeviceDetailsCache:
        """Return device_details cache."""
        return self._device_details

    @property
    def devices(self) -> tuple[Device, ...]:
        """Return all devices."""
        return tuple(self._devices.values())

    @property
    def has_clients(self) -> bool:
        """Check if clients exists in central."""
        return len(self._clients) > 0

    @property
    def interface_ids(self) -> frozenset[str]:
        """Return all associated interface ids."""
        return frozenset(self._clients)

    @property
    def interfaces(self) -> frozenset[Interface]:
        """Return all associated interfaces."""
        return frozenset(client.interface for client in self._clients.values())

    @property
    def is_alive(self) -> bool:
        """Return if XmlRPC-Server is alive."""
        return all(client.is_callback_alive() for client in self._clients.values())

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
        return self._parameter_visibility

    @property
    def paramset_descriptions(self) -> ParamsetDescriptionCache:
        """Return paramset_descriptions cache."""
        return self._paramset_descriptions

    @property
    def poll_clients(self) -> tuple[hmcl.Client, ...]:
        """Return clients that need to poll data."""
        return tuple(client for client in self._clients.values() if not client.supports_push_updates)

    @property
    def primary_client(self) -> hmcl.Client | None:
        """Return the primary client of the backend."""
        if self._primary_client is not None:
            return self._primary_client
        if client := self._get_primary_client():
            self._primary_client = client
        return self._primary_client

    @property
    def program_data_points(self) -> tuple[GenericProgramDataPoint, ...]:
        """Return the program data points."""
        return tuple(
            [x.button for x in self._program_data_points.values()]
            + [x.switch for x in self._program_data_points.values()]
        )

    @property
    def recorder(self) -> SessionRecorder:
        """Return the session recorder."""
        return self._recorder

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
        return tuple(self._sysvar_data_points.values())

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
            versions = [client.version for client in self._clients.values() if client.version]
            self._version = max(versions) if versions else None
        return self._version

    def add_event_subscription(self, *, data_point: BaseParameterDataPointAny) -> None:
        """Add data_point to central event subscription."""
        if isinstance(data_point, GenericDataPoint | GenericEvent) and (
            data_point.is_readable or data_point.supports_events
        ):
            if data_point.dpk not in self._data_point_key_event_subscriptions:
                self._data_point_key_event_subscriptions[data_point.dpk] = []
            self._data_point_key_event_subscriptions[data_point.dpk].append(data_point.event)
            if (
                not data_point.channel.device.client.supports_rpc_callback
                and data_point.state_path not in self._data_point_path_event_subscriptions
            ):
                self._data_point_path_event_subscriptions[data_point.state_path] = data_point.dpk

    async def add_new_device_manually(self, *, interface_id: str, address: str) -> None:
        """Add new devices manually triggered to central unit."""
        if interface_id not in self._clients:
            _LOGGER.error(  # i18n-log: ignore
                "ADD_NEW_DEVICES_MANUALLY failed: Missing client for interface_id %s",
                interface_id,
            )
            return
        client = self._clients[interface_id]
        if not (device_descriptions := await client.get_all_device_descriptions(device_address=address)):
            _LOGGER.error(  # i18n-log: ignore
                "ADD_NEW_DEVICES_MANUALLY failed: No device description found for address %s on interface_id %s",
                address,
                interface_id,
            )
            return

        await self._add_new_devices(
            interface_id=interface_id,
            device_descriptions=device_descriptions,
            source=SourceOfDeviceCreation.MANUAL,
        )

    @callback_backend_system(system_event=BackendSystemEvent.NEW_DEVICES)
    async def add_new_devices(self, *, interface_id: str, device_descriptions: tuple[DeviceDescription, ...]) -> None:
        """Add new devices to central unit."""
        source = (
            SourceOfDeviceCreation.NEW
            if self._device_descriptions.has_device_descriptions(interface_id=interface_id)
            else SourceOfDeviceCreation.INIT
        )
        await self._add_new_devices(interface_id=interface_id, device_descriptions=device_descriptions, source=source)

    def add_program_data_point(self, *, program_dp: ProgramDpType) -> None:
        """Add new program button."""
        self._program_data_points[program_dp.pid] = program_dp

    def add_sysvar_data_point(self, *, sysvar_data_point: GenericSysvarDataPoint) -> None:
        """Add new program button."""
        if (vid := sysvar_data_point.vid) is not None:
            self._sysvar_data_points[vid] = sysvar_data_point
        if sysvar_data_point.state_path not in self._sysvar_data_point_event_subscriptions:
            self._sysvar_data_point_event_subscriptions[sysvar_data_point.state_path] = sysvar_data_point.event

    async def clear_files(self) -> None:
        """Remove all stored files and caches."""
        await self._device_descriptions.clear()
        await self._paramset_descriptions.clear()
        await self._recorder.clear()
        self._device_details.clear()
        self._data_cache.clear()

    @inspector
    async def create_central_links(self) -> None:
        """Create a central links to support press events on all channels with click events."""
        for device in self.devices:
            await device.create_central_links()

    @callback_event
    async def data_point_event(self, *, interface_id: str, channel_address: str, parameter: str, value: Any) -> None:
        """If a device emits some sort event, we will handle it here."""
        _LOGGER_EVENT.debug(
            "EVENT: interface_id = %s, channel_address = %s, parameter = %s, value = %s",
            interface_id,
            channel_address,
            parameter,
            str(value),
        )
        if not self.has_client(interface_id=interface_id):
            return

        self.set_last_event_seen_for_interface(interface_id=interface_id)
        # No need to check the response of a XmlRPC-PING
        if parameter == Parameter.PONG:
            if "#" in value:
                v_interface_id, token = value.split("#")
                if (
                    v_interface_id == interface_id
                    and (client := self.get_client(interface_id=interface_id))
                    and client.supports_ping_pong
                ):
                    client.ping_pong_cache.handle_received_pong(pong_token=token)
            return

        dpk = DataPointKey(
            interface_id=interface_id,
            channel_address=channel_address,
            paramset_key=ParamsetKey.VALUES,
            parameter=parameter,
        )

        if dpk in self._data_point_key_event_subscriptions:
            try:
                received_at = datetime.now()
                for callback_handler in self._data_point_key_event_subscriptions[dpk]:
                    if callable(callback_handler):
                        await callback_handler(value=value, received_at=received_at)
            except RuntimeError as rterr:
                _LOGGER_EVENT.debug(
                    "EVENT: RuntimeError [%s]. Failed to call handler for: %s, %s, %s",
                    extract_exc_args(exc=rterr),
                    interface_id,
                    channel_address,
                    parameter,
                )
            except Exception as exc:
                _LOGGER_EVENT.error(  # i18n-log: ignore
                    "EVENT failed: Unable to call handler for: %s, %s, %s, %s",
                    interface_id,
                    channel_address,
                    parameter,
                    extract_exc_args(exc=exc),
                )

    def data_point_path_event(self, *, state_path: str, value: str) -> None:
        """If a device emits some sort event, we will handle it here."""
        _LOGGER_EVENT.debug(
            "DATA_POINT_PATH_EVENT: topic = %s, payload = %s",
            state_path,
            value,
        )

        if (dpk := self._data_point_path_event_subscriptions.get(state_path)) is not None:
            self._looper.create_task(
                target=cast(
                    AsyncTaskFactory,
                    lambda: self.data_point_event(
                        interface_id=dpk.interface_id,
                        channel_address=dpk.channel_address,
                        parameter=dpk.parameter,
                        value=value,
                    ),
                ),
                name=f"device-data-point-event-{dpk.interface_id}-{dpk.channel_address}-{dpk.parameter}",
            )

    async def delete_device(self, *, interface_id: str, device_address: str) -> None:
        """Delete devices from central."""
        _LOGGER.debug(
            "DELETE_DEVICE: interface_id = %s, device_address = %s",
            interface_id,
            device_address,
        )

        if (device := self._devices.get(device_address)) is None:
            return

        await self.delete_devices(interface_id=interface_id, addresses=[device_address, *list(device.channels.keys())])

    @callback_backend_system(system_event=BackendSystemEvent.DELETE_DEVICES)
    async def delete_devices(self, *, interface_id: str, addresses: tuple[str, ...]) -> None:
        """Delete devices from central."""
        _LOGGER.debug(
            "DELETE_DEVICES: interface_id = %s, addresses = %s",
            interface_id,
            str(addresses),
        )
        for address in addresses:
            if device := self._devices.get(address):
                self.remove_device(device=device)
        await self.save_files(save_device_descriptions=True, save_paramset_descriptions=True)

    @loop_check
    def emit_backend_parameter_callback(
        self, *, interface_id: str, channel_address: str, parameter: str, value: Any
    ) -> None:
        """
        Emit backend_parameter callback in central.

        Re-emitted events from the backend for parameter updates.
        """
        for callback_handler in self._backend_parameter_callbacks:
            try:
                callback_handler(
                    interface_id=interface_id, channel_address=channel_address, parameter=parameter, value=value
                )
            except Exception as exc:
                _LOGGER.error(  # i18n-log: ignore
                    "EMIT_BACKEND_PARAMETER_CALLBACK: Unable to call handler: %s",
                    extract_exc_args(exc=exc),
                )

    @loop_check
    def emit_backend_system_callback(self, *, system_event: BackendSystemEvent, **kwargs: Any) -> None:
        """
        Emit system_event callback in central.

        e.g. DEVICES_CREATED, HUB_REFRESHED
        """
        for callback_handler in self._backend_system_callbacks:
            try:
                callback_handler(system_event=system_event, **kwargs)
            except Exception as exc:
                _LOGGER.error(  # i18n-log: ignore
                    "EMIT_BACKEND_SYSTEM_CALLBACK: Unable to call handler: %s",
                    extract_exc_args(exc=exc),
                )

    @loop_check
    def emit_homematic_callback(self, *, event_type: EventType, event_data: dict[EventKey, Any]) -> None:
        """
        Emit homematic_callback in central.

        # Events like INTERFACE, KEYPRESS, ...
        """

        for callback_handler in self._homematic_callbacks:
            try:
                # Call with keyword arguments as expected by tests and integrations
                callback_handler(event_type=event_type, event_data=event_data)
            except Exception as exc:
                _LOGGER.error(  # i18n-log: ignore
                    "EMIT_HOMEMATIC_CALLBACK: Unable to call handler: %s",
                    extract_exc_args(exc=exc),
                )

    @loop_check
    def emit_interface_event(
        self,
        *,
        interface_id: str,
        interface_event_type: InterfaceEventType,
        data: dict[str, Any],
    ) -> None:
        """Emit an event about the interface status."""
        data = data or {}
        event_data: dict[str, Any] = {
            EventKey.INTERFACE_ID: interface_id,
            EventKey.TYPE: interface_event_type,
            EventKey.DATA: data,
        }

        self.emit_homematic_callback(
            event_type=EventType.INTERFACE,
            event_data=cast(dict[EventKey, Any], INTERFACE_EVENT_SCHEMA(event_data)),
        )

    async def execute_program(self, *, pid: str) -> bool:
        """Execute a program on the backend."""
        if client := self.primary_client:
            return await client.execute_program(pid=pid)
        return False

    @inspector(re_raise=False)
    async def fetch_program_data(self, *, scheduled: bool) -> None:
        """Fetch program data for the hub."""
        await self._hub.fetch_program_data(scheduled=scheduled)

    @inspector(re_raise=False)
    async def fetch_sysvar_data(self, *, scheduled: bool) -> None:
        """Fetch sysvar data for the hub."""
        await self._hub.fetch_sysvar_data(scheduled=scheduled)

    def get_channel(self, *, channel_address: str) -> Channel | None:
        """Return Homematic channel."""
        if device := self.get_device(address=channel_address):
            return device.get_channel(channel_address=channel_address)
        return None

    def get_client(self, *, interface_id: str) -> hmcl.Client:
        """Return a client by interface_id."""
        if not self.has_client(interface_id=interface_id):
            raise AioHomematicException(
                i18n.tr(
                    "exception.central.get_client.interface_missing",
                    interface_id=interface_id,
                    name=self.name,
                )
            )
        return self._clients[interface_id]

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

    def get_data_point_path(self) -> tuple[str, ...]:
        """Return the registered state path."""
        return tuple(self._data_point_path_event_subscriptions)

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
        for device in self._devices.values():
            if interface and interface != device.interface:
                continue
            all_data_points.extend(
                device.get_data_points(category=category, exclude_no_create=exclude_no_create, registered=registered)
            )
        return tuple(all_data_points)

    def get_device(self, *, address: str) -> Device | None:
        """Return Homematic device."""
        d_address = get_device_address(address=address)
        return self._devices.get(d_address)

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
        return tuple(
            he
            for he in (self.program_data_points + self.sysvar_data_points)
            if (category is None or he.category == category) and (registered is None or he.is_registered == registered)
        )

    def get_last_event_seen_for_interface(self, *, interface_id: str) -> datetime | None:
        """Return the last event seen for an interface."""
        return self._last_event_seen_for_interface.get(interface_id)

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

        raw_psd = self._paramset_descriptions.raw_paramset_descriptions
        ignore_set = IGNORE_FOR_UN_IGNORE_PARAMETERS

        # Prepare optional helpers only if needed
        get_model = self._device_descriptions.get_model if full_format else None
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
        if pid and (program := self._program_data_points.get(pid)):
            return program
        if legacy_name:
            for program in self._program_data_points.values():
                if legacy_name in (program.button.legacy_name, program.switch.legacy_name):
                    return program
        return None

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
        if client := self.primary_client:
            return await client.get_system_variable(name=legacy_name)
        return None

    def get_sysvar_data_point(
        self, *, vid: str | None = None, legacy_name: str | None = None
    ) -> GenericSysvarDataPoint | None:
        """Return the sysvar data_point."""
        if vid and (sysvar := self._sysvar_data_points.get(vid)):
            return sysvar
        if legacy_name:
            for sysvar in self._sysvar_data_points.values():
                if sysvar.legacy_name == legacy_name:
                    return sysvar
        return None

    def get_sysvar_data_point_path(self) -> tuple[str, ...]:
        """Return the registered sysvar state path."""
        return tuple(self._sysvar_data_point_event_subscriptions)

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
        """Get the virtual remote for the Client."""
        return tuple(
            cl.get_virtual_remote()  # type: ignore[misc]
            for cl in self._clients.values()
            if cl.get_virtual_remote() is not None
        )

    def has_client(self, *, interface_id: str) -> bool:
        """Check if client exists in central."""
        return interface_id in self._clients

    def identify_channel(self, *, text: str) -> Channel | None:
        """Identify channel within a text."""
        for device in self._devices.values():
            if channel := device.identify_channel(text=text):
                return channel
        return None

    @callback_backend_system(system_event=BackendSystemEvent.LIST_DEVICES)
    def list_devices(self, *, interface_id: str) -> list[DeviceDescription]:
        """Return already existing devices to the backend."""
        result = self._device_descriptions.get_raw_device_descriptions(interface_id=interface_id)
        _LOGGER.debug("LIST_DEVICES: interface_id = %s, channel_count = %i", interface_id, len(result))
        return result

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
            await self._data_cache.load(interface=interface)
        await self._data_cache.refresh_data_point_data(
            paramset_key=paramset_key, interface=interface, direct_call=direct_call
        )

    @inspector(re_raise=False)
    async def refresh_firmware_data(self, *, device_address: str | None = None) -> None:
        """Refresh device firmware data."""
        if device_address and (device := self.get_device(address=device_address)) is not None and device.is_updatable:
            await self._refresh_device_descriptions_and_create_missing_devices(
                client=device.client, refresh_only_existing=True, device_address=device_address
            )
            device.refresh_firmware_data()
        else:
            for client in self._clients.values():
                await self._refresh_device_descriptions_and_create_missing_devices(
                    client=client, refresh_only_existing=True
                )
            for device in self._devices.values():
                if device.is_updatable:
                    device.refresh_firmware_data()

    @inspector(re_raise=False)
    async def refresh_firmware_data_by_state(self, *, device_firmware_states: tuple[DeviceFirmwareState, ...]) -> None:
        """Refresh device firmware data for processing devices."""
        for device in [
            device_in_state
            for device_in_state in self._devices.values()
            if device_in_state.firmware_update_state in device_firmware_states
        ]:
            await self.refresh_firmware_data(device_address=device.address)

    def register_backend_parameter_callback(self, *, cb: BackendParameterCallback) -> UnregisterCallback:
        """Register backend_parameter callback in central."""
        if callable(cb) and cb not in self._backend_parameter_callbacks:
            self._backend_parameter_callbacks.add(cb)
            return partial(self._unregister_backend_parameter_callback, cb=cb)
        return None

    def register_backend_system_callback(self, *, cb: BackendSystemCallback) -> UnregisterCallback:
        """Register system_event callback in central."""
        if callable(cb) and cb not in self._backend_system_callbacks:
            self._backend_system_callbacks.add(cb)
            return partial(self._unregister_backend_system_callback, cb=cb)
        return None

    def register_homematic_callback(self, *, cb: HomematicCallback) -> UnregisterCallback:
        """Register ha_event callback in central."""
        if callable(cb) and cb not in self._homematic_callbacks:
            self._homematic_callbacks.add(cb)
            return partial(self._unregister_homematic_callback, cb=cb)
        return None

    @inspector
    async def remove_central_links(self) -> None:
        """Remove central links."""
        for device in self.devices:
            await device.remove_central_links()

    def remove_device(self, *, device: Device) -> None:
        """Remove device to central collections."""
        if device.address not in self._devices:
            _LOGGER.debug(
                "REMOVE_DEVICE: device %s not registered in central",
                device.address,
            )
            return
        device.remove()

        self._device_descriptions.remove_device(device=device)
        self._paramset_descriptions.remove_device(device=device)
        self._device_details.remove_device(device=device)
        del self._devices[device.address]

    def remove_event_subscription(self, *, data_point: BaseParameterDataPointAny) -> None:
        """Remove event subscription from central collections."""
        if isinstance(data_point, GenericDataPoint | GenericEvent) and data_point.supports_events:
            if data_point.dpk in self._data_point_key_event_subscriptions:
                del self._data_point_key_event_subscriptions[data_point.dpk]
            if data_point.state_path in self._data_point_path_event_subscriptions:
                del self._data_point_path_event_subscriptions[data_point.state_path]

    def remove_program_button(self, *, pid: str) -> None:
        """Remove a program button."""
        if (program_dp := self.get_program_data_point(pid=pid)) is not None:
            program_dp.button.emit_device_removed_event()
            program_dp.switch.emit_device_removed_event()
            del self._program_data_points[pid]

    def remove_sysvar_data_point(self, *, vid: str) -> None:
        """Remove a sysvar data_point."""
        if (sysvar_dp := self.get_sysvar_data_point(vid=vid)) is not None:
            sysvar_dp.emit_device_removed_event()
            del self._sysvar_data_points[vid]
            if sysvar_dp.state_path in self._sysvar_data_point_event_subscriptions:
                del self._sysvar_data_point_event_subscriptions[sysvar_dp.state_path]

    async def restart_clients(self) -> None:
        """Restart clients."""
        await self._stop_clients()
        if await self._start_clients():
            _LOGGER.info(
                i18n.tr(
                    "log.central.restart_clients.restarted",
                    name=self.name,
                )
            )

    async def save_files(
        self,
        *,
        save_device_descriptions: bool = False,
        save_paramset_descriptions: bool = False,
    ) -> None:
        """Save persistent files to disk."""
        if save_device_descriptions:
            await self._device_descriptions.save()
        if save_paramset_descriptions:
            await self._paramset_descriptions.save()

    def set_last_event_seen_for_interface(self, *, interface_id: str) -> None:
        """Set the last event seen for an interface."""
        self._last_event_seen_for_interface[interface_id] = datetime.now()

    async def set_program_state(self, *, pid: str, state: bool) -> bool:
        """Execute a program on the backend."""
        if client := self.primary_client:
            return await client.set_program_state(pid=pid, state=state)
        return False

    async def set_system_variable(self, *, legacy_name: str, value: Any) -> None:
        """Set variable value on the backend."""
        if dp := self.get_sysvar_data_point(legacy_name=legacy_name):
            await dp.send_variable(value=value)
        else:
            _LOGGER.error(
                i18n.tr(
                    "log.central.set_system_variable.not_found",
                    legacy_name=legacy_name,
                    name=self.name,
                )
            )

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
            await self._recorder.deactivate(
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
            if await self._create_clients():
                for client in self._clients.values():
                    await self._refresh_device_descriptions_and_create_missing_devices(
                        client=client, refresh_only_existing=False
                    )
        else:
            self._clients_started = await self._start_clients()
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
        self._stop_scheduler()
        await self._stop_clients()
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

    def sysvar_data_point_path_event(self, *, state_path: str, value: str) -> None:
        """If a device emits some sort event, we will handle it here."""
        _LOGGER_EVENT.debug(
            "SYSVAR_DATA_POINT_PATH_EVENT: topic = %s, payload = %s",
            state_path,
            value,
        )

        if state_path in self._sysvar_data_point_event_subscriptions:
            try:
                callback_handler = self._sysvar_data_point_event_subscriptions[state_path]
                if callable(callback_handler):
                    received_at = datetime.now()
                    self._looper.create_task(
                        target=lambda: callback_handler(value=value, received_at=received_at),
                        name=f"sysvar-data-point-event-{state_path}",
                    )
            except RuntimeError as rterr:
                _LOGGER_EVENT.debug(
                    "EVENT: RuntimeError [%s]. Failed to call handler for: %s",
                    extract_exc_args(exc=rterr),
                    state_path,
                )
            except Exception as exc:  # pragma: no cover
                _LOGGER_EVENT.error(  # i18n-log: ignore
                    "EVENT failed: Unable to call handler for: %s, %s",
                    state_path,
                    extract_exc_args(exc=exc),
                )

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

    @inspector(measure_performance=True)
    async def _add_new_devices(
        self, *, interface_id: str, device_descriptions: tuple[DeviceDescription, ...], source: SourceOfDeviceCreation
    ) -> None:
        """Add new devices to central unit."""
        if not device_descriptions:
            _LOGGER.debug(
                "ADD_NEW_DEVICES: Nothing to add for interface_id %s",
                interface_id,
            )
            return

        _LOGGER.debug(
            "ADD_NEW_DEVICES: interface_id = %s, device_descriptions = %s",
            interface_id,
            len(device_descriptions),
        )

        if interface_id not in self._clients:
            _LOGGER.error(  # i18n-log: ignore
                "ADD_NEW_DEVICES failed: Missing client for interface_id %s",
                interface_id,
            )
            return

        async with self._device_add_semaphore:
            if not (
                new_device_descriptions := self._identify_new_device_descriptions(
                    device_descriptions=device_descriptions, interface_id=interface_id
                )
            ):
                _LOGGER.debug("ADD_NEW_DEVICES: Nothing to add for interface_id %s", interface_id)
                return

            # Here we block the automatic creation of new devices, if required
            if (
                self._config.delay_new_device_creation
                and source == SourceOfDeviceCreation.NEW
                and (
                    new_addresses := extract_device_addresses_from_device_descriptions(
                        device_descriptions=new_device_descriptions
                    )
                )
            ):
                self.emit_backend_system_callback(
                    system_event=BackendSystemEvent.DEVICES_DELAYED,
                    new_addresses=new_addresses,
                    interface_id=interface_id,
                    source=source,
                )
                return

            client = self._clients[interface_id]
            save_descriptions = False
            for dev_desc in new_device_descriptions:
                try:
                    self._device_descriptions.add_device(interface_id=interface_id, device_description=dev_desc)
                    await client.fetch_paramset_descriptions(device_description=dev_desc)
                    save_descriptions = True
                except Exception as exc:  # pragma: no cover
                    save_descriptions = False
                    _LOGGER.error(  # i18n-log: ignore
                        "UPDATE_CACHES_WITH_NEW_DEVICES failed: %s [%s]",
                        type(exc).__name__,
                        extract_exc_args(exc=exc),
                    )

            await self.save_files(
                save_device_descriptions=save_descriptions,
                save_paramset_descriptions=save_descriptions,
            )

        if new_device_addresses := self._check_for_new_device_addresses(interface_id=interface_id):
            await self._device_details.load()
            await self._data_cache.load(interface=client.interface)
            await self._create_devices(new_device_addresses=new_device_addresses, source=source)

    def _check_for_new_device_addresses(self, *, interface_id: str | None = None) -> Mapping[str, set[str]]:
        """Check if there are new devices that need to be created."""
        new_device_addresses: dict[str, set[str]] = {}

        # Cache existing device addresses once to avoid repeated mapping lookups
        existing_addresses = set(self._devices.keys())

        def _check_for_new_device_addresses_helper(*, iid: str) -> None:
            """Check if there are new devices that need to be created."""
            if not self._paramset_descriptions.has_interface_id(interface_id=iid):
                _LOGGER.debug(
                    "CHECK_FOR_NEW_DEVICE_ADDRESSES: Skipping interface %s, missing paramsets",
                    iid,
                )
                return
            # Build the set locally and assign only if non-empty to avoid add-then-delete pattern
            # Use set difference for speed on large collections
            addresses = set(self._device_descriptions.get_addresses(interface_id=iid))
            # get_addresses returns an iterable (likely tuple); convert to set once for efficient diff
            if new_set := addresses - existing_addresses:
                new_device_addresses[iid] = new_set

        if interface_id:
            _check_for_new_device_addresses_helper(iid=interface_id)
        else:
            for iid in self.interface_ids:
                _check_for_new_device_addresses_helper(iid=iid)

        if _LOGGER.isEnabledFor(level=DEBUG):
            count = sum(len(item) for item in new_device_addresses.values())
            _LOGGER.debug(
                "CHECK_FOR_NEW_DEVICE_ADDRESSES: %s: %i.",
                "Found new device addresses" if new_device_addresses else "Did not find any new device addresses",
                count,
            )

        return new_device_addresses

    async def _create_client(self, *, interface_config: hmcl.InterfaceConfig) -> bool:
        """Create a client."""
        try:
            if client := await hmcl.create_client(
                central=self,
                interface_config=interface_config,
            ):
                _LOGGER.debug(
                    "CREATE_CLIENT: Adding client %s to %s",
                    client.interface_id,
                    self.name,
                )
                self._clients[client.interface_id] = client
                return True
        except BaseHomematicException as bhexc:  # pragma: no cover - deterministic simulation of client creation failures would require the full client/proxy stack and network timing; keeping this defensive log-and-state branch untested to avoid brittle CI
            self.emit_interface_event(
                interface_id=interface_config.interface_id,
                interface_event_type=InterfaceEventType.PROXY,
                data={EventKey.AVAILABLE: False},
            )

            _LOGGER.error(
                i18n.tr(
                    "log.central.create_client.no_connection",
                    interface_id=interface_config.interface_id,
                    reason=extract_exc_args(exc=bhexc),
                )
            )
        return False

    async def _create_clients(self) -> bool:
        """Create clients for the central unit. Start connection checker afterwards."""
        if len(self._clients) > 0:
            _LOGGER.error(
                i18n.tr(
                    "log.central.create_clients.already_created",
                    name=self.name,
                )
            )
            return False
        if len(self._config.enabled_interface_configs) == 0:
            _LOGGER.error(
                i18n.tr(
                    "log.central.create_clients.no_interfaces",
                    name=self.name,
                )
            )
            return False

        # create primary clients
        for interface_config in self._config.enabled_interface_configs:
            if interface_config.interface in PRIMARY_CLIENT_CANDIDATE_INTERFACES:
                await self._create_client(interface_config=interface_config)

        # create secondary clients
        for interface_config in self._config.enabled_interface_configs:
            if interface_config.interface not in PRIMARY_CLIENT_CANDIDATE_INTERFACES:
                if (
                    self.primary_client is not None
                    and interface_config.interface not in self.primary_client.system_information.available_interfaces
                ):
                    _LOGGER.error(
                        i18n.tr(
                            "log.central.create_clients.interface_not_available",
                            interface=interface_config.interface,
                            name=self.name,
                        )
                    )
                    interface_config.disable()
                    continue
                await self._create_client(interface_config=interface_config)

        if not self.all_clients_active:
            _LOGGER.warning(
                i18n.tr(
                    "log.central.create_clients.created_count_failed",
                    created=len(self._clients),
                    total=len(self._config.enabled_interface_configs),
                )
            )
            return False

        if self.primary_client is None:
            _LOGGER.warning(
                i18n.tr(
                    "log.central.create_clients.no_primary_identified",
                    name=self.name,
                )
            )
            return True

        _LOGGER.debug("CREATE_CLIENTS successful for %s", self.name)
        return True

    async def _create_devices(
        self, *, new_device_addresses: Mapping[str, set[str]], source: SourceOfDeviceCreation
    ) -> None:
        """Trigger creation of the objects that expose the functionality."""
        if not self._clients:
            raise AioHomematicException(
                i18n.tr(
                    "exception.central.create_devices.no_clients",
                    name=self.name,
                )
            )
        _LOGGER.debug("CREATE_DEVICES: Starting to create devices for %s", self.name)

        new_devices = set[Device]()

        for interface_id, device_addresses in new_device_addresses.items():
            for device_address in device_addresses:
                # Do we check for duplicates here? For now, we do.
                if device_address in self._devices:
                    continue
                device: Device | None = None
                try:
                    device = Device(
                        central=self,
                        interface_id=interface_id,
                        device_address=device_address,
                    )
                except Exception as exc:
                    _LOGGER.error(  # i18n-log: ignore
                        "CREATE_DEVICES failed: %s [%s] Unable to create device: %s, %s",
                        type(exc).__name__,
                        extract_exc_args(exc=exc),
                        interface_id,
                        device_address,
                    )
                try:
                    if device:
                        create_data_points_and_events(device=device)
                        create_custom_data_points(device=device)
                        new_devices.add(device)
                        self._devices[device_address] = device
                except Exception as exc:
                    _LOGGER.error(  # i18n-log: ignore
                        "CREATE_DEVICES failed: %s [%s] Unable to create data points: %s, %s",
                        type(exc).__name__,
                        extract_exc_args(exc=exc),
                        interface_id,
                        device_address,
                    )
        _LOGGER.debug("CREATE_DEVICES: Finished creating devices for %s", self.name)

        if new_devices:
            for device in new_devices:
                await device.finalize_init()
            new_dps = _get_new_data_points(new_devices=new_devices)
            new_channel_events = _get_new_channel_events(new_devices=new_devices)
            self.emit_backend_system_callback(
                system_event=BackendSystemEvent.DEVICES_CREATED,
                new_data_points=new_dps,
                new_channel_events=new_channel_events,
                source=source,
            )

    async def _de_init_clients(self) -> None:
        """De-init clients."""
        for name, client in self._clients.items():
            if await client.deinitialize_proxy():
                _LOGGER.debug("DE_INIT_CLIENTS: Proxy de-initialized: %s", name)

    def _get_primary_client(self) -> hmcl.Client | None:
        """Return the client by interface_id or the first with a virtual remote."""
        client: hmcl.Client | None = None
        for client in self._clients.values():
            if client.interface in PRIMARY_CLIENT_CANDIDATE_INTERFACES and client.available:
                return client
        return client

    def _get_virtual_remote(self, *, device_address: str) -> Device | None:
        """Get the virtual remote for the Client."""
        for client in self._clients.values():
            virtual_remote = client.get_virtual_remote()
            if virtual_remote and virtual_remote.address == device_address:
                return virtual_remote
        return None

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

    def _identify_new_device_descriptions(
        self, *, device_descriptions: tuple[DeviceDescription, ...], interface_id: str | None = None
    ) -> tuple[DeviceDescription, ...]:
        """Identify devices whose ADDRESS isn't already known on any interface."""
        known_addresses = self._device_descriptions.get_addresses(interface_id=interface_id)
        return tuple(
            dev_desc
            for dev_desc in device_descriptions
            if (dev_desc["ADDRESS"] if not (parent_address := dev_desc.get("PARENT")) else parent_address)
            not in known_addresses
        )

    async def _init_clients(self) -> None:
        """Init clients of control unit, and start connection checker."""
        for client in self._clients.copy().values():
            if client.interface not in self.system_information.available_interfaces:
                _LOGGER.debug(
                    "INIT_CLIENTS failed: Interface: %s is not available for the backend %s",
                    client.interface,
                    self.name,
                )
                del self._clients[client.interface_id]
                continue
            if await client.initialize_proxy() == ProxyInitState.INIT_SUCCESS:
                _LOGGER.debug("INIT_CLIENTS: client %s initialized for %s", client.interface_id, self.name)

    async def _init_hub(self) -> None:
        """Init the hub."""
        await self._hub.fetch_program_data(scheduled=True)
        await self._hub.fetch_sysvar_data(scheduled=True)

    async def _load_caches(self) -> bool:
        """Load files to store."""
        if DataOperationResult.LOAD_FAIL in (
            await self._device_descriptions.load(),
            await self._paramset_descriptions.load(),
        ):
            _LOGGER.warning(  # i18n-log: ignore
                "LOAD_CACHES failed: Unable to load store for %s. Clearing files", self.name
            )
            await self.clear_files()
            return False
        await self._device_details.load()
        await self._data_cache.load()
        return True

    async def _refresh_device_descriptions_and_create_missing_devices(
        self, *, client: hmcl.Client, refresh_only_existing: bool, device_address: str | None = None
    ) -> None:
        """Refresh device descriptions and create missing devices."""
        device_descriptions: tuple[DeviceDescription, ...] | None = None

        if (
            device_address
            and (device_description := await client.get_device_description(device_address=device_address)) is not None
        ):
            device_descriptions = (device_description,)
        else:
            device_descriptions = await client.list_devices()

        if (
            device_descriptions
            and refresh_only_existing
            and (
                existing_device_descriptions := tuple(
                    dev_desc
                    for dev_desc in list(device_descriptions)
                    if dev_desc["ADDRESS"]
                    in self.device_descriptions.get_device_descriptions(interface_id=client.interface_id)
                )
            )
        ):
            device_descriptions = existing_device_descriptions

        if device_descriptions:
            await self._add_new_devices(
                interface_id=client.interface_id,
                device_descriptions=device_descriptions,
                source=SourceOfDeviceCreation.REFRESH,
            )

    async def _start_clients(self) -> bool:
        """Start clients ."""
        if not await self._create_clients():
            return False
        await self._load_caches()
        if new_device_addresses := self._check_for_new_device_addresses():
            await self._create_devices(new_device_addresses=new_device_addresses, source=SourceOfDeviceCreation.CACHE)
        await self._init_hub()
        await self._init_clients()
        # Proactively fetch device descriptions if none were created yet to avoid slow startup
        if not self._devices:
            for client in self._clients.values():
                await self._refresh_device_descriptions_and_create_missing_devices(
                    client=client, refresh_only_existing=False
                )
        return True

    def _start_scheduler(self) -> None:
        """Start the scheduler."""
        _LOGGER.debug(
            "START_SCHEDULER: Starting scheduler for %s",
            self.name,
        )
        self._scheduler.start()

    async def _stop_clients(self) -> None:
        """Stop clients."""
        await self._de_init_clients()
        for client in self._clients.values():
            _LOGGER.debug("STOP_CLIENTS: Stopping %s", client.interface_id)
            await client.stop()
        _LOGGER.debug("STOP_CLIENTS: Clearing existing clients.")
        self._clients.clear()
        self._clients_started = False

    def _stop_scheduler(self) -> None:
        """Start the connection checker."""
        self._scheduler.stop()
        _LOGGER.debug(
            "STOP_SCHEDULER: Stopped scheduler for %s",
            self.name,
        )

    def _unregister_backend_parameter_callback(self, *, cb: BackendParameterCallback) -> None:
        """Un register backend_parameter callback in central."""
        if cb in self._backend_parameter_callbacks:
            self._backend_parameter_callbacks.remove(cb)

    def _unregister_backend_system_callback(self, *, cb: BackendSystemCallback) -> None:
        """Un register system_event callback in central."""
        if cb in self._backend_system_callbacks:
            self._backend_system_callbacks.remove(cb)

    def _unregister_homematic_callback(self, *, cb: HomematicCallback) -> None:
        """RUn register ha_event callback in central."""
        if cb in self._homematic_callbacks:
            self._homematic_callbacks.remove(cb)


class _Scheduler(threading.Thread):
    """Periodically check connection to the backend, and load data when required."""

    def __init__(self, *, central: CentralUnit) -> None:
        """Init the connection checker."""
        threading.Thread.__init__(self, name=f"ConnectionChecker for {central.name}")
        self._central: Final = central
        self._unregister_callback = self._central.register_backend_system_callback(cb=self._backend_system_callback)
        self._active = True
        self._devices_created = False
        self._scheduler_jobs = [
            _SchedulerJob(task=self._check_connection, run_interval=CONNECTION_CHECKER_INTERVAL),
            _SchedulerJob(
                task=self._refresh_client_data,
                run_interval=self._central.config.periodic_refresh_interval,
            ),
            _SchedulerJob(
                task=self._refresh_program_data,
                run_interval=self._central.config.sys_scan_interval,
            ),
            _SchedulerJob(task=self._refresh_sysvar_data, run_interval=self._central.config.sys_scan_interval),
            _SchedulerJob(
                task=self._fetch_device_firmware_update_data,
                run_interval=DEVICE_FIRMWARE_CHECK_INTERVAL,
            ),
            _SchedulerJob(
                task=self._fetch_device_firmware_update_data_in_delivery,
                run_interval=DEVICE_FIRMWARE_DELIVERING_CHECK_INTERVAL,
            ),
            _SchedulerJob(
                task=self._fetch_device_firmware_update_data_in_update,
                run_interval=DEVICE_FIRMWARE_UPDATING_CHECK_INTERVAL,
            ),
        ]

    def run(self) -> None:
        """Run the scheduler thread."""
        _LOGGER.debug(
            "run: scheduler for %s",
            self._central.name,
        )

        self._central.looper.create_task(
            target=self._run_scheduler_tasks(),
            name="run_scheduler_tasks",
        )

    def stop(self) -> None:
        """To stop the ConnectionChecker."""
        if self._unregister_callback is not None:
            self._unregister_callback()
        self._active = False

    def _backend_system_callback(self, *, system_event: BackendSystemEvent, **kwargs: Any) -> None:
        """Handle event of new device creation, to delay the start of the sysvar scan."""
        if system_event == BackendSystemEvent.DEVICES_CREATED:
            self._devices_created = True

    async def _check_connection(self) -> None:
        """Check connection to backend."""
        _LOGGER.debug("CHECK_CONNECTION: Checking connection to server %s", self._central.name)
        try:
            if not self._central.all_clients_active:
                _LOGGER.error(
                    i18n.tr(
                        "log.central.scheduler.check_connection.no_clients",
                        name=self._central.name,
                    )
                )
                await self._central.restart_clients()
            else:
                reconnects: list[Any] = []
                reloads: list[Any] = []
                for interface_id in self._central.interface_ids:
                    # check:
                    #  - client is available
                    #  - client is connected
                    #  - interface callback is alive
                    client = self._central.get_client(interface_id=interface_id)
                    if client.available is False or not await client.is_connected() or not client.is_callback_alive():
                        reconnects.append(client.reconnect())
                        reloads.append(self._central.load_and_refresh_data_point_data(interface=client.interface))
                if reconnects:
                    await asyncio.gather(*reconnects)
                    if self._central.available:
                        await asyncio.gather(*reloads)
        except NoConnectionException as nex:
            _LOGGER.error(
                i18n.tr(
                    "log.central.scheduler.check_connection.no_connection",
                    reason=extract_exc_args(exc=nex),
                )
            )
        except Exception as exc:
            _LOGGER.error(
                i18n.tr(
                    "log.central.scheduler.check_connection.failed",
                    exc_type=type(exc).__name__,
                    reason=extract_exc_args(exc=exc),
                )
            )

    @inspector(re_raise=False)
    async def _fetch_device_firmware_update_data(self) -> None:
        """Periodically fetch device firmware update data from backend."""
        if (
            not self._central.config.enable_device_firmware_check
            or not self._central.available
            or not self._devices_created
        ):
            return

        _LOGGER.debug(
            "FETCH_DEVICE_FIRMWARE_UPDATE_DATA: Scheduled fetching of device firmware update data for %s",
            self._central.name,
        )
        await self._central.refresh_firmware_data()

    @inspector(re_raise=False)
    async def _fetch_device_firmware_update_data_in_delivery(self) -> None:
        """Periodically fetch device firmware update data from backend."""
        if (
            not self._central.config.enable_device_firmware_check
            or not self._central.available
            or not self._devices_created
        ):
            return

        _LOGGER.debug(
            "FETCH_DEVICE_FIRMWARE_UPDATE_DATA_IN_DELIVERY: Scheduled fetching of device firmware update data for delivering devices for %s",
            self._central.name,
        )
        await self._central.refresh_firmware_data_by_state(
            device_firmware_states=(
                DeviceFirmwareState.DELIVER_FIRMWARE_IMAGE,
                DeviceFirmwareState.LIVE_DELIVER_FIRMWARE_IMAGE,
            )
        )

    @inspector(re_raise=False)
    async def _fetch_device_firmware_update_data_in_update(self) -> None:
        """Periodically fetch device firmware update data from backend."""
        if (
            not self._central.config.enable_device_firmware_check
            or not self._central.available
            or not self._devices_created
        ):
            return

        _LOGGER.debug(
            "FETCH_DEVICE_FIRMWARE_UPDATE_DATA_IN_UPDATE: Scheduled fetching of device firmware update data for updating devices for %s",
            self._central.name,
        )
        await self._central.refresh_firmware_data_by_state(
            device_firmware_states=(
                DeviceFirmwareState.READY_FOR_UPDATE,
                DeviceFirmwareState.DO_UPDATE_PENDING,
                DeviceFirmwareState.PERFORMING_UPDATE,
            )
        )

    @inspector(re_raise=False)
    async def _refresh_client_data(self) -> None:
        """Refresh client data."""
        if not self._central.available:
            return

        if (poll_clients := self._central.poll_clients) is not None and len(poll_clients) > 0:
            _LOGGER.debug("REFRESH_CLIENT_DATA: Loading data for %s", self._central.name)
            for client in poll_clients:
                await self._central.load_and_refresh_data_point_data(interface=client.interface)
                self._central.set_last_event_seen_for_interface(interface_id=client.interface_id)

    @inspector(re_raise=False)
    async def _refresh_program_data(self) -> None:
        """Refresh system program_data."""
        if not self._central.config.enable_program_scan or not self._central.available or not self._devices_created:
            return

        _LOGGER.debug("REFRESH_PROGRAM_DATA: For %s", self._central.name)
        await self._central.fetch_program_data(scheduled=True)

    @inspector(re_raise=False)
    async def _refresh_sysvar_data(self) -> None:
        """Refresh system variables."""
        if not self._central.config.enable_sysvar_scan or not self._central.available or not self._devices_created:
            return

        _LOGGER.debug("REFRESH_SYSVAR_DATA: For %s", self._central.name)
        await self._central.fetch_sysvar_data(scheduled=True)

    async def _run_scheduler_tasks(self) -> None:
        """Run all tasks."""
        while self._active:
            if self._central.state != CentralUnitState.RUNNING:
                _LOGGER.debug("SCHEDULER: Waiting till central %s is started", self._central.name)
                await asyncio.sleep(SCHEDULER_NOT_STARTED_SLEEP)
                continue

            any_executed = False
            for job in self._scheduler_jobs:
                if not self._active or not job.ready:
                    continue
                await job.run()
                job.schedule_next_execution()
                any_executed = True

            if not self._active:
                break  # type: ignore[unreachable]

            # If no job was executed this cycle, we can sleep until the next job is due
            if not any_executed:
                now = datetime.now()
                try:
                    next_due = min(job.next_run for job in self._scheduler_jobs)
                    # Sleep until the next task should run, but cap to 1s to remain responsive
                    delay = max(0.0, (next_due - now).total_seconds())
                    await asyncio.sleep(min(1.0, delay))
                except ValueError:
                    # No jobs configured; fallback to default loop sleep
                    await asyncio.sleep(SCHEDULER_LOOP_SLEEP)
            else:
                # When work was done, yield briefly to the loop
                await asyncio.sleep(SCHEDULER_LOOP_SLEEP)


class _SchedulerJob:
    """Job to run in the scheduler."""

    def __init__(
        self,
        *,
        task: AsyncTaskFactory,
        run_interval: int,
        next_run: datetime | None = None,
    ):
        """Init the job."""
        self._task: Final = task
        self._next_run = next_run or datetime.now()
        self._run_interval: Final = run_interval

    @property
    def next_run(self) -> datetime:
        """Return the next scheduled run timestamp."""
        return self._next_run

    @property
    def ready(self) -> bool:
        """Return if the job can be executed."""
        return self._next_run < datetime.now()

    async def run(self) -> None:
        """Run the task."""
        await self._task()

    def schedule_next_execution(self) -> None:
        """Schedule the next execution of the job."""
        self._next_run += timedelta(seconds=self._run_interval)


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
