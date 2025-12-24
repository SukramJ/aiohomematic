# AioHomematic API Usage by Homematic(IP) Local

This document catalogs all aiohomematic methods called by the Homematic(IP) Local Home Assistant integration. It serves as a reference for understanding the public API surface used by the integration.

**Generated**: 2025-12-14
**Source**: Homematic(IP) Local integration
**Repository**: https://github.com/sukramj/homematicip_local

## Overview

The Homematic(IP) Local integration interacts with 13 aiohomematic classes across three layers:

### Core API Layer (3 classes)

1. **CentralUnit** (45 methods) - Main orchestration and device management
2. **Client** (9 methods) - Low-level RPC communication
3. **SystemStatusEvent** (3 properties) - Event bus integration

### Model Layer (10 classes)

4. **Device** (22 methods) - Physical device representation
5. **Channel** (8 methods) - Device channel representation
6. **BaseDataPoint** (122 methods) - Generic data point operations
7. **Event** (22 methods) - Event representation
8. **DpSensor** (3 methods) - Sensor-specific data points
9. **CustomDpClimate** (1 method) - Climate entity specialization
10. **BaseCustomDpClimate** (2 methods) - Climate base class
11. **CustomDpLock** (1 method) - Lock entity specialization
12. **CustomDpSiren** (2 methods) - Siren entity specialization
13. **DataPoint (unclassified)** (13 methods) - Generic data point access

## Statistics

- **Total API calls**: 675 (verified against aiohomematic source)
- **Unique methods**: 253 (all verified to exist in aiohomematic)
- **Classes**: 13 (3 core API + 10 model classes)
- **Filtered out**: 71 Home Assistant-specific methods and wrappers

### Method Verification

All reported methods have been verified to actually exist in the aiohomematic codebase. The following Home Assistant-specific methods have been excluded:

- **Device Registry** (7): `config_entries`, `device_class`, `identifiers`, `id`, `name_by_user`, `ensure_via_device_exists`, `enable_sub_devices`
- **Control Unit Wrappers** (2): `get_new_data_points`, `get_new_hub_data_points`
- **Client Wrappers** (1): `async_get_clientsession`
- **Config Flow** (2): `start_central`, `stop_central`
- **SSDP/UPnP Discovery** (3): `ssdp_location`, `upnp`, `SsdpServiceInfo`
- **Data Point Wrappers** (2): `data_point`, `parameter_name`
- **Event Wrappers** (1): `channel_name`
- **Plus 53 additional HA framework methods** (async_get_device, async_attach_trigger, context, etc.)

---

## API Methods by Class

### 1. aiohomematic.central.CentralUnit (45 methods)

The CentralUnit is the primary entry point for all integration operations.

#### Lifecycle Management

- **`create_central`** - Factory method to create CentralUnit instance
- **`start`** - Initialize central and start client connections
- **`stop`** - Gracefully shut down central and all clients
- **`start_central`** - Alternative start method
- **`stop_central`** - Alternative stop method
- **`activate`** - Activate the central unit

#### Configuration & System Information

- **`central`** - Reference to the central unit itself
- **`central_info`** - Access to central information protocol
- **`model`** - CCU/backend model identifier
- **`name`** - Central unit name
- **`serial`** - CCU serial number
- **`url`** - CCU base URL
- **`version`** - CCU/backend version
- **`system_information`** - Complete system information dict
- **`validate_config_and_get_system_information`** - Validate configuration and fetch system info
- **`state`** - Current central state

#### Device Management

- **`devices`** - Dictionary of all devices
- **`get_device`** - Retrieve device by address
- **`delete_device`** - Remove device from central
- **`add_new_devices_manually`** - Add devices outside of automatic discovery
- **`get_virtual_remotes`** - Get all virtual remote devices
- **`get_un_ignore_candidates`** - Get devices that can be un-ignored

#### Data Point Access

- **`get_data_points`** - Get all data points (filtered)
- **`get_generic_data_point`** - Get a generic data point by unique ID
- **`get_hub_data_points`** - Get hub-level data points
- **`get_sysvar_data_point`** - Get system variable data point
- **`get_state_paths`** - Get all state paths for devices

