# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for RequestCoalescer."""

from __future__ import annotations

import asyncio

import pytest

from aiohomematic.central.events import EventBus, RequestCoalescedEvent
from aiohomematic.client import RequestCoalescer
from aiohomematic.metrics import MetricKeys, MetricsObserver
from aiohomematic_test_support.event_capture import EventCapture


class TestRequestCoalescer:
    """Tests for RequestCoalescer."""

    @pytest.mark.asyncio
    async def test_clear_cancels_pending(self) -> None:
        """Test clear() cancels pending futures and clears pending dict."""
        coalescer = RequestCoalescer(name="test")
        execution_started = asyncio.Event()

        async def slow_executor():
            execution_started.set()
            await asyncio.sleep(10)
            return "result"

        # Start a slow request
        task = asyncio.create_task(coalescer.execute(key="slow-key", executor=slow_executor))

        # Wait for execution to start
        await execution_started.wait()
        assert coalescer.pending_count == 1

        # Clear all pending - this cancels futures and clears the dict
        coalescer.clear()
        assert coalescer.pending_count == 0

        # Cancel the task ourselves to clean up (clear() doesn't cancel tasks)
        task.cancel()

        # The task will raise either CancelledError or KeyError
        # (KeyError if finally block runs after clear() removed the key)
        with pytest.raises((asyncio.CancelledError, KeyError)):
            await task

    @pytest.mark.asyncio
    async def test_coalesced_requests(self, event_capture: EventCapture) -> None:
        """Test multiple concurrent requests are coalesced, verified via events."""
        event_bus = EventBus()
        event_capture.subscribe_to(event_bus, RequestCoalescedEvent)

        coalescer = RequestCoalescer(
            name="test",
            event_bus=event_bus,
            interface_id="test-rf",
        )
        execution_count = 0
        execution_started = asyncio.Event()

        async def slow_executor():
            nonlocal execution_count
            execution_count += 1
            execution_started.set()
            await asyncio.sleep(0.1)
            return "result"

        # Start first request
        task1 = asyncio.create_task(coalescer.execute(key="same-key", executor=slow_executor))

        # Wait for execution to start
        await execution_started.wait()

        # Start second request with same key while first is running
        task2 = asyncio.create_task(coalescer.execute(key="same-key", executor=slow_executor))

        results = await asyncio.gather(task1, task2)

        assert results == ["result", "result"]
        assert execution_count == 1  # Only executed once

        # Verify coalescing via event
        event_capture.assert_event_emitted(
            event_type=RequestCoalescedEvent,
            request_key="same-key",
            interface_id="test-rf",
        )

    @pytest.mark.asyncio
    async def test_different_keys_not_coalesced(self, event_capture: EventCapture) -> None:
        """Test requests with different keys are not coalesced - no event emitted."""
        event_bus = EventBus()
        observer = MetricsObserver(event_bus=event_bus)
        event_capture.subscribe_to(event_bus, RequestCoalescedEvent)

        coalescer = RequestCoalescer(
            name="test",
            event_bus=event_bus,
            interface_id="test-rf",
        )
        execution_count = 0

        async def executor():
            nonlocal execution_count
            execution_count += 1
            return f"result-{execution_count}"

        result1 = await coalescer.execute(key="key-1", executor=executor)
        result2 = await coalescer.execute(key="key-2", executor=executor)

        assert result1 == "result-1"
        assert result2 == "result-2"
        assert execution_count == 2
        assert observer.get_counter(key=MetricKeys.coalescer_coalesced(interface_id="test-rf")) == 0

        # Verify no coalescing event was emitted (different keys = no coalescing)
        event_capture.assert_no_event(event_type=RequestCoalescedEvent)

    @pytest.mark.asyncio
    async def test_exception_propagated_to_all_waiters(self) -> None:
        """Test exceptions are propagated to all waiting callers."""
        event_bus = EventBus()
        observer = MetricsObserver(event_bus=event_bus)
        coalescer = RequestCoalescer(name="test", event_bus=event_bus, interface_id="test-rf")
        execution_started = asyncio.Event()

        async def failing_executor():
            execution_started.set()
            await asyncio.sleep(0.05)
            raise ValueError("Test error")

        # Start first request
        task1 = asyncio.create_task(coalescer.execute(key="fail-key", executor=failing_executor))

        # Wait for execution to start
        await execution_started.wait()

        # Start second request with same key
        task2 = asyncio.create_task(coalescer.execute(key="fail-key", executor=failing_executor))

        # Both should raise the same exception
        with pytest.raises(ValueError, match="Test error"):
            await task1

        with pytest.raises(ValueError, match="Test error"):
            await task2

        # Give event loop time to process scheduled events
        await asyncio.sleep(0.01)

        assert observer.get_counter(key=MetricKeys.coalescer_failure(interface_id="test-rf")) == 1
        assert coalescer.pending_count == 0

    def test_init(self) -> None:
        """Test initialization."""
        coalescer = RequestCoalescer(name="test")
        assert coalescer.pending_count == 0

    def test_init_default_name(self) -> None:
        """Test initialization with default name."""
        coalescer = RequestCoalescer()
        assert coalescer.pending_count == 0

    @pytest.mark.asyncio
    async def test_many_waiters(self, event_capture: EventCapture) -> None:
        """Test many concurrent waiters for same key, verified via events."""
        event_bus = EventBus()
        observer = MetricsObserver(event_bus=event_bus)
        event_capture.subscribe_to(event_bus, RequestCoalescedEvent)

        coalescer = RequestCoalescer(
            name="test",
            event_bus=event_bus,
            interface_id="test-rf",
        )
        execution_count = 0
        execution_started = asyncio.Event()

        async def slow_executor():
            nonlocal execution_count
            execution_count += 1
            execution_started.set()
            await asyncio.sleep(0.1)
            return "shared-result"

        # Start many concurrent requests
        tasks = [asyncio.create_task(coalescer.execute(key="shared", executor=slow_executor)) for _ in range(10)]

        # Wait for execution to start
        await execution_started.wait()

        results = await asyncio.gather(*tasks)

        assert all(r == "shared-result" for r in results)
        assert execution_count == 1
        # Local counters track total and executed requests
        assert coalescer.total_requests == 10
        assert coalescer.executed_requests == 1
        # Coalesced counter is event-based (significant event)
        assert observer.get_counter(key=MetricKeys.coalescer_coalesced(interface_id="test-rf")) == 9

        # Verify coalescing events were emitted (one per additional waiter)
        # The last event should show the final coalesced_count of 10
        events = event_capture.get_events_of_type(event_type=RequestCoalescedEvent)
        assert len(events) == 9  # 9 coalesced requests = 9 events
        assert events[-1].coalesced_count == 10  # Final count includes all waiters

    @pytest.mark.asyncio
    async def test_pending_cleanup_on_failure(self) -> None:
        """Test pending entry is cleaned up after failure."""
        coalescer = RequestCoalescer(name="test")

        async def failing_executor():
            raise RuntimeError("Test failure")

        with pytest.raises(RuntimeError):
            await coalescer.execute(key="fail-key", executor=failing_executor)

        # Pending should be empty even after failure (use public property)
        assert coalescer.pending_count == 0

    @pytest.mark.asyncio
    async def test_pending_cleanup_on_success(self) -> None:
        """Test pending entry is cleaned up after success."""
        coalescer = RequestCoalescer(name="test")

        async def executor():
            return "result"

        await coalescer.execute(key="cleanup-key", executor=executor)

        # Pending should be empty (use public property)
        assert coalescer.pending_count == 0

    @pytest.mark.asyncio
    async def test_sequential_requests_same_key(self) -> None:
        """Test sequential requests with same key both execute."""
        event_bus = EventBus()
        observer = MetricsObserver(event_bus=event_bus)
        coalescer = RequestCoalescer(name="test", event_bus=event_bus, interface_id="test-rf")
        execution_count = 0

        async def executor():
            nonlocal execution_count
            execution_count += 1
            return f"result-{execution_count}"

        result1 = await coalescer.execute(key="key", executor=executor)
        result2 = await coalescer.execute(key="key", executor=executor)

        assert result1 == "result-1"
        assert result2 == "result-2"
        assert execution_count == 2

        # Local counters track executed requests
        assert coalescer.total_requests == 2
        assert coalescer.executed_requests == 2
        # No coalescing occurred (sequential requests)
        assert observer.get_counter(key=MetricKeys.coalescer_coalesced(interface_id="test-rf")) == 0

    @pytest.mark.asyncio
    async def test_single_request(self) -> None:
        """Test single request execution."""
        event_bus = EventBus()
        observer = MetricsObserver(event_bus=event_bus)
        coalescer = RequestCoalescer(name="test", event_bus=event_bus, interface_id="test-rf")

        async def executor():
            return "result"

        result = await coalescer.execute(key="test-key", executor=executor)

        assert result == "result"
        # Local counters track request and execution counts
        assert coalescer.total_requests == 1
        assert coalescer.executed_requests == 1
        # No coalescing occurred (single request)
        assert observer.get_counter(key=MetricKeys.coalescer_coalesced(interface_id="test-rf")) == 0
        assert coalescer.pending_count == 0

    @pytest.mark.asyncio
    async def test_waiter_count_tracking(self, event_capture: EventCapture) -> None:
        """Test waiter count is tracked correctly via events."""
        event_bus = EventBus()
        event_capture.subscribe_to(event_bus, RequestCoalescedEvent)

        coalescer = RequestCoalescer(
            name="test",
            event_bus=event_bus,
            interface_id="test-rf",
        )
        execution_started = asyncio.Event()

        async def slow_executor():
            execution_started.set()
            await asyncio.sleep(0.1)
            return "result"

        # Start first request
        task1 = asyncio.create_task(coalescer.execute(key="track-key", executor=slow_executor))

        # Wait for execution to start
        await execution_started.wait()

        # First request starts execution, pending_count should be 1
        assert coalescer.pending_count == 1

        # Add more waiters - this will emit coalesce events
        task2 = asyncio.create_task(coalescer.execute(key="track-key", executor=slow_executor))
        await asyncio.sleep(0.02)  # Give time for task2 to register and event to publish

        # Verify coalescing via event
        event_capture.assert_event_emitted(
            event_type=RequestCoalescedEvent,
            request_key="track-key",
            coalesced_count=2,  # 2 waiters total
        )

        await asyncio.gather(task1, task2)
