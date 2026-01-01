# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Metric emission utilities for event-driven metrics.

This module provides utilities for emitting metric events without
coupling productive code to the metrics system.

Public API
----------
- emit_latency: Emit a latency metric event
- emit_counter: Emit a counter metric event
- emit_gauge: Emit a gauge metric event
- emit_health: Emit a health metric event
- LatencyContext: Context manager for automatic latency tracking
- MetricEmitterMixin: Mixin class for components that emit metrics

Usage
-----
    from aiohomematic.metrics import MetricKeys, emit_latency

    # Emit with type-safe key
    emit_latency(
        event_bus=bus,
        key=MetricKeys.ping_pong_rtt(interface_id="hmip_rf"),
        duration_ms=42.5,
    )

    # Emit with string key (for dynamic keys)
    emit_counter(
        event_bus=bus,
        key="custom.metric.key",
        delta=1,
    )
"""

from __future__ import annotations

from datetime import datetime
import time
from typing import TYPE_CHECKING, Protocol, Self, runtime_checkable

from aiohomematic.metrics.events import CounterMetricEvent, GaugeMetricEvent, HealthMetricEvent, LatencyMetricEvent
from aiohomematic.metrics.keys import MetricKey

if TYPE_CHECKING:
    from aiohomematic.central.events import EventBus


@runtime_checkable
class EventBusProviderProtocol(Protocol):
    """Protocol for objects that provide an EventBus."""

    @property
    def event_bus(self) -> EventBus:
        """Return the event bus."""


# =============================================================================
# Standalone Emission Functions
# =============================================================================


def emit_latency(
    *,
    event_bus: EventBus,
    key: MetricKey | str,
    duration_ms: float,
) -> None:
    """
    Emit a latency metric event.

    Args:
        event_bus: EventBus to publish to.
        key: Metric key (MetricKey instance or string).
        duration_ms: Duration in milliseconds.

    """
    event_bus.publish_sync(
        event=LatencyMetricEvent(
            timestamp=datetime.now(),
            metric_key=str(key),
            duration_ms=duration_ms,
        )
    )


def emit_counter(
    *,
    event_bus: EventBus,
    key: MetricKey | str,
    delta: int = 1,
) -> None:
    """
    Emit a counter metric event.

    Args:
        event_bus: EventBus to publish to.
        key: Metric key (MetricKey instance or string).
        delta: Amount to change the counter by (default: 1).

    """
    event_bus.publish_sync(
        event=CounterMetricEvent(
            timestamp=datetime.now(),
            metric_key=str(key),
            delta=delta,
        )
    )


def emit_gauge(
    *,
    event_bus: EventBus,
    key: MetricKey | str,
    value: float,
) -> None:
    """
    Emit a gauge metric event.

    Args:
        event_bus: EventBus to publish to.
        key: Metric key (MetricKey instance or string).
        value: Current gauge value.

    """
    event_bus.publish_sync(
        event=GaugeMetricEvent(
            timestamp=datetime.now(),
            metric_key=str(key),
            value=value,
        )
    )


def emit_health(
    *,
    event_bus: EventBus,
    key: MetricKey | str,
    healthy: bool,
    reason: str | None = None,
) -> None:
    """
    Emit a health metric event.

    Args:
        event_bus: EventBus to publish to.
        key: Metric key (MetricKey instance or string).
        healthy: Whether the component is healthy.
        reason: Optional reason for the state.

    """
    event_bus.publish_sync(
        event=HealthMetricEvent(
            timestamp=datetime.now(),
            metric_key=str(key),
            healthy=healthy,
            reason=reason,
        )
    )


# =============================================================================
# Context Manager for Latency Tracking
# =============================================================================


class LatencyContext:
    """
    Context manager for automatic latency tracking.

    Usage:
        with LatencyContext(
            event_bus=bus,
            key=MetricKeys.handler_execution(event_type="MyEvent"),
        ):
            # ... do work ...
        # Latency event emitted automatically on exit
    """

    __slots__ = ("_event_bus", "_key", "_start_time")

    def __init__(
        self,
        *,
        event_bus: EventBus | None,
        key: MetricKey | str,
    ) -> None:
        """Initialize the context."""
        self._event_bus = event_bus
        self._key = key
        self._start_time: float = 0.0

    def __enter__(self) -> Self:
        """Start timing."""
        self._start_time = time.monotonic()
        return self

    def __exit__(  # kwonly: disable
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: object
    ) -> None:
        """Emit latency event."""
        if self._event_bus is None:
            return
        duration_ms = (time.monotonic() - self._start_time) * 1000
        emit_latency(
            event_bus=self._event_bus,
            key=self._key,
            duration_ms=duration_ms,
        )


# =============================================================================
# Mixin Class
# =============================================================================


class MetricEmitterMixin:
    """
    Mixin class for components that emit metrics.

    Components using this mixin must have:
    - _event_bus_provider: EventBusProviderProtocol (or _event_bus: EventBus)

    The mixin provides protected methods for emitting each metric type.
    These methods are no-ops if no EventBus is available, making metrics
    collection truly optional.
    """

    # This will be provided by the implementing class
    _event_bus_provider: EventBusProviderProtocol | None

    def _emit_counter(self, *, key: MetricKey | str, delta: int = 1) -> None:
        """
        Emit a counter metric event.

        Args:
            key: Metric key (MetricKey instance or string).
            delta: Amount to change the counter by.

        """
        if (bus := self._get_event_bus()) is None:
            return
        emit_counter(event_bus=bus, key=key, delta=delta)

    def _emit_gauge(self, *, key: MetricKey | str, value: float) -> None:
        """
        Emit a gauge metric event.

        Args:
            key: Metric key (MetricKey instance or string).
            value: Current gauge value.

        """
        if (bus := self._get_event_bus()) is None:
            return
        emit_gauge(event_bus=bus, key=key, value=value)

    def _emit_health(self, *, key: MetricKey | str, healthy: bool, reason: str | None = None) -> None:
        """
        Emit a health metric event.

        Args:
            key: Metric key (MetricKey instance or string).
            healthy: Whether the component is healthy.
            reason: Optional reason for the state.

        """
        if (bus := self._get_event_bus()) is None:
            return
        emit_health(event_bus=bus, key=key, healthy=healthy, reason=reason)

    def _emit_latency(self, *, key: MetricKey | str, duration_ms: float) -> None:
        """
        Emit a latency metric event.

        Args:
            key: Metric key (MetricKey instance or string).
            duration_ms: Duration in milliseconds.

        """
        if (bus := self._get_event_bus()) is None:
            return
        emit_latency(event_bus=bus, key=key, duration_ms=duration_ms)

    def _get_event_bus(self) -> EventBus | None:
        """Get the EventBus if available."""
        if hasattr(self, "_event_bus_provider") and self._event_bus_provider is not None:
            return self._event_bus_provider.event_bus
        if hasattr(self, "_event_bus"):
            return getattr(self, "_event_bus", None)
        return None
