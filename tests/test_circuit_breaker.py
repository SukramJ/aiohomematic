"""Tests for CircuitBreaker."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from aiohomematic.client.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerMetrics,
    CircuitState,
)

if TYPE_CHECKING:
    pass


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


class TestCircuitBreakerMetrics:
    """Tests for CircuitBreakerMetrics."""

    def test_initial_state(self) -> None:
        """Test initial metrics state."""
        metrics = CircuitBreakerMetrics()
        assert metrics.total_requests == 0
        assert metrics.successful_requests == 0
        assert metrics.failed_requests == 0
        assert metrics.rejected_requests == 0
        assert metrics.state_transitions == 0
        assert metrics.last_failure_time is None
        assert metrics.last_state_change is None


class TestCircuitState:
    """Tests for CircuitState enum."""

    def test_values(self) -> None:
        """Test CircuitState values."""
        assert CircuitState.CLOSED == "closed"
        assert CircuitState.OPEN == "open"
        assert CircuitState.HALF_OPEN == "half_open"


class TestCircuitBreaker:
    """Tests for CircuitBreaker."""

    def test_complete_cycle(self) -> None:
        """Test complete circuit breaker cycle."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=0.1,
            success_threshold=2,
        )
        breaker = CircuitBreaker(config=config, interface_id="test")

        # Start CLOSED
        assert breaker.state == CircuitState.CLOSED

        # Failures open circuit
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        # Timeout transitions to HALF_OPEN
        breaker._last_failure_time = datetime.now() - timedelta(seconds=1)
        assert breaker.is_available is True
        assert breaker.state == CircuitState.HALF_OPEN

        # Successes close circuit
        breaker.record_success()
        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED

        # Verify metrics
        assert breaker.metrics.state_transitions == 3  # CLOSED->OPEN->HALF_OPEN->CLOSED

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

    def test_health_callback_on_failure(self) -> None:
        """Test health callback is called on failure."""
        callback = MagicMock()
        breaker = CircuitBreaker(
            interface_id="test",
            health_record_callback=callback,
        )

        breaker.record_failure()
        callback.assert_called_once_with(interface_id="test", success=False)

    def test_health_callback_on_success(self) -> None:
        """Test health callback is called on success."""
        callback = MagicMock()
        breaker = CircuitBreaker(
            interface_id="test",
            health_record_callback=callback,
        )

        breaker.record_success()
        callback.assert_called_once_with(interface_id="test", success=True)

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

    def test_metrics_tracking(self) -> None:
        """Test comprehensive metrics tracking."""
        config = CircuitBreakerConfig(failure_threshold=2)
        breaker = CircuitBreaker(config=config, interface_id="test")

        breaker.record_success()
        breaker.record_failure()
        breaker.record_failure()  # Opens circuit
        breaker.record_rejection()

        assert breaker.metrics.total_requests == 4
        assert breaker.metrics.successful_requests == 1
        assert breaker.metrics.failed_requests == 2
        assert breaker.metrics.rejected_requests == 1
        assert breaker.metrics.state_transitions == 1
        assert breaker.metrics.last_failure_time is not None

    def test_no_transition_to_same_state(self) -> None:
        """Test no transition when already in target state."""
        breaker = CircuitBreaker(interface_id="test")
        initial_transitions = breaker.metrics.state_transitions

        # Try to transition to CLOSED while already CLOSED
        breaker._transition_to(new_state=CircuitState.CLOSED)

        assert breaker.metrics.state_transitions == initial_transitions

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

    def test_record_failure_at_threshold_opens_circuit(self) -> None:
        """Test failures at threshold open circuit."""
        config = CircuitBreakerConfig(failure_threshold=5)
        breaker = CircuitBreaker(config=config, interface_id="test")

        for _ in range(5):
            breaker.record_failure()

        assert breaker.state == CircuitState.OPEN
        assert breaker.is_available is False
        assert breaker.metrics.state_transitions == 1

    def test_record_failure_below_threshold(self) -> None:
        """Test failures below threshold don't open circuit."""
        config = CircuitBreakerConfig(failure_threshold=5)
        breaker = CircuitBreaker(config=config, interface_id="test")

        for _ in range(4):
            breaker.record_failure()

        assert breaker.state == CircuitState.CLOSED
        assert breaker.is_available is True
        assert breaker.metrics.failed_requests == 4

    def test_record_rejection(self) -> None:
        """Test recording a rejected request."""
        breaker = CircuitBreaker(interface_id="test")
        breaker.record_rejection()

        assert breaker.metrics.total_requests == 1
        assert breaker.metrics.rejected_requests == 1

    def test_record_success_in_closed_state(self) -> None:
        """Test recording success in CLOSED state."""
        breaker = CircuitBreaker(interface_id="test")
        breaker.record_success()

        assert breaker.state == CircuitState.CLOSED
        assert breaker.metrics.total_requests == 1
        assert breaker.metrics.successful_requests == 1

    def test_reset(self) -> None:
        """Test resetting circuit breaker."""
        config = CircuitBreakerConfig(failure_threshold=1)
        breaker = CircuitBreaker(config=config, interface_id="test")

        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        breaker.reset()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.is_available is True

    def test_state_transition_logging(self) -> None:
        """Test state transitions are logged."""
        config = CircuitBreakerConfig(failure_threshold=1)
        breaker = CircuitBreaker(config=config, interface_id="test")

        breaker.record_failure()
        assert breaker.metrics.state_transitions == 1
        assert breaker.metrics.last_state_change is not None

    def test_success_count_reset_on_state_change(self) -> None:
        """Test success count is reset on state changes."""
        config = CircuitBreakerConfig(failure_threshold=1, success_threshold=3)
        breaker = CircuitBreaker(config=config, interface_id="test")

        # Open circuit
        breaker.record_failure()
        # Transition to half-open
        breaker._last_failure_time = datetime.now() - timedelta(seconds=100)
        _ = breaker.is_available

        # Record one success
        breaker.record_success()
        assert breaker._success_count == 1

        # Failure resets to OPEN and resets success count
        breaker.record_failure()
        assert breaker._success_count == 0

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
