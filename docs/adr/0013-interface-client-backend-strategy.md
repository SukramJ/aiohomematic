# ADR 0013: InterfaceClient with Backend Strategy Pattern

## Status

**Accepted** (2026-01-05)

See [0013-implementation-status.md](0013-implementation-status.md) for current progress.

---

## Goals (Mandatory)

These goals are **non-negotiable** requirements for this implementation:

| Goal                        | Description                                   | Verification                                  |
| --------------------------- | --------------------------------------------- | --------------------------------------------- |
| **100% Compatible**         | Existing client installations work unchanged  | All existing tests pass with feature flag OFF |
| **100% Functionality**      | InterfaceClient provides identical behavior   | Comparison tests verify identical results     |
| **Feature Flag Switchable** | `USE_INTERFACE_CLIENT` enables instant switch | Single config change toggles implementation   |

### Compatibility Guarantee

```python
# Legacy path (feature flag OFF) - UNCHANGED
central = CentralConfig(...).create_central()
await central.start()
# Uses: ClientCCU / ClientJsonCCU / ClientHomegear (as before)

# New path (feature flag ON) - IDENTICAL BEHAVIOR
central = CentralConfig(
    ...,
    optional_settings=(OptionalSettings.USE_INTERFACE_CLIENT,),
).create_central()
await central.start()
# Uses: InterfaceClient with Backend strategy
# MUST produce identical results
```

---

## Context

The current client architecture has structural issues:

### Current Problems

1. **Code Scattering**: Methods like `set_value` exist in multiple classes:

   - `ClientCCU.set_value()` → delegates to Handler
   - `ClientJsonCCU.set_value()` → overrides with JSON-RPC logic
   - `DeviceHandler.set_value()` → actual implementation

2. **Inconsistent Overriding**:

   - `ClientHomegear` bypasses handlers for system variables
   - `ClientJsonCCU` duplicates handler logic with JSON-RPC calls

3. **Mixed Concerns**: Transport details (XML-RPC vs JSON-RPC) intertwined with business logic

4. **Handler Coupling**: 50+ references to `self._proxy` and `self._json_rpc_client` in handlers

   - Handlers cannot be reused with new Backend without extensive modification
   - Modifying handlers = same effort as migrating logic to InterfaceClient

5. **20+ `supports_*` Properties** spread across three client classes

### Why Handler Reuse Is Not Viable

Analysis shows handlers have tight coupling to transport layer:

| Handler File    | `_proxy`/`_json_rpc` References |
| --------------- | ------------------------------- |
| `device_ops.py` | 13                              |
| `metadata.py`   | 16                              |
| `sysvars.py`    | 4                               |
| `programs.py`   | 4                               |
| `link_mgmt.py`  | 4                               |
| `firmware.py`   | 3                               |
| `backup.py`     | 3                               |
| `base.py`       | 3                               |
| **Total**       | **50**                          |

Adapting handlers to use `BackendOperationsProtocol` requires the same effort as migrating logic directly into InterfaceClient, but results in worse architecture.

---

## Decision

Replace the legacy client hierarchy with a **single InterfaceClient** using the **Backend Strategy Pattern**:

1. **InterfaceClient** contains ALL business logic (validation, callbacks, caching)
2. **Backends** contain ONLY transport logic (XML-RPC, JSON-RPC calls)
3. **Handlers are NOT reused** - their logic migrates into InterfaceClient
4. **Feature Flag** (`USE_INTERFACE_CLIENT`) enables instant switching
5. **Legacy clients remain unchanged** until Phase 5 cleanup

### Key Principle: Clear Separation of Concerns

