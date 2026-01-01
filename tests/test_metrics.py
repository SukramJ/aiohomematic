# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for the metrics aggregation system."""

from __future__ import annotations

from datetime import datetime

import pytest

from aiohomematic.central.events import EventBus, HandlerStats
from aiohomematic.metrics import (
    CacheMetrics,
    CacheStats,
    EventMetrics,
    HealthMetrics,
    LatencyStats,
    MetricsSnapshot,
    ModelMetrics,
    RecoveryMetrics,
    RpcMetrics,
    SizeOnlyStats,
)


class TestLatencyStats:
    """Tests for LatencyStats dataclass."""

    def test_initial_state(self) -> None:
        """Test initial state of LatencyStats."""
        stats = LatencyStats()
        assert stats.count == 0
        assert stats.total_ms == 0.0
        assert stats.max_ms == 0.0
        assert stats.avg_ms == 0.0

    def test_record_multiple_samples(self) -> None:
        """Test recording multiple latency samples."""
        stats = LatencyStats()
        stats.record(duration_ms=50.0)
        stats.record(duration_ms=100.0)
        stats.record(duration_ms=150.0)

        assert stats.count == 3
        assert stats.total_ms == 300.0
        assert stats.min_ms == 50.0
        assert stats.max_ms == 150.0
        assert stats.avg_ms == 100.0

    def test_record_single_sample(self) -> None:
        """Test recording a single latency sample."""
        stats = LatencyStats()
        stats.record(duration_ms=100.0)

        assert stats.count == 1
        assert stats.total_ms == 100.0
        assert stats.min_ms == 100.0
        assert stats.max_ms == 100.0
        assert stats.avg_ms == 100.0

    def test_reset(self) -> None:
        """Test resetting latency statistics."""
        stats = LatencyStats()
        stats.record(duration_ms=100.0)
        stats.reset()

        assert stats.count == 0
        assert stats.total_ms == 0.0
        assert stats.max_ms == 0.0


class TestHandlerStats:
    """Tests for HandlerStats dataclass."""

    def test_avg_duration_with_executions(self) -> None:
        """Test average duration calculation."""
        stats = HandlerStats()
        stats.total_executions = 4
        stats.total_duration_ms = 200.0

        assert stats.avg_duration_ms == 50.0

    def test_avg_duration_zero_executions(self) -> None:
        """Test average duration with zero executions."""
        stats = HandlerStats()
        assert stats.avg_duration_ms == 0.0

    def test_initial_state(self) -> None:
        """Test initial state of HandlerStats."""
        stats = HandlerStats()
        assert stats.total_executions == 0
        assert stats.total_errors == 0
        assert stats.total_duration_ms == 0.0
        assert stats.max_duration_ms == 0.0
        assert stats.avg_duration_ms == 0.0

    def test_reset(self) -> None:
        """Test resetting handler statistics."""
        stats = HandlerStats()
        stats.total_executions = 10
        stats.total_errors = 2
        stats.total_duration_ms = 500.0
        stats.max_duration_ms = 100.0

        stats.reset()

        assert stats.total_executions == 0
        assert stats.total_errors == 0
        assert stats.total_duration_ms == 0.0
        assert stats.max_duration_ms == 0.0


class TestRpcMetrics:
    """Tests for RpcMetrics dataclass."""

    def test_coalesce_rate(self) -> None:
        """Test coalesce rate calculation."""
        metrics = RpcMetrics(total_requests=100, coalesced_requests=30)
        assert metrics.coalesce_rate == 30.0

    def test_failure_rate(self) -> None:
        """Test failure rate calculation."""
        metrics = RpcMetrics(total_requests=100, failed_requests=20)
        assert metrics.failure_rate == 20.0

    def test_rejection_rate(self) -> None:
        """Test rejection rate calculation."""
        metrics = RpcMetrics(total_requests=100, rejected_requests=10)
        assert metrics.rejection_rate == 10.0

    def test_success_rate_with_requests(self) -> None:
        """Test success rate calculation."""
        metrics = RpcMetrics(total_requests=100, successful_requests=80)
        assert metrics.success_rate == 80.0

    def test_success_rate_zero_requests(self) -> None:
        """Test success rate with zero requests."""
        metrics = RpcMetrics()
        assert metrics.success_rate == 100.0


class TestCacheStats:
    """Tests for CacheStats dataclass."""

    def test_hit_rate_with_accesses(self) -> None:
        """Test hit rate calculation."""
        stats = CacheStats(hits=80, misses=20)
        assert stats.hit_rate == 80.0

    def test_hit_rate_zero_accesses(self) -> None:
        """Test hit rate with zero accesses."""
        stats = CacheStats()
        assert stats.hit_rate == 100.0


