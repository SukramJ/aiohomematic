# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Event Bus for decoupled event handling in aiohomematic.

Overview
--------
This module provides a type-safe, async-first event bus that replaces the various
callback dictionaries scattered throughout CentralUnit. It supports:

- Type-safe event subscription and publishing
- Async and sync callback handlers
- Automatic error isolation (one handler failure doesn't affect others)
- Unsubscription via returned callable
- Event filtering and debugging
- Handler priority levels (CRITICAL, HIGH, NORMAL, LOW)
- Batch event publishing for performance optimization

Design Philosophy
-----------------
Instead of multiple callback dictionaries with different signatures, we use:
1. A base Event class with concrete event types (dataclasses)
2. Generic subscription by event type
3. Async-first design with sync compatibility
4. Clear separation of concerns

Public API
----------
- EventBus: Main event bus class for subscription and publishing
- EventBatch: Context manager for batch event publishing
- EventPriority: Enum for handler priority levels
- Event: Base class for all events
- Various event types: DataPointUpdatedEvent, DeviceUpdatedEvent, etc.

Example Usage
-------------
    from aiohomematic.central.event_bus import (
        EventBus,
        EventBatch,
        EventPriority,
        DataPointUpdatedEvent,
    )
    from aiohomematic.const import DataPointKey, ParamsetKey

    bus = EventBus()

    # Subscribe with default priority (note: event is keyword-only)
    async def on_data_point_updated(*, event: DataPointUpdatedEvent) -> None:
        print(f"DataPoint {event.dpk} updated to {event.value}")

    unsubscribe = bus.subscribe(
        event_type=DataPointUpdatedEvent,
        event_key=None,
        handler=on_data_point_updated,
    )

    # Subscribe with high priority (called before normal handlers)
    unsubscribe_high = bus.subscribe(
        event_type=DataPointUpdatedEvent,
        event_key=None,
        handler=on_data_point_updated,
        priority=EventPriority.HIGH,
    )

    # Publish single event
    await bus.publish(event=DataPointUpdatedEvent(
        timestamp=datetime.now(),
        dpk=DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        ),
        value=True,
        received_at=datetime.now(),
    ))

    # Batch publish multiple events (more efficient)
    async with EventBatch(bus=bus) as batch:
        batch.add(event=DeviceUpdatedEvent(timestamp=now, device_address="VCU001"))
        batch.add(event=DeviceUpdatedEvent(timestamp=now, device_address="VCU002"))
        # Events are published when context exits

    # Unsubscribe when done
    unsubscribe()

