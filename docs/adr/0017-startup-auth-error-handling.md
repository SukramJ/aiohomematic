# ADR 0017: Defensive Client Initialization with Staged Validation

---

## Context

### Problem Statement

When Home Assistant starts before OpenCCU/CCU has fully initialized in containerized environments, the `homematicip_local` integration incorrectly requests re-authentication instead of retrying the connection. This regression (introduced in v2.1.2) causes:

- Manual intervention required (click "Repair" and resubmit credentials)
- No Homematic IP entities available until manual fix
- Breaks automated backup/restart workflows

### Root Cause Analysis

**Error Sequence:**

```
1. Home Assistant starts → aiohomematic attempts client creation
2. OpenCCU's auth service not yet ready
3. XML-RPC call to system.listMethods() fails with "ProtocolError: Unauthorized"
4. Error classified as AuthFailure → FailureReason.AUTH
5. CentralStateMachine transitions to FAILED with failure_reason=AUTH
6. Home Assistant integration detects AUTH failure → triggers re-authentication flow
```

**Core Issue:**

The error classification in `_rpc_errors.py:143` does not distinguish between:

| Scenario                                | Current Behavior                             | Expected Behavior    |
| --------------------------------------- | -------------------------------------------- | -------------------- |
| **Timing Issue** (service not ready)    | → AuthFailure → FailureReason.AUTH → Re-auth | → Retry with backoff |
| **True Auth Error** (wrong credentials) | → AuthFailure → FailureReason.AUTH → Re-auth | → Re-auth ✓          |

**Evidence from Incident Store:**

```json
{
  "error_type": "ProtocolError",
  "error_message": "Unauthorized",
  "method": "system.listMethods",
  "tls_enabled": true
}
```

The "Unauthorized" error during `system.listMethods` is interpreted as authentication failure, but in reality indicates the auth service is still initializing.

---

## Decision

Implement **defensive client initialization** that mirrors the staged validation approach already proven in the `ConnectionRecoveryCoordinator`. This combines:

1. **Option 1:** Retry logic during initialization with exponential backoff
2. **Option 2:** TCP healthcheck before attempting RPC operations

### Design Principles

1. **Reuse Proven Patterns:** Leverage the battle-tested staged recovery approach from `ConnectionRecoveryCoordinator`
2. **Defensive Validation:** Never attempt RPC calls until TCP connectivity is confirmed
3. **Fail Fast on True Errors:** Network errors (connection refused) should fail immediately after retries
4. **Fail Slow on Auth Errors:** Auth errors during startup should retry, only triggering re-auth after exhaustion
5. **Fully Configurable:** All timeouts use `TimeoutConfig` to allow user customization

---

