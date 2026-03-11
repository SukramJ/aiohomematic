# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Generic action string data points for write-only string parameters.

Public API of this module is defined by __all__.

Action strings are used for write-only STRING parameters (TYPE=STRING, OPERATIONS=WRITE).
Unlike DpAction which uses Any as the value type, DpActionString provides
type-safe string value handling.
"""

from aiohomematic.const import DataPointCategory
from aiohomematic.model.generic.data_point import GenericDataPoint


class DpActionString(GenericDataPoint[str | None, str]):
    """
    Implementation of a write-only string action.

    This is a data point that gets automatically generated for write-only
    STRING parameters. It provides type-safe string value handling compared
    to the generic DpAction fallback.
    """

    __slots__ = ()

    _category = DataPointCategory.ACTION
    _validate_state_change = False

    def _prepare_value_for_sending(self, *, value: str, do_validate: bool = True) -> str:
        """Prepare value before sending."""
        return str(value)
