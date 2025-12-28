# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Central observer for event-driven metrics aggregation.

This module provides MetricsObserver which subscribes to metric events
on the EventBus and maintains aggregated statistics. It replaces the
polling-based approach with event-driven collection.

Public API
----------
- MetricsObserver: Central aggregator for all metric events
- ObserverSnapshot: Point-in-time snapshot of all collected metrics
- LatencyTracker: Tracks latency statistics for a single metric key
- HealthState: Tracks health state for a component

Usage
-----
    from aiohomematic.metrics import MetricsObserver

    # Create observer (typically done by CentralUnit)
    observer = MetricsObserver(event_bus=central.event_bus)

    # Get snapshot of all metrics
    snapshot = observer.snapshot()
    print(snapshot.latency["ping_pong:HmIP-RF:round_trip"].avg_ms)

    # Get aggregated latency
    latency = observer.get_aggregated_latency(pattern="ping_pong")
    print(latency.avg_ms)

    # Get overall health score
    health_score = observer.get_overall_health_score()
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
import logging
import math
from typing import TYPE_CHECKING, Final

from aiohomematic import i18n
from aiohomematic.central.event_bus import EventPriority
from aiohomematic.metrics.events import (
    CounterMetricEvent,
    GaugeMetricEvent,
    HealthMetricEvent,
    LatencyMetricEvent,
    MetricType,
)
from aiohomematic.metrics.keys import MetricKey
from aiohomematic.metrics.stats import LatencyStats

if TYPE_CHECKING:
    from collections.abc import Callable

    from aiohomematic.central.event_bus import EventBus

_LOGGER: Final = logging.getLogger(__name__)

# Maximum number of unique metric keys to prevent unbounded growth
MAX_METRIC_KEYS: Final = 10_000


@dataclass(slots=True)
class LatencyTracker:
    """Tracks latency statistics for a single metric key."""

    count: int = 0
    total_ms: float = 0.0
    min_ms: float = math.inf
    max_ms: float = 0.0

    @property
    def avg_ms(self) -> float:
        """Return average latency in milliseconds."""
        if self.count == 0:
            return 0.0
        return self.total_ms / self.count

    def copy(self) -> LatencyTracker:
        """Return a copy of this tracker."""
        return LatencyTracker(
            count=self.count,
            total_ms=self.total_ms,
            min_ms=self.min_ms,
            max_ms=self.max_ms,
        )

    def record(self, *, duration_ms: float) -> None:
        """Record a latency sample."""
        self.count += 1
        self.total_ms += duration_ms
        self.min_ms = min(self.min_ms, duration_ms)
        self.max_ms = max(self.max_ms, duration_ms)

    def reset(self) -> None:
        """Reset all statistics."""
        self.count = 0
        self.total_ms = 0.0
        self.min_ms = math.inf
        self.max_ms = 0.0

    def to_stats(self) -> LatencyStats:
        """
        Convert to LatencyStats for external consumption.

        Returns:
            LatencyStats snapshot of current state.

        """
        return LatencyStats(
            count=self.count,
            total_ms=self.total_ms,
            min_ms=self.min_ms,
            max_ms=self.max_ms,
        )


# Type alias for key parameter
KeyType = MetricKey | str


@dataclass(slots=True)
class HealthState:
    """Tracks health state for a component."""

    healthy: bool = True
    reason: str | None = None
    last_change: datetime = field(default_factory=datetime.now)

    def update(self, *, healthy: bool, reason: str | None = None) -> None:
        """Update health state."""
        if self.healthy != healthy:
            self.last_change = datetime.now()
        self.healthy = healthy
        self.reason = reason


