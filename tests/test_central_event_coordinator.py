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
        assert len(coordinator._last_event_seen_for_interface) == 0


class TestEventCoordinatorDataPointSubscription:
    """Test data point subscription (only method kept for backward compatibility)."""

    def test_add_data_point_subscription(self) -> None:
        """Add data point subscription should register with EventBus."""
        central = _FakeCentral()
        coordinator = EventCoordinator(central=central)  # type: ignore[arg-type]

        dpk = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )
        data_point = _FakeDataPoint(dpk=dpk)

        # Should register with EventBus via compatibility wrapper
        coordinator.add_data_point_subscription(data_point=data_point)  # type: ignore[arg-type]


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

        # Should not create any tasks when client doesn't exist
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
            channel_address="BidCos-RF:0",
            parameter=Parameter.PONG,
            value="BidCos-RF#test_token",
        )

        # Should have handled pong
        client.ping_pong_cache.handle_received_pong.assert_called_once_with(pong_token="test_token")

    @pytest.mark.asyncio
    async def test_data_point_event_publishes_to_event_bus(self) -> None:
        """Data point event should publish events to EventBus."""

        central = _FakeCentral()
        central._clients["BidCos-RF"] = _FakeClient()

        coordinator = EventCoordinator(central=central)  # type: ignore[arg-type]

        # Mock EventBus publish to verify it's called
        coordinator._event_bus.publish = AsyncMock()

        await coordinator.data_point_event(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            parameter="STATE",
            value=True,
        )

        # Should have called EventBus publish
        coordinator._event_bus.publish.assert_called_once()


class TestEventCoordinatorEmitMethods:
    """Test emit callback methods."""

    def test_emit_backend_parameter_callback(self) -> None:
        """Emit backend parameter callback should publish to EventBus."""
        central = _FakeCentral()
        coordinator = EventCoordinator(central=central)  # type: ignore[arg-type]

        coordinator.emit_backend_parameter_callback(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            parameter="STATE",
            value=True,
        )

        # Should have created a task to publish to EventBus
        assert len(central.looper.tasks) == 1
        assert "event-bus-backend-param" in central.looper.tasks[0]["name"]

    def test_emit_backend_system_callback(self) -> None:
        """Emit backend system callback should publish to EventBus."""
        central = _FakeCentral()
        coordinator = EventCoordinator(central=central)  # type: ignore[arg-type]

        coordinator.emit_backend_system_callback(
            system_event=BackendSystemEvent.DEVICES_CREATED,
            interface_id="BidCos-RF",
        )

        # Should have created a task to publish to EventBus
        assert len(central.looper.tasks) == 1
        assert "event-bus-backend-system" in central.looper.tasks[0]["name"]

    def test_emit_homematic_callback(self) -> None:
        """Emit Homematic callback should publish to EventBus."""
        central = _FakeCentral()
        coordinator = EventCoordinator(central=central)  # type: ignore[arg-type]

        coordinator.emit_homematic_callback(
            event_type=EventType.KEYPRESS,
            event_data={EventKey.INTERFACE_ID: "BidCos-RF", EventKey.ADDRESS: "VCU0000001:1"},
        )

        # Should have created a task to publish to EventBus
        assert len(central.looper.tasks) == 1
        assert "event-bus-homematic" in central.looper.tasks[0]["name"]

    def test_emit_interface_event(self) -> None:
        """Emit interface event should publish to EventBus."""
        central = _FakeCentral()
        coordinator = EventCoordinator(central=central)  # type: ignore[arg-type]

        coordinator.emit_interface_event(
            interface_id="BidCos-RF",
            interface_event_type=InterfaceEventType.CALLBACK,
            data={EventKey.AVAILABLE: True},
        )

        # Should have created a task to publish to EventBus
        assert len(central.looper.tasks) == 1
        assert "event-bus-homematic" in central.looper.tasks[0]["name"]


class TestEventCoordinatorLastEventSeen:
    """Test last event seen tracking."""

    def test_get_last_event_seen_for_interface_none(self) -> None:
        """Get last event seen should return None when no event has been seen."""
        central = _FakeCentral()
        coordinator = EventCoordinator(central=central)  # type: ignore[arg-type]

        last_event = coordinator.get_last_event_seen_for_interface(interface_id="BidCos-RF")
        assert last_event is None

    def test_set_last_event_seen_for_interface(self) -> None:
        """Set last event seen should update the timestamp."""
        central = _FakeCentral()
        coordinator = EventCoordinator(central=central)  # type: ignore[arg-type]

        coordinator.set_last_event_seen_for_interface(interface_id="BidCos-RF")

        last_event = coordinator.get_last_event_seen_for_interface(interface_id="BidCos-RF")
        assert last_event is not None
        assert isinstance(last_event, datetime)
