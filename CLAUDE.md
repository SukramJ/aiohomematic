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
│   ├── central/                     # Central orchestration (11 files)
│   │   ├── __init__.py             # CentralUnit, CentralConfig
│   │   ├── cache_coordinator.py    # Cache management (DI: 8 protocols)
│   │   ├── client_coordinator.py   # Client lifecycle (DI: ClientFactoryProtocol + 5 protocols)
│   │   ├── device_coordinator.py   # Device operations (DI: 15 protocols)
│   │   ├── device_registry.py      # Device storage (DI: 2 protocols)
│   │   ├── event_coordinator.py    # Event handling (DI: 2 protocols)
│   │   ├── hub_coordinator.py      # Hub entities (DI: 9 protocols)
│   │   ├── scheduler.py            # Background tasks (DI: 7 protocols)
│   │   ├── decorators.py           # RPC function decorators
│   │   ├── rpc_server.py           # XML-RPC callback server
│   │   └── event_bus.py            # Modern event system
│   │
│   ├── client/                      # Protocol adapters (7 files)
│   │   ├── __init__.py             # Client abstractions
│   │   ├── json_rpc.py             # JSON-RPC implementation
│   │   ├── rpc_proxy.py            # XML-RPC proxy wrapper
│   │   ├── _rpc_errors.py          # RPC error handling
│   │   ├── state_machine.py        # Client state machine
│   │   ├── circuit_breaker.py      # Connection circuit breaker
│   │   └── request_coalescer.py    # Request deduplication
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
│   │   │   ├── data_point.py       # Custom data point base class
│   │   │   ├── definition.py       # Profile definitions and factory
│   │   │   ├── profile.py          # ProfileConfig dataclasses
│   │   │   ├── registry.py         # DeviceProfileRegistry
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
│   │   ├── update.py               # Firmware update data
│   │   ├── support.py              # Model utilities
│   │   └── week_profile.py         # Weekly schedule abstraction
│   │
│   ├── interfaces/                  # Protocol interfaces for DI (6 files)
│   │   ├── __init__.py             # Public API exports
│   │   ├── central.py              # Central unit protocols
│   │   ├── client.py               # Client protocols
│   │   ├── model.py                # Device/Channel/DataPoint protocols
│   │   ├── operations.py           # Cache & visibility protocols
│   │   └── coordinators.py         # Coordinator protocols
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

### Docstring Standards

**IMPORTANT**: All code must follow the project's docstring conventions for consistency and maintainability.

#### Documentation Resources

- **[docs/docstring_standards.md](docs/docstring_standards.md)** - Complete docstring style guide with rules, patterns, and anti-patterns
- **[docs/docstring_templates.md](docs/docstring_templates.md)** - Ready-to-use templates for common code patterns
- **[docs/docstring_audit.md](docs/docstring_audit.md)** - Module categorization and improvement roadmap

#### Key Principles

1. **Short and Precise**: Docstrings should be concise yet informative
2. **Programmer-Focused**: Write for developers using or maintaining the code
3. **Type Hints First**: Rely on type annotations; avoid repeating type information
4. **Consistency**: Follow established patterns for similar constructs

#### Quick Rules

**Punctuation**: Always end docstrings with a period (`.`)

**Verb Usage**:

- Functions/Methods: Use imperative mood ("Return the device", not "Returns" or "Gets")
- Classes: Use declarative statements ("Represents a device")

**Module Docstrings** - Three tiers:

```python
# Tier 1 (Core APIs): Comprehensive with sections
"""
Module description.

Overview
--------
Detailed explanation...

Public API
----------
- Class: Description
- function: Description

Quick start
-----------
Usage example...
"""

# Tier 2 (Coordinators): Medium detail
"""
Module description.

Key features:
- Feature 1
- Feature 2
"""

# Tier 3 (Utilities): Brief
"""
Module description.

Public API of this module is defined by __all__.
"""
```

**Method Docstrings**:

```python
# Simple methods (one-line)
def get_device(self, address: str) -> Device | None:
    """Return device by address."""

# Complex methods (with Args/Returns)
def create_device(
    self,
    *,
    interface_id: str,
    device_address: str,
) -> Device:
    """
    Create and register a new device instance.

    Args:
        interface_id: Interface identifier
        device_address: Unique device address

    Returns:
        Created device instance.
    """
```

**Property Docstrings**:

```python
@property
def device_address(self) -> str:
    """Return the device address."""
```

#### Common Anti-Patterns to Avoid

❌ **Don't repeat type information**:

```python
# Bad
def get_address(self) -> str:
    """Return the address as a string."""

# Good
def get_address(self) -> str:
    """Return the device address."""
```

❌ **Don't use inconsistent verbs**:

```python
# Bad
def get_device(...): """Gets device."""
def fetch_value(...): """Fetches value."""

# Good
def get_device(...): """Return device by address."""
def fetch_value(...): """Return parameter value."""
```

❌ **Don't forget periods**:

```python
# Bad
"""Clear the cache"""

# Good
"""Clear the cache."""
```

#### Linter Integration

Docstring formatting is validated by ruff with pydocstyle rules:

```bash
# Check docstring compliance
ruff check --select D

# Auto-fix formatting issues
ruff check --fix --select D
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

#### 2. Protocol-Based Dependency Injection

aiohomematic uses a three-tier dependency injection architecture to reduce coupling:

**Tier 1: Full DI (Infrastructure Layer)** - Components receive only protocol interfaces:

```python
# Example: CacheCoordinator with 8 protocol interfaces
class CacheCoordinator:
    def __init__(
        self,
        *,
        central_info: CentralInfoProtocol,
        device_provider: DeviceProviderProtocol,
        client_provider: ClientProviderProtocol,
        data_point_provider: DataPointProviderProtocol,
        primary_client_provider: PrimaryClientProviderProtocol,
        config_provider: ConfigProviderProtocol,
        task_scheduler: TaskSchedulerProtocol,
        session_recorder_active: bool,
    ) -> None:
        # Zero references to CentralUnit - only protocol interfaces
        self._central_info: Final = central_info
        self._device_provider: Final = device_provider
        # ...
```

**Tier 2: Full Protocol-Based DI (Coordinator Layer)** - Uses protocol interfaces exclusively:

```python
# Example: ClientCoordinator uses ClientFactoryProtocol protocol
class ClientCoordinator:
    def __init__(
        self,
        *,
        client_factory: ClientFactoryProtocol,  # Factory protocol, not CentralUnit
        central_info: CentralInfoProtocol,
        config_provider: ConfigProviderProtocol,
        coordinator_provider: CoordinatorProviderProtocol,
        system_info_provider: SystemInfoProviderProtocol,
    ) -> None:
        self._client_factory: Final = client_factory
        self._central_info: Final = central_info
        # All operations use protocol interfaces

# Example: HubCoordinator constructs Hub with protocol interfaces
class HubCoordinator:
    def __init__(
        self,
        *,
        central_info: CentralInfoProtocol,
        channel_lookup: ChannelLookupProtocol,
        config_provider: ConfigProviderProtocol,
        event_bus_provider: EventBusProviderProtocol,
        event_publisher: EventPublisherProtocol,
        # ... more protocol interfaces
    ) -> None:
        # Creates Hub using protocol interfaces - no CentralUnit reference
        self._hub: Final = Hub(
            central_info=central_info,
            config_provider=config_provider,
            # ... protocol interfaces only
        )
