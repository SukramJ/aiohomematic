# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Connection health tracking for unified availability determination.

This module provides unified health tracking that replaces the three overlapping
availability systems (state machine, circuit breaker, forced availability) with
a single source of truth.

Overview
--------
The health system provides:
- ConnectionHealth: Per-client health status
- CentralHealth: Aggregated system health
- Unified availability determination
- Health scoring for weighted decisions

Key Classes
-----------
- ConnectionHealth: Tracks health of a single client connection
- CentralHealth: Aggregates health across all clients

The health system observes:
- Client state machine status
- Circuit breaker states
- Communication metrics (last request, last event)
- Recovery tracking

Example:
    # Get health for a specific client
    health = central.health.get_client_health("ccu-main-HmIP-RF")
    if health.is_available:
        # Client is fully operational
        ...
    elif health.is_degraded:
        # Client has issues but may work
        ...

    # Check overall system health
    if central.health.all_clients_healthy:
        # All clients are good
        ...

"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Final

from aiohomematic.client.circuit_breaker import CircuitState
from aiohomematic.const import CentralState, ClientState, Interface
from aiohomematic.interfaces.central import CentralHealthProtocol, ConnectionHealthProtocol, HealthTrackerProtocol

if TYPE_CHECKING:
    from typing import Any

    from aiohomematic.central.state_machine import CentralStateMachine

# Threshold for considering events as "recent" (5 minutes)
EVENT_STALENESS_THRESHOLD: Final = 300.0

# Health score weights
_WEIGHT_STATE_MACHINE: Final = 0.4
_WEIGHT_CIRCUIT_BREAKERS: Final = 0.3
_WEIGHT_RECENT_ACTIVITY: Final = 0.3


