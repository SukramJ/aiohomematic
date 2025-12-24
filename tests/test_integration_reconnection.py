# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Reconnection and recovery integration tests.

These tests validate the system's ability to handle connection loss,
reconnection scenarios, and state recovery after network issues.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any
from unittest.mock import Mock

import pytest

from aiohomematic.central import CentralConnectionState
from aiohomematic.central.event_bus import DataPointUpdatedEvent, EventBus
from aiohomematic.central.integration_events import SystemStatusEvent
from aiohomematic.client import AioJsonRpcAioHttpClient, BaseRpcProxy
from aiohomematic.const import DataPointKey, ParamsetKey

TEST_DEVICES: set[str] = {"VCU2128127", "VCU6354483"}


class TestConnectionStateManagement:
    """Test CentralConnectionState behavior."""

    @pytest.mark.asyncio
    async def test_connection_state_add_json_issue(self) -> None:
        """Test adding a JSON-RPC connection issue."""
        state = CentralConnectionState()
        mock_issuer = Mock(spec=AioJsonRpcAioHttpClient)

        added = state.add_issue(issuer=mock_issuer, iid="HmIP-RF")

        assert added is True
        assert state.has_any_issue is True
        assert state.json_issue_count == 1
        assert state.rpc_proxy_issue_count == 0

    @pytest.mark.asyncio
    async def test_connection_state_add_rpc_proxy_issue(self) -> None:
        """Test adding an XML-RPC proxy connection issue."""
        state = CentralConnectionState()
        mock_issuer = Mock(spec=BaseRpcProxy)

        added = state.add_issue(issuer=mock_issuer, iid="BidCos-RF")

        assert added is True
        assert state.has_any_issue is True
        assert state.json_issue_count == 0
        assert state.rpc_proxy_issue_count == 1

    @pytest.mark.asyncio
    async def test_connection_state_clear_all_issues(self) -> None:
        """Test clearing all connection issues."""
        state = CentralConnectionState()
        mock_json_issuer = Mock(spec=AioJsonRpcAioHttpClient)
        mock_rpc_issuer = Mock(spec=BaseRpcProxy)

        state.add_issue(issuer=mock_json_issuer, iid="HmIP-RF")
        state.add_issue(issuer=mock_rpc_issuer, iid="BidCos-RF")
        assert state.issue_count == 2

        cleared = state.clear_all_issues()
        assert cleared == 2
        assert state.has_any_issue is False
        assert state.issue_count == 0

    @pytest.mark.asyncio
    async def test_connection_state_duplicate_issue_not_added(self) -> None:
        """Test that duplicate issues are not added twice."""
        state = CentralConnectionState()
        mock_issuer = Mock(spec=AioJsonRpcAioHttpClient)

        added1 = state.add_issue(issuer=mock_issuer, iid="HmIP-RF")
        added2 = state.add_issue(issuer=mock_issuer, iid="HmIP-RF")

        assert added1 is True
        assert added2 is False
        assert state.issue_count == 1

    @pytest.mark.asyncio
    async def test_connection_state_initial_no_issues(self) -> None:
        """Test that initial state has no connection issues."""
        state = CentralConnectionState()

        assert state.has_any_issue is False
        assert state.issue_count == 0
        assert state.json_issue_count == 0
        assert state.rpc_proxy_issue_count == 0

    @pytest.mark.asyncio
    async def test_connection_state_remove_issue(self) -> None:
        """Test removing a connection issue."""
        state = CentralConnectionState()
        mock_issuer = Mock(spec=AioJsonRpcAioHttpClient)

        state.add_issue(issuer=mock_issuer, iid="HmIP-RF")
        assert state.has_any_issue is True

        removed = state.remove_issue(issuer=mock_issuer, iid="HmIP-RF")
        assert removed is True
        assert state.has_any_issue is False


