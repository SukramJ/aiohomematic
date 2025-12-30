# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Tests for Health Tracking System."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from aiohomematic.central import CentralHealth, ConnectionHealth, HealthTracker
from aiohomematic.client import CircuitState
from aiohomematic.const import CentralState, ClientState, Interface

if TYPE_CHECKING:
    pass


class TestConnectionHealth:
    """Tests for ConnectionHealth dataclass."""

    def test_can_receive_events_no_events(self) -> None:
        """Test can_receive_events with no events received."""
        health = ConnectionHealth(
            interface_id="test",
            interface=Interface.HMIP_RF,
            client_state=ClientState.CONNECTED,
            last_event_received=None,
        )
        assert health.can_receive_events is False

    def test_can_receive_events_not_connected(self) -> None:
        """Test can_receive_events when not connected."""
        health = ConnectionHealth(
            interface_id="test",
            interface=Interface.HMIP_RF,
            client_state=ClientState.DISCONNECTED,
            last_event_received=datetime.now(),
        )
        assert health.can_receive_events is False

    def test_can_receive_events_recent(self) -> None:
        """Test can_receive_events with recent event."""
        health = ConnectionHealth(
            interface_id="test",
            interface=Interface.HMIP_RF,
            client_state=ClientState.CONNECTED,
            last_event_received=datetime.now(),
        )
        assert health.can_receive_events is True

    def test_can_receive_events_stale(self) -> None:
        """Test can_receive_events with stale event."""
        health = ConnectionHealth(
            interface_id="test",
            interface=Interface.HMIP_RF,
            client_state=ClientState.CONNECTED,
            last_event_received=datetime.now() - timedelta(minutes=10),
        )
        assert health.can_receive_events is False

    def test_health_score_circuit_half_open(self) -> None:
        """Test health score with half-open circuit."""
        health = ConnectionHealth(
            interface_id="test",
            interface=Interface.HMIP_RF,
            client_state=ClientState.CONNECTED,
            xml_rpc_circuit=CircuitState.HALF_OPEN,
        )
        # Should be reduced
        score = health.health_score
        assert score < 1.0

    def test_health_score_disconnected(self) -> None:
        """Test health score when disconnected."""
        health = ConnectionHealth(
            interface_id="test",
            interface=Interface.HMIP_RF,
            client_state=ClientState.DISCONNECTED,
        )
        # Should be low
        assert health.health_score < 0.5

    def test_health_score_fully_healthy(self) -> None:
        """Test health score for fully healthy client."""
        health = ConnectionHealth(
            interface_id="test",
            interface=Interface.HMIP_RF,
            client_state=ClientState.CONNECTED,
            xml_rpc_circuit=CircuitState.CLOSED,
            json_rpc_circuit=None,  # No JSON-RPC
            last_successful_request=datetime.now(),
            last_event_received=datetime.now(),
        )
        # Should be close to 1.0
        assert health.health_score >= 0.9

    def test_health_score_json_rpc_closed(self) -> None:
        """Test health score with JSON-RPC circuit closed."""
        health = ConnectionHealth(
            interface_id="test",
            interface=Interface.HMIP_RF,
            client_state=ClientState.CONNECTED,
            xml_rpc_circuit=CircuitState.CLOSED,
            json_rpc_circuit=CircuitState.CLOSED,
        )
        score = health.health_score
        assert score >= 0.7

    def test_health_score_json_rpc_half_open(self) -> None:
        """Test health score with JSON-RPC circuit half-open."""
        health = ConnectionHealth(
            interface_id="test",
            interface=Interface.HMIP_RF,
            client_state=ClientState.CONNECTED,
            xml_rpc_circuit=CircuitState.CLOSED,
            json_rpc_circuit=CircuitState.HALF_OPEN,
        )
        score = health.health_score
        assert 0.5 <= score <= 0.9

    def test_health_score_old_activity(self) -> None:
        """Test health score with old activity timestamps."""
        health = ConnectionHealth(
            interface_id="test",
            interface=Interface.HMIP_RF,
            client_state=ClientState.CONNECTED,
            xml_rpc_circuit=CircuitState.CLOSED,
            last_successful_request=datetime.now() - timedelta(minutes=8),
            last_event_received=datetime.now() - timedelta(minutes=8),
        )
        # Should still have some score but reduced
        score = health.health_score
        assert 0.5 <= score <= 0.9

    def test_health_score_reconnecting(self) -> None:
        """Test health score when reconnecting."""
        health = ConnectionHealth(
            interface_id="test",
            interface=Interface.HMIP_RF,
            client_state=ClientState.RECONNECTING,
            xml_rpc_circuit=CircuitState.CLOSED,
        )
        # Should be medium (state machine contributes half)
        score = health.health_score
        assert 0.2 <= score <= 0.7

    def test_initial_state(self) -> None:
        """Test initial connection health state."""
        health = ConnectionHealth(interface_id="test", interface=Interface.HMIP_RF)
        assert health.interface_id == "test"
        assert health.interface == Interface.HMIP_RF
        assert health.client_state == ClientState.CREATED
        assert health.xml_rpc_circuit == CircuitState.CLOSED
        assert health.json_rpc_circuit is None
        assert health.consecutive_failures == 0
        assert health.reconnect_attempts == 0

    def test_is_available_all_good(self) -> None:
        """Test is_available when all systems are healthy."""
        health = ConnectionHealth(
            interface_id="test",
            interface=Interface.HMIP_RF,
            client_state=ClientState.CONNECTED,
            xml_rpc_circuit=CircuitState.CLOSED,
            json_rpc_circuit=CircuitState.CLOSED,
        )
        assert health.is_available is True

    def test_is_available_disconnected(self) -> None:
        """Test is_available when disconnected."""
        health = ConnectionHealth(
            interface_id="test",
            interface=Interface.HMIP_RF,
            client_state=ClientState.DISCONNECTED,
            xml_rpc_circuit=CircuitState.CLOSED,
        )
        assert health.is_available is False

    def test_is_available_json_circuit_open(self) -> None:
        """Test is_available when JSON-RPC circuit is open."""
        health = ConnectionHealth(
            interface_id="test",
            interface=Interface.HMIP_RF,
            client_state=ClientState.CONNECTED,
            xml_rpc_circuit=CircuitState.CLOSED,
            json_rpc_circuit=CircuitState.OPEN,
        )
        assert health.is_available is False

    def test_is_available_no_json_circuit(self) -> None:
        """Test is_available when no JSON-RPC circuit (Homegear)."""
        health = ConnectionHealth(
            interface_id="test",
            interface=Interface.BIDCOS_RF,
            client_state=ClientState.CONNECTED,
            xml_rpc_circuit=CircuitState.CLOSED,
            json_rpc_circuit=None,
        )
        assert health.is_available is True

    def test_is_available_xml_circuit_open(self) -> None:
        """Test is_available when XML-RPC circuit is open."""
        health = ConnectionHealth(
            interface_id="test",
            interface=Interface.HMIP_RF,
            client_state=ClientState.CONNECTED,
            xml_rpc_circuit=CircuitState.OPEN,
        )
        assert health.is_available is False

    def test_is_connected(self) -> None:
        """Test is_connected property."""
        health = ConnectionHealth(interface_id="test", interface=Interface.HMIP_RF)
        assert health.is_connected is False

        health.client_state = ClientState.CONNECTED
        assert health.is_connected is True

    def test_is_degraded_circuit_open(self) -> None:
        """Test is_degraded when circuit is open but connected."""
        health = ConnectionHealth(
            interface_id="test",
            interface=Interface.HMIP_RF,
            client_state=ClientState.CONNECTED,
            xml_rpc_circuit=CircuitState.OPEN,
        )
        assert health.is_degraded is True

    def test_is_degraded_disconnected(self) -> None:
        """Test is_degraded when disconnected."""
        health = ConnectionHealth(
            interface_id="test",
            interface=Interface.HMIP_RF,
            client_state=ClientState.DISCONNECTED,
            xml_rpc_circuit=CircuitState.OPEN,
        )
        assert health.is_degraded is False

    def test_is_degraded_reconnecting(self) -> None:
        """Test is_degraded when reconnecting with circuit issue."""
        health = ConnectionHealth(
            interface_id="test",
            interface=Interface.HMIP_RF,
            client_state=ClientState.RECONNECTING,
            xml_rpc_circuit=CircuitState.HALF_OPEN,
        )
        assert health.is_degraded is True

    def test_is_failed(self) -> None:
        """Test is_failed property."""
        health = ConnectionHealth(interface_id="test", interface=Interface.HMIP_RF)
        assert health.is_failed is False

        health.client_state = ClientState.FAILED
        assert health.is_failed is True

        health.client_state = ClientState.DISCONNECTED
        assert health.is_failed is True

    def test_record_event_received(self) -> None:
        """Test recording event received."""
        health = ConnectionHealth(interface_id="test", interface=Interface.HMIP_RF)
        assert health.last_event_received is None

        health.record_event_received()
        assert health.last_event_received is not None

    def test_record_failed_request(self) -> None:
        """Test recording failed request."""
        health = ConnectionHealth(interface_id="test", interface=Interface.HMIP_RF)

        health.record_failed_request()
        assert health.last_failed_request is not None
        assert health.consecutive_failures == 1

        health.record_failed_request()
        assert health.consecutive_failures == 2

    def test_record_reconnect_attempt(self) -> None:
        """Test recording reconnect attempt."""
        health = ConnectionHealth(interface_id="test", interface=Interface.HMIP_RF)

        health.record_reconnect_attempt()
        assert health.reconnect_attempts == 1
        assert health.last_reconnect_attempt is not None

    def test_record_successful_request(self) -> None:
        """Test recording successful request."""
        health = ConnectionHealth(interface_id="test", interface=Interface.HMIP_RF)
        health.consecutive_failures = 5

        health.record_successful_request()
        assert health.last_successful_request is not None
        assert health.consecutive_failures == 0

    def test_reset_reconnect_counter(self) -> None:
        """Test resetting reconnect counter."""
        health = ConnectionHealth(interface_id="test", interface=Interface.HMIP_RF)
        health.reconnect_attempts = 5

        health.reset_reconnect_counter()
        assert health.reconnect_attempts == 0

    def test_update_from_client(self) -> None:
        """Test updating health from client."""
        health = ConnectionHealth(interface_id="test", interface=Interface.HMIP_RF)

        # Mock client with state machine
        client = MagicMock()
        client._state_machine.state = ClientState.CONNECTED

        health.update_from_client(client=client)
        assert health.client_state == ClientState.CONNECTED