```
┌─────────────────────────────────────────────────────────────┐
│                    InterfaceClient                           │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                   Business Logic                        │ │
│  │  - Value validation against paramset descriptions       │ │
│  │  - Wait for callback after set_value                    │ │
│  │  - Temporary values for UI feedback                     │ │
│  │  - Request coalescing / deduplication                   │ │
│  │  - Master paramset polling after write                  │ │
│  │  - Connection state management                          │ │
│  │  - Ping/Pong tracking                                   │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────┬──────────────────────────────────┘
                           │ delegates to
                           ▼
┌─────────────────────────────────────────────────────────────┐
│               BackendOperationsProtocol                      │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                   Transport Logic                       │ │
│  │  - XML-RPC / JSON-RPC method calls                      │ │
│  │  - Backend-specific protocol handling                   │ │
│  │  - Response parsing                                     │ │
│  │  - NO business logic, NO validation                     │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## Architecture

### Target Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     ClientProtocol                          │
│  (identical interface for both implementations)             │
└─────────────────────────────────────────────────────────────┘
              ▲                              ▲
              │                              │
┌─────────────┴─────────────┐  ┌────────────┴────────────────┐
│  Legacy Clients           │  │  InterfaceClient (Target)   │
│  ├── ClientCCU            │  │                             │
│  ├── ClientJsonCCU        │  │  ALL business logic here    │
│  └── ClientHomegear       │  │  100% replacement for       │
│                           │  │  legacy clients             │
│  Uses: Handlers           │  │                             │
│  (to be removed Phase 5)  │  │  Uses: Backends (Strategy)  │
└───────────────────────────┘  └─────────────────────────────┘
              │                              │
              └──────────┬───────────────────┘
                         │ USE_INTERFACE_CLIENT
                         ▼
              ┌──────────────────────┐
              │   create_client()    │
              └──────────────────────┘
```

### Backend Strategy Detail

```
┌─────────────────────────────────────────────────────────────┐
│ InterfaceClient                                              │
│                                                              │
│   Business Logic (migrated from Handlers):                   │
│   ├── Value validation (_validate_value)                    │
│   ├── Paramset validation (_validate_paramset)              │
│   ├── Temporary value writing (_write_temporary_value)      │
│   ├── Wait for callback (_wait_for_state_change_or_timeout) │
│   ├── Request coalescing (RequestCoalescer)                 │
│   ├── Master paramset polling (_poll_master_values)         │
│   └── Device details processing                             │
│                                                              │
│   Delegates transport to Backend:                            │
│   └── self._backend.set_value(...)                          │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ BackendOperationsProtocol (Interface)                        │
│                                                              │
│   Pure transport methods:                                    │
│   ├── set_value(address, parameter, value, rx_mode)         │
│   ├── get_value(address, parameter)                         │
│   ├── put_paramset(address, paramset_key, values, rx_mode)  │
│   ├── get_paramset(address, paramset_key)                   │
│   ├── list_devices()                                        │
│   ├── get_device_description(address)                       │
│   ├── get_paramset_description(address, paramset_key)       │
│   └── ... (all RPC methods)                                 │
└─────────────────────────────────────────────────────────────┘
        ▲                     ▲                     ▲
        │                     │                     │
┌───────┴───────┐   ┌────────┴────────┐   ┌───────┴───────────┐
│ CcuBackend     │   │ JsonCcuBackend   │   │ HomegearBackend    │
│                │   │                  │   │                    │
│ XML-RPC for    │   │ JSON-RPC only    │   │ XML-RPC with       │
│ device ops,    │   │ (CCU-Jack)       │   │ Homegear-specific  │
│ JSON-RPC for   │   │                  │   │ methods            │
│ metadata       │   │                  │   │                    │
└────────────────┘   └──────────────────┘   └────────────────────┘
```

---

## Responsibility Matrix

### InterfaceClient (Business Logic)

| Responsibility         | Source                                              | Description                           |
| ---------------------- | --------------------------------------------------- | ------------------------------------- |
| Value validation       | `DeviceHandler._check_set_value()`                  | Validate against paramset description |
| Paramset validation    | `DeviceHandler._check_put_paramset()`               | Validate all values in paramset       |
| Value conversion       | `DeviceHandler._convert_value()`                    | Convert to correct type               |
| Temporary values       | `DeviceHandler._write_temporary_value()`            | Write for immediate UI feedback       |
| Wait for callback      | `DeviceHandler._wait_for_state_change_or_timeout()` | Wait for confirmation event           |
| Request coalescing     | `DeviceHandler._*_coalescer`                        | Deduplicate concurrent requests       |
| Master polling         | `DeviceHandler.put_paramset()`                      | Poll after BidCos MASTER write        |
| Device details parsing | `DeviceHandler.fetch_device_details()`              | Parse JSON, update cache              |
| Connection state       | `ClientCCU`                                         | State machine, ping/pong              |
| Capability checks      | `ClientCCU.supports_*`                              | Check before operations               |

