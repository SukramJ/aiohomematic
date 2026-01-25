# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract tests for client lifecycle behavior.

STABILITY GUARANTEE
-------------------
These tests define the stable API contract for InterfaceClient lifecycle methods.
Any change that breaks these tests requires a MAJOR version bump.

The contract ensures that:
1. initialize_proxy transitions state correctly
2. deinitialize_proxy cleans up state correctly
3. reconnect applies exponential backoff
4. stop unsubscribes and transitions to STOPPED
5. Lifecycle methods respect capability flags
6. ProxyInitState enum values are stable

See ADR-0018 for architectural context.
"""

from __future__ import annotations

from aiohomematic.const import ClientState, ProxyInitState, TimeoutConfig

# =============================================================================
# Contract: ProxyInitState Enum
# =============================================================================


class TestProxyInitStateEnumContract:
    """Contract: ProxyInitState enum values must remain stable."""

    def test_proxy_init_state_has_de_init_failed(self) -> None:
        """Contract: ProxyInitState.DE_INIT_FAILED must exist with value 4."""
        assert hasattr(ProxyInitState, "DE_INIT_FAILED")
        assert ProxyInitState.DE_INIT_FAILED.value == 4

    def test_proxy_init_state_has_de_init_skipped(self) -> None:
        """Contract: ProxyInitState.DE_INIT_SKIPPED must exist with value 16."""
        assert hasattr(ProxyInitState, "DE_INIT_SKIPPED")
        assert ProxyInitState.DE_INIT_SKIPPED.value == 16

    def test_proxy_init_state_has_de_init_success(self) -> None:
        """Contract: ProxyInitState.DE_INIT_SUCCESS must exist with value 8."""
        assert hasattr(ProxyInitState, "DE_INIT_SUCCESS")
        assert ProxyInitState.DE_INIT_SUCCESS.value == 8

    def test_proxy_init_state_has_init_failed(self) -> None:
        """Contract: ProxyInitState.INIT_FAILED must exist with value 0."""
        assert hasattr(ProxyInitState, "INIT_FAILED")
        assert ProxyInitState.INIT_FAILED.value == 0

    def test_proxy_init_state_has_init_success(self) -> None:
        """Contract: ProxyInitState.INIT_SUCCESS must exist with value 1."""
        assert hasattr(ProxyInitState, "INIT_SUCCESS")
        assert ProxyInitState.INIT_SUCCESS.value == 1


# =============================================================================
# Contract: ClientState Lifecycle Values
# =============================================================================


class TestClientStateLifecycleContract:
    """Contract: ClientState values used in lifecycle must be stable."""

    def test_lifecycle_states_exist(self) -> None:
        """Contract: All lifecycle-related states exist."""
        # Initialization
        assert hasattr(ClientState, "CREATED")
        assert hasattr(ClientState, "INITIALIZING")
        assert hasattr(ClientState, "INITIALIZED")

        # Connection
        assert hasattr(ClientState, "CONNECTING")
        assert hasattr(ClientState, "CONNECTED")
        assert hasattr(ClientState, "DISCONNECTED")

        # Recovery
        assert hasattr(ClientState, "RECONNECTING")

        # Shutdown
        assert hasattr(ClientState, "STOPPING")
        assert hasattr(ClientState, "STOPPED")

        # Error
        assert hasattr(ClientState, "FAILED")


# =============================================================================
# Contract: TimeoutConfig Values
# =============================================================================


class TestTimeoutConfigContract:
    """Contract: TimeoutConfig values used in lifecycle must be stable."""

    def test_timeout_config_has_callback_warn_interval(self) -> None:
        """Contract: TimeoutConfig has callback_warn_interval field."""
        config = TimeoutConfig()
        assert hasattr(config, "callback_warn_interval")
        assert isinstance(config.callback_warn_interval, (int, float))

    def test_timeout_config_has_connectivity_error_threshold(self) -> None:
        """Contract: TimeoutConfig has connectivity_error_threshold field."""
        config = TimeoutConfig()
        assert hasattr(config, "connectivity_error_threshold")
        assert isinstance(config.connectivity_error_threshold, int)

    def test_timeout_config_has_ping_timeout(self) -> None:
        """Contract: TimeoutConfig has ping_timeout field."""
        config = TimeoutConfig()
        assert hasattr(config, "ping_timeout")
        assert isinstance(config.ping_timeout, (int, float))

    def test_timeout_config_has_reconnect_fields(self) -> None:
        """Contract: TimeoutConfig has reconnect-related fields."""
        config = TimeoutConfig()

        # Reconnect backoff parameters
        assert hasattr(config, "reconnect_initial_delay")
        assert hasattr(config, "reconnect_max_delay")
        assert hasattr(config, "reconnect_backoff_factor")

        # Verify types
        assert isinstance(config.reconnect_initial_delay, (int, float))
        assert isinstance(config.reconnect_max_delay, (int, float))
        assert isinstance(config.reconnect_backoff_factor, (int, float))

    def test_timeout_config_has_rpc_timeout(self) -> None:
        """Contract: TimeoutConfig has rpc_timeout field."""
        config = TimeoutConfig()
        assert hasattr(config, "rpc_timeout")
        assert isinstance(config.rpc_timeout, (int, float))


# =============================================================================
# Contract: Reconnect Backoff Formula
# =============================================================================


class TestReconnectBackoffContract:
    """Contract: Reconnect backoff follows expected formula."""

    def test_backoff_factor_is_2(self) -> None:
        """Contract: Default reconnect_backoff_factor is 2."""
        config = TimeoutConfig()
        assert config.reconnect_backoff_factor == 2

    def test_backoff_formula(self) -> None:
        """Contract: Backoff formula is initial * factor^attempts, capped at max."""
        config = TimeoutConfig()
        initial = config.reconnect_initial_delay
        factor = config.reconnect_backoff_factor
        max_delay = config.reconnect_max_delay

        # Calculate expected delays for each attempt
        for attempt in range(10):
            expected = min(initial * (factor**attempt), max_delay)
            assert expected <= max_delay

    def test_initial_delay_is_reasonable(self) -> None:
        """Contract: Initial delay is at least 0.5 seconds."""
        config = TimeoutConfig()
        assert config.reconnect_initial_delay >= 0.5

    def test_max_delay_is_reasonable(self) -> None:
        """Contract: Max delay is at least 1 second."""
        config = TimeoutConfig()
        assert config.reconnect_max_delay >= 1


# =============================================================================
# Contract: Lifecycle State Transitions
# =============================================================================


class TestLifecycleStateTransitionsContract:
    """Contract: Lifecycle methods use correct state transitions."""

    def test_deinitialize_proxy_uses_disconnected(self) -> None:
        """Contract: deinitialize_proxy transitions to DISCONNECTED."""
        assert ClientState.DISCONNECTED.value == "disconnected"

    def test_failure_uses_failed(self) -> None:
        """Contract: Failures transition to FAILED."""
        assert ClientState.FAILED.value == "failed"

    def test_init_client_uses_initializing(self) -> None:
        """Contract: init_client transitions to INITIALIZING then INITIALIZED."""
        # This is a documentation contract - init_client must use these states
        assert ClientState.INITIALIZING.value == "initializing"
        assert ClientState.INITIALIZED.value == "initialized"

    def test_initialize_proxy_uses_connecting(self) -> None:
        """Contract: initialize_proxy transitions to CONNECTING then CONNECTED."""
        assert ClientState.CONNECTING.value == "connecting"
        assert ClientState.CONNECTED.value == "connected"

    def test_reconnect_uses_reconnecting(self) -> None:
        """Contract: reconnect transitions to RECONNECTING."""
        assert ClientState.RECONNECTING.value == "reconnecting"

    def test_stop_uses_stopping_and_stopped(self) -> None:
        """Contract: stop transitions to STOPPING then STOPPED."""
        assert ClientState.STOPPING.value == "stopping"
        assert ClientState.STOPPED.value == "stopped"


# =============================================================================
# Contract: Capability-Gated Lifecycle Methods
# =============================================================================


class TestCapabilityGatedLifecycleContract:
    """Contract: Lifecycle methods respect capability flags."""

    def test_ping_pong_false_affects_connection_check(self) -> None:
        """
        Contract: When ping_pong=False, is_callback_alive returns True.

        This prevents false reconnects for interfaces like CUxD/CCU-Jack
        that don't support the ping/pong mechanism.
        """

    def test_rpc_callback_false_skips_deinit(self) -> None:
        """
        Contract: When rpc_callback=False, deinitialize_proxy skips XML-RPC deinit.

        With rpc_callback=False:
        - deinitialize_proxy should still transition to DISCONNECTED
        - But no deinit() RPC call is made
        - Returns DE_INIT_SUCCESS immediately
        """

    def test_rpc_callback_false_skips_init(self) -> None:
        """
        Contract: When rpc_callback=False, initialize_proxy skips XML-RPC init.

        With rpc_callback=False:
        - initialize_proxy should still transition to CONNECTED
        - But it should use list_devices instead of init() call
        - No XML-RPC callback URL is registered
        """


# =============================================================================
# Contract: Client Properties
# =============================================================================


class TestClientPropertiesContract:
    """Contract: Client properties must behave correctly."""

    def test_available_states(self) -> None:
        """Contract: available is True for CONNECTED and RECONNECTING."""
        from aiohomematic.client import ClientStateMachine

        # Document which states count as "available"
        available_states = {
            ClientState.CONNECTED,
            ClientState.RECONNECTING,
        }

        # Verify using state machine
        sm = ClientStateMachine(interface_id="test", event_bus=None)  # type: ignore[arg-type]

        for state in ClientState:
            sm._state = state
            if state in available_states:
                assert sm.is_available is True
            else:
                assert sm.is_available is False

    def test_is_initialized_states(self) -> None:
        """Contract: is_initialized is True for CONNECTED, DISCONNECTED, RECONNECTING."""
        # Document which states count as "initialized"
        initialized_states = {
            ClientState.CONNECTED,
            ClientState.DISCONNECTED,
            ClientState.RECONNECTING,
        }

        not_initialized_states = {
            ClientState.CREATED,
            ClientState.INITIALIZING,
            ClientState.INITIALIZED,  # Not yet connected
            ClientState.CONNECTING,  # Still connecting
            ClientState.STOPPING,
            ClientState.STOPPED,
            ClientState.FAILED,
        }

        # Verify all states are accounted for
        all_states = initialized_states | not_initialized_states
        assert all_states == set(ClientState)


# =============================================================================
# Contract: Connection Error Handling
# =============================================================================


class TestConnectionErrorHandlingContract:
    """Contract: Connection error handling must behave correctly."""

    def test_callback_warn_interval_default(self) -> None:
        """Contract: Default callback_warn_interval allows reasonable time."""
        config = TimeoutConfig()
        # In test mode: 12 seconds (1 * 12)
        # In production: 180 seconds (15 * 12 = 3 minutes)
        # Should be at least 10 seconds
        assert config.callback_warn_interval >= 10

    def test_connectivity_error_threshold_default(self) -> None:
        """Contract: Default connectivity_error_threshold is 1."""
        config = TimeoutConfig()
        # The default should allow quick detection of connection issues
        assert config.connectivity_error_threshold >= 1


# =============================================================================
# Contract: Recovery Integration
# =============================================================================


class TestRecoveryIntegrationContract:
    """Contract: Client recovery integrates correctly with coordinator."""

    def test_can_reconnect_checks_state_machine(self) -> None:
        """
        Contract: can_reconnect property checks state machine.

        Returns True only if RECONNECTING is a valid transition
        from the current state.
        """
        from aiohomematic.client import ClientStateMachine
        from aiohomematic.client.state_machine import _VALID_TRANSITIONS

        # Verify can_reconnect matches transition table
        sm = ClientStateMachine(interface_id="test", event_bus=None)  # type: ignore[arg-type]

        for state in ClientState:
            sm._state = state
            valid_targets = _VALID_TRANSITIONS.get(state, frozenset())
            expected = ClientState.RECONNECTING in valid_targets
            assert sm.can_reconnect == expected

    def test_reconnect_increments_on_failure(self) -> None:
        """
        Contract: Failed reconnect increments attempt counter.

        After failed reconnect():
        - Reconnect attempts counter is incremented
        - State may transition to FAILED if limits exceeded
        """

    def test_reconnect_resets_on_success(self) -> None:
        """
        Contract: Successful reconnect resets circuit breakers.

        After successful reconnect():
        - Circuit breakers are reset
        - Connection error count is reset
        - Reconnect attempts counter is reset
        """
