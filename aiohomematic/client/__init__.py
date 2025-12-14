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

import asyncio
from datetime import datetime
import logging
from typing import Any, Final, cast

from aiohomematic import central as hmcu, i18n
from aiohomematic.central.integration_events import SystemStatusEvent
from aiohomematic.client.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState
from aiohomematic.client.handlers import (
    BackupHandler,
    DeviceOperationsHandler,
    FirmwareHandler,
    LinkManagementHandler,
    MetadataHandler,
    ProgramHandler,
    SystemVariableHandler,
)
from aiohomematic.client.json_rpc import AioJsonRpcAioHttpClient
from aiohomematic.client.request_coalescer import RequestCoalescer, make_coalesce_key
from aiohomematic.client.rpc_proxy import AioXmlRpcProxy, BaseRpcProxy
from aiohomematic.client.state_machine import ClientStateMachine, InvalidStateTransitionError
from aiohomematic.const import (
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
    VIRTUAL_REMOTE_MODELS,
    WAIT_FOR_CALLBACK,
    Backend,
    BackupData,
    CallSource,
    ClientState,
    CommandRxMode,
    DescriptionMarker,
    DeviceDescription,
    ForcedDeviceAvailability,
    InboxDeviceData,
    Interface,
    ParameterData,
    ParameterType,
    ParamsetKey,
    ProductGroup,
    ProgramData,
    ProxyInitState,
    RpcServerType,
    ServiceMessageData,
    ServiceMessageType,
    SystemInformation,
    SystemUpdateData,
    SystemVariableData,
)
from aiohomematic.decorators import inspector
from aiohomematic.exceptions import BaseHomematicException, ClientException, NoConnectionException
from aiohomematic.interfaces.client import ClientDependencies, ClientProtocol
from aiohomematic.interfaces.model import DeviceProtocol
from aiohomematic.property_decorators import hm_property
from aiohomematic.store import CommandCache, PingPongCache
from aiohomematic.support import LogContextMixin, build_xml_rpc_headers, build_xml_rpc_uri, extract_exc_args

__all__ = [
    "AioJsonRpcAioHttpClient",
    "BaseRpcProxy",
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitState",
    "ClientConfig",
    "ClientState",
    "ClientStateMachine",
    "InterfaceConfig",
    "InvalidStateTransitionError",
    "RequestCoalescer",
    "make_coalesce_key",
]

_LOGGER: Final = logging.getLogger(__name__)

_NAME: Final = "NAME"

_CCU_JSON_VALUE_TYPE: Final = {
    "ACTION": "bool",
    "BOOL": "bool",
    "ENUM": "list",
    "FLOAT": "double",
    "INTEGER": "int",
    "STRING": "string",
}


