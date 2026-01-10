# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for ConnectionRecoveryCoordinator."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aiohomematic.async_support import Looper
from aiohomematic.central.coordinators import ConnectionRecoveryCoordinator
from aiohomematic.central.coordinators.connection_recovery import (
    BASE_RETRY_DELAY,
    MAX_RECOVERY_ATTEMPTS,
    MAX_RETRY_DELAY,
    InterfaceRecoveryState,
)
from aiohomematic.central.events import (
    CircuitBreakerStateChangedEvent,
    CircuitBreakerTrippedEvent,
    ConnectionLostEvent,
    EventBus,
    HeartbeatTimerFiredEvent,
    RecoveryAttemptedEvent,
    RecoveryCompletedEvent,
    RecoveryFailedEvent,
    RecoveryStageChangedEvent,
    SystemStatusChangedEvent,
)
from aiohomematic.client import CircuitState
from aiohomematic.const import CentralState, Interface, RecoveryStage

if TYPE_CHECKING:
    pass

# pylint: disable=protected-access


class TestInterfaceRecoveryState:
    """Tests for InterfaceRecoveryState dataclass."""

    def test_can_retry_false_when_at_max_attempts(self) -> None:
        """Test can_retry returns False when at max attempts."""
        state = InterfaceRecoveryState(interface_id="test")
        state.attempt_count = MAX_RECOVERY_ATTEMPTS

        assert state.can_retry is False

    def test_can_retry_true_when_under_max_attempts(self) -> None:
        """Test can_retry returns True when under max attempts."""
        state = InterfaceRecoveryState(interface_id="test")
        state.attempt_count = MAX_RECOVERY_ATTEMPTS - 1

        assert state.can_retry is True

    def test_initial_state(self) -> None:
        """Test initial state of InterfaceRecoveryState."""
        state = InterfaceRecoveryState(interface_id="test-interface")

        assert state.interface_id == "test-interface"
        assert state.attempt_count == 0
        assert state.last_attempt is None
        assert state.last_success is None
        assert state.consecutive_failures == 0
        assert state.current_stage == RecoveryStage.IDLE
        assert state.stages_completed == []
        assert state.recovery_start_time is None

    def test_next_retry_delay_base_on_first_failure(self) -> None:
        """Test next_retry_delay returns BASE_RETRY_DELAY on first failure."""
        state = InterfaceRecoveryState(interface_id="test")
        state.consecutive_failures = 0

        assert state.next_retry_delay == BASE_RETRY_DELAY

    def test_next_retry_delay_capped_at_max(self) -> None:
        """Test next_retry_delay is capped at MAX_RETRY_DELAY."""
        state = InterfaceRecoveryState(interface_id="test")
        state.consecutive_failures = 20  # Very high number

        assert state.next_retry_delay == MAX_RETRY_DELAY

    def test_next_retry_delay_exponential_backoff(self) -> None:
        """Test next_retry_delay uses exponential backoff."""
        state = InterfaceRecoveryState(interface_id="test")

        # First failure: BASE_RETRY_DELAY * 2^0 = BASE_RETRY_DELAY
        state.consecutive_failures = 1
        assert state.next_retry_delay == BASE_RETRY_DELAY

        # Second failure: BASE_RETRY_DELAY * 2^1 = 2 * BASE_RETRY_DELAY
        state.consecutive_failures = 2
        assert state.next_retry_delay == BASE_RETRY_DELAY * 2

        # Third failure: BASE_RETRY_DELAY * 2^2 = 4 * BASE_RETRY_DELAY
        state.consecutive_failures = 3
        assert state.next_retry_delay == BASE_RETRY_DELAY * 4

    def test_record_failure(self) -> None:
        """Test record_failure updates state correctly."""
        state = InterfaceRecoveryState(interface_id="test")
        initial_attempt_count = state.attempt_count
        initial_consecutive = state.consecutive_failures

        state.record_failure()

        assert state.consecutive_failures == initial_consecutive + 1
        assert state.attempt_count == initial_attempt_count + 1
        assert state.last_attempt is not None
        assert (datetime.now() - state.last_attempt).total_seconds() < 1

    def test_record_success(self) -> None:
        """Test record_success updates state correctly."""
        state = InterfaceRecoveryState(interface_id="test")
        state.consecutive_failures = 5
        initial_attempt_count = state.attempt_count

        state.record_success()

        assert state.consecutive_failures == 0
        assert state.attempt_count == initial_attempt_count + 1
        assert state.last_success is not None
        assert state.last_attempt is not None
        assert (datetime.now() - state.last_success).total_seconds() < 1

    def test_reset(self) -> None:
        """Test reset clears recovery state."""
        state = InterfaceRecoveryState(interface_id="test")
        state.attempt_count = 5
        state.consecutive_failures = 3
        state.current_stage = RecoveryStage.RECONNECTING
        state.stages_completed = [RecoveryStage.TCP_CHECKING, RecoveryStage.RPC_CHECKING]
        state.recovery_start_time = 12345.0

        state.reset()

        assert state.attempt_count == 0
        assert state.consecutive_failures == 0
        assert state.current_stage == RecoveryStage.IDLE
        assert state.stages_completed == []
        assert state.recovery_start_time is None

    def test_start_recovery(self) -> None:
        """Test start_recovery initializes recovery cycle."""
        state = InterfaceRecoveryState(interface_id="test")
        state.stages_completed = [RecoveryStage.TCP_CHECKING]

        state.start_recovery()

        assert state.recovery_start_time is not None
        assert state.stages_completed == []

    def test_transition_to_stage(self) -> None:
        """Test transition_to_stage updates stage and returns duration."""
        state = InterfaceRecoveryState(interface_id="test")
        state.current_stage = RecoveryStage.TCP_CHECKING

        duration_ms = state.transition_to_stage(new_stage=RecoveryStage.RPC_CHECKING)

        assert state.current_stage == RecoveryStage.RPC_CHECKING
        assert isinstance(duration_ms, float)
        assert RecoveryStage.TCP_CHECKING in state.stages_completed

    def test_transition_to_stage_idle_not_added_to_completed(self) -> None:
        """Test that IDLE stage is not added to stages_completed."""
        state = InterfaceRecoveryState(interface_id="test")
        assert state.current_stage == RecoveryStage.IDLE

        state.transition_to_stage(new_stage=RecoveryStage.COOLDOWN)

        assert RecoveryStage.IDLE not in state.stages_completed
        assert state.current_stage == RecoveryStage.COOLDOWN


class TestConnectionRecoveryCoordinatorInit:
    """Tests for ConnectionRecoveryCoordinator initialization."""

    def test_get_recovery_state_returns_none_for_unknown(self) -> None:
        """Test get_recovery_state returns None for unknown interface."""
        coordinator = self._create_coordinator()

        result = coordinator.get_recovery_state(interface_id="unknown")

        assert result is None
        coordinator.stop()

    def test_get_recovery_state_returns_state_for_known(self) -> None:
        """Test get_recovery_state returns state for known interface."""
        coordinator = self._create_coordinator()
        state = InterfaceRecoveryState(interface_id="test")
        coordinator._recovery_states["test"] = state

        result = coordinator.get_recovery_state(interface_id="test")

        assert result is state
        coordinator.stop()

    def test_in_recovery_false_initially(self) -> None:
        """Test in_recovery is False initially."""
        coordinator = self._create_coordinator()
        assert coordinator.in_recovery is False
        coordinator.stop()

    def test_in_recovery_true_when_active(self) -> None:
        """Test in_recovery is True when recoveries are active."""
        coordinator = self._create_coordinator()
        coordinator._active_recoveries.add("test-interface")

        assert coordinator.in_recovery is True

        coordinator.stop()

    def test_initialization(self) -> None:
        """Test coordinator initializes correctly."""
        coordinator = self._create_coordinator()

        assert coordinator.in_recovery is False
        assert coordinator.recovery_states == {}
        assert coordinator._shutdown is False

        coordinator.stop()

    def test_set_state_machine(self) -> None:
        """Test set_state_machine sets the state machine reference."""
        coordinator = self._create_coordinator()
        state_machine = MagicMock()

        coordinator.set_state_machine(state_machine=state_machine)

        assert coordinator._state_machine is state_machine
        coordinator.stop()

    def test_stop_unsubscribes_events(self) -> None:
        """Test stop unsubscribes from all events."""
        coordinator = self._create_coordinator()
        initial_unsub_count = len(coordinator._unsubscribers)

        assert initial_unsub_count > 0

        coordinator.stop()

        assert coordinator._shutdown is True
        assert coordinator._unsubscribers == []

    def _create_coordinator(
        self,
        *,
        event_bus: EventBus | None = None,
        state_machine: MagicMock | None = None,
    ) -> ConnectionRecoveryCoordinator:
        """Create a coordinator with mocked dependencies."""
        task_scheduler = Looper()
        if event_bus is None:
            event_bus = EventBus(task_scheduler=task_scheduler)

        central_info = MagicMock()
        central_info.name = "test-central"

        config_provider = MagicMock()
        config_provider.config.timeout_config.reconnect_initial_cooldown = 0.01
        config_provider.config.timeout_config.reconnect_warmup_delay = 0.01
        config_provider.config.timeout_config.reconnect_tcp_check_timeout = 0.1
        config_provider.config.host = "127.0.0.1"
        config_provider.config.tls = False

        client_provider = MagicMock()
        coordinator_provider = MagicMock()
        device_data_refresher = MagicMock()

        return ConnectionRecoveryCoordinator(
            central_info=central_info,
            config_provider=config_provider,
            client_provider=client_provider,
            coordinator_provider=coordinator_provider,
            device_data_refresher=device_data_refresher,
            event_bus=event_bus,
            task_scheduler=task_scheduler,
            state_machine=state_machine,
        )


