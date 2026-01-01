# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Request coalescing for efficient RPC call deduplication.

Overview
--------
RequestCoalescer merges identical concurrent requests into a single backend call.
When multiple callers request the same data simultaneously (e.g., during device
discovery), only one actual RPC call is made and all callers receive the result.

This is particularly beneficial for:
- Device discovery (multiple getParamsetDescription calls for same device type)
- Bulk operations that may request overlapping data
- Any scenario where parallel identical requests would waste bandwidth

How It Works
------------
1. First request for a key starts execution and registers a Future
2. Subsequent requests for the same key await the existing Future
3. When execution completes, all waiters receive the result (or exception)
4. The pending entry is cleaned up for future requests

    Request A (key="X") ──┬──> Execute ──> Result
                          │
    Request B (key="X") ──┤               │
                          │               │
    Request C (key="X") ──┴───────────────┴──> All receive Result

Example Usage
-------------
    from aiohomematic.client import RequestCoalescer

    coalescer = RequestCoalescer()

    async def get_paramset(address: str, key: str) -> dict:
        return await coalescer.execute(
            key=f"getParamset:{address}:{key}",
            executor=lambda: client.getParamset(address, key),
        )

Thread Safety
-------------
RequestCoalescer is designed for single-threaded asyncio use.
All operations assume they run in the same event loop.

"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
import logging
from typing import TYPE_CHECKING, Any, Final, TypeVar, cast

if TYPE_CHECKING:
    from aiohomematic.central.events import EventBus

_LOGGER: Final = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass(slots=True)
class _PendingRequest:
    """Internal tracking for a pending request."""

    future: asyncio.Future[Any]
    created_at: datetime = field(default_factory=datetime.now)
    waiter_count: int = 1


class RequestCoalescer:
    """
    Coalesce identical concurrent requests into a single execution.

    When multiple callers request the same operation simultaneously,
    only one actual call is made and all callers receive the result.
    This significantly reduces backend load during bulk operations.
    """

    def __init__(
        self,
        *,
        name: str = "coalescer",
        event_bus: EventBus | None = None,
        interface_id: str | None = None,
    ) -> None:
        """
        Initialize the request coalescer.

        Args:
        ----
            name: Name for logging identification
            event_bus: Optional event bus for emitting coalesce events
            interface_id: Optional interface ID for event context

        """
        self._name: Final = name
        self._event_bus = event_bus
        self._interface_id = interface_id or name
        self._pending: dict[str, _PendingRequest] = {}

    @property
    def pending_count(self) -> int:
        """Return the number of pending requests."""
        return len(self._pending)

    def clear(self) -> None:
        """
        Clear all pending requests.

        Warning: This will cancel any pending futures. Use with caution,
        typically only during shutdown.
        """
        for _key, pending in list(self._pending.items()):
            if not pending.future.done():
                pending.future.cancel()
        self._pending.clear()
        _LOGGER.debug("COALESCER[%s]: Cleared all pending requests", self._name)

    async def execute(
        self,
        *,
        key: str,
        executor: Callable[[], Awaitable[T]],
    ) -> T:
        """
        Execute a request or wait for an identical pending request.

        If a request with the same key is already in progress, this call
        will wait for that request to complete and return its result.
        Otherwise, it executes the request and shares the result with
        any other callers that arrive while execution is in progress.

        Args:
        ----
            key: Unique key identifying the request (e.g., "method:arg1:arg2")
            executor: Async callable that performs the actual request

        Returns:
        -------
            The result of the request execution

        Raises:
        ------
            Any exception raised by the executor is propagated to all waiters

        """
        self._emit_request_counter()

        # Check if there's already a pending request for this key
        if key in self._pending:
            pending = self._pending[key]
            pending.waiter_count += 1
            self._emit_coalesced_counter()
            _LOGGER.debug(
                "COALESCER[%s]: Coalescing request for key=%s (waiters=%d)",
                self._name,
                key,
                pending.waiter_count,
            )
            # Emit coalesce event
            self._emit_coalesce_event(key=key, coalesced_count=pending.waiter_count)
            return cast(T, await pending.future)

        # Create a new pending request
        loop = asyncio.get_running_loop()
        future: asyncio.Future[T] = loop.create_future()
        self._pending[key] = _PendingRequest(future=future)

        _LOGGER.debug(
            "COALESCER[%s]: Executing request for key=%s",
            self._name,
            key,
        )

        try:
            self._emit_execute_counter()
            result = await executor()
            future.set_result(result)
        except Exception as exc:
            self._emit_failure_counter()
            future.set_exception(exc)
            raise
        else:
            return result
        finally:
            # Clean up the pending entry
            del self._pending[key]

    def _emit_coalesce_event(self, *, key: str, coalesced_count: int) -> None:
        """
        Emit a request coalesced event.

        Args:
        ----
            key: The request key that was coalesced
            coalesced_count: Total number of waiters for this key

        """
        if self._event_bus is None:
            return

        # Import here to avoid circular dependency
        from aiohomematic.central.events import RequestCoalescedEvent  # noqa: PLC0415

        self._event_bus.publish_sync(
            event=RequestCoalescedEvent(
                timestamp=datetime.now(),
                request_key=key,
                coalesced_count=coalesced_count,
                interface_id=self._interface_id,
            )
        )

    def _emit_coalesced_counter(self) -> None:
        """Emit a counter for coalesced requests."""
        if self._event_bus is None:
            return
        from aiohomematic.metrics import MetricKeys, emit_counter  # noqa: PLC0415

        emit_counter(
            event_bus=self._event_bus,
            key=MetricKeys.coalescer_coalesced(interface_id=self._interface_id),
        )

    def _emit_execute_counter(self) -> None:
        """Emit a counter for executed requests."""
        if self._event_bus is None:
            return
        from aiohomematic.metrics import MetricKeys, emit_counter  # noqa: PLC0415

        emit_counter(
            event_bus=self._event_bus,
            key=MetricKeys.coalescer_execute(interface_id=self._interface_id),
        )

    def _emit_failure_counter(self) -> None:
        """Emit a counter for failed requests."""
        if self._event_bus is None:
            return
        from aiohomematic.metrics import MetricKeys, emit_counter  # noqa: PLC0415

        emit_counter(
            event_bus=self._event_bus,
            key=MetricKeys.coalescer_failure(interface_id=self._interface_id),
        )

    def _emit_request_counter(self) -> None:
        """Emit a counter for total requests."""
        if self._event_bus is None:
            return
        from aiohomematic.metrics import MetricKeys, emit_counter  # noqa: PLC0415

        emit_counter(
            event_bus=self._event_bus,
            key=MetricKeys.coalescer_request(interface_id=self._interface_id),
        )


def make_coalesce_key(*, method: str, args: tuple[Any, ...]) -> str:
    """
    Create a coalescing key from method name and arguments.

    This helper creates a consistent key format for use with RequestCoalescer.

    Args:
    ----
        method: The RPC method name
        args: The method arguments

    Returns:
    -------
        A string key suitable for coalescing

    Example:
    -------
        key = make_coalesce_key(method="getParamset", args=("VCU001:1", "VALUES"))
        # Returns: "getParamset:VCU001:1:VALUES"

    """
    # Convert args to strings, handling special types
    arg_strs = []
    for arg in args:
        if isinstance(arg, dict):
            # Sort dict items for consistent hashing
            arg_strs.append(str(sorted(arg.items())))
        else:
            arg_strs.append(str(arg))
    return f"{method}:{':'.join(arg_strs)}"
