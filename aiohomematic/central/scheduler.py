# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Background scheduler for periodic tasks in aiohomematic.

This module provides a modern asyncio-based scheduler that manages periodic
background tasks such as:

- Connection health checks (detection only - emits ConnectionLostEvent)
- Data refreshes (client data, programs, system variables)
- Firmware update checks
- Metrics refresh

Connection recovery is handled by ConnectionRecoveryCoordinator which subscribes
to ConnectionLostEvent emitted by this scheduler.

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
from aiohomematic.central.event_bus import ConnectionLostEvent, DataRefreshCompletedEvent, DataRefreshTriggeredEvent
from aiohomematic.central.event_coordinator import EventCoordinator
from aiohomematic.central.integration_events import DeviceLifecycleEvent, DeviceLifecycleEventType
from aiohomematic.const import SCHEDULER_LOOP_SLEEP, SCHEDULER_NOT_STARTED_SLEEP, CentralState, DeviceFirmwareState
from aiohomematic.exceptions import NoConnectionException
from aiohomematic.interfaces.central import (
    CentralInfoProtocol,
    CentralUnitStateProviderProtocol,
    ConfigProviderProtocol,
    DeviceDataRefresherProtocol,
    EventBusProviderProtocol,
    FirmwareDataRefresherProtocol,
    HubDataFetcherProtocol,
)
from aiohomematic.interfaces.client import ConnectionStateProviderProtocol
from aiohomematic.property_decorators import DelegatedProperty
from aiohomematic.support import extract_exc_args
from aiohomematic.type_aliases import UnsubscribeCallback