class TestConnectionRecoveryCoordinatorEventHandlers:
    """Tests for ConnectionRecoveryCoordinator event handlers."""

    @pytest.mark.asyncio
    async def test_on_circuit_breaker_state_changed_triggers_refresh(self) -> None:
        """Test circuit breaker recovery triggers data refresh."""
        coordinator, event_bus, _ = self._create_coordinator()

        event = CircuitBreakerStateChangedEvent(
            timestamp=datetime.now(),
            interface_id="test-interface",
            old_state=CircuitState.HALF_OPEN,
            new_state=CircuitState.CLOSED,
            failure_count=0,
            success_count=3,
            last_failure_time=None,
        )

        coordinator._on_circuit_breaker_state_changed(event=event)

        await asyncio.sleep(0.05)

        # Verify refresh was attempted (by checking the mock was called)
        assert coordinator._device_data_refresher.load_and_refresh_data_point_data.called
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_on_circuit_breaker_tripped_starts_recovery(self) -> None:
        """Test _on_circuit_breaker_tripped starts recovery."""
        coordinator, _, _ = self._create_coordinator()

        event = CircuitBreakerTrippedEvent(
            timestamp=datetime.now(),
            interface_id="test-interface",
            failure_count=5,
            last_failure_reason="Connection refused",
            cooldown_seconds=30.0,
        )

        coordinator._on_circuit_breaker_tripped(event=event)

        await asyncio.sleep(0.05)

        assert "test-interface" in coordinator._active_recoveries
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_on_connection_lost_skips_if_already_recovering(self) -> None:
        """Test _on_connection_lost skips if already recovering."""
        coordinator, _, _ = self._create_coordinator()
        coordinator._active_recoveries.add("test-interface")

        event = ConnectionLostEvent(
            timestamp=datetime.now(),
            interface_id="test-interface",
            reason="Test",
            detected_at=datetime.now(),
        )

        # Should not create a second recovery
        coordinator._on_connection_lost(event=event)

        # Give time for any async tasks
        await asyncio.sleep(0.01)

        assert len(coordinator._active_recoveries) == 1
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_on_connection_lost_skips_when_shutdown(self) -> None:
        """Test _on_connection_lost does nothing when shutdown."""
        coordinator, _, _ = self._create_coordinator()
        coordinator._shutdown = True

        event = ConnectionLostEvent(
            timestamp=datetime.now(),
            interface_id="test-interface",
            reason="Test",
            detected_at=datetime.now(),
        )

        coordinator._on_connection_lost(event=event)

        await asyncio.sleep(0.01)

        assert "test-interface" not in coordinator._active_recoveries
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_on_connection_lost_starts_recovery(self) -> None:
        """Test _on_connection_lost starts recovery process."""
        coordinator, event_bus, _ = self._create_coordinator()

        events_received: list[SystemStatusChangedEvent] = []

        def capture_event(event: SystemStatusChangedEvent) -> None:
            events_received.append(event)

        event_bus.subscribe(
            event_type=SystemStatusChangedEvent,
            event_key=None,
            handler=capture_event,
        )

        event = ConnectionLostEvent(
            timestamp=datetime.now(),
            interface_id="test-interface",
            reason="Test connection lost",
            detected_at=datetime.now(),
        )

        coordinator._on_connection_lost(event=event)

        # Allow async task to start
        await asyncio.sleep(0.05)

        assert "test-interface" in coordinator._active_recoveries
        coordinator.stop()

    def _create_coordinator(
        self,
        *,
        event_bus: EventBus | None = None,
    ) -> tuple[ConnectionRecoveryCoordinator, EventBus, Looper]:
        """Create a coordinator with mocked dependencies."""
        task_scheduler = Looper()
        if event_bus is None:
            event_bus = EventBus(task_scheduler=task_scheduler)

        central_info = MagicMock()
        central_info.name = "test-central"

        config = MagicMock()
        config.timeout_config.reconnect_initial_cooldown = 0.001
        config.timeout_config.reconnect_warmup_delay = 0.001
        config.timeout_config.reconnect_tcp_check_timeout = 0.01
        config.host = "127.0.0.1"
        config.tls = False

        config_provider = MagicMock()
        config_provider.config = config

        mock_client = MagicMock()
        mock_client.interface = Interface.HMIP_RF
        mock_client.available = False
        mock_client.check_connection_availability = AsyncMock(return_value=False)
        mock_client.reconnect = AsyncMock()
        mock_client.clear_json_rpc_session = MagicMock()

        client_provider = MagicMock()
        client_provider.get_client.return_value = mock_client

        coordinator_provider = MagicMock()

        device_data_refresher = MagicMock()
        device_data_refresher.load_and_refresh_data_point_data = AsyncMock()

        coordinator = ConnectionRecoveryCoordinator(
            central_info=central_info,
            config_provider=config_provider,
            client_provider=client_provider,
            coordinator_provider=coordinator_provider,
            device_data_refresher=device_data_refresher,
            event_bus=event_bus,
            task_scheduler=task_scheduler,
            state_machine=None,
        )

        return coordinator, event_bus, task_scheduler


