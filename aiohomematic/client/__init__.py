# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Client adapters for communicating with Homematic CCU and compatible backends.

Overview
--------
This package provides client implementations that abstract the transport details of
Homematic backends (e.g., CCU via JSON-RPC/XML-RPC or Homegear) and expose a
consistent API used by the central module.

Provided clients
----------------
- Client: Abstract base with common logic for parameter access, metadata retrieval,
  connection checks, and firmware support detection.
- ClientCCU: Concrete client for CCU-compatible backends using XML-RPC for write/reads
  and optional JSON-RPC for rich metadata and sysvar/program access.
- ClientJsonCCU: Specialization of ClientCCU that prefers JSON-RPC endpoints for
  reads/writes and metadata.
- ClientHomegear: Client for Homegear using XML-RPC.

Key responsibilities
--------------------
- Initialize and manage transport proxies (XmlRpcProxy, JsonRpcAioHttpClient)
- Read/write data point values and paramsets
- Fetch device, channel, and parameter descriptions
- Track connection health and implement ping/pong where supported
- Provide program and system variable access (where supported)

Quick start
-----------
Create a client via create_client using an InterfaceConfig and a CentralUnit:

    from aiohomematic import client as hmcl

    iface_cfg = hmcl.InterfaceConfig(central_name="ccu-main", interface=hmcl.Interface.HMIP, port=2010)
    client = hmcl.create_client(central, iface_cfg)
    await client.init_client()
    # ... use client.get_value(...), client.set_value(...), etc.

Notes
-----
- Most users interact with clients via the CentralUnit. Direct usage is possible for
  advanced scenarios.
- XML-RPC support depends on the interface; JSON-RPC is only available on CCU backends.

