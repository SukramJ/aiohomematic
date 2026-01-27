# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Event type definitions for the aiohomematic event system.

This module contains event dataclasses that are used across the codebase.
These events are defined separately from the EventBus to avoid circular
import dependencies.

All event types in this module:
- Are immutable dataclasses (frozen=True, slots=True)
- Inherit from the Event base class
- Have a `key` property for event routing

These events are re-exported from `central.events` for backward compatibility.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum, StrEnum, unique
from typing import Any

from aiohomematic.const import CentralState, CircuitState, ClientState

__all__ = [
    "CentralStateChangedEvent",
    "CircuitBreakerStateChangedEvent",
    "CircuitBreakerTrippedEvent",
    "ClientStateChangedEvent",
    "DataFetchCompletedEvent",
    "DataFetchOperation",
    "Event",
    "EventPriority",
    "HealthRecordedEvent",
]


@unique
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


@unique
class DataFetchOperation(StrEnum):
    """Type of data fetch operation that completed."""

    FETCH_DEVICE_DESCRIPTIONS = "fetch_device_descriptions"
    """Device descriptions were fetched and added to cache."""

    FETCH_PARAMSET_DESCRIPTIONS = "fetch_paramset_descriptions"
    """Paramset descriptions were fetched and added to cache."""


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
class CircuitBreakerStateChangedEvent(Event):
    """
    Circuit breaker state transition.

    Key is interface_id.

    Emitted when a circuit breaker transitions between states
    (CLOSED, OPEN, HALF_OPEN).
    """

    timestamp: datetime
    interface_id: str
    old_state: CircuitState
    new_state: CircuitState
    failure_count: int
    success_count: int
    last_failure_time: datetime | None

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return self.interface_id


@dataclass(frozen=True, slots=True)
class CircuitBreakerTrippedEvent(Event):
    """
    Circuit breaker tripped (opened due to failures).

    Key is interface_id.

    Emitted when a circuit breaker transitions to OPEN state,
    indicating repeated failures.
    """

    timestamp: datetime
    interface_id: str
    failure_count: int
    last_failure_reason: str | None
    cooldown_seconds: float

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return self.interface_id


@dataclass(frozen=True, slots=True)
class ClientStateChangedEvent(Event):
    """
    Client state machine transition.

    Key is interface_id.

    Emitted when a client transitions between states
    (INIT, CONNECTED, DISCONNECTED, etc.).
    """

    timestamp: datetime
    interface_id: str
    old_state: ClientState
    new_state: ClientState
    trigger: str | None

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return self.interface_id


@dataclass(frozen=True, slots=True)
class CentralStateChangedEvent(Event):
    """
    Central unit state machine transition.

    Key is central_name.

    Emitted when the central unit transitions between states
    (STARTING, RUNNING, DEGRADED, etc.).
    """

    timestamp: datetime
    central_name: str
    old_state: CentralState
    new_state: CentralState
    trigger: str | None

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return self.central_name


@dataclass(frozen=True, slots=True)
class DataFetchCompletedEvent(Event):
    """
    Data fetch operation completed.

    Key is interface_id.

    Emitted when paramset descriptions or device descriptions have been
    fetched and added to the cache. This triggers automatic cache persistence
    if changes were detected.
    """

    timestamp: datetime
    interface_id: str
    operation: DataFetchOperation

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return self.interface_id


@dataclass(frozen=True, slots=True)
class HealthRecordedEvent(Event):
    """
    Health status recorded for an interface.

    Key is interface_id.

    Emitted by CircuitBreaker when a request succeeds or fails,
    enabling health tracking without direct callback coupling.
    """

    timestamp: datetime
    interface_id: str
    success: bool

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return self.interface_id
