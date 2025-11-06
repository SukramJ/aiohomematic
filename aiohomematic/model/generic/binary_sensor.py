# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Module for data points implemented using the binary_sensor category."""

from __future__ import annotations

from aiohomematic.const import DataPointCategory
from aiohomematic.model.generic.data_point import GenericDataPoint
from aiohomematic.property_decorators import state_property


class DpBinarySensor(GenericDataPoint[bool | None, bool]):
    """
    Implementation of a binary_sensor.

    This is a default data point that gets automatically generated.
    """

    __slots__ = ()

    _category = DataPointCategory.BINARY_SENSOR

    @state_property
    def value(self) -> bool | None:
        """Return the value of the data_point."""
        if self._value is not None:
            return self._value
        return self._default
