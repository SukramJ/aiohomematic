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
from typing import TYPE_CHECKING, Any, Final

from aiohomematic import i18n
from aiohomematic.central.event_bus import BackendSystemEventData
from aiohomematic.const import (
    CONNECTION_CHECKER_INTERVAL,
    DEVICE_FIRMWARE_CHECK_INTERVAL,
    DEVICE_FIRMWARE_DELIVERING_CHECK_INTERVAL,
    DEVICE_FIRMWARE_UPDATING_CHECK_INTERVAL,
    SCHEDULER_LOOP_SLEEP,
    SCHEDULER_NOT_STARTED_SLEEP,
    BackendSystemEvent,
    CentralUnitState,
    DeviceFirmwareState,
)
from aiohomematic.exceptions import NoConnectionException
from aiohomematic.model.interfaces import (
    CentralInfo,
    CentralUnitStateProvider,
    ClientCoordination,
    ConfigProvider,
    DeviceDataRefresher,
    EventBusProvider,
    HubDataFetcher,
)
from aiohomematic.support import extract_exc_args

if TYPE_CHECKING:
    pass

_LOGGER: Final = logging.getLogger(__name__)

# Type alias for async task factory
AsyncTaskFactory = Callable[[], Awaitable[None]]


class SchedulerJob:
    """Represents a scheduled job with interval-based execution."""

    def __init__(
        self,
        *,
        task: AsyncTaskFactory,
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
    firmware update checks. Replaces the legacy threading-based _Scheduler.

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
        client_coordination: ClientCoordination,
        device_data_refresher: DeviceDataRefresher,
        hub_data_fetcher: HubDataFetcher,
        event_bus_provider: EventBusProvider,
        state_provider: CentralUnitStateProvider,
    ) -> None:
        """
        Initialize the background scheduler.

        Args:
        ----
            central_info: Provider for central system information
            config_provider: Provider for configuration access
            client_coordination: Provider for client coordination operations
            device_data_refresher: Provider for device data refresh operations
            hub_data_fetcher: Provider for hub data fetch operations
            event_bus_provider: Provider for event bus access
            state_provider: Provider for central unit state

        """
        self._central_info: Final = central_info
        self._config_provider: Final = config_provider
        self._client_coordination: Final = client_coordination
        self._device_data_refresher: Final = device_data_refresher
        self._hub_data_fetcher: Final = hub_data_fetcher
        self._event_bus_provider: Final = event_bus_provider
        self._state_provider: Final = state_provider

        self._active = False
        self._devices_created = False
        self._scheduler_task: asyncio.Task[None] | None = None
        self._unsubscribe_callback: Callable[[], None] | None = None

        # Subscribe to DEVICES_CREATED event
        # Create a wrapper to match the EventHandler signature (positional event argument)
        def _event_handler(event: BackendSystemEventData) -> None:
            self._on_backend_system_event(event=event)

        self._unsubscribe_callback = self._event_bus_provider.event_bus.subscribe(
            event_type=BackendSystemEventData,
            handler=_event_handler,
        )

        # Define scheduled jobs
        self._scheduler_jobs: Final[list[SchedulerJob]] = [
            SchedulerJob(
                task=self._check_connection,
                run_interval=CONNECTION_CHECKER_INTERVAL,
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

    async def start(self) -> None:
        """Start the scheduler and begin running scheduled tasks."""
        if self._active:
            _LOGGER.warning("Scheduler for %s is already running", self._central_info.name)  # i18n-log: ignore
            return

        _LOGGER.debug("Starting scheduler for %s", self._central_info.name)
        self._active = True
        self._scheduler_task = asyncio.create_task(self._run_scheduler_loop())

    async def stop(self) -> None:
        """Stop the scheduler and cancel all running tasks."""
        if not self._active:
            return

        _LOGGER.debug("Stopping scheduler for %s", self._central_info.name)
        self._active = False

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
        """Check connection health to all clients and reconnect if necessary."""
        _LOGGER.debug("CHECK_CONNECTION: Checking connection to server %s", self._central_info.name)
        try:
            if not self._client_coordination.all_clients_active:
                _LOGGER.error(
                    i18n.tr(
                        "log.central.scheduler.check_connection.no_clients",
                        name=self._central_info.name,
                    )
                )
                await self._client_coordination.restart_clients()
            else:
                reconnects: list[Any] = []
                reloads: list[Any] = []
                for interface_id in self._client_coordination.interface_ids:
                    # Check: client available, connected, callback alive
                    client = self._client_coordination.get_client(interface_id=interface_id)
                    if client.available is False or not await client.is_connected() or not client.is_callback_alive():
                        reconnects.append(client.reconnect())
                        reloads.append(
                            self._client_coordination.load_and_refresh_data_point_data(interface=client.interface)
                        )
                if reconnects:
                    await asyncio.gather(*reconnects)
                    if self._central_info.available:
                        await asyncio.gather(*reloads)
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

    async def _fetch_device_firmware_update_data(self) -> None:
        """Periodically fetch device firmware update data from backend."""
        if (
            not self._config_provider.config.enable_device_firmware_check
            or not self._central_info.available
            or not self._devices_created
        ):
            return

        _LOGGER.debug(
            "FETCH_DEVICE_FIRMWARE_UPDATE_DATA: Scheduled fetching for %s",
            self._central_info.name,
        )
        await self._device_data_refresher.refresh_firmware_data()

    async def _fetch_device_firmware_update_data_in_delivery(self) -> None:
        """Fetch firmware update data for devices in delivery state."""

        if (
            not self._config_provider.config.enable_device_firmware_check
            or not self._central_info.available
            or not self._devices_created
        ):
            return

        _LOGGER.debug(
            "FETCH_DEVICE_FIRMWARE_UPDATE_DATA_IN_DELIVERY: For delivering devices for %s",
            self._central_info.name,
        )
        await self._device_data_refresher.refresh_firmware_data_by_state(
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
            or not self._devices_created
        ):
            return

        _LOGGER.debug(
            "FETCH_DEVICE_FIRMWARE_UPDATE_DATA_IN_UPDATE: For updating devices for %s",
            self._central_info.name,
        )
        await self._device_data_refresher.refresh_firmware_data_by_state(
            device_firmware_states=(
                DeviceFirmwareState.READY_FOR_UPDATE,
                DeviceFirmwareState.DO_UPDATE_PENDING,
                DeviceFirmwareState.PERFORMING_UPDATE,
            )
        )

    def _on_backend_system_event(self, *, event: BackendSystemEventData) -> None:
        """
        Handle backend system events.

        Args:
        ----
            event: BackendSystemEventData instance

        """
        if event.system_event == BackendSystemEvent.DEVICES_CREATED:
            self._devices_created = True

    async def _refresh_client_data(self) -> None:
        """Refresh client data for polled interfaces."""
        if not self._central_info.available:
            return

        if (poll_clients := self._client_coordination.poll_clients) is not None and len(poll_clients) > 0:
            _LOGGER.debug("REFRESH_CLIENT_DATA: Loading data for %s", self._central_info.name)
            for client in poll_clients:
                await self._client_coordination.load_and_refresh_data_point_data(interface=client.interface)
                self._client_coordination.set_last_event_seen_for_interface(interface_id=client.interface_id)

    async def _refresh_program_data(self) -> None:
        """Refresh system programs data."""
        if (
            not self._config_provider.config.enable_program_scan
            or not self._central_info.available
            or not self._devices_created
        ):
            return

        _LOGGER.debug("REFRESH_PROGRAM_DATA: For %s", self._central_info.name)
        await self._hub_data_fetcher.fetch_program_data(scheduled=True)

    async def _refresh_sysvar_data(self) -> None:
        """Refresh system variables data."""
        if (
            not self._config_provider.config.enable_sysvar_scan
            or not self._central_info.available
            or not self._devices_created
        ):
            return

        _LOGGER.debug("REFRESH_SYSVAR_DATA: For %s", self._central_info.name)
        await self._hub_data_fetcher.fetch_sysvar_data(scheduled=True)

    async def _run_scheduler_loop(self) -> None:
        """Execute the main scheduler loop that runs jobs based on their schedule."""

        while self._active:
            # Wait until central is running
            if self._state_provider.state != CentralUnitState.RUNNING:
                _LOGGER.debug("Scheduler: Waiting until central %s is started", self._central_info.name)
                await asyncio.sleep(SCHEDULER_NOT_STARTED_SLEEP)
                continue

            # Execute ready jobs
            any_executed = False
            for job in self._scheduler_jobs:
                if not self._active or not job.ready:
                    continue

                await job.run()
                job.schedule_next_execution()
                any_executed = True

            if not self._active:
                break  # type: ignore[unreachable]  # noqa: PLW0101

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
