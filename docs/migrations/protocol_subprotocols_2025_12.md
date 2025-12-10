# Migration Guide: DeviceProtocol and ChannelProtocol Sub-Protocols

**Version:** 2025.12.x
**Date:** 2025-12-10
**Breaking Change:** No (additive change)

## Overview

This release introduces a protocol hierarchy for `DeviceProtocol` and `ChannelProtocol`, splitting the large monolithic protocols into focused sub-protocols following the Interface Segregation Principle (ISP).

## What Changed

### Before

```python
# Large monolithic protocols
from aiohomematic.interfaces import DeviceProtocol, ChannelProtocol

def process_device(device: DeviceProtocol) -> None:
    # DeviceProtocol had 72 members (49 properties + 23 methods)
    print(device.name)
```

### After

```python
# Composite protocols (backward compatible)
from aiohomematic.interfaces import DeviceProtocol, ChannelProtocol

# Sub-protocols for narrower contracts
from aiohomematic.interfaces import (
    # Channel sub-protocols
    ChannelIdentity,
    ChannelDataPointAccess,
    ChannelGrouping,
    ChannelMetadata,
    ChannelLinkManagement,
    ChannelLifecycle,
    # Device sub-protocols
    DeviceIdentity,
    DeviceChannelAccess,
    DeviceAvailability,
    DeviceFirmware,
    DeviceLinkManagement,
    DeviceGroupManagement,
    DeviceConfiguration,
    DeviceWeekProfile,
    DeviceProviders,
    DeviceLifecycle,
)

# Using specific sub-protocols for narrower contracts
def get_device_name(device: DeviceIdentity) -> str:
    return device.name

def check_firmware(device: DeviceFirmware) -> bool:
    return device.firmware_updatable
```

## Protocol Hierarchy

### ChannelProtocol (39 members → 6 sub-protocols)

| Sub-Protocol             | Members | Description                                                                                 |
| ------------------------ | ------- | ------------------------------------------------------------------------------------------- |
| `ChannelIdentity`        | 7       | Basic identification (address, name, no, type_name, unique_id, rega_id, full_name)          |
| `ChannelDataPointAccess` | 12      | DataPoint and event access (generic*data_points, custom_data_point, get*\*, add_data_point) |
| `ChannelGrouping`        | 5       | Group management (group_master, group_no, is_group_master, link_peer_channels)              |
| `ChannelMetadata`        | 8       | Metadata (device, function, room, rooms, operation_mode, paramset_descriptions)             |
| `ChannelLinkManagement`  | 4       | Central links (create_central_link, remove_central_link, has_link_target_category)          |
| `ChannelLifecycle`       | 3       | Lifecycle (finalize_init, on_config_changed, remove)                                        |

### DeviceProtocol (72 members → 10 sub-protocols)

| Sub-Protocol            | Members | Description                                                                      |
| ----------------------- | ------- | -------------------------------------------------------------------------------- |
| `DeviceIdentity`        | 8       | Basic identification (address, name, model, manufacturer, interface, identifier) |
| `DeviceChannelAccess`   | 12      | Channel/DataPoint access (channels, get*channel, get*\*\_data_point, get_events) |
| `DeviceAvailability`    | 3       | Availability (available, config_pending, set_forced_availability)                |
| `DeviceFirmware`        | 8       | Firmware management (firmware, available_firmware, update_firmware)              |
| `DeviceLinkManagement`  | 3       | Central links (link_peer_channels, create/remove_central_links)                  |
| `DeviceGroupManagement` | 3       | Group management (add_channel_to_group, get_channel_group_no)                    |
| `DeviceConfiguration`   | 11      | Configuration (product_group, rega_id, rooms, rx_modes, flags)                   |
| `DeviceWeekProfile`     | 4       | Week profile (supports_week_profile, week_profile, init_week_profile)            |
| `DeviceProviders`       | 16      | Protocol providers (central_info, client, event_bus_provider, etc.)              |
| `DeviceLifecycle`       | 5       | Lifecycle (finalize_init, on_config_changed, remove, export_device_definition)   |

## Migration Steps

### For Home Assistant Integration (homematicip_local)

**No immediate action required.** The change is backward compatible:

1. `DeviceProtocol` and `ChannelProtocol` remain the primary interfaces
2. All existing code using these protocols continues to work
3. Sub-protocols are additive—use them optionally for better type safety

### Recommended Improvements (Optional)

1. **Type annotations for helper functions:**

   ```python
   # Before: Using full protocol when only name is needed
   def format_device_name(device: DeviceProtocol) -> str:
       return f"Device: {device.name}"

   # After: Using specific sub-protocol
   def format_device_name(device: DeviceIdentity) -> str:
       return f"Device: {device.name}"
   ```

2. **Test mocking simplification:**

   ```python
   # Before: Mock entire DeviceProtocol (72 members)
   mock_device = MagicMock(spec=DeviceProtocol)

   # After: Mock only what's needed
   mock_device = MagicMock(spec=DeviceIdentity)
   mock_device.name = "Test Device"
   mock_device.address = "VCU0000001"
   ```

3. **Search patterns for finding usage:**

   ```bash
   # Find functions that could use narrower protocols
   grep -r "device: DeviceProtocol" --include="*.py"
   grep -r "channel: ChannelProtocol" --include="*.py"
   ```

## Import Changes

All new sub-protocols are exported from `aiohomematic.interfaces`:

```python
from aiohomematic.interfaces import (
    # Existing (unchanged)
    DeviceProtocol,
    ChannelProtocol,

    # New Channel sub-protocols
    ChannelIdentity,
    ChannelDataPointAccess,
    ChannelGrouping,
    ChannelMetadata,
    ChannelLinkManagement,
    ChannelLifecycle,

    # New Device sub-protocols
    DeviceIdentity,
    DeviceChannelAccess,
    DeviceAvailability,
    DeviceFirmware,
    DeviceLinkManagement,
    DeviceGroupManagement,
    DeviceConfiguration,
    DeviceWeekProfile,
    DeviceProviders,
    DeviceLifecycle,
)
```

## Benefits

1. **Better testability**: Mock only the methods you need
2. **Clearer dependencies**: Function signatures show exact requirements
3. **Smaller interfaces**: Follow Interface Segregation Principle
4. **Documentation**: Sub-protocol names describe functionality

## Questions?

If you have questions about this migration, please open an issue at:
https://github.com/sukramj/aiohomematic/issues
