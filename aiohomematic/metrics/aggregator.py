# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Metrics aggregation from system components.

This module provides MetricsAggregator which collects metrics from
various system components and presents them through a unified interface.

Public API
----------
- MetricsAggregator: Main class for aggregating metrics

Usage
-----
    from aiohomematic.metrics import MetricsAggregator

    aggregator = MetricsAggregator(
        central_name="my-central",
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
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Final

from aiohomematic.client.circuit_breaker import CircuitState
from aiohomematic.const import INIT_DATETIME
from aiohomematic.metrics._protocols import (
    ClientProviderForMetricsProtocol,
    DeviceProviderForMetricsProtocol,
    HubDataPointManagerForMetricsProtocol,
)
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
from aiohomematic.metrics.stats import CacheStats, ServiceStats

if TYPE_CHECKING:
    from aiohomematic.central.event_bus import EventBus
    from aiohomematic.central.health import HealthTracker
    from aiohomematic.central.recovery import RecoveryCoordinator
    from aiohomematic.metrics.observer import MetricsObserver
    from aiohomematic.store.dynamic.data import CentralDataCache


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
        central_name="my-central",
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
        "_observer",
        "_recovery_coordinator",
    )

    def __init__(
        self,
        *,
        central_name: str,
        client_provider: ClientProviderForMetricsProtocol,
        device_provider: DeviceProviderForMetricsProtocol,
        event_bus: EventBus,
        health_tracker: HealthTracker,
        data_cache: CentralDataCache,
        observer: MetricsObserver | None = None,
        hub_data_point_manager: HubDataPointManagerForMetricsProtocol | None = None,
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
            observer: Optional MetricsObserver for event-driven metrics
            hub_data_point_manager: Optional hub data point manager
            recovery_coordinator: Optional recovery coordinator

        """
        self._central_name: Final = central_name
        self._client_provider: Final = client_provider
        self._device_provider: Final = device_provider
        self._event_bus: Final = event_bus
        self._health_tracker: Final = health_tracker
        self._observer: Final = observer
        self._data_cache: Final = data_cache
        self._hub_data_point_manager: Final = hub_data_point_manager
        self._recovery_coordinator: Final = recovery_coordinator

    @property
    def cache(self) -> CacheMetrics:
        """Return cache statistics."""
        # Get hit/miss counts from MetricsObserver (event-driven)
        hits = 0
        misses = 0
        if self._observer is not None:
            hits = self._observer.get_counter(key="cache.data.hit")
            misses = self._observer.get_counter(key="cache.data.miss")

        return CacheMetrics(
            data_cache=CacheStats(
                size=self._data_cache.size,
                hits=hits,
                misses=misses,
            ),
        )

    @property
    def events(self) -> EventMetrics:
        """Return EventBus metrics including operational event counts."""
        event_stats = self._event_bus.get_event_stats()
        handler_stats = self._event_bus.get_handler_stats()

        # Extract operational event counts from event_stats
        circuit_breaker_trips = event_stats.get("CircuitBreakerTrippedEvent", 0)
        client_state_changes = event_stats.get("ClientStateChangedEvent", 0)
        central_state_changes = event_stats.get("CentralStateChangedEvent", 0)
        data_refreshes_triggered = event_stats.get("DataRefreshTriggeredEvent", 0)
        data_refreshes_completed = event_stats.get("DataRefreshCompletedEvent", 0)
        programs_executed = event_stats.get("ProgramExecutedEvent", 0)
        requests_coalesced = event_stats.get("RequestCoalescedEvent", 0)
        health_records = event_stats.get("HealthRecordEvent", 0)

        return EventMetrics(
            total_published=sum(event_stats.values()),
            total_subscriptions=self._event_bus.get_total_subscription_count(),
            handlers_executed=handler_stats.total_executions,
            handler_errors=handler_stats.total_errors,
            avg_handler_duration_ms=handler_stats.avg_duration_ms,
            max_handler_duration_ms=handler_stats.max_duration_ms,
            events_by_type=event_stats,
            circuit_breaker_trips=circuit_breaker_trips,
            state_changes=client_state_changes + central_state_changes,
            data_refreshes_triggered=data_refreshes_triggered,
            data_refreshes_completed=data_refreshes_completed,
            programs_executed=programs_executed,
            requests_coalesced=requests_coalesced,
            health_records=health_records,
        )

    @property
    def health(self) -> HealthMetrics:
        """Return health metrics."""
        health = self._health_tracker.health
        clients_healthy = len(health.healthy_clients)
        clients_degraded = len(health.degraded_clients)
        clients_failed = len(health.failed_clients)

        # Get the most recent event time across all clients
        last_event_time = INIT_DATETIME
        for client_health in health.client_health.values():
            if client_health.last_event_received is not None and client_health.last_event_received > last_event_time:
                last_event_time = client_health.last_event_received

        return HealthMetrics(
            overall_score=health.overall_health_score,
            clients_total=clients_healthy + clients_degraded + clients_failed,
            clients_healthy=clients_healthy,
            clients_degraded=clients_degraded,
            clients_failed=clients_failed,
            last_event_time=last_event_time,
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

        # Latency metrics from MetricsObserver (event-driven)
        if self._observer is not None:
            latency_tracker = self._observer.get_aggregated_latency(pattern="ping_pong.rtt")
            if latency_tracker.count > 0:
                total_latency_ms = latency_tracker.total_ms
                latency_count = latency_tracker.count
                max_latency_ms = latency_tracker.max_ms

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
        """Return service call metrics from MetricsObserver."""
        if self._observer is None:
            return ServiceMetrics()

        # Build stats by method from observer data
        stats_by_method: dict[str, ServiceStats] = {}

        # Get all latency keys for service calls (pattern: service.call.{method})
        for key in self._observer.get_keys_by_prefix(prefix="service.call."):
            # Extract method name from key (service.call.method_name -> method_name)
            parts = key.split(".")
            if len(parts) >= 3:
                method_name = parts[2]
                if (latency := self._observer.get_latency(key=key)) is None:
                    continue
                error_count = self._observer.get_counter(key=f"service.error.{method_name}")

                stats_by_method[method_name] = ServiceStats(
                    call_count=latency.count,
                    error_count=error_count,
                    total_duration_ms=latency.total_ms,
                    max_duration_ms=latency.max_ms,
                )

        if not stats_by_method:
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