"""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from datetime import datetime
import logging
from typing import Any, Final, cast

from aiohomematic import central as hmcu, i18n
from aiohomematic.client.json_rpc import AioJsonRpcAioHttpClient
from aiohomematic.client.rpc_proxy import AioXmlRpcProxy, BaseRpcProxy
from aiohomematic.const import (
    CALLBACK_WARN_INTERVAL,
    DATETIME_FORMAT_MILLIS,
    DEFAULT_MAX_WORKERS,
    DP_KEY_VALUE,
    DUMMY_SERIAL,
    INIT_DATETIME,
    INTERFACE_RPC_SERVER_TYPE,
    INTERFACES_REQUIRING_JSON_RPC_CLIENT,
    INTERFACES_SUPPORTING_FIRMWARE_UPDATES,
    INTERFACES_SUPPORTING_RPC_CALLBACK,
    LINKABLE_INTERFACES,
    RECONNECT_WAIT,
    VIRTUAL_REMOTE_MODELS,
    WAIT_FOR_CALLBACK,
    Backend,
    CallSource,
    CommandRxMode,
    DescriptionMarker,
    DeviceDescription,
    EventKey,
    ForcedDeviceAvailability,
    Interface,
    InterfaceEventType,
    InternalCustomID,
    Operations,
    ParameterData,
    ParameterType,
    ParamsetKey,
    ProductGroup,
    ProgramData,
    ProxyInitState,
    RpcServerType,
    SystemInformation,
    SystemVariableData,
)
from aiohomematic.decorators import inspector, measure_execution_time
from aiohomematic.exceptions import BaseHomematicException, ClientException, NoConnectionException
from aiohomematic.model.device import Device
from aiohomematic.model.support import convert_value
from aiohomematic.property_decorators import hm_property
from aiohomematic.store import CommandCache, PingPongCache
from aiohomematic.support import (
    LogContextMixin,
    build_xml_rpc_headers,
    build_xml_rpc_uri,
    extract_exc_args,
    get_device_address,
    is_channel_address,
    is_paramset_key,
    supports_rx_mode,
)

__all__ = [
    "AioJsonRpcAioHttpClient",
    "BaseRpcProxy",
    "Client",
    "InterfaceConfig",
    "ClientConfig",
]

_LOGGER: Final = logging.getLogger(__name__)

_JSON_ADDRESS: Final = "address"
_JSON_CHANNELS: Final = "channels"
_JSON_ID: Final = "id"
_JSON_INTERFACE: Final = "interface"
_JSON_NAME: Final = "name"
_NAME: Final = "NAME"

_CCU_JSON_VALUE_TYPE: Final = {
    "ACTION": "bool",
    "BOOL": "bool",
    "ENUM": "list",
    "FLOAT": "double",
    "INTEGER": "int",
    "STRING": "string",
}


class Client(ABC, LogContextMixin):
    """Client object to access the backends via XML-RPC or JSON-RPC."""

    def __init__(self, *, client_config: ClientConfig) -> None:
        """Initialize the Client."""
        self._config: Final = client_config
        self._last_value_send_cache = CommandCache(interface_id=client_config.interface_id)
        self._available: bool = True
        self._connection_error_count: int = 0
        self._is_callback_alive: bool = True
        self._is_initialized: bool = False
        self._is_linkable: bool = client_config.interface in LINKABLE_INTERFACES
        self._ping_pong_cache: Final = PingPongCache(
            central=client_config.central, interface_id=client_config.interface_id
        )
        self._proxy: BaseRpcProxy
        self._proxy_read: BaseRpcProxy
        self._system_information: SystemInformation
        self.modified_at: datetime = INIT_DATETIME

    def __str__(self) -> str:
        """Provide some useful information."""
        return f"interface_id: {self.interface_id}"

    @property
    def available(self) -> bool:
        """Return the availability of the client."""
        return self._available

    @property
    def central(self) -> hmcu.CentralUnit:
        """Return the central of the client."""
        return self._config.central

    @property
    def interface(self) -> Interface:
        """Return the interface of the client."""
        return self._config.interface

    @property
    def is_initialized(self) -> bool:
        """Return if interface is initialized."""
        return self._is_initialized

    @property
    def last_value_send_cache(self) -> CommandCache:
        """Return the last value send cache."""
        return self._last_value_send_cache

    @property
    @abstractmethod
    def model(self) -> str:
        """Return the model of the backend."""

    @property
    def ping_pong_cache(self) -> PingPongCache:
        """Return the ping pong cache."""
        return self._ping_pong_cache

    @property
    def supports_firmware_updates(self) -> bool:
        """Return the supports_ping_pong info of the backend."""
        return self._config.supports_firmware_updates

    @property
    def supports_ping_pong(self) -> bool:
        """Return the supports_ping_pong info of the backend."""
        return self.interface in INTERFACES_SUPPORTING_RPC_CALLBACK

    @property
    def supports_push_updates(self) -> bool:
        """Return the client supports push update."""
        return self._config.supports_push_updates

    @property
    def supports_rpc_callback(self) -> bool:
        """Return if interface support rpc callback."""
        return self._config.supports_rpc_callback

    @property
    def system_information(self) -> SystemInformation:
        """Return the system_information of the client."""
        return self._system_information

    @property
    def version(self) -> str:
        """Return the version id of the client."""
        return self._config.version

    @hm_property(log_context=True)
    def interface_id(self) -> str:
        """Return the interface id of the client."""
        return self._config.interface_id

    @inspector
    async def add_link(self, *, sender_address: str, receiver_address: str, name: str, description: str) -> None:
        """Return a list of links."""
        if not self._is_linkable:
            _LOGGER.debug("ADD_LINK: interface %s is not linkable", self.interface_id)
            return
        try:
            await self._proxy.addLink(sender_address, receiver_address, name, description)
        except BaseHomematicException as bhexc:
            raise ClientException(
                i18n.tr(
                    "exception.client.add_link.failed",
                    sender=sender_address,
                    receiver=receiver_address,
                    name=name,
                    description=description,
                    reason=extract_exc_args(exc=bhexc),
                )
            ) from bhexc

    @abstractmethod
    @inspector(re_raise=False, no_raise_return=False)
    async def check_connection_availability(self, *, handle_ping_pong: bool) -> bool:
        """Send ping to the backend to generate PONG event."""

    async def deinitialize_proxy(self) -> ProxyInitState:
        """De-init to stop the backend from sending events for this remote."""
        if not self.supports_rpc_callback:
            return ProxyInitState.DE_INIT_SUCCESS

        if self.modified_at == INIT_DATETIME:
            _LOGGER.debug(
                "PROXY_DE_INIT: Skipping de-init for %s (not initialized)",
                self.interface_id,
            )
            return ProxyInitState.DE_INIT_SKIPPED
        try:
            _LOGGER.debug("PROXY_DE_INIT: init('%s')", self._config.init_url)
            await self._proxy.init(self._config.init_url)
            self._is_initialized = False
        except BaseHomematicException as bhexc:
            _LOGGER.warning(  # i18n-log: ignore
                "PROXY_DE_INIT failed: %s [%s] Unable to de-initialize proxy for %s",
                bhexc.name,
                extract_exc_args(exc=bhexc),
                self.interface_id,
            )
            return ProxyInitState.DE_INIT_FAILED

        self.modified_at = INIT_DATETIME
        return ProxyInitState.DE_INIT_SUCCESS

    @abstractmethod
    @inspector
    async def delete_system_variable(self, *, name: str) -> bool:
        """Delete a system variable from the backend."""

    @inspector
    async def execute_program(self, *, pid: str) -> bool:  # pragma: no cover
        """Execute a program on the backend."""
        _LOGGER.debug("EXECUTE_PROGRAM: not usable for %s.", self.interface_id)
        return True

    @abstractmethod
    @inspector(re_raise=False, measure_performance=True)
    async def fetch_all_device_data(self) -> None:
        """Fetch all device data from the backend."""

    @abstractmethod
    @inspector(re_raise=False, measure_performance=True)
    async def fetch_device_details(self) -> None:
        """Fetch names from the backend."""

    @inspector(re_raise=False)
    async def fetch_paramset_description(self, *, channel_address: str, paramset_key: ParamsetKey) -> None:
        """Fetch a specific paramset and add it to the known ones."""
        _LOGGER.debug("FETCH_PARAMSET_DESCRIPTION: %s for %s", paramset_key, channel_address)

        if paramset_description := await self._get_paramset_description(
            address=channel_address, paramset_key=paramset_key
        ):
            self.central.paramset_descriptions.add(
                interface_id=self.interface_id,
                channel_address=channel_address,
                paramset_key=paramset_key,
                paramset_description=paramset_description,
            )

    @inspector(re_raise=False)
    async def fetch_paramset_descriptions(self, *, device_description: DeviceDescription) -> None:
        """Fetch paramsets for provided device description."""
        data = await self.get_paramset_descriptions(device_description=device_description)
        for address, paramsets in data.items():
            _LOGGER.debug("FETCH_PARAMSET_DESCRIPTIONS for %s", address)
            for paramset_key, paramset_description in paramsets.items():
                self.central.paramset_descriptions.add(
                    interface_id=self.interface_id,
                    channel_address=address,
                    paramset_key=paramset_key,
                    paramset_description=paramset_description,
                )

    @inspector(re_raise=False)
    async def get_all_device_descriptions(self, *, device_address: str) -> tuple[DeviceDescription, ...]:
        """Get all device descriptions from the backend."""
        all_device_description: list[DeviceDescription] = []
        if main_dd := await self.get_device_description(device_address=device_address):
            all_device_description.append(main_dd)
        else:
            _LOGGER.warning(  # i18n-log: ignore
                "GET_ALL_DEVICE_DESCRIPTIONS: No device description for %s",
                device_address,
            )

        if main_dd:
            for channel_address in main_dd["CHILDREN"]:
                if channel_dd := await self.get_device_description(device_address=channel_address):
                    all_device_description.append(channel_dd)
                else:
                    _LOGGER.warning(  # i18n-log: ignore
                        "GET_ALL_DEVICE_DESCRIPTIONS: No channel description for %s",
                        channel_address,
                    )
        return tuple(all_device_description)

    @inspector(re_raise=False, no_raise_return={})
    async def get_all_functions(self) -> dict[str, set[str]]:  # pragma: no cover
        """Get all functions, if available."""
        _LOGGER.debug("GET_ALL_FUNCTIONS: not usable for %s.", self.interface_id)
        return {}

    @inspector
    async def get_all_paramset_descriptions(
        self, *, device_descriptions: tuple[DeviceDescription, ...]
    ) -> dict[str, dict[ParamsetKey, dict[str, ParameterData]]]:
        """Get all paramset descriptions for provided device descriptions."""
        all_paramsets: dict[str, dict[ParamsetKey, dict[str, ParameterData]]] = {}
        for device_description in device_descriptions:
            all_paramsets.update(await self.get_paramset_descriptions(device_description=device_description))
        return all_paramsets

    @inspector(re_raise=False)
    async def get_all_programs(
        self, *, markers: tuple[DescriptionMarker | str, ...]
    ) -> tuple[ProgramData, ...] | None:  # pragma: no cover
        """Get all programs, if available."""
        _LOGGER.debug("GET_ALL_PROGRAMS: not usable for %s.", self.interface_id)
        return None

    @inspector(re_raise=False, no_raise_return={})
    async def get_all_rooms(self) -> dict[str, set[str]]:  # pragma: no cover
        """Get all rooms, if available."""
        _LOGGER.debug("GET_ALL_ROOMS: not usable for %s.", self.interface_id)
        return {}

    @abstractmethod
    @inspector(re_raise=False)
    async def get_all_system_variables(
        self, *, markers: tuple[DescriptionMarker | str, ...]
    ) -> tuple[SystemVariableData, ...] | None:
        """Get all system variables from the backend."""

    @inspector(re_raise=False)
    async def get_device_description(self, *, device_address: str) -> DeviceDescription | None:
        """Get device descriptions from the backend."""
        try:
            if device_description := cast(
                DeviceDescription | None,
                await self._proxy_read.getDeviceDescription(device_address),
            ):
                return device_description
        except BaseHomematicException as bhexc:
            _LOGGER.warning(  # i18n-log: ignore
                "GET_DEVICE_DESCRIPTIONS failed: %s [%s]", bhexc.name, extract_exc_args(exc=bhexc)
            )
        return None

    @inspector
    async def get_link_peers(self, *, address: str) -> tuple[str, ...]:
        """Return a list of link pers."""
        if not self._is_linkable:
            _LOGGER.debug("GET_LINK_PEERS: interface %s is not linkable", self.interface_id)
            return ()
        try:
            return tuple(links) if (links := await self._proxy.getLinkPeers(address)) else ()
        except BaseHomematicException as bhexc:
            raise ClientException(
                i18n.tr("exception.client.get_link_peers.failed", address=address, reason=extract_exc_args(exc=bhexc))
            ) from bhexc

    @inspector
    async def get_links(self, *, address: str, flags: int) -> dict[str, Any]:
        """Return a list of links."""
        if not self._is_linkable:
            _LOGGER.debug("GET_LINKS: interface %s is not linkable", self.interface_id)
            return {}
        try:
            return cast(dict[str, Any], await self._proxy.getLinks(address, flags))
        except BaseHomematicException as bhexc:
            raise ClientException(
                i18n.tr("exception.client.get_links.failed", address=address, reason=extract_exc_args(exc=bhexc))
            ) from bhexc

    @inspector
    async def get_metadata(self, *, address: str, data_id: str) -> dict[str, Any]:
        """Return the metadata for an object."""
        try:
            return cast(dict[str, Any], await self._proxy.getMetadata(address, data_id))
        except BaseHomematicException as bhexc:
            raise ClientException(
                i18n.tr(
                    "exception.client.get_metadata.failed",
                    address=address,
                    data_id=data_id,
                    reason=extract_exc_args(exc=bhexc),
                )
            ) from bhexc

    @inspector
    async def get_paramset(
        self,
        *,
        address: str,
        paramset_key: ParamsetKey | str,
        call_source: CallSource = CallSource.MANUAL_OR_SCHEDULED,
    ) -> dict[str, Any]:
        """
        Return a paramset from the backend.

        Address is usually the channel_address,
        but for bidcos devices there is a master paramset at the device.
        """
        try:
            _LOGGER.debug(
                "GET_PARAMSET: address %s, paramset_key %s, source %s",
                address,
                paramset_key,
                call_source,
            )
            return cast(dict[str, Any], await self._proxy_read.getParamset(address, paramset_key))
        except BaseHomematicException as bhexc:  # pragma: no cover
            raise ClientException(
                i18n.tr(
                    "exception.client.get_paramset.failed",
                    address=address,
                    paramset_key=paramset_key,
                    reason=extract_exc_args(exc=bhexc),
                )
            ) from bhexc

    @inspector(re_raise=False, no_raise_return={})
    async def get_paramset_descriptions(
        self, *, device_description: DeviceDescription
    ) -> dict[str, dict[ParamsetKey, dict[str, ParameterData]]]:
        """Get paramsets for provided device description."""
        paramsets: dict[str, dict[ParamsetKey, dict[str, ParameterData]]] = {}
        address = device_description["ADDRESS"]
        paramsets[address] = {}
        _LOGGER.debug("GET_PARAMSET_DESCRIPTIONS for %s", address)
        for p_key in device_description["PARAMSETS"]:
            paramset_key = ParamsetKey(p_key)
            if paramset_description := await self._get_paramset_description(address=address, paramset_key=paramset_key):
                paramsets[address][paramset_key] = paramset_description
        return paramsets

    def get_product_group(self, *, model: str) -> ProductGroup:
        """Return the product group."""
        l_model = model.lower()
        if l_model.startswith("hmipw-"):
            return ProductGroup.HMIPW
        if l_model.startswith("hmip-"):
            return ProductGroup.HMIP
        if l_model.startswith("hmw-"):
            return ProductGroup.HMW
        if l_model.startswith("hm-"):
            return ProductGroup.HM
        if self.interface == Interface.HMIP_RF:
            return ProductGroup.HMIP
        if self.interface == Interface.BIDCOS_WIRED:
            return ProductGroup.HMW
        if self.interface == Interface.BIDCOS_RF:
            return ProductGroup.HM
        if self.interface == Interface.VIRTUAL_DEVICES:
            return ProductGroup.VIRTUAL
        return ProductGroup.UNKNOWN

    @abstractmethod
    @inspector
    async def get_system_variable(self, *, name: str) -> Any:
        """Get single system variable from the backend."""

    @inspector(log_level=logging.NOTSET)
    async def get_value(
        self,
        *,
        channel_address: str,
        paramset_key: ParamsetKey,
        parameter: str,
        call_source: CallSource = CallSource.MANUAL_OR_SCHEDULED,
    ) -> Any:
        """Return a value from the backend."""
        try:
            _LOGGER.debug(
                "GET_VALUE: channel_address %s, parameter %s, paramset_key, %s, source:%s",
                channel_address,
                parameter,
                paramset_key,
                call_source,
            )
            if paramset_key == ParamsetKey.VALUES:
                return await self._proxy_read.getValue(channel_address, parameter)
            paramset = await self._proxy_read.getParamset(channel_address, ParamsetKey.MASTER) or {}
            return paramset.get(parameter)
        except BaseHomematicException as bhexc:
            raise ClientException(
                i18n.tr(
                    "exception.client.get_value.failed",
                    channel_address=channel_address,
                    parameter=parameter,
                    paramset_key=paramset_key,
                    reason=extract_exc_args(exc=bhexc),
                )
            ) from bhexc

    def get_virtual_remote(self) -> Device | None:
        """Get the virtual remote for the Client."""
        for model in VIRTUAL_REMOTE_MODELS:
            for device in self.central.devices:
                if device.interface_id == self.interface_id and device.model == model:
                    return device
        return None

    @inspector
    async def has_program_ids(self, *, channel_hmid: str) -> bool:
        """Return if a channel has program ids."""
        return False

    @inspector
    async def init_client(self) -> None:
        """Init the client."""
        self._system_information = await self._get_system_information()
        if self.supports_rpc_callback:
            self._proxy = await self._config.create_rpc_proxy(
                interface=self.interface,
                auth_enabled=self.system_information.auth_enabled,
            )
            self._proxy_read = await self._config.create_rpc_proxy(
                interface=self.interface,
                auth_enabled=self.system_information.auth_enabled,
                max_workers=self._config.max_read_workers,
            )

    async def initialize_proxy(self) -> ProxyInitState:
        """Init the proxy has to tell the backend where to send the events."""

        if not self.supports_rpc_callback:
            if device_descriptions := await self.list_devices():
                await self.central.add_new_devices(
                    interface_id=self.interface_id, device_descriptions=device_descriptions
                )
                return ProxyInitState.INIT_SUCCESS
            return ProxyInitState.INIT_FAILED
        try:
            _LOGGER.debug("PROXY_INIT: init('%s', '%s')", self._config.init_url, self.interface_id)
            self._ping_pong_cache.clear()
            await self._proxy.init(self._config.init_url, self.interface_id)
            self._is_initialized = True
            self._mark_all_devices_forced_availability(forced_availability=ForcedDeviceAvailability.NOT_SET)
            _LOGGER.debug("PROXY_INIT: Proxy for %s initialized", self.interface_id)
        except BaseHomematicException as bhexc:
            _LOGGER.error(  # i18n-log: ignore
                "PROXY_INIT failed: %s [%s] Unable to initialize proxy for %s",
                bhexc.name,
                extract_exc_args(exc=bhexc),
                self.interface_id,
            )
            self.modified_at = INIT_DATETIME
            return ProxyInitState.INIT_FAILED
        self.modified_at = datetime.now()
        return ProxyInitState.INIT_SUCCESS

    def is_callback_alive(self) -> bool:
        """Return if XmlRPC-Server is alive based on received events for this client."""
        if not self.supports_ping_pong:
            return True
        if (
            last_events_dt := self.central.get_last_event_seen_for_interface(interface_id=self.interface_id)
        ) is not None:
            if (seconds_since_last_event := (datetime.now() - last_events_dt).total_seconds()) > CALLBACK_WARN_INTERVAL:
                if self._is_callback_alive:
                    self.central.emit_interface_event(
                        interface_id=self.interface_id,
                        interface_event_type=InterfaceEventType.CALLBACK,
                        data={
                            EventKey.AVAILABLE: False,
                            EventKey.SECONDS_SINCE_LAST_EVENT: int(seconds_since_last_event),
                        },
                    )
                    self._is_callback_alive = False
                _LOGGER.error(
                    i18n.tr(
                        "log.client.is_callback_alive.no_events",
                        interface_id=self.interface_id,
                        seconds=int(seconds_since_last_event),
                    )
                )
                return False

            if not self._is_callback_alive:
                self.central.emit_interface_event(
                    interface_id=self.interface_id,
                    interface_event_type=InterfaceEventType.CALLBACK,
                    data={EventKey.AVAILABLE: True},
                )
                self._is_callback_alive = True
        return True

    @inspector(re_raise=False, no_raise_return=False)
    async def is_connected(self) -> bool:
        """
        Perform actions required for connectivity check.

        Connection is not connected, if three consecutive checks fail.
        Return connectivity state.
        """
        if await self.check_connection_availability(handle_ping_pong=True) is True:
            self._connection_error_count = 0
        else:
            self._connection_error_count += 1

        if self._connection_error_count > 3:
            self._mark_all_devices_forced_availability(forced_availability=ForcedDeviceAvailability.FORCE_FALSE)
            return False
        if not self.supports_push_updates:
            return True
        return (datetime.now() - self.modified_at).total_seconds() < CALLBACK_WARN_INTERVAL

    @inspector(re_raise=False, measure_performance=True)
    async def list_devices(self) -> tuple[DeviceDescription, ...] | None:
        """List devices of the backend."""
        try:
            return tuple(await self._proxy_read.listDevices())
        except BaseHomematicException as bhexc:  # pragma: no cover
            _LOGGER.debug(
                "LIST_DEVICES failed: %s [%s]",
                bhexc.name,
                extract_exc_args(exc=bhexc),
            )
        return None

    @inspector(measure_performance=True)
    async def put_paramset(
        self,
        *,
        channel_address: str,
        paramset_key_or_link_address: ParamsetKey | str,
        values: dict[str, Any],
        wait_for_callback: int | None = WAIT_FOR_CALLBACK,
        rx_mode: CommandRxMode | None = None,
        check_against_pd: bool = False,
    ) -> set[DP_KEY_VALUE]:
        """
        Set paramsets manually.

        Address is usually the channel_address, but for bidcos devices there is a master paramset at the device.
        Paramset_key can be a str with a channel address in case of manipulating a direct link.
        If paramset_key is string and contains a channel address, then the LINK paramset must be used for a check.
        """
        is_link_call: bool = False
        checked_values = values
        try:
            if check_against_pd:
                check_paramset_key = (
                    ParamsetKey(paramset_key_or_link_address)
                    if is_paramset_key(paramset_key=paramset_key_or_link_address)
                    else ParamsetKey.LINK
                    if (is_link_call := is_channel_address(address=paramset_key_or_link_address))
                    else None
                )
                if check_paramset_key:
                    checked_values = self._check_put_paramset(
                        channel_address=channel_address,
                        paramset_key=check_paramset_key,
                        values=values,
                    )
                else:
                    raise ClientException(i18n.tr("exception.client.paramset_key.invalid"))

            _LOGGER.debug("PUT_PARAMSET: %s, %s, %s", channel_address, paramset_key_or_link_address, checked_values)
            if rx_mode and (device := self.central.get_device(address=channel_address)):
                if supports_rx_mode(command_rx_mode=rx_mode, rx_modes=device.rx_modes):
                    await self._exec_put_paramset(
                        channel_address=channel_address,
                        paramset_key=paramset_key_or_link_address,
                        values=checked_values,
                        rx_mode=rx_mode,
                    )
                else:
                    raise ClientException(i18n.tr("exception.client.rx_mode.unsupported", rx_mode=rx_mode))
            else:
                await self._exec_put_paramset(
                    channel_address=channel_address,
                    paramset_key=paramset_key_or_link_address,
                    values=checked_values,
                )

            # if a call is related to a link then no further action is needed
            if is_link_call:
                return set()

            # store the send value in the last_value_send_cache
            dpk_values = self._last_value_send_cache.add_put_paramset(
                channel_address=channel_address,
                paramset_key=ParamsetKey(paramset_key_or_link_address),
                values=checked_values,
            )
            self._write_temporary_value(dpk_values=dpk_values)

            if (
                self.interface in (Interface.BIDCOS_RF, Interface.BIDCOS_WIRED)
                and paramset_key_or_link_address == ParamsetKey.MASTER
                and (channel := self.central.get_channel(channel_address=channel_address)) is not None
            ):

                async def poll_master_dp_values() -> None:
                    """Load master paramset values."""
                    if not channel:
                        return
                    for interval in self.central.config.hm_master_poll_after_send_intervals:
                        await asyncio.sleep(interval)
                        for dp in channel.get_readable_data_points(
                            paramset_key=ParamsetKey(paramset_key_or_link_address)
                        ):
                            await dp.load_data_point_value(call_source=CallSource.MANUAL_OR_SCHEDULED, direct_call=True)

                self.central.looper.create_task(target=poll_master_dp_values(), name="poll_master_dp_values")

            if wait_for_callback is not None and (
                device := self.central.get_device(address=get_device_address(address=channel_address))
            ):
                await _wait_for_state_change_or_timeout(
                    device=device,
                    dpk_values=dpk_values,
                    wait_for_callback=wait_for_callback,
                )
        except BaseHomematicException as bhexc:
            raise ClientException(
                i18n.tr(
                    "exception.client.put_paramset.failed",
                    channel_address=channel_address,
                    paramset_key=paramset_key_or_link_address,
                    values=values,
                    reason=extract_exc_args(exc=bhexc),
                )
            ) from bhexc
        else:
            return dpk_values

    async def reconnect(self) -> bool:
        """re-init all RPC clients."""
        if await self.is_connected():
            _LOGGER.debug(
                "RECONNECT: waiting to re-connect client %s for %is",
                self.interface_id,
                int(RECONNECT_WAIT),
            )
            await asyncio.sleep(RECONNECT_WAIT)

            await self.reinitialize_proxy()
            _LOGGER.info(
                i18n.tr(
                    "log.client.reconnect.reconnected",
                    interface_id=self.interface_id,
                )
            )
            return True
        return False

    async def reinitialize_proxy(self) -> ProxyInitState:
        """Reinit Proxy."""
        if await self.deinitialize_proxy() != ProxyInitState.DE_INIT_FAILED:
            return await self.initialize_proxy()
        return ProxyInitState.DE_INIT_FAILED

    @inspector
    async def remove_link(self, *, sender_address: str, receiver_address: str) -> None:
        """Return a list of links."""
        if not self._is_linkable:
            _LOGGER.debug("REMOVE_LINK: interface %s is not linkable", self.interface_id)
            return
        try:
            await self._proxy.removeLink(sender_address, receiver_address)
        except BaseHomematicException as bhexc:
            raise ClientException(
                i18n.tr(
                    "exception.client.remove_link.failed",
                    sender=sender_address,
                    receiver=receiver_address,
                    reason=extract_exc_args(exc=bhexc),
                )
            ) from bhexc

    @inspector
    async def report_value_usage(self, *, address: str, value_id: str, ref_counter: int) -> bool:
        """Report value usage."""
        return False

    @inspector
    async def set_metadata(self, *, address: str, data_id: str, value: dict[str, Any]) -> dict[str, Any]:
        """Write the metadata for an object."""
        try:
            return cast(dict[str, Any], await self._proxy.setMetadata(address, data_id, value))
        except BaseHomematicException as bhexc:
            raise ClientException(
                i18n.tr(
                    "exception.client.set_metadata.failed",
                    address=address,
                    data_id=data_id,
                    value=value,
                    reason=extract_exc_args(exc=bhexc),
                )
            ) from bhexc

    @inspector
    async def set_program_state(self, *, pid: str, state: bool) -> bool:  # pragma: no cover
        """Set the program state on the backend."""
        _LOGGER.debug("SET_PROGRAM_STATE: not usable for %s.", self.interface_id)
        return True

    @abstractmethod
    @inspector(measure_performance=True)
    async def set_system_variable(self, *, legacy_name: str, value: Any) -> bool:
        """Set a system variable on the backend."""

    @inspector(re_raise=False, no_raise_return=set())
    async def set_value(
        self,
        *,
        channel_address: str,
        paramset_key: ParamsetKey,
        parameter: str,
        value: Any,
        wait_for_callback: int | None = WAIT_FOR_CALLBACK,
        rx_mode: CommandRxMode | None = None,
        check_against_pd: bool = False,
    ) -> set[DP_KEY_VALUE]:
        """Set single value on paramset VALUES."""
        if paramset_key == ParamsetKey.VALUES:
            return await self._set_value(
                channel_address=channel_address,
                parameter=parameter,
                value=value,
                wait_for_callback=wait_for_callback,
                rx_mode=rx_mode,
                check_against_pd=check_against_pd,
            )
        return await self.put_paramset(
            channel_address=channel_address,
            paramset_key_or_link_address=paramset_key,
            values={parameter: value},
            wait_for_callback=wait_for_callback,
            rx_mode=rx_mode,
            check_against_pd=check_against_pd,
        )

    async def stop(self) -> None:
        """Stop depending services."""
        if not self.supports_rpc_callback:
            return
        await self._proxy.stop()
        await self._proxy_read.stop()

    @inspector
    async def update_device_firmware(self, *, device_address: str) -> bool:
        """Update the firmware of a Homematic device."""
        if device := self.central.get_device(address=device_address):
            _LOGGER.info(
                i18n.tr(
                    "log.client.update_device_firmware.try",
                    device_address=device_address,
                )
            )
            try:
                update_result = (
                    await self._proxy.installFirmware(device_address)
                    if device.product_group in (ProductGroup.HMIPW, ProductGroup.HMIP)
                    else await self._proxy.updateFirmware(device_address)
                )
                result = bool(update_result) if isinstance(update_result, bool) else bool(update_result[0])
                _LOGGER.info(
                    i18n.tr(
                        "log.client.update_device_firmware.result",
                        device_address=device_address,
                        result=("success" if result else "failed"),
                    )
                )
            except BaseHomematicException as bhexc:
                raise ClientException(
                    i18n.tr("exception.client.update_device_firmware.failed", reason=extract_exc_args(exc=bhexc))
                ) from bhexc
            return result
        return False

    @inspector(re_raise=False)
    async def update_paramset_descriptions(self, *, device_address: str) -> None:
        """Update paramsets descriptions for provided device_address."""
        if not self.central.device_descriptions.get_device_descriptions(interface_id=self.interface_id):
            _LOGGER.warning(  # i18n-log: ignore
                "UPDATE_PARAMSET_DESCRIPTIONS failed: Interface missing in central cache. Not updating paramsets for %s",
                device_address,
            )
            return

        if device_description := self.central.device_descriptions.find_device_description(
            interface_id=self.interface_id, device_address=device_address
        ):
            await self.fetch_paramset_descriptions(device_description=device_description)
        else:
            _LOGGER.warning(  # i18n-log: ignore
                "UPDATE_PARAMSET_DESCRIPTIONS failed: Channel missing in central.cache. Not updating paramsets for %s",
                device_address,
            )
            return
        await self.central.save_files(save_paramset_descriptions=True)

    def _check_put_paramset(
        self, *, channel_address: str, paramset_key: ParamsetKey, values: dict[str, Any]
    ) -> dict[str, Any]:
        """Check put_paramset."""
        checked_values: dict[str, Any] = {}
        for param, value in values.items():
            checked_values[param] = self._convert_value(
                channel_address=channel_address,
                paramset_key=paramset_key,
                parameter=param,
                value=value,
                operation=Operations.WRITE,
            )
        return checked_values

    def _check_set_value(self, *, channel_address: str, paramset_key: ParamsetKey, parameter: str, value: Any) -> Any:
        """Check set_value."""
        return self._convert_value(
            channel_address=channel_address,
            paramset_key=paramset_key,
            parameter=parameter,
            value=value,
            operation=Operations.WRITE,
        )

    def _convert_value(
        self,
        *,
        channel_address: str,
        paramset_key: ParamsetKey,
        parameter: str,
        value: Any,
        operation: Operations,
    ) -> Any:
        """Check a single parameter against paramset descriptions and convert the value."""
        if parameter_data := self.central.paramset_descriptions.get_parameter_data(
            interface_id=self.interface_id,
            channel_address=channel_address,
            paramset_key=paramset_key,
            parameter=parameter,
        ):
            pd_type = parameter_data["TYPE"]
            op_mask = int(operation)
            if (int(parameter_data["OPERATIONS"]) & op_mask) != op_mask:
                raise ClientException(
                    i18n.tr(
                        "exception.client.parameter.operation_unsupported",
                        parameter=parameter,
                        operation=operation.value,
                    )
                )
            # Only build a tuple if a value list exists
            pd_value_list = tuple(parameter_data["VALUE_LIST"]) if parameter_data.get("VALUE_LIST") else None
            return convert_value(value=value, target_type=pd_type, value_list=pd_value_list)
        raise ClientException(
            i18n.tr(
                "exception.client.parameter.not_found",
                parameter=parameter,
                interface_id=self.interface_id,
                channel_address=channel_address,
                paramset_key=paramset_key,
            )
        )

    async def _exec_put_paramset(
        self,
        *,
        channel_address: str,
        paramset_key: ParamsetKey | str,
        values: dict[str, Any],
        rx_mode: CommandRxMode | None = None,
    ) -> None:
        """Put paramset into the backend."""
        if rx_mode:
            await self._proxy.putParamset(channel_address, paramset_key, values, rx_mode)
        else:
            await self._proxy.putParamset(channel_address, paramset_key, values)

    async def _exec_set_value(
        self,
        *,
        channel_address: str,
        parameter: str,
        value: Any,
        rx_mode: CommandRxMode | None = None,
    ) -> None:
        """Set single value on paramset VALUES."""
        if rx_mode:
            await self._proxy.setValue(channel_address, parameter, value, rx_mode)
        else:
            await self._proxy.setValue(channel_address, parameter, value)

    def _get_parameter_type(
        self,
        *,
        channel_address: str,
        paramset_key: ParamsetKey,
        parameter: str,
    ) -> ParameterType | None:
        if parameter_data := self.central.paramset_descriptions.get_parameter_data(
            interface_id=self.interface_id,
            channel_address=channel_address,
            paramset_key=paramset_key,
            parameter=parameter,
        ):
            return parameter_data["TYPE"]
        return None

    async def _get_paramset_description(
        self, *, address: str, paramset_key: ParamsetKey
    ) -> dict[str, ParameterData] | None:
        """Get paramset description from the backend."""
        try:
            return cast(
                dict[str, ParameterData],
                await self._proxy_read.getParamsetDescription(address, paramset_key),
            )
        except BaseHomematicException as bhexc:
            _LOGGER.debug(
                "GET_PARAMSET_DESCRIPTIONS failed with %s [%s] for %s address %s",
                bhexc.name,
                extract_exc_args(exc=bhexc),
                paramset_key,
                address,
            )
        return None

    @abstractmethod
    async def _get_system_information(self) -> SystemInformation:
        """Get system information of the backend."""

    def _mark_all_devices_forced_availability(self, *, forced_availability: ForcedDeviceAvailability) -> None:
        """Mark device's availability state for this interface."""
        available = forced_availability != ForcedDeviceAvailability.FORCE_FALSE
        if self._available != available:
            for device in self.central.devices:
                if device.interface_id == self.interface_id:
                    device.set_forced_availability(forced_availability=forced_availability)
            self._available = available
            _LOGGER.debug(
                "MARK_ALL_DEVICES_FORCED_AVAILABILITY: marked all devices %s for %s",
                "available" if available else "unavailable",
                self.interface_id,
            )
        self.central.emit_interface_event(
            interface_id=self.interface_id,
            interface_event_type=InterfaceEventType.PROXY,
            data={EventKey.AVAILABLE: available},
        )

    @inspector(measure_performance=True)
    async def _set_value(
        self,
        *,
        channel_address: str,
        parameter: str,
        value: Any,
        wait_for_callback: int | None,
        rx_mode: CommandRxMode | None = None,
        check_against_pd: bool = False,
    ) -> set[DP_KEY_VALUE]:
        """Set single value on paramset VALUES."""
        try:
            checked_value = (
                self._check_set_value(
                    channel_address=channel_address,
                    paramset_key=ParamsetKey.VALUES,
                    parameter=parameter,
                    value=value,
                )
                if check_against_pd
                else value
            )
            _LOGGER.debug("SET_VALUE: %s, %s, %s", channel_address, parameter, checked_value)
            if rx_mode and (device := self.central.get_device(address=channel_address)):
                if supports_rx_mode(command_rx_mode=rx_mode, rx_modes=device.rx_modes):
                    await self._exec_set_value(
                        channel_address=channel_address,
                        parameter=parameter,
                        value=value,
                        rx_mode=rx_mode,
                    )
                else:
                    raise ClientException(i18n.tr("exception.client.rx_mode.unsupported", rx_mode=rx_mode))
            else:
                await self._exec_set_value(channel_address=channel_address, parameter=parameter, value=value)
            # store the send value in the last_value_send_cache
            dpk_values = self._last_value_send_cache.add_set_value(
                channel_address=channel_address, parameter=parameter, value=checked_value
            )
            self._write_temporary_value(dpk_values=dpk_values)

            if wait_for_callback is not None and (
                device := self.central.get_device(address=get_device_address(address=channel_address))
            ):
                await _wait_for_state_change_or_timeout(
                    device=device,
                    dpk_values=dpk_values,
                    wait_for_callback=wait_for_callback,
                )
        except BaseHomematicException as bhexc:
            raise ClientException(
                i18n.tr(
                    "exception.client.set_value.failed",
                    channel_address=channel_address,
                    parameter=parameter,
                    value=value,
                    reason=extract_exc_args(exc=bhexc),
                )
            ) from bhexc
        else:
            return dpk_values

    def _write_temporary_value(self, *, dpk_values: set[DP_KEY_VALUE]) -> None:
        """Write data point temp value."""
        for dpk, value in dpk_values:
            if (
                data_point := self.central.get_generic_data_point(
                    channel_address=dpk.channel_address,
                    parameter=dpk.parameter,
                    paramset_key=dpk.paramset_key,
                )
            ) and data_point.requires_polling:
                data_point.write_temporary_value(value=value, write_at=datetime.now())


