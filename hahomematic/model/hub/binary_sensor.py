"""Module for hub data points implemented using the binary_sensor category."""

from __future__ import annotations

from hahomematic.const import DataPointCategory
from hahomematic.model.decorators import state_property
from hahomematic.model.hub.data_point import GenericSysvarDataPoint


class SysvarDpBinarySensor(GenericSysvarDataPoint):
    """Implementation of a sysvar binary_sensor."""

    _category = DataPointCategory.HUB_BINARY_SENSOR

    @state_property
    def value(self) -> bool | None:
        """Return the value of the data_point."""
        if self._value is not None:
            return bool(self._value)
        return None