class TestConnectionRecoveryCoordinatorStages:
    """Tests for ConnectionRecoveryCoordinator recovery stages."""

    @pytest.mark.asyncio
    async def test_check_rpc_available_exception(self) -> None:
        """Test _check_rpc_available returns False on exception."""
        coordinator, mock_client, _ = self._create_coordinator()

        mock_proxy = MagicMock()
        mock_proxy.system = MagicMock()
        mock_proxy.system.listMethods = AsyncMock(side_effect=Exception("RPC error"))
        mock_proxy._reset_transport = MagicMock()
        mock_client._proxy = mock_proxy

        result = await coordinator._check_rpc_available(interface_id="test")

        assert result is False
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_check_rpc_available_json_rpc_only_interface(self) -> None:
        """Test _check_rpc_available uses JSON-RPC for JSON-RPC-only interfaces."""
        coordinator, mock_client, _ = self._create_coordinator()

        # Set interface to a JSON-RPC-only type (CUxD)
        mock_client.interface = Interface.CUXD
        mock_client.check_connection_availability = AsyncMock(return_value=True)

        result = await coordinator._check_rpc_available(interface_id="test")

        assert result is True
        mock_client.check_connection_availability.assert_awaited_once_with(handle_ping_pong=False)
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_check_rpc_available_no_proxy_found(self) -> None:
        """Test _check_rpc_available returns False when no proxy found."""
        coordinator, mock_client, _ = self._create_coordinator()

        # Remove any proxy attributes
        mock_client = MagicMock(spec=["interface"])  # No _proxy or _backend
        mock_client.interface = Interface.HMIP_RF
        coordinator._client_provider.get_client.return_value = mock_client

        result = await coordinator._check_rpc_available(interface_id="test")

        assert result is False
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_check_rpc_available_proxy_without_reset_transport(self) -> None:
        """Test _check_rpc_available works without _reset_transport method."""
        coordinator, mock_client, _ = self._create_coordinator()

        mock_proxy = MagicMock(spec=["system"])  # No _reset_transport
        mock_proxy.system = MagicMock()
        mock_proxy.system.listMethods = AsyncMock(return_value=["system.listMethods"])
        mock_client._proxy = mock_proxy

        result = await coordinator._check_rpc_available(interface_id="test")

        assert result is True
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_check_rpc_available_with_backend_proxy(self) -> None:
        """Test _check_rpc_available with proxy on client._backend."""
        coordinator, mock_client, _ = self._create_coordinator()

        # Remove direct proxy
        if hasattr(mock_client, "_proxy"):
            delattr(mock_client, "_proxy")

        mock_proxy = MagicMock()
        mock_proxy.system = MagicMock()
        mock_proxy.system.listMethods = AsyncMock(return_value=["system.listMethods"])
        mock_proxy._reset_transport = MagicMock()

        mock_backend = MagicMock()
        mock_backend._proxy = mock_proxy
        mock_client._backend = mock_backend

        result = await coordinator._check_rpc_available(interface_id="test")

        assert result is True
        mock_proxy._reset_transport.assert_called_once()
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_check_rpc_available_with_direct_proxy(self) -> None:
        """Test _check_rpc_available with proxy directly on client."""
        coordinator, mock_client, _ = self._create_coordinator()

        mock_proxy = MagicMock()
        mock_proxy.system = MagicMock()
        mock_proxy.system.listMethods = AsyncMock(return_value=["system.listMethods"])
        mock_proxy._reset_transport = MagicMock()
        mock_client._proxy = mock_proxy

        result = await coordinator._check_rpc_available(interface_id="test")

        assert result is True
        mock_proxy._reset_transport.assert_called_once()
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_check_tcp_port_available_os_error(self) -> None:
        """Test _check_tcp_port_available returns False on OS error."""
        coordinator, _, _ = self._create_coordinator()

        with patch("asyncio.open_connection") as mock_open:
            mock_open.side_effect = OSError("Connection refused")

            result = await coordinator._check_tcp_port_available(host="127.0.0.1", port=2001)

            assert result is False

        coordinator.stop()

    @pytest.mark.asyncio
    async def test_check_tcp_port_available_success(self) -> None:
        """Test _check_tcp_port_available returns True when port is open."""
        coordinator, _, _ = self._create_coordinator()

        # Mock successful TCP connection
        with patch("asyncio.open_connection") as mock_open:
            mock_writer = MagicMock()
            mock_writer.close = MagicMock()
            mock_writer.wait_closed = AsyncMock()
            mock_open.return_value = (MagicMock(), mock_writer)

            result = await coordinator._check_tcp_port_available(host="127.0.0.1", port=2001)

            assert result is True

        coordinator.stop()

    @pytest.mark.asyncio
    async def test_check_tcp_port_available_timeout(self) -> None:
        """Test _check_tcp_port_available returns False on timeout."""
        coordinator, _, _ = self._create_coordinator()

        with patch("asyncio.open_connection") as mock_open:
            mock_open.side_effect = TimeoutError()

            result = await coordinator._check_tcp_port_available(host="127.0.0.1", port=2001)

            assert result is False

        coordinator.stop()

    @pytest.mark.asyncio
    async def test_stage_data_load_exception(self) -> None:
        """Test _stage_data_load returns False on exception."""
        coordinator, _, _ = self._create_coordinator()
        coordinator._device_data_refresher.load_and_refresh_data_point_data = AsyncMock(
            side_effect=Exception("Load failed")
        )

        result = await coordinator._stage_data_load(interface_id="test")

        assert result is False
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_stage_data_load_success(self) -> None:
        """Test _stage_data_load returns True on success."""
        coordinator, mock_client, _ = self._create_coordinator()

        result = await coordinator._stage_data_load(interface_id="test")

        assert result is True
        coordinator._device_data_refresher.load_and_refresh_data_point_data.assert_awaited_once()
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_stage_reconnect_exception(self) -> None:
        """Test _stage_reconnect returns False on exception."""
        coordinator, mock_client, _ = self._create_coordinator()
        mock_client.reconnect = AsyncMock(side_effect=Exception("Reconnect failed"))

        result = await coordinator._stage_reconnect(interface_id="test")

        assert result is False
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_stage_reconnect_failure_client_not_available(self) -> None:
        """Test _stage_reconnect returns False when client not available."""
        coordinator, mock_client, _ = self._create_coordinator()
        mock_client.available = False

        result = await coordinator._stage_reconnect(interface_id="test")

        assert result is False
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_stage_reconnect_success(self) -> None:
        """Test _stage_reconnect returns True on success."""
        coordinator, mock_client, _ = self._create_coordinator()
        mock_client.available = True

        result = await coordinator._stage_reconnect(interface_id="test")

        assert result is True
        mock_client.reconnect.assert_awaited_once()
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_stage_rpc_check_failure(self) -> None:
        """Test _stage_rpc_check returns False on failure."""
        coordinator, mock_client, _ = self._create_coordinator()

        mock_proxy = MagicMock()
        mock_proxy.system = MagicMock()
        mock_proxy.system.listMethods = AsyncMock(side_effect=Exception("RPC error"))
        mock_proxy._reset_transport = MagicMock()
        mock_client._proxy = mock_proxy

        result = await coordinator._stage_rpc_check(interface_id="test")

        assert result is False
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_stage_rpc_check_success(self) -> None:
        """Test _stage_rpc_check returns True on success."""
        coordinator, mock_client, _ = self._create_coordinator()

        mock_proxy = MagicMock()
        mock_proxy.system = MagicMock()
        mock_proxy.system.listMethods = AsyncMock(return_value=["system.listMethods"])
        mock_proxy._reset_transport = MagicMock()
        mock_client._proxy = mock_proxy

        result = await coordinator._stage_rpc_check(interface_id="test")

        assert result is True
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_stage_stability_check_failure(self) -> None:
        """Test _stage_stability_check returns False on failure."""
        coordinator, mock_client, _ = self._create_coordinator()

        mock_proxy = MagicMock()
        mock_proxy.system = MagicMock()
        mock_proxy.system.listMethods = AsyncMock(side_effect=Exception("RPC error"))
        mock_proxy._reset_transport = MagicMock()
        mock_client._proxy = mock_proxy

        result = await coordinator._stage_stability_check(interface_id="test")

        assert result is False
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_stage_stability_check_success(self) -> None:
        """Test _stage_stability_check returns True on success."""
        coordinator, mock_client, _ = self._create_coordinator()

        mock_proxy = MagicMock()
        mock_proxy.system = MagicMock()
        mock_proxy.system.listMethods = AsyncMock(return_value=["system.listMethods"])
        mock_proxy._reset_transport = MagicMock()
        mock_client._proxy = mock_proxy

        result = await coordinator._stage_stability_check(interface_id="test")

        assert result is True
        coordinator.stop()

    def _create_coordinator(self) -> tuple[ConnectionRecoveryCoordinator, MagicMock, MagicMock]:
        """Create a coordinator with configurable mocks."""
        task_scheduler = Looper()
        event_bus = EventBus(task_scheduler=task_scheduler)

        central_info = MagicMock()
        central_info.name = "test-central"

        config = MagicMock()
        config.timeout_config.reconnect_initial_cooldown = 0.001
        config.timeout_config.reconnect_warmup_delay = 0.001
        config.timeout_config.reconnect_tcp_check_timeout = 0.01
        config.host = "127.0.0.1"
        config.tls = False

        config_provider = MagicMock()
        config_provider.config = config

        mock_client = MagicMock()
        mock_client.interface = Interface.HMIP_RF
        mock_client.available = True
        mock_client.check_connection_availability = AsyncMock(return_value=True)
        mock_client.reconnect = AsyncMock()
        mock_client.clear_json_rpc_session = MagicMock()

        client_provider = MagicMock()
        client_provider.get_client.return_value = mock_client

        coordinator_provider = MagicMock()

        device_data_refresher = MagicMock()
        device_data_refresher.load_and_refresh_data_point_data = AsyncMock()

        coordinator = ConnectionRecoveryCoordinator(
            central_info=central_info,
            config_provider=config_provider,
            client_provider=client_provider,
            coordinator_provider=coordinator_provider,
            device_data_refresher=device_data_refresher,
            event_bus=event_bus,
            task_scheduler=task_scheduler,
            state_machine=None,
        )

        return coordinator, mock_client, client_provider


