# ADR 0016: XML-RPC API Compliance Analysis

## Status

Analysis (Informational)

## Purpose

This document analyzes the current aiohomematic implementation against the official eQ-3 XML-RPC API specifications:

- **HM_XmlRpc_API.pdf** (V2.16): Primary HomeMatic specification
- **HMIP_XmlRpc_API_Addendum.pdf** (V2.10): HomeMatic IP extensions

---

## 1. DeviceDescription Analysis

### API Specification (HM_XmlRpc_API.pdf, Section 5.1)

| Field              | Type            | Description                          |
| ------------------ | --------------- | ------------------------------------ |
| TYPE               | String          | Device type (required)               |
| ADDRESS            | String          | Unique address (required)            |
| RF_ADDRESS         | Integer         | Radio frequency address              |
| CHILDREN           | Array\<String\> | Channel addresses (device only)      |
| PARENT             | String          | Parent device address (channel only) |
| PARENT_TYPE        | String          | Parent device type (channel only)    |
| INDEX              | Integer         | Channel index (channel only)         |
| AES_ACTIVE         | Integer         | AES encryption status                |
| PARAMSETS          | Array\<String\> | Available paramset keys              |
| FIRMWARE           | String          | Current firmware version             |
| AVAILABLE_FIRMWARE | String          | Available firmware update            |
| UPDATABLE          | Boolean         | Firmware update available flag       |
| VERSION            | Integer         | Description version (required)       |
| FLAGS              | Integer         | Status flags (required)              |
| LINK_SOURCE_ROLES  | String          | Link source role identifiers         |
| LINK_TARGET_ROLES  | String          | Link target role identifiers         |
| DIRECTION          | Integer         | Communication direction              |
| GROUP              | String          | Device group                         |
| TEAM               | String          | Team address                         |
| TEAM_TAG           | String          | Team identifier                      |
| TEAM_CHANNELS      | Array\<String\> | Team channel addresses               |
| INTERFACE          | String          | Interface identifier                 |
| ROAMING            | Integer         | Roaming enabled flag                 |
| RX_MODE            | Integer         | Receive mode bitmask                 |

### HomeMatic IP Extensions (HMIP_XmlRpc_API_Addendum.pdf)

| Field                 | Type   | Description                                             |
| --------------------- | ------ | ------------------------------------------------------- |
| SUBTYPE               | String | Device subtype                                          |
| FIRMWARE_UPDATE_STATE | String | Update state (UP_TO_DATE, NEW_FIRMWARE_AVAILABLE, etc.) |

### Current Implementation (`aiohomematic/const.py`)

```python
class DeviceDescription(TypedDict, total=False):
    TYPE: Required[str]
    ADDRESS: Required[str]
    PARAMSETS: Required[list[str]]
    SUBTYPE: str | None
    CHILDREN: list[str]
    PARENT: str | None
    FIRMWARE: str | None
    AVAILABLE_FIRMWARE: str | None
    UPDATABLE: bool
    FIRMWARE_UPDATE_STATE: str | None
    FIRMWARE_UPDATABLE: bool | None
    INTERFACE: str | None
    RX_MODE: int | None
    LINK_SOURCE_ROLES: str | None
    LINK_TARGET_ROLES: str | None
    # Commented out: RF_ADDRESS, PARENT_TYPE, INDEX, AES_ACTIVE, VERSION, FLAGS,
    #                DIRECTION, GROUP, TEAM, TEAM_TAG, TEAM_CHANNELS, ROAMING
```

### Compliance Status

| Field                 | Spec     | Implementation | Status       | Notes                                        |
| --------------------- | -------- | -------------- | ------------ | -------------------------------------------- |
| TYPE                  | Required | Required       | ✅ Compliant |                                              |
| ADDRESS               | Required | Required       | ✅ Compliant |                                              |
| PARAMSETS             | Optional | Required       | ⚠️ Stricter  | Implementation requires, spec optional       |
| CHILDREN              | Array    | list\[str\]    | ⚠️ Issue     | **PR #2733 issue**: Can be None/empty string |
| PARENT                | String   | str \| None    | ✅ Compliant |                                              |
| PARENT_TYPE           | String   | Commented out  | ❌ Missing   | Not exposed in TypedDict                     |
| INDEX                 | Integer  | Commented out  | ❌ Missing   | Not exposed in TypedDict                     |
| VERSION               | Required | Commented out  | ❌ Missing   | Spec requires, not implemented               |
| FLAGS                 | Required | Commented out  | ❌ Missing   | Spec requires, not implemented               |
| RF_ADDRESS            | Integer  | Commented out  | ❌ Missing   | Not exposed in TypedDict                     |
| AES_ACTIVE            | Integer  | Commented out  | ❌ Missing   | Not exposed in TypedDict                     |
| DIRECTION             | Integer  | Commented out  | ❌ Missing   | Not exposed in TypedDict                     |
| GROUP                 | String   | Commented out  | ❌ Missing   | Not exposed in TypedDict                     |
| TEAM                  | String   | Commented out  | ❌ Missing   | Not exposed in TypedDict                     |
| TEAM_TAG              | String   | Commented out  | ❌ Missing   | Not exposed in TypedDict                     |
| TEAM_CHANNELS         | Array    | Commented out  | ❌ Missing   | Not exposed in TypedDict                     |
| ROAMING               | Integer  | Commented out  | ❌ Missing   | Not exposed in TypedDict                     |
| SUBTYPE               | String   | str \| None    | ✅ Compliant | HmIP extension                               |
| FIRMWARE_UPDATE_STATE | String   | str \| None    | ✅ Compliant | HmIP extension                               |
| FIRMWARE_UPDATABLE    | -        | bool \| None   | ➕ Extra     | Not in spec, implementation-specific         |

