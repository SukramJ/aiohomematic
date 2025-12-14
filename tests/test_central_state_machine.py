# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Tests for the Central State Machine architecture."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

from aiohomematic.central.event_bus import EventBus
from aiohomematic.central.health import CentralHealth, ConnectionHealth, HealthTracker
from aiohomematic.central.integration_events import SystemStatusEvent
from aiohomematic.central.recovery import DataLoadStage, RecoveryCoordinator, RecoveryResult
from aiohomematic.central.state_machine import (
    VALID_CENTRAL_TRANSITIONS,
    CentralStateMachine,
    InvalidCentralStateTransitionError,
)
from aiohomematic.client.circuit_breaker import CircuitState
from aiohomematic.const import CentralState, ClientState, Interface


class TestCentralStateMachine:
    """Tests for CentralStateMachine."""

    def test_can_transition_to(self) -> None:
        """Test that can_transition_to returns correct results."""
        event_bus = MagicMock(spec=EventBus)
        sm = CentralStateMachine(central_name="test-central", event_bus=event_bus)

        assert sm.can_transition_to(target=CentralState.INITIALIZING) is True
        assert sm.can_transition_to(target=CentralState.RUNNING) is False
        assert sm.can_transition_to(target=CentralState.STOPPED) is True

    def test_degraded_to_running(self) -> None:
        """Test transition from DEGRADED to RUNNING when all clients connect."""
        event_bus = MagicMock(spec=EventBus)
        sm = CentralStateMachine(central_name="test-central", event_bus=event_bus)

        sm.transition_to(target=CentralState.INITIALIZING, reason="test")
        sm.transition_to(target=CentralState.DEGRADED, reason="test")
        sm.transition_to(target=CentralState.RUNNING, reason="all clients connected")

        assert sm.is_running is True

    def test_event_publishing(self) -> None:
        """Test that state changes publish events."""
        event_bus = MagicMock(spec=EventBus)
        sm = CentralStateMachine(central_name="test-central", event_bus=event_bus)

        sm.transition_to(target=CentralState.INITIALIZING, reason="test")

        event_bus.publish_sync.assert_called_once()
        call_args = event_bus.publish_sync.call_args
        event = call_args.kwargs["event"]
        assert isinstance(event, SystemStatusEvent)
        assert event.central_state == CentralState.INITIALIZING

    def test_initial_state(self) -> None:
        """Test that the initial state is STARTING."""
        event_bus = MagicMock(spec=EventBus)
        sm = CentralStateMachine(central_name="test-central", event_bus=event_bus)
        assert sm.state == CentralState.STARTING

    def test_invalid_transition_raises(self) -> None:
        """Test that invalid transitions raise an exception."""
        event_bus = MagicMock(spec=EventBus)
        sm = CentralStateMachine(central_name="test-central", event_bus=event_bus)

        # STARTING -> RUNNING is invalid (must go through INITIALIZING)
        with pytest.raises(InvalidCentralStateTransitionError):
            sm.transition_to(target=CentralState.RUNNING, reason="test")

    def test_is_degraded(self) -> None:
        """Test is_degraded property."""
        event_bus = MagicMock(spec=EventBus)
        sm = CentralStateMachine(central_name="test-central", event_bus=event_bus)

        assert sm.is_degraded is False

        sm.transition_to(target=CentralState.INITIALIZING, reason="test")
        sm.transition_to(target=CentralState.DEGRADED, reason="test")

        assert sm.is_degraded is True

    def test_is_running(self) -> None:
        """Test is_running property."""
        event_bus = MagicMock(spec=EventBus)
        sm = CentralStateMachine(central_name="test-central", event_bus=event_bus)

        assert sm.is_running is False

        sm.transition_to(target=CentralState.INITIALIZING, reason="test")
        sm.transition_to(target=CentralState.RUNNING, reason="test")

        assert sm.is_running is True

    def test_state_history(self) -> None:
        """Test that state history is tracked."""
        event_bus = MagicMock(spec=EventBus)
        sm = CentralStateMachine(central_name="test-central", event_bus=event_bus)

        sm.transition_to(target=CentralState.INITIALIZING, reason="test")
        sm.transition_to(target=CentralState.RUNNING, reason="test")

        history = sm.state_history
        assert len(history) >= 2

    def test_valid_transitions(self) -> None:
        """Test that valid transitions succeed."""
        event_bus = MagicMock(spec=EventBus)
        sm = CentralStateMachine(central_name="test-central", event_bus=event_bus)

        # STARTING -> INITIALIZING
        sm.transition_to(target=CentralState.INITIALIZING, reason="test")
        assert sm.state == CentralState.INITIALIZING

        # INITIALIZING -> RUNNING
        sm.transition_to(target=CentralState.RUNNING, reason="test")
        assert sm.state == CentralState.RUNNING

    def test_valid_transitions_coverage(self) -> None:
        """Test that all states have defined transitions."""
        for state in CentralState:
            assert state in VALID_CENTRAL_TRANSITIONS


