# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Central unit orchestration for Homematic CCU and compatible backends.

This module provides the CentralUnit class that orchestrates interfaces, devices,
channels, data points, events, and background jobs for a Homematic CCU.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Set as AbstractSet
import logging
from typing import Final

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
from aiohomematic.central.query_facade import DeviceQueryFacade
from aiohomematic.central.registry import CENTRAL_REGISTRY
from aiohomematic.central.scheduler import BackgroundScheduler
from aiohomematic.central.state_machine import CentralStateMachine
from aiohomematic.client import AioJsonRpcAioHttpClient
from aiohomematic.const import (
    CATEGORIES,
    DATA_POINT_EVENTS,
    DEFAULT_LOCALE,
    IP_ANY_V4,
    LOCAL_HOST,
    PORT_ANY,
    PRIMARY_CLIENT_CANDIDATE_INTERFACES,
    BackupData,
    CentralState,
    ClientState,
    DataPointCategory,
    FailureReason,
    ForcedDeviceAvailability,
    Interface,
    ParamsetKey,
    SystemInformation,
)
from aiohomematic.decorators import inspector
from aiohomematic.exceptions import AioHomematicException, BaseHomematicException, NoClientsException
from aiohomematic.interfaces.central import CentralConfigProtocol, CentralProtocol
from aiohomematic.interfaces.client import ClientProtocol
from aiohomematic.interfaces.model import (
    CallbackDataPointProtocol,
    DeviceProtocol,
    GenericDataPointProtocolAny,
    GenericEventProtocolAny,
)
from aiohomematic.metrics import MetricsAggregator, MetricsObserver
from aiohomematic.model.hub import InstallModeDpType
from aiohomematic.property_decorators import DelegatedProperty, Kind, info_property
from aiohomematic.store import LocalStorageFactory, StorageFactoryProtocol
from aiohomematic.support import extract_exc_args, get_ip_addr
from aiohomematic.support.mixins import LogContextMixin, PayloadMixin

_LOGGER: Final = logging.getLogger(__name__)


