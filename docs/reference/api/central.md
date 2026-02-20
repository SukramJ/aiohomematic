# CentralUnit

The `CentralUnit` class is the core orchestrator that manages the connection to Homematic backends, device discovery, and event handling.

## Overview

```python
from aiohomematic.central import CentralConfig

config = CentralConfig.for_ccu(
    host="192.168.1.100",
    username="Admin",
    password="secret",
)

central = config.create_central()
await central.start()

# Access devices
for device in central.devices:
    print(device.name)

await central.stop()
```

## Class Reference

::: aiohomematic.central.CentralUnit
options:
show_root_heading: true
show_source: false
members: - start - stop - devices - configuration - link - event_bus - state - connection_state - device_coordinator - client_coordinator - hub_coordinator - event_coordinator - cache_coordinator - query_facade - health
