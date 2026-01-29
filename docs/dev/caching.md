# Caching Architecture

This guide documents the caching system in aiohomematic, including storage types, invalidation strategies, and performance considerations.

## Overview

The caching system is organized into three tiers:

| Tier           | Storage     | Purpose                   | Survives Restart |
| -------------- | ----------- | ------------------------- | ---------------- |
| **Persistent** | Disk (JSON) | Device/paramset metadata  | Yes              |
| **Dynamic**    | Memory      | Runtime values, commands  | No               |
| **Visibility** | Memory      | Parameter filtering rules | No               |

## Persistent Caches

Long-lived metadata stored on disk in JSON format.

### Device Descriptions

Stores device and channel topology discovered from the CCU.

```
~/.local/share/aiohomematic/cache/{central}_devices_*.json
```

| Field          | Description                         |
| -------------- | ----------------------------------- |
| Schema Version | 2 (normalized descriptions)         |
| Contents       | Device addresses, channels, types   |
| Invalidation   | Schema version bump or manual clear |

### Paramset Descriptions

Stores parameter metadata (MIN/MAX/FLAGS/etc.) for each device type.

```
~/.local/share/aiohomematic/cache/{central}_paramsets_*.json
```

| Field          | Description                              |
| -------------- | ---------------------------------------- |
| Schema Version | 3 (with device-specific patches)         |
| Contents       | Parameter definitions per device/channel |
| Invalidation   | Schema version bump or manual clear      |

### Incident Store

Stores diagnostic snapshots for troubleshooting.

```
~/.local/share/aiohomematic/cache/{central}_incidents_*.json
```

| Field        | Description                     |
| ------------ | ------------------------------- |
| Retention    | 7 days default                  |
| Max Per Type | 20 incidents                    |
| Loading      | On-demand (diagnostics request) |

## Dynamic Caches

Short-lived, memory-resident data that expires automatically.

### Central Data Cache

Caches device parameter values for fast access.

| Setting      | Value                      |
| ------------ | -------------------------- |
| Max Age      | 10 seconds                 |
| Scope        | Per interface              |
| Invalidation | TTL expiry or event-driven |

**Special Behavior**: During initialization, expiration is disabled to prevent cache misses while devices are being created.

### Device Details Cache

Caches enriched device metadata (names, rooms, functions).

| Setting          | Value                                  |
| ---------------- | -------------------------------------- |
| Refresh Interval | 15 seconds                             |
| Source           | Rega script calls                      |
| Contents         | Human-readable names, room assignments |

### Command Tracker

Tracks recently sent commands per data point.

| Setting           | Value                       |
| ----------------- | --------------------------- |
| TTL               | 180 seconds                 |
| Max Size          | 1,000 entries per interface |
| Warning Threshold | 800 entries                 |
| Eviction          | Remove oldest 20% when full |

### Ping/Pong Tracker

Tracks connection health via ping/pong events.

| Setting   | Value                     |
| --------- | ------------------------- |
| TTL       | 300 seconds               |
| Max Size  | 100 entries per interface |
| Structure | FIFO queue                |

## Cache Invalidation Patterns

### Schema Migration (Coordinated Clear)

When the schema version changes:

1. Both device and paramset caches are checked
2. If **either** has a version mismatch, **both** are cleared
3. Caches are rebuilt together from the CCU
4. Ensures consistency between related caches

### Pessimistic Updates (Schedule Data)

Climate schedules use pessimistic cache updates:

```
set_schedule() → CCU writes data → CONFIG_PENDING=False event
                                          ↓
                                   Cache refreshed from CCU
                                          ↓
                                   data_point_updated event
```

**Benefits**:

- Cache always matches CCU state
- Handles CCU-side validation/rounding
- No partial or inconsistent states

### TTL-Based Expiration

Dynamic caches expire based on time-to-live:

| Cache           | TTL  | Behavior                      |
| --------------- | ---- | ----------------------------- |
| Data Cache      | 10s  | Returns `None` after expiry   |
| Command Tracker | 180s | Lazy cleanup on access        |
| Ping/Pong       | 300s | Removed during next operation |

### Size-Based Eviction

When memory limits are reached:

1. **Cleanup Threshold**: Remove expired entries first
2. **Warning Threshold**: Log warning at 80% capacity
3. **Hard Eviction**: Remove oldest 20% at max capacity

## Performance Strategies

### Hash-Based Change Detection

```python
@property
def has_unsaved_changes(self) -> bool:
    return self.content_hash != self._last_hash_saved
```

Avoids redundant disk writes when data hasn't changed.

### Debounced Saves

```python
await cache.save_delayed(delay=1.0)
```

Batches multiple updates into a single disk write.

### Disabled Expiration During Init

During startup, cache expiration is disabled to prevent misses while devices are being created (which may take longer than the normal TTL).

### Two-Phase Load

1. Check schema version **before** processing
2. If outdated: signal cache rebuild
3. If valid: process and rebuild indexes

Ensures schema migrations are atomic.

## Storage Locations

### Default Location

```
~/.local/share/aiohomematic/cache/
```

### Home Assistant Integration

When running in Home Assistant, caches use HA's native storage:

```
~/.homeassistant/.storage/homematicip_local/
```

The `StorageFactoryProtocol` allows seamless substitution.

## Cache Statistics

Each cache tracks performance metrics:

```python
CacheStatistics:
    hits: int       # Successful lookups
    misses: int     # Failed lookups
    evictions: int  # Entries removed
    hit_rate: float # (hits / total) * 100
```

Access via `CacheCoordinator` for diagnostics.

## CacheCoordinator

The `CacheCoordinator` manages all caches centrally.

### Lifecycle Methods

| Method            | Purpose                             |
| ----------------- | ----------------------------------- |
| `load_all()`      | Load persistent caches on startup   |
| `save_all()`      | Save persistent caches on shutdown  |
| `clear_all()`     | Clear all caches (rebuild required) |
| `clear_on_stop()` | Clear memory caches only            |

### Event Subscriptions

| Event                     | Action                        |
| ------------------------- | ----------------------------- |
| `DeviceRemovedEvent`      | Remove device from all caches |
| `DataFetchCompletedEvent` | Trigger cache save            |

## Memory Limits Summary

| Component         | Max Size | Notes             |
| ----------------- | -------- | ----------------- |
| Command Tracker   | 1,000    | Per interface     |
| Ping/Pong Tracker | 100      | Per interface     |
| Incident Store    | 20       | Per incident type |

## Key Constants

```python
# Expiration
MAX_CACHE_AGE = 10                          # Data cache (seconds)
LAST_COMMAND_SEND_STORE_TIMEOUT = 180       # Command tracker (seconds)
PING_PONG_MISMATCH_COUNT_TTL = 300          # Ping/pong (seconds)

# Memory limits
COMMAND_TRACKER_MAX_SIZE = 1000
COMMAND_TRACKER_WARNING_THRESHOLD = 800
PING_PONG_CACHE_MAX_SIZE = 100
INCIDENT_STORE_MAX_PER_TYPE = 20

# Refresh intervals
periodic_refresh_interval = 15              # Device details (seconds)
```

## Best Practices

### For Library Consumers

1. **Don't bypass caches** - Use provided APIs for data access
2. **Handle cache misses** - Methods may return `None` when data expires
3. **Subscribe to events** - Use `data_point_updated` events instead of polling

### For Contributors

1. **Coordinate cache clears** - Use `CacheCoordinator.clear_all()` not individual clears
2. **Respect schema versions** - Bump version when changing cache structure
3. **Add statistics** - Track hits/misses for new caches

## See Also

- [Architecture Overview](../architecture.md)
- [Data Flow](../data_flow.md)
- [Error Handling](error_handling.md)
