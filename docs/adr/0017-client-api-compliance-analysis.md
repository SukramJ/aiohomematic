# ADR 0017: Client Implementation API Compliance Analysis

## Status

Analysis (Informational)

## Purpose

This document analyzes the aiohomematic client implementation against the official eQ-3 XML-RPC API specifications:

- **HM_XmlRpc_API.pdf** (V2.16): Primary HomeMatic specification
- **HMIP_XmlRpc_API_Addendum.pdf** (V2.10): HomeMatic IP extensions

This analysis focuses on the client layer (RPC methods, error handling, backend implementations) complementing ADR 0016 which covers data structures.

---

## 1. Architecture Overview

### Client Layer Structure

```
aiohomematic/client/
├── backends/               # Backend implementations
│   ├── ccu.py             # CcuBackend (CCU3/CCU2)
│   ├── homegear.py        # HomegearBackend
│   ├── json_ccu.py        # JsonCcuBackend (JSON-RPC only)
│   └── protocol.py        # BackendProtocol interface
├── handlers/              # Operation handlers
│   ├── device_ops.py      # DeviceHandler (values, paramsets)
│   ├── link_mgmt.py       # LinkHandler (direct links)
│   ├── metadata.py        # MetadataHandler
│   ├── firmware.py        # FirmwareHandler
│   ├── programs.py        # ProgramHandler
│   └── sysvars.py         # SysvarHandler
├── rpc_proxy.py           # AioXmlRpcProxy (XML-RPC transport)
├── json_rpc.py            # AioJsonRpcAioHttpClient (JSON-RPC)
├── _rpc_errors.py         # Error mapping utilities
└── circuit_breaker.py     # Connection circuit breaker
```

---

## 2. XML-RPC Method Compliance

### 2.1 Device Discovery Methods

| Spec Method            | Signature (Spec)                            | Implementation                        | Status       |
| ---------------------- | ------------------------------------------- | ------------------------------------- | ------------ |
| `listDevices`          | `(interface_id) → Array<DeviceDescription>` | `CcuBackend.list_devices()`           | ✅ Compliant |
| `getDeviceDescription` | `(address) → DeviceDescription`             | `CcuBackend.get_device_description()` | ✅ Compliant |
| `deleteDevice`         | `(address, flags) → void`                   | ❌ Not implemented                    | ⚠️ Missing   |

**Note on `deleteDevice`**: The spec defines flags for physical device removal. This is intentionally not exposed as it's a destructive operation.

### 2.2 Paramset Methods

| Spec Method              | Signature (Spec)                                | Implementation                          | Status       |
| ------------------------ | ----------------------------------------------- | --------------------------------------- | ------------ |
| `getParamsetDescription` | `(address, paramset_key) → ParamsetDescription` | `CcuBackend.get_paramset_description()` | ✅ Compliant |
| `getParamset`            | `(address, paramset_key) → Struct`              | `CcuBackend.get_paramset()`             | ✅ Compliant |
| `putParamset`            | `(address, key, set) → void`                    | `CcuBackend.put_paramset()`             | ✅ Compliant |
| `putParamset` (with rx)  | `(address, key, set, rx_mode) → void`           | `CcuBackend.put_paramset(rx_mode=...)`  | ✅ Compliant |

**HmIP Extension**: `putParamset` supports optional `rx_mode` parameter for controlling transmission timing.

### 2.3 Value Methods

| Spec Method | Signature (Spec)                              | Implementation                      | Status       |
| ----------- | --------------------------------------------- | ----------------------------------- | ------------ |
| `getValue`  | `(address, value_key) → value`                | `CcuBackend.get_value()`            | ✅ Compliant |
| `setValue`  | `(address, value_key, value) → void`          | `CcuBackend.set_value()`            | ✅ Compliant |
| `setValue`  | `(address, value_key, value, rx_mode) → void` | `CcuBackend.set_value(rx_mode=...)` | ✅ Compliant |

**HmIP Extension**: `setValue` supports optional `rx_mode` parameter.

### 2.4 System Methods

