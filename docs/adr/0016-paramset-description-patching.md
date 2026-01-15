# ADR 0016: Paramset Description Patching

## Status

Proposed (2026-01-15)

## Context

Some Homematic devices return incorrect `paramset_descriptions` from the CCU. These are structural issues in the device firmware or CCU implementation that cannot be fixed by type normalization alone.

### Example: HM-CC-VG-1 (Virtual Heating Group)

| Problem                  | Channel | Parameter       | Actual Value | Expected Value    |
| ------------------------ | ------- | --------------- | ------------ | ----------------- |
| Wrong MIN/MAX            | 1       | SET_TEMPERATURE | MIN=0, MAX=0 | MIN=4.5, MAX=30.5 |
| String instead of number | 1       | SET_TEMPERATURE | MIN="4.5"    | MIN=4.5           |

### Impact of Incorrect Values

1. **Validation failures**: `_convert_write_value()` rejects valid values
2. **UI issues**: Home Assistant slider shows incorrect range
3. **Automation errors**: Values outside incorrect bounds are rejected

### Current Data Flow

```
CCU Backend
    ↓
getParamsetDescription() → XML-RPC
    ↓
normalize_paramset_description() → Type normalization (schemas.py)
    ↓
ParamsetDescriptionRegistry.add() → Cache storage
    ↓
Device/Channel/DataPoint → Usage
```

**Problem**: Current normalization in `schemas.py` only corrects **types** (e.g., String→Int for OPERATIONS), not **incorrect values**.

---

## Decision

Implement a **Paramset Patch System** that applies device-specific value corrections at ingestion time.

### Design Principles

1. **Ingestion-Time Patching**: Patches applied when fetching from CCU
2. **Declarative Approach**: Patch rules as data structures, not code
3. **Device/Parameter-specific**: Patches match on (device_type, channel, parameter, field)
4. **Cache Contains Patched Data**: No patching needed when loading from cache
5. **Schema Version Invalidation**: Cache cleared on schema version mismatch
6. **Logging & Diagnostics**: Applied patches are logged

---

## Implementation

### 1. Architecture Overview

```
CCU Backend / Cache
         ↓
normalize_paramset_description()   ← Existing: Type normalization
         ↓
apply_paramset_patches()           ← NEW: Value correction
         ↓
ParamsetDescriptionRegistry.add()
         ↓
Device/Channel/DataPoint
```

### 2. Directory Structure

```
aiohomematic/store/
├── patches/                    # NEW: Patch system
│   ├── __init__.py            # Public API exports
│   ├── paramset_patches.py    # Patch definitions
│   └── matcher.py             # ParamsetPatchMatcher
├── persistent/
│   └── paramset.py            # Extended: add() with device_type
└── ...
```

### 3. Patch Definition Data Structure

```python
# aiohomematic/store/patches/paramset_patches.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from aiohomematic.const import ParamsetKey


@dataclass(frozen=True, slots=True)
class ParamsetPatch:
    """Definition of a paramset patch."""

    # Matching criteria
    device_type: str                      # e.g., "HM-CC-VG-1"
    channel_no: int | None                # None = all channels, 1 = channel 1 only
    paramset_key: ParamsetKey | None      # None = all ParamsetKeys
    parameter: str                        # e.g., "SET_TEMPERATURE"

    # Fields to patch
    patches: dict[str, Any]               # e.g., {"MIN": 4.5, "MAX": 30.5}

    # Metadata
    reason: str                           # Justification for patch
    ticket: str | None = None             # Issue/ticket reference


# Central registry of all known patches
PARAMSET_PATCHES: Final[tuple[ParamsetPatch, ...]] = (
    # HM-CC-VG-1: Virtual heating group has wrong MIN/MAX for SET_TEMPERATURE
    ParamsetPatch(
        device_type="HM-CC-VG-1",
        channel_no=1,
        paramset_key=ParamsetKey.VALUES,
        parameter="SET_TEMPERATURE",
        patches={"MIN": 4.5, "MAX": 30.5},
        reason="CCU returns invalid MIN/MAX bounds for virtual heating groups",
        ticket="https://github.com/sukramj/aiohomematic/issues/XXX",
    ),
    # Add more patches here...
)
```