#### Hub/System Variables

- **`fetch_program_data`** - Fetch CCU programs
- **`fetch_sysvar_data`** - Fetch system variables
- **`get_system_variable`** - Get system variable by name
- **`set_system_variable`** - Set system variable value
- **`program_data_points`** - Dictionary of program data points
- **`sysvar_data_points`** - Dictionary of system variable data points

#### Events

- **`get_events`** - Get all event instances
- **`event_bus`** - Access to internal event bus
- **`subscribe`** - Subscribe to events (legacy method)

#### Client Management

- **`has_client`** - Check if client exists for interface
- **`has_clients`** - Check if any clients exist
- **`client_coordinator`** - Access to client coordinator
- **`cache_coordinator`** - Access to cache coordinator
- **`device_coordinator`** - Access to device coordinator
- **`hub_coordinator`** - Access to hub coordinator

#### Device Links

- **`create_central_links`** - Create direct links in central storage
- **`remove_central_links`** - Remove direct links from central storage

#### Firmware Management

- **`refresh_firmware_data`** - Refresh firmware information for all devices

#### Maintenance & Debugging

- **`clear_all`** - Clear all caches and state
- **`create_backup_and_download`** - Create and download CCU backup

---

### 2. aiohomematic.client.Client (9 methods)

The Client class provides low-level RPC communication with the CCU/backend.

#### RPC Operations

- **`get_value`** - Get single parameter value via RPC
- **`set_value`** - Set single parameter value via RPC
- **`get_paramset`** - Get entire paramset via RPC
- **`put_paramset`** - Set entire paramset via RPC

#### Device Links

- **`add_link`** - Add direct link between devices
- **`remove_link`** - Remove direct link between devices
- **`get_link_peers`** - Get peers for device links

#### Client Information

- **`client`** - Client instance reference
- **`supports_rpc_callback`** - Check if client supports XML-RPC callbacks

---

### 3. aiohomematic.central.integration_events.SystemStatusEvent (3 properties)

Event data for system status changes (used by Home Assistant integration).

#### Properties

- **`status_type`** - Type of status event (SystemStatusEventType)
- **`central_name`** - Name of the central unit
- **`available`** - Whether the system is available (optional)

---

## Model Layer API

### 4. aiohomematic.model.device.Device (22 methods)

Device represents a physical Homematic device with its channels and properties.

#### Device Identification

- **`address`** - Device address (e.g., "VCU0000001")
- **`device_address`** - Same as address
- **`channel_address`** - Construct channel address from device address
- **`identifier`** - Device identifier

#### Device Information

- **`name`** - Device name
- **`model`** - Device model identifier
- **`manufacturer`** - Device manufacturer
- **`firmware`** - Current firmware version
- **`firmware_update_state`** - Firmware update availability state
- **`interface_id`** - Interface identifier (e.g., "BidCos-RF")
- **`room`** - Room assignment

#### Device State

- **`available`** - Device availability status
- **`set_forced_availability`** - Force device availability state

#### Data Points & Events

- **`generic_data_points`** - Generic data points for this device
- **`generic_events`** - Generic events for this device
- **`parameter`** - Get parameter value
- **`value`** - Get/set device value

#### Device Management

- **`has_sub_devices`** - Check if device has sub-devices
- **`export_device_definition`** - Export device definition for debugging

#### Device Registry Integration

- **`device`** - Device registry entry
- **`devices`** - All devices in registry

#### Event Subscriptions

- **`subscribe_to_device_removed`** - Subscribe to device removal events

---

### 5. aiohomematic.model.device.Channel (8 methods)

Channel represents a logical channel within a device.

#### Channel Identification

- **`address`** - Channel address (e.g., "VCU0000001:1")
- **`channel`** - Channel number (deprecated, use `no`)
- **`no`** - Channel number
- **`unique_id`** - Unique channel identifier
- **`group_no`** - Group number if channel is in a group

#### Channel Information

- **`name`** - Channel name
- **`room`** - Room assignment
- **`device`** - Parent device reference

---

### 6. aiohomematic.model.data_point.BaseDataPoint (122 methods)