@dataclass(frozen=True, slots=True)
class ObserverSnapshot:
    """
    Point-in-time snapshot of all collected metrics.

    Provides a consistent view of metrics at a specific moment.
    """

    timestamp: datetime
    """When the snapshot was taken."""

    latency: dict[str, LatencyTracker]
    """Latency metrics by full key."""

    counters: dict[str, int]
    """Counter metrics by full key."""

    gauges: dict[str, float]
    """Gauge metrics by full key."""

    health: dict[str, HealthState]
    """Health states by component key."""

    def aggregate_counters(self, *, pattern: str) -> int:
        """
        Aggregate counter metrics matching a pattern.

        Args:
            pattern: Key prefix to match

        Returns:
            Sum of matching counters

        """
        total = 0
        for key, value in self.counters.items():
            if key.startswith(pattern):
                total += value
        return total

    def aggregate_latency(self, *, pattern: str) -> LatencyTracker:
        """
        Aggregate latency metrics matching a pattern.

        Args:
            pattern: Key prefix to match (e.g., "ping_pong" matches all ping_pong:* keys)

        Returns:
            Aggregated LatencyTracker

        """
        result = LatencyTracker()
        for key, tracker in self.latency.items():
            if key.startswith(pattern):
                result.count += tracker.count
                result.total_ms += tracker.total_ms
                result.min_ms = min(result.min_ms, tracker.min_ms)
                result.max_ms = max(result.max_ms, tracker.max_ms)
        return result

    def get_counter(self, *, key: str, default: int = 0) -> int:
        """Get counter value for a key."""
        return self.counters.get(key, default)

    def get_gauge(self, *, key: str, default: float = 0.0) -> float:
        """Get gauge value for a key."""
        return self.gauges.get(key, default)

    def get_latency(self, *, key: str, default: float = 0.0) -> float:
        """Get average latency for a key."""
        if tracker := self.latency.get(key):
            return tracker.avg_ms
        return default

    def get_rate(self, *, hit_key: str, miss_key: str) -> float:
        """Calculate hit rate from hit and miss counters."""
        hits = self.counters.get(hit_key, 0)
        misses = self.counters.get(miss_key, 0)
        if (total := hits + misses) == 0:
            return 100.0
        return (hits / total) * 100


