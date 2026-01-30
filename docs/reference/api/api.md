# HomematicAPI

The `HomematicAPI` class provides a high-level facade for interacting with Homematic devices. It's the recommended starting point for most applications.

## Overview

```python
from aiohomematic.api import HomematicAPI

async with HomematicAPI.connect(
    host="192.168.1.100",
    username="Admin",
    password="secret",
) as api:
    for device in api.list_devices():
        print(device.name)
```

## Class Reference

::: aiohomematic.api.HomematicAPI
options:
show_root_heading: true
show_source: false
members: - connect - list_devices - get_device - read_value - write_value - subscribe_to_updates - refresh_data - start - stop - is_connected - central
