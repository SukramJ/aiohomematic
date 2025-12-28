# Metrics Responsibility Concept

## Problem Statement

Currently, there is duplicated/inconsistent responsibility for metrics tracking:

1. **Components** (e.g., PingPongCache, CentralDataCache) maintain their own `*Stats` instances
2. **MetricsObserver** aggregates data via EventBus events
3. **EventBus** maintains its own `HandlerStats` directly
4. **Service Registry** (`metrics/service.py`) maintains `ServiceStats` in a global registry

This violates the Single Responsibility Principle and creates multiple sources of truth.

### Current State Analysis

| Component          | Stats Type        | Current Approach      | Problem            |
| ------------------ | ----------------- | --------------------- | ------------------ |
| `PingPongCache`    | `LatencyStats`    | Direct + emit_latency | Duplicate tracking |
| `CentralDataCache` | `CacheStats`      | Direct only           | No event emission  |
| `EventBus`         | `HandlerStats`    | Direct only           | No event emission  |
| `@inspector`       | `ServiceStats`    | Global registry       | No event emission  |
| `CircuitBreaker`   | Internal counters | Direct only           | No event emission  |

## Proposed Architecture

### Clear Separation of Concerns

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Components (Producers)                       │
│  PingPongCache, CentralDataCache, EventBus, @inspector, etc.        │
│                                                                      │
│  Responsibility: Emit metric events ONLY                            │
│  - emit_latency(event_bus, key, duration_ms, labels)                │
│  - emit_counter(event_bus, key, delta, labels)                      │
│  - emit_gauge(event_bus, key, value, labels)                        │
│  - emit_health(event_bus, key, healthy, labels)                     │
│                                                                      │
│  NO direct Stats maintenance!                                        │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 │ Events via EventBus
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      MetricsObserver (Consumer)                      │
│                                                                      │
│  Responsibility: Subscribe to events and maintain ALL Stats         │
│  - Subscribes to LatencyMetricEvent, CounterMetricEvent, etc.       │
│  - Maintains LatencyTracker instances per metric key                │
│  - Maintains counter/gauge/health state                             │
│  - Provides query API: get_latency(), get_counter(), snapshot()     │
│                                                                      │
│  SINGLE SOURCE OF TRUTH for all metrics!                            │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 │ Query API
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      MetricsAggregator                               │
│                                                                      │
│  Responsibility: Create snapshots from MetricsObserver              │
│  - Queries MetricsObserver for all metric categories                │
│  - Returns MetricsSnapshot with RpcMetrics, EventMetrics, etc.      │
│                                                                      │
│  NO direct component access!                                         │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Naming Convention

Pattern: `{component}.{metric}.{identifier}`

Examples:

- `ping_pong.rtt.hmip_rf` - RTT latency for HmIP-RF interface
- `cache.data.hit` - Data cache hit counter
- `cache.data.miss` - Data cache miss counter
- `handler.execution.DataPointUpdatedEvent` - Handler execution latency
- `service.call.turn_on` - Service method call latency
- `service.error.turn_on` - Service method error counter

### Type-Safe Metric Keys

Keys are type-safe using `MetricKey` dataclass and `MetricKeys` factory:

