"""Module for data points implemented using the select category."""

from __future__ import annotations

from hahomematic.const import DataPointCategory
from hahomematic.model.decorators import state_property
from hahomematic.model.generic.data_point import GenericDataPoint
from hahomematic.model.support import get_value_from_value_list


class DpSelect(GenericDataPoint[int | str, int | float | str]):
    """
    Implementation of a select data_point.

    This is a default data point that gets automatically generated.
    """

    _category = DataPointCategory.SELECT

    @state_property
    def value(self) -> str | None:
        """Get the value of the data_point."""
        if (value := get_value_from_value_list(value=self._value, value_list=self.values)) is not None:
            return value
        return str(self._default)

    def _prepare_value_for_sending(self, value: int | float | str, do_validate: bool = True) -> int:
        """Prepare value before sending."""
        # We allow setting the value via index as well, just in case.
        if isinstance(value, int | float) and self._values and 0 <= value < len(self._values):
            return int(value)
        if self._values and value in self._values:
            return self._values.index(value)
        raise ValueError(f"Value not in value_list for {self.name}/{self.unique_id}")