### Recommendations

1. **CHILDREN Normalization**: Implement normalization at ingestion (see ADR 0015)
2. **VERSION/FLAGS**: Consider adding as they are marked "required" in spec
3. **Commented Fields**: Uncomment and expose fields that are actually used
4. **PARAMSETS Default**: Spec shows optional, consider relaxing `Required`

---

## 2. ParameterDescription (ParameterData) Analysis

### API Specification (HM_XmlRpc_API.pdf, Section 5.2)

| Field      | Type            | Description                                                                     |
| ---------- | --------------- | ------------------------------------------------------------------------------- |
| TYPE       | String          | Parameter type (FLOAT, INTEGER, BOOL, ENUM, STRING, ACTION)                     |
| OPERATIONS | Integer         | Bitmask: 1=Read, 2=Write, 4=Event                                               |
| FLAGS      | Integer         | Bitmask: 0x01=Visible, 0x02=Internal, 0x04=Transform, 0x08=Service, 0x10=Sticky |
| DEFAULT    | \<TYPE\>        | Default value (type matches TYPE)                                               |
| MAX        | \<TYPE\>        | Maximum value                                                                   |
| MIN        | \<TYPE\>        | Minimum value                                                                   |
| UNIT       | String          | Unit of measurement                                                             |
| TAB_ORDER  | Integer         | Display ordering                                                                |
| CONTROL    | String          | UI control hint                                                                 |
| VALUE_LIST | Array\<String\> | Enum values (ENUM type only)                                                    |
| SPECIAL    | Array\<Struct\> | Special values with ID and VALUE                                                |

### Current Implementation (`aiohomematic/const.py`)

```python
class ParameterData(TypedDict, total=False):
    DEFAULT: Any
    FLAGS: int
    ID: str
    MAX: Any
    MIN: Any
    OPERATIONS: int
    SPECIAL: Mapping[str, Any]
    TYPE: ParameterType
    UNIT: str
    VALUE_LIST: Iterable[Any]
```

### ParameterType Enum (`aiohomematic/const.py`)

```python
class ParameterType(StrEnum):
    ACTION = "ACTION"
    BOOL = "BOOL"
    DUMMY = "DUMMY"
    ENUM = "ENUM"
    FLOAT = "FLOAT"
    INTEGER = "INTEGER"
    STRING = "STRING"
    EMPTY = ""
```

### Compliance Status

| Field      | Spec Type       | Implementation      | Status       | Notes                              |
| ---------- | --------------- | ------------------- | ------------ | ---------------------------------- |
| TYPE       | String          | ParameterType       | ✅ Compliant | Enum covers all spec values        |
| OPERATIONS | Integer         | int                 | ✅ Compliant |                                    |
| FLAGS      | Integer         | int                 | ✅ Compliant |                                    |
| DEFAULT    | \<TYPE\>        | Any                 | ✅ Compliant | Flexible typing appropriate        |
| MAX        | \<TYPE\>        | Any                 | ✅ Compliant | Flexible typing appropriate        |
| MIN        | \<TYPE\>        | Any                 | ✅ Compliant | Flexible typing appropriate        |
| UNIT       | String          | str                 | ✅ Compliant |                                    |
| TAB_ORDER  | Integer         | Not present         | ❌ Missing   | UI ordering not exposed            |
| CONTROL    | String          | Not present         | ❌ Missing   | UI hint not exposed                |
| VALUE_LIST | Array\<String\> | Iterable\[Any\]     | ⚠️ Relaxed   | More permissive than spec          |
| SPECIAL    | Array\<Struct\> | Mapping\[str, Any\] | ⚠️ Different | Spec says Array, impl uses Mapping |
| ID         | -               | str                 | ➕ Extra     | Not in spec, impl-specific         |
| DUMMY      | -               | ParameterType       | ➕ Extra     | Not in spec, impl-specific         |

