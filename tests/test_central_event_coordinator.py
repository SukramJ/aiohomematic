"""Tests for aiohomematic.central.event_coordinator."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from aiohomematic.central.event_coordinator import EventCoordinator
from aiohomematic.const import (
    BackendSystemEvent,
    DataPointKey,
    EventKey,
    EventType,
    InterfaceEventType,
    Parameter,
    ParamsetKey,
)
from aiohomematic.model.generic import GenericDataPoint


class _FakeDataPoint(GenericDataPoint):  # type: ignore[type-arg]
    """Minimal fake DataPoint for testing."""

    __slots__ = ("_dpk", "_is_readable", "_supports_events", "state_path", "channel", "event_calls")

    def __init__(
        self,
        *,
        dpk: DataPointKey,
        is_readable: bool = True,
        supports_events: bool = True,
    ) -> None:
        """Initialize a fake data point."""
        # Don't call super().__init__ to avoid complex initialization
        self._dpk = dpk
        self._is_readable = is_readable
        self._supports_events = supports_events
        self.state_path = f"{dpk.interface_id}/{dpk.channel_address}/{dpk.parameter}"
        self.channel = MagicMock()
        self.channel.device = MagicMock()
        self.channel.device.client = MagicMock()
        self.channel.device.client.supports_rpc_callback = False
        self.event_calls: list[dict[str, Any]] = []

    @property  # type: ignore[override]
    def dpk(self) -> DataPointKey:
        """Return the data point key."""
        return self._dpk

    @property  # type: ignore[override]
    def is_readable(self) -> bool:
        """Return if data point is readable."""
        return self._is_readable

    @property  # type: ignore[override]
    def supports_events(self) -> bool:
        """Return if data point supports events."""
        return self._supports_events

    async def event(self, *, value: Any, received_at: datetime) -> None:
        """Record event calls."""
        self.event_calls.append({"value": value, "received_at": received_at})


class _FakeEventBus:
    """Minimal fake EventBus for testing."""

    def __init__(self, *, enable_event_logging: bool = False) -> None:
        """Initialize a fake event bus."""
        self.enable_event_logging = enable_event_logging
        self.published_events: list[Any] = []

    async def publish(self, *, event: Any) -> None:
        """Record published events."""
        self.published_events.append(event)


class _FakeLooper:
    """Minimal fake Looper for testing."""

    def __init__(self) -> None:
        """Initialize a fake looper."""
        self.tasks: list[dict[str, Any]] = []

    def create_task(self, *, target: Any, name: str) -> None:
        """Record task creation."""
        self.tasks.append({"target": target, "name": name})


class _FakeClient:
    """Minimal fake Client for testing."""

    def __init__(self, *, supports_ping_pong: bool = True) -> None:
        """Initialize a fake client."""
        self.supports_ping_pong = supports_ping_pong
        self.ping_pong_cache = MagicMock()
        self.ping_pong_cache.handle_received_pong = MagicMock()


class _FakeCentral:
    """Minimal fake CentralUnit for testing."""

    def __init__(self, *, name: str = "test_central") -> None:
        """Initialize a fake central."""
        self.name = name
        self.looper = _FakeLooper()
        self._clients: dict[str, _FakeClient] = {}

    def get_client(self, *, interface_id: str) -> _FakeClient | None:
        """Get client by interface ID."""
        return self._clients.get(interface_id)

    def has_client(self, *, interface_id: str) -> bool:
        """Check if client exists."""
        return interface_id in self._clients


class TestEventCoordinatorBasics:
    """Test basic EventCoordinator functionality."""

    def test_event_bus_property(self) -> None:
        """Event bus property should return the event bus instance."""
        central = _FakeCentral()
        coordinator = EventCoordinator(central=central)  # type: ignore[arg-type]

        event_bus = coordinator.event_bus
        assert event_bus is not None
        assert event_bus == coordinator._event_bus

    def test_event_coordinator_initialization(self) -> None:
        """EventCoordinator should initialize with central instance."""
        central = _FakeCentral()
        coordinator = EventCoordinator(central=central)  # type: ignore[arg-type]

        assert coordinator._central == central
        assert coordinator._event_bus is not None
        assert len(coordinator._data_point_key_event_subscriptions) == 0
        assert len(coordinator._data_point_path_event_subscriptions) == 0
        assert len(coordinator._sysvar_data_point_event_subscriptions) == 0
        assert len(coordinator._last_event_seen_for_interface) == 0


class TestEventCoordinatorDataPointSubscriptions:
    """Test data point subscription management."""

    def test_add_data_point_subscription(self) -> None:
        """Add data point subscription should register the data point for events."""
        central = _FakeCentral()
        coordinator = EventCoordinator(central=central)  # type: ignore[arg-type]

        dpk = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )
        data_point = _FakeDataPoint(dpk=dpk)

        coordinator.add_data_point_subscription(data_point=data_point)  # type: ignore[arg-type]

        # Should be registered
        assert dpk in coordinator._data_point_key_event_subscriptions
        assert data_point.state_path in coordinator._data_point_path_event_subscriptions

    def test_add_data_point_subscription_not_readable(self) -> None:
        """Add data point subscription should skip non-readable data points."""
        central = _FakeCentral()
        coordinator = EventCoordinator(central=central)  # type: ignore[arg-type]

        dpk = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )
        data_point = _FakeDataPoint(dpk=dpk, is_readable=False, supports_events=False)

        coordinator.add_data_point_subscription(data_point=data_point)  # type: ignore[arg-type]

        # Should not be registered
        assert dpk not in coordinator._data_point_key_event_subscriptions

    def test_get_data_point_path(self) -> None:
        """Get data point path should return registered state paths."""
        central = _FakeCentral()
        coordinator = EventCoordinator(central=central)  # type: ignore[arg-type]

        dpk1 = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )
        dpk2 = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000002:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )

        data_point1 = _FakeDataPoint(dpk=dpk1)
        data_point2 = _FakeDataPoint(dpk=dpk2)

        coordinator.add_data_point_subscription(data_point=data_point1)  # type: ignore[arg-type]
        coordinator.add_data_point_subscription(data_point=data_point2)  # type: ignore[arg-type]

        paths = coordinator.get_data_point_path()
        assert isinstance(paths, tuple)
        assert data_point1.state_path in paths
        assert data_point2.state_path in paths

    def test_remove_data_point_subscription(self) -> None:
        """Remove data point subscription should unregister the data point."""
        central = _FakeCentral()
        coordinator = EventCoordinator(central=central)  # type: ignore[arg-type]

        dpk = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )
        data_point = _FakeDataPoint(dpk=dpk)

        # Add subscription
        coordinator.add_data_point_subscription(data_point=data_point)  # type: ignore[arg-type]
        assert dpk in coordinator._data_point_key_event_subscriptions

        # Remove subscription
        coordinator.remove_data_point_subscription(data_point=data_point)  # type: ignore[arg-type]
        assert dpk not in coordinator._data_point_key_event_subscriptions


class TestEventCoordinatorSysvarSubscriptions:
    """Test system variable subscription management."""

    def test_add_sysvar_subscription(self) -> None:
        """Add sysvar subscription should register the callback."""
        central = _FakeCentral()
        coordinator = EventCoordinator(central=central)  # type: ignore[arg-type]

        state_path = "sv_12345"
        callback = AsyncMock()

        coordinator.add_sysvar_subscription(state_path=state_path, callback=callback)

        # Should be registered
        assert state_path in coordinator._sysvar_data_point_event_subscriptions
        assert coordinator._sysvar_data_point_event_subscriptions[state_path] == callback

    def test_get_sysvar_data_point_path(self) -> None:
        """Get sysvar data point path should return registered state paths."""
        central = _FakeCentral()
        coordinator = EventCoordinator(central=central)  # type: ignore[arg-type]

        state_path1 = "sv_12345"
        state_path2 = "sv_67890"
        callback1 = AsyncMock()
        callback2 = AsyncMock()

        coordinator.add_sysvar_subscription(state_path=state_path1, callback=callback1)
        coordinator.add_sysvar_subscription(state_path=state_path2, callback=callback2)

        paths = coordinator.get_sysvar_data_point_path()
        assert isinstance(paths, tuple)
        assert state_path1 in paths
        assert state_path2 in paths

    def test_remove_sysvar_subscription(self) -> None:
        """Remove sysvar subscription should unregister the callback."""
        central = _FakeCentral()
        coordinator = EventCoordinator(central=central)  # type: ignore[arg-type]

        state_path = "sv_12345"
        callback = AsyncMock()

        # Add subscription
        coordinator.add_sysvar_subscription(state_path=state_path, callback=callback)
        assert state_path in coordinator._sysvar_data_point_event_subscriptions

        # Remove subscription
        coordinator.remove_sysvar_subscription(state_path=state_path)
        assert state_path not in coordinator._sysvar_data_point_event_subscriptions


class TestEventCoordinatorDataPointEvent:
    """Test data point event handling."""

    @pytest.mark.asyncio
    async def test_data_point_event_no_client(self) -> None:
        """Data point event should return early when client doesn't exist."""
        central = _FakeCentral()
        coordinator = EventCoordinator(central=central)  # type: ignore[arg-type]

        await coordinator.data_point_event(
            interface_id="NonExistent",
            channel_address="VCU0000001:1",
            parameter="STATE",
            value=True,
        )

        # Should not have published any events
        assert len(central.looper.tasks) == 0

    @pytest.mark.asyncio
    async def test_data_point_event_pong_response(self) -> None:
        """Data point event should handle PONG responses."""
        central = _FakeCentral()
        client = _FakeClient(supports_ping_pong=True)
        central._clients["BidCos-RF"] = client

        coordinator = EventCoordinator(central=central)  # type: ignore[arg-type]

        await coordinator.data_point_event(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:0",
            parameter=Parameter.PONG,
            value="BidCos-RF#test-token",
        )

        # Should have handled the pong
        client.ping_pong_cache.handle_received_pong.assert_called_once_with(pong_token="test-token")

    @pytest.mark.asyncio
    async def test_data_point_event_publishes_to_event_bus(self) -> None:
        """Data point event should publish to event bus."""
        central = _FakeCentral()
        central._clients["BidCos-RF"] = _FakeClient()

        coordinator = EventCoordinator(central=central)  # type: ignore[arg-type]

        await coordinator.data_point_event(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            parameter="STATE",
            value=True,
        )

        # Should have created a task to publish event
        assert len(central.looper.tasks) == 1
        assert "event-bus-datapoint" in central.looper.tasks[0]["name"]

    @pytest.mark.asyncio
    async def test_data_point_event_with_subscription(self) -> None:
        """Data point event should call subscribed callbacks."""
        central = _FakeCentral()
        central._clients["BidCos-RF"] = _FakeClient()

        coordinator = EventCoordinator(central=central)  # type: ignore[arg-type]

        dpk = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )
        data_point = _FakeDataPoint(dpk=dpk)

        # Add subscription
        coordinator.add_data_point_subscription(data_point=data_point)  # type: ignore[arg-type]

        # Trigger event
        await coordinator.data_point_event(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            parameter="STATE",
            value=True,
        )

        # Should have called the callback
        assert len(data_point.event_calls) == 1
        assert data_point.event_calls[0]["value"] is True


