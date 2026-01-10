# Migration Guide: Capabilities Pattern (2026-01)

## Overview

This migration guide covers the comprehensive refactoring of all `supports_*` properties to a unified Capabilities pattern in aiohomematic. This is a **breaking change** with no backwards compatibility.

**aiohomematic Version:** 2025.12.50+

## Breaking Changes Summary

1. **BackendCapabilities**: Removed `supports_*` prefix from all 19 fields
2. **Entity Capabilities**: New frozen dataclasses (`LightCapabilities`, `SirenCapabilities`, `LockCapabilities`, `ClimateCapabilities`)
3. **Dynamic Properties**: All `supports_*` properties renamed to `has_*`
4. **Handler Classes**: All `supports_*` → `has_*`
5. **ClientConfig**: All `supports_*` → `has_*`

---

## Migration Steps for homematicip_local

### Step 1: Update Entity Capability Checks

#### Light Entities

```python
# BEFORE
if light.supports_brightness:
    brightness = light.brightness
if light.supports_color_temperature:
    color_temp = light.color_temp_kelvin
if light.supports_effects:
    effects = light.effects
if light.supports_hs_color:
    hs = light.hs_color
if light.supports_transition:
    # handle transition

# AFTER
if light.capabilities.brightness:
    brightness = light.brightness
if light.has_color_temperature:  # Dynamic - can change at runtime
    color_temp = light.color_temp_kelvin
if light.has_effects:  # Dynamic
    effects = light.effects
if light.has_hs_color:  # Dynamic
    hs = light.hs_color
if light.capabilities.transition:
    # handle transition
```

#### Siren Entities

```python
# BEFORE
if siren.supports_duration:
    await siren.turn_on(duration=30)
if siren.supports_lights:
    lights = siren.available_lights
if siren.supports_tones:
    tones = siren.available_tones
if siren.supports_soundfiles:
    files = siren.available_soundfiles

# AFTER
if siren.capabilities.duration:
    await siren.turn_on(duration=30)
if siren.capabilities.lights:
    lights = siren.available_lights
if siren.capabilities.tones:
    tones = siren.available_tones
if siren.capabilities.soundfiles:
    files = siren.available_soundfiles
```

#### Lock Entities

```python
# BEFORE
if lock.supports_open:
    await lock.open()

# AFTER
if lock.capabilities.open:
    await lock.open()
```

#### Climate Entities

```python
# BEFORE
if climate.supports_profiles:
    profiles = climate.profiles

# AFTER
if climate.capabilities.profiles:
    profiles = climate.profiles
```

#### Text Display Entities

```python
# BEFORE
if display.supports_icons:
    icons = display.available_icons
if display.supports_sounds:
    sounds = display.available_sounds

# AFTER
if display.has_icons:
    icons = display.available_icons
if display.has_sounds:
    sounds = display.available_sounds
```

### Step 2: Update Device/DataPoint Checks

```python
# BEFORE
if device.supports_week_profile:
    schedule = device.week_profile.schedule
if data_point.supports_events:
    # handle events
if data_point.supports_schedule:
    schedule = data_point.schedule

# AFTER
if device.has_week_profile:
    schedule = device.week_profile.schedule
if data_point.has_events:
    # handle events
if data_point.has_schedule:
    schedule = data_point.schedule
```

### Step 3: Update Central/Client Checks

```python
# BEFORE
if central.supports_ping_pong:
    # handle ping pong

# AFTER
if central.has_ping_pong:
    # handle ping pong
```

### Step 4: Update BackendCapabilities Access

```python
# BEFORE
if client.capabilities.supports_backup:
    await client.create_backup()
if client.capabilities.supports_ping_pong:
    # handle
if client.capabilities.supports_programs:
    programs = await client.get_programs()

# AFTER
if client.capabilities.backup:
    await client.create_backup()
if client.capabilities.ping_pong:
    # handle
if client.capabilities.programs:
    programs = await client.get_programs()
```

### Step 5: Update Handler Checks (if used directly)

