# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Tracing support with context variable propagation.

This module provides tracing spans that automatically propagate through async
call chains, enabling performance monitoring and distributed tracing.

Key features:
- Span: Represents a unit of work with timing and attributes
- Automatic parent-child span relationships via context variables
- Context manager for scoped span creation

Example:
    async with span(name="fetch_devices") as s:
        s.set_attribute(key="count", value=len(devices))
        for device in devices:
            async with span(name="process_device") as child:
                child.set_attribute(key="address", value=device.address)
                await process(device)

Public API of this module is defined by __all__.

"""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import uuid


@dataclass(slots=True)
class Span:
    """
    Tracing span for performance monitoring.

    Spans can be nested to form a trace tree. Each span tracks:
    - Timing (start, end, duration)
    - Attributes (key-value metadata)
    - Events (timestamped occurrences within the span)

    Attributes:
        name: Human-readable name for this span.
        trace_id: Unique identifier for the entire trace (shared by all spans).
        span_id: Unique identifier for this specific span.
        parent_span_id: ID of the parent span, or None for root spans.
        started_at: Timestamp when the span started.
        ended_at: Timestamp when the span ended, or None if still active.
        attributes: Key-value metadata for this span.
        events: List of (timestamp, name, attributes) events within this span.

    """

    name: str
    trace_id: str
    span_id: str
    parent_span_id: str | None
    started_at: datetime = field(default_factory=datetime.now)
    ended_at: datetime | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[tuple[datetime, str, dict[str, Any]]] = field(default_factory=list)

    @property
    def duration_ms(self) -> float | None:
        """
        Return span duration in milliseconds.

        Returns:
            Duration in milliseconds, or None if span hasn't ended.

        """
        if self.ended_at is None:
            return None
        return (self.ended_at - self.started_at).total_seconds() * 1000

    @property
    def is_root(self) -> bool:
        """Return True if this is a root span (no parent)."""
        return self.parent_span_id is None

    def add_event(self, *, name: str, **attributes: Any) -> None:
        """
        Add an event to this span.

        Events are timestamped occurrences within a span, useful for
        marking significant points during execution.

        Args:
            name: Name of the event.
            **attributes: Key-value attributes for the event.

        """
        self.events.append((datetime.now(), name, attributes))

    def end(self) -> None:
        """Mark span as ended with current timestamp."""
        self.ended_at = datetime.now()

    def set_attribute(self, *, key: str, value: Any) -> None:
        """
        Set a span attribute.

        Args:
            key: Attribute key.
            value: Attribute value.

        """
        self.attributes[key] = value


# Context variable for current span
_current_span: ContextVar[Span | None] = ContextVar("current_span", default=None)


def get_current_span() -> Span | None:
    """
    Get the current active span.

    Returns:
        The current Span, or None if no span is active.

    """
    return _current_span.get()


def get_current_trace_id() -> str | None:
    """
    Get the current trace ID.

    Returns:
        The current trace ID, or None if no span is active.

    """
    current = _current_span.get()
    return current.trace_id if current else None


class span:  # noqa: N801
    """
    Context manager for tracing spans.

    Creates a span that is automatically linked to any parent span in
    the current context. The span is ended when the context manager exits.

    Example:
        async with span(name="fetch_devices") as s:
            s.set_attribute(key="count", value=len(devices))
            for device in devices:
                async with span(name="process_device") as child:
                    child.set_attribute(key="address", value=device.address)
                    await process(device)

    """

    __slots__ = ("_span", "_token")

    def __init__(self, *, name: str, **attributes: Any) -> None:
        """
        Initialize a new span.

        Args:
            name: Human-readable name for this span.
            **attributes: Initial attributes for the span.

        """
        parent = _current_span.get()

        self._span = Span(
            name=name,
            trace_id=parent.trace_id if parent else str(uuid.uuid4()),
            span_id=str(uuid.uuid4())[:8],
            parent_span_id=parent.span_id if parent else None,
            attributes=dict(attributes),
        )
        self._token: Token[Span | None] | None = None

    async def __aenter__(self) -> Span:
        """Async enter - delegates to sync enter."""
        return self.__enter__()

    async def __aexit__(self, *args: object) -> None:
        """Async exit - delegates to sync exit."""
        self.__exit__()

    def __enter__(self) -> Span:
        """Enter context and set the current span."""
        self._token = _current_span.set(self._span)
        return self._span

    def __exit__(self, *args: object) -> None:
        """Exit context, end span, and reset current span."""
        self._span.end()
        if self._token is not None:
            _current_span.reset(self._token)


def set_current_span(*, s: Span) -> Token[Span | None]:
    """
    Manually set the current span.

    Returns a token that must be used with reset_current_span().
    Prefer using the span context manager instead.

    Args:
        s: The Span to set as current.

    Returns:
        Token for resetting the span.

    """
    return _current_span.set(s)


def reset_current_span(*, token: Token[Span | None]) -> None:
    """
    Reset the current span using a token from set_current_span().

    Args:
        token: Token returned from set_current_span().

    """
    _current_span.reset(token)


# Define public API for this module
__all__ = [
    "Span",
    "get_current_span",
    "get_current_trace_id",
    "reset_current_span",
    "set_current_span",
    "span",
]
