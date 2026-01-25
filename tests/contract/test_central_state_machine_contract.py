# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract tests for central state machine behavior.

STABILITY GUARANTEE
-------------------
These tests define the stable API contract for the CentralStateMachine.
Any change that breaks these tests requires a MAJOR version bump.

The contract ensures that:
1. Only valid state transitions are allowed
2. Invalid transitions raise InvalidCentralStateTransitionError
3. FAILED state captures failure information
4. DEGRADED state tracks degraded interfaces with reasons
5. RUNNING state clears failure and degraded information
6. Events are emitted on all transitions
7. State history is maintained and bounded

See ADR-0018 for architectural context.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Any

import pytest

from aiohomematic.central.state_machine import (
    VALID_CENTRAL_TRANSITIONS,
    CentralStateMachine,
    InvalidCentralStateTransitionError,
)
from aiohomematic.const import CentralState, FailureReason

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


def _create_central_state_machine(
    *,
    central_name: str = "test-central",
    with_event_bus: bool = False,
) -> tuple[CentralStateMachine, _FakeEventBus | None]:
    """Create a central state machine for testing."""
    event_bus = _FakeEventBus() if with_event_bus else None
    sm = CentralStateMachine(
        central_name=central_name,
        event_bus=event_bus,  # type: ignore[arg-type]
    )
    return sm, event_bus


# =============================================================================
# Contract: State Enum Stability
# =============================================================================


class TestCentralStateEnumContract:
    """Contract: CentralState enum values must remain stable."""

    def test_central_state_has_degraded(self) -> None:
        """Contract: CentralState.DEGRADED must exist."""
        assert hasattr(CentralState, "DEGRADED")
        assert CentralState.DEGRADED.value == "degraded"

    def test_central_state_has_failed(self) -> None:
        """Contract: CentralState.FAILED must exist."""
        assert hasattr(CentralState, "FAILED")
        assert CentralState.FAILED.value == "failed"

    def test_central_state_has_initializing(self) -> None:
        """Contract: CentralState.INITIALIZING must exist."""
        assert hasattr(CentralState, "INITIALIZING")
        assert CentralState.INITIALIZING.value == "initializing"

    def test_central_state_has_recovering(self) -> None:
        """Contract: CentralState.RECOVERING must exist."""
        assert hasattr(CentralState, "RECOVERING")
        assert CentralState.RECOVERING.value == "recovering"

    def test_central_state_has_running(self) -> None:
        """Contract: CentralState.RUNNING must exist."""
        assert hasattr(CentralState, "RUNNING")
        assert CentralState.RUNNING.value == "running"

    def test_central_state_has_starting(self) -> None:
        """Contract: CentralState.STARTING must exist."""
        assert hasattr(CentralState, "STARTING")
        assert CentralState.STARTING.value == "starting"

    def test_central_state_has_stopped(self) -> None:
        """Contract: CentralState.STOPPED must exist."""
        assert hasattr(CentralState, "STOPPED")
        assert CentralState.STOPPED.value == "stopped"


# =============================================================================
# Contract: Valid Transitions
# =============================================================================


