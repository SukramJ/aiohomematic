# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Metric event types for event-driven metrics collection.

This module defines the event hierarchy for metrics emission. Components emit
these events to the EventBus, where MetricsObserver aggregates them.

Event Types
-----------
- LatencyMetricEvent: For timing measurements (RPC calls, ping/pong, handlers)
- CounterMetricEvent: For countable events (cache hits, failures, successes)
- GaugeMetricEvent: For current-value metrics (queue depth, connection count)
- HealthMetricEvent: For health state changes (client health, circuit breaker)

Usage
-----
    from aiohomematic.metrics import MetricKeys, emit_latency

    # Emit latency metric with type-safe key
    emit_latency(
        event_bus=event_bus,
        key=MetricKeys.ping_pong_rtt(interface_id="hmip_rf"),
        duration_ms=45.2,
    )
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final

from aiohomematic.central.events import Event


class MetricType(Enum):
    """Type of metric for categorization."""

    LATENCY = "latency"
    COUNTER = "counter"
    GAUGE = "gauge"
    HEALTH = "health"


@dataclass(frozen=True, slots=True)
class MetricEvent(Event):
    """
    Base class for all metric events.

    All metric events share a common metric_key field that identifies
    the metric. The key follows the pattern: {component}.{metric}.{identifier}
    """

    metric_key: str
    """
    Full metric key identifying this metric.

    Pattern: {component}.{metric}.{identifier}
    Examples: "ping_pong.rtt.hmip_rf", "cache.data.hit", "handler.execution.DataPointValueReceivedEvent"
    """

    @property
    def key(self) -> str:
        """Return the event key for EventBus routing."""
        return self.metric_key


@dataclass(frozen=True, slots=True)
class LatencyMetricEvent(MetricEvent):
    """
    Event for timing measurements.

    Emitted when an operation completes to record its duration.
    Used for RPC calls, ping/pong round-trips, handler execution, etc.
    """

    duration_ms: float = 0.0
    """Duration of the operation in milliseconds."""


@dataclass(frozen=True, slots=True)
class CounterMetricEvent(MetricEvent):
    """
    Event for countable occurrences.

    Emitted when a countable event occurs (cache hit, RPC success, failure, etc.).
    """

    delta: int = 1
    """Amount to change the counter by (default: 1)."""


@dataclass(frozen=True, slots=True)
class GaugeMetricEvent(MetricEvent):
    """
    Event for current-value metrics.

    Emitted when a gauge value changes (queue depth, connection count, etc.).
    Unlike counters, gauges represent the current state, not a delta.
    """

    value: float = 0.0
    """Current value of the gauge."""


@dataclass(frozen=True, slots=True)
class HealthMetricEvent(MetricEvent):
    """
    Event for health state changes.

    Emitted when a component's health state changes.
    """

    healthy: bool = True
    """Whether the component is healthy."""

    reason: str | None = None
    """Optional reason for the health state (especially for unhealthy)."""


# =============================================================================
# Self-Healing Events
# =============================================================================


@dataclass(frozen=True, slots=True)
class SelfHealingTriggeredEvent(Event):
    """
    Emitted when self-healing coordinator reacts to a circuit breaker event.

    Key is interface_id.

    This event allows external observers (like MetricsAggregator) to track
    self-healing activity without the coordinator maintaining internal stats.
    """

    interface_id: str
    action: str  # "trip_logged", "recovery_initiated", "data_refresh_scheduled"
    details: str | None

    @property
    def key(self) -> str:
        """Return interface_id as key."""
        return self.interface_id


@dataclass(frozen=True, slots=True)
class SelfHealingDataRefreshEvent(Event):
    """
    Emitted after self-healing data refresh completes.

    Key is interface_id.

    Allows subscribers to track data refresh success/failure.
    """

    interface_id: str
    success: bool
    error_message: str | None

    @property
    def key(self) -> str:
        """Return interface_id as key."""
        return self.interface_id


# Type alias for any metric event
AnyMetricEvent = LatencyMetricEvent | CounterMetricEvent | GaugeMetricEvent | HealthMetricEvent

# All metric event types for subscription
METRIC_EVENT_TYPES: Final = (
    LatencyMetricEvent,
    CounterMetricEvent,
    GaugeMetricEvent,
    HealthMetricEvent,
)

# Self-healing event types for subscription
SELF_HEALING_EVENT_TYPES: Final = (
    SelfHealingTriggeredEvent,
    SelfHealingDataRefreshEvent,
)