"""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from collections import defaultdict
from collections.abc import Coroutine, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
import logging
import types
from typing import TYPE_CHECKING, Any, Final, Protocol, TypeVar

from aiohomematic.const import DataPointKey, ParamsetKey
from aiohomematic.type_aliases import UnsubscribeCallback

if TYPE_CHECKING:
    from typing import Self

    from aiohomematic.interfaces.operations import TaskScheduler

_LOGGER = logging.getLogger(__name__)

# Type variables for generic event handling
T_Event = TypeVar("T_Event", bound="Event")


class EventPriority(IntEnum):
    """
    Priority levels for event handlers.

    Higher priority handlers are called before lower priority handlers.
    Handlers with the same priority are called in subscription order.

    Use priorities sparingly - most handlers should use NORMAL priority.
    Reserve CRITICAL for handlers that must run before all others (e.g., logging, metrics).
    Reserve LOW for handlers that should run after all others (e.g., cleanup, notifications).
    """

    LOW = 0
    """Lowest priority - runs after all other handlers."""

    NORMAL = 50
    """Default priority for most handlers."""

    HIGH = 100
    """Higher priority - runs before NORMAL handlers."""

    CRITICAL = 200
    """Highest priority - runs before all other handlers (e.g., logging, metrics)."""


# Event handler protocols - handlers receive event as keyword-only argument
class SyncEventHandler(Protocol):
    """Protocol for synchronous event handlers with keyword-only event parameter."""

    def __call__(self, *, event: Any) -> None:
        """Handle event synchronously."""


class AsyncEventHandler(Protocol):
    """Protocol for asynchronous event handlers with keyword-only event parameter."""

    def __call__(self, *, event: Any) -> Coroutine[Any, Any, None]:
        """Handle event asynchronously."""


EventHandler = SyncEventHandler | AsyncEventHandler


@dataclass(slots=True)
class _PrioritizedHandler:
    """Internal wrapper for handlers with priority information."""

    handler: EventHandler
    priority: EventPriority
    order: int  # Insertion order for stable sorting within same priority


@dataclass(frozen=True, slots=True)
class Event(ABC):
    """
    Base class for all events in the EventBus.

    All events are immutable dataclasses with slots for memory efficiency.
    The timestamp field is included in all events for debugging and auditing.
    A key must be provided to uniquely identify the event.
    """

    timestamp: datetime

    @property
    @abstractmethod
    def key(self) -> Any:
        """Key identifier for this event."""


@dataclass(frozen=True, slots=True)
class DataPointUpdatedEvent(Event):
    """
    Fired when a data point value is updated from the backend.

    Key is the DataPointKey.

    The dpk (DataPointKey) contains:
    - interface_id: Interface identifier (e.g., "BidCos-RF")
    - channel_address: Full channel address (e.g., "VCU0000001:1")
    - paramset_key: Paramset type (e.g., ParamsetKey.VALUES)
    - parameter: Parameter name (e.g., "STATE")
    """

    dpk: DataPointKey
    value: Any
    received_at: datetime

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return self.dpk


@dataclass(frozen=True, slots=True)
class BackendParameterEvent(Event):
    """
    Raw parameter update event from backend (re-published from RPC callbacks).

    Key is DataPointKey(
                interface_id=self.interface_id,
                channel_address=self.channel_address,
                paramset_key=ParamsetKey.VALUES,
                parameter=self.parameter,
            )
    """

    interface_id: str
    channel_address: str
    parameter: str
    value: Any

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return DataPointKey(
            interface_id=self.interface_id,
            channel_address=self.channel_address,
            paramset_key=ParamsetKey.VALUES,
            parameter=self.parameter,
        )


@dataclass(frozen=True, slots=True)
class SysvarUpdatedEvent(Event):
    """
    System variable value updated.

    Key is the state path.
    """

    state_path: str
    value: Any
    received_at: datetime

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return self.state_path


@dataclass(frozen=True, slots=True)
class DeviceUpdatedEvent(Event):
    """
    Device state has been updated.

    Key is device_address.
    """

    device_address: str

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return self.device_address


@dataclass(frozen=True, slots=True)
class FirmwareUpdatedEvent(Event):
    """
    Device firmware information has been updated.

    Key is device_address.
    """

    device_address: str

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return self.device_address


@dataclass(frozen=True, slots=True)
class LinkPeerChangedEvent(Event):
    """
    Channel link peer addresses have changed.

    Key is channel_address.
    """

    channel_address: str

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return self.channel_address


@dataclass(frozen=True, slots=True)
class DataPointUpdatedCallbackEvent(Event):
    """
    Data point value updated callback event.

    Key is unique_id.

    This event is fired when a data point's value changes and external
    consumers (like Home Assistant entities) need to be notified.
    Unlike DataPointUpdatedEvent which handles internal backend updates,
    this event is for external integration points.
    """

    unique_id: str
    custom_id: str
    kwargs: dict[str, Any]

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return self.unique_id


@dataclass(frozen=True, slots=True)
class DeviceRemovedEvent(Event):
    """
    Device or data point has been removed.

    Key is unique_id.
    """

    unique_id: str

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return self.unique_id


class EventBus:
    """
    Async-first, type-safe event bus for decoupled communication.

    Features
    --------
    - Type-safe subscriptions (subscribe by event class)
    - Async and sync handler support
    - Automatic error isolation per handler
    - Subscription management with unsubscribe callbacks
    - Optional event logging for debugging

    Thread Safety
    -------------
    This EventBus is designed for single-threaded asyncio use.
    All subscriptions and publishes should happen in the same event loop.
    """

    def __init__(
        self,
        *,
        enable_event_logging: bool = False,
        task_scheduler: TaskScheduler | None = None,
    ) -> None:
        """
        Initialize the event bus.

        Args:
        ----
            enable_event_logging: If True, log all published events (debug only)
            task_scheduler: Optional task scheduler for proper task lifecycle management.
                If provided, publish_sync() will use it instead of raw asyncio.

        """
        self._subscriptions: dict[type[Event], dict[Any, list[_PrioritizedHandler]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self._enable_event_logging = enable_event_logging
        self._event_count: dict[type[Event], int] = defaultdict(int)
        self._handler_order_counter: int = 0  # For stable sorting within same priority
        self._task_scheduler = task_scheduler
        # Track pending tasks to prevent garbage collection (used only when no task_scheduler)
        self._pending_tasks: set[asyncio.Task[None]] = set()

    def clear_event_stats(self) -> None:
        """Clear event statistics counters to free memory."""
        self._event_count.clear()
        _LOGGER.debug("CLEAR_EVENT_STATS: Cleared all event statistics")

    def clear_subscriptions(self, *, event_type: type[Event] | None = None) -> None:
        """
        Clear subscriptions for a specific event type or all types.

        Args:
        ----
            event_type: The event type to clear, or None to clear all

        """
        if event_type is None:
            self._subscriptions.clear()
            self._event_count.clear()
            _LOGGER.debug("CLEAR_SUBSCRIPTION: Cleared all event subscriptions and statistics")
        else:
            self._subscriptions[event_type].clear()
            _LOGGER.debug("CLEAR_SUBSCRIPTION: Cleared subscriptions for %s", event_type.__name__)

    def clear_subscriptions_by_key(self, *, event_key: Any) -> int:
        """
        Clear all subscriptions for a specific event key across all event types.

        This is used to clean up subscriptions when a device or data point is removed,
        preventing memory leaks from orphaned handlers.

        Args:
        ----
            event_key: The key to clear subscriptions for (e.g., unique_id, dpk, channel_address)

        Returns:
        -------
            Number of handlers removed

        """
        total_removed = 0
        for event_type, keys_handlers in self._subscriptions.items():
            if event_key in keys_handlers and (count := len(keys_handlers[event_key])) > 0:
                total_removed += count
                keys_handlers[event_key].clear()
                _LOGGER.debug(
                    "CLEAR_SUBSCRIPTION_BY_KEY: Cleared %d subscription(s) for key=%s, event_type=%s",
                    count,
                    event_key,
                    event_type.__name__,
                )
        return total_removed

    def get_event_stats(self) -> dict[str, int]:
        """
        Get statistics about published events (for debugging).

        Returns
        -------
            Dictionary mapping event type names to publish counts

        """
        return {event_type.__name__: count for event_type, count in self._event_count.items()}

    def get_subscription_count(self, *, event_type: type[Event]) -> int:
        """
        Get the number of active subscriptions for an event type.

        Counts all handlers across all event_keys for the given event_type.

        Args:
        ----
            event_type: The event class to query

        Returns:
        -------
            Number of active subscribers

        """
        return sum(len(handlers) for handlers in self._subscriptions.get(event_type, {}).values())

    def get_total_subscription_count(self) -> int:
        """Return the total number of active subscriptions across all event types."""
        return sum(
            len(handlers) for event_handlers in self._subscriptions.values() for handlers in event_handlers.values()
        )

    def log_leaked_subscriptions(self) -> int:
        """
        Log any remaining subscriptions for debugging memory leaks.

        Call this before clearing subscriptions to identify potential leaks.

        Returns
        -------
            Total number of leaked subscriptions found

        """
        total_leaked = 0
        for event_type, keys_handlers in self._subscriptions.items():
            for key, handlers in keys_handlers.items():
                if handlers:
                    count = len(handlers)
                    total_leaked += count
                    _LOGGER.warning(  # i18n-log: ignore
                        "LEAKED_SUBSCRIPTION: %s (key=%s, count=%d)",
                        event_type.__name__,
                        key,
                        count,
                    )
        if total_leaked > 0:
            _LOGGER.warning("LEAKED_SUBSCRIPTION: Total leaked subscriptions: %d", total_leaked)  # i18n-log: ignore
        return total_leaked

    async def publish(self, *, event: Event) -> None:
        """
        Publish an event to all subscribed handlers.

        Handler lookup strategy (dual-key fallback):
            1. First try: Look up handlers by specific event.key
               (e.g., unique_id for DataPointUpdatedEvent)
            2. Fallback: Look up handlers subscribed with key=None
               (wildcard subscribers that receive all events of this type)

            This allows both targeted subscriptions (only events for specific
            data point) and global subscriptions (all events of a type).

        Priority-based ordering:
            Handlers are sorted by priority (CRITICAL > HIGH > NORMAL > LOW).
            Within the same priority, handlers are called in subscription order.

        Concurrent execution:
            All matching handlers are called concurrently via asyncio.gather().
            return_exceptions=True ensures one failing handler doesn't prevent
            others from receiving the event. Errors are logged in _safe_call_handler.

        Args:
        ----
            event: The event instance to publish

        """
        event_type = type(event)

        # Dual-key lookup: specific key first, then wildcard (None) fallback.
        # The `or` chain short-circuits: if specific key has handlers, use them;
        # otherwise fall back to None-key handlers; otherwise empty list.
        if not (
            prioritized_handlers := (
                self._subscriptions.get(event_type, {}).get(event.key)
                or self._subscriptions.get(event_type, {}).get(None)
                or []
            )
        ):
            if self._enable_event_logging:
                if isinstance(event, BackendParameterEvent):
                    _LOGGER.debug(
                        "PUBLISH: No subscribers for %s: %s [%s]",
                        event_type.__name__,
                        event.parameter,
                        event.channel_address,
                    )
                else:
                    _LOGGER.debug("PUBLISH: No subscribers for %s", event_type.__name__)

            return

        # Track event statistics for debugging
        self._event_count[event_type] += 1

        if self._enable_event_logging:
            _LOGGER.debug(
                "PUBLISH: Publishing %s to %d handler(s) [count: %d]",
                event_type.__name__,
                len(prioritized_handlers),
                self._event_count[event_type],
            )

        # Sort handlers by priority (descending) then by insertion order (ascending).
        # Higher priority values execute first; same priority uses FIFO order.
        sorted_handlers = sorted(
            prioritized_handlers,
            key=lambda ph: (-ph.priority, ph.order),
        )

        # Concurrent handler invocation with error isolation.
        # Each handler runs independently; failures don't affect siblings.
        tasks = [self._safe_call_handler(handler=ph.handler, event=event) for ph in sorted_handlers]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def publish_batch(self, *, events: Sequence[Event]) -> None:
        """
        Publish multiple events efficiently.

        This method optimizes handler lookup by grouping events by type and key,
        reducing redundant lookups when publishing many events of the same type.

        Events are still processed individually per handler, but the overhead of
        looking up handlers is reduced. This is particularly beneficial during
        device discovery or bulk updates.

        Priority ordering is maintained: handlers are sorted by priority
        (CRITICAL > HIGH > NORMAL > LOW) before invocation.

        Args:
        ----
            events: Sequence of events to publish

        Example:
        -------
            events = [
                DeviceUpdatedEvent(timestamp=now, device_address="VCU001"),
                DeviceUpdatedEvent(timestamp=now, device_address="VCU002"),
                DeviceUpdatedEvent(timestamp=now, device_address="VCU003"),
            ]
            await bus.publish_batch(events=events)

        """
        if not events:
            return

        # Group events by (event_type, event_key) for efficient handler lookup
        grouped: dict[tuple[type[Event], Any], list[Event]] = defaultdict(list)
        for event in events:
            grouped[(type(event), event.key)].append(event)

        if self._enable_event_logging:
            _LOGGER.debug(
                "PUBLISH_BATCH: Processing %d events in %d groups",
                len(events),
                len(grouped),
            )

        all_tasks: list[Coroutine[Any, Any, None]] = []

        for (event_type, event_key), grouped_events in grouped.items():
            # Look up handlers once per group
            prioritized_handlers = (
                self._subscriptions.get(event_type, {}).get(event_key)
                or self._subscriptions.get(event_type, {}).get(None)
                or []
            )

            if not prioritized_handlers:
                continue

            # Track event statistics
            self._event_count[event_type] += len(grouped_events)

            # Sort handlers by priority
            sorted_handlers = sorted(
                prioritized_handlers,
                key=lambda ph: (-ph.priority, ph.order),
            )

            # Create tasks for all event-handler combinations
            all_tasks.extend(
                self._safe_call_handler(handler=ph.handler, event=event)
                for event in grouped_events
                for ph in sorted_handlers
            )

        if all_tasks:
            await asyncio.gather(*all_tasks, return_exceptions=True)

    def publish_sync(self, *, event: Event) -> None:
        """
        Schedule an event for publishing from synchronous code.

        This method schedules the event to be published asynchronously via the
        running event loop. Use this when you need to publish events from
        synchronous callbacks or methods that cannot be made async.

        If a TaskScheduler was provided during initialization, it will be used
        for proper task lifecycle management (tracking, shutdown, exception logging).
        Otherwise, falls back to raw asyncio.create_task().

        Note: The event will be published asynchronously after this method returns.
        There is no guarantee about when handlers will be invoked.

        Args:
        ----
            event: The event instance to publish

        """
        if self._task_scheduler is not None:
            # Use TaskScheduler for proper lifecycle management
            # Pass a factory (lambda) instead of a coroutine to defer creation
            # until inside the event loop - avoids "was never awaited" warnings
            self._task_scheduler.create_task(
                target=lambda: self.publish(event=event),
                name=f"event_bus_publish_{type(event).__name__}",
            )
            return

        # Fallback to raw asyncio when no TaskScheduler is available
        try:
            loop = asyncio.get_running_loop()
            # Store task reference to prevent garbage collection
            task = loop.create_task(self.publish(event=event))
            self._pending_tasks.add(task)
            task.add_done_callback(self._pending_tasks.discard)
        except RuntimeError:
            # No running loop - this can happen during shutdown or in tests
            _LOGGER.debug("Cannot publish event %s: no running event loop", type(event).__name__)

    def subscribe(
        self,
        *,
        event_type: type[T_Event],
        event_key: Any,
        handler: EventHandler,
        priority: EventPriority = EventPriority.NORMAL,
    ) -> UnsubscribeCallback:
        """
        Subscribe to events of a specific type.

        Args:
        ----
            event_type: The event class to listen for
            event_key: The key for unique identification
            handler: Async or sync callback with signature (*, event: EventType) -> None
            priority: Handler priority (default: NORMAL). Higher priority handlers
                      are called before lower priority handlers.

        Returns:
        -------
            A callable that unsubscribes this handler when called

        Example:
        -------
            async def on_update(*, event: DataPointUpdatedEvent) -> None:
                print(f"Updated: {event.dpk}")

            # Subscribe with default priority
            unsubscribe = bus.subscribe(event_type=DataPointUpdatedEvent, handler=on_update)

            # Subscribe with high priority
            unsubscribe = bus.subscribe(
                event_type=DataPointUpdatedEvent,
                handler=on_update,
                priority=EventPriority.HIGH,
            )
            # Later...
            unsubscribe()

        """
        # Create prioritized handler wrapper
        generic_handler = handler
        prioritized_handler = _PrioritizedHandler(
            handler=generic_handler,
            priority=priority,
            order=self._handler_order_counter,
        )
        self._handler_order_counter += 1
        self._subscriptions[event_type][event_key].append(prioritized_handler)

        _LOGGER.debug(
            "SUBSCRIBE: Subscribed to %s with priority %s (total subscribers: %d)",
            event_type.__name__,
            priority.name,
            len(self._subscriptions[event_type][event_key]),
        )

        def unsubscribe() -> None:
            """Remove this specific handler from subscriptions."""
            if prioritized_handler in self._subscriptions[event_type][event_key]:
                self._subscriptions[event_type][event_key].remove(prioritized_handler)
                _LOGGER.debug(
                    "SUBSCRIBE: Unsubscribed from %s (remaining: %d)",
                    event_type.__name__,
                    len(self._subscriptions[event_type][event_key]),
                )

        return unsubscribe

    async def _safe_call_handler(self, *, handler: EventHandler, event: Event) -> None:
        """
        Safely invoke a handler, catching and logging exceptions.

        Polymorphic handler detection:
            Handlers can be either sync or async functions. We use a try-then-await
            pattern to support both:
            1. Call the handler (works for both sync and async)
            2. Check if the result is a coroutine (indicates async handler)
            3. If coroutine, await it; if not, the call already completed

            This is more efficient than checking asyncio.iscoroutinefunction() upfront
            because some handlers may be wrapped/decorated in ways that obscure their
            async nature.

        Error isolation:
            Exceptions are caught and logged but not re-raised. This ensures one
            buggy handler doesn't prevent other handlers from receiving events.

        Args:
        ----
            handler: The callback to invoke (sync or async)
            event: The event to pass to the handler

        """
        try:
            # Invoke handler with keyword-only event parameter
            result = handler(event=event)
            # If async, the result is a coroutine that needs to be awaited
            if asyncio.iscoroutine(result):
                await result
        except Exception:
            # Log but don't re-raise - isolate handler errors
            _LOGGER.exception(  # i18n-log: ignore
                "_SAFE_CALL_HANDLER: Error in event handler %s for event %s",
                handler.__name__ if hasattr(handler, "__name__") else handler,
                type(event).__name__,
            )


class EventBatch:
    """
    Context manager for collecting and publishing events in batch.

    EventBatch collects events during a context and publishes them all at once
    when the context exits. This is more efficient than publishing events
    individually when multiple events need to be sent together.

    Features
    --------
    - Async context manager support
    - Automatic flush on context exit
    - Manual flush capability
    - Event count tracking

    Example Usage
    -------------
        async with EventBatch(bus=event_bus) as batch:
            batch.add(DeviceUpdatedEvent(timestamp=now, device_address="VCU001"))
            batch.add(DeviceUpdatedEvent(timestamp=now, device_address="VCU002"))
            # Events are published when the context exits

        # Or with manual flush:
        batch = EventBatch(bus=event_bus)
        batch.add(event1)
        batch.add(event2)
        await batch.flush()

    Thread Safety
    -------------
    EventBatch is designed for single-threaded asyncio use within one context.
    Do not share an EventBatch instance across tasks.
    """

    def __init__(self, *, bus: EventBus) -> None:
        """
        Initialize the event batch.

        Args:
        ----
            bus: The EventBus to publish events to

        """
        self._bus: Final = bus
        self._events: list[Event] = []
        self._flushed: bool = False

    async def __aenter__(self) -> Self:
        """Enter the async context."""
        return self

    async def __aexit__(  # kwonly: disable
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        """Exit the async context and flush events."""
        await self.flush()

    @property
    def event_count(self) -> int:
        """Return the number of events in the batch."""
        return len(self._events)

    @property
    def is_flushed(self) -> bool:
        """Return whether the batch has been flushed."""
        return self._flushed

    def add(self, *, event: Event) -> None:
        """
        Add an event to the batch.

        Args:
        ----
            event: The event to add

        Raises:
        ------
            RuntimeError: If the batch has already been flushed

        """
        if self._flushed:
            raise RuntimeError("Cannot add events to a flushed batch")  # noqa: TRY003  # i18n-exc: ignore
        self._events.append(event)

    def add_all(self, *, events: Sequence[Event]) -> None:
        """
        Add multiple events to the batch.

        Args:
        ----
            events: Sequence of events to add

        Raises:
        ------
            RuntimeError: If the batch has already been flushed

        """
        if self._flushed:
            raise RuntimeError("Cannot add events to a flushed batch")  # noqa: TRY003  # i18n-exc: ignore
        self._events.extend(events)

    async def flush(self) -> int:
        """
        Publish all collected events and clear the batch.

        Returns
        -------
            Number of events that were published

        """
        if self._flushed:
            return 0

        count = len(self._events)
        if self._events:
            await self._bus.publish_batch(events=self._events)
            self._events.clear()

        self._flushed = True
        return count
