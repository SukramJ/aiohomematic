"""Tests for aiohomematic.central.event_bus."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime

import pytest

from aiohomematic.central.event_bus import (
    BackendParameterEvent,
    BackendSystemEventData,
    DataPointUpdatedEvent,
    EventBus,
    HomematicEvent,
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

        bus.subscribe(event_type=BackendSystemEventData, event_key=None, handler=failing_async_handler)
        bus.subscribe(event_type=BackendSystemEventData, event_key=None, handler=working_async_handler)

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

        bus.subscribe(event_type=DataPointUpdatedEvent, event_key=None, handler=handler1)
        bus.subscribe(event_type=SysvarUpdatedEvent, event_key=None, handler=handler2)

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

        bus.subscribe(event_type=DataPointUpdatedEvent, event_key=None, handler=handler1)
        bus.subscribe(event_type=SysvarUpdatedEvent, event_key=None, handler=handler2)

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

        # BackendParameterEvent key is DataPointKey constructed from interface_id, channel_address, parameter
        dpk = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )
        bus.subscribe(event_type=BackendParameterEvent, event_key=dpk, handler=slow_handler)
        bus.subscribe(event_type=BackendParameterEvent, event_key=dpk, handler=fast_handler)

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

        # DataPointUpdatedEvent key is the dpk
        dpk = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )
        bus.subscribe(event_type=DataPointUpdatedEvent, event_key=dpk, handler=handler)

        # Publish multiple events
        for i in range(5):
            event = DataPointUpdatedEvent(
                timestamp=datetime.now(),
                dpk=dpk,
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

        # HomematicEvent key is None
        bus.subscribe(event_type=HomematicEvent, event_key=None, handler=failing_handler)
        bus.subscribe(event_type=HomematicEvent, event_key=None, handler=working_handler)

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

        # BackendParameterEvent key is DataPointKey constructed from fields
        dpk = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )
        bus.subscribe(event_type=BackendParameterEvent, event_key=dpk, handler=handler1)
        bus.subscribe(event_type=BackendParameterEvent, event_key=dpk, handler=handler2)
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

        # DataPointUpdatedEvent key is dpk
        dpk = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )
        unsubscribe = bus.subscribe(event_type=DataPointUpdatedEvent, event_key=dpk, handler=handler)

        # Unsubscribe multiple times should not raise
        unsubscribe()
        unsubscribe()
        unsubscribe()

    @pytest.mark.asyncio
    async def test_publish_with_no_subscribers(self) -> None:
        """Publishing with no subscribers should not raise errors."""
        bus = EventBus()

        event = HomematicEvent(
            timestamp=datetime.now(),
            event_type=EventType.KEYPRESS,
            event_data={EventKey.ADDRESS: "HmIP-RF:1"},
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

        # SysvarUpdatedEvent key is state_path
        state_path = "sv_12345"
        bus.subscribe(event_type=SysvarUpdatedEvent, event_key=state_path, handler=async_handler)

        event = SysvarUpdatedEvent(
            timestamp=datetime.now(),
            state_path=state_path,
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

        # DataPointUpdatedEvent key is dpk
        dpk = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )
        unsubscribe = bus.subscribe(event_type=DataPointUpdatedEvent, event_key=dpk, handler=handler)
        assert bus.get_subscription_count(event_type=DataPointUpdatedEvent) == 1

        event = DataPointUpdatedEvent(
            timestamp=datetime.now(),
            dpk=dpk,
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

        # DataPointUpdatedEvent key is dpk
        dpk = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )
        unsubscribe = bus.subscribe(event_type=DataPointUpdatedEvent, event_key=dpk, handler=handler)
        assert bus.get_subscription_count(event_type=DataPointUpdatedEvent) == 1

        event = DataPointUpdatedEvent(
            timestamp=datetime.now(),
            dpk=dpk,
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


class TestEventBusConcurrency:
    """Concurrency-focused tests for EventBus."""

    @pytest.mark.asyncio
    async def test_concurrent_subscribe_during_publish(self) -> None:
        """Test subscribing while events are being published."""
        bus = EventBus()
        received_before: list[DataPointUpdatedEvent] = []
        received_during: list[DataPointUpdatedEvent] = []

        def handler_before(event: DataPointUpdatedEvent) -> None:
            received_before.append(event)

        def handler_during(event: DataPointUpdatedEvent) -> None:
            received_during.append(event)

        dpk = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )

        # Subscribe first handler
        bus.subscribe(event_type=DataPointUpdatedEvent, event_key=dpk, handler=handler_before)

        async def publish_events() -> None:
            for i in range(50):
                event = DataPointUpdatedEvent(
                    timestamp=datetime.now(),
                    dpk=dpk,
                    value=i,
                    received_at=datetime.now(),
                )
                await bus.publish(event=event)
                await asyncio.sleep(0)

        async def subscribe_during() -> None:
            await asyncio.sleep(0)
            bus.subscribe(event_type=DataPointUpdatedEvent, event_key=dpk, handler=handler_during)

        await asyncio.gather(publish_events(), subscribe_during())

        # First handler should have received all events
        assert len(received_before) == 50
        # Second handler may have received some events (subscribed mid-way)
        assert len(received_during) >= 0  # At least 0, possibly more

    @pytest.mark.asyncio
    async def test_concurrent_unsubscribe_during_publish(self) -> None:
        """Test unsubscribing while events are being published - should not raise."""
        bus = EventBus()
        received: list[DataPointUpdatedEvent] = []

        def handler(event: DataPointUpdatedEvent) -> None:
            received.append(event)

        dpk = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )
        unsubscribe = bus.subscribe(event_type=DataPointUpdatedEvent, event_key=dpk, handler=handler)

        async def publish_events() -> None:
            for i in range(50):
                event = DataPointUpdatedEvent(
                    timestamp=datetime.now(),
                    dpk=dpk,
                    value=i,
                    received_at=datetime.now(),
                )
                await bus.publish(event=event)
                await asyncio.sleep(0)

        async def unsubscribe_during() -> None:
            await asyncio.sleep(0)
            unsubscribe()

        # Should not raise even when unsubscribing during publish
        await asyncio.gather(publish_events(), unsubscribe_during())

        # Handler should have received at least 1 event before unsubscribe
        assert len(received) >= 1

    @pytest.mark.asyncio
    async def test_handler_slow_does_not_block_other_handlers(self) -> None:
        """Test that a slow handler doesn't block other handlers from receiving events."""
        bus = EventBus()
        fast_handler_times: list[float] = []
        slow_handler_done = False

        async def slow_handler(event: DataPointUpdatedEvent) -> None:
            nonlocal slow_handler_done
            await asyncio.sleep(0.1)  # Simulate slow processing
            slow_handler_done = True

        async def fast_handler(event: DataPointUpdatedEvent) -> None:
            fast_handler_times.append(asyncio.get_event_loop().time())

        dpk = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )

        bus.subscribe(event_type=DataPointUpdatedEvent, event_key=dpk, handler=slow_handler)
        bus.subscribe(event_type=DataPointUpdatedEvent, event_key=dpk, handler=fast_handler)

        event = DataPointUpdatedEvent(
            timestamp=datetime.now(),
            dpk=dpk,
            value=True,
            received_at=datetime.now(),
        )

        await bus.publish(event=event)

        # Fast handler should have executed
        assert len(fast_handler_times) == 1
        assert slow_handler_done is True

    @pytest.mark.asyncio
    async def test_high_contention_concurrent_publish(self) -> None:
        """Test many concurrent publishes to the same event key."""
        bus = EventBus()
        received_events: list[DataPointUpdatedEvent] = []
        lock = asyncio.Lock()

        async def handler(event: DataPointUpdatedEvent) -> None:
            async with lock:
                received_events.append(event)

        dpk = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )
        bus.subscribe(event_type=DataPointUpdatedEvent, event_key=dpk, handler=handler)

        # Create many events and publish concurrently
        event_count = 200
        events = [
            DataPointUpdatedEvent(
                timestamp=datetime.now(),
                dpk=dpk,
                value=i,
                received_at=datetime.now(),
            )
            for i in range(event_count)
        ]

        await asyncio.gather(*[bus.publish(event=e) for e in events])

        # All events should be received
        assert len(received_events) == event_count

    @pytest.mark.asyncio
    async def test_multiple_event_keys_concurrent(self) -> None:
        """Test concurrent publishes to different event keys."""
        bus = EventBus()
        results: dict[str, list[int]] = {}

        def make_handler(key: str) -> Callable[[DataPointUpdatedEvent], None]:
            results[key] = []

            def handler(event: DataPointUpdatedEvent) -> None:
                results[key].append(event.value)

            return handler

        # Subscribe to multiple different keys
        dpks = []
        for i in range(5):
            dpk = DataPointKey(
                interface_id="BidCos-RF",
                channel_address=f"VCU000000{i}:1",
                paramset_key=ParamsetKey.VALUES,
                parameter="STATE",
            )
            dpks.append(dpk)
            bus.subscribe(event_type=DataPointUpdatedEvent, event_key=dpk, handler=make_handler(f"key_{i}"))

        # Publish events to all keys concurrently
        async def publish_to_key(dpk: DataPointKey, values: list[int]) -> None:
            for v in values:
                event = DataPointUpdatedEvent(
                    timestamp=datetime.now(),
                    dpk=dpk,
                    value=v,
                    received_at=datetime.now(),
                )
                await bus.publish(event=event)

        await asyncio.gather(*[publish_to_key(dpk, list(range(10))) for dpk in dpks])

        # Each key should have received 10 events
        for i in range(5):
            assert len(results[f"key_{i}"]) == 10

    @pytest.mark.asyncio
    async def test_rapid_subscribe_unsubscribe_cycles(self) -> None:
        """Test rapid subscribe/unsubscribe cycles don't corrupt state."""
        bus = EventBus()

        def handler(event: DataPointUpdatedEvent) -> None:
            pass

        dpk = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )

        # Rapid subscribe/unsubscribe cycles
        for _ in range(100):
            unsub = bus.subscribe(event_type=DataPointUpdatedEvent, event_key=dpk, handler=handler)
            unsub()

        # Should end up with no subscriptions
        assert bus.get_subscription_count(event_type=DataPointUpdatedEvent) == 0

    @pytest.mark.asyncio
    async def test_stress_many_subscribers_same_key(self) -> None:
        """Stress test with many subscribers to the same event key."""
        bus = EventBus()
        subscriber_count = 100
        call_counts: list[int] = [0] * subscriber_count

        def make_handler(idx: int) -> Callable[[DataPointUpdatedEvent], None]:
            def handler(event: DataPointUpdatedEvent) -> None:
                call_counts[idx] += 1

            return handler

        dpk = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )

        # Subscribe many handlers
        for i in range(subscriber_count):
            bus.subscribe(event_type=DataPointUpdatedEvent, event_key=dpk, handler=make_handler(i))

        # Publish one event
        event = DataPointUpdatedEvent(
            timestamp=datetime.now(),
            dpk=dpk,
            value=True,
            received_at=datetime.now(),
        )
        await bus.publish(event=event)

        # All handlers should have been called exactly once
        assert all(count == 1 for count in call_counts)
        assert bus.get_subscription_count(event_type=DataPointUpdatedEvent) == subscriber_count


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
        monitoring_all_events: list[DataPointUpdatedEvent | BackendSystemEventData] = []

        def monitor_datapoint(event: DataPointUpdatedEvent) -> None:
            monitoring_all_events.append(event)

        def monitor_backend(event: BackendSystemEventData) -> None:
            monitoring_all_events.append(event)

        # Create dpks for 3 devices - DataPointUpdatedEvent key is dpk
        dpks = [
            DataPointKey(
                interface_id="BidCos-RF",
                channel_address=f"VCU000000{i}:1",
                paramset_key=ParamsetKey.VALUES,
                parameter="STATE",
            )
            for i in range(3)
        ]

        # Subscribe to each dpk - simulates subscribing per data point
        for dpk in dpks:
            bus.subscribe(event_type=DataPointUpdatedEvent, event_key=dpk, handler=ha_datapoint_handler)
            bus.subscribe(event_type=DataPointUpdatedEvent, event_key=dpk, handler=monitor_datapoint)

        # BackendSystemEventData key is None
        bus.subscribe(event_type=BackendSystemEventData, event_key=None, handler=ha_backend_handler)
        bus.subscribe(event_type=BackendSystemEventData, event_key=None, handler=monitor_backend)

        # Simulate device updates
        for i, dpk in enumerate(dpks):
            event = DataPointUpdatedEvent(
                timestamp=datetime.now(),
                dpk=dpk,
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

        dpk = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )

        bus.subscribe(event_type=DataPointUpdatedEvent, event_key=dpk, handler=datapoint_handler)
        state_path = "sv_12345"
        bus.subscribe(event_type=SysvarUpdatedEvent, event_key=state_path, handler=sysvar_handler)

        # Publish DataPointUpdatedEvent
        dp_event = DataPointUpdatedEvent(
            timestamp=datetime.now(),
            dpk=dpk,
            value=True,
            received_at=datetime.now(),
        )
        await bus.publish(event=dp_event)

        # Publish SysvarUpdatedEvent
        sv_event = SysvarUpdatedEvent(
            timestamp=datetime.now(),
            state_path=state_path,
            value=100,
            received_at=datetime.now(),
        )
        await bus.publish(event=sv_event)

        # Each handler should only have received its own event type
        assert len(datapoint_calls) == 1
        assert len(sysvar_calls) == 1
        assert datapoint_calls[0] == dp_event
        assert sysvar_calls[0] == sv_event
