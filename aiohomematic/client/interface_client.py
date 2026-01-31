# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Unified InterfaceClient implementation.

Uses the Backend Strategy Pattern to abstract transport differences
(CCU, CCU-Jack, Homegear) behind a common interface.

Public API
----------
- InterfaceClient: Unified client for all Homematic backend types
"""

from __future__ import annotations

import asyncio
from datetime import datetime
import logging
from typing import TYPE_CHECKING, Any, Final

from aiohomematic import i18n
from aiohomematic.central.events import ClientStateChangedEvent, SystemStatusChangedEvent
from aiohomematic.client._rpc_errors import exception_to_failure_reason
from aiohomematic.client.backends.protocol import BackendOperationsProtocol
from aiohomematic.client.request_coalescer import RequestCoalescer, make_coalesce_key
from aiohomematic.client.state_change import wait_for_state_change_or_timeout
from aiohomematic.client.state_machine import ClientStateMachine
from aiohomematic.const import (
    DATETIME_FORMAT_MILLIS,
    DP_KEY_VALUE,
    INIT_DATETIME,
    VIRTUAL_REMOTE_MODELS,
    WAIT_FOR_CALLBACK,
    BackupData,
    CallSource,
    ClientState,
    CommandRxMode,
    DescriptionMarker,
    DeviceDescription,
    FailureReason,
    ForcedDeviceAvailability,
    InboxDeviceData,
    Interface,
    Operations,
    ParameterData,
    ParameterType,
    ParamsetKey,
    ProductGroup,
    ProgramData,
    ProxyInitState,
    ServiceMessageData,
    ServiceMessageType,
    SystemInformation,
    SystemUpdateData,
    SystemVariableData,
)
from aiohomematic.decorators import inspector
from aiohomematic.exceptions import BaseHomematicException, ClientException, ValidationException
from aiohomematic.interfaces.client import ClientDependenciesProtocol, ClientProtocol
from aiohomematic.model.support import convert_value
from aiohomematic.property_decorators import DelegatedProperty
from aiohomematic.store.dynamic import CommandTracker, PingPongTracker
from aiohomematic.store.types import IncidentSeverity, IncidentType
from aiohomematic.support import (
    LogContextMixin,
    extract_exc_args,
    get_device_address,
    is_channel_address,
    is_paramset_key,
    supports_rx_mode,
)

if TYPE_CHECKING:
    from aiohomematic.client.backends.capabilities import BackendCapabilities
    from aiohomematic.client.circuit_breaker import CircuitBreaker
    from aiohomematic.client.config import InterfaceConfig
    from aiohomematic.interfaces.model import ChannelProtocol, DeviceProtocol

__all__ = ["InterfaceClient"]

_LOGGER: Final = logging.getLogger(__name__)


class InterfaceClient(ClientProtocol, LogContextMixin):
    """
    Unified client for all Homematic backend types.

    Uses BackendOperationsProtocol to abstract transport differences:
    - CCU: XML-RPC for device ops, JSON-RPC for metadata
    - CCU-Jack: JSON-RPC exclusively
    - Homegear: XML-RPC with Homegear-specific methods
    """

    __slots__ = (
        "_backend",
        "_central",
        "_connection_error_count",
        "_device_description_coalescer",
        "_interface_config",
        "_is_callback_alive",
        "_last_value_send_tracker",
        "_modified_at",
        "_paramset_description_coalescer",
        "_ping_pong_tracker",
        "_reconnect_attempts",
        "_state_machine",
        "_unsubscribe_state_change",
        "_unsubscribe_system_status",
        "_version",
    )

    def __init__(
        self,
        *,
        backend: BackendOperationsProtocol,
        central: ClientDependenciesProtocol,
        interface_config: InterfaceConfig,
        version: str,
    ) -> None:
        """Initialize InterfaceClient."""
        self._backend: Final = backend
        self._central: Final = central
        self._interface_config: Final = interface_config
        self._version: Final = version
        self._last_value_send_tracker: Final = CommandTracker(
            interface_id=backend.interface_id,
        )
        self._state_machine: Final = ClientStateMachine(
            interface_id=backend.interface_id,
            event_bus=central.event_bus,
        )
        # Subscribe to state changes for integration compatibility
        self._unsubscribe_state_change = central.event_bus.subscribe(
            event_type=ClientStateChangedEvent,
            event_key=backend.interface_id,
            handler=self._on_client_state_changed_event,
        )
        self._connection_error_count: int = 0
        self._is_callback_alive: bool = True
        self._reconnect_attempts: int = 0
        self._ping_pong_tracker: Final = PingPongTracker(
            event_bus_provider=central,
            central_info=central,
            interface_id=backend.interface_id,
            connection_state=central.connection_state,
            incident_recorder=central.cache_coordinator.incident_store,
        )
        self._device_description_coalescer: Final = RequestCoalescer(
            name=f"device_desc:{backend.interface_id}",
            event_bus=central.event_bus,
            interface_id=backend.interface_id,
        )
        self._paramset_description_coalescer: Final = RequestCoalescer(
            name=f"paramset:{backend.interface_id}",
            event_bus=central.event_bus,
            interface_id=backend.interface_id,
        )
        self._modified_at: datetime = INIT_DATETIME

        # Subscribe to connection state changes
        self._unsubscribe_system_status = central.event_bus.subscribe(
            event_type=SystemStatusChangedEvent,
            event_key=None,
            handler=self._on_system_status_event,
        )

    def __str__(self) -> str:
        """Provide information."""
        return f"interface_id: {self.interface_id}"

    available: Final = DelegatedProperty[bool](path="_state_machine.is_available")
    central: Final = DelegatedProperty[ClientDependenciesProtocol](path="_central")
    last_value_send_tracker: Final = DelegatedProperty[CommandTracker](path="_last_value_send_tracker")
    ping_pong_tracker: Final = DelegatedProperty[PingPongTracker](path="_ping_pong_tracker")
    state: Final = DelegatedProperty[ClientState](path="_state_machine.state")
    state_machine: Final = DelegatedProperty[ClientStateMachine](path="_state_machine")

    @property
    def all_circuit_breakers_closed(self) -> bool:
        """Return True if all circuit breakers are in closed state."""
        return self._backend.all_circuit_breakers_closed

    @property
    def capabilities(self) -> BackendCapabilities:
        """Return the capability flags for this backend."""
        return self._backend.capabilities

    @property
    def circuit_breaker(self) -> CircuitBreaker | None:
        """Return the primary circuit breaker for metrics access."""
        return self._backend.circuit_breaker

    @property
    def interface(self) -> Interface:
        """Return the interface type."""
        return self._backend.interface

    @property
    def interface_id(self) -> str:
        """Return the interface identifier."""
        return self._backend.interface_id

    @property
    def is_initialized(self) -> bool:
        """Return if interface is initialized."""
        return self._state_machine.state in (
            ClientState.CONNECTED,
            ClientState.DISCONNECTED,
            ClientState.RECONNECTING,
        )

    @property
    def model(self) -> str:
        """Return the backend model."""
        return self._backend.model

    @property
    def modified_at(self) -> datetime:
        """Return the last update datetime value."""
        return self._modified_at

    @modified_at.setter
    def modified_at(self, value: datetime) -> None:
        """Write the last update datetime value."""
        self._modified_at = value

    @property
    def request_coalescer(self) -> RequestCoalescer | None:
        """Return the request coalescer for metrics access."""
        return self._paramset_description_coalescer

    @property
    def system_information(self) -> SystemInformation:
        """Return system information."""
        return self._backend.system_information

    @property
    def version(self) -> str:
        """Return the version."""
        return self._version

    async def accept_device_in_inbox(self, *, device_address: str) -> bool:
        """Accept a device from the CCU inbox."""
        if not self._backend.capabilities.inbox_devices:
            return False
        return await self._backend.accept_device_in_inbox(device_address=device_address)

    async def add_link(
        self,
        *,
        sender_address: str,
        receiver_address: str,
        name: str,
        description: str,
    ) -> None:
        """Add a link between two devices."""
        if not self._backend.capabilities.linking:
            return
        await self._backend.add_link(
            sender_address=sender_address,
            receiver_address=receiver_address,
            name=name,
            description=description,
        )

    @inspector(re_raise=False, no_raise_return=False)
    async def check_connection_availability(self, *, handle_ping_pong: bool) -> bool:
        """Check if proxy is still initialized."""
        try:
            dt_now = datetime.now()
            caller_id: str | None = None
            if handle_ping_pong and self._backend.capabilities.ping_pong and self.is_initialized:
                token = dt_now.strftime(format=DATETIME_FORMAT_MILLIS)
                caller_id = f"{self.interface_id}#{token}"
                # Register token BEFORE sending ping to avoid race condition:
                # CCU may respond with PONG before await returns
                self._ping_pong_tracker.handle_send_ping(ping_token=token)
            if await self._backend.check_connection(handle_ping_pong=handle_ping_pong, caller_id=caller_id):
                self.modified_at = dt_now
                return True
        except BaseHomematicException as bhexc:
            _LOGGER.debug(
                "CHECK_CONNECTION_AVAILABILITY failed: %s [%s]",
                bhexc.name,
                extract_exc_args(exc=bhexc),
            )
        self.modified_at = INIT_DATETIME
        return False

    def clear_json_rpc_session(self) -> None:
        """Clear the JSON-RPC session."""
        self._central.json_rpc_client.clear_session()
        _LOGGER.debug(
            "CLEAR_JSON_RPC_SESSION: Session cleared for %s",
            self.interface_id,
        )

    async def create_backup_and_download(
        self,
        *,
        max_wait_time: float = 300.0,
        poll_interval: float = 5.0,
    ) -> BackupData | None:
        """Create a backup on the CCU and download it."""
        if not self._backend.capabilities.backup:
            return None
        return await self._backend.create_backup_and_download(max_wait_time=max_wait_time, poll_interval=poll_interval)

    async def deinitialize_proxy(self) -> ProxyInitState:
        """De-initialize the proxy."""
        if not self._backend.capabilities.rpc_callback:
            self._state_machine.transition_to(target=ClientState.DISCONNECTED, reason="no callback support")
            return ProxyInitState.DE_INIT_SUCCESS

        if self.modified_at == INIT_DATETIME:
            return ProxyInitState.DE_INIT_SKIPPED

        try:
            init_url = self._get_init_url()
            _LOGGER.debug("PROXY_DE_INIT: init('%s')", init_url)
            await self._backend.deinit_proxy(init_url=init_url)
            self._state_machine.transition_to(target=ClientState.DISCONNECTED, reason="proxy de-initialized")
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

    async def delete_system_variable(self, *, name: str) -> bool:
        """Delete a system variable from the backend."""
        return await self._backend.delete_system_variable(name=name)

    async def execute_program(self, *, pid: str) -> bool:
        """Execute a program on the backend."""
        if not self._backend.capabilities.programs:
            return False
        return await self._backend.execute_program(pid=pid)

    async def fetch_all_device_data(self) -> None:
        """Fetch all device data from the backend."""
        if all_device_data := await self._backend.get_all_device_data(interface=self.interface):
            self._central.cache_coordinator.data_cache.add_data(
                interface=self.interface, all_device_data=all_device_data
            )

    async def fetch_device_details(self) -> None:
        """
        Fetch device names and details from the backend.

        For CCU: Uses JSON-RPC to fetch all details in one call.
        For Homegear: Uses getMetadata to fetch names for each known address.
        """
        # Get known addresses for backends that need them (e.g., Homegear)
        addresses = tuple(
            self._central.cache_coordinator.device_descriptions.get_device_descriptions(
                interface_id=self.interface_id
            ).keys()
        )

        if device_details := await self._backend.get_device_details(addresses=addresses):
            for device in device_details:
                device_address = device["address"]
                self._central.cache_coordinator.device_details.add_name(address=device_address, name=device["name"])
                # Only add rega_id if it's meaningful (non-zero for CCU, 0 for Homegear)
                if device["id"]:
                    self._central.cache_coordinator.device_details.add_address_rega_id(
                        address=device_address, rega_id=device["id"]
                    )
                # Use interface from device data (CCU provides this), fallback to client's interface (Homegear)
                if (iface := device.get("interface")) and iface in Interface:
                    self._central.cache_coordinator.device_details.add_interface(
                        address=device_address, interface=Interface(iface)
                    )
                else:
                    self._central.cache_coordinator.device_details.add_interface(
                        address=device_address, interface=self.interface
                    )
                # Process nested channels array (CCU provides these, Homegear doesn't)
                for channel in device["channels"]:
                    channel_address = channel["address"]
                    self._central.cache_coordinator.device_details.add_name(
                        address=channel_address, name=channel["name"]
                    )
                    if channel["id"]:
                        self._central.cache_coordinator.device_details.add_address_rega_id(
                            address=channel_address, rega_id=channel["id"]
                        )

    async def fetch_paramset_description(
        self,
        *,
        channel_address: str,
        paramset_key: ParamsetKey,
        device_type: str,
    ) -> None:
        """
        Fetch a specific paramset and add it to the known ones.

        Args:
            channel_address: Channel address (e.g., "VCU0000001:1").
            paramset_key: Type of paramset (VALUES, MASTER, or LINK).
            device_type: Device TYPE for patch matching.

        """
        # Note: paramset_description can be an empty dict {} which is valid
        # (e.g., HmIP base device MASTER paramsets have no parameters)
        paramset_description = await self._get_paramset_description(address=channel_address, paramset_key=paramset_key)
        if paramset_description is not None:
            self._central.cache_coordinator.paramset_descriptions.add(
                interface_id=self.interface_id,
                channel_address=channel_address,
                paramset_key=paramset_key,
                paramset_description=paramset_description,
                device_type=device_type,
            )

    async def fetch_paramset_descriptions(self, *, device_description: DeviceDescription) -> None:
        """Fetch paramsets for provided device description."""
        # For channels, use PARENT_TYPE (root device TYPE) for patch matching.
        # Root devices don't have PARENT_TYPE, so fall back to TYPE.
        device_type = device_description.get("PARENT_TYPE") or device_description["TYPE"]

        data = await self.get_paramset_descriptions(device_description=device_description)
        for address, paramsets in data.items():
            for paramset_key, paramset_description in paramsets.items():
                self._central.cache_coordinator.paramset_descriptions.add(
                    interface_id=self.interface_id,
                    channel_address=address,
                    paramset_key=paramset_key,
                    paramset_description=paramset_description,
                    device_type=device_type,
                )

    async def get_all_device_descriptions(self, *, device_address: str) -> tuple[DeviceDescription, ...]:
        """Get all device descriptions from the backend."""
        all_device_description: list[DeviceDescription] = []
        if main_dd := await self.get_device_description(address=device_address):
            all_device_description.append(main_dd)
            channel_descriptions = [
                channel_dd
                for channel_address in main_dd.get("CHILDREN", [])
                if (channel_dd := await self.get_device_description(address=channel_address))
            ]
            all_device_description.extend(channel_descriptions)
        return tuple(all_device_description)

    async def get_all_functions(self) -> dict[str, set[str]]:
        """Get all functions from the backend."""
        if not self._backend.capabilities.functions:
            return {}
        return await self._backend.get_all_functions()

    async def get_all_paramset_descriptions(
        self, *, device_descriptions: tuple[DeviceDescription, ...]
    ) -> dict[str, dict[ParamsetKey, dict[str, ParameterData]]]:
        """Get all paramset descriptions for provided device descriptions."""
        all_paramsets: dict[str, dict[ParamsetKey, dict[str, ParameterData]]] = {}
        for device_description in device_descriptions:
            all_paramsets.update(await self.get_paramset_descriptions(device_description=device_description))
        return all_paramsets

    async def get_all_programs(
        self,
        *,
        markers: tuple[DescriptionMarker | str, ...],
    ) -> tuple[ProgramData, ...]:
        """Get all programs, if available."""
        if not self._backend.capabilities.programs:
            return ()
        return await self._backend.get_all_programs(markers=markers)

    async def get_all_rooms(self) -> dict[str, set[str]]:
        """Get all rooms from the backend."""
        if not self._backend.capabilities.rooms:
            return {}
        return await self._backend.get_all_rooms()

    async def get_all_system_variables(
        self,
        *,
        markers: tuple[DescriptionMarker | str, ...],
    ) -> tuple[SystemVariableData, ...] | None:
        """Get all system variables from the backend."""
        return await self._backend.get_all_system_variables(markers=markers)

    async def get_device_description(self, *, address: str) -> DeviceDescription | None:
        """Get device description from the backend with request coalescing."""
        key = make_coalesce_key(method="getDeviceDescription", args=(address,))

        async def _fetch() -> DeviceDescription | None:
            try:
                return await self._backend.get_device_description(address=address)
            except BaseHomematicException as bhexc:
                _LOGGER.warning(  # i18n-log: ignore
                    "GET_DEVICE_DESCRIPTION failed: %s [%s]", bhexc.name, extract_exc_args(exc=bhexc)
                )
                return None

        return await self._device_description_coalescer.execute(key=key, executor=_fetch)

    async def get_inbox_devices(self) -> tuple[InboxDeviceData, ...]:
        """Get all devices in the inbox (not yet configured)."""
        if not self._backend.capabilities.inbox_devices:
            return ()
        return await self._backend.get_inbox_devices()

    async def get_install_mode(self) -> int:
        """Return the remaining time in install mode."""
        if not self._backend.capabilities.install_mode:
            return 0
        return await self._backend.get_install_mode()

    async def get_link_peers(self, *, channel_address: str) -> tuple[str, ...]:
        """Return a list of link peers."""
        if not self._backend.capabilities.linking:
            return ()
        return await self._backend.get_link_peers(channel_address=channel_address)

    async def get_links(self, *, channel_address: str, flags: int) -> dict[str, Any]:
        """Return a list of links."""
        if not self._backend.capabilities.linking:
            return {}
        return await self._backend.get_links(channel_address=channel_address, flags=flags)

    async def get_metadata(self, *, address: str, data_id: str) -> dict[str, Any]:
        """Return the metadata for an object."""
        if not self._backend.capabilities.metadata:
            return {}
        return await self._backend.get_metadata(address=address, data_id=data_id)

    async def get_paramset(
        self,
        *,
        channel_address: str,
        paramset_key: ParamsetKey | str,
        call_source: CallSource = CallSource.MANUAL_OR_SCHEDULED,
        convert_from_pd: bool = False,
    ) -> dict[str, Any]:
        """Return a paramset from the backend."""
        result = await self._backend.get_paramset(channel_address=channel_address, paramset_key=paramset_key)
        if convert_from_pd and is_paramset_key(paramset_key=paramset_key):
            result = self._check_get_paramset(
                channel_address=channel_address,
                paramset_key=ParamsetKey(paramset_key),
                values=result,
            )
        return result

    async def get_paramset_descriptions(
        self, *, device_description: DeviceDescription
    ) -> dict[str, dict[ParamsetKey, dict[str, ParameterData]]]:
        """
        Get paramsets for provided device description.

        LINK paramsets are skipped as they are only relevant for device linking
        and are fetched dynamically when links are configured.
        """
        paramsets: dict[str, dict[ParamsetKey, dict[str, ParameterData]]] = {}
        address = device_description["ADDRESS"]
        paramsets[address] = {}
        for p_key in device_description["PARAMSETS"]:
            # Skip LINK paramsets - they are only relevant for device linking
            if (paramset_key := ParamsetKey(p_key)) == ParamsetKey.LINK:
                continue
            # Note: paramset_description can be an empty dict {} which is valid
            # (e.g., HmIP base device MASTER paramsets have no parameters)
            if (
                paramset_description := await self._get_paramset_description(address=address, paramset_key=paramset_key)
            ) is not None:
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

    async def get_rega_id_by_address(self, *, address: str) -> int | None:
        """Get the ReGa ID for a device or channel address."""
        if not self._backend.capabilities.rega_id_lookup:
            return None
        return await self._backend.get_rega_id_by_address(address=address)

    async def get_service_messages(
        self,
        *,
        message_type: ServiceMessageType | None = None,
    ) -> tuple[ServiceMessageData, ...]:
        """Get all active service messages from the backend."""
        if not self._backend.capabilities.service_messages:
            return ()
        return await self._backend.get_service_messages(message_type=message_type)

    async def get_system_update_info(self) -> SystemUpdateData | None:
        """Get system update information from the backend."""
        if not self._backend.capabilities.system_update_info:
            return None
        return await self._backend.get_system_update_info()

    async def get_system_variable(self, *, name: str) -> Any:
        """Get single system variable from the backend."""
        return await self._backend.get_system_variable(name=name)

    async def get_value(
        self,
        *,
        channel_address: str,
        paramset_key: ParamsetKey,
        parameter: str,
        call_source: CallSource = CallSource.MANUAL_OR_SCHEDULED,
        convert_from_pd: bool = False,
    ) -> Any:
        """Return a value from the backend."""
        value = await self._backend.get_value(channel_address=channel_address, parameter=parameter)
        if convert_from_pd:
            value = self._convert_read_value(
                channel_address=channel_address,
                paramset_key=paramset_key,
                parameter=parameter,
                value=value,
            )
        return value

    def get_virtual_remote(self) -> DeviceProtocol | None:
        """Get the virtual remote for the Client."""
        for model in VIRTUAL_REMOTE_MODELS:
            for device in self._central.device_registry.devices:
                if device.interface_id == self.interface_id and device.model == model:
                    return device
        return None

    async def has_program_ids(self, *, rega_id: int) -> bool:
        """Return if a channel has program ids."""
        if not self._backend.capabilities.programs:
            return False
        return await self._backend.has_program_ids(rega_id=rega_id)

    @inspector
    async def init_client(self) -> None:
        """Initialize the client."""
        self._state_machine.transition_to(target=ClientState.INITIALIZING)
        try:
            self._state_machine.transition_to(target=ClientState.INITIALIZED)
        except Exception as exc:
            self._state_machine.transition_to(
                target=ClientState.FAILED,
                reason=str(exc),
                failure_reason=exception_to_failure_reason(exc=exc),
            )
            raise

    async def initialize_proxy(self) -> ProxyInitState:
        """Initialize the proxy."""
        self._state_machine.transition_to(target=ClientState.CONNECTING)
        if not self._backend.capabilities.rpc_callback:
            if (device_descriptions := await self.list_devices()) is not None:
                await self._central.device_coordinator.add_new_devices(
                    interface_id=self.interface_id, device_descriptions=device_descriptions
                )
                self._state_machine.transition_to(
                    target=ClientState.CONNECTED, reason="proxy initialized (no callback)"
                )
                return ProxyInitState.INIT_SUCCESS
            self._state_machine.transition_to(
                target=ClientState.FAILED,
                reason="device listing failed",
                failure_reason=FailureReason.NETWORK,
            )
            self._mark_all_devices_forced_availability(forced_availability=ForcedDeviceAvailability.FORCE_FALSE)
            return ProxyInitState.INIT_FAILED

        # Record modified_at before init to detect callback during init
        # This is used to work around VirtualDevices service bug where init()
        # times out but listDevices callback was successfully received
        modified_at_before_init = self.modified_at
        init_success = False
        try:
            self._ping_pong_tracker.clear()
            init_url = self._get_init_url()
            _LOGGER.debug("PROXY_INIT: init('%s', '%s')", init_url, self.interface_id)
            await self._backend.init_proxy(init_url=init_url, interface_id=self.interface_id)
            init_success = True
        except BaseHomematicException as bhexc:
            # Check if we received a callback during init (modified_at was updated)
            # This happens when init() times out but the CCU successfully processed it
            # and called back listDevices. Common with VirtualDevices service bug.
            if self.modified_at > modified_at_before_init:
                _LOGGER.info(  # i18n-log: ignore
                    "PROXY_INIT: init() failed but callback received for %s - treating as success",
                    self.interface_id,
                )
                init_success = True
            else:
                _LOGGER.error(  # i18n-log: ignore
                    "PROXY_INIT failed: %s [%s] Unable to initialize proxy for %s",
                    bhexc.name,
                    extract_exc_args(exc=bhexc),
                    self.interface_id,
                )
                self.modified_at = INIT_DATETIME
                self._state_machine.transition_to(
                    target=ClientState.FAILED,
                    reason="proxy init failed",
                    failure_reason=exception_to_failure_reason(exc=bhexc),
                )
                self._mark_all_devices_forced_availability(forced_availability=ForcedDeviceAvailability.FORCE_FALSE)
                return ProxyInitState.INIT_FAILED

        if init_success:
            self._state_machine.transition_to(target=ClientState.CONNECTED, reason="proxy initialized")
            self._mark_all_devices_forced_availability(forced_availability=ForcedDeviceAvailability.NOT_SET)
            _LOGGER.debug("PROXY_INIT: Proxy for %s initialized", self.interface_id)

        self.modified_at = datetime.now()
        return ProxyInitState.INIT_SUCCESS

    def is_callback_alive(self) -> bool:
        """Return if XmlRPC-Server is alive based on received events."""
        if not self._backend.capabilities.ping_pong:
            return True

        if self._state_machine.is_failed or self._state_machine.state == ClientState.RECONNECTING:
            return False

        if (
            last_events_dt := self._central.event_coordinator.get_last_event_seen_for_interface(
                interface_id=self.interface_id
            )
        ) is not None:
            callback_warn = self._central.config.timeout_config.callback_warn_interval
            if (seconds_since_last_event := (datetime.now() - last_events_dt).total_seconds()) > callback_warn:
                if self._is_callback_alive:
                    self._central.event_bus.publish_sync(
                        event=SystemStatusChangedEvent(
                            timestamp=datetime.now(),
                            callback_state=(self.interface_id, False),
                        )
                    )
                    self._is_callback_alive = False
                    self._record_callback_timeout_incident(
                        seconds_since_last_event=seconds_since_last_event,
                        callback_warn_interval=callback_warn,
                        last_event_time=last_events_dt,
                    )
                _LOGGER.error(
                    i18n.tr(
                        key="log.client.is_callback_alive.no_events",
                        interface_id=self.interface_id,
                        seconds=int(seconds_since_last_event),
                    )
                )
                return False

            if not self._is_callback_alive:
                self._central.event_bus.publish_sync(
                    event=SystemStatusChangedEvent(
                        timestamp=datetime.now(),
                        callback_state=(self.interface_id, True),
                    )
                )
                self._is_callback_alive = True
        return True

    @inspector(re_raise=False, no_raise_return=False)
    async def is_connected(self) -> bool:
        """Perform connectivity check."""
        if await self.check_connection_availability(handle_ping_pong=True) is True:
            self._connection_error_count = 0
        else:
            self._connection_error_count += 1

        error_threshold = self._central.config.timeout_config.connectivity_error_threshold
        if self._connection_error_count > error_threshold:
            self._mark_all_devices_forced_availability(forced_availability=ForcedDeviceAvailability.FORCE_FALSE)
            if self._state_machine.state == ClientState.CONNECTED:
                self._state_machine.transition_to(
                    target=ClientState.DISCONNECTED,
                    reason=f"connection check failed (>{error_threshold} errors)",
                )
            return False
        if not self._backend.capabilities.push_updates:
            return True

        # For interfaces without ping/pong (CUxD, CCU-Jack via MQTT), skip callback_warn check
        # These interfaces are event-driven via Homematic(IP) Local but don't support ping/pong
        if not self._backend.capabilities.ping_pong:
            return True

        callback_warn = self._central.config.timeout_config.callback_warn_interval
        return (datetime.now() - self.modified_at).total_seconds() < callback_warn

    async def list_devices(self) -> tuple[DeviceDescription, ...] | None:
        """List devices of the backend."""
        return await self._backend.list_devices()

    @inspector(re_raise=False, no_raise_return=set())
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
        """Set paramsets manually."""
        is_link_call: bool = False
        checked_values = values
        try:
            # Validate values if requested
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
                    raise ClientException(i18n.tr(key="exception.client.paramset_key.invalid"))

            if rx_mode and (device := self._central.device_coordinator.get_device(address=channel_address)):
                if supports_rx_mode(command_rx_mode=rx_mode, rx_modes=device.rx_modes):
                    await self._backend.put_paramset(
                        channel_address=channel_address,
                        paramset_key=paramset_key_or_link_address,
                        values=checked_values,
                        rx_mode=rx_mode,
                    )
                else:
                    raise ClientException(i18n.tr(key="exception.client.rx_mode.unsupported", rx_mode=rx_mode))
            else:
                await self._backend.put_paramset(
                    channel_address=channel_address,
                    paramset_key=paramset_key_or_link_address,
                    values=checked_values,
                    rx_mode=rx_mode,
                )

            # If a call is related to a link then no further action is needed
            if is_link_call:
                return set()

            # Store the sent values and write temporary values for UI feedback
            dpk_values = self._last_value_send_tracker.add_put_paramset(
                channel_address=channel_address,
                paramset_key=ParamsetKey(paramset_key_or_link_address),
                values=checked_values,
            )
            self._write_temporary_value(dpk_values=dpk_values)

            # Schedule master paramset polling for BidCos interfaces
            if (
                self.interface in (Interface.BIDCOS_RF, Interface.BIDCOS_WIRED)
                and paramset_key_or_link_address == ParamsetKey.MASTER
                and (channel := self._central.device_coordinator.get_channel(channel_address=channel_address))
                is not None
            ):
                await self._poll_master_values(channel=channel, paramset_key=ParamsetKey(paramset_key_or_link_address))

            if wait_for_callback is not None and (
                device := self._central.device_coordinator.get_device(
                    address=get_device_address(address=channel_address)
                )
            ):
                await self._wait_for_state_change(
                    device=device, dpk_values=dpk_values, wait_for_callback=wait_for_callback
                )

        except BaseHomematicException as bhexc:
            raise ClientException(
                i18n.tr(
                    key="exception.client.put_paramset.failed",
                    channel_address=channel_address,
                    paramset_key=paramset_key_or_link_address,
                    values=values,
                    reason=extract_exc_args(exc=bhexc),
                )
            ) from bhexc
        else:
            return dpk_values

    async def reconnect(self) -> bool:
        """Re-init all RPC clients with exponential backoff."""
        # If in INITIALIZED state, transition to DISCONNECTED first.
        # This enables recovery when initial connection was never established
        # (e.g., startup failed before connecting). DISCONNECTED allows RECONNECTING.
        if self._state_machine.state == ClientState.INITIALIZED:
            self._state_machine.transition_to(
                target=ClientState.DISCONNECTED,
                reason="recovery from initialized state",
            )

        if self._state_machine.can_reconnect:
            self._state_machine.transition_to(target=ClientState.RECONNECTING)

            timeout_cfg = self._central.config.timeout_config
            delay = min(
                timeout_cfg.reconnect_initial_delay * (timeout_cfg.reconnect_backoff_factor**self._reconnect_attempts),
                timeout_cfg.reconnect_max_delay,
            )
            _LOGGER.debug(
                "RECONNECT: waiting to re-connect client %s for %.1fs (attempt %d)",
                self.interface_id,
                delay,
                self._reconnect_attempts + 1,
            )
            await asyncio.sleep(delay)

            if await self.reinitialize_proxy() == ProxyInitState.INIT_SUCCESS:
                self.reset_circuit_breakers()
                self._reconnect_attempts = 0
                self._connection_error_count = 0
                _LOGGER.info(
                    i18n.tr(
                        key="log.client.reconnect.reconnected",
                        interface_id=self.interface_id,
                    )
                )
                return True
            self._reconnect_attempts += 1
        return False

    async def reinitialize_proxy(self) -> ProxyInitState:
        """Reinitialize proxy."""
        await self.deinitialize_proxy()
        return await self.initialize_proxy()

    async def remove_link(self, *, sender_address: str, receiver_address: str) -> None:
        """Remove a link between two devices."""
        if not self._backend.capabilities.linking:
            return
        await self._backend.remove_link(sender_address=sender_address, receiver_address=receiver_address)

    async def rename_channel(self, *, rega_id: int, new_name: str) -> bool:
        """Rename a channel on the CCU."""
        if not self._backend.capabilities.rename:
            return False
        return await self._backend.rename_channel(rega_id=rega_id, new_name=new_name)

    async def rename_device(self, *, rega_id: int, new_name: str) -> bool:
        """Rename a device on the CCU."""
        if not self._backend.capabilities.rename:
            return False
        return await self._backend.rename_device(rega_id=rega_id, new_name=new_name)

    async def report_value_usage(self, *, channel_address: str, value_id: str, ref_counter: int) -> bool:
        """Report value usage."""
        if not self._backend.capabilities.value_usage_reporting:
            return False
        return await self._backend.report_value_usage(
            channel_address=channel_address, value_id=value_id, ref_counter=ref_counter
        )

    def reset_circuit_breakers(self) -> None:
        """Reset all circuit breakers to closed state."""
        self._backend.reset_circuit_breakers()

    async def set_install_mode(
        self,
        *,
        on: bool = True,
        time: int = 60,
        mode: int = 1,
        device_address: str | None = None,
    ) -> bool:
        """Set the install mode on the backend."""
        if not self._backend.capabilities.install_mode:
            return False
        return await self._backend.set_install_mode(on=on, time=time, mode=mode, device_address=device_address)

    async def set_metadata(self, *, address: str, data_id: str, value: dict[str, Any]) -> dict[str, Any]:
        """Write the metadata for an object."""
        if not self._backend.capabilities.metadata:
            return {}
        return await self._backend.set_metadata(address=address, data_id=data_id, value=value)

    async def set_program_state(self, *, pid: str, state: bool) -> bool:
        """Set the program state on the backend."""
        if not self._backend.capabilities.programs:
            return False
        return await self._backend.set_program_state(pid=pid, state=state)

    async def set_system_variable(self, *, legacy_name: str, value: Any) -> bool:
        """Set a system variable on the backend."""
        return await self._backend.set_system_variable(name=legacy_name, value=value)

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
        if paramset_key != ParamsetKey.VALUES:
            return await self.put_paramset(
                channel_address=channel_address,
                paramset_key_or_link_address=paramset_key,
                values={parameter: value},
                wait_for_callback=wait_for_callback,
                rx_mode=rx_mode,
                check_against_pd=check_against_pd,
            )

        dpk_values: set[DP_KEY_VALUE] = set()
        try:
            # Validate and convert value if requested
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

            if rx_mode and (device := self._central.device_coordinator.get_device(address=channel_address)):
                if supports_rx_mode(command_rx_mode=rx_mode, rx_modes=device.rx_modes):
                    await self._backend.set_value(
                        channel_address=channel_address, parameter=parameter, value=checked_value, rx_mode=rx_mode
                    )
                else:
                    raise ClientException(i18n.tr(key="exception.client.rx_mode.unsupported", rx_mode=rx_mode))
            else:
                await self._backend.set_value(channel_address=channel_address, parameter=parameter, value=checked_value)

            # Store the sent value and write temporary value for UI feedback
            dpk_values = self._last_value_send_tracker.add_set_value(
                channel_address=channel_address, parameter=parameter, value=checked_value
            )
            self._write_temporary_value(dpk_values=dpk_values)

            if wait_for_callback is not None and (
                device := self._central.device_coordinator.get_device(
                    address=get_device_address(address=channel_address)
                )
            ):
                await self._wait_for_state_change(
                    device=device, dpk_values=dpk_values, wait_for_callback=wait_for_callback
                )
        except BaseHomematicException as bhexc:
            raise ClientException(
                i18n.tr(
                    key="exception.client.set_value.failed",
                    channel_address=channel_address,
                    parameter=parameter,
                    value=value,
                    reason=extract_exc_args(exc=bhexc),
                )
            ) from bhexc
        return dpk_values

    async def stop(self) -> None:
        """Stop depending services."""
        self._unsubscribe_state_change()
        self._unsubscribe_system_status()
        self._state_machine.transition_to(target=ClientState.STOPPING, reason="stop() called")
        await self._backend.stop()
        self._state_machine.transition_to(target=ClientState.STOPPED, reason="services stopped")

    async def trigger_firmware_update(self) -> bool:
        """Trigger the CCU firmware update process."""
        if not self._backend.capabilities.firmware_update_trigger:
            return False
        return await self._backend.trigger_firmware_update()

    async def update_device_firmware(self, *, device_address: str) -> bool:
        """Update the firmware of a Homematic device."""
        if not self._backend.capabilities.device_firmware_update:
            return False
        return await self._backend.update_device_firmware(device_address=device_address)

    async def update_paramset_descriptions(self, *, device_address: str) -> None:
        """Update paramsets descriptions for provided device_address."""
        if device_description := self._central.cache_coordinator.device_descriptions.find_device_description(
            interface_id=self.interface_id, device_address=device_address
        ):
            await self.fetch_paramset_descriptions(device_description=device_description)
            await self._central.save_files(save_paramset_descriptions=True)

    def _check_get_paramset(
        self, *, channel_address: str, paramset_key: ParamsetKey, values: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Convert all values in a paramset to their correct types.

        Iterates through each parameter in the values dict, converting types
        based on the parameter description.

        Returns:
            Dict with type-converted values.

        """
        converted_values: dict[str, Any] = {}
        for param, value in values.items():
            converted_values[param] = self._convert_read_value(
                channel_address=channel_address,
                paramset_key=paramset_key,
                parameter=param,
                value=value,
            )
        return converted_values

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
            checked_values[param] = self._convert_write_value(
                channel_address=channel_address,
                paramset_key=paramset_key,
                parameter=param,
                value=value,
                operation=Operations.WRITE,
            )
        return checked_values

    def _check_set_value(self, *, channel_address: str, paramset_key: ParamsetKey, parameter: str, value: Any) -> Any:
        """Validate and convert a single value against its parameter description."""
        return self._convert_write_value(
            channel_address=channel_address,
            paramset_key=paramset_key,
            parameter=parameter,
            value=value,
            operation=Operations.WRITE,
        )

    def _convert_read_value(
        self,
        *,
        channel_address: str,
        paramset_key: ParamsetKey,
        parameter: str,
        value: Any,
    ) -> Any:
        """
        Convert a read value to its correct type based on parameter description.

        Unlike _convert_write_value (for writes), this method:
        - Does NOT validate operations (READ is implicit)
        - Does NOT validate MIN/MAX bounds (backend already enforced)
        - Only performs type conversion

        Returns:
            Converted value matching the parameter's type definition,
            or original value if parameter not found in description.

        """
        if parameter_data := self._central.cache_coordinator.paramset_descriptions.get_parameter_data(
            interface_id=self.interface_id,
            channel_address=channel_address,
            paramset_key=paramset_key,
            parameter=parameter,
        ):
            pd_type = parameter_data["TYPE"]
            pd_value_list = tuple(parameter_data["VALUE_LIST"]) if parameter_data.get("VALUE_LIST") else None
            return convert_value(value=value, target_type=pd_type, value_list=pd_value_list)
        # Return original value if parameter not in description
        return value

    def _convert_write_value(
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
            interface_id=self.interface_id,
            channel_address=channel_address,
            paramset_key=paramset_key,
            parameter=parameter,
        ):
            pd_type = parameter_data["TYPE"]
            pd_op = int(parameter_data["OPERATIONS"])
            op_mask = int(operation)
            # Some MASTER parameter_data have operations set to 0, so these can not be used for validation
            if pd_op > 0 and ((pd_op & op_mask) != op_mask):
                raise ClientException(
                    i18n.tr(
                        key="exception.client.parameter.operation_unsupported",
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
                # Some devices (e.g., HM-CC-VG-1) return MIN/MAX as strings instead of numbers
                if pd_min is not None:
                    pd_min = float(pd_min) if pd_type == ParameterType.FLOAT else int(pd_min)
                if pd_max is not None:
                    pd_max = float(pd_max) if pd_type == ParameterType.FLOAT else int(pd_max)
                if pd_min is not None and converted_value < pd_min:
                    raise ValidationException(
                        i18n.tr(
                            key="exception.client.parameter.value_below_min",
                            parameter=parameter,
                            value=converted_value,
                            min_value=pd_min,
                        )
                    )
                if pd_max is not None and converted_value > pd_max:
                    raise ValidationException(
                        i18n.tr(
                            key="exception.client.parameter.value_above_max",
                            parameter=parameter,
                            value=converted_value,
                            max_value=pd_max,
                        )
                    )

            return converted_value
        raise ClientException(
            i18n.tr(
                key="exception.client.parameter.not_found",
                parameter=parameter,
                interface_id=self.interface_id,
                channel_address=channel_address,
                paramset_key=paramset_key,
            )
        )

    def _get_init_url(self) -> str:
        """Return the init URL."""
        callback_host = (
            self._central.config.callback_host if self._central.config.callback_host else self._central.callback_ip_addr
        )
        callback_port = (
            self._central.config.callback_port_xml_rpc
            if self._central.config.callback_port_xml_rpc
            else self._central.listen_port_xml_rpc
        )
        return f"http://{callback_host}:{callback_port}"

    async def _get_paramset_description(
        self, *, address: str, paramset_key: ParamsetKey
    ) -> dict[str, ParameterData] | None:
        """
        Fetch a paramset description via backend, with request coalescing.

        Uses request coalescing to deduplicate concurrent requests for the same
        address and paramset_key combination. This is particularly beneficial
        during device discovery when multiple channels request the same descriptions.
        """
        key = make_coalesce_key(method="getParamsetDescription", args=(address, paramset_key))

        async def _fetch() -> dict[str, ParameterData] | None:
            try:
                return await self._backend.get_paramset_description(channel_address=address, paramset_key=paramset_key)
            except BaseHomematicException as bhexc:
                _LOGGER.debug(
                    "GET_PARAMSET_DESCRIPTION failed with %s [%s] for %s address %s",
                    bhexc.name,
                    extract_exc_args(exc=bhexc),
                    paramset_key,
                    address,
                )
                return None

        return await self._paramset_description_coalescer.execute(key=key, executor=_fetch)

    def _mark_all_devices_forced_availability(self, *, forced_availability: ForcedDeviceAvailability) -> None:
        """Mark device's availability state for this interface."""
        available = forced_availability != ForcedDeviceAvailability.FORCE_FALSE
        if not available or self._state_machine.is_available != available:
            for device in self._central.device_registry.devices:
                if device.interface_id == self.interface_id:
                    device.set_forced_availability(forced_availability=forced_availability)
            _LOGGER.debug(
                "MARK_ALL_DEVICES_FORCED_AVAILABILITY: marked all devices %s for %s",
                "available" if available else "unavailable",
                self.interface_id,
            )

    def _on_client_state_changed_event(self, *, event: ClientStateChangedEvent) -> None:
        """Handle client state machine transitions."""
        self._central.event_bus.publish_sync(
            event=SystemStatusChangedEvent(
                timestamp=datetime.now(),
                client_state=(event.interface_id, ClientState(event.old_state), ClientState(event.new_state)),
            )
        )

    def _on_system_status_event(self, *, event: SystemStatusChangedEvent) -> None:
        """Handle system status events."""
        if event.connection_state and event.connection_state[0] == self.interface_id and event.connection_state[1]:
            self._ping_pong_tracker.clear()
            _LOGGER.debug(
                "PING PONG CACHE: Cleared on connection restored: %s",
                self.interface_id,
            )

    async def _poll_master_values(self, *, channel: ChannelProtocol, paramset_key: ParamsetKey) -> None:
        """Poll master paramset values after write for BidCos devices."""

        async def poll_master_dp_values() -> None:
            """Load master paramset values with intervals."""
            for interval in self._central.config.schedule_timer_config.master_poll_after_send_intervals:
                await asyncio.sleep(interval)
                for dp in channel.get_readable_data_points(paramset_key=paramset_key):
                    await dp.load_data_point_value(call_source=CallSource.MANUAL_OR_SCHEDULED, direct_call=True)

        self._central.looper.create_task(target=poll_master_dp_values(), name="poll_master_dp_values")

    def _record_callback_timeout_incident(
        self,
        *,
        seconds_since_last_event: float,
        callback_warn_interval: float,
        last_event_time: datetime,
    ) -> None:
        """Record a CALLBACK_TIMEOUT incident for diagnostics."""
        incident_recorder = self._central.cache_coordinator.incident_store

        # Get circuit breaker state safely
        circuit_breaker_state: str | None = None
        if (cb := self._backend.circuit_breaker) is not None:
            circuit_breaker_state = cb.state.value

        context = {
            "seconds_since_last_event": round(seconds_since_last_event, 2),
            "callback_warn_interval": callback_warn_interval,
            "last_event_time": last_event_time.strftime(DATETIME_FORMAT_MILLIS),
            "client_state": self._state_machine.state.value,
            "circuit_breaker_state": circuit_breaker_state,
        }

        async def _record() -> None:
            try:
                await incident_recorder.record_incident(
                    incident_type=IncidentType.CALLBACK_TIMEOUT,
                    severity=IncidentSeverity.WARNING,
                    message=f"No callback received for {self.interface_id} in {int(seconds_since_last_event)} seconds",
                    interface_id=self.interface_id,
                    context=context,
                )
            except Exception as err:
                _LOGGER.debug("Failed to record CALLBACK_TIMEOUT incident: %s", err)

        self._central.looper.create_task(
            target=_record(),
            name=f"record_callback_timeout_incident_{self.interface_id}",
        )

    async def _wait_for_state_change(
        self, *, device: DeviceProtocol, dpk_values: set[DP_KEY_VALUE], wait_for_callback: int
    ) -> None:
        """Wait for device state change or timeout."""
        await wait_for_state_change_or_timeout(
            device=device, dpk_values=dpk_values, wait_for_callback=wait_for_callback
        )

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
