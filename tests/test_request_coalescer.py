"""Tests for RequestCoalescer."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from aiohomematic.client.request_coalescer import CoalescerMetrics, RequestCoalescer

if TYPE_CHECKING:
    pass


class TestCoalescerMetrics:
    """Tests for CoalescerMetrics dataclass."""

    def test_coalesce_rate_calculation(self) -> None:
        """Test coalesce rate calculation."""
        metrics = CoalescerMetrics(
            total_requests=10,
            executed_requests=4,
            coalesced_requests=6,
            failed_requests=0,
        )
        assert metrics.coalesce_rate == 60.0

    def test_coalesce_rate_no_coalescing(self) -> None:
        """Test coalesce rate with no coalescing."""
        metrics = CoalescerMetrics(
            total_requests=10,
            executed_requests=10,
            coalesced_requests=0,
            failed_requests=0,
        )
        assert metrics.coalesce_rate == 0.0

    def test_coalesce_rate_zero_requests(self) -> None:
        """Test coalesce rate with no requests."""
        metrics = CoalescerMetrics()
        assert metrics.coalesce_rate == 0.0

    def test_initial_state(self) -> None:
        """Test initial metrics state."""
        metrics = CoalescerMetrics()
        assert metrics.total_requests == 0
        assert metrics.executed_requests == 0
        assert metrics.coalesced_requests == 0
        assert metrics.failed_requests == 0


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
    async def test_coalesced_requests(self) -> None:
        """Test multiple concurrent requests are coalesced."""
        coalescer = RequestCoalescer(name="test")
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
        assert coalescer.metrics.total_requests == 2
        assert coalescer.metrics.executed_requests == 1
        assert coalescer.metrics.coalesced_requests == 1

    @pytest.mark.asyncio
    async def test_different_keys_not_coalesced(self) -> None:
        """Test requests with different keys are not coalesced."""
        coalescer = RequestCoalescer(name="test")
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
        assert coalescer.metrics.coalesced_requests == 0

    @pytest.mark.asyncio
    async def test_exception_propagated_to_all_waiters(self) -> None:
        """Test exceptions are propagated to all waiting callers."""
        coalescer = RequestCoalescer(name="test")
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

        assert coalescer.metrics.failed_requests == 1
        assert coalescer.pending_count == 0

    def test_init(self) -> None:
        """Test initialization."""
        coalescer = RequestCoalescer(name="test")
        assert coalescer.pending_count == 0
        assert coalescer.metrics.total_requests == 0

    def test_init_default_name(self) -> None:
        """Test initialization with default name."""
        coalescer = RequestCoalescer()
        assert coalescer.pending_count == 0

    @pytest.mark.asyncio
    async def test_many_waiters(self) -> None:
        """Test many concurrent waiters for same key."""
        coalescer = RequestCoalescer(name="test")
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
        assert coalescer.metrics.total_requests == 10
        assert coalescer.metrics.executed_requests == 1
        assert coalescer.metrics.coalesced_requests == 9

    @pytest.mark.asyncio
    async def test_metrics_property(self) -> None:
        """Test metrics property returns current metrics."""
        coalescer = RequestCoalescer(name="test")

        async def executor():
            return "result"

        await coalescer.execute(key="key", executor=executor)

        metrics = coalescer.metrics
        assert metrics.total_requests == 1
        assert metrics.executed_requests == 1

    @pytest.mark.asyncio
    async def test_pending_cleanup_on_failure(self) -> None:
        """Test pending entry is cleaned up after failure."""
        coalescer = RequestCoalescer(name="test")

        async def failing_executor():
            raise RuntimeError("Test failure")

        with pytest.raises(RuntimeError):
            await coalescer.execute(key="fail-key", executor=failing_executor)

        # Pending should be empty even after failure
        assert coalescer.pending_count == 0
        assert "fail-key" not in coalescer._pending

    @pytest.mark.asyncio
    async def test_pending_cleanup_on_success(self) -> None:
        """Test pending entry is cleaned up after success."""
        coalescer = RequestCoalescer(name="test")

        async def executor():
            return "result"

        await coalescer.execute(key="cleanup-key", executor=executor)

        # Pending should be empty
        assert coalescer.pending_count == 0
        assert "cleanup-key" not in coalescer._pending

    @pytest.mark.asyncio
    async def test_sequential_requests_same_key(self) -> None:
        """Test sequential requests with same key both execute."""
        coalescer = RequestCoalescer(name="test")
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
        assert coalescer.metrics.executed_requests == 2
        assert coalescer.metrics.coalesced_requests == 0

    @pytest.mark.asyncio
    async def test_single_request(self) -> None:
        """Test single request execution."""
        coalescer = RequestCoalescer(name="test")

        async def executor():
            return "result"

        result = await coalescer.execute(key="test-key", executor=executor)

        assert result == "result"
        assert coalescer.metrics.total_requests == 1
        assert coalescer.metrics.executed_requests == 1
        assert coalescer.metrics.coalesced_requests == 0
        assert coalescer.pending_count == 0

    @pytest.mark.asyncio
    async def test_waiter_count_tracking(self) -> None:
        """Test waiter count is tracked correctly."""
        coalescer = RequestCoalescer(name="test")
        execution_started = asyncio.Event()

        async def slow_executor():
            execution_started.set()
            await asyncio.sleep(0.1)
            return "result"

        # Start first request
        task1 = asyncio.create_task(coalescer.execute(key="track-key", executor=slow_executor))

        # Wait for execution to start
        await execution_started.wait()

        # Check waiter count after first request
        pending = coalescer._pending.get("track-key")
        assert pending is not None
        assert pending.waiter_count == 1

        # Add more waiters
        task2 = asyncio.create_task(coalescer.execute(key="track-key", executor=slow_executor))
        await asyncio.sleep(0.01)  # Give time for task2 to register

        assert pending.waiter_count == 2

        await asyncio.gather(task1, task2)
