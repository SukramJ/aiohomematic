# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Metrics collection, aggregation, and observability.

This module provides both event-driven and polling-based metrics collection.

Event-Driven Metrics (MetricsObserver)
--------------------------------------
Components emit metric events to the EventBus, and MetricsObserver aggregates them.
Use emit_* functions to emit metrics and MetricsObserver to query them.

Polling-Based Metrics (MetricsAggregator)
-----------------------------------------
MetricsAggregator queries system components directly to collect metrics.
Use for comprehensive system snapshots.

Public API
----------
Event-driven:
- MetricEvent, LatencyMetricEvent, CounterMetricEvent, GaugeMetricEvent, HealthMetricEvent
- MetricsObserver, ObserverSnapshot, LatencyTracker, HealthState
- emit_latency, emit_counter, emit_gauge, emit_health
- MetricEmitterMixin, LatencyContext

Polling-based:
- MetricsAggregator, MetricsSnapshot
- RpcMetrics, EventMetrics, CacheMetrics, HealthMetrics
- RecoveryMetrics, ModelMetrics, ServiceMetrics

Note: Protocol dependencies for MetricsAggregator are in aiohomematic.interfaces:
- ClientProviderForMetricsProtocol
- DeviceProviderForMetricsProtocol
- HubDataPointManagerForMetricsProtocol

Service tracking:
- record_service_call, get_service_stats, clear_service_stats
"""

from __future__ import annotations

from aiohomematic.metrics.aggregator import MetricsAggregator
from aiohomematic.metrics.dataclasses import (
    CacheMetrics,
    EventMetrics,
    HealthMetrics,
    MetricsSnapshot,
    ModelMetrics,
    RecoveryMetrics,
    RpcMetrics,
    ServiceMetrics,
)
from aiohomematic.metrics.emitter import (
    EventBusProviderProtocol,
    LatencyContext,
    MetricEmitterMixin,
    emit_counter,
    emit_gauge,
    emit_health,
    emit_latency,
)
from aiohomematic.metrics.events import (
    METRIC_EVENT_TYPES,
    AnyMetricEvent,
    CounterMetricEvent,
    GaugeMetricEvent,
    HealthMetricEvent,
    LatencyMetricEvent,
    MetricEvent,
    MetricType,
)
from aiohomematic.metrics.keys import MetricKey, MetricKeys
from aiohomematic.metrics.observer import (
    MAX_METRIC_KEYS,
    HealthState,
    LatencyTracker,
    MetricsObserver,
    ObserverSnapshot,
)
from aiohomematic.metrics.service import clear_service_stats, get_service_stats, record_service_call
from aiohomematic.metrics.stats import CacheStats, LatencyStats, ServiceStats

__all__ = [
    # Aggregator
    "MetricsAggregator",
    # Dataclasses
    "CacheMetrics",
    "EventMetrics",
    "HealthMetrics",
    "MetricsSnapshot",
    "ModelMetrics",
    "RecoveryMetrics",
    "RpcMetrics",
    "ServiceMetrics",
    # Emitter
    "EventBusProviderProtocol",
    "LatencyContext",
    "MetricEmitterMixin",
    "emit_counter",
    "emit_gauge",
    "emit_health",
    "emit_latency",
    # Events
    "AnyMetricEvent",
    "CounterMetricEvent",
    "GaugeMetricEvent",
    "HealthMetricEvent",
    "LatencyMetricEvent",
    "METRIC_EVENT_TYPES",
    "MetricEvent",
    "MetricType",
    # Keys
    "MetricKey",
    "MetricKeys",
    # Observer
    "HealthState",
    "LatencyTracker",
    "MAX_METRIC_KEYS",
    "MetricsObserver",
    "ObserverSnapshot",
    # Service
    "clear_service_stats",
    "get_service_stats",
    "record_service_call",
    # Stats
    "CacheStats",
    "LatencyStats",
    "ServiceStats",
]
