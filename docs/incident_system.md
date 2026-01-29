# Incident System Architecture

## Overview

The Incident System provides persistent storage for diagnostic events, enabling post-mortem analysis of connection and communication issues. It is designed to capture **all relevant information** needed to understand what led to a problem.

## Purpose

1. **Diagnostic Analysis**: Capture enough context so that AI or developers can analyze root causes
2. **Persistent History**: Store incidents across restarts for trend analysis
3. **Correlation**: Enable correlation between related events (e.g., PingPong mismatches followed by circuit breaker trips)
4. **Automatic Cleanup**: Manage storage growth with configurable retention
5. **Per-Type Storage**: Each incident type maintains its own history (max 20 per type, 7-day retention) to ensure important but infrequent events are not crowded out by high-frequency ones

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              CentralUnit                                 │
│                                                                          │
│  ┌─────────────────┐    ┌─────────────────┐   ┌─────────────────────┐  │
│  │ CacheCoordinator│    │ClientCoordinator │   │ConnectionRecovery   │  │
│  │                 │    │                  │   │   Coordinator       │  │
│  │  ┌───────────┐  │    │  ┌────────────┐  │   │                     │  │
│  │  │IncidentSto│◄─┼────┼──│CircuitBreak│  │   │  CONNECTION_LOST ──┼──┤
│  │  │    re     │  │    │  │    er      │  │   │  incidents         │  │
│  │  └───────────┘  │    │  └────────────┘  │   └─────────────────────┘  │
│  │       ▲         │    │                  │                            │
│  │       │         │    └─────────────────┘                             │
│  │  ┌────┴─────┐   │                                                    │
│  │  │PingPongTr│   │                                                    │
│  │  │  acker   │   │                                                    │
│  │  └──────────┘   │                                                    │
│  └─────────────────┘                                                    │
└─────────────────────────────────────────────────────────────────────────┘
```

## Core Components

### IncidentStore

**Location**: `aiohomematic/store/persistent/incident.py`

**Responsibilities**:

- Persist incidents to disk as JSON
- Load incidents on demand
- Auto-cleanup based on retention period
- Provide diagnostics API for Home Assistant

**Persistence Strategy**: Save-on-incident, load-on-demand

- Incidents are written immediately when recorded
- Full history is only loaded when diagnostics are requested
- Reduces memory footprint during normal operation

### IncidentRecorderProtocol

**Location**: `aiohomematic/interfaces/operations.py`

**Purpose**: Decoupled interface for recording incidents, allowing components to record incidents without direct dependency on IncidentStore.

```python
class IncidentRecorderProtocol(Protocol):
    def record_incident(
        self,
        *,
        incident_type: IncidentType,
        severity: IncidentSeverity,
        message: str,
        interface_id: str | None = None,
        context: dict[str, Any] | None = None,
        journal: PingPongJournal | None = None,
    ) -> Coroutine[Any, Any, IncidentSnapshot]: ...
```

## Incident Types

### Connection Health Incidents

| Type                        | Severity | Source                                   | Description                            |
| --------------------------- | -------- | ---------------------------------------- | -------------------------------------- |
| `PING_PONG_MISMATCH_HIGH`   | ERROR    | PingPongTracker                          | Pending PONG count exceeded threshold  |
| `PING_PONG_UNKNOWN_HIGH`    | WARNING  | PingPongTracker                          | Unknown PONG count exceeded threshold  |
| `CIRCUIT_BREAKER_TRIPPED`   | ERROR    | CircuitBreaker                           | Circuit breaker opened due to failures |
| `CIRCUIT_BREAKER_RECOVERED` | INFO     | CircuitBreaker                           | Circuit breaker recovered              |
| `CONNECTION_LOST`           | ERROR    | ConnectionRecoveryCoordinator            | Connection to backend lost             |
| `CONNECTION_RESTORED`       | INFO     | ConnectionRecoveryCoordinator            | Connection to backend restored         |
| `RPC_ERROR`                 | ERROR    | AioXmlRpcProxy / AioJsonRpcAioHttpClient | RPC call failed                        |
| `CALLBACK_TIMEOUT`          | WARNING  | ClientCCU                                | Callback from backend timed out        |

## Incident Data Structure

### IncidentSnapshot

```python
@dataclass(frozen=True, slots=True)
class IncidentSnapshot:
    id: str                              # UUID
    timestamp: datetime                  # When incident occurred
    incident_type: IncidentType          # Type classification
    severity: IncidentSeverity           # INFO, WARNING, ERROR
    message: str                         # Human-readable description
    interface_id: str | None             # Which interface (if applicable)
    context: dict[str, Any]              # Type-specific diagnostic data
    journal: list[JournalEntry] | None   # Event history (for PingPong)