```

**Note**: As of 2025-11-23, Tier 2 coordinators no longer use hybrid DI patterns. The ClientFactoryProtocol protocol was introduced to enable client creation without requiring the full CentralUnit, and Hub construction was refactored to use only protocol interfaces.

**Tier 3: Full DI (Model Layer)** - Device, Channel, and DataPoint classes use full DI:

```python
# Example: Device with 16 protocol interfaces
class Device:
    def __init__(
        self,
        *,
        interface_id: str,
        device_address: str,
        device_details_provider: DeviceDetailsProviderProtocol,
        device_description_provider: DeviceDescriptionProviderProtocol,
        paramset_description_provider: ParamsetDescriptionProviderProtocol,
        parameter_visibility_provider: ParameterVisibilityProviderProtocol,
        client_provider: ClientProviderProtocol,
        config_provider: ConfigProviderProtocol,
        central_info: CentralInfoProtocol,
        event_bus_provider: EventBusProviderProtocol,
        task_scheduler: TaskSchedulerProtocol,
        file_operations: FileOperationsProtocol,
        device_data_refresher: DeviceDataRefresherProtocol,
        data_cache_provider: DataCacheProviderProtocol,
        channel_lookup: ChannelLookupProtocol,
        event_subscription_manager: EventSubscriptionManagerProtocol,
    ) -> None:
        # Stores all protocol interfaces directly
        self._central_info: Final = central_info
        self._event_bus_provider: Final = event_bus_provider
        # ... (all protocol interfaces stored)

# Channel accesses protocol interfaces through its parent Device:
class Channel:
    def __init__(self, *, device: Device, channel_address: str) -> None:
        self._device: Final = device
        # Accesses protocol interfaces via self._device._xxx_provider

# DataPoint classes receive protocol interfaces from channel.device:
class BaseDataPoint:
    def __init__(
        self,
        *,
        channel: Channel,
        unique_id: str,
        is_in_multiple_channels: bool,
    ) -> None:
        # Extracts and passes protocol interfaces to CallbackDataPoint
        super().__init__(
            unique_id=unique_id,
            central_info=channel.device._central_info,
            event_bus_provider=channel.device._event_bus_provider,
            task_scheduler=channel.device._task_scheduler,
            paramset_description_provider=channel.device._paramset_description_provider,
            parameter_visibility_provider=channel.device._parameter_visibility_provider,
        )
```

**Protocol Interfaces** are defined in `aiohomematic/interfaces/` using `@runtime_checkable`:

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class CentralInfoProtocol(Protocol):
    """Protocol for central system information."""
    @property
    def name(self) -> str: ...
    @property
    def model(self) -> str: ...
```

**Naming Convention**: All protocol interfaces use the `-Protocol` suffix to avoid name collisions with implementing classes and to make them instantly recognizable as protocols.

**Key Protocol Interfaces** defined in `aiohomematic/interfaces/`:

- **CentralInfoProtocol**: System identification (name, model, version)
- **ConfigProviderProtocol**: Configuration access (config property)
- **ClientFactoryProtocol**: Client instance creation (create_client_instance method)
- **ClientProviderProtocol**: Client lookup by interface_id
- **DeviceProviderProtocol**: Device registry access
- **DataPointProviderProtocol**: Data point lookup
- **EventBusProviderProtocol**: Event system access (event_bus property)
- **EventPublisherProtocol**: Event emission via EventCoordinator (publish_system_event, publish_device_trigger_event)
- **TaskSchedulerProtocol**: Background task scheduling (create_task method)
- **PrimaryClientProviderProtocol**: Primary client access
- **DeviceDetailsProviderProtocol**: Device metadata (address_id, rooms, interface, name)
- **DeviceDescriptionProviderProtocol**: Device descriptions lookup
- **ParamsetDescriptionProviderProtocol**: Paramset descriptions and multi-channel checks
- **ParameterVisibilityProviderProtocol**: Parameter visibility rules
- **FileOperationsProtocol**: File I/O operations
- **DeviceDataRefresherProtocol**: Device data refresh operations
- **DataCacheProviderProtocol**: Data cache access (get_data method)
- **ChannelLookupProtocol**: Channel lookup by address
- **EventSubscriptionManagerProtocol**: Event subscription management
- **HubDataFetcherProtocol**: Hub data fetching operations
- **HubDataPointManagerProtocol**: Hub data point management (programs and sysvars)
- **HubProtocol**: Hub-level operations (inbox*dp, update_dp, fetch*\*\_data methods)
- **WeekProfileProtocol**: Week profile operations (schedule, get_schedule, set_schedule)

