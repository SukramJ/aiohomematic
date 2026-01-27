# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Typed data structures for store caches.

This module provides typed cache entries and type aliases used across
the persistent and dynamic store implementations.

Type Aliases
------------
- ParameterMap: Parameter name to ParameterData mapping
- ParamsetMap: ParamsetKey to ParameterMap mapping
- ChannelParamsetMap: Channel address to ParamsetMap mapping
- InterfaceParamsetMap: Interface ID to ChannelParamsetMap mapping

Cache Entry Types
-----------------
- CachedCommand: Command cache entry with value and timestamp
- PongTracker: Ping/pong tracking entry with token and seen time
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum, unique
import time
from typing import TYPE_CHECKING, Any, TypeAlias

if TYPE_CHECKING:
    from aiohomematic.const import ParameterData, ParamsetKey

# =============================================================================
# Type Aliases for Paramset Description Cache
# =============================================================================
# These aliases describe the nested structure of paramset descriptions:
# InterfaceParamsetMap[interface_id][channel_address][paramset_key][parameter] = ParameterData

ParameterMap: TypeAlias = dict[str, "ParameterData"]
ParamsetMap: TypeAlias = dict["ParamsetKey", ParameterMap]
ChannelParamsetMap: TypeAlias = dict[str, ParamsetMap]
InterfaceParamsetMap: TypeAlias = dict[str, ChannelParamsetMap]


# =============================================================================
# Cache Name Enum
# =============================================================================


@unique
class CacheName(StrEnum):
    """Enumeration of cache names for identification."""

    DATA = "data"
    """Central data cache for device/channel values."""


# =============================================================================
# Cache Statistics
# =============================================================================


@dataclass(slots=True)
class CacheStatistics:
    """
    Lightweight statistics container for cache performance tracking.

    Provides local counters for hits, misses, and evictions instead of
    event-based tracking to reduce EventBus overhead. MetricsAggregator
    reads these counters directly for reporting.

    Attributes:
        hits: Number of successful cache lookups.
        misses: Number of failed cache lookups.
        evictions: Number of entries evicted from cache.

    """

    hits: int = 0
    misses: int = 0
    evictions: int = 0

    @property
    def hit_rate(self) -> float:
        """Return cache hit rate as percentage (0-100)."""
        if (total := self.hits + self.misses) == 0:
            return 100.0
        return (self.hits / total) * 100

    @property
    def total_lookups(self) -> int:
        """Return total number of cache lookups."""
        return self.hits + self.misses

    def record_eviction(self, *, count: int = 1) -> None:
        """Record cache eviction(s)."""
        self.evictions += count

    def record_hit(self) -> None:
        """Record a cache hit."""
        self.hits += 1

    def record_miss(self) -> None:
        """Record a cache miss."""
        self.misses += 1

    def reset(self) -> None:
        """Reset all counters to zero."""
        self.hits = 0
        self.misses = 0
        self.evictions = 0


# =============================================================================
# Tracker Statistics
# =============================================================================


@dataclass(slots=True)
class TrackerStatistics:
    """
    Lightweight statistics container for tracker memory management.

    Unlike CacheStatistics, trackers don't have hit/miss semantics.
    They only track evictions for memory management monitoring.

    Attributes:
        evictions: Number of entries evicted from tracker.

    """

    evictions: int = 0

    def record_eviction(self, *, count: int = 1) -> None:
        """Record tracker eviction(s)."""
        self.evictions += count

    def reset(self) -> None:
        """Reset all counters to zero."""
        self.evictions = 0


# =============================================================================
# Cache Entry Dataclasses
# =============================================================================


@dataclass(frozen=True, slots=True)
class CachedCommand:
    """
    Cached command entry for tracking sent commands.

    Attributes:
        value: The value that was sent with the command.
        sent_at: Timestamp when the command was sent.

    """

    value: Any
    sent_at: datetime


@dataclass(slots=True)
class PongTracker:
    """
    Tracker for pending or unknown pong tokens.

    Used by PingPongTracker to track ping/pong events with timestamps
    for TTL expiry and size limit enforcement.

    Attributes:
        tokens: Set of pong tokens being tracked.
        seen_at: Mapping of token to monotonic timestamp when it was seen.
        logged: Whether a warning has been logged for this tracker.

    """

    tokens: set[str]
    seen_at: dict[str, float]
    logged: bool = False

    def __len__(self) -> int:
        """Return the number of tracked tokens."""
        return len(self.tokens)

    def add(self, *, token: str, timestamp: float) -> None:
        """Add a token with its timestamp."""
        self.tokens.add(token)
        self.seen_at[token] = timestamp

    def clear(self) -> None:
        """Clear all tokens and timestamps."""
        self.tokens.clear()
        self.seen_at.clear()
        self.logged = False

    def contains(self, *, token: str) -> bool:
        """Check if a token is being tracked."""
        return token in self.tokens

    def remove(self, *, token: str) -> None:
        """Remove a token and its timestamp."""
        self.tokens.discard(token)
        self.seen_at.pop(token, None)


