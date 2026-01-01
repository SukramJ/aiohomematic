# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Mutable statistics classes for metrics tracking.

This module provides mutable dataclasses for tracking runtime statistics.
These are used by components to record metrics which are then aggregated.

Public API
----------
- CacheStats: Cache hit/miss/size statistics
- LatencyStats: Request latency statistics (count, min, max, avg)
- ServiceStats: Service method execution statistics (call count, errors, timing)
"""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(slots=True)
class SizeOnlyStats:
    """
    Size-only statistics for registries and trackers.

    Used for components that are not true caches (no hit/miss semantics):
    - DeviceDescriptionRegistry (authoritative store)
    - ParamsetDescriptionRegistry (authoritative store)
    - ParameterVisibilityRegistry (rule engine with memoization)
    - PingPongTracker (connection health tracker)
    """

    size: int = 0
    """Current number of entries."""


@dataclass(slots=True)
class CacheStats:
    """
    Statistics for cache performance monitoring.

    Used for true caches with hit/miss semantics:
    - CentralDataCache
    - CommandCache
    """

    hits: int = 0
    """Number of successful cache lookups."""

    misses: int = 0
    """Number of cache misses."""

    size: int = 0
    """Current number of entries in the cache."""

    evictions: int = 0
    """Number of entries evicted from the cache."""

    @property
    def hit_rate(self) -> float:
        """Return hit rate as percentage."""
        if (total := self.hits + self.misses) == 0:
            return 100.0
        return (self.hits / total) * 100

    def record_hit(self) -> None:
        """Record a cache hit."""
        self.hits += 1

    def record_miss(self) -> None:
        """Record a cache miss."""
        self.misses += 1

    def reset(self) -> None:
        """Reset cache statistics."""
        self.hits = 0
        self.misses = 0
        self.size = 0
        self.evictions = 0


@dataclass(slots=True)
class LatencyStats:
    """Statistics for request latency tracking."""

    count: int = 0
    """Number of latency samples."""

    total_ms: float = 0.0
    """Total latency in milliseconds."""

    min_ms: float = math.inf
    """Minimum latency in milliseconds."""

    max_ms: float = 0.0
    """Maximum latency in milliseconds."""

    @property
    def avg_ms(self) -> float:
        """Return average latency in milliseconds."""
        if self.count == 0:
            return 0.0
        return self.total_ms / self.count

    def record(self, *, duration_ms: float) -> None:
        """Record a latency sample."""
        self.count += 1
        self.total_ms += duration_ms
        self.min_ms = min(self.min_ms, duration_ms)
        self.max_ms = max(self.max_ms, duration_ms)

    def reset(self) -> None:
        """Reset latency statistics."""
        self.count = 0
        self.total_ms = 0.0
        self.min_ms = math.inf
        self.max_ms = 0.0


@dataclass(slots=True)
class ServiceStats:
    """
    Statistics for service method execution tracking.

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
