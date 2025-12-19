# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Tests for FailureReason propagation through state machines."""

from __future__ import annotations

from unittest.mock import MagicMock

from aiohomematic.central.integration_events import SystemStatusEvent
from aiohomematic.central.state_machine import CentralStateMachine
from aiohomematic.client._rpc_errors import exception_to_failure_reason
from aiohomematic.client.state_machine import ClientStateMachine
from aiohomematic.const import CentralState, ClientState, FailureReason
from aiohomematic.exceptions import (
    AuthFailure,
    CircuitBreakerOpenException,
    ClientException,
    InternalBackendException,
    NoConnectionException,
)


class TestFailureReasonEnum:
    """Tests for FailureReason enum."""

    def test_failure_reason_values(self) -> None:
        """Test that all failure reason values are correct."""
        assert FailureReason.NONE == "none"
        assert FailureReason.AUTH == "auth"
        assert FailureReason.NETWORK == "network"
        assert FailureReason.INTERNAL == "internal"
        assert FailureReason.TIMEOUT == "timeout"
        assert FailureReason.CIRCUIT_BREAKER == "circuit_breaker"
        assert FailureReason.UNKNOWN == "unknown"


class TestExceptionToFailureReason:
    """Tests for exception_to_failure_reason helper function."""

    def test_asyncio_timeout_maps_to_timeout(self) -> None:
        """Test that asyncio.TimeoutError maps to FailureReason.TIMEOUT."""
        exc = TimeoutError("Async operation timed out")
        assert exception_to_failure_reason(exc) == FailureReason.TIMEOUT

    def test_auth_failure_maps_to_auth(self) -> None:
        """Test that AuthFailure maps to FailureReason.AUTH."""
        exc = AuthFailure("Invalid credentials")
        assert exception_to_failure_reason(exc) == FailureReason.AUTH

    def test_circuit_breaker_maps_to_circuit_breaker(self) -> None:
        """Test that CircuitBreakerOpenException maps to FailureReason.CIRCUIT_BREAKER."""
        exc = CircuitBreakerOpenException("Circuit is open")
        assert exception_to_failure_reason(exc) == FailureReason.CIRCUIT_BREAKER

    def test_client_exception_maps_to_unknown(self) -> None:
        """Test that ClientException maps to FailureReason.UNKNOWN."""
        exc = ClientException("Client error")
        assert exception_to_failure_reason(exc) == FailureReason.UNKNOWN

    def test_generic_exception_maps_to_unknown(self) -> None:
        """Test that generic exceptions map to FailureReason.UNKNOWN."""
        exc = ValueError("Some error")
        assert exception_to_failure_reason(exc) == FailureReason.UNKNOWN

    def test_internal_backend_maps_to_internal(self) -> None:
        """Test that InternalBackendException maps to FailureReason.INTERNAL."""
        exc = InternalBackendException("Server error")
        assert exception_to_failure_reason(exc) == FailureReason.INTERNAL

    def test_no_connection_maps_to_network(self) -> None:
        """Test that NoConnectionException maps to FailureReason.NETWORK."""
        exc = NoConnectionException("Host unreachable")
        assert exception_to_failure_reason(exc) == FailureReason.NETWORK

    def test_timeout_error_maps_to_timeout(self) -> None:
        """Test that TimeoutError maps to FailureReason.TIMEOUT."""
        exc = TimeoutError("Operation timed out")
        assert exception_to_failure_reason(exc) == FailureReason.TIMEOUT


class TestClientStateMachineFailureReason:
    """Tests for ClientStateMachine failure reason tracking."""

    def test_initial_failure_reason_is_none(self) -> None:
        """Test that initial failure_reason is NONE."""
        sm = ClientStateMachine(interface_id="test-interface")
        assert sm.failure_reason == FailureReason.NONE
        assert sm.failure_message == ""

    def test_reset_clears_failure_reason(self) -> None:
        """Test that reset() clears failure info."""
        sm = ClientStateMachine(interface_id="test-interface")
        sm.transition_to(target=ClientState.INITIALIZING)
        sm.transition_to(
            target=ClientState.FAILED,
            reason="Test failure",
            failure_reason=FailureReason.INTERNAL,
        )
        assert sm.failure_reason == FailureReason.INTERNAL

        sm.reset()
        assert sm.failure_reason == FailureReason.NONE
        assert sm.failure_message == ""
        assert sm.state == ClientState.CREATED

    def test_transition_to_connected_clears_failure_reason(self) -> None:
        """Test that transitioning to CONNECTED clears failure info."""
        sm = ClientStateMachine(interface_id="test-interface")
        sm.transition_to(target=ClientState.INITIALIZING)
        sm.transition_to(
            target=ClientState.FAILED,
            reason="Auth failed",
            failure_reason=FailureReason.AUTH,
        )
        assert sm.failure_reason == FailureReason.AUTH

        # Recover by going to CONNECTING then CONNECTED
        sm.transition_to(target=ClientState.CONNECTING)
        sm.transition_to(target=ClientState.CONNECTED)
        assert sm.failure_reason == FailureReason.NONE
        assert sm.failure_message == ""

    def test_transition_to_failed_sets_failure_reason(self) -> None:
        """Test that transitioning to FAILED sets the failure reason."""
        sm = ClientStateMachine(interface_id="test-interface")
        sm.transition_to(target=ClientState.INITIALIZING)
        sm.transition_to(
            target=ClientState.FAILED,
            reason="Authentication failed",
            failure_reason=FailureReason.AUTH,
        )
        assert sm.failure_reason == FailureReason.AUTH
        assert sm.failure_message == "Authentication failed"
        assert sm.is_failed is True

    def test_transition_to_failed_with_network_reason(self) -> None:
        """Test FAILED transition with NETWORK failure reason."""
        sm = ClientStateMachine(interface_id="test-interface")
        sm.transition_to(target=ClientState.INITIALIZING)
        sm.transition_to(
            target=ClientState.FAILED,
            reason="Connection refused",
            failure_reason=FailureReason.NETWORK,
        )
        assert sm.failure_reason == FailureReason.NETWORK
        assert sm.failure_message == "Connection refused"

    def test_transition_to_initialized_clears_failure_reason(self) -> None:
        """Test that transitioning to INITIALIZED clears failure info."""
        sm = ClientStateMachine(interface_id="test-interface")
        sm.transition_to(target=ClientState.INITIALIZING)
        sm.transition_to(
            target=ClientState.FAILED,
            reason="Init failed",
            failure_reason=FailureReason.NETWORK,
        )
        assert sm.failure_reason == FailureReason.NETWORK

        # Retry initialization
        sm.transition_to(target=ClientState.INITIALIZING)
        sm.transition_to(target=ClientState.INITIALIZED)
        assert sm.failure_reason == FailureReason.NONE
        assert sm.failure_message == ""


