# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Lock capabilities dataclass.

Contains static capability flags for lock entities.

Public API
----------
- LockCapabilities: Frozen dataclass with lock capability flags
- IP_LOCK_CAPABILITIES: IP lock capabilities
- BUTTON_LOCK_CAPABILITIES: Button lock capabilities
- SMART_DOOR_LOCK_CAPABILITIES: Smart door lock capabilities
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

__all__ = [
    "BUTTON_LOCK_CAPABILITIES",
    "IP_LOCK_CAPABILITIES",
    "LockCapabilities",
    "SMART_DOOR_LOCK_CAPABILITIES",
]


@dataclass(frozen=True, slots=True)
class LockCapabilities:
    """
    Immutable capability flags for lock entities.

    All capabilities are static and determined by device type.
    """

    open: bool = False  # Can be opened (not just locked/unlocked)


# Predefined capability sets for different lock types

IP_LOCK_CAPABILITIES: Final = LockCapabilities(open=True)
BUTTON_LOCK_CAPABILITIES: Final = LockCapabilities(open=False)
SMART_DOOR_LOCK_CAPABILITIES: Final = LockCapabilities(open=True)
