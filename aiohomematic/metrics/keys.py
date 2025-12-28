# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Type-safe metric keys for the metrics system.

This module provides a type-safe way to define and use metric keys throughout
the codebase. Using MetricKey and MetricKeys ensures consistent naming and
enables IDE autocompletion.

Public API
----------
- MetricKey: Frozen dataclass representing a metric key
- MetricKeys: Factory class with static methods for all known metric keys

Usage
-----
    from aiohomematic.metrics import MetricKeys, emit_latency

    # Emit with type-safe key
    emit_latency(
        event_bus=event_bus,
        key=MetricKeys.ping_pong_rtt(interface_id="hmip_rf"),
        duration_ms=42.5,
    )

    # Query with type-safe key
    tracker = observer.get_latency(MetricKeys.ping_pong_rtt(interface_id="hmip_rf"))
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MetricKey:
    """
    Type-safe metric key with component, metric, and optional identifier.

    The string representation follows the pattern: {component}.{metric}.{identifier}
    or {component}.{metric} if no identifier is provided.

    Attributes:
        component: The component emitting the metric (e.g., "ping_pong", "cache").
        metric: The specific metric being tracked (e.g., "rtt", "hit").
        identifier: Optional identifier for the metric instance (e.g., interface_id).

    """

    component: str
    metric: str
    identifier: str = ""

    def __str__(self) -> str:
        """Return the full metric key string."""
        if self.identifier:
            return f"{self.component}.{self.metric}.{self.identifier}"
        return f"{self.component}.{self.metric}"

    def matches_prefix(self, *, prefix: str) -> bool:
        """Check if this key starts with the given prefix."""
        return str(self).startswith(prefix)


class MetricKeys:
    """
    Factory for well-known metric keys.

    Provides type-safe, documented access to all metric keys used in the system.
    Each method returns a MetricKey instance with proper typing.

    Categories:
        - Ping/Pong: Connection health monitoring
        - Cache: Cache performance metrics
        - Handler: EventBus handler execution
        - Service: Service method (@inspector) metrics
        - Circuit: Circuit breaker state and counters
        - Client: Client health status

    """

    # -------------------------------------------------------------------------
    # Ping/Pong Metrics
    # -------------------------------------------------------------------------

    @staticmethod
    def cache_eviction(*, cache_name: str = "data") -> MetricKey:
        """
        Cache eviction counter.

        Incremented when an entry is evicted from the cache.
        """
        return MetricKey("cache", cache_name, "eviction")

    @staticmethod
    def cache_hit(*, cache_name: str = "data") -> MetricKey:
        """
        Cache hit counter.

        Incremented when a cache lookup succeeds.
        """
        return MetricKey("cache", cache_name, "hit")

    @staticmethod
    def cache_miss(*, cache_name: str = "data") -> MetricKey:
        """
        Cache miss counter.

        Incremented when a cache lookup fails.
        """
        return MetricKey("cache", cache_name, "miss")

    @staticmethod
    def cache_size(*, cache_name: str = "data") -> MetricKey:
        """
        Cache size gauge.

        Current number of entries in the cache.
        """
        return MetricKey("cache", cache_name, "size")

    @staticmethod
    def circuit_failure(*, interface_id: str) -> MetricKey:
        """
        Circuit breaker failure counter.

        Incremented when a request fails and is recorded by the circuit breaker.
        """
        return MetricKey("circuit", "failure", interface_id)

    @staticmethod
    def circuit_rejection(*, interface_id: str) -> MetricKey:
        """
        Circuit breaker rejection counter.

        Incremented when a request is rejected because the circuit is open.
        """
        return MetricKey("circuit", "rejection", interface_id)

    @staticmethod
    def circuit_state(*, interface_id: str) -> MetricKey:
        """
        Circuit breaker state gauge.

        Current state: 0=closed, 1=open, 2=half-open.
        """
        return MetricKey("circuit", "state", interface_id)

    @staticmethod
    def circuit_success(*, interface_id: str) -> MetricKey:
        """
        Circuit breaker success counter.

        Incremented when a request succeeds.
        """
        return MetricKey("circuit", "success", interface_id)

    @staticmethod
    def client_health(*, interface_id: str) -> MetricKey:
        """
        Client health status.

        Indicates whether the client connection is healthy.
        """
        return MetricKey("client", "health", interface_id)

    @staticmethod
    def handler_error(*, event_type: str) -> MetricKey:
        """
        Return metric key for handler error counter.

        Incremented when an event handler raises an exception.
        """
        return MetricKey("handler", "error", event_type)

    @staticmethod
    def handler_execution(*, event_type: str) -> MetricKey:
        """
        Return metric key for handler execution latency.

        Tracks how long event handlers take to execute.
        """
        return MetricKey("handler", "execution", event_type)

    @staticmethod
    def ping_pong_rtt(*, interface_id: str) -> MetricKey:
        """
        RTT latency for ping/pong health checks.

        Tracks the round-trip time for ping/pong messages per interface.
        """
        return MetricKey("ping_pong", "rtt", interface_id)

    @staticmethod
    def service_call(*, method: str) -> MetricKey:
        """
        Service method call latency.

        Tracks execution time of methods decorated with @inspector.
        """
        return MetricKey("service", "call", method)

    @staticmethod
    def service_error(*, method: str) -> MetricKey:
        """
        Service method error counter.

        Incremented when a service method raises an exception.
        """
        return MetricKey("service", "error", method)