```python
# BEFORE
if handler.supports_linking:
    await handler.add_link(...)
if handler.supports_programs:
    programs = await handler.get_programs()

# AFTER
if handler.has_linking:
    await handler.add_link(...)
if handler.has_programs:
    programs = await handler.get_programs()
```

### Step 6: Update ClientConfig Access

```python
# BEFORE
config.supports_linking
config.supports_firmware_updates
config.supports_ping_pong
config.supports_push_updates
config.supports_rpc_callback

# AFTER
config.has_linking
config.has_firmware_updates
config.has_ping_pong
config.has_push_updates
config.has_rpc_callback
```

---

## Search-and-Replace Patterns

### Entity Capabilities (to capabilities.\*)

```
.supports_brightness          →  .capabilities.brightness
.supports_transition          →  .capabilities.transition
.supports_duration            →  .capabilities.duration
.supports_lights              →  .capabilities.lights
.supports_tones               →  .capabilities.tones
.supports_soundfiles          →  .capabilities.soundfiles
.supports_open                →  .capabilities.open
.supports_profiles            →  .capabilities.profiles
```

### Dynamic Properties (to has\_\*)

```
.supports_color_temperature   →  .has_color_temperature
.supports_effects             →  .has_effects
.supports_hs_color            →  .has_hs_color
.supports_icons               →  .has_icons
.supports_sounds              →  .has_sounds
.supports_schedule            →  .has_schedule
.supports_week_profile        →  .has_week_profile
.supports_events              →  .has_events
.supports_ping_pong           →  .has_ping_pong
.supports_backup              →  .has_backup
```

### BackendCapabilities (remove supports\_ prefix)

```
capabilities.supports_device_firmware_update   →  capabilities.device_firmware_update
capabilities.supports_firmware_update_trigger  →  capabilities.firmware_update_trigger
capabilities.supports_firmware_updates         →  capabilities.firmware_updates
capabilities.supports_linking                  →  capabilities.linking
capabilities.supports_value_usage_reporting    →  capabilities.value_usage_reporting
capabilities.supports_functions                →  capabilities.functions
capabilities.supports_rooms                    →  capabilities.rooms
capabilities.supports_metadata                 →  capabilities.metadata
capabilities.supports_rename                   →  capabilities.rename
capabilities.supports_rega_id_lookup           →  capabilities.rega_id_lookup
capabilities.supports_service_messages         →  capabilities.service_messages
capabilities.supports_system_update_info       →  capabilities.system_update_info
capabilities.supports_inbox_devices            →  capabilities.inbox_devices
capabilities.supports_install_mode             →  capabilities.install_mode
capabilities.supports_programs                 →  capabilities.programs
capabilities.supports_backup                   →  capabilities.backup
capabilities.supports_ping_pong                →  capabilities.ping_pong
capabilities.supports_push_updates             →  capabilities.push_updates
capabilities.supports_rpc_callback             →  capabilities.rpc_callback
```

### Handler Classes (to has\_\*)

```
.supports_linking                  →  .has_linking
.supports_backup                   →  .has_backup
.supports_programs                 →  .has_programs
.supports_device_firmware_update   →  .has_device_firmware_update
.supports_firmware_update_trigger  →  .has_firmware_update_trigger
.supports_functions                →  .has_functions
.supports_inbox_devices            →  .has_inbox_devices
.supports_install_mode             →  .has_install_mode
.supports_metadata                 →  .has_metadata
.supports_rega_id_lookup           →  .has_rega_id_lookup
.supports_rename                   →  .has_rename
.supports_rooms                    →  .has_rooms
.supports_service_messages         →  .has_service_messages
.supports_system_update_info       →  .has_system_update_info
```

### ClientConfig (to has\_\*)

```
supports_linking          →  has_linking
supports_firmware_updates →  has_firmware_updates
supports_ping_pong        →  has_ping_pong
supports_push_updates     →  has_push_updates
supports_rpc_callback     →  has_rpc_callback
```

---

## Automated Migration Script