### 4. Patch Matcher Component

```python
# aiohomematic/store/patches/matcher.py

from __future__ import annotations

import logging
from typing import Any, Final

from aiohomematic.const import ParameterData, ParamsetKey
from aiohomematic.store.patches.paramset_patches import PARAMSET_PATCHES, ParamsetPatch
from aiohomematic.support import get_split_channel_address

_LOGGER: Final = logging.getLogger(__name__)


class ParamsetPatchMatcher:
    """Matcher for paramset patches based on device context."""

    __slots__ = ("_device_type", "_patches_by_key")

    def __init__(self, *, device_type: str) -> None:
        """
        Initialize matcher for a specific device type.

        Args:
            device_type: The device TYPE from DeviceDescription.
        """
        self._device_type: Final = device_type
        # Pre-filter patches for this device type for O(1) lookup
        self._patches_by_key: Final[dict[tuple[int | None, ParamsetKey | None, str], ParamsetPatch]] = {
            (p.channel_no, p.paramset_key, p.parameter): p
            for p in PARAMSET_PATCHES
            if p.device_type == device_type
        }

    def apply_patches(
        self,
        *,
        channel_address: str,
        paramset_key: ParamsetKey,
        paramset_description: dict[str, ParameterData],
    ) -> dict[str, ParameterData]:
        """
        Apply patches to a paramset description.

        Args:
            channel_address: Channel address (e.g., "VCU0000001:1").
            paramset_key: The paramset key (MASTER, VALUES, etc.).
            paramset_description: The normalized paramset to patch.

        Returns:
            Patched paramset description (same dict, mutated in place).
        """
        if not self._patches_by_key:
            return paramset_description  # No patches for this device type

        _, channel_no = get_split_channel_address(channel_address=channel_address)

        for parameter, param_data in paramset_description.items():
            patch = self._find_matching_patch(
                channel_no=channel_no,
                paramset_key=paramset_key,
                parameter=parameter,
            )
            if patch is not None:
                self._apply_patch(
                    channel_address=channel_address,
                    paramset_key=paramset_key,
                    parameter=parameter,
                    param_data=param_data,
                    patch=patch,
                )

        return paramset_description

    def _find_matching_patch(
        self,
        *,
        channel_no: int | None,
        paramset_key: ParamsetKey,
        parameter: str,
    ) -> ParamsetPatch | None:
        """Find the most specific matching patch."""
        # Priority order: most specific first
        lookup_keys = [
            (channel_no, paramset_key, parameter),  # Exact match
            (None, paramset_key, parameter),         # Any channel
            (channel_no, None, parameter),           # Any paramset_key
            (None, None, parameter),                 # Any channel & paramset_key
        ]
        for key in lookup_keys:
            if patch := self._patches_by_key.get(key):
                return patch
        return None

    def _apply_patch(
        self,
        *,
        channel_address: str,
        paramset_key: ParamsetKey,
        parameter: str,
        param_data: dict[str, Any],
        patch: ParamsetPatch,
    ) -> None:
        """Apply a single patch to parameter data."""
        for field, new_value in patch.patches.items():
            old_value = param_data.get(field)
            if old_value != new_value:
                _LOGGER.debug(
                    "PATCH: %s %s/%s.%s: %s=%r → %r (reason: %s)",
                    self._device_type,
                    channel_address,
                    paramset_key.value,
                    parameter,
                    field,
                    old_value,
                    new_value,
                    patch.reason,
                )
                param_data[field] = new_value
```

### 5. Integration in schemas.py

