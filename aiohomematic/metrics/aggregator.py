# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
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
    CacheProviderForMetricsProtocol,
    ClientProviderForMetricsProtocol,
    DeviceProviderForMetricsProtocol,
    HubDataPointManagerForMetricsProtocol,
    RecoveryProviderForMetricsProtocol,
)
from aiohomematic.metrics.dataclasses import (
    CacheMetrics,
    EventMetrics,
    HealthMetrics,
    MetricsSnapshot,
    ModelMetrics,
    RecoveryMetrics,
    RpcMetrics,
    RpcServerMetrics,
    ServiceMetrics,
)
from aiohomematic.metrics.stats import CacheStats, ServiceStats

if TYPE_CHECKING:
    from aiohomematic.central.events import EventBus
    from aiohomematic.central.health import HealthTracker
    from aiohomematic.metrics.observer import MetricsObserver
    from aiohomematic.store.dynamic import CentralDataCache


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
        "_cache_provider",
        "_central_name",
        "_client_provider",
        "_data_cache",
        "_device_provider",
        "_event_bus",
        "_health_tracker",
        "_hub_data_point_manager",
        "_observer",
        "_recovery_provider",
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
        cache_provider: CacheProviderForMetricsProtocol | None = None,
        recovery_provider: RecoveryProviderForMetricsProtocol | None = None,
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
            cache_provider: Optional cache provider for cache statistics
            recovery_provider: Optional recovery provider for recovery statistics

        """
        self._central_name: Final = central_name
        self._client_provider: Final = client_provider
        self._device_provider: Final = device_provider
        self._event_bus: Final = event_bus
        self._health_tracker: Final = health_tracker
        self._observer: Final = observer
        self._data_cache: Final = data_cache
        self._hub_data_point_manager: Final = hub_data_point_manager
        self._cache_provider: Final = cache_provider
        self._recovery_provider: Final = recovery_provider

    @property
    def cache(self) -> CacheMetrics:
        """Return cache statistics."""
        # Get hit/miss counts from MetricsObserver (event-driven)
        data_hits = 0
        data_misses = 0
        if self._observer is not None:
            data_hits = self._observer.get_counter(key="cache.data.hit")
            data_misses = self._observer.get_counter(key="cache.data.miss")

        # Get data cache size (always available)
        data_cache_size = self._data_cache.size

        # Get cache sizes from provider if available
        visibility_cache_size = 0
        device_descriptions_size = 0
        paramset_descriptions_size = 0
        if self._cache_provider is not None:
            visibility_cache_size = self._cache_provider.visibility_cache_size
            device_descriptions_size = self._cache_provider.device_descriptions_size
            paramset_descriptions_size = self._cache_provider.paramset_descriptions_size

        # Get visibility cache hit/miss from observer (event-driven)
        visibility_hits = 0
        visibility_misses = 0
        if self._observer is not None:
            visibility_hits = self._observer.get_counter(key="cache.visibility.hit")
            visibility_misses = self._observer.get_counter(key="cache.visibility.miss")

        # Aggregate command cache and ping_pong cache from all clients
        command_cache_size = 0
        ping_pong_cache_size = 0
        for client in self._client_provider.clients:
            if (cmd_cache := getattr(client, "last_value_send_cache", None)) is not None:
                command_cache_size += cmd_cache.size
            if (pp_cache := getattr(client, "ping_pong_cache", None)) is not None:
                ping_pong_cache_size += pp_cache.size

        # Get command cache evictions from observer (event-driven)
        command_cache_evictions = 0
        data_cache_evictions = 0
        if self._observer is not None:
            command_cache_evictions = self._observer.get_counter(key="cache.command.eviction")
            data_cache_evictions = self._observer.get_counter(key="cache.data.eviction")

        return CacheMetrics(
            device_descriptions=CacheStats(
                size=device_descriptions_size,
            ),
            paramset_descriptions=CacheStats(
                size=paramset_descriptions_size,
            ),
            data_cache=CacheStats(
                size=data_cache_size,
                hits=data_hits,
                misses=data_misses,
                evictions=data_cache_evictions,
            ),
            command_cache=CacheStats(
                size=command_cache_size,
                evictions=command_cache_evictions,
            ),
            ping_pong_cache=CacheStats(
                size=ping_pong_cache_size,
            ),
            visibility_cache=CacheStats(
                size=visibility_cache_size,
                hits=visibility_hits,
                misses=visibility_misses,
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
        health_records = event_stats.get("HealthRecordedEvent", 0)

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

        # Aggregate metrics across all clients
        last_event_time = INIT_DATETIME
        reconnect_attempts = 0
        for client_health in health.client_health.values():
            if client_health.last_event_received is not None and client_health.last_event_received > last_event_time:
                last_event_time = client_health.last_event_received
            reconnect_attempts += client_health.reconnect_attempts

        return HealthMetrics(
            overall_score=health.overall_health_score,
            clients_total=clients_healthy + clients_degraded + clients_failed,
            clients_healthy=clients_healthy,
            clients_degraded=clients_degraded,
            clients_failed=clients_failed,
            reconnect_attempts=reconnect_attempts,
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
        by_category: dict[str, int] = {}

        for device in devices:
            for channel in device.channels.values():
                for dp in channel.generic_data_points:
                    generic_count += 1
                    cat_name = dp.category.name
                    by_category[cat_name] = by_category.get(cat_name, 0) + 1

                for dp in channel.calculated_data_points:
                    calculated_count += 1
                    cat_name = dp.category.name
                    by_category[cat_name] = by_category.get(cat_name, 0) + 1

                if (custom_dp := channel.custom_data_point) is not None:
                    custom_count += 1
                    cat_name = custom_dp.category.name
                    by_category[cat_name] = by_category.get(cat_name, 0) + 1

        # Subscription counting available via EventBus.get_total_subscription_count()
        subscribed_count = self._event_bus.get_total_subscription_count()

        programs_total = 0
        sysvars_total = 0
        if self._hub_data_point_manager is not None:
            for dp in self._hub_data_point_manager.program_data_points:
                programs_total += 1
                cat_name = dp.category.name
                by_category[cat_name] = by_category.get(cat_name, 0) + 1

            for dp in self._hub_data_point_manager.sysvar_data_points:
                sysvars_total += 1
                cat_name = dp.category.name
                by_category[cat_name] = by_category.get(cat_name, 0) + 1

        return ModelMetrics(
            devices_total=len(devices),
            devices_available=devices_available,
            channels_total=channels_total,
            data_points_generic=generic_count,
            data_points_custom=custom_count,
            data_points_calculated=calculated_count,
            data_points_subscribed=subscribed_count,
            data_points_by_category=dict(sorted(by_category.items())),
            programs_total=programs_total,
            sysvars_total=sysvars_total,
        )

    @property
    def recovery(self) -> RecoveryMetrics:
        """Return recovery metrics."""
        if self._recovery_provider is None:
            return RecoveryMetrics()

        if not (recovery_states := self._recovery_provider.recovery_states):
            return RecoveryMetrics(
                in_progress=self._recovery_provider.in_recovery,
            )

        # Aggregate metrics across all interface recovery states
        attempts_total = 0
        successes = 0
        failures = 0
        max_retries_reached = 0
        last_recovery_time: datetime | None = None

        for state in recovery_states.values():
            attempts_total += state.attempt_count
            failures += state.consecutive_failures
            # Count successes as attempts minus current consecutive failures
            if state.attempt_count > state.consecutive_failures:
                successes += state.attempt_count - state.consecutive_failures
            # Check if max retries reached (can_retry is False when at limit)
            if not state.can_retry:
                max_retries_reached += 1
            # Track most recent recovery attempt
            if state.last_attempt is not None and (
                last_recovery_time is None or state.last_attempt > last_recovery_time
            ):
                last_recovery_time = state.last_attempt

        return RecoveryMetrics(
            attempts_total=attempts_total,
            successes=successes,
            failures=failures,
            max_retries_reached=max_retries_reached,
            in_progress=self._recovery_provider.in_recovery,
            last_recovery_time=last_recovery_time,
        )

    @property
    def rpc(self) -> RpcMetrics:
        """Return aggregated RPC metrics from all clients."""
        # Get counters from observer (event-driven)
        successful_requests = 0
        failed_requests = 0
        rejected_requests = 0
        coalesced_requests = 0
        executed_requests = 0
        state_transitions = 0
        total_latency_ms = 0.0
        max_latency_ms = 0.0
        latency_count = 0

        if self._observer is not None:
            # Circuit breaker metrics from observer
            successful_requests = self._observer.get_aggregated_counter(pattern="circuit.success.")
            failed_requests = self._observer.get_aggregated_counter(pattern="circuit.failure.")
            rejected_requests = self._observer.get_aggregated_counter(pattern="circuit.rejection.")
            state_transitions = self._observer.get_aggregated_counter(pattern="circuit.state_transition.")

            # Coalescer metrics from observer
            coalesced_requests = self._observer.get_aggregated_counter(pattern="coalescer.coalesced.")
            executed_requests = self._observer.get_aggregated_counter(pattern="coalescer.execute.")

            # Latency metrics from observer
            latency_tracker = self._observer.get_aggregated_latency(pattern="ping_pong.rtt")
            if latency_tracker.count > 0:
                total_latency_ms = latency_tracker.total_ms
                latency_count = latency_tracker.count
                max_latency_ms = latency_tracker.max_ms

        # Calculate total requests (success + failure + rejection)
        total_requests = successful_requests + failed_requests + rejected_requests

        # These require direct access (current state, not counters)
        pending_requests = 0
        circuit_breakers_open = 0
        circuit_breakers_half_open = 0
        last_failure_time: datetime | None = None

        for client in self._client_provider.clients:
            # Circuit breaker state (current, not counter)
            if (cb := getattr(client, "circuit_breaker", None)) is not None:
                if cb.state == CircuitState.OPEN:
                    circuit_breakers_open += 1
                elif cb.state == CircuitState.HALF_OPEN:
                    circuit_breakers_half_open += 1

                # last_failure_time from circuit breaker metrics
                if cb.last_failure_time is not None and (
                    last_failure_time is None or cb.last_failure_time > last_failure_time
                ):
                    last_failure_time = cb.last_failure_time

            # Pending count from coalescer (current gauge, not counter)
            if (coalescer := getattr(client, "request_coalescer", None)) is not None:
                pending_requests += coalescer.pending_count

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
    def rpc_server(self) -> RpcServerMetrics:
        """Return RPC server metrics (incoming requests from CCU)."""
        if self._observer is None:
            return RpcServerMetrics()

        total_requests = self._observer.get_counter(key="rpc_server.request")
        total_errors = self._observer.get_counter(key="rpc_server.error")
        active_tasks = int(self._observer.get_gauge(key="rpc_server.active_tasks"))

        # Get latency metrics
        latency = self._observer.get_latency(key="rpc_server.latency")
        avg_latency_ms = 0.0
        max_latency_ms = 0.0
        if latency is not None and latency.count > 0:
            avg_latency_ms = latency.total_ms / latency.count
            max_latency_ms = latency.max_ms

        return RpcServerMetrics(
            total_requests=total_requests,
            total_errors=total_errors,
            active_tasks=active_tasks,
            avg_latency_ms=avg_latency_ms,
            max_latency_ms=max_latency_ms,
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
            rpc_server=self.rpc_server,
            events=self.events,
            cache=self.cache,
            health=self.health,
            recovery=self.recovery,
            model=self.model,
            services=self.services,
        )