class TestEventCoordinatorEmitMethods:
    """Test event emission methods."""

    def test_emit_backend_parameter_callback(self) -> None:
        """Emit backend parameter callback should publish to event bus."""
        central = _FakeCentral()
        coordinator = EventCoordinator(central=central)  # type: ignore[arg-type]

        coordinator.emit_backend_parameter_callback(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            parameter="STATE",
            value=True,
        )

        # Should have created a task to publish event
        assert len(central.looper.tasks) == 1
        assert "event-bus-backend-param" in central.looper.tasks[0]["name"]

    def test_emit_backend_system_callback(self) -> None:
        """Emit backend system callback should publish to event bus."""
        central = _FakeCentral()
        coordinator = EventCoordinator(central=central)  # type: ignore[arg-type]

        coordinator.emit_backend_system_callback(
            system_event=BackendSystemEvent.DEVICES_CREATED,
            device_count=5,
        )

        # Should have created a task to publish event
        assert len(central.looper.tasks) == 1
        assert "event-bus-backend-system" in central.looper.tasks[0]["name"]

    def test_emit_homematic_callback(self) -> None:
        """Emit Homematic callback should publish to event bus."""
        central = _FakeCentral()
        coordinator = EventCoordinator(central=central)  # type: ignore[arg-type]

        coordinator.emit_homematic_callback(
            event_type=EventType.KEYPRESS,
            event_data={EventKey.ADDRESS: "VCU0000001:1"},
        )

        # Should have created a task to publish event
        assert len(central.looper.tasks) == 1
        assert "event-bus-homematic" in central.looper.tasks[0]["name"]

    def test_emit_interface_event(self) -> None:
        """Emit interface event should create and emit interface event."""
        central = _FakeCentral()
        coordinator = EventCoordinator(central=central)  # type: ignore[arg-type]

        coordinator.emit_interface_event(
            interface_id="BidCos-RF",
            interface_event_type=InterfaceEventType.CALLBACK,
            data={EventKey.AVAILABLE: True},
        )

        # Should have created a task to publish event
        assert len(central.looper.tasks) == 1