@dataclass(slots=True)
class ConnectionHealth(ConnectionHealthProtocol):
    """
    Unified health status for a single client connection.

    This class replaces the three overlapping availability systems:
    - state_machine.is_available
    - circuit_breaker.is_available
    - forced_availability

    It provides a single source of truth for connection health with
    detailed metrics for monitoring and debugging.

    Attributes
    ----------
    interface_id : str
        Unique identifier for the interface (e.g., "ccu-main-HmIP-RF")
    interface : Interface
        The interface type (e.g., Interface.HMIP_RF)
    client_state : ClientState
        Current state from the client state machine
    xml_rpc_circuit : CircuitState
        State of the XML-RPC circuit breaker
    json_rpc_circuit : CircuitState | None
        State of the JSON-RPC circuit breaker (None for non-CCU clients)
    last_successful_request : datetime | None
        Timestamp of last successful RPC request
    last_failed_request : datetime | None
        Timestamp of last failed RPC request
    last_event_received : datetime | None
        Timestamp of last event received from backend
    consecutive_failures : int
        Number of consecutive failed operations
    reconnect_attempts : int
        Number of reconnection attempts
    last_reconnect_attempt : datetime | None
        Timestamp of last reconnection attempt
    in_recovery : bool
        True if recovery is in progress for this client

    """

    interface_id: str
    interface: Interface
    client_state: ClientState = ClientState.CREATED
    xml_rpc_circuit: CircuitState = CircuitState.CLOSED
    json_rpc_circuit: CircuitState | None = None
    last_successful_request: datetime | None = None
    last_failed_request: datetime | None = None
    last_event_received: datetime | None = None
    consecutive_failures: int = 0
    reconnect_attempts: int = 0
    last_reconnect_attempt: datetime | None = None
    in_recovery: bool = False

    @property
    def can_receive_events(self) -> bool:
        """
        Check if client can receive events from the backend.

        Returns True if connected and has received events recently.
        """
        if not self.is_connected:
            return False
        if self.last_event_received is None:
            return False
        age = (datetime.now() - self.last_event_received).total_seconds()
        return age < EVENT_STALENESS_THRESHOLD

    @property
    def health_score(self) -> float:
        """
        Calculate a numeric health score (0.0 - 1.0).

        The score is weighted:
        - 40% State Machine status
        - 30% Circuit Breaker status
        - 30% Recent Activity

        Returns:
            Health score between 0.0 (unhealthy) and 1.0 (fully healthy)

        """
        score = 0.0

        # State Machine (40%)
        if self.client_state == ClientState.CONNECTED:
            score += _WEIGHT_STATE_MACHINE
        elif self.client_state == ClientState.RECONNECTING:
            score += _WEIGHT_STATE_MACHINE * 0.5

        # Circuit Breakers (30% total - 15% each)
        xml_weight = _WEIGHT_CIRCUIT_BREAKERS / 2
        json_weight = _WEIGHT_CIRCUIT_BREAKERS / 2

        if self.xml_rpc_circuit == CircuitState.CLOSED:
            score += xml_weight
        elif self.xml_rpc_circuit == CircuitState.HALF_OPEN:
            score += xml_weight * 0.33

        if self.json_rpc_circuit is None:
            # No JSON-RPC circuit - give full credit
            score += json_weight
        elif self.json_rpc_circuit == CircuitState.CLOSED:
            score += json_weight
        elif self.json_rpc_circuit == CircuitState.HALF_OPEN:
            score += json_weight * 0.33

        # Recent Activity (30% total - 15% each for request and event)
        activity_weight = _WEIGHT_RECENT_ACTIVITY / 2

        if self.last_successful_request:
            age = (datetime.now() - self.last_successful_request).total_seconds()
            if age < 60:
                score += activity_weight
            elif age < 300:
                score += activity_weight * 0.66
            elif age < 600:
                score += activity_weight * 0.33

        if self.last_event_received:
            age = (datetime.now() - self.last_event_received).total_seconds()
            if age < 60:
                score += activity_weight
            elif age < 300:
                score += activity_weight * 0.66
            elif age < 600:
                score += activity_weight * 0.33

        return min(score, 1.0)

    @property
    def is_available(self) -> bool:
        """
        Check if client is available for operations.

        Returns True if:
        - Client state is CONNECTED
        - All circuit breakers are CLOSED
        """
        return (
            self.client_state == ClientState.CONNECTED
            and self.xml_rpc_circuit == CircuitState.CLOSED
            and (self.json_rpc_circuit is None or self.json_rpc_circuit == CircuitState.CLOSED)
        )

    @property
    def is_connected(self) -> bool:
        """Check if client is in connected state."""
        return self.client_state == ClientState.CONNECTED

    @property
    def is_degraded(self) -> bool:
        """
        Check if client is in degraded state.

        Returns True if connected/reconnecting but circuit breakers have issues.
        """
        if self.client_state not in (ClientState.CONNECTED, ClientState.RECONNECTING):
            return False
        return self.xml_rpc_circuit != CircuitState.CLOSED or (
            self.json_rpc_circuit is not None and self.json_rpc_circuit != CircuitState.CLOSED
        )

    @property
    def is_failed(self) -> bool:
        """Check if client is in failed or disconnected state."""
        return self.client_state in (ClientState.FAILED, ClientState.DISCONNECTED)

    def record_event_received(self) -> None:
        """Record that an event was received from the backend."""
        self.last_event_received = datetime.now()

    def record_failed_request(self) -> None:
        """Record a failed RPC request."""
        self.last_failed_request = datetime.now()
        self.consecutive_failures += 1

    def record_reconnect_attempt(self) -> None:
        """Record a reconnection attempt."""
        self.reconnect_attempts += 1
        self.last_reconnect_attempt = datetime.now()

    def record_successful_request(self) -> None:
        """Record a successful RPC request."""
        self.last_successful_request = datetime.now()
        self.consecutive_failures = 0

    def reset_reconnect_counter(self) -> None:
        """Reset the reconnect attempt counter (called on successful recovery)."""
        self.reconnect_attempts = 0

    def update_from_client(self, *, client: Any) -> None:
        """
        Update health from client state.

        Args:
            client: The client to read state from (ClientCCU or similar)

        Note:
            This method uses hasattr checks because the client's internal
            attributes (_state_machine, _proxy, _json_rpc_client) are not
            part of the ClientProtocol interface. A proper protocol will
            be added in Phase 1.4.

        """
        # Update client state from state machine
        # pylint: disable=protected-access
        if hasattr(client, "_state_machine"):
            self.client_state = client._state_machine.state

        # Update circuit breaker states
        if hasattr(client, "_proxy") and hasattr(client._proxy, "_circuit_breaker"):
            self.xml_rpc_circuit = client._proxy._circuit_breaker.state

        if (
            hasattr(client, "_json_rpc_client")
            and client._json_rpc_client is not None
            and hasattr(client._json_rpc_client, "_circuit_breaker")
        ):
            self.json_rpc_circuit = client._json_rpc_client._circuit_breaker.state
        # pylint: enable=protected-access