CentralUnit implements all protocols with explicit inheritance through structural subtyping. Each protocol interface defines a minimal API surface, allowing components to depend only on the specific functionality they need rather than the entire CentralUnit.

#### 3. Observer Pattern (EventBus-based)

```python
# DataPoints publish events via EventBus
# Subscribers receive notifications through the modern subscribe_to_* API

# Subscribe to data point updates
def on_value_changed(**kwargs):
    print(f"Value changed: {kwargs}")

unsubscribe = data_point.subscribe_to_data_point_updated(
    handler=on_value_changed,
    custom_id="my-app"
)

# Clean up subscription when done
unsubscribe()
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

#### 5. EventBus Pattern

The project uses a unified **EventBus** system for internal event communication. All subscription methods use the modern `subscribe_to_*` API:

```python
# EventBus API - Direct subscription
from aiohomematic.central.event_bus import DataPointUpdatedEvent

async def on_datapoint_update(event: DataPointUpdatedEvent) -> None:
    print(f"DataPoint {event.dpk} = {event.value}")

unsubscribe = central.event_bus.subscribe(
    event_type=DataPointUpdatedEvent,
    handler=on_datapoint_update
)
unsubscribe()

# Model API - Subscription via Device/Channel/DataPoint
def on_device_updated():
    print("Device state changed")

unsubscribe = device.subscribe_to_device_updated(handler=on_device_updated)
unsubscribe()

def on_value_changed(**kwargs):
    print(f"Value changed: {kwargs}")

unsubscribe = data_point.subscribe_to_data_point_updated(
    handler=on_value_changed,
    custom_id="my-app"
)
unsubscribe()
```

**Method Naming:**

- `subscribe_to_*` - All subscription methods use this modern naming
- `handler` parameter - Use `handler=` instead of `cb=`
- `unsubscribe()` - All subscriptions return an unsubscribe callable

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

Device-to-profile mappings are managed via `DeviceProfileRegistry`. Most new devices can use existing CustomDataPoint subclasses.

1. **Register with DeviceProfileRegistry** in the appropriate entity module (e.g., `switch.py`, `climate.py`):

```python
# In aiohomematic/model/custom/switch.py (or appropriate module)
from aiohomematic.const import DataPointCategory, DeviceProfile, Parameter
from aiohomematic.model.custom.registry import DeviceProfileRegistry, ExtendedDeviceConfig

# Simple registration
DeviceProfileRegistry.register(
    category=DataPointCategory.SWITCH,
    models="HmIP-NEW-SWITCH",           # Single model or tuple of models
    data_point_class=CustomDpSwitch,     # Existing or new CustomDataPoint class
    profile_type=DeviceProfile.IP_SWITCH,
    channels=(3,),                        # Channel(s) where STATE lives
)

# With extended configuration (additional data points)
DeviceProfileRegistry.register(
    category=DataPointCategory.CLIMATE,
    models=("HmIP-NEW-THERMO", "HmIP-NEW-THERMO-2"),
    data_point_class=CustomDpIpThermostat,
    profile_type=DeviceProfile.IP_THERMOSTAT,
    channels=(1,),
    schedule_channel_no=1,
    extended=ExtendedDeviceConfig(
        additional_data_points={
            0: (Parameter.SOME_EXTRA_PARAM,),
        },
    ),
)
```

2. **For devices needing multiple configurations** (e.g., lock + button lock):

```python
from aiohomematic.model.custom.registry import DeviceConfig, DeviceProfileRegistry

