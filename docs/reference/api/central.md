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
for device in central.devices.values():
    print(device.name)

await central.stop()
```

## Class Reference

::: aiohomematic.central.CentralUnit
options:
show_root_heading: true
show_source: false
members: - start - stop - restart_clients - devices - get_device_by_address - get_device_by_name - get_data_point - get_client - hub - event_bus - central_state - connection_state - is_connected - set_value - put_paramset - get_value - get_paramset