```python
# In aiohomematic/metrics/keys.py

@dataclass(frozen=True, slots=True)
class MetricKey:
    """
    Type-safe metric key with component, metric, and optional identifier.

    The string representation follows the pattern: {component}.{metric}.{identifier}
    """

    component: str
    metric: str
    identifier: str = ""

    def __str__(self) -> str:
        """Return the full metric key string."""
        if self.identifier:
            return f"{self.component}.{self.metric}.{self.identifier}"
        return f"{self.component}.{self.metric}"

    def matches_prefix(self, prefix: str) -> bool:
        """Check if this key starts with the given prefix."""
        return str(self).startswith(prefix)


class MetricKeys:
    """
    Factory for well-known metric keys.

    Provides type-safe, documented access to all metric keys used in the system.
    Each method returns a MetricKey instance with proper typing.
    """

    # -------------------------------------------------------------------------
    # Ping/Pong Metrics
    # -------------------------------------------------------------------------

    @staticmethod
    def ping_pong_rtt(*, interface_id: str) -> MetricKey:
        """RTT latency for ping/pong health checks."""
        return MetricKey("ping_pong", "rtt", interface_id)

    # -------------------------------------------------------------------------
    # Cache Metrics
    # -------------------------------------------------------------------------

    @staticmethod
    def cache_hit(*, cache_name: str = "data") -> MetricKey:
        """Cache hit counter."""
        return MetricKey("cache", cache_name, "hit")

    @staticmethod
    def cache_miss(*, cache_name: str = "data") -> MetricKey:
        """Cache miss counter."""
        return MetricKey("cache", cache_name, "miss")

    @staticmethod
    def cache_eviction(*, cache_name: str = "data") -> MetricKey:
        """Cache eviction counter."""
        return MetricKey("cache", cache_name, "eviction")

    @staticmethod
    def cache_size(*, cache_name: str = "data") -> MetricKey:
        """Cache size gauge."""
        return MetricKey("cache", cache_name, "size")

    # -------------------------------------------------------------------------
    # Handler Metrics (EventBus)
    # -------------------------------------------------------------------------

    @staticmethod
    def handler_execution(*, event_type: str) -> MetricKey:
        """Handler execution latency for an event type."""
        return MetricKey("handler", "execution", event_type)

    @staticmethod
    def handler_error(*, event_type: str) -> MetricKey:
        """Handler error counter for an event type."""
        return MetricKey("handler", "error", event_type)

    # -------------------------------------------------------------------------
    # Service Metrics (@inspector decorator)
    # -------------------------------------------------------------------------

    @staticmethod
    def service_call(*, method: str) -> MetricKey:
        """Service method call latency."""
        return MetricKey("service", "call", method)

    @staticmethod
    def service_error(*, method: str) -> MetricKey:
        """Service method error counter."""
        return MetricKey("service", "error", method)

    # -------------------------------------------------------------------------
    # Circuit Breaker Metrics
    # -------------------------------------------------------------------------

    @staticmethod
    def circuit_failure(*, interface_id: str) -> MetricKey:
        """Circuit breaker failure counter."""
        return MetricKey("circuit", "failure", interface_id)

    @staticmethod
    def circuit_success(*, interface_id: str) -> MetricKey:
        """Circuit breaker success counter."""
        return MetricKey("circuit", "success", interface_id)

    @staticmethod
    def circuit_rejection(*, interface_id: str) -> MetricKey:
        """Circuit breaker rejection counter (requests rejected while open)."""
        return MetricKey("circuit", "rejection", interface_id)

    @staticmethod
    def circuit_state(*, interface_id: str) -> MetricKey:
        """Circuit breaker state gauge (0=closed, 1=open, 2=half-open)."""
        return MetricKey("circuit", "state", interface_id)

    # -------------------------------------------------------------------------
    # Health Metrics
    # -------------------------------------------------------------------------

    @staticmethod
    def client_health(*, interface_id: str) -> MetricKey:
        """Client health status."""
        return MetricKey("client", "health", interface_id)
```

**Usage in emit functions:**

```python
# Type-safe emission
emit_latency(
    event_bus=self._event_bus,
    key=MetricKeys.ping_pong_rtt(interface_id=self._interface_id),
    duration_ms=rtt_ms,
)

emit_counter(
    event_bus=self._event_bus,
    key=MetricKeys.cache_hit(),
    delta=1,
)

emit_latency(
    event_bus=self._event_bus,
    key=MetricKeys.handler_execution(event_type=type(event).__name__),
    duration_ms=duration,
)
```

**Usage in MetricsObserver queries:**

```python
# Query by exact key
tracker = observer.get_latency(MetricKeys.ping_pong_rtt(interface_id="hmip_rf"))

# Query by prefix pattern
handler_keys = observer.get_keys_by_prefix("handler.execution.")
```