DeviceProfileRegistry.register_multiple(
    category=DataPointCategory.LOCK,
    models="HmIP-NEW-LOCK",
    configs=(
        DeviceConfig(
            data_point_class=CustomDpIpLock,
            profile_type=DeviceProfile.IP_LOCK,
        ),
        DeviceConfig(
            data_point_class=CustomDpButtonLock,
            profile_type=DeviceProfile.IP_BUTTON_LOCK,
            channels=(0,),
        ),
    ),
)
```

3. **Add tests** in `tests/test_model_*.py`

4. **See `docs/extension_points.md`** for detailed instructions and more examples

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

**IMPORTANT**: `aiohomematic/strings.json` is the **primary source** for all translation keys. The file `translations/en.json` is automatically synchronized from `strings.json`.

1. **Use translation in code**:

```python
from aiohomematic import i18n

# In code (for log messages)
_LOGGER.info(i18n.tr("log.my.message.key", param=value))
```

2. **Add to translation catalogs** (in this order):

```bash
# Step 1: Add key to aiohomematic/strings.json (PRIMARY SOURCE)
{
  "log.my.message.key": "My message with {param}"
}

# Step 2: Run sync script to copy to en.json
python script/check_i18n_catalogs.py --fix

# Step 3: Add German translation to translations/de.json
{
  "log.my.message.key": "Meine Nachricht mit {param}"
}
```

3. **Validate translations**:

```bash
python script/check_i18n.py aiohomematic/  # Check usage in code
python script/check_i18n_catalogs.py       # Check catalog sync
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
- **Protocol Interfaces**: `PascalCase` with `-Protocol` suffix (e.g., `ConfigProviderProtocol`, `ClientProviderProtocol`)
- **Functions/Methods**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private members**: `_leading_underscore`
- **Type variables**: `T`, `T_co`, `T_contra`

**Protocol Naming Convention**:

- **ALL** protocol interfaces must have the `-Protocol` suffix
- This prevents name collisions with implementing classes (e.g., `DeviceProtocol` vs `Device`)
- Makes protocols instantly recognizable in code
- Variable names using protocols keep semantic meaning (e.g., `config_provider: ConfigProviderProtocol`)

```python
# ✅ CORRECT - Protocol definition with suffix
@runtime_checkable
class ConfigProviderProtocol(Protocol):
    """Protocol for accessing configuration."""
    @property
    def config(self) -> CentralConfig: ...

# ✅ CORRECT - Variable name preserves semantic meaning
class Device:
    def __init__(self, *, config_provider: ConfigProviderProtocol):
        self._config_provider = config_provider  # "provider" remains in variable name

# ❌ WRONG - Missing -Protocol suffix causes collision
class Device(Protocol): ...  # Protocol
class Device: ...  # Implementation - NAME COLLISION!
```

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

#### Intentional camelCase Exceptions

The following use camelCase **by design** for backend compatibility:

1. **XML-RPC Callback Methods** in `aiohomematic/central/rpc_server.py`:

   - `event()`, `newDevices()`, `deleteDevices()`, `updateDevice()`, `replaceDevice()`, `readdedDevice()`, `listDevices()`
   - These method names are dictated by the Homematic XML-RPC protocol specification
   - The Homematic CCU/Homegear backend calls these methods by name

2. **SystemEventType Enum Values** in `aiohomematic/const.py`:
   - Values like `newDevices`, `deleteDevices`, `updateDevice`, etc.
   - These correspond directly to the backend event names for consistency

```python
# ✅ CORRECT - camelCase required by Homematic XML-RPC protocol
class HomeMaticXmlRpcServer:
    def event(self, interface_id, channel_address, parameter, value):
        """Handle event callback from CCU (method name required by protocol)."""
        ...

    def newDevices(self, interface_id, device_descriptions):
        """Handle new devices callback (method name required by protocol)."""
        ...

# ❌ WRONG - snake_case would break backend compatibility
def new_devices(self, ...):  # CCU cannot call this - protocol mismatch!
    ...
```

### Constants Organization

All constants are in `aiohomematic/const.py`:

```python
from aiohomematic.const import (
    Interface,           # Enum for interface types
    ParamsetKey,         # Enum for paramset keys
    SystemEventType,  # Enum for system events
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

| File                      | Purpose                    | Key Settings                       |
| ------------------------- | -------------------------- | ---------------------------------- |
| `pyproject.toml`          | Main project configuration | Build, dependencies, tool configs  |
| `.pre-commit-config.yaml` | Pre-commit hooks           | Linters, formatters, type checkers |
| `requirements.txt`        | Runtime dependencies       | aiohttp, orjson, voluptuous        |
| `requirements_test.txt`   | Test dependencies          | pytest, mypy, pylint, ruff         |
| `.yamllint`               | YAML linting rules         | YAML formatting standards          |
| `codecov.yml`             | Coverage configuration     | Coverage thresholds                |

### Core Source Files

| File                               | Lines  | Purpose                    |
| ---------------------------------- | ------ | -------------------------- |
| `aiohomematic/const.py`            | 1,273  | Constants, enums, patterns |
| `aiohomematic/support.py`          | 678    | Cross-cutting utilities    |
| `aiohomematic/central/__init__.py` | 2,390  | Central orchestration      |
| `aiohomematic/client/__init__.py`  | 1,944  | Client protocol adapters   |
| `aiohomematic/model/device.py`     | ~1,800 | Device model               |
| `aiohomematic/model/data_point.py` | ~1,200 | DataPoint base class       |

### Documentation Files

| File                              | Purpose                           |
| --------------------------------- | --------------------------------- |
| `README.md`                       | Project overview, quickstart      |
| `changelog.md`                    | Release history                   |
| `docs/architecture.md`            | Architecture overview             |
| `docs/data_flow.md`               | Data flow diagrams                |
| `docs/extension_points.md`        | How to extend the library         |
| `docs/sequence_diagrams.md`       | Sequence diagrams                 |
| `docs/homeassistant_lifecycle.md` | Home Assistant integration        |
| `docs/docstring_standards.md`     | Docstring style guide and rules   |
| `docs/docstring_templates.md`     | Ready-to-use docstring templates  |
| `docs/docstring_audit.md`         | Module categorization and roadmap |

### Test Files

| File                          | Purpose                           |
| ----------------------------- | --------------------------------- |
| `tests/conftest.py`           | Pytest fixtures and configuration |
| `tests/test_central.py`       | Central unit tests                |
| `tests/test_client.py`        | Client protocol tests             |
| `tests/test_model_climate.py` | Climate entity tests              |
| `tests/test_model_cover.py`   | Cover entity tests                |

### Development Scripts

| Script                          | Purpose                             |
| ------------------------------- | ----------------------------------- |
| `script/sort_class_members.py`  | Organize class members              |
| `script/check_i18n.py`          | Validate translation usage          |
| `script/check_i18n_catalogs.py` | Check translation completeness      |
| `script/lint_kwonly.py`         | Enforce keyword-only arguments      |
| `script/run-in-env.sh`          | Run commands in virtual environment |

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
from aiohomematic.const import Interface, ParamsetKey, SystemEventType

# Exceptions
from aiohomematic.exceptions import AioHomematicException, ClientException

# Device registration (for adding new device support)
from aiohomematic.model.custom.registry import DeviceProfileRegistry, DeviceConfig, ExtendedDeviceConfig
```

### Useful Links

- **GitHub**: https://github.com/sukramj/aiohomematic
- **Issues**: https://github.com/sukramj/aiohomematic/issues
- **Discussions**: https://github.com/sukramj/aiohomematic/discussions
- **Home Assistant Integration**: https://github.com/sukramj/homematicip_local
- **Example Usage**: See `example.py` in repository root

---

## Implementation Policy

This section defines mandatory rules for all implementations in this project.

### Refactoring Completion Checklist

**MANDATORY**: Every refactoring or feature implementation MUST complete ALL items before merging:

```
□ 1. Clean Code    - No legacy compatibility layers, deprecated aliases, or shims
□ 2. Migration     - Migration guide in docs/migrations/ (for breaking changes)
□ 3. Tests         - pytest tests/ passes without errors
□ 4. Linting       - pre-commit run --all-files passes without errors
□ 5. Changelog     - changelog.md updated with version entry
```

