"""The client-object and its methods."""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from datetime import datetime
import logging
from typing import Any, Final, cast

from hahomematic import central as hmcu
from hahomematic.caches.dynamic import CommandCache, PingPongCache
from hahomematic.client.xml_rpc import XmlRpcProxy
from hahomematic.const import (
    CALLBACK_WARN_INTERVAL,
    DATETIME_FORMAT_MILLIS,
    DEFAULT_CUSTOM_ID,
    DEFAULT_MAX_WORKERS,
    DP_KEY_VALUE,
    DUMMY_SERIAL,
    INIT_DATETIME,
    INTERFACES_SUPPORTING_FIRMWARE_UPDATES,
    INTERFACES_SUPPORTING_XML_RPC,
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
    Operations,
    ParameterData,
    ParameterType,
    ParamsetKey,
    ProductGroup,
    ProgramData,
    ProxyInitState,
    SystemInformation,
    SystemVariableData,
)
from hahomematic.decorators import inspector, measure_execution_time
from hahomematic.exceptions import BaseHomematicException, ClientException, NoConnectionException
from hahomematic.model.device import Device
from hahomematic.model.support import convert_value
from hahomematic.support import (
    build_xml_rpc_headers,
    build_xml_rpc_uri,
    get_device_address,
    is_channel_address,
    is_paramset_key,
    reduce_args,
    supports_rx_mode,
)

__all__ = ["Client", "InterfaceConfig", "create_client", "get_client"]

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


