# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Command throttle for rate-limiting outgoing device commands.

Overview
--------
CommandThrottle enforces a minimum delay between consecutive device commands
sent to a Homematic backend.  This reduces RF duty-cycle usage and lowers the
probability of packet loss when multiple devices are addressed in rapid
succession on the same 868 MHz interface.

How It Works
------------
1. Each ``set_value`` / ``put_paramset`` call acquires the throttle before
   sending the command to the backend.
2. If the minimum interval has not elapsed since the last command, the caller
   is suspended (``asyncio.sleep``) for the remaining time.
3. An ``asyncio.Lock`` serialises access so that only one command is in-flight
   at a time when throttling is active.

Configuration
-------------
The throttle interval is configured via ``TimeoutConfig.command_throttle_interval``.
A value of ``0.0`` (the default) disables throttling entirely – the lock is never
acquired and no delay is introduced.

Thread Safety
-------------
CommandThrottle is designed for single-threaded asyncio use.
All operations assume they run in the same event loop.

Public API of this module is defined by __all__.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Final

__all__ = ["CommandThrottle"]

_LOGGER: Final = logging.getLogger(__name__)


class CommandThrottle:
    """
    Rate-limiter for outgoing device commands on a single interface.

    Ensures a configurable minimum interval between consecutive ``set_value``
    and ``put_paramset`` calls to reduce RF contention and duty-cycle usage.
    """

    __slots__ = (
        "_interface_id",
        "_interval",
        "_last_command_time",
        "_lock",
        "_throttled_count",
    )

    def __init__(
        self,
        *,
        interface_id: str,
        interval: float,
    ) -> None:
        """
        Initialize the command throttle.

        Args:
            interface_id: Interface identifier for logging.
            interval: Minimum seconds between consecutive commands.
                      Use 0.0 to disable throttling.

        """
        self._interface_id: Final = interface_id
        self._interval: Final = interval
        self._lock: Final[asyncio.Lock] = asyncio.Lock()
        self._last_command_time: float = 0.0
        self._throttled_count: int = 0

    @property
    def interval(self) -> float:
        """Return the configured throttle interval in seconds."""
        return self._interval

    @property
    def is_enabled(self) -> bool:
        """Return True if throttling is active."""
        return self._interval > 0.0

    @property
    def throttled_count(self) -> int:
        """Return the number of commands that were delayed by the throttle."""
        return self._throttled_count

    async def acquire(self) -> None:
        """
        Acquire permission to send the next device command.

        If the minimum interval has not yet elapsed since the previous command,
        this coroutine sleeps for the remaining time.  When throttling is
        disabled (interval == 0.0) the method returns immediately.
        """
        if not self._interval:
            return

        async with self._lock:
            if (elapsed := time.monotonic() - self._last_command_time) < self._interval:
                delay = self._interval - elapsed
                self._throttled_count += 1
                _LOGGER.debug(
                    "COMMAND_THROTTLE[%s]: Delaying command by %.3fs (throttled_count=%d)",
                    self._interface_id,
                    delay,
                    self._throttled_count,
                )
                await asyncio.sleep(delay)
            self._last_command_time = time.monotonic()
