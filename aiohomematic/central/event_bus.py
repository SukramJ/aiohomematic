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

Design Philosophy
-----------------
Instead of multiple callback dictionaries with different signatures, we use:
1. A base Event class with concrete event types (dataclasses)
2. Generic subscription by event type
3. Async-first design with sync compatibility
4. Clear separation of concerns

Example Usage
-------------
    from aiohomematic.central.event_bus import EventBus, DataPointUpdatedEvent
    from aiohomematic.const import DataPointKey, ParamsetKey

    bus = EventBus()

    # Subscribe to specific event type
    async def on_data_point_updated(event: DataPointUpdatedEvent) -> None:
        print(f"DataPoint {event.dpk} updated to {event.value}")

    unsubscribe = bus.subscribe(event_type=DataPointUpdatedEvent, handler=on_data_point_updated)

    # Publish event
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

    # Unsubscribe when done
    unsubscribe()

Migration Notes
---------------
This EventBus replaces the following callback patterns in CentralUnit:
- _backend_system_callbacks → BackendSystemEvent
- _backend_parameter_callbacks → BackendParameterEvent
- _homematic_callbacks → HomematicEvent
- _data_point_key_event_subscriptions → DataPointUpdatedEvent
- _sysvar_data_point_event_subscriptions → SysvarUpdatedEvent

And in Device/Channel/DataPoint:
- Device._device_updated_callbacks → DeviceUpdatedEvent
- Device._firmware_update_callbacks → FirmwareUpdatedEvent
- Channel._link_peer_changed_callbacks → LinkPeerChangedEvent
- DataPoint._data_point_updated_callbacks → DataPointUpdatedCallbackEvent
- DataPoint._device_removed_callbacks → DeviceRemovedEvent

"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any, TypeVar, cast

from aiohomematic.const import BackendSystemEvent, DataPointKey, EventKey, EventType
from aiohomematic.type_aliases import DataPointEventCallback, SysvarEventCallback

_LOGGER = logging.getLogger(__name__)

# Type variables for generic event handling
T_Event = TypeVar("T_Event", bound="Event")

# Callback type aliases
SyncEventHandler = Callable[[Any], None]
AsyncEventHandler = Callable[[Any], Coroutine[Any, Any, None]]
EventHandler = SyncEventHandler | AsyncEventHandler
UnsubscribeCallback = Callable[[], None]


@dataclass(frozen=True, slots=True)
class Event:
    """
    Base class for all events in the EventBus.

    All events are immutable dataclasses with slots for memory efficiency.
    The timestamp field is included in all events for debugging and auditing.
    """

    timestamp: datetime


@dataclass(frozen=True, slots=True)
class DataPointUpdatedEvent(Event):
    """
    Fired when a data point value is updated from the backend.

    This replaces the _data_point_key_event_subscriptions pattern.

    The dpk (DataPointKey) contains:
    - interface_id: Interface identifier (e.g., "BidCos-RF")
    - channel_address: Full channel address (e.g., "VCU0000001:1")
    - paramset_key: Paramset type (e.g., ParamsetKey.VALUES)
    - parameter: Parameter name (e.g., "STATE")
    """

    dpk: DataPointKey
    value: Any
    received_at: datetime


@dataclass(frozen=True, slots=True)
class BackendParameterEvent(Event):
    """Raw parameter update event from backend (re-emitted from RPC callbacks)."""

    interface_id: str
    channel_address: str
    parameter: str
    value: Any


@dataclass(frozen=True, slots=True)
class BackendSystemEventData(Event):
    """System-level events from backend (devices created, deleted, etc.)."""

    system_event: BackendSystemEvent
    data: dict[str, Any]


@dataclass(frozen=True, slots=True)
class HomematicEvent(Event):
    """Homematic-specific events (INTERFACE, KEYPRESS, etc.)."""

    event_type: EventType
    event_data: dict[EventKey, Any]


@dataclass(frozen=True, slots=True)
class SysvarUpdatedEvent(Event):
    """System variable value updated."""

    state_path: str
    value: Any
    received_at: datetime


@dataclass(frozen=True, slots=True)
class InterfaceEvent(Event):
    """Interface-level event (connection state changes, etc.)."""

    interface_id: str
    event_type: str
    data: dict[str, Any]


@dataclass(frozen=True, slots=True)
class DeviceUpdatedEvent(Event):
    """Device state has been updated."""

    device_address: str


@dataclass(frozen=True, slots=True)
class FirmwareUpdatedEvent(Event):
    """Device firmware information has been updated."""

    device_address: str


@dataclass(frozen=True, slots=True)
class LinkPeerChangedEvent(Event):
    """Channel link peer addresses have changed."""

    channel_address: str


@dataclass(frozen=True, slots=True)
class DataPointUpdatedCallbackEvent(Event):
    """
    Data point value updated callback event.

    This event is fired when a data point's value changes and external
    consumers (like Home Assistant entities) need to be notified.
    Unlike DataPointUpdatedEvent which handles internal backend updates,
    this event is for external integration points.
    """

    unique_id: str
    custom_id: str
    kwargs: dict[str, Any]