## Detailed Design

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│               ClientCoordinator._create_client()             │
│                                                              │
│  FOR attempt IN 1..startup_max_init_attempts:               │
│    ┌────────────────────────────────────────────────────┐   │
│    │ Stage 1: TCP Check (defensive pre-flight)         │   │
│    │  - Wait for TCP port to become available          │   │
│    │  - Max wait: reconnect_tcp_check_timeout          │   │
│    │  - Check interval: reconnect_tcp_check_interval   │   │
│    └────────────────────────────────────────────────────┘   │
│                           ↓                                  │
│    ┌────────────────────────────────────────────────────┐   │
│    │ Stage 2: Client Creation & RPC Validation         │   │
│    │  - Call _client_factory.create_client_instance()  │   │
│    │  - Attempt system.listMethods() / isPresent()     │   │
│    │  - Classify exception type                         │   │
│    └────────────────────────────────────────────────────┘   │
│                           ↓                                  │
│    ┌────────────────────────────────────────────────────┐   │
│    │ Stage 3: Error Classification & Retry Decision    │   │
│    │                                                    │   │
│    │  AuthFailure during startup?                       │   │
│    │    ├─ YES → Log warning, retry with backoff       │   │
│    │    └─ NO  → Classify & propagate                  │   │
│    │                                                    │   │
│    │  NoConnectionException?                            │   │
│    │    ├─ TCP was OK → Backend crashed during init   │   │
│    │    └─ TCP failed → Network issue                  │   │
│    │                                                    │   │
│    │  Retry? Exponential backoff:                       │   │
│    │    delay = startup_init_retry_delay * (2^attempt) │   │
│    │    capped at startup_max_init_retry_delay         │   │
│    └────────────────────────────────────────────────────┘   │
│                           ↓                                  │
│  END FOR                                                     │
│                                                              │
│  All retries exhausted?                                      │
│    → Classify failure reason                                 │
│    → Propagate to CentralStateMachine                        │
└─────────────────────────────────────────────────────────────┘
```

### Staged Validation Details

#### Stage 1: TCP Pre-Flight Check

**Purpose:** Verify backend TCP connectivity before attempting RPC operations.

**Implementation:**

```python
async def _wait_for_tcp_ready(
    self,
    *,
    host: str,
    port: int,
    max_wait_seconds: float,
    check_interval: float,
) -> bool:
    """
    Wait for TCP port to become available.

    Args:
        host: Target host
        port: Target port
        timeout: Maximum time to wait (from reconnect_tcp_check_timeout)
        check_interval: Time between checks (from reconnect_tcp_check_interval)

    Returns:
        True if TCP port became available within timeout, False otherwise.
    """
    start_time = time.perf_counter()
    attempt = 0

    while (time.perf_counter() - start_time) < timeout:
        attempt += 1
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=2.0,
            )
            writer.close()
            await writer.wait_closed()

            _LOGGER.debug(
                "TCP_CHECK: Port %s:%d available after attempt %d (%.1fs)",
                host,
                port,
                attempt,
                time.perf_counter() - start_time,
            )
            return True

        except (TimeoutError, OSError) as exc:
            if attempt == 1:
                _LOGGER.info(
                    i18n.tr(
                        key="log.central.create_client.tcp_wait_started",
                        host=host,
                        port=port,
                        timeout=timeout,
                    )
                )

            # Check if we should continue waiting
            remaining = timeout - (time.perf_counter() - start_time)
            if remaining <= 0:
                break

            await asyncio.sleep(min(check_interval, remaining))

    _LOGGER.warning(
        i18n.tr(
            key="log.central.create_client.tcp_wait_timeout",
            host=host,
            port=port,
            timeout=timeout,
        )
    )
    return False
```

**Key Features:**

- Non-invasive: Opens and immediately closes TCP connection
- Progressive logging: Info on first attempt, debug on success
- Respects timeout: Won't wait longer than configured
- Efficient: Sleeps between checks instead of busy-waiting

#### Stage 2: RPC Validation with Retry Logic

**Purpose:** Attempt client creation with retries for transient errors during startup.

**Implementation:**

```python
async def _create_client(self, *, interface_config: InterfaceConfig) -> bool:
    """
    Create and register a single client with defensive retry logic.

    During startup, auth errors may indicate the backend is still initializing
    rather than incorrect credentials. This method retries such errors with
    exponential backoff before classifying them as true authentication failures.

    Returns:
        True if client was created successfully, False otherwise.
    """
    max_attempts = self._config_provider.config.timeout_config.startup_max_init_attempts

    for attempt in range(1, max_attempts + 1):
        try:
            # Stage 1: TCP Pre-Flight Check
            if attempt == 1:
                tcp_ready = await self._wait_for_tcp_ready(
                    host=self._config_provider.config.host,
                    port=interface_config.port,
                    timeout=self._config_provider.config.timeout_config.reconnect_tcp_check_timeout,
                    check_interval=self._config_provider.config.timeout_config.reconnect_tcp_check_interval,
                )

                if not tcp_ready:
                    # TCP never became available - fail fast with network error
                    self._last_failure_reason = FailureReason.NETWORK
                    self._last_failure_interface_id = interface_config.interface_id
                    _LOGGER.error(
                        i18n.tr(
                            key="log.central.create_client.tcp_unavailable",
                            interface_id=interface_config.interface_id,
                        )
                    )
                    return False

            # Stage 2: Create client and attempt RPC validation
            _LOGGER.debug(
                "CREATE_CLIENT: Attempt %d/%d for %s",
                attempt,
                max_attempts,
                interface_config.interface_id,
            )

            client = self._client_factory.create_client_instance(
                interface_config=interface_config
            )

            # Register client (includes system.listMethods call)
            self._clients[interface_config.interface_id] = client

            # Register with health tracker
            await self._health_tracker.register_client(client=client)

            _LOGGER.debug(
                "CREATE_CLIENT: Registered client %s with health tracker",
                client.interface_id,
            )

            return True

        except AuthFailure as auth_exc:
            # Stage 3: Auth error during startup - retry with backoff
            if attempt < max_attempts:
                retry_delay = self._calculate_startup_retry_delay(attempt=attempt)

                _LOGGER.warning(
                    i18n.tr(
                        key="log.central.create_client.auth_retry",
                        interface_id=interface_config.interface_id,
                        attempt=attempt,
                        max_attempts=max_attempts,
                        delay=retry_delay,
                        reason=str(auth_exc),
                    )
                )

                await asyncio.sleep(retry_delay)
                continue

            # Last attempt exhausted - this is likely a true auth error
            self._last_failure_reason = FailureReason.AUTH
            self._last_failure_interface_id = interface_config.interface_id
            _LOGGER.error(
                i18n.tr(
                    key="log.central.create_client.auth_failed",
                    interface_id=interface_config.interface_id,
                    attempts=max_attempts,
                    reason=extract_exc_args(exc=auth_exc),
                )
            )

        except NoConnectionException as conn_exc:
            # Network error after TCP check passed - backend crashed during init?
            if attempt < max_attempts:
                retry_delay = self._calculate_startup_retry_delay(attempt=attempt)

                _LOGGER.warning(
                    i18n.tr(
                        key="log.central.create_client.connection_retry",
                        interface_id=interface_config.interface_id,
                        attempt=attempt,
                        max_attempts=max_attempts,
                        delay=retry_delay,
                    )
                )

                await asyncio.sleep(retry_delay)
                continue

            # Network error persists
            self._last_failure_reason = FailureReason.NETWORK
            self._last_failure_interface_id = interface_config.interface_id
            _LOGGER.error(
                i18n.tr(
                    key="log.central.create_client.no_connection",
                    interface_id=interface_config.interface_id,
                    reason=extract_exc_args(exc=conn_exc),
                )
            )

        except BaseHomematicException as bhexc:
            # Other errors (internal, circuit breaker, etc.) - don't retry
            self._last_failure_reason = exception_to_failure_reason(exc=bhexc)
            self._last_failure_interface_id = interface_config.interface_id
            _LOGGER.error(
                i18n.tr(
                    key="log.central.create_client.failed",
                    interface_id=interface_config.interface_id,
                    reason=extract_exc_args(exc=bhexc),
                )
            )

    return False