BaseDataPoint is the core class for all device parameters and controls.

#### Identification & Metadata

- **`address`** - Data point address
- **`unique_id`** - Unique identifier
- **`custom_id`** - Custom identifier for grouping
- **`name`** - Data point name
- **`full_name`** - Full descriptive name
- **`parameter`** - Parameter name
- **`category`** - Data point category (e.g., CLIMATE, COVER)
- **`default_category`** - Default category

#### Value Access

- **`value`** - Current value
- **`default`** - Default value
- **`min`** - Minimum value
- **`max`** - Maximum value
- **`unit`** - Unit of measurement
- **`multiplier`** - Value multiplier
- **`data_type`** - Data type (BOOLEAN, INTEGER, FLOAT, STRING, ENUM)

#### State Information

- **`is_valid`** - Value validity status
- **`is_readable`** - Whether parameter is readable
- **`available`** - Data point availability
- **`state_uncertain`** - State uncertainty flag
- **`modified_at`** - Last modification timestamp
- **`refreshed_at`** - Last refresh timestamp

#### Relationships

- **`device`** - Parent device
- **`channel`** - Parent channel
- **`client`** - RPC client
- **`devices`** - Related devices (for groups)
- **`group_master`** - Group master data point
- **`is_in_multi_group`** - Check if in multiple groups
- **`has_sub_devices`** - Check for sub-devices
- **`data_point_provider`** - Access to data point provider

#### Description & Documentation

- **`description`** - Parameter description
- **`additional_information`** - Additional information
- **`hmtype`** - Homematic type
- **`interface_id`** - Interface identifier
- **`model`** - Device model
- **`function`** - Functional description
- **`usage`** - Usage information
- **`name_data`** - Name metadata

#### Generic Controls (applicable to various entity types)

**Switch/Binary Operations:**

- **`is_on`** - On/off state
- **`turn_on`** - Turn on
- **`turn_off`** - Turn off
- **`press`** - Press button
- **`send_value`** - Send value to device
- **`send_variable`** - Send variable value

**Light Operations:**

- **`brightness`** - Brightness level (0-255)
- **`hs_color`** - Hue/saturation color
- **`color_temp_kelvin`** - Color temperature in Kelvin
- **`color_name`** - Color name
- **`channel_color_name`** - Channel-specific color name
- **`group_brightness`** - Group brightness
- **`group_value`** - Group value
- **`supports_brightness`** - Check brightness support
- **`supports_color_temperature`** - Check color temp support
- **`supports_hs_color`** - Check HS color support
- **`supports_effects`** - Check effects support
- **`available_lights`** - Available light channels
- **`effect`** - Current effect
- **`effects`** - Available effects

**Cover Operations:**

- **`current_position`** - Current position (0-100)
- **`current_tilt_position`** - Current tilt position
- **`current_channel_position`** - Channel-specific position
- **`current_channel_tilt_position`** - Channel-specific tilt position
- **`is_closed`** - Closed state
- **`is_opening`** - Opening state
- **`is_closing`** - Closing state
- **`is_jammed`** - Jammed state
- **`set_position`** - Set position
- **`open`** - Open cover
- **`close`** - Close cover
- **`stop`** - Stop movement
- **`open_tilt`** - Open tilt
- **`close_tilt`** - Close tilt
- **`stop_tilt`** - Stop tilt movement

**Lock Operations:**

- **`is_locked`** - Locked state
- **`is_locking`** - Locking in progress
- **`is_unlocking`** - Unlocking in progress
- **`lock`** - Lock
- **`unlock`** - Unlock

**Climate Operations:**

- **`current_temperature`** - Current temperature
- **`target_temperature`** - Target temperature
- **`temperature_offset`** - Temperature offset
- **`current_humidity`** - Current humidity
- **`min_temp`** - Minimum temperature
- **`max_temp`** - Maximum temperature
- **`set_temperature`** - Set target temperature
- **`operation_mode`** - Current operation mode
- **`mode`** - Current mode
- **`modes`** - Available modes
- **`set_mode`** - Set operation mode
- **`optimum_start_stop`** - Optimum start/stop feature

**Schedule/Profile Operations:**

