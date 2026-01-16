# Migration Guide: ChannelEventGroup as Virtual Data Point

## Overview

The `ChannelEventGroup` class has been refactored from a simple helper class to a virtual data point bound to the Channel. This change aligns the event group with the standard `CallbackDataPointProtocol` pattern, simplifying subscription management.

## Breaking Changes

### 1. ChannelEventGroup is now bound to Channel

**Before:**

```python
# Event groups were created on-the-fly when calling get_event_groups()
groups = central.get_event_groups(event_type=DeviceTriggerEventType.KEYPRESS)
# Each call created new ChannelEventGroup instances
```

**After:**

```python
# Event groups are now created during Channel.finalize_init() and reused
groups = central.get_event_groups(event_type=DeviceTriggerEventType.KEYPRESS)
# Each call returns the same ChannelEventGroup instances bound to channels
```

### 2. New subscription method: `subscribe_to_data_point_updated()`

**Before:**

```python
# Used subscribe_to_events() with a handler that receives the event
def on_event(event: GenericEventProtocolAny) -> None:
    event_type = event.parameter.lower()
    # handle event

unsub = event_group.subscribe_to_events(handler=on_event, custom_id=entity_id)
```

**After:**

```python
# Use subscribe_to_data_point_updated() following standard CallbackDataPointProtocol
def on_event(*, data_point: ChannelEventGroupProtocol, custom_id: str) -> None:
    event_type = data_point.last_triggered_event.parameter.lower()
    # handle event

unsub = event_group.subscribe_to_data_point_updated(handler=on_event, custom_id=entity_id)
```

### 3. New property: `last_triggered_event`

The `ChannelEventGroup` now tracks which event was last triggered:

```python
# Access the last triggered event
if event_group.last_triggered_event:
    event_type = event_group.last_triggered_event.parameter.lower()
    event_data = event_group.last_triggered_event.get_event_data()
```

### 4. Direct channel access

Event groups can now be accessed directly from channels:

**New option:**

```python
# Access event group directly from channel
for channel in device.channels.values():
    if channel.event_group:
        event_group = channel.event_group
        # Use the event group
```

## Migration Steps

### Step 1: Update subscription code

Replace `subscribe_to_events()` with `subscribe_to_data_point_updated()`:

```python
# Old code:
def handle_event(event: GenericEventProtocolAny) -> None:
    self._trigger_event(event_type=event.parameter.lower())

unsub = event_group.subscribe_to_events(handler=handle_event, custom_id=entity_id)

# New code:
def handle_event(*, data_point: ChannelEventGroupProtocol, custom_id: str) -> None:
    if data_point.last_triggered_event:
        self._trigger_event(event_type=data_point.last_triggered_event.parameter.lower())

unsub = event_group.subscribe_to_data_point_updated(handler=handle_event, custom_id=entity_id)
```

### Step 2: Update protocol imports (if used)

If you type-hint event groups, ensure you import the updated protocol:

```python
from aiohomematic.interfaces import ChannelEventGroupProtocol
```

### Step 3: Update any custom event handling

If you previously relied on the event handler receiving the triggered event directly, update to use `last_triggered_event`:

```python
# Access event data through last_triggered_event
if (event := event_group.last_triggered_event):
    event_type = event.parameter.lower()
    event_data = event.get_event_data()
```

## New Features

### CallbackDataPointProtocol compliance

`ChannelEventGroup` now follows the standard data point subscription pattern:

- `subscribe_to_data_point_updated()` - Subscribe to event group updates
- `subscribe_to_device_removed()` - Subscribe to device removal (unchanged)
- `is_registered` - Check if the event group is registered externally
- `custom_id` - Get the custom ID used for external registration
- `category` - Returns `DataPointCategory.EVENT`
- `usage` - Returns `DataPointUsage.EVENT`

### Direct channel access

Event groups are now directly accessible from channels:

```python
channel = device.get_channel(channel_address="VCU001:1")
if channel.event_group:
    # Event group is available
    print(f"Events: {channel.event_group.event_types}")
```

## Compatibility Notes

### API remains backward-compatible

The `central.get_event_groups()` method continues to work:

```python
# This still works exactly the same
for event_type in DATA_POINT_EVENTS:
    groups = central.get_event_groups(event_type=event_type, registered=False)
    for group in groups:
        # group is now channel.event_group (reused instance)
        group.subscribe_to_data_point_updated(handler=..., custom_id=entity_id)
```

### Event group lifecycle

Event groups are now created during `Channel.finalize_init()` and cleaned up during `Channel.remove()`. This means:

- Event groups persist for the lifetime of the channel
- No new instances are created on each `get_event_groups()` call
- Internal subscriptions are automatically managed
