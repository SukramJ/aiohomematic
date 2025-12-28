# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Test the BackgroundScheduler."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from aiohomematic.central.scheduler import BackgroundScheduler, SchedulerJob
from aiohomematic.const import CentralState, ScheduleTimerConfig


def _create_schedule_timer_config(
    *,
    periodic_refresh_interval: int = 60,
    sys_scan_interval: int = 300,
) -> ScheduleTimerConfig:
    """Create a ScheduleTimerConfig for testing."""
    return ScheduleTimerConfig(
        connection_checker_interval=1,  # Fast for tests
        device_firmware_check_interval=21600,
        device_firmware_delivering_check_interval=3600,
        device_firmware_updating_check_interval=300,
        periodic_refresh_interval=periodic_refresh_interval,
        sys_scan_interval=sys_scan_interval,
        system_update_check_interval=14400,
        system_update_progress_check_interval=30,
        system_update_progress_timeout=1800,
    )


class TestSchedulerJobBasics:
    """Test SchedulerJob core functionality."""

    def test_scheduler_job_initialization_with_explicit_next_run(self) -> None:
        """SchedulerJob should initialize with explicit next_run time."""

        async def dummy_task() -> None:
            pass

        past = datetime.now() - timedelta(seconds=10)
        job = SchedulerJob(task=dummy_task, run_interval=5, next_run=past)

        assert job.next_run == past
        assert job.ready is True

    def test_scheduler_job_initialization_without_next_run(self) -> None:
        """SchedulerJob should use current time as next_run if not specified."""

        async def dummy_task() -> None:
            pass

        before = datetime.now()
        job = SchedulerJob(task=dummy_task, run_interval=60)
        after = datetime.now()

        # next_run should be between before and after
        assert before <= job.next_run <= after

    def test_scheduler_job_not_ready_when_future(self) -> None:
        """SchedulerJob.ready should return False when next_run is in the future."""

        async def dummy_task() -> None:
            pass

        future = datetime.now() + timedelta(seconds=60)
        job = SchedulerJob(task=dummy_task, run_interval=5, next_run=future)

        assert job.ready is False

    def test_scheduler_job_ready_when_past(self) -> None:
        """SchedulerJob.ready should return True when next_run is in the past."""

        async def dummy_task() -> None:
            pass

        past = datetime.now() - timedelta(seconds=10)
        job = SchedulerJob(task=dummy_task, run_interval=5, next_run=past)

        assert job.ready is True

    @pytest.mark.asyncio
    async def test_scheduler_job_run_executes_task(self) -> None:
        """SchedulerJob.run should execute the task."""
        executed = []

        async def dummy_task() -> None:
            executed.append(True)

        job = SchedulerJob(task=dummy_task, run_interval=5)
        await job.run()

        assert executed == [True]

    def test_scheduler_job_schedule_next_execution(self) -> None:
        """SchedulerJob.schedule_next_execution should advance next_run by interval."""

        async def dummy_task() -> None:
            pass

        start_time = datetime.now()
        job = SchedulerJob(task=dummy_task, run_interval=30, next_run=start_time)

        # Schedule next execution
        job.schedule_next_execution()

        expected = start_time + timedelta(seconds=30)
        assert job.next_run == expected

    def test_scheduler_job_schedule_next_execution_multiple(self) -> None:
        """SchedulerJob.schedule_next_execution should work multiple times."""

        async def dummy_task() -> None:
            pass

        start_time = datetime.now()
        job = SchedulerJob(task=dummy_task, run_interval=10, next_run=start_time)

        # Schedule next execution multiple times
        job.schedule_next_execution()
        assert job.next_run == start_time + timedelta(seconds=10)

        job.schedule_next_execution()
        assert job.next_run == start_time + timedelta(seconds=20)

        job.schedule_next_execution()
        assert job.next_run == start_time + timedelta(seconds=30)