class TestConnectionStateEvents:
    """Test SystemStatusEvent publishing for connection state changes."""

    @pytest.mark.asyncio
    async def test_event_published_on_issue_add(self) -> None:
        """Test that SystemStatusEvent is published when issue is added."""
        event_bus = EventBus()
        received_events: list[SystemStatusEvent] = []

        class MockEventBusProvider:
            @property
            def event_bus(self) -> EventBus:
                return event_bus

        state = CentralConnectionState(event_bus_provider=MockEventBusProvider())

        def on_state_change(event: SystemStatusEvent) -> None:
            if event.connection_state:
                received_events.append(event)

        event_bus.subscribe(
            event_type=SystemStatusEvent,
            event_key=None,
            handler=on_state_change,
        )

        mock_issuer = Mock(spec=AioJsonRpcAioHttpClient)
        state.add_issue(issuer=mock_issuer, iid="HmIP-RF")

        # Allow async event processing
        await asyncio.sleep(0.02)

        assert len(received_events) == 1
        assert received_events[0].connection_state is not None
        assert received_events[0].connection_state[0] == "HmIP-RF"
        assert received_events[0].connection_state[1] is False

    @pytest.mark.asyncio
    async def test_event_published_on_issue_remove(self) -> None:
        """Test that SystemStatusEvent is published when issue is removed."""
        event_bus = EventBus()
        received_events: list[SystemStatusEvent] = []

        class MockEventBusProvider:
            @property
            def event_bus(self) -> EventBus:
                return event_bus

        state = CentralConnectionState(event_bus_provider=MockEventBusProvider())

        def on_state_change(event: SystemStatusEvent) -> None:
            if event.connection_state:
                received_events.append(event)

        event_bus.subscribe(
            event_type=SystemStatusEvent,
            event_key=None,
            handler=on_state_change,
        )

        mock_issuer = Mock(spec=AioJsonRpcAioHttpClient)
        state.add_issue(issuer=mock_issuer, iid="HmIP-RF")
        await asyncio.sleep(0.02)

        state.remove_issue(issuer=mock_issuer, iid="HmIP-RF")
        await asyncio.sleep(0.02)

        assert len(received_events) == 2
        # First event: disconnected
        assert received_events[0].connection_state is not None
        assert received_events[0].connection_state[1] is False
        # Second event: reconnected
        assert received_events[1].connection_state is not None
        assert received_events[1].connection_state[1] is True
        assert received_events[1].connection_state[0] == "HmIP-RF"

    @pytest.mark.asyncio
    async def test_events_published_on_clear_all(self) -> None:
        """Test that events are published for each cleared issue."""
        event_bus = EventBus()
        received_events: list[SystemStatusEvent] = []

        class MockEventBusProvider:
            @property
            def event_bus(self) -> EventBus:
                return event_bus

        state = CentralConnectionState(event_bus_provider=MockEventBusProvider())

        def on_state_change(event: SystemStatusEvent) -> None:
            if event.connection_state:
                received_events.append(event)

        event_bus.subscribe(
            event_type=SystemStatusEvent,
            event_key=None,
            handler=on_state_change,
        )

        mock_json_issuer = Mock(spec=AioJsonRpcAioHttpClient)
        mock_rpc_issuer = Mock(spec=BaseRpcProxy)
        state.add_issue(issuer=mock_json_issuer, iid="HmIP-RF")
        state.add_issue(issuer=mock_rpc_issuer, iid="BidCos-RF")
        await asyncio.sleep(0.02)

        state.clear_all_issues()
        await asyncio.sleep(0.02)

        # 2 disconnect events + 2 reconnect events
        assert len(received_events) == 4
        reconnect_events = [e for e in received_events if e.connection_state and e.connection_state[1] is True]
        assert len(reconnect_events) == 2


class TestPartialConnectivityHandling:
    """Test handling when only some interfaces are reachable."""

    @pytest.mark.asyncio
    async def test_partial_connectivity_one_interface_down(self) -> None:
        """Test state when one interface has issues but others are fine."""
        state = CentralConnectionState()
        mock_json_issuer = Mock(spec=AioJsonRpcAioHttpClient)
        mock_rpc_issuer = Mock(spec=BaseRpcProxy)

        # Only JSON interface has issues
        state.add_issue(issuer=mock_json_issuer, iid="HmIP-RF")

        assert state.has_any_issue is True
        assert state.json_issue_count == 1
        assert state.rpc_proxy_issue_count == 0

        # RPC interface is still healthy - verify we can track separately
        assert state.has_issue(issuer=mock_json_issuer, iid="HmIP-RF") is True
        assert state.has_issue(issuer=mock_rpc_issuer, iid="BidCos-RF") is False

    @pytest.mark.asyncio
    async def test_partial_recovery_one_interface_recovers(self) -> None:
        """Test state when one interface recovers while others stay down."""
        state = CentralConnectionState()
        mock_json_issuer = Mock(spec=AioJsonRpcAioHttpClient)
        mock_rpc_issuer = Mock(spec=BaseRpcProxy)

        # Both interfaces have issues
        state.add_issue(issuer=mock_json_issuer, iid="HmIP-RF")
        state.add_issue(issuer=mock_rpc_issuer, iid="BidCos-RF")
        assert state.issue_count == 2

        # JSON interface recovers
        state.remove_issue(issuer=mock_json_issuer, iid="HmIP-RF")
        assert state.has_any_issue is True
        assert state.json_issue_count == 0
        assert state.rpc_proxy_issue_count == 1

        # RPC interface recovers
        state.remove_issue(issuer=mock_rpc_issuer, iid="BidCos-RF")
        assert state.has_any_issue is False


