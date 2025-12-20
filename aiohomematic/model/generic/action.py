# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Generic action data points for triggering operations.

Public API of this module is defined by __all__.

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
        # For string-based ENUMs (HmIP), send the string value directly.
        # For index-based ENUMs (HM), convert string to index.
        if self._values is not None and isinstance(value, str) and value in self._values:
            if self._enum_value_is_index:
                return get_index_of_value_from_value_list(value=value, value_list=self._values)
            return value
        return value
