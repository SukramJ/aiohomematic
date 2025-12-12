# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Client state machine for managing connection lifecycle.

This module provides a state machine for tracking client connection states
with validated transitions and event emission.

The state machine ensures:
- Only valid state transitions occur
- State changes are logged for debugging
- Invalid transitions raise exceptions for early error detection
"""

from __future__ import annotations

import logging
from typing import Final, Protocol

from aiohomematic.const import ClientState


class StateChangeCallback(Protocol):
    """Protocol for state change callbacks."""

    def __call__(self, *, old_state: ClientState, new_state: ClientState) -> None:
        """Handle state change."""


_LOGGER: Final = logging.getLogger(__name__)

# Valid state transitions define which state changes are allowed.
# This forms a directed graph where each state maps to its valid successors.
#
# State Diagram:
#
#   CREATED ──► INITIALIZING ──► INITIALIZED ──► CONNECTING ──► CONNECTED
#                    │                               ▲              │
#                    ▼                               │              ▼
#                 FAILED ◄─────────────────────────┬┴─────── DISCONNECTED
#                    │                             │              │
#                    ├─────► INITIALIZING          │              ▼
#                    ├─────► CONNECTING ◄──────────┴──────── RECONNECTING
#                    │                                            ▲
#                    └────────────────────────────────────────────┘
#
#   STOPPED ◄── STOPPING ◄─────────────────────────(from CONNECTED/DISCONNECTED/RECONNECTING)
#
_VALID_TRANSITIONS: Final[dict[ClientState, frozenset[ClientState]]] = {
    # Initial state after client creation - can only begin initialization
    ClientState.CREATED: frozenset({ClientState.INITIALIZING}),
    # During initialization (loading metadata, etc.) - succeeds or fails
    ClientState.INITIALIZING: frozenset({ClientState.INITIALIZED, ClientState.FAILED}),
    # Initialization complete - ready to establish connection
    ClientState.INITIALIZED: frozenset({ClientState.CONNECTING}),
    # Attempting to connect to backend - succeeds or fails
    ClientState.CONNECTING: frozenset({ClientState.CONNECTED, ClientState.FAILED}),
    # Fully connected and operational
    ClientState.CONNECTED: frozenset(
        {
            ClientState.DISCONNECTED,  # Connection lost unexpectedly
            ClientState.RECONNECTING,  # Attempting automatic reconnection
            ClientState.STOPPING,  # Graceful shutdown requested
        }
    ),
    # Connection was lost or intentionally closed
    ClientState.DISCONNECTED: frozenset(
        {
            ClientState.CONNECTING,  # Manual reconnection attempt
            ClientState.DISCONNECTED,  # Idempotent - allows repeated deinitialize calls
            ClientState.RECONNECTING,  # Automatic reconnection attempt
            ClientState.STOPPING,  # Graceful shutdown requested
        }
    ),
    # Automatic reconnection in progress
    ClientState.RECONNECTING: frozenset(
        {
            ClientState.CONNECTED,  # Reconnection succeeded
            ClientState.DISCONNECTED,  # Reconnection abandoned
            ClientState.FAILED,  # Reconnection failed permanently
            ClientState.CONNECTING,  # Retry connection establishment
        }
    ),
    # Graceful shutdown in progress - one-way to STOPPED
    ClientState.STOPPING: frozenset({ClientState.STOPPED}),
    # Terminal state - client is fully stopped, no transitions allowed
    ClientState.STOPPED: frozenset(),
    # Error state - allows retry via re-initialization or reconnection
    ClientState.FAILED: frozenset({ClientState.INITIALIZING, ClientState.CONNECTING, ClientState.RECONNECTING}),
}


class InvalidStateTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""

    def __init__(self, *, current: ClientState, target: ClientState, interface_id: str) -> None:
        """Initialize the error."""
        self.current = current
        self.target = target
        self.interface_id = interface_id
        super().__init__(
            f"Invalid state transition from {current.value} to {target.value} for interface {interface_id}"
        )


class ClientStateMachine:
    """
    State machine for client connection lifecycle.

    This class manages the connection state of a client with validated
    transitions and optional callbacks on state changes.

    Thread Safety
    -------------
    This class is NOT thread-safe. All calls should happen from the same
    event loop/thread.

    Example:
    -------
        def on_state_change(*, old_state: ClientState, new_state: ClientState) -> None:
            print(f"State changed: {old_state} -> {new_state}")

        sm = ClientStateMachine(interface_id="BidCos-RF")
        sm.on_state_change = on_state_change

        sm.transition_to(target=ClientState.INITIALIZING)
        sm.transition_to(target=ClientState.INITIALIZED)
        sm.transition_to(target=ClientState.CONNECTING)
        sm.transition_to(target=ClientState.CONNECTED)

    """

    __slots__ = (
        "_interface_id",
        "_state",
        "on_state_change",
    )

    def __init__(self, *, interface_id: str) -> None:
        """
        Initialize the state machine.

        Args:
        ----
            interface_id: Interface identifier for logging

        """
        self._interface_id: Final = interface_id
        self._state: ClientState = ClientState.CREATED
        self.on_state_change: StateChangeCallback | None = None

    @property
    def can_reconnect(self) -> bool:
        """Return True if reconnection is allowed from current state."""
        return ClientState.RECONNECTING in _VALID_TRANSITIONS.get(self._state, frozenset())

    @property
    def is_available(self) -> bool:
        """Return True if client is available (connected or reconnecting)."""
        return self._state in (ClientState.CONNECTED, ClientState.RECONNECTING)

    @property
    def is_connected(self) -> bool:
        """Return True if client is in connected state."""
        return self._state == ClientState.CONNECTED

    @property
    def is_failed(self) -> bool:
        """Return True if client is in failed state."""
        return self._state == ClientState.FAILED

    @property
    def is_stopped(self) -> bool:
        """Return True if client is stopped."""
        return self._state == ClientState.STOPPED

    @property
    def state(self) -> ClientState:
        """Return the current state."""
        return self._state

    def can_transition_to(self, *, target: ClientState) -> bool:
        """
        Check if transition to target state is valid.

        Args:
        ----
            target: Target state to check

        Returns:
        -------
            True if transition is valid, False otherwise

        """
        return target in _VALID_TRANSITIONS.get(self._state, frozenset())

    def reset(self) -> None:
        """
        Reset state machine to CREATED state.

        This should only be used during testing or exceptional recovery.
        """
        old_state = self._state
        self._state = ClientState.CREATED
        _LOGGER.warning(  # i18n-log: ignore
            "STATE_MACHINE: %s: Reset from %s to CREATED",
            self._interface_id,
            old_state.value,
        )

    def transition_to(self, *, target: ClientState, force: bool = False) -> None:
        """
        Transition to a new state.

        Args:
        ----
            target: Target state to transition to
            force: If True, skip validation (use with caution)

        Raises:
        ------
            InvalidStateTransitionError: If transition is not valid and force=False

        """
        if not force and not self.can_transition_to(target=target):
            raise InvalidStateTransitionError(
                current=self._state,
                target=target,
                interface_id=self._interface_id,
            )

        old_state = self._state
        self._state = target

        _LOGGER.debug(
            "STATE_MACHINE: %s: %s -> %s",
            self._interface_id,
            old_state.value,
            target.value,
        )

        if self.on_state_change is not None:
            try:
                self.on_state_change(old_state=old_state, new_state=target)
            except Exception:
                _LOGGER.exception(  # i18n-log: ignore
                    "STATE_MACHINE: Error in state change callback for %s",
                    self._interface_id,
                )
