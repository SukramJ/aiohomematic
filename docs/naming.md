# Naming of devices, channels, and data points

This is a description how naming is handled in AIO homematic, there are additional rules applied for HA entities and devices.

This document explains how human‑readable names are constructed for devices, channels, data points (including events and custom data points), and when unique IDs are used as a fallback.

The logic lives primarily in `aiohomematic/model/support.py` and relies on names stored in the CCU (device and channel names) plus some auto‑generation helpers when no explicit names are available.

## Terminology

- Device: The physical device (e.g., HmIP‑BROLL) identified by a device address (e.g., `000A1B2C3D4E00`).
- Channel: A sub‑unit of a device identified by a channel address (e.g., `000A1B2C3D4E00:1`). Channels may have a user‑editable name in the CCU.
- Data point: A parameter on a channel (e.g., `LEVEL`, `STATE`). These become entities in upper layers.
- Address separator: `:` used between device address and channel number.

## Device names

Function: `get_device_name(central, device_address, model)`

- If a custom name was set in the CCU for the device address, that name is used.
- Otherwise, an auto‑generated name is returned: `<model>_<device_address>`.

Examples:

- CCU has a name: `"Livingroom Blind Controller"` → returned as is.
- No CCU name: model `HmIP‑BROLL`, address `000A1B2C3D4E00` → `HmIP‑BROLL_000A1B2C3D4E00`.

## Channel names

Helpers: `get_channel_name_data(channel)` and `_get_base_name_from_channel_or_device(channel)`

- If the channel has a custom name in the CCU and it differs from the default (`"<model> <channel_address>"`), that CCU channel name is used.
- Otherwise a base name is derived from the device name:
  - If the channel has a channel number (`channel.no` not `None`), the base becomes `<device_name>:<channel_no>`.
  - If there is no channel number, the base is just `<device_name>`.

The returned `ChannelNameData` contains:

- `device_name`: the resolved device name (see above)
- `channel_name`: the channel part without the leading device name duplicated
- `full_name`: `<device_name> <channel_name>` (when `channel_name` is not empty), otherwise just `device_name`
- `sub_device_name`: equals the original channel name when present, otherwise `device_name`

Examples:

- CCU channel name: `"Livingroom Blind Controller:1"` → `device_name="Livingroom Blind Controller"`, `channel_name=":1"`, `full_name="Livingroom Blind Controller :1"`.
- No CCU channel name: device name `HmIP‑BROLL_...` and channel 1 → base `HmIP‑BROLL_...:1`, which yields the same fields as above.

Note about channel number detection:

- `_check_channel_name_with_channel_no(name)` returns true when the name contains exactly one `:` and the part after `:` converts to an integer.

## Data point names (regular)

Function: `get_data_point_name_data(channel, parameter)`
Steps:

1. Resolve a `channel_name` via `_get_base_name_from_channel_or_device` as described above. If there is none, we cannot construct a human‑readable name and fall back to unique IDs elsewhere.
2. Build a human‑friendly parameter name: `parameter.title().replace("_", " ")` (e.g., `LEVEL` → `Level`, `WINDOW_STATE` → `Window State`).
3. If the channel name includes a numeric channel suffix (`<something>:<int>`):
   - Use the part before `:` as the channel base (`c_name`).
   - When the same parameter exists on multiple channels of the device, append a channel marker to the parameter: `" ch<channel_no>"` (omitted for channel 0 or `None`). Determination uses `central.paramset_descriptions.is_in_multiple_channels(...)`.
   - Example full name: `<device_name> <c_name> <Parameter>[ chX]`.
4. Otherwise, use the entire channel name plus parameter.

`DataPointNameData` contains:

- `device_name`, `channel_name`, `parameter_name` and a computed `name` which is the channel+parameter without repeating the device name at the front. `full_name` is `<device_name> <name>`.

Examples:

- Channel name `"Livingroom Blind Controller:1"`, parameter `LEVEL` → `name="Livingroom Blind Controller Level ch1"`, `full_name="Livingroom Blind Controller Livingroom Blind Controller Level ch1"` after de‑duplication yields `"Livingroom Blind Controller Level ch1"`.
- Channel name `"Window Contact"`, parameter `STATE` → `name="Window Contact State"`.

## Event names

Function: `get_event_name(channel, parameter)`

- Similar to `get_data_point_name_data`, but when a numeric channel suffix is present, the channel part in the name becomes just `" ch<channel_no>"` (or empty for channel 0/None), followed by the human‑friendly parameter name.
- Otherwise the full channel name plus parameter is used.

## Custom data point names

Function: `get_custom_data_point_name(channel, is_only_primary_channel, ignore_multiple_channels_for_name, usage, postfix="")`

- If a numeric channel suffix is present and either the current channel is the only primary channel or multiple channels should be ignored for naming, the name uses the channel base (before `:`) and appends the provided `postfix` as the parameter name.
- If a numeric channel suffix is present and the above condition is not met, the name uses the channel base and a generated parameter marker:
  - `"ch<no>"` for `DataPointUsage.CDP_PRIMARY`
  - `"vch<no>"` for others
- Otherwise, if there is no numeric channel suffix, the channel name alone is used.

## Hub data point names

Function: `get_hub_data_point_name_data(channel_or_none, legacy_name, central_name)`

- If no channel is supplied, the full name becomes `<central_name> <legacy_name>`.
- If a channel is supplied, the legacy name is cleaned (removing address/id parts) and used together with the resolved channel name, again trimming `:<no>` when present.

## Fallback to unique IDs

When a readable name cannot be constructed (e.g., no device/channel name information is present), the code logs a debug message and the UI is expected to use a unique ID instead. Unique IDs are built by:

