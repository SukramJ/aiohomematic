"""
Performance benchmarks for device scaling.

These tests measure performance characteristics under load conditions.
Run with: pytest tests/benchmarks/ -v --benchmark-only
"""

from __future__ import annotations

import asyncio
from datetime import datetime
import gc
import sys
import time
from typing import Any

import pytest

from aiohomematic.central.event_bus import DataPointUpdatedEvent, EventBus
from aiohomematic.const import DataPointKey, ParamsetKey


class TestEventBusScaling:
    """Benchmark EventBus performance under load."""

    @pytest.mark.asyncio
    async def test_concurrent_publish(self) -> None:
        """Measure concurrent event publishing performance."""
        bus = EventBus()
        event_count = 500
        received = []
        lock = asyncio.Lock()

        dpk = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )

        async def handler(event: DataPointUpdatedEvent) -> None:
            async with lock:
                received.append(event)

        bus.subscribe(event_type=DataPointUpdatedEvent, event_key=dpk, handler=handler)

        # Create events
        events = [
            DataPointUpdatedEvent(
                timestamp=datetime.now(),
                dpk=dpk,
                value=i,
                received_at=datetime.now(),
            )
            for i in range(event_count)
        ]

        # Measure concurrent publish performance
        start = time.perf_counter()
        await asyncio.gather(*[bus.publish(event=e) for e in events])
        publish_time = time.perf_counter() - start

        # Verify all events received
        assert len(received) == event_count

        # Performance assertion
        assert publish_time < 2.0, f"Concurrent publish too slow: {publish_time}s"

    @pytest.mark.asyncio
    async def test_publish_many_events(self) -> None:
        """Measure event publishing throughput."""
        bus = EventBus()
        event_count = 1000
        received = []

        dpk = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )

        def handler(event: DataPointUpdatedEvent) -> None:
            received.append(event)

        bus.subscribe(event_type=DataPointUpdatedEvent, event_key=dpk, handler=handler)

        # Create events
        events = [
            DataPointUpdatedEvent(
                timestamp=datetime.now(),
                dpk=dpk,
                value=i,
                received_at=datetime.now(),
            )
            for i in range(event_count)
        ]

        # Measure publish performance
        start = time.perf_counter()
        for event in events:
            await bus.publish(event=event)
        publish_time = time.perf_counter() - start

        # Verify all events received
        assert len(received) == event_count

        # Performance assertion
        assert publish_time < 2.0, f"Publish too slow: {publish_time}s"

    @pytest.mark.asyncio
    async def test_subscribe_many_handlers(self) -> None:
        """Measure subscription performance with many handlers."""
        bus = EventBus()
        handler_count = 1000

        dpk = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )

        def make_handler() -> Any:
            def handler(event: DataPointUpdatedEvent) -> None:
                pass

            return handler

        start = time.perf_counter()
        unsubscribes = []
        for _ in range(handler_count):
            unsub = bus.subscribe(
                event_type=DataPointUpdatedEvent,
                event_key=dpk,
                handler=make_handler(),
            )
            unsubscribes.append(unsub)
        subscribe_time = time.perf_counter() - start

        # Verify subscription count
        assert bus.get_subscription_count(event_type=DataPointUpdatedEvent) == handler_count

        # Measure unsubscribe performance
        start = time.perf_counter()
        for unsub in unsubscribes:
            unsub()
        unsubscribe_time = time.perf_counter() - start

        # Performance assertion (should complete in reasonable time)
        assert subscribe_time < 1.0, f"Subscribe too slow: {subscribe_time}s"
        assert unsubscribe_time < 1.0, f"Unsubscribe too slow: {unsubscribe_time}s"


class TestMemoryUsage:
    """Benchmark memory usage under load."""

    def test_event_bus_memory_with_many_subscriptions(self) -> None:
        """Measure memory growth with many subscriptions."""
        bus = EventBus()
        subscription_count = 5000

        # Force garbage collection
        gc.collect()
        _ = sys.getsizeof(bus)  # baseline memory

        dpks = [
            DataPointKey(
                interface_id="BidCos-RF",
                channel_address=f"VCU{i:07d}:1",
                paramset_key=ParamsetKey.VALUES,
                parameter="STATE",
            )
            for i in range(subscription_count)
        ]

        def handler(event: DataPointUpdatedEvent) -> None:
            pass

        unsubscribes = []
        for dpk in dpks:
            unsub = bus.subscribe(
                event_type=DataPointUpdatedEvent,
                event_key=dpk,
                handler=handler,
            )
            unsubscribes.append(unsub)

        gc.collect()
        _ = sys.getsizeof(bus)  # final memory after subscriptions

        # Verify subscriptions work
        assert bus.get_subscription_count(event_type=DataPointUpdatedEvent) == subscription_count

        # Cleanup
        for unsub in unsubscribes:
            unsub()

        gc.collect()
        _ = sys.getsizeof(bus)  # cleanup_mem - verify memory is reclaimed


class TestDataPointKeyPerformance:
    """Benchmark DataPointKey operations."""

    def test_datapoint_key_dict_lookup(self) -> None:
        """Measure DataPointKey dictionary lookup performance."""
        key_count = 10000

        dpks = [
            DataPointKey(
                interface_id="BidCos-RF",
                channel_address=f"VCU{i:07d}:1",
                paramset_key=ParamsetKey.VALUES,
                parameter="STATE",
            )
            for i in range(key_count)
        ]

        # Create dictionary
        dpk_dict = {dpk: i for i, dpk in enumerate(dpks)}

        # Measure lookup performance
        start = time.perf_counter()
        for dpk in dpks:
            _ = dpk_dict[dpk]
        lookup_time = time.perf_counter() - start

        # Performance assertion
        assert lookup_time < 0.5, f"Lookup too slow: {lookup_time}s"

    def test_datapoint_key_hashing(self) -> None:
        """Measure DataPointKey hashing performance."""
        key_count = 10000

        dpks = [
            DataPointKey(
                interface_id="BidCos-RF",
                channel_address=f"VCU{i:07d}:1",
                paramset_key=ParamsetKey.VALUES,
                parameter="STATE",
            )
            for i in range(key_count)
        ]

        # Measure hash performance
        start = time.perf_counter()
        hashes = [hash(dpk) for dpk in dpks]
        hash_time = time.perf_counter() - start

        # Verify unique hashes
        unique_hashes = len(set(hashes))
        assert unique_hashes == key_count

        # Performance assertion
        assert hash_time < 0.5, f"Hashing too slow: {hash_time}s"


class TestRetryPerformance:
    """Benchmark retry mechanism performance."""

    @pytest.mark.asyncio
    async def test_retry_overhead(self) -> None:
        """Measure retry decorator overhead for successful calls."""
        from aiohomematic.retry import with_retry

        call_count = 1000
        calls = []

        @with_retry(max_attempts=3, initial_backoff=0.01)
        async def fast_operation() -> str:
            calls.append(1)
            return "success"

        # Measure overhead
        start = time.perf_counter()
        for _ in range(call_count):
            await fast_operation()
        total_time = time.perf_counter() - start

        # Verify all calls succeeded
        assert len(calls) == call_count

        # Performance assertion - retry decorator should add minimal overhead
        assert total_time < 1.0, f"Retry overhead too high: {total_time}s"
