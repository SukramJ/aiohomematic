# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Error-path and stress tests for resilience infrastructure.

This module covers gaps identified in the architecture review (#2):
- RequestCoalescer stress testing (burst, mixed failures, rapid reuse)
- Circuit breaker → recovery integration (event chain, deduplication)
- Central stop cleanup (cache, tracker, coordinator cleanup)
- CentralDataCache error paths (expiration, initialization, statistics)
"""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import TYPE_CHECKING, TypeAlias
from unittest.mock import MagicMock

import pytest

from aiohomematic.async_support import Looper
from aiohomematic.central.coordinators import ConnectionRecoveryCoordinator
from aiohomematic.central.events import CircuitBreakerTrippedEvent, ConnectionLostEvent, EventBus
from aiohomematic.client import CircuitBreaker, CircuitBreakerConfig, CircuitState, RequestCoalescer
from aiohomematic.const import INIT_DATETIME, NO_CACHE_ENTRY, Interface
from aiohomematic.store.dynamic import CentralDataCache
from aiohomematic_test_support.event_capture import EventCapture

if TYPE_CHECKING:
    from aiohomematic.central import CentralUnit

_AsyncStrFactory: TypeAlias = Callable[[], Awaitable[str]]


# ---------------------------------------------------------------------------
# Class 1: RequestCoalescer Stress Tests
# ---------------------------------------------------------------------------


class TestRequestCoalescerStress:
    """Stress tests for RequestCoalescer under concurrent load."""

    @pytest.mark.asyncio
    async def test_burst_mixed_success_and_failure(self) -> None:
        """Test 10 success + 10 failure tasks with different keys all resolve correctly."""
        coalescer = RequestCoalescer(name="stress-test")

        async def success_executor(idx: int) -> str:
            await asyncio.sleep(0.01)
            return f"ok-{idx}"

        async def failure_executor(idx: int) -> str:
            await asyncio.sleep(0.01)
            raise ValueError(f"fail-{idx}")

        def make_success(idx: int) -> _AsyncStrFactory:
            async def _exec() -> str:
                return await success_executor(idx)

            return _exec

        def make_failure(idx: int) -> _AsyncStrFactory:
            async def _exec() -> str:
                return await failure_executor(idx)

            return _exec

        success_tasks: list[asyncio.Task[str]] = [
            asyncio.create_task(coalescer.execute(key=f"ok-{i}", executor=make_success(i))) for i in range(10)
        ]
        failure_tasks: list[asyncio.Task[str]] = [
            asyncio.create_task(coalescer.execute(key=f"fail-{i}", executor=make_failure(i))) for i in range(10)
        ]

        success_results = await asyncio.gather(*success_tasks, return_exceptions=True)
        failure_results = await asyncio.gather(*failure_tasks, return_exceptions=True)

        # All success tasks should have string results
        for i, result in enumerate(success_results):
            assert result == f"ok-{i}", f"Success task {i} returned {result}"

        # All failure tasks should have ValueError
        for i, result in enumerate(failure_results):
            assert isinstance(result, ValueError), f"Failure task {i} returned {type(result)}"
            assert str(result) == f"fail-{i}"

        assert coalescer.pending_count == 0

    @pytest.mark.asyncio
    async def test_clear_during_active_requests(self) -> None:
        """Test clear() while keys have active executors."""
        coalescer = RequestCoalescer(name="stress-test")
        execution_started = asyncio.Event()

        async def slow_executor() -> str:
            execution_started.set()
            await asyncio.sleep(10)
            return "should-not-complete"

        # Start 5 requests with different keys
        tasks = []
        for i in range(5):
            execution_started.clear()
            task = asyncio.create_task(coalescer.execute(key=f"active-{i}", executor=slow_executor))
            if i == 0:
                await execution_started.wait()
            tasks.append(task)

        # Give time for tasks to register
        await asyncio.sleep(0.05)

        # Clear all pending
        coalescer.clear()
        assert coalescer.pending_count == 0

        # Cancel tasks to clean up
        for task in tasks:
            task.cancel()

        # Suppress CancelledError / KeyError from cleanup
        await asyncio.gather(*tasks, return_exceptions=True)

    @pytest.mark.asyncio
    async def test_concurrent_different_keys_no_interference(self) -> None:
        """Test 50 concurrent requests with unique keys all complete independently."""
        coalescer = RequestCoalescer(name="stress-test")

        async def executor(idx: int) -> str:
            await asyncio.sleep(0.01)
            return f"result-{idx}"

        def make_exec(idx: int) -> _AsyncStrFactory:
            async def _exec() -> str:
                return await executor(idx)

            return _exec

        tasks: list[asyncio.Task[str]] = [
            asyncio.create_task(coalescer.execute(key=f"unique-{i}", executor=make_exec(i))) for i in range(50)
        ]

        results = await asyncio.gather(*tasks)

        assert len(results) == 50
        for i, result in enumerate(results):
            assert result == f"result-{i}"

        assert coalescer.total_requests == 50
        assert coalescer.executed_requests == 50
        assert coalescer.pending_count == 0

    @pytest.mark.asyncio
    async def test_executor_returns_none(self) -> None:
        """Test coalescer handles None return value correctly for all waiters."""
        coalescer = RequestCoalescer(name="stress-test")
        execution_started = asyncio.Event()

        async def none_executor() -> None:
            execution_started.set()
            await asyncio.sleep(0.05)

        # Start first request
        task1 = asyncio.create_task(coalescer.execute(key="none-key", executor=none_executor))
        await execution_started.wait()

        # Add waiters
        task2 = asyncio.create_task(coalescer.execute(key="none-key", executor=none_executor))
        task3 = asyncio.create_task(coalescer.execute(key="none-key", executor=none_executor))

        results = await asyncio.gather(task1, task2, task3)

        assert list(results) == [None, None, None]
        assert coalescer.pending_count == 0

    @pytest.mark.asyncio
    async def test_many_waiters_on_failing_key(self) -> None:
        """Test 20 concurrent requests on same key where executor fails."""
        coalescer = RequestCoalescer(name="stress-test")
        execution_count = 0
        execution_started = asyncio.Event()

        async def failing_executor() -> str:
            nonlocal execution_count
            execution_count += 1
            execution_started.set()
            await asyncio.sleep(0.05)
            raise TimeoutError("backend timeout")

        # Start first request
        task1 = asyncio.create_task(coalescer.execute(key="shared-fail", executor=failing_executor))
        await execution_started.wait()

        # Add 19 more waiters
        tasks = [
            asyncio.create_task(coalescer.execute(key="shared-fail", executor=failing_executor)) for _ in range(19)
        ]

        results = await asyncio.gather(task1, *tasks, return_exceptions=True)

        # All 20 should get the same TimeoutError
        for result in results:
            assert isinstance(result, TimeoutError)
            assert str(result) == "backend timeout"

        # Only 1 execution should have happened
        assert execution_count == 1
        assert coalescer.pending_count == 0

    @pytest.mark.asyncio
    async def test_rapid_reuse_after_failure(self) -> None:
        """Test key can be reused immediately after failure completes."""
        coalescer = RequestCoalescer(name="stress-test")
        call_count = 0

        async def failing_executor() -> str:
            nonlocal call_count
            call_count += 1
            raise RuntimeError("temporary failure")

        async def success_executor() -> str:
            nonlocal call_count
            call_count += 1
            return "recovered"

        # First call fails
        with pytest.raises(RuntimeError, match="temporary failure"):
            await coalescer.execute(key="reuse-key", executor=failing_executor)

        # Immediately reuse the same key — should not be stuck
        result = await coalescer.execute(key="reuse-key", executor=success_executor)
        assert result == "recovered"
        assert call_count == 2
        assert coalescer.pending_count == 0


# ---------------------------------------------------------------------------
# Class 2: Circuit Breaker → Recovery Integration Tests
# ---------------------------------------------------------------------------


class TestCircuitBreakerRecoveryIntegration:
    """Tests for the event chain from circuit breaker trip to recovery coordinator."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_trip_emits_event(self, event_capture: EventCapture) -> None:
        """Test CircuitBreaker trip publishes CircuitBreakerTrippedEvent."""
        looper = Looper()
        event_bus = EventBus(task_scheduler=looper)
        event_capture.subscribe_to(event_bus, CircuitBreakerTrippedEvent)

        config = CircuitBreakerConfig(failure_threshold=2)
        breaker = CircuitBreaker(config=config, interface_id="test-iface", event_bus=event_bus, task_scheduler=looper)

        breaker.record_failure()
        breaker.record_failure()

        assert breaker.state == CircuitState.OPEN

        await asyncio.sleep(0.02)

        event_capture.assert_event_emitted(
            event_type=CircuitBreakerTrippedEvent,
            interface_id="test-iface",
            failure_count=2,
        )

    @pytest.mark.asyncio
    async def test_duplicate_connection_lost_events_deduplicated(self) -> None:
        """Test second ConnectionLostEvent for same interface_id is ignored when already recovering."""
        coordinator = self._create_coordinator()
        coordinator._active_recoveries.add("test-interface")

        event = ConnectionLostEvent(
            timestamp=datetime.now(),
            interface_id="test-interface",
            reason="Connection refused",
            detected_at=datetime.now(),
        )

        # Should not create a second recovery
        coordinator._on_connection_lost(event=event)

        await asyncio.sleep(0.02)

        # Still only one entry
        assert len(coordinator._active_recoveries) == 1
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_max_retries_triggers_failed_state(self) -> None:
        """Test _handle_max_retries_reached sets _in_failed_state=True."""
        coordinator = self._create_coordinator()

        assert coordinator._in_failed_state is False

        await coordinator._handle_max_retries_reached(interface_id="test-interface")

        assert coordinator._in_failed_state is True

        coordinator.stop()  # type: ignore[unreachable]

    @pytest.mark.asyncio
    async def test_shutdown_prevents_recovery_start(self) -> None:
        """Test after coordinator.stop(), ConnectionLostEvent does not trigger recovery."""
        coordinator = self._create_coordinator()
        coordinator.stop()

        assert coordinator._shutdown is True

        event = ConnectionLostEvent(
            timestamp=datetime.now(),
            interface_id="test-interface",
            reason="Connection refused",
            detected_at=datetime.now(),
        )

        coordinator._on_connection_lost(event=event)

        await asyncio.sleep(0.02)

        assert "test-interface" not in coordinator._active_recoveries

    def _create_coordinator(
        self,
        *,
        event_bus: EventBus | None = None,
    ) -> ConnectionRecoveryCoordinator:
        """Create a coordinator with mocked dependencies."""
        task_scheduler = Looper()
        if event_bus is None:
            event_bus = EventBus(task_scheduler=task_scheduler)

        central_info = MagicMock()
        central_info.name = "test-central"

        config_provider = MagicMock()
        config_provider.config.timeout_config.reconnect_initial_cooldown = 0.01
        config_provider.config.timeout_config.reconnect_warmup_delay = 0.01
        config_provider.config.timeout_config.reconnect_tcp_check_timeout = 0.1
        config_provider.config.host = "127.0.0.1"
        config_provider.config.tls = False

        client_provider = MagicMock()
        coordinator_provider = MagicMock()
        device_data_refresher = MagicMock()

        return ConnectionRecoveryCoordinator(
            central_info=central_info,
            config_provider=config_provider,
            client_provider=client_provider,
            coordinator_provider=coordinator_provider,
            device_data_refresher=device_data_refresher,
            event_bus=event_bus,
            task_scheduler=task_scheduler,
        )


# ---------------------------------------------------------------------------
# Class 3: Central Stop Cleanup Tests
# ---------------------------------------------------------------------------


class TestCentralStopCleanup:
    """Tests verifying resource cleanup after central.stop()."""

    @pytest.mark.asyncio
    async def test_cache_coordinator_stopped_after_stop(  # type: ignore[no-untyped-def]
        self, central_unit_pydevccu_mini
    ) -> None:
        """Test cache coordinator event subscriptions cleared after stop."""
        central: CentralUnit = central_unit_pydevccu_mini

        await central.stop()

        # Cache coordinator's unsubscribers should be cleared
        assert central.cache_coordinator._unsubscribers == []

    @pytest.mark.asyncio
    async def test_clear_all_clears_data_cache(  # type: ignore[no-untyped-def]
        self, central_unit_pydevccu_mini
    ) -> None:
        """Test clear_all clears the data cache."""
        central: CentralUnit = central_unit_pydevccu_mini

        # Data cache should have data after start
        # (central_unit_pydevccu_mini already started the central)
        initial_size = central.cache_coordinator.data_cache.size

        await central.stop()
        await central.cache_coordinator.clear_all()

        assert central.cache_coordinator.data_cache.size == 0
        # If there was data, we cleared something meaningful
        assert initial_size >= 0

    @pytest.mark.asyncio
    async def test_double_stop_is_safe(  # type: ignore[no-untyped-def]
        self, central_unit_pydevccu_mini
    ) -> None:
        """Test calling stop() twice does not raise."""
        central: CentralUnit = central_unit_pydevccu_mini

        await central.stop()
        await central.stop()  # Should not raise

    @pytest.mark.asyncio
    async def test_recovery_coordinator_stopped_after_stop(  # type: ignore[no-untyped-def]
        self, central_unit_pydevccu_mini
    ) -> None:
        """Test recovery coordinator is stopped after central stop."""
        central: CentralUnit = central_unit_pydevccu_mini

        # Before stop: recovery coordinator should be active
        assert central.connection_recovery_coordinator._shutdown is False
        assert len(central.connection_recovery_coordinator._unsubscribers) > 0

        await central.stop()

        assert central.connection_recovery_coordinator._shutdown is True
        assert central.connection_recovery_coordinator._unsubscribers == []  # type: ignore[unreachable]


# ---------------------------------------------------------------------------
# Class 4: CentralDataCache Error Paths
# ---------------------------------------------------------------------------


class TestCentralDataCacheErrorPaths:
    """Error-path tests for CentralDataCache."""

    def test_cache_expires_after_max_age(self) -> None:
        """Test backdating _refreshed_at causes expiration and eviction."""
        cache = self._create_cache()
        cache.set_initialization_complete()

        # Add data
        cache.add_data(
            interface=Interface.HMIP_RF,
            all_device_data={f"{Interface.HMIP_RF}.VCU001:1.STATE": True},
        )
        assert cache.size == 1

        # Backdate to INIT_DATETIME (1970-01-01) to force expiration
        cache._refreshed_at[Interface.HMIP_RF] = INIT_DATETIME

        # get_data should see expired cache, clear it, and return NO_CACHE_ENTRY
        result = cache.get_data(
            interface=Interface.HMIP_RF,
            channel_address="VCU001:1",
            parameter="STATE",
        )

        assert result == NO_CACHE_ENTRY
        assert cache.size == 0
        assert cache.statistics.evictions == 1

    def test_clear_specific_interface(self) -> None:
        """Test clear(interface=X) only clears X, other interfaces retain data."""
        cache = self._create_cache(interfaces=(Interface.HMIP_RF, Interface.BIDCOS_RF))
        cache.set_initialization_complete()

        cache.add_data(
            interface=Interface.HMIP_RF,
            all_device_data={f"{Interface.HMIP_RF}.VCU001:1.STATE": True},
        )
        cache.add_data(
            interface=Interface.BIDCOS_RF,
            all_device_data={f"{Interface.BIDCOS_RF}.MEQ001:1.STATE": False},
        )

        assert cache.size == 2

        # Clear only HMIP_RF
        cache.clear(interface=Interface.HMIP_RF)

        # HMIP_RF should be empty
        result_hmip = cache.get_data(
            interface=Interface.HMIP_RF,
            channel_address="VCU001:1",
            parameter="STATE",
        )
        assert result_hmip == NO_CACHE_ENTRY

        # BIDCOS_RF should still have data
        result_bidcos = cache.get_data(
            interface=Interface.BIDCOS_RF,
            channel_address="MEQ001:1",
            parameter="STATE",
        )
        assert result_bidcos is False

    def test_expiration_suppressed_during_initialization(self) -> None:
        """Test while _is_initializing=True, old data is still returned."""
        cache = self._create_cache()
        # _is_initializing is True by default

        key = f"{Interface.HMIP_RF}.VCU001:1.STATE"
        cache.add_data(
            interface=Interface.HMIP_RF,
            all_device_data={key: True},
        )

        # Backdate to INIT_DATETIME — would normally expire
        cache._refreshed_at[Interface.HMIP_RF] = INIT_DATETIME

        # During initialization, expiration is suppressed
        result = cache.get_data(
            interface=Interface.HMIP_RF,
            channel_address="VCU001:1",
            parameter="STATE",
        )

        assert result is True
        assert cache.statistics.hits == 1
        assert cache.statistics.evictions == 0

    def test_get_data_returns_no_cache_entry_for_empty_interface(self) -> None:
        """Test empty cache returns NO_CACHE_ENTRY and records miss."""
        cache = self._create_cache()

        result = cache.get_data(
            interface=Interface.HMIP_RF,
            channel_address="VCU001:1",
            parameter="STATE",
        )

        assert result == NO_CACHE_ENTRY
        assert cache.statistics.misses == 1
        assert cache.statistics.hits == 0

    def test_statistics_accuracy(self) -> None:
        """Test hits and misses tracked correctly across multiple operations."""
        cache = self._create_cache()
        cache.set_initialization_complete()

        key = f"{Interface.HMIP_RF}.VCU001:1.STATE"
        cache.add_data(
            interface=Interface.HMIP_RF,
            all_device_data={key: 42},
        )

        # 3 hits
        for _ in range(3):
            result = cache.get_data(
                interface=Interface.HMIP_RF,
                channel_address="VCU001:1",
                parameter="STATE",
            )
            assert result == 42

        # 2 misses (nonexistent parameter)
        for _ in range(2):
            result = cache.get_data(
                interface=Interface.HMIP_RF,
                channel_address="VCU001:1",
                parameter="NONEXISTENT",
            )
            assert result == NO_CACHE_ENTRY

        assert cache.statistics.hits == 3
        assert cache.statistics.misses == 2
        assert cache.statistics.total_lookups == 5
        assert cache.statistics.hit_rate == pytest.approx(60.0)

    def _create_cache(
        self,
        *,
        interfaces: tuple[Interface, ...] = (Interface.HMIP_RF,),
    ) -> CentralDataCache:
        """Create a CentralDataCache with mocked providers."""
        device_provider = MagicMock()
        device_provider.interfaces = list(interfaces)
        client_provider = MagicMock()
        data_point_provider = MagicMock()
        central_info = MagicMock()
        central_info.name = "test-central"

        return CentralDataCache(
            device_provider=device_provider,
            client_provider=client_provider,
            data_point_provider=data_point_provider,
            central_info=central_info,
        )
