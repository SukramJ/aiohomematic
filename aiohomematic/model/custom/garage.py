# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Garage door enums.

Kept in a dedicated module so combined data points (e.g. the garage door mode
combined data point) can reference the same enum values as the custom garage
cover data point without importing the cover module (which would create a
circular import via the custom/combined dependency).
"""

from enum import IntEnum, StrEnum, unique

__all__ = ["GarageDoorActivity", "GarageDoorCommand", "GarageDoorState"]


@unique
class GarageDoorActivity(IntEnum):
    """Enum with garage door activity states."""

    CLOSING = 5
    OPENING = 2


@unique
class GarageDoorCommand(StrEnum):
    """Enum with garage door commands."""

    CLOSE = "CLOSE"
    NOP = "NOP"
    OPEN = "OPEN"
    PARTIAL_OPEN = "PARTIAL_OPEN"
    STOP = "STOP"


@unique
class GarageDoorState(StrEnum):
    """Enum with garage door states."""

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    VENTILATION_POSITION = "VENTILATION_POSITION"
    POSITION_UNKNOWN = "_POSITION_UNKNOWN"