class ClientCCU(Client):
    """Client implementation for CCU backend."""

    def __init__(self, *, client_config: ClientConfig) -> None:
        """Initialize the Client."""
        self._json_rpc_client: Final = client_config.central.json_rpc_client
        super().__init__(client_config=client_config)

    @property
    def model(self) -> str:
        """Return the model of the backend."""
        return Backend.CCU

    @inspector(re_raise=False, no_raise_return=False)
    async def check_connection_availability(self, *, handle_ping_pong: bool) -> bool:
        """Check if _proxy is still initialized."""
        try:
            dt_now = datetime.now()
            if handle_ping_pong and self.supports_ping_pong and self._is_initialized:
                token = dt_now.strftime(format=DATETIME_FORMAT_MILLIS)
                callerId = f"{self.interface_id}#{token}" if handle_ping_pong else self.interface_id
                await self._proxy.ping(callerId)
                self._ping_pong_cache.handle_send_ping(ping_token=token)
            elif not self._is_initialized:
                await self._proxy.ping(self.interface_id)
            self.modified_at = dt_now
        except BaseHomematicException as bhexc:
            _LOGGER.debug(
                "CHECK_CONNECTION_AVAILABILITY failed: %s [%s]",
                bhexc.name,
                extract_exc_args(exc=bhexc),
            )
        else:
            return True
        self.modified_at = INIT_DATETIME
        return False

    @inspector
    async def delete_system_variable(self, *, name: str) -> bool:
        """Delete a system variable from the backend."""
        return await self._json_rpc_client.delete_system_variable(name=name)

    @inspector
    async def execute_program(self, *, pid: str) -> bool:
        """Execute a program on the backend."""
        return await self._json_rpc_client.execute_program(pid=pid)

    @inspector(re_raise=False, measure_performance=True)
    async def fetch_all_device_data(self) -> None:
        """Fetch all device data from the backend."""
        try:
            if all_device_data := await self._json_rpc_client.get_all_device_data(interface=self.interface):
                _LOGGER.debug(
                    "FETCH_ALL_DEVICE_DATA: Fetched all device data for interface %s",
                    self.interface,
                )
                self.central.data_cache.add_data(interface=self.interface, all_device_data=all_device_data)
                return
        except ClientException:
            self.central.emit_interface_event(
                interface_id=self.interface_id,
                interface_event_type=InterfaceEventType.FETCH_DATA,
                data={EventKey.AVAILABLE: False},
            )
            raise

        _LOGGER.debug(
            "FETCH_ALL_DEVICE_DATA: Unable to get all device data via JSON-RPC RegaScript for interface %s",
            self.interface,
        )

    @inspector(re_raise=False, measure_performance=True)
    async def fetch_device_details(self) -> None:
        """Get all names via JSON-RPS and store in data.NAMES."""
        if json_result := await self._json_rpc_client.get_device_details():
            for device in json_result:
                # ignore unknown interfaces
                if (interface := device[_JSON_INTERFACE]) and interface not in Interface:
                    continue

                device_address = device[_JSON_ADDRESS]
                self.central.device_details.add_interface(address=device_address, interface=Interface(interface))
                self.central.device_details.add_name(address=device_address, name=device[_JSON_NAME])
                self.central.device_details.add_address_id(address=device_address, hmid=device[_JSON_ID])
                for channel in device.get(_JSON_CHANNELS, []):
                    channel_address = channel[_JSON_ADDRESS]
                    self.central.device_details.add_name(address=channel_address, name=channel[_JSON_NAME])
                    self.central.device_details.add_address_id(address=channel_address, hmid=channel[_JSON_ID])
        else:
            _LOGGER.debug("FETCH_DEVICE_DETAILS: Unable to fetch device details via JSON-RPC")

    @inspector(re_raise=False, no_raise_return={})
    async def get_all_functions(self) -> dict[str, set[str]]:
        """Get all functions from the backend."""
        functions: dict[str, set[str]] = {}
        channel_ids_function = await self._json_rpc_client.get_all_channel_ids_function()
        for address, channel_id in self.central.device_details.device_channel_ids.items():
            if sections := channel_ids_function.get(channel_id):
                if address not in functions:
                    functions[address] = set()
                functions[address].update(sections)
        return functions

    @inspector(re_raise=False)
    async def get_all_programs(self, *, markers: tuple[DescriptionMarker | str, ...]) -> tuple[ProgramData, ...]:
        """Get all programs, if available."""
        return await self._json_rpc_client.get_all_programs(markers=markers)

    @inspector(re_raise=False, no_raise_return={})
    async def get_all_rooms(self) -> dict[str, set[str]]:
        """Get all rooms from the backend."""
        rooms: dict[str, set[str]] = {}
        channel_ids_room = await self._json_rpc_client.get_all_channel_ids_room()
        for address, channel_id in self.central.device_details.device_channel_ids.items():
            if names := channel_ids_room.get(channel_id):
                if address not in rooms:
                    rooms[address] = set()
                rooms[address].update(names)
        return rooms

    @inspector(re_raise=False)
    async def get_all_system_variables(
        self, *, markers: tuple[DescriptionMarker | str, ...]
    ) -> tuple[SystemVariableData, ...] | None:
        """Get all system variables from the backend."""
        return await self._json_rpc_client.get_all_system_variables(markers=markers)

    @inspector
    async def get_system_variable(self, *, name: str) -> Any:
        """Get single system variable from the backend."""
        return await self._json_rpc_client.get_system_variable(name=name)

    @inspector
    async def has_program_ids(self, *, channel_hmid: str) -> bool:
        """Return if a channel has program ids."""
        return await self._json_rpc_client.has_program_ids(channel_hmid=channel_hmid)

    @inspector
    async def report_value_usage(self, *, address: str, value_id: str, ref_counter: int) -> bool:
        """Report value usage."""
        try:
            return bool(await self._proxy.reportValueUsage(address, value_id, ref_counter))
        except BaseHomematicException as bhexc:
            raise ClientException(
                i18n.tr(
                    "exception.client.report_value_usage.failed",
                    address=address,
                    value_id=value_id,
                    ref_counter=ref_counter,
                    reason=extract_exc_args(exc=bhexc),
                )
            ) from bhexc

    @inspector
    async def set_program_state(self, *, pid: str, state: bool) -> bool:
        """Set the program state on the backend."""
        return await self._json_rpc_client.set_program_state(pid=pid, state=state)

    @inspector(measure_performance=True)
    async def set_system_variable(self, *, legacy_name: str, value: Any) -> bool:
        """Set a system variable on the backend."""
        return await self._json_rpc_client.set_system_variable(legacy_name=legacy_name, value=value)

    async def _get_system_information(self) -> SystemInformation:
        """Get system information of the backend."""
        return await self._json_rpc_client.get_system_information()


