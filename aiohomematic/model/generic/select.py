# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Module for data points implemented using the select category."""

from __future__ import annotations

from aiohomematic import i18n
from aiohomematic.const import DataPointCategory
from aiohomematic.exceptions import ValidationException
from aiohomematic.model.generic.data_point import GenericDataPoint
from aiohomematic.model.support import get_value_from_value_list
from aiohomematic.property_decorators import state_property


class DpSelect(GenericDataPoint[int | str, int | float | str]):
    """
    Implementation of a select data_point.

    This is a default data point that gets automatically generated.
    """

    __slots__ = ()

    _category = DataPointCategory.SELECT

    @state_property
    def value(self) -> int | str:
        """Get the value of the data_point."""
        if (value := get_value_from_value_list(value=self._value, value_list=self.values)) is not None:
            return value
        return self._default

    def _prepare_value_for_sending(self, *, value: int | float | str, do_validate: bool = True) -> int:
        """Prepare value before sending."""
        # We allow setting the value via index as well, just in case.
        if isinstance(value, int | float) and self._values and 0 <= value < len(self._values):
            return int(value)
        if self._values and value in self._values:
            return self._values.index(value)
        raise ValidationException(
            i18n.tr(
                "exception.model.select.value_not_in_value_list",
                name=self.name,
                unique_id=self.unique_id,
            )
        )
