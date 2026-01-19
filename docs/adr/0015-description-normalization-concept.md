# ADR 0015: Description Data Normalization and Validation

## Status

Implemented (2026-01-07)

---

## Context

### Problem

PR #2733 introduced `_normalize_device_description` in `rpc_server.py` to ensure `CHILDREN` is always an array when returning data to the CCU via `listDevices()`. However, this approach addresses the symptom (malformed output) rather than the root cause (malformed input).

The current architecture has multiple entry points for device and paramset descriptions:

**DeviceDescription entry points:**

1. XML-RPC callbacks (`newDevices` in `RPCFunctions`)
2. Backend queries (`list_devices`, `get_device_description`)
3. Cache persistence (`load`/`save` in `DeviceDescriptionRegistry`)

**ParameterData/ParamsetDescription entry points:** 4. Backend queries (`get_paramset_description`) 5. Cache persistence (`load`/`save` in `ParamsetDescriptionRegistry`)

Normalizing data at each exit point is error-prone and violates the DRY principle. Instead, data should be normalized at ingestion time, following the **"Parse, don't validate"** pattern.

### Root Cause

Different backends (CCU, Homegear, JSON-RPC) return inconsistent data:

- `CHILDREN` may be `None`, `""` (empty string), or `["addr"]` (array)
- `OPERATIONS` may be String `"3"` instead of Integer `3`
- `FLAGS` may be String instead of Integer
- `PARAMSETS` may be missing (should default to `["MASTER", "VALUES"]`)

---

## Decision

Implement a comprehensive normalization and validation layer using **voluptuous** that:

1. **Normalizes data at all ingestion points** (not at output)
2. **Uses schema versioning** for cache migration
3. **Provides consistent TypedDict structures** throughout the codebase

### Key Principle: "Parse, Don't Validate"

Transform malformed input into well-formed data structures **once** at ingestion, ensuring the rest of the codebase always works with correct data.

---

## Architecture

### Normalization Flow

```
┌──────────────────────┐
│ Backend / Cache      │
│ (may have bad data)  │
└──────────┬───────────┘
           ↓
┌──────────────────────────────────┐
│ Normalization (schemas.py)       │
│ - Type coercion                  │
│ - Default values                 │
│ - Field validation               │
└──────────┬───────────────────────┘
           ↓
┌──────────────────────────────────┐
│ Cache Storage                    │
│ (stores normalized data)         │
└──────────┬───────────────────────┘
           ↓
┌──────────────────────────────────┐
│ Model Layer                      │
│ (always receives valid data)     │
└──────────────────────────────────┘
```

### Ingestion Points

| Entry Point                             | Location                    | Normalization Applied          |
| --------------------------------------- | --------------------------- | ------------------------------ |
| Backend: list_devices()                 | DeviceHandler               | normalize_device_description   |
| Backend: get_device_description()       | DeviceHandler               | normalize_device_description   |
| Callback: newDevices()                  | RPCFunctions                | normalize_device_description   |
| Cache load: DeviceDescriptionRegistry   | DeviceDescriptionRegistry   | normalize_device_description   |
| Backend: get_paramset_description()     | DeviceHandler               | normalize_paramset_description |
| Cache load: ParamsetDescriptionRegistry | ParamsetDescriptionRegistry | normalize_paramset_description |

---

## Normalization Strategy

### DeviceDescription Normalization

**Key Normalizations:**

| Field       | Input Types      | Normalization Rule            | Output Type |
| ----------- | ---------------- | ----------------------------- | ----------- | ----- |
| `CHILDREN`  | None, "", String | → `[]` or `[string]`          | `list[str]` |
| `PARAMSETS` | None, missing    | → `["MASTER", "VALUES"]`      | `list[str]` |
| `RX_MODE`   | String, None     | → Coerce to int, default None | `int        | None` |
| `FLAGS`     | String           | → Coerce to int               | `int`       |
| `TYPE`      | Any              | → String (required)           | `str`       |
| `ADDRESS`   | Any              | → String (required)           | `str`       |

**Special Handling:**

- `extra=vol.ALLOW_EXTRA` - Backend-specific fields preserved
- Fallback on validation failure - Minimal fix applied (e.g., ensure CHILDREN is array)

### ParameterData Normalization

**Key Normalizations:**

| Field        | Input Types  | Normalization Rule                           | Output Type |
| ------------ | ------------ | -------------------------------------------- | ----------- | ------ |
| `TYPE`       | String       | → Validate against known types, uppercase    | `str`       |
| `OPERATIONS` | String, None | → Integer bitmask (1=Read, 2=Write, 4=Event) | `int`       |
| `FLAGS`      | String, None | → Integer bitmask (0x01=Visible, etc.)       | `int`       |
| `MAX`        | String       | → Coerce to appropriate numeric type         | `int        | float` |
| `MIN`        | String       | → Coerce to appropriate numeric type         | `int        | float` |

**Valid Parameter Types:**
`FLOAT`, `INTEGER`, `BOOL`, `ENUM`, `STRING`, `ACTION`, `DUMMY`

---

## Schema Versioning

### Cache Migration Strategy

To handle schema changes without breaking existing caches:

```python
class BasePersistentCache:
    SCHEMA_VERSION: int = 2  # Bump when normalization changes

    async def load(self) -> DataOperationResult:
        data = await self._storage.load()
        loaded_version = data.get("_schema_version", 1)

        if loaded_version < self.SCHEMA_VERSION:
            data = self._migrate_schema(data, from_version=loaded_version)
        # ...
```

**Current Schema Versions:**

- `DeviceDescriptionRegistry`: Version 2 (CHILDREN normalization)
- `ParamsetDescriptionRegistry`: Version 2 (OPERATIONS/FLAGS integer coercion)

