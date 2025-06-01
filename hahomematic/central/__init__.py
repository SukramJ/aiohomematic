"""
CentralUnit module.

This is the python representation of a CCU.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine, Mapping, Set as AbstractSet
from datetime import datetime, timedelta
from functools import partial
import logging
from logging import DEBUG
import threading
from typing import Any, Final, cast

from aiohttp import ClientSession
import voluptuous as vol

from hahomematic import client as hmcl
from hahomematic.async_support import Looper, loop_check
from hahomematic.caches.dynamic import CentralDataCache, DeviceDetailsCache
from hahomematic.caches.persistent import DeviceDescriptionCache, ParamsetDescriptionCache
from hahomematic.caches.visibility import ParameterVisibilityCache
from hahomematic.central import xml_rpc_server as xmlrpc
from hahomematic.central.decorators import callback_backend_system, callback_event
from hahomematic.client.json_rpc import JsonRpcAioHttpClient
from hahomematic.client.xml_rpc import XmlRpcProxy
from hahomematic.const import (
    CALLBACK_TYPE,
    CATEGORIES,
    CONNECTION_CHECKER_INTERVAL,
    DATA_POINT_EVENTS,
    DATETIME_FORMAT_MILLIS,
    DEFAULT_ENABLE_DEVICE_FIRMWARE_CHECK,
    DEFAULT_ENABLE_PROGRAM_SCAN,
    DEFAULT_ENABLE_SYSVAR_SCAN,
    DEFAULT_HM_MASTER_POLL_AFTER_SEND_INTERVALS,
    DEFAULT_IGNORE_CUSTOM_DEVICE_DEFINITION_MODELS,
    DEFAULT_MAX_READ_WORKERS,
    DEFAULT_PERIODIC_REFRESH_INTERVAL,
    DEFAULT_PROGRAM_MARKERS,
    DEFAULT_SYS_SCAN_INTERVAL,
    DEFAULT_SYSVAR_MARKERS,
    DEFAULT_TLS,
    DEFAULT_UN_IGNORES,
    DEFAULT_VERIFY_TLS,
    DEVICE_FIRMWARE_CHECK_INTERVAL,
    DEVICE_FIRMWARE_DELIVERING_CHECK_INTERVAL,
    DEVICE_FIRMWARE_UPDATING_CHECK_INTERVAL,
    IGNORE_FOR_UN_IGNORE_PARAMETERS,
    INTERFACES_REQUIRING_PERIODIC_REFRESH,
    IP_ANY_V4,
    LOCAL_HOST,
    PORT_ANY,
    PRIMARY_CLIENT_CANDIDATE_INTERFACES,
    TIMEOUT,
    UN_IGNORE_WILDCARD,
    BackendSystemEvent,
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
    Parameter,
    ParamsetKey,
    ProxyInitState,
    SystemInformation,
)
from hahomematic.decorators import inspector
from hahomematic.exceptions import (
    BaseHomematicException,
    HaHomematicConfigException,
    HaHomematicException,
    NoClientsException,
    NoConnectionException,
)
from hahomematic.model import create_data_points_and_events
from hahomematic.model.custom import CustomDataPoint, create_custom_data_points
from hahomematic.model.data_point import BaseParameterDataPoint, CallbackDataPoint
from hahomematic.model.decorators import info_property
from hahomematic.model.device import Channel, Device
from hahomematic.model.event import GenericEvent
from hahomematic.model.generic import GenericDataPoint
from hahomematic.model.hub import (
    GenericHubDataPoint,
    GenericProgramDataPoint,
    GenericSysvarDataPoint,
    Hub,
    ProgramDpType,
)
from hahomematic.model.support import PayloadMixin
from hahomematic.support import check_config, get_channel_no, get_device_address, get_ip_addr, reduce_args

__all__ = ["CentralConfig", "CentralUnit", "INTERFACE_EVENT_SCHEMA"]

_LOGGER: Final = logging.getLogger(__name__)

# {central_name, central}
CENTRAL_INSTANCES: Final[dict[str, CentralUnit]] = {}
ConnectionProblemIssuer = JsonRpcAioHttpClient | XmlRpcProxy

INTERFACE_EVENT_SCHEMA = vol.Schema(
    {
        vol.Required(str(EventKey.INTERFACE_ID)): str,
        vol.Required(str(EventKey.TYPE)): InterfaceEventType,
        vol.Required(str(EventKey.DATA)): vol.Schema(
            {vol.Required(vol.Any(EventKey)): vol.Schema(vol.Any(str, int, bool))}
        ),
    }
)


class CentralUnit(PayloadMixin):
    """Central unit that collects everything to handle communication from/to CCU/Homegear."""

    def __init__(self, central_config: CentralConfig) -> None:
        """Init the central unit."""
        self._started: bool = False
        self._clients_started: bool = False
        self._device_add_semaphore: Final = asyncio.Semaphore()
        self._connection_state: Final = CentralConnectionState()
        self._tasks: Final[set[asyncio.Future[Any]]] = set()
        # Keep the config for the central
        self._config: Final = central_config
        self._url: Final = self._config.create_central_url()
        self._model: str | None = None
        self._looper = Looper()
        self._xml_rpc_server: xmlrpc.XmlRpcServer | None = None
        self._json_rpc_client: JsonRpcAioHttpClient | None = None

        # Caches for CCU data
        self._data_cache: Final = CentralDataCache(central=self)
        self._device_details: Final = DeviceDetailsCache(central=self)
        self._device_descriptions: Final = DeviceDescriptionCache(central=self)
        self._paramset_descriptions: Final = ParamsetDescriptionCache(central=self)
        self._parameter_visibility: Final = ParameterVisibilityCache(central=self)

        self._primary_client: hmcl.Client | None = None
        # {interface_id, client}
        self._clients: Final[dict[str, hmcl.Client]] = {}
        self._data_point_key_event_subscriptions: Final[
            dict[DataPointKey, list[Callable[[Any], Coroutine[Any, Any, None]]]]
        ] = {}
        self._data_point_path_event_subscriptions: Final[dict[str, DataPointKey]] = {}
        self._sysvar_data_point_event_subscriptions: Final[dict[str, Callable]] = {}
        # {device_address, device}
        self._devices: Final[dict[str, Device]] = {}
        # {sysvar_name, sysvar_data_point}
        self._sysvar_data_points: Final[dict[str, GenericSysvarDataPoint]] = {}
        # {sysvar_name, program_button}
        self._program_data_points: Final[dict[str, ProgramDpType]] = {}
        # Signature: (name, *args)
        # e.g. DEVICES_CREATED, HUB_REFRESHED
        self._backend_system_callbacks: Final[set[Callable]] = set()
        # Signature: (interface_id, channel_address, parameter, value)
        # Re-Fired events from CCU for parameter updates
        self._backend_parameter_callbacks: Final[set[Callable]] = set()
        # Signature: (event_type, event_data)
        # Events like INTERFACE, KEYPRESS, ...
        self._homematic_callbacks: Final[set[Callable]] = set()

        CENTRAL_INSTANCES[self.name] = self
        self._scheduler: Final = _Scheduler(central=self)
        self._hub: Hub = Hub(central=self)
        self._version: str | None = None
        # store last event received datetime by interface_id
        self._last_events: Final[dict[str, datetime]] = {}
        self._xml_rpc_callback_ip: str = IP_ANY_V4
        self._listen_ip_addr: str = IP_ANY_V4
        self._listen_port: int = PORT_ANY

    @property
    def available(self) -> bool:
        """Return the availability of the central."""
        return all(client.available for client in self._clients.values())

    @property
    def callback_ip_addr(self) -> str:
        """Return the xml rpc server callback ip address."""
        return self._xml_rpc_callback_ip

    @info_property
    def url(self) -> str:
        """Return the central url."""
        return self._url

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
    def device_details(self) -> DeviceDetailsCache:
        """Return device_details cache."""
        return self._device_details

    @property
    def device_descriptions(self) -> DeviceDescriptionCache:
        """Return device_descriptions cache."""
        return self._device_descriptions

    @property
    def devices(self) -> tuple[Device, ...]:
        """Return all devices."""
        return tuple(self._devices.values())

    @property
    def _has_active_threads(self) -> bool:
        """Return if active sub threads are alive."""
        if self._scheduler.is_alive():
            return True
        return bool(
            self._xml_rpc_server and self._xml_rpc_server.no_central_assigned and self._xml_rpc_server.is_alive()
        )

    @property
    def interface_ids(self) -> tuple[str, ...]:
        """Return all associated interface ids."""
        return tuple(self._clients)

    @property
    def interfaces(self) -> tuple[Interface, ...]:
        """Return all associated interfaces."""
        return tuple(client.interface for client in self._clients.values())

    @property
    def is_alive(self) -> bool:
        """Return if XmlRPC-Server is alive."""
        return all(client.is_callback_alive() for client in self._clients.values())

    @property
    def json_rpc_client(self) -> JsonRpcAioHttpClient:
        """Return the json rpc client."""
        if not self._json_rpc_client:
            self._json_rpc_client = self._config.create_json_rpc_client(central=self)
        return self._json_rpc_client

    @property
    def paramset_descriptions(self) -> ParamsetDescriptionCache:
        """Return paramset_descriptions cache."""
        return self._paramset_descriptions

    @property
    def parameter_visibility(self) -> ParameterVisibilityCache:
        """Return parameter_visibility cache."""
        return self._parameter_visibility

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
    def listen_ip_addr(self) -> str:
        """Return the xml rpc server listening ip address."""
        return self._listen_ip_addr

    @property
    def listen_port(self) -> int:
        """Return the xml rpc listening server port."""
        return self._listen_port

    @property
    def looper(self) -> Looper:
        """Return the loop support."""
        return self._looper

    @info_property
    def model(self) -> str | None:
        """Return the model of the backend."""
        if not self._model and (client := self.primary_client):
            self._model = client.model
        return self._model

    @info_property
    def name(self) -> str:
        """Return the name of the backend."""
        return self._config.name

    @property
    def program_data_points(self) -> tuple[GenericProgramDataPoint, ...]:
        """Return the program data points."""
        return tuple(
            [x.button for x in self._program_data_points.values()]
            + [x.switch for x in self._program_data_points.values()]
        )

    @property
    def started(self) -> bool:
        """Return if the central is started."""
        return self._started

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

    @info_property
    def version(self) -> str | None:
        """Return the version of the backend."""
        if self._version is None:
            versions = [client.version for client in self._clients.values() if client.version]
            self._version = max(versions) if versions else None
        return self._version

    def add_sysvar_data_point(self, sysvar_data_point: GenericSysvarDataPoint) -> None:
        """Add new program button."""
        if (vid := sysvar_data_point.vid) is not None:
            self._sysvar_data_points[vid] = sysvar_data_point
        if sysvar_data_point.state_path not in self._sysvar_data_point_event_subscriptions:
            self._sysvar_data_point_event_subscriptions[sysvar_data_point.state_path] = sysvar_data_point.event

    def remove_sysvar_data_point(self, vid: str) -> None:
        """Remove a sysvar data_point."""
        if (sysvar_dp := self.get_sysvar_data_point(vid=vid)) is not None:
            sysvar_dp.fire_device_removed_callback()
            del self._sysvar_data_points[vid]
            if sysvar_dp.state_path in self._sysvar_data_point_event_subscriptions:
                del self._sysvar_data_point_event_subscriptions[sysvar_dp.state_path]

    def add_program_data_point(self, program_dp: ProgramDpType) -> None:
        """Add new program button."""
        self._program_data_points[program_dp.pid] = program_dp

    def remove_program_button(self, pid: str) -> None:
        """Remove a program button."""
        if (program_dp := self.get_program_data_point(pid=pid)) is not None:
            program_dp.button.fire_device_removed_callback()
            program_dp.switch.fire_device_removed_callback()
            del self._program_data_points[pid]

    def identify_channel(self, text: str) -> Channel | None:
        """Identify channel within a text."""
        for device in self._devices.values():
            if channel := device.identify_channel(text=text):
                return channel
        return None

    async def save_caches(
        self, save_device_descriptions: bool = False, save_paramset_descriptions: bool = False
    ) -> None:
        """Save persistent caches."""
        if save_device_descriptions:
            await self._device_descriptions.save()
        if save_paramset_descriptions:
            await self._paramset_descriptions.save()

    async def start(self) -> None:
        """Start processing of the central unit."""

        if self._started:
            _LOGGER.debug("START: Central %s already started", self.name)
            return
        if self._config.enabled_interface_configs and (
            ip_addr := await self._identify_ip_addr(port=self._config.connection_check_port)
        ):
            self._xml_rpc_callback_ip = ip_addr
            self._listen_ip_addr = self._config.listen_ip_addr if self._config.listen_ip_addr else ip_addr

        listen_port: int = (
            self._config.listen_port
            if self._config.listen_port
            else self._config.callback_port or self._config.default_callback_port
        )
        try:
            if (
                xml_rpc_server := xmlrpc.create_xml_rpc_server(ip_addr=self._listen_ip_addr, port=listen_port)
                if self._config.enable_server
                else None
            ):
                self._xml_rpc_server = xml_rpc_server
                self._listen_port = xml_rpc_server.listen_port
                self._xml_rpc_server.add_central(self)
        except OSError as oserr:
            raise HaHomematicException(
                f"START: Failed to start central unit {self.name}: {reduce_args(args=oserr.args)}"
            ) from oserr

        if self._config.start_direct:
            if await self._create_clients():
                for client in self._clients.values():
                    await self._refresh_device_descriptions(client=client)
        else:
            self._clients_started = await self._start_clients()
            if self._config.enable_server:
                self._start_scheduler()

        self._started = True

    async def stop(self) -> None:
        """Stop processing of the central unit."""
        if not self._started:
            _LOGGER.debug("STOP: Central %s not started", self.name)
            return
        await self.save_caches(save_device_descriptions=True, save_paramset_descriptions=True)
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

        # wait until tasks are finished
        await self.looper.block_till_done()

        DONE = asyncio.Event()
        while self._has_active_threads:
            await DONE.wait()
        self._started = False

    async def restart_clients(self) -> None:
        """Restart clients."""
        await self._stop_clients()
        if await self._start_clients():
            _LOGGER.info("RESTART_CLIENTS: Central %s restarted clients", self.name)

    @inspector(re_raise=False)
    async def refresh_firmware_data(self, device_address: str | None = None) -> None:
        """Refresh device firmware data."""
        if device_address and (device := self.get_device(address=device_address)) is not None and device.is_updatable:
            await self._refresh_device_descriptions(client=device.client, device_address=device_address)
            device.refresh_firmware_data()
        else:
            for client in self._clients.values():
                await self._refresh_device_descriptions(client=client)
            for device in self._devices.values():
                if device.is_updatable:
                    device.refresh_firmware_data()

    @inspector(re_raise=False)
    async def refresh_firmware_data_by_state(self, device_firmware_states: tuple[DeviceFirmwareState, ...]) -> None:
        """Refresh device firmware data for processing devices."""
        for device in [
            device_in_state
            for device_in_state in self._devices.values()
            if device_in_state.firmware_update_state in device_firmware_states
        ]:
            await self.refresh_firmware_data(device_address=device.address)

    async def _refresh_device_descriptions(self, client: hmcl.Client, device_address: str | None = None) -> None:
        """Refresh device descriptions."""
        device_descriptions: tuple[DeviceDescription, ...] | None = None
        if (
            device_address
            and (device_description := await client.get_device_description(device_address=device_address)) is not None
        ):
            device_descriptions = (device_description,)
        else:
            device_descriptions = await client.list_devices()

        if device_descriptions:
            await self._add_new_devices(
                interface_id=client.interface_id,
                device_descriptions=device_descriptions,
            )

    async def _start_clients(self) -> bool:
        """Start clients ."""
        if not await self._create_clients():
            return False
        await self._load_caches()
        if new_device_addresses := self._check_for_new_device_addresses():
            await self._create_devices(new_device_addresses=new_device_addresses)
        await self._init_hub()
        await self._init_clients()
        return True

    async def _stop_clients(self) -> None:
        """Stop clients."""
        await self._de_init_clients()
        for client in self._clients.values():
            _LOGGER.debug("STOP_CLIENTS: Stopping %s", client.interface_id)
            await client.stop()
        _LOGGER.debug("STOP_CLIENTS: Clearing existing clients.")
        self._clients.clear()
        self._clients_started = False

    async def _create_clients(self) -> bool:
        """Create clients for the central unit. Start connection checker afterwards."""
        if len(self._clients) > 0:
            _LOGGER.warning(
                "CREATE_CLIENTS: Clients for %s are already created",
                self.name,
            )
            return False
        if len(self._config.enabled_interface_configs) == 0:
            _LOGGER.warning(
                "CREATE_CLIENTS failed: No Interfaces for %s defined",
                self.name,
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
                    _LOGGER.warning(
                        "CREATE_CLIENTS failed: Interface: %s is not available for backend %s",
                        interface_config.interface,
                        self.name,
                    )
                    interface_config.disable()
                    continue
                await self._create_client(interface_config=interface_config)

        if not self.all_clients_active:
            _LOGGER.warning(
                "CREATE_CLIENTS failed: Created %i of %i clients",
                len(self._clients),
                len(self._config.enabled_interface_configs),
            )
            return False

        if self.primary_client is None:
            _LOGGER.warning("CREATE_CLIENTS failed: No primary client identified for %s", self.name)
            return True

        _LOGGER.debug("CREATE_CLIENTS successful for %s", self.name)
        return True

    async def _create_client(self, interface_config: hmcl.InterfaceConfig) -> bool:
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
        except BaseHomematicException as ex:
            self.fire_interface_event(
                interface_id=interface_config.interface_id,
                interface_event_type=InterfaceEventType.PROXY,
                data={EventKey.AVAILABLE: False},
            )

            _LOGGER.warning(
                "CREATE_CLIENT failed: No connection to interface %s [%s]",
                interface_config.interface_id,
                reduce_args(args=ex.args),
            )
        return False

    async def _init_clients(self) -> None:
        """Init clients of control unit, and start connection checker."""
        for client in self._clients.copy().values():
            if client.interface not in self.system_information.available_interfaces:
                _LOGGER.debug(
                    "INIT_CLIENTS failed: Interface: %s is not available for backend %s",
                    client.interface,
                    self.name,
                )
                del self._clients[client.interface_id]
                continue
            if await client.initialize_proxy() == ProxyInitState.INIT_SUCCESS:
                _LOGGER.debug("INIT_CLIENTS: client %s initialized for %s", client.interface_id, self.name)

    async def _de_init_clients(self) -> None:
        """De-init clients."""
        for name, client in self._clients.items():
            if await client.deinitialize_proxy():
                _LOGGER.debug("DE_INIT_CLIENTS: Proxy de-initialized: %s", name)

    async def _init_hub(self) -> None:
        """Init the hub."""
        await self._hub.fetch_program_data(scheduled=True)
        await self._hub.fetch_sysvar_data(scheduled=True)

    @loop_check
    def fire_interface_event(
        self,
        interface_id: str,
        interface_event_type: InterfaceEventType,
        data: dict[str, Any],
    ) -> None:
        """Fire an event about the interface status."""
        data = data or {}
        event_data: dict[str, Any] = {
            EventKey.INTERFACE_ID: interface_id,
            EventKey.TYPE: interface_event_type,
            EventKey.DATA: data,
        }

        self.fire_homematic_callback(
            event_type=EventType.INTERFACE,
            event_data=cast(dict[EventKey, Any], INTERFACE_EVENT_SCHEMA(event_data)),
        )

    async def _identify_ip_addr(self, port: int) -> str:
        ip_addr: str | None = None
        while ip_addr is None:
            try:
                ip_addr = await self.looper.async_add_executor_job(
                    get_ip_addr, self._config.host, port, name="get_ip_addr"
                )
            except HaHomematicException:
                ip_addr = LOCAL_HOST
            if ip_addr is None:
                _LOGGER.warning("GET_IP_ADDR: Waiting for %i s,", CONNECTION_CHECKER_INTERVAL)
                await asyncio.sleep(TIMEOUT / 10)
        return ip_addr

    def _start_scheduler(self) -> None:
        """Start the scheduler."""
        _LOGGER.debug(
            "START_SCHEDULER: Starting scheduler for %s",
            self.name,
        )
        self._scheduler.start()

    def _stop_scheduler(self) -> None:
        """Start the connection checker."""
        self._scheduler.stop()
        _LOGGER.debug(
            "STOP_SCHEDULER: Stopped scheduler for %s",
            self.name,
        )

    async def validate_config_and_get_system_information(self) -> SystemInformation:
        """Validate the central configuration."""
        if len(self._config.enabled_interface_configs) == 0:
            raise NoClientsException("validate_config: No clients defined.")

        system_information = SystemInformation()
        for interface_config in self._config.enabled_interface_configs:
            try:
                client = await hmcl.create_client(central=self, interface_config=interface_config)
            except BaseHomematicException as ex:
                _LOGGER.error(
                    "VALIDATE_CONFIG_AND_GET_SYSTEM_INFORMATION failed for client %s: %s",
                    interface_config.interface,
                    reduce_args(args=ex.args),
                )
                raise
            if client.interface in PRIMARY_CLIENT_CANDIDATE_INTERFACES and not system_information.serial:
                system_information = client.system_information
        return system_information

    def get_client(self, interface_id: str) -> hmcl.Client:
        """Return a client by interface_id."""
        if not self.has_client(interface_id=interface_id):
            raise HaHomematicException(f"get_client: interface_id {interface_id} does not exist on {self.name}")
        return self._clients[interface_id]

    def get_channel(self, channel_address: str) -> Channel | None:
        """Return homematic channel."""
        if device := self.get_device(address=channel_address):
            return device.get_channel(channel_address=channel_address)
        return None

    def get_device(self, address: str) -> Device | None:
        """Return homematic device."""
        d_address = get_device_address(address=address)
        return self._devices.get(d_address)

    def get_data_point_by_custom_id(self, custom_id: str) -> CallbackDataPoint | None:
        """Return homematic data_point by custom_id."""
        for data_point in self.get_data_points(registered=True):
            if data_point.custom_id == custom_id:
                return data_point
        return None

    def get_data_points(
        self,
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

    def get_readable_generic_data_points(
        self, paramset_key: ParamsetKey | None = None, interface: Interface | None = None
    ) -> tuple[GenericDataPoint, ...]:
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

    def _get_primary_client(self) -> hmcl.Client | None:
        """Return the client by interface_id or the first with a virtual remote."""
        client: hmcl.Client | None = None
        for client in self._clients.values():
            if client.interface in PRIMARY_CLIENT_CANDIDATE_INTERFACES and client.available:
                return client
        return client

    def get_hub_data_points(
        self, category: DataPointCategory | None = None, registered: bool | None = None
    ) -> tuple[GenericHubDataPoint, ...]:
        """Return the program data points."""
        return tuple(
            he
            for he in (self.program_data_points + self.sysvar_data_points)
            if (category is None or he.category == category) and (registered is None or he.is_registered == registered)
        )

    def get_events(self, event_type: EventType, registered: bool | None = None) -> tuple[tuple[GenericEvent, ...], ...]:
        """Return all channel event data points."""
        hm_channel_events: list[tuple[GenericEvent, ...]] = []
        for device in self.devices:
            for channel_events in device.get_events(event_type=event_type).values():
                if registered is None or (channel_events[0].is_registered == registered):
                    hm_channel_events.append(channel_events)
                    continue
        return tuple(hm_channel_events)

    def get_virtual_remotes(self) -> tuple[Device, ...]:
        """Get the virtual remote for the Client."""
        return tuple(
            cl.get_virtual_remote()  # type: ignore[misc]
            for cl in self._clients.values()
            if cl.get_virtual_remote() is not None
        )

    def has_client(self, interface_id: str) -> bool:
        """Check if client exists in central."""
        return interface_id in self._clients

    @property
    def all_clients_active(self) -> bool:
        """Check if all configured clients exists in central."""
        count_client = len(self._clients)
        return count_client > 0 and count_client == len(self._config.enabled_interface_configs)

    @property
    def has_clients(self) -> bool:
        """Check if clients exists in central."""
        return len(self._clients) > 0

    async def _load_caches(self) -> bool:
        """Load files to caches."""
        if DataOperationResult.LOAD_FAIL in (
            await self._device_descriptions.load(),
            await self._paramset_descriptions.load(),
        ):
            _LOGGER.warning("LOAD_CACHES failed: Unable to load caches for %s. Clearing files", self.name)
            await self.clear_caches()
            return False
        await self._device_details.load()
        await self._data_cache.load()
        return True

    async def _create_devices(self, new_device_addresses: Mapping[str, set[str]]) -> None:
        """Trigger creation of the objects that expose the functionality."""
        if not self._clients:
            raise HaHomematicException(
                f"CREATE_DEVICES failed: No clients initialized. Not starting central {self.name}."
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
                except Exception as ex:  # pragma: no cover
                    _LOGGER.error(
                        "CREATE_DEVICES failed: %s [%s] Unable to create device: %s, %s",
                        type(ex).__name__,
                        reduce_args(args=ex.args),
                        interface_id,
                        device_address,
                    )
                try:
                    if device:
                        create_data_points_and_events(device=device)
                        create_custom_data_points(device=device)
                        await device.load_value_cache()
                        new_devices.add(device)
                        self._devices[device_address] = device
                except Exception as ex:  # pragma: no cover
                    _LOGGER.error(
                        "CREATE_DEVICES failed: %s [%s] Unable to create data points: %s, %s",
                        type(ex).__name__,
                        reduce_args(args=ex.args),
                        interface_id,
                        device_address,
                    )
        _LOGGER.debug("CREATE_DEVICES: Finished creating devices for %s", self.name)

        if new_devices:
            new_dps = _get_new_data_points(new_devices=new_devices)
            new_channel_events = _get_new_channel_events(new_devices=new_devices)
            self.fire_backend_system_callback(
                system_event=BackendSystemEvent.DEVICES_CREATED,
                new_data_points=new_dps,
                new_channel_events=new_channel_events,
            )

    async def delete_device(self, interface_id: str, device_address: str) -> None:
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
    async def delete_devices(self, interface_id: str, addresses: tuple[str, ...]) -> None:
        """Delete devices from central."""
        _LOGGER.debug(
            "DELETE_DEVICES: interface_id = %s, addresses = %s",
            interface_id,
            str(addresses),
        )
        for address in addresses:
            if device := self._devices.get(address):
                self.remove_device(device=device)
        await self.save_caches()

    @callback_backend_system(system_event=BackendSystemEvent.NEW_DEVICES)
    async def add_new_devices(self, interface_id: str, device_descriptions: tuple[DeviceDescription, ...]) -> None:
        """Add new devices to central unit."""
        await self._add_new_devices(interface_id=interface_id, device_descriptions=device_descriptions)

    @inspector(measure_performance=True)
    async def _add_new_devices(self, interface_id: str, device_descriptions: tuple[DeviceDescription, ...]) -> None:
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
            _LOGGER.warning(
                "ADD_NEW_DEVICES failed: Missing client for interface_id %s",
                interface_id,
            )
            return

        async with self._device_add_semaphore:
            # We need this to avoid adding duplicates.
            known_addresses = tuple(
                dev_desc["ADDRESS"]
                for dev_desc in self._device_descriptions.get_raw_device_descriptions(interface_id=interface_id)
            )
            client = self._clients[interface_id]
            save_paramset_descriptions = False
            save_device_descriptions = False
            for dev_desc in device_descriptions:
                try:
                    self._device_descriptions.add_device(interface_id=interface_id, device_description=dev_desc)
                    save_device_descriptions = True
                    if dev_desc["ADDRESS"] not in known_addresses:
                        await client.fetch_paramset_descriptions(device_description=dev_desc)
                        save_paramset_descriptions = True
                except Exception as ex:  # pragma: no cover
                    save_device_descriptions = False
                    save_paramset_descriptions = False
                    _LOGGER.error(
                        "ADD_NEW_DEVICES failed: %s [%s]",
                        type(ex).__name__,
                        reduce_args(args=ex.args),
                    )

            await self.save_caches(
                save_device_descriptions=save_device_descriptions,
                save_paramset_descriptions=save_paramset_descriptions,
            )
            if new_device_addresses := self._check_for_new_device_addresses():
                await self._device_details.load()
                await self._data_cache.load()
                await self._create_devices(new_device_addresses=new_device_addresses)

    def _check_for_new_device_addresses(self) -> Mapping[str, set[str]]:
        """Check if there are new devices, that needs to be created."""
        new_device_addresses: dict[str, set[str]] = {}
        for interface_id in self.interface_ids:
            if not self._paramset_descriptions.has_interface_id(interface_id=interface_id):
                _LOGGER.debug(
                    "CHECK_FOR_NEW_DEVICE_ADDRESSES: Skipping interface %s, missing paramsets",
                    interface_id,
                )
                continue

            if interface_id not in new_device_addresses:
                new_device_addresses[interface_id] = set()

            for device_address in self._device_descriptions.get_addresses(interface_id=interface_id):
                if device_address not in self._devices:
                    new_device_addresses[interface_id].add(device_address)

            if not new_device_addresses[interface_id]:
                del new_device_addresses[interface_id]

        if _LOGGER.isEnabledFor(level=DEBUG):
            count: int = 0
            for item in new_device_addresses.values():
                count += len(item)

            _LOGGER.debug(
                "CHECK_FOR_NEW_DEVICE_ADDRESSES: %s: %i.",
                "Found new device addresses" if new_device_addresses else "Did not find any new device addresses",
                count,
            )

        return new_device_addresses

    @callback_event
    async def data_point_event(self, interface_id: str, channel_address: str, parameter: str, value: Any) -> None:
        """If a device emits some sort event, we will handle it here."""
        _LOGGER.debug(
            "EVENT: interface_id = %s, channel_address = %s, parameter = %s, value = %s",
            interface_id,
            channel_address,
            parameter,
            str(value),
        )
        if not self.has_client(interface_id=interface_id):
            return

        self.set_last_event_dt(interface_id=interface_id)
        # No need to check the response of a XmlRPC-PING
        if parameter == Parameter.PONG:
            if "#" in value:
                v_interface_id, v_timestamp = value.split("#")
                if (
                    v_interface_id == interface_id
                    and (client := self.get_client(interface_id=interface_id))
                    and client.supports_ping_pong
                ):
                    client.ping_pong_cache.handle_received_pong(
                        pong_ts=datetime.strptime(v_timestamp, DATETIME_FORMAT_MILLIS)
                    )
            return

        dpk = DataPointKey(
            interface_id=interface_id,
            channel_address=channel_address,
            paramset_key=ParamsetKey.VALUES,
            parameter=parameter,
        )

        if dpk in self._data_point_key_event_subscriptions:
            try:
                for callback_handler in self._data_point_key_event_subscriptions[dpk]:
                    if callable(callback_handler):
                        await callback_handler(value)
            except RuntimeError as rte:  # pragma: no cover
                _LOGGER.debug(
                    "EVENT: RuntimeError [%s]. Failed to call callback for: %s, %s, %s",
                    reduce_args(args=rte.args),
                    interface_id,
                    channel_address,
                    parameter,
                )
            except Exception as ex:  # pragma: no cover
                _LOGGER.warning(
                    "EVENT failed: Unable to call callback for: %s, %s, %s, %s",
                    interface_id,
                    channel_address,
                    parameter,
                    reduce_args(args=ex.args),
                )

    def data_point_path_event(self, state_path: str, value: str) -> None:
        """If a device emits some sort event, we will handle it here."""
        _LOGGER.debug(
            "DATA_POINT_PATH_EVENT: topic = %s, payload = %s",
            state_path,
            value,
        )

        if (dpk := self._data_point_path_event_subscriptions.get(state_path)) is not None:
            self._looper.create_task(
                self.data_point_event(
                    interface_id=dpk.interface_id,
                    channel_address=dpk.channel_address,
                    parameter=dpk.parameter,
                    value=value,
                ),
                name=f"device-data-point-event-{dpk.interface_id}-{dpk.channel_address}-{dpk.parameter}",
            )

    def sysvar_data_point_path_event(self, state_path: str, value: str) -> None:
        """If a device emits some sort event, we will handle it here."""
        _LOGGER.debug(
            "SYSVAR_DATA_POINT_PATH_EVENT: topic = %s, payload = %s",
            state_path,
            value,
        )

        if state_path in self._sysvar_data_point_event_subscriptions:
            try:
                callback_handler = self._sysvar_data_point_event_subscriptions[state_path]
                if callable(callback_handler):
                    self._looper.create_task(callback_handler(value), name=f"sysvar-data-point-event-{state_path}")
            except RuntimeError as rte:  # pragma: no cover
                _LOGGER.debug(
                    "EVENT: RuntimeError [%s]. Failed to call callback for: %s",
                    reduce_args(args=rte.args),
                    state_path,
                )
            except Exception as ex:  # pragma: no cover
                _LOGGER.warning(
                    "EVENT failed: Unable to call callback for: %s, %s",
                    state_path,
                    reduce_args(args=ex.args),
                )

    @callback_backend_system(system_event=BackendSystemEvent.LIST_DEVICES)
    def list_devices(self, interface_id: str) -> list[DeviceDescription]:
        """Return already existing devices to CCU / Homegear."""
        result = self._device_descriptions.get_raw_device_descriptions(interface_id=interface_id)
        _LOGGER.debug("LIST_DEVICES: interface_id = %s, channel_count = %i", interface_id, len(result))
        return result

    def add_event_subscription(self, data_point: BaseParameterDataPoint) -> None:
        """Add data_point to central event subscription."""
        if isinstance(data_point, (GenericDataPoint, GenericEvent)) and (
            data_point.is_readable or data_point.supports_events
        ):
            if data_point.dpk not in self._data_point_key_event_subscriptions:
                self._data_point_key_event_subscriptions[data_point.dpk] = []
            self._data_point_key_event_subscriptions[data_point.dpk].append(data_point.event)
            if (
                not data_point.channel.device.client.supports_xml_rpc
                and data_point.state_path not in self._data_point_path_event_subscriptions
            ):
                self._data_point_path_event_subscriptions[data_point.state_path] = data_point.dpk

    @inspector()
    async def create_central_links(self) -> None:
        """Create a central links to support press events on all channels with click events."""
        for device in self.devices:
            await device.create_central_links()

    @inspector()
    async def remove_central_links(self) -> None:
        """Remove central links."""
        for device in self.devices:
            await device.remove_central_links()

    def remove_device(self, device: Device) -> None:
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

    def remove_event_subscription(self, data_point: BaseParameterDataPoint) -> None:
        """Remove event subscription from central collections."""
        if isinstance(data_point, (GenericDataPoint, GenericEvent)) and data_point.supports_events:
            if data_point.dpk in self._data_point_key_event_subscriptions:
                del self._data_point_key_event_subscriptions[data_point.dpk]
            if data_point.state_path in self._data_point_path_event_subscriptions:
                del self._data_point_path_event_subscriptions[data_point.state_path]

    def get_last_event_dt(self, interface_id: str) -> datetime | None:
        """Return the last event dt."""
        return self._last_events.get(interface_id)

    def set_last_event_dt(self, interface_id: str) -> None:
        """Set the last event dt."""
        self._last_events[interface_id] = datetime.now()

    async def execute_program(self, pid: str) -> bool:
        """Execute a program on CCU / Homegear."""
        if client := self.primary_client:
            return await client.execute_program(pid=pid)
        return False

    async def set_program_state(self, pid: str, state: bool) -> bool:
        """Execute a program on CCU / Homegear."""
        if client := self.primary_client:
            return await client.set_program_state(pid=pid, state=state)
        return False

    @inspector(re_raise=False)
    async def fetch_sysvar_data(self, scheduled: bool) -> None:
        """Fetch sysvar data for the hub."""
        await self._hub.fetch_sysvar_data(scheduled=scheduled)

    @inspector(re_raise=False)
    async def fetch_program_data(self, scheduled: bool) -> None:
        """Fetch program data for the hub."""
        await self._hub.fetch_program_data(scheduled=scheduled)

    @inspector(measure_performance=True)
    async def load_and_refresh_data_point_data(
        self,
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

    async def get_system_variable(self, legacy_name: str) -> Any | None:
        """Get system variable from CCU / Homegear."""
        if client := self.primary_client:
            return await client.get_system_variable(legacy_name)
        return None

    async def set_system_variable(self, legacy_name: str, value: Any) -> None:
        """Set variable value on CCU/Homegear."""
        if dp := self.get_sysvar_data_point(legacy_name=legacy_name):
            await dp.send_variable(value=value)
        else:
            _LOGGER.warning("Variable %s not found on %s", legacy_name, self.name)

    def get_parameters(
        self,
        paramset_key: ParamsetKey,
        operations: tuple[Operations, ...],
        full_format: bool = False,
        un_ignore_candidates_only: bool = False,
        use_channel_wildcard: bool = False,
    ) -> list[str]:
        """Return all parameters from VALUES paramset."""
        parameters: set[str] = set()
        for channels in self._paramset_descriptions.raw_paramset_descriptions.values():
            for channel_address in channels:
                model: str | None = None
                if full_format:
                    model = self._device_descriptions.get_model(
                        device_address=get_device_address(address=channel_address)
                    )
                for parameter, parameter_data in channels[channel_address].get(paramset_key, {}).items():
                    if all(parameter_data["OPERATIONS"] & operation for operation in operations):
                        if un_ignore_candidates_only and (
                            (
                                (
                                    dp := self.get_generic_data_point(
                                        channel_address=channel_address,
                                        parameter=parameter,
                                        paramset_key=paramset_key,
                                    )
                                )
                                and dp.enabled_default
                                and not dp.is_un_ignored
                            )
                            or parameter in IGNORE_FOR_UN_IGNORE_PARAMETERS
                        ):
                            continue

                        if not full_format:
                            parameters.add(parameter)
                            continue

                        channel = (
                            UN_IGNORE_WILDCARD if use_channel_wildcard else get_channel_no(address=channel_address)
                        )

                        full_parameter = f"{parameter}:{paramset_key}@{model}:"
                        if channel is not None:
                            full_parameter += str(channel)
                        parameters.add(full_parameter)

        return list(parameters)

    def _get_virtual_remote(self, device_address: str) -> Device | None:
        """Get the virtual remote for the Client."""
        for client in self._clients.values():
            virtual_remote = client.get_virtual_remote()
            if virtual_remote and virtual_remote.address == device_address:
                return virtual_remote
        return None

    def get_generic_data_point(
        self, channel_address: str, parameter: str, paramset_key: ParamsetKey | None = None
    ) -> GenericDataPoint | None:
        """Get data_point by channel_address and parameter."""
        if device := self.get_device(address=channel_address):
            return device.get_generic_data_point(
                channel_address=channel_address, parameter=parameter, paramset_key=paramset_key
            )
        return None

    def get_event(self, channel_address: str, parameter: str) -> GenericEvent | None:
        """Return the hm event."""
        if device := self.get_device(address=channel_address):
            return device.get_generic_event(channel_address=channel_address, parameter=parameter)
        return None

    def get_custom_data_point(self, address: str, channel_no: int) -> CustomDataPoint | None:
        """Return the hm custom_data_point."""
        if device := self.get_device(address=address):
            return device.get_custom_data_point(channel_no=channel_no)
        return None

    def get_sysvar_data_point(
        self, vid: str | None = None, legacy_name: str | None = None
    ) -> GenericSysvarDataPoint | None:
        """Return the sysvar data_point."""
        if vid and (sysvar := self._sysvar_data_points.get(vid)):
            return sysvar
        if legacy_name:
            for sysvar in self._sysvar_data_points.values():
                if sysvar.legacy_name == legacy_name:
                    return sysvar
        return None

    def get_program_data_point(self, pid: str | None = None, legacy_name: str | None = None) -> ProgramDpType | None:
        """Return the program data points."""
        if pid and (program := self._program_data_points.get(pid)):
            return program
        if legacy_name:
            for program in self._program_data_points.values():
                if legacy_name in (program.button.legacy_name, program.switch.legacy_name):
                    return program
        return None

    def get_data_point_path(self) -> tuple[str, ...]:
        """Return the registered state path."""
        return tuple(self._data_point_path_event_subscriptions)

    def get_sysvar_data_point_path(self) -> tuple[str, ...]:
        """Return the registered sysvar state path."""
        return tuple(self._sysvar_data_point_event_subscriptions)

    def get_un_ignore_candidates(self, include_master: bool = False) -> list[str]:
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

    async def clear_caches(self) -> None:
        """Clear all stored data."""
        await self._device_descriptions.clear()
        await self._paramset_descriptions.clear()
        self._device_details.clear()
        self._data_cache.clear()

    def register_homematic_callback(self, cb: Callable) -> CALLBACK_TYPE:
        """Register ha_event callback in central."""
        if callable(cb) and cb not in self._homematic_callbacks:
            self._homematic_callbacks.add(cb)
            return partial(self._unregister_homematic_callback, cb=cb)
        return None

    def _unregister_homematic_callback(self, cb: Callable) -> None:
        """RUn register ha_event callback in central."""
        if cb in self._homematic_callbacks:
            self._homematic_callbacks.remove(cb)

    @loop_check
    def fire_homematic_callback(self, event_type: EventType, event_data: dict[EventKey, str]) -> None:
        """
        Fire homematic_callback in central.

        # Events like INTERFACE, KEYPRESS, ...
        """
        for callback_handler in self._homematic_callbacks:
            try:
                callback_handler(event_type, event_data)
            except Exception as ex:
                _LOGGER.error(
                    "FIRE_HOMEMATIC_CALLBACK: Unable to call handler: %s",
                    reduce_args(args=ex.args),
                )

    def register_backend_parameter_callback(self, cb: Callable) -> CALLBACK_TYPE:
        """Register backend_parameter callback in central."""
        if callable(cb) and cb not in self._backend_parameter_callbacks:
            self._backend_parameter_callbacks.add(cb)
            return partial(self._unregister_backend_parameter_callback, cb=cb)
        return None

    def _unregister_backend_parameter_callback(self, cb: Callable) -> None:
        """Un register backend_parameter callback in central."""
        if cb in self._backend_parameter_callbacks:
            self._backend_parameter_callbacks.remove(cb)

    @loop_check
    def fire_backend_parameter_callback(
        self, interface_id: str, channel_address: str, parameter: str, value: Any
    ) -> None:
        """
        Fire backend_parameter callback in central.

        Re-Fired events from CCU for parameter updates.
        """
        for callback_handler in self._backend_parameter_callbacks:
            try:
                callback_handler(interface_id, channel_address, parameter, value)
            except Exception as ex:
                _LOGGER.error(
                    "FIRE_BACKEND_PARAMETER_CALLBACK: Unable to call handler: %s",
                    reduce_args(args=ex.args),
                )

    def register_backend_system_callback(self, cb: Callable) -> CALLBACK_TYPE:
        """Register system_event callback in central."""
        if callable(cb) and cb not in self._backend_parameter_callbacks:
            self._backend_system_callbacks.add(cb)
            return partial(self._unregister_backend_system_callback, cb=cb)
        return None

    def _unregister_backend_system_callback(self, cb: Callable) -> None:
        """Un register system_event callback in central."""
        if cb in self._backend_system_callbacks:
            self._backend_system_callbacks.remove(cb)

    @loop_check
    def fire_backend_system_callback(self, system_event: BackendSystemEvent, **kwargs: Any) -> None:
        """
        Fire system_event callback in central.

        e.g. DEVICES_CREATED, HUB_REFRESHED
        """
        for callback_handler in self._backend_system_callbacks:
            try:
                callback_handler(system_event, **kwargs)
            except Exception as ex:
                _LOGGER.error(
                    "FIRE_BACKEND_SYSTEM_CALLBACK: Unable to call handler: %s",
                    reduce_args(args=ex.args),
                )

    def __str__(self) -> str:
        """Provide some useful information."""
        return f"central: {self.name}"


class _Scheduler(threading.Thread):
    """Periodically check connection to CCU / Homegear, and load data when required."""

    def __init__(self, central: CentralUnit) -> None:
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

    def _backend_system_callback(self, system_event: BackendSystemEvent, **kwargs: Any) -> None:
        """Handle event of new device creation, to delay the start of the sysvar scan."""
        if system_event == BackendSystemEvent.DEVICES_CREATED:
            self._devices_created = True

    def run(self) -> None:
        """Run the scheduler thread."""
        _LOGGER.debug(
            "run: scheduler for %s",
            self._central.name,
        )

        self._central.looper.create_task(
            self._run_scheduler_tasks(),
            name="run_scheduler_tasks",
        )

    def stop(self) -> None:
        """To stop the ConnectionChecker."""
        if self._unregister_callback is not None:
            self._unregister_callback()
        self._active = False

    async def _run_scheduler_tasks(self) -> None:
        """Run all tasks."""
        while self._active:
            if not self._central.started:
                _LOGGER.debug("SCHEDULER: Waiting till central %s is started", self._central.name)
                await asyncio.sleep(10)
                continue
            for job in self._scheduler_jobs:
                if not self._active or not job.ready:
                    continue
                await job.run()
                job.schedule_next_execution()
            if self._active:
                await asyncio.sleep(5)

    async def _check_connection(self) -> None:
        """Check connection to backend."""
        _LOGGER.debug("CHECK_CONNECTION: Checking connection to server %s", self._central.name)
        try:
            if not self._central.all_clients_active:
                _LOGGER.warning(
                    "CHECK_CONNECTION failed: No clients exist. Trying to create clients for server %s",
                    self._central.name,
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
            _LOGGER.error("CHECK_CONNECTION failed: no connection: %s", reduce_args(args=nex.args))
        except Exception as ex:
            _LOGGER.error(
                "CHECK_CONNECTION failed: %s [%s]",
                type(ex).__name__,
                reduce_args(args=ex.args),
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
                self._central.set_last_event_dt(interface_id=client.interface_id)

    @inspector(re_raise=False)
    async def _refresh_sysvar_data(self) -> None:
        """Refresh system variables."""
        if not self._central.config.enable_sysvar_scan or not self._central.available or not self._devices_created:
            return

        _LOGGER.debug("REFRESH_SYSVAR_DATA: For %s", self._central.name)
        await self._central.fetch_sysvar_data(scheduled=True)

    @inspector(re_raise=False)
    async def _refresh_program_data(self) -> None:
        """Refresh system program_data."""
        if not self._central.config.enable_program_scan or not self._central.available or not self._devices_created:
            return

        _LOGGER.debug("REFRESH_PROGRAM_DATA: For %s", self._central.name)
        await self._central.fetch_program_data(scheduled=True)

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


class _SchedulerJob:
    """Job to run in the scheduler."""

    def __init__(
        self,
        task: Callable,
        run_interval: int,
        next_run: datetime = datetime.now(),
    ):
        """Init the job."""
        self._task: Final = task
        self._next_run = next_run
        self._run_interval: Final = run_interval

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
        central_id: str,
        default_callback_port: int,
        host: str,
        interface_configs: AbstractSet[hmcl.InterfaceConfig],
        name: str,
        password: str,
        storage_folder: str,
        username: str,
        client_session: ClientSession | None = None,
        callback_host: str | None = None,
        callback_port: int | None = None,
        enable_device_firmware_check: bool = DEFAULT_ENABLE_DEVICE_FIRMWARE_CHECK,
        enable_program_scan: bool = DEFAULT_ENABLE_PROGRAM_SCAN,
        enable_sysvar_scan: bool = DEFAULT_ENABLE_SYSVAR_SCAN,
        hm_master_poll_after_send_intervals: tuple[int, ...] = DEFAULT_HM_MASTER_POLL_AFTER_SEND_INTERVALS,
        ignore_custom_device_definition_models: tuple[str, ...] = DEFAULT_IGNORE_CUSTOM_DEVICE_DEFINITION_MODELS,
        interfaces_requiring_periodic_refresh: tuple[Interface, ...] = INTERFACES_REQUIRING_PERIODIC_REFRESH,
        json_port: int | None = None,
        listen_ip_addr: str | None = None,
        listen_port: int | None = None,
        max_read_workers: int = DEFAULT_MAX_READ_WORKERS,
        periodic_refresh_interval: int = DEFAULT_PERIODIC_REFRESH_INTERVAL,
        program_markers: tuple[DescriptionMarker | str, ...] = DEFAULT_PROGRAM_MARKERS,
        start_direct: bool = False,
        sys_scan_interval: int = DEFAULT_SYS_SCAN_INTERVAL,
        sysvar_markers: tuple[DescriptionMarker | str, ...] = DEFAULT_SYSVAR_MARKERS,
        tls: bool = DEFAULT_TLS,
        un_ignore_list: tuple[str, ...] = DEFAULT_UN_IGNORES,
        verify_tls: bool = DEFAULT_VERIFY_TLS,
    ) -> None:
        """Init the client config."""
        self._interface_configs: Final = interface_configs
        self.callback_host: Final = callback_host
        self.callback_port: Final = callback_port
        self.central_id: Final = central_id
        self.client_session: Final = client_session
        self.default_callback_port: Final = default_callback_port
        self.enable_device_firmware_check: Final = enable_device_firmware_check
        self.enable_program_scan: Final = enable_program_scan
        self.enable_sysvar_scan: Final = enable_sysvar_scan
        self.hm_master_poll_after_send_intervals: Final = hm_master_poll_after_send_intervals
        self.host: Final = host
        self.ignore_custom_device_definition_models: Final = ignore_custom_device_definition_models
        self.interfaces_requiring_periodic_refresh: Final = interfaces_requiring_periodic_refresh
        self.json_port: Final = json_port
        self.listen_ip_addr: Final = listen_ip_addr
        self.listen_port: Final = listen_port
        self.max_read_workers = max_read_workers
        self.name: Final = name
        self.password: Final = password
        self.periodic_refresh_interval = periodic_refresh_interval
        self.program_markers: Final = program_markers
        self.start_direct: Final = start_direct
        self.storage_folder: Final = storage_folder
        self.sys_scan_interval: Final = sys_scan_interval
        self.sysvar_markers: Final = sysvar_markers
        self.tls: Final = tls
        self.un_ignore_list: Final = un_ignore_list
        self.username: Final = username
        self.verify_tls: Final = verify_tls

    @property
    def enable_server(self) -> bool:
        """Return if server and connection checker should be started."""
        return self.start_direct is False

    @property
    def load_un_ignore(self) -> bool:
        """Return if un_ignore should be loaded."""
        return self.start_direct is False

    @property
    def connection_check_port(self) -> int:
        """Return the connection check port."""
        if used_ports := tuple(ic.port for ic in self._interface_configs if ic.port is not None):
            return used_ports[0]
        if self.json_port:
            return self.json_port
        return 443 if self.tls else 80

    @property
    def enabled_interface_configs(self) -> tuple[hmcl.InterfaceConfig, ...]:
        """Return the interface configs."""
        return tuple(ic for ic in self._interface_configs if ic.enabled is True)

    @property
    def use_caches(self) -> bool:
        """Return if caches should be used."""
        return self.start_direct is False

    def check_config(self) -> None:
        """Check config. Throws BaseHomematicException on failure."""
        if config_failures := check_config(
            central_name=self.name,
            host=self.host,
            username=self.username,
            password=self.password,
            storage_folder=self.storage_folder,
            callback_host=self.callback_host,
            callback_port=self.callback_port,
            json_port=self.json_port,
            interface_configs=self._interface_configs,
        ):
            failures = ", ".join(config_failures)
            raise HaHomematicConfigException(failures)

    def create_central(self) -> CentralUnit:
        """Create the central. Throws BaseHomematicException on validation failure."""
        try:
            self.check_config()
            return CentralUnit(self)
        except BaseHomematicException as ex:
            raise HaHomematicException(
                f"CREATE_CENTRAL: Not able to create a central: : {reduce_args(args=ex.args)}"
            ) from ex

    def create_central_url(self) -> str:
        """Return the required url."""
        url = "https://" if self.tls else "http://"
        url = f"{url}{self.host}"
        if self.json_port:
            url = f"{url}:{self.json_port}"
        return f"{url}"

    def create_json_rpc_client(self, central: CentralUnit) -> JsonRpcAioHttpClient:
        """Create a json rpc client."""
        return JsonRpcAioHttpClient(
            username=self.username,
            password=self.password,
            device_url=central.url,
            connection_state=central.connection_state,
            client_session=self.client_session,
            tls=self.tls,
            verify_tls=self.verify_tls,
        )


class CentralConnectionState:
    """The central connection status."""

    def __init__(self) -> None:
        """Init the CentralConnectionStatus."""
        self._json_issues: Final[list[str]] = []
        self._xml_proxy_issues: Final[list[str]] = []

    def add_issue(self, issuer: ConnectionProblemIssuer, iid: str) -> bool:
        """Add issue to collection."""
        if isinstance(issuer, JsonRpcAioHttpClient) and iid not in self._json_issues:
            self._json_issues.append(iid)
            _LOGGER.debug("add_issue: add issue  [%s] for JsonRpcAioHttpClient", iid)
            return True
        if isinstance(issuer, XmlRpcProxy) and iid not in self._xml_proxy_issues:
            self._xml_proxy_issues.append(iid)
            _LOGGER.debug("add_issue: add issue [%s] for %s", iid, issuer.interface_id)
            return True
        return False

    def remove_issue(self, issuer: ConnectionProblemIssuer, iid: str) -> bool:
        """Add issue to collection."""
        if isinstance(issuer, JsonRpcAioHttpClient) and iid in self._json_issues:
            self._json_issues.remove(iid)
            _LOGGER.debug("remove_issue: removing issue [%s] for JsonRpcAioHttpClient", iid)
            return True
        if isinstance(issuer, XmlRpcProxy) and issuer.interface_id in self._xml_proxy_issues:
            self._xml_proxy_issues.remove(iid)
            _LOGGER.debug("remove_issue: removing issue [%s] for %s", iid, issuer.interface_id)
            return True
        return False

    def has_issue(self, issuer: ConnectionProblemIssuer, iid: str) -> bool:
        """Add issue to collection."""
        if isinstance(issuer, JsonRpcAioHttpClient):
            return iid in self._json_issues
        if isinstance(issuer, XmlRpcProxy):
            return iid in self._xml_proxy_issues

    def handle_exception_log(
        self,
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
                reduce_args(args=exception.args),
                extra_msg,
            )
        else:
            self.add_issue(issuer=issuer, iid=iid)
            logger.log(
                level,
                "%s failed: %s [%s] %s",
                iid,
                exception_name,
                reduce_args(args=exception.args),
                extra_msg,
            )


def _get_new_data_points(
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


def _get_new_channel_events(new_devices: set[Device]) -> tuple[tuple[GenericEvent, ...], ...]:
    """Return new channel events by category."""
    channel_events: list[tuple[GenericEvent, ...]] = []

    for device in new_devices:
        for event_type in DATA_POINT_EVENTS:
            if (hm_channel_events := list(device.get_events(event_type=event_type, registered=False).values())) and len(
                hm_channel_events
            ) > 0:
                channel_events.append(hm_channel_events)  # type: ignore[arg-type] # noqa:PERF401

    return tuple(channel_events)