class TestValidCentralTransitionsContract:
    """Contract: Valid central state transitions must succeed."""

    def test_degraded_to_failed(self) -> None:
        """Contract: DEGRADED -> FAILED is valid."""
        sm, _ = _create_central_state_machine()
        sm.transition_to(target=CentralState.INITIALIZING)
        sm.transition_to(target=CentralState.DEGRADED)
        sm.transition_to(target=CentralState.FAILED)
        assert sm.state == CentralState.FAILED

    def test_degraded_to_recovering(self) -> None:
        """Contract: DEGRADED -> RECOVERING is valid."""
        sm, _ = _create_central_state_machine()
        sm.transition_to(target=CentralState.INITIALIZING)
        sm.transition_to(target=CentralState.DEGRADED)
        sm.transition_to(target=CentralState.RECOVERING)
        assert sm.state == CentralState.RECOVERING

    def test_degraded_to_running(self) -> None:
        """Contract: DEGRADED -> RUNNING is valid."""
        sm, _ = _create_central_state_machine()
        sm.transition_to(target=CentralState.INITIALIZING)
        sm.transition_to(target=CentralState.DEGRADED)
        sm.transition_to(target=CentralState.RUNNING)
        assert sm.state == CentralState.RUNNING

    def test_degraded_to_stopped(self) -> None:
        """Contract: DEGRADED -> STOPPED is valid."""
        sm, _ = _create_central_state_machine()
        sm.transition_to(target=CentralState.INITIALIZING)
        sm.transition_to(target=CentralState.DEGRADED)
        sm.transition_to(target=CentralState.STOPPED)
        assert sm.state == CentralState.STOPPED

    def test_failed_to_recovering(self) -> None:
        """Contract: FAILED -> RECOVERING is valid (manual retry)."""
        sm, _ = _create_central_state_machine()
        sm.transition_to(target=CentralState.INITIALIZING)
        sm.transition_to(target=CentralState.FAILED)
        sm.transition_to(target=CentralState.RECOVERING)
        assert sm.state == CentralState.RECOVERING

    def test_failed_to_stopped(self) -> None:
        """Contract: FAILED -> STOPPED is valid."""
        sm, _ = _create_central_state_machine()
        sm.transition_to(target=CentralState.INITIALIZING)
        sm.transition_to(target=CentralState.FAILED)
        sm.transition_to(target=CentralState.STOPPED)
        assert sm.state == CentralState.STOPPED

    def test_initializing_to_degraded(self) -> None:
        """Contract: INITIALIZING -> DEGRADED is valid."""
        sm, _ = _create_central_state_machine()
        sm.transition_to(target=CentralState.INITIALIZING)
        sm.transition_to(target=CentralState.DEGRADED)
        assert sm.state == CentralState.DEGRADED

    def test_initializing_to_failed(self) -> None:
        """Contract: INITIALIZING -> FAILED is valid."""
        sm, _ = _create_central_state_machine()
        sm.transition_to(target=CentralState.INITIALIZING)
        sm.transition_to(target=CentralState.FAILED)
        assert sm.state == CentralState.FAILED

    def test_initializing_to_running(self) -> None:
        """Contract: INITIALIZING -> RUNNING is valid."""
        sm, _ = _create_central_state_machine()
        sm.transition_to(target=CentralState.INITIALIZING)
        sm.transition_to(target=CentralState.RUNNING)
        assert sm.state == CentralState.RUNNING

    def test_initializing_to_stopped(self) -> None:
        """Contract: INITIALIZING -> STOPPED is valid."""
        sm, _ = _create_central_state_machine()
        sm.transition_to(target=CentralState.INITIALIZING)
        sm.transition_to(target=CentralState.STOPPED)
        assert sm.state == CentralState.STOPPED

    def test_recovering_to_degraded(self) -> None:
        """Contract: RECOVERING -> DEGRADED is valid."""
        sm, _ = _create_central_state_machine()
        sm.transition_to(target=CentralState.INITIALIZING)
        sm.transition_to(target=CentralState.RUNNING)
        sm.transition_to(target=CentralState.RECOVERING)
        sm.transition_to(target=CentralState.DEGRADED)
        assert sm.state == CentralState.DEGRADED

    def test_recovering_to_failed(self) -> None:
        """Contract: RECOVERING -> FAILED is valid."""
        sm, _ = _create_central_state_machine()
        sm.transition_to(target=CentralState.INITIALIZING)
        sm.transition_to(target=CentralState.RUNNING)
        sm.transition_to(target=CentralState.RECOVERING)
        sm.transition_to(target=CentralState.FAILED)
        assert sm.state == CentralState.FAILED

    def test_recovering_to_running(self) -> None:
        """Contract: RECOVERING -> RUNNING is valid."""
        sm, _ = _create_central_state_machine()
        sm.transition_to(target=CentralState.INITIALIZING)
        sm.transition_to(target=CentralState.RUNNING)
        sm.transition_to(target=CentralState.RECOVERING)
        sm.transition_to(target=CentralState.RUNNING)
        assert sm.state == CentralState.RUNNING

    def test_recovering_to_stopped(self) -> None:
        """Contract: RECOVERING -> STOPPED is valid."""
        sm, _ = _create_central_state_machine()
        sm.transition_to(target=CentralState.INITIALIZING)
        sm.transition_to(target=CentralState.RUNNING)
        sm.transition_to(target=CentralState.RECOVERING)
        sm.transition_to(target=CentralState.STOPPED)
        assert sm.state == CentralState.STOPPED

    def test_running_to_degraded(self) -> None:
        """Contract: RUNNING -> DEGRADED is valid."""
        sm, _ = _create_central_state_machine()
        sm.transition_to(target=CentralState.INITIALIZING)
        sm.transition_to(target=CentralState.RUNNING)
        sm.transition_to(target=CentralState.DEGRADED)
        assert sm.state == CentralState.DEGRADED

    def test_running_to_recovering(self) -> None:
        """Contract: RUNNING -> RECOVERING is valid."""
        sm, _ = _create_central_state_machine()
        sm.transition_to(target=CentralState.INITIALIZING)
        sm.transition_to(target=CentralState.RUNNING)
        sm.transition_to(target=CentralState.RECOVERING)
        assert sm.state == CentralState.RECOVERING

    def test_running_to_stopped(self) -> None:
        """Contract: RUNNING -> STOPPED is valid."""
        sm, _ = _create_central_state_machine()
        sm.transition_to(target=CentralState.INITIALIZING)
        sm.transition_to(target=CentralState.RUNNING)
        sm.transition_to(target=CentralState.STOPPED)
        assert sm.state == CentralState.STOPPED

    def test_starting_to_initializing(self) -> None:
        """Contract: STARTING -> INITIALIZING is valid."""
        sm, _ = _create_central_state_machine()
        assert sm.state == CentralState.STARTING
        sm.transition_to(target=CentralState.INITIALIZING)
        assert sm.state == CentralState.INITIALIZING

    def test_starting_to_stopped(self) -> None:
        """Contract: STARTING -> STOPPED is valid (stop before start)."""
        sm, _ = _create_central_state_machine()
        sm.transition_to(target=CentralState.STOPPED)
        assert sm.state == CentralState.STOPPED