```

## Context Data Requirements

**Critical**: Each incident MUST include enough context for AI analysis.

### PING_PONG_MISMATCH_HIGH Context

```python
{
    "pending_count": int,        # Current pending PONG count
    "threshold": int,            # Configured threshold
    # Plus: journal with last N PING/PONG events and timestamps
}
```

### PING_PONG_UNKNOWN_HIGH Context

```python
{
    "unknown_count": int,        # Current unknown PONG count
    "threshold": int,            # Configured threshold
    # Plus: journal with last N PING/PONG events and timestamps
}
```

### CIRCUIT_BREAKER_TRIPPED Context

```python
{
    "old_state": str,            # State before trip (closed/half_open)
    "failure_count": int,        # Consecutive failures that caused trip
    "failure_threshold": int,    # Configured threshold
    "recovery_timeout": float,   # Seconds before half-open attempt
    "last_failure_time": str,    # ISO timestamp of last failure
    "total_requests": int,       # Total requests since start
}
```

### CIRCUIT_BREAKER_RECOVERED Context

```python
{
    "success_count": int,        # Successful requests in half-open
    "success_threshold": int,    # Configured threshold for recovery
}
```

### CONNECTION_LOST Context

```python
{
    "reason": str,                    # Reason for connection loss
    "detected_at": str,               # ISO timestamp when loss was detected
    "client_state": str | None,       # Client state at time of loss
    "circuit_breaker_state": str | None,  # Circuit breaker state
    "recovery_attempt_count": int,    # Number of recovery attempts so far
    "active_recoveries": list[str],   # List of interfaces currently recovering
    "in_failed_state": bool,          # Whether coordinator is in FAILED state
}
```

### CONNECTION_RESTORED Context

```python
{
    "total_attempts": int,            # Total recovery attempts made
    "total_duration_ms": float,       # Total recovery duration in milliseconds
    "stages_completed": list[str],    # Recovery stages completed (e.g., ["TCP_CHECKING", "RPC_CHECKING", ...])
    "client_state": str | None,       # Client state after restoration
    "circuit_breaker_state": str | None,  # Circuit breaker state after restoration
    "was_in_failed_state": bool,      # Whether coordinator was in FAILED state before recovery
}
```

### RPC_ERROR Context

```python
{
    "protocol": str,                  # Protocol type ("xml-rpc" or "json-rpc")
    "method": str,                    # RPC method that failed (e.g., "setValue", "getParamset")
    "error_type": str,                # Error type (e.g., "SSLError", "OSError", "XMLRPCFault", "JSONRPCError")
    "error_message": str,             # Sanitized error message (sensitive info removed)
    "tls_enabled": bool,              # Whether TLS is enabled for this connection
}
```

### CALLBACK_TIMEOUT Context

```python
{
    "seconds_since_last_event": float,    # Time since last callback was received
    "callback_warn_interval": float,      # Configured threshold in seconds
    "last_event_time": str,               # ISO timestamp of last callback received
    "client_state": str,                  # Client state when timeout detected
    "circuit_breaker_state": str | None,  # Circuit breaker state (if available)
}
```

## Storage Configuration

### Per-Type Limits

Incidents are stored **per IncidentType** to ensure each type maintains its own history:

```python
INCIDENT_STORE_MAX_PER_TYPE: Final = 20  # Max incidents per type
DEFAULT_MAX_AGE_DAYS: Final = 7          # 7-day retention
```

**Benefits**:

- High-frequency incidents (e.g., CONNECTION_LOST during network issues) don't crowd out rare but important incidents
- Each incident type has guaranteed storage space
- Easy to analyze patterns within a specific incident type

**Example Storage Distribution**:

```
PING_PONG_MISMATCH_HIGH:   5 incidents (last 7 days)
CIRCUIT_BREAKER_TRIPPED:  12 incidents (last 7 days)
CONNECTION_LOST:          20 incidents (oldest evicted to maintain limit)
CIRCUIT_BREAKER_RECOVERED: 8 incidents (last 7 days)
```

## Integration Pattern

### Sync-to-Async Bridge

Components like CircuitBreaker operate synchronously but IncidentStore is async. The pattern used:

```python
def _record_incident_sync(self, ...) -> None:
    if (incident_recorder := self._incident_recorder) is None:
        return

    # Capture current state for async closure
    captured_data = {...}

    async def _record() -> None:
        try:
            await incident_recorder.record_incident(...)
        except Exception as err:
            _LOGGER.debug("Failed to record incident: %s", err)

    # Fire and forget - suppress if no event loop
    with contextlib.suppress(RuntimeError):
        asyncio.get_running_loop().create_task(_record())
