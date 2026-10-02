# godevccu Migration Guide (2026.09.5)

## Overview

[godevccu](https://github.com/SukramJ/godevccu) replaces pydevccu as the virtual CCU
that aiohomematic is developed and tested against. pydevccu is retired.

godevccu (0.8.0 and later) identifies itself in Homegear mode with a `getVersion` of
`godevccu-<version>`. aiohomematic detects the simulator by that name, and the backend
enum, the test-support package and the test suite follow the new name.

Real CCU, OpenCCU, Homegear, CUxD and CCU-Jack installations are not affected.

## Breaking Changes

### `Backend.PYDEVCCU` is replaced by `Backend.GODEVCCU`

**Before:**

```python
from aiohomematic.const import Backend

Backend.PYDEVCCU          # "PyDevCCU"
central.model             # "PyDevCCU" when connected to pydevccu
```

**After:**

```python
from aiohomematic.const import Backend

Backend.GODEVCCU          # "GoDevCCU"
central.model             # "GoDevCCU" when connected to godevccu
```

There is no alias: `Backend.PYDEVCCU` no longer exists.

### Simulator detection

The `HomegearBackend` and backend detection recognise a version string containing
`godevccu`. A version string containing `pydevccu` is no longer special and is treated
like any other CCU version string.

### `aiohomematic_test_support`

| Before                                                                  | After                                                         |
| ----------------------------------------------------------------------- | ------------------------------------------------------------- |
| `const.FULL_SESSION_RANDOMIZED_PYDEVCCU`                                | `const.FULL_SESSION_GODEVCCU` (`"full_session_godevccu.zip"`) |
| `factory.get_pydev_ccu_central_unit_full`                               | `factory.get_godevccu_central_unit_full`                      |
| `helper.load_device_description` reads the installed `pydevccu` package | reads `aiohomematic_test_support/data/device_descriptions/`   |

The new session file was recorded against godevccu 0.8.0. It contains 399 devices
(the pydevccu session had 395): four device types were added (`HmIP-SWSD-2`,
`HmIP-UDI-SMI55`, `HmIP-PSMCO`, `HmIP-DLP`) and the `HmIP-FWI` device moved from
`VCU1851882` to `VCU4820995`. All other device addresses and their device models are
unchanged.

## Migration Steps

1. Replace `Backend.PYDEVCCU` with `Backend.GODEVCCU` and `"PyDevCCU"` with
   `"GoDevCCU"` wherever you compare against the backend model.
2. Tests that use `aiohomematic_test_support`: rename the imports listed above.
   Count assertions over the full session change with the added devices.
3. Run simulator tests against the godevccu binary instead of `pydevccu`:
   `script/install_godevccu.sh` (aiohomematic) or a godevccu release from
   <https://github.com/SukramJ/godevccu/releases>, version 0.8.0 or later.

## Search-and-Replace Patterns

| Search                             | Replace                          |
| ---------------------------------- | -------------------------------- |
| `Backend.PYDEVCCU`                 | `Backend.GODEVCCU`               |
| `"PyDevCCU"`                       | `"GoDevCCU"`                     |
| `FULL_SESSION_RANDOMIZED_PYDEVCCU` | `FULL_SESSION_GODEVCCU`          |
| `get_pydev_ccu_central_unit_full`  | `get_godevccu_central_unit_full` |

## Compatibility Notes

- godevccu 0.8.0 or later is required: older godevccu releases report
  `pydevccu-0.2.0` and are no longer recognised as the simulator.
- pydevccu is no longer recognised as the simulator either.
