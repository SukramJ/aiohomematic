# Docstring Templates for aiohomematic

This document provides ready-to-use docstring templates for common patterns in the aiohomematic codebase. Copy and adapt these templates when writing new code.

**Related Documents**:

- [Docstring Standards](./docstring_standards.md) - Complete style guide
- [Docstring Audit](./docstring_audit.md) - Module categorization

---

## Module Docstrings

### Template: Tier 1 (Core API Modules)

```python
"""
{Brief one-line description ending with period}.

Overview
--------
{2-3 paragraphs explaining:
- Purpose and responsibilities
- Key design decisions
- How it fits into the architecture}

{Optional section: Architecture/Subpackages/Components}
-----------------
{Bulleted list or paragraphs describing major components}

Public API
----------
- `ClassName`: Brief description.
- `function_name`: Brief description.

Quick start
-----------
{Short code example showing typical usage:}

    from aiohomematic.{package} import SomeClass

    instance = SomeClass(param1="value", param2=42)
    result = await instance.do_something()

Notes
-----
{Optional additional information, warnings, or references}
"""
```

**Use for**: `aiohomematic/__init__.py`, `central/__init__.py`, `client/__init__.py`, `model/__init__.py`, `model/hub/__init__.py`

### Template: Tier 2 (Coordinator/Internal Modules)

```python
"""
{Brief one-line description ending with period}.

{1-2 paragraphs providing context and explaining key responsibilities}

Key features:
- Feature or responsibility 1
- Feature or responsibility 2
- Feature or responsibility 3
"""
```

**Use for**: Coordinators, store modules, internal implementations

**Example**:

```python
"""
Device coordinator for managing device lifecycle and operations.

This module provides centralized device management including device creation,
registration, removal, and device-related operations. The DeviceCoordinator
works in conjunction with DeviceRegistry to maintain the runtime device model.

Key features:
- Device creation from descriptions
- Device registration and lookup
- Device removal and cleanup
- Device update operations
"""
```

### Template: Tier 3 (Utility/Generic Modules)

```python
"""
{Brief description of module purpose}.

Public API of this module is defined by __all__.
"""
```

**Use for**: Utilities, constants, generic implementations, simple modules

**Examples**:

```python
"""
Constants and enumerations for aiohomematic.

Public API of this module is defined by __all__.
"""
```

```python
"""
Generic sensor data points for numeric and text values.

Public API of this module is defined by __all__.
"""
```

---

## Class Docstrings

### Template: Protocol/Interface

```python
class SomeProtocol(Protocol):
    """Protocol for {brief description of contract}."""
```

**Examples**:

```python
class DeviceProvider(Protocol):
    """Protocol for providing access to device registry."""

class CentralInfo(Protocol):
    """Protocol for central system information."""

class TaskScheduler(Protocol):
    """Protocol for scheduling background tasks."""
```

### Template: Base Class

```python
class BaseClassName(ABC):
    """
    Base class for {purpose}.

    {Optional: Explain inheritance contract and what subclasses must implement}
    """
```

**Examples**:

```python
class BaseDataPoint(ABC):
    """
    Base class for all data point implementations.

    Subclasses must implement value property and update methods.
    """

class CustomDataPoint(BaseDataPoint):
    """Base class for custom device-specific data points."""
```

### Template: Concrete Class (Single Line)

```python
class ClassName:
    """Brief description of what this class represents or does."""
```

**Examples**:

```python
class Device:
    """Represents a Homematic device with channels and data points."""

class Channel:
    """Represents a device channel containing data points."""

class SchedulerJob:
    """Scheduled background task with interval-based execution."""
```

### Template: Data Class

```python
@dataclass
class ConfigClass:
    """Configuration for {purpose}."""
```

**Examples**:

```python
@dataclass
class CentralConfig:
    """Configuration for central unit initialization."""

@dataclass
class InterfaceConfig:
    """Configuration for a single interface connection."""
```

---

## Method and Function Docstrings

### Template: Simple Method (One-Line)

```python
def method_name(self, param: ParamType) -> ReturnType:
    """Return {what is returned}."""
```