| Spec Method          | Signature (Spec)              | Implementation                  | Status       |
| -------------------- | ----------------------------- | ------------------------------- | ------------ |
| `init`               | `(url, interface_id) → Array` | `CcuBackend.init_proxy()`       | ✅ Compliant |
| `init` (deinit)      | `(url) → void`                | `CcuBackend.deinit_proxy()`     | ✅ Compliant |
| `ping`               | `(caller_id) → Boolean`       | `CcuBackend.check_connection()` | ✅ Compliant |
| `getVersion`         | `() → String`                 | Via `system.listMethods`        | ✅ Compliant |
| `system.listMethods` | `() → Array<String>`          | `AioXmlRpcProxy.do_init()`      | ✅ Compliant |
| `system.multicall`   | `(Array<Struct>) → Array`     | Python xmlrpc.client built-in   | ✅ Compliant |

### 2.5 Link Methods

| Spec Method    | Signature (Spec)                               | Implementation                 | Status       |
| -------------- | ---------------------------------------------- | ------------------------------ | ------------ |
| `addLink`      | `(sender, receiver, name, description) → void` | `LinkHandler.add_link()`       | ✅ Compliant |
| `removeLink`   | `(sender, receiver) → void`                    | `LinkHandler.remove_link()`    | ✅ Compliant |
| `getLinkPeers` | `(address) → Array<String>`                    | `LinkHandler.get_link_peers()` | ✅ Compliant |
| `getLinks`     | `(address, flags) → Array<Struct>`             | `LinkHandler.get_links()`      | ✅ Compliant |
| `getLinkInfo`  | `(sender, receiver) → Struct`                  | ❌ Not implemented             | ⚠️ Missing   |
| `setLinkInfo`  | `(sender, receiver, name, description) → void` | ❌ Not implemented             | ⚠️ Missing   |

### 2.6 Metadata Methods

| Spec Method      | Signature (Spec)                   | Implementation                   | Status       |
| ---------------- | ---------------------------------- | -------------------------------- | ------------ |
| `getMetadata`    | `(address, data_id) → value`       | `MetadataHandler.get_metadata()` | ✅ Compliant |
| `setMetadata`    | `(address, data_id, value) → void` | `MetadataHandler.set_metadata()` | ✅ Compliant |
| `deleteMetadata` | `(address, data_id) → void`        | ❌ Not implemented               | ⚠️ Missing   |
| `getAllMetadata` | `(address) → Struct`               | ❌ Not implemented               | ⚠️ Missing   |

### 2.7 Install Mode Methods

| Spec Method      | Signature (Spec)                               | Implementation                       | Status       |
| ---------------- | ---------------------------------------------- | ------------------------------------ | ------------ |
| `getInstallMode` | `() → Integer`                                 | `MetadataHandler.get_install_mode()` | ✅ Compliant |
| `setInstallMode` | `(on, time, mode) → void`                      | `MetadataHandler.set_install_mode()` | ✅ Compliant |
| `setInstallMode` | `(on, time, address) → void` (device-specific) | `MetadataHandler.set_install_mode()` | ✅ Compliant |

**HmIP Extension**: `setInstallModeWithWhitelist` for HmIP device pairing is implemented via JSON-RPC (`set_install_mode_hmip`).

### 2.8 Firmware Methods

| Spec Method       | Signature (Spec)             | Implementation                        | Status       |
| ----------------- | ---------------------------- | ------------------------------------- | ------------ |
| `updateFirmware`  | `(address) → Boolean`        | `CcuBackend.update_device_firmware()` | ✅ Compliant |
| `installFirmware` | `(address) → Boolean` (HmIP) | `CcuBackend.update_device_firmware()` | ✅ Compliant |

**Note**: Implementation tries `installFirmware` first (HmIP), falls back to `updateFirmware` (BidCos).

### 2.9 Additional Methods (Not in Spec but Implemented)

| Method                    | Implementation                               | Notes                  |
| ------------------------- | -------------------------------------------- | ---------------------- |
| `reportValueUsage`        | `CcuBackend.report_value_usage()`            | Homegear extension     |
| `clientServerInitialized` | `HomegearBackend.check_connection()`         | Homegear-specific ping |
| `getAllSystemVariables`   | `HomegearBackend.get_all_system_variables()` | Homegear extension     |
| `getSystemVariable`       | `HomegearBackend.get_system_variable()`      | Homegear extension     |
| `setSystemVariable`       | `HomegearBackend.set_system_variable()`      | Homegear extension     |
| `deleteSystemVariable`    | `HomegearBackend.delete_system_variable()`   | Homegear extension     |

---

## 3. XML-RPC Callback Compliance

