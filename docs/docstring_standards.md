# Docstring Standards for aiohomematic

This document defines the docstring conventions for the aiohomematic project. These standards ensure consistency, clarity, and maintainability across the codebase.

## Core Principles

1. **Short and Precise**: Docstrings should be concise yet informative
2. **Programmer-Focused**: Write for developers using or maintaining the code
3. **Type Hints First**: Rely on type annotations; avoid repeating type information in docstrings
4. **Consistency**: Follow established patterns for similar constructs

---

## General Rules

### Punctuation

- **Always end docstrings with a period** (`.`)
- Use proper sentence structure

### Sentence Structure

- **Functions/Methods**: Use imperative mood

  - ✅ `"""Return the device by address."""`
  - ❌ `"""Returns the device by address."""`
  - ❌ `"""Gets the device by address."""`

- **Classes**: Use declarative statements
  - ✅ `"""Represents a Homematic device."""`
  - ✅ `"""Base class for data points."""`
  - ✅ `"""Coordinator for managing device lifecycle."""`

### Verb Consistency

Use consistent verbs across the codebase:

| Action             | Preferred Verb     | Examples                              |
| ------------------ | ------------------ | ------------------------------------- |
| Retrieving data    | Return             | `"""Return the device address."""`    |
| Creating instances | Initialize, Create | `"""Initialize the central unit."""`  |
| Validation         | Validate           | `"""Validate the channel address."""` |
| Checking state     | Check              | `"""Check if device is ready."""`     |
| Converting         | Convert            | `"""Convert value to integer."""`     |

**Avoid**: "Get", "Fetch", "Retrieve" (use "Return" instead)

---

## Module-Level Docstrings

Module docstrings appear at the top of every Python file and describe the module's purpose.

### Tier 1: Core API Modules (Comprehensive)

**When to use**: Entry points and primary packages (`central/__init__.py`, `client/__init__.py`, `model/hub/__init__.py`)

**Structure**:

```python
"""
{Brief one-line description}.

Overview
--------
{2-3 paragraphs explaining purpose, responsibilities, and design philosophy}

Public API
----------
{List of key classes/functions exposed by this module}
- ClassName: Brief description
- function_name: Brief description

Quick start
-----------
{Short code example or usage pattern}

Notes
-----
{Optional additional information, warnings, or related modules}
"""
```

**Example**:

```python
"""
Central unit and core orchestration for Homematic CCU and compatible backends.

Overview
--------
This package provides the central coordination layer for aiohomematic. The
CentralUnit class manages client lifecycles, device creation, event handling,
and background tasks. It serves as the primary entry point for interacting
with Homematic systems.

Public API
----------
- CentralUnit: Main coordination class for managing all operations
- CentralConfig: Configuration dataclass for central initialization

Quick start
-----------
Typical usage is to create a CentralConfig, instantiate CentralUnit,
and call start():

    config = CentralConfig(name="ccu", host="192.168.1.100", ...)
    central = config.create_central()
    await central.start()
"""
```

### Tier 2: Coordinator/Internal Modules (Medium Detail)

**When to use**: Coordinators, stores, and internal implementation modules

**Structure**:

```python
"""
{Brief one-line description}.

{1-2 paragraphs with key details}

Key features:
- Feature 1
- Feature 2
- Feature 3
"""
```

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

### Tier 3: Utility/Generic Modules (Brief)

**When to use**: Utilities, constants, generic implementations, simple modules

**Structure**:

```python
"""
{Brief description of module purpose}.

Public API of this module is defined by __all__.
"""
```

**Example**:

```python
"""
Constants used by aiohomematic.

Public API of this module is defined by __all__.
"""
```

---

## Class Docstrings

### Protocols and Interfaces

**Pattern**: Describe the contract and purpose

```python
class DeviceProvider(Protocol):
    """Protocol for providing access to device registry."""

class CentralInfo(Protocol):
    """Protocol for central system information."""
```

