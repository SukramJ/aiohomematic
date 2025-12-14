# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Background scheduler for periodic tasks in aiohomematic.

This module provides a modern asyncio-based scheduler that replaces the legacy
threading-based _Scheduler. It manages periodic background tasks such as:

- Connection health checks
- Data refreshes (client data, programs, system variables)
- Firmware update checks

The scheduler runs tasks based on configurable intervals and handles errors
gracefully without affecting other tasks.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import contextlib
from datetime import datetime, timedelta
import logging
from typing import Final

from aiohomematic import i18n
from aiohomematic.central.client_coordinator import ClientCoordinator
from aiohomematic.central.event_coordinator import EventCoordinator
from aiohomematic.central.integration_events import DeviceLifecycleEvent, DeviceLifecycleEventType
from aiohomematic.const import (
    DEVICE_FIRMWARE_CHECK_INTERVAL,
    DEVICE_FIRMWARE_DELIVERING_CHECK_INTERVAL,
    DEVICE_FIRMWARE_UPDATING_CHECK_INTERVAL,
    SCHEDULER_LOOP_SLEEP,
    SCHEDULER_NOT_STARTED_SLEEP,
    SYSTEM_UPDATE_CHECK_INTERVAL,
    Backend,
    CentralState,
    DeviceFirmwareState,
    Interface,
)
from aiohomematic.exceptions import BaseHomematicException, NoConnectionException
from aiohomematic.interfaces.central import (
    CentralInfo,
    CentralUnitStateProvider,
    ConfigProvider,
    DeviceDataRefresher,
    EventBusProvider,
    FirmwareDataRefresher,
    HubDataFetcher,
)
from aiohomematic.interfaces.client import ConnectionStateProvider, JsonRpcClientProvider
from aiohomematic.support import extract_exc_args
from aiohomematic.type_aliases import UnsubscribeCallback

_LOGGER: Final = logging.getLogger(__name__)

# Constants for post-reconnect data loading retry
# JSON-RPC service can take 30-60 seconds to become available after CCU restart
_POST_RECONNECT_RETRY_DELAY: Final = 10.0  # seconds between retries
_POST_RECONNECT_MAX_RETRIES: Final = 15  # maximum retry attempts (150 seconds total)
# Data loading retries - CCU may respond to pings but not be ready for data operations
# for an extended period after restart. ReGa/script engine may take additional time.
_DATA_LOAD_MAX_RETRIES: Final = 8  # maximum data loading retries after stability confirmed
_DATA_LOAD_RETRY_DELAY: Final = 20.0  # seconds between data loading retries (160s total)

# Type alias for async task factory
_AsyncTaskFactory = Callable[[], Awaitable[None]]


class SchedulerJob:
    """Represents a scheduled job with interval-based execution."""

    def __init__(
        self,
        *,
        task: _AsyncTaskFactory,
        run_interval: int,
        next_run: datetime | None = None,
    ):
        """
        Initialize a scheduler job.

        Args:
        ----
            task: Async callable to execute
            run_interval: Interval in seconds between executions
            next_run: When to run next (defaults to now)

        """
        self._task: Final = task
        self._next_run = next_run or datetime.now()
        self._run_interval: Final = run_interval

    @property
    def name(self) -> str:
        """Return the name of the task."""
        return self._task.__name__

    @property
    def next_run(self) -> datetime:
        """Return the next scheduled run timestamp."""
        return self._next_run

    @property
    def ready(self) -> bool:
        """Return True if the job is ready to execute."""
        return self._next_run < datetime.now()

    async def run(self) -> None:
        """Execute the job's task."""
        await self._task()

    def schedule_next_execution(self) -> None:
        """Schedule the next execution based on run_interval."""
        self._next_run += timedelta(seconds=self._run_interval)


