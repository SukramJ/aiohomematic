# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Module for hub data points implemented using the switch category."""

from __future__ import annotations

from aiohomematic.const import DataPointCategory
from aiohomematic.decorators import inspector
from aiohomematic.model.hub.data_point import GenericProgramDataPoint, GenericSysvarDataPoint
from aiohomematic.property_decorators import state_property


class SysvarDpSwitch(GenericSysvarDataPoint):
    """Implementation of a sysvar switch data_point."""

    __slots__ = ()

    _category = DataPointCategory.HUB_SWITCH
    _is_extended = True


class ProgramDpSwitch(GenericProgramDataPoint):
    """Implementation of a program switch data_point."""

    __slots__ = ()

    _category = DataPointCategory.HUB_SWITCH

    @state_property
    def value(self) -> bool | None:
        """Get the value of the data_point."""
        return self._is_active

    @inspector
    async def turn_off(self) -> None:
        """Turn the program off."""
        await self.central.set_program_state(pid=self._pid, state=False)
        await self._central.fetch_program_data(scheduled=False)

    @inspector
    async def turn_on(self) -> None:
        """Turn the program on."""
        await self.central.set_program_state(pid=self._pid, state=True)
        await self._central.fetch_program_data(scheduled=False)