- **`schedule`** - Current schedule
- **`simple_schedule`** - Simplified schedule
- **`get_schedule_profile`** - Get schedule profile
- **`get_schedule_weekday`** - Get weekday schedule
- **`set_schedule_profile`** - Set schedule profile
- **`set_schedule_weekday`** - Set weekday schedule
- **`set_simple_schedule_profile`** - Set simple schedule profile
- **`set_simple_schedule_weekday`** - Set simple weekday schedule
- **`copy_schedule_profile`** - Copy schedule profile
- **`available_schedule_profiles`** - Available schedule profiles
- **`supports_schedule`** - Check schedule support
- **`profile`** - Current profile
- **`profiles`** - Available profiles
- **`set_profile`** - Set profile
- **`supports_profiles`** - Check profile support

**Timer Operations:**

- **`set_on_time`** - Set on time
- **`set_timer_on_time`** - Set timer on time

**Siren Operations:**

- **`available_tones`** - Available alarm tones

**Firmware Operations:**

- **`firmware`** - Current firmware version
- **`current_firmware`** - Same as firmware
- **`available_firmware`** - Available firmware version
- **`latest_firmware`** - Latest firmware version
- **`refresh_firmware_data`** - Refresh firmware information
- **`update_firmware`** - Update device firmware

**Away Mode (Climate):**

- **`enable_away_mode_by_calendar`** - Enable away mode by calendar
- **`enable_away_mode_by_duration`** - Enable away mode by duration
- **`disable_away_mode`** - Disable away mode

**Data Management:**

- **`load_data_point_value`** - Load data point value
- **`get_data_point_by_custom_id`** - Get data point by custom ID

**Event Subscriptions:**

- **`subscribe_to_data_point_updated`** - Subscribe to value updates
- **`subscribe_to_device_removed`** - Subscribe to device removal

**Cover-Specific:**

- **`activity`** - Activity state
- **`identifier`** - Device identifier

---

### 7. aiohomematic.model.event.Event (22 methods)

Event represents push notifications from devices.

#### Event Identification

- **`event`** - Event name
- **`event_type`** - Event type
- **`parameter`** - Event parameter
- **`interface_id`** - Interface identifier
- **`channel`** - Channel number

#### Event Data

- **`value`** - Event value
- **`data`** - Event data
- **`event_data`** - Same as data
- **`get_event_data`** - Get event data with type

#### Event State

- **`new_state`** - New state value
- **`old_state`** - Previous state value
- **`acceptable`** - Event acceptable flag
- **`alive`** - Device alive status
- **`connected`** - Device connected status
- **`system_event`** - System event indicator

#### Event Statistics

- **`seconds_since_last_event`** - Time since last event
- **`mismatch_count`** - Mismatch count
- **`mismatch_type`** - Mismatch type
- **`reason`** - Event reason

#### Event Metadata

- **`usage`** - Usage information
- **`name_data`** - Name metadata

#### Event Subscriptions

- **`subscribe_to_data_point_updated`** - Subscribe to event updates

---

### 8. aiohomematic.model.generic.DpSensor (3 methods)

DpSensor provides sensor-specific data point properties.

#### Sensor Properties

- **`data_type`** - Sensor data type
- **`multiplier`** - Value multiplier
- **`unit`** - Unit of measurement

---

### 9. aiohomematic.model.custom.CustomDpClimate (1 method)

CustomDpClimate provides climate-specific extensions.

#### Climate Properties

- **`target_temperature_step`** - Temperature adjustment step size

---

### 10. aiohomematic.model.custom.climate.BaseCustomDpClimate (2 methods)

BaseCustomDpClimate provides base climate functionality.

#### Schedule Operations

- **`copy_schedule`** - Copy complete schedule
- **`copy_schedule_profile`** - Copy specific schedule profile

---

### 11. aiohomematic.model.custom.CustomDpLock (1 method)

CustomDpLock provides lock-specific extensions.

#### Lock Capabilities

- **`supports_open`** - Check if lock supports open operation

---

### 12. aiohomematic.model.custom.CustomDpSiren (2 methods)

CustomDpSiren provides siren-specific extensions.

#### Siren Capabilities

