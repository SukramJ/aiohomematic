# Paramset Inconsistency (Missing Device Parameters After Firmware Update)

## What Is This Issue?

After a firmware update on HmIP (HomematicIP) devices, certain device parameters may
become invisible to Home Assistant and other integrations. The device works, but some
configuration options that should be available after the firmware update are missing.

**Example:** An HmIP-FSM16 (switching actuator with power metering) with firmware 1.22.8
should allow switching between consumption mode and feed-in mode via the
`CHANNEL_OPERATION_MODE` parameter on channel 5. After a firmware update, this option
may not appear even though the device firmware supports it.

## How Does This Happen?

This is a known bug in the HmIPServer (crRFD) component of the CCU / RaspberryMatic:

1. When a device receives a **firmware update**, the HmIPServer updates its internal
   parameter schema (the "description" of what parameters a device supports).
2. However, the HmIPServer sometimes **fails to update its stored parameter values**
   (the `.dev` files in `/etc/config/crRFD/data/`).
3. This creates a **mismatch**: the schema says the parameter exists, but the stored
   data does not contain it.
4. Integrations like Home Assistant rely on the stored data to display and control
   parameters, so the missing parameters become invisible.

This issue is **not caused by Home Assistant or aiohomematic**. It is a server-side bug
in the HmIPServer by eQ-3.

## Which Devices Are Affected?

Any HmIP or HmIPW device can potentially be affected after a firmware update. Confirmed
affected devices include:

| Device     | Missing Parameters                                                          |
| ---------- | --------------------------------------------------------------------------- |
| HmIP-FSM16 | `CHANNEL_OPERATION_MODE`                                                    |
| HmIP-SPI   | `DISABLE_MSG_TO_AC`                                                         |
| HmIP-SMO   | `DISABLE_MSG_TO_AC`                                                         |
| HmIPW-WTH  | `CLIMATE_FUNCTION`, `HUMIDITY_LIMIT_VALUE`, `TWO_POINT_HYSTERESIS_HUMIDITY` |
| HMIP-SWDO  | `SAMPLE_INTERVAL`                                                           |

**Note:** This list is not exhaustive. Any HmIP device that has received a firmware
update could be affected.

## How Does aiohomematic Detect This?

Starting with version 2026.2.8, aiohomematic automatically checks for paramset
inconsistencies after device creation. The check compares:

- **Parameter descriptions** (`getParamsetDescription`): What parameters the device
  firmware supports.
- **Actual parameter values** (`getParamset`): What parameters the HmIPServer actually
  stores.

If parameters exist in the description but are missing from the actual stored data, a
**warning** is generated.

### Where to See the Warning

1. **Home Assistant Repairs**: Go to **Settings > System > Repairs**. If affected
   devices are detected, a repair issue titled "Paramset Inconsistency" will appear
   listing the affected devices and parameters.

2. **Home Assistant Logs**: Look for log messages starting with `PARAMSET_CONSISTENCY`:

   ```
   PARAMSET_CONSISTENCY: Device VCU0000001 on interface ccu-HmIP-RF has 1 parameter(s)
   in description but not in MASTER paramset: VCU0000001:5:CHANNEL_OPERATION_MODE.
   A factory reset on the device may resolve this issue.
   ```

3. **Diagnostics**: The incident is recorded in the aiohomematic diagnostics data,
   downloadable via **Settings > Devices & Services > Homematic(IP) Local > Download
   Diagnostics**.

## How to Fix Affected Devices

The only reliable fix is to perform a **factory reset** of the affected device on the
CCU. This forces the HmIPServer to re-read all parameters from the device firmware.

### Step-by-Step Instructions

1. Open the **CCU WebUI** in your browser (e.g., `http://your-ccu-ip`).

2. Navigate to **Settings > Devices** (Einstellungen > Geraete).

3. Find the affected device in the list.

4. Click on the device to open its settings.

5. Click the **Reset** button (Werksreset / Factory Reset).

   > **Important:** This is a _factory reset on the CCU side only_. It resets the
   > CCU's stored parameters for this device, NOT the device itself. The device does
   > not lose its pairing or configuration.

6. Wait for the CCU to re-read the device parameters. This usually takes a few seconds.

7. **Reload the Homematic(IP) Local integration** in Home Assistant:

   - Go to **Settings > Devices & Services**
   - Find the Homematic(IP) Local integration
   - Click the three dots menu > **Reload**

8. The previously missing parameters should now appear as entities in Home Assistant.

### What Does the Factory Reset Do?

- It tells the HmIPServer to **discard** its stored parameter data for this device.
- The HmIPServer then **re-reads** all parameters directly from the device firmware.
- This resolves the mismatch between description and actual values.
- The device itself is **NOT** affected: it keeps its pairing, configuration, and
  firmware version.

### Alternative: CCU Restart

In some cases, a **full CCU restart** can also resolve the issue, but a device-level
factory reset is more targeted and reliable.

## Frequently Asked Questions

### Will this issue come back?

It can recur after future firmware updates if the HmIPServer again fails to refresh
its stored data. The fix (factory reset) can be repeated as needed.

### Does the factory reset affect my device settings?

No. The factory reset only resets the CCU's _internal cache_ of the device parameters.
The device itself retains its pairing, configuration, and firmware. You may need to
re-apply some CCU-side configuration settings (like device names or room assignments)
depending on your CCU version.

### Can aiohomematic fix this automatically?

No. The root cause is in the HmIPServer (crRFD) component on the CCU, which is
maintained by eQ-3. aiohomematic can only **detect** the issue and **warn** you.
Only eQ-3 can fix the server-side behavior that causes this inconsistency.

### Why are only HmIP devices affected?

The HmIPServer (crRFD) is a separate process that manages only HmIP and HmIPW devices.
Classic Homematic (BidCos-RF) devices are managed by a different process (rfd) that does
not have this bug.

### I don't see the repair issue in Home Assistant

The check runs only once after device creation or after a CONFIG_PENDING event (which
occurs after configuration changes or firmware updates). If you want to trigger the
check again, reload the integration.

## References

- [Original forum discussion (German)](https://homematic-forum.de/forum/viewtopic.php?t=77531)
  by jmaus (RaspberryMatic developer)
- [HmIP XML-RPC API Addendum](https://www.eq-3.de/downloads/download/homematic/hm_web_ui_doku/HMIP_XmlRpc_API_Addendum.pdf)
  by eQ-3
