# ADR 0005: Unbounded Parameter Visibility Cache

## Status

Accepted

## Context

The `ParameterVisibilityCache` determines which parameters should be exposed as DataPoints and events. This check is performed frequently during device creation and UI rendering.

A question arose whether the cache should have size limits (LRU eviction) or TTL expiration to prevent unbounded memory growth.

## Decision

Use **unbounded memoization** for `ParameterVisibilityCache` without explicit size limits or TTL.

### Implementation

```python
class ParameterVisibilityCache:
    def __init__(self, *, config_provider: ConfigProvider) -> None:
        self._config_provider = config_provider
        self._cache: dict[tuple[str, str, ParamsetKey, str], bool] = {}

    def is_visible(
        self,
        *,
        interface_id: str,
        channel_address: str,
        paramset_key: ParamsetKey,
        parameter: str,
    ) -> bool:
        key = (interface_id, channel_address, paramset_key, parameter)
        if key not in self._cache:
            self._cache[key] = self._compute_visibility(...)
        return self._cache[key]
```

## Consequences

### Advantages

- **Simplicity**: No eviction logic or TTL management
- **Predictable performance**: O(1) lookup after first computation
- **No cache misses after warmup**: All visibility rules cached permanently

### Why Unbounded is Safe

1. **Natural bounds from domain**: The cache is inherently bounded by the finite number of devices and parameters:

   - Typical installation: 10-200 devices
   - Each device: 1-20 channels
   - Each channel: 5-50 parameters
   - **Maximum entries**: ~50,000 (realistic max)

2. **Static data**: Parameter visibility rules don't change during runtime. Once computed, visibility remains constant until restart.

3. **Memory efficiency**: Each entry is small:

   - Key: tuple of 4 strings (~200 bytes)
   - Value: boolean (8 bytes)
   - 50,000 entries ≈ 10 MB maximum

4. **Performance critical path**: Visibility checks occur during:

   - Device/DataPoint creation
   - UI rendering
   - Event filtering

   Caching eliminates repeated rule evaluation.

### Disadvantages Accepted

- **Memory not released**: Cache entries persist until process restart
- **No invalidation**: If rules change (they don't at runtime), restart required

## Alternatives Considered

### 1. LRU Cache with Size Limit

**Rejected**: Would cause cache misses for less frequently accessed parameters. All parameters are equally important.

### 2. TTL-Based Expiration

**Rejected**: Visibility rules are static. TTL would cause unnecessary recomputation.

### 3. Lazy Computation Without Caching

**Rejected**: Rule evaluation is expensive (involves config lookups and pattern matching). Would significantly impact performance.

### 4. `@functools.lru_cache` Decorator

**Considered viable**: Would work but provides less control. Explicit dict cache chosen for clarity and potential future enhancements.

## References

- `aiohomematic/store/visibility.py` - ParameterVisibilityCache implementation
- `docs/architecture.md` - "ParameterVisibilityCache: Unbounded Memoization" section

---

_Created: 2025-12-10_
_Author: Architecture Review_
