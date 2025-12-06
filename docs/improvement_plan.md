# aiohomematic Improvement Plan

## Executive Summary

Based on comprehensive codebase analysis, the aiohomematic library demonstrates **strong architectural fundamentals** with excellent dependency injection, type safety, and separation of concerns. However, there are opportunities for improvement in **modularity, security defaults, robustness, and usability**.

---

## 1. Architecture Improvements

### 1.1 Split Monolithic `interfaces.py` (2,566 lines -> ~4 modules)

**Problem**: All 44 protocol definitions in one file creates maintenance burden and cognitive load.

**Solution**: Split into focused modules:

```
aiohomematic/interfaces/
├── __init__.py           # Re-exports for backwards compatibility
├── central.py            # CentralInfo, ConfigProvider, ClientFactory, etc.
├── model.py              # DeviceProtocol, ChannelProtocol, DataPointProtocol
├── coordinators.py       # Coordinator-specific protocols
└── operations.py         # FileOperations, TaskScheduler, etc.
```

**Files to modify**:

- `aiohomematic/interfaces.py` -> split and move
- All files importing from interfaces.py (update imports)

---

### 1.2 Reduce Code Duplication in Custom Entities

**Problem**: Climate (1,185 LOC), Light (1,143 LOC), Cover (805 LOC) have duplicated patterns in `_init_data_point_fields()` and `_post_init_data_point_fields()`.

**Solution**:

- Create shared mixins for common behaviors (temperature handling, color management, position tracking)
- Extract Template Method pattern for initialization pipeline
- Consolidate field resolution logic

**Files to modify**:

- `aiohomematic/model/custom/climate.py`
- `aiohomematic/model/custom/light.py`
- `aiohomematic/model/custom/cover.py`
- Create new: `aiohomematic/model/custom/mixins.py`

---

### 1.3 Resolve Circular Dependency in EventCoordinator

**Problem**: Runtime import of `INTERFACE_EVENT_SCHEMA` at line 302 of `event_coordinator.py` to avoid circular dependency.

**Solution**: Move `INTERFACE_EVENT_SCHEMA` to a separate validation module.

**Files to modify**:

- `aiohomematic/central/__init__.py` (extract schema)
- `aiohomematic/central/event_coordinator.py` (update import)
- Create new: `aiohomematic/schemas.py`

---

### 1.4 Extract Data Point Type Determination to Strategy Pattern

**Problem**: Complex nested if-elif tree in `_determine_data_point_type()` (~40 lines) is hard to extend.

**Solution**: Create `DataPointTypeResolver` class with lookup table strategy.

**Files to modify**:

- `aiohomematic/model/generic/__init__.py`

---

## 2. Security Improvements

### 2.1 Implement Login Rate Limiting

**Problem**: No protection against brute force attacks on JSON-RPC login.

**Solution**:

- Add exponential backoff after failed login attempts
- Track failed attempts per session
- Implement configurable lockout threshold

**Files to modify**:

- `aiohomematic/client/json_rpc.py` (`_do_login` method)
- `aiohomematic/const.py` (add rate limit constants)

---

### 2.2 Sanitize Error Messages

**Problem**: Error messages include sensitive context (host, method, parameters).

**Solution**:

- Implement log-level-dependent detail stripping
- Full details for DEBUG, sanitized for INFO/WARNING
- Create error message sanitization helper

**Files to modify**:

- `aiohomematic/client/_rpc_errors.py`
- `aiohomematic/exceptions.py`

---

### 2.3 Secure Credential Handling

**Problem**: Username/password stored as regular strings in memory.

**Solution**:

- Clear credentials after successful login if only session ID needed
- Use `secrets.compare_digest()` for string comparisons
- Document credential lifecycle

**Files to modify**:

- `aiohomematic/client/json_rpc.py`

---

## 3. Robustness Improvements

### 3.1 Implement Per-Request Retry Logic with Exponential Backoff

**Problem**: Most network operations lack automatic retry. Transient errors cause permanent failures.

**Solution**:

- Create `RetryStrategy` class with exponential backoff
- Apply to RPC calls for transient errors (timeout, connection refused)
- Preserve fast-fail for permanent errors (401, 404)

**Files to modify**:

- `aiohomematic/client/__init__.py`
- `aiohomematic/client/json_rpc.py`
- `aiohomematic/client/rpc_proxy.py`
- Create new: `aiohomematic/retry.py`

---

### 3.2 Add Paramset Value Validation Before Transmission

**Problem**: Invalid values could be sent to devices without validation.

**Solution**:

- Validate paramset values against ParameterData schema before PUT operations
- Add validation helper that checks min/max/type constraints

**Files to modify**:

- `aiohomematic/client/__init__.py`
- `aiohomematic/model/data_point.py`

---

### 3.3 Improve Connection State Synchronization

**Problem**: Connection state may become inconsistent after network errors.

**Solution**:

- Explicitly update connection state after all network operations
- Add state machine for connection lifecycle
- Emit events on state transitions

**Files to modify**:

- `aiohomematic/central/__init__.py` (CentralConnectionState)
- `aiohomematic/central/scheduler.py`

---

### 3.4 Add Resource Limits for Internal Collections

**Problem**: Task sets and caches could grow unbounded in pathological cases.

**Solution**:

- Implement bounded collections with eviction policies
- Add monitoring/metrics for collection sizes
- Log warnings when approaching limits

**Files to modify**:

- `aiohomematic/async_support.py`
- `aiohomematic/store/dynamic.py`

---

## 4. Usability Improvements

### 4.1 Add Configuration Presets

**Problem**: Basic setup requires 3+ InterfaceConfig objects and many parameters.

**Solution**: Add factory methods with sensible defaults:

```python
CentralConfig.for_ccu3(host="...", username="...", password="...")
CentralConfig.for_homegear(host="...", username="...", password="...")
```

**Files to modify**:

- `aiohomematic/central/__init__.py` (CentralConfig class)

---

### 4.2 Create Simplified Facade API

**Problem**: CentralUnit has 132 public methods + 43 properties. Hard to discover primary operations.

**Solution**: Create `HomematicAPI` facade wrapping common operations:

- `get_device(address)`
- `read_value(device, parameter)`
- `write_value(device, parameter, value)`
- `subscribe_to_updates(callback)`
- `list_devices()`

**Files to create**:

- `aiohomematic/api.py` (facade)

---

### 4.3 Create "Getting Started" Documentation

**Problem**: No standalone Python project guide (README assumes Home Assistant).

**Solution**: Create `docs/getting_started.md` with:

- Minimal working example
- Common patterns (device discovery, value reading, subscriptions)
- Error handling best practices
- Connection retry strategies

**Files to create**:

- `docs/getting_started.md`

---

### 4.4 Document Top 15 Most-Used Methods

**Problem**: Large API surface makes discoverability difficult.

**Solution**: Create `docs/common_operations.md` documenting:

- Device discovery and listing
- Reading/writing parameter values
- Subscribing to events
- Managing programs and sysvars
- Connection lifecycle

**Files to create**:

- `docs/common_operations.md`

---

## 5. Testing Improvements

### 5.1 Add Integration Tests for Multi-Step Scenarios

**Problem**: Limited cross-component integration tests.

**Solution**: Add tests for scenarios like:

- Device discovery -> read value -> write value -> verify
- Connection loss -> reconnection -> state recovery
- Concurrent updates from multiple interfaces

**Files to create**:

- `tests/test_integration_scenarios.py`

---

### 5.2 Add Performance Benchmarks

**Problem**: No tests for handling large device counts (100+, 1000+).

**Solution**: Create benchmark suite:

- Device discovery time vs. device count
- Memory usage under load
- Concurrent operation throughput

**Files to create**:

- `tests/benchmarks/` directory
- `tests/benchmarks/test_device_scaling.py`

---

### 5.3 Add Event Bus Concurrency Tests

**Problem**: Limited testing of subscription edge cases.

**Solution**: Test scenarios:

- Subscriber exceptions during event dispatch
- Concurrent subscribe/unsubscribe operations
- Subscription cleanup under rapid updates

**Files to modify**:

- `tests/test_central_event_bus.py`

---

### 5.4 Expand CLI Tests

**Problem**: Only basic CLI entry point tested.

**Solution**: Add tests for:

- Various argument combinations
- Help output validation
- Error handling for invalid inputs

**Files to modify**:

- `tests/test_hmcli.py`

---

## Priority Matrix

| Improvement                          | Impact              | Effort | Priority |
| ------------------------------------ | ------------------- | ------ | -------- |
| 3.1 Retry logic with backoff         | High (Reliability)  | Medium | **P1**   |
| 2.1 Login rate limiting              | Medium (Security)   | Low    | **P1**   |
| 4.1 Configuration presets            | High (Usability)    | Low    | **P1**   |
| 1.1 Split interfaces.py              | Medium (Maintain.)  | Medium | **P2**   |
| 1.2 Reduce custom entity duplication | Medium (Maintain.)  | High   | **P2**   |
| 4.3 Getting started docs             | High (Usability)    | Low    | **P2**   |
| 3.2 Paramset validation              | Medium (Robustness) | Medium | **P2**   |
| 2.2 Sanitize error messages          | Low (Security)      | Low    | **P3**   |
| 5.1 Integration tests                | Medium (Quality)    | Medium | **P3**   |
| 4.2 Facade API                       | Medium (Usability)  | Medium | **P3**   |
| 1.3 Resolve circular dependency      | Low (Maintain.)     | Low    | **P3**   |

---

## Implementation Approach (Single Release)

Since backward compatibility is flexible, all improvements will be implemented in one comprehensive release.

### Work Packages (Parallel Execution)

