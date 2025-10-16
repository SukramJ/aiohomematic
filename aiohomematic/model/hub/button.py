# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Module for hub data points implemented using the button category."""

from __future__ import annotations

from aiohomematic.const import DataPointCategory
from aiohomematic.decorators import inspector
from aiohomematic.model.hub.data_point import GenericProgramDataPoint
from aiohomematic.property_decorators import state_property


class ProgramDpButton(GenericProgramDataPoint):
    """Class for a Homematic program button."""

    __slots__ = ()

    _category = DataPointCategory.HUB_BUTTON

    @state_property
    def available(self) -> bool:
        """Return the availability of the device."""
        return self._is_active and self._central.available

    @inspector
    async def press(self) -> None:
        """Handle the button press."""
        await self.central.execute_program(pid=self.pid)
