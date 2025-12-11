# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Circuit Breaker pattern implementation for RPC calls.

Overview
--------
The Circuit Breaker prevents retry-storms when backends are unavailable by
tracking failures and temporarily blocking requests when a failure threshold
is reached. This protects both the client (from wasting resources on doomed
requests) and the backend (from being overwhelmed during recovery).

State Machine
-------------
The circuit breaker has three states:

    CLOSED (normal operation)
        │
        │ failure_threshold failures
        ▼
    OPEN (fast-fail all requests)
        │
        │ recovery_timeout elapsed
        ▼
    HALF_OPEN (test one request)
        │
        ├── success_threshold successes → CLOSED
        └── failure → OPEN

Example Usage
-------------
    from aiohomematic.client.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

    breaker = CircuitBreaker(
        config=CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=30.0,
            success_threshold=2,
        ),
        interface_id="BidCos-RF",
    )

    # In request handler:
    if not breaker.is_available:
        raise NoConnectionException("Circuit breaker is open")

    try:
        result = await do_request()
        breaker.record_success()
        return result
    except Exception:
        breaker.record_failure()
        raise

"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import logging
from typing import TYPE_CHECKING, Any, Final

from aiohomematic import i18n

if TYPE_CHECKING:
    from aiohomematic.central import CentralConnectionState

_LOGGER: Final = logging.getLogger(__name__)


class CircuitState(StrEnum):
    """Circuit breaker states."""

    CLOSED = "closed"
    """Normal operation - requests are allowed through."""

    OPEN = "open"
    """Failure mode - requests are immediately rejected."""

    HALF_OPEN = "half_open"
    """Test mode - one request is allowed to test recovery."""


@dataclass(frozen=True, slots=True)
class CircuitBreakerConfig:
    """Configuration for CircuitBreaker behavior."""

    failure_threshold: int = 5
    """Number of consecutive failures before opening the circuit."""

    recovery_timeout: float = 30.0
    """Seconds to wait in OPEN state before transitioning to HALF_OPEN."""

    success_threshold: int = 2
    """Number of consecutive successes in HALF_OPEN before closing the circuit."""


@dataclass(slots=True)
class CircuitBreakerMetrics:
    """Metrics for monitoring circuit breaker behavior."""

    total_requests: int = 0
    """Total number of requests processed."""

    successful_requests: int = 0
    """Number of successful requests."""

    failed_requests: int = 0
    """Number of failed requests."""

    rejected_requests: int = 0
    """Number of requests rejected due to open circuit."""

    state_transitions: int = 0
    """Number of state transitions."""

    last_failure_time: datetime | None = None
    """Timestamp of last failure."""

    last_state_change: datetime | None = None
    """Timestamp of last state change."""


