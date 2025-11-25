# Backend Detection

This document describes the backend detection module for aiohomematic.

## Overview

The backend detection module (`aiohomematic.backend_detection`) provides functionality to detect the type of Homematic backend (CCU or Homegear/PyDevCCU) and discover available interfaces without requiring a fully initialized environment.

This is useful for:

- Auto-discovery during initial setup
- Configuration validation
- Diagnostic tools

## Supported Backends

| Backend      | Description              | Detection Method               |
| ------------ | ------------------------ | ------------------------------ |
| **CCU**      | Homematic CCU3/CCU2      | Version string like "3.61.345" |
| **Homegear** | Homegear software        | Version contains "Homegear"    |
| **PyDevCCU** | Development CCU emulator | Version contains "pydevccu"    |

## Ports Probed

The detection probes the following ports:

| Interface    | Non-TLS Port | TLS Port |
| ------------ | ------------ | -------- |
| HmIP-RF      | 2010         | 42010    |
| BidCos-RF    | 2001         | 42001    |
| BidCos-Wired | 2000         | 42000    |

For CCU backends, JSON-RPC is also queried on:

- Port 80 (HTTP)
- Port 443 (HTTPS)

## Detection Algorithm

```
1. Probe XML-RPC ports in order (non-TLS first, then TLS)
2. For each port:
   a. Call system.listMethods() to verify connection
   b. Call getVersion() if available
   c. Determine backend type from version string

3. If Homegear/PyDevCCU detected:
   - Return with only BidCos-RF interface

4. If CCU detected:
   - Query JSON-RPC for available interfaces
   - Return with discovered interfaces
```

## Usage

### Basic Usage

```python
from aiohomematic.backend_detection import detect_backend, DetectionConfig

config = DetectionConfig(
    host="192.168.1.100",
    username="admin",
    password="secret",
)

result = await detect_backend(config=config)

if result:
    print(f"Backend: {result.backend}")
    print(f"Interfaces: {result.available_interfaces}")
    print(f"Port: {result.detected_port}")
    print(f"TLS: {result.tls}")
else:
    print("No backend found")
```

### Configuration Options

```python
@dataclass
class DetectionConfig:
    host: str                      # Required: Host address
    username: str = ""             # Optional: Username for authentication
    password: str = ""             # Optional: Password for authentication
    request_timeout: float = 5.0   # Optional: Connection timeout in seconds
    verify_tls: bool = False       # Optional: Verify TLS certificates
```

### Result Structure

```python
@dataclass
class BackendDetectionResult:
    backend: Backend              # CCU, HOMEGEAR, or PYDEVCCU
    available_interfaces: tuple[Interface, ...]  # Detected interfaces
    detected_port: int            # Port where backend was found
    tls: bool                     # Whether TLS is used
    host: str                     # Host address
    version: str | None           # Backend version string
    auth_enabled: bool | None     # Whether auth is enabled (CCU only)
```

### Using with aiohttp Session

You can provide an existing aiohttp `ClientSession` to reuse connections:

```python
import aiohttp
from aiohomematic.backend_detection import detect_backend, DetectionConfig

async with aiohttp.ClientSession() as session:
    config = DetectionConfig(host="192.168.1.100")
    result = await detect_backend(config=config, client_session=session)
```

## Logging

All detection operations are logged at INFO level:

```
detect_backend: Starting detection for host 192.168.1.100
detect_backend: Probing 192.168.1.100:2010 (TLS=False, interface=HmIP-RF)
detect_backend: Found version '3.61.345' on port 2010
detect_backend: Detected backend type: CCU
detect_backend: Querying JSON-RPC at http://192.168.1.100:80/api/homematic.cgi
detect_backend: Found interfaces via JSON-RPC: (Interface.HMIP_RF, Interface.BIDCOS_RF)
```

## Error Handling

The detection module catches all exceptions internally and returns `None` if no backend can be detected. Errors are logged at INFO level:

```python
result = await detect_backend(config=config)

if result is None:
    # No backend found - check logs for details
    print("Could not detect backend")
```

## Examples

### Detect CCU with Multiple Interfaces

```python
config = DetectionConfig(
    host="192.168.1.100",
    username="Admin",
    password="secret123",
)

result = await detect_backend(config=config)

# Result:
# BackendDetectionResult(
#     backend=<Backend.CCU>,
#     available_interfaces=(Interface.HMIP_RF, Interface.BIDCOS_RF, Interface.BIDCOS_WIRED),
#     detected_port=2010,
#     tls=False,
#     host="192.168.1.100",
#     version="3.61.345",
#     auth_enabled=True,
# )
```

### Detect Homegear

```python
config = DetectionConfig(host="192.168.1.100")

result = await detect_backend(config=config)

# Result:
# BackendDetectionResult(
#     backend=<Backend.HOMEGEAR>,
#     available_interfaces=(Interface.BIDCOS_RF,),
#     detected_port=2010,
#     tls=False,
#     host="192.168.1.100",
#     version="Homegear 0.8.0",
#     auth_enabled=None,
# )
```

### Detect with TLS

```python
config = DetectionConfig(
    host="192.168.1.100",
    verify_tls=True,  # Verify TLS certificates
)

result = await detect_backend(config=config)

if result and result.tls:
    print(f"Backend found on TLS port {result.detected_port}")
```

## Integration with CentralConfig

After detection, you can use the result to create a `CentralConfig`:

```python
from aiohomematic.backend_detection import detect_backend, DetectionConfig
from aiohomematic.central import CentralConfig
from aiohomematic.client import InterfaceConfig

# Detect backend
detection_config = DetectionConfig(
    host="192.168.1.100",
    username="admin",
    password="secret",
)
result = await detect_backend(config=detection_config)

if result:
    # Create interface configs from detected interfaces
    interface_configs = frozenset(
        InterfaceConfig(
            central_name="my-ccu",
            interface=iface,
            port=_get_port_for_interface(iface, result.tls),
        )
        for iface in result.available_interfaces
    )

    # Create central config
    central_config = CentralConfig(
        name="my-ccu",
        host=result.host,
        username=detection_config.username,
        password=detection_config.password,
        central_id="unique-id",
        interface_configs=interface_configs,
        tls=result.tls,
    )
```

## Limitations

- Detection requires network access to the backend
- JSON-RPC interface query requires valid credentials for CCU with authentication enabled
- Unknown interfaces returned by the backend are skipped
- The module does not cache detection results
