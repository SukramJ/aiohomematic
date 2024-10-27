"""Module for data points implemented using the binary_sensor category."""

from __future__ import annotations

from hahomematic.const import DataPointCategory
from hahomematic.model.decorators import state_property
from hahomematic.model.generic.data_point import GenericDataPoint


class DpBinarySensor(GenericDataPoint[bool | None, bool]):
    """
    Implementation of a binary_sensor.

    This is a default data point that gets automatically generated.
    """

    _category = DataPointCategory.BINARY_SENSOR

    @state_property
    def value(self) -> bool | None:  # type: ignore[override]
        """Return the value of the data_point."""
        if self._value is not None:
            return self._value  # type: ignore[no-any-return]
        return self._default  # type: ignore[no-any-return]
