# Migration Guide: Central State Machine & EventBus Connection State

**Version:** 2025.12.23
**Date:** 2025-12-12
**Breaking Change:** Yes

## Overview

This release introduces a new **Central State Machine** architecture for improved reconnection reliability and migrates connection state notifications from callback-based API to the unified **EventBus** pattern.

**Impact:** This is a **breaking change** for the Home Assistant integration and any other consumers that use connection state callbacks.

## What Changed

### 1. Connection State Callbacks → EventBus Migration

#### Before (REMOVED - No Longer Works)

```python
from aiohomematic.central import CentralUnit

def on_state_change(interface_id: str, connected: bool) -> None:
    """Called when interface connection state changes."""
    status = "connected" if connected else "disconnected"
    print(f"{interface_id}: {status}")

# Register callback
unsubscribe = central.connection_state.register_state_change_callback(
    callback=on_state_change
)

# Later: stop receiving notifications
unsubscribe()
```

#### After (EventBus-Based)

```python
from aiohomematic.central import CentralUnit
from aiohomematic.central.event_bus import ConnectionStateChangedEvent

async def on_connection_state_changed(event: ConnectionStateChangedEvent) -> None:
    """Called when interface connection state changes."""
    status = "connected" if event.connected else "disconnected"
    print(f"{event.interface_id}: {status}")

# Subscribe to event
unsubscribe = central.event_bus.subscribe(
    event_type=ConnectionStateChangedEvent,
    handler=on_connection_state_changed
)

# Later: stop receiving notifications
unsubscribe()
```

**Key Differences:**

- Handler is now `async` (EventBus handlers are coroutines)
- Handler receives an `Event` object instead of individual parameters
- Event object has `interface_id` and `connected` properties
- Subscription is via `event_bus.subscribe()` instead of `register_state_change_callback()`

### 2. New Central State Machine

A new **CentralState** enum has been introduced to track the overall system state:

```python
from aiohomematic.const import CentralState

class CentralState(StrEnum):
    """Central State Machine states for overall system health orchestration."""

    STARTING = "starting"          # System is starting up
    INITIALIZING = "initializing"  # Clients are being initialized
    RUNNING = "running"            # ALL clients are CONNECTED ✅
    DEGRADED = "degraded"          # At least one client is not connected ⚠️
    RECOVERING = "recovering"      # System is attempting recovery
    FAILED = "failed"              # Max retries reached ❌
    STOPPED = "stopped"            # System has been stopped
```

**Important:** The `RUNNING` state now means **ALL** clients are connected, not just "at least one".

### 3. New CentralStateChangedEvent

Monitor the overall system state with the new event:

```python
from aiohomematic.central.event_bus import CentralStateChangedEvent
from aiohomematic.const import CentralState

async def on_central_state_changed(event: CentralStateChangedEvent) -> None:
    """Called when overall central state changes."""
    print(f"Central: {event.old_state} → {event.new_state}")
    print(f"Reason: {event.reason}")

    if event.new_state == CentralState.RUNNING:
        print("✅ All clients connected!")
    elif event.new_state == CentralState.DEGRADED:
        print("⚠️ Some clients disconnected")
    elif event.new_state == CentralState.FAILED:
        print("❌ Recovery failed - max retries reached")

# Subscribe to central state changes
unsubscribe = central.event_bus.subscribe(
    event_type=CentralStateChangedEvent,
    handler=on_central_state_changed
)
```

### 4. New Properties on CentralUnit

```python
# New properties for Central State Machine
current_state: CentralState = central.central_state
state_machine: CentralStateMachine = central.central_state_machine

# Existing properties (unchanged for backward compatibility)
is_available: bool = central.available
legacy_state: CentralUnitState = central.state
```

## Migration Steps for Home Assistant Integration

### Step 1: Replace Connection State Callbacks

**Find all usages of:**

```python
central.connection_state.register_state_change_callback(...)
```

**Replace with:**

```python
from aiohomematic.central.event_bus import ConnectionStateChangedEvent

async def on_connection_state_changed(event: ConnectionStateChangedEvent) -> None:
    # Access event.interface_id and event.connected
    ...

unsubscribe = central.event_bus.subscribe(
    event_type=ConnectionStateChangedEvent,
    handler=on_connection_state_changed
)
```

