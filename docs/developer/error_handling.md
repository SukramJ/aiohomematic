# Error Handling Guide

This guide documents the exception hierarchy, error handling patterns, and recovery mechanisms in aiohomematic.

## Exception Hierarchy

```
BaseHomematicException
│
├── ClientException          # Generic client-level errors
├── NoConnectionException    # Network/connection failures
├── AuthFailure              # Authentication failures
├── InternalBackendException # Backend internal errors
├── CircuitBreakerOpenException  # Circuit breaker active
├── ValidationException      # Input validation failures
├── UnsupportedException     # Feature not supported
├── NoClientsException       # All clients unavailable
├── DescriptionNotFoundException  # Cache lookup failures
├── AioHomematicException    # Generic library errors
└── AioHomematicConfigException  # Configuration errors
```

## Exception Reference

| Exception                     | When Raised                               | Recovery                   |
| ----------------------------- | ----------------------------------------- | -------------------------- |
| `ClientException`             | RPC call failures, transport issues       | Retry with backoff         |
| `NoConnectionException`       | TCP connection refused, host unreachable  | Wait and retry             |
| `AuthFailure`                 | Invalid credentials (401, -32001)         | User must fix credentials  |
| `InternalBackendException`    | CCU/Homegear internal error (500, -32603) | Wait and retry             |
| `CircuitBreakerOpenException` | Too many recent failures                  | Automatic recovery         |
| `ValidationException`         | Invalid parameters                        | Fix input data             |
| `UnsupportedException`        | Operation not available                   | Check backend capabilities |

## Failure Reasons

Exceptions are categorized into failure reasons for state machine transitions:

```python
class FailureReason(StrEnum):
    NONE = "none"              # Normal operation
    AUTH = "auth"              # Authentication failure
    NETWORK = "network"        # Network connectivity
    INTERNAL = "internal"      # Backend internal error
    TIMEOUT = "timeout"        # Operation timed out
    CIRCUIT_BREAKER = "circuit_breaker"  # Circuit breaker open
    UNKNOWN = "unknown"        # Unclassified error
```

### Mapping Exceptions to Failure Reasons

```python
from aiohomematic.client._rpc_errors import exception_to_failure_reason

reason = exception_to_failure_reason(exc=caught_exception)
# Returns FailureReason enum value
```

## Circuit Breaker

The circuit breaker prevents cascading failures by temporarily blocking requests after repeated failures.

### States

```
CLOSED (normal) → OPEN (blocking) → HALF_OPEN (testing) → CLOSED
```

| State         | Behavior                                                         |
| ------------- | ---------------------------------------------------------------- |
| **CLOSED**    | Normal operation, requests pass through                          |
| **OPEN**      | All requests immediately fail with `CircuitBreakerOpenException` |
| **HALF_OPEN** | One test request allowed; success closes, failure reopens        |

### Configuration

```python
class CircuitBreakerConfig:
    failure_threshold: int = 5      # Failures before opening
    recovery_timeout: float = 30.0  # Seconds before HALF_OPEN
    success_threshold: int = 2      # Successes to close from HALF_OPEN
```

### Behavior

1. **Failures accumulate** in CLOSED state
2. **Threshold reached** → transition to OPEN
3. **Requests blocked** → raise `CircuitBreakerOpenException`
4. **Recovery timeout elapses** → transition to HALF_OPEN
5. **Test request succeeds** → transition to CLOSED
6. **Test request fails** → back to OPEN

**Important**: `CircuitBreakerOpenException` is **not retryable**. The circuit breaker handles its own recovery.

## Connection Recovery

When connection is lost, the `ConnectionRecoveryCoordinator` manages staged recovery.

### Recovery Stages

```
IDLE → DETECTING → COOLDOWN → TCP_CHECKING → RPC_CHECKING →
WARMING_UP → STABILITY_CHECK → RECONNECTING → DATA_LOADING → RECOVERED
```

| Stage           | Purpose                              |
| --------------- | ------------------------------------ |
| COOLDOWN        | Initial wait period                  |
| TCP_CHECKING    | Non-invasive port availability check |
| RPC_CHECKING    | RPC service responds to listMethods  |
| WARMING_UP      | Allow services to stabilize          |
| STABILITY_CHECK | Confirm consistent RPC responses     |
| RECONNECTING    | Full client reconnection             |
| DATA_LOADING    | Reload device and paramset data      |

### Failure Handling

If any stage fails:

1. Increment retry counter
2. Apply exponential backoff (5s → 10s → 20s → 40s → 60s max)
3. Retry from TCP_CHECKING stage
4. After 8 failures → enter FAILED state
5. FAILED state → periodic heartbeat retry every 60s