### Base Classes

**Pattern**: Explain inheritance contract and what subclasses should implement

```python
class BaseDataPoint(ABC):
    """
    Base class for all data point implementations.

    Subclasses must implement value property and update methods.
    """

class BasePersistentFile(ABC):
    """
    Base class for persistent file storage.

    Provides caching and serialization for device/paramset descriptions.
    """
```

### Concrete Classes

**Pattern**: Describe what the class represents or does

```python
class Device:
    """Represents a Homematic device with channels and data points."""

class CentralUnit:
    """Central orchestration unit for managing Homematic backend connections."""

class SchedulerJob:
    """Scheduled background task with interval-based execution."""
```

### Data Classes

**Pattern**: Simple one-line description

```python
@dataclass
class CentralConfig:
    """Configuration for central unit initialization."""

@dataclass
class DeviceDescription:
    """Device metadata from backend."""
```

---

## Method and Function Docstrings

### Simple Methods (One-Line)

**When to use**:

- Getters, setters, properties
- Simple operations with obvious behavior
- Methods with 0-2 parameters
- Well-named methods where docstring adds little value

**Pattern**:

```python
def get_device_by_address(self, address: str) -> Device | None:
    """Return device by address."""

@property
def is_connected(self) -> bool:
    """Return connection status."""

def clear_cache(self) -> None:
    """Clear all cached data."""
```

### Complex Methods (Extended)

**When to use**:

- Methods with 3+ parameters
- Non-obvious behavior or side effects
- Methods requiring parameter explanation
- Methods with important return value details

**Pattern**:

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

### `__init__` Methods

**Simple constructors** (no or few parameters):

```python
def __init__(self) -> None:
    """Initialize the coordinator."""
```

**Complex constructors** (multiple parameters, DI):

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

### Validators

**Pattern**: Simple one-line

```python
def channel_address(value: str, /) -> str:
    """Validate channel address format."""

def positive_int(value: int, /) -> int:
    """Validate value is positive integer."""
```

### Decorators

**Pattern**: Explain purpose, behavior, and usage

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

## Property Docstrings

Properties should have concise docstrings:

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

---

## Test Module Docstrings

### Test Files

```python
"""Tests for device coordinator functionality."""
```

### Test Classes

```python
class TestDeviceCoordinator:
    """Test suite for DeviceCoordinator."""
```

### Test Functions

```python
async def test_device_creation(factory):
    """Test device creation with valid parameters."""

def test_address_validation():
    """Test address validation with various inputs."""
```

---

## Examples: Before and After

### Example 1: Inconsistent Module Docstring

**Before**:

```python
"""Module for data points implemented using the sensor category"""
```

**After**:

```python
"""
Generic sensor data points.

Public API of this module is defined by __all__.
"""
```

### Example 2: Inconsistent Method Docstrings

**Before**:

```python
def get_device(self, addr):
    """Gets device"""

def fetch_value(self, param):
    """Returns the value of param"""
```

**After**:

```python
def get_device(self, address: str) -> Device | None:
    """Return device by address."""

def fetch_value(self, parameter: str) -> Any:
    """Return parameter value."""
```

### Example 3: Missing **init** Documentation

**Before**:

```python
def __init__(self, central, addr, channel_no):
    """Init custom entity."""
```

**After**:

```python
def __init__(
    self,
    *,
    central: CentralUnit,
    device_address: str,
    channel_no: int,
) -> None:
    """
    Initialize custom climate entity.

    Args:
        central: Central unit instance
        device_address: Device address
        channel_no: Channel number
    """
```

---

## Anti-Patterns to Avoid

### ❌ Repeating Type Information

```python
# Bad: Type already in signature
def get_address(self) -> str:
    """Return the address as a string."""

# Good: Don't repeat types
def get_address(self) -> str:
    """Return the device address."""
```

### ❌ Vague or Redundant Docstrings