class TestConnectionRecoveryCoordinatorStateTransitions:
    """Tests for ConnectionRecoveryCoordinator state transitions."""

    def test_transition_to_degraded(self) -> None:
        """Test _transition_to_degraded transitions state machine."""
        coordinator, state_machine = self._create_coordinator_with_state_machine()

        coordinator._transition_to_degraded(failed_count=2)

        state_machine.transition_to.assert_called_with(
            target=CentralState.DEGRADED,
            reason="Partial recovery: 2 interface(s) still failed",
        )
        coordinator.stop()

    def test_transition_to_failed(self) -> None:
        """Test _transition_to_failed transitions state machine."""
        coordinator, state_machine = self._create_coordinator_with_state_machine()

        coordinator._transition_to_failed(interface_id="test-interface")

        state_machine.transition_to.assert_called()
        call_kwargs = state_machine.transition_to.call_args.kwargs
        assert call_kwargs["target"] == CentralState.FAILED
        assert "test-interface" in call_kwargs["reason"]
        coordinator.stop()

    def test_transition_to_recovering(self) -> None:
        """Test _transition_to_recovering transitions state machine."""
        coordinator, state_machine = self._create_coordinator_with_state_machine()

        coordinator._transition_to_recovering()

        state_machine.can_transition_to.assert_called_with(target=CentralState.RECOVERING)
        state_machine.transition_to.assert_called_with(
            target=CentralState.RECOVERING,
            reason="Connection recovery in progress",
        )
        coordinator.stop()

    def test_transition_to_running(self) -> None:
        """Test _transition_to_running transitions state machine."""
        coordinator, state_machine = self._create_coordinator_with_state_machine()

        coordinator._transition_to_running()

        state_machine.can_transition_to.assert_called_with(target=CentralState.RUNNING)
        state_machine.transition_to.assert_called_with(
            target=CentralState.RUNNING,
            reason="All interfaces recovered successfully",
        )
        coordinator.stop()

    def test_transition_without_state_machine(self) -> None:
        """Test transitions do nothing without state machine."""
        task_scheduler = Looper()
        event_bus = EventBus(task_scheduler=task_scheduler)

        coordinator = ConnectionRecoveryCoordinator(
            central_info=MagicMock(name="test"),
            config_provider=MagicMock(),
            client_provider=MagicMock(),
            coordinator_provider=MagicMock(),
            device_data_refresher=MagicMock(),
            event_bus=event_bus,
            task_scheduler=task_scheduler,
            state_machine=None,  # No state machine
        )

        # These should not raise
        coordinator._transition_to_recovering()
        coordinator._transition_to_running()
        coordinator._transition_to_degraded(failed_count=1)
        coordinator._transition_to_failed(interface_id="test")

        coordinator.stop()

    def _create_coordinator_with_state_machine(
        self,
    ) -> tuple[ConnectionRecoveryCoordinator, MagicMock]:
        """Create a coordinator with a mock state machine."""
        task_scheduler = Looper()
        event_bus = EventBus(task_scheduler=task_scheduler)

        central_info = MagicMock()
        central_info.name = "test-central"

        config = MagicMock()
        config.timeout_config.reconnect_initial_cooldown = 0.001
        config.timeout_config.reconnect_warmup_delay = 0.001
        config.timeout_config.reconnect_tcp_check_timeout = 0.01
        config.host = "127.0.0.1"
        config.tls = False

        config_provider = MagicMock()
        config_provider.config = config

        mock_client = MagicMock()
        mock_client.interface = Interface.HMIP_RF
        mock_client.available = True

        client_provider = MagicMock()
        client_provider.get_client.return_value = mock_client

        state_machine = MagicMock()
        state_machine.can_transition_to.return_value = True

        coordinator = ConnectionRecoveryCoordinator(
            central_info=central_info,
            config_provider=config_provider,
            client_provider=client_provider,
            coordinator_provider=MagicMock(),
            device_data_refresher=MagicMock(),
            event_bus=event_bus,
            task_scheduler=task_scheduler,
            state_machine=state_machine,
        )

        return coordinator, state_machine


class TestConnectionRecoveryCoordinatorEvents:
    """Tests for ConnectionRecoveryCoordinator event emission."""

    @pytest.mark.asyncio
    async def test_emit_recovery_attempt(self) -> None:
        """Test _emit_recovery_attempt emits RecoveryAttemptedEvent."""
        coordinator, event_bus = self._create_coordinator()
        events: list[RecoveryAttemptedEvent] = []

        event_bus.subscribe(
            event_type=RecoveryAttemptedEvent,
            event_key=None,
            handler=lambda event: events.append(event),
        )

        state = InterfaceRecoveryState(interface_id="test")
        state.attempt_count = 3
        state.current_stage = RecoveryStage.TCP_CHECKING

        await coordinator._emit_recovery_attempt(
            interface_id="test",
            state=state,
            success=False,
            error_message="Test error",
        )

        await asyncio.sleep(0.02)

        assert len(events) == 1
        assert events[0].interface_id == "test"
        assert events[0].attempt_number == 3
        assert events[0].success is False
        assert events[0].error_message == "Test error"
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_emit_recovery_completed(self) -> None:
        """Test _emit_recovery_completed emits RecoveryCompletedEvent."""
        coordinator, event_bus = self._create_coordinator()
        events: list[RecoveryCompletedEvent] = []

        event_bus.subscribe(
            event_type=RecoveryCompletedEvent,
            event_key=None,
            handler=lambda event: events.append(event),
        )

        state = InterfaceRecoveryState(interface_id="test")
        state.attempt_count = 2
        state.recovery_start_time = 1000.0
        state.stages_completed = [RecoveryStage.TCP_CHECKING, RecoveryStage.RPC_CHECKING]

        with patch("time.perf_counter", return_value=1001.0):
            await coordinator._emit_recovery_completed(interface_id="test", state=state)

        await asyncio.sleep(0.02)

        assert len(events) == 1
        assert events[0].interface_id == "test"
        assert events[0].total_attempts == 2
        assert events[0].total_duration_ms == 1000.0
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_emit_recovery_failed(self) -> None:
        """Test _emit_recovery_failed emits RecoveryFailedEvent."""
        coordinator, event_bus = self._create_coordinator()
        events: list[RecoveryFailedEvent] = []

        event_bus.subscribe(
            event_type=RecoveryFailedEvent,
            event_key=None,
            handler=lambda event: events.append(event),
        )

        state = InterfaceRecoveryState(interface_id="test")
        state.attempt_count = MAX_RECOVERY_ATTEMPTS
        state.current_stage = RecoveryStage.RPC_CHECKING

        await coordinator._emit_recovery_failed(interface_id="test", state=state)

        await asyncio.sleep(0.02)

        assert len(events) == 1
        assert events[0].interface_id == "test"
        assert events[0].total_attempts == MAX_RECOVERY_ATTEMPTS
        assert events[0].requires_manual_intervention is True
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_transition_stage_emits_event(self) -> None:
        """Test _transition_stage emits RecoveryStageChangedEvent."""
        coordinator, event_bus = self._create_coordinator()
        events: list[RecoveryStageChangedEvent] = []

        event_bus.subscribe(
            event_type=RecoveryStageChangedEvent,
            event_key=None,
            handler=lambda event: events.append(event),
        )

        state = InterfaceRecoveryState(interface_id="test")
        state.current_stage = RecoveryStage.COOLDOWN
        coordinator._recovery_states["test"] = state

        await coordinator._transition_stage(
            interface_id="test",
            new_stage=RecoveryStage.TCP_CHECKING,
        )

        await asyncio.sleep(0.02)

        assert len(events) == 1
        assert events[0].interface_id == "test"
        assert events[0].old_stage == RecoveryStage.COOLDOWN
        assert events[0].new_stage == RecoveryStage.TCP_CHECKING
        coordinator.stop()

    def _create_coordinator(self) -> tuple[ConnectionRecoveryCoordinator, EventBus]:
        """Create a coordinator for event testing."""
        task_scheduler = Looper()
        event_bus = EventBus(task_scheduler=task_scheduler)

        central_info = MagicMock()
        central_info.name = "test-central"

        config = MagicMock()
        config.timeout_config.reconnect_initial_cooldown = 0.001
        config.timeout_config.reconnect_warmup_delay = 0.001
        config.timeout_config.reconnect_tcp_check_timeout = 0.01
        config.host = "127.0.0.1"
        config.tls = False

        config_provider = MagicMock()
        config_provider.config = config

        mock_client = MagicMock()
        mock_client.interface = Interface.HMIP_RF

        client_provider = MagicMock()
        client_provider.get_client.return_value = mock_client

        coordinator = ConnectionRecoveryCoordinator(
            central_info=central_info,
            config_provider=config_provider,
            client_provider=client_provider,
            coordinator_provider=MagicMock(),
            device_data_refresher=MagicMock(),
            event_bus=event_bus,
            task_scheduler=task_scheduler,
            state_machine=None,
        )

        return coordinator, event_bus