class TestConnectionHealth:
    """Tests for ConnectionHealth."""

    def test_health_score_fully_healthy(self) -> None:
        """Test health score when fully healthy."""
        health = ConnectionHealth(
            interface_id="test-id",
            interface=Interface.HMIP_RF,
            client_state=ClientState.CONNECTED,
            xml_rpc_circuit=CircuitState.CLOSED,
            last_successful_request=datetime.now(),
            last_event_received=datetime.now(),
        )
        assert health.health_score >= 0.9

    def test_health_score_unhealthy(self) -> None:
        """Test health score when unhealthy."""
        health = ConnectionHealth(
            interface_id="test-id",
            interface=Interface.HMIP_RF,
            client_state=ClientState.FAILED,
            xml_rpc_circuit=CircuitState.OPEN,
        )
        assert health.health_score < 0.5

    def test_initial_state(self) -> None:
        """Test initial state of ConnectionHealth."""
        health = ConnectionHealth(
            interface_id="test-id",
            interface=Interface.HMIP_RF,
        )
        assert health.client_state == ClientState.CREATED
        assert health.xml_rpc_circuit == CircuitState.CLOSED
        assert health.is_connected is False

    def test_is_available(self) -> None:
        """Test is_available property."""
        health = ConnectionHealth(
            interface_id="test-id",
            interface=Interface.HMIP_RF,
            client_state=ClientState.CONNECTED,
        )
        assert health.is_available is True

        health.xml_rpc_circuit = CircuitState.OPEN
        assert health.is_available is False

    def test_is_degraded(self) -> None:
        """Test is_degraded property."""
        health = ConnectionHealth(
            interface_id="test-id",
            interface=Interface.HMIP_RF,
            client_state=ClientState.CONNECTED,
            xml_rpc_circuit=CircuitState.OPEN,
        )
        assert health.is_degraded is True

    def test_is_failed(self) -> None:
        """Test is_failed property."""
        health = ConnectionHealth(
            interface_id="test-id",
            interface=Interface.HMIP_RF,
            client_state=ClientState.FAILED,
        )
        assert health.is_failed is True

    def test_record_methods(self) -> None:
        """Test recording methods."""
        health = ConnectionHealth(
            interface_id="test-id",
            interface=Interface.HMIP_RF,
        )

        health.record_successful_request()
        assert health.last_successful_request is not None
        assert health.consecutive_failures == 0

        health.record_failed_request()
        assert health.last_failed_request is not None
        assert health.consecutive_failures == 1

        health.record_reconnect_attempt()
        assert health.reconnect_attempts == 1

        health.reset_reconnect_counter()
        assert health.reconnect_attempts == 0


class TestCentralHealth:
    """Tests for CentralHealth."""

    def test_all_clients_healthy(self) -> None:
        """Test all_clients_healthy property."""
        health = CentralHealth()
        health.register_client(interface_id="test-1", interface=Interface.HMIP_RF)
        health.register_client(interface_id="test-2", interface=Interface.BIDCOS_RF)

        # Update both to connected
        health.client_health["test-1"].client_state = ClientState.CONNECTED
        health.client_health["test-2"].client_state = ClientState.CONNECTED

        assert health.all_clients_healthy is True

    def test_any_client_healthy(self) -> None:
        """Test any_client_healthy property."""
        health = CentralHealth()
        health.register_client(interface_id="test-1", interface=Interface.HMIP_RF)
        health.register_client(interface_id="test-2", interface=Interface.BIDCOS_RF)

        # Only one connected
        health.client_health["test-1"].client_state = ClientState.CONNECTED
        health.client_health["test-2"].client_state = ClientState.FAILED

        assert health.any_client_healthy is True
        assert health.all_clients_healthy is False

    def test_empty_health(self) -> None:
        """Test health with no clients."""
        health = CentralHealth()
        assert health.all_clients_healthy is False
        assert health.any_client_healthy is False
        assert health.overall_health_score == 0.0

    def test_failed_clients(self) -> None:
        """Test failed_clients property."""
        health = CentralHealth()
        health.register_client(interface_id="test-1", interface=Interface.HMIP_RF)
        health.register_client(interface_id="test-2", interface=Interface.BIDCOS_RF)

        health.client_health["test-1"].client_state = ClientState.CONNECTED
        health.client_health["test-2"].client_state = ClientState.FAILED

        assert "test-2" in health.failed_clients
        assert "test-1" not in health.failed_clients

    def test_healthy_clients(self) -> None:
        """Test healthy_clients property."""
        health = CentralHealth()
        health.register_client(interface_id="test-1", interface=Interface.HMIP_RF)
        health.register_client(interface_id="test-2", interface=Interface.BIDCOS_RF)

        health.client_health["test-1"].client_state = ClientState.CONNECTED
        health.client_health["test-2"].client_state = ClientState.FAILED

        assert "test-1" in health.healthy_clients
        assert "test-2" not in health.healthy_clients

    def test_should_be_degraded(self) -> None:
        """Test should_be_degraded property."""
        health = CentralHealth()
        health.register_client(interface_id="test-1", interface=Interface.HMIP_RF)
        health.register_client(interface_id="test-2", interface=Interface.BIDCOS_RF)

        health.client_health["test-1"].client_state = ClientState.CONNECTED
        health.client_health["test-2"].client_state = ClientState.FAILED

        assert health.should_be_degraded() is True