### Step 2: Update Handler Signatures

**Old signature:**

```python
def on_state_change(interface_id: str, connected: bool) -> None:
    ...
```

**New signature:**

```python
async def on_connection_state_changed(event: ConnectionStateChangedEvent) -> None:
    interface_id = event.interface_id
    connected = event.connected
    ...
```

### Step 3: Subscribe to Central State Changes (Recommended)

Add monitoring for the overall system state:

```python
from aiohomematic.central.event_bus import CentralStateChangedEvent
from aiohomematic.const import CentralState

async def on_central_state_changed(event: CentralStateChangedEvent) -> None:
    """Handle central state changes."""
    if event.new_state == CentralState.DEGRADED:
        # Show warning in UI - some interfaces disconnected
        _LOGGER.warning(
            "Central in DEGRADED state: %s (reason: %s)",
            event.new_state,
            event.reason
        )
    elif event.new_state == CentralState.FAILED:
        # Show error in UI - recovery failed
        _LOGGER.error(
            "Central in FAILED state: %s (reason: %s)",
            event.new_state,
            event.reason
        )
    elif event.new_state == CentralState.RUNNING:
        # All interfaces connected
        _LOGGER.info("Central is RUNNING - all interfaces connected")

central.event_bus.subscribe(
    event_type=CentralStateChangedEvent,
    handler=on_central_state_changed
)
```

### Step 4: Update Availability Checks

The semantics of `RUNNING` have changed:

**Before:**

```python
# central.state == CentralUnitState.RUNNING meant "at least one client connected"
if central.state == CentralUnitState.RUNNING:
    # System is operational
    ...
```

**After:**

```python
# Option 1: Use central_state for precise state tracking
if central.central_state == CentralState.RUNNING:
    # ALL clients connected
    ...
elif central.central_state == CentralState.DEGRADED:
    # Some clients connected, some disconnected
    ...

# Option 2: Use available property for "any client connected"
if central.available:
    # At least one client is usable (backward compatible)
    ...
```

## Example: Full Migration

### Before

```python
class HomematicHub:
    def __init__(self, central: CentralUnit):
        self.central = central

    async def setup(self):
        # Old callback registration
        self._unsubscribe_state = self.central.connection_state.register_state_change_callback(
            callback=self._on_state_change
        )

    def _on_state_change(self, interface_id: str, connected: bool) -> None:
        """Handle connection state changes (sync function)."""
        if connected:
            print(f"{interface_id} connected")
        else:
            print(f"{interface_id} disconnected")

    async def cleanup(self):
        if self._unsubscribe_state:
            self._unsubscribe_state()
```

### After

```python
from aiohomematic.central.event_bus import (
    ConnectionStateChangedEvent,
    CentralStateChangedEvent,
)
from aiohomematic.const import CentralState

class HomematicHub:
    def __init__(self, central: CentralUnit):
        self.central = central
        self._unsubscribe_connection: Callable[[], None] | None = None
        self._unsubscribe_central: Callable[[], None] | None = None

    async def setup(self):
        # Subscribe to connection state changes (per interface)
        self._unsubscribe_connection = self.central.event_bus.subscribe(
            event_type=ConnectionStateChangedEvent,
            handler=self._on_connection_state_changed
        )

        # Subscribe to central state changes (overall system)
        self._unsubscribe_central = self.central.event_bus.subscribe(
            event_type=CentralStateChangedEvent,
            handler=self._on_central_state_changed
        )

    async def _on_connection_state_changed(self, event: ConnectionStateChangedEvent) -> None:
        """Handle connection state changes (async function)."""
        if event.connected:
            print(f"{event.interface_id} connected")
        else:
            print(f"{event.interface_id} disconnected")

    async def _on_central_state_changed(self, event: CentralStateChangedEvent) -> None:
        """Handle central state changes."""
        if event.new_state == CentralState.RUNNING:
            print("✅ All interfaces connected")
        elif event.new_state == CentralState.DEGRADED:
            print(f"⚠️ System degraded: {event.reason}")
        elif event.new_state == CentralState.FAILED:
            print(f"❌ System failed: {event.reason}")

    async def cleanup(self):
        if self._unsubscribe_connection:
            self._unsubscribe_connection()
        if self._unsubscribe_central:
            self._unsubscribe_central()
```