class TestCacheMetrics:
    """Tests for CacheMetrics dataclass."""

    def test_overall_hit_rate(self) -> None:
        """Test overall hit rate calculation (only true caches contribute)."""
        metrics = CacheMetrics(
            # Registries don't contribute to hit rate
            device_descriptions=SizeOnlyStats(size=100),
            paramset_descriptions=SizeOnlyStats(size=200),
            visibility_registry=SizeOnlyStats(size=50),
            ping_pong_tracker=SizeOnlyStats(size=10),
            # True caches contribute to hit rate
            data_cache=CacheStats(hits=80, misses=20),
            command_cache=CacheStats(hits=20, misses=0),
        )
        # Total: 100 hits, 20 misses = 83.33%
        assert abs(metrics.overall_hit_rate - 83.33) < 0.1

    def test_total_entries(self) -> None:
        """Test total entries calculation."""
        metrics = CacheMetrics(
            device_descriptions=SizeOnlyStats(size=10),
            paramset_descriptions=SizeOnlyStats(size=20),
            visibility_registry=SizeOnlyStats(size=15),
            ping_pong_tracker=SizeOnlyStats(size=2),
            data_cache=CacheStats(size=30),
            command_cache=CacheStats(size=5),
        )
        assert metrics.total_entries == 82


class TestHealthMetrics:
    """Tests for HealthMetrics dataclass."""

    def test_availability_rate(self) -> None:
        """Test availability rate calculation."""
        metrics = HealthMetrics(clients_total=10, clients_healthy=8)
        assert metrics.availability_rate == 80.0

    def test_availability_rate_zero_clients(self) -> None:
        """Test availability rate with zero clients."""
        metrics = HealthMetrics()
        assert metrics.availability_rate == 100.0


class TestRecoveryMetrics:
    """Tests for RecoveryMetrics dataclass."""

    def test_success_rate(self) -> None:
        """Test success rate calculation."""
        metrics = RecoveryMetrics(attempts_total=10, successes=8)
        assert metrics.success_rate == 80.0

    def test_success_rate_zero_attempts(self) -> None:
        """Test success rate with zero attempts."""
        metrics = RecoveryMetrics()
        assert metrics.success_rate == 100.0


class TestEventMetrics:
    """Tests for EventMetrics dataclass."""

    def test_error_rate(self) -> None:
        """Test error rate calculation."""
        metrics = EventMetrics(handlers_executed=100, handler_errors=5)
        assert metrics.error_rate == 5.0

    def test_error_rate_zero_executions(self) -> None:
        """Test error rate with zero executions."""
        metrics = EventMetrics()
        assert metrics.error_rate == 0.0

    def test_operational_counters_defaults(self) -> None:
        """Test that operational event counters have correct defaults."""
        metrics = EventMetrics()
        assert metrics.circuit_breaker_trips == 0
        assert metrics.state_changes == 0
        assert metrics.data_refreshes_triggered == 0
        assert metrics.data_refreshes_completed == 0
        assert metrics.programs_executed == 0
        assert metrics.requests_coalesced == 0

    def test_operational_counters_values(self) -> None:
        """Test that operational event counters can be set."""
        metrics = EventMetrics(
            circuit_breaker_trips=5,
            state_changes=10,
            data_refreshes_triggered=3,
            data_refreshes_completed=2,
            programs_executed=7,
            requests_coalesced=15,
        )
        assert metrics.circuit_breaker_trips == 5
        assert metrics.state_changes == 10
        assert metrics.data_refreshes_triggered == 3
        assert metrics.data_refreshes_completed == 2
        assert metrics.programs_executed == 7
        assert metrics.requests_coalesced == 15


class TestMetricsSnapshot:
    """Tests for MetricsSnapshot dataclass."""

    def test_default_values(self) -> None:
        """Test default values of MetricsSnapshot."""
        snapshot = MetricsSnapshot()
        assert isinstance(snapshot.timestamp, datetime)
        assert isinstance(snapshot.rpc, RpcMetrics)
        assert isinstance(snapshot.events, EventMetrics)
        assert isinstance(snapshot.cache, CacheMetrics)
        assert isinstance(snapshot.health, HealthMetrics)
        assert isinstance(snapshot.recovery, RecoveryMetrics)
        assert isinstance(snapshot.model, ModelMetrics)


