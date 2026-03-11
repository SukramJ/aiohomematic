# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Performance benchmarks for EventBus."""

from datetime import datetime

import pytest

from aiohomematic.async_support import Looper
from aiohomematic.central.events import DeviceStateChangedEvent, EventBus

from .conftest import BenchmarkTimer


@pytest.fixture
def event_bus() -> EventBus:
    """Create an EventBus for benchmarking."""
    looper = Looper()
    return EventBus(task_scheduler=looper)


@pytest.mark.benchmark
async def test_event_bus_publish_no_subscribers(bench: BenchmarkTimer, event_bus: EventBus) -> None:
    """Benchmark: publishing events with no subscribers."""
    iterations = 1000

    with bench.measure(name="publish_no_subs", iterations=iterations):
        for i in range(iterations):
            await event_bus.publish(
                event=DeviceStateChangedEvent(
                    timestamp=datetime.now(),
                    device_address=f"VCU{i:07d}",
                )
            )

    result = bench.last()
    assert result.ops_per_sec > 5000, f"Expected >5000 ops/s, got {result.ops_per_sec:.0f}"


@pytest.mark.benchmark
async def test_event_bus_publish_with_subscribers(bench: BenchmarkTimer, event_bus: EventBus) -> None:
    """Benchmark: publishing events with multiple subscribers."""
    iterations = 500
    handler_call_count = 0

    async def handler(*, event: DeviceStateChangedEvent) -> None:
        nonlocal handler_call_count
        handler_call_count += 1

    # Subscribe 5 handlers with wildcard key
    for _ in range(5):
        event_bus.subscribe(
            event_type=DeviceStateChangedEvent,
            event_key=None,
            handler=handler,
        )

    with bench.measure(name="publish_with_subs", iterations=iterations):
        for i in range(iterations):
            await event_bus.publish(
                event=DeviceStateChangedEvent(
                    timestamp=datetime.now(),
                    device_address=f"VCU{i:07d}",
                )
            )

    assert handler_call_count == iterations * 5
    result = bench.last()
    assert result.ops_per_sec > 500, f"Expected >500 ops/s, got {result.ops_per_sec:.0f}"


@pytest.mark.benchmark
async def test_event_bus_subscribe_unsubscribe(bench: BenchmarkTimer, event_bus: EventBus) -> None:
    """Benchmark: subscribe and unsubscribe cycle throughput."""
    iterations = 2000

    async def noop_handler(*, event: DeviceStateChangedEvent) -> None:
        pass

    with bench.measure(name="sub_unsub_cycle", iterations=iterations):
        for _ in range(iterations):
            unsub = event_bus.subscribe(
                event_type=DeviceStateChangedEvent,
                event_key=None,
                handler=noop_handler,
            )
            unsub()

    result = bench.last()
    assert result.ops_per_sec > 2000, f"Expected >2000 ops/s, got {result.ops_per_sec:.0f}"
