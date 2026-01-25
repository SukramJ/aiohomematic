# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract tests for client state machine behavior.

STABILITY GUARANTEE
-------------------
These tests define the stable API contract for the ClientStateMachine.
Any change that breaks these tests requires a MAJOR version bump.

The contract ensures that:
1. Only valid state transitions are allowed
2. Invalid transitions raise InvalidStateTransitionError
3. FAILED state captures failure information
4. CONNECTED/INITIALIZED states clear failure information
5. Events are emitted on all transitions
6. State properties return correct values

See ADR-0018 for architectural context.
"""

from __future__ import annotations

from typing import Any

import pytest

from aiohomematic.client import ClientStateMachine, InvalidStateTransitionError
from aiohomematic.client.state_machine import _VALID_TRANSITIONS
from aiohomematic.const import ClientState, FailureReason

# =============================================================================
# Test Fixtures
# =============================================================================


class _FakeEventBus:
    """Minimal fake EventBus for contract testing."""

    def __init__(self) -> None:
        self.published_events: list[Any] = []

    def publish_sync(self, *, event: Any) -> None:
        """Publish an event synchronously."""
        self.published_events.append(event)


def _create_state_machine(
    *,
    interface_id: str = "test-interface",
    with_event_bus: bool = False,
) -> tuple[ClientStateMachine, _FakeEventBus | None]:
    """Create a client state machine for testing."""
    event_bus = _FakeEventBus() if with_event_bus else None
    sm = ClientStateMachine(
        interface_id=interface_id,
        event_bus=event_bus,  # type: ignore[arg-type]
    )
    return sm, event_bus


# =============================================================================
# Contract: State Enum Stability
# =============================================================================


class TestClientStateEnumContract:
    """Contract: ClientState enum values must remain stable."""

    def test_client_state_has_connected(self) -> None:
        """Contract: ClientState.CONNECTED must exist."""
        assert hasattr(ClientState, "CONNECTED")
        assert ClientState.CONNECTED.value == "connected"

    def test_client_state_has_connecting(self) -> None:
        """Contract: ClientState.CONNECTING must exist."""
        assert hasattr(ClientState, "CONNECTING")
        assert ClientState.CONNECTING.value == "connecting"

    def test_client_state_has_created(self) -> None:
        """Contract: ClientState.CREATED must exist."""
        assert hasattr(ClientState, "CREATED")
        assert ClientState.CREATED.value == "created"

    def test_client_state_has_disconnected(self) -> None:
        """Contract: ClientState.DISCONNECTED must exist."""
        assert hasattr(ClientState, "DISCONNECTED")
        assert ClientState.DISCONNECTED.value == "disconnected"

    def test_client_state_has_failed(self) -> None:
        """Contract: ClientState.FAILED must exist."""
        assert hasattr(ClientState, "FAILED")
        assert ClientState.FAILED.value == "failed"

    def test_client_state_has_initialized(self) -> None:
        """Contract: ClientState.INITIALIZED must exist."""
        assert hasattr(ClientState, "INITIALIZED")
        assert ClientState.INITIALIZED.value == "initialized"

    def test_client_state_has_initializing(self) -> None:
        """Contract: ClientState.INITIALIZING must exist."""
        assert hasattr(ClientState, "INITIALIZING")
        assert ClientState.INITIALIZING.value == "initializing"

    def test_client_state_has_reconnecting(self) -> None:
        """Contract: ClientState.RECONNECTING must exist."""
        assert hasattr(ClientState, "RECONNECTING")
        assert ClientState.RECONNECTING.value == "reconnecting"

    def test_client_state_has_stopped(self) -> None:
        """Contract: ClientState.STOPPED must exist."""
        assert hasattr(ClientState, "STOPPED")
        assert ClientState.STOPPED.value == "stopped"

    def test_client_state_has_stopping(self) -> None:
        """Contract: ClientState.STOPPING must exist."""
        assert hasattr(ClientState, "STOPPING")
        assert ClientState.STOPPING.value == "stopping"


# =============================================================================
# Contract: Valid Transitions
# =============================================================================


class TestValidTransitionsContract:
    """Contract: Valid state transitions must succeed."""

    def test_connected_to_disconnected(self) -> None:
        """Contract: CONNECTED -> DISCONNECTED is valid."""
        sm, _ = _create_state_machine()
        sm.transition_to(target=ClientState.INITIALIZING)
        sm.transition_to(target=ClientState.INITIALIZED)
        sm.transition_to(target=ClientState.CONNECTING)
        sm.transition_to(target=ClientState.CONNECTED)
        sm.transition_to(target=ClientState.DISCONNECTED)
        assert sm.state == ClientState.DISCONNECTED

    def test_connected_to_reconnecting(self) -> None:
        """Contract: CONNECTED -> RECONNECTING is valid."""
        sm, _ = _create_state_machine()
        sm.transition_to(target=ClientState.INITIALIZING)
        sm.transition_to(target=ClientState.INITIALIZED)
        sm.transition_to(target=ClientState.CONNECTING)
        sm.transition_to(target=ClientState.CONNECTED)
        sm.transition_to(target=ClientState.RECONNECTING)
        assert sm.state == ClientState.RECONNECTING

    def test_connected_to_stopping(self) -> None:
        """Contract: CONNECTED -> STOPPING is valid."""
        sm, _ = _create_state_machine()
        sm.transition_to(target=ClientState.INITIALIZING)
        sm.transition_to(target=ClientState.INITIALIZED)
        sm.transition_to(target=ClientState.CONNECTING)
        sm.transition_to(target=ClientState.CONNECTED)
        sm.transition_to(target=ClientState.STOPPING)
        assert sm.state == ClientState.STOPPING

    def test_connecting_to_connected(self) -> None:
        """Contract: CONNECTING -> CONNECTED is valid."""
        sm, _ = _create_state_machine()
        sm.transition_to(target=ClientState.INITIALIZING)
        sm.transition_to(target=ClientState.INITIALIZED)
        sm.transition_to(target=ClientState.CONNECTING)
        sm.transition_to(target=ClientState.CONNECTED)
        assert sm.state == ClientState.CONNECTED

    def test_connecting_to_failed(self) -> None:
        """Contract: CONNECTING -> FAILED is valid."""
        sm, _ = _create_state_machine()
        sm.transition_to(target=ClientState.INITIALIZING)
        sm.transition_to(target=ClientState.INITIALIZED)
        sm.transition_to(target=ClientState.CONNECTING)
        sm.transition_to(target=ClientState.FAILED)
        assert sm.state == ClientState.FAILED

    def test_created_to_initializing(self) -> None:
        """Contract: CREATED -> INITIALIZING is valid."""
        sm, _ = _create_state_machine()
        assert sm.state == ClientState.CREATED
        sm.transition_to(target=ClientState.INITIALIZING)
        assert sm.state == ClientState.INITIALIZING

    def test_disconnected_to_connecting(self) -> None:
        """Contract: DISCONNECTED -> CONNECTING is valid (manual reconnect)."""
        sm, _ = _create_state_machine()
        sm.transition_to(target=ClientState.INITIALIZING)
        sm.transition_to(target=ClientState.INITIALIZED)
        sm.transition_to(target=ClientState.DISCONNECTED)
        sm.transition_to(target=ClientState.CONNECTING)
        assert sm.state == ClientState.CONNECTING

    def test_disconnected_to_disconnected_idempotent(self) -> None:
        """Contract: DISCONNECTED -> DISCONNECTED is valid (idempotent)."""
        sm, _ = _create_state_machine()
        sm.transition_to(target=ClientState.INITIALIZING)
        sm.transition_to(target=ClientState.INITIALIZED)
        sm.transition_to(target=ClientState.DISCONNECTED)
        sm.transition_to(target=ClientState.DISCONNECTED)
        assert sm.state == ClientState.DISCONNECTED

    def test_disconnected_to_reconnecting(self) -> None:
        """Contract: DISCONNECTED -> RECONNECTING is valid (auto reconnect)."""
        sm, _ = _create_state_machine()
        sm.transition_to(target=ClientState.INITIALIZING)
        sm.transition_to(target=ClientState.INITIALIZED)
        sm.transition_to(target=ClientState.DISCONNECTED)
        sm.transition_to(target=ClientState.RECONNECTING)
        assert sm.state == ClientState.RECONNECTING

    def test_disconnected_to_stopping(self) -> None:
        """Contract: DISCONNECTED -> STOPPING is valid."""
        sm, _ = _create_state_machine()
        sm.transition_to(target=ClientState.INITIALIZING)
        sm.transition_to(target=ClientState.INITIALIZED)
        sm.transition_to(target=ClientState.DISCONNECTED)
        sm.transition_to(target=ClientState.STOPPING)
        assert sm.state == ClientState.STOPPING

    def test_failed_to_connecting(self) -> None:
        """Contract: FAILED -> CONNECTING is valid (retry connect)."""
        sm, _ = _create_state_machine()
        sm.transition_to(target=ClientState.INITIALIZING)
        sm.transition_to(target=ClientState.FAILED)
        sm.transition_to(target=ClientState.CONNECTING)
        assert sm.state == ClientState.CONNECTING

    def test_failed_to_disconnected(self) -> None:
        """Contract: FAILED -> DISCONNECTED is valid (graceful shutdown)."""
        sm, _ = _create_state_machine()
        sm.transition_to(target=ClientState.INITIALIZING)
        sm.transition_to(target=ClientState.FAILED)
        sm.transition_to(target=ClientState.DISCONNECTED)
        assert sm.state == ClientState.DISCONNECTED

    def test_failed_to_initializing(self) -> None:
        """Contract: FAILED -> INITIALIZING is valid (retry init)."""
        sm, _ = _create_state_machine()
        sm.transition_to(target=ClientState.INITIALIZING)
        sm.transition_to(target=ClientState.FAILED)
        sm.transition_to(target=ClientState.INITIALIZING)
        assert sm.state == ClientState.INITIALIZING

    def test_failed_to_reconnecting(self) -> None:
        """Contract: FAILED -> RECONNECTING is valid (auto retry)."""
        sm, _ = _create_state_machine()
        sm.transition_to(target=ClientState.INITIALIZING)
        sm.transition_to(target=ClientState.FAILED)
        sm.transition_to(target=ClientState.RECONNECTING)
        assert sm.state == ClientState.RECONNECTING

    def test_initialized_to_connecting(self) -> None:
        """Contract: INITIALIZED -> CONNECTING is valid."""
        sm, _ = _create_state_machine()
        sm.transition_to(target=ClientState.INITIALIZING)
        sm.transition_to(target=ClientState.INITIALIZED)
        sm.transition_to(target=ClientState.CONNECTING)
        assert sm.state == ClientState.CONNECTING

    def test_initialized_to_disconnected(self) -> None:
        """Contract: INITIALIZED -> DISCONNECTED is valid (for recovery reset)."""
        sm, _ = _create_state_machine()
        sm.transition_to(target=ClientState.INITIALIZING)
        sm.transition_to(target=ClientState.INITIALIZED)
        sm.transition_to(target=ClientState.DISCONNECTED)
        assert sm.state == ClientState.DISCONNECTED

    def test_initializing_to_failed(self) -> None:
        """Contract: INITIALIZING -> FAILED is valid."""
        sm, _ = _create_state_machine()
        sm.transition_to(target=ClientState.INITIALIZING)
        sm.transition_to(target=ClientState.FAILED)
        assert sm.state == ClientState.FAILED

    def test_initializing_to_initialized(self) -> None:
        """Contract: INITIALIZING -> INITIALIZED is valid."""
        sm, _ = _create_state_machine()
        sm.transition_to(target=ClientState.INITIALIZING)
        sm.transition_to(target=ClientState.INITIALIZED)
        assert sm.state == ClientState.INITIALIZED

    def test_reconnecting_to_connected(self) -> None:
        """Contract: RECONNECTING -> CONNECTED is valid."""
        sm, _ = _create_state_machine()
        sm.transition_to(target=ClientState.INITIALIZING)
        sm.transition_to(target=ClientState.INITIALIZED)
        sm.transition_to(target=ClientState.CONNECTING)
        sm.transition_to(target=ClientState.CONNECTED)
        sm.transition_to(target=ClientState.RECONNECTING)
        sm.transition_to(target=ClientState.CONNECTED)
        assert sm.state == ClientState.CONNECTED

    def test_reconnecting_to_connecting(self) -> None:
        """Contract: RECONNECTING -> CONNECTING is valid (retry)."""
        sm, _ = _create_state_machine()
        sm.transition_to(target=ClientState.INITIALIZING)
        sm.transition_to(target=ClientState.INITIALIZED)
        sm.transition_to(target=ClientState.CONNECTING)
        sm.transition_to(target=ClientState.CONNECTED)
        sm.transition_to(target=ClientState.RECONNECTING)
        sm.transition_to(target=ClientState.CONNECTING)
        assert sm.state == ClientState.CONNECTING

    def test_reconnecting_to_disconnected(self) -> None:
        """Contract: RECONNECTING -> DISCONNECTED is valid."""
        sm, _ = _create_state_machine()
        sm.transition_to(target=ClientState.INITIALIZING)
        sm.transition_to(target=ClientState.INITIALIZED)
        sm.transition_to(target=ClientState.CONNECTING)
        sm.transition_to(target=ClientState.CONNECTED)
        sm.transition_to(target=ClientState.RECONNECTING)
        sm.transition_to(target=ClientState.DISCONNECTED)
        assert sm.state == ClientState.DISCONNECTED

    def test_reconnecting_to_failed(self) -> None:
        """Contract: RECONNECTING -> FAILED is valid."""
        sm, _ = _create_state_machine()
        sm.transition_to(target=ClientState.INITIALIZING)
        sm.transition_to(target=ClientState.INITIALIZED)
        sm.transition_to(target=ClientState.CONNECTING)
        sm.transition_to(target=ClientState.CONNECTED)
        sm.transition_to(target=ClientState.RECONNECTING)
        sm.transition_to(target=ClientState.FAILED)
        assert sm.state == ClientState.FAILED

    def test_stopping_to_stopped(self) -> None:
        """Contract: STOPPING -> STOPPED is valid."""
        sm, _ = _create_state_machine()
        sm.transition_to(target=ClientState.INITIALIZING)
        sm.transition_to(target=ClientState.INITIALIZED)
        sm.transition_to(target=ClientState.CONNECTING)
        sm.transition_to(target=ClientState.CONNECTED)
        sm.transition_to(target=ClientState.STOPPING)
        sm.transition_to(target=ClientState.STOPPED)
        assert sm.state == ClientState.STOPPED


# =============================================================================
# Contract: Invalid Transitions
# =============================================================================


class TestInvalidTransitionsContract:
    """Contract: Invalid state transitions must raise InvalidStateTransitionError."""

    def test_connected_to_created_is_invalid(self) -> None:
        """Contract: CONNECTED -> CREATED is invalid."""
        sm, _ = _create_state_machine()
        sm.transition_to(target=ClientState.INITIALIZING)
        sm.transition_to(target=ClientState.INITIALIZED)
        sm.transition_to(target=ClientState.CONNECTING)
        sm.transition_to(target=ClientState.CONNECTED)
        with pytest.raises(InvalidStateTransitionError):
            sm.transition_to(target=ClientState.CREATED)

    def test_created_to_connected_is_invalid(self) -> None:
        """Contract: CREATED -> CONNECTED is invalid."""
        sm, _ = _create_state_machine()
        with pytest.raises(InvalidStateTransitionError) as exc_info:
            sm.transition_to(target=ClientState.CONNECTED)
        assert exc_info.value.current == ClientState.CREATED
        assert exc_info.value.target == ClientState.CONNECTED

    def test_created_to_stopping_is_invalid(self) -> None:
        """Contract: CREATED -> STOPPING is invalid."""
        sm, _ = _create_state_machine()
        with pytest.raises(InvalidStateTransitionError):
            sm.transition_to(target=ClientState.STOPPING)

    def test_initializing_to_connected_is_invalid(self) -> None:
        """Contract: INITIALIZING -> CONNECTED is invalid (must go through INITIALIZED)."""
        sm, _ = _create_state_machine()
        sm.transition_to(target=ClientState.INITIALIZING)
        with pytest.raises(InvalidStateTransitionError):
            sm.transition_to(target=ClientState.CONNECTED)

    def test_stopped_to_any_is_invalid(self) -> None:
        """Contract: STOPPED -> any state is invalid (terminal state)."""
        sm, _ = _create_state_machine()
        sm.transition_to(target=ClientState.INITIALIZING)
        sm.transition_to(target=ClientState.INITIALIZED)
        sm.transition_to(target=ClientState.CONNECTING)
        sm.transition_to(target=ClientState.CONNECTED)
        sm.transition_to(target=ClientState.STOPPING)
        sm.transition_to(target=ClientState.STOPPED)

        for state in ClientState:
            if state != ClientState.STOPPED:
                with pytest.raises(InvalidStateTransitionError):
                    sm.transition_to(target=state)

    def test_stopping_to_reconnecting_is_invalid(self) -> None:
        """Contract: STOPPING -> RECONNECTING is invalid."""
        sm, _ = _create_state_machine()
        sm.transition_to(target=ClientState.INITIALIZING)
        sm.transition_to(target=ClientState.INITIALIZED)
        sm.transition_to(target=ClientState.CONNECTING)
        sm.transition_to(target=ClientState.CONNECTED)
        sm.transition_to(target=ClientState.STOPPING)
        with pytest.raises(InvalidStateTransitionError):
            sm.transition_to(target=ClientState.RECONNECTING)


# =============================================================================
# Contract: Failure State Tracking
# =============================================================================


class TestFailureStateTrackingContract:
    """Contract: FAILED state must track failure information."""

    def test_all_failure_reasons_can_be_tracked(self) -> None:
        """Contract: All FailureReason enum values can be tracked."""
        for reason in FailureReason:
            sm, _ = _create_state_machine()
            sm.transition_to(target=ClientState.INITIALIZING)
            sm.transition_to(
                target=ClientState.FAILED,
                reason=f"Test {reason.value}",
                failure_reason=reason,
            )
            assert sm.failure_reason == reason

    def test_connected_clears_failure_info(self) -> None:
        """Contract: Entering CONNECTED state clears failure information."""
        sm, _ = _create_state_machine()
        sm.transition_to(target=ClientState.INITIALIZING)
        sm.transition_to(
            target=ClientState.FAILED,
            reason="Timeout",
            failure_reason=FailureReason.TIMEOUT,
        )
        assert sm.failure_reason == FailureReason.TIMEOUT

        # Recover from failed state
        sm.transition_to(target=ClientState.CONNECTING)
        sm.transition_to(target=ClientState.CONNECTED)

        assert sm.failure_reason == FailureReason.NONE
        assert sm.failure_message == ""

    def test_failed_captures_failure_message(self) -> None:
        """Contract: Entering FAILED state captures failure_message."""
        sm, _ = _create_state_machine()
        sm.transition_to(target=ClientState.INITIALIZING)
        sm.transition_to(
            target=ClientState.FAILED,
            reason="Authentication failed",
            failure_reason=FailureReason.AUTH,
        )
        assert sm.failure_message == "Authentication failed"

    def test_failed_captures_failure_reason(self) -> None:
        """Contract: Entering FAILED state captures failure_reason."""
        sm, _ = _create_state_machine()
        sm.transition_to(target=ClientState.INITIALIZING)
        sm.transition_to(
            target=ClientState.FAILED,
            reason="Network error",
            failure_reason=FailureReason.NETWORK,
        )
        assert sm.failure_reason == FailureReason.NETWORK

    def test_initialized_clears_failure_info(self) -> None:
        """Contract: Entering INITIALIZED state clears failure information."""
        sm, _ = _create_state_machine()
        sm.transition_to(target=ClientState.INITIALIZING)
        sm.transition_to(
            target=ClientState.FAILED,
            reason="Internal error",
            failure_reason=FailureReason.INTERNAL,
        )

        # Retry init from failed state
        sm.transition_to(target=ClientState.INITIALIZING)
        sm.transition_to(target=ClientState.INITIALIZED)

        assert sm.failure_reason == FailureReason.NONE
        assert sm.failure_message == ""


# =============================================================================
# Contract: State Properties
# =============================================================================


class TestStatePropertiesContract:
    """Contract: State property accessors must return correct values."""

    def test_can_reconnect_checks_valid_transitions(self) -> None:
        """Contract: can_reconnect returns True if RECONNECTING is a valid transition."""
        sm, _ = _create_state_machine()

        for state in ClientState:
            sm.reset()
            sm._state = state

            # Check against the actual transition table
            valid_targets = _VALID_TRANSITIONS.get(state, frozenset())
            expected = ClientState.RECONNECTING in valid_targets
            assert sm.can_reconnect == expected, f"can_reconnect mismatch for {state}"

    def test_can_transition_to_checks_valid_transitions(self) -> None:
        """Contract: can_transition_to returns True if target is in valid transitions."""
        sm, _ = _create_state_machine()

        for state in ClientState:
            sm.reset()
            sm._state = state
            valid_targets = _VALID_TRANSITIONS.get(state, frozenset())

            for target in ClientState:
                expected = target in valid_targets
                actual = sm.can_transition_to(target=target)
                assert actual == expected, f"can_transition_to({state} -> {target}) mismatch"

    def test_is_available_true_for_connected_and_reconnecting(self) -> None:
        """Contract: is_available returns True for CONNECTED and RECONNECTING."""
        sm, _ = _create_state_machine()

        for state in ClientState:
            sm.reset()
            sm._state = state

            if state in (ClientState.CONNECTED, ClientState.RECONNECTING):
                assert sm.is_available is True, f"is_available should be True for {state}"
            else:
                assert sm.is_available is False, f"is_available should be False for {state}"

    def test_is_connected_true_only_when_connected(self) -> None:
        """Contract: is_connected returns True only when state == CONNECTED."""
        sm, _ = _create_state_machine()

        for state in ClientState:
            sm.reset()
            sm._state = state  # Direct state set for testing

            if state == ClientState.CONNECTED:
                assert sm.is_connected is True, f"is_connected should be True for {state}"
            else:
                assert sm.is_connected is False, f"is_connected should be False for {state}"

    def test_is_failed_true_only_when_failed(self) -> None:
        """Contract: is_failed returns True only when state == FAILED."""
        sm, _ = _create_state_machine()

        for state in ClientState:
            sm.reset()
            sm._state = state

            if state == ClientState.FAILED:
                assert sm.is_failed is True, f"is_failed should be True for {state}"
            else:
                assert sm.is_failed is False, f"is_failed should be False for {state}"

    def test_is_stopped_true_only_when_stopped(self) -> None:
        """Contract: is_stopped returns True only when state == STOPPED."""
        sm, _ = _create_state_machine()

        for state in ClientState:
            sm.reset()
            sm._state = state

            if state == ClientState.STOPPED:
                assert sm.is_stopped is True, f"is_stopped should be True for {state}"
            else:
                assert sm.is_stopped is False, f"is_stopped should be False for {state}"


# =============================================================================
# Contract: Event Emission
# =============================================================================


class TestEventEmissionContract:
    """Contract: Events must be emitted on state transitions."""

    def test_event_includes_trigger_reason(self) -> None:
        """Contract: Event includes trigger reason when provided."""
        from aiohomematic.central.events import ClientStateChangedEvent

        sm, event_bus = _create_state_machine(with_event_bus=True)
        assert event_bus is not None

        sm.transition_to(target=ClientState.INITIALIZING, reason="test reason")

        event = event_bus.published_events[0]
        assert isinstance(event, ClientStateChangedEvent)
        assert event.trigger == "test reason"

    def test_multiple_transitions_emit_multiple_events(self) -> None:
        """Contract: Multiple transitions emit multiple events."""
        from aiohomematic.central.events import ClientStateChangedEvent

        sm, event_bus = _create_state_machine(with_event_bus=True)
        assert event_bus is not None

        sm.transition_to(target=ClientState.INITIALIZING)
        sm.transition_to(target=ClientState.INITIALIZED)
        sm.transition_to(target=ClientState.CONNECTING)
        sm.transition_to(target=ClientState.CONNECTED)

        assert len(event_bus.published_events) == 4

        # Verify event sequence
        expected_sequence = [
            (ClientState.CREATED, ClientState.INITIALIZING),
            (ClientState.INITIALIZING, ClientState.INITIALIZED),
            (ClientState.INITIALIZED, ClientState.CONNECTING),
            (ClientState.CONNECTING, ClientState.CONNECTED),
        ]

        for i, (old_state, new_state) in enumerate(expected_sequence):
            event = event_bus.published_events[i]
            assert isinstance(event, ClientStateChangedEvent)
            assert event.old_state == old_state
            assert event.new_state == new_state

    def test_no_event_without_event_bus(self) -> None:
        """Contract: No exception when event_bus is None."""
        sm, event_bus = _create_state_machine(with_event_bus=False)
        assert event_bus is None

        # Should not raise
        sm.transition_to(target=ClientState.INITIALIZING)
        sm.transition_to(target=ClientState.INITIALIZED)

    def test_transition_emits_client_state_changed_event(self) -> None:
        """Contract: Every transition emits ClientStateChangedEvent."""
        from aiohomematic.central.events import ClientStateChangedEvent

        sm, event_bus = _create_state_machine(with_event_bus=True)
        assert event_bus is not None

        sm.transition_to(target=ClientState.INITIALIZING)

        assert len(event_bus.published_events) == 1
        event = event_bus.published_events[0]
        assert isinstance(event, ClientStateChangedEvent)
        assert event.old_state == ClientState.CREATED
        assert event.new_state == ClientState.INITIALIZING


# =============================================================================
# Contract: Force Transition
# =============================================================================


class TestForceTransitionContract:
    """Contract: Force flag bypasses transition validation."""

    def test_force_allows_invalid_transition(self) -> None:
        """Contract: force=True allows normally invalid transitions."""
        sm, _ = _create_state_machine()

        # CREATED -> CONNECTED is normally invalid
        with pytest.raises(InvalidStateTransitionError):
            sm.transition_to(target=ClientState.CONNECTED)

        # But force=True allows it
        sm.transition_to(target=ClientState.CONNECTED, force=True)
        assert sm.state == ClientState.CONNECTED

    def test_reset_returns_to_created(self) -> None:
        """Contract: reset() returns state machine to CREATED state."""
        sm, _ = _create_state_machine()
        sm.transition_to(target=ClientState.INITIALIZING)
        sm.transition_to(target=ClientState.INITIALIZED)
        sm.transition_to(target=ClientState.CONNECTING)
        sm.transition_to(target=ClientState.CONNECTED)

        sm.reset()

        assert sm.state == ClientState.CREATED
        assert sm.failure_reason == FailureReason.NONE
        assert sm.failure_message == ""


# =============================================================================
# Contract: Transition Table Completeness
# =============================================================================


class TestTransitionTableCompletenessContract:
    """Contract: Transition table must cover all states."""

    def test_all_states_have_transition_entries(self) -> None:
        """Contract: Every ClientState has an entry in _VALID_TRANSITIONS."""
        for state in ClientState:
            assert state in _VALID_TRANSITIONS, f"Missing transition entry for {state}"

    def test_stopped_has_no_transitions(self) -> None:
        """Contract: STOPPED is terminal - no valid transitions."""
        assert _VALID_TRANSITIONS[ClientState.STOPPED] == frozenset()

    def test_transition_targets_are_valid_states(self) -> None:
        """Contract: All transition targets are valid ClientState values."""
        for source, targets in _VALID_TRANSITIONS.items():
            for target in targets:
                assert target in ClientState, f"Invalid target {target} from {source}"
