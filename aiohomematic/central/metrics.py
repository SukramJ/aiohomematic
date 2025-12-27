# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Central metrics aggregation and observability.

This module provides a unified interface for accessing system metrics
from various components (CircuitBreaker, RequestCoalescer, EventBus,
Health, Caches, Service calls). It aggregates scattered metrics into
a single access point.

Phase 1: Aggregation of existing metrics
Phase 2: Enhanced instrumentation (latency, cache hits, handler duration)
Phase 3: Service call metrics via @inspector decorator

Public API
----------
- MetricsAggregator: Main class for aggregating metrics
- RpcMetrics: RPC communication metrics
- EventMetrics: EventBus metrics
- CacheMetrics: Cache statistics
- HealthMetrics: Connection health metrics
- RecoveryMetrics: Recovery statistics
- ModelMetrics: Model statistics
- ServiceMetrics: Service call statistics
- MetricsSnapshot: Point-in-time snapshot of all metrics
- record_service_call: Record a service call for metrics
- get_service_stats: Get service stats for a central
- clear_service_stats: Clear service stats for a central
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import threading
from typing import TYPE_CHECKING, Any, Final

from aiohomematic.client.circuit_breaker import CircuitState
from aiohomematic.const import INIT_DATETIME

if TYPE_CHECKING:
    from collections.abc import Mapping

    from aiohomematic.central.event_bus import EventBus
    from aiohomematic.central.health import HealthTracker
    from aiohomematic.central.recovery import RecoveryCoordinator
    from aiohomematic.interfaces.client import ClientProtocol
    from aiohomematic.interfaces.model import DeviceProtocol
    from aiohomematic.store.dynamic.data import CentralDataCache


# =============================================================================
# Metric Dataclasses
# =============================================================================


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

    @property
    def error_rate(self) -> float:
        """Return handler error rate as percentage."""
        if self.handlers_executed == 0:
            return 0.0
        return (self.handler_errors / self.handlers_executed) * 100


@dataclass(frozen=True, slots=True)
class CacheStats:
    """Statistics for a single cache."""

    size: int = 0
    """Current number of entries."""

    hits: int = 0
    """Cache hits."""

    misses: int = 0
    """Cache misses."""

    evictions: int = 0
    """Entries evicted."""

    @property
    def hit_rate(self) -> float:
        """Return hit rate as percentage."""
        if (total := self.hits + self.misses) == 0:
            return 100.0
        return (self.hits / total) * 100


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


# =============================================================================
# Service Call Metrics
# =============================================================================


@dataclass(slots=True)
class ServiceStats:
    """
    Mutable statistics for a single service method.

    This class tracks call counts, errors, and timing for service methods
    decorated with @inspector(measure_performance=True).
    """

    call_count: int = 0
    """Total number of calls to this method."""

    error_count: int = 0
    """Number of calls that raised exceptions."""

    total_duration_ms: float = 0.0
    """Total execution time in milliseconds."""

    max_duration_ms: float = 0.0
    """Maximum execution time in milliseconds."""

    @property
    def avg_duration_ms(self) -> float:
        """Return average execution time in milliseconds."""
        if self.call_count == 0:
            return 0.0
        return self.total_duration_ms / self.call_count

    @property
    def error_rate(self) -> float:
        """Return error rate as percentage."""
        if self.call_count == 0:
            return 0.0
        return (self.error_count / self.call_count) * 100

    def record(self, *, duration_ms: float, had_error: bool) -> None:
        """Record a service call."""
        self.call_count += 1
        self.total_duration_ms += duration_ms
        self.max_duration_ms = max(self.max_duration_ms, duration_ms)
        if had_error:
            self.error_count += 1

    def reset(self) -> None:
        """Reset all statistics."""
        self.call_count = 0
        self.error_count = 0
        self.total_duration_ms = 0.0
        self.max_duration_ms = 0.0


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