@dataclass(frozen=True, slots=True)
class DeviceRemovedEvent(Event):
    """Device or data point has been removed."""

    unique_id: str


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

    def __init__(self, *, enable_event_logging: bool = False) -> None:
        """
        Initialize the event bus.

        Args:
        ----
            enable_event_logging: If True, log all published events (debug only)

        """
        self._subscriptions: defaultdict[type[Event], list[EventHandler]] = defaultdict(list)
        self._enable_event_logging = enable_event_logging
        self._event_count: defaultdict[type[Event], int] = defaultdict(int)

    def clear_subscriptions(self, *, event_type: type[Event] | None = None) -> None:
        """
        Clear subscriptions for a specific event type or all types.

        Args:
        ----
            event_type: The event type to clear, or None to clear all

        """
        if event_type is None:
            self._subscriptions.clear()
            _LOGGER.debug("Cleared all event subscriptions")
        else:
            self._subscriptions[event_type].clear()
            _LOGGER.debug("Cleared subscriptions for %s", event_type.__name__)

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

        Args:
        ----
            event_type: The event class to query

        Returns:
        -------
            Number of active subscribers

        """
        return len(self._subscriptions.get(event_type, []))

    async def publish(self, *, event: Event) -> None:
        """
        Publish an event to all subscribed handlers.

        Handlers are called concurrently via asyncio.gather. Exceptions in
        individual handlers are caught and logged but don't affect other handlers.

        Args:
        ----
            event: The event instance to publish

        """
        event_type = type(event)
        if not (handlers := self._subscriptions.get(event_type, [])):
            if self._enable_event_logging:
                _LOGGER.debug("No subscribers for %s", event_type.__name__)
            return

        self._event_count[event_type] += 1

        if self._enable_event_logging:
            _LOGGER.debug(
                "Publishing %s to %d handler(s) [count: %d]",
                event_type.__name__,
                len(handlers),
                self._event_count[event_type],
            )

        # Call all handlers concurrently, isolating errors
        tasks = [self._safe_call_handler(handler=handler, event=event) for handler in handlers]
        await asyncio.gather(*tasks, return_exceptions=True)

    def subscribe(
        self,
        *,
        event_type: type[T_Event],
        handler: Callable[[T_Event], None] | Callable[[T_Event], Coroutine[Any, Any, None]],
    ) -> UnsubscribeCallback:
        """
        Subscribe to events of a specific type.

        Args:
        ----
            event_type: The event class to listen for
            handler: Async or sync callback that accepts the event

        Returns:
        -------
            A callable that unsubscribes this handler when called

        Example:
        -------
            async def on_update(event: DataPointUpdatedEvent) -> None:
                print(f"Updated: {event.dpk}")

            unsubscribe = bus.subscribe(event_type=DataPointUpdatedEvent, handler=on_update)
            # Later...
            unsubscribe()

        """
        # Cast to generic handler type for storage
        generic_handler = cast(EventHandler, handler)
        self._subscriptions[event_type].append(generic_handler)

        _LOGGER.debug(
            "Subscribed to %s (total subscribers: %d)",
            event_type.__name__,
            len(self._subscriptions[event_type]),
        )

        def unsubscribe() -> None:
            """Remove this specific handler from subscriptions."""
            if generic_handler in self._subscriptions[event_type]:
                self._subscriptions[event_type].remove(generic_handler)
                _LOGGER.debug(
                    "Unsubscribed from %s (remaining: %d)",
                    event_type.__name__,
                    len(self._subscriptions[event_type]),
                )

        return unsubscribe

    def subscribe_datapoint_event_callback(
        self, *, dpk: DataPointKey, callback: DataPointEventCallback
    ) -> UnsubscribeCallback:
        """
        Subscribe to data point events for a specific data point key.

        This is a compatibility wrapper for the old DataPointEventCallback protocol.
        New code should use subscribe(DataPointUpdatedEvent, handler) with filtering.

        Args:
        ----
            dpk: Data point key to filter for
            callback: Legacy callback following DataPointEventCallback protocol

        Returns:
        -------
            Unsubscribe callback

        """

        async def adapter(event: DataPointUpdatedEvent) -> None:
            # Only call callback if this is the data point we're interested in
            if event.dpk == dpk:
                await callback(value=event.value, received_at=event.received_at)

        return self.subscribe(event_type=DataPointUpdatedEvent, handler=adapter)

    def subscribe_sysvar_event_callback(self, *, state_path: str, callback: SysvarEventCallback) -> UnsubscribeCallback:
        """
        Subscribe to system variable events for a specific state path.

        This is a compatibility wrapper for the old SysvarEventCallback.
        New code should use subscribe(SysvarUpdatedEvent, handler) with filtering.

        Args:
        ----
            state_path: System variable state path to filter for
            callback: Legacy callback following SysvarEventCallback signature

        Returns:
        -------
            Unsubscribe callback

        """

        async def adapter(event: SysvarUpdatedEvent) -> None:
            # Only call callback if this is the sysvar we're interested in
            if event.state_path == state_path:
                await callback(value=event.value, received_at=event.received_at)

        return self.subscribe(event_type=SysvarUpdatedEvent, handler=adapter)

    async def _safe_call_handler(self, *, handler: EventHandler, event: Event) -> None:
        """
        Safely invoke a handler, catching and logging exceptions.

        Supports both sync and async handlers.

        Args:
        ----
            handler: The callback to invoke
            event: The event to pass to the handler

        """
        try:
            # Check if handler is async
            result = handler(event)
            if asyncio.iscoroutine(result):
                await result
        except Exception:
            _LOGGER.exception(  # i18n-log: ignore
                "Error in event handler %s for event %s",
                handler.__name__ if hasattr(handler, "__name__") else handler,
                type(event).__name__,
            )