class TestHealthTracker:
    """Tests for HealthTracker."""

    def test_register_client(self) -> None:
        """Test registering a client."""
        tracker = HealthTracker(central_name="test-central")
        health = tracker.register_client(
            interface_id="test-id",
            interface=Interface.HMIP_RF,
        )

        assert health is not None
        assert health.interface_id == "test-id"
        assert tracker.get_client_health(interface_id="test-id") is health

    def test_unregister_client(self) -> None:
        """Test unregistering a client."""
        tracker = HealthTracker(central_name="test-central")
        tracker.register_client(interface_id="test-id", interface=Interface.HMIP_RF)
        tracker.unregister_client(interface_id="test-id")

        assert tracker.get_client_health(interface_id="test-id") is None

    def test_update_client_health(self) -> None:
        """Test updating client health from state change."""
        tracker = HealthTracker(central_name="test-central")
        tracker.register_client(interface_id="test-id", interface=Interface.HMIP_RF)

        tracker.update_client_health(
            interface_id="test-id",
            old_state=ClientState.CREATED,
            new_state=ClientState.CONNECTED,
        )

        health = tracker.get_client_health(interface_id="test-id")
        assert health is not None
        assert health.client_state == ClientState.CONNECTED

    def test_update_client_health_reconnect_tracking(self) -> None:
        """Test that reconnection attempts are tracked."""
        tracker = HealthTracker(central_name="test-central")
        tracker.register_client(interface_id="test-id", interface=Interface.HMIP_RF)

        tracker.update_client_health(
            interface_id="test-id",
            old_state=ClientState.DISCONNECTED,
            new_state=ClientState.RECONNECTING,
        )

        health = tracker.get_client_health(interface_id="test-id")
        assert health is not None
        assert health.reconnect_attempts == 1


