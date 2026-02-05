# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Priority-aware command throttle for rate-limiting outgoing device commands.

Overview
--------
CommandThrottle enforces a minimum delay between consecutive device commands
sent to a Homematic backend, with support for three priority levels:

- CRITICAL: Security and access control commands (bypass throttle and queue)
- HIGH: Interactive user commands (normal throttle, high priority)
- LOW: Bulk operations and automations (normal throttle, low priority)

How It Works
------------
1. Each command acquires the throttle with a priority level
2. CRITICAL commands bypass the queue and throttle entirely (<100ms)
3. HIGH/LOW commands are enqueued in a priority queue (heapq)
4. Background worker processes queue with throttle interval
5. Within same priority, FIFO order is maintained

Configuration
-------------
The throttle interval is configured via TimeoutConfig.command_throttle_interval.
A value of 0.0 (the default) disables throttling entirely.

Thread Safety
-------------
CommandThrottle is designed for single-threaded asyncio use.
All operations assume they run in the same event loop.

Public API of this module is defined by __all__.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from enum import IntEnum
import heapq
import logging
import time
from typing import Final

from aiohomematic import i18n
from aiohomematic.exceptions import CommandSupersededError
from aiohomematic.interfaces.client import CommandThrottleProtocol

__all__ = ["CommandThrottle", "CommandPriority", "PrioritizedCommand"]

_LOGGER: Final = logging.getLogger(__name__)


class CommandPriority(IntEnum):
    """
    Command priority levels.

    Lower numeric value = higher priority in queue.
    """

    CRITICAL = 0  # Security, access control - bypass throttle
    HIGH = 1  # Interactive user commands - normal throttle
    LOW = 2  # Bulk operations, automations - normal throttle


@dataclass(frozen=True, order=True)
class PrioritizedCommand:
    """
    Command wrapper for priority queue.

    Ordering:
    1. Priority (CRITICAL < HIGH < LOW)
    2. Timestamp (FIFO within same priority)
    """

    priority: CommandPriority = field(compare=True)
    timestamp: float = field(compare=True)
    future: asyncio.Future[None] = field(compare=False, repr=False)
    device_address: str = field(compare=False)