class TestConnectionStateTransitions:
    """Test connection state machine transitions."""

    @pytest.mark.asyncio
    async def test_multiple_interfaces_state_transitions(self) -> None:
        """Test state transitions with multiple interfaces."""
        event_bus = EventBus()
        state_history: list[tuple[str, bool]] = []

        class MockEventBusProvider:
            @property
            def event_bus(self) -> EventBus:
                return event_bus

        state = CentralConnectionState(event_bus_provider=MockEventBusProvider())

        def track_state(event: SystemStatusEvent) -> None:
            if event.connection_state:
                state_history.append((event.connection_state[0], event.connection_state[1]))

        event_bus.subscribe(
            event_type=SystemStatusEvent,
            event_key=None,
            handler=track_state,
        )

        mock_json_issuer = Mock(spec=AioJsonRpcAioHttpClient)
        mock_rpc_issuer = Mock(spec=BaseRpcProxy)

        # Both interfaces go down
        state.add_issue(issuer=mock_json_issuer, iid="HmIP-RF")
        state.add_issue(issuer=mock_rpc_issuer, iid="BidCos-RF")
        await asyncio.sleep(0.02)

        # One recovers
        state.remove_issue(issuer=mock_json_issuer, iid="HmIP-RF")
        await asyncio.sleep(0.02)

        # Second recovers
        state.remove_issue(issuer=mock_rpc_issuer, iid="BidCos-RF")
        await asyncio.sleep(0.02)

        assert len(state_history) == 4
        # Verify we have 2 disconnects and 2 reconnects
        disconnects = [h for h in state_history if h[1] is False]
        reconnects = [h for h in state_history if h[1] is True]
        assert len(disconnects) == 2
        assert len(reconnects) == 2

    @pytest.mark.asyncio
    async def test_state_transition_degraded_to_healthy(self) -> None:
        """Test transition from degraded back to healthy state."""
        event_bus = EventBus()
        state_history: list[tuple[str, bool]] = []

        class MockEventBusProvider:
            @property
            def event_bus(self) -> EventBus:
                return event_bus

        state = CentralConnectionState(event_bus_provider=MockEventBusProvider())

        def track_state(event: SystemStatusEvent) -> None:
            if event.connection_state:
                state_history.append((event.connection_state[0], event.connection_state[1]))

        event_bus.subscribe(
            event_type=SystemStatusEvent,
            event_key=None,
            handler=track_state,
        )

        mock_issuer = Mock(spec=AioJsonRpcAioHttpClient)

        # Add and then remove issue
        state.add_issue(issuer=mock_issuer, iid="HmIP-RF")
        await asyncio.sleep(0.02)

        state.remove_issue(issuer=mock_issuer, iid="HmIP-RF")
        await asyncio.sleep(0.02)

        assert state.has_any_issue is False
        assert len(state_history) == 2
        assert state_history[0] == ("HmIP-RF", False)  # disconnected
        assert state_history[1] == ("HmIP-RF", True)  # reconnected

    @pytest.mark.asyncio
    async def test_state_transition_healthy_to_degraded(self) -> None:
        """Test transition from healthy to degraded state."""
        event_bus = EventBus()
        state_history: list[tuple[str, bool]] = []

        class MockEventBusProvider:
            @property
            def event_bus(self) -> EventBus:
                return event_bus

        state = CentralConnectionState(event_bus_provider=MockEventBusProvider())

        def track_state(event: SystemStatusEvent) -> None:
            if event.connection_state:
                state_history.append((event.connection_state[0], event.connection_state[1]))

        event_bus.subscribe(
            event_type=SystemStatusEvent,
            event_key=None,
            handler=track_state,
        )

        mock_issuer = Mock(spec=AioJsonRpcAioHttpClient)

        # Healthy -> First issue
        assert state.has_any_issue is False
        state.add_issue(issuer=mock_issuer, iid="HmIP-RF")
        await asyncio.sleep(0.02)
        assert state.has_any_issue is True

        assert len(state_history) == 1
        assert state_history[0] == ("HmIP-RF", False)