```python
# Extend aiohomematic/schemas.py

def normalize_and_patch_paramset_description(
    *,
    paramset: dict[str, Any] | None,
    channel_address: str,
    paramset_key: ParamsetKey,
    device_type: str,
) -> dict[str, ParameterData]:
    """
    Normalize and patch a paramset description.

    Two-phase process:
    1. Normalize types (OPERATIONS, FLAGS, etc.)
    2. Apply device-specific patches for incorrect values

    Args:
        paramset: Raw paramset from CCU or cache.
        channel_address: Channel address for patch matching.
        paramset_key: Paramset key for patch matching.
        device_type: Device TYPE for patch matching.

    Returns:
        Normalized and patched paramset description.
    """
    # Phase 1: Type normalization (existing logic)
    normalized = normalize_paramset_description(paramset=paramset)

    # Phase 2: Apply device-specific patches
    from aiohomematic.store.patches import ParamsetPatchMatcher

    matcher = ParamsetPatchMatcher(device_type=device_type)
    return matcher.apply_patches(
        channel_address=channel_address,
        paramset_key=paramset_key,
        paramset_description=normalized,
    )
```

### 6. Integration in ParamsetDescriptionRegistry

The `add()` method needs to know the `device_type`:

```python
# aiohomematic/store/persistent/paramset.py - Extension

def add(
    self,
    *,
    interface_id: str,
    channel_address: str,
    paramset_key: ParamsetKey,
    paramset_description: dict[str, ParameterData],
    device_type: str,  # NEW: For patch matching
) -> None:
    """Add paramset description to cache (normalized and patched)."""
    from aiohomematic.schemas import normalize_and_patch_paramset_description

    patched = normalize_and_patch_paramset_description(
        paramset=paramset_description,
        channel_address=channel_address,
        paramset_key=paramset_key,
        device_type=device_type,
    )
    self._raw_paramset_descriptions[interface_id][channel_address][paramset_key] = patched
    self._add_address_parameter(channel_address=channel_address, paramsets=[patched])
```

---

## Cache Strategy: Schema Version Invalidation

### Challenge

When loading from cache, we need `device_type` to apply patches. But `device_type` is stored in `devices.json`, not `paramsets.json`.

### Solution: Clear Cache on Schema Mismatch

Instead of complex migration or storing redundant data, we use a simple approach:

```
Schema version mismatch? → Delete cache → Rebuild from CCU
```

**Key insight**: When fetching fresh from CCU, `device_type` is always available from `device_description["TYPE"]`. Patches are applied during fetch, and the cache stores **already patched data**.

### Implementation

```python
# In BasePersistentCache or ParamsetDescriptionRegistry

async def load(self) -> DataOperationResult:
    """Load content from storage with schema version check."""
    try:
        data = await self._storage.load()
    except Exception:
        return DataOperationResult.LOAD_FAIL

    if data is None:
        return DataOperationResult.NO_LOAD

    # Check schema version - if mismatch, invalidate cache
    loaded_version = data.get("_schema_version", 1)
    if loaded_version < self.SCHEMA_VERSION:
        _LOGGER.info(
            "Cache schema version %s < %s, clearing cache for rebuild",
            loaded_version,
            self.SCHEMA_VERSION,
        )
        await self._storage.clear()
        return DataOperationResult.NO_LOAD  # Force fresh fetch from CCU

    # ... rest of existing load logic ...
```

### Advantages

1. **No redundant storage**: No `device_type` in `paramsets.json`
2. **No complex migration logic**: Just clear and rebuild
3. **Cache contains patched data**: No patching needed when loading
4. **Simple and robust**: One-time rebuild on version bump

### Trade-off

- **One-time longer startup**: After update, cache is rebuilt from CCU
- This is acceptable because it happens only once per schema version bump

---

## Data Flow with Patching

### Fresh Fetch from CCU (Normal Path)

```
CCU.getParamsetDescription(address, paramset_key)
         ↓
InterfaceClient._get_paramset_description()
         ↓
normalize_paramset_description()     ← Type normalization
         ↓
InterfaceClient.fetch_paramset_descriptions()
         ↓  (knows device_description["TYPE"])
ParamsetDescriptionRegistry.add(device_type=...)
         ↓
apply_paramset_patches()             ← Value correction
         ↓
Save to cache (patched data)
```

### Loading from Cache (Fast Path)