### 3.1 Callback Methods (RPC Server → aiohomematic)

| Spec Method     | Signature (Spec)                                   | Implementation                 | Status       |
| --------------- | -------------------------------------------------- | ------------------------------ | ------------ |
| `event`         | `(interface_id, address, value_key, value) → void` | `RPCFunctions.event()`         | ✅ Compliant |
| `newDevices`    | `(interface_id, dev_descriptions) → void`          | `RPCFunctions.newDevices()`    | ✅ Compliant |
| `deleteDevices` | `(interface_id, addresses) → void`                 | `RPCFunctions.deleteDevices()` | ✅ Compliant |
| `updateDevice`  | `(interface_id, address, hint) → void`             | `RPCFunctions.updateDevice()`  | ✅ Compliant |
| `replaceDevice` | `(interface_id, old_address, new_address) → void`  | `RPCFunctions.replaceDevice()` | ✅ Compliant |
| `readdedDevice` | `(interface_id, addresses) → void`                 | `RPCFunctions.readdedDevice()` | ✅ Compliant |
| `listDevices`   | `(interface_id) → Array<DeviceDescription>`        | `RPCFunctions.listDevices()`   | ✅ Compliant |
| `error`         | `(interface_id, error_code, msg) → void`           | `RPCFunctions.error()`         | ✅ Compliant |

**Note**: Method names intentionally use camelCase to match the HomeMatic XML-RPC protocol specification.

### 3.2 UpdateDevice Hints

| Spec Value | Constant            | Implementation              | Status       |
| ---------- | ------------------- | --------------------------- | ------------ |
| 0          | Firmware update     | `UpdateDeviceHint.FIRMWARE` | ✅ Compliant |
| 1          | Link partner change | `UpdateDeviceHint.LINKS`    | ✅ Compliant |

---

## 4. Error Code Compliance

### 4.1 XML-RPC Fault Codes

| Spec Code | Description                 | Implementation                             | Status       |
| --------- | --------------------------- | ------------------------------------------ | ------------ |
| -1        | Generic error (UNREACH)     | `_XmlRpcFaultCode.GENERIC_ERROR`           | ✅ Compliant |
| -2        | Unknown device              | `_XmlRpcFaultCode.UNKNOWN_DEVICE`          | ✅ Compliant |
| -3        | Unknown paramset            | `_XmlRpcFaultCode.UNKNOWN_PARAMSET`        | ✅ Compliant |
| -4        | Device address expected     | `_XmlRpcFaultCode.ADDRESS_EXPECTED`        | ✅ Compliant |
| -5        | Unknown parameter           | `_XmlRpcFaultCode.UNKNOWN_PARAMETER`       | ✅ Compliant |
| -6        | Operation not supported     | `_XmlRpcFaultCode.OPERATION_NOT_SUPPORTED` | ✅ Compliant |
| -7        | Update not possible         | `_XmlRpcFaultCode.UPDATE_NOT_POSSIBLE`     | ✅ Compliant |
| -8        | Insufficient DutyCycle      | `_XmlRpcFaultCode.INSUFFICIENT_DUTYCYCLE`  | ✅ Compliant |
| -9        | Device out of range         | `_XmlRpcFaultCode.DEVICE_OUT_OF_RANGE`     | ✅ Compliant |
| -10       | Transmission pending (HmIP) | `_XmlRpcFaultCode.TRANSMISSION_PENDING`    | ✅ Compliant |

### 4.2 Error Handling Architecture

```python
# rpc_proxy.py: Exception hierarchy
BaseHomematicException
├── AuthFailure           # Authentication errors (401, unauthorized)
├── ClientException       # Generic client errors
├── NoConnectionException # Network/connection errors
│   └── CircuitBreakerOpenException  # Circuit breaker triggered
├── InternalBackendException  # Backend internal errors (-32603)
└── UnsupportedException  # Unsupported method called

# Error mapping chain
XML-RPC Fault → _rpc_errors.map_xmlrpc_fault() → Domain Exception
JSON-RPC Error → _rpc_errors.map_jsonrpc_error() → Domain Exception
Transport Error → _rpc_errors.map_transport_error() → Domain Exception
```

### 4.3 Expected vs Unexpected Errors

The implementation distinguishes between expected and unexpected errors for logging:

```python
# Expected during normal operation (WARNING level)
_EXPECTED_XMLRPC_FAULT_CODES = frozenset({
    _XmlRpcFaultCode.GENERIC_ERROR,      # -1: Device temporarily unreachable
    _XmlRpcFaultCode.UNKNOWN_DEVICE,     # -2: Device removed
    _XmlRpcFaultCode.UNKNOWN_PARAMSET,   # -3: Paramset not available
    _XmlRpcFaultCode.UNKNOWN_PARAMETER,  # -5: Parameter not found
    _XmlRpcFaultCode.DEVICE_OUT_OF_RANGE,# -9: Device out of range
    _XmlRpcFaultCode.TRANSMISSION_PENDING,# -10: HmIP transmission pending
})
```

---

## 5. Transport Layer Compliance

### 5.1 XML-RPC Transport

| Requirement                         | Implementation                        | Status       |
| ----------------------------------- | ------------------------------------- | ------------ |
| ISO-8859-1 encoding                 | `encoding=ISO_8859_1` in ServerProxy  | ✅ Compliant |
| TLS support                         | `get_tls_context()` with SSLContext   | ✅ Compliant |
| Certificate verification (optional) | `verify_tls` parameter                | ✅ Compliant |
| Custom headers                      | `headers` parameter in AioXmlRpcProxy | ✅ Compliant |
| Async execution                     | ThreadPoolExecutor for blocking calls | ✅ Compliant |

### 5.2 Circuit Breaker Pattern

The implementation includes a circuit breaker to prevent retry storms:

```python
class CircuitBreaker:
    """
    States:
    - CLOSED: Normal operation
    - HALF_OPEN: Testing recovery
    - OPEN: Rejecting requests

    Bypass methods (allowed even when open):
    - getVersion
    - clientServerInitialized
    - init
    - ping
    - system.listMethods
    """
```

### 5.3 Connection State Management

```python
class CentralConnectionState:
    """
    Tracks connection issues per interface.
    - add_issue(): Mark interface as having connection problems
    - remove_issue(): Clear connection problem flag
    - has_issue(): Check if interface has problems
    """
```

---

## 6. Backend-Specific Compliance

### 6.1 CCU Backend (ccu.py)

| Feature                    | Implementation                                | Status       |
| -------------------------- | --------------------------------------------- | ------------ |
| XML-RPC for device ops     | `_proxy`, `_proxy_read`                       | ✅ Compliant |
| JSON-RPC for metadata      | `_json_rpc`                                   | ✅ Compliant |
| Backup support             | `create_backup_and_download()`                | ✅ Extended  |
| Install mode (HmIP/BidCos) | Both JSON-RPC and XML-RPC paths               | ✅ Compliant |
| Firmware updates           | `installFirmware` + `updateFirmware` fallback | ✅ Compliant |

### 6.2 Homegear Backend (homegear.py)

| Feature                      | Implementation                 | Status       |
| ---------------------------- | ------------------------------ | ------------ |
| XML-RPC only                 | `_proxy`, `_proxy_read`        | ✅ Compliant |
| System variables via XML-RPC | `get/set/deleteSystemVariable` | ✅ Extended  |
| Connection check             | `clientServerInitialized`      | ✅ Extended  |
| No JSON-RPC                  | Intentionally excluded         | ✅ Correct   |

### 6.3 JsonCCU Backend (json_ccu.py)

| Feature                  | Implementation             | Status      |
| ------------------------ | -------------------------- | ----------- |
| JSON-RPC for all ops     | `_json_rpc`                | ✅ Extended |
| No XML-RPC proxy         | `NullRpcProxy` placeholder | ✅ Correct  |
| Limited paramset support | Via JSON-RPC methods       | ⚠️ Partial  |

---

## 7. Missing or Incomplete Implementations

### 7.1 Not Implemented (Intentional)

| Method                 | Reason                             |
| ---------------------- | ---------------------------------- |
| `deleteDevice`         | Destructive operation, not exposed |
| `activateLinkParamset` | Rarely used, complex               |
| `setTempKey`           | Security-sensitive                 |
| `setBidcosInterface`   | Low-level configuration            |
| `changeKey`            | Security-sensitive key management  |

### 7.2 Not Implemented (Could Add)

