# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Module for data points implemented using the text category."""

from __future__ import annotations

from typing import cast

from aiohomematic.const import DataPointCategory
from aiohomematic.model.generic.data_point import GenericDataPoint
from aiohomematic.model.support import check_length_and_log
from aiohomematic.property_decorators import state_property


class DpText(GenericDataPoint[str, str]):
    """
    Implementation of a text.

    This is a default data point that gets automatically generated.
    """

    __slots__ = ()

    _category = DataPointCategory.TEXT

    @state_property
    def value(self) -> str:
        """Get the value of the data_point."""
        if (val := check_length_and_log(name=self.name, value=self._value)) is not None:
            return cast(str, val)
        return self._default
