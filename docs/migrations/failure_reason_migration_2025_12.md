# Migration Guide: FailureReason Support

**Date**: December 2025
**Version**: 2025.12.34+ (propagation fix in 2025.12.35)
**Breaking Change**: No (additive API)

## Overview

This release introduces `FailureReason` support to differentiate between various failure types when the Central or Client enters a `FAILED` state. Previously, integrations could only detect that the system was in a failed state, but couldn't determine the root cause (authentication failure, network issue, etc.).

## New Features

### 1. FailureReason Enum

A new enum `FailureReason` is available in `aiohomematic.const`:

```python
from aiohomematic.const import FailureReason

class FailureReason(StrEnum):
    NONE = "none"                    # No failure - normal operation
    AUTH = "auth"                    # Authentication/authorization failure
    NETWORK = "network"              # Network connectivity issue
    INTERNAL = "internal"            # Internal backend error
    TIMEOUT = "timeout"              # Operation timed out
    CIRCUIT_BREAKER = "circuit_breaker"  # Circuit breaker is open
    UNKNOWN = "unknown"              # Unknown or unclassified error
```

### 2. ClientStateMachine Changes

`ClientStateMachine` now tracks failure reason:

```python
# New properties
sm.failure_reason -> FailureReason   # Returns the categorized failure reason
sm.failure_message -> str            # Returns human-readable message

# Updated method signature
sm.transition_to(
    target=ClientState.FAILED,
    reason="Human-readable message",
    failure_reason=FailureReason.AUTH,  # NEW optional parameter
)
```

### 3. CentralStateMachine Changes

`CentralStateMachine` now tracks failure reason and source interface:

```python
# New properties
sm.failure_reason -> FailureReason       # Returns the categorized failure reason
sm.failure_message -> str                # Returns human-readable message
sm.failure_interface_id -> str | None    # Returns the interface that caused the failure

# Updated method signature
sm.transition_to(
    target=CentralState.FAILED,
    reason="Human-readable message",
    failure_reason=FailureReason.AUTH,       # NEW optional parameter
    failure_interface_id="HmIP-RF",          # NEW optional parameter
)
```

### 4. SystemStatusEvent Changes

`SystemStatusEvent` now includes failure information:

```python
from aiohomematic.central.integration_events import SystemStatusEvent
from aiohomematic.const import FailureReason

# New fields
event.failure_reason -> FailureReason | None  # Set when central_state is FAILED
event.failure_interface_id -> str | None      # Interface that caused the failure
```

### 5. Helper Function

A new helper function to map exceptions to failure reasons:

```python
from aiohomematic.client._rpc_errors import exception_to_failure_reason
from aiohomematic.const import FailureReason
from aiohomematic.exceptions import AuthFailure

exc = AuthFailure("Invalid credentials")
reason = exception_to_failure_reason(exc)
assert reason == FailureReason.AUTH
```

## Migration Steps for Home Assistant Integration

### Step 1: Update SystemStatusEvent Handler

**Before:**

```python
async def on_system_status(*, event: SystemStatusEvent) -> None:
    if event.central_state == CentralState.FAILED:
        # Could only show generic error
        async_create_issue(
            hass,
            domain=DOMAIN,
            issue_id="connection_failed",
            translation_key="connection_failed",
            severity=IssueSeverity.ERROR,
        )
```

**After:**

```python
from aiohomematic.const import FailureReason

async def on_system_status(*, event: SystemStatusEvent) -> None:
    if event.central_state == CentralState.FAILED:
        # Now can show specific error based on failure_reason
        if event.failure_reason == FailureReason.AUTH:
            async_create_issue(
                hass,
                domain=DOMAIN,
                issue_id="authentication_failed",
                translation_key="authentication_failed",
                severity=IssueSeverity.ERROR,
                data={
                    "interface_id": event.failure_interface_id,
                },
            )
        elif event.failure_reason == FailureReason.NETWORK:
            async_create_issue(
                hass,
                domain=DOMAIN,
                issue_id="network_error",
                translation_key="network_error",
                severity=IssueSeverity.ERROR,
            )
        elif event.failure_reason == FailureReason.INTERNAL:
            async_create_issue(
                hass,
                domain=DOMAIN,
                issue_id="backend_error",
                translation_key="backend_error",
                severity=IssueSeverity.WARNING,
            )
        else:
            # Fallback for UNKNOWN or other reasons
            async_create_issue(
                hass,
                domain=DOMAIN,
                issue_id="connection_failed",
                translation_key="connection_failed",
                severity=IssueSeverity.ERROR,
            )
```

### Step 2: Add Translation Keys

Add new translation keys to `strings.json`:

```json
{
  "issues": {
    "authentication_failed": {
      "title": "Authentication Failed",
      "description": "Could not authenticate with the CCU. Please check your username and password in the integration configuration."
    },
    "network_error": {
      "title": "Network Connection Error",
      "description": "Could not connect to the CCU. Please check that the CCU is powered on and reachable on the network."
    },
    "backend_error": {
      "title": "CCU Internal Error",
      "description": "The CCU reported an internal error. Please try restarting the CCU."
    }
  }
}
```

### Step 3: Query Failure Reason Programmatically

You can also query the failure reason directly from the state machine:

```python
# Check current failure reason
if central.state_machine.is_failed:
    reason = central.state_machine.failure_reason
    message = central.state_machine.failure_message
    interface = central.state_machine.failure_interface_id

    _LOGGER.error(
        "Central failed with reason=%s, message=%s, interface=%s",
        reason.value,
        message,
        interface,
    )
```

## Compatibility Notes

- This is an **additive change** - existing code will continue to work
- The new `failure_reason` parameter has a default value of `FailureReason.NONE`
- If you don't pass `failure_reason`, the behavior is unchanged
- The `failure_reason` and `failure_interface_id` fields on `SystemStatusEvent` are `None` when not in FAILED state

## Failure Reason Propagation Path

The failure reason is propagated through the system as follows:

1. **Exception occurs** during client operation (e.g., login failure, network error)
2. **Client state machine** captures the failure reason via `exception_to_failure_reason()`
3. **ClientCoordinator** tracks the last failure reason and interface_id
4. **Central state machine** receives the failure info when transitioning to FAILED
5. **SystemStatusEvent** is published with `failure_reason` and `failure_interface_id`
6. **Integration** receives the event and can display appropriate error messages

### New Protocol: ClientStateMachineProtocol

A new protocol is available for accessing client state machine properties:

```python
from aiohomematic.interfaces.client import ClientStateMachineProtocol

# Access via client
client.state_machine.is_failed         # bool
client.state_machine.failure_reason    # FailureReason
client.state_machine.failure_message   # str
```

### ClientCoordinator Changes

The `ClientCoordinator` now tracks the last failure from client creation:

```python
# Access failure info from ClientCoordinator
coordinator.last_failure_reason        # FailureReason
coordinator.last_failure_interface_id  # str | None
```

## Testing

Run the new tests to verify the implementation:

```bash
pytest tests/test_failure_reason.py -v
```

## See Also

- [Event Reference](../event_reference.md) - Full event documentation
- [Common Operations](../common_operations.md) - Error handling examples