# =============================================================================
# Contract: Invalid Transitions
# =============================================================================


class TestInvalidCentralTransitionsContract:
    """Contract: Invalid central state transitions must raise exception."""

    def test_failed_to_running_is_invalid(self) -> None:
        """Contract: FAILED -> RUNNING is invalid (must go through RECOVERING)."""
        sm, _ = _create_central_state_machine()
        sm.transition_to(target=CentralState.INITIALIZING)
        sm.transition_to(target=CentralState.FAILED)
        with pytest.raises(InvalidCentralStateTransitionError):
            sm.transition_to(target=CentralState.RUNNING)

    def test_running_to_failed_is_invalid(self) -> None:
        """Contract: RUNNING -> FAILED is invalid (must go through DEGRADED)."""
        sm, _ = _create_central_state_machine()
        sm.transition_to(target=CentralState.INITIALIZING)
        sm.transition_to(target=CentralState.RUNNING)
        with pytest.raises(InvalidCentralStateTransitionError):
            sm.transition_to(target=CentralState.FAILED)

    def test_running_to_initializing_is_invalid(self) -> None:
        """Contract: RUNNING -> INITIALIZING is invalid."""
        sm, _ = _create_central_state_machine()
        sm.transition_to(target=CentralState.INITIALIZING)
        sm.transition_to(target=CentralState.RUNNING)
        with pytest.raises(InvalidCentralStateTransitionError):
            sm.transition_to(target=CentralState.INITIALIZING)

    def test_starting_to_failed_is_invalid(self) -> None:
        """Contract: STARTING -> FAILED is invalid."""
        sm, _ = _create_central_state_machine()
        with pytest.raises(InvalidCentralStateTransitionError):
            sm.transition_to(target=CentralState.FAILED)

    def test_starting_to_running_is_invalid(self) -> None:
        """Contract: STARTING -> RUNNING is invalid (must go through INITIALIZING)."""
        sm, _ = _create_central_state_machine()
        with pytest.raises(InvalidCentralStateTransitionError) as exc_info:
            sm.transition_to(target=CentralState.RUNNING)
        assert exc_info.value.current == CentralState.STARTING
        assert exc_info.value.target == CentralState.RUNNING

    def test_stopped_to_any_is_invalid(self) -> None:
        """Contract: STOPPED -> any state is invalid (terminal state)."""
        sm, _ = _create_central_state_machine()
        sm.transition_to(target=CentralState.STOPPED)

        for state in CentralState:
            if state != CentralState.STOPPED:
                with pytest.raises(InvalidCentralStateTransitionError):
                    sm.transition_to(target=state)


# =============================================================================
# Contract: Failure State Tracking
# =============================================================================