```bash
#!/bin/bash
# Run from homematicip_local root directory

# Entity Capabilities
find . -name "*.py" -exec sed -i '' \
    -e 's/\.supports_brightness/.capabilities.brightness/g' \
    -e 's/\.supports_transition/.capabilities.transition/g' \
    -e 's/\.supports_duration/.capabilities.duration/g' \
    -e 's/\.supports_lights/.capabilities.lights/g' \
    -e 's/\.supports_tones/.capabilities.tones/g' \
    -e 's/\.supports_soundfiles/.capabilities.soundfiles/g' \
    -e 's/\.supports_open/.capabilities.open/g' \
    -e 's/\.supports_profiles/.capabilities.profiles/g' \
    {} \;

# Dynamic Properties
find . -name "*.py" -exec sed -i '' \
    -e 's/\.supports_color_temperature/.has_color_temperature/g' \
    -e 's/\.supports_effects/.has_effects/g' \
    -e 's/\.supports_hs_color/.has_hs_color/g' \
    -e 's/\.supports_icons/.has_icons/g' \
    -e 's/\.supports_sounds/.has_sounds/g' \
    -e 's/\.supports_schedule/.has_schedule/g' \
    -e 's/\.supports_week_profile/.has_week_profile/g' \
    -e 's/\.supports_events/.has_events/g' \
    -e 's/\.supports_ping_pong/.has_ping_pong/g' \
    -e 's/\.supports_backup/.has_backup/g' \
    {} \;

# BackendCapabilities (remove supports_ prefix)
find . -name "*.py" -exec sed -i '' \
    -e 's/capabilities\.supports_/capabilities./g' \
    {} \;

echo "Migration complete. Please review changes and run tests."
```

---

## Files Already Updated in homematicip_local

The following files were already updated during the aiohomematic migration:

| File                | Changes                                         |
| ------------------- | ----------------------------------------------- |
| `climate.py`        | `.supports_profiles` → `.capabilities.profiles` |
| `climate.py`        | `.supports_schedule` → `.has_schedule`          |
| `generic_entity.py` | `.supports_schedule` → `.has_schedule`          |
| `notify.py`         | `.supports_icons` → `.has_icons`                |
| `notify.py`         | `.supports_sounds` → `.has_sounds`              |
| `services.py`       | `ATTR_SUPPORTS_ICONS` → `ATTR_HAS_ICONS`        |
| `services.py`       | `ATTR_SUPPORTS_SOUNDS` → `ATTR_HAS_SOUNDS`      |

---

## Compatibility Notes

### Static vs Dynamic Capabilities

Understanding when to use `capabilities.*` vs `has_*`:

| Type             | Access Pattern             | Use Case                                |
| ---------------- | -------------------------- | --------------------------------------- |
| `capabilities.*` | Static, computed once      | Hardware capabilities that never change |
| `has_*`          | Dynamic, checked each time | Runtime state that can change           |

**Example:** A light might have `capabilities.color_temperature = True` (hardware supports it) but `has_color_temperature = False` (currently in RGB mode).

### IpRGBWLight Special Case

For `CustomDpIpRGBWLight`, the `has_*` properties are truly dynamic because the device operation mode can change:

```python
# These can change when user switches device operation mode
light.has_color_temperature  # True only in TUNABLE_WHITE mode
light.has_effects            # True in all modes except PWM
light.has_hs_color           # True only in RGB/RGBW modes
```

---

## Testing Checklist

After migration, verify:

- [ ] Light entities show correct features based on capabilities
- [ ] Color temperature lights work correctly
- [ ] RGB/RGBW lights switch modes properly
- [ ] Siren turn_on with duration works
- [ ] Lock open action works for supported locks
- [ ] Climate profiles are available for thermostats
- [ ] Text display icons and sounds work
- [ ] Week profile/schedule features work
- [ ] No AttributeError exceptions in logs

---

**Created:** 2026-01-10
**aiohomematic Version:** 2025.12.50+
**Status:** Active
