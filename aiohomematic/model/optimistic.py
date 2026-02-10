# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Optimistic value tracking for data points.

Manages the lifecycle of an optimistic value: apply, confirm, and rollback.
Pure state management — no event publishing, logging, or I/O.

Public API of this module is defined by __all__.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import time

__all__ = ["OptimisticValueTracker"]


class OptimisticValueTracker[ParameterT]:
    """Track optimistic value state with rollback support."""

    __slots__ = (
        "_pending_sends",
        "_previous_value",
        "_sent_at",
        "_timeout_handle",
        "_value",
    )

    def __init__(self) -> None:
        """Initialize the tracker with no active optimistic state."""
        self._value: ParameterT | None = None
        self._previous_value: ParameterT | None = None
        self._timeout_handle: asyncio.TimerHandle | None = None
        self._sent_at: float | None = None
        self._pending_sends: int = 0

    @property
    def age(self) -> float | None:
        """Return age of optimistic value in seconds, or None if not active."""
        if self._sent_at is None:
            return None
        return time.monotonic() - self._sent_at

    @property
    def is_active(self) -> bool:
        """Return True if an optimistic value is pending confirmation."""
        return self._value is not None

    @property
    def pending_sends(self) -> int:
        """Return the number of pending send confirmations."""
        return self._pending_sends

    @property
    def previous_value(self) -> ParameterT | None:
        """Return the previous confirmed value captured before optimistic apply."""
        return self._previous_value

    @property
    def value(self) -> ParameterT | None:
        """Return the optimistic value, or None if not active."""
        return self._value

    def apply(self, *, value: ParameterT, current_value: ParameterT | None) -> None:
        """
        Set an optimistic value.

        During bursts (rapid successive sends), only the first send captures
        the previous value for rollback. Subsequent sends overwrite the
        optimistic value but keep the original rollback target.

        Args:
            value: The optimistic value to set.
            current_value: The current confirmed value (captured as rollback target on first send).

        """
        if self._pending_sends == 0:
            self._previous_value = current_value
        self._pending_sends += 1
        self._value = value
        self._sent_at = time.monotonic()

    def cancel_timer(self) -> None:
        """Cancel pending rollback timer if any."""
        if self._timeout_handle:
            self._timeout_handle.cancel()
            self._timeout_handle = None

    def clear(self) -> None:
        """Clear all optimistic state (after confirmation or correction)."""
        self._value = None
        self._previous_value = None
        self._sent_at = None
        self.cancel_timer()

    def confirm_one(self) -> bool:
        """
        Decrement pending sends count for one confirmation.

        Return True if this was the final confirmation (all sends confirmed).
        """
        self._pending_sends = max(0, self._pending_sends - 1)
        return self._pending_sends == 0

    def rollback(self) -> tuple[ParameterT | None, ParameterT | None]:
        """
        Rollback optimistic state and return (rolled_back_value, restored_value).

        Return (None, None) if no optimistic value is active.
        """
        if self._value is None:
            return None, None

        rolled_back_value = self._value
        restored_value = self._previous_value

        self._value = None
        self._sent_at = None
        self._pending_sends = 0
        self.cancel_timer()
        self._previous_value = None

        return rolled_back_value, restored_value

    def schedule_rollback(self, *, timeout: float, callback: Callable[[], None]) -> None:
        """
        Schedule a rollback callback after timeout seconds.

        Cancels any existing timer before scheduling a new one.
        """
        self.cancel_timer()
        loop = asyncio.get_event_loop()
        self._timeout_handle = loop.call_later(timeout, callback)