### Changelog Versioning Rules

**CRITICAL**: When updating `changelog.md`, ALWAYS check if the version has already been tagged:

1. **Check existing tags** before modifying any version entry:

   ```bash
   git tag --list '2025.12.*' | tail -5
   ```

2. **NEVER modify already-tagged versions**. Tagged versions are immutable.

3. **Create a NEW version** for new changes:

   - If `2025.12.40` is already tagged, create `2025.12.41`
   - New changes ALWAYS go into the untagged (newest) version

4. **Version structure in changelog**:

   ```markdown
   # Version 2025.12.41 (2025-12-20) ← NEW, untagged - add changes here

   ...

   # Version 2025.12.40 (2025-12-20) ← Tagged - DO NOT MODIFY

   ...
   ```

5. **When in doubt**, check git status to see which version is the latest untagged version.

### Implementation Plan Requirements

**CRITICAL**: Implementation plans created by Opus/Sonnet MUST be executable by Haiku without errors.

A valid implementation plan must:

1. **Resolve ALL Ambiguities Upfront**

   - No "decide later" or "TBD" items
   - Every decision point must have a concrete answer
   - If multiple approaches exist, one MUST be selected and documented

2. **Provide Exact File Paths**

   - Full paths to all files to be created/modified
   - Example: `aiohomematic/model/custom/new_device.py` (not just "create a new file")

3. **Include Complete Code Snippets**

   - Entire function/class implementations, not partial examples
   - All imports required for each file
   - Exact method signatures with full type annotations

4. **Specify Exact Locations for Edits**

   - Line numbers or unique context strings for modifications
   - Before/after code blocks for changes
   - Example: "In `device.py`, replace lines 145-150 with..."

5. **Document Dependencies and Order**

   - Which steps depend on which
   - Exact execution order
   - Files that must exist before others can be created

6. **Include Test Requirements**
   - Specific test cases to add
   - Expected test file locations
   - Test function names and what they verify

**Plan Template**:

````markdown
## Implementation Plan: {Feature Name}

### Overview

One paragraph describing what will be implemented and why.

### Prerequisites

- List existing files/classes/functions that will be used
- Any setup required before starting

### Step 1: {Description}

**File**: `full/path/to/file.py`
**Action**: Create / Modify / Delete

**Code**:

```python
# Complete code to add/replace
from __future__ import annotations
...
```
````

**Verification**: How to verify this step succeeded

### Step 2: ...

### Quality Gates

- [ ] pytest tests/ passes
- [ ] pre-commit run --all-files passes
- [ ] No mypy errors
- [ ] Changelog updated

````

### Clean Code Policy

When implementing new features or refactoring existing code:

1. **No Legacy Code**: After implementation, the codebase must be clean without any legacy compatibility layers, deprecated aliases, or backward-compatibility shims introduced during the change.

2. **No Backward Compatibility Layers**: Do not create:
   - Type aliases for old names
   - Re-exports of renamed symbols
   - Deprecation warnings for removed APIs
   - Compatibility adapters or wrappers
   - `# TODO: remove after migration` comments

3. **Complete Migration**: All usages of changed APIs must be updated in a single change. Partial migrations that leave legacy code are not acceptable.

4. **Protocol Inheritance**: When splitting protocols (e.g., `DeviceProtocol` into sub-protocols):
   - The implementation class (e.g., `Device`) must inherit from all sub-protocols
   - The composite protocol (e.g., `DeviceProtocol`) must inherit from all sub-protocols
   - No separate "legacy" protocol should remain

5. **Documentation Updates**: All changes must include:
   - Updated docstrings for modified classes/methods
   - Updated `*.md` documentation files
   - Migration guide for downstream consumers (e.g., Home Assistant)

### Quality Gate Commands

Run these commands before considering any implementation complete:

```bash
# 1. Run all tests
pytest tests/

# 2. Run all pre-commit hooks (includes ruff, mypy, pylint, etc.)
pre-commit run --all-files

# 3. Verify no TODO/FIXME related to migration
grep -r "TODO.*migration\|FIXME.*migration\|TODO.*remove\|TODO.*deprecated" aiohomematic/

# 4. Check for unused imports/code
ruff check --select F401,F841
````

### Migration Plan Requirements

For breaking changes affecting downstream projects (e.g., Home Assistant integration):

1. **Create Migration Guide** in `docs/migrations/`:

   - File naming: `{feature}_migration_{year}_{month}.md`
   - Example: `event_migration_2025_12.md`

2. **Required Sections**:

   ```markdown
   # Migration Guide: {Feature Name}

   ## Overview

   Brief description of what changed and why.

   ## Breaking Changes

   - List each breaking change with before/after code examples

   ## Migration Steps

   Step-by-step instructions for updating dependent code.

   ## Search-and-Replace Patterns

   Patterns for automated migration where applicable.

   ## Compatibility Notes

   Any edge cases or special considerations.
   ```

3. **Reference in Changelog**: Link to migration guide in changelog entry.

### Rationale

This policy ensures:

- Codebase remains clean and maintainable
- No accumulation of technical debt
- Clear migration path for downstream projects
- Single source of truth for APIs
- Implementation plans can be executed by any model without interpretation

---

## Tips for AI Assistants

### Do's

✅ **Always** include `from __future__ import annotations` at the top of Python files
✅ **Always** provide complete type annotations for all functions and methods
✅ **Always** run pre-commit hooks before committing
✅ **Always** write tests for new functionality
✅ **Always** update documentation when changing public APIs
✅ **Always** use keyword-only arguments for ALL parameters (excluding self/cls)
✅ **Always** use descriptive variable names
✅ **Always** handle exceptions with proper context
✅ **Always** complete the Refactoring Completion Checklist before finishing
✅ **Always** update changelog.md with breaking changes
✅ **Always** create implementation plans that are Haiku-executable

### Don'ts

❌ **Never** commit without type annotations
❌ **Never** skip pre-commit hooks
❌ **Never** commit to `master` or `devel` directly
❌ **Never** use `Any` type without justification
❌ **Never** perform I/O operations in model classes
❌ **Never** use bare `except:` clauses
❌ **Never** modify `aiohomematic/const.py` without thorough review
❌ **Never** break backward compatibility without major version bump
❌ **Never** leave legacy compatibility layers or deprecated aliases
❌ **Never** create plans with ambiguities or "TBD" items

### Refactoring Workflow

When performing a refactoring task, follow this workflow:

1. **Plan**: Create a detailed implementation plan (see Implementation Plan Requirements)
2. **Clarify**: Resolve ALL ambiguities before starting implementation
3. **Implement**: Make all changes following the exact plan
4. **Clean**: Remove all legacy code, aliases, and compatibility shims
5. **Test**: Run `pytest tests/` - all tests must pass
6. **Lint**: Run `pre-commit run --all-files` - no errors allowed
7. **Document**: Update changelog.md and create migration guide if needed
8. **Verify**: Check for leftover TODOs related to migration

### Implementation Plan Quality Standard

**A plan is only complete when Haiku can execute it without asking questions.**

Before finalizing any implementation plan, verify:

- [ ] Every file path is absolute and correct
- [ ] Every code block is complete (not "..." or "similar to above")
- [ ] Every import statement is explicitly listed
- [ ] Every type annotation is complete
- [ ] Every step has a clear verification method
- [ ] No decisions are deferred to implementation time

### When in Doubt

1. **Read the architecture docs**: `docs/architecture.md`
2. **Look at existing examples**: Similar functionality in codebase
3. **Run the tests**: `pytest tests/`
4. **Check the type hints**: `mypy` will guide you
5. **Review the changelog**: `changelog.md` for recent changes
6. **Check migration guides**: `docs/migrations/` for patterns

---

**Last Updated**: 2025-12-16
**Version**: 2025.12.30
