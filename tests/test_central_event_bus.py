"""Tests for aiohomematic.central.event_bus."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import pytest

from aiohomematic.central.event_bus import (
    BackendParameterEvent,
    BackendSystemEventData,
    DataPointUpdatedEvent,
    EventBus,
    HomematicEvent,
    InterfaceEvent,
    SysvarUpdatedEvent,
)
from aiohomematic.const import BackendSystemEvent, DataPointKey, EventKey, EventType, ParamsetKey


class TestEventBus:
    """Test EventBus core functionality."""

    @pytest.mark.asyncio
    async def test_async_handler_exception_isolation(self) -> None:
        """Exception in async handler should not affect other handlers."""
        bus = EventBus()
        calls = []

        async def failing_async_handler(event: BackendSystemEventData) -> None:
            raise RuntimeError("Async failure")

        async def working_async_handler(event: BackendSystemEventData) -> None:
            calls.append(event)

        bus.subscribe(event_type=BackendSystemEventData, handler=failing_async_handler)
        bus.subscribe(event_type=BackendSystemEventData, handler=working_async_handler)

        event = BackendSystemEventData(
            timestamp=datetime.now(),
            system_event=BackendSystemEvent.DEVICES_CREATED,
            data={"device_count": 5},
        )

        await bus.publish(event=event)

        # Working handler should have been called
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_clear_all_subscriptions(self) -> None:
        """Clear all subscriptions."""
        bus = EventBus()

        def handler1(event: DataPointUpdatedEvent) -> None:
            pass

        def handler2(event: SysvarUpdatedEvent) -> None:
            pass

        bus.subscribe(event_type=DataPointUpdatedEvent, handler=handler1)
        bus.subscribe(event_type=SysvarUpdatedEvent, handler=handler2)

        # Clear all
        bus.clear_subscriptions()

        assert bus.get_subscription_count(event_type=DataPointUpdatedEvent) == 0
        assert bus.get_subscription_count(event_type=SysvarUpdatedEvent) == 0

    @pytest.mark.asyncio
    async def test_clear_subscriptions_specific_type(self) -> None:
        """Clear subscriptions for specific event type."""
        bus = EventBus()

        def handler1(event: DataPointUpdatedEvent) -> None:
            pass

        def handler2(event: SysvarUpdatedEvent) -> None:
            pass

        bus.subscribe(event_type=DataPointUpdatedEvent, handler=handler1)
        bus.subscribe(event_type=SysvarUpdatedEvent, handler=handler2)

        assert bus.get_subscription_count(event_type=DataPointUpdatedEvent) == 1
        assert bus.get_subscription_count(event_type=SysvarUpdatedEvent) == 1

        # Clear only DataPointUpdatedEvent
        bus.clear_subscriptions(event_type=DataPointUpdatedEvent)

        assert bus.get_subscription_count(event_type=DataPointUpdatedEvent) == 0
        assert bus.get_subscription_count(event_type=SysvarUpdatedEvent) == 1  # Still there

    @pytest.mark.asyncio
    async def test_concurrent_handler_execution(self) -> None:
        """Handlers should be executed concurrently."""
        bus = EventBus()
        execution_order = []

        async def slow_handler(event: BackendParameterEvent) -> None:
            execution_order.append("slow_start")
            await asyncio.sleep(0.1)
            execution_order.append("slow_end")

        async def fast_handler(event: BackendParameterEvent) -> None:
            execution_order.append("fast_start")
            await asyncio.sleep(0.01)
            execution_order.append("fast_end")

        bus.subscribe(event_type=BackendParameterEvent, handler=slow_handler)
        bus.subscribe(event_type=BackendParameterEvent, handler=fast_handler)

        event = BackendParameterEvent(
            timestamp=datetime.now(),
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            parameter="STATE",
            value=True,
        )

        await bus.publish(event=event)

        # Both should have started before either finished (concurrent execution)
        assert execution_order[0] in ["slow_start", "fast_start"]
        assert execution_order[1] in ["slow_start", "fast_start"]
        assert execution_order[0] != execution_order[1]

        # Fast should finish before slow
        assert "fast_end" in execution_order
        assert "slow_end" in execution_order
        assert execution_order.index("fast_end") < execution_order.index("slow_end")

    def test_event_bus_initialization(self) -> None:
        """EventBus should initialize with empty subscriptions."""
        bus = EventBus()
        assert bus.get_subscription_count(event_type=DataPointUpdatedEvent) == 0
        assert bus.get_event_stats() == {}

    def test_event_bus_initialization_with_logging(self) -> None:
        """EventBus can be initialized with event logging enabled."""
        bus = EventBus(enable_event_logging=True)
        assert bus._enable_event_logging is True  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_event_stats_tracking(self) -> None:
        """EventBus should track event statistics."""
        bus = EventBus()

        def handler(event: DataPointUpdatedEvent) -> None:
            pass

        bus.subscribe(event_type=DataPointUpdatedEvent, handler=handler)

        # Publish multiple events
        for i in range(5):
            event = DataPointUpdatedEvent(
                timestamp=datetime.now(),
                dpk=DataPointKey(
                    interface_id="BidCos-RF",
                    channel_address="VCU0000001:1",
                    paramset_key=ParamsetKey.VALUES,
                    parameter="STATE",
                ),
                value=i,
                received_at=datetime.now(),
            )
            await bus.publish(event=event)

        stats = bus.get_event_stats()
        assert "DataPointUpdatedEvent" in stats
        assert stats["DataPointUpdatedEvent"] == 5

    @pytest.mark.asyncio
    async def test_handler_exception_isolation(self) -> None:
        """Exception in one handler should not affect other handlers."""
        bus = EventBus()
        handler1_calls = []
        handler2_calls = []

        def failing_handler(event: HomematicEvent) -> None:
            handler1_calls.append(event)
            raise ValueError("Handler failed!")

        def working_handler(event: HomematicEvent) -> None:
            handler2_calls.append(event)

        bus.subscribe(event_type=HomematicEvent, handler=failing_handler)
        bus.subscribe(event_type=HomematicEvent, handler=working_handler)

        event = HomematicEvent(
            timestamp=datetime.now(),
            event_type=EventType.KEYPRESS,
            event_data={EventKey.ADDRESS: "VCU0000001:1"},
        )

        # Should not raise despite failing_handler
        await bus.publish(event=event)

        # Both handlers were called (even though first one failed)
        assert len(handler1_calls) == 1
        assert len(handler2_calls) == 1

    @pytest.mark.asyncio
    async def test_multiple_subscribers_same_event(self) -> None:
        """Multiple handlers can subscribe to the same event type."""
        bus = EventBus()
        handler1_calls = []
        handler2_calls = []

        def handler1(event: BackendParameterEvent) -> None:
            handler1_calls.append(event)

        def handler2(event: BackendParameterEvent) -> None:
            handler2_calls.append(event)

        bus.subscribe(event_type=BackendParameterEvent, handler=handler1)
        bus.subscribe(event_type=BackendParameterEvent, handler=handler2)
        assert bus.get_subscription_count(event_type=BackendParameterEvent) == 2

        event = BackendParameterEvent(
            timestamp=datetime.now(),
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            parameter="STATE",
            value=True,
        )

        await bus.publish(event=event)

        # Both handlers should have been called
        assert len(handler1_calls) == 1
        assert len(handler2_calls) == 1

    @pytest.mark.asyncio
    async def test_multiple_unsubscribe_calls_safe(self) -> None:
        """Calling unsubscribe multiple times should be safe."""
        bus = EventBus()

        def handler(event: DataPointUpdatedEvent) -> None:
            pass

        unsubscribe = bus.subscribe(event_type=DataPointUpdatedEvent, handler=handler)

        # Unsubscribe multiple times should not raise
        unsubscribe()
        unsubscribe()
        unsubscribe()

    @pytest.mark.asyncio
    async def test_publish_with_no_subscribers(self) -> None:
        """Publishing with no subscribers should not raise errors."""
        bus = EventBus()

        event = InterfaceEvent(
            timestamp=datetime.now(),
            interface_id="HmIP-RF",
            event_type="CONNECTED",
            data={},
        )

        # Should not raise
        await bus.publish(event=event)

    @pytest.mark.asyncio
    async def test_subscribe_and_publish_async_handler(self) -> None:
        """Subscribe with async handler and publish event."""
        bus = EventBus()
        received_events: list[SysvarUpdatedEvent] = []

        async def async_handler(event: SysvarUpdatedEvent) -> None:
            await asyncio.sleep(0)  # Simulate async work
            received_events.append(event)

        bus.subscribe(event_type=SysvarUpdatedEvent, handler=async_handler)

        event = SysvarUpdatedEvent(
            timestamp=datetime.now(),
            state_path="sv_12345",
            value=42,
            received_at=datetime.now(),
        )

        await bus.publish(event=event)
        assert len(received_events) == 1
        assert received_events[0].value == 42

    @pytest.mark.asyncio
    async def test_subscribe_and_publish_sync_handler(self) -> None:
        """Subscribe with sync handler and publish event."""
        bus = EventBus()
        received_events: list[DataPointUpdatedEvent] = []

        def handler(event: DataPointUpdatedEvent) -> None:
            received_events.append(event)

        unsubscribe = bus.subscribe(event_type=DataPointUpdatedEvent, handler=handler)
        assert bus.get_subscription_count(event_type=DataPointUpdatedEvent) == 1

        event = DataPointUpdatedEvent(
            timestamp=datetime.now(),
            dpk=DataPointKey(
                interface_id="BidCos-RF",
                channel_address="VCU0000001:1",
                paramset_key=ParamsetKey.VALUES,
                parameter="STATE",
            ),
            value=True,
            received_at=datetime.now(),
        )

        await bus.publish(event=event)
        assert len(received_events) == 1
        assert received_events[0] == event

        # Unsubscribe
        unsubscribe()
        assert bus.get_subscription_count(event_type=DataPointUpdatedEvent) == 0

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_handler(self) -> None:
        """Unsubscribe callback should remove the handler."""
        bus = EventBus()
        calls = []

        def handler(event: DataPointUpdatedEvent) -> None:
            calls.append(event)

        unsubscribe = bus.subscribe(event_type=DataPointUpdatedEvent, handler=handler)
        assert bus.get_subscription_count(event_type=DataPointUpdatedEvent) == 1

        event = DataPointUpdatedEvent(
            timestamp=datetime.now(),
            dpk=DataPointKey(
                interface_id="BidCos-RF",
                channel_address="VCU0000001:1",
                paramset_key=ParamsetKey.VALUES,
                parameter="STATE",
            ),
            value=True,
            received_at=datetime.now(),
        )

        await bus.publish(event=event)
        assert len(calls) == 1

        # Unsubscribe
        unsubscribe()
        assert bus.get_subscription_count(event_type=DataPointUpdatedEvent) == 0

        # Publish again - handler should not be called
        await bus.publish(event=event)
        assert len(calls) == 1  # Still 1, not 2


class TestDataPointKey:
    """Test DataPointKey functionality (from const.py)."""

    def test_datapoint_key_creation(self) -> None:
        """DataPointKey should be created with interface_id, channel_address, paramset_key, parameter."""
        dpk = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )
        assert dpk.interface_id == "BidCos-RF"
        assert dpk.channel_address == "VCU0000001:1"
        assert dpk.paramset_key == ParamsetKey.VALUES
        assert dpk.parameter == "STATE"

    def test_datapoint_key_equality(self) -> None:
        """DataPointKey instances with same values should be equal."""
        dpk1 = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )
        dpk2 = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )
        dpk3 = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000002:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )

        assert dpk1 == dpk2
        assert dpk1 != dpk3

    def test_datapoint_key_hashable(self) -> None:
        """DataPointKey should be hashable (can be used as dict key)."""
        dpk1 = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )
        dpk2 = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )

        dpk_dict = {dpk1: "value1"}
        dpk_dict[dpk2] = "value2"

        # Same key, so only one entry
        assert len(dpk_dict) == 1
        assert dpk_dict[dpk1] == "value2"

    def test_datapoint_key_immutability(self) -> None:
        """DataPointKey should be immutable (NamedTuple)."""
        dpk = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )

        with pytest.raises(AttributeError):
            dpk.interface_id = "HmIP-RF"  # type: ignore[misc]


class TestEventImmutability:
    """Test that events are immutable."""

    def test_backend_system_event_immutability(self) -> None:
        """BackendSystemEventData should be immutable."""
        event = BackendSystemEventData(
            timestamp=datetime.now(),
            system_event=BackendSystemEvent.DEVICES_CREATED,
            data={"count": 5},
        )

        with pytest.raises(AttributeError):
            event.system_event = BackendSystemEvent.DELETE_DEVICES  # type: ignore[misc]

    def test_event_immutability(self) -> None:
        """Events should be frozen dataclasses (immutable)."""
        event = DataPointUpdatedEvent(
            timestamp=datetime.now(),
            dpk=DataPointKey(
                interface_id="BidCos-RF",
                channel_address="VCU0000001:1",
                paramset_key=ParamsetKey.VALUES,
                parameter="STATE",
            ),
            value=True,
            received_at=datetime.now(),
        )

        with pytest.raises(AttributeError):
            event.value = False  # type: ignore[misc]


class TestEventBusIntegration:
    """Integration tests for EventBus with multiple event types."""

    @pytest.mark.asyncio
    async def test_event_bus_real_world_scenario(self) -> None:
        """Simulate real-world usage with multiple subscribers and events."""
        bus = EventBus(enable_event_logging=False)

        # Simulate Home Assistant integration subscribing to events
        ha_datapoint_updates = []
        ha_backend_events = []

        async def ha_datapoint_handler(event: DataPointUpdatedEvent) -> None:
            ha_datapoint_updates.append(event)

        async def ha_backend_handler(event: BackendSystemEventData) -> None:
            ha_backend_events.append(event)

        # Simulate internal monitoring
        monitoring_all_events = []

        def monitor_datapoint(event: DataPointUpdatedEvent) -> None:
            monitoring_all_events.append(event)

        def monitor_backend(event: BackendSystemEventData) -> None:
            monitoring_all_events.append(event)

        # Subscribe
        bus.subscribe(event_type=DataPointUpdatedEvent, handler=ha_datapoint_handler)
        bus.subscribe(event_type=BackendSystemEventData, handler=ha_backend_handler)
        bus.subscribe(event_type=DataPointUpdatedEvent, handler=monitor_datapoint)
        bus.subscribe(event_type=BackendSystemEventData, handler=monitor_backend)

        # Simulate device updates
        for i in range(3):
            event = DataPointUpdatedEvent(
                timestamp=datetime.now(),
                dpk=DataPointKey(
                    interface_id="BidCos-RF",
                    channel_address=f"VCU000000{i}:1",
                    paramset_key=ParamsetKey.VALUES,
                    parameter="STATE",
                ),
                value=i % 2 == 0,
                received_at=datetime.now(),
            )
            await bus.publish(event=event)

        # Simulate system event
        system_event = BackendSystemEventData(
            timestamp=datetime.now(),
            system_event=BackendSystemEvent.DEVICES_CREATED,
            data={"count": 3},
        )
        await bus.publish(event=system_event)

        # Verify all events were received
        assert len(ha_datapoint_updates) == 3
        assert len(ha_backend_events) == 1
        assert len(monitoring_all_events) == 4  # 3 datapoint + 1 backend

        # Verify stats
        stats = bus.get_event_stats()
        assert stats["DataPointUpdatedEvent"] == 3
        assert stats["BackendSystemEventData"] == 1
        assert stats["BackendSystemEventData"] == 1

    @pytest.mark.asyncio
    async def test_multiple_event_types_independent(self) -> None:
        """Different event types should not interfere with each other."""
        bus = EventBus()

        datapoint_calls = []
        sysvar_calls = []

        def datapoint_handler(event: DataPointUpdatedEvent) -> None:
            datapoint_calls.append(event)

        def sysvar_handler(event: SysvarUpdatedEvent) -> None:
            sysvar_calls.append(event)

        bus.subscribe(event_type=DataPointUpdatedEvent, handler=datapoint_handler)
        bus.subscribe(event_type=SysvarUpdatedEvent, handler=sysvar_handler)

        # Publish DataPointUpdatedEvent
        dp_event = DataPointUpdatedEvent(
            timestamp=datetime.now(),
            dpk=DataPointKey(
                interface_id="BidCos-RF",
                channel_address="VCU0000001:1",
                paramset_key=ParamsetKey.VALUES,
                parameter="STATE",
            ),
            value=True,
            received_at=datetime.now(),
        )
        await bus.publish(event=dp_event)

        # Publish SysvarUpdatedEvent
        sv_event = SysvarUpdatedEvent(
            timestamp=datetime.now(),
            state_path="sv_12345",
            value=100,
            received_at=datetime.now(),
        )
        await bus.publish(event=sv_event)

        # Each handler should only have received its own event type
        assert len(datapoint_calls) == 1
        assert len(sysvar_calls) == 1
        assert datapoint_calls[0] == dp_event
        assert sysvar_calls[0] == sv_event


class TestLegacyCompatibility:
    """Test legacy callback protocol compatibility."""

    @pytest.mark.asyncio
    async def test_legacy_and_new_api_coexist(self) -> None:
        """Legacy and new API should work together."""
        bus = EventBus()
        legacy_calls = []
        new_calls = []

        # Legacy callback
        def legacy_callback(*, system_event: BackendSystemEvent, **kwargs: Any) -> None:
            legacy_calls.append(system_event)

        # New event handler
        def new_handler(event: BackendSystemEventData) -> None:
            new_calls.append(event)

        # Subscribe both
        bus.subscribe_backend_system_callback(callback=legacy_callback)
        bus.subscribe(event_type=BackendSystemEventData, handler=new_handler)

        # Publish event
        event = BackendSystemEventData(
            timestamp=datetime.now(),
            system_event=BackendSystemEvent.DEVICES_CREATED,
            data={"count": 3},
        )
        await bus.publish(event=event)

        # Both should have received the event
        assert len(legacy_calls) == 1
        assert len(new_calls) == 1
        assert legacy_calls[0] == BackendSystemEvent.DEVICES_CREATED
        assert new_calls[0] == event

    @pytest.mark.asyncio
    async def test_subscribe_backend_parameter_callback(self) -> None:
        """Legacy BackendParameterCallback should work via adapter."""
        bus = EventBus()
        received_calls = []

        def legacy_callback(*, interface_id: str, channel_address: str, parameter: str, value: Any) -> None:
            received_calls.append(
                {
                    "interface_id": interface_id,
                    "channel_address": channel_address,
                    "parameter": parameter,
                    "value": value,
                }
            )

        # Subscribe using legacy method
        bus.subscribe_backend_parameter_callback(callback=legacy_callback)

        # Publish event
        await bus.publish(
            event=BackendParameterEvent(
                timestamp=datetime.now(),
                interface_id="HmIP-RF",
                channel_address="VCU1234567:1",
                parameter="TEMPERATURE",
                value=21.5,
            )
        )

        # Verify callback was called
        assert len(received_calls) == 1
        assert received_calls[0]["interface_id"] == "HmIP-RF"
        assert received_calls[0]["channel_address"] == "VCU1234567:1"
        assert received_calls[0]["parameter"] == "TEMPERATURE"
        assert received_calls[0]["value"] == 21.5

    @pytest.mark.asyncio
    async def test_subscribe_backend_system_callback(self) -> None:
        """Legacy BackendSystemCallback should work via adapter."""
        bus = EventBus()
        received_calls = []

        def legacy_callback(*, system_event: BackendSystemEvent, **kwargs: Any) -> None:
            received_calls.append({"system_event": system_event, "kwargs": kwargs})

        # Subscribe using legacy method
        unsubscribe = bus.subscribe_backend_system_callback(callback=legacy_callback)

        # Publish event
        await bus.publish(
            event=BackendSystemEventData(
                timestamp=datetime.now(),
                system_event=BackendSystemEvent.DEVICES_CREATED,
                data={"device_count": 5, "interface_id": "BidCos-RF"},
            )
        )

        # Verify callback was called with correct arguments
        assert len(received_calls) == 1
        assert received_calls[0]["system_event"] == BackendSystemEvent.DEVICES_CREATED
        assert received_calls[0]["kwargs"]["device_count"] == 5
        assert received_calls[0]["kwargs"]["interface_id"] == "BidCos-RF"

        # Unsubscribe
        unsubscribe()
        assert bus.get_subscription_count(event_type=BackendSystemEventData) == 0

    @pytest.mark.asyncio
    async def test_subscribe_datapoint_event_callback_with_filtering(self) -> None:
        """Legacy DataPointEventCallback should filter by DataPointKey."""
        bus = EventBus()
        received_calls = []

        target_dpk = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )

        async def legacy_callback(*, value: Any, received_at: datetime) -> None:
            received_calls.append({"value": value, "received_at": received_at})

        # Subscribe for specific data point
        bus.subscribe_datapoint_event_callback(dpk=target_dpk, callback=legacy_callback)

        # Publish event for the target data point
        received_time = datetime.now()
        await bus.publish(
            event=DataPointUpdatedEvent(
                timestamp=datetime.now(),
                dpk=target_dpk,
                value=True,
                received_at=received_time,
            )
        )

        # Publish event for a different data point
        other_dpk = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000002:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )
        await bus.publish(
            event=DataPointUpdatedEvent(
                timestamp=datetime.now(),
                dpk=other_dpk,
                value=False,
                received_at=datetime.now(),
            )
        )

        # Only the first event should have triggered the callback
        assert len(received_calls) == 1
        assert received_calls[0]["value"] is True
        assert received_calls[0]["received_at"] == received_time

    @pytest.mark.asyncio
    async def test_subscribe_homematic_callback(self) -> None:
        """Legacy HomematicCallback should work via adapter."""
        bus = EventBus()
        received_calls = []

        def legacy_callback(*, event_type: EventType, event_data: dict[EventKey, Any]) -> None:
            received_calls.append({"event_type": event_type, "event_data": event_data})

        # Subscribe using legacy method
        bus.subscribe_homematic_callback(callback=legacy_callback)

        # Publish event
        await bus.publish(
            event=HomematicEvent(
                timestamp=datetime.now(),
                event_type=EventType.KEYPRESS,
                event_data={
                    EventKey.ADDRESS: "VCU0000001:1",
                    EventKey.PARAMETER: "PRESS_SHORT",
                    EventKey.VALUE: "PRESSED",
                },
            )
        )

        # Verify callback was called
        assert len(received_calls) == 1
        assert received_calls[0]["event_type"] == EventType.KEYPRESS
        assert received_calls[0]["event_data"][EventKey.ADDRESS] == "VCU0000001:1"

    @pytest.mark.asyncio
    async def test_subscribe_sysvar_event_callback_with_filtering(self) -> None:
        """Legacy SysvarEventCallback should filter by state_path."""
        bus = EventBus()
        received_calls = []

        target_path = "sv_12345"

        async def legacy_callback(*, value: Any, received_at: datetime) -> None:
            received_calls.append({"value": value, "received_at": received_at})

        # Subscribe for specific system variable
        bus.subscribe_sysvar_event_callback(state_path=target_path, callback=legacy_callback)

        # Publish event for target sysvar
        received_time = datetime.now()
        await bus.publish(
            event=SysvarUpdatedEvent(
                timestamp=datetime.now(),
                state_path=target_path,
                value=42,
                received_at=received_time,
            )
        )

        # Publish event for different sysvar
        await bus.publish(
            event=SysvarUpdatedEvent(
                timestamp=datetime.now(),
                state_path="sv_67890",
                value=99,
                received_at=datetime.now(),
            )
        )

        # Only the first event should have triggered the callback
        assert len(received_calls) == 1
        assert received_calls[0]["value"] == 42
        assert received_calls[0]["received_at"] == received_time