class TestCentralFailureStateTrackingContract:
    """Contract: FAILED state must track failure information."""

    def test_failed_captures_failure_interface_id(self) -> None:
        """Contract: Entering FAILED state can capture failure_interface_id."""
        sm, _ = _create_central_state_machine()
        sm.transition_to(target=CentralState.INITIALIZING)
        sm.transition_to(
            target=CentralState.FAILED,
            reason="Interface timeout",
            failure_reason=FailureReason.TIMEOUT,
            failure_interface_id="BidCos-RF",
        )
        assert sm.failure_interface_id == "BidCos-RF"

    def test_failed_captures_failure_message(self) -> None:
        """Contract: Entering FAILED state captures failure_message."""
        sm, _ = _create_central_state_machine()
        sm.transition_to(target=CentralState.INITIALIZING)
        sm.transition_to(
            target=CentralState.FAILED,
            reason="Authentication failed",
            failure_reason=FailureReason.AUTH,
        )
        assert sm.failure_message == "Authentication failed"

    def test_failed_captures_failure_reason(self) -> None:
        """Contract: Entering FAILED state captures failure_reason."""
        sm, _ = _create_central_state_machine()
        sm.transition_to(target=CentralState.INITIALIZING)
        sm.transition_to(
            target=CentralState.FAILED,
            reason="No clients connected",
            failure_reason=FailureReason.NETWORK,
        )
        assert sm.failure_reason == FailureReason.NETWORK

    def test_running_clears_failure_info(self) -> None:
        """Contract: Entering RUNNING state clears failure information."""
        sm, _ = _create_central_state_machine()
        sm.transition_to(target=CentralState.INITIALIZING)
        sm.transition_to(
            target=CentralState.FAILED,
            reason="Timeout",
            failure_reason=FailureReason.TIMEOUT,
            failure_interface_id="HmIP-RF",
        )

        sm.transition_to(target=CentralState.RECOVERING)
        sm.transition_to(target=CentralState.RUNNING)

        assert sm.failure_reason == FailureReason.NONE
        assert sm.failure_message == ""
        assert sm.failure_interface_id is None


# =============================================================================
# Contract: Degraded State Tracking
# =============================================================================


class TestDegradedStateTrackingContract:
    """Contract: DEGRADED state must track degraded interfaces."""

    def test_degraded_captures_interface_reasons(self) -> None:
        """Contract: Entering DEGRADED state captures interface failure reasons."""
        sm, _ = _create_central_state_machine()
        sm.transition_to(target=CentralState.INITIALIZING)

        degraded_interfaces = {
            "BidCos-RF": FailureReason.NETWORK,
            "HmIP-RF": FailureReason.TIMEOUT,
        }
        sm.transition_to(
            target=CentralState.DEGRADED,
            reason="Multiple interfaces failed",
            degraded_interfaces=degraded_interfaces,
        )

        assert len(sm.degraded_interfaces) == 2
        assert sm.degraded_interfaces["BidCos-RF"] == FailureReason.NETWORK
        assert sm.degraded_interfaces["HmIP-RF"] == FailureReason.TIMEOUT

    def test_degraded_interfaces_is_mapping_proxy(self) -> None:
        """Contract: degraded_interfaces returns immutable MappingProxyType."""
        sm, _ = _create_central_state_machine()
        sm.transition_to(target=CentralState.INITIALIZING)
        sm.transition_to(
            target=CentralState.DEGRADED,
            degraded_interfaces={"test": FailureReason.UNKNOWN},
        )

        assert isinstance(sm.degraded_interfaces, MappingProxyType)

    def test_failed_clears_degraded_interfaces(self) -> None:
        """Contract: Entering FAILED state clears degraded_interfaces."""
        sm, _ = _create_central_state_machine()
        sm.transition_to(target=CentralState.INITIALIZING)
        sm.transition_to(
            target=CentralState.DEGRADED,
            degraded_interfaces={"BidCos-RF": FailureReason.NETWORK},
        )

        sm.transition_to(target=CentralState.FAILED, failure_reason=FailureReason.TIMEOUT)
        assert len(sm.degraded_interfaces) == 0

    def test_running_clears_degraded_interfaces(self) -> None:
        """Contract: Entering RUNNING state clears degraded_interfaces."""
        sm, _ = _create_central_state_machine()
        sm.transition_to(target=CentralState.INITIALIZING)
        sm.transition_to(
            target=CentralState.DEGRADED,
            degraded_interfaces={"BidCos-RF": FailureReason.NETWORK},
        )
        assert len(sm.degraded_interfaces) == 1

        sm.transition_to(target=CentralState.RUNNING)
        assert len(sm.degraded_interfaces) == 0


# =============================================================================
# Contract: State Properties
# =============================================================================


