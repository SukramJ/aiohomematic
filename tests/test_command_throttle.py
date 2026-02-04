# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for CommandThrottle."""

from __future__ import annotations

import asyncio
import time

import pytest

from aiohomematic.client import CommandThrottle


class TestCommandThrottle:
    """Tests for CommandThrottle."""

    @pytest.mark.asyncio
    async def test_acquire_disabled_returns_immediately(self) -> None:
        """Test acquire returns immediately when throttling is disabled."""
        throttle = CommandThrottle(interface_id="test-rf", interval=0.0)
        start = time.monotonic()
        await throttle.acquire()
        await throttle.acquire()
        await throttle.acquire()
        elapsed = time.monotonic() - start
        # Should complete almost instantly (well under 100ms for 3 calls)
        assert elapsed < 0.1
        assert throttle.throttled_count == 0

    @pytest.mark.asyncio
    async def test_acquire_enforces_interval(self) -> None:
        """Test acquire enforces minimum interval between commands."""
        throttle = CommandThrottle(interface_id="test-rf", interval=0.1)

        start = time.monotonic()
        await throttle.acquire()
        await throttle.acquire()
        await throttle.acquire()
        elapsed = time.monotonic() - start

        # 3 commands with 0.1s interval: first is immediate, 2nd and 3rd wait
        # Should take at least 0.2s (2 * 0.1s intervals)
        assert elapsed >= 0.18  # Allow small tolerance
        assert throttle.throttled_count == 2

    @pytest.mark.asyncio
    async def test_acquire_no_delay_when_interval_elapsed(self) -> None:
        """Test acquire does not delay when sufficient time has passed."""
        throttle = CommandThrottle(interface_id="test-rf", interval=0.05)

        await throttle.acquire()
        # Wait longer than the interval
        await asyncio.sleep(0.1)

        start = time.monotonic()
        await throttle.acquire()
        elapsed = time.monotonic() - start

        # Should return almost instantly since interval already elapsed
        assert elapsed < 0.05
        assert throttle.throttled_count == 0

    @pytest.mark.asyncio
    async def test_concurrent_commands_are_serialized(self) -> None:
        """Test concurrent acquire calls are serialized by the lock."""
        throttle = CommandThrottle(interface_id="test-rf", interval=0.05)

        order: list[int] = []

        async def command(index: int) -> None:
            await throttle.acquire()
            order.append(index)

        # Launch 5 commands concurrently
        tasks = [asyncio.create_task(command(i)) for i in range(5)]
        await asyncio.gather(*tasks)

        # All 5 commands should have executed
        assert len(order) == 5
        # First command is immediate, remaining 4 are delayed
        assert throttle.throttled_count == 4

    @pytest.mark.asyncio
    async def test_concurrent_commands_total_time(self) -> None:
        """Test total time for concurrent commands respects interval."""
        throttle = CommandThrottle(interface_id="test-rf", interval=0.05)

        start = time.monotonic()
        tasks = [asyncio.create_task(throttle.acquire()) for _ in range(5)]
        await asyncio.gather(*tasks)
        elapsed = time.monotonic() - start

        # 5 commands at 0.05s: first immediate, then 4 * 0.05s = 0.2s minimum
        assert elapsed >= 0.18  # Allow small tolerance

    def test_init_disabled(self) -> None:
        """Test initialization with throttling disabled."""
        throttle = CommandThrottle(interface_id="test-rf", interval=0.0)
        assert throttle.is_enabled is False
        assert throttle.interval == 0.0
        assert throttle.throttled_count == 0

    def test_init_enabled(self) -> None:
        """Test initialization with throttling enabled."""
        throttle = CommandThrottle(interface_id="test-rf", interval=0.5)
        assert throttle.is_enabled is True
        assert throttle.interval == 0.5
        assert throttle.throttled_count == 0