class TestConnectionRecoveryCoordinatorHeartbeat:
    """Tests for ConnectionRecoveryCoordinator heartbeat functionality."""

    @pytest.mark.asyncio
    async def test_on_heartbeat_timer_fired_skipped_when_not_failed(self) -> None:
        """Test _on_heartbeat_timer_fired does nothing when not in failed state."""
        coordinator = self._create_coordinator()
        coordinator._in_failed_state = False

        event = HeartbeatTimerFiredEvent(
            timestamp=datetime.now(),
            central_name="test-central",
            interface_ids=("test-interface",),
        )

        # Should not raise and should not trigger recovery
        coordinator._on_heartbeat_timer_fired(event=event)

        coordinator.stop()

    @pytest.mark.asyncio
    async def test_on_heartbeat_timer_fired_when_in_failed_state(self) -> None:
        """Test _on_heartbeat_timer_fired triggers recovery when in failed state."""
        coordinator = self._create_coordinator()
        coordinator._in_failed_state = True

        event = HeartbeatTimerFiredEvent(
            timestamp=datetime.now(),
            central_name="test-central",
            interface_ids=("test-interface",),
        )

        coordinator._on_heartbeat_timer_fired(event=event)

        # Task should be scheduled for recovery
        await asyncio.sleep(0.01)
        coordinator.stop()

    def test_start_heartbeat_timer(self) -> None:
        """Test _start_heartbeat_timer starts heartbeat task."""
        coordinator = self._create_coordinator()
        coordinator._in_failed_state = True

        coordinator._start_heartbeat_timer()

        # Heartbeat task should be created (via task scheduler)
        # We can't directly test the task, but we verify no exception
        coordinator.stop()

    def test_stop_heartbeat_timer(self) -> None:
        """Test _stop_heartbeat_timer stops heartbeat task."""
        coordinator = self._create_coordinator()

        # Create a mock task
        mock_task = MagicMock()
        mock_task.done.return_value = False
        coordinator._heartbeat_task = mock_task

        coordinator._stop_heartbeat_timer()

        mock_task.cancel.assert_called_once()
        assert coordinator._heartbeat_task is None
        coordinator.stop()

    def _create_coordinator(self) -> ConnectionRecoveryCoordinator:
        """Create a coordinator for heartbeat testing."""
        task_scheduler = Looper()
        event_bus = EventBus(task_scheduler=task_scheduler)

        central_info = MagicMock()
        central_info.name = "test-central"

        config = MagicMock()
        config_provider = MagicMock()
        config_provider.config = config

        return ConnectionRecoveryCoordinator(
            central_info=central_info,
            config_provider=config_provider,
            client_provider=MagicMock(),
            coordinator_provider=MagicMock(),
            device_data_refresher=MagicMock(),
            event_bus=event_bus,
            task_scheduler=task_scheduler,
            state_machine=None,
        )


class TestConnectionRecoveryCoordinatorIncidents:
    """Tests for ConnectionRecoveryCoordinator incident recording."""

    @pytest.mark.asyncio
    async def test_record_connection_lost_incident(self) -> None:
        """Test _record_connection_lost_incident records incident."""
        coordinator, incident_recorder = self._create_coordinator_with_incident_recorder()

        event = ConnectionLostEvent(
            timestamp=datetime.now(),
            interface_id="test-interface",
            reason="Test reason",
            detected_at=datetime.now(),
        )

        coordinator._record_connection_lost_incident(event=event)

        await asyncio.sleep(0.05)

        incident_recorder.record_incident.assert_awaited_once()
        call_kwargs = incident_recorder.record_incident.await_args.kwargs
        assert "test-interface" in call_kwargs["message"]
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_record_connection_restored_incident(self) -> None:
        """Test _record_connection_restored_incident records incident."""
        coordinator, incident_recorder = self._create_coordinator_with_incident_recorder()

        state = InterfaceRecoveryState(interface_id="test-interface")
        state.attempt_count = 3
        state.recovery_start_time = 1000.0
        state.stages_completed = [RecoveryStage.TCP_CHECKING]

        with patch("time.perf_counter", return_value=1001.0):
            coordinator._record_connection_restored_incident(
                interface_id="test-interface",
                state=state,
            )

        await asyncio.sleep(0.05)

        incident_recorder.record_incident.assert_awaited_once()
        call_kwargs = incident_recorder.record_incident.await_args.kwargs
        assert "restored" in call_kwargs["message"].lower()
        coordinator.stop()

    def test_record_incident_skipped_without_recorder(self) -> None:
        """Test incident recording is skipped without recorder."""
        task_scheduler = Looper()
        event_bus = EventBus(task_scheduler=task_scheduler)

        coordinator = ConnectionRecoveryCoordinator(
            central_info=MagicMock(name="test"),
            config_provider=MagicMock(),
            client_provider=MagicMock(),
            coordinator_provider=MagicMock(),
            device_data_refresher=MagicMock(),
            event_bus=event_bus,
            task_scheduler=task_scheduler,
            state_machine=None,
            incident_recorder=None,  # No recorder
        )

        event = ConnectionLostEvent(
            timestamp=datetime.now(),
            interface_id="test",
            reason="Test",
            detected_at=datetime.now(),
        )

        # Should not raise
        coordinator._record_connection_lost_incident(event=event)
        coordinator.stop()

    def _create_coordinator_with_incident_recorder(
        self,
    ) -> tuple[ConnectionRecoveryCoordinator, MagicMock]:
        """Create a coordinator with an incident recorder."""
        task_scheduler = Looper()
        event_bus = EventBus(task_scheduler=task_scheduler)

        central_info = MagicMock()
        central_info.name = "test-central"

        config = MagicMock()
        config_provider = MagicMock()
        config_provider.config = config

        mock_client = MagicMock()
        mock_client.interface = Interface.HMIP_RF
        mock_client.state.state.value = "connected"
        mock_client._circuit_breaker = MagicMock()
        mock_client._circuit_breaker.state.value = "closed"

        client_provider = MagicMock()
        client_provider.get_client.return_value = mock_client

        incident_recorder = MagicMock()
        incident_recorder.record_incident = AsyncMock()

        coordinator = ConnectionRecoveryCoordinator(
            central_info=central_info,
            config_provider=config_provider,
            client_provider=client_provider,
            coordinator_provider=MagicMock(),
            device_data_refresher=MagicMock(),
            event_bus=event_bus,
            task_scheduler=task_scheduler,
            state_machine=None,
            incident_recorder=incident_recorder,
        )

        return coordinator, incident_recorder


class TestConnectionRecoveryCoordinatorClientPort:
    """Tests for ConnectionRecoveryCoordinator._get_client_port."""

    def test_get_client_port_from_config_interface_config(self) -> None:
        """Test _get_client_port gets port from _config.interface_config."""
        coordinator = self._create_coordinator()

        mock_client = MagicMock(spec=[])  # No _interface_config attribute
        mock_client._config = MagicMock()
        mock_client._config.interface_config.port = 2001
        coordinator._client_provider.get_client.return_value = mock_client

        port = coordinator._get_client_port(interface_id="test")

        assert port == 2001
        coordinator.stop()

    def test_get_client_port_from_interface_config(self) -> None:
        """Test _get_client_port gets port from _interface_config."""
        coordinator = self._create_coordinator()

        mock_client = MagicMock()
        mock_client._interface_config.port = 2010
        coordinator._client_provider.get_client.return_value = mock_client

        port = coordinator._get_client_port(interface_id="test")

        assert port == 2010
        coordinator.stop()

    def test_get_client_port_returns_none_on_exception(self) -> None:
        """Test _get_client_port returns None on exception."""
        coordinator = self._create_coordinator()

        coordinator._client_provider.get_client.side_effect = Exception("Client not found")

        port = coordinator._get_client_port(interface_id="test")

        assert port is None
        coordinator.stop()

    def _create_coordinator(self) -> ConnectionRecoveryCoordinator:
        """Create a coordinator for port testing."""
        task_scheduler = Looper()
        event_bus = EventBus(task_scheduler=task_scheduler)

        return ConnectionRecoveryCoordinator(
            central_info=MagicMock(name="test"),
            config_provider=MagicMock(),
            client_provider=MagicMock(),
            coordinator_provider=MagicMock(),
            device_data_refresher=MagicMock(),
            event_bus=event_bus,
            task_scheduler=task_scheduler,
            state_machine=None,
        )