class ClientJsonCCU(ClientCCU):
    """Client implementation for CCU-like backend (CCU-Jack)."""

    @inspector
    async def add_link(self, *, sender_address: str, receiver_address: str, name: str, description: str) -> None:
        """Return a list of links."""
        _LOGGER.debug("ADD_LINK: not usable for %s.", self.interface_id)

    @inspector(re_raise=False, no_raise_return=False)
    async def check_connection_availability(self, *, handle_ping_pong: bool) -> bool:
        """Check if proxy is still initialized."""
        return await self._json_rpc_client.is_present(interface=self.interface)

    @inspector(re_raise=False)
    async def get_device_description(self, *, device_address: str) -> DeviceDescription | None:
        """Get device descriptions from the backend."""
        try:
            if device_description := await self._json_rpc_client.get_device_description(
                interface=self.interface, address=device_address
            ):
                return device_description
        except BaseHomematicException as bhexc:
            _LOGGER.warning(  # i18n-log: ignore
                "GET_DEVICE_DESCRIPTIONS failed: %s [%s]", bhexc.name, extract_exc_args(exc=bhexc)
            )
        return None

    @inspector
    async def get_link_peers(self, *, address: str) -> tuple[str, ...]:
        """Return a list of link pers."""
        _LOGGER.debug("GET_LINK_PEERS: not usable for %s.", self.interface_id)
        return ()

    @inspector
    async def get_links(self, *, address: str, flags: int) -> dict[str, Any]:
        """Return a list of links."""
        _LOGGER.debug("GET_LINKS: not usable for %s.", self.interface_id)
        return {}

    @inspector
    async def get_metadata(self, *, address: str, data_id: str) -> dict[str, Any]:
        """Return the metadata for an object."""
        _LOGGER.debug("GET_METADATA: not usable for %s.", self.interface_id)
        return {}

    @inspector
    async def get_paramset(
        self,
        *,
        address: str,
        paramset_key: ParamsetKey | str,
        call_source: CallSource = CallSource.MANUAL_OR_SCHEDULED,
    ) -> dict[str, Any]:
        """
        Return a paramset from the backend.

        Address is usually the channel_address,
        but for bidcos devices there is a master paramset at the device.
        """
        try:
            _LOGGER.debug(
                "GET_PARAMSET: address %s, paramset_key %s, source %s",
                address,
                paramset_key,
                call_source,
            )
            return (
                await self._json_rpc_client.get_paramset(
                    interface=self.interface, address=address, paramset_key=paramset_key
                )
                or {}
            )
        except BaseHomematicException as bhexc:
            raise ClientException(
                i18n.tr(
                    "exception.client.json_ccu.get_paramset.failed",
                    address=address,
                    paramset_key=paramset_key,
                    reason=extract_exc_args(exc=bhexc),
                )
            ) from bhexc

    @inspector(log_level=logging.NOTSET)
    async def get_value(
        self,
        *,
        channel_address: str,
        paramset_key: ParamsetKey,
        parameter: str,
        call_source: CallSource = CallSource.MANUAL_OR_SCHEDULED,
    ) -> Any:
        """Return a value from the backend."""
        try:
            _LOGGER.debug(
                "GET_VALUE: channel_address %s, parameter %s, paramset_key, %s, source:%s",
                channel_address,
                parameter,
                paramset_key,
                call_source,
            )
            if paramset_key == ParamsetKey.VALUES:
                return await self._json_rpc_client.get_value(
                    interface=self.interface,
                    address=channel_address,
                    paramset_key=paramset_key,
                    parameter=parameter,
                )
            paramset = (
                await self._json_rpc_client.get_paramset(
                    interface=self.interface,
                    address=channel_address,
                    paramset_key=ParamsetKey.MASTER,
                )
                or {}
            )
            return paramset.get(parameter)
        except BaseHomematicException as bhexc:
            raise ClientException(
                i18n.tr(
                    "exception.client.json_ccu.get_value.failed",
                    channel_address=channel_address,
                    parameter=parameter,
                    paramset_key=paramset_key,
                    reason=extract_exc_args(exc=bhexc),
                )
            ) from bhexc

    @inspector(re_raise=False, measure_performance=True)
    async def list_devices(self) -> tuple[DeviceDescription, ...] | None:
        """List devices of Homematic backend."""
        try:
            return await self._json_rpc_client.list_devices(interface=self.interface)
        except BaseHomematicException as bhexc:
            _LOGGER.debug(
                "LIST_DEVICES failed with %s [%s]",
                bhexc.name,
                extract_exc_args(exc=bhexc),
            )
        return None

    @inspector
    async def remove_link(self, *, sender_address: str, receiver_address: str) -> None:
        """Return a list of links."""
        _LOGGER.debug("REMOVE_LINK: not usable for %s.", self.interface_id)

    @inspector
    async def report_value_usage(self, *, address: str, value_id: str, ref_counter: int) -> bool:
        """Report value usage."""
        _LOGGER.debug("REPORT_VALUE_USAGE: not usable for %s.", self.interface_id)
        return True

    @inspector
    async def set_metadata(self, *, address: str, data_id: str, value: dict[str, Any]) -> dict[str, Any]:
        """Write the metadata for an object."""
        _LOGGER.debug("SET_METADATA: not usable for %s.", self.interface_id)
        return {}

    @inspector
    async def update_device_firmware(self, *, device_address: str) -> bool:
        """Update the firmware of a Homematic device."""
        _LOGGER.debug("UPDATE_DEVICE_FIRMWARE: not usable for %s.", self.interface_id)
        return True

    async def _exec_put_paramset(
        self,
        *,
        channel_address: str,
        paramset_key: ParamsetKey | str,
        values: dict[str, Any],
        rx_mode: CommandRxMode | None = None,
    ) -> None:
        """Put paramset into the backend."""
        # _values: list[dict[str, Any]] = []
        for parameter, value in values.items():
            await self._exec_set_value(
                channel_address=channel_address, parameter=parameter, value=value, rx_mode=rx_mode
            )

    async def _exec_set_value(
        self,
        *,
        channel_address: str,
        parameter: str,
        value: Any,
        rx_mode: CommandRxMode | None = None,
    ) -> None:
        """Set single value on paramset VALUES."""
        if (
            value_type := self._get_parameter_type(
                channel_address=channel_address,
                paramset_key=ParamsetKey.VALUES,
                parameter=parameter,
            )
        ) is None:
            raise ClientException(
                i18n.tr(
                    "exception.client.json_ccu.set_value.unknown_type",
                    channel_address=channel_address,
                    paramset_key=ParamsetKey.VALUES,
                    parameter=parameter,
                )
            )

        _type = _CCU_JSON_VALUE_TYPE.get(value_type, "string")
        await self._json_rpc_client.set_value(
            interface=self.interface,
            address=channel_address,
            parameter=parameter,
            value_type=_type,
            value=value,
        )

    async def _get_paramset_description(
        self, *, address: str, paramset_key: ParamsetKey
    ) -> dict[str, ParameterData] | None:
        """Get paramset description from the backend."""
        try:
            return cast(
                dict[str, ParameterData],
                await self._json_rpc_client.get_paramset_description(
                    interface=self.interface, address=address, paramset_key=paramset_key
                ),
            )
        except BaseHomematicException as bhexc:
            _LOGGER.debug(
                "GET_PARAMSET_DESCRIPTIONS failed with %s [%s] for %s address %s",
                bhexc.name,
                extract_exc_args(exc=bhexc),
                paramset_key,
                address,
            )
        return None

    async def _get_system_information(self) -> SystemInformation:
        """Get system information of the backend."""
        return SystemInformation(
            available_interfaces=(self.interface,),
            serial=f"{self.interface}_{DUMMY_SERIAL}",
        )


