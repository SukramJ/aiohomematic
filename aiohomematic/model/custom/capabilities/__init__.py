# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Entity capabilities dataclasses.

Provides frozen dataclasses for static capability flags of custom entities.
Dynamic capabilities that change at runtime use has_* properties on the entity class.

Public API
----------
- LightCapabilities: Capability flags for light entities
- SirenCapabilities: Capability flags for siren entities
- LockCapabilities: Capability flags for lock entities
- ClimateCapabilities: Capability flags for climate entities
"""

from __future__ import annotations

from aiohomematic.model.custom.capabilities.climate import (
    BASIC_CLIMATE_CAPABILITIES,
    IP_THERMOSTAT_CAPABILITIES,
    ClimateCapabilities,
)
from aiohomematic.model.custom.capabilities.light import (
    COLOR_DIMMER_CAPABILITIES,
    COLOR_TEMP_DIMMER_CAPABILITIES,
    DIMMER_CAPABILITIES,
    FIXED_COLOR_LIGHT_CAPABILITIES,
    RGBW_LIGHT_CAPABILITIES,
    LightCapabilities,
)
from aiohomematic.model.custom.capabilities.lock import (
    BUTTON_LOCK_CAPABILITIES,
    IP_LOCK_CAPABILITIES,
    SMART_DOOR_LOCK_CAPABILITIES,
    LockCapabilities,
)
from aiohomematic.model.custom.capabilities.siren import (
    BASIC_SIREN_CAPABILITIES,
    SMOKE_SENSOR_SIREN_CAPABILITIES,
    SOUND_PLAYER_CAPABILITIES,
    SirenCapabilities,
)

__all__ = [
    # Light
    "COLOR_DIMMER_CAPABILITIES",
    "COLOR_TEMP_DIMMER_CAPABILITIES",
    "DIMMER_CAPABILITIES",
    "FIXED_COLOR_LIGHT_CAPABILITIES",
    "LightCapabilities",
    "RGBW_LIGHT_CAPABILITIES",
    # Siren
    "BASIC_SIREN_CAPABILITIES",
    "SMOKE_SENSOR_SIREN_CAPABILITIES",
    "SOUND_PLAYER_CAPABILITIES",
    "SirenCapabilities",
    # Lock
    "BUTTON_LOCK_CAPABILITIES",
    "IP_LOCK_CAPABILITIES",
    "LockCapabilities",
    "SMART_DOOR_LOCK_CAPABILITIES",
    # Climate
    "BASIC_CLIMATE_CAPABILITIES",
    "ClimateCapabilities",
    "IP_THERMOSTAT_CAPABILITIES",
]