class MetricsObserver:
    """
    Central observer that subscribes to metric events and maintains aggregated statistics.

    This class replaces the polling-based approach of MetricsAggregator with
    event-driven collection. Components emit metric events to the EventBus,
    and this observer aggregates them into queryable statistics.

    Features:
    - Subscribes to all metric event types with LOW priority
    - Maintains rolling statistics without blocking productive code
    - Provides thread-safe snapshot export
    - Limits metric key count to prevent unbounded growth
    - Computes derived metrics (overall health score, last event age)
    """

    __slots__ = (
        "_counters",
        "_event_bus",
        "_gauges",
        "_health",
        "_last_event_time",
        "_latency",
        "_unsubscribers",
    )

    def __init__(self, *, event_bus: EventBus) -> None:
        """
        Initialize the metrics observer.

        Args:
            event_bus: EventBus to subscribe to for metric events

        """
        self._event_bus: Final = event_bus
        self._latency: dict[str, LatencyTracker] = defaultdict(LatencyTracker)
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, float] = {}
        self._health: dict[str, HealthState] = defaultdict(HealthState)
        self._last_event_time: datetime | None = None
        self._unsubscribers: list[Callable[[], None]] = []

        self._subscribe_to_events()

    @property
    def counter_keys(self) -> list[str]:
        """Return all counter metric keys."""
        return list(self._counters.keys())

    @property
    def gauge_keys(self) -> list[str]:
        """Return all gauge metric keys."""
        return list(self._gauges.keys())

    @property
    def health_keys(self) -> list[str]:
        """Return all health metric keys."""
        return list(self._health.keys())

    @property
    def latency_keys(self) -> list[str]:
        """Return all latency metric keys."""
        return list(self._latency.keys())

    def clear(self) -> None:
        """Clear all collected metrics."""
        self._latency.clear()
        self._counters.clear()
        self._gauges.clear()
        self._health.clear()
        self._last_event_time = None
        _LOGGER.debug("METRICS OBSERVER: Cleared all metrics")

    def get_aggregated_counter(self, *, pattern: str) -> int:
        """
        Get sum of counters for all keys matching a pattern.

        Args:
            pattern: Key prefix to match

        Returns:
            Sum of matching counters

        """
        total = 0
        for key, value in self._counters.items():
            if key.startswith(pattern):
                total += value
        return total

    def get_aggregated_latency(self, *, pattern: str) -> LatencyTracker:
        """
        Get aggregated latency for all keys matching a pattern.

        Args:
            pattern: Key prefix to match

        Returns:
            Aggregated LatencyTracker

        """
        result = LatencyTracker()
        for key, tracker in self._latency.items():
            if key.startswith(pattern):
                result.count += tracker.count
                result.total_ms += tracker.total_ms
                if tracker.min_ms != math.inf:
                    result.min_ms = min(result.min_ms, tracker.min_ms)
                result.max_ms = max(result.max_ms, tracker.max_ms)
        return result

    def get_counter(self, *, key: KeyType, default: int = 0) -> int:
        """
        Get counter value for a key.

        Args:
            key: Metric key (MetricKey instance or string).
            default: Default value if key not found.

        Returns:
            Counter value.

        """
        return self._counters.get(str(key), default)

    def get_gauge(self, *, key: KeyType, default: float = 0.0) -> float:
        """
        Get gauge value for a key.

        Args:
            key: Metric key (MetricKey instance or string).
            default: Default value if key not found.

        Returns:
            Gauge value.

        """
        return self._gauges.get(str(key), default)

    def get_health(self, *, key: KeyType) -> HealthState | None:
        """
        Get health state for a key.

        Args:
            key: Metric key (MetricKey instance or string).

        Returns:
            HealthState or None if not found.

        """
        return self._health.get(str(key))

    def get_keys_by_prefix(self, *, prefix: str) -> list[str]:
        """
        Get all metric keys matching a prefix.

        Args:
            prefix: Key prefix to match (e.g., "handler.execution").

        Returns:
            List of matching keys.

        """
        # Collect all keys from all metric types, deduplicated
        all_keys: set[str] = set()
        all_keys.update(self._latency.keys())
        all_keys.update(self._counters.keys())
        all_keys.update(self._gauges.keys())
        all_keys.update(self._health.keys())
        return [key for key in all_keys if key.startswith(prefix)]

    def get_last_event_age_seconds(self) -> float:
        """
        Get seconds since last metric event was received.

        Returns:
            Seconds since last event, or -1.0 if no events received yet

        """
        if self._last_event_time is None:
            return -1.0
        return (datetime.now() - self._last_event_time).total_seconds()

    def get_last_event_time(self) -> datetime | None:
        """Return the timestamp of the last received event."""
        return self._last_event_time

    def get_latency(self, *, key: KeyType) -> LatencyTracker | None:
        """
        Get latency tracker for a key.

        Args:
            key: Metric key (MetricKey instance or string).

        Returns:
            LatencyTracker or None if not found.

        """
        return self._latency.get(str(key))

    def get_metric(self, *, key: KeyType, metric_type: MetricType) -> float:
        """
        Get a single metric value by key and type.

        Args:
            key: Metric key (MetricKey instance or string).
            metric_type: Type of metric to retrieve.

        Returns:
            The metric value (float).

        """
        key_str = str(key)
        if metric_type == MetricType.LATENCY:
            if tracker := self._latency.get(key_str):
                return tracker.avg_ms
            return 0.0
        if metric_type == MetricType.COUNTER:
            return float(self._counters.get(key_str, 0))
        if metric_type == MetricType.GAUGE:
            return self._gauges.get(key_str, 0.0)
        # MetricType.HEALTH
        if health := self._health.get(key_str):
            return 100.0 if health.healthy else 0.0
        return 100.0  # Default to healthy

    def get_overall_health_score(self) -> float:
        """
        Compute overall health score from all tracked health states.

        Returns:
            Health score as a value between 0.0 and 1.0

        """
        if not self._health:
            return 1.0  # Default to healthy if no health data

        healthy_count = sum(1 for h in self._health.values() if h.healthy)
        return healthy_count / len(self._health)

    def record_event_received(self) -> None:
        """Record that an event was received (for last_event_time tracking)."""
        self._last_event_time = datetime.now()

    def snapshot(self) -> ObserverSnapshot:
        """
        Export a consistent snapshot of all metrics.

        Returns:
            ObserverSnapshot with copies of all metric data

        """
        return ObserverSnapshot(
            timestamp=datetime.now(),
            latency={k: v.copy() for k, v in self._latency.items()},
            counters=dict(self._counters),
            gauges=dict(self._gauges),
            health={
                k: HealthState(healthy=v.healthy, reason=v.reason, last_change=v.last_change)
                for k, v in self._health.items()
            },
        )

    def stop(self) -> None:
        """Unsubscribe from all events."""
        for unsub in self._unsubscribers:
            unsub()
        self._unsubscribers.clear()
        _LOGGER.debug("METRICS OBSERVER: Unsubscribed from all events")

    async def _handle_counter(self, *, event: CounterMetricEvent) -> None:
        """Handle counter metric event."""
        if len(self._counters) >= MAX_METRIC_KEYS:
            _LOGGER.warning(i18n.tr(key="log.metrics.observer.counter_key_limit", metric_key=event.metric_key))
            return
        self._counters[event.metric_key] += event.delta
        self._last_event_time = event.timestamp

    async def _handle_gauge(self, *, event: GaugeMetricEvent) -> None:
        """Handle gauge metric event."""
        if len(self._gauges) >= MAX_METRIC_KEYS:
            _LOGGER.warning(i18n.tr(key="log.metrics.observer.gauge_key_limit", metric_key=event.metric_key))
            return
        self._gauges[event.metric_key] = event.value
        self._last_event_time = event.timestamp

    async def _handle_health(self, *, event: HealthMetricEvent) -> None:
        """Handle health metric event."""
        self._health[event.metric_key].update(healthy=event.healthy, reason=event.reason)
        self._last_event_time = event.timestamp

    async def _handle_latency(self, *, event: LatencyMetricEvent) -> None:
        """Handle latency metric event."""
        if len(self._latency) >= MAX_METRIC_KEYS:
            _LOGGER.warning(i18n.tr(key="log.metrics.observer.latency_key_limit", metric_key=event.metric_key))
            return
        self._latency[event.metric_key].record(duration_ms=event.duration_ms)
        self._last_event_time = event.timestamp

    def _subscribe_to_events(self) -> None:
        """Subscribe to all metric event types with LOW priority."""
        # Latency events
        unsub = self._event_bus.subscribe(
            event_type=LatencyMetricEvent,
            event_key=None,
            handler=self._handle_latency,
            priority=EventPriority.LOW,
        )
        self._unsubscribers.append(unsub)

        # Counter events
        unsub = self._event_bus.subscribe(
            event_type=CounterMetricEvent,
            event_key=None,
            handler=self._handle_counter,
            priority=EventPriority.LOW,
        )
        self._unsubscribers.append(unsub)

        # Gauge events
        unsub = self._event_bus.subscribe(
            event_type=GaugeMetricEvent,
            event_key=None,
            handler=self._handle_gauge,
            priority=EventPriority.LOW,
        )
        self._unsubscribers.append(unsub)

        # Health events
        unsub = self._event_bus.subscribe(
            event_type=HealthMetricEvent,
            event_key=None,
            handler=self._handle_health,
            priority=EventPriority.LOW,
        )
        self._unsubscribers.append(unsub)

        _LOGGER.debug("METRICS OBSERVER: Subscribed to all metric event types")