class ClientHomegear(ClientCCU):
    """
    Client implementation for Homegear backend.

    Inherit from ClientCCU to share common behavior used by tests and code paths
    that expect a CCU-like client interface for Homegear selections.
    """

    @property
    def model(self) -> str:
        """Return the model of the backend."""
        if self._config.version:
            return Backend.PYDEVCCU if Backend.PYDEVCCU.lower() in self._config.version else Backend.HOMEGEAR
        return Backend.CCU

    @property
    def supports_ping_pong(self) -> bool:
        """Return the supports_ping_pong info of the backend."""
        return False

    @inspector(re_raise=False, no_raise_return=False)
    async def check_connection_availability(self, *, handle_ping_pong: bool) -> bool:
        """Check if proxy is still initialized."""
        try:
            await self._proxy.clientServerInitialized(self.interface_id)
            self.modified_at = datetime.now()
        except BaseHomematicException as bhexc:  # pragma: no cover
            _LOGGER.debug(
                "CHECK_CONNECTION_AVAILABILITY failed: %s [%s]",
                bhexc.name,
                extract_exc_args(exc=bhexc),
            )
        else:
            return True
        self.modified_at = INIT_DATETIME
        return False

    @inspector
    async def delete_system_variable(self, *, name: str) -> bool:
        """Delete a system variable from the backend."""
        await self._proxy.deleteSystemVariable(name)
        return True

    @inspector(re_raise=False, measure_performance=True)
    async def fetch_all_device_data(self) -> None:
        """Fetch all device data from the backend."""
        return

    @inspector(re_raise=False, measure_performance=True)
    async def fetch_device_details(self) -> None:
        """Get all names from metadata (Homegear)."""
        _LOGGER.debug("FETCH_DEVICE_DETAILS: Fetching names via Metadata")
        for address in self.central.device_descriptions.get_device_descriptions(interface_id=self.interface_id):
            try:
                self.central.device_details.add_name(
                    address=address,
                    name=await self._proxy_read.getMetadata(address, _NAME),
                )
            except BaseHomematicException as bhexc:  # pragma: no cover
                _LOGGER.warning(  # i18n-log: ignore
                    "%s [%s] Failed to fetch name for device %s",
                    bhexc.name,
                    extract_exc_args(exc=bhexc),
                    address,
                )

    @inspector(re_raise=False)
    async def get_all_system_variables(
        self, *, markers: tuple[DescriptionMarker | str, ...]
    ) -> tuple[SystemVariableData, ...] | None:
        """Get all system variables from the backend."""
        variables: list[SystemVariableData] = []
        if hg_variables := await self._proxy.getAllSystemVariables():
            for name, value in hg_variables.items():
                variables.append(SystemVariableData(vid=name, legacy_name=name, value=value))
        return tuple(variables)

    @inspector
    async def get_system_variable(self, *, name: str) -> Any:
        """Get single system variable from the backend."""
        return await self._proxy.getSystemVariable(name)

    @inspector(measure_performance=True)
    async def set_system_variable(self, *, legacy_name: str, value: Any) -> bool:
        """Set a system variable on the backend."""
        await self._proxy.setSystemVariable(legacy_name, value)
        return True

    async def _get_system_information(self) -> SystemInformation:
        """Get system information of the backend."""
        return SystemInformation(available_interfaces=(Interface.BIDCOS_RF,), serial=f"{self.interface}_{DUMMY_SERIAL}")


