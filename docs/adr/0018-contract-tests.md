# ADR-0018: Contract Tests for CUxD/CCU-Jack Stability

**Status**: Accepted
**Date**: 2026-01-25
**Authors**: AI Assistant (Claude)

## Context

CUxD and CCU-Jack are JSON-RPC-only interfaces that operate without XML-RPC callbacks. The lack of testing capabilities for these interfaces (no test hardware available to maintainer) creates a risk: changes to core recovery logic, state machine, or connection handling could break CUxD/CCU-Jack without anyone noticing.

### Problem Statement

The codebase has capability-driven behavior that protects CUxD/CCU-Jack from incorrect behavior (e.g., `ping_pong=False` checks prevent false reconnects). However, these critical code paths were not covered by tests, making them vulnerable to accidental regression.

### Solution

Implement comprehensive **contract tests** that:

1. Guarantee capability semantics remain stable
2. Protect CUxD/CCU-Jack from regressions in core functionality
3. Document the expected behavior for future maintainers
4. Serve as an API contract for any future plugin development

## Decision

Create a comprehensive contract test suite in `tests/contract/` that verifies:

1. **Capability Contract**: Backend capability flags and their behavioral effects
2. **State Machine Contract**: Client and central state machine transitions
3. **Recovery Contract**: Connection recovery logic and backoff algorithms
4. **Event System Contract**: Event types and structure stability
5. **Lifecycle Contract**: Client lifecycle methods and state transitions

**Breaking these tests requires a MAJOR version bump** and coordination with downstream projects (e.g., Homematic(IP) Local for Home Assistant).

---

## Capability Contract Map

The core capability-driven behavior that protects CUxD/CCU-Jack:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      CAPABILITY-DRIVEN BEHAVIOR                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Capability: ping_pong = False                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ InterfaceClient.is_callback_alive()                                 │   │
│  │   → MUST return True immediately                                    │   │
│  │   → MUST NOT check callback_warn_interval                           │   │
│  │   → MUST NOT log "no events received" errors                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ InterfaceClient.is_connected()                                      │   │
│  │   → MUST return True (after connection check passes)                │   │
│  │   → MUST NOT check callback_warn_interval                           │   │
│  │   → MUST NOT trigger reconnect due to missing events                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  Capability: rpc_callback = False                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ InterfaceClient.initialize_proxy()                                  │   │
│  │   → MUST NOT call init() on XML-RPC proxy                           │   │
│  │   → MUST NOT expect callback registration                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  JSON-RPC-only interfaces (CUxD, CCU-Jack):                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ ConnectionRecoveryCoordinator._check_rpc_available()                │   │
│  │   → MUST use check_connection_availability() (JSON-RPC isPresent)   │   │
│  │   → MUST NOT use XML-RPC system.listMethods()                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ ConnectionRecoveryCoordinator port selection                        │   │
│  │   → MUST use JSON-RPC port (80/443) for TCP checks                  │   │
│  │   → MUST NOT use XML-RPC ports (2000-2011)                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Contract Test Suite

### Test Modules

| Module                                   | Purpose                                              | Tests |
| ---------------------------------------- | ---------------------------------------------------- | ----- |
| `test_capability_contract.py`            | Backend capabilities (CUxD, CCU-Jack, CCU, Homegear) | 43    |
| `test_central_state_machine_contract.py` | Central state machine transitions                    | 59    |
| `test_client_state_machine_contract.py`  | Client state machine transitions                     | 59    |
| `test_client_lifecycle_contract.py`      | Client lifecycle methods                             | 31    |
| `test_configuration_contract.py`         | CentralConfig, InterfaceConfig, TimeoutConfig        | 51    |
| `test_connection_recovery_contract.py`   | Connection recovery behavior                         | 41    |
| `test_enum_constants_contract.py`        | Enum value stability (Interface, Backend, etc.)      | 91    |
| `test_event_system_contract.py`          | Event types and structure                            | 53    |
| `test_exception_hierarchy_contract.py`   | Exception class hierarchy                            | 32    |
| `test_hub_entities_contract.py`          | Hub entity classes and NamedTuples                   | 47    |
| `test_protocol_interfaces_contract.py`   | Protocol interface definitions                       | 36    |
| `test_subscription_api_contract.py`      | EventBus subscription API                            | 26    |

