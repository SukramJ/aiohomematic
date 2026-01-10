# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Climate capabilities dataclass.

Contains static capability flags for climate entities.

Public API
----------
- ClimateCapabilities: Frozen dataclass with climate capability flags
- BASIC_CLIMATE_CAPABILITIES: Basic climate capabilities
- IP_THERMOSTAT_CAPABILITIES: IP thermostat capabilities
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

__all__ = [
    "BASIC_CLIMATE_CAPABILITIES",
    "ClimateCapabilities",
    "IP_THERMOSTAT_CAPABILITIES",
]


@dataclass(frozen=True, slots=True)
class ClimateCapabilities:
    """
    Immutable capability flags for climate entities.

    All capabilities are static and determined by device type.
    """

    profiles: bool = False  # Supports heating profiles/schedules


# Predefined capability sets for different climate device types

BASIC_CLIMATE_CAPABILITIES: Final = ClimateCapabilities(profiles=False)
IP_THERMOSTAT_CAPABILITIES: Final = ClimateCapabilities(profiles=True)