- **`supports_duration`** - Check if siren supports duration setting
- **`supports_tones`** - Check if siren supports tone selection

---

### 13. aiohomematic.?.DataPoint (13 methods)

Unclassified data point accesses (when type inference was uncertain).

#### Generic Data Point Properties

- **`category`** - Data point category
- **`channel`** - Parent channel
- **`data_point_name_postfix`** - Name postfix
- **`device`** - Parent device
- **`enabled_default`** - Default enabled state
- **`full_name`** - Full name
- **`group_master`** - Group master
- **`is_in_multi_group`** - Multi-group membership
- **`model`** - Device model
- **`name`** - Data point name
- **`parameter`** - Parameter name
- **`unique_id`** - Unique identifier
- **`unit`** - Unit of measurement

---

## Usage Patterns

### Typical Integration Flow

1. **Initialization**

   ```python
   central = CentralConfig.create_central()
   await central.start()
   ```

2. **Device Discovery**

   ```python
   devices = central.devices
   device = central.get_device(address)
   ```

3. **Data Point Access**

   ```python
   data_points = central.get_data_points()
   dp = central.get_generic_data_point(unique_id)
   ```

4. **Event Subscription**

   ```python
   central.event_bus.subscribe(...)
   ```

5. **Cleanup**
   ```python
   await central.stop()
   ```

### Common Operations

- **System Variables**: `get_system_variable()`, `set_system_variable()`
- **Programs**: `fetch_program_data()`, `program_data_points`
- **Firmware**: `refresh_firmware_data()`
- **Device Links**: `get_link_peers()`, `add_link()`, `remove_link()`
- **Backup**: `create_backup_and_download()`

---

## Stability Considerations

### Stable Public API (recommended for external use)

The following methods are considered stable and recommended for external integrations:

- **CentralUnit**: `start()`, `stop()`, `devices`, `get_device()`, `get_data_points()`, `get_system_variable()`, `set_system_variable()`, `event_bus`
- **Client**: `get_value()`, `set_value()`, `get_paramset()`, `put_paramset()`

### Internal API (may change)

The following methods are primarily for internal use and may change:

- Coordinator access methods (`cache_coordinator`, `client_coordinator`, etc.)
- Legacy methods (`subscribe` - use `event_bus` instead)

### Filtered Methods

The scanner automatically filters out Home Assistant-specific methods that are not part of aiohomematic's API:

- **Device Registry**: `async_get()`, `async_get_device()`, `async_get_or_create()`, `async_remove_device()`
- **Config Flow**: `async_step_user()`, `async_step_central()`, `async_step_reauth()`
- **Triggers/Actions**: `async_attach_trigger()`, `async_get_actions()`, `async_get_triggers()`
- **Entity Properties**: `native_value`, `device_info`, `entity_description`, `context`

---

## Version Compatibility

This analysis is based on:

- **aiohomematic**: 2025.12.47
- **Homematic(IP) Local**: Latest version as of 2025-12-24

For breaking changes and migration guides, see:

- [aiohomematic changelog](../changelog.md)
- [Homematic(IP) Local releases](https://github.com/sukramj/homematicip_local/releases)

---

## Related Documentation

- [Architecture Overview](architecture.md)
- [Extension Points](extension_points.md)
- [Data Flow](data_flow.md)
- [Home Assistant Lifecycle](homeassistant_lifecycle.md)

---

## Generating This Documentation

This documentation was generated using the `scan_aiohomematic_calls.py` script with method verification enabled:

```bash
python script/scan_aiohomematic_calls.py \
    /path/to/homematicip_local/custom_components/homematicip_local \
    --verify-methods \
    --show-unverified \
    --output api_usage.txt
```

The script:

1. Scans all Python files for aiohomematic method calls
2. Filters out Python builtins and Home Assistant framework methods
3. Verifies each detected method exists in the aiohomematic source code
4. Reports only methods that are confirmed to be part of aiohomematic's public API

---

**Last Updated**: 2025-12-24
**Generated by**: `script/scan_aiohomematic_calls.py --verify-methods`
**Verification**: All 253 methods confirmed to exist in aiohomematic 2025.12.47
