# ADR 0015: Description Data Normalization and Validation

## Status

Implemented (2026-01-07)

## Context

PR #2733 introduced `_normalize_device_description` in `rpc_server.py` to ensure `CHILDREN` is always an array when returning data to the CCU via `listDevices()`. However, this approach addresses the symptom (malformed output) rather than the root cause (malformed input).

The current architecture has multiple entry points for device and paramset descriptions:

**DeviceDescription entry points:**

1. **XML-RPC callbacks** (`newDevices` in `RPCFunctions`)
2. **Backend queries** (`list_devices`, `get_device_description` in `DeviceHandler`)
3. **Cache persistence** (`load`/`save` in `DeviceDescriptionRegistry`)

**ParameterData/ParamsetDescription entry points:** 4. **Backend queries** (`get_paramset_description` in `DeviceHandler`) 5. **Cache persistence** (`load`/`save` in `ParamsetDescriptionRegistry`)

Normalizing data at each exit point is error-prone and violates the DRY principle. Instead, data should be normalized at ingestion time, following the **"Parse, don't validate"** pattern.

### Referenced API Specifications

- **HM_XmlRpc_API.pdf** (V2.16): Primary HomeMatic XML-RPC specification
- **HMIP_XmlRpc_API_Addendum.pdf** (V2.10): HomeMatic IP extensions

---

## Decision

Implement a comprehensive normalization and validation layer using **voluptuous** that:

1. Normalizes data at all ingestion points
2. Uses schema versioning for cache migration
3. Provides consistent TypedDict structures throughout the codebase

---

## Implementation

### 1. Voluptuous Schemas

Create new module `aiohomematic/schemas.py`:

```python
"""
Validation and normalization schemas for API data structures.

Uses voluptuous to validate and normalize data received from Homematic backends.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from aiohomematic.const import ParameterType

# ============================================================================
# DeviceDescription Schema
# ============================================================================

# Per API spec: CHILDREN is Array<String>, must never be None or empty string
def _normalize_children(value: Any) -> list[str]:
    """Normalize CHILDREN field to always be a list."""
    if value is None:
        return []
    if isinstance(value, str):
        return [] if value == "" else [value]
    if isinstance(value, (list, tuple)):
        return list(value)
    return []


# Per API spec: PARAMSETS is Array<String>, defaults to ["MASTER", "VALUES"]
def _normalize_paramsets(value: Any) -> list[str]:
    """Normalize PARAMSETS field to always be a list."""
    if value is None:
        return ["MASTER", "VALUES"]
    if isinstance(value, (list, tuple)):
        return list(value)
    return ["MASTER", "VALUES"]


DEVICE_DESCRIPTION_SCHEMA = vol.Schema(
    {
        # Required fields per API spec
        vol.Required("TYPE"): vol.Coerce(str),
        vol.Required("ADDRESS"): vol.Coerce(str),
        vol.Required("PARAMSETS", default=["MASTER", "VALUES"]): _normalize_paramsets,
        # Optional fields with normalization
        vol.Optional("CHILDREN", default=[]): _normalize_children,
        vol.Optional("PARENT"): vol.Any(None, str),
        vol.Optional("PARENT_TYPE"): vol.Any(None, str),
        vol.Optional("SUBTYPE"): vol.Any(None, str),
        vol.Optional("FIRMWARE"): vol.Any(None, str),
        vol.Optional("AVAILABLE_FIRMWARE"): vol.Any(None, str),
        vol.Optional("UPDATABLE"): vol.Coerce(bool),
        vol.Optional("FIRMWARE_UPDATE_STATE"): vol.Any(None, str),
        vol.Optional("FIRMWARE_UPDATABLE"): vol.Any(None, bool),
        vol.Optional("INTERFACE"): vol.Any(None, str),
        # Per API spec: RX_MODE is Integer (bitmask)
        vol.Optional("RX_MODE"): vol.Any(None, vol.Coerce(int)),
        vol.Optional("LINK_SOURCE_ROLES"): vol.Any(None, str),
        vol.Optional("LINK_TARGET_ROLES"): vol.Any(None, str),
        # Additional fields from spec (currently commented in const.py)
        vol.Optional("RF_ADDRESS"): vol.Any(None, vol.Coerce(int)),
        vol.Optional("INDEX"): vol.Any(None, vol.Coerce(int)),
        vol.Optional("AES_ACTIVE"): vol.Any(None, vol.Coerce(int)),
        vol.Optional("VERSION"): vol.Any(None, vol.Coerce(int)),
        vol.Optional("FLAGS"): vol.Any(None, vol.Coerce(int)),
        vol.Optional("DIRECTION"): vol.Any(None, vol.Coerce(int)),
        vol.Optional("GROUP"): vol.Any(None, str),
        vol.Optional("TEAM"): vol.Any(None, str),
        vol.Optional("TEAM_TAG"): vol.Any(None, str),
        vol.Optional("TEAM_CHANNELS"): vol.Any(None, list),
        vol.Optional("ROAMING"): vol.Any(None, vol.Coerce(int)),
    },
    extra=vol.ALLOW_EXTRA,  # Allow backend-specific extra fields
)


# ============================================================================
# ParameterData Schema (ParameterDescription in API)
# ============================================================================

# Parameter TYPE values per API spec
VALID_PARAMETER_TYPES = {
    "FLOAT", "INTEGER", "BOOL", "ENUM", "STRING", "ACTION",
    # Additional types found in practice
    "DUMMY", "",
}


def _normalize_parameter_type(value: Any) -> str:
    """Normalize and validate parameter TYPE field."""
    if value is None:
        return ""
    str_val = str(value).upper()
    return str_val if str_val in VALID_PARAMETER_TYPES else ""


# Per API spec: OPERATIONS is bitmask (1=Read, 2=Write, 4=Event)
def _normalize_operations(value: Any) -> int:
    """Normalize OPERATIONS to integer bitmask."""
    if value is None:
        return 0
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


# Per API spec: FLAGS is bitmask (0x01=Visible, 0x02=Internal, 0x04=Transform, etc.)
def _normalize_flags(value: Any) -> int:
    """Normalize FLAGS to integer bitmask."""
    if value is None:
        return 0
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


PARAMETER_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional("TYPE"): _normalize_parameter_type,
        vol.Optional("OPERATIONS", default=0): _normalize_operations,
        vol.Optional("FLAGS", default=0): _normalize_flags,
        vol.Optional("DEFAULT"): vol.Any(None, str, int, float, bool),
        vol.Optional("MAX"): vol.Any(None, str, int, float),
        vol.Optional("MIN"): vol.Any(None, str, int, float),
        vol.Optional("UNIT"): vol.Any(None, str),
        vol.Optional("ID"): vol.Any(None, str),
        # Per API spec: TAB_ORDER is Integer (display ordering)
        vol.Optional("TAB_ORDER"): vol.Any(None, vol.Coerce(int)),
        # Per API spec: CONTROL is String (UI hint)
        vol.Optional("CONTROL"): vol.Any(None, str),
        # Per API spec: VALUE_LIST is Array (for ENUM type)
        vol.Optional("VALUE_LIST"): vol.Any(None, list),
        # Per API spec: SPECIAL is Array of Struct {ID: String, VALUE: <TYPE>}
        vol.Optional("SPECIAL"): vol.Any(None, list, dict),
    },
    extra=vol.ALLOW_EXTRA,
)


# ============================================================================
# ParamsetDescription Schema
# ============================================================================

def normalize_paramset_description(
    paramset: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    """
    Normalize a paramset description dict.

    A ParamsetDescription is a Struct where each key is a parameter name
    and each value is a ParameterDescription (ParameterData).
    """
    if paramset is None:
        return {}
    result = {}
    for param_name, param_data in paramset.items():
        try:
            result[param_name] = PARAMETER_DATA_SCHEMA(param_data)
        except vol.Invalid:
            # Keep original data if validation fails, log warning
            result[param_name] = param_data
    return result


# ============================================================================
# Public API
# ============================================================================

def normalize_device_description(device_description: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize a device description dict.

    Should be called at all ingestion points:
    - After receiving from list_devices()
    - After receiving from get_device_description()
    - After receiving from newDevices() callback
    - After loading from cache

    Args:
        device_description: Raw device description from backend or cache.

    Returns:
        Normalized DeviceDescription dict with guaranteed field types.
    """
    try:
        return dict(DEVICE_DESCRIPTION_SCHEMA(device_description))
    except vol.Invalid:
        # On validation failure, at minimum ensure CHILDREN is a list
        result = dict(device_description)
        children = result.get("CHILDREN")
        if children is None or isinstance(children, str):
            result["CHILDREN"] = []
        return result


def normalize_parameter_data(parameter_data: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize a parameter data dict (ParameterDescription).

    Args:
        parameter_data: Raw parameter data from backend or cache.

    Returns:
        Normalized ParameterData dict with guaranteed field types.
    """
    try:
        return dict(PARAMETER_DATA_SCHEMA(parameter_data))
    except vol.Invalid:
        return dict(parameter_data)
```

