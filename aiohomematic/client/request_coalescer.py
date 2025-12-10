# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
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
    from aiohomematic.client.request_coalescer import RequestCoalescer

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
from typing import Any, Final, TypeVar, cast

_LOGGER: Final = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass(slots=True)
class CoalescerMetrics:
    """Metrics for monitoring coalescer effectiveness."""

    total_requests: int = 0
    """Total number of requests received."""

    executed_requests: int = 0
    """Number of requests that actually executed (not coalesced)."""

    coalesced_requests: int = 0
    """Number of requests that were coalesced (avoided execution)."""

    failed_requests: int = 0
    """Number of requests that failed."""

    @property
    def coalesce_rate(self) -> float:
        """Return the percentage of requests that were coalesced."""
        if self.total_requests == 0:
            return 0.0
        return (self.coalesced_requests / self.total_requests) * 100


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

    def __init__(self, *, name: str = "coalescer") -> None:
        """
        Initialize the request coalescer.

        Args:
        ----
            name: Name for logging identification

        """
        self._name: Final = name
        self._pending: dict[str, _PendingRequest] = {}
        self._metrics: CoalescerMetrics = CoalescerMetrics()

    @property
    def metrics(self) -> CoalescerMetrics:
        """Return current metrics."""
        return self._metrics

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
        self._metrics.total_requests += 1

        # Check if there's already a pending request for this key
        if key in self._pending:
            pending = self._pending[key]
            pending.waiter_count += 1
            self._metrics.coalesced_requests += 1
            _LOGGER.debug(
                "COALESCER[%s]: Coalescing request for key=%s (waiters=%d)",
                self._name,
                key,
                pending.waiter_count,
            )
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
            self._metrics.executed_requests += 1
            result = await executor()
            future.set_result(result)
        except Exception as exc:
            self._metrics.failed_requests += 1
            future.set_exception(exc)
            raise
        else:
            return result
        finally:
            # Clean up the pending entry
            del self._pending[key]


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
