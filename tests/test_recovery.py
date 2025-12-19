"""Tests for RecoveryCoordinator."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from aiohomematic.central.recovery import (
    BASE_RETRY_DELAY,
    MAX_RECOVERY_ATTEMPTS,
    DataLoadStage,
    RecoveryCoordinator,
    RecoveryResult,
    RecoveryState,
)
from aiohomematic.const import CentralState, FailureReason

if TYPE_CHECKING:
    pass


class TestRecoveryState:
    """Tests for RecoveryState dataclass."""

    def test_can_retry_at_limit(self) -> None:
        """Test can_retry returns False at max attempts."""
        state = RecoveryState(interface_id="test-interface")
        state.attempt_count = MAX_RECOVERY_ATTEMPTS
        assert state.can_retry is False

    def test_can_retry_below_limit(self) -> None:
        """Test can_retry returns True below max attempts."""
        state = RecoveryState(interface_id="test-interface")
        state.attempt_count = MAX_RECOVERY_ATTEMPTS - 1
        assert state.can_retry is True

    def test_history_trimming(self) -> None:
        """Test history is trimmed to last 20 attempts."""
        state = RecoveryState(interface_id="test-interface")

        # Record more than 20 attempts
        for _ in range(25):
            state.record_attempt(result=RecoveryResult.FAILED, stage=DataLoadStage.BASIC)

        # History should be trimmed to 20
        assert len(state.history) == 20
        assert state.attempt_count == 25

    def test_initial_state(self) -> None:
        """Test initial recovery state."""
        state = RecoveryState(interface_id="test-interface")
        assert state.interface_id == "test-interface"
        assert state.attempt_count == 0
        assert state.consecutive_failures == 0
        assert state.last_attempt is None
        assert state.last_success is None
        assert state.can_retry is True
        assert len(state.history) == 0

    def test_next_retry_delay_capped(self) -> None:
        """Test retry delay is capped at MAX_RETRY_DELAY."""
        state = RecoveryState(interface_id="test-interface")
        state.consecutive_failures = 100  # Very high value
        # Should be capped at 60 seconds
        assert state.next_retry_delay <= 60.0

    def test_next_retry_delay_exponential_backoff(self) -> None:
        """Test exponential backoff for retry delay."""
        state = RecoveryState(interface_id="test-interface")
        state.consecutive_failures = 1
        assert state.next_retry_delay == BASE_RETRY_DELAY

        state.consecutive_failures = 2
        assert state.next_retry_delay == BASE_RETRY_DELAY * 2

        state.consecutive_failures = 3
        assert state.next_retry_delay == BASE_RETRY_DELAY * 4

    def test_next_retry_delay_initial(self) -> None:
        """Test initial retry delay."""
        state = RecoveryState(interface_id="test-interface")
        assert state.next_retry_delay == BASE_RETRY_DELAY

    def test_record_attempt_failure(self) -> None:
        """Test recording a failed attempt."""
        state = RecoveryState(interface_id="test-interface")
        state.record_attempt(
            result=RecoveryResult.FAILED,
            stage=DataLoadStage.BASIC,
            error="Connection refused",
        )
        assert state.attempt_count == 1
        assert state.consecutive_failures == 1
        assert state.last_success is None
        assert len(state.history) == 1
        assert state.history[0].result == RecoveryResult.FAILED
        assert state.history[0].error_message == "Connection refused"

    def test_record_attempt_multiple_failures(self) -> None:
        """Test consecutive failures are tracked."""
        state = RecoveryState(interface_id="test-interface")
        for _ in range(3):
            state.record_attempt(result=RecoveryResult.FAILED, stage=DataLoadStage.BASIC)
        assert state.attempt_count == 3
        assert state.consecutive_failures == 3

    def test_record_attempt_resets_consecutive_on_success(self) -> None:
        """Test success resets consecutive failure count."""
        state = RecoveryState(interface_id="test-interface")
        state.record_attempt(result=RecoveryResult.FAILED, stage=DataLoadStage.BASIC)
        state.record_attempt(result=RecoveryResult.FAILED, stage=DataLoadStage.BASIC)
        assert state.consecutive_failures == 2

        state.record_attempt(result=RecoveryResult.SUCCESS, stage=DataLoadStage.FULL)
        assert state.consecutive_failures == 0

    def test_record_attempt_success(self) -> None:
        """Test recording a successful attempt."""
        state = RecoveryState(interface_id="test-interface")
        state.record_attempt(
            result=RecoveryResult.SUCCESS,
            stage=DataLoadStage.FULL,
        )
        assert state.attempt_count == 1
        assert state.consecutive_failures == 0
        assert state.last_success is not None
        assert len(state.history) == 1
        assert state.history[0].result == RecoveryResult.SUCCESS

    def test_reset(self) -> None:
        """Test reset clears state."""
        state = RecoveryState(interface_id="test-interface")
        state.record_attempt(result=RecoveryResult.FAILED, stage=DataLoadStage.BASIC)
        state.record_attempt(result=RecoveryResult.FAILED, stage=DataLoadStage.BASIC)

        state.reset()
        assert state.attempt_count == 0
        assert state.consecutive_failures == 0


class TestRecoveryCoordinator:
    """Tests for RecoveryCoordinator."""

    def test_get_client_failure_reason_exception_handling(self) -> None:
        """Test _get_client_failure_reason handles exceptions."""
        client_provider = MagicMock()
        client_provider.get_client.side_effect = Exception("Not found")

        coordinator = RecoveryCoordinator(
            central_name="test-central",
            client_provider=client_provider,
        )
        reason = coordinator._get_client_failure_reason(interface_id="test")
        assert reason == FailureReason.UNKNOWN

    def test_get_client_failure_reason_no_provider(self) -> None:
        """Test _get_client_failure_reason without client provider."""
        coordinator = RecoveryCoordinator(central_name="test-central")
        reason = coordinator._get_client_failure_reason(interface_id="test")
        assert reason == FailureReason.UNKNOWN

    def test_get_client_failure_reason_none_becomes_unknown(self) -> None:
        """Test NONE failure reason becomes UNKNOWN."""
        client = MagicMock()
        client.state_machine.failure_reason = FailureReason.NONE

        client_provider = MagicMock()
        client_provider.get_client.return_value = client

        coordinator = RecoveryCoordinator(
            central_name="test-central",
            client_provider=client_provider,
        )
        reason = coordinator._get_client_failure_reason(interface_id="test")
        assert reason == FailureReason.UNKNOWN

    def test_get_client_failure_reason_with_provider(self) -> None:
        """Test _get_client_failure_reason with client provider."""
        client = MagicMock()
        client.state_machine.failure_reason = FailureReason.AUTH

        client_provider = MagicMock()
        client_provider.get_client.return_value = client

        coordinator = RecoveryCoordinator(
            central_name="test-central",
            client_provider=client_provider,
        )
        reason = coordinator._get_client_failure_reason(interface_id="test")
        assert reason == FailureReason.AUTH

    def test_get_recovery_state(self) -> None:
        """Test getting recovery state."""
        coordinator = RecoveryCoordinator(central_name="test-central")
        coordinator.register_interface(interface_id="test-interface")

        state = coordinator.get_recovery_state(interface_id="test-interface")
        assert state is not None
        assert state.interface_id == "test-interface"

    def test_get_recovery_state_not_found(self) -> None:
        """Test getting non-existent recovery state."""
        coordinator = RecoveryCoordinator(central_name="test-central")
        state = coordinator.get_recovery_state(interface_id="unknown")
        assert state is None

    @pytest.mark.asyncio
    async def test_heartbeat_retry_cancelled_on_shutdown(self) -> None:
        """Test heartbeat retry is cancelled on shutdown."""
        coordinator = RecoveryCoordinator(central_name="test-central")
        coordinator.shutdown()

        result = await coordinator.heartbeat_retry()
        assert result == RecoveryResult.CANCELLED

    @pytest.mark.asyncio
    async def test_heartbeat_retry_in_failed_state(self) -> None:
        """Test heartbeat retry actually attempts recovery in FAILED state."""
        health_tracker = MagicMock()
        health_tracker.health.failed_clients = ["interface-1"]

        state_machine = MagicMock()
        state_machine.state = CentralState.FAILED
        state_machine.can_transition_to.return_value = True

        coordinator = RecoveryCoordinator(
            central_name="test-central",
            state_machine=state_machine,
            health_tracker=health_tracker,
        )

        # Simulate interface at max retries
        state = coordinator.register_interface(interface_id="interface-1")
        state.attempt_count = MAX_RECOVERY_ATTEMPTS

        reconnect_func = AsyncMock(return_value=True)
        get_reconnect_func = lambda iface_id: reconnect_func

        result = await coordinator.heartbeat_retry(
            get_reconnect_func=get_reconnect_func,
        )

        # Recovery was successful, so counter was reset
        assert state.attempt_count == 0
        assert result == RecoveryResult.SUCCESS

    @pytest.mark.asyncio
    async def test_heartbeat_retry_not_in_failed_state(self) -> None:
        """Test heartbeat retry when not in FAILED state."""
        state_machine = MagicMock()
        state_machine.state = CentralState.RUNNING

        coordinator = RecoveryCoordinator(
            central_name="test-central",
            state_machine=state_machine,
        )

        result = await coordinator.heartbeat_retry()
        assert result == RecoveryResult.SUCCESS

    def test_init(self) -> None:
        """Test initialization."""
        coordinator = RecoveryCoordinator(central_name="test-central")
        assert coordinator.in_recovery is False
        assert coordinator.recovery_states == {}

    @pytest.mark.asyncio
    async def test_recover_all_failed_cancelled_on_shutdown(self) -> None:
        """Test recover_all_failed is cancelled on shutdown."""
        coordinator = RecoveryCoordinator(central_name="test-central")
        coordinator.shutdown()

        result = await coordinator.recover_all_failed()
        assert result == RecoveryResult.CANCELLED

    @pytest.mark.asyncio
    async def test_recover_all_failed_max_retries_transitions_to_failed(self) -> None:
        """Test transition to FAILED state when all clients hit max retries."""
        health_tracker = MagicMock()
        health_tracker.health.failed_clients = ["interface-1", "interface-2"]

        state_machine = MagicMock()
        state_machine.can_transition_to.return_value = True
        state_machine.state = CentralState.DEGRADED

        coordinator = RecoveryCoordinator(
            central_name="test-central",
            health_tracker=health_tracker,
            state_machine=state_machine,
        )

        # Set both interfaces at max retries
        state1 = coordinator.register_interface(interface_id="interface-1")
        state1.attempt_count = MAX_RECOVERY_ATTEMPTS
        state2 = coordinator.register_interface(interface_id="interface-2")
        state2.attempt_count = MAX_RECOVERY_ATTEMPTS

        result = await coordinator.recover_all_failed()

        # Should transition to FAILED state
        assert result == RecoveryResult.MAX_RETRIES
        state_machine.transition_to.assert_called()
        call_args = state_machine.transition_to.call_args
        assert call_args.kwargs["target"] == CentralState.FAILED

    @pytest.mark.asyncio
    async def test_recover_all_failed_no_failed_clients(self) -> None:
        """Test recover_all_failed with no failed clients."""
        health_tracker = MagicMock()
        health_tracker.health.failed_clients = []

        coordinator = RecoveryCoordinator(
            central_name="test-central",
            health_tracker=health_tracker,
        )

        result = await coordinator.recover_all_failed()
        assert result == RecoveryResult.SUCCESS

    @pytest.mark.asyncio
    async def test_recover_all_failed_no_health_tracker(self) -> None:
        """Test recover_all_failed without health tracker."""
        coordinator = RecoveryCoordinator(central_name="test-central")

        result = await coordinator.recover_all_failed()
        assert result == RecoveryResult.FAILED

    @pytest.mark.asyncio
    async def test_recover_all_failed_partial(self) -> None:
        """Test partial recovery when some clients fail."""
        health_tracker = MagicMock()
        health_tracker.health.failed_clients = ["interface-1", "interface-2"]

        state_machine = MagicMock()
        state_machine.can_transition_to.return_value = True
        state_machine.state = CentralState.DEGRADED

        coordinator = RecoveryCoordinator(
            central_name="test-central",
            health_tracker=health_tracker,
            state_machine=state_machine,
        )

        # First interface succeeds, second fails
        call_count = [0]

        async def reconnect_func():
            call_count[0] += 1
            return call_count[0] == 1  # First succeeds, second fails

        get_reconnect_func = lambda iface_id: reconnect_func

        result = await coordinator.recover_all_failed(
            get_reconnect_func=get_reconnect_func,
        )

        assert result == RecoveryResult.PARTIAL

    @pytest.mark.asyncio
    async def test_recover_all_failed_success(self) -> None:
        """Test successful recovery of all failed clients."""
        health_tracker = MagicMock()
        health_tracker.health.failed_clients = ["interface-1"]

        state_machine = MagicMock()
        state_machine.can_transition_to.return_value = True
        state_machine.state = CentralState.DEGRADED

        coordinator = RecoveryCoordinator(
            central_name="test-central",
            health_tracker=health_tracker,
            state_machine=state_machine,
        )

        reconnect_func = AsyncMock(return_value=True)
        get_reconnect_func = lambda iface_id: reconnect_func

        result = await coordinator.recover_all_failed(
            get_reconnect_func=get_reconnect_func,
        )

        assert result == RecoveryResult.SUCCESS

    @pytest.mark.asyncio
    async def test_recover_client_cancelled_error_propagated(self) -> None:
        """Test CancelledError is propagated."""
        coordinator = RecoveryCoordinator(central_name="test-central")

        reconnect_func = AsyncMock(side_effect=asyncio.CancelledError())

        with pytest.raises(asyncio.CancelledError):
            await coordinator.recover_client(
                interface_id="test-interface",
                reconnect_func=reconnect_func,
            )

    @pytest.mark.asyncio
    async def test_recover_client_cancelled_on_shutdown(self) -> None:
        """Test recovery is cancelled when shutdown is set."""
        coordinator = RecoveryCoordinator(central_name="test-central")
        coordinator.shutdown()

        result = await coordinator.recover_client(interface_id="test-interface")

        assert result == RecoveryResult.CANCELLED

    @pytest.mark.asyncio
    async def test_recover_client_exception_handling(self) -> None:
        """Test exception handling during recovery."""
        coordinator = RecoveryCoordinator(central_name="test-central")

        reconnect_func = AsyncMock(side_effect=Exception("Connection error"))

        result = await coordinator.recover_client(
            interface_id="test-interface",
            reconnect_func=reconnect_func,
        )

        assert result == RecoveryResult.FAILED
        state = coordinator.get_recovery_state(interface_id="test-interface")
        assert state is not None
        assert state.consecutive_failures == 1

    @pytest.mark.asyncio
    async def test_recover_client_max_retries(self) -> None:
        """Test client recovery when max retries reached."""
        coordinator = RecoveryCoordinator(central_name="test-central")
        state = coordinator.register_interface(interface_id="test-interface")
        state.attempt_count = MAX_RECOVERY_ATTEMPTS

        result = await coordinator.recover_client(interface_id="test-interface")

        assert result == RecoveryResult.MAX_RETRIES

    @pytest.mark.asyncio
    async def test_recover_client_partial_recovery(self) -> None:
        """Test partial recovery when data load verification fails."""
        coordinator = RecoveryCoordinator(central_name="test-central")

        reconnect_func = AsyncMock(return_value=True)
        verify_func = AsyncMock(return_value=False)  # Verification fails

        result = await coordinator.recover_client(
            interface_id="test-interface",
            reconnect_func=reconnect_func,
            verify_func=verify_func,
        )

        assert result == RecoveryResult.PARTIAL
        state = coordinator.get_recovery_state(interface_id="test-interface")
        assert state is not None
        assert state.attempt_count == 1

    @pytest.mark.asyncio
    async def test_recover_client_reconnect_fails(self) -> None:
        """Test client recovery when reconnect fails."""
        coordinator = RecoveryCoordinator(central_name="test-central")

        reconnect_func = AsyncMock(return_value=False)

        result = await coordinator.recover_client(
            interface_id="test-interface",
            reconnect_func=reconnect_func,
        )

        assert result == RecoveryResult.FAILED

    @pytest.mark.asyncio
    async def test_recover_client_success(self) -> None:
        """Test successful client recovery."""
        coordinator = RecoveryCoordinator(central_name="test-central")

        reconnect_func = AsyncMock(return_value=True)
        verify_func = AsyncMock(return_value=True)

        result = await coordinator.recover_client(
            interface_id="test-interface",
            reconnect_func=reconnect_func,
            verify_func=verify_func,
        )

        assert result == RecoveryResult.SUCCESS
        reconnect_func.assert_called_once()

    @pytest.mark.asyncio
    async def test_recover_client_verify_exception(self) -> None:
        """Test recovery when verify function raises exception."""
        coordinator = RecoveryCoordinator(central_name="test-central")

        reconnect_func = AsyncMock(return_value=True)
        verify_func = AsyncMock(side_effect=RuntimeError("Verification error"))

        result = await coordinator.recover_client(
            interface_id="test-interface",
            reconnect_func=reconnect_func,
            verify_func=verify_func,
        )

        assert result == RecoveryResult.PARTIAL

    def test_register_interface(self) -> None:
        """Test registering an interface."""
        coordinator = RecoveryCoordinator(central_name="test-central")
        state = coordinator.register_interface(interface_id="test-interface")
        assert state.interface_id == "test-interface"
        assert "test-interface" in coordinator.recovery_states

    def test_register_interface_idempotent(self) -> None:
        """Test registering same interface twice returns same state."""
        coordinator = RecoveryCoordinator(central_name="test-central")
        state1 = coordinator.register_interface(interface_id="test-interface")
        state2 = coordinator.register_interface(interface_id="test-interface")
        assert state1 is state2

    def test_reset_interface(self) -> None:
        """Test resetting an interface."""
        coordinator = RecoveryCoordinator(central_name="test-central")
        state = coordinator.register_interface(interface_id="test-interface")
        state.record_attempt(result=RecoveryResult.FAILED, stage=DataLoadStage.BASIC)
        assert state.attempt_count == 1

        coordinator.reset_interface(interface_id="test-interface")
        assert state.attempt_count == 0

    def test_set_health_tracker(self) -> None:
        """Test setting health tracker."""
        coordinator = RecoveryCoordinator(central_name="test-central")
        health_tracker = MagicMock()

        coordinator.set_health_tracker(health_tracker=health_tracker)
        assert coordinator._health_tracker is health_tracker

    def test_set_state_machine(self) -> None:
        """Test setting state machine."""
        coordinator = RecoveryCoordinator(central_name="test-central")
        state_machine = MagicMock()

        coordinator.set_state_machine(state_machine=state_machine)
        assert coordinator._state_machine is state_machine

    def test_shutdown(self) -> None:
        """Test shutdown flag."""
        coordinator = RecoveryCoordinator(central_name="test-central")
        assert coordinator._shutdown is False

        coordinator.shutdown()
        assert coordinator._shutdown is True

    def test_unregister_interface(self) -> None:
        """Test unregistering an interface."""
        coordinator = RecoveryCoordinator(central_name="test-central")
        coordinator.register_interface(interface_id="test-interface")
        assert "test-interface" in coordinator.recovery_states

        coordinator.unregister_interface(interface_id="test-interface")
        assert "test-interface" not in coordinator.recovery_states


class TestDataLoadStage:
    """Tests for DataLoadStage enum."""

    def test_stage_values(self) -> None:
        """Test DataLoadStage values."""
        assert DataLoadStage.BASIC == "basic"
        assert DataLoadStage.DEVICES == "devices"
        assert DataLoadStage.PARAMSETS == "paramsets"
        assert DataLoadStage.VALUES == "values"
        assert DataLoadStage.FULL == "full"


class TestRecoveryResult:
    """Tests for RecoveryResult enum."""

    def test_result_values(self) -> None:
        """Test RecoveryResult values."""
        assert RecoveryResult.SUCCESS == "success"
        assert RecoveryResult.PARTIAL == "partial"
        assert RecoveryResult.FAILED == "failed"
        assert RecoveryResult.MAX_RETRIES == "max_retries"
        assert RecoveryResult.CANCELLED == "cancelled"
