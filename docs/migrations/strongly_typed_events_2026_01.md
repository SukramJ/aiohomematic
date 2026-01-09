# Migration Guide: Strongly Typed Events (2026.1.24)

## Overview

Multiple event classes and the `IntegrationIssue` dataclass have been refactored to use strong typing with enums instead of string-based fields. This prevents consumer errors caused by incorrect string comparisons and provides better IDE support.

## Breaking Changes

### 1. IntegrationIssue Changes

#### `severity` Field Type Changed

**Before:**

```python
issue.severity == "error"  # string comparison
issue.severity == "warning"  # string comparison
```

**After:**

```python
from aiohomematic.const import IntegrationIssueSeverity

issue.severity == IntegrationIssueSeverity.ERROR  # enum comparison
issue.severity == IntegrationIssueSeverity.WARNING  # enum comparison
```

#### `issue_type` Field Added

**Before:**

```python
if issue.issue_id.startswith("ping_pong_mismatch_"):
    # handle ping/pong issue
elif issue.issue_id.startswith("fetch_data_failed_"):
    # handle fetch data issue
```

**After:**

```python
from aiohomematic.const import IntegrationIssueType

if issue.issue_type == IntegrationIssueType.PING_PONG_MISMATCH:
    # handle ping/pong issue
elif issue.issue_type == IntegrationIssueType.FETCH_DATA_FAILED:
    # handle fetch data issue
```

#### `mismatch_count` Field Type Changed

**Before:**

```python
issue.translation_placeholders.get("mismatch_count") == "0"  # string comparison
```

**After:**

```python
issue.mismatch_count == 0  # int comparison
```

#### `mismatch_type` Field Type

**Before:**

```python
mismatch_type = issue.translation_placeholders.get("mismatch_type")
```

**After:**

```python
mismatch_type = issue.mismatch_type  # PingPongMismatchType | None
```

### 2. ClientStateChangedEvent Changes

**Before:**

```python
event.old_state == "connected"  # string comparison
event.new_state == "disconnected"  # string comparison
```

**After:**

```python
from aiohomematic.const import ClientState

event.old_state == ClientState.CONNECTED  # enum comparison
event.new_state == ClientState.DISCONNECTED  # enum comparison
```

### 3. CentralStateChangedEvent Changes

**Before:**

```python
event.old_state == "running"  # string comparison
event.new_state == "degraded"  # string comparison
```

**After:**

```python
from aiohomematic.const import CentralState

event.old_state == CentralState.RUNNING  # enum comparison
event.new_state == CentralState.DEGRADED  # enum comparison
```

### 4. DataRefreshTriggeredEvent / DataRefreshCompletedEvent Changes

**Before:**

```python
event.refresh_type == "client_data"  # string comparison
event.refresh_type == "sysvar"  # string comparison
```

**After:**

```python
from aiohomematic.const import DataRefreshType

event.refresh_type == DataRefreshType.CLIENT_DATA  # enum comparison
event.refresh_type == DataRefreshType.SYSVAR  # enum comparison
```

### 5. ProgramExecutedEvent Changes

**Before:**

```python
event.triggered_by == "api"  # string comparison
event.triggered_by == "user"  # string comparison
```

**After:**

```python
from aiohomematic.const import ProgramTrigger

event.triggered_by == ProgramTrigger.API  # enum comparison
event.triggered_by == ProgramTrigger.USER  # enum comparison
```

## New Enum Values

### IntegrationIssueSeverity

```python
class IntegrationIssueSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
```

### IntegrationIssueType

```python
class IntegrationIssueType(StrEnum):
    PING_PONG_MISMATCH = "ping_pong_mismatch"
    FETCH_DATA_FAILED = "fetch_data_failed"
```

### DataRefreshType

```python
class DataRefreshType(StrEnum):
    CLIENT_DATA = "client_data"
    INBOX = "inbox"
    METRICS = "metrics"
    PROGRAM = "program"
    SYSTEM_UPDATE = "system_update"
    SYSVAR = "sysvar"
```

### ProgramTrigger

```python
class ProgramTrigger(StrEnum):
    API = "api"
    USER = "user"
    SCHEDULER = "scheduler"
    AUTOMATION = "automation"
```

## Migration Steps

### For Home Assistant Integration (homematicip_local)

1. **Update imports:**

   ```python
   from aiohomematic.const import (
       IntegrationIssueSeverity,
       IntegrationIssueType,
   )
   ```

2. **Update severity comparisons:**

   ```python
   # Before
   severity = ir.IssueSeverity.ERROR if issue.severity == "error" else ir.IssueSeverity.WARNING

   # After
   severity = (
       ir.IssueSeverity.ERROR
       if issue.severity == IntegrationIssueSeverity.ERROR
       else ir.IssueSeverity.WARNING
   )
   ```

3. **Update issue type checks:**

   ```python
   # Before
   if issue.translation_key == "ping_pong_mismatch" and issue_placeholders.get("mismatch_count") == "0":

   # After
   if issue.issue_type == IntegrationIssueType.PING_PONG_MISMATCH and issue.mismatch_count == 0:
   ```

4. **Translation placeholders are still available:**
   The `translation_placeholders` property still returns a `dict[str, str]` for passing to HA's `async_create_issue()`. The values are automatically converted to strings:

   ```python
   ir.async_create_issue(
       ...,
       translation_key=issue.translation_key,  # Still works
       translation_placeholders=issue.translation_placeholders,  # Still works
   )
   ```

### For Event Subscribers

If you subscribe to state change events and compare states:

```python
# Before
async def on_client_state(*, event: ClientStateChangedEvent) -> None:
    if event.new_state == "connected":
        ...

# After
from aiohomematic.const import ClientState

async def on_client_state(*, event: ClientStateChangedEvent) -> None:
    if event.new_state == ClientState.CONNECTED:
        ...
```

## Compatibility Notes

- The `translation_key` property still returns a string value for HA translations
- The `issue_id` property still returns a string for HA issue identification
- The `translation_placeholders` property converts all values to strings for HA compatibility
- All enum values are `StrEnum` so they can still be compared to strings if needed (but enum comparison is preferred)