class TestEventBusHandlerStats:
    """Tests for EventBus handler statistics integration."""

    def test_clear_event_stats_resets_handler_stats(self) -> None:
        """Test that clear_event_stats resets handler stats."""
        bus = EventBus()
        bus._handler_stats.total_executions = 10
        bus._handler_stats.total_errors = 2

        bus.clear_event_stats()

        stats = bus.get_handler_stats()
        assert stats.total_executions == 0
        assert stats.total_errors == 0

    @pytest.mark.asyncio
    async def test_handler_error_tracking(self) -> None:
        """Test that handler errors are tracked."""
        from aiohomematic.central.events import DeviceStateChangedEvent

        bus = EventBus()

        async def failing_handler(*, event: DeviceStateChangedEvent) -> None:
            raise ValueError("Test error")

        bus.subscribe(
            event_type=DeviceStateChangedEvent,
            event_key=None,
            handler=failing_handler,
        )

        event = DeviceStateChangedEvent(timestamp=datetime.now(), device_address="VCU001")
        await bus.publish(event=event)

        stats = bus.get_handler_stats()
        assert stats.total_executions == 1
        assert stats.total_errors == 1

    @pytest.mark.asyncio
    async def test_handler_stats_tracking(self) -> None:
        """Test that handler stats are tracked during event publishing."""
        from aiohomematic.central.events import DeviceStateChangedEvent

        bus = EventBus()

        async def dummy_handler(*, event: DeviceStateChangedEvent) -> None:
            pass

        bus.subscribe(
            event_type=DeviceStateChangedEvent,
            event_key=None,
            handler=dummy_handler,
        )

        event = DeviceStateChangedEvent(timestamp=datetime.now(), device_address="VCU001")
        await bus.publish(event=event)

        stats = bus.get_handler_stats()
        assert stats.total_executions == 1
        assert stats.total_errors == 0
        assert stats.total_duration_ms > 0


class TestServiceStats:
    """Tests for ServiceStats dataclass."""

    def test_initial_state(self) -> None:
        """Test initial state of ServiceStats."""
        from aiohomematic.metrics import ServiceStats

        stats = ServiceStats()
        assert stats.call_count == 0
        assert stats.error_count == 0
        assert stats.total_duration_ms == 0.0
        assert stats.max_duration_ms == 0.0
        assert stats.avg_duration_ms == 0.0
        assert stats.error_rate == 0.0

    def test_record_multiple_calls(self) -> None:
        """Test recording multiple service calls."""
        from aiohomematic.metrics import ServiceStats

        stats = ServiceStats()
        stats.record(duration_ms=50.0, had_error=False)
        stats.record(duration_ms=100.0, had_error=True)
        stats.record(duration_ms=150.0, had_error=False)

        assert stats.call_count == 3
        assert stats.error_count == 1
        assert stats.total_duration_ms == 300.0
        assert stats.max_duration_ms == 150.0
        assert stats.avg_duration_ms == 100.0
        assert abs(stats.error_rate - 33.33) < 0.1

    def test_record_single_call(self) -> None:
        """Test recording a single service call."""
        from aiohomematic.metrics import ServiceStats

        stats = ServiceStats()
        stats.record(duration_ms=50.0, had_error=False)

        assert stats.call_count == 1
        assert stats.error_count == 0
        assert stats.total_duration_ms == 50.0
        assert stats.max_duration_ms == 50.0
        assert stats.avg_duration_ms == 50.0
        assert stats.error_rate == 0.0

    def test_reset(self) -> None:
        """Test resetting service statistics."""
        from aiohomematic.metrics import ServiceStats

        stats = ServiceStats()
        stats.record(duration_ms=100.0, had_error=True)
        stats.reset()

        assert stats.call_count == 0
        assert stats.error_count == 0
        assert stats.total_duration_ms == 0.0
        assert stats.max_duration_ms == 0.0


class TestServiceMetrics:
    """Tests for ServiceMetrics dataclass."""

    def test_default_values(self) -> None:
        """Test default values of ServiceMetrics."""
        from aiohomematic.metrics import ServiceMetrics

        metrics = ServiceMetrics()
        assert metrics.total_calls == 0
        assert metrics.total_errors == 0
        assert metrics.avg_duration_ms == 0.0
        assert metrics.max_duration_ms == 0.0
        assert metrics.error_rate == 0.0
        assert len(metrics.by_method) == 0

    def test_error_rate_calculation(self) -> None:
        """Test error rate calculation."""
        from aiohomematic.metrics import ServiceMetrics

        metrics = ServiceMetrics(total_calls=100, total_errors=25)
        assert metrics.error_rate == 25.0