class TestCentralHealth:
    """Tests for CentralHealth dataclass."""

    def test_all_clients_healthy_all_good(self) -> None:
        """Test all_clients_healthy when all healthy."""
        health = CentralHealth()
        client1 = health.register_client(interface_id="c1", interface=Interface.HMIP_RF)
        client2 = health.register_client(interface_id="c2", interface=Interface.BIDCOS_RF)

        client1.client_state = ClientState.CONNECTED
        client2.client_state = ClientState.CONNECTED

        assert health.all_clients_healthy is True

    def test_all_clients_healthy_empty(self) -> None:
        """Test all_clients_healthy with no clients."""
        health = CentralHealth()
        assert health.all_clients_healthy is False

    def test_all_clients_healthy_one_failed(self) -> None:
        """Test all_clients_healthy with one failed client."""
        health = CentralHealth()
        client1 = health.register_client(interface_id="c1", interface=Interface.HMIP_RF)
        client2 = health.register_client(interface_id="c2", interface=Interface.BIDCOS_RF)

        client1.client_state = ClientState.CONNECTED
        client2.client_state = ClientState.FAILED

        assert health.all_clients_healthy is False

    def test_any_client_healthy(self) -> None:
        """Test any_client_healthy property."""
        health = CentralHealth()
        client1 = health.register_client(interface_id="c1", interface=Interface.HMIP_RF)
        client2 = health.register_client(interface_id="c2", interface=Interface.BIDCOS_RF)

        client1.client_state = ClientState.CONNECTED
        client2.client_state = ClientState.FAILED

        assert health.any_client_healthy is True

    def test_degraded_clients(self) -> None:
        """Test degraded_clients property."""
        health = CentralHealth()
        client1 = health.register_client(interface_id="c1", interface=Interface.HMIP_RF)
        client2 = health.register_client(interface_id="c2", interface=Interface.BIDCOS_RF)

        client1.client_state = ClientState.CONNECTED
        client2.client_state = ClientState.CONNECTED
        client2.xml_rpc_circuit = CircuitState.OPEN

        assert health.degraded_clients == ["c2"]

    def test_failed_clients(self) -> None:
        """Test failed_clients property."""
        health = CentralHealth()
        client1 = health.register_client(interface_id="c1", interface=Interface.HMIP_RF)
        client2 = health.register_client(interface_id="c2", interface=Interface.BIDCOS_RF)

        client1.client_state = ClientState.CONNECTED
        client2.client_state = ClientState.FAILED

        assert health.failed_clients == ["c2"]

    def test_get_client_health(self) -> None:
        """Test getting client health."""
        health = CentralHealth()
        health.register_client(interface_id="test", interface=Interface.HMIP_RF)

        client_health = health.get_client_health(interface_id="test")
        assert client_health is not None
        assert client_health.interface_id == "test"

    def test_get_client_health_not_found(self) -> None:
        """Test getting non-existent client health."""
        health = CentralHealth()
        assert health.get_client_health(interface_id="unknown") is None

    def test_healthy_clients(self) -> None:
        """Test healthy_clients property."""
        health = CentralHealth()
        client1 = health.register_client(interface_id="c1", interface=Interface.HMIP_RF)
        client2 = health.register_client(interface_id="c2", interface=Interface.BIDCOS_RF)

        client1.client_state = ClientState.CONNECTED
        client2.client_state = ClientState.FAILED

        assert health.healthy_clients == ["c1"]

    def test_initial_state(self) -> None:
        """Test initial central health state."""
        health = CentralHealth()
        assert health.central_state == CentralState.STARTING
        assert health.client_health == {}
        assert health.primary_interface is None

    def test_overall_health_score_average(self) -> None:
        """Test overall_health_score is average of clients."""
        health = CentralHealth()
        client1 = health.register_client(interface_id="c1", interface=Interface.HMIP_RF)
        client2 = health.register_client(interface_id="c2", interface=Interface.BIDCOS_RF)

        client1.client_state = ClientState.CONNECTED
        client2.client_state = ClientState.CONNECTED

        score = health.overall_health_score
        assert score > 0.0

    def test_overall_health_score_empty(self) -> None:
        """Test overall_health_score with no clients."""
        health = CentralHealth()
        assert health.overall_health_score == 0.0

    def test_primary_client_healthy_empty(self) -> None:
        """Test primary_client_healthy with no clients."""
        health = CentralHealth()
        assert health.primary_client_healthy is False

    def test_primary_client_healthy_fallback_to_hmip(self) -> None:
        """Test primary_client_healthy falls back to HmIP-RF."""
        health = CentralHealth()

        client1 = health.register_client(interface_id="c1", interface=Interface.HMIP_RF)
        client2 = health.register_client(interface_id="c2", interface=Interface.BIDCOS_RF)

        client1.client_state = ClientState.CONNECTED
        client2.client_state = ClientState.CONNECTED

        assert health.primary_client_healthy is True

    def test_primary_client_healthy_last_resort(self) -> None:
        """Test primary_client_healthy uses first client as last resort."""
        health = CentralHealth()

        # Only BIDCOS_RF, no HmIP-RF
        client1 = health.register_client(interface_id="c1", interface=Interface.BIDCOS_RF)
        client1.client_state = ClientState.CONNECTED

        # Should use first (and only) client as last resort
        assert health.primary_client_healthy is True

    def test_primary_client_healthy_with_primary_interface(self) -> None:
        """Test primary_client_healthy with specified primary interface."""
        health = CentralHealth()
        health.primary_interface = Interface.HMIP_RF

        client1 = health.register_client(interface_id="c1", interface=Interface.HMIP_RF)
        client2 = health.register_client(interface_id="c2", interface=Interface.BIDCOS_RF)

        client1.client_state = ClientState.CONNECTED
        client2.client_state = ClientState.FAILED

        assert health.primary_client_healthy is True

    def test_register_client(self) -> None:
        """Test registering a client."""
        health = CentralHealth()
        client_health = health.register_client(
            interface_id="test",
            interface=Interface.HMIP_RF,
        )
        assert client_health.interface_id == "test"
        assert "test" in health.client_health

    def test_should_be_degraded(self) -> None:
        """Test should_be_degraded property."""
        health = CentralHealth()
        client1 = health.register_client(interface_id="c1", interface=Interface.HMIP_RF)
        client2 = health.register_client(interface_id="c2", interface=Interface.BIDCOS_RF)

        client1.client_state = ClientState.CONNECTED
        client2.client_state = ClientState.FAILED

        assert health.should_be_degraded() is True

    def test_should_be_running(self) -> None:
        """Test should_be_running property."""
        health = CentralHealth()
        client1 = health.register_client(interface_id="c1", interface=Interface.HMIP_RF)

        client1.client_state = ClientState.CONNECTED
        assert health.should_be_running() is True

        client1.client_state = ClientState.FAILED
        assert health.should_be_running() is False

    def test_unregister_client(self) -> None:
        """Test unregistering a client."""
        health = CentralHealth()
        health.register_client(interface_id="test", interface=Interface.HMIP_RF)
        assert "test" in health.client_health

        health.unregister_client(interface_id="test")
        assert "test" not in health.client_health

    def test_update_central_state(self) -> None:
        """Test updating central state."""
        health = CentralHealth()
        health.update_central_state(state=CentralState.RUNNING)
        assert health.central_state == CentralState.RUNNING
        assert health.state == CentralState.RUNNING


