# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for CircuitBreaker."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from aiohomematic.central.events import CircuitBreakerStateChangedEvent, CircuitBreakerTrippedEvent, EventBus
from aiohomematic.client import CircuitBreaker, CircuitBreakerConfig, CircuitState
from aiohomematic.metrics import MetricKeys, MetricsObserver
from aiohomematic_test_support.event_capture import EventCapture


class TestCircuitBreakerConfig:
    """Tests for CircuitBreakerConfig."""

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = CircuitBreakerConfig(
            failure_threshold=10,
            recovery_timeout=60.0,
            success_threshold=3,
        )
        assert config.failure_threshold == 10
        assert config.recovery_timeout == 60.0
        assert config.success_threshold == 3

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = CircuitBreakerConfig()
        assert config.failure_threshold == 5
        assert config.recovery_timeout == 30.0
        assert config.success_threshold == 2

    def test_frozen(self) -> None:
        """Test config is immutable."""
        config = CircuitBreakerConfig()
        with pytest.raises(AttributeError):
            config.failure_threshold = 10  # type: ignore[misc]


class TestCircuitState:
    """Tests for CircuitState enum."""

    def test_values(self) -> None:
        """Test CircuitState values."""
        assert CircuitState.CLOSED == "closed"
        assert CircuitState.OPEN == "open"
        assert CircuitState.HALF_OPEN == "half_open"


