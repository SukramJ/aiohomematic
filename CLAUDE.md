# CLAUDE.md - AI Assistant Guide for aiohomematic

This document provides comprehensive guidance for AI assistants (like Claude) working on the aiohomematic codebase. It covers project structure, development workflows, coding conventions, and common tasks.

## Table of Contents

1. [Project Overview](#project-overview)
2. [Codebase Structure](#codebase-structure)
3. [Development Environment Setup](#development-environment-setup)
4. [Code Quality & Standards](#code-quality--standards)
5. [Testing Guidelines](#testing-guidelines)
6. [Architecture & Design Patterns](#architecture--design-patterns)
7. [Common Development Tasks](#common-development-tasks)
8. [Git Workflow](#git-workflow)
9. [Key Conventions](#key-conventions)
10. [Important Files Reference](#important-files-reference)

---

## Project Overview

**aiohomematic** is a modern, async Python library for controlling and monitoring Homematic and HomematicIP devices. It powers the Home Assistant integration "Homematic(IP) Local".

### Key Characteristics

- **Language**: Python 3.13+
- **Framework**: AsyncIO-based
- **Status**: Production/Stable (Development Status 5)
- **Type Safety**: Fully typed with mypy strict mode
- **License**: MIT
- **Current Version**: 2025.11.16 (defined in `aiohomematic/const.py`)

### Core Dependencies

```python
aiohttp>=3.12.0         # Async HTTP client
orjson>=3.11.0          # Fast JSON serialization
python-slugify>=8.0.0   # URL-safe string conversion
voluptuous>=0.15.0      # Configuration/schema validation
```

### Project Goals

- Automatic entity discovery from device/channel parameters
- Extensible via custom entity classes for complex devices
- Fast startup through caching of paramsets
- Designed for Home Assistant integration

---

## Codebase Structure

### Directory Layout

```
/home/user/aiohomematic/
├── aiohomematic/                    # Main package (67 files, ~26.8K LOC)
│   ├── central/                     # Central orchestration (3 files)
│   │   ├── __init__.py             # CentralUnit, CentralConfig
│   │   ├── decorators.py           # RPC function decorators
│   │   └── rpc_server.py           # XML-RPC callback server
│   │
│   ├── client/                      # Protocol adapters (4 files)
│   │   ├── __init__.py             # Client abstractions
│   │   ├── json_rpc.py             # JSON-RPC implementation
│   │   ├── rpc_proxy.py            # XML-RPC proxy wrapper
│   │   └── _rpc_errors.py          # RPC error handling
│   │
│   ├── model/                       # Domain model (43 files, ~13.8K LOC)
│   │   ├── custom/                 # Device-specific implementations
│   │   │   ├── climate.py          # Thermostats
│   │   │   ├── cover.py            # Blinds/shutters
│   │   │   ├── light.py            # Lights/dimmers
│   │   │   ├── lock.py             # Door locks
│   │   │   ├── siren.py            # Sirens/alarms
│   │   │   ├── switch.py           # Switches/relays
│   │   │   ├── valve.py            # Heating valves
│   │   │   ├── data_point.py       # Custom data point definitions
│   │   │   ├── definition.py       # Custom device profiles
│   │   │   └── support.py          # Helper utilities
│   │   │
│   │   ├── generic/                # Generic entity types
│   │   │   ├── action.py           # Action triggers
│   │   │   ├── binary_sensor.py    # Boolean sensors
│   │   │   ├── button.py           # Momentary buttons
│   │   │   ├── select.py           # Dropdown selectors
│   │   │   ├── sensor.py           # Numeric/text sensors
│   │   │   ├── switch.py           # Toggle switches
│   │   │   ├── number.py           # Numeric input
│   │   │   ├── text.py             # Text input
│   │   │   └── data_point.py       # Generic data point impl
│   │   │
│   │   ├── hub/                    # Hub-level entities (8 files)
│   │   │   └── __init__.py         # Programs & system variables
│   │   │
│   │   ├── calculated/             # Derived metrics (4 files)
│   │   │   ├── data_point.py       # Calculated data points
│   │   │   ├── climate.py          # Climate calculations
│   │   │   └── operating_voltage_level.py  # Battery/voltage
│   │   │
│   │   ├── device.py               # Device & Channel classes
│   │   ├── data_point.py           # Base DataPoint class
│   │   ├── event.py                # Event representation
│   │   ├── support.py              # Model utilities
│   │   └── week_profile.py         # Weekly schedule abstraction
│   │
│   ├── store/                       # Persistence and caching (4 files)
│   │   ├── __init__.py             # Store orchestration
│   │   ├── persistent.py           # Disk-backed caches
│   │   ├── dynamic.py              # In-memory caches
│   │   └── visibility.py           # Parameter filtering rules
│   │
│   ├── rega_scripts/               # Homematic scripts (6 *.fn files)
│   ├── translations/               # i18n JSON files
│   │
│   └── [Core modules]
│       ├── const.py                # Constants, enums, patterns
│       ├── support.py              # Cross-cutting utilities
│       ├── property_decorators.py  # Property decorators
│       ├── decorators.py           # Function decorators
│       ├── async_support.py        # Async helpers
│       ├── i18n.py                 # Internationalization
│       ├── converter.py            # Value type conversion
│       ├── exceptions.py           # Custom exceptions
│       ├── type_aliases.py         # Type hint aliases
│       ├── hmcli.py                # CLI entry point
│       ├── validator.py            # Startup validation
│       └── py.typed                # PEP 561 marker
│
├── aiohomematic_test_support/      # Reusable test infrastructure
│   ├── const.py                    # Test constants
│   ├── factory.py                  # Test factories
│   ├── mock.py                     # Mock session players
│   ├── data/                       # Pre-recorded test sessions
│   └── pyproject.toml              # Separate package config
│
├── tests/                          # Test suite (46 files)
│   ├── conftest.py                 # Pytest fixtures
│   ├── helpers/                    # Mock helpers
│   └── test_*.py                   # Test modules
│
├── docs/                           # Documentation (11 files)
│   ├── architecture.md             # Architecture overview
│   ├── data_flow.md                # Data flow diagrams
│   ├── extension_points.md         # How to extend
│   ├── sequence_diagrams.md        # Sequence diagrams
│   ├── homeassistant_lifecycle.md  # HA integration
│   └── [Other docs]
│
├── script/                         # Development scripts (10 files)
│   ├── sort_class_members.py       # Organize class members
│   ├── check_i18n.py               # Validate translations
│   ├── check_i18n_catalogs.py      # Check translation catalogs
│   ├── lint_kwonly.py              # Enforce keyword-only args
│   └── run-in-env.sh               # Run tools in venv
│
├── .github/workflows/              # CI/CD workflows
│
└── [Configuration files]
    ├── pyproject.toml              # Main project configuration
    ├── .pre-commit-config.yaml     # Pre-commit hooks
    ├── requirements.txt            # Base dependencies
    ├── requirements_test.txt       # Test dependencies
    ├── .yamllint                   # YAML linting rules
    ├── codecov.yml                 # Coverage config
    ├── example.py                  # Usage example
    └── README.md, changelog.md
```

---

## Development Environment Setup

### Prerequisites

- **Python**: 3.13 or higher
- **Package Manager**: pip, uv (recommended)
- **Git**: For version control

### Initial Setup

```bash
# Clone the repository
git clone https://github.com/sukramj/aiohomematic.git
cd aiohomematic

# Create virtual environment
python3.13 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements_test.txt

# Install pre-commit hooks
pre-commit install
```

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest --cov=aiohomematic tests/

# Run specific test file
pytest tests/test_central.py

# Run with verbose output
pytest -v tests/

# Run tests with specific markers
pytest -m "not slow" tests/
```

### Running Linters

```bash
# Run all pre-commit hooks
pre-commit run --all-files

# Run specific tools
ruff check --fix                    # Lint and auto-fix
ruff format                         # Format code
mypy                                # Type check
pylint -j 0 aiohomematic           # Full linting
bandit --quiet                      # Security check
codespell                           # Spell check

# Run custom scripts
python script/sort_class_members.py
python script/check_i18n.py
```

---

## Code Quality & Standards

### Type Checking (mypy - STRICT MODE)

**CRITICAL**: This project uses mypy in **strict mode**. All code MUST be fully typed.

```python
# pyproject.toml settings:
strict = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
disallow_untyped_calls = true
warn_return_any = true
```

#### Type Annotation Requirements

```python
# ✅ CORRECT - All parameters and return types annotated
def get_device_by_address(self, address: str) -> Device | None:
    """Get device by address."""
    return self._devices.get(address)

# ❌ INCORRECT - Missing type annotations
def get_device_by_address(self, address):
    return self._devices.get(address)

# ✅ CORRECT - Complex types properly annotated
async def fetch_devices(
    self,
    *,
    include_internal: bool = False,
) -> dict[str, DeviceDescription]:
    """Fetch all device descriptions."""
    ...

# ✅ CORRECT - Using TYPE_CHECKING for imports
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiohomematic.central import CentralUnit
```

### Linting (ruff + pylint)

#### Ruff Configuration

- **Target**: Python 3.13
- **Line Length**: 120 characters
- **Enabled Rules**: A, ASYNC, B, C, D, E, F, FLY, G, I, INP, ISC, LOG, PERF, PGH, PIE, PL, PT, PYI, RET, RSE, RUF, S, SIM, SLOT, T, TID, TRY, UP, W

#### Import Requirements

**MANDATORY**: Every Python file MUST start with:

```python
from __future__ import annotations
```

This is enforced by ruff's `required-imports` setting.

#### Import Sorting (isort via ruff)

```python
# Correct import order:
from __future__ import annotations

# 1. Standard library
import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING

# 2. Third-party
import aiohttp
import orjson

# 3. First-party (aiohomematic)
from aiohomematic.const import Interface
from aiohomematic.support import validate_address

# 4. TYPE_CHECKING imports (to avoid circular imports)
if TYPE_CHECKING:
    from aiohomematic.central import CentralUnit
```

#### Code Style Conventions

```python
# Use keyword-only arguments for functions with > 2 parameters
def create_client(
    *,  # Force keyword-only
    host: str,
    username: str,
    password: str,
    port: int = 2001,
) -> Client:
    """Create a new client."""
    ...

# Docstrings required for all public classes and methods
class Device:
    """Representation of a Homematic device."""

    def get_channel(self, channel_no: int) -> Channel | None:
        """Get channel by number."""
        ...

# Use descriptive variable names (avoid single letters except in comprehensions)
# ✅ CORRECT
for device_address in device_addresses:
    ...

# ⚠️ ACCEPTABLE only in simple comprehensions
devices = [d for d in all_devices if d.is_ready]
```

### Formatting (ruff format)

```bash
# Auto-format all code
ruff format

# Check formatting without changes
ruff format --check
```

---

## Testing Guidelines

### Test Organization

Tests are organized in `/tests/` with the following structure:

```
tests/
├── conftest.py              # Shared fixtures
├── helpers/                 # Test helpers
│   ├── mock_json_rpc.py
│   └── mock_xml_rpc.py
├── test_central.py          # Central unit tests
├── test_client.py           # Client tests
├── test_model_*.py          # Model tests by entity type
└── fixtures/                # Test data
```

### Fixtures (conftest.py)

Key fixtures available:

```python
# Factory fixtures for creating test clients
factory_with_ccu_client
factory_with_homegear_client

# Full central unit with client
central_client_factory_with_ccu_client
central_client_factory_with_homegear_client

# Session playback for reproducible tests
session_player_ccu
session_player_pydevccu

# Virtual CCU instances
central_unit_pydevccu_mini
central_unit_pydevccu_full

# HTTP session
aiohttp_session

# Mock servers
mock_xml_rpc_server
mock_json_rpc_server
```

### Writing Tests

```python
"""Test for central unit."""

from __future__ import annotations

import pytest

from aiohomematic.central import CentralUnit
from aiohomematic.const import Interface


@pytest.mark.asyncio
async def test_device_discovery(
    central_client_factory_with_ccu_client,
) -> None:
    """Test device discovery."""
    central, _ = await central_client_factory_with_ccu_client()

    await central.start()

    # Assertions
    assert len(central.devices) > 0
    assert central.is_connected is True

    await central.stop()


def test_address_validation() -> None:
    """Test address validation."""
    from aiohomematic.support import validate_address

    assert validate_address("VCU0000001:1") is True
    assert validate_address("invalid") is False
```

### Test Coverage

- **Target Coverage**: 90%+ for core logic
- **Excluded Files**:
  - `aiohomematic/validator.py`
  - `aiohomematic/exceptions.py`
  - `aiohomematic/central/rpc_server.py`

```bash
# Generate coverage report
pytest --cov=aiohomematic --cov-report=html tests/

# View HTML report
open htmlcov/index.html
```

---

## Architecture & Design Patterns

### High-Level Architecture

The codebase follows a layered architecture:

```
┌─────────────────────────────────────────┐
│         Home Assistant / Consumer       │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│         Central (Orchestrator)          │
│  - CentralUnit, CentralConfig           │
│  - Lifecycle management                 │
│  - Device/DataPoint registry            │
│  - XML-RPC callback server              │
└──────────────────┬──────────────────────┘
                   │
        ┌──────────┼──────────┐
        │          │          │
┌───────▼───┐  ┌──▼────┐  ┌──▼────┐
│  Client   │  │ Model │  │ Store │
│  XML-RPC  │  │Device │  │ Cache │
│  JSON-RPC │  │Data   │  │Persist│
└───────────┘  │Point  │  └───────┘
               └───────┘
                   │
        ┌──────────┼──────────┐
        │          │          │
   ┌────▼───┐ ┌───▼───┐ ┌────▼────┐
   │Generic │ │Custom │ │Calculate│
   │Entities│ │Device │ │Derived  │
   └────────┘ └───────┘ └─────────┘
```

### Key Components

#### 1. Central (aiohomematic/central/)

**Responsibility**: Orchestrates the entire system

- Manages client lifecycles
- Creates devices and data points
- Runs lightweight scheduler
- Exposes XML-RPC callback server for events
- Provides query facade over runtime model

```python
from aiohomematic.central import CentralConfig
from aiohomematic.client import InterfaceConfig

# Create central configuration
config = CentralConfig(
    name="ccu-main",
    host="192.168.1.100",
    username="admin",
    password="secret",
    central_id="unique-id",
    interface_configs={
        InterfaceConfig(
            central_name="ccu-main",
            interface=Interface.HMIP_RF,
            port=2010,
        ),
    },
)

# Create and start central
central = config.create_central()
await central.start()

# Access devices
device = central.get_device_by_address("VCU0000001")

# Stop central
await central.stop()
```

#### 2. Client (aiohomematic/client/)

**Responsibility**: Protocol adapters to Homematic backends

- Implements XML-RPC and JSON-RPC communication
- Maintains connection health
- Translates high-level operations to backend requests

**Key Types**:
- `ClientCCU` - CCU3/CCU2 via XML-RPC
- `ClientJsonCCU` - CCU via JSON-RPC
- `ClientHomegear` - Homegear backend

#### 3. Model (aiohomematic/model/)

**Responsibility**: Runtime representation of devices and data points

- **NO I/O operations** - pure domain model
- Transforms paramset descriptions into typed DataPoints
- Provides generic, custom, and calculated entity types

**Key Classes**:
- `Device` - Represents a physical device
- `Channel` - A device channel
- `DataPoint` - Addressable parameter with read/write/event capabilities
- `Event` - Push-style notification

#### 4. Store (aiohomematic/store/)

**Responsibility**: Caching and persistence

- **Persistent**: DeviceDescriptionCache, ParamsetDescriptionCache (disk)
- **Dynamic**: CentralDataCache, CommandCache, PingPongCache (memory)
- **Visibility**: ParameterVisibilityCache (filtering rules)

### Design Patterns Used

#### 1. Factory Pattern

```python
# In aiohomematic/model/generic/__init__.py
def create_data_points_and_events(
    central: CentralUnit,
    device: Device,
    channel: Channel,
    paramset_description: dict[str, Any],
) -> None:
    """Factory function to create data points and events."""
    # Creates appropriate DataPoint subclass based on metadata
    ...
```

#### 2. Dependency Injection

```python
# Central is injected into objects that need it
class Device:
    def __init__(
        self,
        *,
        central: CentralUnit,
        address: str,
        ...
    ):
        self._central = central
```

#### 3. Observer Pattern

```python
# DataPoints support subscription
def subscribe(
    self,
    callback: Callable[[str, Any], None],
) -> None:
    """Subscribe to value changes."""
    self._callbacks.append(callback)

# Usage
data_point.subscribe(lambda name, value: print(f"{name} = {value}"))
```

#### 4. Decorator Pattern

```python
# Property decorators for dynamic behavior
from aiohomematic.property_decorators import config_property

class DataPoint:
    @config_property
    def value(self) -> Any:
        """Get current value."""
        return self._value
```

### Concurrency Model

- **Async I/O**: All network operations use asyncio
- **Background Thread**: Scheduler runs in separate thread for periodic tasks
- **Thread-Safe**: Collections use appropriate locking where needed

```python
# Async operations
async def get_value(self, parameter: str) -> Any:
    """Get parameter value via async RPC call."""
    return await self._client.get_value(...)

# Background scheduler (runs in thread)
class _Scheduler:
    """Background scheduler for periodic tasks."""
    def _schedule_refresh(self) -> None:
        """Schedule periodic refresh in separate thread."""
        ...
```

---

## Common Development Tasks

### Adding a New Device Type

1. **Create custom entity class** in `aiohomematic/model/custom/`:

```python
"""Custom entity for new device type."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiohomematic.model.custom.data_point import CustomDataPoint

if TYPE_CHECKING:
    from aiohomematic.central import CentralUnit


class NewDeviceEntity(CustomDataPoint):
    """Custom entity for new device type."""

    def __init__(
        self,
        *,
        central: CentralUnit,
        device_address: str,
        channel_no: int,
    ):
        """Initialize new device entity."""
        super().__init__(
            central=central,
            device_address=device_address,
            channel_no=channel_no,
        )
```

2. **Register in definition.py**:

```python
# In aiohomematic/model/custom/definition.py
CUSTOM_DEVICE_DEFINITIONS: dict[str, CustomDeviceDefinition] = {
    "NEW_DEVICE_TYPE": CustomDeviceDefinition(
        entity_classes={
            NewDeviceEntity: (
                "NEW_DEVICE_CHANNEL_TYPE",
                {"PARAMETER_NAME"},
            ),
        },
    ),
}
```

3. **Add tests** in `tests/test_model_newdevice.py`

4. **Update documentation** in `docs/extension_points.md`

### Adding a Calculated Data Point

1. **Create calculated class** in `aiohomematic/model/calculated/`:

```python
"""Calculated data point."""

from __future__ import annotations

from aiohomematic.model.calculated.data_point import CalculatedDataPoint


class NewCalculation(CalculatedDataPoint):
    """Calculate derived value."""

    async def calculate_value(self) -> float:
        """Calculate and return derived value."""
        value1 = await self._get_source_value("PARAMETER1")
        value2 = await self._get_source_value("PARAMETER2")
        return value1 + value2
```

2. **Register in model** and **add tests**

### Adding a Translation

1. **Use translation in code**:

```python
from aiohomematic.i18n import gettext as _

# In code
message = _("ERROR_MESSAGE_KEY")
```

2. **Add to translation catalog**:

```bash
# Edit aiohomematic/translations/en.json
{
  "ERROR_MESSAGE_KEY": "Error message in English"
}
```

3. **Validate translations**:

```bash
python script/check_i18n.py
python script/check_i18n_catalogs.py
```

### Debugging Tips

#### Enable Debug Logging

```python
import logging

logging.basicConfig(level=logging.DEBUG)
```

#### Use Session Recorder

```python
# In test or development
from aiohomematic.const import OptionalSettings

config = CentralConfig(
    ...,
    optional_settings=(OptionalSettings.SESSION_RECORDER,),
)
```

#### Performance Metrics

```python
from aiohomematic.const import OptionalSettings

config = CentralConfig(
    ...,
    optional_settings=(OptionalSettings.PERFORMANCE_METRICS,),
)
```

---

## Git Workflow

### Branch Structure

- **Main Branch**: `master` (protected)
- **Development Branch**: `devel` (protected)
- **Feature Branches**: `feature/description`
- **Bug Fix Branches**: `fix/description`
- **AI Assistant Branches**: `claude/claude-md-{session-id}`

### Commit Messages

Follow conventional commit format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

**Examples**:

```bash
feat(model): Add support for new device type

Implements custom entity class for XYZ device with support for
parameter ABC and DEF.

Closes #123
```

```bash
fix(client): Handle connection timeout gracefully

Added retry logic with exponential backoff for RPC calls.
```

### Pull Request Process

1. **Create feature branch** from `devel`
2. **Make changes** with tests
3. **Run pre-commit hooks**: `pre-commit run --all-files`
4. **Commit changes** with descriptive messages
5. **Push to remote**: `git push -u origin feature/branch-name`
6. **Create Pull Request** to `devel` branch
7. **Wait for CI** to pass
8. **Request review** from maintainers

### Pre-commit Hooks

The following hooks run automatically on commit:

1. **sort-class-members** - Organize class members
2. **check-i18n** - Validate translations
3. **ruff** - Lint and format
4. **mypy** - Type check
5. **pylint** - Additional linting
6. **codespell** - Spell check
7. **bandit** - Security check
8. **yamllint** - YAML validation

**Bypass hooks** (NOT recommended):

```bash
git commit --no-verify -m "message"
```

---

## Key Conventions

### Import Aliases

The project defines standard import aliases (enforced by ruff):

```python
import voluptuous as vol

from aiohomematic.central import CentralUnit as hmcu
from aiohomematic.client import Client as hmcl
from aiohomematic.model.custom import definition as hmed
from aiohomematic.support import support as hms
```

### Naming Conventions

#### Files and Modules

- **Module names**: `snake_case.py`
- **Package names**: `lowercase`

#### Classes and Functions

- **Classes**: `PascalCase`
- **Functions/Methods**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private members**: `_leading_underscore`
- **Type variables**: `T`, `T_co`, `T_contra`

#### Variables

```python
# Device addresses
device_address: str = "VCU0000001"
channel_address: str = "VCU0000001:1"

# Use descriptive names
device_descriptions: dict[str, DeviceDescription]
paramset_descriptions: dict[str, ParameterDescription]

# Avoid abbreviations unless common
# ✅ GOOD
device = get_device()

# ⚠️ AVOID
dev = get_dev()
```

### Constants Organization

All constants are in `aiohomematic/const.py`:

```python
from aiohomematic.const import (
    Interface,           # Enum for interface types
    ParamsetKey,         # Enum for paramset keys
    BackendSystemEvent,  # Enum for system events
    DEFAULT_TIMEOUT,     # Timeout values
    VERSION,             # Package version
)
```

### Error Handling

Use custom exceptions from `aiohomematic/exceptions.py`:

```python
from aiohomematic.exceptions import (
    AioHomematicException,      # Base exception
    ClientException,            # Client errors
    NoConnectionException,      # Connection errors
    ValidationException,        # Validation errors
)

# Raise with context
raise ClientException(
    f"Failed to connect to {self.host}:{self.port}"
)

# Catch and re-raise
try:
    await self._client.connect()
except aiohttp.ClientError as err:
    raise ClientException("Connection failed") from err
```

### Async Patterns

```python
# Use async context managers
async with aiohttp.ClientSession() as session:
    async with session.get(url) as response:
        data = await response.json()

# Use asyncio.gather for parallel operations
results = await asyncio.gather(
    client1.fetch_devices(),
    client2.fetch_devices(),
    return_exceptions=True,
)

# Use timeout for operations
async with asyncio.timeout(10):
    await long_running_operation()
```

### Type Hints Best Practices

```python
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Final, TypeAlias

# Use modern union syntax (Python 3.10+)
def get_value(self, key: str) -> str | None:
    ...

# Use TypeAlias for complex types
DeviceMap: TypeAlias = dict[str, Device]

# Use Final for constants
DEFAULT_PORT: Final = 2001

# Use Callable for function types
CallbackType: TypeAlias = Callable[[str, Any], None]

# Use Mapping/Sequence for read-only collections
def process_devices(devices: Mapping[str, Device]) -> None:
    ...
```

---

## Important Files Reference

### Configuration Files

| File | Purpose | Key Settings |
|------|---------|--------------|
| `pyproject.toml` | Main project configuration | Build, dependencies, tool configs |
| `.pre-commit-config.yaml` | Pre-commit hooks | Linters, formatters, type checkers |
| `requirements.txt` | Runtime dependencies | aiohttp, orjson, voluptuous |
| `requirements_test.txt` | Test dependencies | pytest, mypy, pylint, ruff |
| `.yamllint` | YAML linting rules | YAML formatting standards |
| `codecov.yml` | Coverage configuration | Coverage thresholds |

### Core Source Files

| File | Lines | Purpose |
|------|-------|---------|
| `aiohomematic/const.py` | 1,273 | Constants, enums, patterns |
| `aiohomematic/support.py` | 678 | Cross-cutting utilities |
| `aiohomematic/central/__init__.py` | 2,390 | Central orchestration |
| `aiohomematic/client/__init__.py` | 1,944 | Client protocol adapters |
| `aiohomematic/model/device.py` | ~1,800 | Device model |
| `aiohomematic/model/data_point.py` | ~1,200 | DataPoint base class |

### Documentation Files

| File | Purpose |
|------|---------|
| `README.md` | Project overview, quickstart |
| `changelog.md` | Release history |
| `docs/architecture.md` | Architecture overview |
| `docs/data_flow.md` | Data flow diagrams |
| `docs/extension_points.md` | How to extend the library |
| `docs/sequence_diagrams.md` | Sequence diagrams |
| `docs/homeassistant_lifecycle.md` | Home Assistant integration |

### Test Files

| File | Purpose |
|------|---------|
| `tests/conftest.py` | Pytest fixtures and configuration |
| `tests/test_central.py` | Central unit tests |
| `tests/test_client.py` | Client protocol tests |
| `tests/test_model_climate.py` | Climate entity tests |
| `tests/test_model_cover.py` | Cover entity tests |

### Development Scripts

| Script | Purpose |
|--------|---------|
| `script/sort_class_members.py` | Organize class members |
| `script/check_i18n.py` | Validate translation usage |
| `script/check_i18n_catalogs.py` | Check translation completeness |
| `script/lint_kwonly.py` | Enforce keyword-only arguments |
| `script/run-in-env.sh` | Run commands in virtual environment |

---

## Quick Reference

### Running Common Commands

```bash
# Format code
ruff format

# Lint code
ruff check --fix

# Type check
mypy

# Run all checks
pre-commit run --all-files

# Run tests
pytest tests/

# Run tests with coverage
pytest --cov=aiohomematic tests/

# Check translation usage
python script/check_i18n.py

# Organize class members
python script/sort_class_members.py
```

### Public API Entry Points

```python
# Central configuration
from aiohomematic.central import CentralConfig, CentralUnit

# Client configuration
from aiohomematic.client import InterfaceConfig, Client

# Model classes
from aiohomematic.model import Device, Channel, DataPoint, Event

# Constants and enums
from aiohomematic.const import Interface, ParamsetKey, BackendSystemEvent

# Exceptions
from aiohomematic.exceptions import AioHomematicException, ClientException

# Validation
from aiohomematic.model.custom import validate_custom_data_point_definition
```

### Useful Links

- **GitHub**: https://github.com/sukramj/aiohomematic
- **Issues**: https://github.com/sukramj/aiohomematic/issues
- **Discussions**: https://github.com/sukramj/aiohomematic/discussions
- **Home Assistant Integration**: https://github.com/sukramj/homematicip_local
- **Example Usage**: See `example.py` in repository root

---

## Tips for AI Assistants

### Do's

✅ **Always** include `from __future__ import annotations` at the top of Python files
✅ **Always** provide complete type annotations for all functions and methods
✅ **Always** run pre-commit hooks before committing
✅ **Always** write tests for new functionality
✅ **Always** update documentation when changing public APIs
✅ **Always** use keyword-only arguments for functions with > 2 parameters
✅ **Always** use descriptive variable names
✅ **Always** handle exceptions with proper context

### Don'ts

❌ **Never** commit without type annotations
❌ **Never** skip pre-commit hooks
❌ **Never** commit to `master` or `devel` directly
❌ **Never** use `Any` type without justification
❌ **Never** perform I/O operations in model classes
❌ **Never** use bare `except:` clauses
❌ **Never** modify `aiohomematic/const.py` without thorough review
❌ **Never** break backward compatibility without major version bump

### When in Doubt

1. **Read the architecture docs**: `docs/architecture.md`
2. **Look at existing examples**: Similar functionality in codebase
3. **Run the tests**: `pytest tests/`
4. **Check the type hints**: `mypy` will guide you
5. **Review the changelog**: `changelog.md` for recent changes

---

**Last Updated**: 2025-11-16
**Version**: 2025.11.16