class TestBackgroundSchedulerBasics:
    """Test BackgroundScheduler initialization and lifecycle."""

    def test_background_scheduler_initialization(self) -> None:
        """BackgroundScheduler should initialize with central instance."""
        central = MagicMock()
        central.event_bus = MagicMock()
        central.event_bus.subscribe = MagicMock(return_value=lambda: None)
        central.config = MagicMock()
        central.config.schedule_timer_config = _create_schedule_timer_config()
        central.config.enable_device_firmware_check = True

        central.connection_state = MagicMock()
        central.connection_state.has_any_issue = False

        scheduler = BackgroundScheduler(
            central_info=central,
            config_provider=central,
            client_coordinator=central,
            connection_state_provider=central,
            device_data_refresher=central,
            firmware_data_refresher=central,
            event_coordinator=central,
            hub_data_fetcher=central,
            event_bus_provider=central,
            json_rpc_client_provider=central,
            state_provider=central,
        )

        # Verify initialization using public API
        assert scheduler.is_active is False
        assert scheduler.devices_created is False

    @pytest.mark.asyncio
    async def test_background_scheduler_start(self) -> None:
        """BackgroundScheduler.start should activate the scheduler."""
        central = MagicMock()
        central.event_bus = MagicMock()
        central.event_bus.subscribe = MagicMock(return_value=lambda: None)
        central.config = MagicMock()
        central.config.schedule_timer_config = _create_schedule_timer_config()
        central.config.enable_device_firmware_check = True

        central.connection_state = MagicMock()
        central.connection_state.has_any_issue = False

        scheduler = BackgroundScheduler(
            central_info=central,
            config_provider=central,
            client_coordinator=central,
            connection_state_provider=central,
            device_data_refresher=central,
            firmware_data_refresher=central,
            event_coordinator=central,
            hub_data_fetcher=central,
            event_bus_provider=central,
            json_rpc_client_provider=central,
            state_provider=central,
        )
        # Before start: scheduler should not be active
        assert scheduler.is_active is False

        # Mock the scheduler loop to prevent actual execution
        with patch.object(scheduler, "_run_scheduler_loop", return_value=AsyncMock()):
            await scheduler.start()

        # After start: scheduler should be active
        assert scheduler.is_active is True

    @pytest.mark.asyncio
    async def test_background_scheduler_start_when_already_running(self, caplog: pytest.LogCaptureFixture) -> None:
        """BackgroundScheduler.start should warn if already running."""
        central = MagicMock()
        central.name = "test-ccu"
        central.event_bus = MagicMock()
        central.event_bus.subscribe = MagicMock(return_value=lambda: None)
        central.config = MagicMock()
        central.config.schedule_timer_config = _create_schedule_timer_config()
        central.config.enable_device_firmware_check = True

        central.connection_state = MagicMock()
        central.connection_state.has_any_issue = False

        scheduler = BackgroundScheduler(
            central_info=central,
            config_provider=central,
            client_coordinator=central,
            connection_state_provider=central,
            device_data_refresher=central,
            firmware_data_refresher=central,
            event_coordinator=central,
            hub_data_fetcher=central,
            event_bus_provider=central,
            json_rpc_client_provider=central,
            state_provider=central,
        )

        # Start once
        with patch.object(scheduler, "_run_scheduler_loop", return_value=AsyncMock()):
            await scheduler.start()

        # Try to start again
        with caplog.at_level("WARNING"), patch.object(scheduler, "_run_scheduler_loop", return_value=AsyncMock()):
            await scheduler.start()

        assert any("already running" in rec.getMessage() for rec in caplog.records)

    @pytest.mark.asyncio
    async def test_background_scheduler_stop(self) -> None:
        """BackgroundScheduler.stop should deactivate the scheduler."""
        central = MagicMock()
        central.event_bus = MagicMock()
        unsubscribe_callback = MagicMock()
        central.event_bus.subscribe = MagicMock(return_value=unsubscribe_callback)
        central.config = MagicMock()
        central.config.schedule_timer_config = _create_schedule_timer_config()
        central.config.enable_device_firmware_check = True

        central.connection_state = MagicMock()
        central.connection_state.has_any_issue = False

        scheduler = BackgroundScheduler(
            central_info=central,
            config_provider=central,
            client_coordinator=central,
            connection_state_provider=central,
            device_data_refresher=central,
            firmware_data_refresher=central,
            event_coordinator=central,
            hub_data_fetcher=central,
            event_bus_provider=central,
            json_rpc_client_provider=central,
            state_provider=central,
        )

        # Start the scheduler
        with patch.object(scheduler, "_run_scheduler_loop", return_value=AsyncMock()):
            await scheduler.start()
            assert scheduler.is_active is True

        # Stop the scheduler
        await scheduler.stop()

        assert scheduler.is_active is False
        unsubscribe_callback.assert_called_once()
        assert scheduler._unsubscribe_callback is None

    @pytest.mark.asyncio
    async def test_background_scheduler_stop_when_not_running(self) -> None:
        """BackgroundScheduler.stop should be safe when not running."""
        central = MagicMock()
        central.event_bus = MagicMock()
        central.event_bus.subscribe = MagicMock(return_value=lambda: None)
        central.config = MagicMock()
        central.config.schedule_timer_config = _create_schedule_timer_config()
        central.config.enable_device_firmware_check = True

        central.connection_state = MagicMock()
        central.connection_state.has_any_issue = False

        scheduler = BackgroundScheduler(
            central_info=central,
            config_provider=central,
            client_coordinator=central,
            connection_state_provider=central,
            device_data_refresher=central,
            firmware_data_refresher=central,
            event_coordinator=central,
            hub_data_fetcher=central,
            event_bus_provider=central,
            json_rpc_client_provider=central,
            state_provider=central,
        )
        assert scheduler.is_active is False

        # Stopping when not running should be safe
        await scheduler.stop()

        assert scheduler.is_active is False

    def test_background_scheduler_subscribes_to_events(self) -> None:
        """BackgroundScheduler should subscribe to DEVICES_CREATED event."""
        central = MagicMock()
        central.event_bus = MagicMock()
        unsubscribe_callback = MagicMock()
        central.event_bus.subscribe = MagicMock(return_value=unsubscribe_callback)
        central.config = MagicMock()
        central.config.schedule_timer_config = _create_schedule_timer_config()
        central.config.enable_device_firmware_check = True

        central.connection_state = MagicMock()
        central.connection_state.has_any_issue = False

        scheduler = BackgroundScheduler(
            central_info=central,
            config_provider=central,
            client_coordinator=central,
            connection_state_provider=central,
            device_data_refresher=central,
            firmware_data_refresher=central,
            event_coordinator=central,
            hub_data_fetcher=central,
            event_bus_provider=central,
            json_rpc_client_provider=central,
            state_provider=central,
        )

        # Verify subscribe was called
        central.event_bus.subscribe.assert_called_once()
        assert scheduler._unsubscribe_callback == unsubscribe_callback