### Backends (Transport Only)

| Responsibility           | Description                               |
| ------------------------ | ----------------------------------------- |
| RPC calls                | Execute XML-RPC or JSON-RPC methods       |
| Response parsing         | Convert RPC response to typed data        |
| Error wrapping           | Wrap transport errors in exceptions       |
| Protocol selection       | Choose XML-RPC vs JSON-RPC per method     |
| Backend-specific methods | Homegear extensions, CCU-Jack differences |

### What Backends Must NOT Do

- ❌ Validate values against paramset descriptions
- ❌ Wait for callbacks
- ❌ Write temporary values
- ❌ Access device registry or data points
- ❌ Manage connection state
- ❌ Coalesce requests

---

## Handler Logic Migration Checklist

### Phase 2a: Core Operations (DeviceHandler) - CRITICAL

| Logic               | Source Method                         | Target Method              | Status |
| ------------------- | ------------------------------------- | -------------------------- | ------ |
| Value validation    | `_check_set_value()`                  | `_validate_value()`        | ⬜     |
| Paramset validation | `_check_put_paramset()`               | `_validate_paramset()`     | ⬜     |
| Value conversion    | `_convert_value()`                    | `_convert_value()`         | ⬜     |
| Temporary values    | `_write_temporary_value()`            | `_write_temporary_value()` | ⬜     |
| Wait for callback   | `_wait_for_state_change_or_timeout()` | Already imported           | ✅     |
| Request coalescing  | `RequestCoalescer` instances          | `_request_coalescer`       | ⬜     |
| Master polling      | `put_paramset()` poll logic           | `_poll_master_values()`    | ⬜     |
| `check_against_pd`  | Parameter in `set_value`              | Same parameter             | ⬜     |

### Phase 2b: Metadata Operations

| Logic                    | Source          | Target                    | Status |
| ------------------------ | --------------- | ------------------------- | ------ |
| `get_all_rooms()`        | MetadataHandler | Direct delegation         | ⬜     |
| `get_all_functions()`    | MetadataHandler | Direct delegation         | ⬜     |
| `fetch_device_details()` | MetadataHandler | `_fetch_device_details()` | ⬜     |

### Phase 2c: Other Handlers

| Handler                 | Migration Strategy                    | Status |
| ----------------------- | ------------------------------------- | ------ |
| `LinkHandler`           | Direct delegation, minimal logic      | ⬜     |
| `FirmwareHandler`       | Direct delegation                     | ⬜     |
| `ProgramHandler`        | Direct delegation                     | ⬜     |
| `SystemVariableHandler` | Direct delegation                     | ⬜     |
| `BackupHandler`         | Move polling logic to InterfaceClient | ⬜     |

---

## Feature Flag

```python
# aiohomematic/const.py
class OptionalSettings(StrEnum):
    """Optional settings for CentralConfig."""
    SESSION_RECORDER = "session_recorder"
    PERFORMANCE_METRICS = "performance_metrics"
    ASYNC_RPC_SERVER = "async_rpc_server"
    USE_INTERFACE_CLIENT = "use_interface_client"  # Toggle implementation
```

### Usage in ClientCoordinator

```python
use_new = (
    OptionalSettings.USE_INTERFACE_CLIENT
    in self._config_provider.config.optional_settings
)
client = await create_client(use_interface_client=use_new, ...)
```

---

## File Structure

### New Files

```
aiohomematic/client/
├── backends/                      # Transport layer
│   ├── __init__.py               # Package exports
│   ├── base.py                   # BaseBackend (abstract)
│   ├── capabilities.py           # BackendCapabilities dataclass
│   ├── ccu.py                    # CcuBackend (XML-RPC + JSON-RPC)
│   ├── factory.py                # create_backend()
│   ├── homegear.py               # HomegearBackend
│   ├── json_ccu.py               # JsonCcuBackend
│   └── protocol.py               # BackendOperationsProtocol
│
└── interface_client.py           # All business logic
```