**WP1: Security Hardening**

- Add login rate limiting (`json_rpc.py`, `const.py`)
- Sanitize error messages (`_rpc_errors.py`, `exceptions.py`)
- Secure credential handling (`json_rpc.py`)

**WP2: Robustness Enhancements**

- Implement retry logic with exponential backoff (create `retry.py`, update clients)
- Add paramset validation before transmission (`client/__init__.py`, `data_point.py`)
- Improve connection state synchronization (`central/__init__.py`, `scheduler.py`)
- Add resource limits for collections (`async_support.py`, `store/dynamic.py`)

**WP3: Architecture Refactoring**

- Split `interfaces.py` into `interfaces/` package (central.py, model.py, coordinators.py, operations.py)
- Create shared mixins for custom entities (`model/custom/mixins.py`)
- Resolve circular dependency (create `schemas.py`)
- Extract DataPointTypeResolver strategy (`model/generic/__init__.py`)

**WP4: Usability Improvements**

- Add configuration presets to CentralConfig (`central/__init__.py`)
- Create simplified facade API (`api.py`)
- Create getting started documentation (`docs/getting_started.md`)
- Document common operations (`docs/common_operations.md`)

**WP5: Testing Expansion**

- Add integration test scenarios (`tests/test_integration_scenarios.py`)
- Create performance benchmarks (`tests/benchmarks/`)
- Expand event bus concurrency tests (`tests/test_central_event_bus.py`)
- Expand CLI tests (`tests/test_hmcli.py`)

### Execution Order (Dependencies)

```
WP3 (Architecture) ──┐
                     ├──> WP1 (Security) ──┐
WP4.1 (Presets) ─────┘                     │
                                           ├──> WP5 (Testing)
WP2 (Robustness) ──────────────────────────┘
WP4.2-4 (Docs/API) ────────────────────────────> Final Review
```

1. **First**: WP3 (Architecture) - enables cleaner implementation of other changes
2. **Parallel**: WP1 (Security) + WP2 (Robustness) + WP4 (Usability)
3. **Final**: WP5 (Testing) - validates all changes

### Breaking Changes (Documented)

1. **interfaces.py split**: Import paths change (migration: update `from aiohomematic.interfaces import X`)
2. **Login rate limiting**: Failed logins may be throttled (new behavior, no migration needed)

---

## Files Summary

### Files to Create

| File                                      | Purpose                        |
| ----------------------------------------- | ------------------------------ |
| `aiohomematic/interfaces/__init__.py`     | Re-exports for backward compat |
| `aiohomematic/interfaces/central.py`      | Central-related protocols      |
| `aiohomematic/interfaces/model.py`        | Model-related protocols        |
| `aiohomematic/interfaces/coordinators.py` | Coordinator protocols          |
| `aiohomematic/interfaces/operations.py`   | Operation protocols            |
| `aiohomematic/model/custom/mixins.py`     | Shared custom entity behaviors |
| `aiohomematic/schemas.py`                 | Validation schemas             |
| `aiohomematic/retry.py`                   | Retry logic with backoff       |
| `aiohomematic/api.py`                     | Simplified facade API          |
| `docs/getting_started.md`                 | Standalone usage guide         |
| `docs/common_operations.md`               | Top 15 operations documented   |
| `tests/test_integration_scenarios.py`     | Multi-step integration tests   |
| `tests/benchmarks/`                       | Performance benchmark suite    |

### Files to Modify

| File                                        | Changes                     |
| ------------------------------------------- | --------------------------- |
| `aiohomematic/client/json_rpc.py`           | Rate limiting, secure creds |
| `aiohomematic/client/__init__.py`           | Retry logic, validation     |
| `aiohomematic/client/rpc_proxy.py`          | Retry logic                 |
| `aiohomematic/client/_rpc_errors.py`        | Error sanitization          |
| `aiohomematic/central/__init__.py`          | Config presets, state sync  |
| `aiohomematic/central/scheduler.py`         | Connection state sync       |
| `aiohomematic/central/event_coordinator.py` | Import fix                  |
| `aiohomematic/model/generic/__init__.py`    | DataPointTypeResolver       |
| `aiohomematic/model/custom/climate.py`      | Use mixins                  |
| `aiohomematic/model/custom/light.py`        | Use mixins                  |
| `aiohomematic/model/custom/cover.py`        | Use mixins                  |
| `aiohomematic/model/data_point.py`          | Paramset validation         |
| `aiohomematic/async_support.py`             | Resource limits             |
| `aiohomematic/store/dynamic.py`             | Resource limits             |
| `aiohomematic/const.py`                     | Rate limit constants        |
| `aiohomematic/exceptions.py`                | Error sanitization          |
| `tests/test_central_event_bus.py`           | Concurrency tests           |
| `tests/test_hmcli.py`                       | Expanded CLI tests          |

---

**Created**: 2025-12-06
**Status**: Approved for implementation
