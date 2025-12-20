"""Tests for aiohomematic.central.event_coordinator."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from aiohomematic.central.event_coordinator import EventCoordinator
from aiohomematic.const import DataPointKey, DeviceTriggerEventType, EventData, Parameter, ParamsetKey, SystemEventType
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


class _FakeHealthTracker:
    """Minimal fake HealthTracker for testing."""

    def record_event_received(self, *, interface_id: str) -> None:
        """Record that an event was received."""

    def record_failed_request(self, *, interface_id: str) -> None:
        """Record a failed request."""

    def record_successful_request(self, *, interface_id: str) -> None:
        """Record a successful request."""


class _FakeEventBus:
    """Minimal fake EventBus for testing."""

    def __init__(self) -> None:
        """Initialize a fake event bus."""
        self._subscriptions: dict[str, list[Any]] = {}

    def clear_subscriptions(self, *, event_type: type | None = None) -> None:
        """Clear subscriptions."""

    async def publish(self, event: Any) -> None:
        """Publish an event."""

    def subscribe(self, *, event_type: type, handler: Any, event_key: Any = None) -> Any:
        """Subscribe to an event type."""
        return lambda: None


class _FakeCentral:
    """Minimal fake CentralUnit for testing."""

    def __init__(self, *, name: str = "test_central") -> None:
        """Initialize a fake central."""
        self.name = name
        self.looper = _FakeLooper()
        self._clients: dict[str, _FakeClient] = {}
        self.event_bus = _FakeEventBus()
        self.health_tracker = _FakeHealthTracker()

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
        coordinator = EventCoordinator(
            client_provider=central,
            event_bus=central.event_bus,
            health_tracker=central.health_tracker,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        event_bus = coordinator.event_bus
        assert event_bus is not None
        assert event_bus == coordinator._event_bus

    def test_event_coordinator_initialization(self) -> None:
        """EventCoordinator should initialize with central instance."""
        central = _FakeCentral()
        coordinator = EventCoordinator(
            client_provider=central,
            event_bus=central.event_bus,
            health_tracker=central.health_tracker,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        assert coordinator._client_provider == central
        assert coordinator._event_bus is not None
        assert len(coordinator._last_event_seen_for_interface) == 0


class TestEventCoordinatorDataPointSubscription:
    """Test data point subscription (only method kept for backward compatibility)."""

    def test_add_data_point_subscription(self) -> None:
        """Add data point subscription should register with EventBus."""
        central = _FakeCentral()
        coordinator = EventCoordinator(
            client_provider=central,
            event_bus=central.event_bus,
            health_tracker=central.health_tracker,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

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
        coordinator = EventCoordinator(
            client_provider=central,
            event_bus=central.event_bus,
            health_tracker=central.health_tracker,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        await coordinator.data_point_event(
            interface_id="NonExistent",
            channel_address="VCU0000001:1",
            parameter="STATE",
            value=True,
        )

        # Method returns early when client doesn't exist:
        # - last_event_seen_for_interface should not be set
        assert len(coordinator._last_event_seen_for_interface) == 0

        # Note: The @callback_event decorator on data_point_event creates a task
        # after the method returns (for re-publishing to external callbacks).
        # This is separate from the early return behavior we're testing.
        # Filter out decorator wrapper tasks to verify no other tasks were created
        non_decorator_tasks = [t for t in central.looper.tasks if t["name"] != "wrapper_event_callback"]
        assert len(non_decorator_tasks) == 0

    @pytest.mark.asyncio
    async def test_data_point_event_pong_response(self) -> None:
        """Data point event should handle PONG responses."""
        central = _FakeCentral()
        client = _FakeClient(supports_ping_pong=True)
        central._clients["BidCos-RF"] = client

        coordinator = EventCoordinator(
            client_provider=central,
            event_bus=central.event_bus,
            health_tracker=central.health_tracker,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

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

        coordinator = EventCoordinator(
            client_provider=central,
            event_bus=central.event_bus,
            health_tracker=central.health_tracker,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

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
    """Test publish callback methods."""

    def test_publish_backend_parameter_handler(self) -> None:
        """Publish backend parameter callback should publish to EventBus."""
        central = _FakeCentral()
        coordinator = EventCoordinator(
            client_provider=central,
            event_bus=central.event_bus,
            health_tracker=central.health_tracker,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        coordinator.publish_backend_parameter_event(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            parameter="STATE",
            value=True,
        )

        # Should have created a task to publish to EventBus
        assert len(central.looper.tasks) == 1
        assert "event-bus-backend-param" in central.looper.tasks[0]["name"]

    def test_publish_backend_system_handler(self) -> None:
        """Publish backend system callback should publish to EventBus."""
        central = _FakeCentral()
        coordinator = EventCoordinator(
            client_provider=central,
            event_bus=central.event_bus,
            health_tracker=central.health_tracker,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        coordinator.publish_system_event(
            system_event=SystemEventType.DEVICES_CREATED,
            interface_id="BidCos-RF",
        )

        # Should have created a task to publish to EventBus
        assert len(central.looper.tasks) == 1
        # Task name now reflects the specific event type
        assert "event-bus-devices-created" in central.looper.tasks[0]["name"]

    def test_publish_homematic_handler(self) -> None:
        """Publish Homematic callback should publish to EventBus."""
        central = _FakeCentral()
        coordinator = EventCoordinator(
            client_provider=central,
            event_bus=central.event_bus,
            health_tracker=central.health_tracker,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        coordinator.publish_device_trigger_event(
            trigger_type=DeviceTriggerEventType.KEYPRESS,
            event_data=EventData(
                interface_id="BidCos-RF",
                model="HM-Test",
                address="VCU0000001",
                channel_no=None,
                parameter="PRESS_SHORT",
            ),
        )

        # Should have created a task to publish to EventBus
        assert len(central.looper.tasks) == 1
        # Task name now includes address and parameter
        assert "event-bus-device-trigger-VCU0000001-PRESS_SHORT" in central.looper.tasks[0]["name"]


class TestEventCoordinatorLastEventSeen:
    """Test last event seen tracking."""

    def test_get_last_event_seen_for_interface_none(self) -> None:
        """Get last event seen should return None when no event has been seen."""
        central = _FakeCentral()
        coordinator = EventCoordinator(
            client_provider=central,
            event_bus=central.event_bus,
            health_tracker=central.health_tracker,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        last_event = coordinator.get_last_event_seen_for_interface(interface_id="BidCos-RF")
        assert last_event is None

    def test_set_last_event_seen_for_interface(self) -> None:
        """Set last event seen should update the timestamp."""
        central = _FakeCentral()
        coordinator = EventCoordinator(
            client_provider=central,
            event_bus=central.event_bus,
            health_tracker=central.health_tracker,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        coordinator.set_last_event_seen_for_interface(interface_id="BidCos-RF")

        last_event = coordinator.get_last_event_seen_for_interface(interface_id="BidCos-RF")
        assert last_event is not None
        assert isinstance(last_event, datetime)
