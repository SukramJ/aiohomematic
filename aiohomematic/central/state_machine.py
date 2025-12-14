# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Central state machine for orchestrating overall system health.

This module provides the CentralStateMachine which manages the overall state
of the system based on individual client states. It acts as an orchestrator
above the client-level state machines.

Overview
--------
The CentralStateMachine provides:
- Unified view of system health
- Coordinated state transitions
- Event emission for state changes
- Validation of state transitions

State Machine
-------------
```
STARTING ──► INITIALIZING ──► RUNNING ◄──► DEGRADED
                  │              │            │
                  │              ▼            ▼
                  │          RECOVERING ◄────┘
                  │              │
                  │              ├──► RUNNING
                  │              ├──► DEGRADED
                  │              └──► FAILED
                  │
                  └──► FAILED

STOPPED ◄── (from any state)
```

The CentralStateMachine observes client state machines and determines the
overall system state:
- RUNNING: All clients are CONNECTED
- DEGRADED: At least one client is not CONNECTED
- RECOVERING: Recovery is in progress
- FAILED: Max retries reached, manual intervention required
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import logging
from typing import TYPE_CHECKING, Final

from aiohomematic.const import CentralState
from aiohomematic.interfaces.central import CentralStateMachineProtocol

if TYPE_CHECKING:
    from aiohomematic.central.event_bus import EventBus

_LOGGER: Final = logging.getLogger(__name__)

# Valid state transitions define which state changes are allowed.
# This forms a directed graph where each state maps to its valid successors.
VALID_CENTRAL_TRANSITIONS: Final[dict[CentralState, frozenset[CentralState]]] = {
    # Initial state - Central is being created
    CentralState.STARTING: frozenset(
        {
            CentralState.INITIALIZING,
            CentralState.STOPPED,  # stop() before start()
        }
    ),
    # During initialization - clients are being initialized
    CentralState.INITIALIZING: frozenset(
        {
            CentralState.RUNNING,  # All clients OK
            CentralState.DEGRADED,  # At least one client not OK
            CentralState.FAILED,  # Critical init error
            CentralState.STOPPED,  # stop() during init
        }
    ),
    # Normal operation - all clients connected
    CentralState.RUNNING: frozenset(
        {
            CentralState.DEGRADED,  # Client problem detected
            CentralState.RECOVERING,  # Proactive recovery
            CentralState.STOPPED,  # Graceful shutdown
        }
    ),
    # Limited operation - at least one client not connected
    CentralState.DEGRADED: frozenset(
        {
            CentralState.RUNNING,  # All clients recovered
            CentralState.RECOVERING,  # Start recovery
            CentralState.FAILED,  # Too long degraded
            CentralState.STOPPED,  # Shutdown
        }
    ),
    # Active recovery in progress
    CentralState.RECOVERING: frozenset(
        {
            CentralState.RUNNING,  # Recovery successful
            CentralState.DEGRADED,  # Partial recovery
            CentralState.FAILED,  # Max retries reached
            CentralState.STOPPED,  # Shutdown during recovery
        }
    ),
    # Critical error - manual intervention required
    CentralState.FAILED: frozenset(
        {
            CentralState.RECOVERING,  # Manual retry
            CentralState.STOPPED,  # Shutdown
        }
    ),
    # Terminal state - no transitions allowed
    CentralState.STOPPED: frozenset(),
}


class InvalidCentralStateTransitionError(Exception):
    """Raised when an invalid central state transition is attempted."""

    def __init__(self, *, current: CentralState, target: CentralState, central_name: str) -> None:
        """Initialize the error."""
        self.current = current
        self.target = target
        self.central_name = central_name
        super().__init__(f"Invalid central state transition from {current.value} to {target.value} for {central_name}")