### 2. Schema Versioning for Cache Migration

Extend `BasePersistentCache` to support schema versioning:

```python
# In aiohomematic/store/persistent/base.py

class BasePersistentCache(ABC):
    """Base class for persistent caches with schema versioning."""

    # Subclasses override to define their schema version
    SCHEMA_VERSION: int = 1

    async def load(self) -> DataOperationResult:
        """Load content from storage with migration support."""
        try:
            data = await self._storage.load()
        except Exception:
            return DataOperationResult.LOAD_FAIL

        if data is None:
            return DataOperationResult.NO_LOAD

        # Check and migrate schema version
        loaded_version = data.pop("_schema_version", 1)
        if loaded_version < self.SCHEMA_VERSION:
            data = self._migrate_schema(data=data, from_version=loaded_version)

        # ... rest of existing load logic ...

    async def save(self) -> DataOperationResult:
        """Save content with schema version tag."""
        if not self._should_save:
            return DataOperationResult.NO_SAVE

        # Add schema version before saving
        save_data = {"_schema_version": self.SCHEMA_VERSION, **self._content}

        try:
            await self._storage.save(data=save_data)
            self._last_hash_saved = self.content_hash
        except Exception:
            return DataOperationResult.SAVE_FAIL
        return DataOperationResult.SAVE_SUCCESS

    def _migrate_schema(self, *, data: dict[str, Any], from_version: int) -> dict[str, Any]:
        """
        Migrate data from older schema version.

        Subclasses override to implement version-specific migrations.
        Default implementation returns data unchanged.
        """
        return data
```

### 3. DeviceDescriptionRegistry Migration

```python
# In aiohomematic/store/persistent/device.py

from aiohomematic.schemas import normalize_device_description

class DeviceDescriptionRegistry(BasePersistentCache, ...):
    """Registry for device/channel descriptions."""

    # Bump version when normalization logic changes
    SCHEMA_VERSION: int = 2

    def add_device(self, *, interface_id: str, device_description: DeviceDescription) -> None:
        """Add a device to the cache (normalized)."""
        # Normalize at ingestion
        normalized = normalize_device_description(device_description)
        # ... existing logic with normalized data ...

    def _process_loaded_content(self, *, data: dict[str, Any]) -> None:
        """Rebuild indexes from loaded data."""
        self._addresses.clear()
        self._device_descriptions.clear()
        for interface_id, device_descriptions in data.items():
            if interface_id.startswith("_"):  # Skip metadata keys
                continue
            for device_description in device_descriptions:
                # Normalize each description when loading
                normalized = normalize_device_description(device_description)
                self._process_device_description(
                    interface_id=interface_id,
                    device_description=normalized,
                )

    def _migrate_schema(self, *, data: dict[str, Any], from_version: int) -> dict[str, Any]:
        """Migrate device descriptions from older schema."""
        if from_version < 2:
            # Migration from v1: normalize all CHILDREN fields
            for interface_id, descriptions in data.items():
                if interface_id.startswith("_"):
                    continue
                for desc in descriptions:
                    children = desc.get("CHILDREN")
                    if children is None or isinstance(children, str):
                        desc["CHILDREN"] = []
        return data
```

