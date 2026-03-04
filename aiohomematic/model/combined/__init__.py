# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Combined data points for AioHomematic.

This subpackage provides data points that combine multiple underlying data
points into a single writable entity. The primary use case is timer value+unit
pairs (e.g., DURATION_VALUE + DURATION_UNIT) that need to be exposed as a
single number entity in Home Assistant.

Modules/classes:
- CombinedDataPoint: Abstract base class for combined data points.
- CombinedDpTimerAction: Concrete implementation for timer value+unit pairs.
- CombinedTimerField: Descriptor for declarative combined timer field definitions.
"""

from __future__ import annotations

from aiohomematic.model.combined.data_point import CombinedDataPoint
from aiohomematic.model.combined.field import CombinedTimerField
from aiohomematic.model.combined.timer import CombinedDpTimerAction

__all__ = [
    "CombinedDataPoint",
    "CombinedDpTimerAction",
    "CombinedTimerField",
]