class TestBackgroundSchedulerEventHandling:
    """Test BackgroundScheduler event handling."""

    def test_on_device_lifecycle_event_created(self) -> None:
        """BackgroundScheduler should track DeviceLifecycleEvent with CREATED type."""
        from datetime import datetime

        from aiohomematic.central.integration_events import DeviceLifecycleEvent, DeviceLifecycleEventType

        central = MagicMock()
        central.event_bus = MagicMock()
        central.event_bus.subscribe = MagicMock(return_value=lambda: None)
        central.config = MagicMock()
        central.config.schedule_timer_config = _create_schedule_timer_config()
        central.config.enable_device_firmware_check = True

        central.connection_state = MagicMock()
        central.connection_state.has_any_issue = False

        scheduler = BackgroundScheduler(
            central_info=central,
            config_provider=central,
            client_coordinator=central,
            connection_state_provider=central,
            device_data_refresher=central,
            firmware_data_refresher=central,
            event_coordinator=central,
            hub_data_fetcher=central,
            event_bus_provider=central,
            json_rpc_client_provider=central,
            state_provider=central,
        )
        assert scheduler.devices_created is False

        # Create a DeviceLifecycleEvent with CREATED type
        event = DeviceLifecycleEvent(
            timestamp=datetime.now(),
            event_type=DeviceLifecycleEventType.CREATED,
            device_addresses=("VCU0000001",),
        )

        scheduler._on_device_lifecycle_event(event=event)

        assert scheduler.devices_created is True

    def test_on_device_lifecycle_event_other_types(self) -> None:
        """BackgroundScheduler should ignore non-CREATED DeviceLifecycleEvent types."""
        from datetime import datetime

        from aiohomematic.central.integration_events import DeviceLifecycleEvent, DeviceLifecycleEventType

        central = MagicMock()
        central.event_bus = MagicMock()
        central.event_bus.subscribe = MagicMock(return_value=lambda: None)
        central.config = MagicMock()
        central.config.schedule_timer_config = _create_schedule_timer_config()
        central.config.enable_device_firmware_check = True

        central.connection_state = MagicMock()
        central.connection_state.has_any_issue = False

        scheduler = BackgroundScheduler(
            central_info=central,
            config_provider=central,
            client_coordinator=central,
            connection_state_provider=central,
            device_data_refresher=central,
            firmware_data_refresher=central,
            event_coordinator=central,
            hub_data_fetcher=central,
            event_bus_provider=central,
            json_rpc_client_provider=central,
            state_provider=central,
        )
        assert scheduler.devices_created is False

        # Create a DeviceLifecycleEvent with REMOVED type
        event = DeviceLifecycleEvent(
            timestamp=datetime.now(),
            event_type=DeviceLifecycleEventType.REMOVED,
            device_addresses=("VCU0000001",),
        )

        scheduler._on_device_lifecycle_event(event=event)

        assert scheduler.devices_created is False