class ClientConfig:
    """Config for a Client."""

    def __init__(
        self,
        *,
        central: hmcu.CentralUnit,
        interface_config: InterfaceConfig,
    ) -> None:
        """Initialize the config."""
        self.central: Final = central
        self.version: str = "0"
        self.system_information = SystemInformation()
        self.interface_config: Final = interface_config
        self.interface: Final = interface_config.interface
        self.interface_id: Final = interface_config.interface_id
        self.max_read_workers: Final[int] = central.config.max_read_workers
        self.has_credentials: Final[bool] = central.config.username is not None and central.config.password is not None
        self.supports_firmware_updates: Final = self.interface in INTERFACES_SUPPORTING_FIRMWARE_UPDATES
        self.supports_push_updates: Final = self.interface not in central.config.interfaces_requiring_periodic_refresh
        self.supports_rpc_callback: Final = self.interface in INTERFACES_SUPPORTING_RPC_CALLBACK
        callback_host: Final = (
            central.config.callback_host if central.config.callback_host else central.callback_ip_addr
        )
        callback_port = (
            central.config.callback_port_xml_rpc
            if central.config.callback_port_xml_rpc
            else central.listen_port_xml_rpc
        )
        init_url = f"{callback_host}:{callback_port}"
        self.init_url: Final = f"http://{init_url}"

        self.xml_rpc_uri: Final = build_xml_rpc_uri(
            host=central.config.host,
            port=interface_config.port,
            path=interface_config.remote_path,
            tls=central.config.tls,
        )

    async def create_client(self) -> Client:
        """Identify the used client."""
        try:
            self.version = await self._get_version()
            client: Client | None
            if self.interface == Interface.BIDCOS_RF and ("Homegear" in self.version or "pydevccu" in self.version):
                client = ClientHomegear(client_config=self)
            elif self.interface in INTERFACES_REQUIRING_JSON_RPC_CLIENT:
                client = ClientJsonCCU(client_config=self)
            else:
                client = ClientCCU(client_config=self)

            if client:
                await client.init_client()
                if await client.check_connection_availability(handle_ping_pong=False):
                    return client
            raise NoConnectionException(
                i18n.tr("exception.client.client_config.no_connection", interface_id=self.interface_id)
            )
        except BaseHomematicException:
            raise
        except Exception as exc:  # pragma: no cover
            raise NoConnectionException(
                i18n.tr(
                    "exception.client.client_config.unable_to_connect",
                    reason=extract_exc_args(exc=exc),
                )
            ) from exc

    async def create_rpc_proxy(
        self, *, interface: Interface, auth_enabled: bool | None = None, max_workers: int = DEFAULT_MAX_WORKERS
    ) -> BaseRpcProxy:
        """Return a RPC proxy for the backend communication."""
        return await self._create_xml_rpc_proxy(auth_enabled=auth_enabled, max_workers=max_workers)

    async def _create_simple_rpc_proxy(self, *, interface: Interface) -> BaseRpcProxy:
        """Return a RPC proxy for the backend communication."""
        return await self._create_xml_rpc_proxy(auth_enabled=True, max_workers=0)

    async def _create_xml_rpc_proxy(
        self, *, auth_enabled: bool | None = None, max_workers: int = DEFAULT_MAX_WORKERS
    ) -> AioXmlRpcProxy:
        """Return a XmlRPC proxy for the backend communication."""
        config = self.central.config
        xml_rpc_headers = (
            build_xml_rpc_headers(
                username=config.username,
                password=config.password,
            )
            if auth_enabled
            else []
        )
        xml_proxy = AioXmlRpcProxy(
            max_workers=max_workers,
            interface_id=self.interface_id,
            connection_state=self.central.connection_state,
            uri=self.xml_rpc_uri,
            headers=xml_rpc_headers,
            tls=config.tls,
            verify_tls=config.verify_tls,
            session_recorder=self.central.recorder,
        )
        await xml_proxy.do_init()
        return xml_proxy

    async def _get_version(self) -> str:
        """Return the version of the the backend."""
        if self.interface in INTERFACES_REQUIRING_JSON_RPC_CLIENT:
            return "0"
        check_proxy = await self._create_simple_rpc_proxy(interface=self.interface)
        try:
            if (methods := check_proxy.supported_methods) and "getVersion" in methods:
                # BidCos-Wired does not support getVersion()
                return cast(str, await check_proxy.getVersion())
        except Exception as exc:  # pragma: no cover
            raise NoConnectionException(
                i18n.tr(
                    "exception.client.client_config.unable_to_connect",
                    reason=extract_exc_args(exc=exc),
                )
            ) from exc
        return "0"


