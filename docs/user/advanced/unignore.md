# Unignore Parameters

The integration maintains lists of parameters that are filtered out when entities are created. This filtering provides a cleaner user experience by hiding technical or rarely-used parameters.

For advanced users who need access to these hidden parameters, the **unignore mechanism** allows you to make specific parameters visible as entities.

!!! note
For definitions of terms like Parameter, Channel, and Paramset (VALUES, MASTER), see the [Glossary](../../reference/glossary.md).

## Before You Start

**Please understand the following:**

- Use at your own risk
- Excessive writing of `MASTER` paramset parameters can damage devices
- Entity customization (names, icons) must be done via Home Assistant

## Configuration via UI

1. Go to **Settings** → **Devices & Services**
2. Click on **Homematic(IP) Local** → **Configure**
3. Navigate to the **Interface** page
4. Enable **Advanced configuration** and proceed
5. Add parameters to the **un_ignore** list
6. The integration reloads automatically after saving

## Pattern Format

```
DEVICE_TYPE:CHANNEL:PARAMETER
```

| Component     | Description                   | Example       |
| ------------- | ----------------------------- | ------------- |
| `DEVICE_TYPE` | Device model or `*` for all   | `HmIP-eTRV-2` |
| `CHANNEL`     | Channel number or `*` for all | `0`, `1`, `*` |
| `PARAMETER`   | Parameter name                | `LOW_BAT`     |

## Examples

| Pattern                 | Effect                                             |
| ----------------------- | -------------------------------------------------- |
| `HmIP-eTRV-2:0:LOW_BAT` | Show LOW_BAT on channel 0 of HmIP-eTRV-2 devices   |
| `HmIP-SWDO:1:ERROR`     | Show ERROR on channel 1 of HmIP-SWDO devices       |
| `*:*:RSSI_PEER`         | Show RSSI_PEER on all channels of all devices      |
| `*:0:OPERATING_VOLTAGE` | Show OPERATING_VOLTAGE on channel 0 of all devices |

## Finding Parameter Names

To find which parameters a device has:

1. **Export device definition:**

   ```yaml
   action: homematicip_local.export_device_definition
   data:
     device_id: YOUR_DEVICE_ID
   ```

2. **Check the CCU WebUI** → Device settings → show technical data

3. **Use the get_paramset action:**

   ```yaml
   action: homematicip_local.get_paramset
   data:
     device_id: YOUR_DEVICE_ID
     channel: 0
     paramset_key: VALUES
   ```

## See Also

- [Device Support](../device_support.md) - How devices are supported
- [Actions Reference](../features/homeassistant_actions.md) - Raw device access
- [Glossary](../../reference/glossary.md) - Terminology reference
