# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Light capabilities dataclass.

Contains static capability flags for light entities. Dynamic capabilities
that depend on runtime state (like device_operation_mode) use has_* properties
on the entity class instead.

Public API
----------
- LightCapabilities: Frozen dataclass with light capability flags
- DIMMER_CAPABILITIES: Basic dimmer capabilities
- COLOR_DIMMER_CAPABILITIES: Color dimmer capabilities
- COLOR_TEMP_DIMMER_CAPABILITIES: Color temperature dimmer capabilities
- FIXED_COLOR_LIGHT_CAPABILITIES: Fixed color light capabilities
- RGBW_LIGHT_CAPABILITIES: RGBW light capabilities (dynamic features via has_*)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

__all__ = [
    "COLOR_DIMMER_CAPABILITIES",
    "COLOR_TEMP_DIMMER_CAPABILITIES",
    "DIMMER_CAPABILITIES",
    "FIXED_COLOR_LIGHT_CAPABILITIES",
    "LightCapabilities",
    "RGBW_LIGHT_CAPABILITIES",
]


@dataclass(frozen=True, slots=True)
class LightCapabilities:
    """
    Immutable capability flags for light entities.

    Contains ONLY static capabilities that don't change at runtime.
    For CustomDpIpRGBWLight, color_temperature/hs_color/effects depend on
    device_operation_mode and use has_* properties instead.
    """

    # Core features
    brightness: bool = True  # All lights support brightness by default
    transition: bool = False  # Ramp time support

    # Color features (static detection based on DataPoint presence)
    color_temperature: bool = False  # Has color temperature DataPoint
    hs_color: bool = False  # Has hue/saturation DataPoints
    effects: bool = False  # Has effect DataPoint


# Predefined capability sets for different light types

DIMMER_CAPABILITIES: Final = LightCapabilities(
    brightness=True,
    transition=True,
)

COLOR_DIMMER_CAPABILITIES: Final = LightCapabilities(
    brightness=True,
    transition=True,
    hs_color=True,
)

COLOR_TEMP_DIMMER_CAPABILITIES: Final = LightCapabilities(
    brightness=True,
    transition=True,
    color_temperature=True,
)

FIXED_COLOR_LIGHT_CAPABILITIES: Final = LightCapabilities(
    brightness=True,
    transition=True,
    # Fixed color uses color property but not hs_color
)

# RGBW lights have dynamic capabilities based on device_operation_mode
# Static capabilities only include brightness/transition
# Color features are checked via has_* properties at runtime
RGBW_LIGHT_CAPABILITIES: Final = LightCapabilities(
    brightness=True,
    transition=True,
    # color_temperature, hs_color, effects are dynamic - use has_* properties
)
