# ADR 0014: Removal of Retry Logic for RPC Operations

## Status

Accepted

## Context

The project introduced automatic retry logic (`@with_retry` decorator and `RetryStrategy` class) in version 2025.12.8 to handle transient network errors in RPC operations. This feature:

1. Retried failed RPC calls up to 3 times with exponential backoff
2. Was applied to XML-RPC operations in `AioXmlRpcProxy`
3. Was applied to JSON-RPC operations in `AioJsonRpcAioHttpClient`
4. Was applied to high-level API operations in `HomematicAPI`

### Problems Identified

1. **Circuit Breaker Conflicts**: The retry mechanism conflicted with the `CircuitBreaker` pattern. Each retry attempt counted as a separate failure, causing the circuit breaker to trip prematurely. For example, 2 requests × 3 retries = 6 failures, exceeding the 5-failure threshold.

2. **Cascading Failures**: On slow backends like VirtualDevices on Raspberry Pi 4 with OpenCCU, retries during initialization caused rapid circuit breaker trips before the client could fully start (see Issue #2731).

3. **State Machine Redundancy**: The `ClientStateMachine` and `ConnectionRecoveryCoordinator` already provide comprehensive reconnection logic with:

   - TCP port availability checks
   - RPC service health verification
   - Warmup periods for service stabilization
   - Exponential backoff recovery

4. **Potential Side Effects for Write Operations**: Retrying `setValue()` operations could cause unintended duplicate actions (e.g., toggling a switch multiple times).

5. **Homematic Architecture Mismatch**: The CCU/Homegear backends have their own connection management. The event-driven callback model (XML-RPC server receiving events from CCU) doesn't align well with request-level retry semantics.

### Bypass Lists Growth

To mitigate the issues, bypass lists were introduced:

- `_CIRCUIT_BREAKER_BYPASS_METHODS`: 5 methods bypassed
- `_RETRY_BYPASS_METHODS`: 2 methods bypassed (and growing)

This indicated that the retry mechanism was causing more problems than it solved.

## Decision

**Remove the retry logic entirely** from the codebase:

1. Delete `aiohomematic/retry.py` module
2. Remove `@with_retry` decorator from all locations
3. Remove `RetryStrategy` usage from `AioXmlRpcProxy`
4. Remove retry-related constants (`RETRY_MAX_ATTEMPTS`, etc.)
5. Remove all retry-related tests

### Rationale

The existing error handling mechanisms are sufficient:

| Mechanism                     | Purpose                     | Location   |
| ----------------------------- | --------------------------- | ---------- |
| CircuitBreaker                | Fast-fail on backend outage | Per-proxy  |
| CentralConnectionState        | Aggregate health tracking   | Central    |
| ClientStateMachine            | Connection lifecycle        | Per-client |
| ConnectionRecoveryCoordinator | Automatic reconnection      | Central    |

These components provide comprehensive error handling without the side effects of request-level retries.

## Consequences

### Positive

- Simpler codebase with fewer moving parts
- No more retry-induced circuit breaker trips
- Predictable behavior: one request = one attempt
- Better performance on slow backends
- Clearer error propagation to consumers

### Negative

- Transient network glitches may cause immediate failures instead of automatic recovery
- Consumers (Home Assistant) may see more temporary errors during network instability

### Mitigation

The `ConnectionRecoveryCoordinator` provides reconnection logic at the connection level, which is the appropriate place to handle network instability in Homematic systems.

## Alternatives Considered

### Keep Retry for Read-Only Operations

Only apply retry to `getValue()`, `getParamset()`, etc. Rejected because:

- Still conflicts with circuit breaker
- Adds complexity with operation-type discrimination
- Read operations are also covered by ConnectionRecoveryCoordinator

### Reduce Max Attempts to 1

Effectively disables retry while keeping the code. Rejected because:

- Dead code adds maintenance burden
- Confusing for developers
- Better to remove cleanly

## References

- Issue #2731: VirtualDevices circuit breaker trips during initialization
- ADR 0001: CircuitBreaker and CentralConnectionState Coexistence
- Changelog 2025.12.8: Original retry introduction
- Changelog 2026.1.11: init() retry bypass
- Changelog 2026.1.14: system.listMethods retry bypass (superseded by this ADR)