def _calculate_startup_retry_delay(self, *, attempt: int) -> float:
    """
    Calculate retry delay using exponential backoff.

    Args:
        attempt: Current attempt number (1-indexed)

    Returns:
        Delay in seconds before next retry.
    """
    config = self._config_provider.config.timeout_config

    # Exponential backoff: base_delay * (backoff_factor ^ (attempt - 1))
    delay = config.startup_init_retry_delay * (
        config.reconnect_backoff_factor ** (attempt - 1)
    )

    # Cap at maximum
    return min(delay, config.startup_max_init_retry_delay)
```

#### Stage 3: Error Classification & State Propagation

**Failure Reason Mapping:**

| Exception Type                | During Startup       | After Startup      | Failure Reason                  | Re-Auth?            |
| ----------------------------- | -------------------- | ------------------ | ------------------------------- | ------------------- |
| `AuthFailure`                 | Retry → Then AUTH    | AUTH               | `FailureReason.AUTH`            | Yes (after retries) |
| `NoConnectionException`       | Retry → Then NETWORK | NETWORK            | `FailureReason.NETWORK`         | No                  |
| `InternalBackendException`    | No retry             | No retry           | `FailureReason.INTERNAL`        | No                  |
| `CircuitBreakerOpenException` | No retry             | Automatic recovery | `FailureReason.CIRCUIT_BREAKER` | No                  |
| `TimeoutError`                | Retry → Then TIMEOUT | TIMEOUT            | `FailureReason.TIMEOUT`         | No                  |

### Configuration Parameters

#### Reused TimeoutConfig Fields

**No new TCP-related parameters needed.** Startup reuses existing recovery parameters:

| Parameter                      | Default | Usage Context                                       |
| ------------------------------ | ------- | --------------------------------------------------- |
| `reconnect_tcp_check_timeout`  | 60s     | TCP availability timeout (startup & recovery)       |
| `reconnect_tcp_check_interval` | 5s      | Interval between TCP checks (startup & recovery)    |
| `reconnect_backoff_factor`     | 2       | Exponential backoff multiplier (startup & recovery) |

**Rationale:** Startup and recovery both need TCP checks with identical behavior. Reusing parameters:

- ✅ Reduces configuration complexity (3 fewer parameters)
- ✅ Ensures consistent TCP check behavior
- ✅ Simplifies user configuration (set TCP parameters once)

#### New TimeoutConfig Fields

Add **only 3 new parameters** to `aiohomematic/const.py:TimeoutConfig`:

```python
class TimeoutConfig(NamedTuple):
    """Configuration for various timeout and interval settings."""

    # ... existing fields (including reconnect_tcp_check_timeout, reconnect_tcp_check_interval, reconnect_backoff_factor) ...

    # ========================================
    # Startup / Initial Connection Parameters
    # ========================================

    startup_max_init_attempts: int = 5
    """
    Maximum number of initialization attempts during client creation (default: 5).

    If client creation fails with retryable errors (AuthFailure, NoConnectionException),
    this controls how many times we retry before giving up and propagating the error
    to the state machine.

    Total max time for initialization:
    - TCP wait: ~60s (reconnect_tcp_check_timeout)
    - RPC retries: 5 attempts * ~10s avg = ~50s
    - Total: ~110s max
    """

    startup_init_retry_delay: float = 0.5 if _TEST_SPEEDUP else 3
    """
    Base delay between initialization retry attempts (default: 3s).

    Uses exponential backoff with reconnect_backoff_factor (default: 2):
    - Attempt 1→2: 3s
    - Attempt 2→3: 6s
    - Attempt 3→4: 12s
    - Attempt 4→5: 24s
    - Capped at startup_max_init_retry_delay
    """

    startup_max_init_retry_delay: float = 2 if _TEST_SPEEDUP else 30
    """
    Maximum delay between initialization retry attempts (default: 30s).

    Caps the exponential backoff to prevent excessively long waits.
    Note: This is shorter than reconnect_max_delay (120s) because startup
    should fail faster than recovery attempts.
    """