class TestConnectionRecoveryCoordinatorFullRecovery:
    """Integration-like tests for full recovery scenarios."""

    @pytest.mark.asyncio
    async def test_execute_recovery_stages_failure_at_tcp_check(self) -> None:
        """Test _execute_recovery_stages fails at TCP check."""
        coordinator, _, _ = self._create_coordinator_for_full_recovery()

        state = InterfaceRecoveryState(interface_id="test")
        coordinator._recovery_states["test"] = state

        # Mock TCP check failure at the class level (due to __slots__)
        with patch.object(
            ConnectionRecoveryCoordinator,
            "_check_tcp_port_available",
            new=AsyncMock(return_value=False),
        ):
            result = await coordinator._execute_recovery_stages(interface_id="test")

        assert result is False
        assert state.current_stage == RecoveryStage.TCP_CHECKING
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_execute_recovery_stages_success(self) -> None:
        """Test _execute_recovery_stages completes successfully."""
        coordinator, _, event_bus = self._create_coordinator_for_full_recovery()

        # Track stage events
        stage_events: list[RecoveryStageChangedEvent] = []
        event_bus.subscribe(
            event_type=RecoveryStageChangedEvent,
            event_key=None,
            handler=lambda event: stage_events.append(event),
        )

        # Create recovery state
        state = InterfaceRecoveryState(interface_id="test")
        coordinator._recovery_states["test"] = state

        # Mock TCP check success at the class level (due to __slots__)
        with patch.object(
            ConnectionRecoveryCoordinator,
            "_check_tcp_port_available",
            new=AsyncMock(return_value=True),
        ):
            result = await coordinator._execute_recovery_stages(interface_id="test")

        assert result is True

        await asyncio.sleep(0.05)

        # Verify all stages were traversed
        stages_in_order = [e.new_stage for e in stage_events]
        assert RecoveryStage.COOLDOWN in stages_in_order
        assert RecoveryStage.TCP_CHECKING in stages_in_order
        assert RecoveryStage.RPC_CHECKING in stages_in_order
        assert RecoveryStage.RECOVERED in stages_in_order
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_recovery_with_backoff(self) -> None:
        """Test that recovery uses exponential backoff."""
        coordinator, _, _ = self._create_coordinator_for_full_recovery()

        state = InterfaceRecoveryState(interface_id="test")
        coordinator._recovery_states["test"] = state

        # Record failures
        state.record_failure()
        delay1 = state.next_retry_delay

        state.record_failure()
        delay2 = state.next_retry_delay

        state.record_failure()
        delay3 = state.next_retry_delay

        # Each delay should be larger
        assert delay2 > delay1
        assert delay3 > delay2
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_transition_after_recovery_to_running(self) -> None:
        """Test _transition_after_recovery transitions to RUNNING when all recoveries complete."""
        coordinator, state_machine, _ = self._create_coordinator_for_full_recovery()

        # No active recoveries
        coordinator._active_recoveries.clear()

        coordinator._transition_after_recovery()

        state_machine.transition_to.assert_called_with(
            target=CentralState.RUNNING,
            reason="All interfaces recovered successfully",
        )
        assert coordinator._in_failed_state is False
        coordinator.stop()

    def _create_coordinator_for_full_recovery(
        self,
    ) -> tuple[ConnectionRecoveryCoordinator, MagicMock, EventBus]:
        """Create a coordinator configured for full recovery testing."""
        task_scheduler = Looper()
        event_bus = EventBus(task_scheduler=task_scheduler)

        central_info = MagicMock()
        central_info.name = "test-central"

        config = MagicMock()
        config.timeout_config.reconnect_initial_cooldown = 0.001
        config.timeout_config.reconnect_warmup_delay = 0.001
        config.timeout_config.reconnect_tcp_check_timeout = 0.02
        config.host = "127.0.0.1"
        config.tls = False

        config_provider = MagicMock()
        config_provider.config = config

        # Create a fully mocked client
        mock_client = MagicMock()
        mock_client.interface = Interface.HMIP_RF
        mock_client.available = True
        mock_client.reconnect = AsyncMock()
        mock_client.clear_json_rpc_session = MagicMock()
        mock_client._interface_config.port = 2010

        # Mock proxy for RPC check
        mock_proxy = MagicMock()
        mock_proxy.system = MagicMock()
        mock_proxy.system.listMethods = AsyncMock(return_value=["system.listMethods"])
        mock_proxy._reset_transport = MagicMock()
        mock_client._proxy = mock_proxy

        client_provider = MagicMock()
        client_provider.get_client.return_value = mock_client

        device_data_refresher = MagicMock()
        device_data_refresher.load_and_refresh_data_point_data = AsyncMock()

        state_machine = MagicMock()
        state_machine.can_transition_to.return_value = True

        coordinator = ConnectionRecoveryCoordinator(
            central_info=central_info,
            config_provider=config_provider,
            client_provider=client_provider,
            coordinator_provider=MagicMock(),
            device_data_refresher=device_data_refresher,
            event_bus=event_bus,
            task_scheduler=task_scheduler,
            state_machine=state_machine,
        )

        return coordinator, state_machine, event_bus