# =============================================================================
# PingPong Journal Types
# =============================================================================


@unique
class PingPongEventType(StrEnum):
    """Types of events recorded in the PingPong journal."""

    PING_SENT = "PING_SENT"
    """A PING was sent to the backend."""

    PONG_RECEIVED = "PONG_RECEIVED"
    """A matching PONG was received (success)."""

    PONG_UNKNOWN = "PONG_UNKNOWN"
    """A PONG was received without a matching PING."""

    PONG_EXPIRED = "PONG_EXPIRED"
    """A PING expired without receiving a PONG (TTL exceeded)."""


@dataclass(frozen=True, slots=True)
class PingPongJournalEvent:
    """
    Single event in the PingPong diagnostic journal.

    Immutable record of a ping/pong event for diagnostic purposes.
    Events are stored in a ring buffer and can be exported for analysis.

    Attributes:
        timestamp: Monotonic timestamp for age calculation and ordering.
        timestamp_iso: ISO format timestamp for human-readable display.
        event_type: Type of event (PING_SENT, PONG_RECEIVED, etc.).
        token: The ping/pong token (truncated for display).
        rtt_ms: Round-trip time in milliseconds (only for PONG_RECEIVED).

    """

    timestamp: float
    timestamp_iso: str
    event_type: PingPongEventType
    token: str
    rtt_ms: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {
            "time": self.timestamp_iso,
            "type": self.event_type.value,
            "token": self.token,
        }
        if self.rtt_ms is not None:
            result["rtt_ms"] = round(self.rtt_ms, 2)
        return result


@dataclass(slots=True)
class PingPongJournal:
    """
    Ring buffer for PingPong diagnostic events.

    Provides diagnostic history for HA Diagnostics without log parsing.
    Events are stored in a fixed-size ring buffer with optional time-based eviction.

    Features:
        - Fixed-size ring buffer (default 100 entries)
        - Time-based eviction (default 30 minutes)
        - RTT statistics aggregation (avg/min/max)
        - JSON-serializable for HA Diagnostics

    Attributes:
        max_entries: Maximum number of events to store.
        max_age_seconds: Maximum age of events before eviction.

    """

    max_entries: int = 100
    max_age_seconds: float = 1800.0  # 30 minutes
    _events: list[PingPongJournalEvent] | None = None
    _rtt_samples: list[float] | None = None

    def __post_init__(self) -> None:
        """Initialize internal collections."""
        if self._events is None:
            self._events = []
        if self._rtt_samples is None:
            self._rtt_samples = []

    @property
    def events(self) -> list[PingPongJournalEvent]:
        """Return the events list."""
        if self._events is None:
            self._events = []
        return self._events

    @property
    def rtt_samples(self) -> list[float]:
        """Return the RTT samples list."""
        if self._rtt_samples is None:
            self._rtt_samples = []
        return self._rtt_samples

    def clear(self) -> None:
        """Clear all events and statistics."""
        self.events.clear()
        self.rtt_samples.clear()

    def count_events_by_type(self, *, event_type: PingPongEventType, minutes: int = 5) -> int:
        """Count events of a specific type within the last N minutes."""
        cutoff = time.monotonic() - (minutes * 60)
        return sum(1 for e in self.events if e.event_type == event_type and e.timestamp >= cutoff)

    def get_diagnostics(self) -> dict[str, Any]:
        """Return full diagnostics data for HA Diagnostics."""
        return {
            "total_events": len(self.events),
            "max_entries": self.max_entries,
            "max_age_seconds": self.max_age_seconds,
            "rtt_statistics": self.get_rtt_statistics(),
            "recent_events": self.get_recent_events(limit=20),
        }

    def get_recent_events(self, *, limit: int = 50) -> list[dict[str, Any]]:
        """Return recent events as list of dicts."""
        return [e.to_dict() for e in self.events[-limit:]]

    def get_rtt_statistics(self) -> dict[str, Any]:
        """Return RTT statistics from collected samples."""
        if not self.rtt_samples:
            return {
                "samples": 0,
                "avg_ms": None,
                "min_ms": None,
                "max_ms": None,
            }

        return {
            "samples": len(self.rtt_samples),
            "avg_ms": round(sum(self.rtt_samples) / len(self.rtt_samples), 2),
            "min_ms": round(min(self.rtt_samples), 2),
            "max_ms": round(max(self.rtt_samples), 2),
        }

    def get_success_rate(self, *, minutes: int = 5) -> float:
        """Calculate success rate (PONGs received / PINGs sent) over last N minutes."""
        pings = self.count_events_by_type(event_type=PingPongEventType.PING_SENT, minutes=minutes)
        pongs = self.count_events_by_type(event_type=PingPongEventType.PONG_RECEIVED, minutes=minutes)

        if pings == 0:
            return 1.0  # No pings = 100% success (nothing to fail)
        return pongs / pings

    def record_ping_sent(self, *, token: str) -> None:
        """Record a PING being sent."""
        self._add_event(
            event_type=PingPongEventType.PING_SENT,
            token=token,
        )

    def record_pong_expired(self, *, token: str) -> None:
        """Record a PING that expired without PONG."""
        self._add_event(
            event_type=PingPongEventType.PONG_EXPIRED,
            token=token,
        )

    def record_pong_received(self, *, token: str, rtt_ms: float) -> None:
        """Record a matching PONG received with RTT."""
        self._add_event(
            event_type=PingPongEventType.PONG_RECEIVED,
            token=token,
            rtt_ms=rtt_ms,
        )
        # Keep last 50 RTT samples for statistics
        self.rtt_samples.append(rtt_ms)
        if len(self.rtt_samples) > 50:
            self.rtt_samples.pop(0)

    def record_pong_unknown(self, *, token: str) -> None:
        """Record an unknown PONG (no matching PING)."""
        self._add_event(
            event_type=PingPongEventType.PONG_UNKNOWN,
            token=token,
        )

    def _add_event(
        self,
        *,
        event_type: PingPongEventType,
        token: str,
        rtt_ms: float | None = None,
    ) -> None:
        """Add event to journal with automatic eviction."""
        now = time.monotonic()

        # Time-based eviction
        while self.events and (now - self.events[0].timestamp) > self.max_age_seconds:
            self.events.pop(0)

        # Size-based eviction
        while len(self.events) >= self.max_entries:
            self.events.pop(0)

        # Truncate token for display (keep last 20 chars)
        display_token = token[-20:] if len(token) > 20 else token

        self.events.append(
            PingPongJournalEvent(
                timestamp=now,
                timestamp_iso=datetime.now().isoformat(timespec="milliseconds"),
                event_type=event_type,
                token=display_token,
                rtt_ms=rtt_ms,
            )
        )