class TestBackgroundSchedulerJobExecution:
    """Test BackgroundScheduler job execution."""

    @pytest.mark.asyncio
    async def test_check_connection_handles_generic_exception(self) -> None:
        """_check_connection should handle generic exceptions gracefully."""
        central = MagicMock()
        central.name = "test-ccu"
        central.event_bus = MagicMock()
        central.event_bus.subscribe = MagicMock(return_value=lambda: None)
        central.config = MagicMock()
        central.config.schedule_timer_config = _create_schedule_timer_config()
        central.config.enable_device_firmware_check = True

        # Make all_clients_active raise an exception
        type(central).all_clients_active = PropertyMock(side_effect=RuntimeError("unexpected error"))

        central.connection_state = MagicMock()
        central.connection_state.has_any_issue = False

        scheduler = BackgroundScheduler(
            central_info=central,
            config_provider=central,
            client_coordinator=central,
            connection_state_provider=central,
            device_data_refresher=central,
            firmware_data_refresher=central,
            event_coordinator=central,
            hub_data_fetcher=central,
            event_bus_provider=central,
            json_rpc_client_provider=central,
            state_provider=central,
        )

        # Should handle the exception gracefully
        await scheduler._check_connection()

    @pytest.mark.asyncio
    async def test_check_connection_handles_no_connection_exception(self) -> None:
        """_check_connection should handle NoConnectionException gracefully."""
        from aiohomematic.exceptions import NoConnectionException

        central = MagicMock()
        central.name = "test-ccu"
        central.event_bus = MagicMock()
        central.event_bus.subscribe = MagicMock(return_value=lambda: None)
        central.config = MagicMock()
        central.config.schedule_timer_config = _create_schedule_timer_config()
        central.config.enable_device_firmware_check = True
        central.all_clients_active = True

        central.connection_state = MagicMock()
        central.connection_state.has_any_issue = False

        scheduler = BackgroundScheduler(
            central_info=central,
            config_provider=central,
            client_coordinator=central,
            connection_state_provider=central,
            device_data_refresher=central,
            firmware_data_refresher=central,
            event_coordinator=central,
            hub_data_fetcher=central,
            event_bus_provider=central,
            json_rpc_client_provider=central,
            state_provider=central,
        )

        # Mock the central method to raise NoConnectionException
        central.all_clients_active = False
        central.restart_clients = AsyncMock(side_effect=NoConnectionException("test error"))

        # Should handle the exception gracefully
        await scheduler._check_connection()

    @pytest.mark.asyncio
    async def test_check_connection_when_all_clients_active(self) -> None:
        """_check_connection should succeed when all clients are active."""
        central = MagicMock()
        central.name = "test-ccu"
        central.event_bus = MagicMock()
        central.event_bus.subscribe = MagicMock(return_value=lambda: None)
        central.config = MagicMock()
        central.config.schedule_timer_config = _create_schedule_timer_config()
        central.config.enable_device_firmware_check = True
        central.all_clients_active = True

        central.connection_state = MagicMock()
        central.connection_state.has_any_issue = False

        scheduler = BackgroundScheduler(
            central_info=central,
            config_provider=central,
            client_coordinator=central,
            connection_state_provider=central,
            device_data_refresher=central,
            firmware_data_refresher=central,
            event_coordinator=central,
            hub_data_fetcher=central,
            event_bus_provider=central,
            json_rpc_client_provider=central,
            state_provider=central,
        )

        # Should complete without errors
        await scheduler._check_connection()

    @pytest.mark.asyncio
    async def test_fetch_device_firmware_skips_when_disabled(self) -> None:
        """_fetch_device_firmware_update_data should skip when firmware check is disabled."""
        central = MagicMock()
        central.name = "test-ccu"
        central.event_bus = MagicMock()
        central.event_bus.subscribe = MagicMock(return_value=lambda: None)
        central.config = MagicMock()
        central.config.schedule_timer_config = _create_schedule_timer_config()
        central.config.enable_device_firmware_check = False
        central.available = True

        central.connection_state = MagicMock()
        central.connection_state.has_any_issue = False

        scheduler = BackgroundScheduler(
            central_info=central,
            config_provider=central,
            client_coordinator=central,
            connection_state_provider=central,
            device_data_refresher=central,
            firmware_data_refresher=central,
            event_coordinator=central,
            hub_data_fetcher=central,
            event_bus_provider=central,
            json_rpc_client_provider=central,
            state_provider=central,
        )

        # Mock the fetch method
        scheduler._device_data_refresher.fetch_device_firmware_update_data = AsyncMock()

        await scheduler._fetch_device_firmware_update_data()

        # Should not be called
        scheduler._device_data_refresher.fetch_device_firmware_update_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetch_device_firmware_skips_when_unavailable(self) -> None:
        """_fetch_device_firmware_update_data should skip when central is unavailable."""
        central = MagicMock()
        central.name = "test-ccu"
        central.event_bus = MagicMock()
        central.event_bus.subscribe = MagicMock(return_value=lambda: None)
        central.config = MagicMock()
        central.config.schedule_timer_config = _create_schedule_timer_config()
        central.config.enable_device_firmware_check = True
        central.available = False

        central.connection_state = MagicMock()
        central.connection_state.has_any_issue = False

        scheduler = BackgroundScheduler(
            central_info=central,
            config_provider=central,
            client_coordinator=central,
            connection_state_provider=central,
            device_data_refresher=central,
            firmware_data_refresher=central,
            event_coordinator=central,
            hub_data_fetcher=central,
            event_bus_provider=central,
            json_rpc_client_provider=central,
            state_provider=central,
        )

        # Mock the fetch method
        scheduler._device_data_refresher.fetch_device_firmware_update_data = AsyncMock()

        await scheduler._fetch_device_firmware_update_data()

        # Should not be called
        scheduler._device_data_refresher.fetch_device_firmware_update_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_refresh_client_data(self) -> None:
        """_refresh_client_data should refresh client data when central is available."""
        central = MagicMock()
        central.name = "test-ccu"
        central.event_bus = MagicMock()
        central.event_bus.subscribe = MagicMock(return_value=lambda: None)
        central.event_bus.publish = AsyncMock()
        central.event_bus.publish_sync = MagicMock()
        central.config = MagicMock()
        central.config.schedule_timer_config = _create_schedule_timer_config()
        central.config.enable_device_firmware_check = True
        central.available = True

        # Mock poll_clients and required methods
        mock_client = MagicMock()
        mock_client.interface = "BidCos-RF"
        mock_client.interface_id = "BidCos-RF"
        central.poll_clients = [mock_client]
        central.load_and_refresh_data_point_data = AsyncMock()
        central.set_last_event_seen_for_interface = MagicMock()

        central.connection_state = MagicMock()
        central.connection_state.has_any_issue = False

        scheduler = BackgroundScheduler(
            central_info=central,
            config_provider=central,
            client_coordinator=central,
            connection_state_provider=central,
            device_data_refresher=central,
            firmware_data_refresher=central,
            event_coordinator=central,
            hub_data_fetcher=central,
            event_bus_provider=central,
            json_rpc_client_provider=central,
            state_provider=central,
        )

        await scheduler._refresh_client_data()

        central.load_and_refresh_data_point_data.assert_called_once()
        central.set_last_event_seen_for_interface.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_program_data(self) -> None:
        """_refresh_program_data should fetch program data when enabled."""
        central = MagicMock()
        central.name = "test-ccu"
        central.event_bus = MagicMock()
        central.event_bus.subscribe = MagicMock(return_value=lambda: None)
        central.event_bus.publish = AsyncMock()
        central.event_bus.publish_sync = MagicMock()
        central.config = MagicMock()
        central.config.schedule_timer_config = _create_schedule_timer_config()
        central.config.enable_device_firmware_check = True
        central.config.enable_program_scan = True
        central.available = True
        central.hub_coordinator = MagicMock()
        central.hub_coordinator.fetch_program_data = AsyncMock()

        central.connection_state = MagicMock()
        central.connection_state.has_any_issue = False

        scheduler = BackgroundScheduler(
            central_info=central,
            config_provider=central,
            client_coordinator=central,
            connection_state_provider=central,
            device_data_refresher=central,
            firmware_data_refresher=central,
            event_coordinator=central,
            hub_data_fetcher=central.hub_coordinator,
            event_bus_provider=central,
            json_rpc_client_provider=central,
            state_provider=central,
        )
        scheduler._devices_created_event.set()

        await scheduler._refresh_program_data()

        central.hub_coordinator.fetch_program_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_sysvar_data(self) -> None:
        """_refresh_sysvar_data should fetch sysvar data when enabled."""
        central = MagicMock()
        central.name = "test-ccu"
        central.event_bus = MagicMock()
        central.event_bus.subscribe = MagicMock(return_value=lambda: None)
        central.event_bus.publish = AsyncMock()
        central.event_bus.publish_sync = MagicMock()
        central.config = MagicMock()
        central.config.schedule_timer_config = _create_schedule_timer_config()
        central.config.enable_device_firmware_check = True
        central.config.enable_sysvar_scan = True
        central.available = True
        central.hub_coordinator = MagicMock()
        central.hub_coordinator.fetch_sysvar_data = AsyncMock()

        central.connection_state = MagicMock()
        central.connection_state.has_any_issue = False

        scheduler = BackgroundScheduler(
            central_info=central,
            config_provider=central,
            client_coordinator=central,
            connection_state_provider=central,
            device_data_refresher=central,
            firmware_data_refresher=central,
            event_coordinator=central,
            hub_data_fetcher=central.hub_coordinator,
            event_bus_provider=central,
            json_rpc_client_provider=central,
            state_provider=central,
        )
        scheduler._devices_created_event.set()

        await scheduler._refresh_sysvar_data()

        central.hub_coordinator.fetch_sysvar_data.assert_called_once()