```

#### Configuration Recommendations

**For Docker Environments (Recommended):**

```python
timeout_config = TimeoutConfig(
    reconnect_tcp_check_timeout=90,      # Allow 90s for TCP availability (reused)
    reconnect_tcp_check_interval=5,      # Check every 5s (reused)
    startup_max_init_attempts=5,         # Retry up to 5 times
    startup_init_retry_delay=5,          # Start with 5s delay
    startup_max_init_retry_delay=45,     # Cap at 45s
)
```

**For Fast Networks (Production):**

```python
timeout_config = TimeoutConfig(
    reconnect_tcp_check_timeout=30,      # Backend should start quickly (reused)
    reconnect_tcp_check_interval=2,      # Check every 2s (reused)
    startup_max_init_attempts=3,         # Only 3 attempts
    startup_init_retry_delay=2,          # Quick retries
    startup_max_init_retry_delay=15,     # Cap at 15s
)
```

**For Development/Testing:**

```python
# Already handled by _TEST_SPEEDUP in default values
timeout_config = TimeoutConfig()  # Uses fast defaults when testing
```

### Translation Keys

Add to `aiohomematic/strings.json`:

```json
{
  "log.central.create_client.tcp_wait_started": "CREATE_CLIENT: Waiting for TCP port {host}:{port} (timeout: {timeout}s)",
  "log.central.create_client.tcp_wait_timeout": "CREATE_CLIENT: TCP port {host}:{port} did not become available within {timeout}s",
  "log.central.create_client.tcp_unavailable": "CREATE_CLIENT failed: TCP port unavailable for {interface_id}",
  "log.central.create_client.auth_retry": "CREATE_CLIENT: Auth error for {interface_id} (attempt {attempt}/{max_attempts}), retrying in {delay}s: {reason}",
  "log.central.create_client.auth_failed": "CREATE_CLIENT failed: Authentication error for {interface_id} after {attempts} attempts: {reason}",
  "log.central.create_client.connection_retry": "CREATE_CLIENT: Connection error for {interface_id} (attempt {attempt}/{max_attempts}), retrying in {delay}s",
  "log.central.create_client.failed": "CREATE_CLIENT failed: {interface_id} - {reason}"
}
```

---

## Relationship to ConnectionRecoveryCoordinator

### Comparison Matrix

| Feature              | ConnectionRecoveryCoordinator                   | Proposed: ClientCoordinator Startup     |
| -------------------- | ----------------------------------------------- | --------------------------------------- |
| **Trigger**          | ConnectionLostEvent, CircuitBreakerTrippedEvent | Initial client creation                 |
| **Context**          | Existing connection lost                        | Cold start, no previous connection      |
| **TCP Check**        | ✅ With cooldown (30s) + timeout (60s)          | ✅ Immediate, timeout (60s)             |
| **RPC Check**        | ✅ system.listMethods with warmup               | ✅ Implicit in client creation          |
| **Warmup Delay**     | ✅ 15s after first RPC success                  | ❌ Not needed (no established clients)  |
| **Stability Check**  | ✅ Second RPC check post-warmup                 | ❌ Not needed (state machine validates) |
| **Max Attempts**     | 8 (MAX_RECOVERY_ATTEMPTS)                       | 5 (startup_max_init_attempts)           |
| **Backoff**          | 5s → 60s (BASE → MAX_RETRY_DELAY)               | 3s → 30s (startup → max init)           |
| **State Transition** | RECOVERING → RUNNING/DEGRADED/FAILED            | INITIALIZING → RUNNING/FAILED           |
| **Auth Error Retry** | ❌ No (circuit breaker trips)                   | ✅ Yes (may be transient)               |

### Why Fewer Stages for Startup?

**ConnectionRecoveryCoordinator** assumes:

- There WAS a working connection
- Other interfaces may still be operational
- Backend may have partially crashed
- Need to ensure stability before declaring recovery

**Initial Startup** assumes:

- No previous connection state
- Nothing is operational yet
- Backend is starting from scratch
- State machine will validate after creation

**Therefore:** We skip warmup/stability checks during startup, but keep defensive TCP validation.

---

## Testing Strategy

### Unit Tests

**Test File:** `tests/test_central_client_coordinator_startup.py`

```python
"""Test startup retry logic in ClientCoordinator."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from aiohomematic.central.coordinators.client import ClientCoordinator
from aiohomematic.const import FailureReason, TimeoutConfig
from aiohomematic.exceptions import AuthFailure, NoConnectionException


class TestClientCoordinatorStartup:
    """Test defensive client initialization with retries."""

    @pytest.mark.asyncio
    async def test_create_client_success_first_attempt(
        self,
        client_coordinator: ClientCoordinator,
        interface_config: InterfaceConfig,
    ) -> None:
        """Test successful client creation on first attempt."""
        success = await client_coordinator._create_client(
            interface_config=interface_config
        )

        assert success is True
        assert interface_config.interface_id in client_coordinator._clients
        assert client_coordinator._last_failure_reason == FailureReason.NONE

    @pytest.mark.asyncio
    async def test_create_client_tcp_wait_timeout(
        self,
        client_coordinator: ClientCoordinator,
        interface_config: InterfaceConfig,
    ) -> None:
        """Test client creation fails when TCP port never becomes available."""
        # Mock TCP check to always fail
        with patch.object(
            client_coordinator,
            "_wait_for_tcp_ready",
            return_value=False,
        ):
            success = await client_coordinator._create_client(
                interface_config=interface_config
            )

        assert success is False
        assert interface_config.interface_id not in client_coordinator._clients
        assert client_coordinator._last_failure_reason == FailureReason.NETWORK

    @pytest.mark.asyncio
    async def test_create_client_auth_error_retries_then_succeeds(
        self,
        client_coordinator: ClientCoordinator,
        interface_config: InterfaceConfig,
    ) -> None:
        """Test auth error during startup retries and eventually succeeds."""
        attempts = 0

        def mock_create_client_instance(*args, **kwargs):
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise AuthFailure("Backend still starting")
            return Mock()  # Success on 3rd attempt

        with patch.object(
            client_coordinator._client_factory,
            "create_client_instance",
            side_effect=mock_create_client_instance,
        ):
            # Use faster timeouts for testing
            with patch.object(
                client_coordinator._config_provider.config,
                "timeout_config",
                TimeoutConfig(
                    reconnect_tcp_check_timeout=1,         # Reused parameter
                    reconnect_tcp_check_interval=0.1,      # Reused parameter
                    startup_max_init_attempts=5,
                    startup_init_retry_delay=0.1,
                    startup_max_init_retry_delay=0.5,
                ),
            ):
                success = await client_coordinator._create_client(
                    interface_config=interface_config
                )

        assert success is True
        assert attempts == 3
        assert client_coordinator._last_failure_reason == FailureReason.NONE

    @pytest.mark.asyncio
    async def test_create_client_auth_error_exhausts_retries(
        self,
        client_coordinator: ClientCoordinator,
        interface_config: InterfaceConfig,
    ) -> None:
        """Test auth error persists through all retries."""
        with patch.object(
            client_coordinator._client_factory,
            "create_client_instance",
            side_effect=AuthFailure("Invalid credentials"),
        ):
            with patch.object(
                client_coordinator._config_provider.config,
                "timeout_config",
                TimeoutConfig(
                    reconnect_tcp_check_timeout=1,         # Reused parameter
                    startup_max_init_attempts=3,
                    startup_init_retry_delay=0.1,
                ),
            ):
                success = await client_coordinator._create_client(
                    interface_config=interface_config
                )

        assert success is False
        assert client_coordinator._last_failure_reason == FailureReason.AUTH

    @pytest.mark.asyncio
    async def test_create_client_exponential_backoff(
        self,
        client_coordinator: ClientCoordinator,
        interface_config: InterfaceConfig,
    ) -> None:
        """Test exponential backoff between retry attempts."""
        delays = []

        async def mock_sleep(delay: float) -> None:
            delays.append(delay)

        with patch("asyncio.sleep", side_effect=mock_sleep):
            with patch.object(
                client_coordinator._client_factory,
                "create_client_instance",
                side_effect=AuthFailure("Backend starting"),
            ):
                with patch.object(
                    client_coordinator._config_provider.config,
                    "timeout_config",
                    TimeoutConfig(
                        reconnect_tcp_check_timeout=1,         # Reused parameter
                        startup_max_init_attempts=4,
                        startup_init_retry_delay=2,
                        startup_max_init_retry_delay=10,
                        reconnect_backoff_factor=2,            # Reused parameter
                    ),
                ):
                    await client_coordinator._create_client(
                        interface_config=interface_config
                    )

        # Expected: 2s, 4s, 8s (16s would be capped at 10s → 10s)
        assert delays == [2.0, 4.0, 8.0]
```

### Integration Tests

**Scenario 1: Docker Startup Race (OpenCCU starts after HA)**

```python
@pytest.mark.integration
async def test_docker_startup_race_condition(mock_openccu_delayed: MockOpenCCU) -> None:
    """
    Simulate Docker startup where OpenCCU starts 45 seconds after Home Assistant.

    Expected: Client creation waits for TCP, retries auth errors, succeeds.
    """
    # Start with OpenCCU offline
    mock_openccu_delayed.stop()

    config = CentralConfig.for_ccu(
        host="localhost",
        username="admin",
        password="secret",
        timeout_config=TimeoutConfig(
            reconnect_tcp_check_timeout=90,          # Reused: Allow 90s for TCP availability
            startup_max_init_attempts=5,
            startup_init_retry_delay=5,
        ),
    )

    central = await config.create_central()

    # Start OpenCCU after 45 seconds
    asyncio.create_task(delayed_start(mock_openccu_delayed, delay=45))

    # This should succeed without requiring re-auth
    start_time = time.perf_counter()
    await central.start()
    duration = time.perf_counter() - start_time

    assert central.is_connected
    assert central.state_machine.state == CentralState.RUNNING
    assert duration < 90  # Completed within TCP ready timeout
    assert duration > 45  # Waited for OpenCCU to start
```

**Scenario 2: True Authentication Error**

```python
@pytest.mark.integration
async def test_true_auth_error_triggers_reauth(mock_ccu: MockCCU) -> None:
    """
    Simulate true authentication error (wrong password).

    Expected: Retries exhaust, failure_reason=AUTH, triggers re-auth in HA.
    """
    config = CentralConfig.for_ccu(
        host="localhost",
        username="admin",
        password="wrong_password",  # Incorrect password
        timeout_config=TimeoutConfig(
            reconnect_tcp_check_timeout=10,          # Reused: 10s TCP wait
            startup_max_init_attempts=3,
        ),
    )

    central = await config.create_central()

    with pytest.raises(AioHomematicException):
        await central.start()

    assert central.state_machine.state == CentralState.FAILED
    assert central.state_machine.failure_reason == FailureReason.AUTH
```

---

## Consequences

### Positive

1. **Fixes Docker Startup Race:** No more false re-authentication requests
2. **Reuses Proven Patterns:** TCP check mirrored from ConnectionRecoveryCoordinator
3. **Fully Configurable:** Users can tune timeouts for their environment
4. **Maintains Fast Fail:** True network errors still fail quickly
5. **Clear Logging:** Progressive logging shows what's happening during startup
6. **No Breaking Changes:** Existing configurations work with sensible defaults

### Negative

1. **Longer Startup Time:** May take up to ~135s in worst-case Docker scenario (configurable)
2. **More Complex Logic:** ClientCoordinator initialization becomes more sophisticated
3. **More Tests Required:** Need thorough testing of retry paths
4. **Potential for Confusion:** Users might not understand why startup is "slow"

### Mitigation

- **Default Timeout Balance:** 60s TCP + 5 retries \* ~10s avg = ~110s max (acceptable for startup)
- **Progressive Logging:** Clear log messages explain what's happening
- **Documentation:** ADR + migration guide explain the behavior
- **Telemetry:** Metrics track startup duration for monitoring

---

## Migration Guide

### For aiohomematic Users

**No action required.** The new retry logic is transparent and uses sensible defaults.

**Optional:** Customize timeouts in your configuration:

```python
from aiohomematic.const import TimeoutConfig
from aiohomematic.central import CentralConfig

async def start_central():
    config = CentralConfig.for_ccu(
        host="192.168.1.100",
        username="admin",
        password="secret",
        timeout_config=TimeoutConfig(
            reconnect_tcp_check_timeout=120,  # Allow 2 min for TCP (reused)
            startup_max_init_attempts=5,      # Up to 5 retries
        ),
    )

    central = await config.create_central()
    await central.start()
```

### For Home Assistant Integration (homematicip_local)

**Current behavior:**

```python
if central.state_machine.failure_reason == FailureReason.AUTH:
    _LOGGER.warning("Central %s FAILED due to authentication error. Triggering reauthentication flow")
    entry.async_start_reauth(hass)
```

**No change needed.** The retry logic now prevents `FailureReason.AUTH` from being set during transient startup issues. True auth errors still propagate correctly after retries are exhausted.

**Optional monitoring:**

```python
# Log startup duration for diagnostics
if central.state_machine.state == CentralState.RUNNING:
    startup_duration = time.perf_counter() - start_time
    _LOGGER.info("Central %s started successfully in %.1fs", central.name, startup_duration)
```

---

## Implementation Checklist

### Phase 1: Core Implementation

- [ ] Add new `TimeoutConfig` fields in `const.py`
- [ ] Implement `_wait_for_tcp_ready()` in `ClientCoordinator`
- [ ] Implement `_calculate_startup_retry_delay()` in `ClientCoordinator`
- [ ] Refactor `_create_client()` with retry logic
- [ ] Add translation keys to `strings.json`
- [ ] Update `strings.json` → `translations/en.json` sync

### Phase 2: Testing

- [ ] Unit tests for TCP wait logic
- [ ] Unit tests for retry logic (success after N attempts)
- [ ] Unit tests for retry exhaustion (auth/network)
- [ ] Unit tests for exponential backoff calculation
- [ ] Integration test: Docker startup race condition
- [ ] Integration test: True auth error after retries
- [ ] Integration test: Network error (connection refused)

### Phase 3: Documentation

- [ ] Update `docs/architecture.md` with startup flow diagram
- [ ] Update `CLAUDE.md` with configuration examples
- [ ] Update `changelog.md` with feature description
- [ ] Increment version in `const.py:VERSION`
- [ ] Create migration guide in `docs/migrations/`

### Phase 4: Quality Assurance

- [ ] Run `pytest tests/` - all pass
- [ ] Run `pre-commit run --all-files` - no errors
- [ ] Test with OpenCCU in Docker (real environment)
- [ ] Test with CCU3 hardware
- [ ] Test with Homegear backend
- [ ] Verify log output is clear and helpful

---

## References

- **Issue:** #2830 - homematicip_local enters re-authentication when OpenCCU is still starting
- **Related Code:**
  - `aiohomematic/central/coordinators/client.py` - ClientCoordinator
  - `aiohomematic/central/coordinators/connection_recovery.py` - ConnectionRecoveryCoordinator (staged recovery pattern)
  - `aiohomematic/client/_rpc_errors.py` - Error classification
  - `aiohomematic/const.py` - TimeoutConfig
- **Inspiration:** ConnectionRecoveryCoordinator's staged recovery approach (TCP → RPC → Warmup → Stability → Init)
