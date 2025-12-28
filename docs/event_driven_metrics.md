# Event-Driven Metrics Architecture

This document describes the event-driven metrics system in aiohomematic, which provides a decoupled, efficient approach to collecting and aggregating runtime metrics.

## Overview

The event-driven metrics architecture replaces polling-based metric collection with an event-based approach. Components emit metric events to the EventBus, and the MetricsObserver aggregates them into queryable statistics.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            EventBus                                     │
│  (Central message broker for all metric events)                         │
└─────────────────────────────────────────────────────────────────────────┘
        ▲                    ▲                    ▲                    │
        │                    │                    │                    │
        │ emit_latency()     │ emit_counter()     │ emit_health()      │
        │                    │                    │                    ▼
┌───────┴───────┐    ┌───────┴───────┐    ┌───────┴───────┐    ┌───────────────┐
│ PingPongCache │    │    Client     │    │ HealthTracker │    │MetricsObserver│
│               │    │               │    │               │    │               │
│ round_trip    │    │ rpc_call      │    │ client_state  │    │ Aggregates:   │
│ latency       │    │ latency       │    │ changes       │    │ - Latency     │
└───────────────┘    └───────────────┘    └───────────────┘    │ - Counters    │
                                                                │ - Gauges      │
                                                                │ - Health      │
                                                                └───────┬───────┘
                                                                        │
                                                                        ▼
                                                                ┌───────────────┐
                                                                │  Hub Sensors  │
                                                                │               │
                                                                │ Expose to HA  │
                                                                └───────────────┘
```

## Module Structure

```
aiohomematic/metrics/
├── __init__.py      # Public API exports
├── events.py        # MetricEvent hierarchy
├── observer.py      # MetricsObserver aggregator
└── emitter.py       # Emission utilities (emit_*, MetricEmitterMixin)
```

## Core Components

### MetricEvent Hierarchy

All metric events inherit from a common `Event` base class and use the EventBus for delivery:

```python
from aiohomematic.metrics import (
    LatencyMetricEvent,
    CounterMetricEvent,
    GaugeMetricEvent,
    HealthMetricEvent,
    MetricType,
)
```

| Event Type           | Purpose                | Key Fields                 |
| -------------------- | ---------------------- | -------------------------- |
| `LatencyMetricEvent` | Timing measurements    | `duration_ms`, `operation` |
| `CounterMetricEvent` | Incrementing counts    | `metric_name`, `increment` |
| `GaugeMetricEvent`   | Point-in-time values   | `metric_name`, `value`     |
| `HealthMetricEvent`  | Component health state | `healthy`, `reason`        |

All events share common fields:

- `timestamp`: When the event occurred
- `source`: Component name (e.g., "ping_pong", "client")
- `source_id`: Optional identifier (e.g., interface_id)
- `full_key`: Computed key combining source, source_id, and operation/metric_name

### MetricsObserver

The `MetricsObserver` subscribes to all metric event types on the EventBus with LOW priority (non-blocking) and maintains aggregated statistics:

```python
from aiohomematic.metrics import MetricsObserver

# Created by CentralUnit
observer = MetricsObserver(event_bus=central.event_bus)

# Get snapshot of all metrics
snapshot = observer.snapshot()

# Query specific metrics
latency = observer.get_aggregated_latency(pattern="ping_pong")
print(f"Avg round-trip: {latency.avg_ms:.2f}ms")

# Get overall health score (0.0 to 1.0)
health_score = observer.get_overall_health_score()
```

Key features:

- **Event-driven**: No polling, metrics arrive via EventBus
- **LOW priority**: Handlers run after productive code completes
- **Bounded growth**: Limits on unique metric keys (MAX_METRIC_KEYS = 10,000)
- **Thread-safe snapshots**: `snapshot()` returns immutable copy

### Emission Utilities

The `emitter` module provides convenient functions for emitting metrics:

```python
from aiohomematic.metrics import emit_latency, emit_counter, emit_gauge, emit_health