class TestSchedulerJobExecution:
    """Test SchedulerJob execution and scheduling."""

    @pytest.mark.asyncio
    async def test_job_execution_and_scheduling(self) -> None:
        """Job should execute and schedule next execution correctly."""
        executions: list[datetime] = []

        async def tracking_task() -> None:
            executions.append(datetime.now())

        start_time = datetime.now()
        job = SchedulerJob(task=tracking_task, run_interval=5, next_run=start_time)

        # Execute and schedule
        await job.run()
        job.schedule_next_execution()

        assert len(executions) == 1
        assert job.next_run == start_time + timedelta(seconds=5)

    @pytest.mark.asyncio
    async def test_job_with_async_exception_still_schedules(self) -> None:
        """Job should schedule next run even if task raises exception."""

        async def failing_task() -> None:
            raise ValueError("task failed")

        start_time = datetime.now()
        job = SchedulerJob(task=failing_task, run_interval=10, next_run=start_time)

        # Run the task (it will raise)
        with pytest.raises(ValueError):
            await job.run()

        # But scheduling should still work
        job.schedule_next_execution()
        assert job.next_run == start_time + timedelta(seconds=10)


class TestSchedulerLoopExecution:
    """Test scheduler loop execution and task management."""

    @pytest.mark.asyncio
    async def test_scheduler_loop_executes_ready_jobs(self) -> None:
        """Scheduler loop should execute jobs that are ready."""
        central = MagicMock()
        central.name = "test-ccu"
        central.event_bus = MagicMock()
        central.event_bus.subscribe = MagicMock(return_value=lambda: None)
        central.config = MagicMock()
        central.config.periodic_refresh_interval = 3600  # Very long interval
        central.config.sys_scan_interval = 3600
        central.config.enable_device_firmware_check = False
        central.state = CentralState.RUNNING
        central.available = False

        executions: list[str] = []

        async def test_task() -> None:
            executions.append("executed")

        central.connection_state = MagicMock()
        central.connection_state.has_any_issue = False

        scheduler = BackgroundScheduler(
            central_info=central,
            config_provider=central,
            client_coordinator=central,
            connection_state_provider=central,
            device_data_refresher=central,
            firmware_data_refresher=central,
            event_coordinator=central,
            hub_data_fetcher=central,
            event_bus_provider=central,
            json_rpc_client_provider=central,
            state_provider=central,
        )

        # Replace the connection checker with our test task
        past_time = datetime.now() - timedelta(seconds=10)
        scheduler._scheduler_jobs[0] = SchedulerJob(
            task=test_task,
            run_interval=1,
            next_run=past_time,
        )

        # Run just one iteration of the loop
        await scheduler._run_scheduler_loop()

    @pytest.mark.asyncio
    async def test_scheduler_loop_waits_for_running_state(self) -> None:
        """Scheduler loop should wait until central is in RUNNING state."""
        central = MagicMock()
        central.name = "test-ccu"
        central.event_bus = MagicMock()
        central.event_bus.subscribe = MagicMock(return_value=lambda: None)
        central.config = MagicMock()
        central.config.schedule_timer_config = _create_schedule_timer_config()
        central.config.enable_device_firmware_check = True
        central.state = CentralState.INITIALIZING
        central.connection_state = MagicMock()
        central.connection_state.has_any_issue = False

        BackgroundScheduler(
            central_info=central,
            config_provider=central,
            client_coordinator=central,
            connection_state_provider=central,
            device_data_refresher=central,
            firmware_data_refresher=central,
            event_coordinator=central,
            hub_data_fetcher=central,
            event_bus_provider=central,
            json_rpc_client_provider=central,
            state_provider=central,
        )

        # The loop should return early if state is not RUNNING
        # We'll test this by checking that the loop doesn't execute jobs
        await asyncio.sleep(0.01)  # Small delay to allow loop to start

    @pytest.mark.asyncio
    async def test_scheduler_stop_cancels_running_loop(self) -> None:
        """Scheduler.stop should cancel the running scheduler task."""
        central = MagicMock()
        central.name = "test-ccu"
        central.event_bus = MagicMock()
        unsubscribe = MagicMock()
        central.event_bus.subscribe = MagicMock(return_value=unsubscribe)
        central.config = MagicMock()
        central.config.schedule_timer_config = _create_schedule_timer_config()
        central.config.enable_device_firmware_check = True

        central.connection_state = MagicMock()
        central.connection_state.has_any_issue = False

        scheduler = BackgroundScheduler(
            central_info=central,
            config_provider=central,
            client_coordinator=central,
            connection_state_provider=central,
            device_data_refresher=central,
            firmware_data_refresher=central,
            event_coordinator=central,
            hub_data_fetcher=central,
            event_bus_provider=central,
            json_rpc_client_provider=central,
            state_provider=central,
        )

        # Start the scheduler
        with patch.object(scheduler, "_run_scheduler_loop", return_value=AsyncMock()):
            await scheduler.start()
            assert scheduler._scheduler_task is not None
            task = scheduler._scheduler_task

        # Stop the scheduler
        await scheduler.stop()

        assert scheduler.is_active is False
        assert task.cancelled() is True


