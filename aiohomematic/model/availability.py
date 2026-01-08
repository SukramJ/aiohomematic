# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Availability information for Homematic devices.

This module provides the AvailabilityInfo dataclass that bundles
device reachability, battery state, and signal strength information
into a single unified view for external consumers.

Public API of this module is defined by __all__.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final

__all__: Final = ["AvailabilityInfo"]


@dataclass(frozen=True, slots=True)
class AvailabilityInfo:
    """
    Bundled availability information for a Homematic device.

    Provides a unified view of device connectivity and health status,
    combining reachability, battery state, and signal strength.

    This dataclass is immutable (frozen) to ensure thread-safety when
    passed between components.

    Example:
        >>> info = device.availability
        >>> if not info.is_reachable:
        ...     print(f"Device unreachable since {info.last_updated}")
        >>> if info.low_battery:
        ...     print(f"Battery low: {info.battery_level}%")

    """

    is_reachable: bool
    """Device is reachable (inverse of UNREACH parameter)."""

    last_updated: datetime | None
    """Most recent data point modification time across all channels."""

    battery_level: int | None = None
    """Battery level percentage (0-100), from OperatingVoltageLevel or BATTERY_STATE."""

    low_battery: bool | None = None
    """Low battery indicator from LOW_BAT parameter."""

    signal_strength: int | None = None
    """Signal strength in dBm from RSSI_DEVICE (negative values, e.g., -65)."""

    @property
    def has_battery(self) -> bool:
        """Return True if any battery information is available."""
        return self.battery_level is not None or self.low_battery is not None

    @property
    def has_signal_info(self) -> bool:
        """Return True if signal strength information is available."""
        return self.signal_strength is not None