class CentralUnit(
    PayloadMixin,
    LogContextMixin,
    CentralProtocol,
):
    """Central unit that collects everything to handle communication from/to the backend."""

    def __init__(self, *, central_config: CentralConfigProtocol) -> None:
        """
        Initialize the central unit.

        Dependency Graph (initialization order)::

            config, url, looper
                 │
                 ▼
            event_bus ──────────────────────────────────┐
                 │                                      │
                 ▼                                      │
            state_machine ─── health_tracker            │
                                                        │
            storage_factory                             │
                 │                                      │
                 ▼                                      │
            client_coordinator ─┬─ cache_coordinator    │
                                │       │               │
                                ▼       ▼               │
                        event_coordinator               │
                                │                       │
                                ▼                       │
            connection_state ── json_rpc_client ◄───────┘
                                                        │
            device_registry ── device_coordinator ◄─────┤
                                      │                 │
                                      ▼                 │
                            hub_coordinator ◄───────────┤
                                      │                 │
                                      ▼                 │
            scheduler, recovery_coordinator ◄───────────┘
                                      │
                                      ▼
                      metrics_observer, metrics_aggregator

        """
        # -- 1. Core configuration and runtime --
        self._config: Final[CentralConfigProtocol] = central_config
        try:
            i18n.set_locale(locale=self._config.locale)
        except Exception:  # pragma: no cover - keep init robust
            i18n.set_locale(locale=DEFAULT_LOCALE)
        self._url: Final = self._config.create_central_url()
        self._model: str | None = None
        self._looper = Looper()
        self._xml_rpc_server: rpc.AsyncXmlRpcServer | None = None

        # -- 2. Event infrastructure (needed by all coordinators) --
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

        # -- 3. Storage --
        self._storage_factory: Final[StorageFactoryProtocol] = central_config.storage_factory or LocalStorageFactory(
            base_directory=central_config.storage_directory,
            central_name=central_config.name,
            task_scheduler=self.looper,
        )

        # -- 4. Core coordinators (order matters: client → cache → event) --
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
            storage_factory=self._storage_factory,
            task_scheduler=self.looper,
        )
        self._event_coordinator: Final = EventCoordinator(
            client_provider=self._client_coordinator,
            event_bus=self._event_bus,
            health_tracker=self._health_tracker,
            task_scheduler=self.looper,
        )

        # -- 5. Connection state and JSON-RPC client --
        self._connection_state: Final = CentralConnectionState(event_bus_provider=self)
        self._json_rpc_client: Final = AioJsonRpcAioHttpClient(
            username=self._config.username,
            password=self._config.password,
            device_url=self._url,
            connection_state=self._connection_state,
            client_session=self._config.client_session,
            tls=self._config.tls,
            verify_tls=self._config.verify_tls,
            session_recorder=self._cache_coordinator.recorder,
            event_bus=self._event_bus,
            incident_recorder=self._cache_coordinator.incident_store,
        )

        # -- 6. Device management (depends on cache + event coordinators) --
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
            incident_recorder=self._cache_coordinator.incident_store,
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
            health_tracker=self._health_tracker,
            metrics_provider=self,
            parameter_visibility_provider=self._cache_coordinator.parameter_visibility,
            paramset_description_provider=self._cache_coordinator.paramset_descriptions,
            primary_client_provider=self._client_coordinator,
            task_scheduler=self.looper,
        )

        # -- 7. Query facade (depends on device + cache + client + hub coordinators) --
        self._query_facade: Final = DeviceQueryFacade(
            device_registry=self._device_registry,
            device_coordinator=self._device_coordinator,
            cache_coordinator=self._cache_coordinator,
            client_coordinator=self._client_coordinator,
            hub_coordinator=self._hub_coordinator,
        )

        # -- 8. Scheduling and recovery --
        CENTRAL_REGISTRY.register(name=self.name, central=self)
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
        )
        self._connection_recovery_coordinator: Final = ConnectionRecoveryCoordinator(
            central_info=self,
            config_provider=self,
            client_provider=self._client_coordinator,
            coordinator_provider=self,
            device_data_refresher=self,
            event_bus=self._event_bus,
            task_scheduler=self.looper,
            hub_data_fetcher=self._hub_coordinator,
            state_machine=self._central_state_machine,
        )

        # -- 9. Observability --
        self._metrics_observer: Final = MetricsObserver(event_bus=self._event_bus)
        self._metrics_aggregator: Final = MetricsAggregator(
            central_name=self.name,
            client_provider=self._client_coordinator,
            device_provider=self._device_registry,
            event_bus=self._event_bus,
            health_tracker=self._health_tracker,
            data_cache=self._cache_coordinator.data_cache,
            observer=self._metrics_observer,
            hub_data_point_manager=self._hub_coordinator,
            cache_provider=self._cache_coordinator,
            recovery_provider=self._connection_recovery_coordinator,
        )

        # -- 10. Event subscriptions and runtime state --
        self._unsubscribe_system_status = self.event_bus.subscribe(
            event_type=SystemStatusChangedEvent,
            event_key=None,
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
    config: Final = DelegatedProperty[CentralConfigProtocol](path="_config")
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
    json_rpc_client: Final = DelegatedProperty[AioJsonRpcAioHttpClient](path="_json_rpc_client")
    listen_ip_addr: Final = DelegatedProperty[str](path="_listen_ip_addr")
    listen_port_xml_rpc: Final = DelegatedProperty[int](path="_listen_port_xml_rpc")
    looper: Final = DelegatedProperty[Looper](path="_looper")
    metrics: Final = DelegatedProperty[MetricsObserver](path="_metrics_observer")
    metrics_aggregator: Final = DelegatedProperty[MetricsAggregator](path="_metrics_aggregator")
    name: Final = DelegatedProperty[str](path="_config.name", kind=Kind.INFO, log_context=True)
    query_facade: Final = DelegatedProperty[DeviceQueryFacade](path="_query_facade")
    state: Final = DelegatedProperty[CentralState](path="_central_state_machine.state")
    url: Final = DelegatedProperty[str](path="_url", kind=Kind.INFO, log_context=True)

    @property
    def _has_active_threads(self) -> bool:
        """Return if active sub threads are alive."""
        # BackgroundScheduler is async-based, not a thread
        # Async XML-RPC server doesn't use threads either
        if not self._xml_rpc_server or not self._xml_rpc_server.no_central_assigned:
            return False
        return self._xml_rpc_server.started

    @property
    def has_ping_pong(self) -> bool:
        """Return the backend supports ping pong."""
        if primary_client := self._client_coordinator.primary_client:
            return primary_client.capabilities.ping_pong
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

    def get_data_point_by_custom_id(self, *, custom_id: str) -> CallbackDataPointProtocol | None:
        """Return Homematic data_point by custom_id."""
        return self._query_facade.get_data_point_by_custom_id(custom_id=custom_id)

    def get_readable_generic_data_points(
        self, *, paramset_key: ParamsetKey | None = None, interface: Interface | None = None
    ) -> tuple[GenericDataPointProtocolAny, ...]:
        """Return the readable generic data points."""
        return self._query_facade.get_readable_generic_data_points(paramset_key=paramset_key, interface=interface)

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
        """
        Save files if they have unsaved changes.

        This method uses save_if_changed() to avoid unnecessary disk writes
        when caches have no unsaved changes. This is particularly important
        during shutdown or reconnection scenarios where event-based auto-save
        may have already persisted the changes.

        For internal use only - external code should use cache_coordinator directly.
        """
        await self._cache_coordinator.save_if_changed(
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
            self._listen_ip_addr = self._config.listen_ip_addr or ip_addr

        port_xml_rpc: int = (
            self._config.listen_port_xml_rpc
            or self._config.callback_port_xml_rpc
            or self._config.default_callback_port_xml_rpc
        )
        try:
            if self._config.enable_xml_rpc_server:
                async_server = await rpc.create_async_xml_rpc_server(ip_addr=self._listen_ip_addr, port=port_xml_rpc)
                self._xml_rpc_server = async_server
                self._listen_port_xml_rpc = async_server.listen_port
                async_server.add_central(central=self)
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
            # Device creation is now done inside start_clients() before hub init
            await self._client_coordinator.start_clients()
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
        self._evaluate_central_state(trigger="start() completed", from_start=True)

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
        if self._json_rpc_client.is_activated:
            await self._json_rpc_client.logout()
            await self._json_rpc_client.stop()

        if self._xml_rpc_server:
            # un-register this instance from XmlRPC-Server
            self._xml_rpc_server.remove_central(central=self)
            # un-register and stop XmlRPC-Server, if possible
            if self._xml_rpc_server.no_central_assigned:
                await self._xml_rpc_server.stop()
            _LOGGER.debug("STOP: XmlRPC-Server stopped")
        else:
            _LOGGER.debug("STOP: shared XmlRPC-Server NOT stopped. There is still another central instance registered")

        _LOGGER.debug("STOP: Removing instance")
        CENTRAL_REGISTRY.unregister(name=self.name)

        # Clear hub coordinator subscriptions (sysvar event subscriptions)
        self._hub_coordinator.clear()
        _LOGGER.debug("STOP: Hub coordinator subscriptions cleared")

        # Clear cache coordinator subscriptions (device removed event subscription)
        self._cache_coordinator.stop()
        _LOGGER.debug("STOP: Cache coordinator subscriptions cleared")

        # Clear event coordinator subscriptions (status event subscriptions)
        self._event_coordinator.clear()
        _LOGGER.debug("STOP: Event coordinator subscriptions cleared")

        # Clear external subscriptions (from Home Assistant integration)
        # These are subscriptions made via subscribe_to_device_removed(), subscribe_to_firmware_updated(), etc.
        # The integration is responsible for unsubscribing, but we clean up as a fallback
        self._event_coordinator.event_bus.clear_external_subscriptions()
        _LOGGER.debug("STOP: External subscriptions cleared")

        # Unsubscribe from system status events
        self._unsubscribe_system_status()
        _LOGGER.debug("STOP: Central system status subscription cleared")

        # Log any leaked subscriptions before clearing (only when debug logging is enabled)
        if _LOGGER.isEnabledFor(logging.DEBUG):
            self._event_coordinator.event_bus.log_leaked_subscriptions()

        # Clear EventBus subscriptions to prevent memory leaks
        self._event_coordinator.event_bus.clear_subscriptions()
        _LOGGER.debug("STOP: EventBus subscriptions cleared")

        # Clear all in-memory caches (device_details, data_cache, parameter_visibility)
        self._cache_coordinator.clear_on_stop()
        _LOGGER.debug("STOP: In-memory caches cleared")

        # Clear client-level trackers (command tracker, ping-pong tracker)
        for client in self._client_coordinator.clients:
            client.last_value_send_tracker.clear()
            client.ping_pong_tracker.clear()
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

    def _build_degraded_interfaces_map(self) -> dict[str, FailureReason]:
        """Build map of disconnected interfaces with their failure reasons."""
        return {
            client.interface_id: (
                reason
                if (reason := client.state_machine.failure_reason) != FailureReason.NONE
                else FailureReason.UNKNOWN
            )
            for client in self._client_coordinator.clients
            if client.state != ClientState.CONNECTED
        }

    def _determine_failure_info(self) -> tuple[FailureReason, str | None]:
        """Determine failure reason and interface from failed clients."""
        for client in self._client_coordinator.clients:
            if client.state_machine.is_failed and client.state_machine.failure_reason != FailureReason.NONE:
                return client.state_machine.failure_reason, client.interface_id
        return FailureReason.NETWORK, None

    def _evaluate_central_state(self, *, trigger: str, from_start: bool = False) -> None:
        """
        Evaluate and transition central state based on current client states.

        This method consolidates the state evaluation logic used by both start()
        and _on_system_status_event() to avoid duplication.

        Args:
            trigger: Description of what triggered the evaluation (used in reason strings).
            from_start: If True, called from start() after initialization.
                Allows transitions from INITIALIZING without recovery or state guards.
                If False, called from event handler with stricter guards:
                DEGRADED only from RUNNING, FAILED only from RUNNING/DEGRADED,
                and RUNNING blocked while recovery is in progress.

        """
        current_state = self._central_state_machine.state
        clients = self._client_coordinator.clients
        # Note: all() returns True for empty iterables, so we must check clients exist
        all_connected = bool(clients) and all(client.state == ClientState.CONNECTED for client in clients)
        any_connected = any(client.state == ClientState.CONNECTED for client in clients)

        # RUNNING: All clients connected
        # from_start: no recovery check needed (recovery not started yet)
        # event handler: don't transition to RUNNING while recovery is in progress
        if (
            all_connected
            and (from_start or not self._connection_recovery_coordinator.in_recovery)
            and self._central_state_machine.can_transition_to(target=CentralState.RUNNING)
        ):
            self._central_state_machine.transition_to(
                target=CentralState.RUNNING,
                reason=f"all clients connected ({trigger})",
            )
        # DEGRADED: Some clients disconnected
        # from_start: allowed from INITIALIZING
        # event handler: only from RUNNING (to avoid interfering with recovery)
        elif (
            any_connected
            and not all_connected
            and (from_start or current_state == CentralState.RUNNING)
            and self._central_state_machine.can_transition_to(target=CentralState.DEGRADED)
        ):
            degraded_interfaces = self._build_degraded_interfaces_map()
            self._central_state_machine.transition_to(
                target=CentralState.DEGRADED,
                reason=f"clients not connected: {', '.join(degraded_interfaces.keys())}",
                degraded_interfaces=degraded_interfaces,
            )
        # FAILED: No clients connected
        # from_start: allowed from INITIALIZING, uses coordinator's cached failure info
        # event handler: only from RUNNING/DEGRADED, determines failure from client states
        elif (
            not any_connected
            and (from_start or current_state in (CentralState.RUNNING, CentralState.DEGRADED))
            and self._central_state_machine.can_transition_to(target=CentralState.FAILED)
        ):
            if from_start:
                failure_reason = self._client_coordinator.last_failure_reason
                failure_interface_id = self._client_coordinator.last_failure_interface_id
            else:
                failure_reason, failure_interface_id = self._determine_failure_info()
            self._central_state_machine.transition_to(
                target=CentralState.FAILED,
                reason=f"no clients connected ({trigger})",
                failure_reason=failure_reason,
                failure_interface_id=failure_interface_id,
            )

    async def _identify_ip_addr(self, *, port: int) -> str:
        ip_addr: str | None = None
        while ip_addr is None:
            try:
                ip_addr = await get_ip_addr(host=self._config.host, port=port)
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

        # Get the current client state to handle race conditions where events
        # may be processed out of order (e.g., disconnected event processed after connected event)
        try:
            client = self._client_coordinator.get_client(interface_id=interface_id)
            current_client_state = client.state
        except AioHomematicException:
            # Client not found, use event state
            current_client_state = new_state

        # Immediately mark devices as unavailable when client disconnects or fails
        # Only if the current state is still disconnected/failed (to handle race conditions)
        if new_state in (ClientState.DISCONNECTED, ClientState.FAILED):
            if current_client_state in (ClientState.DISCONNECTED, ClientState.FAILED):
                for device in self._device_registry.devices:
                    if device.interface_id == interface_id:
                        device.set_forced_availability(forced_availability=ForcedDeviceAvailability.FORCE_FALSE)
                _LOGGER.debug(
                    "CLIENT_STATE_CHANGE: Marked all devices unavailable for %s (state=%s)",
                    interface_id,
                    new_state.value,
                )
            else:
                _LOGGER.debug(
                    "CLIENT_STATE_CHANGE: Skipped marking devices unavailable for %s "
                    "(event_state=%s, current_state=%s - already recovered)",
                    interface_id,
                    new_state.value,
                    current_client_state.value,
                )

        # Reset forced availability when client reconnects successfully
        # Include CONNECTING because the sequence is often:
        # reconnecting -> disconnected -> connecting -> connected
        if new_state == ClientState.CONNECTED and old_state in (
            ClientState.CONNECTING,
            ClientState.DISCONNECTED,
            ClientState.FAILED,
            ClientState.RECONNECTING,
        ):
            for device in self._device_registry.devices:
                if device.interface_id == interface_id:
                    device.set_forced_availability(forced_availability=ForcedDeviceAvailability.NOT_SET)
            _LOGGER.debug(
                "CLIENT_STATE_CHANGE: Reset device availability for %s (reconnected)",
                interface_id,
            )

        # Determine overall central state based on all client states.
        # Only transition if central is in a state that allows it.
        if self._central_state_machine.state not in (CentralState.STARTING, CentralState.STOPPED):
            self._evaluate_central_state(trigger=f"triggered by {interface_id}")

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
        category: set()
        for category in CATEGORIES
        if category not in (DataPointCategory.EVENT, DataPointCategory.EVENT_GROUP)
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
