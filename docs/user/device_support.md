# Device Support

This guide explains how aiohomematic supports Homematic devices and what to do if your device doesn't work as expected.

## Generic Approach

aiohomematic uses a **generic approach** to device support:

1. **All devices are supported** - Every Homematic device automatically creates entities based on its parameters
2. **No device list needed** - New devices work immediately without library updates
3. **Custom mappings enhance** - Complex devices get additional features through custom mappings

### How It Works

```
CCU Device → Parameter Discovery → Entity Creation
     ↓              ↓                    ↓
  HmIP-eTRV    ACTUAL_TEMPERATURE    sensor.temperature
               SET_POINT_TEMPERATURE  climate entity
               VALVE_STATE           sensor.valve
               BATTERY_STATE         sensor.battery
```

When you add a device to your CCU:

1. The integration reads the device's **parameter descriptions** from the CCU
2. Each parameter becomes an entity (sensor, switch, number, etc.)
3. Parameters are mapped to appropriate entity types based on their characteristics

## Entity Types

Parameters are automatically mapped to Home Assistant entity types:

| Parameter Type            | Entity Type   | Example              |
| ------------------------- | ------------- | -------------------- |
| Boolean (read-only)       | Binary Sensor | `WINDOW_STATE`       |
| Boolean (writable)        | Switch        | `STATE`              |
| Float/Integer (read-only) | Sensor        | `ACTUAL_TEMPERATURE` |
| Float/Integer (writable)  | Number        | `LEVEL`              |
| Enum (read-only)          | Sensor        | `ERROR_CODE`         |
| Enum (writable)           | Select        | `OPERATING_MODE`     |
| Action                    | Button        | `PRESS_SHORT`        |

## Custom Mappings

Some devices benefit from **custom mappings** that combine multiple parameters into a single, richer entity:

| Device Type | Custom Entity | Combined Parameters                                          |
| ----------- | ------------- | ------------------------------------------------------------ |
| Thermostat  | Climate       | SET_POINT_TEMPERATURE, ACTUAL_TEMPERATURE, VALVE_STATE, etc. |
| Dimmer      | Light         | LEVEL, ON_TIME, RAMP_TIME                                    |
| Blind       | Cover         | LEVEL, STOP, WORKING                                         |
| Lock        | Lock          | LOCK_STATE, LOCK_TARGET_LEVEL, ERROR                         |

### Benefits of Custom Mappings

- **Better UX** - Single climate card instead of multiple sensors
- **Proper actions** - `climate.set_temperature` instead of raw parameter writes
- **State aggregation** - Combined availability and error handling

## Parameter Filtering

**Not all parameters become entities.** The integration filters parameters to provide a clean, useful set of entities:

| Category                        | Behavior                                  |
| ------------------------------- | ----------------------------------------- |
| **Common parameters**           | Created as entities (enabled or disabled) |
| **Internal/service parameters** | Not created by default                    |
| **Maintenance parameters**      | Created but disabled by default           |

This filtering prevents hundreds of technical parameters from cluttering your Home Assistant instance.

### Disabled Entities

Many entities are created **disabled by default** to avoid cluttering your dashboard:

- Signal strength values (RSSI_DEVICE, RSSI_PEER)
- Duty cycle information (DUTY_CYCLE)
- Device-specific diagnostic parameters

**To enable:**

1. Go to **Settings** → **Devices & Services**
2. Find your device
3. Click on disabled entities
4. Enable the ones you need

### Adding Hidden Parameters (Unignore)

If you need a parameter that isn't created as an entity, you can **unignore** it via the integration configuration:

1. Go to **Settings** → **Devices & Services** → **Homematic(IP) Local**
2. Click **Configure** → navigate to **Interface** page
3. Enable **Advanced configuration**
4. Add the parameter pattern to the **un_ignore** list (e.g., `*:*:RSSI_PEER`)

See [Unignore Parameters](advanced/unignore.md) for detailed instructions and pattern examples.

## When Devices Don't Work as Expected

### New Device Model

If you have a brand-new device model:

1. **Check if it works at all** - Are basic entities created?
2. **Verify CCU pairing** - Is the device working in CCU WebUI?
3. **Check for updates** - Update aiohomematic and the integration

### Missing Custom Mapping

If a device works but lacks a proper custom entity (e.g., shows raw sensors instead of a climate entity):

1. **Export the device definition:**

   ```yaml
   action: homematicip_local.export_device_definition
   data:
     device_id: YOUR_DEVICE_ID
   ```

2. **Open an issue** on [GitHub](https://github.com/sukramj/aiohomematic/issues) with:
   - Device model (e.g., HmIP-eTRV-2)
   - The exported ZIP file
   - Description of expected behavior

### Wrong Entity Type

If a parameter is mapped to the wrong entity type:

- This is usually intentional based on the parameter's characteristics
- Use Home Assistant's entity customization if needed
- Report if you believe it's a bug

## Using Generic Entities

Even without custom mappings, you can control any device:

### Reading Values

```yaml
# Read any parameter
action: homematicip_local.get_device_value
data:
  device_id: YOUR_DEVICE_ID
  channel: 1
  parameter: ACTUAL_TEMPERATURE
```

### Writing Values

```yaml
# Write any parameter
action: homematicip_local.set_device_value
data:
  device_id: YOUR_DEVICE_ID
  channel: 1
  parameter: SET_POINT_TEMPERATURE
  value: "21.0"
  value_type: double
```

### Paramsets

```yaml
# Read complete paramset
action: homematicip_local.get_paramset
data:
  device_id: YOUR_DEVICE_ID
  channel: 1
  paramset_key: VALUES
```

## Device Categories

### Fully Supported (Custom Mapping)

These device types have complete custom entity support:

- **Climate** - Thermostats, wall thermostats, heating groups
- **Cover** - Blinds, shutters, garage doors
- **Light** - Dimmers, switches with brightness
- **Lock** - Door locks
- **Siren** - Alarm sirens, MP3 players
- **Switch** - All switch types

### Generic Support (Auto-Discovery)

All other devices work through generic entity creation:

- Weather stations
- Energy meters
- Motion sensors
- Door/window contacts
- Smoke detectors
- Water sensors
- And all future devices

## See Also

- [Extension Points](../developer/extension_points.md) - For developers adding custom mappings
- [Actions Reference](features/homeassistant_actions.md) - Raw device access
- [Unignore Parameters](advanced/unignore.md) - Access hidden parameters
