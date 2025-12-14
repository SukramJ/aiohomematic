"""
Device operations handler.

Handles value read/write, paramset operations, and device description fetching.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
import logging
from typing import TYPE_CHECKING, Any, Final, cast

from aiohomematic import i18n
from aiohomematic.central.integration_events import IntegrationIssue, SystemStatusEvent
from aiohomematic.client.handlers.base import BaseHandler
from aiohomematic.client.request_coalescer import RequestCoalescer, make_coalesce_key
from aiohomematic.const import (
    DP_KEY_VALUE,
    WAIT_FOR_CALLBACK,
    CallSource,
    CommandRxMode,
    DeviceDescription,
    Interface,
    InternalCustomID,
    Operations,
    ParameterData,
    ParameterType,
    ParamsetKey,
)
from aiohomematic.decorators import inspector, measure_execution_time
from aiohomematic.exceptions import BaseHomematicException, ClientException, ValidationException
from aiohomematic.interfaces.client import DeviceDiscoveryOperations, ParamsetOperations, ValueOperations
from aiohomematic.model.support import convert_value
from aiohomematic.support import (
    extract_exc_args,
    get_device_address,
    is_channel_address,
    is_paramset_key,
    supports_rx_mode,
)

if TYPE_CHECKING:
    from aiohomematic.client import AioJsonRpcAioHttpClient
    from aiohomematic.client.rpc_proxy import BaseRpcProxy
    from aiohomematic.interfaces.client import ClientDependencies
    from aiohomematic.interfaces.model import DeviceProtocol
    from aiohomematic.store import CommandCache

_LOGGER: Final = logging.getLogger(__name__)


class DeviceOperationsHandler(
    BaseHandler,
    DeviceDiscoveryOperations,
    ParamsetOperations,
    ValueOperations,
):
    """
    Handler for device value and paramset operations.

    Implements DeviceDiscoveryOperations, ParamsetOperations, and ValueOperations
    protocols for ISP-compliant client operations.

    Handles:
    - Reading and writing data point values
    - Reading and writing paramsets
    - Fetching device and paramset descriptions
    - Value conversion and validation
    """

    __slots__ = ("_device_description_coalescer", "_last_value_send_cache", "_paramset_description_coalescer")

    def __init__(
        self,
        *,
        central: ClientDependencies,
        interface: Interface,
        interface_id: str,
        json_rpc_client: AioJsonRpcAioHttpClient,
        proxy: BaseRpcProxy,
        proxy_read: BaseRpcProxy,
        last_value_send_cache: CommandCache,
    ) -> None:
        """Initialize the device operations handler."""
        super().__init__(
            central=central,
            interface=interface,
            interface_id=interface_id,
            json_rpc_client=json_rpc_client,
            proxy=proxy,
            proxy_read=proxy_read,
        )
        self._last_value_send_cache: Final = last_value_send_cache
        self._device_description_coalescer: Final = RequestCoalescer(name=f"device_desc:{interface_id}")
        self._paramset_description_coalescer: Final = RequestCoalescer(name=f"paramset:{interface_id}")

    @inspector(re_raise=False, measure_performance=True)
    async def fetch_all_device_data(self) -> None:
        """
        Fetch all device data from the backend via JSON-RPC.

        Retrieves current values for all data points on this interface in a single
        bulk request. This is more efficient than fetching values individually.

        The fetched data is stored in the central data cache for later use during
        device initialization.

        Raises
        ------
            ClientException: If the JSON-RPC call fails. Also publishes a
                SystemStatusEvent with an IntegrationIssue.

        """
        try:
            if all_device_data := await self._json_rpc_client.get_all_device_data(interface=self._interface):
                _LOGGER.debug(
                    "FETCH_ALL_DEVICE_DATA: Fetched all device data for interface %s",
                    self._interface,
                )
                self._central.cache_coordinator.data_cache.add_data(
                    interface=self._interface, all_device_data=all_device_data
                )
                return
        except ClientException:
            issue = IntegrationIssue(
                severity="error",
                issue_id=f"fetch_data_failed_{self._interface_id}",
                translation_key="issue.fetch_data_failed",
                translation_placeholders=(("interface_id", self._interface_id),),
            )
            self._central.event_bus.publish_sync(
                event=SystemStatusEvent(
                    timestamp=datetime.now(),
                    issues=(issue,),
                )
            )
            raise

        _LOGGER.debug(
            "FETCH_ALL_DEVICE_DATA: Unable to get all device data via JSON-RPC RegaScript for interface %s",
            self._interface,
        )

    @inspector(re_raise=False, measure_performance=True)
    async def fetch_device_details(self) -> None:
        """
        Fetch device details (names, interfaces, rega IDs) via JSON-RPC.

        Retrieves metadata for all devices and channels from the CCU's ReGaHSS
        scripting engine. The JSON response contains:
        - address: Device/channel address (e.g., "VCU0000001" or "VCU0000001:1")
        - name: User-defined name from the CCU interface
        - id: ReGaHSS internal ID for scripting
        - interface: Interface type (HmIP-RF, BidCos-RF, etc.)
        - channels: Array of child channel objects

        Data is stored in the central's device_details cache for later use
        during device/channel creation.
        """
        _JSON_ADDRESS: Final = "address"
        _JSON_CHANNELS: Final = "channels"
        _JSON_ID: Final = "id"
        _JSON_INTERFACE: Final = "interface"
        _JSON_NAME: Final = "name"

        if json_result := await self._json_rpc_client.get_device_details():
            for device in json_result:
                # ignore unknown interfaces
                if (interface := device[_JSON_INTERFACE]) and interface not in Interface:
                    continue

                device_address = device[_JSON_ADDRESS]
                self._central.cache_coordinator.device_details.add_interface(
                    address=device_address, interface=Interface(interface)
                )
                self._central.cache_coordinator.device_details.add_name(address=device_address, name=device[_JSON_NAME])
                self._central.cache_coordinator.device_details.add_address_rega_id(
                    address=device_address, rega_id=int(device[_JSON_ID])
                )
                for channel in device.get(_JSON_CHANNELS, []):
                    channel_address = channel[_JSON_ADDRESS]
                    self._central.cache_coordinator.device_details.add_name(
                        address=channel_address, name=channel[_JSON_NAME]
                    )
                    self._central.cache_coordinator.device_details.add_address_rega_id(
                        address=channel_address, rega_id=int(channel[_JSON_ID])
                    )
        else:
            _LOGGER.debug("FETCH_DEVICE_DETAILS: Unable to fetch device details via JSON-RPC")

    @inspector(re_raise=False)
    async def fetch_paramset_description(self, *, channel_address: str, paramset_key: ParamsetKey) -> None:
        """
        Fetch a single paramset description and add it to the cache.

        Args:
            channel_address: Channel address (e.g., "VCU0000001:1").
            paramset_key: Type of paramset (VALUES, MASTER, or LINK).

        """
        _LOGGER.debug("FETCH_PARAMSET_DESCRIPTION: %s for %s", paramset_key, channel_address)

        if paramset_description := await self._get_paramset_description(
            address=channel_address, paramset_key=paramset_key
        ):
            self._central.cache_coordinator.paramset_descriptions.add(
                interface_id=self._interface_id,
                channel_address=channel_address,
                paramset_key=paramset_key,
                paramset_description=paramset_description,
            )

    @inspector(re_raise=False)
    async def fetch_paramset_descriptions(self, *, device_description: DeviceDescription) -> None:
        """
        Fetch all paramset descriptions for a device and store in cache.

        Iterates through all available paramsets (VALUES, MASTER, LINK) for the
        device/channel specified in the device_description and adds each to the
        central's paramset_descriptions cache.

        Args:
            device_description: Device description from listDevices() containing
                ADDRESS and PARAMSETS fields.

        """
        data = await self.get_paramset_descriptions(device_description=device_description)
        for address, paramsets in data.items():
            _LOGGER.debug("FETCH_PARAMSET_DESCRIPTIONS for %s", address)
            for paramset_key, paramset_description in paramsets.items():
                self._central.cache_coordinator.paramset_descriptions.add(
                    interface_id=self._interface_id,
                    channel_address=address,
                    paramset_key=paramset_key,
                    paramset_description=paramset_description,
                )

    @inspector(re_raise=False)
    async def get_all_device_descriptions(self, *, device_address: str) -> tuple[DeviceDescription, ...]:
        """
        Return device description and all child channel descriptions.

        Fetches the main device description, then iterates through its CHILDREN
        field to fetch each channel's description. Logs warnings for any
        missing descriptions but continues processing.

        Args:
            device_address: Device address without channel suffix (e.g., "VCU0000001").

        Returns:
            Tuple of DeviceDescription dicts, starting with the main device
            followed by all its channels. Empty tuple if device not found.

        """
        all_device_description: list[DeviceDescription] = []
        if main_dd := await self.get_device_description(address=device_address):
            all_device_description.append(main_dd)
        else:
            _LOGGER.warning(  # i18n-log: ignore
                "GET_ALL_DEVICE_DESCRIPTIONS: No device description for %s",
                device_address,
            )

        if main_dd:
            for channel_address in main_dd["CHILDREN"]:
                if channel_dd := await self.get_device_description(address=channel_address):
                    all_device_description.append(channel_dd)
                else:
                    _LOGGER.warning(  # i18n-log: ignore
                        "GET_ALL_DEVICE_DESCRIPTIONS: No channel description for %s",
                        channel_address,
                    )
        return tuple(all_device_description)

    @inspector
    async def get_all_paramset_descriptions(
        self, *, device_descriptions: tuple[DeviceDescription, ...]
    ) -> dict[str, dict[ParamsetKey, dict[str, ParameterData]]]:
        """
        Return aggregated paramset descriptions for multiple devices.

        Iterates through each device description, fetching its paramset
        descriptions and merging them into a single dictionary.

        Args:
            device_descriptions: Tuple of DeviceDescription dicts to process.

        Returns:
            Nested dict mapping: address -> paramset_key -> parameter -> ParameterData.

        """
        all_paramsets: dict[str, dict[ParamsetKey, dict[str, ParameterData]]] = {}
        for device_description in device_descriptions:
            all_paramsets.update(await self.get_paramset_descriptions(device_description=device_description))
        return all_paramsets

    @inspector(re_raise=False)
    async def get_device_description(self, *, address: str) -> DeviceDescription | None:
        """
        Return device description for a single address.

        Uses request coalescing to deduplicate concurrent requests for the same
        address. This is beneficial during device discovery when multiple callers
        may request the same device description simultaneously.

        Args:
            address: Device or channel address (e.g., "VCU0000001" or "VCU0000001:1").

        Returns:
            DeviceDescription dict with TYPE, ADDRESS, CHILDREN, PARAMSETS, etc.
            None if the address is not found or the RPC call fails.

        """
        key = make_coalesce_key(method="getDeviceDescription", args=(address,))

        async def _fetch() -> DeviceDescription | None:
            try:
                if device_description := cast(
                    DeviceDescription | None,
                    await self._proxy_read.getDeviceDescription(address),
                ):
                    return device_description
            except BaseHomematicException as bhexc:
                _LOGGER.warning(  # i18n-log: ignore
                    "GET_DEVICE_DESCRIPTION failed: %s [%s]", bhexc.name, extract_exc_args(exc=bhexc)
                )
            return None

        return await self._device_description_coalescer.execute(key=key, executor=_fetch)

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

        Address is usually the channel_address, but for bidcos devices
        there is a master paramset at the device.
        """
        try:
            _LOGGER.debug(
                "GET_PARAMSET: address %s, paramset_key %s, source %s",
                address,
                paramset_key,
                call_source,
            )
            return cast(dict[str, Any], await self._proxy_read.getParamset(address, paramset_key))
        except BaseHomematicException as bhexc:
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
        """
        Return paramset descriptions for a single device/channel.

        Iterates through the PARAMSETS field of the device_description to fetch
        each available paramset (VALUES, MASTER, LINK) from the backend.

        Args:
            device_description: DeviceDescription dict containing ADDRESS and
                PARAMSETS fields.

        Returns:
            Dict mapping address -> paramset_key -> parameter_name -> ParameterData.
            Empty dict if all paramset fetches fail.

        """
        paramsets: dict[str, dict[ParamsetKey, dict[str, ParameterData]]] = {}
        address = device_description["ADDRESS"]
        paramsets[address] = {}
        _LOGGER.debug("GET_PARAMSET_DESCRIPTIONS for %s", address)
        for p_key in device_description["PARAMSETS"]:
            paramset_key = ParamsetKey(p_key)
            if paramset_description := await self._get_paramset_description(address=address, paramset_key=paramset_key):
                paramsets[address][paramset_key] = paramset_description
        return paramsets

    @inspector(log_level=logging.NOTSET)
    async def get_value(
        self,
        *,
        channel_address: str,
        paramset_key: ParamsetKey,
        parameter: str,
        call_source: CallSource = CallSource.MANUAL_OR_SCHEDULED,
    ) -> Any:
        """
        Return a single parameter value from the backend.

        For VALUES paramset: Uses the optimized getValue() RPC call.
        For MASTER paramset: Fetches entire paramset via getParamset() and
        extracts the requested parameter, as there's no direct getValue for MASTER.

        Args:
            channel_address: Channel address (e.g., "VCU0000001:1").
            paramset_key: VALUES or MASTER paramset key.
            parameter: Parameter name (e.g., "STATE", "LEVEL").
            call_source: Origin of the call for logging/metrics.

        Returns:
            Parameter value (type varies by parameter definition).

        Raises:
            ClientException: If the RPC call fails.

        """
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

    @inspector(re_raise=False, measure_performance=True)
    async def list_devices(self) -> tuple[DeviceDescription, ...] | None:
        """
        Return all device descriptions from the backend.

        Calls the XML-RPC listDevices() method to retrieve descriptions for all
        devices and channels known to this interface.

        Returns:
            Tuple of DeviceDescription dicts for all devices/channels.
            None if the RPC call fails (e.g., connection error).

        """
        try:
            return tuple(await self._proxy_read.listDevices())
        except BaseHomematicException as bhexc:
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

        Address is usually the channel_address, but for bidcos devices there is
        a master paramset at the device. Paramset_key can be a str with a channel
        address in case of manipulating a direct link.
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
            if rx_mode and (device := self._central.device_coordinator.get_device(address=channel_address)):
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
                self._interface in ("BidCos-RF", "BidCos-Wired")
                and paramset_key_or_link_address == ParamsetKey.MASTER
                and (channel := self._central.device_coordinator.get_channel(channel_address=channel_address))
                is not None
            ):

                async def poll_master_dp_values() -> None:
                    """Load master paramset values."""
                    if not channel:
                        return
                    for interval in self._central.config.hm_master_poll_after_send_intervals:
                        await asyncio.sleep(interval)
                        for dp in channel.get_readable_data_points(
                            paramset_key=ParamsetKey(paramset_key_or_link_address)
                        ):
                            await dp.load_data_point_value(call_source=CallSource.MANUAL_OR_SCHEDULED, direct_call=True)

                self._central.looper.create_task(target=poll_master_dp_values(), name="poll_master_dp_values")

            if wait_for_callback is not None and (
                device := self._central.device_coordinator.get_device(
                    address=get_device_address(address=channel_address)
                )
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

    @inspector
    async def report_value_usage(
        self,
        *,
        address: str,
        value_id: str,
        ref_counter: int,
        supports: bool = True,
    ) -> bool:
        """
        Report value usage to the backend for subscription management.

        Used by the Homematic backend to track which parameters are actively
        being used. This helps optimize event delivery by only sending events
        for subscribed parameters.

        Args:
            address: Channel address (e.g., "VCU0000001:1").
            value_id: Parameter identifier.
            ref_counter: Reference count (positive = subscribe, 0 = unsubscribe).
            supports: Whether this client type supports value usage reporting.
                Defaults to True; ClientCCU passes actual capability.

        Returns:
            True if the report was successful, False if not supported or failed.

        Raises:
            ClientException: If the RPC call fails (when supports=True).

        """
        if not supports:
            _LOGGER.debug("REPORT_VALUE_USAGE: Not supported by client for %s", self._interface_id)
            return False

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
        """
        Set a single parameter value.

        Routes to set_value_internal() for VALUES paramset or put_paramset()
        for MASTER paramset.

        Args:
            channel_address: Channel address (e.g., "VCU0000001:1").
            paramset_key: VALUES or MASTER paramset key.
            parameter: Parameter name (e.g., "STATE", "LEVEL").
            value: New value to set.
            wait_for_callback: Seconds to wait for confirmation event (None = don't wait).
            rx_mode: Optional transmission mode (BURST, WAKEUP, etc.).
            check_against_pd: Validate value against paramset description.

        Returns:
            Set of (DataPointKey, value) tuples for the affected data points.

        """
        if paramset_key == ParamsetKey.VALUES:
            return await self.set_value_internal(
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

    @inspector(measure_performance=True)
    async def set_value_internal(
        self,
        *,
        channel_address: str,
        parameter: str,
        value: Any,
        wait_for_callback: int | None,
        rx_mode: CommandRxMode | None = None,
        check_against_pd: bool = False,
    ) -> set[DP_KEY_VALUE]:
        """
        Set a single value on the VALUES paramset via setValue() RPC.

        This is the core implementation for sending values to devices. It:
        1. Optionally validates the value against paramset description
        2. Sends the value via XML-RPC setValue()
        3. Caches the sent value for comparison with callback events
        4. Writes a temporary value to the data point for immediate UI feedback
        5. Optionally waits for the backend callback confirming the change

        Args:
            channel_address: Channel address (e.g., "VCU0000001:1").
            parameter: Parameter name (e.g., "STATE", "LEVEL").
            value: New value to set.
            wait_for_callback: Seconds to wait for confirmation event (None = don't wait).
            rx_mode: Optional transmission mode (BURST, WAKEUP, etc.).
            check_against_pd: Validate value against paramset description.

        Returns:
            Set of (DataPointKey, value) tuples for the affected data points.

        Raises:
            ClientException: If the RPC call fails or rx_mode is unsupported.

        """
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
            if rx_mode and (device := self._central.device_coordinator.get_device(address=channel_address)):
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
                device := self._central.device_coordinator.get_device(
                    address=get_device_address(address=channel_address)
                )
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

    @inspector(re_raise=False)
    async def update_paramset_descriptions(self, *, device_address: str) -> None:
        """
        Re-fetch and update paramset descriptions for a device.

        Used when a device's firmware is updated or its configuration changes.
        Fetches fresh paramset descriptions from the backend and saves them
        to the persistent cache.

        Args:
            device_address: Device address without channel suffix (e.g., "VCU0000001").

        """
        if not self._central.cache_coordinator.device_descriptions.get_device_descriptions(
            interface_id=self._interface_id
        ):
            _LOGGER.warning(  # i18n-log: ignore
                "UPDATE_PARAMSET_DESCRIPTIONS failed: Interface missing in central cache. Not updating paramsets for %s",
                device_address,
            )
            return

        if device_description := self._central.cache_coordinator.device_descriptions.find_device_description(
            interface_id=self._interface_id, device_address=device_address
        ):
            await self.fetch_paramset_descriptions(device_description=device_description)
        else:
            _LOGGER.warning(  # i18n-log: ignore
                "UPDATE_PARAMSET_DESCRIPTIONS failed: Channel missing in central.cache. Not updating paramsets for %s",
                device_address,
            )
            return
        await self._central.save_files(save_paramset_descriptions=True)

    def _check_put_paramset(
        self, *, channel_address: str, paramset_key: ParamsetKey, values: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Validate and convert all values in a paramset against their descriptions.

        Iterates through each parameter in the values dict, converting types
        and validating against MIN/MAX constraints.

        Returns:
            Dict with validated/converted values.

        Raises:
            ClientException: If any parameter validation fails.

        """
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
        """Validate and convert a single value against its parameter description."""
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
        """
        Validate and convert a parameter value against its description.

        Performs the following checks:
        1. Parameter exists in paramset description
        2. Requested operation (READ/WRITE/EVENT) is supported
        3. Value is converted to the correct type (INTEGER, FLOAT, BOOL, ENUM, STRING)
        4. For numeric types, value is within MIN/MAX bounds

        Returns:
            Converted value matching the parameter's type definition.

        Raises:
            ClientException: If parameter not found or operation not supported.
            ValidationException: If value is outside MIN/MAX bounds.

        """
        if parameter_data := self._central.cache_coordinator.paramset_descriptions.get_parameter_data(
            interface_id=self._interface_id,
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
            converted_value = convert_value(value=value, target_type=pd_type, value_list=pd_value_list)

            # Validate MIN/MAX constraints for numeric types
            if pd_type in (ParameterType.INTEGER, ParameterType.FLOAT) and converted_value is not None:
                pd_min = parameter_data.get("MIN")
                pd_max = parameter_data.get("MAX")
                if pd_min is not None and converted_value < pd_min:
                    raise ValidationException(
                        i18n.tr(
                            "exception.client.parameter.value_below_min",
                            parameter=parameter,
                            value=converted_value,
                            min_value=pd_min,
                        )
                    )
                if pd_max is not None and converted_value > pd_max:
                    raise ValidationException(
                        i18n.tr(
                            "exception.client.parameter.value_above_max",
                            parameter=parameter,
                            value=converted_value,
                            max_value=pd_max,
                        )
                    )

            return converted_value
        raise ClientException(
            i18n.tr(
                "exception.client.parameter.not_found",
                parameter=parameter,
                interface_id=self._interface_id,
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
        """Execute the XML-RPC putParamset call with optional rx_mode."""
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
        """Execute the XML-RPC setValue call with optional rx_mode."""
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
        """Return the parameter's TYPE field from its description, or None if not found."""
        if parameter_data := self._central.cache_coordinator.paramset_descriptions.get_parameter_data(
            interface_id=self._interface_id,
            channel_address=channel_address,
            paramset_key=paramset_key,
            parameter=parameter,
        ):
            return parameter_data["TYPE"]
        return None

    async def _get_paramset_description(
        self, *, address: str, paramset_key: ParamsetKey
    ) -> dict[str, ParameterData] | None:
        """
        Fetch a paramset description via XML-RPC, returning None on failure.

        Uses request coalescing to deduplicate concurrent requests for the same
        address and paramset_key combination. This is particularly beneficial
        during device discovery when multiple channels request the same descriptions.
        """
        key = make_coalesce_key(method="getParamsetDescription", args=(address, paramset_key))

        async def _fetch() -> dict[str, ParameterData] | None:
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

        return await self._paramset_description_coalescer.execute(key=key, executor=_fetch)

    def _write_temporary_value(self, *, dpk_values: set[DP_KEY_VALUE]) -> None:
        """Write temporary values to polling data points for immediate UI feedback."""
        for dpk, value in dpk_values:
            if (
                data_point := self._central.get_generic_data_point(
                    channel_address=dpk.channel_address,
                    parameter=dpk.parameter,
                    paramset_key=dpk.paramset_key,
                )
            ) and data_point.requires_polling:
                data_point.write_temporary_value(value=value, write_at=datetime.now())


@measure_execution_time
async def _wait_for_state_change_or_timeout(
    *,
    device: DeviceProtocol,
    dpk_values: set[DP_KEY_VALUE],
    wait_for_callback: int,
) -> None:
    """Wait for all affected data points to receive confirmation callbacks in parallel."""
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
    *, device: DeviceProtocol, dpk_value: DP_KEY_VALUE, wait_for_callback: int
) -> None:
    """
    Wait for a single data point to receive its confirmation callback.

    Subscribes to the data point's update events and waits until the received
    value matches the sent value (using fuzzy float comparison) or times out.
    """
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
        unreg = dp.subscribe_to_data_point_updated(handler=_async_event_changed, custom_id=InternalCustomID.DEFAULT)

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
    """Compare values with fuzzy float matching (2 decimal places) for confirmation."""
    if isinstance(value1, float):
        return bool(round(value1, 2) == round(value2, 2))
    return bool(value1 == value2)