**Examples**:

```python
def get_device_by_address(self, address: str) -> Device | None:
    """Return device by address."""

def is_connected(self) -> bool:
    """Return connection status."""

def clear_cache(self) -> None:
    """Clear all cached data."""
```

### Template: Property

```python
@property
def property_name(self) -> PropertyType:
    """Return the {property description}."""
```

**Examples**:

```python
@property
def device_address(self) -> str:
    """Return the device address."""

@property
def available(self) -> bool:
    """Return whether device is available."""

@config_property
def value(self) -> Any:
    """Return current data point value."""
```

### Template: Complex Method with Args/Returns

```python
def method_name(
    self,
    *,
    param1: Type1,
    param2: Type2,
    optional_param: Type3 = default,
) -> ReturnType:
    """
    {Brief description of what the method does}.

    Args:
        param1: Description of param1
        param2: Description of param2
        optional_param: Description of optional parameter

    Returns:
        Description of return value.

    Raises:
        ExceptionType: When this exception occurs.
    """
```

**Examples**:

```python
def create_device(
    self,
    *,
    interface_id: str,
    device_address: str,
    device_type: str,
    force_create: bool = False,
) -> Device:
    """
    Create and register a new device instance.

    Args:
        interface_id: Interface identifier (e.g., "hmip-rf")
        device_address: Unique device address
        device_type: Device type identifier
        force_create: Force creation even if device exists

    Returns:
        Created or existing Device instance.

    Raises:
        DeviceCreationException: If device creation fails.
    """
```

### Template: Simple **init** Method

```python
def __init__(self) -> None:
    """Initialize the {class name}."""
```

**Examples**:

```python
def __init__(self) -> None:
    """Initialize the coordinator."""

def __init__(self) -> None:
    """Initialize the event bus."""
```

### Template: Complex **init** Method

```python
def __init__(
    self,
    *,
    param1: Type1,
    param2: Type2,
    param3: Type3,
) -> None:
    """
    Initialize the {class name}.

    Args:
        param1: Description of param1
        param2: Description of param2
        param3: Description of param3
    """
```

**Examples**:

```python
def __init__(
    self,
    *,
    central_info: CentralInfo,
    device_provider: DeviceProvider,
    client_provider: ClientProvider,
) -> None:
    """
    Initialize the device coordinator.

    Args:
        central_info: System information provider
        device_provider: Device registry access
        client_provider: Client lookup functionality
    """
```

### Template: Validator Function

```python
def validate_something(value: ValueType, /) -> ValueType:
    """Validate {what is being validated}."""
```

**Examples**:

```python
def channel_address(value: str, /) -> str:
    """Validate channel address format."""

def positive_int(value: int, /) -> int:
    """Validate value is positive integer."""

def interface_id(value: str, /) -> str:
    """Validate interface identifier."""
```

### Template: Decorator

```python
def decorator_name[**P, R](
    func: Callable[P, R] | None = None,
    /,
    *,
    param1: Type1 = default1,
    param2: Type2 = default2,
) -> DecoratorReturnType:
    """
    {Brief description of decorator purpose}.

    {Explanation of behavior and usage patterns}

    Can be used with or without parameters:
        @decorator_name
        @decorator_name(param1=value)

    Args:
        func: Function to decorate (when used without parameters)
        param1: Description of param1
        param2: Description of param2

    Returns:
        Decorated function or decorator function.
    """
```

**Example**:

```python
def inspector[**P, R](
    func: Callable[P, R] | None = None,
    /,
    *,
    log_level: int = logging.ERROR,
    re_raise: bool = True,
    is_service: bool = True,
) -> Callable[[Callable[P, R]], Callable[P, R]] | Callable[P, R]:
    """
    Decorator for exception handling and performance measurement.

    Works with both sync and async functions. Can be used with or without
    parameters:
        @inspector
        @inspector(log_level=logging.DEBUG)
        @inspector(re_raise=False, is_service=False)

    Args:
        func: Function to decorate (when used without parameters)
        log_level: Logging level for exceptions
        re_raise: Whether to re-raise caught exceptions
        is_service: Whether to mark as a service method (ha_service attribute).
            Service methods are user-invokable commands (e.g., turn_on, turn_off).
            Set False for internal methods (e.g., load_data_point_value).

    Returns:
        Decorated function or decorator function.
    """
```