### Recommendations

1. **TAB_ORDER/CONTROL**: Add if UI ordering needed
2. **SPECIAL Type**: Spec defines as Array of Struct `{ID: String, VALUE: <TYPE>}`, current impl uses Mapping
3. **VALUE_LIST Type**: Consider stricter typing `list[str]`

---

## 3. ParamsetDescription Analysis

### API Specification (HM_XmlRpc_API.pdf, Section 5.2)

```
ParamsetDescription = Struct<ParameterDescription>
```

A ParamsetDescription is a struct (dictionary) where:

- Keys are parameter names (strings)
- Values are ParameterDescription structs

### Current Implementation

The implementation correctly treats ParamsetDescription as `dict[str, ParameterData]`.

### Compliance Status: ✅ Compliant

---

## 4. Operations Bitmask Analysis

### API Specification

| Value | Constant | Description            |
| ----- | -------- | ---------------------- |
| 1     | Read     | Parameter readable     |
| 2     | Write    | Parameter writable     |
| 4     | Event    | Parameter sends events |

### Current Implementation (`aiohomematic/const.py`)

```python
class Operations(IntEnum):
    NONE = 0
    READ = 1
    WRITE = 2
    EVENT = 4
```

### Compliance Status: ✅ Fully Compliant

---

## 5. Flags Bitmask Analysis

### API Specification

| Value | Constant  | Description                |
| ----- | --------- | -------------------------- |
| 0x01  | Visible   | Parameter is visible       |
| 0x02  | Internal  | Internal parameter         |
| 0x04  | Transform | Value transformation       |
| 0x08  | Service   | Service message            |
| 0x10  | Sticky    | Sticky value (remains set) |

### Current Implementation (`aiohomematic/const.py`)

```python
class Flag(IntFlag):
    VISIBLE = 1
    INTERNAL = 2
    TRANSFORM = 4
    SERVICE = 8
    STICKY = 16
```

### Compliance Status: ✅ Fully Compliant

---

## 6. RX_MODE Bitmask Analysis

### API Specification (HM_XmlRpc_API.pdf, Section 5.3)

| Value | Constant    | Description             |
| ----- | ----------- | ----------------------- |
| 0x01  | ALWAYS      | Always receives         |
| 0x02  | BURST       | Burst mode              |
| 0x04  | CONFIG      | Configuration mode      |
| 0x08  | WAKEUP      | Wakeup mode             |
| 0x10  | LAZY_CONFIG | Lazy configuration mode |

### Current Implementation

```python
class RxMode(IntFlag):
    ALWAYS = 0x01
    BURST = 0x02
    CONFIG = 0x04
    WAKEUP = 0x08
    LAZY_CONFIG = 0x10
```

### Compliance Status: ✅ Fully Compliant

---

## 7. XML-RPC Method Compliance

### Device Discovery Methods

| Method               | Spec                            | Implementation | Status       |
| -------------------- | ------------------------------- | -------------- | ------------ |
| listDevices          | () → Array\<DeviceDescription\> | ✅ Implemented | ✅ Compliant |
| getDeviceDescription | (address) → DeviceDescription   | ✅ Implemented | ✅ Compliant |
| newDevices           | Callback                        | ✅ Implemented | ✅ Compliant |
| deleteDevices        | Callback                        | ✅ Implemented | ✅ Compliant |
| updateDevice         | Callback                        | ✅ Implemented | ✅ Compliant |
| replaceDevice        | Callback                        | ✅ Implemented | ✅ Compliant |
| readdedDevice        | Callback                        | ✅ Implemented | ✅ Compliant |

### Paramset Methods

| Method                 | Spec                                 | Implementation | Status       |
| ---------------------- | ------------------------------------ | -------------- | ------------ |
| getParamsetDescription | (address, key) → ParamsetDescription | ✅ Implemented | ✅ Compliant |
| getParamset            | (address, key) → Struct              | ✅ Implemented | ✅ Compliant |
| putParamset            | (address, key, set) → void           | ✅ Implemented | ✅ Compliant |

### Value Methods

| Method   | Spec                           | Implementation | Status       |
| -------- | ------------------------------ | -------------- | ------------ |
| getValue | (address, param) → value       | ✅ Implemented | ✅ Compliant |
| setValue | (address, param, value) → void | ✅ Implemented | ✅ Compliant |