### Migration Example

```python
# V1 → V2 migration for DeviceDescriptionRegistry
def _migrate_schema(self, data, from_version):
    if from_version < 2:
        # Normalize all CHILDREN fields
        for interface_id, descriptions in data.items():
            for desc in descriptions:
                if desc.get("CHILDREN") is None or isinstance(desc.get("CHILDREN"), str):
                    desc["CHILDREN"] = []
    return data
```

---

## Consequences

### Positive

✅ **Single Source of Truth**: Data is correct from the moment it enters the system
✅ **Defense in Depth**: Multiple validation points ensure data integrity
✅ **Cache Efficiency**: Schema versioning allows one-time migration
✅ **Reduced Complexity**: No need for exit-point normalization
✅ **Type Safety**: Consistent TypedDict structures throughout codebase
✅ **Extensibility**: Easy to add new normalizations/validations

### Negative

⚠️ **Slight Overhead**: Validation at each ingestion point adds minimal CPU cost
⚠️ **Cache Invalidation**: Schema version bump requires cache reload (one-time)
⚠️ **Complexity**: Additional module and migration logic

### Risks and Mitigations

| Risk                            | Mitigation                                     |
| ------------------------------- | ---------------------------------------------- |
| Overly strict validation        | Use `ALLOW_EXTRA`, fallback to raw on failure  |
| Performance impact              | Simple dict operations, minimal overhead       |
| Breaking existing functionality | Fallback logic preserves minimal functionality |

---

## Alternatives Considered

### Alternative 1: Output Normalization Only

Normalize data at each output point (listDevices, etc.).

**Rejected**: Error-prone, violates DRY, multiple points of failure.

### Alternative 2: Inline Normalization in Caches

Normalize within each cache's add/load methods without centralized schemas.

**Rejected**: Duplicated logic, harder to maintain, inconsistent rules.

### Alternative 3: No Normalization (Trust Backend)

Assume backend always returns correct data.

**Rejected**: Real-world data shows multiple backends return inconsistent formats.

---

## Implementation

**Status:** ✅ Implemented in version 2026.1.7

### Core Module

**`aiohomematic/schemas.py`** - Validation and normalization schemas

**Public API:**

```python
def normalize_device_description(device_description: dict[str, Any]) -> dict[str, Any]:
    """Normalize a device description dict."""

def normalize_parameter_data(parameter_data: dict[str, Any]) -> dict[str, Any]:
    """Normalize a parameter data dict (ParameterDescription)."""

def normalize_paramset_description(paramset: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Normalize a paramset description dict."""
```

**Schema Definitions:**

- `DEVICE_DESCRIPTION_SCHEMA` - voluptuous schema for DeviceDescription
- `PARAMETER_DATA_SCHEMA` - voluptuous schema for ParameterData
- Custom normalizers: `_normalize_children()`, `_normalize_paramsets()`, `_normalize_operations()`, etc.

### Updated Caches

**`aiohomematic/store/persistent/device.py`**

- `DeviceDescriptionRegistry.SCHEMA_VERSION = 2`
- Normalization in `add_device()` and `_process_loaded_content()`
- Migration logic in `_migrate_schema()`

**`aiohomematic/store/persistent/paramset.py`**

- `ParamsetDescriptionRegistry.SCHEMA_VERSION = 2`
- Normalization in `add()` and `_process_loaded_content()`
- Migration logic in `_migrate_schema()`

### Integration

**Backend queries** (`aiohomematic/client/handlers/device_ops.py`):

```python
async def list_devices(self) -> tuple[DeviceDescription, ...] | None:
    raw_descriptions = await self._proxy_read.listDevices()
    return tuple(normalize_device_description(desc) for desc in raw_descriptions)
```

**XML-RPC callbacks** (`aiohomematic/central/rpc_server.py`):

```python
def newDevices(self, interface_id: str, device_descriptions: list[dict[str, Any]], /) -> None:
    normalized = tuple(normalize_device_description(desc) for desc in device_descriptions)
    # ...
```

**Removed:**

- `_normalize_device_description()` from `rpc_server.py` (no longer needed)

---

## API Specification References

Normalization follows official HomeMatic API specifications:

- **HM_XmlRpc_API.pdf V2.16**: Primary HomeMatic XML-RPC specification
- **HMIP_XmlRpc_API_Addendum.pdf V2.10**: HomeMatic IP extensions

**Key API Requirements:**

- `CHILDREN` must be `Array<String>` (never None or empty string)
- `PARAMSETS` must be `Array<String>` (defaults to `["MASTER", "VALUES"]`)
- `OPERATIONS` is Integer bitmask: 1=Read, 2=Write, 4=Event
- `FLAGS` is Integer bitmask: 0x01=Visible, 0x02=Internal, 0x04=Transform, etc.
- `RX_MODE` is Integer bitmask (CCU2/CCU3)

---

## References

- [PR #2733: \_normalize_device_description](https://github.com/sukramj/aiohomematic/pull/2733) - Original motivation
- [ADR 0011: Storage Abstraction](0011-storage-abstraction.md) - Cache architecture
- [voluptuous Documentation](https://github.com/alecthomas/voluptuous) - Schema validation library
- [HM_XmlRpc_API.pdf V2.16](./tmp/HM_XmlRpc_API.pdf) - HomeMatic XML-RPC API Specification
- [HMIP_XmlRpc_API_Addendum.pdf V2.10](./tmp/HMIP_XmlRpc_API_Addendum.pdf) - HomeMatic IP Extensions

---

_Created: 2026-01-07_
_Author: Architecture Review_
