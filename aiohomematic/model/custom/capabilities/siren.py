# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Siren capabilities dataclass.

Contains static capability flags for siren entities.

Public API
----------
- SirenCapabilities: Frozen dataclass with siren capability flags
- BASIC_SIREN_CAPABILITIES: Standard siren capabilities
- SMOKE_SENSOR_SIREN_CAPABILITIES: Smoke sensor siren capabilities
- SOUND_PLAYER_CAPABILITIES: Sound player capabilities
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

__all__ = [
    "BASIC_SIREN_CAPABILITIES",
    "SMOKE_SENSOR_SIREN_CAPABILITIES",
    "SOUND_PLAYER_CAPABILITIES",
    "SirenCapabilities",
]


@dataclass(frozen=True, slots=True)
class SirenCapabilities:
    """
    Immutable capability flags for siren entities.

    All capabilities are static and determined at initialization
    based on device type and available DataPoints.
    """

    duration: bool = False  # Supports duration parameter for alarm
    lights: bool = False  # Has optical alarm selection DataPoint
    tones: bool = False  # Has acoustic alarm selection DataPoint
    soundfiles: bool = False  # Has soundfile selection DataPoint (sound players)


# Predefined capability sets for different siren types

BASIC_SIREN_CAPABILITIES: Final = SirenCapabilities(
    duration=True,
    lights=True,
    tones=True,
)

SMOKE_SENSOR_SIREN_CAPABILITIES: Final = SirenCapabilities(
    duration=False,
    lights=False,
    tones=True,
)

SOUND_PLAYER_CAPABILITIES: Final = SirenCapabilities(
    duration=True,
    lights=False,
    tones=False,
    soundfiles=True,
)
