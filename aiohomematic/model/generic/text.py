# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025 Daniel Perna, SukramJ
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
    def value(self) -> str | None:
        """Get the value of the data_point."""
        return cast(str | None, check_length_and_log(name=self.name, value=self._value))