class TestEventCoordinatorLastEventSeen:
    """Test last event seen tracking."""

    def test_get_last_event_seen_for_interface_none(self) -> None:
        """Get last event seen should return None when no event seen."""
        central = _FakeCentral()
        coordinator = EventCoordinator(central=central)  # type: ignore[arg-type]

        last_seen = coordinator.get_last_event_seen_for_interface(interface_id="NonExistent")
        assert last_seen is None

    def test_set_last_event_seen_for_interface(self) -> None:
        """Set last event seen should track timestamp."""
        central = _FakeCentral()
        coordinator = EventCoordinator(central=central)  # type: ignore[arg-type]

        before = datetime.now()
        coordinator.set_last_event_seen_for_interface(interface_id="BidCos-RF")
        after = datetime.now()

        last_seen = coordinator.get_last_event_seen_for_interface(interface_id="BidCos-RF")
        assert last_seen is not None
        assert before <= last_seen <= after


class TestEventCoordinatorPathEvents:
    """Test path-based event handling."""

    def test_data_point_path_event(self) -> None:
        """Data point path event should route to data_point_event."""
        central = _FakeCentral()
        central._clients["BidCos-RF"] = _FakeClient()

        coordinator = EventCoordinator(central=central)  # type: ignore[arg-type]

        dpk = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )
        data_point = _FakeDataPoint(dpk=dpk)

        # Add subscription
        coordinator.add_data_point_subscription(data_point=data_point)  # type: ignore[arg-type]

        # Trigger path event
        coordinator.data_point_path_event(
            state_path=data_point.state_path,
            value="true",
        )

        # Should have created a task to handle the event
        assert len(central.looper.tasks) == 1
        assert "device-data-point-event" in central.looper.tasks[0]["name"]

    def test_sysvar_data_point_path_event(self) -> None:
        """Sysvar data point path event should call callback and publish to event bus."""
        central = _FakeCentral()
        coordinator = EventCoordinator(central=central)  # type: ignore[arg-type]

        state_path = "sv_12345"
        callback = AsyncMock()

        # Add subscription
        coordinator.add_sysvar_subscription(state_path=state_path, callback=callback)

        # Trigger event
        coordinator.sysvar_data_point_path_event(state_path=state_path, value="42")

        # Should have created tasks for event bus and callback
        assert len(central.looper.tasks) >= 1
        assert any("event-bus-sysvar" in task["name"] for task in central.looper.tasks)