---

## Test Docstrings

### Template: Test Module

```python
"""Tests for {module or feature being tested}."""
```

**Examples**:

```python
"""Tests for device coordinator functionality."""
"""Tests for custom climate data points."""
"""Tests for central unit lifecycle."""
```

### Template: Test Class

```python
class TestSomeFeature:
    """Test suite for {feature or class being tested}."""
```

**Examples**:

```python
class TestDeviceCoordinator:
    """Test suite for DeviceCoordinator."""

class TestCentralUnit:
    """Test suite for CentralUnit lifecycle."""
```

### Template: Test Function

```python
async def test_some_functionality(fixture_name):
    """Test {specific functionality being tested}."""
```

**Examples**:

```python
async def test_device_creation(factory):
    """Test device creation with valid parameters."""

def test_address_validation():
    """Test address validation with various inputs."""

async def test_connection_error_handling(central):
    """Test central handles connection errors gracefully."""
```

---

## Custom Data Point Docstrings

### Template: Custom Entity Class

```python
class CustomEntityName(CustomDataPoint):
    """Custom entity for {device type or purpose}."""
```

**Examples**:

```python
class CeClimate(CustomDataPoint):
    """Custom entity for thermostat and climate devices."""

class CeCover(CustomDataPoint):
    """Custom entity for blinds and shutters."""

class CeLight(CustomDataPoint):
    """Custom entity for dimmable and colored lights."""
```

---

## Calculated Data Point Docstrings

### Template: Calculated Entity

```python
class CalculatedEntityName(CalculatedDataPoint):
    """Calculated data point for {what is calculated}."""
```

**Examples**:

```python
class DewPoint(CalculatedDataPoint):
    """Calculated data point for dew point temperature."""

class OperatingVoltageLevel(CalculatedDataPoint):
    """Calculated data point for battery level percentage."""
```

---

## Quick Reference: Verb Usage

| Action      | Verb               | Example                                  |
| ----------- | ------------------ | ---------------------------------------- |
| Retrieving  | Return             | `"""Return the device address."""`       |
| Creating    | Initialize, Create | `"""Initialize the central unit."""`     |
| Validating  | Validate           | `"""Validate channel address format."""` |
| Checking    | Check              | `"""Check if device is ready."""`        |
| Converting  | Convert            | `"""Convert value to integer."""`        |
| Starting    | Start              | `"""Start the background scheduler."""`  |
| Stopping    | Stop               | `"""Stop all running tasks."""`          |
| Registering | Register           | `"""Register device in registry."""`     |
| Removing    | Remove             | `"""Remove device from registry."""`     |

**Avoid**: "Get", "Fetch", "Retrieve" - use "Return" instead for consistency.

---

## Anti-Patterns to Avoid

### ❌ Repeating Type Information

```python
# Bad
def get_address(self) -> str:
    """Return the address as a string."""

# Good
def get_address(self) -> str:
    """Return the device address."""
```

### ❌ Vague Docstrings

```python
# Bad
def process_data(self, data: dict[str, Any]) -> None:
    """Process the data."""

# Good
def process_data(self, data: dict[str, Any]) -> None:
    """Update device state from backend data."""
```

### ❌ Inconsistent Verbs

```python
# Bad - Mixed verbs
def get_device(self, address: str) -> Device:
    """Gets device."""

def fetch_channels(self) -> list[Channel]:
    """Fetches channels."""

# Good - Consistent imperative mood
def get_device(self, address: str) -> Device:
    """Return device by address."""

def fetch_channels(self) -> list[Channel]:
    """Return all device channels."""
```

### ❌ Missing Periods

```python
# Bad
def clear_cache(self) -> None:
    """Clear the cache"""

# Good
def clear_cache(self) -> None:
    """Clear the cache."""
```

---

**Last Updated**: 2025-11-24
**Version**: 1.0
