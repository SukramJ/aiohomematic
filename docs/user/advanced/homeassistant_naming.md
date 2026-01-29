# Naming Conventions

This document explains how Homematic(IP) Local for OpenCCU names devices and entities in Home Assistant.

## Terminology

| Term           | Description                                                                              |
| -------------- | ---------------------------------------------------------------------------------------- |
| **Device**     | Physical device registered on CCU (or hub-level pseudo device). Maps to HA Device entry. |
| **Channel**    | Functional sub-unit of a device. One device can have multiple channels.                  |
| **Data point** | Parameter exposed by a device/channel (e.g., LEVEL, STATE).                              |
| **Entity**     | Home Assistant entity created from one or multiple data points.                          |

## Name Sources

Names are taken from these sources, in priority order:

1. **User-defined names from CCU** (rooms, device names, channel names)
2. **Homematic logical names** (device type, channel number) as fallback
3. **Home Assistant translations** for parameter/entity type (localized names)

## Device Names

The HA device name is primarily the **CCU device name**.

### Sub-Device Naming

When "sub devices" are enabled and a device has grouped channels:

| Condition                                      | Device Name                   |
| ---------------------------------------------- | ----------------------------- |
| Master channel has non-empty, non-numeric name | Master channel name           |
| Master channel name is numeric                 | `{device name}-{master name}` |
| Master channel has no name                     | `{device name}-{group_no}`    |

If sub devices are disabled, the plain CCU device name is used.

## Entity Names

Entity names combine:

- The user/device/channel part from CCU
- A translated parameter/entity type name from HA translations

### Naming Rules

**Generic/Calculated entities:**

1. Start from the data point's name (based on device/channel names and parameter names)
2. If sub devices enabled with sub devices present, use only the parameter part
3. Replace raw parameter name with HA translation (e.g., "Level" → "Brightness" for lights)

**Custom entities:**

1. If entity name starts with device name, remove device name to avoid duplication
2. Replace raw parameter name with HA translation

**Special cases:**

- If entity name equals device name → entity name set to empty (HA displays device name only)
- If entity name is empty → HA derives name from device and platform

### Translation Removal

If the HA translation for a specific entity name key is an **empty string**, the translated part is omitted entirely.

## Use Device Name Property

Entities without their own distinct name "use the device name" in HA. This is exposed via the `use_device_name` property.

## Examples

### Dimmer Channel

- Device: "Livingroom Light"
- Parameter: LEVEL
- **Result:** Entity name "Brightness" (translated from LEVEL)

### Switch Channel

- Device: "Garden Pump"
- Parameter: STATE
- Custom entity mapping: switch
- **Result:** Entity name "Switch" or empty (depends on translations)

### Multi-Group Device

- Base device: "RGB Controller"
- Master channel: "Shelf"
- **Result:**
  - Device: "Shelf" (uses master channel name)
  - Entities: "Brightness", "Color Temperature" (parameter parts translated, device name removed)

## Tips

1. **Name in CCU first** - The integration picks up CCU names automatically
2. **Check HA translations** - Some names are intentionally empty to let UI focus on device name
3. **Use meaningful names** - Clean entity IDs come from clean device names

## See Also

- [aiohomematic naming documentation](../../contributor/coding/naming.md)
- [Integration Guide](../homeassistant_integration.md)
