# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Client implementations for Homematic CCU and compatible backends.

This module provides concrete client classes that handle communication with
Homematic backends via XML-RPC and JSON-RPC protocols.

Public API
----------
- ClientCCU: Primary client for CCU-compatible backends using XML-RPC for
  device operations and optional JSON-RPC for metadata/program/sysvar access.
- ClientJsonCCU: Specialized client for CCU-Jack that prefers JSON-RPC
  endpoints for all operations where available.
- ClientHomegear: Client for Homegear backend using XML-RPC exclusively.
- ClientConfig: Factory class that creates appropriate client instances
  based on interface configuration and backend type.

Key features
------------
- Automatic protocol selection based on backend capabilities
- Connection health tracking via circuit breaker pattern
- Request coalescing for duplicate concurrent requests
- Paramset caching and lazy loading
- Program and system variable management (CCU backends)
- Firmware update support (where available)

Usage
-----
Clients are typically created through CentralUnit, but can be instantiated
directly via ClientConfig:

    config = ClientConfig(client_deps=deps, interface_config=iface_cfg)
    client = await config.create_client()
    await client.init_client()
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime
import logging
from typing import Any, Final, cast

from aiohomematic import i18n
from aiohomematic.central.events import ClientStateChangedEvent, SystemStatusChangedEvent
from aiohomematic.client._rpc_errors import exception_to_failure_reason
from aiohomematic.client.backends.capabilities import (
    CCU_CAPABILITIES,
    HOMEGEAR_CAPABILITIES,
    JSON_CCU_CAPABILITIES,
    BackendCapabilities,
)
from aiohomematic.client.circuit_breaker import CircuitBreaker
from aiohomematic.client.config import InterfaceConfig
from aiohomematic.client.handlers import (
    BackupHandler,
    DeviceHandler,
    FirmwareHandler,
    LinkHandler,
    MetadataHandler,
    ProgramHandler,
    SystemVariableHandler,
    _wait_for_state_change_or_timeout,
)
from aiohomematic.client.request_coalescer import RequestCoalescer
from aiohomematic.client.rpc_proxy import AioXmlRpcProxy, BaseRpcProxy, NullRpcProxy
from aiohomematic.client.state_machine import ClientStateMachine
from aiohomematic.const import (
    DATETIME_FORMAT_MILLIS,
    DEFAULT_MAX_WORKERS,
    DP_KEY_VALUE,
    DUMMY_SERIAL,
    INIT_DATETIME,
    INTERFACES_REQUIRING_JSON_RPC_CLIENT,
    INTERFACES_SUPPORTING_FIRMWARE_UPDATES,
    INTERFACES_SUPPORTING_RPC_CALLBACK,
    LINKABLE_INTERFACES,
    VIRTUAL_REMOTE_MODELS,
    WAIT_FOR_CALLBACK,
    Backend,
    BackupData,
    CallSource,
    CircuitState,
    ClientState,
    CommandRxMode,
    DescriptionMarker,
    DeviceDescription,
    FailureReason,
    ForcedDeviceAvailability,
    InboxDeviceData,
    Interface,
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
from aiohomematic.exceptions import BaseHomematicException, ClientException, NoConnectionException
from aiohomematic.interfaces.client import ClientDependenciesProtocol, ClientProtocol
from aiohomematic.interfaces.model import DeviceProtocol
from aiohomematic.model.support import convert_value
from aiohomematic.property_decorators import DelegatedProperty
from aiohomematic.store.dynamic import CommandTracker, PingPongTracker
from aiohomematic.store.types import IncidentSeverity, IncidentType
from aiohomematic.support import (
    LogContextMixin,
    build_xml_rpc_headers,
    build_xml_rpc_uri,
    extract_exc_args,
    get_device_address,
    is_paramset_key,
    supports_rx_mode,
)

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
    - DeviceHandler: Value read/write, paramset operations
    - LinkHandler: Device linking operations
    - FirmwareHandler: Firmware update operations
    - SystemVariableHandler: System variable CRUD
    - ProgramHandler: Program execution and state
    - BackupHandler: Backup creation and download
    - MetadataHandler: Metadata, renaming, rooms, functions, install mode
    """

    __slots__ = (
        "_available",
        "_backup_handler",
        "_capabilities",
        "_config",
        "_connection_error_count",
        "_device_ops_handler",
        "_firmware_handler",
        "_is_callback_alive",
        "_is_initialized",
        "_json_rpc_client",
        "_last_value_send_tracker",
        "_link_handler",
        "_metadata_handler",
        "_modified_at",
        "_ping_pong_tracker",
        "_program_handler",
        "_proxy",
        "_proxy_read",
        "_reconnect_attempts",
        "_state_machine",
        "_sysvar_handler",
        "_system_information",
        "_unsubscribe_state_change",
        "_unsubscribe_system_status",
    )

    def __init__(self, *, client_config: ClientConfig) -> None:
        """Initialize the Client."""
        self._config: Final = client_config
        # Initialize capabilities based on config (backup updated in init_client)
        self._capabilities: BackendCapabilities = replace(
            CCU_CAPABILITIES,
            firmware_updates=client_config.has_firmware_updates,
            linking=client_config.has_linking,
            ping_pong=client_config.has_ping_pong,
            push_updates=client_config.has_push_updates,
            rpc_callback=client_config.has_rpc_callback,
        )
        self._json_rpc_client: Final = client_config.client_deps.json_rpc_client
        self._last_value_send_tracker: Final = CommandTracker(
            interface_id=client_config.interface_id,
        )
        self._state_machine: Final = ClientStateMachine(
            interface_id=client_config.interface_id,
            event_bus=client_config.client_deps.event_bus,
        )
        # Subscribe to state changes to emit SystemStatusChangedEvent for integration compatibility
        self._unsubscribe_state_change = client_config.client_deps.event_bus.subscribe(
            event_type=ClientStateChangedEvent,
            event_key=client_config.interface_id,
            handler=self._on_client_state_changed_event,
        )
        self._connection_error_count: int = 0
        self._is_callback_alive: bool = True
        self._reconnect_attempts: int = 0
        self._ping_pong_tracker: Final = PingPongTracker(
            event_bus_provider=client_config.client_deps,
            central_info=client_config.client_deps,
            interface_id=client_config.interface_id,
            connection_state=client_config.client_deps.connection_state,
            incident_recorder=client_config.client_deps.cache_coordinator.incident_store,
        )
        self._proxy: BaseRpcProxy
        self._proxy_read: BaseRpcProxy
        self._system_information: SystemInformation
        self._modified_at: datetime = INIT_DATETIME

        # Subscribe to connection state changes to clear ping/pong cache on reconnect.
        # This prevents stale pending pongs from causing false mismatch alarms
        # after CCU restart when PINGs sent during downtime cannot be answered.
        self._unsubscribe_system_status = client_config.client_deps.event_bus.subscribe(
            event_type=SystemStatusChangedEvent,
            event_key=None,
            handler=self._on_system_status_event,
        )

        # Handler instances (initialized after proxy setup in init_client)
        self._device_ops_handler: DeviceHandler
        self._link_handler: LinkHandler
        self._firmware_handler: FirmwareHandler
        self._sysvar_handler: SystemVariableHandler
        self._program_handler: ProgramHandler
        self._backup_handler: BackupHandler
        self._metadata_handler: MetadataHandler

    def __str__(self) -> str:
        """Provide some useful information."""
        return f"interface_id: {self.interface_id}"

    available: Final = DelegatedProperty[bool](path="_state_machine.is_available")
    central: Final = DelegatedProperty[ClientDependenciesProtocol](path="_config.client_deps")
    interface: Final = DelegatedProperty[Interface](path="_config.interface")
    interface_id: Final = DelegatedProperty[str](path="_config.interface_id", log_context=True)
    last_value_send_tracker: Final = DelegatedProperty[CommandTracker](path="_last_value_send_tracker")
    ping_pong_tracker: Final = DelegatedProperty[PingPongTracker](path="_ping_pong_tracker")
    state: Final = DelegatedProperty[ClientState](path="_state_machine.state")
    state_machine: Final = DelegatedProperty[ClientStateMachine](path="_state_machine")
    system_information: Final = DelegatedProperty[SystemInformation](path="_system_information")
    version: Final = DelegatedProperty[str](path="_config.version")

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
    def capabilities(self) -> BackendCapabilities:
        """Return the capability flags for this backend."""
        return self._capabilities

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        """Return the primary circuit breaker for metrics access."""
        return self._proxy.circuit_breaker

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
    def request_coalescer(self) -> RequestCoalescer | None:
        """Return the request coalescer for metrics access."""
        if hasattr(self, "_device_ops_handler"):
            return self._device_ops_handler.paramset_description_coalescer
        return None

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
        ping_timeout = self._config.client_deps.config.timeout_config.ping_timeout
        try:
            dt_now = datetime.now()
            if handle_ping_pong and self._capabilities.ping_pong and self.is_initialized:
                token = dt_now.strftime(format=DATETIME_FORMAT_MILLIS)
                callerId = f"{self.interface_id}#{token}"
                # Register token BEFORE sending ping to avoid race condition:
                # CCU may respond with PONG before await returns
                self._ping_pong_tracker.handle_send_ping(ping_token=token)
                async with asyncio.timeout(ping_timeout):
                    await self._proxy.ping(callerId)
            elif not self.is_initialized:
                async with asyncio.timeout(ping_timeout):
                    await self._proxy.ping(self.interface_id)
            self.modified_at = dt_now
        except TimeoutError:
            _LOGGER.debug(
                "CHECK_CONNECTION_AVAILABILITY: Ping timeout after %.1fs for %s",
                ping_timeout,
                self.interface_id,
            )
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

    def clear_json_rpc_session(self) -> None:
        """Clear the JSON-RPC session to force re-authentication on next request."""
        self._json_rpc_client.clear_session()
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
        return await self._backup_handler.create_backup_and_download(
            max_wait_time=max_wait_time,
            poll_interval=poll_interval,
        )

    async def deinitialize_proxy(self) -> ProxyInitState:
        """De-init to stop the backend from sending events for this remote."""
        if not self._capabilities.rpc_callback:
            self._state_machine.transition_to(target=ClientState.DISCONNECTED, reason="no callback support")
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
        convert_from_pd: bool = False,
    ) -> dict[str, Any]:
        """Return a paramset from the backend."""
        return await self._device_ops_handler.get_paramset(
            address=address,
            paramset_key=paramset_key,
            call_source=call_source,
            convert_from_pd=convert_from_pd,
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
        convert_from_pd: bool = False,
    ) -> Any:
        """Return a value from the backend."""
        return await self._device_ops_handler.get_value(
            channel_address=channel_address,
            paramset_key=paramset_key,
            parameter=parameter,
            call_source=call_source,
            convert_from_pd=convert_from_pd,
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
            # Update capabilities with backup from system information
            if not self._system_information.has_backup:
                self._capabilities = replace(self._capabilities, backup=False)
            if self._capabilities.rpc_callback:
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
        except Exception as exc:
            self._state_machine.transition_to(
                target=ClientState.FAILED,
                reason=str(exc),
                failure_reason=exception_to_failure_reason(exc=exc),
            )
            raise

    async def initialize_proxy(self) -> ProxyInitState:
        """Initialize the proxy has to tell the backend where to send the events."""
        self._state_machine.transition_to(target=ClientState.CONNECTING)
        if not self._capabilities.rpc_callback:
            if (device_descriptions := await self.list_devices()) is not None:
                await self.central.device_coordinator.add_new_devices(
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
            # Mark devices as unavailable when device listing fails
            self._mark_all_devices_forced_availability(forced_availability=ForcedDeviceAvailability.FORCE_FALSE)
            return ProxyInitState.INIT_FAILED
        # Record modified_at before init to detect callback during init
        # This is used to work around VirtualDevices service bug where init()
        # times out but listDevices callback was successfully received
        modified_at_before_init = self.modified_at
        init_success = False
        try:
            _LOGGER.debug("PROXY_INIT: init('%s', '%s')", self._config.init_url, self.interface_id)
            self._ping_pong_tracker.clear()
            await self._proxy.init(self._config.init_url, self.interface_id)
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
                # Mark devices as unavailable when proxy init fails
                # This ensures data points show unavailable during CCU restart/recovery
                self._mark_all_devices_forced_availability(forced_availability=ForcedDeviceAvailability.FORCE_FALSE)
                return ProxyInitState.INIT_FAILED

        if init_success:
            self._state_machine.transition_to(target=ClientState.CONNECTED, reason="proxy initialized")
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
        self.modified_at = datetime.now()
        return ProxyInitState.INIT_SUCCESS

    def is_callback_alive(self) -> bool:
        """Return if XmlRPC-Server is alive based on received events for this client."""
        if not self._capabilities.ping_pong:
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
            callback_warn = self._config.client_deps.config.timeout_config.callback_warn_interval
            if (seconds_since_last_event := (datetime.now() - last_events_dt).total_seconds()) > callback_warn:
                if self._is_callback_alive:
                    self.central.event_bus.publish_sync(
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
                self.central.event_bus.publish_sync(
                    event=SystemStatusChangedEvent(
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

        Connection is not connected if consecutive checks exceed threshold.
        Return connectivity state.
        """
        if await self.check_connection_availability(handle_ping_pong=True) is True:
            self._connection_error_count = 0
        else:
            self._connection_error_count += 1

        error_threshold = self._config.client_deps.config.timeout_config.connectivity_error_threshold
        if self._connection_error_count > error_threshold:
            self._mark_all_devices_forced_availability(forced_availability=ForcedDeviceAvailability.FORCE_FALSE)
            # Update state machine to reflect connection loss
            if self._state_machine.state == ClientState.CONNECTED:
                self._state_machine.transition_to(
                    target=ClientState.DISCONNECTED,
                    reason=f"connection check failed (>{error_threshold} errors)",
                )
            return False
        if not self._capabilities.push_updates:
            return True

        # For interfaces without ping/pong (CUxD, CCU-Jack via MQTT), skip callback_warn check
        # These interfaces are event-driven via Homematic(IP) Local but don't support ping/pong
        if not self._capabilities.ping_pong:
            return True

        callback_warn = self._config.client_deps.config.timeout_config.callback_warn_interval
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
            timeout_cfg = self._config.client_deps.config.timeout_config
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
                        key="log.client.reconnect.reconnected",
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
            supports=self._capabilities.value_usage_reporting,
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
        # Unsubscribe from state change events before stopping
        self._unsubscribe_state_change()
        self._unsubscribe_system_status()
        self._state_machine.transition_to(target=ClientState.STOPPING, reason="stop() called")
        if self._capabilities.rpc_callback:
            await self._proxy.stop()
            await self._proxy_read.stop()
        self._state_machine.transition_to(target=ClientState.STOPPED, reason="services stopped")

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
        self._device_ops_handler = DeviceHandler(
            client_deps=self._config.client_deps,
            interface=self._config.interface,
            interface_id=self._config.interface_id,
            json_rpc_client=self._json_rpc_client,
            proxy=self._proxy,
            proxy_read=self._proxy_read,
            last_value_send_tracker=self._last_value_send_tracker,
        )

        self._link_handler = LinkHandler(
            client_deps=self._config.client_deps,
            interface=self._config.interface,
            interface_id=self._config.interface_id,
            json_rpc_client=self._json_rpc_client,
            proxy=self._proxy,
            proxy_read=self._proxy_read,
            has_linking=self._capabilities.linking,
        )

        self._firmware_handler = FirmwareHandler(
            client_deps=self._config.client_deps,
            interface=self._config.interface,
            interface_id=self._config.interface_id,
            json_rpc_client=self._json_rpc_client,
            proxy=self._proxy,
            proxy_read=self._proxy_read,
            has_device_firmware_update=self._capabilities.device_firmware_update,
            has_firmware_update_trigger=self._capabilities.firmware_update_trigger,
        )

        self._sysvar_handler = SystemVariableHandler(
            client_deps=self._config.client_deps,
            interface=self._config.interface,
            interface_id=self._config.interface_id,
            json_rpc_client=self._json_rpc_client,
            proxy=self._proxy,
            proxy_read=self._proxy_read,
        )

        self._program_handler = ProgramHandler(
            client_deps=self._config.client_deps,
            interface=self._config.interface,
            interface_id=self._config.interface_id,
            json_rpc_client=self._json_rpc_client,
            proxy=self._proxy,
            proxy_read=self._proxy_read,
            has_programs=self._capabilities.programs,
        )

        self._backup_handler = BackupHandler(
            client_deps=self._config.client_deps,
            interface=self._config.interface,
            interface_id=self._config.interface_id,
            json_rpc_client=self._json_rpc_client,
            proxy=self._proxy,
            proxy_read=self._proxy_read,
            has_backup=self._capabilities.backup,
            system_information=self._system_information,
        )

        self._metadata_handler = MetadataHandler(
            client_deps=self._config.client_deps,
            interface=self._config.interface,
            interface_id=self._config.interface_id,
            json_rpc_client=self._json_rpc_client,
            proxy=self._proxy,
            proxy_read=self._proxy_read,
            has_functions=self._capabilities.functions,
            has_inbox_devices=self._capabilities.inbox_devices,
            has_install_mode=self._capabilities.install_mode,
            has_metadata=self._capabilities.metadata,
            has_rega_id_lookup=self._capabilities.rega_id_lookup,
            has_rename=self._capabilities.rename,
            has_rooms=self._capabilities.rooms,
            has_service_messages=self._capabilities.service_messages,
            has_system_update_info=self._capabilities.system_update_info,
        )

    def _mark_all_devices_forced_availability(self, *, forced_availability: ForcedDeviceAvailability) -> None:
        """Mark device's availability state for this interface."""
        available = forced_availability != ForcedDeviceAvailability.FORCE_FALSE
        # Always update devices when marking unavailable (FORCE_FALSE) to ensure
        # data points show unavailable during connection failures.
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

    def _on_client_state_changed_event(self, *, event: ClientStateChangedEvent) -> None:
        """Handle client state machine transitions by emitting SystemStatusChangedEvent for integration compatibility."""
        self._config.client_deps.event_bus.publish_sync(
            event=SystemStatusChangedEvent(
                timestamp=datetime.now(),
                client_state=(event.interface_id, ClientState(event.old_state), ClientState(event.new_state)),
            )
        )

    def _on_system_status_event(self, *, event: SystemStatusChangedEvent) -> None:
        """Handle system status events to clear ping/pong cache on reconnect."""
        if event.connection_state and event.connection_state[0] == self.interface_id and event.connection_state[1]:
            # Clear stale ping/pong state when connection is restored.
            # PINGs sent during CCU downtime cannot receive PONGs, so the cache
            # would contain stale entries that cause false mismatch alarms.
            self._ping_pong_tracker.clear()
            _LOGGER.debug(
                "PING PONG CACHE: Cleared on connection restored: %s",
                self.interface_id,
            )

    def _record_callback_timeout_incident(
        self,
        *,
        seconds_since_last_event: float,
        callback_warn_interval: float,
        last_event_time: datetime,
    ) -> None:
        """Record a CALLBACK_TIMEOUT incident for diagnostics."""
        incident_recorder = self._config.client_deps.cache_coordinator.incident_store

        # Get circuit breaker state safely (_proxy may not be set during early startup)
        circuit_breaker_state: str | None = None
        if hasattr(self, "_proxy") and hasattr(self._proxy, "circuit_breaker"):
            circuit_breaker_state = self._proxy.circuit_breaker.state.value

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

        self._config.client_deps.looper.create_task(
            target=_record(),
            name=f"record_callback_timeout_incident_{self.interface_id}",
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

    def __init__(self, *, client_config: ClientConfig) -> None:
        """Initialize the Client."""
        super().__init__(client_config=client_config)
        # Override capabilities with JSON_CCU_CAPABILITIES
        self._capabilities = replace(
            JSON_CCU_CAPABILITIES,
            push_updates=client_config.has_push_updates,
        )

    @inspector(re_raise=False, no_raise_return=False)
    async def check_connection_availability(self, *, handle_ping_pong: bool) -> bool:
        """Check if proxy is still initialized."""
        ping_timeout = self._config.client_deps.config.timeout_config.ping_timeout
        try:
            async with asyncio.timeout(ping_timeout):
                return await self._json_rpc_client.is_present(interface=self.interface)
        except TimeoutError:
            _LOGGER.debug(
                "CHECK_CONNECTION_AVAILABILITY: Timeout after %.1fs for %s",
                ping_timeout,
                self.interface_id,
            )
            return False

    async def fetch_paramset_description(self, *, channel_address: str, paramset_key: ParamsetKey) -> None:
        """Fetch a specific paramset and add it to the known ones."""
        _LOGGER.debug("FETCH_PARAMSET_DESCRIPTION for %s/%s", channel_address, paramset_key)
        # Note: paramset_description can be an empty dict {} which is valid
        # (e.g., HmIP base device MASTER paramsets have no parameters)
        if (
            paramset_description := await self._get_paramset_description(
                address=channel_address, paramset_key=paramset_key
            )
        ) is not None:
            self.central.cache_coordinator.paramset_descriptions.add(
                interface_id=self.interface_id,
                channel_address=channel_address,
                paramset_key=paramset_key,
                paramset_description=paramset_description,
            )

    async def fetch_paramset_descriptions(self, *, device_description: DeviceDescription) -> None:
        """Fetch paramsets for provided device description."""
        data = await self.get_paramset_descriptions(device_description=device_description)
        for address, paramsets in data.items():
            _LOGGER.debug("FETCH_PARAMSET_DESCRIPTIONS for %s", address)
            for paramset_key, paramset_description in paramsets.items():
                self.central.cache_coordinator.paramset_descriptions.add(
                    interface_id=self.interface_id,
                    channel_address=address,
                    paramset_key=paramset_key,
                    paramset_description=paramset_description,
                )

    @inspector(re_raise=False)
    async def get_all_device_descriptions(self, *, device_address: str) -> tuple[DeviceDescription, ...]:
        """Return device description and all child channel descriptions."""
        all_device_description: list[DeviceDescription] = []
        if main_dd := await self.get_device_description(address=device_address):
            all_device_description.append(main_dd)
        else:
            _LOGGER.warning(  # i18n-log: ignore
                "GET_ALL_DEVICE_DESCRIPTIONS: No device description for %s",
                device_address,
            )

        if main_dd:
            for channel_address in main_dd.get("CHILDREN", []):
                if channel_dd := await self.get_device_description(address=channel_address):
                    all_device_description.append(channel_dd)
                else:
                    _LOGGER.warning(  # i18n-log: ignore
                        "GET_ALL_DEVICE_DESCRIPTIONS: No channel description for %s",
                        channel_address,
                    )
        return tuple(all_device_description)

    async def get_all_paramset_descriptions(
        self, *, device_descriptions: tuple[DeviceDescription, ...]
    ) -> dict[str, dict[ParamsetKey, dict[str, ParameterData]]]:
        """Get all paramset descriptions for provided device descriptions."""
        all_paramsets: dict[str, dict[ParamsetKey, dict[str, ParameterData]]] = {}
        for device_description in device_descriptions:
            all_paramsets.update(await self.get_paramset_descriptions(device_description=device_description))
        return all_paramsets

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
        convert_from_pd: bool = False,
    ) -> dict[str, Any]:
        """Return a paramset from the backend."""
        try:
            _LOGGER.debug(
                "GET_PARAMSET: address %s, paramset_key %s, source %s",
                address,
                paramset_key,
                call_source,
            )
            result = (
                await self._json_rpc_client.get_paramset(
                    interface=self.interface, address=address, paramset_key=paramset_key
                )
                or {}
            )
            if convert_from_pd and is_paramset_key(paramset_key=paramset_key):
                result = self._check_get_paramset(
                    channel_address=address,
                    paramset_key=ParamsetKey(paramset_key),
                    values=result,
                )
        except BaseHomematicException as bhexc:
            raise ClientException(
                i18n.tr(
                    key="exception.client.json_ccu.get_paramset.failed",
                    address=address,
                    paramset_key=paramset_key,
                    reason=extract_exc_args(exc=bhexc),
                )
            ) from bhexc
        else:
            return result

    @inspector(re_raise=False, no_raise_return={})
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
        _LOGGER.debug("GET_PARAMSET_DESCRIPTIONS for %s", address)
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

    @inspector(log_level=logging.NOTSET)
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
        try:
            _LOGGER.debug(
                "GET_VALUE: channel_address %s, parameter %s, paramset_key, %s, source:%s",
                channel_address,
                parameter,
                paramset_key,
                call_source,
            )
            if paramset_key == ParamsetKey.VALUES:
                value = await self._json_rpc_client.get_value(
                    interface=self.interface,
                    address=channel_address,
                    paramset_key=paramset_key,
                    parameter=parameter,
                )
            else:
                paramset = (
                    await self._json_rpc_client.get_paramset(
                        interface=self.interface,
                        address=channel_address,
                        paramset_key=ParamsetKey.MASTER,
                    )
                    or {}
                )
                value = paramset.get(parameter)
            if convert_from_pd:
                value = self._convert_read_value(
                    channel_address=channel_address,
                    paramset_key=paramset_key,
                    parameter=parameter,
                    value=value,
                )
        except BaseHomematicException as bhexc:
            raise ClientException(
                i18n.tr(
                    key="exception.client.json_ccu.get_value.failed",
                    channel_address=channel_address,
                    parameter=parameter,
                    paramset_key=paramset_key,
                    reason=extract_exc_args(exc=bhexc),
                )
            ) from bhexc
        else:
            return value

    @inspector
    async def init_client(self) -> None:
        """Initialize the client."""
        self._state_machine.transition_to(target=ClientState.INITIALIZING)
        try:
            self._system_information = await self._get_system_information()
            # Use NullRpcProxy since ClientJsonCCU uses JSON-RPC exclusively.
            # The handlers are needed for JSON-RPC operations but don't use proxies.
            self._proxy = NullRpcProxy(
                interface_id=self.interface_id,
                connection_state=self._config.client_deps.connection_state,
                event_bus=self._config.client_deps.event_bus,
            )
            self._proxy_read = self._proxy
            self._init_handlers()
            self._state_machine.transition_to(target=ClientState.INITIALIZED)
        except Exception as exc:
            self._state_machine.transition_to(
                target=ClientState.FAILED,
                reason=str(exc),
                failure_reason=exception_to_failure_reason(exc=exc),
            )
            raise

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
        """
        Set paramsets manually via JSON-RPC.

        Overrides the base class to use JSON-RPC instead of XML-RPC proxy.
        """
        try:
            await self._exec_put_paramset(
                channel_address=channel_address,
                paramset_key=paramset_key_or_link_address,
                values=values,
                rx_mode=rx_mode,
            )
            # store the send value in the last_value_send_tracker
            dpk_values = self._last_value_send_tracker.add_put_paramset(
                channel_address=channel_address,
                paramset_key=ParamsetKey(paramset_key_or_link_address),
                values=values,
            )
            self._write_temporary_value(dpk_values=dpk_values)
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
        Set single value on paramset VALUES via JSON-RPC.

        Overrides the base class to use JSON-RPC instead of XML-RPC proxy.
        """
        if paramset_key != ParamsetKey.VALUES:
            return await self.put_paramset(
                channel_address=channel_address,
                paramset_key_or_link_address=paramset_key,
                values={parameter: value},
                wait_for_callback=wait_for_callback,
                rx_mode=rx_mode,
                check_against_pd=check_against_pd,
            )

        try:
            _LOGGER.debug("SET_VALUE: %s, %s, %s", channel_address, parameter, value)
            if rx_mode and (device := self.central.device_coordinator.get_device(address=channel_address)):
                if supports_rx_mode(command_rx_mode=rx_mode, rx_modes=device.rx_modes):
                    await self._exec_set_value(
                        channel_address=channel_address,
                        parameter=parameter,
                        value=value,
                        rx_mode=rx_mode,
                    )
                else:
                    raise ClientException(i18n.tr(key="exception.client.rx_mode.unsupported", rx_mode=rx_mode))
            else:
                await self._exec_set_value(channel_address=channel_address, parameter=parameter, value=value)

            # store the send value in the last_value_send_tracker
            dpk_values = self._last_value_send_tracker.add_set_value(
                channel_address=channel_address, parameter=parameter, value=value
            )
            self._write_temporary_value(dpk_values=dpk_values)

            if wait_for_callback is not None and (
                device := self.central.device_coordinator.get_device(
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
                    key="exception.client.set_value.failed",
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
        """Re-fetch and update paramset descriptions for a device."""
        if not self.central.cache_coordinator.device_descriptions.get_device_descriptions(
            interface_id=self.interface_id
        ):
            _LOGGER.warning(  # i18n-log: ignore
                "UPDATE_PARAMSET_DESCRIPTIONS failed: Interface missing in central cache. Not updating paramsets for %s",
                device_address,
            )
            return

        if device_description := self.central.cache_coordinator.device_descriptions.find_device_description(
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
        if parameter_data := self.central.cache_coordinator.paramset_descriptions.get_parameter_data(
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
                    key="exception.client.json_ccu.set_value.unknown_type",
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

    def _write_temporary_value(self, *, dpk_values: set[DP_KEY_VALUE]) -> None:
        """Write temporary values to polling data points for immediate UI feedback."""
        for dpk, value in dpk_values:
            if (
                data_point := self.central.get_generic_data_point(
                    channel_address=dpk.channel_address,
                    parameter=dpk.parameter,
                    paramset_key=dpk.paramset_key,
                )
            ) and data_point.requires_polling:
                data_point.write_temporary_value(value=value, write_at=datetime.now())


class ClientHomegear(ClientCCU):
    """
    Client implementation for Homegear backend.

    Inherit from ClientCCU to share common behavior used by tests and code paths
    that expect a CCU-like client interface for Homegear selections.
    """

    def __init__(self, *, client_config: ClientConfig) -> None:
        """Initialize the Client."""
        super().__init__(client_config=client_config)
        # Override capabilities with HOMEGEAR_CAPABILITIES
        self._capabilities = replace(
            HOMEGEAR_CAPABILITIES,
            push_updates=client_config.has_push_updates,
        )

    @property
    def model(self) -> str:
        """Return the model of the backend."""
        if self._config.version:
            return Backend.PYDEVCCU if Backend.PYDEVCCU.lower() in self._config.version else Backend.HOMEGEAR
        return Backend.CCU

    @inspector(re_raise=False, no_raise_return=False)
    async def check_connection_availability(self, *, handle_ping_pong: bool) -> bool:
        """Check if proxy is still initialized."""
        ping_timeout = self._config.client_deps.config.timeout_config.ping_timeout
        try:
            async with asyncio.timeout(ping_timeout):
                await self._proxy.clientServerInitialized(self.interface_id)
            self.modified_at = datetime.now()
        except TimeoutError:
            _LOGGER.debug(
                "CHECK_CONNECTION_AVAILABILITY: Timeout after %.1fs for %s",
                ping_timeout,
                self.interface_id,
            )
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
        client_deps: ClientDependenciesProtocol,
        interface_config: InterfaceConfig,
    ) -> None:
        """Initialize the config."""
        self.client_deps: Final[ClientDependenciesProtocol] = client_deps
        self.version: str = "0"
        self.system_information = SystemInformation()
        self.interface_config: Final = interface_config
        self.interface: Final = interface_config.interface
        self.interface_id: Final = interface_config.interface_id
        self.max_read_workers: Final[int] = client_deps.config.max_read_workers
        self.has_credentials: Final[bool] = (
            client_deps.config.username is not None and client_deps.config.password is not None
        )
        self.has_linking: Final = self.interface in LINKABLE_INTERFACES
        self.has_firmware_updates: Final = self.interface in INTERFACES_SUPPORTING_FIRMWARE_UPDATES
        self.has_ping_pong: Final = self.interface in INTERFACES_SUPPORTING_RPC_CALLBACK
        self.has_push_updates: Final = self.interface not in client_deps.config.interfaces_requiring_periodic_refresh
        self.has_rpc_callback: Final = self.interface in INTERFACES_SUPPORTING_RPC_CALLBACK
        callback_host: Final = (
            client_deps.config.callback_host if client_deps.config.callback_host else client_deps.callback_ip_addr
        )
        callback_port = (
            client_deps.config.callback_port_xml_rpc
            if client_deps.config.callback_port_xml_rpc
            else client_deps.listen_port_xml_rpc
        )
        init_url = f"{callback_host}:{callback_port}"
        self.init_url: Final = f"http://{init_url}"

        self.xml_rpc_uri: Final = build_xml_rpc_uri(
            host=client_deps.config.host,
            port=interface_config.port,
            path=interface_config.remote_path,
            tls=client_deps.config.tls,
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
                i18n.tr(key="exception.client.client_config.no_connection", interface_id=self.interface_id)
            )
        except BaseHomematicException:
            raise
        except Exception as exc:
            raise NoConnectionException(
                i18n.tr(
                    key="exception.client.client_config.unable_to_connect",
                    reason=extract_exc_args(exc=exc),
                )
            ) from exc

    async def create_rpc_proxy(
        self,
        *,
        interface: Interface,
        auth_enabled: bool | None = None,
        max_workers: int = DEFAULT_MAX_WORKERS,
    ) -> BaseRpcProxy:
        """Return a RPC proxy for the backend communication."""
        return await self._create_xml_rpc_proxy(
            auth_enabled=auth_enabled,
            max_workers=max_workers,
        )

    async def _create_simple_rpc_proxy(self, *, interface: Interface) -> BaseRpcProxy:
        """Return a RPC proxy for the backend communication."""
        return await self._create_xml_rpc_proxy(auth_enabled=True, max_workers=0)

    async def _create_xml_rpc_proxy(
        self,
        *,
        auth_enabled: bool | None = None,
        max_workers: int = DEFAULT_MAX_WORKERS,
    ) -> AioXmlRpcProxy:
        """Return a XmlRPC proxy for the backend communication."""
        config = self.client_deps.config
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
            connection_state=self.client_deps.connection_state,
            uri=self.xml_rpc_uri,
            headers=xml_rpc_headers,
            tls=config.tls,
            verify_tls=config.verify_tls,
            session_recorder=self.client_deps.cache_coordinator.recorder,
            event_bus=self.client_deps.event_bus,
            incident_recorder=self.client_deps.cache_coordinator.incident_store,
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
                    key="exception.client.client_config.unable_to_connect",
                    reason=extract_exc_args(exc=exc),
                )
            ) from exc
        return "0"