@dataclass(slots=True)
class CentralHealth(CentralHealthProtocol):
    """
    Aggregated health status for the entire central system.

    This class provides a unified view of system health by aggregating
    health from all connected clients.

    Attributes
    ----------
    central_state : CentralState
        Current state of the central state machine
    client_health : dict[str, ConnectionHealth]
        Health status for each client (interface_id -> health)
    primary_interface : Interface | None
        The primary interface type for determining primary_client_healthy

    """

    central_state: CentralState = CentralState.STARTING
    client_health: dict[str, ConnectionHealth] = field(default_factory=dict)
    primary_interface: Interface | None = None

    @property
    def all_clients_healthy(self) -> bool:
        """Check if all clients are fully healthy."""
        if not self.client_health:
            return False
        return all(h.is_available for h in self.client_health.values())

    @property
    def any_client_healthy(self) -> bool:
        """Check if at least one client is healthy."""
        return any(h.is_available for h in self.client_health.values())

    @property
    def degraded_clients(self) -> list[str]:
        """Return list of interface IDs with degraded health."""
        return [iid for iid, h in self.client_health.items() if h.is_degraded]

    @property
    def failed_clients(self) -> list[str]:
        """Return list of interface IDs that have failed."""
        return [iid for iid, h in self.client_health.items() if h.is_failed]

    @property
    def healthy_clients(self) -> list[str]:
        """Return list of healthy interface IDs."""
        return [iid for iid, h in self.client_health.items() if h.is_available]

    @property
    def overall_health_score(self) -> float:
        """
        Calculate weighted average health score across all clients.

        Returns 0.0 if no clients are registered.
        """
        if not self.client_health:
            return 0.0
        scores = [h.health_score for h in self.client_health.values()]
        return sum(scores) / len(scores)

    @property
    def primary_client_healthy(self) -> bool:
        """
        Check if the primary client (for JSON-RPC) is healthy.

        The primary client is determined by:
        1. If primary_interface is set, find client with that interface
        2. Otherwise, prefer HmIP-RF, then first available
        """
        if not self.client_health:
            return False

        # Find primary client
        primary_health: ConnectionHealth | None = None

        if self.primary_interface:
            for health in self.client_health.values():
                if health.interface == self.primary_interface:
                    primary_health = health
                    break

        if primary_health is None:
            # Fallback: prefer HmIP-RF
            for health in self.client_health.values():
                if health.interface == Interface.HMIP_RF:
                    primary_health = health
                    break

        if primary_health is None:
            # Last resort: first client
            primary_health = next(iter(self.client_health.values()), None)

        return primary_health.is_available if primary_health else False

    @property
    def state(self) -> CentralState:
        """Return current central state."""
        return self.central_state

    def get_client_health(self, *, interface_id: str) -> ConnectionHealth | None:
        """
        Get health for a specific client.

        Args:
            interface_id: The interface ID to look up

        Returns:
            ConnectionHealth for the client, or None if not found

        """
        return self.client_health.get(interface_id)

    def register_client(
        self,
        *,
        interface_id: str,
        interface: Interface,
    ) -> ConnectionHealth:
        """
        Register a new client and create its health tracker.

        Args:
            interface_id: Unique identifier for the interface
            interface: The interface type

        Returns:
            The created ConnectionHealth instance

        """
        health = ConnectionHealth(interface_id=interface_id, interface=interface)
        self.client_health[interface_id] = health
        return health

    def should_be_degraded(self) -> bool:
        """
        Determine if central should be in DEGRADED state.

        Returns True if at least one client is healthy but not all.
        """
        return self.any_client_healthy and not self.all_clients_healthy

    def should_be_running(self) -> bool:
        """
        Determine if central should be in RUNNING state.

        Based on user's choice: ALL clients must be CONNECTED.
        """
        return self.all_clients_healthy

    def unregister_client(self, *, interface_id: str) -> None:
        """
        Remove a client from health tracking.

        Args:
            interface_id: The interface ID to remove

        """
        self.client_health.pop(interface_id, None)

    def update_central_state(self, *, state: CentralState) -> None:
        """
        Update the cached central state.

        Args:
            state: The new central state

        """
        self.central_state = state