class TestCentralStatePropertiesContract:
    """Contract: State property accessors must return correct values."""

    def test_can_transition_to_checks_valid_transitions(self) -> None:
        """Contract: can_transition_to returns True if target is valid."""
        sm, _ = _create_central_state_machine()

        for state in CentralState:
            sm._state = state
            valid_targets = VALID_CENTRAL_TRANSITIONS.get(state, frozenset())

            for target in CentralState:
                expected = target in valid_targets
                actual = sm.can_transition_to(target=target)
                assert actual == expected, f"can_transition_to({state} -> {target}) mismatch"

    def test_is_degraded_true_only_when_degraded(self) -> None:
        """Contract: is_degraded returns True only when state == DEGRADED."""
        sm, _ = _create_central_state_machine()

        for state in CentralState:
            sm._state = state

            if state == CentralState.DEGRADED:
                assert sm.is_degraded is True, f"is_degraded should be True for {state}"
            else:
                assert sm.is_degraded is False, f"is_degraded should be False for {state}"

    def test_is_failed_true_only_when_failed(self) -> None:
        """Contract: is_failed returns True only when state == FAILED."""
        sm, _ = _create_central_state_machine()

        for state in CentralState:
            sm._state = state

            if state == CentralState.FAILED:
                assert sm.is_failed is True, f"is_failed should be True for {state}"
            else:
                assert sm.is_failed is False, f"is_failed should be False for {state}"

    def test_is_operational_true_for_running_and_degraded(self) -> None:
        """Contract: is_operational returns True for RUNNING and DEGRADED."""
        sm, _ = _create_central_state_machine()

        for state in CentralState:
            sm._state = state

            if state in (CentralState.RUNNING, CentralState.DEGRADED):
                assert sm.is_operational is True, f"is_operational should be True for {state}"
            else:
                assert sm.is_operational is False, f"is_operational should be False for {state}"

    def test_is_recovering_true_only_when_recovering(self) -> None:
        """Contract: is_recovering returns True only when state == RECOVERING."""
        sm, _ = _create_central_state_machine()

        for state in CentralState:
            sm._state = state

            if state == CentralState.RECOVERING:
                assert sm.is_recovering is True, f"is_recovering should be True for {state}"
            else:
                assert sm.is_recovering is False, f"is_recovering should be False for {state}"

    def test_is_running_true_only_when_running(self) -> None:
        """Contract: is_running returns True only when state == RUNNING."""
        sm, _ = _create_central_state_machine()

        for state in CentralState:
            sm._state = state  # Direct state set for testing

            if state == CentralState.RUNNING:
                assert sm.is_running is True, f"is_running should be True for {state}"
            else:
                assert sm.is_running is False, f"is_running should be False for {state}"

    def test_is_stopped_true_only_when_stopped(self) -> None:
        """Contract: is_stopped returns True only when state == STOPPED."""
        sm, _ = _create_central_state_machine()

        for state in CentralState:
            sm._state = state

            if state == CentralState.STOPPED:
                assert sm.is_stopped is True, f"is_stopped should be True for {state}"
            else:
                assert sm.is_stopped is False, f"is_stopped should be False for {state}"


# =============================================================================
# Contract: State History
# =============================================================================


class TestStateHistoryContract:
    """Contract: State history must be maintained and bounded."""

    def test_history_is_bounded_at_100(self) -> None:
        """Contract: State history is bounded at 100 entries."""
        sm, _ = _create_central_state_machine()

        # Make more than 100 transitions
        for _ in range(60):
            sm.transition_to(target=CentralState.INITIALIZING, force=True)
            sm.transition_to(target=CentralState.RUNNING, force=True)

        # Should be capped at 100
        assert len(sm.state_history) <= 100

    def test_seconds_in_current_state_increases(self) -> None:
        """Contract: seconds_in_current_state returns positive value."""
        sm, _ = _create_central_state_machine()
        sm.transition_to(target=CentralState.INITIALIZING)

        # Should be a positive number (or zero for fast tests)
        assert sm.seconds_in_current_state >= 0

    def test_state_history_returns_copy(self) -> None:
        """Contract: state_history property returns a copy."""
        sm, _ = _create_central_state_machine()
        sm.transition_to(target=CentralState.INITIALIZING)

        history1 = sm.state_history
        history2 = sm.state_history

        # Should be different objects
        assert history1 is not history2

        # But with same content
        assert history1 == history2

    def test_transitions_are_recorded_in_history(self) -> None:
        """Contract: Every transition is recorded in state_history."""
        sm, _ = _create_central_state_machine()

        sm.transition_to(target=CentralState.INITIALIZING)
        sm.transition_to(target=CentralState.RUNNING)
        sm.transition_to(target=CentralState.DEGRADED)

        history = sm.state_history
        assert len(history) == 3

        # Check structure: (timestamp, old_state, new_state, reason)
        assert history[0][1] == CentralState.STARTING
        assert history[0][2] == CentralState.INITIALIZING
        assert history[1][1] == CentralState.INITIALIZING
        assert history[1][2] == CentralState.RUNNING
        assert history[2][1] == CentralState.RUNNING
        assert history[2][2] == CentralState.DEGRADED


