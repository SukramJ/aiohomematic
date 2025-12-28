# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Event-driven mock server for test triggers.

Overview
--------
This module provides a mock server that responds to events by injecting
data or triggering actions. This enables event-based test orchestration
where test behavior is triggered by events rather than explicit calls.

The EventDrivenMockServer allows tests to:
- Configure responses to specific event types
- Inject mock data when certain events are published
- Build complex test scenarios with event-driven behavior

Public API
----------
- EventDrivenMockServer: Main mock server class
- ResponseBuilder: Fluent builder for configuring responses
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from aiohomematic.central.event_bus import Event, EventBus


@dataclass
class MockAction:
    """
    An action to perform when an event is received.

    Attributes:
    ----------
        handler: The callback to invoke when the event is received
        filter_fn: Optional filter function to match specific events
        one_shot: If True, the action is removed after first invocation

    """

    handler: Callable[[Any], Any]
    filter_fn: Callable[[Any], bool] | None = None
    one_shot: bool = False


@dataclass
class EventDrivenMockServer:
    """
    Mock server that responds to events.

    Provides a fluent API for configuring responses to specific event types.
    When an event is published that matches a configured response, the
    corresponding action is executed.

    Example Usage
    -------------
        mock_server = EventDrivenMockServer(event_bus=central.event_bus)

        # Configure response to inject data when refresh is triggered
        mock_server.when(DataRefreshTriggeredEvent).then_call(
            lambda event: inject_mock_data()
        )

        # Configure one-shot response
        mock_server.when(CircuitBreakerTrippedEvent).once().then_call(
            lambda event: trigger_recovery()
        )

        # Later, cleanup:
        mock_server.cleanup()

    """

    _event_bus: EventBus = field(repr=False)
    """The EventBus to subscribe to."""

    _responses: dict[type[Event], list[MockAction]] = field(default_factory=dict)
    """Mapping of event types to their configured actions."""

    _unsubscribers: list[Callable[[], None]] = field(default_factory=list)
    """Unsubscribe callbacks for cleanup."""

    _invocation_count: dict[type[Event], int] = field(default_factory=dict)
    """Count of invocations per event type."""

    def cleanup(self) -> None:
        """Unsubscribe from all events and clear responses."""
        for unsub in self._unsubscribers:
            unsub()
        self._unsubscribers.clear()
        self._responses.clear()
        self._invocation_count.clear()

    def get_invocation_count(self, *, event_type: type[Event]) -> int:
        """
        Return the number of times handlers were invoked for an event type.

        Args:
        ----
            event_type: The event type to query

        Returns:
        -------
            Number of handler invocations

        """
        return self._invocation_count.get(event_type, 0)

    def when[T: Event](self, *, event_type: type[T]) -> ResponseBuilder[T]:
        """
        Start configuring a response for an event type.

        Args:
        ----
            event_type: The event type to respond to

        Returns:
        -------
            A ResponseBuilder for configuring the response

        """
        return ResponseBuilder(mock_server=self, event_type=event_type)

    def _add_response(
        self,
        *,
        event_type: type[Event],
        action: MockAction,
    ) -> None:
        """
        Add a response for an event type.

        If this is the first response for this event type, subscribe to it.

        Args:
        ----
            event_type: The event type to respond to
            action: The action to perform

        """
        if event_type not in self._responses:
            self._responses[event_type] = []
            # Subscribe to this event type
            unsub = self._event_bus.subscribe(
                event_type=event_type,
                event_key=None,
                handler=lambda event, et=event_type: self._on_event(event=event, event_type=et),
            )
            self._unsubscribers.append(unsub)

        self._responses[event_type].append(action)

    def _on_event(self, *, event: Event, event_type: type[Event]) -> None:
        """
        Handle an event by invoking matching responses.

        Args:
        ----
            event: The event that was published
            event_type: The event type (for lookup)

        """
        if event_type not in self._responses:
            return

        # Track invocations
        self._invocation_count[event_type] = self._invocation_count.get(event_type, 0) + 1

        # Process actions (copy list to allow modification during iteration)
        actions_to_remove: list[MockAction] = []
        for action in list(self._responses[event_type]):
            # Check filter if present
            if action.filter_fn is not None and not action.filter_fn(event):
                continue

            # Invoke handler
            action.handler(event)

            # Mark one-shot actions for removal
            if action.one_shot:
                actions_to_remove.append(action)

        # Remove one-shot actions
        for action in actions_to_remove:
            self._responses[event_type].remove(action)


@dataclass
class ResponseBuilder[T: "Event"]:
    """
    Fluent builder for configuring mock responses.

    Provides a chainable API for configuring how the mock server should
    respond to specific events.

    Example:
    -------
        mock_server.when(SomeEvent)
            .matching(lambda e: e.interface_id == "test")
            .once()
            .then_call(handler_fn)

    """

    mock_server: EventDrivenMockServer
    """The mock server to configure."""

    event_type: type[T]
    """The event type being configured."""

    _filter_fn: Callable[[T], bool] | None = None
    """Optional filter function."""

    _one_shot: bool = False
    """Whether this is a one-shot response."""

    def matching(self, *, filter_fn: Callable[[T], bool]) -> ResponseBuilder[T]:
        """
        Add a filter to match specific events.

        Args:
        ----
            filter_fn: Function that returns True for matching events

        Returns:
        -------
            Self for chaining

        """
        self._filter_fn = filter_fn
        return self

    def once(self) -> ResponseBuilder[T]:
        """
        Make this a one-shot response (removed after first invocation).

        Returns
        -------
            Self for chaining

        """
        self._one_shot = True
        return self

    def then_call(self, *, handler: Callable[[T], Any]) -> None:
        """
        Configure the handler to call when the event is received.

        Args:
        ----
            handler: Function to call with the event

        """
        self.mock_server._add_response(  # noqa: SLF001  # pylint: disable=protected-access
            event_type=self.event_type,
            action=MockAction(
                handler=handler,
                filter_fn=self._filter_fn,
                one_shot=self._one_shot,
            ),
        )

    def then_publish(self, *, event_factory: Callable[[T], Event]) -> None:
        """
        Configure the mock to publish another event when this event is received.

        Args:
        ----
            event_factory: Function that creates the event to publish

        """

        def publish_handler(event: T) -> None:
            new_event = event_factory(event)
            self.mock_server._event_bus.publish_sync(event=new_event)  # noqa: SLF001  # pylint: disable=protected-access

        self.then_call(handler=publish_handler)


def create_event_mock_server(*, event_bus: EventBus) -> EventDrivenMockServer:
    """
    Create an EventDrivenMockServer instance.

    Factory function for creating an event-driven mock server.

    Args:
    ----
        event_bus: The EventBus to subscribe to

    Returns:
    -------
        Configured EventDrivenMockServer instance

    """
    return EventDrivenMockServer(_event_bus=event_bus)