class CircuitBreaker:
    """
    Circuit breaker for RPC calls to prevent retry-storms.

    The circuit breaker monitors request success/failure rates and
    temporarily blocks requests when too many failures occur. This
    prevents overwhelming a failing backend and allows time for recovery.

    Thread Safety
    -------------
    This class is designed for single-threaded asyncio use.
    State changes are not thread-safe.
    """

    def __init__(
        self,
        *,
        config: CircuitBreakerConfig | None = None,
        interface_id: str,
        connection_state: CentralConnectionState | None = None,
        issuer: Any = None,
    ) -> None:
        """
        Initialize the circuit breaker.

        Args:
        ----
            config: Configuration for thresholds and timeouts
            interface_id: Interface identifier for logging and CentralConnectionState
            connection_state: Optional CentralConnectionState for integration
            issuer: Optional issuer object for CentralConnectionState

        """
        self._config: Final = config or CircuitBreakerConfig()
        self._interface_id: Final = interface_id
        self._connection_state = connection_state
        self._issuer = issuer

        self._state: CircuitState = CircuitState.CLOSED
        self._failure_count: int = 0
        self._success_count: int = 0
        self._last_failure_time: datetime | None = None
        self._metrics: CircuitBreakerMetrics = CircuitBreakerMetrics()

    @property
    def is_available(self) -> bool:
        """
        Check if requests should be allowed through.

        Returns True if:
        - State is CLOSED (normal operation)
        - State is HALF_OPEN (testing recovery)
        - State is OPEN but recovery_timeout has elapsed (transitions to HALF_OPEN)
        """
        if self._state == CircuitState.CLOSED:
            return True

        if self._state == CircuitState.OPEN:
            # Check if recovery timeout has elapsed
            if self._last_failure_time:
                elapsed = (datetime.now() - self._last_failure_time).total_seconds()
                if elapsed >= self._config.recovery_timeout:
                    self._transition_to(new_state=CircuitState.HALF_OPEN)
                    return True
            return False

        # HALF_OPEN - allow one request through
        return True

    @property
    def metrics(self) -> CircuitBreakerMetrics:
        """Return current metrics."""
        return self._metrics

    @property
    def state(self) -> CircuitState:
        """Return the current circuit state."""
        return self._state

    def record_failure(self) -> None:
        """
        Record a failed request.

        In CLOSED state: increments failure count and may open circuit.
        In HALF_OPEN state: immediately opens circuit.
        """
        self._metrics.total_requests += 1
        self._metrics.failed_requests += 1
        self._metrics.last_failure_time = datetime.now()

        self._failure_count += 1
        self._last_failure_time = datetime.now()

        if self._state == CircuitState.CLOSED:
            if self._failure_count >= self._config.failure_threshold:
                self._transition_to(new_state=CircuitState.OPEN)
        elif self._state == CircuitState.HALF_OPEN:
            # Any failure in HALF_OPEN goes back to OPEN
            self._transition_to(new_state=CircuitState.OPEN)

    def record_rejection(self) -> None:
        """Record a rejected request (circuit is open)."""
        self._metrics.total_requests += 1
        self._metrics.rejected_requests += 1

    def record_success(self) -> None:
        """
        Record a successful request.

        In CLOSED state: resets failure count.
        In HALF_OPEN state: increments success count and may close circuit.
        """
        self._metrics.total_requests += 1
        self._metrics.successful_requests += 1

        if self._state == CircuitState.CLOSED:
            self._failure_count = 0
        elif self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self._config.success_threshold:
                self._transition_to(new_state=CircuitState.CLOSED)

    def reset(self) -> None:
        """Reset the circuit breaker to initial state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
        _LOGGER.debug(
            "CIRCUIT_BREAKER: Reset to CLOSED for %s",
            self._interface_id,
        )

    def _transition_to(self, *, new_state: CircuitState) -> None:
        """
        Handle state transition with logging and CentralConnectionState notification.

        Args:
        ----
            new_state: The target state to transition to

        """
        if (old_state := self._state) == new_state:
            return

        self._state = new_state
        self._metrics.state_transitions += 1
        self._metrics.last_state_change = datetime.now()

        # Use DEBUG for expected recovery transitions, INFO for issues and recovery attempts
        if old_state == CircuitState.HALF_OPEN and new_state == CircuitState.CLOSED:
            # Recovery successful - expected behavior during reconnection (DEBUG is allowed without i18n)
            _LOGGER.debug(
                "CIRCUIT_BREAKER: %s → %s for %s (failures=%d, successes=%d)",
                old_state,
                new_state,
                self._interface_id,
                self._failure_count,
                self._success_count,
            )
        else:
            # Problem detected (CLOSED→OPEN) or testing recovery (OPEN→HALF_OPEN)
            _LOGGER.info(
                i18n.tr(
                    "log.client.circuit_breaker.state_transition",
                    old_state=old_state,
                    new_state=new_state,
                    interface_id=self._interface_id,
                    failure_count=self._failure_count,
                    success_count=self._success_count,
                )
            )

        # Reset counters based on new state
        if new_state == CircuitState.CLOSED:
            self._failure_count = 0
            self._success_count = 0
            # Notify CentralConnectionState that connection is restored
            if self._connection_state and self._issuer:
                self._connection_state.remove_issue(issuer=self._issuer, iid=self._interface_id)
        elif new_state == CircuitState.OPEN:
            self._success_count = 0
            # Notify CentralConnectionState about the issue
            if self._connection_state and self._issuer:
                self._connection_state.add_issue(issuer=self._issuer, iid=self._interface_id)
        elif new_state == CircuitState.HALF_OPEN:
            self._success_count = 0
