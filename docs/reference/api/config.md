# CentralConfig

The `CentralConfig` class defines the configuration for connecting to a Homematic backend.

## Overview

```python
from aiohomematic.central import CentralConfig
from aiohomematic.client import InterfaceConfig
from aiohomematic.const import Interface

# Simple: Use factory methods
config = CentralConfig.for_ccu(
    host="192.168.1.100",
    username="Admin",
    password="secret",
)

# Advanced: Full configuration
config = CentralConfig(
    name="my-ccu",
    host="192.168.1.100",
    username="Admin",
    password="secret",
    central_id="unique-id",
    interface_configs={
        InterfaceConfig(
            central_name="my-ccu",
            interface=Interface.HMIP_RF,
            port=2010,
        ),
    },
)
```

## Class Reference

::: aiohomematic.central.CentralConfig
options:
show_root_heading: true
show_source: false

## InterfaceConfig

::: aiohomematic.client.InterfaceConfig
options:
show_root_heading: true
show_source: false
