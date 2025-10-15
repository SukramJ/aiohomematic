# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Module for action data points.

Actions are used to send data for write only parameters to backend.
"""

from __future__ import annotations

from typing import Any

from aiohomematic.const import DataPointCategory
from aiohomematic.model.generic.data_point import GenericDataPoint
from aiohomematic.model.support import get_index_of_value_from_value_list


class DpAction(GenericDataPoint[None, Any]):
    """
    Implementation of an action.

    This is an internal default category that gets automatically generated.
    """

    __slots__ = ()

    _category = DataPointCategory.ACTION
    _validate_state_change = False

    def _prepare_value_for_sending(self, *, value: Any, do_validate: bool = True) -> Any:
        """Prepare value before sending."""
        if (index := get_index_of_value_from_value_list(value=value, value_list=self._values)) is not None:
            return index
        return value