### Exponential Backoff

```python
# Retry delay calculation
delay = BASE_RETRY_DELAY * (2 ** (consecutive_failures - 1))
delay = min(delay, MAX_RETRY_DELAY)

# Progression: 5s → 10s → 20s → 40s → 60s (capped)
```

## Client State Machine

Clients maintain connection state via a state machine.

### States

| State        | Description                      |
| ------------ | -------------------------------- |
| CREATED      | Initial state                    |
| INITIALIZING | Loading configuration            |
| INITIALIZED  | Ready to connect                 |
| CONNECTING   | Establishing connection          |
| CONNECTED    | Active and operational           |
| DISCONNECTED | Connection lost                  |
| RECONNECTING | Attempting to restore connection |
| FAILED       | Unrecoverable error              |
| STOPPING     | Graceful shutdown in progress    |
| STOPPED      | Terminated                       |

### Key Properties

```python
state_machine.is_available  # True if CONNECTED or RECONNECTING
state_machine.can_reconnect # True if reconnection possible
```

### Valid Transitions

```python
# Normal flow
CREATED → INITIALIZING → INITIALIZED → CONNECTING → CONNECTED

# Disconnection and recovery
CONNECTED → DISCONNECTED → RECONNECTING → CONNECTED

# Failure
CONNECTING → FAILED
INITIALIZING → FAILED

# Shutdown
CONNECTED → STOPPING → STOPPED
```

## Request Coalescing

Concurrent identical requests are deduplicated to reduce backend load.

```python
# First request executes
# Subsequent identical requests wait for shared result
# All waiters receive same result (or exception)

result = await coalescer.execute(
    key="unique_request_identifier",
    executor=lambda: actual_rpc_call(),
)
```

**Benefit**: During device discovery, multiple requests for the same device description share a single RPC call.

## Timeout Configuration

Default timeouts are defined in `CentralConfig`:

| Setting                  | Default | Purpose                           |
| ------------------------ | ------- | --------------------------------- |
| `rpc_timeout`            | 60s     | Individual RPC call timeout       |
| `ping_timeout`           | 10s     | Connectivity check timeout        |
| `callback_warn_interval` | 180s    | Time before missing event warning |

### Recovery Timeouts

| Setting                       | Default | Purpose                 |
| ----------------------------- | ------- | ----------------------- |
| `reconnect_initial_delay`     | 2s      | First retry delay       |
| `reconnect_max_delay`         | 120s    | Maximum retry delay     |
| `reconnect_initial_cooldown`  | 30s     | Initial cooldown period |
| `reconnect_tcp_check_timeout` | 60s     | TCP check total timeout |
| `reconnect_warmup_delay`      | 15s     | Post-connection warmup  |

## Error Handling Best Practices

### Catching Exceptions

```python
from aiohomematic.exceptions import (
    ClientException,
    NoConnectionException,
    AuthFailure,
    CircuitBreakerOpenException,
)

try:
    await client.get_value(...)
except AuthFailure:
    # User must fix credentials
    notify_user("Invalid credentials")
except NoConnectionException:
    # Network issue - will auto-recover
    log.warning("Connection lost, recovery in progress")
except CircuitBreakerOpenException:
    # Too many failures - don't retry
    log.info("Circuit breaker active, waiting for recovery")
except ClientException as exc:
    # Generic client error
    log.error(f"RPC call failed: {exc}")
```

### Handling Recovery Events

```python
from aiohomematic.central.events import InterfaceStateChangedEvent

def on_interface_state(event: InterfaceStateChangedEvent) -> None:
    if event.state == InterfaceState.CONNECTED:
        log.info(f"Interface {event.interface_id} connected")
    elif event.state == InterfaceState.DISCONNECTED:
        log.warning(f"Interface {event.interface_id} disconnected")
    elif event.state == InterfaceState.RECOVERING:
        log.info(f"Interface {event.interface_id} recovering...")

central.event_bus.subscribe(
    event_type=InterfaceStateChangedEvent,
    handler=on_interface_state,
)
```

## Logging

The `log_exception` decorator provides consistent exception logging:

```python
from aiohomematic.exceptions import log_exception

@log_exception(
    exc_type=ClientException,
    level=logging.ERROR,
    re_raise=False,
    exc_return=None,
)
async def safe_operation():
    # Exception is logged and None returned
    await risky_call()
```

## See Also

- [Architecture Overview](../architecture.md)
- [Circuit Breaker ADR](../adr/0001-circuit-breaker-and-connection-state.md)
- [Data Flow](../architecture/data_flow.md)