### System Methods

| Method               | Spec                  | Implementation | Status       |
| -------------------- | --------------------- | -------------- | ------------ |
| init                 | (url, id) → Array     | ✅ Implemented | ✅ Compliant |
| ping                 | (caller_id) → Boolean | ✅ Implemented | ✅ Compliant |
| listBidcosInterfaces | () → Array            | ✅ Implemented | ✅ Compliant |
| system.listMethods   | () → Array            | ✅ Implemented | ✅ Compliant |
| system.multicall     | (Array) → Array       | ✅ Implemented | ✅ Compliant |

### HomeMatic IP Extensions

| Method                      | Spec                | Implementation | Status       |
| --------------------------- | ------------------- | -------------- | ------------ |
| installFirmware             | (address) → Boolean | ✅ Implemented | ✅ Compliant |
| setInstallModeWithWhitelist | Extended init       | ❓ Unknown     | Needs review |

---

## 8. Error Code Compliance

### API Specification

| Code | Description                          |
| ---- | ------------------------------------ |
| -1   | Unknown device                       |
| -2   | Unknown paramset                     |
| -3   | Unknown parameter                    |
| -4   | Device not ready                     |
| -5   | Invalid value                        |
| -6   | Invalid call (operation not allowed) |
| -7   | HM script error                      |
| -10  | Transmission pending (HmIP)          |

### Current Implementation

Error handling is implemented via exception classes. Specific RPC fault codes are handled in `aiohomematic/client/_rpc_errors.py`.

### Compliance Status: ✅ Compliant (via exception mapping)

---

## 9. Summary of Findings

### High Priority Recommendations

1. **CHILDREN Normalization** (Critical)

   - **Issue**: CHILDREN can be None or empty string, breaking CCU Java parser
   - **Solution**: Implement ADR 0015 normalization at ingestion points

2. **VERSION/FLAGS Fields** (Medium)
   - **Issue**: Spec marks as "required", implementation comments them out
   - **Solution**: Uncomment in TypedDict, validate presence

### Medium Priority Recommendations

3. **SPECIAL Field Type** (Low Impact)

   - **Issue**: Spec defines as Array, implementation uses Mapping
   - **Solution**: Verify actual backend responses, adjust type accordingly

4. **TAB_ORDER/CONTROL Fields** (Low Impact)

   - **Issue**: Not exposed in ParameterData
   - **Solution**: Add if UI ordering needed

5. **Commented DeviceDescription Fields** (Documentation)
   - **Issue**: Many spec fields commented out
   - **Solution**: Document which fields are intentionally excluded

### Low Priority Recommendations

6. **PARAMSETS Required Status**

   - **Issue**: Implementation marks Required, spec shows optional
   - **Solution**: Consider relaxing or documenting reason

7. **VALUE_LIST Type Strictness**
   - **Issue**: Spec says Array\<String\>, impl uses Iterable\[Any\]
   - **Solution**: Consider stricter typing

---

## 10. Proposed Changes

### Immediate (PR #2733 Follow-up)

```python
# 1. Move normalization from rpc_server.py to schemas.py
# 2. Normalize at all ingestion points per ADR 0015
```

### Short-term

```python
# Update DeviceDescription TypedDict
class DeviceDescription(TypedDict, total=False):
    TYPE: Required[str]
    ADDRESS: Required[str]
    # Change from Required to optional per spec
    PARAMSETS: list[str]
    # Document CHILDREN normalization requirement
    CHILDREN: list[str]  # Always normalized to list at ingestion
    # Uncomment commonly used fields
    VERSION: int
    FLAGS: int
    PARENT_TYPE: str | None
    INDEX: int | None
    # ... rest unchanged ...
```

### Long-term

```python
# Update ParameterData TypedDict
class ParameterData(TypedDict, total=False):
    # ... existing fields ...
    # Add missing spec fields
    TAB_ORDER: int | None
    CONTROL: str | None
    # Fix SPECIAL type if needed
    SPECIAL: list[dict[str, Any]]  # Per spec: Array<Struct{ID, VALUE}>
```

---

## References

- [HM_XmlRpc_API.pdf V2.16](./tmp/HM_XmlRpc_API.pdf): Primary specification
- [HMIP_XmlRpc_API_Addendum.pdf V2.10](./tmp/HMIP_XmlRpc_API_Addendum.pdf): HmIP extensions
- [PR #2733](https://github.com/sukramj/aiohomematic/pull/2733): CHILDREN normalization fix
- [ADR 0015: Description Normalization](0015-description-normalization-concept.md): Proposed solution

---

_Created: 2026-01-07_
_Author: API Compliance Review_
