# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Cover capabilities dataclass.

Contains static capability flags for cover entities.

Public API
----------
- CoverCapabilities: Frozen dataclass with cover capability flags
- COVER_CAPABILITIES: Basic cover capabilities (position + stop)
- BLIND_CAPABILITIES: Blind capabilities (position + tilt + stop)
- GARAGE_CAPABILITIES: Garage door capabilities (position + stop + vent)
"""

from dataclasses import dataclass
from typing import Final

__all__ = [
    "BLIND_CAPABILITIES",
    "COVER_CAPABILITIES",
    "CoverCapabilities",
    "GARAGE_CAPABILITIES",
]


@dataclass(frozen=True, slots=True)
class CoverCapabilities:
    """
    Immutable capability flags for cover entities.

    All capabilities are static and determined by device type.
    """

    position: bool = True  # Supports continuous position control
    tilt: bool = False  # Supports tilt/slat angle control
    stop: bool = True  # Supports stop command during movement
    vent: bool = False  # Supports ventilation position (garage doors)


# Predefined capability sets for different cover types

COVER_CAPABILITIES: Final = CoverCapabilities(
    position=True,
    tilt=False,
    stop=True,
)

BLIND_CAPABILITIES: Final = CoverCapabilities(
    position=True,
    tilt=True,
    stop=True,
)

GARAGE_CAPABILITIES: Final = CoverCapabilities(
    position=True,
    tilt=False,
    stop=True,
    vent=True,
)
