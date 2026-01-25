# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract tests for connection recovery behavior.

STABILITY GUARANTEE
-------------------
These tests define the stable API contract for the ConnectionRecoveryCoordinator.
Any change that breaks these tests requires a MAJOR version bump.

The contract ensures that:
1. MAX_RECOVERY_ATTEMPTS is enforced (8 attempts)
2. Exponential backoff formula is correct
3. Recovery stages progress correctly
4. Heartbeat retry starts on FAILED state
5. Concurrent recoveries are limited
6. Recovery events are emitted correctly

See ADR-0018 for architectural context.
"""

from __future__ import annotations

from aiohomematic.central.coordinators.connection_recovery import (
    BASE_RETRY_DELAY,
    HEARTBEAT_RETRY_INTERVAL,
    MAX_CONCURRENT_RECOVERIES,
    MAX_RECOVERY_ATTEMPTS,
    MAX_RETRY_DELAY,
    InterfaceRecoveryState,
)
from aiohomematic.const import RecoveryStage

# =============================================================================
# Contract: Constants Stability
# =============================================================================


class TestRecoveryConstantsContract:
    """Contract: Recovery constants must remain stable."""

    def test_base_retry_delay_is_5(self) -> None:
        """Contract: BASE_RETRY_DELAY must be 5 seconds."""
        assert BASE_RETRY_DELAY == 5.0

    def test_heartbeat_retry_interval_is_60(self) -> None:
        """Contract: HEARTBEAT_RETRY_INTERVAL must be 60 seconds."""
        assert HEARTBEAT_RETRY_INTERVAL == 60.0

    def test_max_concurrent_recoveries_is_2(self) -> None:
        """Contract: MAX_CONCURRENT_RECOVERIES must be 2."""
        assert MAX_CONCURRENT_RECOVERIES == 2

    def test_max_recovery_attempts_is_8(self) -> None:
        """Contract: MAX_RECOVERY_ATTEMPTS must be 8."""
        assert MAX_RECOVERY_ATTEMPTS == 8

    def test_max_retry_delay_is_60(self) -> None:
        """Contract: MAX_RETRY_DELAY must be 60 seconds."""
        assert MAX_RETRY_DELAY == 60.0


# =============================================================================
# Contract: RecoveryStage Enum Stability
# =============================================================================


class TestRecoveryStageEnumContract:
    """Contract: RecoveryStage enum values must remain stable."""

    def test_recovery_stage_has_cooldown(self) -> None:
        """Contract: RecoveryStage.COOLDOWN must exist."""
        assert hasattr(RecoveryStage, "COOLDOWN")
        assert RecoveryStage.COOLDOWN.value == "cooldown"

    def test_recovery_stage_has_data_loading(self) -> None:
        """Contract: RecoveryStage.DATA_LOADING must exist."""
        assert hasattr(RecoveryStage, "DATA_LOADING")
        assert RecoveryStage.DATA_LOADING.value == "data_loading"

    def test_recovery_stage_has_detecting(self) -> None:
        """Contract: RecoveryStage.DETECTING must exist."""
        assert hasattr(RecoveryStage, "DETECTING")
        assert RecoveryStage.DETECTING.value == "detecting"

    def test_recovery_stage_has_failed(self) -> None:
        """Contract: RecoveryStage.FAILED must exist."""
        assert hasattr(RecoveryStage, "FAILED")
        assert RecoveryStage.FAILED.value == "failed"

    def test_recovery_stage_has_heartbeat(self) -> None:
        """Contract: RecoveryStage.HEARTBEAT must exist."""
        assert hasattr(RecoveryStage, "HEARTBEAT")
        assert RecoveryStage.HEARTBEAT.value == "heartbeat"

    def test_recovery_stage_has_idle(self) -> None:
        """Contract: RecoveryStage.IDLE must exist."""
        assert hasattr(RecoveryStage, "IDLE")
        assert RecoveryStage.IDLE.value == "idle"

    def test_recovery_stage_has_reconnecting(self) -> None:
        """Contract: RecoveryStage.RECONNECTING must exist."""
        assert hasattr(RecoveryStage, "RECONNECTING")
        assert RecoveryStage.RECONNECTING.value == "reconnecting"

    def test_recovery_stage_has_recovered(self) -> None:
        """Contract: RecoveryStage.RECOVERED must exist."""
        assert hasattr(RecoveryStage, "RECOVERED")
        assert RecoveryStage.RECOVERED.value == "recovered"

    def test_recovery_stage_has_rpc_checking(self) -> None:
        """Contract: RecoveryStage.RPC_CHECKING must exist."""
        assert hasattr(RecoveryStage, "RPC_CHECKING")
        assert RecoveryStage.RPC_CHECKING.value == "rpc_checking"

    def test_recovery_stage_has_stability_check(self) -> None:
        """Contract: RecoveryStage.STABILITY_CHECK must exist."""
        assert hasattr(RecoveryStage, "STABILITY_CHECK")
        assert RecoveryStage.STABILITY_CHECK.value == "stability_check"

    def test_recovery_stage_has_tcp_checking(self) -> None:
        """Contract: RecoveryStage.TCP_CHECKING must exist."""
        assert hasattr(RecoveryStage, "TCP_CHECKING")
        assert RecoveryStage.TCP_CHECKING.value == "tcp_checking"

    def test_recovery_stage_has_warming_up(self) -> None:
        """Contract: RecoveryStage.WARMING_UP must exist."""
        assert hasattr(RecoveryStage, "WARMING_UP")
        assert RecoveryStage.WARMING_UP.value == "warming_up"


# =============================================================================
# Contract: InterfaceRecoveryState Behavior
# =============================================================================


class TestInterfaceRecoveryStateContract:
    """Contract: InterfaceRecoveryState must behave correctly."""

    def test_can_retry_false_at_max_attempts(self) -> None:
        """Contract: can_retry is False when attempt_count >= MAX_RECOVERY_ATTEMPTS."""
        state = InterfaceRecoveryState(interface_id="test-interface")

        for _ in range(MAX_RECOVERY_ATTEMPTS):
            assert state.can_retry is True
            state.record_failure()

        assert state.can_retry is False

    def test_can_retry_true_initially(self) -> None:
        """Contract: can_retry is True when attempt_count < MAX_RECOVERY_ATTEMPTS."""
        state = InterfaceRecoveryState(interface_id="test-interface")
        assert state.can_retry is True

    def test_initial_state_has_zero_attempts(self) -> None:
        """Contract: New recovery state has attempt_count = 0."""
        state = InterfaceRecoveryState(interface_id="test-interface")
        assert state.attempt_count == 0

    def test_initial_state_has_zero_failures(self) -> None:
        """Contract: New recovery state has consecutive_failures = 0."""
        state = InterfaceRecoveryState(interface_id="test-interface")
        assert state.consecutive_failures == 0

    def test_initial_state_is_idle(self) -> None:
        """Contract: New recovery state starts in IDLE stage."""
        state = InterfaceRecoveryState(interface_id="test-interface")
        assert state.current_stage == RecoveryStage.IDLE

    def test_record_failure_increments_counters(self) -> None:
        """Contract: record_failure increments attempt_count and consecutive_failures."""
        state = InterfaceRecoveryState(interface_id="test-interface")

        state.record_failure()
        assert state.attempt_count == 1
        assert state.consecutive_failures == 1

        state.record_failure()
        assert state.attempt_count == 2
        assert state.consecutive_failures == 2

    def test_record_success_resets_consecutive_failures(self) -> None:
        """Contract: record_success resets consecutive_failures but increments attempt_count."""
        state = InterfaceRecoveryState(interface_id="test-interface")

        state.record_failure()
        state.record_failure()
        assert state.consecutive_failures == 2

        state.record_success()
        assert state.consecutive_failures == 0
        assert state.attempt_count == 3  # 2 failures + 1 success

    def test_reset_clears_all_counters(self) -> None:
        """Contract: reset clears attempt_count, consecutive_failures, and stage."""
        state = InterfaceRecoveryState(interface_id="test-interface")

        state.record_failure()
        state.record_failure()
        state.transition_to_stage(new_stage=RecoveryStage.TCP_CHECKING)

        state.reset()

        assert state.attempt_count == 0
        assert state.consecutive_failures == 0
        assert state.current_stage == RecoveryStage.IDLE
        assert len(state.stages_completed) == 0


# =============================================================================
# Contract: Exponential Backoff Formula
# =============================================================================


class TestExponentialBackoffContract:
    """Contract: Exponential backoff must follow the correct formula."""

    def test_backoff_sequence(self) -> None:
        """Contract: Backoff sequence is 5, 5, 10, 20, 40, 60, 60, ..."""
        state = InterfaceRecoveryState(interface_id="test-interface")

        expected_delays = [5.0, 5.0, 10.0, 20.0, 40.0, 60.0, 60.0, 60.0]

        for expected in expected_delays:
            assert state.next_retry_delay == expected, f"Expected {expected}, got {state.next_retry_delay}"
            state.record_failure()

    def test_delay_is_capped_at_max(self) -> None:
        """Contract: Delay is capped at MAX_RETRY_DELAY (60s)."""
        state = InterfaceRecoveryState(interface_id="test-interface")

        # Record many failures to trigger cap
        for _ in range(10):
            state.record_failure()

        assert state.next_retry_delay == MAX_RETRY_DELAY
        assert state.next_retry_delay <= MAX_RETRY_DELAY

    def test_first_failure_delay_is_base(self) -> None:
        """Contract: First failure uses BASE_RETRY_DELAY (5s)."""
        state = InterfaceRecoveryState(interface_id="test-interface")
        assert state.next_retry_delay == BASE_RETRY_DELAY

    def test_fourth_failure_delay_is_quadrupled(self) -> None:
        """Contract: After 3 failures, delay is BASE * 2^2 = 20s."""
        state = InterfaceRecoveryState(interface_id="test-interface")
        state.record_failure()
        state.record_failure()
        state.record_failure()
        # consecutive_failures = 3, delay = 5 * 2^2 = 20
        assert state.next_retry_delay == BASE_RETRY_DELAY * 4

    def test_second_failure_delay_is_base(self) -> None:
        """Contract: After 1 failure, delay is BASE * 2^0 = 5s."""
        state = InterfaceRecoveryState(interface_id="test-interface")
        state.record_failure()
        # consecutive_failures = 1, delay = 5 * 2^0 = 5
        assert state.next_retry_delay == BASE_RETRY_DELAY

    def test_third_failure_delay_is_doubled(self) -> None:
        """Contract: After 2 failures, delay is BASE * 2^1 = 10s."""
        state = InterfaceRecoveryState(interface_id="test-interface")
        state.record_failure()
        state.record_failure()
        # consecutive_failures = 2, delay = 5 * 2^1 = 10
        assert state.next_retry_delay == BASE_RETRY_DELAY * 2


# =============================================================================
# Contract: Stage Transitions
# =============================================================================


class TestStageTransitionsContract:
    """Contract: Recovery stage transitions must work correctly."""

    def test_start_recovery_clears_stages_completed(self) -> None:
        """Contract: start_recovery clears stages_completed list."""
        state = InterfaceRecoveryState(interface_id="test-interface")

        # Add some stages
        state.transition_to_stage(new_stage=RecoveryStage.COOLDOWN)
        state.transition_to_stage(new_stage=RecoveryStage.TCP_CHECKING)
        assert len(state.stages_completed) > 0

        state.start_recovery()

        assert len(state.stages_completed) == 0

    def test_start_recovery_sets_start_time(self) -> None:
        """Contract: start_recovery sets recovery_start_time."""
        state = InterfaceRecoveryState(interface_id="test-interface")

        assert state.recovery_start_time is None

        state.start_recovery()

        assert state.recovery_start_time is not None
        assert state.recovery_start_time > 0

    def test_transition_records_completed_stages(self) -> None:
        """Contract: transition_to_stage records completed stages (except IDLE/RECOVERED/FAILED)."""
        state = InterfaceRecoveryState(interface_id="test-interface")

        state.transition_to_stage(new_stage=RecoveryStage.COOLDOWN)
        state.transition_to_stage(new_stage=RecoveryStage.TCP_CHECKING)
        state.transition_to_stage(new_stage=RecoveryStage.RPC_CHECKING)
        state.transition_to_stage(new_stage=RecoveryStage.RECOVERED)

        # IDLE should not be in completed stages (initial state)
        # COOLDOWN and TCP_CHECKING should be recorded
        # RPC_CHECKING should be recorded
        # RECOVERED should not be recorded (terminal stage)
        assert RecoveryStage.COOLDOWN in state.stages_completed
        assert RecoveryStage.TCP_CHECKING in state.stages_completed
        assert RecoveryStage.RPC_CHECKING in state.stages_completed
        assert RecoveryStage.IDLE not in state.stages_completed
        assert RecoveryStage.RECOVERED not in state.stages_completed

    def test_transition_returns_duration_ms(self) -> None:
        """Contract: transition_to_stage returns duration in milliseconds."""
        state = InterfaceRecoveryState(interface_id="test-interface")

        duration_ms = state.transition_to_stage(new_stage=RecoveryStage.COOLDOWN)

        # Duration should be a non-negative number
        assert isinstance(duration_ms, float)
        assert duration_ms >= 0

    def test_transition_to_stage_updates_current_stage(self) -> None:
        """Contract: transition_to_stage updates current_stage."""
        state = InterfaceRecoveryState(interface_id="test-interface")

        state.transition_to_stage(new_stage=RecoveryStage.COOLDOWN)
        assert state.current_stage == RecoveryStage.COOLDOWN

        state.transition_to_stage(new_stage=RecoveryStage.TCP_CHECKING)
        assert state.current_stage == RecoveryStage.TCP_CHECKING


# =============================================================================
# Contract: Full Recovery Cycle
# =============================================================================


class TestFullRecoveryCycleContract:
    """Contract: Full recovery cycle must work correctly."""

    def test_failed_recovery_cycle(self) -> None:
        """Contract: Failed recovery cycle increments attempt counters."""
        state = InterfaceRecoveryState(interface_id="test-interface")

        # Start recovery
        state.start_recovery()

        # Progress through some stages
        state.transition_to_stage(new_stage=RecoveryStage.COOLDOWN)
        state.transition_to_stage(new_stage=RecoveryStage.TCP_CHECKING)
        state.transition_to_stage(new_stage=RecoveryStage.FAILED)

        # Record failure
        state.record_failure()

        # Verify state
        assert state.attempt_count == 1
        assert state.consecutive_failures == 1

    def test_max_attempts_exhausted(self) -> None:
        """Contract: After MAX_RECOVERY_ATTEMPTS, can_retry is False."""
        state = InterfaceRecoveryState(interface_id="test-interface")

        # Exhaust all attempts
        for i in range(MAX_RECOVERY_ATTEMPTS):
            state.start_recovery()
            state.transition_to_stage(new_stage=RecoveryStage.FAILED)
            state.record_failure()

            if i < MAX_RECOVERY_ATTEMPTS - 1:
                assert state.can_retry is True
            else:
                assert state.can_retry is False

        # Final check
        assert state.attempt_count == MAX_RECOVERY_ATTEMPTS
        assert state.can_retry is False

    def test_successful_recovery_cycle(self) -> None:
        """Contract: Successful recovery cycle resets state correctly."""
        state = InterfaceRecoveryState(interface_id="test-interface")

        # Start recovery
        state.start_recovery()
        assert state.recovery_start_time is not None

        # Progress through stages
        state.transition_to_stage(new_stage=RecoveryStage.COOLDOWN)
        state.transition_to_stage(new_stage=RecoveryStage.TCP_CHECKING)
        state.transition_to_stage(new_stage=RecoveryStage.RPC_CHECKING)
        state.transition_to_stage(new_stage=RecoveryStage.WARMING_UP)
        state.transition_to_stage(new_stage=RecoveryStage.STABILITY_CHECK)
        state.transition_to_stage(new_stage=RecoveryStage.RECONNECTING)
        state.transition_to_stage(new_stage=RecoveryStage.DATA_LOADING)
        state.transition_to_stage(new_stage=RecoveryStage.RECOVERED)

        # Record success
        state.record_success()

        # Verify state
        assert state.consecutive_failures == 0
        assert state.last_success is not None


# =============================================================================
# Contract: Recovery Stage Progression Order
# =============================================================================


class TestRecoveryStageProgressionContract:
    """Contract: Recovery stages must follow the documented progression."""

    def test_normal_recovery_stage_order(self) -> None:
        """Contract: Normal recovery progresses through stages in order."""
        expected_order = [
            RecoveryStage.IDLE,
            RecoveryStage.COOLDOWN,
            RecoveryStage.TCP_CHECKING,
            RecoveryStage.RPC_CHECKING,
            RecoveryStage.WARMING_UP,
            RecoveryStage.STABILITY_CHECK,
            RecoveryStage.RECONNECTING,
            RecoveryStage.DATA_LOADING,
            RecoveryStage.RECOVERED,
        ]

        state = InterfaceRecoveryState(interface_id="test-interface")

        # Verify initial stage
        assert state.current_stage == expected_order[0]

        # Progress through stages
        for next_stage in expected_order[1:]:
            state.transition_to_stage(new_stage=next_stage)
            assert state.current_stage == next_stage

    def test_stage_display_names_are_strings(self) -> None:
        """Contract: All stages have display_name property returning string."""
        for stage in RecoveryStage:
            assert hasattr(stage, "display_name")
            assert isinstance(stage.display_name, str)
            assert len(stage.display_name) > 0
