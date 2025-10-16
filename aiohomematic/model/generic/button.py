# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Module for data points implemented using the button category."""

from __future__ import annotations

from aiohomematic.const import DataPointCategory
from aiohomematic.decorators import inspector
from aiohomematic.model.generic.data_point import GenericDataPoint


class DpButton(GenericDataPoint[None, bool]):
    """
    Implementation of a button.

    This is a default data point that gets automatically generated.
    """

    __slots__ = ()

    _category = DataPointCategory.BUTTON
    _validate_state_change = False

    @inspector
    async def press(self) -> None:
        """Handle the button press."""
        await self.send_value(value=True)