# =============================================================================
# Service Stats Global Registry
# =============================================================================

# Registry keyed by (central_name, method_name) for multi-Central isolation
_SERVICE_STATS_REGISTRY: dict[tuple[str, str], ServiceStats] = {}
_SERVICE_STATS_LOCK: Final = threading.Lock()


def record_service_call(
    *,
    central_name: str,
    method_name: str,
    duration_ms: float,
    had_error: bool,
) -> None:
    """
    Record a service call for metrics.

    Called by @inspector decorator when measure_performance=True.

    Args:
        central_name: Name of the CentralUnit (for multi-Central isolation)
        method_name: Name of the service method
        duration_ms: Execution duration in milliseconds
        had_error: Whether the call raised an exception

    """
    key = (central_name, method_name)
    with _SERVICE_STATS_LOCK:
        if key not in _SERVICE_STATS_REGISTRY:
            _SERVICE_STATS_REGISTRY[key] = ServiceStats()
        _SERVICE_STATS_REGISTRY[key].record(duration_ms=duration_ms, had_error=had_error)


def get_service_stats(*, central_name: str) -> dict[str, ServiceStats]:
    """
    Get service statistics for a specific central.

    Args:
        central_name: Name of the CentralUnit

    Returns:
        Dictionary mapping method names to their statistics

    """
    with _SERVICE_STATS_LOCK:
        return {
            method_name: stats for (cn, method_name), stats in _SERVICE_STATS_REGISTRY.items() if cn == central_name
        }


def clear_service_stats(*, central_name: str | None = None) -> None:
    """
    Clear service statistics.

    Args:
        central_name: If provided, clear only stats for this central.
                     If None, clear all stats.

    """
    with _SERVICE_STATS_LOCK:
        if central_name is None:
            _SERVICE_STATS_REGISTRY.clear()
        else:
            keys_to_remove = [key for key in _SERVICE_STATS_REGISTRY if key[0] == central_name]
            for key in keys_to_remove:
                del _SERVICE_STATS_REGISTRY[key]


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


# =============================================================================
# Metrics Aggregator
# =============================================================================