- `generate_unique_id(central, address, parameter=None, prefix=None)` for data points.
- `generate_channel_unique_id(central, address)` for channels.

Rules for IDs:

- `:` and `-` are replaced with `_`.
- Optional `parameter` and `prefix` are appended with underscore separators.
- For CCU‑internal addresses (`PROGRAM`, `SYSVAR`, `INT000...`, or virtual remote addresses), the central ID is prepended to ensure global uniqueness.
- IDs are always returned in lowercase.

## Worked examples

Below are end-to-end examples showing inputs (model, addresses, CCU names, channel numbers, parameters) and the produced names.

1. Device names

- Input: model `HmIP-BROLL`, address `000A1B2C3D4E00`, CCU device name = none
  - Output device_name: `HmIP-BROLL_000A1B2C3D4E00`
- Input: model `HmIP-BROLL`, address `000A1B2C3D4E00`, CCU device name = "Livingroom Blind Controller"
  - Output device_name: `Livingroom Blind Controller`

2. Channel names

- Input: device_name `Livingroom Blind Controller`, channel address `...:1`, CCU channel name = none
  - Base: `Livingroom Blind Controller:1`
  - ChannelNameData:
    - device_name: `Livingroom Blind Controller`
    - channel_name: `:1`
    - full_name: `Livingroom Blind Controller :1`
    - sub_device_name: `Livingroom Blind Controller:1`
- Input: device_name `HmIP-SWDO_00112233445566`, channel address `...:0`, CCU channel name = default (`"HmIP-SWDO ...:0"`)
  - Base: `HmIP-SWDO_00112233445566:0`
  - ChannelNameData.full_name: `HmIP-SWDO_00112233445566 :0`
- Input: CCU channel name explicitly set to `"Window Contact"` (no ":<no>")
  - ChannelNameData:
    - device_name: `<resolved device name>`
    - channel_name: `Window Contact`
    - full_name: `<device_name> Window Contact`

3. Data point names (regular)

- Input: channel base `Livingroom Blind Controller:1`, parameter `LEVEL`, parameter appears on multiple channels
  - Parameter friendly: `Level`
  - ch marker: ` ch1`
  - DataPointNameData:
    - name: `Livingroom Blind Controller Level ch1`
    - full_name: `Livingroom Blind Controller Livingroom Blind Controller Level ch1` → effectively shown as `Livingroom Blind Controller Level ch1`
- Input: channel base `Window Contact` (no ":<no>"), parameter `WINDOW_STATE`
  - Parameter friendly: `Window State`
  - DataPointNameData.name: `Window Contact Window State`
  - full_name: `<device_name> Window Contact Window State`
- Input: channel base `HmIP-WTH-2_ABCDEF01234567:0`, parameter present only on channel 0
  - Because parameter is not in multiple channels, no `ch0` is appended; name will be based on base without suffix logic.

4. Event names

- Input: channel base `HmIP-WGC_99887766554433:2`, parameter `MOTION`
  - Event friendly parameter: `Motion`
  - Numeric suffix present → channel part becomes ` ch2`
  - DataPointNameData.name: `ch2 Motion`
  - full_name: `<device_name> ch2 Motion`
- Input: channel base `Doorbell` (custom channel name), parameter `PRESS`
  - DataPointNameData.name: `Doorbell Press`
  - full_name: `<device_name> Doorbell Press`

5. Custom data point names

- Input: channel base `Kitchen Light:3`, usage = `CDP_PRIMARY`, only_primary_channel = false, ignore_multiple_channels_for_name = false
  - Numeric suffix present → use base `Kitchen Light` and parameter marker `ch3`
  - DataPointNameData.name: `Kitchen Light ch3`
  - full_name: `<device_name> Kitchen Light ch3`
- Input: channel base `Kitchen Light:3`, usage = `CDP_SECONDARY` (not primary), only_primary_channel = false
  - Marker becomes `vch3`
  - full_name: `<device_name> Kitchen Light vch3`
- Input: channel base `Kitchen Light:3`, only_primary_channel = true, postfix = `Brightness`
  - Name uses base and postfix: DataPointNameData.name: `Kitchen Light Brightness`

6. Hub data point names

- Input: no channel, central_name `CCU-Main`, legacy_name `program_trigger`
  - HubNameData.full_name: `CCU-Main program_trigger`
- Input: channel base `System:0`, legacy_name `INT0001_PROGRAM_STATE_ABC` (contains address/id fragments)
  - Cleaned legacy name: `PROGRAM STATE ABC`
  - Numeric suffix trimmed from channel → channel_name becomes `System`
  - HubNameData.full_name: `System PROGRAM STATE ABC`

7. Unique ID fallbacks

- Input: address `ABCDEF12345678:4`, parameter `LEVEL`
  - generate_unique_id → `abcdef12345678_4_level`
- Input: address `PROGRAM`, parameter `STATE`, central_id `ccu-main`
  - generate_unique_id → `ccu-main_program_state`
- Input: virtual remote address `BidCos-RF:1`, central_id `ccu-main`
  - generate_channel_unique_id → `ccu-main_bidcos_rf_1`

## Where to find the code

- Main implementation: `aiohomematic/model/support.py`
  - Device name: `get_device_name`
  - Channel names: `get_channel_name_data`, `_get_base_name_from_channel_or_device`, `_check_channel_name_with_channel_no`
  - Data point names: `get_data_point_name_data`, `get_event_name`, `get_custom_data_point_name`, `get_hub_data_point_name_data`
  - Unique IDs: `generate_unique_id`, `generate_channel_unique_id`
