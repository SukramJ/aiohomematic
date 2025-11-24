# EventBus Migration Guide for Home Assistant Integration

This guide explains how to migrate the `homematicip_local` Home Assistant integration from the legacy callback system to the new EventBus API in aiohomematic.

## Table of Contents

1. [Overview](#overview)
2. [Benefits of EventBus](#benefits-of-eventbus)
3. [Migration Strategy](#migration-strategy)
4. [API Changes](#api-changes)
5. [Code Examples](#code-examples)
6. [Testing](#testing)
7. [Rollback Plan](#rollback-plan)

---

## Overview

The aiohomematic library has introduced a new **EventBus** system that replaces the scattered callback registration methods with a unified, type-safe event subscription API.

### What Changed

**Before (Legacy API):**

```python
# Multiple different callback registration methods
central.subscribe_backend_system_callback(cb=system_callback)
central.subscribe_backend_parameter_callback(cb=parameter_callback)
central.subscribe_homematic_callback(cb=homematic_callback)
```

**After (EventBus API):**

```python
# Unified event subscription
central.event_bus.subscribe(event_type=BackendSystemEventData, handler=system_handler)
central.event_bus.subscribe(event_type=BackendParameterEvent, handler=parameter_handler)
central.event_bus.subscribe(event_type=HomematicEvent, handler=homematic_handler)
```

### Compatibility

⚠️ **BREAKING CHANGE IN v2025.11.16+**:

- **CentralUnit Callbacks Removed**: `register_backend_system_callback()`, `register_backend_parameter_callback()`, and `register_homematic_callback()` have been completely removed from CentralUnit
- **Device/Channel/DataPoint Callbacks**: Still available as backward-compatible adapters that delegate to EventBus
- **Migration Required**: Integrations using CentralUnit callbacks must migrate to EventBus immediately
- **Gradual Migration Path**: Device/Channel/DataPoint callback adapters will remain for extended backward compatibility

### ⚠️ Breaking Changes

**CentralUnit Callbacks - REMOVED as of v2025.11.16:**

| Method                                           | Status      | Migration                                                                 |
| ------------------------------------------------ | ----------- | ------------------------------------------------------------------------- |
| `central.subscribe_backend_parameter_callback()` | **REMOVED** | Use `central.event_bus.subscribe(event_type=BackendParameterEvent, ...)`  |
| `central.subscribe_backend_system_callback()`    | **REMOVED** | Use `central.event_bus.subscribe(event_type=BackendSystemEventData, ...)` |
| `central.subscribe_homematic_callback()`         | **REMOVED** | Use `central.event_bus.subscribe(event_type=HomematicEvent, ...)`         |

**What Changed:**

- ❌ **Removed**: CentralUnit no longer exposes callback registration methods
- ✅ **Available**: EventBus API provides replacements
- ✅ **Migration Period**: You can migrate callbacks one at a time
- ⚠️ **Action Required**: Update integrations immediately to use EventBus

**Timeline:**

| Version        | Status              | Action                                           |
| -------------- | ------------------- | ------------------------------------------------ |
| **2025.11.16** | **BREAKING CHANGE** | Legacy CentralUnit callbacks removed             |
| **2026.Q1+**   | Stable              | EventBus is the standard API                     |
| **Future**     | Possible removal    | Device/Channel/DataPoint callback adapters (TBD) |

**Device/Channel/DataPoint Callbacks - BACKWARD COMPATIBLE:**

Device, Channel, and DataPoint classes still expose their callback registration methods. These are implemented as adapters that subscribe to EventBus internally:

- `device.subscribe_device_updated_callback()`
- `device.subscribe_firmware_update_callback()`
- `channel.subscribe_link_peer_changed_callback()`
- `data_point.subscribe_data_point_updated_callback()`
- `data_point.subscribe_device_removed_callback()`

**Status**: These adapters will remain available for extended backward compatibility. Migration is recommended but not immediately required for these.

**Recommended Action:**

Migrate CentralUnit callback usage to EventBus API immediately. See [Migration Strategy](#migration-strategy) below.

---

## Benefits of EventBus

### 1. Type Safety

```python
# EventBus provides type-safe events with IDE autocomplete
async def on_datapoint_updated(event: DataPointUpdatedEvent) -> None:
    # IDE knows event.dpk, event.value, event.received_at
    print(f"DataPoint {event.dpk.channel_address}:{event.dpk.parameter} = {event.value}")
```

### 2. Error Isolation

```python
# One handler's exception doesn't affect other handlers
bus.subscribe(event_type=DataPointUpdatedEvent, handler=handler1)  # Might fail
bus.subscribe(event_type=DataPointUpdatedEvent, handler=handler2)  # Will still run
```

### 3. Cleaner Unsubscription

```python
# Old way: manage callbacks manually
central.subscribe_backend_system_callback(cb=callback)
# Later: need to call _unregister_backend_system_callback

# New way: returned callable
unsubscribe = central.event_bus.subscribe(event_type=BackendSystemEventData, handler=callback)
# Later: just call it
unsubscribe()
```

### 4. Event Filtering

```python
# Filter events in the handler
async def filtered_handler(event: DataPointUpdatedEvent) -> None:
    if event.dpk.channel_address.startswith("VCU"):
        await process_event(event)

central.event_bus.subscribe(event_type=DataPointUpdatedEvent, handler=filtered_handler)
```

### 5. Debugging Support

```python
# Built-in event statistics
stats = central.event_bus.get_event_stats()
print(f"DataPointUpdatedEvent published {stats['DataPointUpdatedEvent']} times")

# Check subscription count
count = central.event_bus.get_subscription_count(event_type=DataPointUpdatedEvent)
print(f"{count} handlers subscribed")
```

---

## Migration Strategy

### Phase 1: Add EventBus Subscriptions (Parallel)

Keep legacy callbacks and add EventBus subscriptions alongside them.

```python
# In your coordinator/integration setup
async def async_setup_entry(hass, entry):
    central = create_central(...)

    # Keep existing legacy callbacks (for now)
    central.subscribe_backend_system_callback(cb=_system_callback)

    # Add new EventBus subscriptions
    unsubscribe_system = central.event_bus.subscribe(
        event_type=BackendSystemEventData,
        handler=_on_system_event
    )

    # Store unsubscribe callbacks for cleanup
    entry.async_on_unload(unsubscribe_system)
```

### Phase 2: Test EventBus Handlers

Verify EventBus handlers work correctly in parallel with legacy callbacks.

### Phase 3: Remove Legacy Callbacks

Once EventBus is proven stable, remove legacy callback registrations.

```python
async def async_setup_entry(hass, entry):
    central = create_central(...)

    # Only EventBus subscriptions
    unsubscribe_system = central.event_bus.subscribe(
        event_type=BackendSystemEventData,
        handler=_on_system_event
    )

    entry.async_on_unload(unsubscribe_system)
```

---

## API Changes

### 1. Backend System Events

**Legacy API:**

```python
def system_callback(*, system_event: BackendSystemEvent, **kwargs) -> None:
    if system_event == BackendSystemEvent.DEVICES_CREATED:
        device_count = kwargs.get("device_count", 0)
        # Handle event

central.subscribe_backend_system_callback(cb=system_callback)
```

**EventBus API:**

```python
from aiohomematic.central.event_bus import BackendSystemEventData

async def on_system_event(event: BackendSystemEventData) -> None:
    if event.system_event == BackendSystemEvent.DEVICES_CREATED:
        device_count = event.data.get("device_count", 0)
        # Handle event

unsubscribe = central.event_bus.subscribe(
    event_type=BackendSystemEventData,
    handler=on_system_event
)
```

**Key Changes:**

- Event data in `event.data` instead of `**kwargs`
- Handler can be async (recommended) or sync
- Returns unsubscribe callable

### 2. Backend Parameter Events

**Legacy API:**

```python
def parameter_callback(
    *,
    interface_id: str,
    channel_address: str,
    parameter: str,
    value: Any
) -> None:
    # Handle parameter update

central.subscribe_backend_parameter_callback(cb=parameter_callback)
```

**EventBus API:**

```python
from aiohomematic.central.event_bus import BackendParameterEvent

async def on_parameter_event(event: BackendParameterEvent) -> None:
    # Access via event attributes
    interface_id = event.interface_id
    channel_address = event.channel_address
    parameter = event.parameter
    value = event.value
    # Handle parameter update

unsubscribe = central.event_bus.subscribe(
    event_type=BackendParameterEvent,
    handler=on_parameter_event
)
```

**Key Changes:**

- Structured event object instead of multiple parameters
- Includes `event.timestamp` for debugging

### 3. DataPoint Events

**Legacy API:**

```python
# Subscribe to specific data point
async def datapoint_callback(*, value: Any, received_at: datetime) -> None:
    # Handle value update

dpk = DataPointKey(
    interface_id="HmIP-RF",
    channel_address="VCU0000001:1",
    paramset_key=ParamsetKey.VALUES,
    parameter="STATE"
)

# Not exposed via public API, used internally
```

**EventBus API:**

```python
from aiohomematic.central.event_bus import DataPointUpdatedEvent

async def on_datapoint_update(event: DataPointUpdatedEvent) -> None:
    if event.dpk.channel_address == "VCU0000001:1":
        print(f"{event.dpk.parameter} = {event.value}")

unsubscribe = central.event_bus.subscribe(
    event_type=DataPointUpdatedEvent,
    handler=on_datapoint_update
)
```

**Key Changes:**

- Public API for subscribing to all data point updates
- Filter in handler for specific data points
- `event.dpk` is a `DataPointKey` named tuple

### 4. System Variable Events

**Legacy API:**

```python
# Subscribe to specific sysvar
async def sysvar_callback(*, value: Any, received_at: datetime) -> None:
    # Handle sysvar update

# Internal API, not exposed publicly
```

**EventBus API:**

```python
from aiohomematic.central.event_bus import SysvarUpdatedEvent

async def on_sysvar_update(event: SysvarUpdatedEvent) -> None:
    if event.state_path == "sv_12345":
        print(f"Sysvar = {event.value}")

unsubscribe = central.event_bus.subscribe(
    event_type=SysvarUpdatedEvent,
    handler=on_sysvar_update
)
```

**Key Changes:**

- Public API for all sysvar updates
- `event.state_path` identifies the variable
- Filter in handler for specific sysvars

### 5. Homematic Events (KEYPRESS, etc.)

**Legacy API:**

```python
def homematic_callback(
    *,
    event_type: EventType,
    event_data: dict[EventKey, Any]
) -> None:
    if event_type == EventType.KEYPRESS:
        address = event_data[EventKey.ADDRESS]
        # Handle keypress

central.subscribe_homematic_callback(cb=homematic_callback)
```

**EventBus API:**

```python
from aiohomematic.central.event_bus import HomematicEvent

async def on_homematic_event(event: HomematicEvent) -> None:
    if event.event_type == EventType.KEYPRESS:
        address = event.event_data[EventKey.ADDRESS]
        # Handle keypress

unsubscribe = central.event_bus.subscribe(
    event_type=HomematicEvent,
    handler=on_homematic_event
)
```

**Key Changes:**

- Minimal change in structure
- Can be async
- Type-safe event object

---

## Code Examples

### Example 1: Home Assistant Coordinator Setup

```python
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from aiohomematic.central import CentralUnit
from aiohomematic.central.event_bus import (
    BackendSystemEventData,
    DataPointUpdatedEvent,
    HomematicEvent,
)
from aiohomematic.const import BackendSystemEvent, EventType


class HomematicCoordinator(DataUpdateCoordinator):
    """Homematic data update coordinator."""

    def __init__(self, hass: HomeAssistant, central: CentralUnit):
        """Initialize coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name="Homematic",
        )
        self.central = central
        self._unsubscribers = []

    async def async_setup(self) -> None:
        """Set up the coordinator with EventBus subscriptions."""

        # Subscribe to system events
        self._unsubscribers.append(
            self.central.event_bus.subscribe(
                event_type=BackendSystemEventData,
                handler=self._on_system_event,
            )
        )

        # Subscribe to data point updates
        self._unsubscribers.append(
            self.central.event_bus.subscribe(
                event_type=DataPointUpdatedEvent,
                handler=self._on_datapoint_update,
            )
        )

        # Subscribe to Homematic events (keypresses, etc.)
        self._unsubscribers.append(
            self.central.event_bus.subscribe(
                event_type=HomematicEvent,
                handler=self._on_homematic_event,
            )
        )

    async def _on_system_event(self, event: BackendSystemEventData) -> None:
        """Handle system events."""
        if event.system_event == BackendSystemEvent.DEVICES_CREATED:
            # Trigger Home Assistant device discovery
            await self.async_refresh()

        elif event.system_event == BackendSystemEvent.HUB_REFRESHED:
            # Update hub data
            await self.async_request_refresh()

    async def _on_datapoint_update(self, event: DataPointUpdatedEvent) -> None:
        """Handle data point updates."""
        # Update Home Assistant entities
        entity_id = self._get_entity_id_from_dpk(event.dpk)
        if entity_id:
            self.hass.bus.async_fire(
                "homematicip_local_value_update",
                {
                    "entity_id": entity_id,
                    "value": event.value,
                    "received_at": event.received_at.isoformat(),
                },
            )

    async def _on_homematic_event(self, event: HomematicEvent) -> None:
        """Handle Homematic events (keypresses, etc.)."""
        if event.event_type == EventType.KEYPRESS:
            # Fire Home Assistant event
            self.hass.bus.async_fire(
                "homematicip_local_keypress",
                {
                    "address": event.event_data.get(EventKey.ADDRESS),
                    "parameter": event.event_data.get(EventKey.PARAMETER),
                },
            )

    async def async_shutdown(self) -> None:
        """Shutdown coordinator and unsubscribe from events."""
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()
```

### Example 2: Config Entry Setup with Cleanup

```python
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""

    # Create central
    central = await create_central(entry.data)

    # Start central
    await central.start()

    # Subscribe to events
    unsubscribers = []

    unsubscribers.append(
        central.event_bus.subscribe(
            event_type=BackendSystemEventData,
            handler=lambda e: _handle_system_event(hass, e),
        )
    )

    unsubscribers.append(
        central.event_bus.subscribe(
            event_type=DataPointUpdatedEvent,
            handler=lambda e: _handle_datapoint(hass, e),
        )
    )

    # Store for cleanup
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "central": central,
        "unsubscribers": unsubscribers,
    }

    # Register cleanup
    entry.async_on_unload(
        lambda: _cleanup_subscriptions(unsubscribers)
    )

    return True


def _cleanup_subscriptions(unsubscribers: list) -> None:
    """Clean up EventBus subscriptions."""
    for unsubscribe in unsubscribers:
        unsubscribe()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    central = data["central"]

    # Cleanup happens via entry.async_on_unload

    await central.stop()

    hass.data[DOMAIN].pop(entry.entry_id)

    return True
```

### Example 3: Entity State Updates

```python
from homeassistant.helpers.entity import Entity

from aiohomematic.central.event_bus import DataPointUpdatedEvent
from aiohomematic.const import DataPointKey, ParamsetKey


class HomematicEntity(Entity):
    """Base Homematic entity."""

    def __init__(self, central: CentralUnit, device_address: str, channel_no: int):
        """Initialize entity."""
        self._central = central
        self._device_address = device_address
        self._channel_no = channel_no
        self._unsubscribe = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to data point updates when entity is added."""

        async def on_update(event: DataPointUpdatedEvent) -> None:
            # Check if this update is for our device
            if event.dpk.channel_address == f"{self._device_address}:{self._channel_no}":
                # Update entity state
                self.async_write_ha_state()

        self._unsubscribe = self._central.event_bus.subscribe(
            event_type=DataPointUpdatedEvent,
            handler=on_update,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe when entity is removed."""
        if self._unsubscribe:
            self._unsubscribe()
            self._unsubscribe = None


class HomematicSwitch(HomematicEntity):
    """Homematic switch entity."""

    @property
    def is_on(self) -> bool:
        """Return if switch is on."""
        dpk = DataPointKey(
            interface_id=self._central.primary_client.interface_id,
            channel_address=f"{self._device_address}:{self._channel_no}",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )
        # Get value from central's cache
        device = self._central.get_device(self._device_address)
        if device and (channel := device.get_channel(self._channel_no)):
            if data_point := channel.get_data_point(parameter="STATE"):
                return bool(data_point.value)
        return False

    async def async_turn_on(self, **kwargs) -> None:
        """Turn switch on."""
        device = self._central.get_device(self._device_address)
        if device and (channel := device.get_channel(self._channel_no)):
            if data_point := channel.get_data_point(parameter="STATE"):
                await data_point.set_value(True)
```

---

## Testing

### Unit Tests

```python
import pytest
from unittest.mock import Mock, AsyncMock

from aiohomematic.central.event_bus import DataPointUpdatedEvent
from aiohomematic.const import DataPointKey, ParamsetKey


@pytest.mark.asyncio
async def test_eventbus_subscription(central):
    """Test EventBus subscription and event handling."""

    # Create mock handler
    handler = AsyncMock()

    # Subscribe
    unsubscribe = central.event_bus.subscribe(
        event_type=DataPointUpdatedEvent,
        handler=handler,
    )

    # Trigger event (simulate backend update)
    dpk = DataPointKey(
        interface_id="HmIP-RF",
        channel_address="VCU0000001:1",
        paramset_key=ParamsetKey.VALUES,
        parameter="STATE",
    )

    # Simulate data point update
    await central.data_point_event(
        interface_id=dpk.interface_id,
        channel_address=dpk.channel_address,
        parameter=dpk.parameter,
        value=True,
    )

    # Wait a bit for async event propagation
    await asyncio.sleep(0.1)

    # Verify handler was called
    assert handler.called
    event = handler.call_args[0][0]
    assert isinstance(event, DataPointUpdatedEvent)
    assert event.dpk == dpk
    assert event.value is True

    # Cleanup
    unsubscribe()
```

### Integration Tests

Test in your Home Assistant development environment:

1. Set up test config entry
2. Subscribe to events
3. Trigger backend updates
4. Verify Home Assistant entities update correctly
5. Check event firing
6. Test cleanup on config entry removal

---

## Rollback Plan

### If Issues Occur

1. **Keep Legacy Callbacks Active**: The dual-system approach means legacy callbacks continue to work
2. **Remove EventBus Subscriptions**: Simply remove the EventBus subscription code
3. **Monitor Logs**: EventBus logs errors with handler names for debugging

### Monitoring

```python
# Enable EventBus debug logging
import logging

logging.getLogger("aiohomematic.central.event_bus").setLevel(logging.DEBUG)
```

### Debugging

```python
# Check subscription counts
stats = central.event_bus.get_event_stats()
_LOGGER.debug("EventBus stats: %s", stats)

# Check active subscriptions
count = central.event_bus.get_subscription_count(event_type=DataPointUpdatedEvent)
_LOGGER.debug("Active DataPointUpdatedEvent subscribers: %d", count)
```

---

## Best Practices

### 1. Use Async Handlers

```python
# Preferred: async handler
async def on_event(event: DataPointUpdatedEvent) -> None:
    await async_operation()

# Acceptable: sync handler (for simple operations)
def on_event(event: DataPointUpdatedEvent) -> None:
    simple_operation()
```

### 2. Store Unsubscribe Callbacks

```python
# Good: store for cleanup
self._unsubscribers = []
self._unsubscribers.append(
    central.event_bus.subscribe(event_type=Event, handler=handler)
)

# Bad: losing reference
central.event_bus.subscribe(event_type=Event, handler=handler)  # Can't unsubscribe!
```

### 3. Filter in Handler

```python
# Filter for specific devices/parameters
async def on_datapoint(event: DataPointUpdatedEvent) -> None:
    if event.dpk.channel_address not in interested_addresses:
        return  # Skip uninteresting events

    # Process relevant event
    await process(event)
```

### 4. Handle Errors Gracefully

```python
async def on_event(event: DataPointUpdatedEvent) -> None:
    try:
        await risky_operation(event)
    except Exception as exc:
        _LOGGER.error("Failed to handle event: %s", exc)
        # EventBus isolates this error from other handlers
```

### 5. Use Type Hints

```python
from aiohomematic.central.event_bus import DataPointUpdatedEvent

# Type hints help IDE and mypy
async def on_datapoint(event: DataPointUpdatedEvent) -> None:
    # IDE knows event.dpk, event.value, etc.
    pass
```

---

## Summary

### Migration Checklist

- [ ] Identify all callback registrations in integration
- [ ] Add parallel EventBus subscriptions
- [ ] Test EventBus handlers in development
- [ ] Verify entity updates work correctly
- [ ] Check event firing (keypresses, etc.)
- [ ] Monitor logs for errors
- [ ] Remove legacy callback registrations
- [ ] Update documentation
- [ ] Release with changelog notes

### Key Takeaways

1. **Backward Compatible**: Both systems work together
2. **Gradual Migration**: Migrate one callback at a time
3. **Type Safe**: Better IDE support and error catching
4. **Cleaner Code**: Unified API, easier maintenance
5. **Better Debugging**: Event stats and subscription counts

---

## Support

For questions or issues:

- **aiohomematic issues**: https://github.com/sukramj/aiohomematic/issues
- **EventBus documentation**: `docs/event_bus.md`
- **API reference**: `aiohomematic/central/event_bus.py`

---

**Last Updated**: 2025-11-18
**aiohomematic Version**: 2025.11.16+
