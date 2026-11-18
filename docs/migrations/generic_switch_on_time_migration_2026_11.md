# Generic Switch On-Time Migration (2026.11.6)

## Overview

The generic switch `DpSwitch` stages an on-time like `CustomDpSwitch` instead of writing it
immediately. This fixes a timed switch-on of a switch that is already on
([homematicip_local#1378](https://github.com/SukramJ/homematicip_local/issues/1378)).

## Breaking Changes

`DpSwitch.set_on_time()` is removed.

**Before:**

```python
await switch.set_on_time(on_time=60)  # wrote ON_TIME at once
await switch.turn_on()  # skipped when the switch was already on
```

**After:**

```python
switch.set_timer_on_time(on_time=60)  # staged, nothing is sent
await switch.turn_on()  # writes ON_TIME, then STATE=True, even when already on
```

or in one call:

```python
await switch.turn_on(on_time=60)
```

## Migration Steps

1. Replace every `await <DpSwitch>.set_on_time(on_time=…)` with
   `<DpSwitch>.set_timer_on_time(on_time=…)` (synchronous).
2. Make sure a `turn_on()` follows; the staged on-time is only sent with it.
3. Code that branched between `CustomDpSwitch.set_timer_on_time()` and `DpSwitch.set_on_time()`
   can call `set_timer_on_time()` for both.

## Search-and-Replace Patterns

| Search                  | Replace                 |
| ----------------------- | ----------------------- |
| `await dp.set_on_time(` | `dp.set_timer_on_time(` |

## Compatibility Notes

- `turn_off()` drops a staged on-time.
- While a started on-time is running, `turn_on()` sends `STATE=True` again, as `CustomDpSwitch` does.
