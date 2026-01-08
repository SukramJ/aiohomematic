# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
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
    from aiohomematic.async_support import Looper
    from aiohomematic.client import (
        CircuitBreaker,
        CircuitBreakerConfig,
    )

    looper = Looper()
    breaker = CircuitBreaker(
        config=CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=30.0,
            success_threshold=2,
        ),
        interface_id="BidCos-RF",
        task_scheduler=looper,
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
import logging
from typing import TYPE_CHECKING, Any, Final

from aiohomematic import i18n
from aiohomematic.central.events.types import CircuitBreakerStateChangedEvent, CircuitBreakerTrippedEvent
from aiohomematic.const import CircuitState
from aiohomematic.metrics import MetricKeys, emit_counter
from aiohomematic.property_decorators import DelegatedProperty
from aiohomematic.store.types import IncidentSeverity, IncidentType

if TYPE_CHECKING:
    from aiohomematic.central import CentralConnectionState
    from aiohomematic.central.events import EventBus
    from aiohomematic.interfaces import IncidentRecorderProtocol, TaskSchedulerProtocol


_LOGGER: Final = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CircuitBreakerConfig:
    """Configuration for CircuitBreaker behavior."""

    failure_threshold: int = 5
    """Number of consecutive failures before opening the circuit."""

    recovery_timeout: float = 30.0
    """Seconds to wait in OPEN state before transitioning to HALF_OPEN."""

    success_threshold: int = 2
    """Number of consecutive successes in HALF_OPEN before closing the circuit."""


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
        event_bus: EventBus | None = None,
        incident_recorder: IncidentRecorderProtocol | None = None,
        task_scheduler: TaskSchedulerProtocol,
    ) -> None:
        """
        Initialize the circuit breaker.

        Args:
        ----
            config: Configuration for thresholds and timeouts
            interface_id: Interface identifier for logging and CentralConnectionState
            connection_state: Optional CentralConnectionState for integration
            issuer: Optional issuer object for CentralConnectionState
            event_bus: Optional EventBus for emitting events (metrics and health records)
            incident_recorder: Optional IncidentRecorderProtocol for recording diagnostic incidents
            task_scheduler: TaskSchedulerProtocol for scheduling async incident recording

        """
        self._config: Final = config or CircuitBreakerConfig()
        self._interface_id: Final = interface_id
        self._connection_state: Final = connection_state
        self._issuer: Final = issuer
        self._event_bus: Final = event_bus
        self._incident_recorder: Final = incident_recorder
        self._task_scheduler: Final = task_scheduler

        self._state: CircuitState = CircuitState.CLOSED
        self._failure_count: int = 0
        self._success_count: int = 0
        self._total_requests: int = 0
        self._last_failure_time: datetime | None = None

    state: Final = DelegatedProperty[CircuitState](path="_state")
    total_requests: Final = DelegatedProperty[int](path="_total_requests")

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
    def last_failure_time(self) -> datetime | None:
        """Return the timestamp of the last failure."""
        return self._last_failure_time

    def record_failure(self) -> None:
        """
        Record a failed request.

        In CLOSED state: increments failure count and may open circuit.
        In HALF_OPEN state: immediately opens circuit.
        """
        self._failure_count += 1
        self._total_requests += 1
        self._last_failure_time = datetime.now()

        if self._state == CircuitState.CLOSED:
            if self._failure_count >= self._config.failure_threshold:
                self._transition_to(new_state=CircuitState.OPEN)
        elif self._state == CircuitState.HALF_OPEN:
            # Any failure in HALF_OPEN goes back to OPEN
            self._transition_to(new_state=CircuitState.OPEN)

        # Emit failure counter (failures are significant events worth tracking)
        self._emit_counter(metric="failure")

    def record_rejection(self) -> None:
        """Record a rejected request (circuit is open)."""
        self._emit_counter(metric="rejection")

    def record_success(self) -> None:
        """
        Record a successful request.

        In CLOSED state: resets failure count.
        In HALF_OPEN state: increments success count and may close circuit.

        Note: Success is not emitted as an event (high frequency, low signal).
        Use total_requests property for request counting.
        """
        self._total_requests += 1

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
        self._total_requests = 0
        self._last_failure_time = None
        _LOGGER.debug(
            "CIRCUIT_BREAKER: Reset to CLOSED for %s",
            self._interface_id,
        )

    def _emit_counter(self, *, metric: str) -> None:
        """
        Emit a counter metric event for significant events only.

        Uses lazy import to avoid circular dependency:
        circuit_breaker → metrics → aggregator → circuit_breaker.

        Args:
        ----
            metric: The metric type ("failure", "rejection")

        Note:
        ----
            Success is not emitted as an event (high frequency, low signal).
            Only failures and rejections are tracked via events.

        """
        if self._event_bus is None:
            return

        if metric == "failure":
            key = MetricKeys.circuit_failure(interface_id=self._interface_id)
        elif metric == "rejection":
            key = MetricKeys.circuit_rejection(interface_id=self._interface_id)
        else:
            return

        emit_counter(event_bus=self._event_bus, key=key)

    def _emit_state_change_event(
        self,
        *,
        old_state: CircuitState,
        new_state: CircuitState,
    ) -> None:
        """Emit a circuit breaker state change event."""
        if self._event_bus is None:
            return

        self._event_bus.publish_sync(
            event=CircuitBreakerStateChangedEvent(
                timestamp=datetime.now(),
                interface_id=self._interface_id,
                old_state=old_state,
                new_state=new_state,
                failure_count=self._failure_count,
                success_count=self._success_count,
                last_failure_time=self._last_failure_time,
            )
        )

    def _emit_state_transition_counter(self) -> None:
        """Emit a counter for state transitions."""
        if self._event_bus is None:
            return

        emit_counter(
            event_bus=self._event_bus,
            key=MetricKeys.circuit_state_transition(interface_id=self._interface_id),
        )

    def _emit_tripped_event(self) -> None:
        """Emit a circuit breaker tripped event."""
        if self._event_bus is None:
            return

        self._event_bus.publish_sync(
            event=CircuitBreakerTrippedEvent(
                timestamp=datetime.now(),
                interface_id=self._interface_id,
                failure_count=self._failure_count,
                last_failure_reason=None,  # Could be enhanced in future
                cooldown_seconds=self._config.recovery_timeout,
            )
        )

    def _record_recovered_incident(self) -> None:
        """Record an incident when circuit breaker recovers."""
        if (incident_recorder := self._incident_recorder) is None:
            return

        # Capture values for the async closure
        interface_id = self._interface_id
        success_count = self._success_count
        success_threshold = self._config.success_threshold

        async def _record() -> None:
            try:
                await incident_recorder.record_incident(
                    incident_type=IncidentType.CIRCUIT_BREAKER_RECOVERED,
                    severity=IncidentSeverity.INFO,
                    message=f"Circuit breaker recovered for {interface_id} after {success_count} successful requests",
                    interface_id=interface_id,
                    context={
                        "success_count": success_count,
                        "success_threshold": success_threshold,
                    },
                )
            except Exception as err:  # pragma: no cover
                _LOGGER.debug(
                    "CIRCUIT_BREAKER: Failed to record recovered incident for %s: %s",
                    interface_id,
                    err,
                )

        # Schedule the async recording via task scheduler
        self._task_scheduler.create_task(
            target=_record(),
            name=f"record_circuit_breaker_recovered_incident_{interface_id}",
        )

    def _record_tripped_incident(self, *, old_state: CircuitState) -> None:
        """Record an incident when circuit breaker opens."""
        if (incident_recorder := self._incident_recorder) is None:
            return

        # Capture values for the async closure
        interface_id = self._interface_id
        failure_count = self._failure_count
        failure_threshold = self._config.failure_threshold
        recovery_timeout = self._config.recovery_timeout
        last_failure_time = self._last_failure_time.isoformat() if self._last_failure_time else None
        total_requests = self._total_requests

        async def _record() -> None:
            try:
                await incident_recorder.record_incident(
                    incident_type=IncidentType.CIRCUIT_BREAKER_TRIPPED,
                    severity=IncidentSeverity.ERROR,
                    message=f"Circuit breaker opened for {interface_id} after {failure_count} failures",
                    interface_id=interface_id,
                    context={
                        "old_state": str(old_state),
                        "failure_count": failure_count,
                        "failure_threshold": failure_threshold,
                        "recovery_timeout": recovery_timeout,
                        "last_failure_time": last_failure_time,
                        "total_requests": total_requests,
                    },
                )
            except Exception as err:  # pragma: no cover
                _LOGGER.debug(
                    "CIRCUIT_BREAKER: Failed to record tripped incident for %s: %s",
                    interface_id,
                    err,
                )

        # Schedule the async recording via task scheduler
        self._task_scheduler.create_task(
            target=_record(),
            name=f"record_circuit_breaker_tripped_incident_{interface_id}",
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
        self._emit_state_transition_counter()

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
                    key="log.client.circuit_breaker.state_transition",
                    old_state=old_state,
                    new_state=new_state,
                    interface_id=self._interface_id,
                    failure_count=self._failure_count,
                    success_count=self._success_count,
                )
            )

        # Emit state change event
        self._emit_state_change_event(old_state=old_state, new_state=new_state)

        # Emit tripped event and record incident when circuit opens
        if new_state == CircuitState.OPEN:
            self._emit_tripped_event()
            self._record_tripped_incident(old_state=old_state)

        # Record recovery incident when circuit recovers from HALF_OPEN
        if old_state == CircuitState.HALF_OPEN and new_state == CircuitState.CLOSED:
            self._record_recovered_incident()

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