## Affected Components - Detailed Migration

### 1. PingPongCache

**Current:**

```python
class PingPongCache:
    _latency_stats: LatencyStats

    def handle_pong(self, pong_ts: float) -> None:
        rtt_ms = (pong_ts - ping_ts) * 1000
        self._latency_stats.record(duration_ms=rtt_ms)  # Direct
        emit_latency(...)  # Also event
```

**Target:**

```python
class PingPongCache:
    # NO _latency_stats!

    def handle_pong(self, pong_ts: float) -> None:
        rtt_ms = (pong_ts - ping_ts) * 1000
        emit_latency(
            event_bus=self._event_bus,
            key=MetricKeys.ping_pong_rtt(interface_id=self._interface_id),
            duration_ms=rtt_ms,
        )
```

### 2. CentralDataCache

**Current:**

```python
class CentralDataCache:
    _stats: CacheStats

    def get(self, key: str) -> Any:
        if key in self._cache:
            self._stats.record_hit()  # Direct only
            return self._cache[key]
        self._stats.record_miss()  # Direct only
        return None
```

**Target:**

```python
class CentralDataCache:
    # NO _stats!

    def get(self, key: str) -> Any:
        if key in self._cache:
            emit_counter(self._event_bus, key=MetricKeys.cache_hit(), delta=1)
            return self._cache[key]
        emit_counter(self._event_bus, key=MetricKeys.cache_miss(), delta=1)
        return None
```

### 3. EventBus (HandlerStats)

**Current:**

```python
class EventBus:
    _handler_stats: HandlerStats

    async def _dispatch(self, event: Event) -> None:
        start = monotonic()
        await handler(event)
        duration = (monotonic() - start) * 1000
        self._handler_stats.record(duration_ms=duration)  # Direct only
```

**Target:**

```python
class EventBus:
    # NO _handler_stats!

    async def _dispatch(self, event: Event) -> None:
        event_type_name = type(event).__name__
        start = monotonic()
        try:
            await handler(event)
            had_error = False
        except Exception:
            had_error = True
            raise
        finally:
            duration = (monotonic() - start) * 1000
            emit_latency(
                event_bus=self,
                key=MetricKeys.handler_execution(event_type=event_type_name),
                duration_ms=duration,
            )
            if had_error:
                emit_counter(
                    event_bus=self,
                    key=MetricKeys.handler_error(event_type=event_type_name),
                    delta=1,
                )
```

### 4. @inspector Decorator (ServiceStats)

**Current:**

```python
# In decorators.py
def inspector(...):
    async def wrapper(*args, **kwargs):
        start = monotonic()
        try:
            return await func(*args, **kwargs)
        finally:
            duration = (monotonic() - start) * 1000
            record_service_call(  # Global registry
                central_name=...,
                method_name=func.__name__,
                duration_ms=duration,
                had_error=had_error,
            )
```

**Target:**

```python
def inspector(...):
    async def wrapper(*args, **kwargs):
        method_name = func.__name__
        start = monotonic()
        try:
            return await func(*args, **kwargs)
        finally:
            duration = (monotonic() - start) * 1000
            if event_bus := _get_event_bus(context_obj):
                emit_latency(
                    event_bus=event_bus,
                    key=MetricKeys.service_call(method=method_name),
                    duration_ms=duration,
                )
                if had_error:
                    emit_counter(
                        event_bus=event_bus,
                        key=MetricKeys.service_error(method=method_name),
                        delta=1,
                    )
```

### 5. CircuitBreaker

**Current:** Maintains internal counters for failures, successes, rejections.

**Target:** Emit events for state changes and request outcomes:

```python
# On failure
emit_counter(
    event_bus=event_bus,
    key=MetricKeys.circuit_failure(interface_id=self._interface_id),
    delta=1,
)

# On success
emit_counter(
    event_bus=event_bus,
    key=MetricKeys.circuit_success(interface_id=self._interface_id),
    delta=1,
)

# On state change
emit_gauge(
    event_bus=event_bus,
    key=MetricKeys.circuit_state(interface_id=self._interface_id),
    value=new_state.value,
)
```