class HealthTracker(HealthTrackerProtocol):
    """
    Central health tracking coordinator.

    This class manages health tracking for all clients and provides
    methods to query and update health status.
    """

    __slots__ = (
        "_central_health",
        "_central_name",
        "_state_machine",
    )

    def __init__(
        self,
        *,
        central_name: str,
        state_machine: CentralStateMachine | None = None,
    ) -> None:
        """
        Initialize the health tracker.

        Args:
            central_name: Name of the central unit
            state_machine: Optional reference to the central state machine

        """
        self._central_name: Final = central_name
        self._state_machine = state_machine
        self._central_health: Final = CentralHealth()

    @property
    def health(self) -> CentralHealth:
        """Return the aggregated central health."""
        return self._central_health

    def get_client_health(self, *, interface_id: str) -> ConnectionHealth | None:
        """
        Get health for a specific client.

        Args:
            interface_id: The interface ID to look up

        Returns:
            ConnectionHealth for the client, or None if not found

        """
        return self._central_health.get_client_health(interface_id=interface_id)

    def register_client(
        self,
        *,
        interface_id: str,
        interface: Interface,
    ) -> ConnectionHealth:
        """
        Register a new client for health tracking.

        Args:
            interface_id: Unique identifier for the interface
            interface: The interface type

        Returns:
            The created ConnectionHealth instance

        """
        return self._central_health.register_client(
            interface_id=interface_id,
            interface=interface,
        )

    def set_primary_interface(self, *, interface: Interface) -> None:
        """
        Set the primary interface type.

        Args:
            interface: The primary interface type

        """
        self._central_health.primary_interface = interface

    def set_state_machine(self, *, state_machine: CentralStateMachine) -> None:
        """
        Set the central state machine reference.

        Args:
            state_machine: The central state machine

        """
        self._state_machine = state_machine

    def unregister_client(self, *, interface_id: str) -> None:
        """
        Remove a client from health tracking.

        Args:
            interface_id: The interface ID to remove

        """
        self._central_health.unregister_client(interface_id=interface_id)

    def update_all_from_clients(self, *, clients: dict[str, Any]) -> None:
        """
        Update health for all clients.

        Args:
            clients: Dictionary of interface_id -> client

        """
        for interface_id, client in clients.items():
            if (health := self._central_health.get_client_health(interface_id=interface_id)) is not None:
                health.update_from_client(client=client)

        # Update central state in health
        if self._state_machine is not None:
            self._central_health.update_central_state(state=self._state_machine.state)

    def update_client_health(
        self,
        *,
        interface_id: str,
        old_state: ClientState,
        new_state: ClientState,
    ) -> None:
        """
        Update health for a specific client based on state change.

        Args:
            interface_id: The interface ID that changed
            old_state: Previous client state
            new_state: New client state

        """
        if (health := self._central_health.get_client_health(interface_id=interface_id)) is not None:
            health.client_state = new_state

            # Track reconnection attempts
            if new_state == ClientState.RECONNECTING and old_state != ClientState.RECONNECTING:
                health.record_reconnect_attempt()

            # Reset reconnect counter on successful connection
            if new_state == ClientState.CONNECTED:
                health.reset_reconnect_counter()

        # Update central state in health
        if self._state_machine is not None:
            self._central_health.update_central_state(state=self._state_machine.state)