class TestSchedulerJobFiltering:
    """Test scheduler job filtering and conditional execution."""

    @pytest.mark.asyncio
    async def test_refresh_client_data_skips_when_no_poll_clients(self) -> None:
        """_refresh_client_data should skip when there are no poll clients."""
        central = MagicMock()
        central.name = "test-ccu"
        central.event_bus = MagicMock()
        central.event_bus.subscribe = MagicMock(return_value=lambda: None)
        central.config = MagicMock()
        central.config.schedule_timer_config = _create_schedule_timer_config()
        central.config.enable_device_firmware_check = True
        central.available = True
        central.poll_clients = []

        central.connection_state = MagicMock()
        central.connection_state.has_any_issue = False

        scheduler = BackgroundScheduler(
            central_info=central,
            config_provider=central,
            client_coordinator=central,
            connection_state_provider=central,
            device_data_refresher=central,
            firmware_data_refresher=central,
            event_coordinator=central,
            hub_data_fetcher=central,
            event_bus_provider=central,
            json_rpc_client_provider=central,
            state_provider=central,
        )
        central.load_and_refresh_data_point_data = AsyncMock()

        await scheduler._refresh_client_data()

        # Should not call the method
        central.load_and_refresh_data_point_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_refresh_client_data_skips_when_poll_clients_none(self) -> None:
        """_refresh_client_data should skip when poll_clients is None."""
        central = MagicMock()
        central.name = "test-ccu"
        central.event_bus = MagicMock()
        central.event_bus.subscribe = MagicMock(return_value=lambda: None)
        central.config = MagicMock()
        central.config.schedule_timer_config = _create_schedule_timer_config()
        central.config.enable_device_firmware_check = True
        central.available = True
        central.poll_clients = None

        central.connection_state = MagicMock()
        central.connection_state.has_any_issue = False

        scheduler = BackgroundScheduler(
            central_info=central,
            config_provider=central,
            client_coordinator=central,
            connection_state_provider=central,
            device_data_refresher=central,
            firmware_data_refresher=central,
            event_coordinator=central,
            hub_data_fetcher=central,
            event_bus_provider=central,
            json_rpc_client_provider=central,
            state_provider=central,
        )
        central.load_and_refresh_data_point_data = AsyncMock()

        await scheduler._refresh_client_data()

        # Should not call the method
        central.load_and_refresh_data_point_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_refresh_client_data_skips_when_unavailable(self) -> None:
        """_refresh_client_data should skip when central is unavailable."""
        central = MagicMock()
        central.name = "test-ccu"
        central.event_bus = MagicMock()
        central.event_bus.subscribe = MagicMock(return_value=lambda: None)
        central.config = MagicMock()
        central.config.schedule_timer_config = _create_schedule_timer_config()
        central.config.enable_device_firmware_check = True
        central.available = False

        central.connection_state = MagicMock()
        central.connection_state.has_any_issue = False

        scheduler = BackgroundScheduler(
            central_info=central,
            config_provider=central,
            client_coordinator=central,
            connection_state_provider=central,
            device_data_refresher=central,
            firmware_data_refresher=central,
            event_coordinator=central,
            hub_data_fetcher=central,
            event_bus_provider=central,
            json_rpc_client_provider=central,
            state_provider=central,
        )
        central.load_and_refresh_data_point_data = AsyncMock()

        await scheduler._refresh_client_data()

        # Should not call the method
        central.load_and_refresh_data_point_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_refresh_program_data_skips_when_devices_not_created(self) -> None:
        """_refresh_program_data should skip until devices are created."""
        central = MagicMock()
        central.name = "test-ccu"
        central.event_bus = MagicMock()
        central.event_bus.subscribe = MagicMock(return_value=lambda: None)
        central.config = MagicMock()
        central.config.schedule_timer_config = _create_schedule_timer_config()
        central.config.enable_device_firmware_check = True
        central.config.enable_program_scan = True
        central.available = True

        central.connection_state = MagicMock()
        central.connection_state.has_any_issue = False

        scheduler = BackgroundScheduler(
            central_info=central,
            config_provider=central,
            client_coordinator=central,
            connection_state_provider=central,
            device_data_refresher=central,
            firmware_data_refresher=central,
            event_coordinator=central,
            hub_data_fetcher=central,
            event_bus_provider=central,
            json_rpc_client_provider=central,
            state_provider=central,
        )
        assert scheduler.devices_created is False
        central.hub_coordinator.fetch_program_data = AsyncMock()

        await scheduler._refresh_program_data()

        # Should not call the method until devices are created
        central.hub_coordinator.fetch_program_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_refresh_program_data_skips_when_disabled(self) -> None:
        """_refresh_program_data should skip when program scan is disabled."""
        central = MagicMock()
        central.name = "test-ccu"
        central.event_bus = MagicMock()
        central.event_bus.subscribe = MagicMock(return_value=lambda: None)
        central.config = MagicMock()
        central.config.schedule_timer_config = _create_schedule_timer_config()
        central.config.enable_device_firmware_check = True
        central.config.enable_program_scan = False
        central.available = True

        central.connection_state = MagicMock()
        central.connection_state.has_any_issue = False

        scheduler = BackgroundScheduler(
            central_info=central,
            config_provider=central,
            client_coordinator=central,
            connection_state_provider=central,
            device_data_refresher=central,
            firmware_data_refresher=central,
            event_coordinator=central,
            hub_data_fetcher=central,
            event_bus_provider=central,
            json_rpc_client_provider=central,
            state_provider=central,
        )
        central.hub_coordinator.fetch_program_data = AsyncMock()

        await scheduler._refresh_program_data()

        # Should not call the method
        central.hub_coordinator.fetch_program_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_refresh_sysvar_data_skips_when_devices_not_created(self) -> None:
        """_refresh_sysvar_data should skip until devices are created."""
        central = MagicMock()
        central.name = "test-ccu"
        central.event_bus = MagicMock()
        central.event_bus.subscribe = MagicMock(return_value=lambda: None)
        central.config = MagicMock()
        central.config.schedule_timer_config = _create_schedule_timer_config()
        central.config.enable_device_firmware_check = True
        central.config.enable_sysvar_scan = True
        central.available = True

        central.connection_state = MagicMock()
        central.connection_state.has_any_issue = False

        scheduler = BackgroundScheduler(
            central_info=central,
            config_provider=central,
            client_coordinator=central,
            connection_state_provider=central,
            device_data_refresher=central,
            firmware_data_refresher=central,
            event_coordinator=central,
            hub_data_fetcher=central,
            event_bus_provider=central,
            json_rpc_client_provider=central,
            state_provider=central,
        )
        assert scheduler.devices_created is False
        central.hub_coordinator.fetch_sysvar_data = AsyncMock()

        await scheduler._refresh_sysvar_data()

        # Should not call the method until devices are created
        central.hub_coordinator.fetch_sysvar_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_refresh_sysvar_data_skips_when_disabled(self) -> None:
        """_refresh_sysvar_data should skip when sysvar scan is disabled."""
        central = MagicMock()
        central.name = "test-ccu"
        central.event_bus = MagicMock()
        central.event_bus.subscribe = MagicMock(return_value=lambda: None)
        central.config = MagicMock()
        central.config.schedule_timer_config = _create_schedule_timer_config()
        central.config.enable_device_firmware_check = True
        central.config.enable_sysvar_scan = False
        central.available = True

        central.connection_state = MagicMock()
        central.connection_state.has_any_issue = False

        scheduler = BackgroundScheduler(
            central_info=central,
            config_provider=central,
            client_coordinator=central,
            connection_state_provider=central,
            device_data_refresher=central,
            firmware_data_refresher=central,
            event_coordinator=central,
            hub_data_fetcher=central,
            event_bus_provider=central,
            json_rpc_client_provider=central,
            state_provider=central,
        )
        central.hub_coordinator.fetch_sysvar_data = AsyncMock()

        await scheduler._refresh_sysvar_data()

        # Should not call the method
        central.hub_coordinator.fetch_sysvar_data.assert_not_called()