class TestEventCoordinatorIntegration:
    """Integration tests for EventCoordinator."""

    @pytest.mark.asyncio
    async def test_full_event_flow(self) -> None:
        """Test full event flow from data point event to callback."""
        central = _FakeCentral()
        central._clients["BidCos-RF"] = _FakeClient()

        coordinator = EventCoordinator(central=central)  # type: ignore[arg-type]

        dpk = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )
        data_point = _FakeDataPoint(dpk=dpk)

        # Subscribe
        coordinator.add_data_point_subscription(data_point=data_point)  # type: ignore[arg-type]

        # Trigger event
        await coordinator.data_point_event(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            parameter="STATE",
            value=True,
        )

        # Verify callback was called
        assert len(data_point.event_calls) == 1
        assert data_point.event_calls[0]["value"] is True

        # Verify event bus was notified
        assert len(central.looper.tasks) == 1

        # Verify last event seen was updated
        last_seen = coordinator.get_last_event_seen_for_interface(interface_id="BidCos-RF")
        assert last_seen is not None

    @pytest.mark.asyncio
    async def test_multiple_subscriptions_same_data_point(self) -> None:
        """Test multiple subscriptions to the same data point."""
        central = _FakeCentral()
        central._clients["BidCos-RF"] = _FakeClient()

        coordinator = EventCoordinator(central=central)  # type: ignore[arg-type]

        dpk = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )
        data_point1 = _FakeDataPoint(dpk=dpk)
        data_point2 = _FakeDataPoint(dpk=dpk)

        # Subscribe both
        coordinator.add_data_point_subscription(data_point=data_point1)  # type: ignore[arg-type]
        coordinator.add_data_point_subscription(data_point=data_point2)  # type: ignore[arg-type]

        # Trigger event
        await coordinator.data_point_event(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            parameter="STATE",
            value=True,
        )

        # Both callbacks should have been called
        assert len(data_point1.event_calls) == 1
        assert len(data_point2.event_calls) == 1
