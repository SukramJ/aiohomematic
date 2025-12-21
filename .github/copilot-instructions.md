# GitHub Copilot Instructions for aiohomematic

This document provides guidance for GitHub Copilot when working with the aiohomematic codebase.

## Project Overview

**aiohomematic** is an async Python library for controlling Homematic and HomematicIP devices. It powers the Home Assistant integration "Homematic(IP) Local".

- **Python Version**: 3.13+
- **Type Safety**: Fully typed with mypy strict mode
- **Async Framework**: AsyncIO-based

## Mandatory Code Standards

### Required Import

Every Python file MUST start with:

```python
from __future__ import annotations
```

### Type Annotations

All code MUST be fully typed. mypy runs in strict mode.

```python
# Correct
def get_device(self, address: str) -> Device | None:
    """Return device by address."""
    return self._devices.get(address)

# Incorrect - missing type annotations
def get_device(self, address):
    return self._devices.get(address)
```

### Keyword-Only Arguments

Use keyword-only arguments for functions with multiple parameters:

```python
def create_client(
    *,
    host: str,
    username: str,
    password: str,
    port: int = 2001,
) -> Client:
    """Create a new client."""
    ...
```

### Docstrings

- End all docstrings with a period (`.`)
- Use imperative mood for functions/methods ("Return the device", not "Returns")
- Use declarative statements for classes ("Represents a device")

```python
def get_value(self, parameter: str) -> Any:
    """Return the current parameter value."""

class Device:
    """Representation of a Homematic device."""
```

### Import Order

```python
from __future__ import annotations

# 1. Standard library
import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING

# 2. Third-party
import aiohttp

# 3. First-party
from aiohomematic.const import Interface

# 4. TYPE_CHECKING imports
if TYPE_CHECKING:
    from aiohomematic.central import CentralUnit
```

## Architecture Guidelines

### Protocol-Based Dependency Injection

Components use protocol interfaces for loose coupling:

```python
from aiohomematic.interfaces import ConfigProviderProtocol

class MyComponent:
    def __init__(self, *, config_provider: ConfigProviderProtocol) -> None:
        self._config_provider = config_provider
```

Protocol naming convention: Always use `-Protocol` suffix (e.g., `ConfigProviderProtocol`).

### Model Layer

Model classes (`Device`, `Channel`, `DataPoint`) perform NO I/O operations. They are pure domain models.

### Error Handling

Use custom exceptions from `aiohomematic/exceptions.py`:

```python
from aiohomematic.exceptions import ClientException

raise ClientException(f"Failed to connect to {host}:{port}")
```

## Pull Request Guidelines

### Branch Target

- Create feature branches from `devel`
- Submit PRs to the `devel` branch (NOT `master`)

### Quality Checks

All PRs must pass:

1. `pytest tests/` - All tests pass
2. `pre-commit run --all-files` - Linting, formatting, type checking
3. No mypy errors
4. Update `changelog.md` for user-facing changes

### Commit Messages

Use conventional commit format:

```
feat(model): Add support for new device type
fix(client): Handle connection timeout gracefully
docs(readme): Update installation instructions
```

## Code Style Quick Reference

| Rule | Example |
|------|---------|
| Line length | 120 characters max |
| String quotes | Double quotes preferred |
| Type unions | `str \| None` (not `Optional[str]`) |
| Collections | Use `collections.abc` (not `typing`) |
| Constants | `UPPER_SNAKE_CASE` |
| Private members | `_leading_underscore` |

## Common Patterns

### Async Operations

```python
async def fetch_data(self) -> dict[str, Any]:
    """Fetch data from backend."""
    async with asyncio.timeout(10):
        return await self._client.get_data()
```

### Property Definitions

```python
@property
def device_address(self) -> str:
    """Return the device address."""
    return self._device_address
```

### Event Subscriptions

```python
unsubscribe = data_point.subscribe_to_data_point_updated(
    handler=on_value_changed,
    custom_id="my-handler"
)
# Later: unsubscribe()
```

## Files to Know

| File | Purpose |
|------|---------|
| `aiohomematic/const.py` | All constants and enums |
| `aiohomematic/exceptions.py` | Custom exceptions |
| `aiohomematic/interfaces/` | Protocol definitions |
| `CLAUDE.md` | Comprehensive development guide |

## What NOT to Do

- Don't commit without type annotations
- Don't use `Any` without justification
- Don't perform I/O in model classes
- Don't use bare `except:` clauses
- Don't skip pre-commit hooks
- Don't commit directly to `master` or `devel`