# Emit latency metric
emit_latency(
    event_bus=event_bus,
    source="ping_pong",
    source_id=interface_id,
    operation="round_trip",
    duration_ms=42.5,
)

# Emit counter metric
emit_counter(
    event_bus=event_bus,
    source="cache",
    metric_name="hit",
    increment=1,
)

# Emit gauge metric
emit_gauge(
    event_bus=event_bus,
    source="connections",
    metric_name="active",
    value=5.0,
)

# Emit health metric
emit_health(
    event_bus=event_bus,
    source="client",
    source_id=interface_id,
    healthy=True,
    reason=None,
)
```

### LatencyContext

For automatic latency tracking, use the context manager:

```python
from aiohomematic.metrics import LatencyContext

with LatencyContext(
    event_bus=event_bus,
    source="rpc",
    operation="get_value",
    source_id=interface_id,
):
    result = await client.get_value(...)
# Latency event emitted automatically on exit
```

### MetricEmitterMixin

For classes that emit many metrics, use the mixin:

```python
from aiohomematic.metrics import MetricEmitterMixin

class MyComponent(MetricEmitterMixin):
    def __init__(self, event_bus_provider):
        self._event_bus_provider = event_bus_provider
        self._metric_source = "my_component"
        self._metric_source_id = "instance_1"

    def do_work(self):
        start = time.monotonic()
        # ... work ...
        self._emit_latency(
            operation="do_work",
            duration_ms=(time.monotonic() - start) * 1000,
        )
        self._emit_counter(metric_name="operations")
```

## Metric Key Format

Metric keys follow a hierarchical format for easy aggregation:

```
{source}:{source_id}:{operation|metric_name}
```

Examples:

- `ping_pong:HmIP-RF:round_trip` - Latency for HmIP-RF interface
- `client:BidCos-RF:rpc_call` - Latency for BidCos-RF RPC calls
- `cache::hit` - Counter for cache hits (no source_id)

Aggregation by pattern:

```python
# Get all ping_pong latencies across interfaces
latency = observer.get_aggregated_latency(pattern="ping_pong")

# Get all cache counters
total_hits = observer.get_aggregated_counter(pattern="cache")
```

## Data Flow

### Latency Metric Flow (PingPongCache Example)

```
1. PingPongCache.handle_received_pong()
   │
   ├─► Calculates round-trip time
   │
   ├─► emit_latency(event_bus, source="ping_pong", ...)
   │       │
   │       └─► Creates LatencyMetricEvent
   │           │
   │           └─► event_bus.publish_sync(event)
   │
   └─► EventBus delivers to MetricsObserver._handle_latency()
           │
           └─► Updates _latency[full_key].record(duration_ms)
```

### Health Metric Flow (HealthTracker Example)

```
1. HealthTracker.update_health()
   │
   ├─► Detects client state change
   │
   ├─► emit_health(event_bus, source="client", healthy=False, ...)
   │       │
   │       └─► Creates HealthMetricEvent
   │           │
   │           └─► event_bus.publish_sync(event)
   │
   └─► EventBus delivers to MetricsObserver._handle_health()
           │
           └─► Updates _health[full_key].update(healthy, reason)
```

## Integration with Hub Sensors

Hub sensors expose metrics to Home Assistant:

```python
# In Hub.create_metrics_dps()
self._metrics_dps = MetricsDpType(
    system_health=HmSystemHealthSensor(
        metrics_observer=central.metrics,
        ...
    ),
    connection_latency=HmConnectionLatencySensor(
        metrics_observer=central.metrics,
        ...
    ),
    last_event_age=HmLastEventAgeSensor(
        metrics_observer=central.metrics,
        ...
    ),
)
```

Sensor implementations query the observer:

```python
class HmSystemHealthSensor(HmMetricsSensor):
    def _get_current_value(self) -> float:
        return round(self._metrics_observer.get_overall_health_score() * 100, 1)