class InterfaceConfig:
    """interface config for a Client."""

    def __init__(
        self,
        *,
        central_name: str,
        interface: Interface,
        port: int,
        remote_path: str | None = None,
    ) -> None:
        """Init the interface config."""
        self.interface: Final[Interface] = interface

        self.rpc_server: Final[RpcServerType] = INTERFACE_RPC_SERVER_TYPE[interface]
        self.interface_id: Final[str] = f"{central_name}-{self.interface}"
        self.port: Final = port
        self.remote_path: Final = remote_path
        self._init_validate()
        self._enabled: bool = True

    @property
    def enabled(self) -> bool:
        """Return if the interface config is enabled."""
        return self._enabled

    def disable(self) -> None:
        """Disable the interface config."""
        self._enabled = False

    def _init_validate(self) -> None:
        """Validate the client_config."""
        if not self.port and self.interface in INTERFACES_SUPPORTING_RPC_CALLBACK:
            raise ClientException(
                i18n.tr(
                    "exception.client.interface_config.port_required",
                    interface=self.interface,
                )
            )


async def create_client(
    central: hmcu.CentralUnit,
    interface_config: InterfaceConfig,
) -> Client:
    """Return a new client for with a given interface_config."""
    return await ClientConfig(central=central, interface_config=interface_config).create_client()