class TestHealthTracker:
    """Tests for HealthTracker class."""

    def test_get_client_health(self) -> None:
        """Test getting client health."""
        tracker = HealthTracker(central_name="test")
        tracker.register_client(interface_id="c1", interface=Interface.HMIP_RF)
        health = tracker.get_client_health(interface_id="c1")
        assert health is not None

    def test_init(self) -> None:
        """Test initialization."""
        tracker = HealthTracker(central_name="test")
        assert tracker.health is not None

    def test_record_event_received(self) -> None:
        """Test recording event received."""
        tracker = HealthTracker(central_name="test")
        tracker.register_client(interface_id="c1", interface=Interface.HMIP_RF)

        tracker.record_event_received(interface_id="c1")
        health = tracker.get_client_health(interface_id="c1")
        assert health is not None
        assert health.last_event_received is not None

    def test_record_event_received_unknown_client(self) -> None:
        """Test recording event for unknown client."""
        tracker = HealthTracker(central_name="test")
        # Should not raise
        tracker.record_event_received(interface_id="unknown")

    def test_record_failed_request(self) -> None:
        """Test recording failed request."""
        tracker = HealthTracker(central_name="test")
        tracker.register_client(interface_id="c1", interface=Interface.HMIP_RF)

        tracker.record_failed_request(interface_id="c1")
        health = tracker.get_client_health(interface_id="c1")
        assert health is not None
        assert health.consecutive_failures == 1

    def test_record_successful_request(self) -> None:
        """Test recording successful request."""
        tracker = HealthTracker(central_name="test")
        tracker.register_client(interface_id="c1", interface=Interface.HMIP_RF)

        tracker.record_successful_request(interface_id="c1")
        health = tracker.get_client_health(interface_id="c1")
        assert health is not None
        assert health.last_successful_request is not None

    def test_register_client(self) -> None:
        """Test registering a client."""
        tracker = HealthTracker(central_name="test")
        health = tracker.register_client(
            interface_id="c1",
            interface=Interface.HMIP_RF,
        )
        assert health.interface_id == "c1"

    def test_set_primary_interface(self) -> None:
        """Test setting primary interface."""
        tracker = HealthTracker(central_name="test")
        tracker.set_primary_interface(interface=Interface.HMIP_RF)
        assert tracker.health.primary_interface == Interface.HMIP_RF

    def test_set_state_machine(self) -> None:
        """Test setting state machine."""
        tracker = HealthTracker(central_name="test")
        state_machine = MagicMock()
        tracker.set_state_machine(state_machine=state_machine)
        assert tracker._state_machine == state_machine

    def test_unregister_client(self) -> None:
        """Test unregistering a client."""
        tracker = HealthTracker(central_name="test")
        tracker.register_client(interface_id="c1", interface=Interface.HMIP_RF)
        tracker.unregister_client(interface_id="c1")
        assert tracker.get_client_health(interface_id="c1") is None

    def test_update_all_from_clients(self) -> None:
        """Test updating all client health from clients."""
        tracker = HealthTracker(central_name="test")
        tracker.register_client(interface_id="c1", interface=Interface.HMIP_RF)

        client = MagicMock()
        client._state_machine.state = ClientState.CONNECTED

        tracker.update_all_from_clients(clients={"c1": client})

        health = tracker.get_client_health(interface_id="c1")
        assert health is not None
        assert health.client_state == ClientState.CONNECTED

    def test_update_client_health_connected_resets_counter(self) -> None:
        """Test updating client health resets reconnect counter on connect."""
        tracker = HealthTracker(central_name="test")
        health = tracker.register_client(interface_id="c1", interface=Interface.HMIP_RF)
        health.reconnect_attempts = 5

        tracker.update_client_health(
            interface_id="c1",
            old_state=ClientState.RECONNECTING,
            new_state=ClientState.CONNECTED,
        )

        assert health.reconnect_attempts == 0

    def test_update_client_health_reconnecting(self) -> None:
        """Test updating client health records reconnect attempt."""
        tracker = HealthTracker(central_name="test")
        tracker.register_client(interface_id="c1", interface=Interface.HMIP_RF)

        tracker.update_client_health(
            interface_id="c1",
            old_state=ClientState.CONNECTED,
            new_state=ClientState.RECONNECTING,
        )

        health = tracker.get_client_health(interface_id="c1")
        assert health is not None
        assert health.reconnect_attempts == 1

    def test_update_client_health_state_change(self) -> None:
        """Test updating client health on state change."""
        tracker = HealthTracker(central_name="test")
        tracker.register_client(interface_id="c1", interface=Interface.HMIP_RF)

        tracker.update_client_health(
            interface_id="c1",
            old_state=ClientState.CONNECTING,
            new_state=ClientState.CONNECTED,
        )

        health = tracker.get_client_health(interface_id="c1")
        assert health is not None
        assert health.client_state == ClientState.CONNECTED
