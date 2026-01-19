# ADR 0017: Defensive Client Initialization with Staged Validation

**Status:** ✅ Implemented (v2026.1.41)
**Date:** 2026-01-19
**Decision Makers:** Architecture Team

---

## Context

### Problem

When Home Assistant starts before OpenCCU/CCU in containerized environments, `homematicip_local` integration incorrectly requests re-authentication instead of retrying the connection. This forces manual intervention and breaks automated workflows.

**Error Sequence:**

1. Home Assistant starts → aiohomematic attempts client creation
2. OpenCCU's auth service not yet ready → XML-RPC `system.listMethods()` returns "Unauthorized"
3. Error classified as `AuthFailure` → `FailureReason.AUTH`
4. Home Assistant integration triggers re-authentication flow

**Root Cause:**

Error classification does not distinguish between **timing issues** (service still initializing) and **true authentication failures** (wrong credentials).

| Scenario                         | Current Behavior      | Expected Behavior     |
| -------------------------------- | --------------------- | --------------------- |
| **Timing** (service not ready)   | → Re-authentication   | → Retry with backoff  |
| **Auth Error** (bad credentials) | → Re-authentication ✓ | → Re-authentication ✓ |

---

## Decision

**Implement defensive client initialization with 3-stage validation** inspired by the proven approach in `ConnectionRecoveryCoordinator`.

### Strategy

Combine two complementary approaches:

1. **TCP Pre-Flight Check**: Wait for port availability before attempting RPC calls
2. **Retry with Exponential Backoff**: Retry `AuthFailure` during startup with increasing delays

### Key Principles

- **Reuse Proven Patterns**: Mirror staged validation from `ConnectionRecoveryCoordinator`
- **Defensive Validation**: Never attempt RPC until TCP connectivity confirmed
- **Fail Fast on Network Errors**: Connection refused → immediate failure
- **Fail Slow on Auth Errors**: Auth errors during startup → retry with backoff
- **Fully Configurable**: All timeouts use `TimeoutConfig`

---

## Architecture

### Staged Validation Flow

```
┌─────────────────────────────────────────────────────────────┐
│           ClientCoordinator._create_client()                 │
│                                                              │
│  FOR attempt IN 1..startup_max_init_attempts:               │
│    ┌────────────────────────────────────────────────────┐   │
│    │ Stage 1: TCP Check (defensive pre-flight)         │   │
│    │  - Wait for TCP port to become available          │   │
│    │  - Max wait: reconnect_tcp_check_timeout (60s)    │   │
│    │  - Check interval: reconnect_tcp_check_interval   │   │
│    └────────────────────────────────────────────────────┘   │
│                           ↓                                  │
│    ┌────────────────────────────────────────────────────┐   │
│    │ Stage 2: Client Creation & RPC Validation         │   │
│    │  - Call create_client_instance()                   │   │
│    │  - Perform initial RPC handshake                   │   │
│    └────────────────────────────────────────────────────┘   │
│                           ↓                                  │
│    ┌────────────────────────────────────────────────────┐   │
│    │ Stage 3: Error Classification & Retry Decision    │   │
│    │  - AuthFailure → Retry with exponential backoff   │   │
│    │  - Other errors → Fail immediately                 │   │
│    └────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Configuration Parameters

#### New TimeoutConfig Parameters

```python
class TimeoutConfig(NamedTuple):
    # New parameters for startup resilience
    startup_max_init_attempts: int = 5          # Max retry attempts
    startup_init_retry_delay: float = 3         # Initial delay (seconds)
    startup_max_init_retry_delay: float = 30    # Max delay after backoff

    # Reused from existing recovery coordinator
    reconnect_tcp_check_timeout: float = 60     # TCP wait timeout
    reconnect_tcp_check_interval: float = 5     # TCP check interval
    reconnect_backoff_factor: float = 2         # Backoff multiplier
