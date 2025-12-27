# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Generic select data points for dropdown selection values.

Public API of this module is defined by __all__.
"""

from __future__ import annotations

from aiohomematic import i18n
from aiohomematic.const import DataPointCategory
from aiohomematic.exceptions import ValidationException
from aiohomematic.model.generic.data_point import GenericDataPoint
from aiohomematic.model.support import get_value_from_value_list


class DpSelect(GenericDataPoint[int | str, int | float | str]):
    """
    Implementation of a select data_point.

    This is a default data point that gets automatically generated.
    """

    __slots__ = ()

    _category = DataPointCategory.SELECT

    def _get_value(self) -> int | str:
        """Return the value for readings."""
        # For index-based ENUMs (HM), convert integer index to string value.
        if (value := get_value_from_value_list(value=self._value, value_list=self.values)) is not None:
            return value
        # For string-based ENUMs (HmIP), return the string value directly if valid.
        if isinstance(self._value, str) and self._values is not None and self._value in self._values:
            return self._value
        return self._default

    def _prepare_value_for_sending(self, *, value: int | float | str, do_validate: bool = True) -> int | str:
        """Prepare value before sending."""
        # We allow setting the value via index as well, just in case.
        if isinstance(value, int | float) and self._values and 0 <= value < len(self._values):
            return int(value)
        if self._values and value in self._values:
            # For string-based ENUMs (HmIP), send the string value directly.
            # For index-based ENUMs (HM), convert string to index.
            if self._enum_value_is_index:
                return self._values.index(value)
            return str(value)
        raise ValidationException(
            i18n.tr(
                key="exception.model.select.value_not_in_value_list",
                name=self.name,
                unique_id=self.unique_id,
            )
        )