```
ParamsetDescriptionRegistry.load()
         ↓
Check schema version (must match)
         ↓
_process_loaded_content()
         ↓
Build in-memory structure (data already patched)
```

### Schema Version Mismatch (Rebuild Path)

```
ParamsetDescriptionRegistry.load()
         ↓
Schema version < SCHEMA_VERSION
         ↓
Clear cache files
         ↓
Return NO_LOAD → Triggers fresh fetch from CCU
         ↓
[Continues with "Fresh Fetch" path above]
```

---

## Extensibility

### Adding New Patches

```python
# In paramset_patches.py - simply add to tuple:

PARAMSET_PATCHES: Final[tuple[ParamsetPatch, ...]] = (
    # Existing patches...

    # NEW: Another patch
    ParamsetPatch(
        device_type="HM-XY-123",
        channel_no=None,  # All channels
        paramset_key=ParamsetKey.VALUES,
        parameter="SOME_PARAM",
        patches={"DEFAULT": 50, "MAX": 100},
        reason="Factory default is wrong",
    ),
)
```

### Conditional Patches (Future Extension)

```python
@dataclass(frozen=True, slots=True)
class ConditionalParamsetPatch(ParamsetPatch):
    """Patch with condition."""

    condition: Callable[[dict[str, Any]], bool] | None = None

    def should_apply(self, param_data: dict[str, Any]) -> bool:
        """Check if patch should be applied."""
        if self.condition is None:
            return True
        return self.condition(param_data)


# Example: Only patch if MIN=0
ParamsetPatch(
    device_type="HM-CC-VG-1",
    parameter="SET_TEMPERATURE",
    patches={"MIN": 4.5},
    condition=lambda pd: pd.get("MIN") == 0,
)
```

---

## Migration and Rollout Plan

### Phase 1: Infrastructure (Schema Version 3)

1. Create new module `aiohomematic/store/patches/`
2. Implement `ParamsetPatch` and `ParamsetPatchMatcher`
3. Increase schema version to 3
4. On version mismatch: clear cache (no migration needed)

### Phase 2: Integration

1. Extend `add()` with `device_type` parameter
2. Update callers (`InterfaceClient.fetch_paramset_descriptions`)
3. Add logging for applied patches

### Phase 3: Define Patches

1. Create HM-CC-VG-1 SET_TEMPERATURE patch
2. Research other known issues and add patches
3. Write tests

### Phase 4: Documentation

1. Update changelog
2. Update CLAUDE.md

---

## Consequences

### Benefits

1. **Generic Solution**: Works for any device/parameter combination
2. **Maintainable**: Patches are declarative and documented
3. **Simple Cache Strategy**: Clear on mismatch, no complex migration
4. **Performant**: Pre-filtered patches per device type, O(1) lookup
5. **Traceable**: All applied patches are logged with reasons
6. **No Redundancy**: device_type not stored in paramsets.json

### Trade-offs

1. **Additional Module**: New patch system code
2. **One-time Rebuild**: Cache rebuilt on first start after update

### Risks

1. **Incorrect Patches**: Wrong patch values could cause issues
   - Mitigation: Require ticket reference and reason for each patch
2. **Patch Conflicts**: Multiple patches for same parameter
   - Mitigation: Most-specific-first matching priority

---

## Summary

| Aspect             | Solution                                            |
| ------------------ | --------------------------------------------------- |
| **When to patch?** | At ingestion (CCU fetch only)                       |
| **How to match?**  | device_type + channel_no + paramset_key + parameter |
| **Cache strategy** | Clear on schema mismatch, rebuild from CCU          |
| **Performance**    | O(1) lookup via pre-filtering                       |
| **Extensibility**  | Declarative patch definitions                       |
| **Compatibility**  | Schema version bump → cache invalidation            |

---

## References

- [ADR 0015: Description Data Normalization](0015-description-normalization-concept.md)
- [HM_XmlRpc_API.pdf V2.16](./tmp/HM_XmlRpc_API.pdf): HomeMatic XML-RPC API Specification
- Related Issues: TBD

---

_Created: 2026-01-15_
_Author: Architecture Review_