# =============================================================================
# Incident Store Types
# =============================================================================


@unique
class IncidentType(StrEnum):
    """Types of incidents that can be recorded for diagnostics."""

    PING_PONG_MISMATCH_HIGH = "PING_PONG_MISMATCH_HIGH"
    """PingPong pending count exceeded threshold."""

    PING_PONG_UNKNOWN_HIGH = "PING_PONG_UNKNOWN_HIGH"
    """PingPong unknown PONG count exceeded threshold."""

    CONNECTION_LOST = "CONNECTION_LOST"
    """Connection to backend was lost."""

    CONNECTION_RESTORED = "CONNECTION_RESTORED"
    """Connection to backend was restored."""

    RPC_ERROR = "RPC_ERROR"
    """RPC call failed with error."""

    CALLBACK_TIMEOUT = "CALLBACK_TIMEOUT"
    """Callback from backend timed out."""

    CIRCUIT_BREAKER_TRIPPED = "CIRCUIT_BREAKER_TRIPPED"
    """Circuit breaker opened due to excessive failures."""

    CIRCUIT_BREAKER_RECOVERED = "CIRCUIT_BREAKER_RECOVERED"
    """Circuit breaker recovered after successful test requests."""


@unique
class IncidentSeverity(StrEnum):
    """Severity levels for incidents."""

    INFO = "info"
    """Informational incident (e.g., connection restored)."""

    WARNING = "warning"
    """Warning incident (e.g., threshold approached)."""

    ERROR = "error"
    """Error incident (e.g., connection lost)."""

    CRITICAL = "critical"
    """Critical incident (e.g., repeated failures)."""


@dataclass(frozen=True, slots=True)
class IncidentSnapshot:
    """
    Immutable snapshot of an incident for diagnostic analysis.

    Unlike Journal events which expire after TTL, incidents are preserved
    indefinitely (up to max count) for post-mortem analysis.

    Attributes:
        incident_id: Unique identifier for this incident.
        timestamp_iso: ISO format timestamp for human-readable display.
        incident_type: Type of incident that occurred.
        severity: Severity level of the incident.
        interface_id: Interface where incident occurred (if applicable).
        message: Human-readable description of the incident.
        context: Additional context data for debugging.
        journal_excerpt: Journal events around the time of incident.

    """

    incident_id: str
    timestamp_iso: str
    incident_type: IncidentType
    severity: IncidentSeverity
    interface_id: str | None
    message: str
    context: dict[str, Any]
    journal_excerpt: list[dict[str, Any]]

    @classmethod
    def from_dict(cls, *, data: dict[str, Any]) -> IncidentSnapshot:
        """Create IncidentSnapshot from dictionary."""
        return cls(
            incident_id=data["incident_id"],
            timestamp_iso=data["timestamp"],
            incident_type=IncidentType(data["type"]),
            severity=IncidentSeverity(data["severity"]),
            interface_id=data.get("interface_id"),
            message=data["message"],
            context=data.get("context", {}),
            journal_excerpt=data.get("journal_excerpt", []),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "incident_id": self.incident_id,
            "timestamp": self.timestamp_iso,
            "type": self.incident_type.value,
            "severity": self.severity.value,
            "interface_id": self.interface_id,
            "message": self.message,
            "context": self.context,
            "journal_excerpt": self.journal_excerpt,
        }
