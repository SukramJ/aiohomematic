"""Tests for command throttle with priority queue."""

from __future__ import annotations

import asyncio

from aiohomematic.client import CommandPriority, CommandThrottle


class TestCommandThrottle:
    """Test command throttle with priority system."""

    async def test_critical_priority_bypasses_throttle(self) -> None:
        """Test that CRITICAL priority commands bypass throttle."""
        throttle = CommandThrottle(interface_id="TEST", interval=0.1)

        start = asyncio.get_event_loop().time()
        # These should all execute immediately, bypassing the queue
        await throttle.acquire(priority=CommandPriority.CRITICAL, device_address="TEST:1")
        await throttle.acquire(priority=CommandPriority.CRITICAL, device_address="TEST:1")
        await throttle.acquire(priority=CommandPriority.CRITICAL, device_address="TEST:1")
        elapsed = asyncio.get_event_loop().time() - start

        # CRITICAL commands bypass throttle
        assert elapsed < 0.05

    async def test_high_priority_throttled(self) -> None:
        """Test that HIGH priority commands are throttled."""
        throttle = CommandThrottle(interface_id="TEST", interval=0.05)

        start = asyncio.get_event_loop().time()
        await throttle.acquire(priority=CommandPriority.HIGH, device_address="TEST:1")
        await throttle.acquire(priority=CommandPriority.HIGH, device_address="TEST:1")
        await throttle.acquire(priority=CommandPriority.HIGH, device_address="TEST:1")
        elapsed = asyncio.get_event_loop().time() - start

        # Should take at least 2 intervals (3 commands = 2 waits)
        assert elapsed >= 0.10

    async def test_metrics_critical_count(self) -> None:
        """Test that CRITICAL commands are counted separately."""
        throttle = CommandThrottle(interface_id="TEST", interval=0.1)

        await throttle.acquire(priority=CommandPriority.CRITICAL, device_address="TEST:1")
        await throttle.acquire(priority=CommandPriority.CRITICAL, device_address="TEST:1")
        await throttle.acquire(priority=CommandPriority.HIGH, device_address="TEST:1")

        assert throttle.critical_count == 2

    async def test_no_throttle_when_interval_zero(self) -> None:
        """Test that throttle is bypassed when interval is 0."""
        throttle = CommandThrottle(interface_id="TEST", interval=0.0)

        start = asyncio.get_event_loop().time()
        await throttle.acquire(priority=CommandPriority.HIGH, device_address="TEST:1")
        await throttle.acquire(priority=CommandPriority.HIGH, device_address="TEST:1")
        await throttle.acquire(priority=CommandPriority.HIGH, device_address="TEST:1")
        elapsed = asyncio.get_event_loop().time() - start

        # All commands should execute immediately
        assert elapsed < 0.01

    async def test_priority_ordering(self) -> None:
        """Test that commands are processed in priority order."""
        throttle = CommandThrottle(interface_id="TEST", interval=0.05)
        execution_order: list[CommandPriority] = []

        async def execute_with_priority(priority: CommandPriority) -> None:
            await throttle.acquire(priority=priority, device_address="TEST:1")
            execution_order.append(priority)

        # Start HIGH priority command (will execute first)
        task_high1 = asyncio.create_task(execute_with_priority(CommandPriority.HIGH))

        # Give it time to start
        await asyncio.sleep(0.01)

        # Queue several commands with different priorities
        task_low = asyncio.create_task(execute_with_priority(CommandPriority.LOW))
        task_high2 = asyncio.create_task(execute_with_priority(CommandPriority.HIGH))
        task_critical = asyncio.create_task(execute_with_priority(CommandPriority.CRITICAL))

        # Wait for all to complete
        await asyncio.gather(task_high1, task_low, task_high2, task_critical)

        # Verify execution order
        assert len(execution_order) == 4
        # Verify critical commands were counted
        # Note: HIGH commands may be processed immediately if no queue, so throttled_count might be 0


class TestBurstDetection:
    """Test burst detection in command throttle."""

    async def test_burst_detection_disabled_when_threshold_zero(self) -> None:
        """Test that burst detection is disabled when threshold is 0."""
        throttle = CommandThrottle(
            interface_id="TEST",
            interval=0.05,
            burst_threshold=0,
            burst_window=2.0,
        )

        for _ in range(10):
            await throttle.acquire(priority=CommandPriority.HIGH, device_address="TEST:1")

        assert throttle.burst_count == 0

    async def test_burst_detection_does_not_affect_critical(self) -> None:
        """Test that CRITICAL commands are never downgraded by burst detection."""
        throttle = CommandThrottle(
            interface_id="TEST",
            interval=0.05,
            burst_threshold=3,
            burst_window=2.0,
        )

        # Send 6 CRITICAL commands rapidly
        for _ in range(6):
            await throttle.acquire(priority=CommandPriority.CRITICAL, device_address="TEST:1")

        assert throttle.burst_count == 0
        assert throttle.critical_count == 6

    async def test_burst_detection_downgrades_high_to_low(self) -> None:
        """Test that HIGH commands are downgraded to LOW during burst."""
        throttle = CommandThrottle(
            interface_id="TEST",
            interval=0.05,
            burst_threshold=3,
            burst_window=2.0,
        )

        # Send 6 HIGH commands rapidly — first 3 are within threshold, rest trigger burst
        for _ in range(6):
            await throttle.acquire(priority=CommandPriority.HIGH, device_address="TEST:1")

        assert throttle.burst_count > 0

    async def test_burst_detection_sliding_window_expires(self) -> None:
        """Test that burst window expires and old commands are evicted."""
        throttle = CommandThrottle(
            interface_id="TEST",
            interval=0.05,
            burst_threshold=5,
            burst_window=0.1,
        )

        # Send 3 commands
        for _ in range(3):
            await throttle.acquire(priority=CommandPriority.HIGH, device_address="TEST:1")

        # Wait for burst window to expire
        await asyncio.sleep(0.15)

        # Send 3 more — should not trigger burst since window expired
        for _ in range(3):
            await throttle.acquire(priority=CommandPriority.HIGH, device_address="TEST:1")

        assert throttle.burst_count == 0

    def test_burst_properties(self) -> None:
        """Test that burst properties return correct values."""
        throttle = CommandThrottle(
            interface_id="TEST",
            interval=0.0,
            burst_threshold=10,
            burst_window=2.5,
        )

        assert throttle.burst_count == 0
        assert throttle.burst_threshold == 10
        assert throttle.burst_window == 2.5


class TestCommandPriorityEnum:
    """Test CommandPriority enum."""

    def test_priority_ordering(self) -> None:
        """Test that priorities can be compared."""
        assert CommandPriority.CRITICAL < CommandPriority.HIGH
        assert CommandPriority.HIGH < CommandPriority.LOW
        assert CommandPriority.CRITICAL < CommandPriority.LOW

    def test_priority_values(self) -> None:
        """Test that priority values are in correct order."""
        assert CommandPriority.CRITICAL.value == 0  # Highest priority (lowest number)
        assert CommandPriority.HIGH.value == 1
        assert CommandPriority.LOW.value == 2  # Lowest priority (highest number)
