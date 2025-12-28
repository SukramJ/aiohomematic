# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Service call metrics tracking (DEPRECATED).

.. deprecated:: 2025.12.53
    This module is deprecated. The @inspector decorator now emits events directly
    to the EventBus. Use MetricsObserver to query service metrics instead.

    For service call latency: observer.get_latency(key="service.call.{method}")
    For service errors: observer.get_counter(key="service.error.{method}")

This module provides a global registry for tracking service method
execution statistics. Previously used by the @inspector decorator.

Public API
----------
- record_service_call: Record a service call for metrics (deprecated)
- get_service_stats: Get service stats for a central (deprecated)
- clear_service_stats: Clear service stats (deprecated)

Usage
-----
    # DEPRECATED - use MetricsObserver instead
    from aiohomematic.metrics import record_service_call, get_service_stats

    # Record a call (typically done by @inspector decorator)
    record_service_call(
        central_name="my-central",
        method_name="get_value",
        duration_ms=42.5,
        had_error=False,
    )

    # Get stats for a central
    stats = get_service_stats(central_name="my-central")
    for method, stat in stats.items():
        print(f"{method}: {stat.call_count} calls, avg {stat.avg_duration_ms:.2f}ms")
"""

from __future__ import annotations

import threading
from typing import Final

from aiohomematic.metrics.stats import ServiceStats

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
