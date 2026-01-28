# HmIP-SWSD Smoke Detector Binary Sensors

This guide documents how to create binary sensors for the Homematic HmIP-SWSD smoke detector in Home Assistant.

**Contributor:** @ChristophCaina

## Problem

The HmIP-SWSD smoke detector provides multiple states beyond simple on/off, so it doesn't default to a binary sensor. This makes it harder to use Home Assistant's `state_colors` feature introduced in HA 2022.12.

## Solution

Create two separate binary sensors using template sensors:

1. **Smoke Detector** - monitors smoke alarm states
2. **Intrusion Alarm** - monitors security/tamper states

## Template Configuration

Add this to your `configuration.yaml` or a separate template file:

```yaml
template:
  - binary_sensor:
      # Smoke Detector Binary Sensor
      - name: "Smoke Detector Alarm"
        unique_id: smoke_detector_alarm_binary
        device_class: smoke
        icon: >
          {% if is_state('sensor.rauchwarnmelder_arbeitszimmer_smoke_detector_alarm_status', 'idle_off') %}
            mdi:smoke-detector-variant
          {% elif is_state('sensor.rauchwarnmelder_arbeitszimmer_smoke_detector_alarm_status', 'primary_alarm') %}
            mdi:smoke-detector-alert
          {% elif is_state('sensor.rauchwarnmelder_arbeitszimmer_smoke_detector_alarm_status', 'secondary_alarm') %}
            mdi:smoke-detector-alert
          {% else %}
            mdi:smoke-detector-variant-off
          {% endif %}
        state: >
          {% if is_state('sensor.rauchwarnmelder_arbeitszimmer_smoke_detector_alarm_status', 'primary_alarm') %}
            on
          {% elif is_state('sensor.rauchwarnmelder_arbeitszimmer_smoke_detector_alarm_status', 'secondary_alarm') %}
            on
          {% else %}
            off
          {% endif %}
        availability: >
          {{ states('sensor.rauchwarnmelder_arbeitszimmer_smoke_detector_alarm_status') not in ['unavailable', 'unknown'] }}

      # Intrusion Alarm Binary Sensor
      - name: "Intrusion Alarm"
        unique_id: intrusion_alarm_binary
        device_class: tamper
        icon: >
          {% if is_state('sensor.rauchwarnmelder_arbeitszimmer_smoke_detector_alarm_status', 'intrusion_alarm') %}
            mdi:shield-alert
          {% else %}
            mdi:shield-check
          {% endif %}
        state: >
          {% if is_state('sensor.rauchwarnmelder_arbeitszimmer_smoke_detector_alarm_status', 'intrusion_alarm') %}
            on
          {% else %}
            off
          {% endif %}
        availability: >
          {{ states('sensor.rauchwarnmelder_arbeitszimmer_smoke_detector_alarm_status') not in ['unavailable', 'unknown'] }}
```

## Source States

The HmIP-SWSD exposes these alarm states:

| State             | Description                                |
| ----------------- | ------------------------------------------ |
| `idle_off`        | No alarm, detector inactive                |
| `primary_alarm`   | Direct smoke detection by this device      |
| `secondary_alarm` | Triggered by another linked smoke detector |
| `intrusion_alarm` | Security system activation / tamper alert  |

## Customization

Replace `sensor.rauchwarnmelder_arbeitszimmer_smoke_detector_alarm_status` with your actual entity ID.

## Tips

- The `smoke` device class enables proper state colors in HA dashboards
- The `tamper` device class is used for the intrusion alarm to differentiate it from smoke alarms
- Both sensors share the same source entity but track different alarm conditions