## Additional Events Available

Besides `ConnectionStateChangedEvent` and `CentralStateChangedEvent`, the EventBus also provides:

- `ClientStateChangedEvent` - Individual client state transitions (CREATED → INITIALIZING → CONNECTED, etc.)
- `DataPointUpdatedEvent` - DataPoint value updates
- `DeviceUpdatedEvent` - Device state updates
- `HomematicEvent` - Backend events from CCU
- And more... (see `aiohomematic/central/event_bus.py`)

## Benefits

### For End Users

- **Better reconnection reliability**: Automatic recovery with exponential backoff
- **Clearer system state**: Distinct states for RUNNING, DEGRADED, RECOVERING, FAILED
- **Faster recovery**: Coordinated client recovery with health tracking
- **Proper failure handling**: Max retries (8 attempts) with heartbeat retry every 60s

### For Developers

- **Unified event system**: All events use the same EventBus pattern
- **Better testability**: Events are easier to test than callbacks
- **Type safety**: Event objects are strongly typed
- **Consistency**: Same pattern across the entire codebase

## Backward Compatibility

### Removed APIs (Breaking Changes)

- ❌ `CentralConnectionState.register_state_change_callback()` - Use `EventBus.subscribe(ConnectionStateChangedEvent)` instead
- ❌ `StateChangeCallback` type alias - Renamed to `StateChangeCallbackProtocol`

### Deprecated APIs (Still Available)

- ⚠️ `CentralUnit.available` property - Still works, but consider using `central_state` for more precise tracking
- ⚠️ `CentralUnit.state` property - Returns legacy `CentralUnitState`, but `central_state` provides better granularity

### New APIs (Additive)

- ✅ `CentralUnit.central_state` property - Returns `CentralState` enum
- ✅ `CentralUnit.central_state_machine` property - Access to state machine
- ✅ `EventBus.subscribe(ConnectionStateChangedEvent)` - Subscribe to connection state changes
- ✅ `EventBus.subscribe(CentralStateChangedEvent)` - Subscribe to central state changes
- ✅ `EventBus.subscribe(ClientStateChangedEvent)` - Subscribe to client state changes

## Troubleshooting

### Issue: Handler not called

**Problem:**

```python
# Handler is not async - will fail silently
def on_connection_changed(event: ConnectionStateChangedEvent) -> None:
    ...
```

**Solution:**

```python
# Make handler async
async def on_connection_changed(event: ConnectionStateChangedEvent) -> None:
    ...
```

### Issue: AttributeError on event

**Problem:**

```python
async def on_connection_changed(event: ConnectionStateChangedEvent) -> None:
    # Trying to access old callback parameters
    interface_id = event.interface_id  # ✅ Works
    connected = event.is_connected      # ❌ Wrong attribute name
```

**Solution:**

```python
async def on_connection_changed(event: ConnectionStateChangedEvent) -> None:
    interface_id = event.interface_id  # ✅ Correct
    connected = event.connected        # ✅ Correct attribute name
```

### Issue: Central shows DEGRADED instead of RUNNING

**Behavior:** This is expected behavior when not all clients are connected.

**Before:** `RUNNING` meant "at least one client connected"
**After:** `RUNNING` means "ALL clients connected"

If you need "at least one client connected", use:

```python
if central.available:
    # At least one client is usable
    ...
```

## Timeline

- **Version 2025.12.23** (2025-12-12): Initial release with Central State Machine
- **Migration deadline**: Immediate - old callback API has been removed

## References

- Changelog: `changelog.md` (Version 2025.12.23)
- EventBus Documentation: `docs/event_bus.md`
- Architecture Documentation: `docs/architecture.md`
- Sequence Diagrams: `docs/sequence_diagrams.md` (includes state machine flows)

## Questions?

For questions or issues with the migration, please:

1. Check the EventBus documentation: `docs/event_bus.md`
2. Review example code in `tests/test_central_state_machine.py`
3. Open an issue on GitHub: https://github.com/sukramj/aiohomematic/issues
