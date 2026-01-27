# HmIP-SRH Window Handle Sensor (Three-State)

This guide documents how to integrate the Homematic HmIP-SRH window handle sensor with Home Assistant, displaying all three states: **closed**, **tilted**, and **open**.

## Challenge

Home Assistant typically expects binary sensors for window states (open/closed). The HmIP-SRH provides three states, which requires custom templates to display properly.

## Prerequisites

For full visual customization, install these via HACS:

- **card-mod** - Custom styling for Lovelace cards
- **fontawesome** - Additional icons (optional, for custom window icons)

## Implementation Options

### Option 1: Template Sensor (Recommended)

The simplest approach using a template sensor with dynamic icons:

```yaml
template:
  - sensor:
      - name: "Window Bedroom"
        unique_id: window_bedroom_state
        state: >
          {% if is_state('sensor.fenster_schlafzimmer_state', 'open') %}
            open
          {% elif is_state('sensor.fenster_schlafzimmer_state', 'closed') %}
            closed
          {% else %}
            tilted
          {% endif %}
        icon: >
          {% if is_state('sensor.fenster_schlafzimmer_state', 'open') %}
            mdi:window-open
          {% elif is_state('sensor.fenster_schlafzimmer_state', 'closed') %}
            mdi:window-closed
          {% else %}
            mdi:window-open-variant
          {% endif %}
```

### Option 2: Template Binary Sensor

If you prefer a binary sensor (for automations expecting on/off):

```yaml
template:
  - binary_sensor:
      - name: "Window Bedroom"
        unique_id: window_bedroom_binary
        device_class: window
        state: >
          {% if is_state('sensor.fenster_schlafzimmer_state', 'closed') %}
            off
          {% else %}
            on
          {% endif %}
        icon: >
          {% if is_state('sensor.fenster_schlafzimmer_state', 'open') %}
            mdi:window-open
          {% elif is_state('sensor.fenster_schlafzimmer_state', 'closed') %}
            mdi:window-closed
          {% else %}
            mdi:window-open-variant
          {% endif %}
```

### Option 3: Entity Filter Card with card-mod

For advanced UI customization with dynamic colors:

```yaml
type: entity-filter
entities:
  - entity: sensor.fenster_schlafzimmer_state
    card_mod:
      style: |
        :host {
          {% if is_state('sensor.fenster_schlafzimmer_state', 'open') %}
          --card-mod-icon-color: var(--state-active-color);
          --card-mod-icon: mdi:window-open;
          {% elif is_state('sensor.fenster_schlafzimmer_state', 'closed') %}
          --card-mod-icon-color: var(--state-icon-color);
          --card-mod-icon: mdi:window-closed;
          {% else %}
          --card-mod-icon-color: var(--state-active-color);
          --card-mod-icon: mdi:window-open-variant;
          {% endif %}
        }
state_filter:
  - closed
  - tilted
  - open
card:
  type: entities
  state_color: true
  title: Windows
```

## State Mapping Reference

| HmIP-SRH State | Description | Suggested Icon |
|----------------|-------------|----------------|
| `closed` | Window fully closed | `mdi:window-closed` |
| `tilted` | Window tilted/vented | `mdi:window-open-variant` |
| `open` | Window fully open | `mdi:window-open` |

## Custom Icons (Optional)

For FontAwesome Pro icons (requires HACS fontawesome integration):

| State | FontAwesome Icon |
|-------|------------------|
| closed | `fapro:x-window-closed` |
| tilted | `fapro:x-window-tilted` |
| open | `fapro:x-window-open-left` |

## Tips

- Use CSS variables `var(--state-active-color)` and `var(--state-icon-color)` for automatic theme compatibility
- Replace `sensor.fenster_schlafzimmer_state` with your actual entity ID
- The template sensor approach requires no frontend customization and works with all Lovelace cards
