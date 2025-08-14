"""Module for hub data points implemented using the button category."""

from __future__ import annotations

from aiohomematic.const import DataPointCategory
from aiohomematic.decorators import inspector
from aiohomematic.model.decorators import state_property
from aiohomematic.model.hub.data_point import GenericProgramDataPoint


class ProgramDpButton(GenericProgramDataPoint):
    """Class for a HomeMatic program button."""

    __slots__ = ()

    _category = DataPointCategory.HUB_BUTTON

    @state_property
    def available(self) -> bool:
        """Return the availability of the device."""
        return self._is_active and self._central.available

    @inspector()
    async def press(self) -> None:
        """Handle the button press."""
        await self.central.execute_program(pid=self.pid)
