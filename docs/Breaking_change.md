# Breaking Changes Migration Guide

This document provides step-by-step instructions for migrating your application to the new version of aiohomematic.

---

## Overview

This release includes architectural improvements that require updates to import statements and some API usage patterns. Follow the steps below to migrate your application.

---

## Migration Steps

### Step 1: Update Protocol Interface Imports

**What changed**: The monolithic `aiohomematic/interfaces.py` file has been split into a package with focused modules for better maintainability.

**Before**:

```python
from aiohomematic.interfaces import (
    CentralInfo,
    ConfigProvider,
    ClientFactory,
    DeviceProtocol,
    ChannelProtocol,
    DataPointProtocol,
    TaskScheduler,
    FileOperations,
)
```

**After**:

```python
# Option 1: Import from the package (recommended - maintains backward compatibility)
from aiohomematic.interfaces import (
    CentralInfo,
    ConfigProvider,
    ClientFactory,
    DeviceProtocol,
    ChannelProtocol,
    DataPointProtocol,
    TaskScheduler,
    FileOperations,
)

# Option 2: Import from specific submodules (for explicit dependency management)
from aiohomematic.interfaces.central import CentralInfo, ConfigProvider, ClientFactory
from aiohomematic.interfaces.model import DeviceProtocol, ChannelProtocol, DataPointProtocol
from aiohomematic.interfaces.operations import TaskScheduler, FileOperations
```

**Action required**: No immediate action required if using `from aiohomematic.interfaces import ...`. The package `__init__.py` re-exports all protocols for backward compatibility.

**Status**: Complete

---

## Changelog

| Date       | Change                                       | Status   |
| ---------- | -------------------------------------------- | -------- |
| 2025-12-06 | Split interfaces.py into interfaces/ package | Complete |
| TBD        | Create shared mixins for custom entities     | Pending  |
| TBD        | Move INTERFACE_EVENT_SCHEMA to schemas.py    | Pending  |
| TBD        | Extract DataPointTypeResolver strategy       | Pending  |

---

## Version Compatibility

| aiohomematic Version   | Python Version | Breaking Changes |
| ---------------------- | -------------- | ---------------- |
| Current (pre-refactor) | 3.13+          | None             |
| Next (post-refactor)   | 3.13+          | See steps above  |

---

**Last Updated**: 2025-12-06
