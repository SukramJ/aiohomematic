# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Generic action select data points for write-only parameters with selectable values.

Public API of this module is defined by __all__.

Action selects are used for write-only ENUM parameters that have a VALUE_LIST.
They provide a value getter for displaying the current selection.
"""

from __future__ import annotations

from aiohomematic import i18n
from aiohomematic.const import DataPointCategory
from aiohomematic.exceptions import ValidationException
from aiohomematic.model.generic.data_point import GenericDataPoint
from aiohomematic.model.support import get_value_from_value_list


class DpActionSelect(GenericDataPoint[int | str | None, int | str]):
    """
    Implementation of an action with selectable values.

    This is a write-only data point with a VALUE_LIST that provides
    a value getter for displaying the current selection.
    Used for ENUM parameters that are write-only but have defined values.
    """

    __slots__ = ()

    _category = DataPointCategory.ACTION_SELECT
    _validate_state_change = False

    def _get_value(self) -> int | str | None:
        """Return the value for readings."""
        # For index-based ENUMs (HM), convert integer index to string value.
        if (value := get_value_from_value_list(value=self._value, value_list=self.values)) is not None:
            return value
        # For string-based ENUMs (HmIP), return the string value directly if valid.
        if isinstance(self._value, str) and self._values is not None and self._value in self._values:
            return self._value
        return self._default

    def _prepare_value_for_sending(self, *, value: int | str, do_validate: bool = True) -> int | str:
        """Prepare value before sending with validation against value_list."""
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
                key="exception.model.action_select.value_not_in_value_list",
                name=self.name,
                unique_id=self.unique_id,
            )
        )