class TestEventSubscriptionPersistence:
    """Test that event subscriptions survive reconnection scenarios."""

    @pytest.mark.asyncio
    async def test_event_subscription_persists_through_state_changes(self) -> None:
        """Test that subscriptions remain active after connection state changes."""
        event_bus = EventBus()
        connection_events: list[SystemStatusEvent] = []
        data_events: list[DataPointUpdatedEvent] = []

        def on_connection_change(event: SystemStatusEvent) -> None:
            connection_events.append(event)

        def on_data_update(event: DataPointUpdatedEvent) -> None:
            data_events.append(event)

        dpk = DataPointKey(
            interface_id="HmIP-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )

        # Subscribe to both event types
        unsub_connection = event_bus.subscribe(
            event_type=SystemStatusEvent,
            event_key=None,
            handler=on_connection_change,
        )
        unsub_data = event_bus.subscribe(
            event_type=DataPointUpdatedEvent,
            event_key=dpk,
            handler=on_data_update,
        )

        # Verify subscriptions are active
        assert event_bus.get_subscription_count(event_type=SystemStatusEvent) == 1
        assert event_bus.get_subscription_count(event_type=DataPointUpdatedEvent) == 1

        # Simulate connection state change
        connection_event = SystemStatusEvent(
            timestamp=datetime.now(),
            connection_state=("HmIP-RF", False),
        )
        await event_bus.publish(event=connection_event)

        # Simulate data event (would happen after reconnection)
        data_event = DataPointUpdatedEvent(
            timestamp=datetime.now(),
            dpk=dpk,
            value=True,
            received_at=datetime.now(),
        )
        await event_bus.publish(event=data_event)

        # Both handlers should have received their events
        assert len(connection_events) >= 1  # May receive multiple SystemStatusEvents
        assert len(data_events) == 1

        # Subscriptions should still be active
        assert event_bus.get_subscription_count(event_type=SystemStatusEvent) == 1
        assert event_bus.get_subscription_count(event_type=DataPointUpdatedEvent) == 1

        # Cleanup
        unsub_connection()
        unsub_data()

    @pytest.mark.asyncio
    async def test_multiple_reconnection_cycles_preserve_subscriptions(self) -> None:
        """Test subscriptions survive multiple disconnect/reconnect cycles."""
        event_bus = EventBus()
        events_received: list[SystemStatusEvent] = []

        def on_event(event: SystemStatusEvent) -> None:
            events_received.append(event)

        event_bus.subscribe(
            event_type=SystemStatusEvent,
            event_key=None,
            handler=on_event,
        )

        # Simulate 5 disconnect/reconnect cycles
        for _ in range(5):
            # Disconnect
            await event_bus.publish(
                event=SystemStatusEvent(
                    timestamp=datetime.now(),
                    connection_state=("HmIP-RF", False),
                )
            )
            # Reconnect
            await event_bus.publish(
                event=SystemStatusEvent(
                    timestamp=datetime.now(),
                    connection_state=("HmIP-RF", True),
                )
            )

        # All events should have been received
        assert len(events_received) == 10
        # Verify alternating pattern
        for i, event in enumerate(events_received):
            expected_connected = i % 2 == 1  # odd indices are reconnects
            assert event.connection_state is not None
            assert event.connection_state[1] == expected_connected


class TestReconnectionWithCentral:
    """Test reconnection scenarios with actual Central fixtures."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_central_connection_state_accessible(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test that central exposes connection state."""
        central, _, _ = central_client_factory_with_homegear_client

        # Central should have connection state
        assert hasattr(central, "connection_state")
        connection_state = central.connection_state

        # Initially should have no issues (connected)
        assert connection_state.has_any_issue is False

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_central_devices_accessible_after_init(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test that devices are accessible after central initialization."""
        central, _, _ = central_client_factory_with_homegear_client

        devices = list(central.device_registry.devices)
        assert len(devices) > 0

        # Verify device properties are populated
        for device in devices:
            assert device.address is not None
            assert device.model is not None

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_event_bus_accessible_from_central(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test that event bus is accessible from central."""
        central, _, _ = central_client_factory_with_homegear_client

        assert hasattr(central, "event_bus")
        event_bus = central.event_bus
        assert event_bus is not None

        # Test subscription works
        events: list[Any] = []

        def handler(event: SystemStatusEvent) -> None:
            events.append(event)

        unsub = event_bus.subscribe(
            event_type=SystemStatusEvent,
            event_key=None,
            handler=handler,
        )

        assert event_bus.get_subscription_count(event_type=SystemStatusEvent) >= 1

        unsub()


class TestExceptionHandlingDuringReconnection:
    """Test exception handling in connection state management."""

    @pytest.mark.asyncio
    async def test_handle_exception_log_adds_issue(self) -> None:
        """Test that handle_exception_log properly adds issues."""
        state = CentralConnectionState()
        mock_issuer = Mock(spec=AioJsonRpcAioHttpClient)

        # Initially no issues
        assert state.has_any_issue is False

        # Handle an exception
        state.handle_exception_log(
            issuer=mock_issuer,
            iid="HmIP-RF",
            exception=TimeoutError("Connection timed out"),
        )

        # Issue should be added
        assert state.has_any_issue is True
        assert state.has_issue(issuer=mock_issuer, iid="HmIP-RF") is True

    @pytest.mark.asyncio
    async def test_handle_exception_log_multiple_logs_disabled(self) -> None:
        """Test that duplicate exceptions don't spam logs when multiple_logs=False."""
        state = CentralConnectionState()
        mock_issuer = Mock(spec=AioJsonRpcAioHttpClient)

        # First exception
        state.handle_exception_log(
            issuer=mock_issuer,
            iid="HmIP-RF",
            exception=TimeoutError("Connection timed out"),
            multiple_logs=False,
        )

        # Second exception for same interface - should be handled differently
        state.handle_exception_log(
            issuer=mock_issuer,
            iid="HmIP-RF",
            exception=TimeoutError("Connection timed out again"),
            multiple_logs=False,
        )

        # Still only one issue tracked
        assert state.issue_count == 1

    @pytest.mark.asyncio
    async def test_recovery_clears_issues_from_exceptions(self) -> None:
        """Test that issues from exceptions can be cleared on recovery."""
        state = CentralConnectionState()
        mock_issuer = Mock(spec=AioJsonRpcAioHttpClient)

        # Add issue via exception handling
        state.handle_exception_log(
            issuer=mock_issuer,
            iid="HmIP-RF",
            exception=ConnectionError("Backend unavailable"),
        )
        assert state.has_any_issue is True

        # Simulate recovery
        state.remove_issue(issuer=mock_issuer, iid="HmIP-RF")
        assert state.has_any_issue is False


class TestConcurrentConnectionStateOperations:
    """Test thread-safety of connection state operations."""

    @pytest.mark.asyncio
    async def test_concurrent_add_remove_operations(self) -> None:
        """Test concurrent add/remove operations don't corrupt state."""
        state = CentralConnectionState()
        mock_json_issuer = Mock(spec=AioJsonRpcAioHttpClient)
        mock_rpc_issuer = Mock(spec=BaseRpcProxy)

        async def add_remove_json() -> None:
            for i in range(20):
                state.add_issue(issuer=mock_json_issuer, iid=f"JSON-{i}")
                await asyncio.sleep(0.001)
                state.remove_issue(issuer=mock_json_issuer, iid=f"JSON-{i}")

        async def add_remove_rpc() -> None:
            for i in range(20):
                state.add_issue(issuer=mock_rpc_issuer, iid=f"RPC-{i}")
                await asyncio.sleep(0.001)
                state.remove_issue(issuer=mock_rpc_issuer, iid=f"RPC-{i}")

        # Run concurrently
        await asyncio.gather(add_remove_json(), add_remove_rpc())

        # State should be clean after all operations
        assert state.issue_count == 0
        assert state.has_any_issue is False

    @pytest.mark.asyncio
    async def test_concurrent_clear_operations(self) -> None:
        """Test concurrent clear operations are safe."""
        state = CentralConnectionState()
        mock_issuer = Mock(spec=AioJsonRpcAioHttpClient)

        # Add some issues
        for i in range(10):
            state.add_issue(issuer=mock_issuer, iid=f"Interface-{i}")

        async def clear_task() -> int:
            return state.clear_all_issues()

        # Multiple concurrent clears
        results = await asyncio.gather(
            clear_task(),
            clear_task(),
            clear_task(),
        )

        # Only one should have cleared issues, others should return 0
        assert sum(results) == 10
        assert state.issue_count == 0
