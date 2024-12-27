"""Module for hub data points implemented using the switch category."""

from __future__ import annotations

from hahomematic.const import DataPointCategory
from hahomematic.decorators import service
from hahomematic.model.decorators import state_property
from hahomematic.model.hub.data_point import GenericProgramDataPoint, GenericSysvarDataPoint


class SysvarDpSwitch(GenericSysvarDataPoint):
    """Implementation of a sysvar switch data_point."""

    _category = DataPointCategory.HUB_SWITCH
    _is_extended = True


class ProgramDpSwitch(GenericProgramDataPoint):
    """Implementation of a program switch data_point."""

    _category = DataPointCategory.HUB_SWITCH

    @state_property
    def value(self) -> bool | None:
        """Get the value of the data_point."""
        return self._is_active

    @service()
    async def turn_on(self) -> None:
        """Turn the program on."""
        await self.central.set_program_state(pid=self._pid, state=True)
        await self._central.fetch_program_data(scheduled=False)

    @service()
    async def turn_off(self) -> None:
        """Turn the program off."""
        await self.central.set_program_state(pid=self._pid, state=False)
        await self._central.fetch_program_data(scheduled=False)
