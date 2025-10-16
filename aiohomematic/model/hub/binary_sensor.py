# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Module for hub data points implemented using the binary_sensor category."""

from __future__ import annotations

from aiohomematic.const import DataPointCategory
from aiohomematic.model.hub.data_point import GenericSysvarDataPoint
from aiohomematic.property_decorators import state_property


class SysvarDpBinarySensor(GenericSysvarDataPoint):
    """Implementation of a sysvar binary_sensor."""

    __slots__ = ()

    _category = DataPointCategory.HUB_BINARY_SENSOR

    @state_property
    def value(self) -> bool | None:
        """Return the value of the data_point."""
        if self._value is not None:
            return bool(self._value)
        return None
