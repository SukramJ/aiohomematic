# ADR 0001: CircuitBreaker and CentralConnectionState Coexistence

## Status

Accepted

## Context

The project requires robust error handling for backend communication:

1. **Existing component**: `CentralConnectionState` tracks connection issues per interface and notifies external consumers (Home Assistant) about state changes.

2. **Proposed addition**: `CircuitBreaker` pattern to prevent retry-storms during backend outages.

**Core question**: Should `CentralConnectionState` be replaced or extended by `CircuitBreaker`, or should both components coexist?

## Decision

**Keep both components** with clearly separated responsibilities:

### CentralConnectionState (keep)

- Centralized health aggregation at the API level
- State-change callbacks for external consumers
- Interface-specific issue tracking
- Log-spam prevention via `handle_exception_log()`

### CircuitBreaker (add new)

- Per-proxy request flow control
- Tri-state model (CLOSED/OPEN/HALF_OPEN)
- Automatic timeout-based recovery
- Fast-fail for known backend outages

### Integration

```
CentralConnectionState (central, aggregates)
         ^ notifies
    +----+----+
    |    |    |
    v    v    v
CircuitBreaker (per proxy)
    |    |    |
    v    v    v
BaseRpcProxy / AioJsonRpcClient
```

CircuitBreaker notifies CentralConnectionState on relevant state transitions:

- CLOSED -> OPEN: `add_issue()`
- OPEN -> CLOSED: `remove_issue()`

## Consequences

### Advantages

- **Separation of Concerns**: Each component has clear responsibility
- **Backward compatibility**: Existing API remains unchanged
- **Improved resilience**: Fast-fail + automatic recovery
- **Testability**: Both components independently testable
- **External consumers**: Home Assistant continues to receive state callbacks

### Disadvantages

- **Complexity**: Two components instead of one
- **Coordination**: CircuitBreaker must correctly notify CentralConnectionState
- **Maintenance**: Two APIs to maintain

## Alternatives Considered

### 1. Replace CentralConnectionState with CircuitBreaker

**Rejected**: CentralConnectionState provides features CircuitBreaker lacks:

- State-change callbacks for external consumers
- Log-spam prevention
- Aggregated view across all interfaces

### 2. Extend CentralConnectionState to include CircuitBreaker

**Rejected**: Would violate Single Responsibility Principle. CentralConnectionState handles health monitoring, not request flow control.

### 3. Only CircuitBreaker, CentralConnectionState as wrapper

**Rejected**: Increased complexity without clear benefit. CentralConnectionState has its own logic (callbacks, logging) that doesn't belong in CircuitBreaker.

## References

- [Circuit Breaker Pattern (Martin Fowler)](https://martinfowler.com/bliki/CircuitBreaker.html)
- `aiohomematic/central/__init__.py` - CentralConnectionState implementation
- `aiohomematic/client/circuit_breaker.py` - CircuitBreaker implementation

---

_Created: 2025-12-10_
_Author: Architecture Review_
