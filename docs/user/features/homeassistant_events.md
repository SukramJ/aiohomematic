# Events Reference

This page documents all events that the Homematic(IP) Local for OpenCCU integration fires
on the Home Assistant event bus, including the payload of each event.

Use **Developer Tools → Events** in Home Assistant to listen to any of these event types live.

!!! info "Looking for the library event bus?"
This page covers the events an automation can trigger on. For the internal aiohomematic
EventBus used by developers, see [Event Reference](../../architecture/events/event_reference.md).

---

## Overview

| Event type                                       | Fired when                                      |
| ------------------------------------------------ | ----------------------------------------------- |
| `homematic.keypress`                             | A button on a device is pressed                 |
| `homematic.impulse`                              | A device reports an impulse                     |
| `homematic.device_error`                         | An `ERROR*` / `SENSOR_ERROR*` parameter changes |
| `homematic.device_availability`                  | A device becomes reachable or unreachable       |
| `homematicip_local.optimistic_rollback`          | An optimistic value was rolled back             |
| `homematicip_local.central_state_changed`        | The central changes its health state            |
| `homematicip_local.interface_connection_changed` | An interface connects or disconnects            |

Device parameters outside this list never produce an event. In particular, CCU service
messages such as `CONFIG_PENDING`, `UPDATE_PENDING`, `STICKY_UNREACH`, `LOW_BAT` and
`SABOTAGE` are **not** events — see [Service messages are not events](#service-messages-are-not-events).

---

## homematic.keypress

Fired when a device reports a button press. This is the event behind the remote control
blueprints and the device triggers offered in the automation UI.

**Triggering parameters:** `PRESS`, `PRESS_CONT`, `PRESS_LOCK`, `PRESS_LONG`,
`PRESS_LONG_RELEASE`, `PRESS_LONG_START`, `PRESS_SHORT`, `PRESS_UNLOCK`

| Field          | Type  | Description                                            |
| -------------- | ----- | ------------------------------------------------------ |
| `device_id`    | `str` | Home Assistant device registry ID                      |
| `name`         | `str` | Device name (a user-assigned name takes priority)      |
| `address`      | `str` | Device address, e.g. `0001D8A9B12C34`                  |
| `model`        | `str` | Device model, e.g. `HmIP-WRC2`                         |
| `interface_id` | `str` | Interface, e.g. `openccu-HmIP-RF`                      |
| `type`         | `str` | Triggering parameter in lower case, e.g. `press_short` |
| `subtype`      | `int` | Channel number the press came from                     |

!!! note
The parameter name is delivered as `type` and the channel as `subtype`. This event has no
separate `parameter`, `channel_no` or `value` field.

---

## homematic.impulse

Fired when a device reports an impulse. The only triggering parameter is `SEQUENCE_OK`.

The payload is identical to [homematic.keypress](#homematickeypress), with `type` set to
`sequence_ok`.

---

## homematic.device_error

Fired when a device reports an error condition.

**Triggering parameters:** every parameter whose name **starts with** `ERROR` or
`SENSOR_ERROR` — for example `ERROR_OVERHEAT`, `ERROR_OVERLOAD`, `ERROR_JAMMED`,
`ERROR_NON_FLAT_POSITIONING`, `ERROR_SABOTAGE` or `SENSOR_ERROR`.

`ERROR_CODE` is deliberately excluded: it is a raw numeric code whose meaning differs per
device and carries no usable information in a notification.

The event fires on every change of the error state, so both the arrival and the clearing of
an error produce an event. For boolean parameters an event is also fired when the value
transitions from unknown to `true`; for numeric parameters, from unknown to a value greater
than zero.

| Field          | Type          | Description                                                  |
| -------------- | ------------- | ------------------------------------------------------------ |
| `device_id`    | `str`         | Home Assistant device registry ID                            |
| `name`         | `str`         | Device name (a user-assigned name takes priority)            |
| `address`      | `str`         | Device address                                               |
| `channel_no`   | `int`         | Channel number reporting the error                           |
| `model`        | `str`         | Device model                                                 |
| `interface_id` | `str`         | Interface                                                    |
| `parameter`    | `str`         | Error parameter name, e.g. `ERROR_OVERHEAT`                  |
| `value`        | `bool \| int` | Raw parameter value                                          |
| `error_value`  | `bool \| int` | Same as `value`                                              |
| `error`        | `bool`        | `true` while the error is active, `false` once it clears     |
| `identifier`   | `str`         | Stable ID `<address>_<parameter>`, usable as notification ID |
| `title`        | `str`         | Ready-made notification title                                |
| `message`      | `str`         | Ready-made notification message                              |

Use `error` to decide whether to raise or dismiss a notification, and `identifier` to address
the same notification in both cases. The `Show device error` blueprint does exactly this.

---

## homematic.device_availability

Fired when a device changes between reachable and unreachable.

Reachability is derived from the `UN_REACH` parameter on channel `0`. Only if a device has no
`UN_REACH` parameter at all does `STICKY_UNREACH` act as a fallback. Since HmIP and BidCos
devices provide both, `UN_REACH` is what decides in practice, and `STICKY_UNREACH` does not
affect availability. The `force_device_availability` action overrides the result and also
fires this event.

| Field          | Type   | Description                                              |
| -------------- | ------ | -------------------------------------------------------- |
| `device_id`    | `str`  | Home Assistant device registry ID                        |
| `name`         | `str`  | Device name (a user-assigned name takes priority)        |
| `address`      | `str`  | Device address                                           |
| `channel_no`   | `int`  | Always `0` — availability is per device, not per channel |
| `model`        | `str`  | Device model                                             |
| `interface_id` | `str`  | Interface                                                |
| `parameter`    | `str`  | Always the literal `AVAILABILITY`                        |
| `unavailable`  | `bool` | `true` when the device became unreachable                |
| `identifier`   | `str`  | Stable ID `<address>_availability`                       |
| `title`        | `str`  | Ready-made notification title                            |
| `message`      | `str`  | Ready-made notification message                          |

!!! note
`parameter` is a fixed placeholder set by the integration, not a CCU parameter — devices have
no `AVAILABILITY` parameter.

---

## homematicip_local.optimistic_rollback

Fired when a value that was optimistically applied in Home Assistant had to be reverted
because the CCU did not confirm it. Requires **system notifications** to be enabled in the
integration's advanced options. See [Optimistic Updates](optimistic_updates.md) for background.

| Field               | Type    | Description                                               |
| ------------------- | ------- | --------------------------------------------------------- |
| `device_id`         | `str`   | Home Assistant device registry ID (omitted if unknown)    |
| `name`              | `str`   | Device name (omitted if unknown)                          |
| `address`           | `str`   | Device address                                            |
| `interface_id`      | `str`   | Interface                                                 |
| `parameter`         | `str`   | Affected parameter                                        |
| `reason`            | `str`   | `timeout`, `send_error` or `mismatch`                     |
| `rolled_back_value` | `Any`   | The optimistic value that failed                          |
| `restored_value`    | `Any`   | The previously confirmed value that was restored          |
| `age_seconds`       | `float` | How long the optimistic value was held                    |
| `error`             | `str`   | Error message, only present when `reason` is `send_error` |

The three reasons mean: the CCU did not respond within the optimistic update timeout
(`timeout`), sending raised an exception (`send_error`), or the CCU confirmed a different
value than the one sent (`mismatch`).

---

## homematicip_local.central_state_changed

Fired when the central changes its overall health state.

| Field           | Type  | Description                                     |
| --------------- | ----- | ----------------------------------------------- |
| `instance_name` | `str` | Name of the central instance                    |
| `new_state`     | `str` | `degraded`, `failed`, `recovering` or `running` |

`degraded` means at least one interface is not connected, `failed` means manual intervention
is required, `recovering` means a reconnect is in progress and `running` means all interfaces
are connected. When a degraded or failed state is caused by an authentication problem, a
reauthentication flow is started instead of firing this event.

---

## homematicip_local.interface_connection_changed

Fired when a single interface connects or disconnects.

| Field           | Type   | Description                                |
| --------------- | ------ | ------------------------------------------ |
| `instance_name` | `str`  | Name of the central instance               |
| `interface_id`  | `str`  | Affected interface, e.g. `openccu-HmIP-RF` |
| `connected`     | `bool` | `true` when the interface (re-)connected   |

---

## Service messages are not events

The CCU maintains its own list of service messages (Servicemeldungen) — the entries visible in
the OpenCCU web UI. These are **not** delivered as events, and the parameters behind them
(`CONFIG_PENDING`, `UPDATE_PENDING`, `STICKY_UNREACH`, `UN_REACH`) do not produce Home
Assistant entities either.

Instead, the integration exposes the complete list through the hub sensor
`sensor.<instance>_hub_service_messages`:

- **State**: the number of currently active service messages
- **Attributes**: `message_1`, `message_2`, … — one per message, each containing the device
  name and the message text

The sensor is enabled by default and refreshes on the system variable scan interval (30 seconds
by default), so automations should use a **state trigger** on this sensor rather than an event
trigger.

**Example — notify when a service message appears:**

```yaml
triggers:
  - trigger: numeric_state
    entity_id: sensor.openccu_hub_service_messages
    above: 0
actions:
  - action: persistent_notification.create
    data:
      title: CCU service messages
      message: >
        {{ state_attr('sensor.openccu_hub_service_messages', 'message_1') }}
```

A matching sensor `sensor.<instance>_hub_alarm_messages` exposes CCU alarm messages
(Alarmmeldungen) the same way.

!!! note "LOW_BAT and SABOTAGE"
These two are a separate case: they are regular binary sensors on the device and should be
used as entities, not looked for among the events.

---

## See Also

- [Actions Reference](homeassistant_actions.md) — all custom actions of the integration
- [Optimistic Updates](optimistic_updates.md) — background on optimistic values and rollbacks
- [Event Reference](../../architecture/events/event_reference.md) — internal aiohomematic EventBus (developers)
