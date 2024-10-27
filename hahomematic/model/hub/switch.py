"""Module for hub data points implemented using the switch category."""

from __future__ import annotations

from hahomematic.const import DataPointCategory
from hahomematic.model.hub.data_point import GenericSysvarDataPoint


class SysvarDpSwitch(GenericSysvarDataPoint):
    """Implementation of a sysvar switch data_point."""

    _category = DataPointCategory.HUB_SWITCH
    _is_extended = True