**Total: 569 contract tests**

### Contract Scope

1. **State Machine Contracts**

   - Valid/invalid state transitions
   - Failure tracking and reset behavior
   - State properties (is_available, is_connected, can_reconnect)
   - Event emission on state changes

2. **Capability Contracts**

   - Capability flag stability (ping_pong, rpc_callback, push_updates)
   - Capability-gated behavior (skip callback checks when ping_pong=False)
   - Backend-specific capabilities (CCU, Homegear, CUxD/CCU-Jack)

3. **Recovery Contracts**

   - Exponential backoff formula: `delay = BASE * 2^(failures-1)`, capped at MAX
   - Maximum recovery attempts (8)
   - Recovery stage progression
   - Circuit breaker behavior

4. **Event Contracts**

   - Event types are frozen (immutable)
   - Required fields exist for each event type
   - Event priority ordering: LOW < NORMAL < HIGH < CRITICAL

5. **Lifecycle Contracts**

   - ProxyInitState enum values (integer-based)
   - TimeoutConfig fields for reconnect backoff
   - State transitions for init/deinit/reconnect/stop

6. **Enum Constants Contracts**

   - Interface, Backend, DataPointCategory enum values
   - DeviceProfile, ParamsetKey, SystemEventType values
   - StrEnum, IntEnum inheritance stability

7. **Configuration Contracts**

   - CentralConfig required and optional fields
   - InterfaceConfig fields and interface-to-RPC mapping
   - TimeoutConfig and ScheduleTimerConfig fields

8. **Exception Hierarchy Contracts**

   - All exceptions extend BaseHomematicException
   - Exception name attribute stability
   - Catching patterns work correctly

9. **Protocol Interface Contracts**

   - Protocols are runtime checkable
   - Required properties and methods exist
   - Protocol exports from interfaces package

10. **Hub Entity Contracts**

    - HUB_CATEGORIES contains expected categories
    - Hub data point classes exist (Program, Sysvar, Metrics, etc.)
    - NamedTuple fields (ProgramDpType, MetricsDpType, ConnectivityDpType)

11. **Subscription API Contracts**
    - EventBus methods (subscribe, publish, publish_sync, publish_batch)
    - Subscribe returns unsubscribe callable
    - Event types and imports stability

### Running Contract Tests

```bash
# Run contract tests specifically
pytest tests/contract/ -v

# Contract tests are included in normal test runs
pytest tests/

# Run with coverage
pytest tests/contract/ --cov=aiohomematic -v
```

---

## Stability Guarantee

### What This Means

Any change that breaks these contract tests:

1. **Requires a MAJOR version bump** (e.g., 2025.x.x → 2026.0.0)
2. **Requires coordination** with downstream projects (Homematic(IP) Local)
3. **Requires a migration guide** in `docs/migrations/`

### Contract Versioning

| Contract Version | aiohomematic Version | Changes                     |
| ---------------- | -------------------- | --------------------------- |
| 1.0              | 2026.1.51            | Initial contract test suite |

### When Contract Changes Are Needed

1. Discuss impact with maintainers
2. Update contract version in this ADR
3. Bump aiohomematic MAJOR version
4. Create migration guide
5. Announce breaking change

---

## Benefits

1. **Protection Without Hardware**: CUxD/CCU-Jack behavior is validated without physical test devices
2. **Regression Prevention**: Changes to recovery, state machines, or events cannot silently break CUxD
3. **Documentation**: Contract tests document expected behavior for future maintainers
4. **API Stability**: Plugin developers can rely on stable capability semantics
5. **Confidence**: Core refactoring can proceed safely knowing contracts protect edge cases

---

## References

- Implementation: `tests/contract/` directory
- Capability definitions: `aiohomematic/client/backends/capabilities.py`
- State machines: `aiohomematic/client/state_machine.py`, `aiohomematic/central/state_machine.py`
- Recovery logic: `aiohomematic/central/coordinators/connection_recovery.py`
- Event types: `aiohomematic/central/events/`