```python
# Bad: Adds no value
def process_data(self, data: dict[str, Any]) -> None:
    """Process the data."""

# Good: Explain what processing means
def process_data(self, data: dict[str, Any]) -> None:
    """Update device state from backend data."""
```

### ❌ Inconsistent Verb Usage

```python
# Bad: Inconsistent
def get_device(self, address: str) -> Device:
    """Gets device."""

def return_channels(self) -> list[Channel]:
    """Returns channels."""

def fetch_value(self, param: str) -> Any:
    """Fetches value."""

# Good: Consistent imperative mood
def get_device(self, address: str) -> Device:
    """Return device by address."""

def return_channels(self) -> list[Channel]:
    """Return all device channels."""

def fetch_value(self, parameter: str) -> Any:
    """Return parameter value."""
```

### ❌ Missing Periods

```python
# Bad: No period
def clear_cache(self) -> None:
    """Clear the cache"""

# Good: Always end with period
def clear_cache(self) -> None:
    """Clear the cache."""
```

---

## Tooling and Validation

### Ruff Configuration

The project uses `ruff` for both linting and formatting with the following docstring rules:

**Enabled Rules**:

- `D` (pydocstyle): All docstring conventions
- Line length: 120 characters
- Target version: Python 3.13

**Key Settings**:

- `D212`: Multi-line docstring summary starts on first line
- `D213`: Multi-line docstring summary starts on second line (incompatible with D212, ignored)
- Auto-fix enabled for most docstring issues

### Formatting Commands

**Format all code**:

```bash
ruff format aiohomematic/ aiohomematic_test_support/
```

**Check docstring compliance**:

```bash
ruff check --select D aiohomematic/ aiohomematic_test_support/
```

**Auto-fix docstring issues**:

```bash
ruff check --fix --select D aiohomematic/ aiohomematic_test_support/
```

**Check all rules**:

```bash
ruff check aiohomematic/ aiohomematic_test_support/
```

### Pre-commit Hooks

Docstring validation is enforced via pre-commit hooks. Run:

```bash
pre-commit run --all-files
```

This includes:

- `ruff` - Linting and auto-fixing
- `ruff-format` - Code formatting
- `mypy` - Type checking (validates type hints match docstrings)

### Formatting Standards Applied

All docstrings in this project follow these formatting rules:

1. **Multi-line Docstrings**: Opening quotes on same line as first text

   ```python
   """Brief summary here.

   Extended description continues here.
   """
   ```

2. **Blank Lines**: One blank line after last section in module docstrings

   ```python
   """Module docstring.

   Notes
   -----
   Final section here.

   """
   ```

3. **Punctuation**: All docstrings end with a period

   ```python
   """Initialize the coordinator."""  # ✓ Correct
   ```

4. **Line Length**: Docstrings respect 120 character line limit
   - Long descriptions wrap at word boundaries
   - Code examples may exceed but should be minimal

### Manual Review Checklist

When writing or reviewing docstrings:

- [ ] Ends with period
- [ ] Uses imperative mood (functions) or declarative (classes)
- [ ] Consistent verb usage (Return, not Get/Fetch)
- [ ] Appropriate detail level for complexity
- [ ] No type repetition from signature
- [ ] Proper grammar and spelling
- [ ] Formatted with `ruff format`
- [ ] Passes `ruff check --select D`

### CI/CD Integration

The project's CI pipeline validates:

- All code is formatted with `ruff format`
- All docstrings pass `ruff check --select D`
- Type hints are complete and match docstrings (`mypy --strict`)

Commits that fail these checks will be rejected.

---

## References

- [PEP 257 – Docstring Conventions](https://peps.python.org/pep-0257/)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)
- [NumPy Docstring Guide](https://numpydoc.readthedocs.io/en/latest/format.html)
- [aiohomematic CLAUDE.md](../CLAUDE.md)

---

**Last Updated**: 2025-11-24
**Version**: 1.0