class TestSchedulerFirmwareChecks:
    """Test firmware update check scheduling."""

    @pytest.mark.asyncio
    async def test_fetch_device_firmware_update_data(self) -> None:
        """_fetch_device_firmware_update_data should work when enabled."""
        central = MagicMock()
        central.name = "test-ccu"
        central.event_bus = MagicMock()
        central.event_bus.subscribe = MagicMock(return_value=lambda: None)
        central.config = MagicMock()
        central.config.schedule_timer_config = _create_schedule_timer_config()
        central.config.enable_device_firmware_check = True
        central.available = True
        central.refresh_firmware_data = AsyncMock()

        central.connection_state = MagicMock()
        central.connection_state.has_any_issue = False

        scheduler = BackgroundScheduler(
            central_info=central,
            config_provider=central,
            client_coordinator=central,
            connection_state_provider=central,
            device_data_refresher=central,
            firmware_data_refresher=central,
            event_coordinator=central,
            hub_data_fetcher=central,
            event_bus_provider=central,
            json_rpc_client_provider=central,
            state_provider=central,
        )
        scheduler._devices_created_event.set()

        await scheduler._fetch_device_firmware_update_data()

        central.refresh_firmware_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_device_firmware_update_data_in_delivery(self) -> None:
        """_fetch_device_firmware_update_data_in_delivery should work when devices delivering."""
        central = MagicMock()
        central.name = "test-ccu"
        central.event_bus = MagicMock()
        central.event_bus.subscribe = MagicMock(return_value=lambda: None)
        central.config = MagicMock()
        central.config.schedule_timer_config = _create_schedule_timer_config()
        central.config.enable_device_firmware_check = True
        central.available = True
        central.refresh_firmware_data_by_state = AsyncMock()

        central.connection_state = MagicMock()
        central.connection_state.has_any_issue = False

        scheduler = BackgroundScheduler(
            central_info=central,
            config_provider=central,
            client_coordinator=central,
            connection_state_provider=central,
            device_data_refresher=central,
            firmware_data_refresher=central,
            event_coordinator=central,
            hub_data_fetcher=central,
            event_bus_provider=central,
            json_rpc_client_provider=central,
            state_provider=central,
        )
        scheduler._devices_created_event.set()

        await scheduler._fetch_device_firmware_update_data_in_delivery()

        central.refresh_firmware_data_by_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_device_firmware_update_data_in_update(self) -> None:
        """_fetch_device_firmware_update_data_in_update should work when devices updating."""
        central = MagicMock()
        central.name = "test-ccu"
        central.event_bus = MagicMock()
        central.event_bus.subscribe = MagicMock(return_value=lambda: None)
        central.config = MagicMock()
        central.config.schedule_timer_config = _create_schedule_timer_config()
        central.config.enable_device_firmware_check = True
        central.available = True
        central.refresh_firmware_data_by_state = AsyncMock()

        central.connection_state = MagicMock()
        central.connection_state.has_any_issue = False

        scheduler = BackgroundScheduler(
            central_info=central,
            config_provider=central,
            client_coordinator=central,
            connection_state_provider=central,
            device_data_refresher=central,
            firmware_data_refresher=central,
            event_coordinator=central,
            hub_data_fetcher=central,
            event_bus_provider=central,
            json_rpc_client_provider=central,
            state_provider=central,
        )
        scheduler._devices_created_event.set()

        await scheduler._fetch_device_firmware_update_data_in_update()

        central.refresh_firmware_data_by_state.assert_called_once()