class TestRecoveryCoordinator:
    """Tests for RecoveryCoordinator."""

    def test_get_recovery_state(self) -> None:
        """Test getting recovery state for an interface."""
        event_bus = MagicMock(spec=EventBus)
        state_machine = CentralStateMachine(central_name="test", event_bus=event_bus)
        health_tracker = HealthTracker(central_name="test")

        coordinator = RecoveryCoordinator(
            central_name="test",
            state_machine=state_machine,
            health_tracker=health_tracker,
        )

        # Should return None for unregistered interface
        assert coordinator.get_recovery_state(interface_id="test-id") is None

        # Register and retrieve
        coordinator.register_interface(interface_id="test-id")
        state = coordinator.get_recovery_state(interface_id="test-id")
        assert state is not None
        assert state.interface_id == "test-id"

    def test_initial_state(self) -> None:
        """Test initial state of RecoveryCoordinator."""
        event_bus = MagicMock(spec=EventBus)
        state_machine = CentralStateMachine(central_name="test", event_bus=event_bus)
        health_tracker = HealthTracker(central_name="test")

        coordinator = RecoveryCoordinator(
            central_name="test",
            state_machine=state_machine,
            health_tracker=health_tracker,
        )

        assert coordinator.recovery_states == {}
        assert coordinator.in_recovery is False

    def test_register_interface(self) -> None:
        """Test registering an interface for recovery tracking."""
        event_bus = MagicMock(spec=EventBus)
        state_machine = CentralStateMachine(central_name="test", event_bus=event_bus)
        health_tracker = HealthTracker(central_name="test")

        coordinator = RecoveryCoordinator(
            central_name="test",
            state_machine=state_machine,
            health_tracker=health_tracker,
        )

        state = coordinator.register_interface(interface_id="test-id")
        assert state is not None
        assert state.interface_id == "test-id"
        assert state.attempt_count == 0

    def test_reset_interface(self) -> None:
        """Test reset_interface clears attempt tracking."""
        event_bus = MagicMock(spec=EventBus)
        state_machine = CentralStateMachine(central_name="test", event_bus=event_bus)
        health_tracker = HealthTracker(central_name="test")

        coordinator = RecoveryCoordinator(
            central_name="test",
            state_machine=state_machine,
            health_tracker=health_tracker,
        )

        # Register and simulate attempts
        state = coordinator.register_interface(interface_id="test-id")
        state.record_attempt(result=RecoveryResult.FAILED, stage=DataLoadStage.BASIC)
        state.record_attempt(result=RecoveryResult.FAILED, stage=DataLoadStage.BASIC)

        assert state.attempt_count == 2
        assert state.consecutive_failures == 2

        # Reset
        coordinator.reset_interface(interface_id="test-id")

        state = coordinator.get_recovery_state(interface_id="test-id")
        assert state is not None
        assert state.attempt_count == 0
        assert state.consecutive_failures == 0


class TestSystemStatusEvent:
    """Tests for SystemStatusEvent."""

    def test_event_with_central_state(self) -> None:
        """Test event with central state."""
        event = SystemStatusEvent(
            timestamp=datetime.now(),
            central_state=CentralState.RUNNING,
        )

        assert event.central_state == CentralState.RUNNING
        assert event.client_state is None
        assert event.key is None  # Global event

    def test_event_with_client_state(self) -> None:
        """Test event with client state."""
        event = SystemStatusEvent(
            timestamp=datetime.now(),
            client_state=("test-id", ClientState.CONNECTING, ClientState.CONNECTED),
        )

        assert event.client_state is not None
        assert event.client_state[0] == "test-id"
        assert event.client_state[1] == ClientState.CONNECTING
        assert event.client_state[2] == ClientState.CONNECTED
        assert event.key is None  # Global event

    def test_event_with_connection_state(self) -> None:
        """Test event with connection state."""
        event = SystemStatusEvent(
            timestamp=datetime.now(),
            connection_state=("test-id", True),
        )

        assert event.connection_state is not None
        assert event.connection_state[0] == "test-id"
        assert event.connection_state[1] is True
        assert event.key is None  # Global event


class TestHealthTrackerIntegration:
    """Tests for HealthTracker integration with CentralUnit."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (None, True, None, None),
        ],
    )
    async def test_clients_registered_with_health_tracker_on_start(
        self, central_client_factory_with_homegear_client: Any
    ) -> None:
        """Test that clients are registered with health tracker when central starts."""
        central, _, _ = central_client_factory_with_homegear_client

        # Verify clients exist
        clients = central.client_coordinator.clients
        assert len(clients) > 0

        # Verify each client is registered with health tracker
        for client in clients:
            health = central.health_tracker.get_client_health(interface_id=client.interface_id)
            assert health is not None, f"Client {client.interface_id} not registered with health tracker"
            assert health.interface == client.interface
            assert health.interface_id == client.interface_id

        # Verify primary interface is set if we have a primary client
        if primary_client := central.client_coordinator.primary_client:
            assert central.health.primary_interface == primary_client.interface

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (None, True, None, None),
        ],
    )
    async def test_health_tracker_update_client_health_works_after_registration(
        self, central_client_factory_with_homegear_client: Any
    ) -> None:
        """Test that update_client_health properly updates registered clients."""
        central, _, _ = central_client_factory_with_homegear_client

        # Get first client
        client = central.client_coordinator.clients[0]

        # Get current health
        health = central.health_tracker.get_client_health(interface_id=client.interface_id)
        assert health is not None

        # Simulate a state change update
        central.health_tracker.update_client_health(
            interface_id=client.interface_id,
            old_state=ClientState.CONNECTED,
            new_state=ClientState.DISCONNECTED,
        )

        # Verify health was updated
        health = central.health_tracker.get_client_health(interface_id=client.interface_id)
        assert health is not None
        assert health.client_state == ClientState.DISCONNECTED