class TestCentralStateMachineFailureReason:
    """Tests for CentralStateMachine failure reason tracking."""

    def test_initial_failure_reason_is_none(self) -> None:
        """Test that initial failure_reason is NONE."""
        sm = CentralStateMachine(central_name="test-central")
        assert sm.failure_reason == FailureReason.NONE
        assert sm.failure_message == ""
        assert sm.failure_interface_id is None

    def test_transition_to_failed_sets_failure_reason(self) -> None:
        """Test that transitioning to FAILED sets the failure reason."""
        sm = CentralStateMachine(central_name="test-central")
        sm.transition_to(target=CentralState.INITIALIZING)
        sm.transition_to(
            target=CentralState.FAILED,
            reason="Authentication failed on HmIP-RF",
            failure_reason=FailureReason.AUTH,
            failure_interface_id="HmIP-RF",
        )
        assert sm.failure_reason == FailureReason.AUTH
        assert sm.failure_message == "Authentication failed on HmIP-RF"
        assert sm.failure_interface_id == "HmIP-RF"
        assert sm.is_failed is True

    def test_transition_to_running_clears_failure_reason(self) -> None:
        """Test that transitioning to RUNNING clears failure info."""
        sm = CentralStateMachine(central_name="test-central")
        sm.transition_to(target=CentralState.INITIALIZING)
        sm.transition_to(
            target=CentralState.FAILED,
            reason="Network failure",
            failure_reason=FailureReason.NETWORK,
            failure_interface_id="BidCos-RF",
        )
        assert sm.failure_reason == FailureReason.NETWORK

        # Recover
        sm.transition_to(target=CentralState.RECOVERING)
        sm.transition_to(target=CentralState.RUNNING)
        assert sm.failure_reason == FailureReason.NONE
        assert sm.failure_message == ""
        assert sm.failure_interface_id is None


class TestSystemStatusEventFailureReason:
    """Tests for SystemStatusEvent failure reason fields."""

    def test_event_with_failure_reason(self) -> None:
        """Test creating SystemStatusEvent with failure reason."""
        from datetime import datetime

        event = SystemStatusEvent(
            timestamp=datetime.now(),
            central_state=CentralState.FAILED,
            failure_reason=FailureReason.AUTH,
            failure_interface_id="HmIP-RF",
        )
        assert event.central_state == CentralState.FAILED
        assert event.failure_reason == FailureReason.AUTH
        assert event.failure_interface_id == "HmIP-RF"

    def test_event_without_failure_reason(self) -> None:
        """Test creating SystemStatusEvent without failure reason."""
        from datetime import datetime

        event = SystemStatusEvent(
            timestamp=datetime.now(),
            central_state=CentralState.RUNNING,
        )
        assert event.central_state == CentralState.RUNNING
        assert event.failure_reason is None
        assert event.failure_interface_id is None


class TestCentralStateMachineEventPublishing:
    """Tests for CentralStateMachine event publishing with failure reason."""

    def test_publish_failure_event_includes_failure_reason(self) -> None:
        """Test that state change event includes failure reason."""
        mock_event_bus = MagicMock()
        sm = CentralStateMachine(central_name="test-central", event_bus=mock_event_bus)

        sm.transition_to(target=CentralState.INITIALIZING)
        sm.transition_to(
            target=CentralState.FAILED,
            reason="Auth failed",
            failure_reason=FailureReason.AUTH,
            failure_interface_id="HmIP-RF",
        )

        # Check that publish_sync was called with correct event
        assert mock_event_bus.publish_sync.called
        call_args = mock_event_bus.publish_sync.call_args
        event = call_args.kwargs["event"]

        assert isinstance(event, SystemStatusEvent)
        assert event.central_state == CentralState.FAILED
        assert event.failure_reason == FailureReason.AUTH
        assert event.failure_interface_id == "HmIP-RF"

    def test_publish_running_event_has_no_failure_reason(self) -> None:
        """Test that RUNNING event does not include failure reason."""
        mock_event_bus = MagicMock()
        sm = CentralStateMachine(central_name="test-central", event_bus=mock_event_bus)

        sm.transition_to(target=CentralState.INITIALIZING)
        sm.transition_to(target=CentralState.RUNNING)

        # Check the last call to publish_sync
        call_args = mock_event_bus.publish_sync.call_args
        event = call_args.kwargs["event"]

        assert isinstance(event, SystemStatusEvent)
        assert event.central_state == CentralState.RUNNING
        assert event.failure_reason is None
        assert event.failure_interface_id is None
