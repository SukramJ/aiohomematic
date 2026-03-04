# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Generic action boolean data points for write-only boolean parameters.

Public API of this module is defined by __all__.

Action booleans are used for write-only BOOL parameters (TYPE=BOOL, OPERATIONS=WRITE).
Unlike DpAction which uses Any as the value type, DpActionBoolean provides
type-safe boolean value handling.
"""

from __future__ import annotations

from aiohomematic.const import DataPointCategory
from aiohomematic.model.generic.data_point import GenericDataPoint


class DpActionBoolean(GenericDataPoint[bool | None, bool]):
    """
    Implementation of a write-only boolean action.

    This is a data point that gets automatically generated for write-only
    BOOL parameters. It provides type-safe boolean value handling compared
    to the generic DpAction fallback.
    """

    __slots__ = ()

    _category = DataPointCategory.ACTION
    _validate_state_change = False

    def _prepare_value_for_sending(self, *, value: bool, do_validate: bool = True) -> bool:
        """Prepare value before sending."""
        return bool(value)
