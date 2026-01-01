# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Event capture utilities for test verification.

This module provides tools for capturing and asserting events in tests,
enabling behavior-focused testing through event verification.

Public API
----------
- EventCapture: Capture events for test verification
- EventSequenceAssertion: Verify event ordering
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from aiohomematic.central.events import Event, EventBus

T = TypeVar("T", bound="Event")


@dataclass
class EventCapture:
    """
    Capture events from EventBus for test verification.

    Provides methods to subscribe to events, capture them, and make assertions
    about what events were emitted during test execution.

    Example:
    -------
        capture = EventCapture()
        capture.subscribe_to(event_bus, CircuitBreakerTrippedEvent)

        # ... perform test actions ...

        capture.assert_event_emitted(
            CircuitBreakerTrippedEvent,
            interface_id="test",
            failure_count=5,
        )
        capture.cleanup()

    """

    captured_events: list[Event] = field(default_factory=list)
    """List of all captured events."""

    _unsubscribers: list[Callable[[], None]] = field(default_factory=list)
    """Unsubscribe callbacks for cleanup."""

    def assert_event_emitted(
        self,
        *,
        event_type: type[Event],
        count: int | None = None,
        **expected_attrs: Any,
    ) -> None:
        """
        Assert that an event with specific attributes was emitted.

        Args:
            event_type: The expected event type
            count: If provided, assert exactly this many events were emitted
            **expected_attrs: Expected attribute values on the event

        Raises:
            AssertionError: If no matching event found or count mismatch

        """
        events = self.get_events_of_type(event_type=event_type)

        if count is not None and len(events) != count:
            raise AssertionError(f"Expected {count} {event_type.__name__} events, got {len(events)}")

        if not expected_attrs:
            if not events:
                raise AssertionError(f"No {event_type.__name__} events captured")
            return

        for event in events:
            if all(getattr(event, k, None) == v for k, v in expected_attrs.items()):
                return

        raise AssertionError(
            f"No {event_type.__name__} found with attributes {expected_attrs}. Captured {len(events)} events: {events}"
        )

    def assert_no_event(self, *, event_type: type[Event]) -> None:
        """
        Assert that no events of a specific type were emitted.

        Args:
            event_type: The event type that should not exist

        Raises:
            AssertionError: If any events of that type were captured

        """
        if events := self.get_events_of_type(event_type=event_type):
            raise AssertionError(f"Expected no {event_type.__name__} events, but found {len(events)}: {events}")

    def cleanup(self) -> None:
        """Unsubscribe from all events and clear captured events."""
        for unsub in self._unsubscribers:
            unsub()
        self._unsubscribers.clear()
        self.captured_events.clear()

    def clear(self) -> None:
        """Clear all captured events."""
        self.captured_events.clear()

    def get_event_count(self, *, event_type: type[Event]) -> int:
        """
        Return count of captured events of a specific type.

        Args:
            event_type: The event type to count

        Returns:
            Number of events of that type

        """
        return len(self.get_events_of_type(event_type=event_type))

    def get_events_of_type(self, *, event_type: type[T]) -> list[T]:
        """
        Return all captured events of a specific type.

        Args:
            event_type: The event type to filter by

        Returns:
            List of events matching the type

        """
        return [e for e in self.captured_events if isinstance(e, event_type)]

    def subscribe_to(self, event_bus: EventBus, *event_types: type[Event]) -> None:
        """
        Subscribe to specific event types on the EventBus.

        Args:
            event_bus: The EventBus to subscribe to
            *event_types: Event types to capture

        """
        for event_type in event_types:
            unsubscribe = event_bus.subscribe(
                event_type=event_type,
                event_key=None,
                handler=self._capture_handler,
            )
            self._unsubscribers.append(unsubscribe)

    def _capture_handler(self, *, event: Event) -> None:
        """Handle event by capturing it."""
        self.captured_events.append(event)


@dataclass
class EventSequenceAssertion:
    """
    Assert events occur in expected sequence.

    Useful for verifying state machine transitions and multi-step processes.

    Example:
    -------
        sequence = EventSequenceAssertion(expected_sequence=[
            ConnectionStageChangedEvent,
            ClientStateChangedEvent,
            CentralStateChangedEvent,
        ])
        event_bus.subscribe(Event, sequence.on_event)

        # ... perform actions ...

        sequence.verify()

    """

    expected_sequence: list[type[Event]]
    """The expected sequence of event types."""

    captured_types: list[type[Event]] = field(default_factory=list)
    """Captured event types in order."""

    def on_event(self, *, event: Event) -> None:
        """
        Handle event by capturing its type.

        Args:
            event: The event that was published

        """
        self.captured_types.append(type(event))

    def reset(self) -> None:
        """Reset captured types for reuse."""
        self.captured_types.clear()

    def verify(self, *, strict: bool = False) -> None:
        """
        Verify the captured sequence matches expected.

        Args:
            strict: If True, require exact sequence match.
                    If False, verify expected events appear in order
                    (other events may be interspersed).

        Raises:
            AssertionError: If sequence doesn't match

        """
        if strict:
            self._verify_strict()
        else:
            self._verify_subsequence()

    def _verify_strict(self) -> None:
        """Verify exact sequence match."""
        if len(self.captured_types) != len(self.expected_sequence):
            raise AssertionError(
                f"Expected {len(self.expected_sequence)} events, "
                f"got {len(self.captured_types)}.\n"
                f"Expected: {[e.__name__ for e in self.expected_sequence]}\n"
                f"Got: {[e.__name__ for e in self.captured_types]}"
            )

        for i, (expected, actual) in enumerate(zip(self.expected_sequence, self.captured_types, strict=True)):
            if expected != actual:
                raise AssertionError(f"Event {i}: expected {expected.__name__}, got {actual.__name__}")

    def _verify_subsequence(self) -> None:
        """Verify expected events appear in order (non-strict)."""
        expected_idx = 0
        for actual_type in self.captured_types:
            if expected_idx >= len(self.expected_sequence):
                break
            if actual_type == self.expected_sequence[expected_idx]:
                expected_idx += 1

        if expected_idx < len(self.expected_sequence):
            missing = self.expected_sequence[expected_idx:]
            raise AssertionError(
                f"Missing expected events in sequence: {[e.__name__ for e in missing]}\n"
                f"Expected: {[e.__name__ for e in self.expected_sequence]}\n"
                f"Got: {[e.__name__ for e in self.captured_types]}"
            )