class Client(ABC):
    """Client object to access the backends via XML-RPC or JSON-RPC."""

    def __init__(self, client_config: _ClientConfig) -> None:
        """Initialize the Client."""
        self._config: Final = client_config
        self._supports_xml_rpc = self.interface in INTERFACES_SUPPORTING_XML_RPC
        self._last_value_send_cache = CommandCache(interface_id=client_config.interface_id)
        self._available: bool = True
        self._connection_error_count: int = 0
        self._is_callback_alive: bool = True
        self._is_initialized: bool = False
        self._ping_pong_cache: Final = PingPongCache(
            central=client_config.central, interface_id=client_config.interface_id
        )
        self._proxy: XmlRpcProxy
        self._proxy_read: XmlRpcProxy
        self._system_information: SystemInformation
        self.modified_at: datetime = INIT_DATETIME

    async def init_client(self) -> None:
        """Init the client."""
        self._system_information = await self._get_system_information()
        self._proxy = await self._config.create_xml_rpc_proxy(auth_enabled=self.system_information.auth_enabled)
        self._proxy_read = await self._config.create_xml_rpc_proxy(
            auth_enabled=self.system_information.auth_enabled,
            max_workers=self._config.max_read_workers,
        )

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
    def interface_id(self) -> str:
        """Return the interface id of the client."""
        return self._config.interface_id

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
    def supports_xml_rpc(self) -> bool:
        """Return if interface support xml rpc."""
        return self._supports_xml_rpc

    @property
    def system_information(self) -> SystemInformation:
        """Return the system_information of the client."""
        return self._system_information

    @property
    def version(self) -> str:
        """Return the version id of the client."""
        return self._config.version

    def get_product_group(self, model: str) -> ProductGroup:
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

    @property
    @abstractmethod
    def supports_ping_pong(self) -> bool:
        """Return the supports_ping_pong info of the backend."""

    @property
    def supports_push_updates(self) -> bool:
        """Return the client supports push update."""
        return self.interface not in self.central.config.interfaces_requiring_periodic_refresh

    @property
    def supports_firmware_updates(self) -> bool:
        """Return the supports_ping_pong info of the backend."""
        return self.interface in INTERFACES_SUPPORTING_FIRMWARE_UPDATES

    async def initialize_proxy(self) -> ProxyInitState:
        """Init the proxy has to tell the CCU / Homegear where to send the events."""

        if not self.supports_xml_rpc:
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
        except BaseHomematicException as ex:
            _LOGGER.warning(
                "PROXY_INIT failed: %s [%s] Unable to initialize proxy for %s",
                ex.name,
                reduce_args(args=ex.args),
                self.interface_id,
            )
            self.modified_at = INIT_DATETIME
            return ProxyInitState.INIT_FAILED
        self.modified_at = datetime.now()
        return ProxyInitState.INIT_SUCCESS

    async def deinitialize_proxy(self) -> ProxyInitState:
        """De-init to stop CCU from sending events for this remote."""
        if not self.supports_xml_rpc:
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
        except BaseHomematicException as ex:
            _LOGGER.warning(
                "PROXY_DE_INIT failed: %s [%s] Unable to de-initialize proxy for %s",
                ex.name,
                reduce_args(args=ex.args),
                self.interface_id,
            )
            return ProxyInitState.DE_INIT_FAILED

        self.modified_at = INIT_DATETIME
        return ProxyInitState.DE_INIT_SUCCESS

    async def reinitialize_proxy(self) -> ProxyInitState:
        """Reinit Proxy."""
        if await self.deinitialize_proxy() != ProxyInitState.DE_INIT_FAILED:
            return await self.initialize_proxy()
        return ProxyInitState.DE_INIT_FAILED

    def _mark_all_devices_forced_availability(self, forced_availability: ForcedDeviceAvailability) -> None:
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
        self.central.fire_interface_event(
            interface_id=self.interface_id,
            interface_event_type=InterfaceEventType.PROXY,
            data={EventKey.AVAILABLE: available},
        )

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
                "RECONNECT: re-connected client %s",
                self.interface_id,
            )
            return True
        return False

    async def stop(self) -> None:
        """Stop depending services."""
        if not self.supports_xml_rpc:
            return
        await self._proxy.stop()
        await self._proxy_read.stop()

    @abstractmethod
    @inspector(re_raise=False, measure_performance=True)
    async def fetch_all_device_data(self) -> None:
        """Fetch all device data from CCU."""

    @abstractmethod
    @inspector(re_raise=False, measure_performance=True)
    async def fetch_device_details(self) -> None:
        """Fetch names from backend."""

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

    def is_callback_alive(self) -> bool:
        """Return if XmlRPC-Server is alive based on received events for this client."""
        if not self.supports_ping_pong:
            return True
        if (last_events_dt := self.central.get_last_event_dt(interface_id=self.interface_id)) is not None:
            if (seconds_since_last_event := (datetime.now() - last_events_dt).total_seconds()) > CALLBACK_WARN_INTERVAL:
                if self._is_callback_alive:
                    self.central.fire_interface_event(
                        interface_id=self.interface_id,
                        interface_event_type=InterfaceEventType.CALLBACK,
                        data={
                            EventKey.AVAILABLE: False,
                            EventKey.SECONDS_SINCE_LAST_EVENT: int(seconds_since_last_event),
                        },
                    )
                    self._is_callback_alive = False
                _LOGGER.warning(
                    "IS_CALLBACK_ALIVE: Callback for %s has not received events for %is",
                    self.interface_id,
                    seconds_since_last_event,
                )
                return False

            if not self._is_callback_alive:
                self.central.fire_interface_event(
                    interface_id=self.interface_id,
                    interface_event_type=InterfaceEventType.CALLBACK,
                    data={EventKey.AVAILABLE: True},
                )
                self._is_callback_alive = True
        return True

    @abstractmethod
    @inspector(re_raise=False, no_raise_return=False)
    async def check_connection_availability(self, handle_ping_pong: bool) -> bool:
        """Send ping to CCU to generate PONG event."""

    @abstractmethod
    @inspector()
    async def execute_program(self, pid: str) -> bool:
        """Execute a program on CCU / Homegear."""

    @abstractmethod
    @inspector()
    async def set_program_state(self, pid: str, state: bool) -> bool:
        """Set the program state on CCU / Homegear."""

    @abstractmethod
    @inspector(measure_performance=True)
    async def set_system_variable(self, legacy_name: str, value: Any) -> bool:
        """Set a system variable on CCU / Homegear."""

    @abstractmethod
    @inspector()
    async def delete_system_variable(self, name: str) -> bool:
        """Delete a system variable from CCU / Homegear."""

    @abstractmethod
    @inspector()
    async def get_system_variable(self, name: str) -> Any:
        """Get single system variable from CCU / Homegear."""

    @abstractmethod
    @inspector(re_raise=False)
    async def get_all_system_variables(
        self, markers: tuple[DescriptionMarker | str, ...]
    ) -> tuple[SystemVariableData, ...] | None:
        """Get all system variables from CCU / Homegear."""

    @abstractmethod
    @inspector(re_raise=False)
    async def get_all_programs(self, markers: tuple[DescriptionMarker | str, ...]) -> tuple[ProgramData, ...] | None:
        """Get all programs, if available."""

    @abstractmethod
    @inspector(re_raise=False, no_raise_return={})
    async def get_all_rooms(self) -> dict[str, set[str]]:
        """Get all rooms, if available."""

    @abstractmethod
    @inspector(re_raise=False, no_raise_return={})
    async def get_all_functions(self) -> dict[str, set[str]]:
        """Get all functions, if available."""

    @abstractmethod
    async def _get_system_information(self) -> SystemInformation:
        """Get system information of the backend."""

    def get_virtual_remote(self) -> Device | None:
        """Get the virtual remote for the Client."""
        for model in VIRTUAL_REMOTE_MODELS:
            for device in self.central.devices:
                if device.interface_id == self.interface_id and device.model == model:
                    return device
        return None

    @inspector(re_raise=False)
    async def get_device_description(self, device_address: str) -> DeviceDescription | None:
        """Get device descriptions from CCU / Homegear."""
        try:
            if device_description := cast(
                DeviceDescription | None,
                await self._proxy_read.getDeviceDescription(device_address),
            ):
                return device_description
        except BaseHomematicException as ex:
            _LOGGER.warning("GET_DEVICE_DESCRIPTIONS failed: %s [%s]", ex.name, reduce_args(args=ex.args))
        return None

    @inspector()
    async def add_link(self, sender_address: str, receiver_address: str, name: str, description: str) -> None:
        """Return a list of links."""
        try:
            await self._proxy.addLink(sender_address, receiver_address, name, description)
        except BaseHomematicException as ex:
            raise ClientException(
                f"ADD_LINK failed with for: {sender_address}/{receiver_address}/{name}/{description}: {reduce_args(args=ex.args)}"
            ) from ex

    @inspector()
    async def remove_link(self, sender_address: str, receiver_address: str) -> None:
        """Return a list of links."""
        try:
            await self._proxy.removeLink(sender_address, receiver_address)
        except BaseHomematicException as ex:
            raise ClientException(
                f"REMOVE_LINK failed with for: {sender_address}/{receiver_address}: {reduce_args(args=ex.args)}"
            ) from ex

    @inspector()
    async def get_link_peers(self, address: str) -> tuple[str, ...] | None:
        """Return a list of link pers."""
        try:
            return tuple(await self._proxy.getLinkPeers(address))
        except BaseHomematicException as ex:
            raise ClientException(f"GET_LINK_PEERS failed with for: {address}: {reduce_args(args=ex.args)}") from ex

    @inspector()
    async def get_links(self, address: str, flags: int) -> dict[str, Any]:
        """Return a list of links."""
        try:
            return cast(dict[str, Any], await self._proxy.getLinks(address, flags))
        except BaseHomematicException as ex:
            raise ClientException(f"GET_LINKS failed with for: {address}: {reduce_args(args=ex.args)}") from ex

    @inspector()
    async def get_metadata(self, address: str, data_id: str) -> dict[str, Any]:
        """Return the metadata for an object."""
        try:
            return cast(dict[str, Any], await self._proxy.getMetadata(address, data_id))
        except BaseHomematicException as ex:
            raise ClientException(
                f"GET_METADATA failed with for: {address}/{data_id}: {reduce_args(args=ex.args)}"
            ) from ex

    @inspector()
    async def set_metadata(self, address: str, data_id: str, value: dict[str, Any]) -> dict[str, Any]:
        """Write the metadata for an object."""
        try:
            return cast(dict[str, Any], await self._proxy.setMetadata(address, data_id, value))
        except BaseHomematicException as ex:
            raise ClientException(
                f"SET_METADATA failed with for: {address}/{data_id}/{value}: {reduce_args(args=ex.args)}"
            ) from ex

    @inspector(log_level=logging.NOTSET)
    async def get_value(
        self,
        channel_address: str,
        paramset_key: ParamsetKey,
        parameter: str,
        call_source: CallSource = CallSource.MANUAL_OR_SCHEDULED,
    ) -> Any:
        """Return a value from CCU."""
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
        except BaseHomematicException as ex:
            raise ClientException(
                f"GET_VALUE failed with for: {channel_address}/{parameter}/{paramset_key}: {reduce_args(args=ex.args)}"
            ) from ex

    @inspector(measure_performance=True)
    async def _set_value(
        self,
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
                    raise ClientException(f"Unsupported rx_mode: {rx_mode}")
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
        except BaseHomematicException as ex:
            raise ClientException(
                f"SET_VALUE failed for {channel_address}/{parameter}/{value}: {reduce_args(args=ex.args)}"
            ) from ex
        else:
            return dpk_values

    async def _exec_set_value(
        self,
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

    def _check_set_value(self, channel_address: str, paramset_key: ParamsetKey, parameter: str, value: Any) -> Any:
        """Check set_value."""
        return self._convert_value(
            channel_address=channel_address,
            paramset_key=paramset_key,
            parameter=parameter,
            value=value,
            operation=Operations.WRITE,
        )

    def _write_temporary_value(self, dpk_values: set[DP_KEY_VALUE]) -> None:
        """Write data point temp value."""
        for dpk, value in dpk_values:
            if (
                data_point := self.central.get_generic_data_point(
                    channel_address=dpk.channel_address,
                    parameter=dpk.parameter,
                    paramset_key=dpk.paramset_key,
                )
            ) and data_point.requires_polling:
                data_point.write_temporary_value(value=value)

    @inspector(re_raise=False, no_raise_return=set())
    async def set_value(
        self,
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

    @inspector()
    async def get_paramset(
        self,
        address: str,
        paramset_key: ParamsetKey | str,
        call_source: CallSource = CallSource.MANUAL_OR_SCHEDULED,
    ) -> dict[str, Any]:
        """
        Return a paramset from CCU.

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
        except BaseHomematicException as ex:
            raise ClientException(
                f"GET_PARAMSET failed with for {address}/{paramset_key}: {reduce_args(args=ex.args)}"
            ) from ex

    @inspector(measure_performance=True)
    async def put_paramset(
        self,
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
                    raise ClientException(
                        "Parameter paramset_key is neither a valid ParamsetKey nor a channel address."
                    )

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
                    raise ClientException(f"Unsupported rx_mode: {rx_mode}")
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
        except BaseHomematicException as ex:
            raise ClientException(
                f"PUT_PARAMSET failed for {channel_address}/{paramset_key_or_link_address}/{values}: {reduce_args(args=ex.args)}"
            ) from ex
        else:
            return dpk_values

    async def _exec_put_paramset(
        self,
        channel_address: str,
        paramset_key: ParamsetKey | str,
        values: dict[str, Any],
        rx_mode: CommandRxMode | None = None,
    ) -> None:
        """Put paramset into CCU."""
        if rx_mode:
            await self._proxy.putParamset(channel_address, paramset_key, values, rx_mode)
        else:
            await self._proxy.putParamset(channel_address, paramset_key, values)

    def _check_put_paramset(
        self, channel_address: str, paramset_key: ParamsetKey, values: dict[str, Any]
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

    def _convert_value(
        self,
        channel_address: str,
        paramset_key: ParamsetKey,
        parameter: str,
        value: Any,
        operation: Operations,
    ) -> Any:
        # Rewrite check for LINK paramset
        """Check a single parameter against paramset descriptions."""
        if parameter_data := self.central.paramset_descriptions.get_parameter_data(
            interface_id=self.interface_id,
            channel_address=channel_address,
            paramset_key=paramset_key,
            parameter=parameter,
        ):
            pd_type = parameter_data["TYPE"]
            pd_value_list = tuple(parameter_data["VALUE_LIST"]) if parameter_data.get("VALUE_LIST") else None
            if not bool(pd_operation := int(parameter_data["OPERATIONS"]) & operation) and pd_operation:
                raise ClientException(
                    f"Parameter {parameter} does not support the requested operation {operation.value}"
                )

            return convert_value(value=value, target_type=pd_type, value_list=pd_value_list)
        raise ClientException(
            f"Parameter {parameter} could not be found: {self.interface_id}/{channel_address}/{paramset_key}"
        )

    def _get_parameter_type(
        self,
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

    @inspector(re_raise=False)
    async def fetch_paramset_description(self, channel_address: str, paramset_key: ParamsetKey) -> None:
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
    async def fetch_paramset_descriptions(self, device_description: DeviceDescription) -> None:
        """Fetch paramsets for provided device description."""
        data = await self.get_paramset_descriptions(device_description=device_description)
        for address, paramsets in data.items():
            _LOGGER.debug("FETCH_PARAMSET_DESCRIPTIONS for %s", address)
            for paramset_key, paramset_description in paramsets.items():
                self.central.paramset_descriptions.add(
                    interface_id=self.interface_id,
                    channel_address=address,
                    paramset_key=ParamsetKey(paramset_key),
                    paramset_description=paramset_description,
                )

    @inspector(re_raise=False, no_raise_return={})
    async def get_paramset_descriptions(
        self, device_description: DeviceDescription
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

    async def _get_paramset_description(
        self, address: str, paramset_key: ParamsetKey
    ) -> dict[str, ParameterData] | None:
        """Get paramset description from CCU."""
        try:
            return cast(
                dict[str, ParameterData],
                await self._proxy_read.getParamsetDescription(address, paramset_key),
            )
        except BaseHomematicException as ex:
            _LOGGER.debug(
                "GET_PARAMSET_DESCRIPTIONS failed with %s [%s] for %s address %s",
                ex.name,
                reduce_args(args=ex.args),
                paramset_key,
                address,
            )
        return None

    @inspector()
    async def get_all_paramset_descriptions(
        self, device_descriptions: tuple[DeviceDescription, ...]
    ) -> dict[str, dict[ParamsetKey, dict[str, ParameterData]]]:
        """Get all paramset descriptions for provided device descriptions."""
        all_paramsets: dict[str, dict[ParamsetKey, dict[str, ParameterData]]] = {}
        for device_description in device_descriptions:
            all_paramsets.update(await self.get_paramset_descriptions(device_description=device_description))
        return all_paramsets

    @inspector()
    async def has_program_ids(self, channel_hmid: str) -> bool:
        """Return if a channel has program ids."""
        return False

    @inspector(re_raise=False, measure_performance=True)
    async def list_devices(self) -> tuple[DeviceDescription, ...] | None:
        """List devices of homematic backend."""
        try:
            return tuple(await self._proxy_read.listDevices())
        except BaseHomematicException as ex:
            _LOGGER.debug(
                "LIST_DEVICES failed: %s [%s]",
                ex.name,
                reduce_args(args=ex.args),
            )
        return None

    @inspector()
    async def report_value_usage(self, address: str, value_id: str, ref_counter: int) -> bool:
        """Report value usage."""
        return False

    @inspector()
    async def update_device_firmware(self, device_address: str) -> bool:
        """Update the firmware of a homematic device."""
        if device := self.central.get_device(address=device_address):
            _LOGGER.info(
                "UPDATE_DEVICE_FIRMWARE: Trying firmware update for %s",
                device_address,
            )
            try:
                update_result = (
                    await self._proxy.installFirmware(device_address)
                    if device.product_group in (ProductGroup.HMIPW, ProductGroup.HMIP)
                    else await self._proxy.updateFirmware(device_address)
                )
                result = bool(update_result) if isinstance(update_result, bool) else bool(update_result[0])
                _LOGGER.info(
                    "UPDATE_DEVICE_FIRMWARE: Executed firmware update for %s with result '%s'",
                    device_address,
                    "success" if result else "failed",
                )
            except BaseHomematicException as ex:
                raise ClientException(f"UPDATE_DEVICE_FIRMWARE failed]: {reduce_args(args=ex.args)}") from ex
            return result
        return False

    @inspector(re_raise=False)
    async def update_paramset_descriptions(self, device_address: str) -> None:
        """Update paramsets descriptions for provided device_address."""
        if not self.central.device_descriptions.get_device_descriptions(interface_id=self.interface_id):
            _LOGGER.warning(
                "UPDATE_PARAMSET_DESCRIPTIONS failed: "
                "Interface missing in central cache. "
                "Not updating paramsets for %s",
                device_address,
            )
            return

        if device_description := self.central.device_descriptions.find_device_description(
            interface_id=self.interface_id, device_address=device_address
        ):
            await self.fetch_paramset_descriptions(device_description=device_description)
        else:
            _LOGGER.warning(
                "UPDATE_PARAMSET_DESCRIPTIONS failed: Channel missing in central.cache. Not updating paramsets for %s",
                device_address,
            )
            return
        await self.central.save_caches(save_paramset_descriptions=True)

    def __str__(self) -> str:
        """Provide some useful information."""
        return f"interface_id: {self.interface_id}"


class ClientCCU(Client):
    """Client implementation for CCU backend."""

    def __init__(self, client_config: _ClientConfig) -> None:
        """Initialize the Client."""
        self._json_rpc_client: Final = client_config.central.json_rpc_client
        super().__init__(client_config=client_config)

    @property
    def model(self) -> str:
        """Return the model of the backend."""
        return Backend.CCU

    @property
    def supports_ping_pong(self) -> bool:
        """Return the supports_ping_pong info of the backend."""
        return True

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

    @inspector(re_raise=False, measure_performance=True)
    async def fetch_all_device_data(self) -> None:
        """Fetch all device data from CCU."""
        try:
            if all_device_data := await self._json_rpc_client.get_all_device_data(interface=self.interface):
                _LOGGER.debug(
                    "FETCH_ALL_DEVICE_DATA: Fetched all device data for interface %s",
                    self.interface,
                )
                self.central.data_cache.add_data(interface=self.interface, all_device_data=all_device_data)
                return
        except ClientException:
            self.central.fire_interface_event(
                interface_id=self.interface_id,
                interface_event_type=InterfaceEventType.FETCH_DATA,
                data={EventKey.AVAILABLE: False},
            )
            raise

        _LOGGER.debug(
            "FETCH_ALL_DEVICE_DATA: Unable to get all device data via JSON-RPC RegaScript for interface %s",
            self.interface,
        )

    @inspector(re_raise=False, no_raise_return=False)
    async def check_connection_availability(self, handle_ping_pong: bool) -> bool:
        """Check if _proxy is still initialized."""
        try:
            dt_now = datetime.now()
            if handle_ping_pong and self.supports_ping_pong and self._is_initialized:
                callerId = (
                    f"{self.interface_id}#{dt_now.strftime(format=DATETIME_FORMAT_MILLIS)}"
                    if handle_ping_pong
                    else self.interface_id
                )
                self._ping_pong_cache.handle_send_ping(ping_ts=dt_now)
                await self._proxy.ping(callerId)
            elif not self._is_initialized:
                await self._proxy.ping(self.interface_id)
            self.modified_at = dt_now
        except BaseHomematicException as ex:
            _LOGGER.debug(
                "CHECK_CONNECTION_AVAILABILITY failed: %s [%s]",
                ex.name,
                reduce_args(args=ex.args),
            )
        else:
            return True
        self.modified_at = INIT_DATETIME
        return False

    @inspector()
    async def execute_program(self, pid: str) -> bool:
        """Execute a program on CCU."""
        return await self._json_rpc_client.execute_program(pid=pid)

    @inspector()
    async def set_program_state(self, pid: str, state: bool) -> bool:
        """Set the program state on CCU."""
        return await self._json_rpc_client.set_program_state(pid=pid, state=state)

    @inspector()
    async def has_program_ids(self, channel_hmid: str) -> bool:
        """Return if a channel has program ids."""
        return await self._json_rpc_client.has_program_ids(channel_hmid=channel_hmid)

    @inspector()
    async def report_value_usage(self, address: str, value_id: str, ref_counter: int) -> bool:
        """Report value usage."""
        try:
            return bool(await self._proxy.reportValueUsage(address, value_id, ref_counter))
        except BaseHomematicException as ex:
            raise ClientException(
                f"REPORT_VALUE_USAGE failed with: {address}/{value_id}/{ref_counter}: {reduce_args(args=ex.args)}"
            ) from ex

    @inspector(measure_performance=True)
    async def set_system_variable(self, legacy_name: str, value: Any) -> bool:
        """Set a system variable on CCU / Homegear."""
        return await self._json_rpc_client.set_system_variable(legacy_name=legacy_name, value=value)

    @inspector()
    async def delete_system_variable(self, name: str) -> bool:
        """Delete a system variable from CCU / Homegear."""
        return await self._json_rpc_client.delete_system_variable(name=name)

    @inspector()
    async def get_system_variable(self, name: str) -> Any:
        """Get single system variable from CCU / Homegear."""
        return await self._json_rpc_client.get_system_variable(name=name)

    @inspector(re_raise=False)
    async def get_all_system_variables(
        self, markers: tuple[DescriptionMarker | str, ...]
    ) -> tuple[SystemVariableData, ...] | None:
        """Get all system variables from CCU."""
        return await self._json_rpc_client.get_all_system_variables(markers=markers)

    @inspector(re_raise=False)
    async def get_all_programs(self, markers: tuple[DescriptionMarker | str, ...]) -> tuple[ProgramData, ...]:
        """Get all programs, if available."""
        return await self._json_rpc_client.get_all_programs(markers=markers)

    @inspector(re_raise=False, no_raise_return={})
    async def get_all_rooms(self) -> dict[str, set[str]]:
        """Get all rooms from CCU."""
        rooms: dict[str, set[str]] = {}
        channel_ids_room = await self._json_rpc_client.get_all_channel_ids_room()
        for address, channel_id in self.central.device_details.device_channel_ids.items():
            if names := channel_ids_room.get(channel_id):
                if address not in rooms:
                    rooms[address] = set()
                rooms[address].update(names)
        return rooms

    @inspector(re_raise=False, no_raise_return={})
    async def get_all_functions(self) -> dict[str, set[str]]:
        """Get all functions from CCU."""
        functions: dict[str, set[str]] = {}
        channel_ids_function = await self._json_rpc_client.get_all_channel_ids_function()
        for address, channel_id in self.central.device_details.device_channel_ids.items():
            if sections := channel_ids_function.get(channel_id):
                if address not in functions:
                    functions[address] = set()
                functions[address].update(sections)
        return functions

    async def _get_system_information(self) -> SystemInformation:
        """Get system information of the backend."""
        return await self._json_rpc_client.get_system_information()


class ClientJsonCCU(ClientCCU):
    """Client implementation for CCU backend."""

    async def init_client(self) -> None:
        """Init the client."""
        self._system_information = await self._get_system_information()

    @inspector(re_raise=False, no_raise_return=False)
    async def check_connection_availability(self, handle_ping_pong: bool) -> bool:
        """Check if proxy is still initialized."""
        return await self._json_rpc_client.is_present(interface=self.interface)

    @property
    def supports_ping_pong(self) -> bool:
        """Return the supports_ping_pong info of the backend."""
        return False

    @inspector(re_raise=False)
    async def get_device_description(self, device_address: str) -> DeviceDescription | None:
        """Get device descriptions from CCU / Homegear."""
        try:
            if device_description := await self._json_rpc_client.get_device_description(
                interface=self.interface, address=device_address
            ):
                return device_description
        except BaseHomematicException as ex:
            _LOGGER.warning("GET_DEVICE_DESCRIPTIONS failed: %s [%s]", ex.name, reduce_args(args=ex.args))
        return None

    @inspector()
    async def get_paramset(
        self,
        address: str,
        paramset_key: ParamsetKey | str,
        call_source: CallSource = CallSource.MANUAL_OR_SCHEDULED,
    ) -> dict[str, Any]:
        """
        Return a paramset from CCU.

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
        except BaseHomematicException as ex:
            raise ClientException(
                f"GET_PARAMSET failed with for {address}/{paramset_key}: {reduce_args(args=ex.args)}"
            ) from ex

    @inspector(log_level=logging.NOTSET)
    async def get_value(
        self,
        channel_address: str,
        paramset_key: ParamsetKey,
        parameter: str,
        call_source: CallSource = CallSource.MANUAL_OR_SCHEDULED,
    ) -> Any:
        """Return a value from CCU."""
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
        except BaseHomematicException as ex:
            raise ClientException(
                f"GET_VALUE failed with for: {channel_address}/{parameter}/{paramset_key}: {reduce_args(args=ex.args)}"
            ) from ex

    @inspector(re_raise=False, measure_performance=True)
    async def list_devices(self) -> tuple[DeviceDescription, ...] | None:
        """List devices of homematic backend."""
        try:
            return await self._json_rpc_client.list_devices(interface=self.interface)
        except BaseHomematicException as ex:
            _LOGGER.debug(
                "LIST_DEVICES failed with %s [%s]",
                ex.name,
                reduce_args(args=ex.args),
            )
        return None

    async def _get_paramset_description(
        self, address: str, paramset_key: ParamsetKey
    ) -> dict[str, ParameterData] | None:
        """Get paramset description from CCU."""
        try:
            return cast(
                dict[str, ParameterData],
                await self._json_rpc_client.get_paramset_description(
                    interface=self.interface, address=address, paramset_key=paramset_key
                ),
            )
        except BaseHomematicException as ex:
            _LOGGER.debug(
                "GET_PARAMSET_DESCRIPTIONS failed with %s [%s] for %s address %s",
                ex.name,
                reduce_args(args=ex.args),
                paramset_key,
                address,
            )
        return None

    async def _exec_put_paramset(
        self,
        channel_address: str,
        paramset_key: ParamsetKey | str,
        values: dict[str, Any],
        rx_mode: CommandRxMode | None = None,
    ) -> None:
        """Put paramset into CCU."""
        # _values: list[dict[str, Any]] = []
        for parameter, value in values.items():
            await self._exec_set_value(
                channel_address=channel_address, parameter=parameter, value=value, rx_mode=rx_mode
            )

        # Funktioniert nicht
        #     if (
        #         value_type := self._get_parameter_type(
        #             channel_address=channel_address,
        #             paramset_key=ParamsetKey.VALUES,
        #             parameter=parameter,
        #         )
        #     ) is None:
        #         raise ClientException(
        #             f"PUT_PARAMSET failed: Unable to identify parameter type {channel_address}/{paramset_key}/{parameter}"
        #         )
        #     _type = _CCU_JSON_VALUE_TYPE.get(value_type, "string")
        #
        #     _values.append({"name": parameter, "type":_type, "value": str(value)})
        #
        # await self._json_rpc_client.put_paramset(
        #     interface=self.interface,
        #     address=channel_address,
        #     paramset_key=paramset_key,
        #     values=_values,
        # )

    async def _exec_set_value(
        self,
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
                f"SET_VALUE failed: Unable to identify parameter type {channel_address}/{ParamsetKey.VALUES}/{parameter}"
            )

        _type = _CCU_JSON_VALUE_TYPE.get(value_type, "string")
        await self._json_rpc_client.set_value(
            interface=self.interface,
            address=channel_address,
            parameter=parameter,
            value_type=_type,
            value=value,
        )

    async def _get_system_information(self) -> SystemInformation:
        """Get system information of the backend."""
        return SystemInformation(
            available_interfaces=(self.interface,),
            serial=f"{self.interface}_{DUMMY_SERIAL}",
        )


class ClientHomegear(Client):
    """Client implementation for Homegear backend."""

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

    @inspector(re_raise=False)
    async def fetch_all_device_data(self) -> None:
        """Fetch all device data from CCU."""
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
            except BaseHomematicException as ex:
                _LOGGER.warning(
                    "%s [%s] Failed to fetch name for device %s",
                    ex.name,
                    reduce_args(args=ex.args),
                    address,
                )

    @inspector(re_raise=False, no_raise_return=False)
    async def check_connection_availability(self, handle_ping_pong: bool) -> bool:
        """Check if proxy is still initialized."""
        try:
            await self._proxy.clientServerInitialized(self.interface_id)
            self.modified_at = datetime.now()
        except BaseHomematicException as ex:
            _LOGGER.debug(
                "CHECK_CONNECTION_AVAILABILITY failed: %s [%s]",
                ex.name,
                reduce_args(args=ex.args),
            )
        else:
            return True
        self.modified_at = INIT_DATETIME
        return False

    @inspector()
    async def execute_program(self, pid: str) -> bool:
        """Execute a program on Homegear."""
        return True

    @inspector()
    async def set_program_state(self, pid: str, state: bool) -> bool:
        """Set the program state on Homegear."""
        return True

    @inspector(measure_performance=True)
    async def set_system_variable(self, legacy_name: str, value: Any) -> bool:
        """Set a system variable on CCU / Homegear."""
        await self._proxy.setSystemVariable(legacy_name, value)
        return True

    @inspector()
    async def delete_system_variable(self, name: str) -> bool:
        """Delete a system variable from CCU / Homegear."""
        await self._proxy.deleteSystemVariable(name)
        return True

    @inspector()
    async def get_system_variable(self, name: str) -> Any:
        """Get single system variable from CCU / Homegear."""
        return await self._proxy.getSystemVariable(name)

    @inspector(re_raise=False)
    async def get_all_system_variables(
        self, markers: tuple[DescriptionMarker | str, ...]
    ) -> tuple[SystemVariableData, ...] | None:
        """Get all system variables from Homegear."""
        variables: list[SystemVariableData] = []
        if hg_variables := await self._proxy.getAllSystemVariables():
            for name, value in hg_variables.items():
                variables.append(SystemVariableData(vid=name, legacy_name=name, value=value))
        return tuple(variables)

    @inspector(re_raise=False)
    async def get_all_programs(self, markers: tuple[DescriptionMarker | str, ...]) -> tuple[ProgramData, ...] | None:
        """Get all programs, if available."""
        return ()

    @inspector(re_raise=False, no_raise_return={})
    async def get_all_rooms(self) -> dict[str, set[str]]:
        """Get all rooms from Homegear."""
        return {}

    @inspector(re_raise=False, no_raise_return={})
    async def get_all_functions(self) -> dict[str, set[str]]:
        """Get all functions from Homegear."""
        return {}

    async def _get_system_information(self) -> SystemInformation:
        """Get system information of the backend."""
        return SystemInformation(available_interfaces=(Interface.BIDCOS_RF,), serial=f"{self.interface}_{DUMMY_SERIAL}")


class _ClientConfig:
    """Config for a Client."""

    def __init__(
        self,
        central: hmcu.CentralUnit,
        interface_config: InterfaceConfig,
    ) -> None:
        self.central: Final = central
        self.version: str = "0"
        self.system_information = SystemInformation()
        self.interface_config: Final = interface_config
        self.interface: Final = interface_config.interface
        self.interface_id: Final = interface_config.interface_id
        self.max_read_workers: Final[int] = central.config.max_read_workers
        self.has_credentials: Final[bool] = central.config.username is not None and central.config.password is not None
        self.init_url: Final[str] = f"http://{
            central.config.callback_host if central.config.callback_host else central.callback_ip_addr
        }:{central.config.callback_port if central.config.callback_port else central.listen_port}"
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
            elif self.interface in (Interface.CCU_JACK, Interface.CUXD):
                client = ClientJsonCCU(client_config=self)
            else:
                client = ClientCCU(client_config=self)

            if client:
                await client.init_client()
                if await client.check_connection_availability(handle_ping_pong=False):
                    return client
            raise NoConnectionException(f"No connection to {self.interface_id}")
        except BaseHomematicException:
            raise
        except Exception as ex:
            raise NoConnectionException(f"Unable to connect {reduce_args(args=ex.args)}.") from ex

    async def _get_version(self) -> str:
        """Return the version of the backend."""
        if self.interface in (Interface.CCU_JACK, Interface.CUXD):
            return "0"
        check_proxy = await self._create_simple_xml_rpc_proxy()
        try:
            if (methods := check_proxy.supported_methods) and "getVersion" in methods:
                # BidCos-Wired does not support getVersion()
                return cast(str, await check_proxy.getVersion())
        except Exception as ex:
            raise NoConnectionException(f"Unable to connect {reduce_args(args=ex.args)}.") from ex
        return "0"

    async def create_xml_rpc_proxy(
        self, auth_enabled: bool | None = None, max_workers: int = DEFAULT_MAX_WORKERS
    ) -> XmlRpcProxy:
        """Return a XmlRPC proxy for backend communication."""
        config = self.central.config
        xml_rpc_headers = (
            build_xml_rpc_headers(
                username=config.username,
                password=config.password,
            )
            if auth_enabled
            else []
        )
        xml_proxy = XmlRpcProxy(
            max_workers=max_workers,
            interface_id=self.interface_id,
            connection_state=self.central.connection_state,
            uri=self.xml_rpc_uri,
            headers=xml_rpc_headers,
            tls=config.tls,
            verify_tls=config.verify_tls,
        )
        await xml_proxy.do_init()
        return xml_proxy

    async def _create_simple_xml_rpc_proxy(self) -> XmlRpcProxy:
        """Return a XmlRPC proxy for backend communication."""
        return await self.create_xml_rpc_proxy(auth_enabled=True, max_workers=0)


class InterfaceConfig:
    """interface config for a Client."""

    def __init__(
        self,
        central_name: str,
        interface: Interface,
        port: int | None = None,
        remote_path: str | None = None,
    ) -> None:
        """Init the interface config."""
        self.interface: Final[Interface] = interface
        self.interface_id: Final[str] = f"{central_name}-{self.interface}"
        self.port: Final = port
        self.remote_path: Final = remote_path
        self._init_validate()
        self._enabled: bool = True

    def _init_validate(self) -> None:
        """Validate the client_config."""
        if not self.port and self.interface in INTERFACES_SUPPORTING_XML_RPC:
            raise ClientException(f"VALIDATE interface config failed: Port must defined for interface{self.interface}")

    @property
    def enabled(self) -> bool:
        """Return if the interface config is enabled."""
        return self._enabled

    def disable(self) -> None:
        """Disable the interface config."""
        self._enabled = False


async def create_client(
    central: hmcu.CentralUnit,
    interface_config: InterfaceConfig,
) -> Client:
    """Return a new client for with a given interface_config."""
    return await _ClientConfig(central=central, interface_config=interface_config).create_client()


def get_client(interface_id: str) -> Client | None:
    """Return client by interface_id."""
    for central in hmcu.CENTRAL_INSTANCES.values():
        if central.has_client(interface_id=interface_id):
            return central.get_client(interface_id=interface_id)
    return None


@measure_execution_time
async def _wait_for_state_change_or_timeout(
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
    device: Device, dpk_value: DP_KEY_VALUE, wait_for_callback: int
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
            if _isclose(value, dp.value):
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
            unsub := dp.register_data_point_updated_callback(cb=_async_event_changed, custom_id=DEFAULT_CUSTOM_ID)
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
            unsub()


def _isclose(value1: Any, value2: Any) -> bool:
    """Check if the both values are close to each other."""
    if isinstance(value1, float):
        return bool(round(value1, 2) == round(value2, 2))
    return bool(value1 == value2)