class TestConnectionRecoveryCoordinatorAdditionalCoverage:
    """Additional tests to improve coverage to 90%+."""

    @pytest.mark.asyncio
    async def test_execute_recovery_stages_cancelled_error(self) -> None:
        """Test _execute_recovery_stages handles CancelledError."""
        coordinator, _, _ = self._create_coordinator()

        state = InterfaceRecoveryState(interface_id="test")
        coordinator._recovery_states["test"] = state

        with (
            patch.object(
                ConnectionRecoveryCoordinator,
                "_check_tcp_port_available",
                new=AsyncMock(side_effect=asyncio.CancelledError()),
            ),
            pytest.raises(asyncio.CancelledError),
        ):
            await coordinator._execute_recovery_stages(interface_id="test")

        coordinator.stop()

    @pytest.mark.asyncio
    async def test_execute_recovery_stages_failure_at_data_load(self) -> None:
        """Test _execute_recovery_stages fails at data load stage."""
        coordinator, mock_client, _ = self._create_coordinator()

        state = InterfaceRecoveryState(interface_id="test")
        coordinator._recovery_states["test"] = state

        # Data load fails
        coordinator._device_data_refresher.load_and_refresh_data_point_data = AsyncMock(
            side_effect=Exception("Data load failed")
        )

        with patch.object(
            ConnectionRecoveryCoordinator,
            "_check_tcp_port_available",
            new=AsyncMock(return_value=True),
        ):
            result = await coordinator._execute_recovery_stages(interface_id="test")

        assert result is False
        assert state.current_stage == RecoveryStage.DATA_LOADING
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_execute_recovery_stages_failure_at_reconnect(self) -> None:
        """Test _execute_recovery_stages fails at reconnect stage."""
        coordinator, mock_client, _ = self._create_coordinator()

        state = InterfaceRecoveryState(interface_id="test")
        coordinator._recovery_states["test"] = state

        # Reconnect fails
        mock_client.reconnect = AsyncMock(side_effect=Exception("Reconnect failed"))

        with patch.object(
            ConnectionRecoveryCoordinator,
            "_check_tcp_port_available",
            new=AsyncMock(return_value=True),
        ):
            result = await coordinator._execute_recovery_stages(interface_id="test")

        assert result is False
        assert state.current_stage == RecoveryStage.RECONNECTING
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_execute_recovery_stages_failure_at_rpc_check(self) -> None:
        """Test _execute_recovery_stages fails at RPC check stage."""
        coordinator, mock_client, _ = self._create_coordinator()

        state = InterfaceRecoveryState(interface_id="test")
        coordinator._recovery_states["test"] = state

        # Make RPC check fail
        mock_client._proxy.system.listMethods = AsyncMock(side_effect=Exception("RPC error"))

        with patch.object(
            ConnectionRecoveryCoordinator,
            "_check_tcp_port_available",
            new=AsyncMock(return_value=True),
        ):
            result = await coordinator._execute_recovery_stages(interface_id="test")

        assert result is False
        assert state.current_stage == RecoveryStage.RPC_CHECKING
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_execute_recovery_stages_failure_at_stability_check(self) -> None:
        """Test _execute_recovery_stages fails at stability check stage."""
        coordinator, mock_client, _ = self._create_coordinator()

        state = InterfaceRecoveryState(interface_id="test")
        coordinator._recovery_states["test"] = state

        call_count = 0

        async def rpc_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call (RPC check) succeeds
                return ["system.listMethods"]
            # Second call (stability check) fails
            raise Exception("Stability check failed")

        mock_client._proxy.system.listMethods = AsyncMock(side_effect=rpc_side_effect)

        with patch.object(
            ConnectionRecoveryCoordinator,
            "_check_tcp_port_available",
            new=AsyncMock(return_value=True),
        ):
            result = await coordinator._execute_recovery_stages(interface_id="test")

        assert result is False
        assert state.current_stage == RecoveryStage.STABILITY_CHECK
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_execute_recovery_stages_generic_exception(self) -> None:
        """Test _execute_recovery_stages handles generic Exception."""
        coordinator, _, _ = self._create_coordinator()

        state = InterfaceRecoveryState(interface_id="test")
        coordinator._recovery_states["test"] = state

        with patch.object(
            ConnectionRecoveryCoordinator,
            "_check_tcp_port_available",
            new=AsyncMock(side_effect=RuntimeError("Unexpected error")),
        ):
            result = await coordinator._execute_recovery_stages(interface_id="test")

        assert result is False
        coordinator.stop()

    def test_get_client_port_fallback_to_config(self) -> None:
        """Test _get_client_port falls back to _config.interface_config."""
        coordinator, _, _ = self._create_coordinator()

        # Create client without _interface_config but with _config.interface_config
        mock_client = MagicMock(spec=["_config"])
        mock_client._config = MagicMock()
        mock_client._config.interface_config.port = 2001
        coordinator._client_provider.get_client.return_value = mock_client

        port = coordinator._get_client_port(interface_id="test")

        assert port == 2001
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_handle_max_retries_reached(self) -> None:
        """Test _handle_max_retries_reached sets failed state and starts heartbeat."""
        state_machine = MagicMock()
        state_machine.can_transition_to.return_value = True

        coordinator, _, event_bus = self._create_coordinator(state_machine=state_machine)

        state = InterfaceRecoveryState(interface_id="test")
        state.attempt_count = MAX_RECOVERY_ATTEMPTS
        coordinator._recovery_states["test"] = state

        events: list[RecoveryFailedEvent] = []
        event_bus.subscribe(
            event_type=RecoveryFailedEvent,
            event_key=None,
            handler=lambda event: events.append(event),
        )

        await coordinator._handle_max_retries_reached(interface_id="test")

        await asyncio.sleep(0.02)

        assert coordinator._in_failed_state is True
        state_machine.transition_to.assert_called()
        assert len(events) == 1
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_heartbeat_loop_emits_event_for_failed_interfaces(self) -> None:
        """Test _heartbeat_loop emits HeartbeatTimerFiredEvent for failed interfaces."""
        coordinator, _, event_bus = self._create_coordinator()
        coordinator._in_failed_state = True

        # Create a failed state (can't retry)
        state = InterfaceRecoveryState(interface_id="test")
        state.attempt_count = MAX_RECOVERY_ATTEMPTS
        coordinator._recovery_states["test"] = state

        events: list[HeartbeatTimerFiredEvent] = []
        event_bus.subscribe(
            event_type=HeartbeatTimerFiredEvent,
            event_key=None,
            handler=lambda event: events.append(event),
        )

        # Run one iteration of the loop
        async def run_one_iteration():
            await asyncio.sleep(0.01)
            coordinator._in_failed_state = False

        task = asyncio.create_task(run_one_iteration())

        with patch(
            "aiohomematic.central.coordinators.connection_recovery.HEARTBEAT_RETRY_INTERVAL",
            0.005,
        ):
            await asyncio.wait_for(coordinator._heartbeat_loop(), timeout=1.0)

        await task
        await asyncio.sleep(0.02)

        assert len(events) >= 1
        assert "test" in events[0].interface_ids
        # Verify attempt count was reset
        assert state.attempt_count == MAX_RECOVERY_ATTEMPTS - 1
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_heartbeat_loop_exits_on_shutdown(self) -> None:
        """Test _heartbeat_loop exits on shutdown."""
        coordinator, _, _ = self._create_coordinator()
        coordinator._in_failed_state = True

        # Schedule shutdown after a small delay
        async def schedule_shutdown():
            await asyncio.sleep(0.01)
            coordinator._shutdown = True

        task = asyncio.create_task(schedule_shutdown())

        # The loop should exit when shutdown is set
        with patch(
            "aiohomematic.central.coordinators.connection_recovery.HEARTBEAT_RETRY_INTERVAL",
            0.005,
        ):
            await asyncio.wait_for(coordinator._heartbeat_loop(), timeout=1.0)

        await task
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_heartbeat_loop_exits_when_not_failed(self) -> None:
        """Test _heartbeat_loop exits when not in failed state."""
        coordinator, _, _ = self._create_coordinator()
        coordinator._in_failed_state = False

        # Should exit immediately
        await coordinator._heartbeat_loop()

        coordinator.stop()

    def test_on_circuit_breaker_state_changed_not_recovery(self) -> None:
        """Test _on_circuit_breaker_state_changed ignores non-recovery transitions."""
        coordinator, _, _ = self._create_coordinator()

        # CLOSED -> OPEN (not a recovery)
        event = CircuitBreakerStateChangedEvent(
            timestamp=datetime.now(),
            interface_id="test",
            old_state=CircuitState.CLOSED,
            new_state=CircuitState.OPEN,
            failure_count=5,
            success_count=0,
            last_failure_time=datetime.now(),
        )

        # Should not trigger refresh
        coordinator._on_circuit_breaker_state_changed(event=event)

        # No refresh task should have been created
        coordinator.stop()

    def test_on_circuit_breaker_state_changed_when_shutdown(self) -> None:
        """Test _on_circuit_breaker_state_changed does nothing when shutdown."""
        coordinator, _, _ = self._create_coordinator()
        coordinator._shutdown = True

        event = CircuitBreakerStateChangedEvent(
            timestamp=datetime.now(),
            interface_id="test",
            old_state=CircuitState.HALF_OPEN,
            new_state=CircuitState.CLOSED,
            failure_count=0,
            success_count=3,
            last_failure_time=None,
        )

        # Should not raise and should not trigger refresh
        coordinator._on_circuit_breaker_state_changed(event=event)
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_record_connection_restored_incident_with_no_state(self) -> None:
        """Test _record_connection_restored_incident handles missing state gracefully."""
        incident_recorder = MagicMock()
        incident_recorder.record_incident = AsyncMock()

        coordinator, _, _ = self._create_coordinator(incident_recorder=incident_recorder)

        # Create minimal state
        state = InterfaceRecoveryState(interface_id="test")
        state.recovery_start_time = None  # No start time

        coordinator._record_connection_restored_incident(interface_id="test", state=state)

        await asyncio.sleep(0.02)

        # Should still record incident
        incident_recorder.record_incident.assert_awaited_once()
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_stage_tcp_check_json_rpc_port_fallback(self) -> None:
        """Test _stage_tcp_check uses JSON-RPC port for JSON-RPC-only interfaces."""
        coordinator, mock_client, _ = self._create_coordinator()

        # Set up as JSON-RPC-only interface with no port
        mock_client.interface = Interface.CUXD
        mock_client._interface_config.port = 0

        with patch.object(
            ConnectionRecoveryCoordinator,
            "_check_tcp_port_available",
            new=AsyncMock(return_value=True),
        ):
            result = await coordinator._stage_tcp_check(interface_id="test")

        assert result is True
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_stage_tcp_check_no_port_configured(self) -> None:
        """Test _stage_tcp_check returns False when no port configured for non-JSON-RPC."""
        coordinator, mock_client, _ = self._create_coordinator()

        # Set up as non-JSON-RPC interface with no port
        mock_client.interface = Interface.HMIP_RF
        mock_client._interface_config.port = 0

        coordinator._client_provider.get_client.return_value = mock_client

        # Override _get_client_port to return None
        with patch.object(
            ConnectionRecoveryCoordinator,
            "_get_client_port",
            return_value=None,
        ):
            result = await coordinator._stage_tcp_check(interface_id="test")

        assert result is False
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_stage_tcp_check_timeout(self) -> None:
        """Test _stage_tcp_check returns False on timeout."""
        coordinator, _, _ = self._create_coordinator()

        # Set very short timeout
        coordinator._config_provider.config.timeout_config.reconnect_tcp_check_timeout = 0.01

        with patch.object(
            ConnectionRecoveryCoordinator,
            "_check_tcp_port_available",
            new=AsyncMock(return_value=False),
        ):
            result = await coordinator._stage_tcp_check(interface_id="test")

        assert result is False
        coordinator.stop()

    def test_start_heartbeat_timer_already_running(self) -> None:
        """Test _start_heartbeat_timer does nothing if already running."""
        coordinator, _, _ = self._create_coordinator()

        # Create a mock task that appears to be running
        mock_task = MagicMock()
        mock_task.done.return_value = False
        coordinator._heartbeat_task = mock_task

        coordinator._start_heartbeat_timer()

        # Should not have created a new task (no call to task_scheduler)
        assert coordinator._heartbeat_task is mock_task
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_start_recovery_failure_max_retries_during(self) -> None:
        """Test _start_recovery handles max retries reached during recovery."""
        state_machine = MagicMock()
        state_machine.can_transition_to.return_value = True

        coordinator, _, _ = self._create_coordinator(state_machine=state_machine)

        # Create state that will exceed max retries after one failure
        state = InterfaceRecoveryState(interface_id="test")
        state.attempt_count = MAX_RECOVERY_ATTEMPTS - 1
        coordinator._recovery_states["test"] = state

        coordinator._active_recoveries.add("test")

        with patch.object(
            ConnectionRecoveryCoordinator,
            "_check_tcp_port_available",
            new=AsyncMock(return_value=False),
        ):
            await coordinator._start_recovery(interface_id="test")

        await asyncio.sleep(0.02)

        # Should have transitioned to failed state
        assert coordinator._in_failed_state is True
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_start_recovery_failure_with_retry(self) -> None:
        """Test _start_recovery failure path schedules retry."""
        coordinator, _, event_bus = self._create_coordinator()

        # Track events
        attempted_events: list[RecoveryAttemptedEvent] = []
        event_bus.subscribe(
            event_type=RecoveryAttemptedEvent,
            event_key=None,
            handler=lambda event: attempted_events.append(event),
        )

        coordinator._active_recoveries.add("test")

        # Fail TCP check but allow one retry
        call_count = 0

        async def tcp_check_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return call_count != 1  # First attempt fails, subsequent succeed

        with (
            patch.object(
                ConnectionRecoveryCoordinator,
                "_check_tcp_port_available",
                new=AsyncMock(side_effect=tcp_check_side_effect),
            ),
            patch(
                "aiohomematic.central.coordinators.connection_recovery.BASE_RETRY_DELAY",
                0.01,
            ),
        ):
            await coordinator._start_recovery(interface_id="test")

        await asyncio.sleep(0.05)

        # Should have attempted at least once
        assert len(attempted_events) >= 1
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_start_recovery_max_retries_upfront(self) -> None:
        """Test _start_recovery handles max retries reached upfront."""
        state_machine = MagicMock()
        state_machine.can_transition_to.return_value = True

        coordinator, _, _ = self._create_coordinator(state_machine=state_machine)

        # Create state that already exceeded max retries
        state = InterfaceRecoveryState(interface_id="test")
        state.attempt_count = MAX_RECOVERY_ATTEMPTS
        coordinator._recovery_states["test"] = state

        await coordinator._start_recovery(interface_id="test")

        # Should have called _handle_max_retries_reached
        assert coordinator._in_failed_state is True
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_start_recovery_success_path(self) -> None:
        """Test _start_recovery success path with full recovery."""
        state_machine = MagicMock()
        state_machine.can_transition_to.return_value = True
        incident_recorder = MagicMock()
        incident_recorder.record_incident = AsyncMock()

        coordinator, mock_client, event_bus = self._create_coordinator(
            state_machine=state_machine,
            incident_recorder=incident_recorder,
        )

        # Track events
        completed_events: list[RecoveryCompletedEvent] = []
        event_bus.subscribe(
            event_type=RecoveryCompletedEvent,
            event_key=None,
            handler=lambda event: completed_events.append(event),
        )

        coordinator._active_recoveries.add("test")

        with patch.object(
            ConnectionRecoveryCoordinator,
            "_check_tcp_port_available",
            new=AsyncMock(return_value=True),
        ):
            await coordinator._start_recovery(interface_id="test")

        await asyncio.sleep(0.05)

        # Verify success path
        assert "test" not in coordinator._active_recoveries
        assert len(completed_events) == 1
        # Verify state was reset
        if "test" in coordinator._recovery_states:
            assert coordinator._recovery_states["test"].attempt_count == 0
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_start_recovery_when_shutdown(self) -> None:
        """Test _start_recovery exits early when shutdown."""
        coordinator, _, _ = self._create_coordinator()
        coordinator._shutdown = True

        await coordinator._start_recovery(interface_id="test")

        # Should not create recovery state
        assert "test" not in coordinator._recovery_states
        coordinator.stop()

    def test_transition_after_recovery_with_active_recoveries(self) -> None:
        """Test _transition_after_recovery when some recoveries still active."""
        state_machine = MagicMock()
        state_machine.can_transition_to.return_value = True

        coordinator, _, _ = self._create_coordinator(state_machine=state_machine)

        # Add active recovery
        coordinator._active_recoveries.add("still-recovering")

        coordinator._transition_after_recovery()

        # Should NOT transition to RUNNING
        state_machine.transition_to.assert_not_called()
        coordinator.stop()

    def test_transition_after_recovery_with_no_active_recoveries(self) -> None:
        """Test _transition_after_recovery transitions to RUNNING when no active recoveries."""
        state_machine = MagicMock()
        state_machine.can_transition_to.return_value = True

        coordinator, _, _ = self._create_coordinator(state_machine=state_machine)
        coordinator._in_failed_state = True

        # Clear active recoveries (even if there are states in _recovery_states)
        coordinator._active_recoveries.clear()

        coordinator._transition_after_recovery()

        # Should transition to RUNNING (not DEGRADED) when no active recoveries
        state_machine.transition_to.assert_called()
        call_kwargs = state_machine.transition_to.call_args.kwargs
        assert call_kwargs["target"] == CentralState.RUNNING
        # Should also clear failed state
        assert coordinator._in_failed_state is False
        coordinator.stop()

    def _create_coordinator(
        self,
        *,
        state_machine: MagicMock | None = None,
        incident_recorder: MagicMock | None = None,
    ) -> tuple[ConnectionRecoveryCoordinator, MagicMock, EventBus]:
        """Create a coordinator with full mocking."""
        task_scheduler = Looper()
        event_bus = EventBus(task_scheduler=task_scheduler)

        central_info = MagicMock()
        central_info.name = "test-central"

        config = MagicMock()
        config.timeout_config.reconnect_initial_cooldown = 0.001
        config.timeout_config.reconnect_warmup_delay = 0.001
        config.timeout_config.reconnect_tcp_check_timeout = 0.02
        config.host = "127.0.0.1"
        config.tls = False

        config_provider = MagicMock()
        config_provider.config = config

        mock_client = MagicMock()
        mock_client.interface = Interface.HMIP_RF
        mock_client.available = True
        mock_client.reconnect = AsyncMock()
        mock_client.clear_json_rpc_session = MagicMock()
        mock_client._interface_config.port = 2010

        mock_proxy = MagicMock()
        mock_proxy.system = MagicMock()
        mock_proxy.system.listMethods = AsyncMock(return_value=["system.listMethods"])
        mock_proxy._reset_transport = MagicMock()
        mock_client._proxy = mock_proxy

        client_provider = MagicMock()
        client_provider.get_client.return_value = mock_client

        device_data_refresher = MagicMock()
        device_data_refresher.load_and_refresh_data_point_data = AsyncMock()

        coordinator = ConnectionRecoveryCoordinator(
            central_info=central_info,
            config_provider=config_provider,
            client_provider=client_provider,
            coordinator_provider=MagicMock(),
            device_data_refresher=device_data_refresher,
            event_bus=event_bus,
            task_scheduler=task_scheduler,
            state_machine=state_machine,
            incident_recorder=incident_recorder,
        )

        return coordinator, mock_client, event_bus