```

**Rationale for Reuse:**

- Reduces configuration complexity (3 new parameters instead of 6)
- Ensures consistency between startup and recovery behaviors
- Simplifies user configuration

### Implementation Components

1. **`_wait_for_tcp_ready()`** - TCP availability check with timeout
2. **`_calculate_startup_retry_delay()`** - Exponential backoff calculation
3. **Enhanced `_create_client()`** - Retry loop with staged validation

### Translation Keys

Added 6 new keys under `log.central.startup.*`:

- `tcp_ready`, `tcp_check_failed`, `tcp_timeout`, `tcp_not_ready`
- `auth_retry`, `auth_failed`

---

## Consequences

### Positive

✅ **Solves Docker Startup Race Condition**: False re-authentication requests eliminated
✅ **Automatic Recovery**: No manual intervention required for timing issues
✅ **Maintains Security**: True auth errors still trigger re-authentication after retries
✅ **Reuses Proven Patterns**: Leverages battle-tested recovery coordinator approach
✅ **Backward Compatible**: No breaking changes to public API
✅ **Configurable**: Users can tune timeouts for their environment

### Negative

⚠️ **Delayed Startup**: Adds up to ~60s for TCP check + ~45s for retries (worst case)
⚠️ **Complexity**: Additional state management in startup path
⚠️ **Test Coverage**: Requires comprehensive integration testing

### Neutral

ℹ️ **No Changes to Recovery**: Existing `ConnectionRecoveryCoordinator` unchanged
ℹ️ **Parameter Reuse**: Shares timeout config with recovery coordinator

---

## Comparison: Startup vs Recovery

| Aspect               | Startup (This ADR)                      | Recovery (Existing)                |
| -------------------- | --------------------------------------- | ---------------------------------- |
| **Trigger**          | Initial client creation                 | Connection lost event              |
| **Context**          | Cold start, no previous connection      | Established connection lost        |
| **TCP Check**        | ✅ Immediate, timeout 60s               | ✅ With cooldown 30s + timeout 60s |
| **RPC Check**        | ✅ Implicit in client creation          | ✅ Explicit system.listMethods     |
| **Warmup Delay**     | ❌ Not needed (no established clients)  | ✅ 15s after first RPC success     |
| **Stability Check**  | ❌ Not needed (state machine validates) | ✅ Second RPC check post-warmup    |
| **Max Attempts**     | 5 (`startup_max_init_attempts`)         | 8 (`MAX_RECOVERY_ATTEMPTS`)        |
| **Retry Delay**      | 3s → 30s exponential                    | 2s → 120s exponential              |
| **Auth Error Retry** | ✅ YES (up to 5 attempts)               | ❌ NO (fails immediately)          |

**Key Difference**: Startup retries auth errors (assuming timing issue), recovery does not (assumes credentials changed).

---

## Alternatives Considered

### Alternative 1: Increase RPC Timeout Only

**Rejected** - Doesn't solve race condition, delays failure detection.

### Alternative 2: Ping Backend Before First Attempt

**Rejected** - TCP check is more reliable and reuses existing infrastructure.

### Alternative 3: Classify "Unauthorized" During listMethods Specially

**Rejected** - Too fragile, doesn't handle other transient errors.

### Alternative 4: Separate Timeout Parameters for Startup

**Rejected** - Unnecessary complexity, reusing recovery parameters is cleaner.

---

## Migration Guide

### For aiohomematic Users

**No action required.** Retry logic uses sensible defaults.

**Optional customization:**

```python
from aiohomematic.const import TimeoutConfig
from aiohomematic.central import CentralConfig

async def start_central():
    config = CentralConfig.for_ccu(
        host="192.168.1.100",
        username="admin",
        password="secret",
        timeout_config=TimeoutConfig(
            reconnect_tcp_check_timeout=120,  # Allow 2min for TCP
            startup_max_init_attempts=5,      # Up to 5 retries
        ),
    )
    central = await config.create_central()
    await central.start()
```

### For Home Assistant Integration (homematicip_local)

**No changes needed.** The retry logic prevents `FailureReason.AUTH` from being set during transient startup issues. True auth errors still propagate correctly after retries are exhausted.

---

## Testing Strategy

### Unit Tests

- TCP check success/timeout/retry scenarios
- Exponential backoff calculation
- Auth error retry with exhaustion

### Integration Tests

- Docker Compose with staggered container startup
- OpenCCU/CCU hardware restart scenarios
- Network partition simulation

### Performance Tests

- Measure worst-case startup delay (~105s max)
- Verify no regression in normal startup path

---

## Implementation

**Status:** ✅ **Implemented** in version **2026.1.41** (2026-01-19)

**Changed Files:**

- `aiohomematic/const.py` - Added 3 new TimeoutConfig parameters
- `aiohomematic/central/coordinators/client.py` - Staged validation logic
- `aiohomematic/strings.json` + `translations/de.json` - 6 new translation keys
- `tests/test_central_client_coordinator.py` - `TestStartupResilience` test class

**Verification:**

- ✅ All unit tests pass
- ✅ mypy strict type checking passes
- ✅ ruff linting passes

---

## References

- **Issue:** [#2830](https://github.com/SukramJ/aiohomematic/issues/2830) - homematicip_local enters re-authentication when OpenCCU is still starting
- **Related Patterns:**
  - `ConnectionRecoveryCoordinator` - Staged recovery with TCP → RPC → Warmup → Stability
- **Related Code:**
  - `aiohomematic/central/coordinators/client.py`
  - `aiohomematic/central/coordinators/connection_recovery.py`
  - `aiohomematic/client/_rpc_errors.py`
  - `aiohomematic/const.py`