class TestCircuitBreaker:
    """Tests for CircuitBreaker."""

    @pytest.mark.asyncio
    async def test_complete_cycle(self, event_capture: EventCapture) -> None:
        """Test complete circuit breaker cycle, verified via events."""
        event_bus = EventBus()
        event_capture.subscribe_to(
            event_bus,
            CircuitBreakerStateChangedEvent,
            CircuitBreakerTrippedEvent,
        )

        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=0.1,
            success_threshold=2,
        )
        breaker = CircuitBreaker(config=config, interface_id="test", event_bus=event_bus)

        # Start CLOSED
        assert breaker.state == CircuitState.CLOSED

        # Failures open circuit
        breaker.record_failure()
        breaker.record_failure()

        # Timeout transitions to HALF_OPEN
        breaker._last_failure_time = datetime.now() - timedelta(seconds=1)
        _ = breaker.is_available

        # Successes close circuit
        breaker.record_success()
        breaker.record_success()

        await asyncio.sleep(0.02)

        # Verify full cycle via events
        state_events = event_capture.get_events_of_type(event_type=CircuitBreakerStateChangedEvent)
        assert len(state_events) == 3

        # CLOSED -> OPEN
        assert state_events[0].old_state == CircuitState.CLOSED
        assert state_events[0].new_state == CircuitState.OPEN

        # OPEN -> HALF_OPEN
        assert state_events[1].old_state == CircuitState.OPEN
        assert state_events[1].new_state == CircuitState.HALF_OPEN

        # HALF_OPEN -> CLOSED
        assert state_events[2].old_state == CircuitState.HALF_OPEN
        assert state_events[2].new_state == CircuitState.CLOSED

        # Verify trip event was emitted
        event_capture.assert_event_emitted(
            event_type=CircuitBreakerTrippedEvent,
            interface_id="test",
            failure_count=2,
        )

    def test_connection_state_notified_on_close(self) -> None:
        """Test CentralConnectionState is notified when circuit closes."""
        connection_state = MagicMock()
        issuer = MagicMock()
        config = CircuitBreakerConfig(failure_threshold=1, success_threshold=1)
        breaker = CircuitBreaker(
            config=config,
            interface_id="test",
            connection_state=connection_state,
            issuer=issuer,
        )

        # Open circuit
        breaker.record_failure()
        # Transition to half-open
        breaker._last_failure_time = datetime.now() - timedelta(seconds=100)
        _ = breaker.is_available

        # Close circuit with success
        breaker.record_success()
        connection_state.remove_issue.assert_called_once_with(issuer=issuer, iid="test")

    def test_connection_state_notified_on_open(self) -> None:
        """Test CentralConnectionState is notified when circuit opens."""
        connection_state = MagicMock()
        issuer = MagicMock()
        config = CircuitBreakerConfig(failure_threshold=1)
        breaker = CircuitBreaker(
            config=config,
            interface_id="test",
            connection_state=connection_state,
            issuer=issuer,
        )

        breaker.record_failure()
        connection_state.add_issue.assert_called_once_with(issuer=issuer, iid="test")

    def test_half_open_failure_reopens_circuit(self) -> None:
        """Test failure in half-open state reopens circuit."""
        config = CircuitBreakerConfig(failure_threshold=1)
        breaker = CircuitBreaker(config=config, interface_id="test")

        # Open circuit
        breaker.record_failure()
        # Transition to half-open
        breaker._last_failure_time = datetime.now() - timedelta(seconds=100)
        _ = breaker.is_available  # Triggers transition

        assert breaker.state == CircuitState.HALF_OPEN

        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

    def test_half_open_is_available(self) -> None:
        """Test HALF_OPEN state is available."""
        config = CircuitBreakerConfig(failure_threshold=1)
        breaker = CircuitBreaker(config=config, interface_id="test")

        breaker.record_failure()
        breaker._last_failure_time = datetime.now() - timedelta(seconds=100)

        # First check transitions to HALF_OPEN
        assert breaker.is_available is True
        assert breaker.state == CircuitState.HALF_OPEN

        # HALF_OPEN should remain available
        assert breaker.is_available is True

    def test_half_open_success_at_threshold_closes_circuit(self) -> None:
        """Test success at threshold closes circuit."""
        config = CircuitBreakerConfig(failure_threshold=1, success_threshold=2)
        breaker = CircuitBreaker(config=config, interface_id="test")

        # Open circuit
        breaker.record_failure()
        # Transition to half-open
        breaker._last_failure_time = datetime.now() - timedelta(seconds=100)
        _ = breaker.is_available  # Triggers transition

        breaker.record_success()
        breaker.record_success()

        assert breaker.state == CircuitState.CLOSED

    def test_half_open_success_increments_count(self) -> None:
        """Test success in half-open state increments count."""
        config = CircuitBreakerConfig(failure_threshold=1, success_threshold=2)
        breaker = CircuitBreaker(config=config, interface_id="test")

        # Open circuit
        breaker.record_failure()
        # Transition to half-open
        breaker._last_failure_time = datetime.now() - timedelta(seconds=100)
        _ = breaker.is_available  # Triggers transition

        assert breaker.state == CircuitState.HALF_OPEN

        breaker.record_success()
        assert breaker.state == CircuitState.HALF_OPEN  # Not yet at threshold

    def test_init_custom_config(self) -> None:
        """Test initialization with custom config."""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker(config=config, interface_id="test")
        assert breaker.state == CircuitState.CLOSED

    def test_init_default_config(self) -> None:
        """Test initialization with default config."""
        breaker = CircuitBreaker(interface_id="test")
        assert breaker.state == CircuitState.CLOSED
        assert breaker.is_available is True

    def test_initial_state_is_closed(self) -> None:
        """Test circuit starts in CLOSED state."""
        breaker = CircuitBreaker(interface_id="test")
        assert breaker.state == CircuitState.CLOSED
        assert breaker.is_available is True

    @pytest.mark.asyncio
    async def test_metrics_tracking_via_observer(self) -> None:
        """Test comprehensive metrics tracking via observer."""
        event_bus = EventBus()
        observer = MetricsObserver(event_bus=event_bus)
        config = CircuitBreakerConfig(failure_threshold=2)
        breaker = CircuitBreaker(config=config, interface_id="test", event_bus=event_bus)

        breaker.record_success()
        breaker.record_failure()
        breaker.record_failure()  # Opens circuit
        breaker.record_rejection()

        # Give event loop time to process scheduled events
        await asyncio.sleep(0.01)

        # Verify counters via observer (only significant events are emitted)
        assert observer.get_counter(key=MetricKeys.circuit_failure(interface_id="test")) == 2
        assert observer.get_counter(key=MetricKeys.circuit_rejection(interface_id="test")) == 1
        assert observer.get_counter(key=MetricKeys.circuit_state_transition(interface_id="test")) == 1
        # Success is tracked via local counter (not event-based)
        assert breaker.total_requests == 3  # 1 success + 2 failures (rejection doesn't increment total)
        assert breaker.last_failure_time is not None

    @pytest.mark.asyncio
    async def test_no_transition_to_same_state(self) -> None:
        """Test no transition when already in target state."""
        event_bus = EventBus()
        observer = MetricsObserver(event_bus=event_bus)
        breaker = CircuitBreaker(interface_id="test", event_bus=event_bus)

        await asyncio.sleep(0.01)
        initial_transitions = observer.get_counter(key=MetricKeys.circuit_state_transition(interface_id="test"))

        # Try to transition to CLOSED while already CLOSED
        breaker._transition_to(new_state=CircuitState.CLOSED)

        await asyncio.sleep(0.01)
        assert observer.get_counter(key=MetricKeys.circuit_state_transition(interface_id="test")) == initial_transitions

    def test_open_circuit_not_available(self) -> None:
        """Test open circuit is not available."""
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=1000.0)
        breaker = CircuitBreaker(config=config, interface_id="test")

        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN
        assert breaker.is_available is False

    def test_open_circuit_transitions_to_half_open_after_timeout(self) -> None:
        """Test open circuit transitions to half-open after recovery timeout."""
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=0.1)
        breaker = CircuitBreaker(config=config, interface_id="test")

        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        # Simulate time passing by manipulating last_failure_time
        breaker._last_failure_time = datetime.now() - timedelta(seconds=1)

        assert breaker.is_available is True
        assert breaker.state == CircuitState.HALF_OPEN

    def test_open_without_last_failure_time(self) -> None:
        """Test OPEN state behavior without last_failure_time."""
        config = CircuitBreakerConfig(failure_threshold=1)
        breaker = CircuitBreaker(config=config, interface_id="test")

        breaker.record_failure()
        breaker._last_failure_time = None  # Simulate edge case

        assert breaker.is_available is False

    @pytest.mark.asyncio
    async def test_record_failure_at_threshold_opens_circuit(self) -> None:
        """Test failures at threshold open circuit."""
        event_bus = EventBus()
        observer = MetricsObserver(event_bus=event_bus)
        config = CircuitBreakerConfig(failure_threshold=5)
        breaker = CircuitBreaker(config=config, interface_id="test", event_bus=event_bus)

        for _ in range(5):
            breaker.record_failure()

        assert breaker.state == CircuitState.OPEN
        assert breaker.is_available is False

        await asyncio.sleep(0.01)
        assert observer.get_counter(key=MetricKeys.circuit_state_transition(interface_id="test")) == 1

    @pytest.mark.asyncio
    async def test_record_failure_below_threshold(self) -> None:
        """Test failures below threshold don't open circuit."""
        event_bus = EventBus()
        observer = MetricsObserver(event_bus=event_bus)
        config = CircuitBreakerConfig(failure_threshold=5)
        breaker = CircuitBreaker(config=config, interface_id="test", event_bus=event_bus)

        for _ in range(4):
            breaker.record_failure()

        assert breaker.state == CircuitState.CLOSED
        assert breaker.is_available is True

        await asyncio.sleep(0.01)
        assert observer.get_counter(key=MetricKeys.circuit_failure(interface_id="test")) == 4

    @pytest.mark.asyncio
    async def test_record_rejection(self) -> None:
        """Test recording a rejected request."""
        event_bus = EventBus()
        observer = MetricsObserver(event_bus=event_bus)
        breaker = CircuitBreaker(interface_id="test", event_bus=event_bus)
        breaker.record_rejection()

        await asyncio.sleep(0.01)
        assert observer.get_counter(key=MetricKeys.circuit_rejection(interface_id="test")) == 1

    @pytest.mark.asyncio
    async def test_record_success_in_closed_state(self) -> None:
        """Test recording success in CLOSED state."""
        breaker = CircuitBreaker(interface_id="test")
        breaker.record_success()

        assert breaker.state == CircuitState.CLOSED
        # Success tracked via local counter (not event-based for performance)
        assert breaker.total_requests == 1

    def test_reset(self) -> None:
        """Test resetting circuit breaker."""
        config = CircuitBreakerConfig(failure_threshold=1)
        breaker = CircuitBreaker(config=config, interface_id="test")

        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        breaker.reset()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.is_available is True

    @pytest.mark.asyncio
    async def test_state_transition_counter(self) -> None:
        """Test state transitions emit counter events."""
        event_bus = EventBus()
        observer = MetricsObserver(event_bus=event_bus)
        config = CircuitBreakerConfig(failure_threshold=1)
        breaker = CircuitBreaker(config=config, interface_id="test", event_bus=event_bus)

        breaker.record_failure()

        await asyncio.sleep(0.01)
        assert observer.get_counter(key=MetricKeys.circuit_state_transition(interface_id="test")) == 1

    @pytest.mark.asyncio
    async def test_success_count_reset_on_state_change(self, event_capture: EventCapture) -> None:
        """Test success count is reset on state changes, verified via events."""
        event_bus = EventBus()
        event_capture.subscribe_to(event_bus, CircuitBreakerStateChangedEvent)

        config = CircuitBreakerConfig(failure_threshold=1, success_threshold=3)
        breaker = CircuitBreaker(config=config, interface_id="test", event_bus=event_bus)

        # Open circuit
        breaker.record_failure()
        # Transition to half-open
        breaker._last_failure_time = datetime.now() - timedelta(seconds=100)
        _ = breaker.is_available

        # Record one success (not enough to close)
        breaker.record_success()

        # Failure resets to OPEN - verify via event
        breaker.record_failure()

        await asyncio.sleep(0.02)

        # Verify state transitions via events: CLOSED->OPEN, OPEN->HALF_OPEN, HALF_OPEN->OPEN
        events = event_capture.get_events_of_type(event_type=CircuitBreakerStateChangedEvent)
        assert len(events) == 3

        # Last event should show HALF_OPEN -> OPEN (reset due to failure in half-open)
        assert events[2].old_state == CircuitState.HALF_OPEN
        assert events[2].new_state == CircuitState.OPEN
        # Event captures state at transition time; failure_count incremented
        assert events[2].failure_count == 2

    def test_success_resets_failure_count_in_closed_state(self) -> None:
        """Test success resets failure count in closed state."""
        config = CircuitBreakerConfig(failure_threshold=5)
        breaker = CircuitBreaker(config=config, interface_id="test")

        # Record some failures
        for _ in range(3):
            breaker.record_failure()

        # Then a success
        breaker.record_success()

        # More failures should need full threshold again
        for _ in range(4):
            breaker.record_failure()

        assert breaker.state == CircuitState.CLOSED
