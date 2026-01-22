# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for aiohomematic.central.event_coordinator."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from aiohomematic.central.coordinators import EventCoordinator
from aiohomematic.const import DataPointKey, DeviceTriggerEventType, EventData, Parameter, ParamsetKey, SystemEventType
from aiohomematic.model.generic import GenericDataPoint


class _FakeDataPoint(GenericDataPoint):  # type: ignore[type-arg]
    """Minimal fake DataPoint for testing."""

    __slots__ = ("_dpk", "_is_readable", "_has_events", "state_path", "channel", "event_calls")

    def __init__(
        self,
        *,
        dpk: DataPointKey,
        is_readable: bool = True,
        has_events: bool = True,
    ) -> None:
        """Initialize a fake data point."""
        # Don't call super().__init__ to avoid complex initialization
        self._dpk = dpk
        self._is_readable = is_readable
        self._has_events = has_events
        self.state_path = f"{dpk.interface_id}/{dpk.channel_address}/{dpk.parameter}"
        self.channel = MagicMock()
        self.channel.device = MagicMock()
        self.channel.device.client = MagicMock()
        self.channel.device.client.capabilities = MagicMock()
        self.channel.device.client.capabilities.rpc_callback = False
        self.event_calls: list[dict[str, Any]] = []

    @property  # type: ignore[override]
    def dpk(self) -> DataPointKey:
        """Return the data point key."""
        return self._dpk

    @property  # type: ignore[override]
    def has_events(self) -> bool:
        """Return if data point supports events."""
        return self._has_events

    @property  # type: ignore[override]
    def is_readable(self) -> bool:
        """Return if data point is readable."""
        return self._is_readable

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

    def __init__(self, *, has_ping_pong: bool = True) -> None:
        """Initialize a fake client."""
        self.capabilities = MagicMock()
        self.capabilities.ping_pong = has_ping_pong
        self.ping_pong_tracker = MagicMock()
        self.ping_pong_tracker.handle_received_pong = MagicMock()


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

    def __init__(self, *, task_scheduler: Any = None) -> None:
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
        # Verify property returns same instance (use public API)
        assert event_bus is coordinator.event_bus

    def test_event_coordinator_initialization(self) -> None:
        """EventCoordinator should initialize correctly."""
        central = _FakeCentral()
        coordinator = EventCoordinator(
            client_provider=central,
            event_bus=central.event_bus,
            health_tracker=central.health_tracker,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        # Verify initialization using public API
        assert coordinator.event_bus is not None
        # No events seen yet for any interface
        assert coordinator.get_last_event_seen_for_interface(interface_id="any") is None


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
        # - last_event_seen_for_interface should not be set (use public API)
        assert coordinator.get_last_event_seen_for_interface(interface_id="NonExistent") is None

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
        client = _FakeClient(has_ping_pong=True)
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
        client.ping_pong_tracker.handle_received_pong.assert_called_once_with(pong_token="test_token")

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

        # Mock EventBus publish to verify it's called (use public property)
        coordinator.event_bus.publish = AsyncMock()

        await coordinator.data_point_event(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            parameter="STATE",
            value=True,
        )

        # Should have called EventBus publish (use public property)
        coordinator.event_bus.publish.assert_called_once()


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
                device_address="VCU0000001",
                channel_no=None,
                parameter="PRESS_SHORT",
            ),
        )

        # Should have created a task to publish to EventBus
        assert len(central.looper.tasks) == 1
        # Task name now includes address and parameter
        assert "event-bus-device-trigger-VCU0000001-None-PRESS_SHORT" in central.looper.tasks[0]["name"]


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

    def test_multiple_interfaces_tracked_independently(self) -> None:
        """Different interfaces should have independent last_event tracking."""
        central = _FakeCentral()
        coordinator = EventCoordinator(
            client_provider=central,
            event_bus=central.event_bus,
            health_tracker=central.health_tracker,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        # Set for first interface
        coordinator.set_last_event_seen_for_interface(interface_id="BidCos-RF")
        first_event = coordinator.get_last_event_seen_for_interface(interface_id="BidCos-RF")

        # Second interface should still be None
        second_event = coordinator.get_last_event_seen_for_interface(interface_id="HmIP-RF")
        assert second_event is None

        # Set for second interface
        coordinator.set_last_event_seen_for_interface(interface_id="HmIP-RF")
        second_event = coordinator.get_last_event_seen_for_interface(interface_id="HmIP-RF")
        assert second_event is not None

        # First interface should be unchanged
        assert coordinator.get_last_event_seen_for_interface(interface_id="BidCos-RF") == first_event

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


class TestEventCoordinatorClear:
    """Test clear method."""

    def test_clear_unsubscribes_event_handlers(self) -> None:
        """Clear should unsubscribe all event handlers."""
        central = _FakeCentral()
        coordinator = EventCoordinator(
            client_provider=central,
            event_bus=central.event_bus,
            health_tracker=central.health_tracker,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        # Add some mock subscriptions
        unsubscribe_called = {"dp": False, "status": False}

        def make_unsubscribe(key: str) -> Any:
            def unsub() -> None:
                unsubscribe_called[key] = True

            return unsub

        coordinator._data_point_unsubscribes.append(make_unsubscribe("dp"))
        coordinator._status_unsubscribes.append(make_unsubscribe("status"))

        # Clear
        coordinator.clear()

        # Unsubscribe callbacks should have been called
        assert unsubscribe_called["dp"] is True
        assert unsubscribe_called["status"] is True

        # Lists should be cleared
        assert len(coordinator._data_point_unsubscribes) == 0
        assert len(coordinator._status_unsubscribes) == 0


class TestEventCoordinatorEventRouting:
    """Test event routing to appropriate handlers."""

    @pytest.mark.asyncio
    async def test_data_point_event_pong_no_ping_pong_support(self) -> None:
        """PONG event should be ignored when client has no ping_pong support."""
        central = _FakeCentral()
        client = _FakeClient(has_ping_pong=False)
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

        # Should NOT have handled pong
        client.ping_pong_tracker.handle_received_pong.assert_not_called()

    @pytest.mark.asyncio
    async def test_data_point_event_updates_last_seen(self) -> None:
        """Data point event should update last event seen timestamp."""
        central = _FakeCentral()
        central._clients["BidCos-RF"] = _FakeClient()

        coordinator = EventCoordinator(
            client_provider=central,
            event_bus=central.event_bus,
            health_tracker=central.health_tracker,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        # Initially no events
        assert coordinator.get_last_event_seen_for_interface(interface_id="BidCos-RF") is None

        await coordinator.data_point_event(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            parameter="STATE",
            value=True,
        )

        # Should have updated last seen
        assert coordinator.get_last_event_seen_for_interface(interface_id="BidCos-RF") is not None

    @pytest.mark.asyncio
    async def test_data_point_event_with_various_value_types(self) -> None:
        """Data point events should handle various value types."""
        central = _FakeCentral()
        central._clients["BidCos-RF"] = _FakeClient()

        coordinator = EventCoordinator(
            client_provider=central,
            event_bus=central.event_bus,
            health_tracker=central.health_tracker,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]
        coordinator.event_bus.publish = AsyncMock()

        test_values = [
            True,  # bool
            False,
            42,  # int
            3.14,  # float
            "hello",  # string
            0,
            1.0,
        ]

        for value in test_values:
            await coordinator.data_point_event(
                interface_id="BidCos-RF",
                channel_address="VCU0000001:1",
                parameter="VALUE",
                value=value,
            )

        # All events should have been published
        assert coordinator.event_bus.publish.call_count == len(test_values)


class TestEventCoordinatorSystemEvents:
    """Test system event publishing."""

    def test_publish_system_event_delete_devices(self) -> None:
        """Publish system event for DELETE_DEVICES."""
        central = _FakeCentral()
        coordinator = EventCoordinator(
            client_provider=central,
            event_bus=central.event_bus,
            health_tracker=central.health_tracker,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        coordinator.publish_system_event(
            system_event=SystemEventType.DELETE_DEVICES,
            interface_id="BidCos-RF",
            addresses=("VCU0000001", "VCU0000002"),
        )

        assert len(central.looper.tasks) == 1
        # Task name includes "devices-removed" or similar
        assert "devices" in central.looper.tasks[0]["name"].lower()

    def test_publish_system_event_devices_created(self) -> None:
        """Publish system event for DEVICES_CREATED."""
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
            device_descriptions=(),
        )

        assert len(central.looper.tasks) == 1
        assert "devices-created" in central.looper.tasks[0]["name"]

    def test_publish_system_event_hub_refreshed(self) -> None:
        """Publish system event for HUB_REFRESHED."""
        from aiohomematic.const import DataPointCategory

        central = _FakeCentral()
        coordinator = EventCoordinator(
            client_provider=central,
            event_bus=central.event_bus,
            health_tracker=central.health_tracker,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        # Provide new_data_points to trigger the event emission
        coordinator.publish_system_event(
            system_event=SystemEventType.HUB_REFRESHED,
            new_data_points={DataPointCategory.SENSOR: ["sensor1"]},
        )

        assert len(central.looper.tasks) == 1
        assert "hub" in central.looper.tasks[0]["name"].lower() or "data" in central.looper.tasks[0]["name"].lower()


class TestEventCoordinatorDeviceTriggerEvents:
    """Test device trigger event publishing."""

    def test_publish_device_trigger_device_error(self) -> None:
        """Publish device trigger event for device error."""
        central = _FakeCentral()
        coordinator = EventCoordinator(
            client_provider=central,
            event_bus=central.event_bus,
            health_tracker=central.health_tracker,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        coordinator.publish_device_trigger_event(
            trigger_type=DeviceTriggerEventType.DEVICE_ERROR,
            event_data=EventData(
                interface_id="HmIP-RF",
                model="HmIP-SMI",
                device_address="0001234567890ABC",
                channel_no=1,
                parameter="ERROR",
            ),
        )

        assert len(central.looper.tasks) == 1

    def test_publish_device_trigger_impulse(self) -> None:
        """Publish device trigger event for impulse."""
        central = _FakeCentral()
        coordinator = EventCoordinator(
            client_provider=central,
            event_bus=central.event_bus,
            health_tracker=central.health_tracker,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        coordinator.publish_device_trigger_event(
            trigger_type=DeviceTriggerEventType.IMPULSE,
            event_data=EventData(
                interface_id="BidCos-RF",
                model="HM-PBI-4-FM",
                device_address="VCU0000001",
                channel_no=2,
                parameter="PRESS_LONG",
            ),
        )

        assert len(central.looper.tasks) == 1
        assert "device-trigger" in central.looper.tasks[0]["name"]

    def test_publish_device_trigger_with_channel(self) -> None:
        """Publish device trigger event with channel number."""
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
                model="HM-PBI-4-FM",
                device_address="VCU0000001",
                channel_no=1,
                parameter="PRESS_SHORT",
            ),
        )

        assert len(central.looper.tasks) == 1
        assert "VCU0000001-1-PRESS_SHORT" in central.looper.tasks[0]["name"]