class CommandThrottle(CommandThrottleProtocol):
    """
    Priority-aware rate-limiter for device commands.

    Features:
    - Three priority levels (CRITICAL, HIGH, LOW)
    - CRITICAL commands bypass throttle and queue
    - HIGH/LOW commands respect throttle interval and queue
    - Per-interface throttling to reduce RF duty cycle
    - Background worker processes queue continuously
    """

    __slots__ = (
        "_burst_count",
        "_burst_threshold",
        "_burst_timestamps",
        "_burst_window",
        "_critical_count",
        "_interface_id",
        "_interval",
        "_last_command_time",
        "_lock",
        "_purged_count",
        "_queue",
        "_stopped",
        "_throttled_count",
        "_worker_task",
    )

    def __init__(
        self,
        *,
        interface_id: str,
        interval: float,
        burst_threshold: int = 5,
        burst_window: float = 0.5,
    ) -> None:
        """
        Initialize priority-aware command throttle.

        Args:
            interface_id: Interface identifier (e.g., "HmIP-RF")
            interval: Minimum delay between commands in seconds (0.0 = disabled)
            burst_threshold: Number of commands within burst_window that triggers burst
                detection (0 = disabled)
            burst_window: Time window in seconds for burst detection

        """
        self._interface_id: Final = interface_id
        self._interval: Final = interval
        self._last_command_time: float = 0.0
        self._queue: list[PrioritizedCommand] = []
        self._lock: Final = asyncio.Lock()
        self._stopped: bool = False

        # Burst detection
        self._burst_threshold: Final = burst_threshold
        self._burst_window: Final = burst_window
        self._burst_timestamps: deque[float] = deque()

        # Statistics
        self._throttled_count: int = 0
        self._critical_count: int = 0
        self._burst_count: int = 0
        self._purged_count: int = 0

        # Start background worker if throttling enabled
        self._worker_task: asyncio.Task[None] | None = None
        if self._interval > 0.0:
            self._worker_task = asyncio.create_task(
                self._worker(),
                name=f"CommandThrottle-{interface_id}",
            )

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"CommandThrottle(interface={self._interface_id}, "
            f"interval={self._interval:.3f}s, "
            f"queue_size={self.queue_size}, "
            f"throttled={self._throttled_count}, "
            f"critical={self._critical_count}, "
            f"burst={self._burst_count}, "
            f"purged={self._purged_count})"
        )

    @property
    def burst_count(self) -> int:
        """Return number of burst downgrades."""
        return self._burst_count

    @property
    def burst_threshold(self) -> int:
        """Return configured burst threshold."""
        return self._burst_threshold

    @property
    def burst_window(self) -> float:
        """Return configured burst window in seconds."""
        return self._burst_window

    @property
    def critical_count(self) -> int:
        """Return number of critical commands that bypassed throttle."""
        return self._critical_count

    @property
    def interface_id(self) -> str:
        """Return interface identifier."""
        return self._interface_id

    @property
    def interval(self) -> float:
        """Return throttle interval in seconds."""
        return self._interval

    @property
    def is_enabled(self) -> bool:
        """Return True if throttling is active."""
        return self._interval > 0.0

    @property
    def purged_count(self) -> int:
        """Return number of purged commands."""
        return self._purged_count

    @property
    def queue_size(self) -> int:
        """Return current queue size."""
        return len(self._queue)

    @property
    def throttled_count(self) -> int:
        """Return number of throttled commands (statistics)."""
        return self._throttled_count

    async def acquire(
        self,
        *,
        priority: CommandPriority = CommandPriority.HIGH,
        device_address: str = "",
        purge_addresses: frozenset[str] = frozenset(),
    ) -> None:
        """
        Acquire permission to send device command with priority.

        Args:
            priority: Command priority level
            device_address: Device address (for logging/debugging)
            purge_addresses: Channel addresses to purge from queue (for CRITICAL commands)

        Behavior:
        - Throttling disabled (interval=0.0): Return immediately
        - CRITICAL priority: Purge matching queue entries, bypass queue and throttle
        - HIGH priority during burst: Downgraded to LOW, then enqueued
        - HIGH/LOW priority: Enqueue and wait for worker to grant permission

        Raises:
            asyncio.CancelledError: If throttle is stopped while waiting

        """
        # Throttling disabled
        if not self._interval:
            return

        # CRITICAL commands bypass everything
        if priority == CommandPriority.CRITICAL:
            self._critical_count += 1
            if purge_addresses:
                await self._purge_commands(purge_addresses=purge_addresses)
            _LOGGER.debug(
                "COMMAND_THROTTLE[%s]: CRITICAL command bypassing queue (device=%s)",
                self._interface_id,
                device_address,
            )
            return

        # Burst detection: downgrade HIGH → LOW when burst detected
        if priority == CommandPriority.HIGH and self._detect_burst():
            self._burst_count += 1
            _LOGGER.info(
                i18n.tr(
                    key="log.client.command_throttle.burst_downgrade",
                    interface_id=self._interface_id,
                    device_address=device_address,
                    count=len(self._burst_timestamps),
                    window=self._burst_window,
                )
            )
            priority = CommandPriority.LOW

        # Check if stopped
        if self._stopped:
            raise asyncio.CancelledError(i18n.tr(key="log.client.command_throttle.stopped"))

        # HIGH/LOW commands go through priority queue
        future: asyncio.Future[None] = asyncio.Future()
        cmd = PrioritizedCommand(
            priority=priority,
            timestamp=time.monotonic(),
            future=future,
            device_address=device_address,
        )

        # Enqueue command
        async with self._lock:
            heapq.heappush(self._queue, cmd)
            queue_size = len(self._queue)

        _LOGGER.debug(
            "COMMAND_THROTTLE[%s]: Enqueued %s command (device=%s, queue_size=%d)",
            self._interface_id,
            priority.name,
            device_address,
            queue_size,
        )

        # Wait for worker to grant permission
        await future

    def stop(self) -> None:
        """Stop background worker and reject pending commands."""
        if self._stopped:
            return

        _LOGGER.info(i18n.tr(key="log.client.command_throttle.stopping_worker", interface_id=self._interface_id))
        self._stopped = True

        # Cancel worker task
        if self._worker_task:
            self._worker_task.cancel()

        # Reject all pending commands
        while self._queue:
            cmd = heapq.heappop(self._queue)
            if not cmd.future.done():
                cmd.future.set_exception(asyncio.CancelledError(i18n.tr(key="log.client.command_throttle.stopped")))

    def _detect_burst(self) -> bool:
        """Detect command burst using sliding window."""
        if not self._burst_threshold:
            return False

        now = time.monotonic()
        self._burst_timestamps.append(now)

        # Evict old entries
        cutoff = now - self._burst_window
        while self._burst_timestamps and self._burst_timestamps[0] < cutoff:
            self._burst_timestamps.popleft()

        return len(self._burst_timestamps) > self._burst_threshold

    async def _purge_commands(self, *, purge_addresses: frozenset[str]) -> None:
        """Cancel and remove pending commands matching any of the given channel addresses."""
        async with self._lock:
            remaining: list[PrioritizedCommand] = []
            purged_count = 0

            for cmd in self._queue:
                if cmd.device_address in purge_addresses:
                    if not cmd.future.done():
                        cmd.future.set_exception(
                            CommandSupersededError(f"Superseded by CRITICAL command (channel group: {purge_addresses})")
                        )
                    purged_count += 1
                else:
                    remaining.append(cmd)

            if purged_count:
                self._queue = remaining
                heapq.heapify(self._queue)
                self._purged_count += purged_count
                _LOGGER.info(
                    i18n.tr(
                        key="log.client.command_throttle.purged_commands",
                        interface_id=self._interface_id,
                        purged_count=purged_count,
                    )
                )

    async def _worker(self) -> None:
        """
        Background worker that processes queue with throttling.

        Worker Loop:
        1. Wait for commands in queue
        2. Pop highest priority command
        3. Apply throttle delay if needed
        4. Grant permission (resolve future)
        5. Repeat
        """
        _LOGGER.info(
            i18n.tr(
                key="log.client.command_throttle.worker_started",
                interface_id=self._interface_id,
                interval=self._interval,
            )
        )

        while not self._stopped:
            try:
                # Wait for commands
                while not self._queue and not self._stopped:  # noqa: ASYNC110
                    await asyncio.sleep(0.1)

                # Check if stopped (can be set asynchronously during sleep)
                if self._stopped:
                    break  # type: ignore[unreachable]  # mypy doesn't track async state changes

                # Pop highest priority command (FIFO within priority)
                async with self._lock:
                    if not self._queue:
                        continue
                    cmd = heapq.heappop(self._queue)
                    queue_size = len(self._queue)

                # Apply throttle delay if needed
                if (elapsed := time.monotonic() - self._last_command_time) < self._interval:
                    delay = self._interval - elapsed
                    self._throttled_count += 1

                    _LOGGER.debug(
                        "COMMAND_THROTTLE[%s]: Delaying %s command by %.3fs (device=%s, queue_size=%d)",
                        self._interface_id,
                        cmd.priority.name,
                        delay,
                        cmd.device_address,
                        queue_size,
                    )

                    await asyncio.sleep(delay)

                # Update timestamp and grant permission
                self._last_command_time = time.monotonic()

                if not cmd.future.done():
                    cmd.future.set_result(None)

            except asyncio.CancelledError:
                _LOGGER.info(
                    i18n.tr(key="log.client.command_throttle.worker_cancelled", interface_id=self._interface_id)
                )
                break

            except Exception:
                _LOGGER.exception(
                    i18n.tr(key="log.client.command_throttle.worker_error", interface_id=self._interface_id)
                )

        _LOGGER.info(i18n.tr(key="log.client.command_throttle.worker_stopped", interface_id=self._interface_id))
