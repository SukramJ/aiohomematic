# Constants and Enums

aiohomematic provides several enums and constants for type-safe configuration.

## Commonly Used Enums

### Interface

Identifies the communication interface to the backend.

```python
from aiohomematic.const import Interface

# HomematicIP wireless devices
Interface.HMIP_RF

# Classic Homematic wireless devices
Interface.BIDCOS_RF

# Wired devices
Interface.BIDCOS_WIRED

# Virtual devices / Heating groups
Interface.VIRTUAL_DEVICES

# CUxD extension
Interface.CUXD

# CCU-Jack
Interface.CCU_JACK
```

### ParamsetKey

Identifies the type of parameter set.

```python
from aiohomematic.const import ParamsetKey

# Runtime values (STATE, LEVEL, etc.)
ParamsetKey.VALUES

# Configuration parameters
ParamsetKey.MASTER

# Link parameters (for direct device links)
ParamsetKey.LINK
```

### CentralState

System state of the central unit.

```python
from aiohomematic.const import CentralState

CentralState.STOPPED      # Not started
CentralState.STARTING     # Initializing
CentralState.RUNNING      # All interfaces connected
CentralState.DEGRADED     # Some interfaces disconnected
CentralState.RECONNECTING # Attempting reconnection
CentralState.FAILED       # Maximum retries exceeded
CentralState.STOPPING     # Shutting down
```

## Class Reference

::: aiohomematic.const.Interface
options:
show_root_heading: true
show_source: false
members: false

::: aiohomematic.const.ParamsetKey
options:
show_root_heading: true
show_source: false
members: false

::: aiohomematic.const.CentralState
options:
show_root_heading: true
show_source: false
members: false