class MetricsAggregator:
    """
    Aggregate metrics from various system components.

    Provides a unified interface for accessing all system metrics.
    This class collects data from:
    - CircuitBreaker (per client)
    - RequestCoalescer (per client)
    - EventBus
    - HealthTracker
    - RecoveryCoordinator
    - Various caches
    - Device registry

    Example:
    -------
    ```python
    aggregator = MetricsAggregator(
        client_provider=central,
        event_bus=central.event_bus,
        health_tracker=central.health_tracker,
        ...
    )

    # Get individual metric categories
    rpc_metrics = aggregator.rpc
    event_metrics = aggregator.events

    # Get full snapshot
    snapshot = aggregator.snapshot()
    ```

    """

    __slots__ = (
        "_central_name",
        "_client_provider",
        "_data_cache",
        "_device_provider",
        "_event_bus",
        "_health_tracker",
        "_hub_data_point_manager",
        "_recovery_coordinator",
    )

    def __init__(
        self,
        *,
        central_name: str,
        client_provider: _ClientProviderForMetrics,
        device_provider: _DeviceProviderForMetrics,
        event_bus: EventBus,
        health_tracker: HealthTracker,
        data_cache: CentralDataCache,
        hub_data_point_manager: _HubDataPointManagerForMetrics | None = None,
        recovery_coordinator: RecoveryCoordinator | None = None,
    ) -> None:
        """
        Initialize the metrics aggregator.

        Args:
            central_name: Name of the CentralUnit (for service stats isolation)
            client_provider: Provider for client access
            device_provider: Provider for device access
            event_bus: The EventBus instance
            health_tracker: The HealthTracker instance
            data_cache: The CentralDataCache instance
            hub_data_point_manager: Optional hub data point manager
            recovery_coordinator: Optional recovery coordinator

        """
        self._central_name: Final = central_name
        self._client_provider: Final = client_provider
        self._device_provider: Final = device_provider
        self._event_bus: Final = event_bus
        self._health_tracker: Final = health_tracker
        self._data_cache: Final = data_cache
        self._hub_data_point_manager: Final = hub_data_point_manager
        self._recovery_coordinator: Final = recovery_coordinator

    @property
    def cache(self) -> CacheMetrics:
        """Return cache statistics."""
        data_stats = self._data_cache.stats

        return CacheMetrics(
            data_cache=CacheStats(
                size=data_stats.size,
                hits=data_stats.hits,
                misses=data_stats.misses,
            ),
        )

    @property
    def events(self) -> EventMetrics:
        """Return EventBus metrics."""
        event_stats = self._event_bus.get_event_stats()
        handler_stats = self._event_bus.get_handler_stats()

        return EventMetrics(
            total_published=sum(event_stats.values()),
            total_subscriptions=self._event_bus.get_total_subscription_count(),
            handlers_executed=handler_stats.total_executions,
            handler_errors=handler_stats.total_errors,
            avg_handler_duration_ms=handler_stats.avg_duration_ms,
            max_handler_duration_ms=handler_stats.max_duration_ms,
            events_by_type=event_stats,
        )

    @property
    def health(self) -> HealthMetrics:
        """Return health metrics."""
        health = self._health_tracker.health
        clients_healthy = len(health.healthy_clients)
        clients_degraded = len(health.degraded_clients)
        clients_failed = len(health.failed_clients)

        return HealthMetrics(
            overall_score=health.overall_health_score,
            clients_total=clients_healthy + clients_degraded + clients_failed,
            clients_healthy=clients_healthy,
            clients_degraded=clients_degraded,
            clients_failed=clients_failed,
        )

    @property
    def model(self) -> ModelMetrics:
        """Return model statistics."""
        devices = self._device_provider.devices
        devices_available = sum(1 for d in devices if d.available)
        channels_total = sum(len(d.channels) for d in devices)

        generic_count = 0
        custom_count = 0
        calculated_count = 0

        for device in devices:
            for channel in device.channels.values():
                generic_count += len(channel.generic_data_points)
                calculated_count += len(channel.calculated_data_points)
                if channel.custom_data_point is not None:
                    custom_count += 1

        # Subscription counting available via EventBus.get_total_subscription_count()
        subscribed_count = self._event_bus.get_total_subscription_count()

        programs_total = 0
        sysvars_total = 0
        if self._hub_data_point_manager is not None:
            programs_total = len(self._hub_data_point_manager.program_data_points)
            sysvars_total = len(self._hub_data_point_manager.sysvar_data_points)

        return ModelMetrics(
            devices_total=len(devices),
            devices_available=devices_available,
            channels_total=channels_total,
            data_points_generic=generic_count,
            data_points_custom=custom_count,
            data_points_calculated=calculated_count,
            data_points_subscribed=subscribed_count,
            programs_total=programs_total,
            sysvars_total=sysvars_total,
        )

    @property
    def recovery(self) -> RecoveryMetrics:
        """Return recovery metrics."""
        # RecoveryCoordinator stats tracking to be added in future enhancement
        # For now, return default metrics
        return RecoveryMetrics()

    @property
    def rpc(self) -> RpcMetrics:
        """Return aggregated RPC metrics from all clients."""
        total_requests = 0
        successful_requests = 0
        failed_requests = 0
        rejected_requests = 0
        coalesced_requests = 0
        executed_requests = 0
        pending_requests = 0
        state_transitions = 0
        circuit_breakers_open = 0
        circuit_breakers_half_open = 0
        last_failure_time: datetime | None = None
        total_latency_ms = 0.0
        max_latency_ms = 0.0
        latency_count = 0

        for client in self._client_provider.clients:
            # Circuit breaker metrics (if available on this client type)
            if (cb := getattr(client, "circuit_breaker", None)) is not None:
                cb_metrics = cb.metrics
                total_requests += cb_metrics.total_requests
                successful_requests += cb_metrics.successful_requests
                failed_requests += cb_metrics.failed_requests
                rejected_requests += cb_metrics.rejected_requests
                state_transitions += cb_metrics.state_transitions

                if cb.state == CircuitState.OPEN:
                    circuit_breakers_open += 1
                elif cb.state == CircuitState.HALF_OPEN:
                    circuit_breakers_half_open += 1

                if cb_metrics.last_failure_time is not None and (
                    last_failure_time is None or cb_metrics.last_failure_time > last_failure_time
                ):
                    last_failure_time = cb_metrics.last_failure_time

            # Request coalescer metrics (if available on this client type)
            if (coalescer := getattr(client, "request_coalescer", None)) is not None:
                coal_metrics = coalescer.metrics
                coalesced_requests += coal_metrics.coalesced_requests
                executed_requests += coal_metrics.executed_requests
                pending_requests += coalescer.pending_count

            # Latency metrics (if available on this client type)
            if (latency_stats := getattr(client, "latency_tracker", None)) is not None and latency_stats.count > 0:
                total_latency_ms += latency_stats.avg_ms * latency_stats.count
                latency_count += latency_stats.count
                max_latency_ms = max(max_latency_ms, latency_stats.max_ms)

        avg_latency_ms = total_latency_ms / latency_count if latency_count > 0 else 0.0

        return RpcMetrics(
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            rejected_requests=rejected_requests,
            coalesced_requests=coalesced_requests,
            executed_requests=executed_requests,
            pending_requests=pending_requests,
            circuit_breakers_open=circuit_breakers_open,
            circuit_breakers_half_open=circuit_breakers_half_open,
            state_transitions=state_transitions,
            avg_latency_ms=avg_latency_ms,
            max_latency_ms=max_latency_ms,
            last_failure_time=last_failure_time,
        )

    @property
    def services(self) -> ServiceMetrics:
        """Return service call metrics."""
        if not (stats_by_method := get_service_stats(central_name=self._central_name)):
            return ServiceMetrics()

        total_calls = sum(s.call_count for s in stats_by_method.values())
        total_errors = sum(s.error_count for s in stats_by_method.values())
        total_duration = sum(s.total_duration_ms for s in stats_by_method.values())
        max_duration = max((s.max_duration_ms for s in stats_by_method.values()), default=0.0)

        avg_duration = total_duration / total_calls if total_calls > 0 else 0.0

        return ServiceMetrics(
            total_calls=total_calls,
            total_errors=total_errors,
            avg_duration_ms=avg_duration,
            max_duration_ms=max_duration,
            by_method=stats_by_method,
        )

    def snapshot(self) -> MetricsSnapshot:
        """Return point-in-time snapshot of all metrics."""
        return MetricsSnapshot(
            timestamp=datetime.now(),
            rpc=self.rpc,
            events=self.events,
            cache=self.cache,
            health=self.health,
            recovery=self.recovery,
            model=self.model,
            services=self.services,
        )


# =============================================================================
# Internal Protocols for Loose Coupling
# =============================================================================

from typing import Protocol, runtime_checkable  # noqa: E402


@runtime_checkable
class _ClientProviderForMetrics(Protocol):
    """Internal protocol for client access."""

    @property
    def clients(self) -> tuple[ClientProtocol, ...]: ...


@runtime_checkable
class _DeviceProviderForMetrics(Protocol):
    """Internal protocol for device access."""

    @property
    def devices(self) -> tuple[DeviceProtocol, ...]: ...


@runtime_checkable
class _HubDataPointManagerForMetrics(Protocol):
    """Internal protocol for hub data point access."""

    @property
    def program_data_points(self) -> tuple[Any, ...]: ...

    @property
    def sysvar_data_points(self) -> tuple[Any, ...]: ...
