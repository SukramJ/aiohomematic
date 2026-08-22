# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Combined data points for AioHomematic.

This subpackage provides data points that combine multiple underlying data
points into a single writable entity. Use cases include timer value+unit
pairs (e.g., DURATION_VALUE + DURATION_UNIT), hue+saturation color pairs
(HUE + SATURATION), and a garage door's discrete mode combining the
read-only DOOR_STATE with the write-only DOOR_COMMAND.

Modules/classes:
- CombinedDataPoint: Abstract base class for combined data points.
- CombinedDpGarageDoorMode: Concrete implementation for garage door mode.
- CombinedDpHsColor: Concrete implementation for hue+saturation color pairs.
- CombinedDpTimerAction: Concrete implementation for timer value+unit pairs.
- CombinedGarageDoorModeField: Descriptor for declarative combined garage door mode field definitions.
- CombinedHsColorField: Descriptor for declarative combined HS color field definitions.
- CombinedTimerField: Descriptor for declarative combined timer field definitions.
"""

from aiohomematic.model.combined.data_point import CombinedDataPoint
from aiohomematic.model.combined.field import CombinedGarageDoorModeField, CombinedHsColorField, CombinedTimerField
from aiohomematic.model.combined.garage_door_mode import CombinedDpGarageDoorMode
from aiohomematic.model.combined.hs_color import CombinedDpHsColor
from aiohomematic.model.combined.timer import CombinedDpTimerAction

__all__ = [
    "CombinedDataPoint",
    "CombinedDpGarageDoorMode",
    "CombinedDpHsColor",
    "CombinedDpTimerAction",
    "CombinedGarageDoorModeField",
    "CombinedHsColorField",
    "CombinedTimerField",
]