class ClientCCU(ClientProtocol, LogContextMixin):
    """
    Client object to access the backends via XML-RPC or JSON-RPC.

    This class acts as a facade over specialized handler classes:
    - DeviceOperationsHandler: Value read/write, paramset operations
    - LinkManagementHandler: Device linking operations
    - FirmwareHandler: Firmware update operations
    - SystemVariableHandler: System variable CRUD
    - ProgramHandler: Program execution and state
    - BackupHandler: Backup creation and download
    - MetadataHandler: Metadata, renaming, rooms, functions, install mode
    """

    __slots__ = (
        "_available",
        "_backup_handler",
        "_config",
        "_connection_error_count",
        "_device_ops_handler",
        "_firmware_handler",
        "_is_callback_alive",
        "_is_initialized",
        "_json_rpc_client",
        "_last_value_send_cache",
        "_link_handler",
        "_metadata_handler",
        "_modified_at",
        "_ping_pong_cache",
        "_program_handler",
        "_proxy",
        "_proxy_read",
        "_reconnect_attempts",
        "_state_machine",
        "_sysvar_handler",
        "_system_information",
    )

    def __init__(self, *, client_config: ClientConfig) -> None:
        """Initialize the Client."""
        self._config: Final = client_config
        self._json_rpc_client: Final = client_config.central.json_rpc_client
        self._last_value_send_cache = CommandCache(interface_id=client_config.interface_id)
        self._state_machine: Final = ClientStateMachine(interface_id=client_config.interface_id)
        # Wire up state machine callback to emit events
        self._state_machine.on_state_change = self._on_client_state_change
        self._connection_error_count: int = 0
        self._is_callback_alive: bool = True
        self._reconnect_attempts: int = 0
        self._ping_pong_cache: Final = PingPongCache(
            event_bus_provider=client_config.central,
            central_info=client_config.central,
            interface_id=client_config.interface_id,
            connection_state=client_config.central.connection_state,
        )
        self._proxy: BaseRpcProxy
        self._proxy_read: BaseRpcProxy
        self._system_information: SystemInformation
        self._modified_at: datetime = INIT_DATETIME

        # Subscribe to connection state changes to clear ping/pong cache on reconnect.
        # This prevents stale pending pongs from causing false mismatch alarms
        # after CCU restart when PINGs sent during downtime cannot be answered.
        client_config.central.event_bus.subscribe(
            event_type=SystemStatusEvent,
            event_key=None,
            handler=self._on_system_status_event,
        )

        # Handler instances (initialized after proxy setup in init_client)
        self._device_ops_handler: DeviceOperationsHandler
        self._link_handler: LinkManagementHandler
        self._firmware_handler: FirmwareHandler
        self._sysvar_handler: SystemVariableHandler
        self._program_handler: ProgramHandler
        self._backup_handler: BackupHandler
        self._metadata_handler: MetadataHandler

    def __str__(self) -> str:
        """Provide some useful information."""
        return f"interface_id: {self.interface_id}"

    @property
    def all_circuit_breakers_closed(self) -> bool:
        """Return True if all circuit breakers are in closed state."""
        if self._proxy.circuit_breaker.state != CircuitState.CLOSED:
            return False
        if (
            hasattr(self, "_proxy_read")
            and self._proxy_read is not self._proxy
            and self._proxy_read.circuit_breaker.state != CircuitState.CLOSED
        ):
            return False
        return self._json_rpc_client.circuit_breaker.state == CircuitState.CLOSED

    @property
    def available(self) -> bool:
        """Return the availability of the client."""
        return self._state_machine.is_available

    @property
    def central(self) -> ClientDependencies:
        """Return the central of the client."""
        return self._config.central

    @property
    def interface(self) -> Interface:
        """Return the interface of the client."""
        return self._config.interface

    @property
    def is_initialized(self) -> bool:
        """Return if interface is initialized."""
        return self._state_machine.state in (
            ClientState.CONNECTED,
            ClientState.DISCONNECTED,
            ClientState.RECONNECTING,
        )

    @property
    def last_value_send_cache(self) -> CommandCache:
        """Return the last value send cache."""
        return self._last_value_send_cache

    @property
    def model(self) -> str:
        """Return the model of the backend."""
        return Backend.CCU

    @property
    def modified_at(self) -> datetime:
        """Return the last update datetime value."""
        return self._modified_at

    @modified_at.setter
    def modified_at(self, value: datetime) -> None:
        """Write the last update datetime value."""
        self._modified_at = value

    @property
    def ping_pong_cache(self) -> PingPongCache:
        """Return the ping pong cache."""
        return self._ping_pong_cache

    @property
    def state(self) -> ClientState:
        """Return the current client state."""
        return self._state_machine.state

    @property
    def supports_backup(self) -> bool:
        """Return if the backend supports backup creation and download."""
        return self._system_information.supports_backup

    @property
    def supports_device_firmware_update(self) -> bool:
        """Return if the backend supports device firmware updates."""
        return True

    @property
    def supports_firmware_update_trigger(self) -> bool:
        """Return if the backend supports triggering system firmware updates."""
        return True

    @property
    def supports_firmware_updates(self) -> bool:
        """Return the supports_ping_pong info of the backend."""
        return self._config.supports_firmware_updates

    @property
    def supports_functions(self) -> bool:
        """Return if interface supports functions."""
        return True

    @property
    def supports_inbox_devices(self) -> bool:
        """Return if the backend supports inbox devices."""
        return True

    @property
    def supports_install_mode(self) -> bool:
        """Return if the backend supports install mode operations."""
        return True

    @property
    def supports_linking(self) -> bool:
        """Return if the backend supports device linking operations."""
        return self._config.supports_linking

    @property
    def supports_metadata(self) -> bool:
        """Return if the backend supports metadata operations."""
        return True

    @property
    def supports_ping_pong(self) -> bool:
        """Return the supports_ping_pong info of the backend."""
        return self._config.supports_ping_pong

    @property
    def supports_programs(self) -> bool:
        """Return if interface supports programs."""
        return True

    @property
    def supports_push_updates(self) -> bool:
        """Return the client supports push update."""
        return self._config.supports_push_updates

    @property
    def supports_rega_id_lookup(self) -> bool:
        """Return if the backend supports ReGa ID lookups."""
        return True

    @property
    def supports_rename(self) -> bool:
        """Return if the backend supports renaming devices and channels."""
        return True

    @property
    def supports_rooms(self) -> bool:
        """Return if interface supports rooms."""
        return True

    @property
    def supports_rpc_callback(self) -> bool:
        """Return if interface support rpc callback."""
        return self._config.supports_rpc_callback

    @property
    def supports_service_messages(self) -> bool:
        """Return if the backend supports service messages."""
        return True

    @property
    def supports_system_update_info(self) -> bool:
        """Return if the backend supports system update information."""
        return True

    @property
    def supports_value_usage_reporting(self) -> bool:
        """Return if the backend supports value usage reporting."""
        return True

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

    async def accept_device_in_inbox(self, *, device_address: str) -> bool:
        """Accept a device from the CCU inbox."""
        return await self._metadata_handler.accept_device_in_inbox(device_address=device_address)

    async def add_link(
        self,
        *,
        sender_address: str,
        receiver_address: str,
        name: str,
        description: str,
    ) -> None:
        """Add a link between two devices."""
        return await self._link_handler.add_link(
            sender_address=sender_address,
            receiver_address=receiver_address,
            name=name,
            description=description,
        )

    @inspector(re_raise=False, no_raise_return=False)
    async def check_connection_availability(self, *, handle_ping_pong: bool) -> bool:
        """Check if _proxy is still initialized."""
        try:
            dt_now = datetime.now()
            if handle_ping_pong and self.supports_ping_pong and self.is_initialized:
                token = dt_now.strftime(format=DATETIME_FORMAT_MILLIS)
                callerId = f"{self.interface_id}#{token}" if handle_ping_pong else self.interface_id
                await self._proxy.ping(callerId)
                self._ping_pong_cache.handle_send_ping(ping_token=token)
            elif not self.is_initialized:
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

    async def create_backup_and_download(
        self,
        *,
        max_wait_time: float = 300.0,
        poll_interval: float = 5.0,
    ) -> BackupData | None:
        """Create a backup on the CCU and download it."""
        return await self._backup_handler.create_backup_and_download(
            max_wait_time=max_wait_time,
            poll_interval=poll_interval,
        )

    async def deinitialize_proxy(self) -> ProxyInitState:
        """De-init to stop the backend from sending events for this remote."""
        if not self.supports_rpc_callback:
            self._state_machine.transition_to(target=ClientState.DISCONNECTED)
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
            self._state_machine.transition_to(target=ClientState.DISCONNECTED)
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
        return await self._sysvar_handler.delete_system_variable(name=name)

    async def execute_program(self, *, pid: str) -> bool:
        """Execute a program on the backend."""
        return await self._program_handler.execute_program(pid=pid)

    async def fetch_all_device_data(self) -> None:
        """Fetch all device data from the backend."""
        return await self._device_ops_handler.fetch_all_device_data()

    async def fetch_device_details(self) -> None:
        """Get all names via JSON-RPS and store in data.NAMES."""
        return await self._device_ops_handler.fetch_device_details()

    async def fetch_paramset_description(self, *, channel_address: str, paramset_key: ParamsetKey) -> None:
        """Fetch a specific paramset and add it to the known ones."""
        return await self._device_ops_handler.fetch_paramset_description(
            channel_address=channel_address,
            paramset_key=paramset_key,
        )

    async def fetch_paramset_descriptions(self, *, device_description: DeviceDescription) -> None:
        """Fetch paramsets for provided device description."""
        return await self._device_ops_handler.fetch_paramset_descriptions(device_description=device_description)

    async def get_all_device_descriptions(self, *, device_address: str) -> tuple[DeviceDescription, ...]:
        """Get all device descriptions from the backend."""
        return await self._device_ops_handler.get_all_device_descriptions(device_address=device_address)

    async def get_all_functions(self) -> dict[str, set[str]]:
        """Get all functions from the backend."""
        return await self._metadata_handler.get_all_functions()

    async def get_all_paramset_descriptions(
        self, *, device_descriptions: tuple[DeviceDescription, ...]
    ) -> dict[str, dict[ParamsetKey, dict[str, ParameterData]]]:
        """Get all paramset descriptions for provided device descriptions."""
        return await self._device_ops_handler.get_all_paramset_descriptions(device_descriptions=device_descriptions)

    async def get_all_programs(
        self,
        *,
        markers: tuple[DescriptionMarker | str, ...],
    ) -> tuple[ProgramData, ...]:
        """Get all programs, if available."""
        return await self._program_handler.get_all_programs(markers=markers)

    async def get_all_rooms(self) -> dict[str, set[str]]:
        """Get all rooms from the backend."""
        return await self._metadata_handler.get_all_rooms()

    async def get_all_system_variables(
        self,
        *,
        markers: tuple[DescriptionMarker | str, ...],
    ) -> tuple[SystemVariableData, ...] | None:
        """Get all system variables from the backend."""
        return await self._sysvar_handler.get_all_system_variables(markers=markers)

    async def get_device_description(self, *, address: str) -> DeviceDescription | None:
        """Get device descriptions from the backend."""
        return await self._device_ops_handler.get_device_description(address=address)

    async def get_inbox_devices(self) -> tuple[InboxDeviceData, ...]:
        """Get all devices in the inbox (not yet configured)."""
        return await self._metadata_handler.get_inbox_devices()

    async def get_install_mode(self) -> int:
        """Return the remaining time in install mode."""
        return await self._metadata_handler.get_install_mode()

    async def get_link_peers(self, *, address: str) -> tuple[str, ...]:
        """Return a list of link peers."""
        return await self._link_handler.get_link_peers(address=address)

    async def get_links(self, *, address: str, flags: int) -> dict[str, Any]:
        """Return a list of links."""
        return await self._link_handler.get_links(address=address, flags=flags)

    async def get_metadata(self, *, address: str, data_id: str) -> dict[str, Any]:
        """Return the metadata for an object."""
        return await self._metadata_handler.get_metadata(address=address, data_id=data_id)

    async def get_paramset(
        self,
        *,
        address: str,
        paramset_key: ParamsetKey | str,
        call_source: CallSource = CallSource.MANUAL_OR_SCHEDULED,
    ) -> dict[str, Any]:
        """Return a paramset from the backend."""
        return await self._device_ops_handler.get_paramset(
            address=address,
            paramset_key=paramset_key,
            call_source=call_source,
        )

    async def get_paramset_descriptions(
        self, *, device_description: DeviceDescription
    ) -> dict[str, dict[ParamsetKey, dict[str, ParameterData]]]:
        """Get paramsets for provided device description."""
        return await self._device_ops_handler.get_paramset_descriptions(device_description=device_description)

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
        return await self._metadata_handler.get_rega_id_by_address(address=address)

    async def get_service_messages(
        self,
        *,
        message_type: ServiceMessageType | None = None,
    ) -> tuple[ServiceMessageData, ...]:
        """Get all active service messages from the backend."""
        return await self._metadata_handler.get_service_messages(message_type=message_type)

    async def get_system_update_info(self) -> SystemUpdateData | None:
        """Get system update information from the backend."""
        return await self._metadata_handler.get_system_update_info()

    async def get_system_variable(self, *, name: str) -> Any:
        """Get single system variable from the backend."""
        return await self._sysvar_handler.get_system_variable(name=name)

    async def get_value(
        self,
        *,
        channel_address: str,
        paramset_key: ParamsetKey,
        parameter: str,
        call_source: CallSource = CallSource.MANUAL_OR_SCHEDULED,
    ) -> Any:
        """Return a value from the backend."""
        return await self._device_ops_handler.get_value(
            channel_address=channel_address,
            paramset_key=paramset_key,
            parameter=parameter,
            call_source=call_source,
        )

    def get_virtual_remote(self) -> DeviceProtocol | None:
        """Get the virtual remote for the Client."""
        for model in VIRTUAL_REMOTE_MODELS:
            for device in self.central.device_registry.devices:
                if device.interface_id == self.interface_id and device.model == model:
                    return device
        return None

    async def has_program_ids(self, *, rega_id: int) -> bool:
        """Return if a channel has program ids."""
        return await self._program_handler.has_program_ids(rega_id=rega_id)

    @inspector
    async def init_client(self) -> None:
        """Initialize the client."""
        self._state_machine.transition_to(target=ClientState.INITIALIZING)
        try:
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
                self._init_handlers()
            self._state_machine.transition_to(target=ClientState.INITIALIZED)
        except Exception:
            self._state_machine.transition_to(target=ClientState.FAILED)
            raise

    async def initialize_proxy(self) -> ProxyInitState:
        """Initialize the proxy has to tell the backend where to send the events."""
        self._state_machine.transition_to(target=ClientState.CONNECTING)
        if not self.supports_rpc_callback:
            if device_descriptions := await self.list_devices():
                await self.central.device_coordinator.add_new_devices(
                    interface_id=self.interface_id, device_descriptions=device_descriptions
                )
                self._state_machine.transition_to(target=ClientState.CONNECTED)
                return ProxyInitState.INIT_SUCCESS
            self._state_machine.transition_to(target=ClientState.FAILED)
            # Mark devices as unavailable when device listing fails
            self._mark_all_devices_forced_availability(forced_availability=ForcedDeviceAvailability.FORCE_FALSE)
            return ProxyInitState.INIT_FAILED
        try:
            _LOGGER.debug("PROXY_INIT: init('%s', '%s')", self._config.init_url, self.interface_id)
            self._ping_pong_cache.clear()
            await self._proxy.init(self._config.init_url, self.interface_id)
            self._state_machine.transition_to(target=ClientState.CONNECTED)
            self._mark_all_devices_forced_availability(forced_availability=ForcedDeviceAvailability.NOT_SET)
            # Clear any stale connection issues from failed attempts during reconnection
            # This ensures subsequent RPC calls are not blocked
            self._proxy.clear_connection_issue()
            _LOGGER.debug("PROXY_INIT: Proxy for %s initialized", self.interface_id)

            # Recreate proxies AFTER successful init to get fresh HTTP transport
            # This prevents "ResponseNotReady" errors on subsequent requests that occur
            # when the HTTP connection is in an inconsistent state after reconnection.
            # The callback URL remains unchanged (XML-RPC server port stays the same).
            try:
                _LOGGER.debug(
                    "PROXY_INIT: Recreating proxy objects for %s to get fresh HTTP transport",
                    self.interface_id,
                )
                self._proxy = await self._config.create_rpc_proxy(
                    interface=self.interface,
                    auth_enabled=self.system_information.auth_enabled,
                )
                self._proxy_read = await self._config.create_rpc_proxy(
                    interface=self.interface,
                    auth_enabled=self.system_information.auth_enabled,
                    max_workers=self._config.max_read_workers,
                )
                self._init_handlers()
                _LOGGER.debug("PROXY_INIT: Proxies recreated with fresh transport for %s", self.interface_id)
            except Exception as exc:
                _LOGGER.warning(  # i18n-log: ignore
                    "PROXY_INIT: Failed to recreate proxies for %s: %s - continuing with existing proxies",
                    self.interface_id,
                    exc,
                )
        except BaseHomematicException as bhexc:
            _LOGGER.error(  # i18n-log: ignore
                "PROXY_INIT failed: %s [%s] Unable to initialize proxy for %s",
                bhexc.name,
                extract_exc_args(exc=bhexc),
                self.interface_id,
            )
            self.modified_at = INIT_DATETIME
            self._state_machine.transition_to(target=ClientState.FAILED)
            # Mark devices as unavailable when proxy init fails
            # This ensures entities show unavailable during CCU restart/recovery
            self._mark_all_devices_forced_availability(forced_availability=ForcedDeviceAvailability.FORCE_FALSE)
            return ProxyInitState.INIT_FAILED
        self.modified_at = datetime.now()
        return ProxyInitState.INIT_SUCCESS

    def is_callback_alive(self) -> bool:
        """Return if XmlRPC-Server is alive based on received events for this client."""
        if not self.supports_ping_pong:
            return True

        # If client is in RECONNECTING or FAILED state, callback is definitely not alive
        # This ensures reconnection continues after CCU restart until init() succeeds
        if self._state_machine.is_failed or self._state_machine.state == ClientState.RECONNECTING:
            return False

        # Check event timestamp for all other states (including startup states)
        if (
            last_events_dt := self.central.event_coordinator.get_last_event_seen_for_interface(
                interface_id=self.interface_id
            )
        ) is not None:
            callback_warn = self._config.central.config.timeout_config.callback_warn_interval
            if (seconds_since_last_event := (datetime.now() - last_events_dt).total_seconds()) > callback_warn:
                if self._is_callback_alive:
                    self.central.event_bus.publish_sync(
                        event=SystemStatusEvent(
                            timestamp=datetime.now(),
                            callback_state=(self.interface_id, False),
                        )
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
                self.central.event_bus.publish_sync(
                    event=SystemStatusEvent(
                        timestamp=datetime.now(),
                        callback_state=(self.interface_id, True),
                    )
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
            # Update state machine to reflect connection loss
            if self._state_machine.state == ClientState.CONNECTED:
                self._state_machine.transition_to(target=ClientState.DISCONNECTED)
            return False
        if not self.supports_push_updates:
            return True

        callback_warn = self._config.central.config.timeout_config.callback_warn_interval
        return (datetime.now() - self.modified_at).total_seconds() < callback_warn

    async def list_devices(self) -> tuple[DeviceDescription, ...] | None:
        """List devices of the backend."""
        return await self._device_ops_handler.list_devices()

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
        return await self._device_ops_handler.put_paramset(
            channel_address=channel_address,
            paramset_key_or_link_address=paramset_key_or_link_address,
            values=values,
            wait_for_callback=wait_for_callback,
            rx_mode=rx_mode,
            check_against_pd=check_against_pd,
        )

    async def reconnect(self) -> bool:
        """Re-init all RPC clients with exponential backoff."""
        if self._state_machine.can_reconnect:
            self._state_machine.transition_to(target=ClientState.RECONNECTING)

            # Calculate exponential backoff delay using timeout_config
            timeout_cfg = self._config.central.config.timeout_config
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
                # Reset circuit breakers after successful reconnect to allow
                # immediate data refresh without waiting for recovery timeout
                self.reset_circuit_breakers()
                self._reconnect_attempts = 0  # Reset on success
                self._connection_error_count = 0  # Reset error count on success
                _LOGGER.info(
                    i18n.tr(
                        "log.client.reconnect.reconnected",
                        interface_id=self.interface_id,
                    )
                )
                return True
            # Increment attempt counter for next reconnect try
            self._reconnect_attempts += 1
            # State machine already transitioned in reinitialize_proxy
        return False

    async def reinitialize_proxy(self) -> ProxyInitState:
        """Reinit Proxy."""
        await self.deinitialize_proxy()
        return await self.initialize_proxy()

    async def remove_link(self, *, sender_address: str, receiver_address: str) -> None:
        """Remove a link between two devices."""
        return await self._link_handler.remove_link(
            sender_address=sender_address,
            receiver_address=receiver_address,
        )

    async def rename_channel(self, *, rega_id: int, new_name: str) -> bool:
        """Rename a channel on the CCU."""
        return await self._metadata_handler.rename_channel(rega_id=rega_id, new_name=new_name)

    async def rename_device(self, *, rega_id: int, new_name: str) -> bool:
        """Rename a device on the CCU."""
        return await self._metadata_handler.rename_device(rega_id=rega_id, new_name=new_name)

    async def report_value_usage(self, *, address: str, value_id: str, ref_counter: int) -> bool:
        """Report value usage."""
        return await self._device_ops_handler.report_value_usage(
            address=address,
            value_id=value_id,
            ref_counter=ref_counter,
            supports=self.supports_value_usage_reporting,
        )

    def reset_circuit_breakers(self) -> None:
        """Reset all circuit breakers to closed state."""
        self._proxy.circuit_breaker.reset()
        if hasattr(self, "_proxy_read") and self._proxy_read is not self._proxy:
            self._proxy_read.circuit_breaker.reset()
        self._json_rpc_client.circuit_breaker.reset()
        _LOGGER.debug(
            "RESET_CIRCUIT_BREAKERS: All circuit breakers reset for %s",
            self.interface_id,
        )

    async def set_install_mode(
        self,
        *,
        on: bool = True,
        time: int = 60,
        mode: int = 1,
        device_address: str | None = None,
    ) -> bool:
        """Set the install mode on the backend."""
        return await self._metadata_handler.set_install_mode(
            on=on,
            time=time,
            mode=mode,
            device_address=device_address,
        )

    async def set_metadata(self, *, address: str, data_id: str, value: dict[str, Any]) -> dict[str, Any]:
        """Write the metadata for an object."""
        return await self._metadata_handler.set_metadata(address=address, data_id=data_id, value=value)

    async def set_program_state(self, *, pid: str, state: bool) -> bool:
        """Set the program state on the backend."""
        return await self._program_handler.set_program_state(pid=pid, state=state)

    async def set_system_variable(self, *, legacy_name: str, value: Any) -> bool:
        """Set a system variable on the backend."""
        return await self._sysvar_handler.set_system_variable(legacy_name=legacy_name, value=value)

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
        return await self._device_ops_handler.set_value(
            channel_address=channel_address,
            paramset_key=paramset_key,
            parameter=parameter,
            value=value,
            wait_for_callback=wait_for_callback,
            rx_mode=rx_mode,
            check_against_pd=check_against_pd,
        )

    async def stop(self) -> None:
        """Stop depending services."""
        self._state_machine.transition_to(target=ClientState.STOPPING)
        if self.supports_rpc_callback:
            await self._proxy.stop()
            await self._proxy_read.stop()
        self._state_machine.transition_to(target=ClientState.STOPPED)

    async def trigger_firmware_update(self) -> bool:
        """Trigger the CCU firmware update process."""
        return await self._firmware_handler.trigger_firmware_update()

    async def update_device_firmware(self, *, device_address: str) -> bool:
        """Update the firmware of a Homematic device."""
        return await self._firmware_handler.update_device_firmware(device_address=device_address)

    async def update_paramset_descriptions(self, *, device_address: str) -> None:
        """Update paramsets descriptions for provided device_address."""
        return await self._device_ops_handler.update_paramset_descriptions(device_address=device_address)

    async def _get_system_information(self) -> SystemInformation:
        """Get system information of the backend."""
        return await self._json_rpc_client.get_system_information()

    def _init_handlers(self) -> None:
        """Initialize all handler instances."""
        self._device_ops_handler = DeviceOperationsHandler(
            central=self._config.central,
            interface=self._config.interface,
            interface_id=self._config.interface_id,
            json_rpc_client=self._json_rpc_client,
            proxy=self._proxy,
            proxy_read=self._proxy_read,
            last_value_send_cache=self._last_value_send_cache,
        )

        self._link_handler = LinkManagementHandler(
            central=self._config.central,
            interface=self._config.interface,
            interface_id=self._config.interface_id,
            json_rpc_client=self._json_rpc_client,
            proxy=self._proxy,
            proxy_read=self._proxy_read,
            supports_linking=self.supports_linking,
        )

        self._firmware_handler = FirmwareHandler(
            central=self._config.central,
            interface=self._config.interface,
            interface_id=self._config.interface_id,
            json_rpc_client=self._json_rpc_client,
            proxy=self._proxy,
            proxy_read=self._proxy_read,
            supports_device_firmware_update=self.supports_device_firmware_update,
            supports_firmware_update_trigger=self.supports_firmware_update_trigger,
        )

        self._sysvar_handler = SystemVariableHandler(
            central=self._config.central,
            interface=self._config.interface,
            interface_id=self._config.interface_id,
            json_rpc_client=self._json_rpc_client,
            proxy=self._proxy,
            proxy_read=self._proxy_read,
        )

        self._program_handler = ProgramHandler(
            central=self._config.central,
            interface=self._config.interface,
            interface_id=self._config.interface_id,
            json_rpc_client=self._json_rpc_client,
            proxy=self._proxy,
            proxy_read=self._proxy_read,
            supports_programs=self.supports_programs,
        )

        self._backup_handler = BackupHandler(
            central=self._config.central,
            interface=self._config.interface,
            interface_id=self._config.interface_id,
            json_rpc_client=self._json_rpc_client,
            proxy=self._proxy,
            proxy_read=self._proxy_read,
            supports_backup=self.supports_backup,
            system_information=self._system_information,
        )

        self._metadata_handler = MetadataHandler(
            central=self._config.central,
            interface=self._config.interface,
            interface_id=self._config.interface_id,
            json_rpc_client=self._json_rpc_client,
            proxy=self._proxy,
            proxy_read=self._proxy_read,
            supports_functions=self.supports_functions,
            supports_inbox_devices=self.supports_inbox_devices,
            supports_install_mode=self.supports_install_mode,
            supports_metadata=self.supports_metadata,
            supports_rega_id_lookup=self.supports_rega_id_lookup,
            supports_rename=self.supports_rename,
            supports_rooms=self.supports_rooms,
            supports_service_messages=self.supports_service_messages,
            supports_system_update_info=self.supports_system_update_info,
        )

    def _mark_all_devices_forced_availability(self, *, forced_availability: ForcedDeviceAvailability) -> None:
        """Mark device's availability state for this interface."""
        available = forced_availability != ForcedDeviceAvailability.FORCE_FALSE
        # Always update devices when marking unavailable (FORCE_FALSE) to ensure
        # entities show unavailable during connection failures.
        # Only skip updates when already in matching available state.
        if not available or self._state_machine.is_available != available:
            for device in self.central.device_registry.devices:
                if device.interface_id == self.interface_id:
                    device.set_forced_availability(forced_availability=forced_availability)
            _LOGGER.debug(
                "MARK_ALL_DEVICES_FORCED_AVAILABILITY: marked all devices %s for %s",
                "available" if available else "unavailable",
                self.interface_id,
            )

    def _on_client_state_change(self, *, old_state: ClientState, new_state: ClientState) -> None:
        """Handle client state machine transitions by emitting events."""
        self._config.central.event_bus.publish_sync(
            event=SystemStatusEvent(
                timestamp=datetime.now(),
                client_state=(self.interface_id, old_state, new_state),
            )
        )

    def _on_system_status_event(self, *, event: SystemStatusEvent) -> None:
        """Handle system status events to clear ping/pong cache on reconnect."""
        if event.connection_state and event.connection_state[0] == self.interface_id and event.connection_state[1]:
            # Clear stale ping/pong state when connection is restored.
            # PINGs sent during CCU downtime cannot receive PONGs, so the cache
            # would contain stale entries that cause false mismatch alarms.
            self._ping_pong_cache.clear()
            _LOGGER.debug(
                "PING PONG CACHE: Cleared on connection restored: %s",
                self.interface_id,
            )

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
        """Set single value on paramset VALUES (internal implementation)."""
        return await self._device_ops_handler.set_value_internal(
            channel_address=channel_address,
            parameter=parameter,
            value=value,
            wait_for_callback=wait_for_callback,
            rx_mode=rx_mode,
            check_against_pd=check_against_pd,
        )


class ClientJsonCCU(ClientCCU):
    """Client implementation for CCU-like backend (CCU-Jack)."""

    @property
    def supports_backup(self) -> bool:
        """Return if the backend supports backup creation and download."""
        return False

    @property
    def supports_device_firmware_update(self) -> bool:
        """Return if the backend supports device firmware updates."""
        return False

    @property
    def supports_firmware_update_trigger(self) -> bool:
        """Return if the backend supports triggering system firmware updates."""
        return False

    @property
    def supports_functions(self) -> bool:
        """Return if interface supports functions."""
        return False

    @property
    def supports_inbox_devices(self) -> bool:
        """Return if the backend supports inbox devices."""
        return False

    @property
    def supports_install_mode(self) -> bool:
        """Return if the backend supports install mode operations."""
        return False

    @property
    def supports_linking(self) -> bool:
        """Return if the backend supports device linking operations."""
        return False

    @property
    def supports_metadata(self) -> bool:
        """Return if the backend supports metadata operations."""
        return False

    @property
    def supports_programs(self) -> bool:
        """Return if interface supports programs."""
        return False

    @property
    def supports_rega_id_lookup(self) -> bool:
        """Return if the backend supports ReGa ID lookups."""
        return False

    @property
    def supports_rename(self) -> bool:
        """Return if the backend supports renaming devices and channels."""
        return False

    @property
    def supports_rooms(self) -> bool:
        """Return if interface supports rooms."""
        return False

    @property
    def supports_service_messages(self) -> bool:
        """Return if the backend supports service messages."""
        return False

    @property
    def supports_system_update_info(self) -> bool:
        """Return if the backend supports system update information."""
        return False

    @property
    def supports_value_usage_reporting(self) -> bool:
        """Return if the backend supports value usage reporting."""
        return False

    @inspector(re_raise=False, no_raise_return=False)
    async def check_connection_availability(self, *, handle_ping_pong: bool) -> bool:
        """Check if proxy is still initialized."""
        return await self._json_rpc_client.is_present(interface=self.interface)

    @inspector(re_raise=False)
    async def get_device_description(self, *, address: str) -> DeviceDescription | None:
        """Get device descriptions from the backend."""
        try:
            if device_description := await self._json_rpc_client.get_device_description(
                interface=self.interface, address=address
            ):
                return device_description
        except BaseHomematicException as bhexc:
            _LOGGER.warning(  # i18n-log: ignore
                "GET_DEVICE_DESCRIPTIONS failed: %s [%s]", bhexc.name, extract_exc_args(exc=bhexc)
            )
        return None

    @inspector
    async def get_paramset(
        self,
        *,
        address: str,
        paramset_key: ParamsetKey | str,
        call_source: CallSource = CallSource.MANUAL_OR_SCHEDULED,
    ) -> dict[str, Any]:
        """Return a paramset from the backend."""
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

    async def _exec_put_paramset(
        self,
        *,
        channel_address: str,
        paramset_key: ParamsetKey | str,
        values: dict[str, Any],
        rx_mode: CommandRxMode | None = None,
    ) -> None:
        """Put paramset into the backend."""
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

    def _get_parameter_type(
        self,
        *,
        channel_address: str,
        paramset_key: ParamsetKey,
        parameter: str,
    ) -> ParameterType | None:
        """Return the parameter type for a given parameter."""
        if parameter_data := self.central.cache_coordinator.paramset_descriptions.get_parameter_data(
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
    def supports_backup(self) -> bool:
        """Return if the backend supports backup creation and download."""
        return False

    @property
    def supports_device_firmware_update(self) -> bool:
        """Return if the backend supports device firmware updates."""
        return False

    @property
    def supports_firmware_update_trigger(self) -> bool:
        """Return if the backend supports triggering system firmware updates."""
        return False

    @property
    def supports_firmware_updates(self) -> bool:
        """Return the supports_ping_pong info of the backend."""
        return False

    @property
    def supports_functions(self) -> bool:
        """Return if interface supports functions."""
        return False

    @property
    def supports_inbox_devices(self) -> bool:
        """Return if the backend supports inbox devices."""
        return False

    @property
    def supports_install_mode(self) -> bool:
        """Return if the backend supports install mode operations."""
        return False

    @property
    def supports_linking(self) -> bool:
        """Return if the backend supports device linking operations."""
        return False

    @property
    def supports_metadata(self) -> bool:
        """Return if the backend supports metadata operations."""
        return False

    @property
    def supports_ping_pong(self) -> bool:
        """Return if the backend supports ping pong."""
        return False

    @property
    def supports_programs(self) -> bool:
        """Return if interface supports programs."""
        return False

    @property
    def supports_rega_id_lookup(self) -> bool:
        """Return if the backend supports ReGa ID lookups."""
        return False

    @property
    def supports_rename(self) -> bool:
        """Return if the backend supports renaming devices and channels."""
        return False

    @property
    def supports_rooms(self) -> bool:
        """Return if interface supports rooms."""
        return False

    @property
    def supports_service_messages(self) -> bool:
        """Return if the backend supports service messages."""
        return False

    @property
    def supports_system_update_info(self) -> bool:
        """Return if the backend supports system update information."""
        return False

    @property
    def supports_value_usage_reporting(self) -> bool:
        """Return if the backend supports value usage reporting."""
        return False

    @inspector(re_raise=False, no_raise_return=False)
    async def check_connection_availability(self, *, handle_ping_pong: bool) -> bool:
        """Check if proxy is still initialized."""
        try:
            await self._proxy.clientServerInitialized(self.interface_id)
            self.modified_at = datetime.now()
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
        for address in self.central.cache_coordinator.device_descriptions.get_device_descriptions(
            interface_id=self.interface_id
        ):
            try:
                self.central.cache_coordinator.device_details.add_name(
                    address=address,
                    name=await self._proxy_read.getMetadata(address, _NAME),
                )
            except BaseHomematicException as bhexc:
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
        central: ClientDependencies,
        interface_config: InterfaceConfig,
    ) -> None:
        """Initialize the config."""
        self.central: Final[ClientDependencies] = central
        self.version: str = "0"
        self.system_information = SystemInformation()
        self.interface_config: Final = interface_config
        self.interface: Final = interface_config.interface
        self.interface_id: Final = interface_config.interface_id
        self.max_read_workers: Final[int] = central.config.max_read_workers
        self.has_credentials: Final[bool] = central.config.username is not None and central.config.password is not None
        self.supports_linking: Final = self.interface in LINKABLE_INTERFACES
        self.supports_firmware_updates: Final = self.interface in INTERFACES_SUPPORTING_FIRMWARE_UPDATES
        self.supports_ping_pong: Final = self.interface in INTERFACES_SUPPORTING_RPC_CALLBACK
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

    async def create_client(self) -> ClientProtocol:
        """Identify the used client."""
        try:
            self.version = await self._get_version()
            client: ClientProtocol | None
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
        except Exception as exc:
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
            session_recorder=self.central.cache_coordinator.recorder,
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
        except Exception as exc:
            raise NoConnectionException(
                i18n.tr(
                    "exception.client.client_config.unable_to_connect",
                    reason=extract_exc_args(exc=exc),
                )
            ) from exc
        return "0"


class InterfaceConfig:
    """Configuration for a single Homematic interface connection."""

    def __init__(
        self,
        *,
        central_name: str,
        interface: Interface,
        port: int,
        remote_path: str | None = None,
    ) -> None:
        """Initialize the interface configuration."""
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
    central: ClientDependencies,
    interface_config: InterfaceConfig,
) -> ClientProtocol:
    """Return a new client for with a given interface_config."""
    return await ClientConfig(central=central, interface_config=interface_config).create_client()


def get_client(interface_id: str) -> ClientProtocol | None:
    """Return client by interface_id."""
    for central in hmcu.CENTRAL_INSTANCES.values():
        if central.client_coordinator.has_client(interface_id=interface_id):
            return central.client_coordinator.get_client(interface_id=interface_id)
    return None
