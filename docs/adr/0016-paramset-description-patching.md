# ADR 0016: Paramset Description Patching

## Status

Proposed (2026-01-15)

---

## Context

### Problem

Some Homematic devices return incorrect paramset descriptions from the CCU. These are structural issues in device firmware or CCU implementation that cannot be fixed by type normalization alone.

**Example: HM-CC-VG-1 (Virtual Heating Group)**

| Problem                  | Channel | Parameter       | Actual Value | Expected Value    |
| ------------------------ | ------- | --------------- | ------------ | ----------------- |
| Wrong MIN/MAX            | 1       | SET_TEMPERATURE | MIN=0, MAX=0 | MIN=4.5, MAX=30.5 |
| String instead of number | 1       | SET_TEMPERATURE | MIN="4.5"    | MIN=4.5           |

### Impact

1. **Validation failures**: `_convert_write_value()` rejects valid values
2. **UI issues**: Home Assistant slider shows incorrect range (0-0 instead of 4.5-30.5)
3. **Automation errors**: Setpoint values within correct range (4.5-30.5) are rejected

### Current Limitation

Type normalization in `schemas.py` (ADR 0015) corrects **data types** (e.g., String→Float) but cannot correct **incorrect values**. We need value-level patching for device-specific bugs.

---

## Decision

Implement a **declarative patch system** that applies device-specific value corrections at data ingestion time.

### Key Principles

1. **Ingestion-Time Patching**: Apply patches when fetching from CCU, not on every read
2. **Declarative Approach**: Patches defined as data structures, not code
3. **Device/Parameter Matching**: Match on (device_type, channel, parameter, field)
4. **Cache Contains Patched Data**: Once patched, data stays corrected in cache
5. **Schema Version Invalidation**: Cache rebuild on schema version mismatch
6. **Traceable**: All applied patches logged with justification

---

## Architecture

### Data Flow with Patching

```
┌─────────────────┐
│ CCU Backend     │
└────────┬────────┘
         ↓
┌────────────────────────┐
│ Type Normalization     │ ← ADR 0015: Fix data types
│ (schemas.py)           │
└────────┬───────────────┘
         ↓
┌────────────────────────┐
│ Value Patching         │ ← ADR 0016: Fix incorrect values
│ (NEW)                  │
└────────┬───────────────┘
         ↓
┌────────────────────────┐
│ Cache Storage          │ ← Stores corrected data
│ (paramsets.json)       │
└────────────────────────┘
         ↓
┌────────────────────────┐
│ Device/Channel/        │
│ DataPoint Usage        │
└────────────────────────┘
```

### Patch Definition Structure

Patches are declarative data structures:

```python
{
    "device_type": "HM-CC-VG-1",
    "channel_no": 1,
    "paramset_key": "VALUES",
    "parameter": "SET_TEMPERATURE",
    "patches": {"MIN": 4.5, "MAX": 30.5},
    "reason": "CCU returns invalid MIN/MAX bounds",
    "ticket": "https://github.com/sukramj/aiohomematic/issues/XXX"
}
```

### Matching Strategy

**Priority order** (most specific first):

1. Exact match: (device_type, channel_no, paramset_key, parameter)
2. Any channel: (device_type, None, paramset_key, parameter)
3. Any paramset: (device_type, channel_no, None, parameter)
4. Any channel & paramset: (device_type, None, None, parameter)

### Cache Strategy

**Problem**: Cache loading requires `device_type` to apply patches, but `device_type` is in `devices.json`, not `paramsets.json`.

**Solution**: Schema version invalidation

- On schema version mismatch → clear cache → rebuild from CCU
- Fresh CCU fetch always has `device_type` available
- Cache stores **already-patched** data
- No patching needed when loading from cache

**Trade-off**: One-time cache rebuild after schema version bump (acceptable).

---

## Consequences

### Positive

✅ **Generic Solution**: Works for any device/parameter combination
✅ **Maintainable**: Patches are declarative with justification
✅ **Simple Cache Strategy**: Clear-and-rebuild on version mismatch (no complex migration)
✅ **Performant**: Pre-filtered patches per device type, O(1) lookup
✅ **Traceable**: All applied patches logged with reason
✅ **No Redundancy**: device_type not duplicated in paramsets.json

### Negative

⚠️ **One-time Rebuild**: Cache cleared on first start after schema version bump
⚠️ **Additional Module**: New patch system adds code complexity
⚠️ **Maintenance**: Each new device bug requires patch definition

### Risks and Mitigations

| Risk              | Mitigation                                    |
| ----------------- | --------------------------------------------- |
| Incorrect patches | Require ticket reference and reason for each  |
| Patch conflicts   | Most-specific-first matching priority         |
| Stale patches     | Log when patches don't change values (no-ops) |

---

## Alternatives Considered

### Alternative 1: Manual Per-Device Overrides in Code

Override values in custom entity classes.

**Rejected**: Not scalable, scattered logic, hard to maintain.

### Alternative 2: Store device_type in paramsets.json

Include device_type redundantly in paramset cache for patching on load.

**Rejected**: Data duplication, larger cache files, complexity.

### Alternative 3: Complex Cache Migration

Migrate cache by fetching device_type from devices.json during paramset load.

**Rejected**: Complex logic, cross-cache dependencies, clear-and-rebuild is simpler.

### Alternative 4: Patch at Read Time

Apply patches every time paramset is accessed.

**Rejected**: Performance overhead, defeats caching purpose.

---

## Implementation

**Status:** ⏳ Proposed (NOT yet implemented)

**When Implemented:**

**New Modules:**

- `aiohomematic/store/patches/paramset_patches.py` - Patch definitions
- `aiohomematic/store/patches/matcher.py` - Matching and application logic

**Modified Files:**

- `aiohomematic/schemas.py` - Extended with `apply_paramset_patches()`
- `aiohomematic/store/persistent/paramset.py` - Added `device_type` parameter to `add()`
- `aiohomematic/const.py` - Schema version bump (2 → 3)

**Key Components:**

- `ParamsetPatch` dataclass - Declarative patch definition
- `ParamsetPatchMatcher` - Pattern matching and application
- `normalize_and_patch_paramset_description()` - Two-phase normalization

**Testing:**

- Unit tests for patch matching (exact, wildcard, priority)
- Integration tests with HM-CC-VG-1 device
- Cache invalidation tests

For detailed implementation design, see:

- Implementation specifications in GitHub issue/PR when created
- Final implementation in source code files listed above

---

## Adding New Patches

To add a patch for a new device issue:

1. **Document the issue** with example values
2. **Create GitHub issue** with reproduction steps
3. **Add patch definition** to `paramset_patches.py`:
   ```python
   ParamsetPatch(
       device_type="HM-XY-123",
       channel_no=1,
       paramset_key=ParamsetKey.VALUES,
       parameter="PROBLEM_PARAM",
       patches={"FIELD": correct_value},
       reason="Brief explanation of CCU bug",
       ticket="https://github.com/.../issues/XXX",
   )
   ```
4. **Bump schema version** if needed
5. **Add tests** for the new patch
6. **Update changelog**

---

## References

- [ADR 0015: Description Data Normalization](0015-description-normalization-concept.md) - Type normalization prerequisite
- [ADR 0011: Storage Abstraction](0011-storage-abstraction.md) - Cache architecture
- HM_XmlRpc_API.pdf V2.16 - HomeMatic XML-RPC API Specification (available from eQ-3)
- Related Issues: TBD when implemented

---

_Created: 2026-01-15_
_Author: Architecture Review_