_LOGGER: Final = logging.getLogger(__name__)

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

    name: Final = DelegatedProperty[str](path="_task.__name__")
    next_run: Final = DelegatedProperty[datetime](path="_next_run")

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
        central_info: CentralInfoProtocol,
        config_provider: ConfigProviderProtocol,
        client_coordinator: ClientCoordinator,
        connection_state_provider: ConnectionStateProviderProtocol,
        device_data_refresher: DeviceDataRefresherProtocol,
        firmware_data_refresher: FirmwareDataRefresherProtocol,
        event_coordinator: EventCoordinator,
        hub_data_fetcher: HubDataFetcherProtocol,
        event_bus_provider: EventBusProviderProtocol,
        state_provider: CentralUnitStateProviderProtocol,
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
        self._state_provider: Final = state_provider

        # Use asyncio.Event for thread-safe state flags
        self._active_event: Final = asyncio.Event()
        self._devices_created_event: Final = asyncio.Event()
        self._scheduler_task: asyncio.Task[None] | None = None
        self._unsubscribe_callback: UnsubscribeCallback | None = None

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
                run_interval=self._config_provider.config.schedule_timer_config.connection_checker_interval,
            ),
            SchedulerJob(
                task=self._refresh_client_data,
                run_interval=self._config_provider.config.schedule_timer_config.periodic_refresh_interval,
            ),
            SchedulerJob(
                task=self._refresh_program_data,
                run_interval=self._config_provider.config.schedule_timer_config.sys_scan_interval,
            ),
            SchedulerJob(
                task=self._refresh_sysvar_data,
                run_interval=self._config_provider.config.schedule_timer_config.sys_scan_interval,
            ),
            SchedulerJob(
                task=self._refresh_inbox_data,
                run_interval=self._config_provider.config.schedule_timer_config.sys_scan_interval,
            ),
            SchedulerJob(
                task=self._refresh_system_update_data,
                run_interval=self._config_provider.config.schedule_timer_config.system_update_check_interval,
            ),
            SchedulerJob(
                task=self._fetch_device_firmware_update_data,
                run_interval=self._config_provider.config.schedule_timer_config.device_firmware_check_interval,
            ),
            SchedulerJob(
                task=self._fetch_device_firmware_update_data_in_delivery,
                run_interval=self._config_provider.config.schedule_timer_config.device_firmware_delivering_check_interval,
            ),
            SchedulerJob(
                task=self._fetch_device_firmware_update_data_in_update,
                run_interval=self._config_provider.config.schedule_timer_config.device_firmware_updating_check_interval,
            ),
            SchedulerJob(
                task=self._refresh_metrics_data,
                run_interval=self._config_provider.config.schedule_timer_config.metrics_refresh_interval,
            ),
        ]

    has_connection_issue: Final = DelegatedProperty[bool](
        path="_connection_state_provider.connection_state.has_any_issue"
    )

    @property
    def devices_created(self) -> bool:
        """Return True if devices have been created."""
        return self._devices_created_event.is_set()

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
        Check connection health to all clients.

        Detection only - emits ConnectionLostEvent when connection issues are detected.
        Actual recovery is handled by ConnectionRecoveryCoordinator.
        """
        _LOGGER.debug("CHECK_CONNECTION: Checking connection to server %s", self._central_info.name)
        try:
            if not self._client_coordinator.all_clients_active:
                _LOGGER.error(
                    i18n.tr(
                        key="log.central.scheduler.check_connection.no_clients",
                        name=self._central_info.name,
                    )
                )
                # Emit ConnectionLostEvent for each inactive client
                for client in self._client_coordinator.clients:
                    if not client.available:
                        await self._emit_connection_lost(
                            interface_id=client.interface_id,
                            reason="client_not_active",
                        )
                return

            # Normal operation - perform client health checks
            for client in self._client_coordinator.clients:
                if client.available is False or not await client.is_connected() or not client.is_callback_alive():
                    # Connection loss detected - emit event for ConnectionRecoveryCoordinator
                    reason = (
                        "not_available"
                        if not client.available
                        else "not_connected"
                        if not await client.is_connected()
                        else "callback_not_alive"
                    )
                    await self._emit_connection_lost(
                        interface_id=client.interface_id,
                        reason=reason,
                    )
                    _LOGGER.info(
                        i18n.tr(
                            key="log.central.scheduler.check_connection.connection_loss_detected",
                            name=self._central_info.name,
                        )
                    )

        except NoConnectionException as nex:
            _LOGGER.error(
                i18n.tr(
                    key="log.central.scheduler.check_connection.no_connection",
                    reason=extract_exc_args(exc=nex),
                )
            )
        except Exception as exc:
            _LOGGER.error(
                i18n.tr(
                    key="log.central.scheduler.check_connection.failed",
                    exc_type=type(exc).__name__,
                    reason=extract_exc_args(exc=exc),
                )
            )

    async def _emit_connection_lost(self, *, interface_id: str, reason: str) -> None:
        """Emit a ConnectionLostEvent for the specified interface."""
        await self._event_bus_provider.event_bus.publish(
            event=ConnectionLostEvent(
                timestamp=datetime.now(),
                interface_id=interface_id,
                reason=reason,
                detected_at=datetime.now(),
            )
        )

    async def _emit_refresh_completed(
        self,
        *,
        refresh_type: str,
        interface_id: str | None,
        success: bool,
        duration_ms: float,
        items_refreshed: int = 0,
        error_message: str | None = None,
    ) -> None:
        """
        Emit a data refresh completed event.

        Args:
        ----
            refresh_type: Type of refresh (e.g., "client_data", "program")
            interface_id: Interface ID or None for hub-level refreshes
            success: True if refresh completed successfully
            duration_ms: Duration of the refresh operation in milliseconds
            items_refreshed: Number of items refreshed
            error_message: Error message if success is False

        """
        await self._event_bus_provider.event_bus.publish(
            event=DataRefreshCompletedEvent(
                timestamp=datetime.now(),
                refresh_type=refresh_type,
                interface_id=interface_id,
                success=success,
                duration_ms=duration_ms,
                items_refreshed=items_refreshed,
                error_message=error_message,
            )
        )

    def _emit_refresh_triggered(
        self,
        *,
        refresh_type: str,
        interface_id: str | None,
        scheduled: bool,
    ) -> None:
        """
        Emit a data refresh triggered event.

        Args:
        ----
            refresh_type: Type of refresh (e.g., "client_data", "program")
            interface_id: Interface ID or None for hub-level refreshes
            scheduled: True if this is a scheduled refresh

        """
        self._event_bus_provider.event_bus.publish_sync(
            event=DataRefreshTriggeredEvent(
                timestamp=datetime.now(),
                refresh_type=refresh_type,
                interface_id=interface_id,
                scheduled=scheduled,
            )
        )

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
                start_time = datetime.now()
                self._emit_refresh_triggered(
                    refresh_type="client_data",
                    interface_id=client.interface_id,
                    scheduled=True,
                )
                try:
                    await self._device_data_refresher.load_and_refresh_data_point_data(interface=client.interface)
                    self._event_coordinator.set_last_event_seen_for_interface(interface_id=client.interface_id)
                    duration_ms = (datetime.now() - start_time).total_seconds() * 1000
                    await self._emit_refresh_completed(
                        refresh_type="client_data",
                        interface_id=client.interface_id,
                        success=True,
                        duration_ms=duration_ms,
                    )
                except Exception as exc:
                    duration_ms = (datetime.now() - start_time).total_seconds() * 1000
                    await self._emit_refresh_completed(
                        refresh_type="client_data",
                        interface_id=client.interface_id,
                        success=False,
                        duration_ms=duration_ms,
                        error_message=str(exc),
                    )
                    raise

    async def _refresh_inbox_data(self) -> None:
        """Refresh inbox data."""
        if not self._central_info.available or not self.devices_created:
            return

        _LOGGER.debug("REFRESH_INBOX_DATA: For %s", self._central_info.name)
        start_time = datetime.now()
        self._emit_refresh_triggered(
            refresh_type="inbox",
            interface_id=None,
            scheduled=True,
        )
        try:
            await self._hub_data_fetcher.fetch_inbox_data(scheduled=True)
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            await self._emit_refresh_completed(
                refresh_type="inbox",
                interface_id=None,
                success=True,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            await self._emit_refresh_completed(
                refresh_type="inbox",
                interface_id=None,
                success=False,
                duration_ms=duration_ms,
                error_message=str(exc),
            )
            raise

    async def _refresh_metrics_data(self) -> None:
        """Refresh metrics hub sensors."""
        if not self._central_info.available or not self.devices_created:
            return

        _LOGGER.debug("REFRESH_METRICS_DATA: For %s", self._central_info.name)
        start_time = datetime.now()
        self._emit_refresh_triggered(
            refresh_type="metrics",
            interface_id=None,
            scheduled=True,
        )
        try:
            self._hub_data_fetcher.fetch_metrics_data(scheduled=True)
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            await self._emit_refresh_completed(
                refresh_type="metrics",
                interface_id=None,
                success=True,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            await self._emit_refresh_completed(
                refresh_type="metrics",
                interface_id=None,
                success=False,
                duration_ms=duration_ms,
                error_message=str(exc),
            )
            raise

    async def _refresh_program_data(self) -> None:
        """Refresh system programs data."""
        if (
            not self._config_provider.config.enable_program_scan
            or not self._central_info.available
            or not self.devices_created
        ):
            return

        _LOGGER.debug("REFRESH_PROGRAM_DATA: For %s", self._central_info.name)
        start_time = datetime.now()
        self._emit_refresh_triggered(
            refresh_type="program",
            interface_id=None,
            scheduled=True,
        )
        try:
            await self._hub_data_fetcher.fetch_program_data(scheduled=True)
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            await self._emit_refresh_completed(
                refresh_type="program",
                interface_id=None,
                success=True,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            await self._emit_refresh_completed(
                refresh_type="program",
                interface_id=None,
                success=False,
                duration_ms=duration_ms,
                error_message=str(exc),
            )
            raise

    async def _refresh_system_update_data(self) -> None:
        """Refresh system update data."""
        if not self._central_info.available or not self.devices_created:
            return

        _LOGGER.debug("REFRESH_SYSTEM_UPDATE_DATA: For %s", self._central_info.name)
        start_time = datetime.now()
        self._emit_refresh_triggered(
            refresh_type="system_update",
            interface_id=None,
            scheduled=True,
        )
        try:
            await self._hub_data_fetcher.fetch_system_update_data(scheduled=True)
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            await self._emit_refresh_completed(
                refresh_type="system_update",
                interface_id=None,
                success=True,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            await self._emit_refresh_completed(
                refresh_type="system_update",
                interface_id=None,
                success=False,
                duration_ms=duration_ms,
                error_message=str(exc),
            )
            raise

    async def _refresh_sysvar_data(self) -> None:
        """Refresh system variables data."""
        if (
            not self._config_provider.config.enable_sysvar_scan
            or not self._central_info.available
            or not self.devices_created
        ):
            return

        _LOGGER.debug("REFRESH_SYSVAR_DATA: For %s", self._central_info.name)
        start_time = datetime.now()
        self._emit_refresh_triggered(
            refresh_type="sysvar",
            interface_id=None,
            scheduled=True,
        )
        try:
            await self._hub_data_fetcher.fetch_sysvar_data(scheduled=True)
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            await self._emit_refresh_completed(
                refresh_type="sysvar",
                interface_id=None,
                success=True,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            await self._emit_refresh_completed(
                refresh_type="sysvar",
                interface_id=None,
                success=False,
                duration_ms=duration_ms,
                error_message=str(exc),
            )
            raise

    async def _run_scheduler_loop(self) -> None:
        """Execute the main scheduler loop that runs jobs based on their schedule."""
        connection_issue_logged = False
        while self.is_active:
            # Wait until central is operational (RUNNING or DEGRADED)
            # DEGRADED means at least one interface is working, so scheduler should run
            if (current_state := self._state_provider.state) not in (CentralState.RUNNING, CentralState.DEGRADED):
                _LOGGER.debug(
                    "Scheduler: Waiting until central %s is operational (current: %s)",
                    self._central_info.name,
                    current_state.value,
                )
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
