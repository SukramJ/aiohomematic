# Lifecycle of Devices and DataPoints (Home Assistant)

This document explains how aiohomematic handles devices and DataPoints (parameters) when used with Home Assistant – from discovery through ongoing updates to orderly teardown. It targets maintainers, integration developers, and power users.

## Terms

- Device: A physical or virtual Homematic/HomematicIP device. Implemented by `aiohomematic.model.device.Device`.
- Channel: Logical sub‑unit of a device; contains DataPoints and events. Implemented by `Device.Channel`.
- DataPoint: Representation of a single parameter (e.g., LEVEL, STATE). Implemented generically by `aiohomematic.model.generic.data_point.GenericDataPoint` or specialized classes; firmware update exposed via `aiohomematic.model.update.DpUpdate`.
- Central: Connects the RPC clients (XML‑RPC/HmIP JSON‑RPC) to the CCU/Homegear and manages devices, events, and caches.

---

## 1. Discovery

Sequence at startup or after re‑connecting to CCU/Homegear:

1. Interface availability and methods: The client layers (`client.xml_rpc`, `client.json_rpc`) check supported methods and register the callback endpoint at the CCU.
2. Load device list/details:
   - For most interfaces: XML‑RPC provides the device catalog and channel descriptions.
   - For CCU: JSON‑RPC provides `get_all_device_data`, `get_system_variable`, `set_system_variable`, etc.
3. Caching for fast restarts:
   - Paramset descriptions (`VALUES`, optionally `MASTER`) and values are persisted in `homematicip_local`. This often eliminates the need for a full fetch on subsequent starts.
4. Create devices and DataPoints:
   - For each device configuration a `Device` object is created; with `Channel` instances below it.
   - For each channel parameter, a `GenericDataPoint` (or Custom/Calculated) is created depending on visibility/definition. The usage decision is made via `DataPointUsage` (see `GenericDataPoint.usage`). Hidden/suppressed parameters or those without definition may be set to `NO_CREATE`.
5. Initial values:
   - Readable DataPoints initially load their values (possibly from cache). Some base DPs like `UN_REACH`, `STICKY_UN_REACH`, `CONFIG_PENDING` are prioritized to know availability and configuration status early.
6. Special case update entity:
   - Per device a `DpUpdate` is created that reflects firmware status/versions and exposes firmware actions.

Home Assistant view: The HA integration (Homematic(IP) Local) registers for Central callbacks and creates HA entities based on the created DataPoints once their `usage == DATA_POINT` and a unique ID is available.

---

## 2. Ongoing updates

Event and value processing during operation:

- Value changes (events):
  - The CCU sends XML‑RPC events. They are routed to the matching DataPoints (`GenericDataPoint.event`).
  - The DataPoint writes the new value via `write_value` and checks for state change (`is_state_change`).
  - Special handling:
    - `CONFIG_PENDING`: Transition from True→False triggers reloading the paramset descriptions and a refresh of readable MASTER parameters (see `GenericDataPoint.event`).
    - Availability (`UN_REACH`, `STICKY_UN_REACH`): Triggers `fire_device_updated_callback` on the device and a central event `EventType.DEVICE_AVAILABILITY` so HA can adjust availability.
- Reading/sending values:
  - Read: Via `DataPoint.load_data_point_value()` in conjunction with the device store/client. Cache is consulted to avoid unnecessary CCU calls.
  - Write: `GenericDataPoint.send_value()` validates, converts, de‑duplicates (no sending without a state change), and calls `client.set_value()`.
- Firmware update:
  - `DpUpdate` mirrors fields like `available`, `firmware`, `latest_firmware`, `firmware_update_state`, `in_progress`. `update_firmware()` delegates to `Device.update_firmware()`.

Reconnection/resubscribe:

- On connection loss, the Central restores operation: RPC clients re‑register, events start flowing again, DataPoints remain intact. HA entities keep their IDs; states are updated once the first events/refresh arrive.

---

## 3. Teardown

Orderly teardown at different levels:

- DataPoint removal at channel level:
  - `Channel.remove()` removes registered DataPoints (and events) from the channel via `_remove_data_point()` and cleans link metadata.
- Device removal:
  - `Device.remove()` initiates teardown for all channels and data structures of the device.
- Callback de‑registration:
  - DataPoints/Updates register callbacks (e.g., `register_data_point_updated_callback`). On removal these are properly cleaned up via returned unsubscribe functions or explicit unsubscribe.
- Central stop:
  - When the integration shuts down, the Central stops the RPC clients, cancels subscriptions, and closes sessions. HA does not automatically remove entities unless devices are considered permanently deleted (see next point).
- Device mutations (delete/re‑pairing):
  - If the CCU permanently deletes a device or addresses change, the Central removes the associated Device/Channel/DataPoint objects. The HA integration receives corresponding signals so entities can be archived/removed.

---

## 4. Lifecycle signals for Home Assistant

Signals/callbacks relevant for integration developers:

- Device availability: `EventType.DEVICE_AVAILABILITY` as well as `Device.subscribe_device_updated_callback()` for changes to `UN_REACH`/`STICKY_UN_REACH`.
- DataPoint updates: DataPoints call registered callbacks after `write_value`; HA uses this to update entity state.
- Firmware: `DpUpdate.subscribe_data_point_updated_callback()` reflects firmware changes and progress.

---

## 5. Best practices for HA integration logic

- Create entities only when `usage == DATA_POINT` and `unique_id` is stable.
- Tie an entity’s availability to `Device.available` (and consume the dedicated availability events).
- When `CONFIG_PENDING` changes True→False: re‑load MASTER parameters (already triggered by aiohomematic; optionally request a refresh from HA if needed).
- Only send write commands if target state differs from current (`send_value` already does this). Log errors/validation exceptions.
- Account for reconnects: keep entities, update states on events. Do not register callbacks twice.

---

## 6. References (code)

- `aiohomematic/model/device.py`: Device/Channel, removal, cache init, callback mechanisms, firmware functions.
- `aiohomematic/model/generic/data_point.py`: Event processing, usage decision, send/read logic, availability events, config‑pending handling.
- `aiohomematic/model/update.py`: `DpUpdate` for firmware status and actions.
- `aiohomematic/client/xml_rpc.py` and `aiohomematic/client/json_rpc.py`: Transport, login/session, method probing.

---

## 7. FAQ

- Why is no entity created for some parameters?
  - The parameter may be marked as hidden or resolves to `DataPointUsage.NO_CREATE` (e.g., due to `parameter_visibility`).
- Why are there no updates after a CCU restart?
  - Check whether the callback port is reachable and whether the Central renews subscriptions after reconnect (consult integration logs). Firewalls/NAT are common causes.
- How do I know that a device’s configuration is finished?
  - When `CONFIG_PENDING` changes from True to False; MASTER parameters are then reloaded which provides consistent attributes/values for HA entities.