class CentralStateMachine(CentralStateMachineProtocol):
    """
    State machine for central system health orchestration.

    This class manages the overall state of the central system based on
    individual client states. It provides:
    - Unified system state (RUNNING, DEGRADED, RECOVERING, FAILED)
    - Validated state transitions
    - Event emission for monitoring
    - Callback support for state changes

    Thread Safety
    -------------
    This class is NOT thread-safe. All calls should happen from the same
    event loop/thread.

    Example:
        def on_state_change(old_state: CentralState, new_state: CentralState, reason: str) -> None:
            print(f"Central state: {old_state} -> {new_state} ({reason})")

        sm = CentralStateMachine(central_name="ccu-main")
        sm.on_state_change = on_state_change

        sm.transition_to(target=CentralState.INITIALIZING, reason="start() called")
        sm.transition_to(target=CentralState.RUNNING, reason="all clients connected")

    """

    __slots__ = (
        "_central_name",
        "_event_bus",
        "_last_state_change",
        "_state",
        "_state_history",
        "on_state_change",
    )

    def __init__(
        self,
        *,
        central_name: str,
        event_bus: EventBus | None = None,
    ) -> None:
        """
        Initialize the central state machine.

        Args:
            central_name: Name of the central unit for logging
            event_bus: Optional event bus for publishing state change events

        """
        self._central_name: Final = central_name
        self._event_bus = event_bus
        self._state: CentralState = CentralState.STARTING
        self._last_state_change: datetime = datetime.now()
        self._state_history: list[tuple[datetime, CentralState, CentralState, str]] = []
        self.on_state_change: Callable[[CentralState, CentralState, str], None] | None = None

    @property
    def is_degraded(self) -> bool:
        """Return True if system is in degraded state."""
        return self._state == CentralState.DEGRADED

    @property
    def is_failed(self) -> bool:
        """Return True if system is in failed state."""
        return self._state == CentralState.FAILED

    @property
    def is_operational(self) -> bool:
        """Return True if system is operational (RUNNING or DEGRADED)."""
        return self._state in (CentralState.RUNNING, CentralState.DEGRADED)

    @property
    def is_recovering(self) -> bool:
        """Return True if recovery is in progress."""
        return self._state == CentralState.RECOVERING

    @property
    def is_running(self) -> bool:
        """Return True if system is fully running."""
        return self._state == CentralState.RUNNING

    @property
    def is_stopped(self) -> bool:
        """Return True if system is stopped."""
        return self._state == CentralState.STOPPED

    @property
    def last_state_change(self) -> datetime:
        """Return timestamp of last state change."""
        return self._last_state_change

    @property
    def seconds_in_current_state(self) -> float:
        """Return seconds since last state change."""
        return (datetime.now() - self._last_state_change).total_seconds()

    @property
    def state(self) -> CentralState:
        """Return the current state."""
        return self._state

    @property
    def state_history(self) -> list[tuple[datetime, CentralState, CentralState, str]]:
        """Return state transition history (timestamp, old_state, new_state, reason)."""
        return self._state_history.copy()

    def can_transition_to(self, *, target: CentralState) -> bool:
        """
        Check if transition to target state is valid.

        Args:
            target: Target state to check

        Returns:
            True if transition is valid, False otherwise

        """
        return target in VALID_CENTRAL_TRANSITIONS.get(self._state, frozenset())

    def set_event_bus(self, *, event_bus: EventBus) -> None:
        """
        Set the event bus for publishing state change events.

        This is useful when the event bus is created after the state machine.

        Args:
            event_bus: The event bus to use

        """
        self._event_bus = event_bus

    def transition_to(self, *, target: CentralState, reason: str = "", force: bool = False) -> None:
        """
        Transition to a new state.

        Args:
            target: Target state to transition to
            reason: Human-readable reason for the transition
            force: If True, skip validation (use with caution)

        Raises:
            InvalidCentralStateTransitionError: If transition is not valid and force=False

        """
        if not force and not self.can_transition_to(target=target):
            raise InvalidCentralStateTransitionError(
                current=self._state,
                target=target,
                central_name=self._central_name,
            )

        old_state = self._state
        self._state = target
        self._last_state_change = datetime.now()

        # Record in history (keep last 100 transitions)
        self._state_history.append((self._last_state_change, old_state, target, reason))
        if len(self._state_history) > 100:
            self._state_history = self._state_history[-100:]

        # Log the transition
        if old_state != target:
            _LOGGER.info(  # i18n-log: ignore
                "CENTRAL_STATE: %s: %s -> %s (%s)",
                self._central_name,
                old_state.value,
                target.value,
                reason or "no reason specified",
            )

        # Call the callback
        if self.on_state_change is not None:
            try:
                self.on_state_change(old_state, target, reason)
            except Exception:
                _LOGGER.exception(  # i18n-log: ignore
                    "CENTRAL_STATE: Error in state change callback for %s",
                    self._central_name,
                )

        # Publish event to event bus
        if self._event_bus is not None:
            self._publish_state_change_event(old_state=old_state, new_state=target, reason=reason)

    def _publish_state_change_event(self, *, old_state: CentralState, new_state: CentralState, reason: str) -> None:
        """
        Publish state change event to the event bus.

        Args:
            old_state: Previous state
            new_state: New state
            reason: Reason for the transition

        """
        # Import here to avoid circular dependency
        from aiohomematic.central.integration_events import SystemStatusEvent  # noqa: PLC0415

        if self._event_bus is not None:
            self._event_bus.publish_sync(
                event=SystemStatusEvent(
                    timestamp=self._last_state_change,
                    central_state=new_state,
                )
            )