class HmConnectionLatencySensor(HmMetricsSensor):
    def _get_current_value(self) -> float:
        latency = self._metrics_observer.get_aggregated_latency(pattern="ping_pong")
        return round(latency.avg_ms, 1)

class HmLastEventAgeSensor(HmMetricsSensor):
    def _get_current_value(self) -> float:
        return round(self._metrics_observer.get_last_event_age_seconds(), 1)
```

## CentralUnit Integration

CentralUnit creates and manages the MetricsObserver:

```python
class CentralUnit:
    def __init__(self, ...):
        # Create observer subscribed to EventBus
        self._metrics_observer = MetricsObserver(event_bus=self._event_bus)

        # HealthTracker emits health events
        self._health_tracker = HealthTracker(
            central_name=self._config.name,
            state_machine=self._central_state_machine,
            event_bus=self._event_bus,
        )

    @property
    def metrics(self) -> MetricsObserver:
        """Return the event-driven metrics observer."""
        return self._metrics_observer

    async def stop(self) -> None:
        self._metrics_observer.stop()  # Unsubscribe from events
```

## EventBus Priority

Metric handlers use LOW priority to avoid blocking productive code:

```python
# In MetricsObserver._subscribe_to_events()
unsub = self._event_bus.subscribe(
    event_type=LatencyMetricEvent,
    event_key=None,  # Subscribe to all keys
    handler=self._handle_latency,
    priority=EventPriority.LOW,  # Run after HIGH/NORMAL handlers
)
```

Priority order: CRITICAL > HIGH > NORMAL > LOW

## Snapshot and Querying

The `ObserverSnapshot` provides a point-in-time view:

```python
snapshot = observer.snapshot()

# Access latency trackers
for key, tracker in snapshot.latency.items():
    print(f"{key}: avg={tracker.avg_ms:.2f}ms, count={tracker.count}")

# Access counters
for key, value in snapshot.counters.items():
    print(f"{key}: {value}")

# Access gauges
for key, value in snapshot.gauges.items():
    print(f"{key}: {value:.2f}")

# Access health states
for key, state in snapshot.health.items():
    print(f"{key}: {'healthy' if state.healthy else state.reason}")

# Convenience methods
cache_hit_rate = snapshot.get_rate(hit_key="cache::hit", miss_key="cache::miss")
avg_latency = snapshot.get_latency(key="ping_pong:HmIP-RF:round_trip")
```

## Best Practices

### 1. Use emit\_\* Functions

Prefer the standalone functions for consistency:

```python
# Good
emit_latency(event_bus=bus, source="my_component", ...)

# Avoid direct event construction
event_bus.publish_sync(LatencyMetricEvent(...))  # Works but less clean
```

### 2. Consistent Source Naming

Use consistent, descriptive source names:

| Source      | Description                       |
| ----------- | --------------------------------- |
| `ping_pong` | Ping/pong round-trip measurements |
| `client`    | Client health state               |
| `rpc`       | RPC call latencies                |
| `cache`     | Cache hit/miss counters           |

### 3. Use source_id for Disambiguation

When the same component exists multiple times:

```python
emit_latency(
    event_bus=bus,
    source="ping_pong",
    source_id=interface_id,  # e.g., "HmIP-RF", "BidCos-RF"
    operation="round_trip",
    duration_ms=rtt,
)
```

### 4. Clean Up on Stop

Always call `stop()` to unsubscribe:

```python
async def stop(self):
    self._metrics_observer.stop()
```

## Public API

```python
from aiohomematic.metrics import (
    # Events
    LatencyMetricEvent,
    CounterMetricEvent,
    GaugeMetricEvent,
    HealthMetricEvent,
    MetricType,

    # Observer
    MetricsObserver,
    ObserverSnapshot,
    LatencyTracker,
    HealthState,

    # Emission utilities
    emit_latency,
    emit_counter,
    emit_gauge,
    emit_health,
    LatencyContext,
    MetricEmitterMixin,
)
```