| Method                 | Priority | Use Case                          |
| ---------------------- | -------- | --------------------------------- |
| `getLinkInfo`          | Low      | Display link metadata             |
| `setLinkInfo`          | Low      | Update link metadata              |
| `deleteMetadata`       | Low      | Clean up metadata                 |
| `getAllMetadata`       | Low      | Bulk metadata retrieval           |
| `listBidcosInterfaces` | Medium   | Multi-interface management        |
| `getServiceMessages`   | Medium   | XML-RPC variant (JSON-RPC exists) |

---

## 8. Recommendations

### 8.1 High Priority

1. **Data Normalization** (ADR 0015, 0016)

   - Implement normalization at ingestion points
   - Add schema versioning for cache migration

2. **Error Message Improvements**
   - Map all fault codes to user-friendly messages
   - Add German translations for error messages

### 8.2 Medium Priority

3. **Add `listBidcosInterfaces`**

   - Useful for multi-interface setups
   - Returns interface hardware information

4. **Add XML-RPC `getServiceMessages`**
   - Alternative to JSON-RPC for service message retrieval
   - Better for Homegear compatibility

### 8.3 Low Priority

5. **Add Link Metadata Methods**

   - `getLinkInfo` / `setLinkInfo` for link descriptions
   - Lower priority as links are rarely modified

6. **Add Metadata Cleanup Methods**
   - `deleteMetadata` / `getAllMetadata`
   - Useful for advanced users

---

## 9. Parameter Type Handling

### 9.1 Type Conversion

The implementation handles Homematic type conversions:

```python
# aiohomematic/model/support.py
def convert_value(value: Any, parameter_type: ParameterType) -> Any:
    """Convert value to appropriate type based on parameter definition."""
    if parameter_type == ParameterType.BOOL:
        return bool(value)
    if parameter_type == ParameterType.FLOAT:
        return float(value)
    if parameter_type == ParameterType.INTEGER:
        return int(value)
    if parameter_type == ParameterType.ENUM:
        return int(value)  # Enum index
    return value  # STRING, ACTION
```

### 9.2 RX_MODE Handling

```python
class CommandRxMode(IntFlag):
    """Receive mode for commands (per HmIP spec)."""
    ALWAYS = 0x01
    BURST = 0x02
    CONFIG = 0x04
    WAKEUP = 0x08
    LAZY_CONFIG = 0x10

# Usage in setValue/putParamset
if rx_mode:
    await self._proxy.setValue(address, parameter, value, rx_mode)
else:
    await self._proxy.setValue(address, parameter, value)
```

---

## 10. Summary

### Overall Compliance Score

| Category                 | Implemented | Total  | Compliance |
| ------------------------ | ----------- | ------ | ---------- |
| Device Discovery Methods | 2           | 3      | 67%        |
| Paramset Methods         | 4           | 4      | 100%       |
| Value Methods            | 2           | 2      | 100%       |
| System Methods           | 5           | 5      | 100%       |
| Link Methods             | 4           | 6      | 67%        |
| Metadata Methods         | 2           | 4      | 50%        |
| Install Mode Methods     | 2           | 2      | 100%       |
| Firmware Methods         | 2           | 2      | 100%       |
| Callback Methods         | 8           | 8      | 100%       |
| Error Codes              | 10          | 10     | 100%       |
| **Total**                | **41**      | **46** | **89%**    |

### Key Findings

1. **Core Functionality**: All essential methods for device control are implemented
2. **Error Handling**: Full compliance with spec error codes
3. **Callbacks**: Complete implementation of all callback methods
4. **Extensions**: Proper support for HmIP extensions (rx_mode, installFirmware)
5. **Gaps**: Minor gaps in link metadata and advanced metadata methods

### Action Items

| Priority | Task                             | Reference   |
| -------- | -------------------------------- | ----------- |
| High     | Implement data normalization     | ADR 0015    |
| Medium   | Add `listBidcosInterfaces`       | Section 7.2 |
| Low      | Add link/metadata helper methods | Section 7.2 |

---

## References

- [HM_XmlRpc_API.pdf V2.16](./tmp/HM_XmlRpc_API.pdf): Primary specification
- [HMIP_XmlRpc_API_Addendum.pdf V2.10](./tmp/HMIP_XmlRpc_API_Addendum.pdf): HmIP extensions
- [ADR 0015: Description Normalization](0015-description-normalization-concept.md)
- [ADR 0016: API Compliance Analysis (Data Structures)](0016-api-compliance-analysis.md)

---

_Created: 2026-01-07_
_Author: Client Implementation Review_
