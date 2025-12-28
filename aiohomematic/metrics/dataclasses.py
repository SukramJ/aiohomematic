# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Metrics dataclasses for system observability.

This module provides frozen dataclasses for metric snapshots.
All classes are immutable to ensure thread-safe access.

Public API
----------
- RpcMetrics: RPC communication metrics
- EventMetrics: EventBus metrics
- CacheMetrics: Cache statistics
- HealthMetrics: Connection health metrics
- RecoveryMetrics: Recovery statistics
- ModelMetrics: Model statistics
- ServiceMetrics: Service call statistics
- MetricsSnapshot: Point-in-time snapshot of all metrics
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from aiohomematic.const import INIT_DATETIME
from aiohomematic.metrics.stats import CacheStats, ServiceStats

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass(frozen=True, slots=True)
class RpcMetrics:
    """
    RPC communication metrics aggregated from all clients.

    Combines CircuitBreaker and RequestCoalescer metrics.
    """

    total_requests: int = 0
    """Total number of RPC requests made."""

    successful_requests: int = 0
    """Number of successful RPC requests."""

    failed_requests: int = 0
    """Number of failed RPC requests."""

    rejected_requests: int = 0
    """Number of requests rejected by circuit breakers."""

    coalesced_requests: int = 0
    """Number of requests that were coalesced (avoided execution)."""

    executed_requests: int = 0
    """Number of requests that actually executed."""

    pending_requests: int = 0
    """Currently in-flight requests."""

    circuit_breakers_open: int = 0
    """Number of circuit breakers in OPEN state."""

    circuit_breakers_half_open: int = 0
    """Number of circuit breakers in HALF_OPEN state."""

    state_transitions: int = 0
    """Total circuit breaker state transitions."""

    avg_latency_ms: float = 0.0
    """Average request latency in milliseconds."""

    max_latency_ms: float = 0.0
    """Maximum request latency in milliseconds."""

    last_failure_time: datetime | None = None
    """Timestamp of last failure."""

    @property
    def coalesce_rate(self) -> float:
        """Return coalesce rate as percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.coalesced_requests / self.total_requests) * 100

    @property
    def failure_rate(self) -> float:
        """Return failure rate as percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.failed_requests / self.total_requests) * 100

    @property
    def rejection_rate(self) -> float:
        """Return rejection rate as percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.rejected_requests / self.total_requests) * 100

    @property
    def success_rate(self) -> float:
        """Return success rate as percentage."""
        if self.total_requests == 0:
            return 100.0
        return (self.successful_requests / self.total_requests) * 100


@dataclass(frozen=True, slots=True)
class EventMetrics:
    """EventBus metrics."""

    total_published: int = 0
    """Total events published."""

    total_subscriptions: int = 0
    """Active subscription count."""

    handlers_executed: int = 0
    """Total handler executions."""

    handler_errors: int = 0
    """Handler exceptions caught."""

    avg_handler_duration_ms: float = 0.0
    """Average handler execution time in milliseconds."""

    max_handler_duration_ms: float = 0.0
    """Maximum handler execution time in milliseconds."""

    events_by_type: Mapping[str, int] = field(default_factory=dict)
    """Event counts per type."""

    # Operational event counters
    circuit_breaker_trips: int = 0
    """Number of CircuitBreakerTrippedEvent events."""

    state_changes: int = 0
    """Number of ClientStateChangedEvent + CentralStateChangedEvent events."""

    data_refreshes_triggered: int = 0
    """Number of DataRefreshTriggeredEvent events."""

    data_refreshes_completed: int = 0
    """Number of DataRefreshCompletedEvent events."""

    programs_executed: int = 0
    """Number of ProgramExecutedEvent events."""

    requests_coalesced: int = 0
    """Number of RequestCoalescedEvent events."""

    @property
    def error_rate(self) -> float:
        """Return handler error rate as percentage."""
        if self.handlers_executed == 0:
            return 0.0
        return (self.handler_errors / self.handlers_executed) * 100


@dataclass(frozen=True, slots=True)
class CacheMetrics:
    """Aggregated cache metrics."""

    device_descriptions: CacheStats = field(default_factory=CacheStats)
    """Device description cache stats."""

    paramset_descriptions: CacheStats = field(default_factory=CacheStats)
    """Paramset description cache stats."""

    data_cache: CacheStats = field(default_factory=CacheStats)
    """Central data cache stats."""

    command_cache: CacheStats = field(default_factory=CacheStats)
    """Command cache stats."""

    ping_pong_cache: CacheStats = field(default_factory=CacheStats)
    """Ping-pong cache stats."""

    visibility_cache: CacheStats = field(default_factory=CacheStats)
    """Visibility cache stats."""

    @property
    def overall_hit_rate(self) -> float:
        """Return overall cache hit rate."""
        total_hits = self.device_descriptions.hits + self.paramset_descriptions.hits + self.data_cache.hits
        total_misses = self.device_descriptions.misses + self.paramset_descriptions.misses + self.data_cache.misses
        if (total := total_hits + total_misses) == 0:
            return 100.0
        return (total_hits / total) * 100

    @property
    def total_entries(self) -> int:
        """Return total cached entries across all caches."""
        return (
            self.device_descriptions.size
            + self.paramset_descriptions.size
            + self.data_cache.size
            + self.command_cache.size
            + self.ping_pong_cache.size
            + self.visibility_cache.size
        )


@dataclass(frozen=True, slots=True)
class HealthMetrics:
    """Connection health metrics."""

    overall_score: float = 1.0
    """Weighted health score (0.0 - 1.0)."""

    clients_total: int = 0
    """Total registered clients."""

    clients_healthy: int = 0
    """Healthy client count."""

    clients_degraded: int = 0
    """Degraded client count."""

    clients_failed: int = 0
    """Failed client count."""

    reconnect_attempts: int = 0
    """Total reconnect attempts."""

    last_event_time: datetime = field(default=INIT_DATETIME)
    """Timestamp of last backend event."""

    @property
    def availability_rate(self) -> float:
        """Return client availability as percentage."""
        if self.clients_total == 0:
            return 100.0
        return (self.clients_healthy / self.clients_total) * 100

    @property
    def last_event_age_seconds(self) -> float:
        """Return seconds since last event."""
        if self.last_event_time == INIT_DATETIME:
            return -1.0
        return (datetime.now() - self.last_event_time).total_seconds()


@dataclass(frozen=True, slots=True)
class RecoveryMetrics:
    """Recovery statistics."""

    attempts_total: int = 0
    """Total recovery attempts."""

    successes: int = 0
    """Successful recoveries."""

    failures: int = 0
    """Failed recoveries."""

    max_retries_reached: int = 0
    """Times max retry limit was hit."""

    in_progress: bool = False
    """Recovery currently active."""

    last_recovery_time: datetime | None = None
    """Timestamp of last recovery attempt."""

    @property
    def success_rate(self) -> float:
        """Return recovery success rate."""
        if self.attempts_total == 0:
            return 100.0
        return (self.successes / self.attempts_total) * 100


@dataclass(frozen=True, slots=True)
class ModelMetrics:
    """Model statistics."""

    devices_total: int = 0
    """Total devices."""

    devices_available: int = 0
    """Available devices."""

    channels_total: int = 0
    """Total channels."""

    data_points_generic: int = 0
    """Generic data points."""

    data_points_custom: int = 0
    """Custom data points."""

    data_points_calculated: int = 0
    """Calculated data points."""

    data_points_subscribed: int = 0
    """Data points with active subscriptions."""

    programs_total: int = 0
    """Hub programs."""

    sysvars_total: int = 0
    """System variables."""


@dataclass(frozen=True, slots=True)
class ServiceMetrics:
    """
    Aggregated service method metrics (immutable snapshot).

    Provides statistics for all service methods decorated with
    @inspector(measure_performance=True).
    """

    total_calls: int = 0
    """Total calls across all methods."""

    total_errors: int = 0
    """Total errors across all methods."""

    avg_duration_ms: float = 0.0
    """Average duration across all calls."""

    max_duration_ms: float = 0.0
    """Maximum duration across all calls."""

    by_method: Mapping[str, ServiceStats] = field(default_factory=dict)
    """Statistics per method name."""

    @property
    def error_rate(self) -> float:
        """Return overall error rate as percentage."""
        if self.total_calls == 0:
            return 0.0
        return (self.total_errors / self.total_calls) * 100


@dataclass(frozen=True, slots=True)
class MetricsSnapshot:
    """Point-in-time snapshot of all system metrics."""

    timestamp: datetime = field(default_factory=datetime.now)
    """Snapshot timestamp."""

    rpc: RpcMetrics = field(default_factory=RpcMetrics)
    """RPC communication metrics."""

    events: EventMetrics = field(default_factory=EventMetrics)
    """EventBus metrics."""

    cache: CacheMetrics = field(default_factory=CacheMetrics)
    """Cache statistics."""

    health: HealthMetrics = field(default_factory=HealthMetrics)
    """Connection health metrics."""

    recovery: RecoveryMetrics = field(default_factory=RecoveryMetrics)
    """Recovery statistics."""

    model: ModelMetrics = field(default_factory=ModelMetrics)
    """Model statistics."""

    services: ServiceMetrics = field(default_factory=ServiceMetrics)
    """Service call statistics."""
