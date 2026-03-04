# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Combined data points for AioHomematic.

This subpackage provides data points that combine multiple underlying data
points into a single writable entity. Use cases include timer value+unit
pairs (e.g., DURATION_VALUE + DURATION_UNIT) and hue+saturation color pairs
(HUE + SATURATION).

Modules/classes:
- CombinedDataPoint: Abstract base class for combined data points.
- CombinedDpHsColor: Concrete implementation for hue+saturation color pairs.
- CombinedDpTimerAction: Concrete implementation for timer value+unit pairs.
- CombinedHsColorField: Descriptor for declarative combined HS color field definitions.
- CombinedTimerField: Descriptor for declarative combined timer field definitions.
"""

from __future__ import annotations

from aiohomematic.model.combined.data_point import CombinedDataPoint
from aiohomematic.model.combined.field import CombinedHsColorField, CombinedTimerField
from aiohomematic.model.combined.hs_color import CombinedDpHsColor
from aiohomematic.model.combined.timer import CombinedDpTimerAction

__all__ = [
    "CombinedDataPoint",
    "CombinedDpHsColor",
    "CombinedDpTimerAction",
    "CombinedHsColorField",
    "CombinedTimerField",
]