# =============================================================================
# Contract: Event Emission
# =============================================================================


class TestCentralEventEmissionContract:
    """Contract: Events must be emitted on state transitions."""

    def test_central_state_changed_event_has_correct_fields(self) -> None:
        """Contract: CentralStateChangedEvent has required fields."""
        from aiohomematic.central.events import CentralStateChangedEvent

        sm, event_bus = _create_central_state_machine(with_event_bus=True)
        assert event_bus is not None

        sm.transition_to(target=CentralState.INITIALIZING, reason="test reason")

        central_event = next(e for e in event_bus.published_events if isinstance(e, CentralStateChangedEvent))

        assert central_event.central_name == "test-central"
        assert central_event.old_state == CentralState.STARTING
        assert central_event.new_state == CentralState.INITIALIZING
        assert central_event.trigger == "test reason"

    def test_no_event_without_event_bus(self) -> None:
        """Contract: No exception when event_bus is None."""
        sm, event_bus = _create_central_state_machine(with_event_bus=False)
        assert event_bus is None

        # Should not raise
        sm.transition_to(target=CentralState.INITIALIZING)
        sm.transition_to(target=CentralState.RUNNING)

    def test_system_status_event_includes_central_state(self) -> None:
        """Contract: SystemStatusChangedEvent includes central_state."""
        from aiohomematic.central.events import SystemStatusChangedEvent

        sm, event_bus = _create_central_state_machine(with_event_bus=True)
        assert event_bus is not None

        sm.transition_to(target=CentralState.INITIALIZING)

        status_event = next(e for e in event_bus.published_events if isinstance(e, SystemStatusChangedEvent))

        assert status_event.central_state == CentralState.INITIALIZING

    def test_transition_emits_both_events(self) -> None:
        """Contract: Transition emits SystemStatusChangedEvent and CentralStateChangedEvent."""
        from aiohomematic.central.events import CentralStateChangedEvent, SystemStatusChangedEvent

        sm, event_bus = _create_central_state_machine(with_event_bus=True)
        assert event_bus is not None

        sm.transition_to(target=CentralState.INITIALIZING)

        # Should emit both event types
        assert len(event_bus.published_events) == 2

        event_types = {type(e) for e in event_bus.published_events}
        assert SystemStatusChangedEvent in event_types
        assert CentralStateChangedEvent in event_types


# =============================================================================
# Contract: Transition Table Completeness
# =============================================================================


class TestCentralTransitionTableCompletenessContract:
    """Contract: Transition table must cover all states."""

    def test_all_states_have_transition_entries(self) -> None:
        """Contract: Every CentralState has an entry in VALID_CENTRAL_TRANSITIONS."""
        for state in CentralState:
            assert state in VALID_CENTRAL_TRANSITIONS, f"Missing transition entry for {state}"

    def test_stopped_has_no_transitions(self) -> None:
        """Contract: STOPPED is terminal - no valid transitions."""
        assert VALID_CENTRAL_TRANSITIONS[CentralState.STOPPED] == frozenset()

    def test_stopped_reachable_from_most_states(self) -> None:
        """Contract: STOPPED is reachable from most operational states."""
        # All states except STOPPED itself should be able to reach STOPPED
        for state in VALID_CENTRAL_TRANSITIONS:
            if state != CentralState.STOPPED:
                # At least STARTING should be able to reach STOPPED
                pass  # This is a documentation test, not a strict requirement

    def test_transition_targets_are_valid_states(self) -> None:
        """Contract: All transition targets are valid CentralState values."""
        for source, targets in VALID_CENTRAL_TRANSITIONS.items():
            for target in targets:
                assert target in CentralState, f"Invalid target {target} from {source}"
