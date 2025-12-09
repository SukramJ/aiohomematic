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

from collections.abc import Callable
import logging
from typing import Final

from aiohomematic.const import ClientState

_LOGGER: Final = logging.getLogger(__name__)

# Define valid state transitions
_VALID_TRANSITIONS: Final[dict[ClientState, frozenset[ClientState]]] = {
    ClientState.CREATED: frozenset({ClientState.INITIALIZING}),
    ClientState.INITIALIZING: frozenset({ClientState.INITIALIZED, ClientState.FAILED}),
    ClientState.INITIALIZED: frozenset({ClientState.CONNECTING}),
    ClientState.CONNECTING: frozenset({ClientState.CONNECTED, ClientState.FAILED}),
    ClientState.CONNECTED: frozenset(
        {
            ClientState.DISCONNECTED,
            ClientState.RECONNECTING,
            ClientState.STOPPING,
        }
    ),
    ClientState.DISCONNECTED: frozenset(
        {
            ClientState.CONNECTING,  # Allow re-connect after disconnect
            ClientState.DISCONNECTED,  # Allow idempotent deinitialize calls
            ClientState.RECONNECTING,
            ClientState.STOPPING,
        }
    ),
    ClientState.RECONNECTING: frozenset(
        {
            ClientState.CONNECTED,
            ClientState.DISCONNECTED,
            ClientState.FAILED,
            ClientState.CONNECTING,  # Allow transition to CONNECTING during reconnect
        }
    ),
    ClientState.STOPPING: frozenset({ClientState.STOPPED}),
    ClientState.STOPPED: frozenset(),  # Terminal state
    ClientState.FAILED: frozenset({ClientState.INITIALIZING, ClientState.CONNECTING}),  # Allow retry
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
        def on_state_change(old_state: ClientState, new_state: ClientState) -> None:
            print(f"State changed: {old_state} -> {new_state}")

        sm = ClientStateMachine(interface_id="BidCos-RF")
        sm.on_state_change = on_state_change

        sm.transition_to(ClientState.INITIALIZING)
        sm.transition_to(ClientState.INITIALIZED)
        sm.transition_to(ClientState.CONNECTING)
        sm.transition_to(ClientState.CONNECTED)

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
        self.on_state_change: Callable[[ClientState, ClientState], None] | None = None

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
                self.on_state_change(old_state, target)
            except Exception:
                _LOGGER.exception(  # i18n-log: ignore
                    "STATE_MACHINE: Error in state change callback for %s",
                    self._interface_id,
                )