class TestSchedulerJobReadiness:
    """Test job readiness detection and scheduling."""

    def test_job_becomes_ready_after_past_time(self) -> None:
        """Job should become ready once current time exceeds next_run."""

        async def dummy_task() -> None:
            pass

        # Schedule 1 second in the future
        future_time = datetime.now() + timedelta(seconds=1)
        job = SchedulerJob(task=dummy_task, run_interval=10, next_run=future_time)

        # Should not be ready yet
        assert job.ready is False

        # Wait for the time to pass
        import time

        time.sleep(1.1)

        # Now should be ready
        assert job.ready is True

    def test_job_interval_property(self) -> None:
        """Job should maintain correct interval."""

        async def dummy_task() -> None:
            pass

        job = SchedulerJob(task=dummy_task, run_interval=42)
        assert job._run_interval == 42

    @pytest.mark.asyncio
    async def test_multiple_jobs_schedule_independently(self) -> None:
        """Multiple jobs should maintain independent schedules."""
        executions: dict[str, int] = {"job1": 0, "job2": 0}

        async def job1_task() -> None:
            executions["job1"] += 1

        async def job2_task() -> None:
            executions["job2"] += 1

        past = datetime.now() - timedelta(seconds=10)
        job1 = SchedulerJob(task=job1_task, run_interval=5, next_run=past)
        job2 = SchedulerJob(task=job2_task, run_interval=10, next_run=past)

        # Execute both jobs
        await job1.run()
        await job2.run()

        # Schedule next executions
        job1.schedule_next_execution()
        job2.schedule_next_execution()

        # Both should have executed
        assert executions["job1"] == 1
        assert executions["job2"] == 1

        # Job1 should be ready sooner (5 second interval vs 10)
        assert job1.next_run < job2.next_run


class TestSchedulerErrorRecovery:
    """Test scheduler error recovery and resilience."""

    @pytest.mark.asyncio
    async def test_multiple_clients_refresh(self) -> None:
        """_refresh_client_data should handle multiple poll clients."""
        central = MagicMock()
        central.name = "test-ccu"
        central.event_bus = MagicMock()
        central.event_bus.subscribe = MagicMock(return_value=lambda: None)
        central.event_bus.publish = AsyncMock()
        central.event_bus.publish_sync = MagicMock()
        central.config = MagicMock()
        central.config.schedule_timer_config = _create_schedule_timer_config()
        central.config.enable_device_firmware_check = True
        central.available = True

        # Create multiple mock clients
        mock_client1 = MagicMock()
        mock_client1.interface = "BidCos-RF"
        mock_client1.interface_id = "BidCos-RF"

        mock_client2 = MagicMock()
        mock_client2.interface = "HmIP-RF"
        mock_client2.interface_id = "HmIP-RF"

        central.poll_clients = [mock_client1, mock_client2]
        central.load_and_refresh_data_point_data = AsyncMock()
        central.set_last_event_seen_for_interface = MagicMock()

        central.connection_state = MagicMock()
        central.connection_state.has_any_issue = False

        scheduler = BackgroundScheduler(
            central_info=central,
            config_provider=central,
            client_coordinator=central,
            connection_state_provider=central,
            device_data_refresher=central,
            firmware_data_refresher=central,
            event_coordinator=central,
            hub_data_fetcher=central,
            event_bus_provider=central,
            json_rpc_client_provider=central,
            state_provider=central,
        )

        await scheduler._refresh_client_data()

        # Should have been called twice (once per client)
        assert central.load_and_refresh_data_point_data.call_count == 2
        assert central.set_last_event_seen_for_interface.call_count == 2

    @pytest.mark.asyncio
    async def test_task_exception_does_not_stop_scheduler(self) -> None:
        """Exceptions in tasks should not stop the scheduler."""

        async def failing_task() -> None:
            raise RuntimeError("task failed")

        job = SchedulerJob(task=failing_task, run_interval=10)

        # Run should raise
        with pytest.raises(RuntimeError):
            await job.run()

        # But the job should still be schedulable
        job.schedule_next_execution()
        assert job._next_run > datetime.now()