## MetricsObserver Extensions

The MetricsObserver needs additional query methods:

```python
class MetricsObserver:
    # Existing
    def get_latency(self, key: str) -> LatencyTracker | None: ...
    def get_counter(self, key: str) -> int: ...
    def get_gauge(self, key: str) -> float | None: ...
    def get_health(self, key: str) -> HealthState | None: ...

    # New aggregation methods
    def get_cache_metrics(self) -> CacheMetrics:
        """Aggregate cache.*.hit and cache.*.miss counters."""
        hits = sum(self.get_counter(k) for k in self._counters if ".hit" in k)
        misses = sum(self.get_counter(k) for k in self._counters if ".miss" in k)
        return CacheMetrics(hits=hits, misses=misses, ...)

    def get_handler_metrics(self) -> dict[str, LatencyStats]:
        """Get all handler.execution.* latency stats."""
        return {
            k.replace("handler.execution.", ""): tracker.to_stats()
            for k, tracker in self._latency_trackers.items()
            if k.startswith("handler.execution.")
        }

    def get_service_metrics(self, central_name: str) -> ServiceMetrics:
        """Aggregate service.call.* and service.error.* for a central."""
        ...
```

## Files to Delete After Migration

Once migration is complete, these become obsolete:

- `aiohomematic/metrics/service.py` - Global registry replaced by MetricsObserver
- `HandlerStats` class in `event_bus.py` - Replaced by LatencyTracker in MetricsObserver

## Migration Plan

### Phase 1: Foundation

1. **Create `metrics/keys.py`** with `MetricKey` and `MetricKeys`
2. **Update emit functions** to accept `MetricKey | str` for key parameter
3. **Extend MetricsObserver** query API:
   - `get_latency(key: MetricKey | str) -> LatencyTracker | None`
   - `get_counter(key: MetricKey | str) -> int`
   - `get_keys_by_prefix(prefix: str) -> list[str]`
   - `to_stats()` method on LatencyTracker

### Phase 2: Migrate Components

Order by dependency (least dependent first):

1. **PingPongCache** - Remove `_latency_stats`, use `MetricKeys.ping_pong_rtt()`
2. **CentralDataCache** - Remove `_stats`, use `MetricKeys.cache_hit/miss()`
3. **CircuitBreaker** - Add event emission with `MetricKeys.circuit_*()`
4. **EventBus** - Remove `HandlerStats`, use `MetricKeys.handler_*()`
5. **@inspector** - Remove `record_service_call`, use `MetricKeys.service_*()`

### Phase 3: Update MetricsAggregator

1. Remove direct component queries
2. Query MetricsObserver exclusively using `MetricKeys`
3. Delete `metrics/service.py`

### Phase 4: Cleanup

1. Remove `HandlerStats` from `event_bus.py`
2. Review Stats classes - keep only those used by MetricsObserver
3. Update all tests
4. Update documentation

## Benefits

1. **Single Source of Truth**: All metrics live in MetricsObserver
2. **Decoupling**: Components only emit, don't aggregate
3. **Consistency**: Same pattern for all metric types
4. **Testability**: Easy to test emission without aggregation logic
5. **Flexibility**: Easy to add new observers (Prometheus, logging, etc.)
6. **Simplicity**: No global registries, no component-level stats

## New Files

| File              | Purpose                                        |
| ----------------- | ---------------------------------------------- |
| `metrics/keys.py` | `MetricKey` dataclass and `MetricKeys` factory |

## Decisions

1. **MetricsAggregator queries MetricsObserver only** - No direct component access
2. **Key naming**: `{component}.{metric}.{identifier}`
3. **Type-safe keys**: `MetricKey` dataclass with `MetricKeys` factory
4. **No backward compatibility** - Clean migration, no legacy shims
5. **Stats classes remain** in `metrics/stats.py` - Used internally by MetricsObserver