def get_client(interface_id: str) -> Client | None:
    """Return client by interface_id."""
    for central in hmcu.CENTRAL_INSTANCES.values():
        if central.has_client(interface_id=interface_id):
            return central.get_client(interface_id=interface_id)
    return None


@measure_execution_time
async def _wait_for_state_change_or_timeout(
    *,
    device: Device,
    dpk_values: set[DP_KEY_VALUE],
    wait_for_callback: int,
) -> None:
    """Wait for a data_point to change state."""
    waits = [
        _track_single_data_point_state_change_or_timeout(
            device=device,
            dpk_value=dpk_value,
            wait_for_callback=wait_for_callback,
        )
        for dpk_value in dpk_values
    ]
    await asyncio.gather(*waits)


@measure_execution_time
async def _track_single_data_point_state_change_or_timeout(
    *, device: Device, dpk_value: DP_KEY_VALUE, wait_for_callback: int
) -> None:
    """Wait for a data_point to change state."""
    ev = asyncio.Event()
    dpk, value = dpk_value

    def _async_event_changed(*args: Any, **kwargs: Any) -> None:
        if dp:
            _LOGGER.debug(
                "TRACK_SINGLE_DATA_POINT_STATE_CHANGE_OR_TIMEOUT: Received event %s with value %s",
                dpk,
                dp.value,
            )
            if _isclose(value1=value, value2=dp.value):
                _LOGGER.debug(
                    "TRACK_SINGLE_DATA_POINT_STATE_CHANGE_OR_TIMEOUT: Finished event %s with value %s",
                    dpk,
                    dp.value,
                )
                ev.set()

    if dp := device.get_generic_data_point(
        channel_address=dpk.channel_address,
        parameter=dpk.parameter,
        paramset_key=ParamsetKey(dpk.paramset_key),
    ):
        if not dp.supports_events:
            _LOGGER.debug(
                "TRACK_SINGLE_DATA_POINT_STATE_CHANGE_OR_TIMEOUT: DataPoint supports no events %s",
                dpk,
            )
            return
        if (
            unreg := dp.register_data_point_updated_callback(
                cb=_async_event_changed, custom_id=InternalCustomID.DEFAULT
            )
        ) is None:
            return

        try:
            async with asyncio.timeout(wait_for_callback):
                await ev.wait()
        except TimeoutError:
            _LOGGER.debug(
                "TRACK_SINGLE_DATA_POINT_STATE_CHANGE_OR_TIMEOUT: Timeout waiting for event %s with value %s",
                dpk,
                dp.value,
            )
        finally:
            unreg()


def _isclose(*, value1: Any, value2: Any) -> bool:
    """Check if the both values are close to each other."""
    if isinstance(value1, float):
        return bool(round(value1, 2) == round(value2, 2))
    return bool(value1 == value2)