class BackgroundScheduler:
    """
    Modern asyncio-based scheduler for periodic background tasks.

    Manages scheduled tasks such as connection checks, data refreshes, and
    firmware update checks.

    Features:
    ---------
    - Asyncio-based (no threads)
    - Graceful error handling per task
    - Configurable intervals
    - Start/stop lifecycle management
    - Responsive to central state changes

    """

    def __init__(
        self,
        *,
        central_info: CentralInfo,
        config_provider: ConfigProvider,
        client_coordinator: ClientCoordinator,
        connection_state_provider: ConnectionStateProvider,
        device_data_refresher: DeviceDataRefresher,
        firmware_data_refresher: FirmwareDataRefresher,
        event_coordinator: EventCoordinator,
        hub_data_fetcher: HubDataFetcher,
        event_bus_provider: EventBusProvider,
        json_rpc_client_provider: JsonRpcClientProvider,
        state_provider: CentralUnitStateProvider,
    ) -> None:
        """
        Initialize the background scheduler.

        Args:
        ----
            central_info: Provider for central system information
            config_provider: Provider for configuration access
            client_coordinator: Client coordinator for client operations
            connection_state_provider: Provider for connection state access
            device_data_refresher: Provider for device data refresh operations
            firmware_data_refresher: Provider for firmware data refresh operations
            event_coordinator: Event coordinator for event management
            hub_data_fetcher: Provider for hub data fetch operations
            event_bus_provider: Provider for event bus access
            json_rpc_client_provider: Provider for JSON-RPC client access
            state_provider: Provider for central unit state

        """
        self._central_info: Final = central_info
        self._config_provider: Final = config_provider
        self._client_coordinator: Final = client_coordinator
        self._connection_state_provider: Final = connection_state_provider
        self._device_data_refresher: Final = device_data_refresher
        self._firmware_data_refresher: Final = firmware_data_refresher
        self._event_coordinator: Final = event_coordinator
        self._hub_data_fetcher: Final = hub_data_fetcher
        self._event_bus_provider: Final = event_bus_provider
        self._json_rpc_client_provider: Final = json_rpc_client_provider
        self._state_provider: Final = state_provider

        # Use asyncio.Event for thread-safe state flags
        self._active_event: Final = asyncio.Event()
        self._devices_created_event: Final = asyncio.Event()
        self._scheduler_task: asyncio.Task[None] | None = None
        self._unsubscribe_callback: UnsubscribeCallback | None = None

        # Track when connection was lost for staged reconnection
        self._connection_lost_at: datetime | None = None
        # Track if TCP port became available (stage 1 passed)
        self._tcp_port_available: bool = False
        # Track when first RPC check (listMethods) passed - start of warmup phase
        self._rpc_check_passed_at: datetime | None = None

        # Subscribe to DeviceLifecycleEvent for CREATED events
        def _event_handler(*, event: DeviceLifecycleEvent) -> None:
            self._on_device_lifecycle_event(event=event)

        self._unsubscribe_callback = self._event_bus_provider.event_bus.subscribe(
            event_type=DeviceLifecycleEvent,
            event_key=None,
            handler=_event_handler,
        )

        # Define scheduled jobs
        self._scheduler_jobs: Final[list[SchedulerJob]] = [
            SchedulerJob(
                task=self._check_connection,
                run_interval=int(self._config_provider.config.timeout_config.connection_checker_interval),
            ),
            SchedulerJob(
                task=self._refresh_client_data,
                run_interval=self._config_provider.config.periodic_refresh_interval,
            ),
            SchedulerJob(
                task=self._refresh_program_data,
                run_interval=self._config_provider.config.sys_scan_interval,
            ),
            SchedulerJob(
                task=self._refresh_sysvar_data,
                run_interval=self._config_provider.config.sys_scan_interval,
            ),
            SchedulerJob(
                task=self._refresh_inbox_data,
                run_interval=self._config_provider.config.sys_scan_interval,
            ),
            SchedulerJob(
                task=self._refresh_system_update_data,
                run_interval=SYSTEM_UPDATE_CHECK_INTERVAL,
            ),
            SchedulerJob(
                task=self._fetch_device_firmware_update_data,
                run_interval=DEVICE_FIRMWARE_CHECK_INTERVAL,
            ),
            SchedulerJob(
                task=self._fetch_device_firmware_update_data_in_delivery,
                run_interval=DEVICE_FIRMWARE_DELIVERING_CHECK_INTERVAL,
            ),
            SchedulerJob(
                task=self._fetch_device_firmware_update_data_in_update,
                run_interval=DEVICE_FIRMWARE_UPDATING_CHECK_INTERVAL,
            ),
        ]

    @property
    def devices_created(self) -> bool:
        """Return True if devices have been created."""
        return self._devices_created_event.is_set()

    @property
    def has_connection_issue(self) -> bool:
        """Return True if there is a known connection issue."""
        return self._connection_state_provider.connection_state.has_any_issue

    @property
    def is_active(self) -> bool:
        """Return True if the scheduler is active."""
        return self._active_event.is_set()

    async def start(self) -> None:
        """Start the scheduler and begin running scheduled tasks."""
        if self._active_event.is_set():
            _LOGGER.warning("Scheduler for %s is already running", self._central_info.name)  # i18n-log: ignore
            return

        _LOGGER.debug("Starting scheduler for %s", self._central_info.name)
        self._active_event.set()
        self._scheduler_task = asyncio.create_task(self._run_scheduler_loop())

    async def stop(self) -> None:
        """Stop the scheduler and cancel all running tasks."""
        if not self._active_event.is_set():
            return

        _LOGGER.debug("Stopping scheduler for %s", self._central_info.name)
        self._active_event.clear()

        # Unsubscribe from events
        if self._unsubscribe_callback:
            self._unsubscribe_callback()
            self._unsubscribe_callback = None

        # Cancel scheduler task
        if self._scheduler_task and not self._scheduler_task.done():
            self._scheduler_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._scheduler_task

    async def _check_connection(self) -> None:
        """
        Check connection health to all clients and reconnect if necessary.

        Uses a staged reconnection approach when connection is lost:
        - Stage 1: TCP port check (non-invasive, no CCU load)
        - Stage 2: system.listMethods (read-only RPC check)
        - Stage 3: Full reconnect (init + proxy recreate)
        """
        _LOGGER.debug("CHECK_CONNECTION: Checking connection to server %s", self._central_info.name)
        try:
            if not self._client_coordinator.all_clients_active:
                _LOGGER.error(
                    i18n.tr(
                        "log.central.scheduler.check_connection.no_clients",
                        name=self._central_info.name,
                    )
                )
                await self._client_coordinator.restart_clients()

            # Staged reconnection when connection is lost
            elif self._connection_lost_at is not None:
                await self._handle_staged_reconnection()

            else:
                # Normal operation - perform client health checks
                # These checks may involve pings to the CCU
                clients_to_reconnect = [
                    client
                    for client in self._client_coordinator.clients
                    if client.available is False or not await client.is_connected() or not client.is_callback_alive()
                ]

                if clients_to_reconnect:
                    # Connection loss detected - start staged reconnection
                    self._connection_lost_at = datetime.now()
                    self._tcp_port_available = False
                    self._rpc_check_passed_at = None
                    _LOGGER.info(
                        i18n.tr(
                            "log.central.scheduler.check_connection.connection_loss_detected",
                            name=self._central_info.name,
                        )
                    )

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

    async def _check_rpc_available(self) -> bool:
        """
        Check if RPC interface is available via system.listMethods.

        This is a read-only RPC call that verifies the CCU XML-RPC service
        is responding. Used during staged reconnection to verify service
        availability before attempting full init.
        """
        for client in self._client_coordinator.clients:
            # Access proxy's system.listMethods via XML-RPC magic method
            # pylint: disable=protected-access
            if hasattr(client, "_proxy") and hasattr(client._proxy, "system"):
                try:
                    result = await client._proxy.system.listMethods()
                    return bool(result)  # Return True if we got a valid response
                except Exception:  # noqa: BLE001
                    return False
        return False

    async def _check_tcp_port_available(self, *, host: str, port: int) -> bool:
        """
        Check if a TCP port is available (non-invasive connectivity check).

        This is used as the first stage of reconnection to verify the CCU
        is responding before attempting RPC calls. It's non-invasive as it
        only opens and immediately closes a TCP connection.
        """
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=2.0,
            )
            writer.close()
            await writer.wait_closed()
        except (TimeoutError, OSError):
            return False
        else:
            return True

    async def _fetch_device_firmware_update_data(self) -> None:
        """Periodically fetch device firmware update data from backend."""
        if (
            not self._config_provider.config.enable_device_firmware_check
            or not self._central_info.available
            or not self.devices_created
        ):
            return

        _LOGGER.debug(
            "FETCH_DEVICE_FIRMWARE_UPDATE_DATA: Scheduled fetching for %s",
            self._central_info.name,
        )
        await self._firmware_data_refresher.refresh_firmware_data()

    async def _fetch_device_firmware_update_data_in_delivery(self) -> None:
        """Fetch firmware update data for devices in delivery state."""
        if (
            not self._config_provider.config.enable_device_firmware_check
            or not self._central_info.available
            or not self.devices_created
        ):
            return

        _LOGGER.debug(
            "FETCH_DEVICE_FIRMWARE_UPDATE_DATA_IN_DELIVERY: For delivering devices for %s",
            self._central_info.name,
        )
        await self._firmware_data_refresher.refresh_firmware_data_by_state(
            device_firmware_states=(
                DeviceFirmwareState.DELIVER_FIRMWARE_IMAGE,
                DeviceFirmwareState.LIVE_DELIVER_FIRMWARE_IMAGE,
            )
        )

    async def _fetch_device_firmware_update_data_in_update(self) -> None:
        """Fetch firmware update data for devices in update state."""
        if (
            not self._config_provider.config.enable_device_firmware_check
            or not self._central_info.available
            or not self.devices_created
        ):
            return

        _LOGGER.debug(
            "FETCH_DEVICE_FIRMWARE_UPDATE_DATA_IN_UPDATE: For updating devices for %s",
            self._central_info.name,
        )
        await self._firmware_data_refresher.refresh_firmware_data_by_state(
            device_firmware_states=(
                DeviceFirmwareState.READY_FOR_UPDATE,
                DeviceFirmwareState.DO_UPDATE_PENDING,
                DeviceFirmwareState.PERFORMING_UPDATE,
            )
        )

    def _get_first_client_port(self) -> int | None:
        """Get the port from the first configured client."""
        for client in self._client_coordinator.clients:
            # Access internal config to get port - pylint: disable=protected-access
            if hasattr(client, "_config") and hasattr(client._config, "interface_config"):
                port = client._config.interface_config.port  # pylint: disable=protected-access
                return port if isinstance(port, int) else None
        return None

    async def _handle_staged_reconnection(self) -> None:
        """
        Handle staged reconnection after connection loss.

        Stage 0: Initial cool-down (give CCU time to start shutting down gracefully)
        Stage 1: Check TCP port availability (non-invasive)
        Stage 2: First listMethods check (verify RPC is responding)
        Stage 3: Warmup delay (allow CCU services to stabilize)
        Stage 4: Second listMethods check (confirm stability)
        Stage 5: Perform full reconnection (init + proxy recreate)
        """
        timeout_config = self._config_provider.config.timeout_config
        # _connection_lost_at is guaranteed non-None when this method is called
        assert self._connection_lost_at is not None
        elapsed = (datetime.now() - self._connection_lost_at).total_seconds()

        # Stage 0: Initial cool-down before any checks
        if elapsed < timeout_config.reconnect_initial_cooldown:
            remaining = timeout_config.reconnect_initial_cooldown - elapsed
            _LOGGER.debug(
                "CHECK_CONNECTION: Initial cool-down for %s - %.1fs remaining",
                self._central_info.name,
                remaining,
            )
            return  # Wait for cool-down to complete

        # Stage 1: TCP port check (non-invasive)
        # Calculate time since cool-down ended (TCP check phase)
        tcp_check_elapsed = elapsed - timeout_config.reconnect_initial_cooldown
        if not self._tcp_port_available:
            # Check if max TCP check timeout exceeded (measured from after cool-down)
            if tcp_check_elapsed >= timeout_config.reconnect_tcp_check_timeout:
                _LOGGER.warning(
                    i18n.tr(
                        "log.central.scheduler.check_connection.tcp_check_timeout",
                        name=self._central_info.name,
                        timeout=timeout_config.reconnect_tcp_check_timeout,
                    )
                )
                # Reset and retry from beginning
                self._connection_lost_at = datetime.now()
                return

            # Perform TCP port check
            host = self._config_provider.config.host
            port = self._get_first_client_port()
            if port and await self._check_tcp_port_available(host=host, port=port):
                self._tcp_port_available = True
                _LOGGER.info(
                    i18n.tr(
                        "log.central.scheduler.check_connection.tcp_port_available",
                        name=self._central_info.name,
                        host=host,
                        port=port,
                    )
                )
            else:
                _LOGGER.debug(
                    "CHECK_CONNECTION: TCP port check for %s - port %s:%s not yet available (%.1fs of %.1fs)",
                    self._central_info.name,
                    host,
                    port,
                    tcp_check_elapsed,
                    timeout_config.reconnect_tcp_check_timeout,
                )
                return  # Wait for next check interval

        # Stage 2: First listMethods check (verify RPC is responding)
        if self._rpc_check_passed_at is None:
            if await self._check_rpc_available():
                self._rpc_check_passed_at = datetime.now()
                _LOGGER.info(
                    i18n.tr(
                        "log.central.scheduler.check_connection.rpc_check_passed",
                        name=self._central_info.name,
                    )
                )
            else:
                _LOGGER.debug(
                    "CHECK_CONNECTION: RPC check for %s - listMethods not yet responding",
                    self._central_info.name,
                )
                return  # Wait for next check interval

        # Stage 3: Warmup delay (allow CCU services to stabilize)
        warmup_elapsed = (datetime.now() - self._rpc_check_passed_at).total_seconds()
        if warmup_elapsed < timeout_config.reconnect_warmup_delay:
            remaining = timeout_config.reconnect_warmup_delay - warmup_elapsed
            _LOGGER.debug(
                "CHECK_CONNECTION: Warmup for %s - %.1fs remaining",
                self._central_info.name,
                remaining,
            )
            return  # Wait for warmup to complete

        # Stage 4: Second listMethods check (confirm stability)
        if not await self._check_rpc_available():
            # RPC became unavailable during warmup - reset to stage 2
            _LOGGER.warning(
                i18n.tr(
                    "log.central.scheduler.check_connection.rpc_unstable",
                    name=self._central_info.name,
                )
            )
            self._rpc_check_passed_at = None
            return  # Retry RPC check

        _LOGGER.info(
            i18n.tr(
                "log.central.scheduler.check_connection.rpc_stable",
                name=self._central_info.name,
            )
        )

        # Stage 5: Full reconnection (init + proxy recreate)
        _LOGGER.info(
            i18n.tr(
                "log.central.scheduler.check_connection.attempting_reconnect",
                name=self._central_info.name,
            )
        )

        reconnects = [client.reconnect() for client in self._client_coordinator.clients]
        await asyncio.gather(*reconnects)

        # Check which interfaces are now available
        available_interfaces = [client.interface for client in self._client_coordinator.clients if client.available]

        if available_interfaces:
            # Reconnection successful - reset state
            self._connection_lost_at = None
            self._tcp_port_available = False
            self._rpc_check_passed_at = None
            _LOGGER.info(
                i18n.tr(
                    "log.central.scheduler.check_connection.reconnect_success",
                    name=self._central_info.name,
                    interfaces=", ".join(str(i) for i in available_interfaces),
                )
            )
            # Load data with retry logic - JSON-RPC service may not be
            # fully available immediately after CCU restart
            await self._load_data_with_retry(interfaces=available_interfaces)
        else:
            # Reconnection failed - reset to retry from stage 1
            self._tcp_port_available = False
            self._rpc_check_passed_at = None
            _LOGGER.warning(
                i18n.tr(
                    "log.central.scheduler.check_connection.reconnect_failed",
                    name=self._central_info.name,
                )
            )

    async def _load_data_with_retry(self, *, interfaces: list[Interface]) -> None:
        """
        Load data point data for interfaces with retry logic.

        After CCU restart, both JSON-RPC and XML-RPC services may not be immediately
        available. This method waits for both services to become available before
        loading data.

        For non-CCU backends (Homegear, PyDevCCU), retry logic is skipped as they
        don't have the same service availability issues.

        Args:
        ----
            interfaces: List of interfaces to reload data for

        """
        # Check if any client uses the CCU backend (which has JSON-RPC service)
        uses_ccu_backend = any(
            client.model == Backend.CCU for client in self._client_coordinator.clients if client.interface in interfaces
        )

        # For CCU backends, wait for JSON-RPC service to become available
        if uses_ccu_backend:
            json_rpc_client = self._json_rpc_client_provider.json_rpc_client
            for attempt in range(_POST_RECONNECT_MAX_RETRIES):
                if await json_rpc_client.is_service_available():
                    _LOGGER.debug(
                        "LOAD_DATA_WITH_RETRY: JSON-RPC service available for %s (attempt %d)",
                        self._central_info.name,
                        attempt + 1,
                    )
                    break
                if attempt < _POST_RECONNECT_MAX_RETRIES - 1:
                    _LOGGER.debug(
                        "LOAD_DATA_WITH_RETRY: JSON-RPC service not yet available for %s "
                        "- retrying in %.1fs (attempt %d/%d)",
                        self._central_info.name,
                        _POST_RECONNECT_RETRY_DELAY,
                        attempt + 1,
                        _POST_RECONNECT_MAX_RETRIES,
                    )
                    await asyncio.sleep(_POST_RECONNECT_RETRY_DELAY)
                else:
                    _LOGGER.warning(  # i18n-log: ignore
                        "LOAD_DATA_WITH_RETRY: JSON-RPC service not available after %d attempts for %s "
                        "- proceeding with data load anyway",
                        _POST_RECONNECT_MAX_RETRIES,
                        self._central_info.name,
                    )

        # Wait for XML-RPC stability - verify all clients are in CONNECTED state AND
        # can actually communicate with the backend. The state machine may be in CONNECTED
        # state but the backend ports may not be fully ready yet.
        clients_to_check = [client for client in self._client_coordinator.clients if client.interface in interfaces]
        for attempt in range(_POST_RECONNECT_MAX_RETRIES):
            all_stable = True
            for client in clients_to_check:
                # Check both state machine status AND actual connection availability
                if not client.available or not await client.check_connection_availability(handle_ping_pong=False):
                    all_stable = False
                    break
            if all_stable:
                _LOGGER.debug(
                    "LOAD_DATA_WITH_RETRY: All clients stable for %s (attempt %d)",
                    self._central_info.name,
                    attempt + 1,
                )
                break
            if attempt < _POST_RECONNECT_MAX_RETRIES - 1:
                _LOGGER.debug(
                    "LOAD_DATA_WITH_RETRY: Not all clients stable for %s - retrying in %.1fs (attempt %d/%d)",
                    self._central_info.name,
                    _POST_RECONNECT_RETRY_DELAY,
                    attempt + 1,
                    _POST_RECONNECT_MAX_RETRIES,
                )
                await asyncio.sleep(_POST_RECONNECT_RETRY_DELAY)
            else:
                _LOGGER.warning(  # i18n-log: ignore
                    "LOAD_DATA_WITH_RETRY: Not all clients stable after %d attempts for %s "
                    "- proceeding with data load anyway",
                    _POST_RECONNECT_MAX_RETRIES,
                    self._central_info.name,
                )

        # Load data for all interfaces with retry logic
        # Even after stability checks pass, data operations may fail if CCU is still initializing.
        # Data loading doesn't raise exceptions for individual failures - instead check if circuit
        # breakers opened during loading (indicating backend wasn't ready).
        for data_attempt in range(_DATA_LOAD_MAX_RETRIES):
            # Before each data load attempt, verify XML-RPC is actually ready
            # by doing an active connection check. The CCU may accept init() but
            # not be ready for data operations yet.
            if data_attempt > 0:
                # Wait before retry
                _LOGGER.debug(
                    "LOAD_DATA_WITH_RETRY: Waiting %.1fs before data load retry %d/%d for %s",
                    _DATA_LOAD_RETRY_DELAY,
                    data_attempt + 1,
                    _DATA_LOAD_MAX_RETRIES,
                    self._central_info.name,
                )
                await asyncio.sleep(_DATA_LOAD_RETRY_DELAY)

                # Re-check XML-RPC stability before retry
                all_stable = True
                for client in clients_to_check:
                    if not await client.check_connection_availability(handle_ping_pong=False):
                        all_stable = False
                        _LOGGER.debug(
                            "LOAD_DATA_WITH_RETRY: Client %s not stable before retry %d/%d",
                            client.interface_id,
                            data_attempt + 1,
                            _DATA_LOAD_MAX_RETRIES,
                        )
                        break
                if not all_stable:
                    # Skip this attempt, circuit breakers will be checked at end of loop
                    continue

            try:
                reloads = [
                    self._device_data_refresher.load_and_refresh_data_point_data(interface=interface)
                    for interface in interfaces
                ]
                await asyncio.gather(*reloads)
            except BaseHomematicException as bhexc:
                _LOGGER.debug(
                    "LOAD_DATA_WITH_RETRY: Data load attempt %d/%d raised exception for %s: %s [%s]",
                    data_attempt + 1,
                    _DATA_LOAD_MAX_RETRIES,
                    self._central_info.name,
                    bhexc.name,
                    extract_exc_args(exc=bhexc),
                )
                # Reset circuit breakers to allow retry
                for client in clients_to_check:
                    client.reset_circuit_breakers()
                if data_attempt >= _DATA_LOAD_MAX_RETRIES - 1:
                    _LOGGER.warning(  # i18n-log: ignore
                        "LOAD_DATA_WITH_RETRY: Data load failed after %d attempts for %s: %s [%s]",
                        _DATA_LOAD_MAX_RETRIES,
                        self._central_info.name,
                        bhexc.name,
                        extract_exc_args(exc=bhexc),
                    )
                    return
                continue

            # Check if any circuit breakers opened during data loading
            # This indicates the CCU wasn't ready even though stability checks passed
            if all(client.all_circuit_breakers_closed for client in clients_to_check):
                _LOGGER.debug(
                    "LOAD_DATA_WITH_RETRY: Data loaded successfully for %s",
                    self._central_info.name,
                )
                return

            # Circuit breakers opened - CCU not fully ready
            _LOGGER.debug(
                "LOAD_DATA_WITH_RETRY: Circuit breakers opened during data load attempt %d/%d for %s",
                data_attempt + 1,
                _DATA_LOAD_MAX_RETRIES,
                self._central_info.name,
            )
            # Reset circuit breakers to allow retry
            for client in clients_to_check:
                client.reset_circuit_breakers()

            if data_attempt >= _DATA_LOAD_MAX_RETRIES - 1:
                _LOGGER.warning(  # i18n-log: ignore
                    "LOAD_DATA_WITH_RETRY: Circuit breakers opened during all %d data load attempts for %s "
                    "- CCU may not be fully ready",
                    _DATA_LOAD_MAX_RETRIES,
                    self._central_info.name,
                )

    def _on_device_lifecycle_event(self, *, event: DeviceLifecycleEvent) -> None:
        """
        Handle device lifecycle events.

        Args:
        ----
            event: DeviceLifecycleEvent instance

        """
        if event.event_type == DeviceLifecycleEventType.CREATED:
            self._devices_created_event.set()

    async def _refresh_client_data(self) -> None:
        """Refresh client data for polled interfaces."""
        if not self._central_info.available:
            return

        if (poll_clients := self._client_coordinator.poll_clients) is not None and len(poll_clients) > 0:
            _LOGGER.debug("REFRESH_CLIENT_DATA: Loading data for %s", self._central_info.name)
            for client in poll_clients:
                await self._device_data_refresher.load_and_refresh_data_point_data(interface=client.interface)
                self._event_coordinator.set_last_event_seen_for_interface(interface_id=client.interface_id)

    async def _refresh_inbox_data(self) -> None:
        """Refresh inbox data."""
        if not self._central_info.available or not self.devices_created:
            return

        _LOGGER.debug("REFRESH_INBOX_DATA: For %s", self._central_info.name)
        await self._hub_data_fetcher.fetch_inbox_data(scheduled=True)

    async def _refresh_program_data(self) -> None:
        """Refresh system programs data."""
        if (
            not self._config_provider.config.enable_program_scan
            or not self._central_info.available
            or not self.devices_created
        ):
            return

        _LOGGER.debug("REFRESH_PROGRAM_DATA: For %s", self._central_info.name)
        await self._hub_data_fetcher.fetch_program_data(scheduled=True)

    async def _refresh_system_update_data(self) -> None:
        """Refresh system update data."""
        if not self._central_info.available or not self.devices_created:
            return

        _LOGGER.debug("REFRESH_SYSTEM_UPDATE_DATA: For %s", self._central_info.name)
        await self._hub_data_fetcher.fetch_system_update_data(scheduled=True)

    async def _refresh_sysvar_data(self) -> None:
        """Refresh system variables data."""
        if (
            not self._config_provider.config.enable_sysvar_scan
            or not self._central_info.available
            or not self.devices_created
        ):
            return

        _LOGGER.debug("REFRESH_SYSVAR_DATA: For %s", self._central_info.name)
        await self._hub_data_fetcher.fetch_sysvar_data(scheduled=True)

    async def _run_scheduler_loop(self) -> None:
        """Execute the main scheduler loop that runs jobs based on their schedule."""
        connection_issue_logged = False
        while self.is_active:
            # Wait until central is running
            if self._state_provider.state != CentralState.RUNNING:
                _LOGGER.debug("Scheduler: Waiting until central %s is started", self._central_info.name)
                await asyncio.sleep(SCHEDULER_NOT_STARTED_SLEEP)
                continue

            # Check for connection issues - pause most jobs when connection is down
            # Only _check_connection continues to run to detect reconnection
            has_issue = self.has_connection_issue
            if has_issue and not connection_issue_logged:
                _LOGGER.debug(
                    "Scheduler: Pausing jobs due to connection issue for %s (connection check continues)",
                    self._central_info.name,
                )
                connection_issue_logged = True
            elif not has_issue and connection_issue_logged:
                _LOGGER.debug(
                    "Scheduler: Resuming jobs after connection restored for %s",
                    self._central_info.name,
                )
                connection_issue_logged = False

            # Execute ready jobs
            any_executed = False
            for job in self._scheduler_jobs:
                if not self.is_active or not job.ready:
                    continue

                # Skip non-connection-check jobs when there's a connection issue
                # This prevents unnecessary RPC calls and log spam during CCU restart
                if has_issue and job.name != "_check_connection":
                    continue

                try:
                    await job.run()
                except Exception:
                    _LOGGER.exception(  # i18n-log: ignore
                        "SCHEDULER: Job %s failed for %s",
                        job.name,
                        self._central_info.name,
                    )
                job.schedule_next_execution()
                any_executed = True

            if not self.is_active:
                break  # type: ignore[unreachable]

            # Sleep logic: minimize CPU usage when idle
            if not any_executed:
                now = datetime.now()
                try:
                    next_due = min(job.next_run for job in self._scheduler_jobs)
                    # Sleep until the next task, capped at 1s for responsiveness
                    delay = max(0.0, (next_due - now).total_seconds())
                    await asyncio.sleep(min(1.0, delay))
                except ValueError:
                    # No jobs configured; use default sleep
                    await asyncio.sleep(SCHEDULER_LOOP_SLEEP)
            else:
                # Brief yield after executing jobs
                await asyncio.sleep(SCHEDULER_LOOP_SLEEP)