### 4. ParamsetDescriptionRegistry Migration

```python
# In aiohomematic/store/persistent/paramset.py

from aiohomematic.schemas import normalize_paramset_description

class ParamsetDescriptionRegistry(BasePersistentCache, ...):
    """Registry for paramset descriptions."""

    # Bump version when normalization logic changes
    SCHEMA_VERSION: int = 2

    def add(
        self,
        *,
        interface_id: str,
        channel_address: str,
        paramset_key: ParamsetKey,
        paramset_description: dict[str, ParameterData],
    ) -> None:
        """Add paramset description to cache (normalized)."""
        # Normalize at ingestion
        normalized = normalize_paramset_description(paramset_description)
        self._raw_paramset_descriptions[interface_id][channel_address][paramset_key] = normalized
        self._add_address_parameter(channel_address=channel_address, paramsets=[normalized])

    def _process_loaded_content(self, *, data: dict[str, Any]) -> None:
        """Rebuild indexes from loaded data."""
        self._content.clear()
        self._content.update(self._create_empty_content())
        for interface_id, channels in data.items():
            if interface_id.startswith("_"):  # Skip metadata keys
                continue
            for channel_address, paramsets in channels.items():
                for paramset_key_str, paramset_desc in paramsets.items():
                    paramset_key = ParamsetKey(paramset_key_str)
                    # Normalize each paramset description when loading
                    normalized = normalize_paramset_description(paramset_desc)
                    self._content[interface_id][channel_address][paramset_key] = normalized

        self._address_parameter_cache.clear()
        self._init_address_parameter_list()

    def _migrate_schema(self, *, data: dict[str, Any], from_version: int) -> dict[str, Any]:
        """Migrate paramset descriptions from older schema."""
        if from_version < 2:
            # Migration from v1: normalize all parameter data
            for interface_id, channels in data.items():
                if interface_id.startswith("_"):
                    continue
                for channel_address, paramsets in channels.items():
                    for paramset_key, params in paramsets.items():
                        for param_name, param_data in params.items():
                            # Ensure OPERATIONS and FLAGS are integers
                            if "OPERATIONS" in param_data:
                                param_data["OPERATIONS"] = int(param_data["OPERATIONS"] or 0)
                            if "FLAGS" in param_data:
                                param_data["FLAGS"] = int(param_data["FLAGS"] or 0)
        return data
```

### 5. Integration Points

#### 5.1 DeviceHandler (Backend Queries for DeviceDescription)

```python
# In aiohomematic/client/handlers/device_ops.py

from aiohomematic.schemas import normalize_device_description, normalize_paramset_description

async def list_devices(self) -> tuple[DeviceDescription, ...] | None:
    """Return all device descriptions from the backend (normalized)."""
    try:
        raw_descriptions = await self._proxy_read.listDevices()
        return tuple(
            normalize_device_description(desc)
            for desc in raw_descriptions
        )
    except BaseHomematicException:
        return None


async def get_device_description(self, *, address: str) -> DeviceDescription | None:
    """Return device description for a single address (normalized)."""
    # ... existing coalescing logic ...
    async def _fetch() -> DeviceDescription | None:
        try:
            if raw := await self._proxy_read.getDeviceDescription(address):
                return normalize_device_description(raw)
        except BaseHomematicException:
            pass
        return None
    # ...


async def _get_paramset_description(
    self, *, address: str, paramset_key: ParamsetKey
) -> dict[str, ParameterData] | None:
    """Fetch and normalize paramset description."""
    try:
        raw = await self._proxy_read.getParamsetDescription(address, paramset_key)
        return normalize_paramset_description(raw)
    except BaseHomematicException:
        return None
```

#### 4.2 RPCFunctions (XML-RPC Callbacks)