```

### Dependency Injection

Incident recorder is injected as an optional dependency:

```python
class CircuitBreaker:
    def __init__(
        self,
        *,
        incident_recorder: IncidentRecorderProtocol | None = None,
        ...
    ) -> None:
        self._incident_recorder = incident_recorder
```

## Storage Format

Incidents are stored as JSON in `{storage_path}/cache/{central_name}_hm_incidents.json`:

```json
{
  "incidents": [
    {
      "id": "uuid-v4",
      "timestamp": "2026-01-03T10:15:30.123456",
      "incident_type": "CIRCUIT_BREAKER_TRIPPED",
      "severity": "error",
      "message": "Circuit breaker opened for BidCos-RF after 5 failures",
      "interface_id": "BidCos-RF",
      "context": {
        "old_state": "closed",
        "failure_count": 5,
        "failure_threshold": 5,
        "recovery_timeout": 30.0,
        "last_failure_time": "2026-01-03T10:15:30.100000",
        "total_requests": 127
      },
      "journal": null
    }
  ],
  "version": 1
}
```

## Home Assistant Integration

### Diagnostics Export

IncidentStore exposes a diagnostics method for HA:

```python
async def get_diagnostics(self) -> dict[str, Any]:
    """Return diagnostic data for Home Assistant."""
    return {
        "incidents": [i.to_dict() for i in await self._load_incidents()],
        "total_count": len(self._incidents),
        "retention_days": self._retention_days,
    }
```

This is integrated in `homematicip_local/diagnostics.py`:

```python
diag["incident_store"] = await central.cache_coordinator.incident_store.get_diagnostics()
```

## Design Principles

### 1. Comprehensive Context

Every incident should include enough information to answer:

- What happened?
- When did it happen?
- What was the system state?
- What thresholds or configurations were in effect?
- What events led up to this?

### 2. Fire-and-Forget Recording

Incident recording should never block the caller:

- Use async tasks scheduled on event loop
- Silently skip if no event loop
- Log and continue on recording failures

### 3. Minimal Runtime Impact

- Save-on-incident avoids keeping all data in memory
- Load-on-demand for diagnostics only
- Auto-cleanup prevents unbounded growth

### 4. Protocol-Based DI

Components depend on `IncidentRecorderProtocol`, not `IncidentStore`:

- Enables testing with mocks
- Allows alternative implementations
- Reduces coupling

## Adding New Incident Types

### 1. Add Type to IncidentType Enum

```python
# aiohomematic/store/types.py
class IncidentType(StrEnum):
    MY_NEW_INCIDENT = "MY_NEW_INCIDENT"
    """Description of when this incident occurs."""
```

### 2. Add Recording in Component

```python
def _record_my_incident(self) -> None:
    if (incident_recorder := self._incident_recorder) is None:
        return

    from aiohomematic.store.types import IncidentSeverity, IncidentType

    # Capture all relevant state
    context = {
        "relevant_field_1": self._field_1,
        "relevant_field_2": self._field_2,
        "configuration": self._config.some_setting,
        # Include anything that helps diagnose the issue
    }

    async def _record() -> None:
        try:
            await incident_recorder.record_incident(
                incident_type=IncidentType.MY_NEW_INCIDENT,
                severity=IncidentSeverity.ERROR,
                message=f"Descriptive message about what happened",
                interface_id=self._interface_id,
                context=context,
            )
        except Exception as err:
            _LOGGER.debug("Failed to record incident: %s", err)

    with contextlib.suppress(RuntimeError):
        asyncio.get_running_loop().create_task(_record())
```

### 3. Add Tests

```python
@pytest.mark.asyncio
async def test_my_incident_recorded(self) -> None:
    from unittest.mock import AsyncMock, MagicMock

    incident_recorder = MagicMock()
    incident_recorder.record_incident = AsyncMock()

    # Trigger the incident
    ...

    # Wait for async task
    await asyncio.sleep(0.01)

    # Verify
    incident_recorder.record_incident.assert_called_once()
    call_kwargs = incident_recorder.record_incident.call_args.kwargs
    assert call_kwargs["incident_type"] == IncidentType.MY_NEW_INCIDENT
```

### 4. Document Context Schema

Add the context schema to this document in the "Context Data Requirements" section.

## Related Documentation

- [Architecture Overview](architecture.md)
- [Circuit Breaker Implementation](https://github.com/sukramj/aiohomematic/blob/devel/aiohomematic/client/circuit_breaker.py)