### Unchanged (Legacy - Remove in Phase 5)

```
aiohomematic/client/
├── ccu.py                        # Legacy clients
├── handlers/                     # Legacy handlers (50+ transport refs)
│   ├── base.py
│   ├── device_ops.py
│   ├── link_mgmt.py
│   ├── firmware.py
│   ├── metadata.py
│   ├── programs.py
│   ├── sysvars.py
│   └── backup.py
```

---

## Migration Phases

### Phase 1: Core Implementation ✅ COMPLETE

- [x] Create `backends/` package with all backends
- [x] Create `InterfaceClient` with basic delegation
- [x] Add feature flag `USE_INTERFACE_CLIENT`
- [x] All existing tests pass (feature flag OFF)

### Phase 2: Handler Logic Migration ⬅️ CURRENT

- [ ] Migrate value validation from DeviceHandler
- [ ] Migrate value conversion
- [ ] Migrate temporary value writing
- [ ] Migrate request coalescing
- [ ] Migrate master paramset polling
- [ ] Add comparison tests (legacy vs InterfaceClient)
- [ ] Verify 100% identical behavior

**Success Criteria:**

- [ ] All comparison tests pass
- [ ] No behavioral differences detected
- [ ] Test coverage >= 85% for InterfaceClient

### Phase 3: Beta Testing

- [ ] Enable feature flag for beta testers
- [ ] Monitor for differences/errors
- [ ] Minimum 4 weeks of error-free operation
- [ ] Collect user feedback

**Success Criteria:**

- [ ] Zero regressions reported
- [ ] Performance within 5% of legacy

### Phase 4: Rollout

- [ ] Feature flag = True (default)
- [ ] Legacy remains available as fallback
- [ ] Update documentation

### Phase 5: Cleanup

- [ ] Remove legacy clients (`ClientCCU`, `ClientJsonCCU`, `ClientHomegear`)
- [ ] Remove handlers package
- [ ] Remove feature flag
- [ ] Rename `InterfaceClient` → `Client`

---

## Testing Strategy

### Comparison Tests (Mandatory for Phase 2)

```python
@pytest.fixture(params=["legacy", "interface_client"])
def client_impl(request):
    return request.param

async def test_set_value_identical_behavior(client_impl, ...):
    """Verify both implementations produce identical results."""
    use_new = client_impl == "interface_client"
    client = await create_client(use_interface_client=use_new, ...)

    result = await client.set_value(
        channel_address="VCU0000001:1",
        paramset_key=ParamsetKey.VALUES,
        parameter="STATE",
        value=True,
        wait_for_callback=5,
    )

    assert isinstance(result, set)
```

### Test Coverage Matrix

| Operation          | Legacy Test | InterfaceClient Test | Comparison Test |
| ------------------ | ----------- | -------------------- | --------------- |
| `set_value`        | ✅          | ⬜                   | ⬜              |
| `put_paramset`     | ✅          | ⬜                   | ⬜              |
| Value validation   | ✅          | ⬜                   | ⬜              |
| Wait for callback  | ✅          | ⬜                   | ⬜              |
| Temporary values   | ✅          | ⬜                   | ⬜              |
| Request coalescing | ✅          | ⬜                   | ⬜              |
| Master polling     | ✅          | ⬜                   | ⬜              |

---

## Risk Mitigation

| Risk                     | Mitigation                                 |
| ------------------------ | ------------------------------------------ |
| Breaking Changes         | Feature flag enables instant rollback      |
| Undiscovered Differences | Comparison tests verify identical behavior |
| Performance Regression   | A/B testing with metrics                   |
| Missing Edge Cases       | Session replay tests from real CCU         |

---

## References

- [Strategy Pattern](https://refactoring.guru/design-patterns/strategy)
- [Strangler Fig Pattern](https://martinfowler.com/bliki/StranglerFigApplication.html)
- [ADR 0012: Async XML-RPC Server](0012-async-xml-rpc-server-poc.md) - Similar feature flag approach

---

_Created: 2026-01-04_
_Updated: 2026-01-05_
_Author: Architecture Review_
_Status: Accepted_