```python
# In aiohomematic/central/rpc_server.py

from aiohomematic.schemas import normalize_device_description

class RPCFunctions:
    def newDevices(self, interface_id: str, device_descriptions: list[dict[str, Any]], /) -> None:
        """Add new devices send from the backend (normalized)."""
        if entry := self.get_central_entry(interface_id=interface_id):
            # Normalize at callback entry point
            normalized = tuple(
                normalize_device_description(desc)
                for desc in device_descriptions
            )
            entry.looper.create_task(
                target=entry.central.device_coordinator.add_new_devices(
                    interface_id=interface_id, device_descriptions=normalized
                ),
                name=f"newDevices-{interface_id}",
            )

    def listDevices(self, interface_id: str, /) -> list[dict[str, Any]]:
        """Return already existing devices to the backend."""
        # No normalization needed here - data is already normalized in cache
        if entry := self.get_central_entry(interface_id=interface_id):
            return [
                dict(device_description)
                for device_description in entry.central.device_coordinator.list_devices(
                    interface_id=interface_id
                )
            ]
        return []
```

#### 4.3 Remove Output Normalization

After implementing ingestion-time normalization, remove the `_normalize_device_description` function from `rpc_server.py` as it becomes redundant.

---

## Migration Strategy

### Phase 1: Add Schema Infrastructure

1. Create `aiohomematic/schemas.py` with validation schemas
2. Extend `BasePersistentCache` with schema versioning support
3. Update `DeviceDescriptionRegistry` with SCHEMA_VERSION = 2
4. Update `ParamsetDescriptionRegistry` with SCHEMA_VERSION = 2

### Phase 2: Update DeviceDescription Ingestion Points

1. Update `DeviceHandler.list_devices()` to normalize DeviceDescriptions
2. Update `DeviceHandler.get_device_description()` to normalize DeviceDescription
3. Update `RPCFunctions.newDevices()` to normalize DeviceDescriptions
4. Update `DeviceDescriptionRegistry._process_loaded_content()` to normalize on load

### Phase 3: Update ParameterData Ingestion Points

1. Update `DeviceHandler._get_paramset_description()` to normalize ParameterData
2. Update `ParamsetDescriptionRegistry.add()` to normalize on add
3. Update `ParamsetDescriptionRegistry._process_loaded_content()` to normalize on load

### Phase 4: Clean Up

1. Remove `_normalize_device_description()` from `rpc_server.py`
2. Update tests to verify normalized data
3. Document migration in changelog

---

## Consequences

### Benefits

1. **Single Source of Truth**: Data is correct from the moment it enters the system
2. **Defense in Depth**: Multiple validation points ensure data integrity
3. **Cache Efficiency**: Schema versioning allows one-time migration
4. **Reduced Complexity**: No need for exit-point normalization
5. **Type Safety**: Consistent TypedDict structures throughout codebase
6. **Extensibility**: Easy to add new normalizations/validations

### Trade-offs

1. **Slight Overhead**: Validation at each ingestion point adds CPU cost
2. **Cache Invalidation**: Schema version bump requires cache reload
3. **Complexity**: Additional module and migration logic

### Risks

1. **Validation Strictness**: Overly strict validation could reject valid data
   - Mitigation: Use `extra=vol.ALLOW_EXTRA` and fallback to raw data on failure
2. **Performance Impact**: Normalizing large device lists
   - Mitigation: Normalization is simple dict operations, minimal overhead

---

## References

- [PR #2733: \_normalize_device_description](https://github.com/sukramj/aiohomematic/pull/2733)
- [HM_XmlRpc_API.pdf V2.16](./tmp/HM_XmlRpc_API.pdf): HomeMatic XML-RPC API Specification
- [HMIP_XmlRpc_API_Addendum.pdf V2.10](./tmp/HMIP_XmlRpc_API_Addendum.pdf): HomeMatic IP Extensions
- [ADR 0011: Storage Abstraction](0011-storage-abstraction.md)
- [voluptuous Documentation](https://github.com/alecthomas/voluptuous)

---

_Created: 2026-01-07_
_Author: Architecture Review_
