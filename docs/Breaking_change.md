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

### Step 2: DataPointTypeResolver Available for Extension

**What changed**: The data point type determination logic has been refactored into a `DataPointTypeResolver` class with a lookup table strategy. This makes it easier to extend the mapping for custom parameter types.

**Before**: The `_determine_data_point_type()` function used a nested if-elif tree that was difficult to extend.

**After**: The new `DataPointTypeResolver` class provides:

- A lookup table (`_WRITABLE_TYPE_MAP`) for standard type mappings
- Separate methods for handling ACTION types, writable types, and read-only types
- Clear extension points for custom parameter handling

**Usage**:

```python
from aiohomematic.model.generic import DataPointTypeResolver

# Use the resolver directly
dp_type = DataPointTypeResolver.resolve(
    channel=channel,
    parameter="LEVEL",
    parameter_data=parameter_data,
)
```

**Action required**: No immediate action required. The existing `_determine_data_point_type()` function still works and now delegates to the resolver.

**Status**: Complete

---

### Step 3: Login Rate Limiting

**What changed**: The JSON-RPC client now implements exponential backoff for failed login attempts to protect against brute force attacks.

**Behavior**:

- After a failed login, subsequent attempts are delayed with exponential backoff
- Initial backoff: 1 second, multiplied by 2 after each failure
- Maximum backoff: 60 seconds
- Warning logged when rate limiting is active
- Error logged after 5 consecutive failed attempts
- Counters reset on successful login

**New constants in `aiohomematic.const`**:

- `LOGIN_MAX_FAILED_ATTEMPTS = 5`
- `LOGIN_INITIAL_BACKOFF_SECONDS = 1.0`
- `LOGIN_MAX_BACKOFF_SECONDS = 60.0`
- `LOGIN_BACKOFF_MULTIPLIER = 2.0`

**Action required**: No action required. This is a new security feature that activates automatically on failed logins.

**Status**: Complete

---

## Changelog

| Date       | Change                                           | Status   |
| ---------- | ------------------------------------------------ | -------- |
| 2025-12-06 | Split interfaces.py into interfaces/ package     | Complete |
| 2025-12-06 | Create shared mixins for custom entities         | Complete |
| 2025-12-06 | Move INTERFACE_EVENT_SCHEMA to schemas.py        | Complete |
| 2025-12-06 | Extract DataPointTypeResolver strategy           | Complete |
| 2025-12-06 | Add login rate limiting with exponential backoff | Complete |
| 2025-12-06 | Add error message sanitization helpers           | Complete |

---

### Step 4: Error Message Sanitization

**What changed**: Added sanitization utilities to protect sensitive information in error messages and logs.

**New features**:

- `sanitize_error_message(message)`: Sanitizes error messages by redacting:

  - IP addresses → `<ip-redacted>`
  - Hostnames → `<host-redacted>`
  - Session IDs → `session_id=<redacted>`
  - Passwords → `password=<redacted>`

- `RpcContext.fmt(sanitize=True)`: Format context without host information
- `RpcContext.fmt_sanitized()`: Convenience method for sanitized output

**Usage**:

```python
from aiohomematic.client._rpc_errors import sanitize_error_message, RpcContext

# Sanitize an error message
safe_msg = sanitize_error_message("Connection failed to 192.168.1.100")
# Result: "Connection failed to <ip-redacted>"

# Use sanitized context
ctx = RpcContext(protocol="JSON-RPC", method="login", host="192.168.1.100")
print(ctx.fmt_sanitized())  # "protocol=JSON-RPC, method=login"
```

**Action required**: No action required. These are new utility functions for enhanced security.

**Status**: Complete

---

## Version Compatibility

| aiohomematic Version   | Python Version | Breaking Changes |
| ---------------------- | -------------- | ---------------- |
| Current (pre-refactor) | 3.13+          | None             |
| Next (post-refactor)   | 3.13+          | See steps above  |

---

**Last Updated**: 2025-12-06
