"""Module for hub data points implemented using the button category."""

from __future__ import annotations

from typing import Final

from hahomematic import central as hmcu
from hahomematic.const import PROGRAM_ADDRESS, DataPointCategory, HubData, ProgramData
from hahomematic.model.decorators import get_service_calls, service, state_property
from hahomematic.model.hub.data_point import GenericHubDataPoint


class ProgramDpButton(GenericHubDataPoint):
    """Class for a HomeMatic program button."""

    _category = DataPointCategory.HUB_BUTTON

    def __init__(
        self,
        central: hmcu.CentralUnit,
        data: ProgramData,
    ) -> None:
        """Initialize the data_point."""
        super().__init__(
            central=central,
            address=PROGRAM_ADDRESS,
            data=data,
        )
        self.pid: Final = data.pid
        self.ccu_program_name: Final = data.name
        self.is_active: bool = data.is_active
        self.is_internal: bool = data.is_internal
        self.last_execute_time: str = data.last_execute_time
        self._service_methods = get_service_calls(obj=self)

    @state_property
    def available(self) -> bool:
        """Return the availability of the device."""
        return self.is_active

    def get_name(self, data: HubData) -> str:
        """Return the name of the program button data_point."""
        if data.name.lower().startswith(tuple({"p_", "prg_"})):
            return data.name
        return f"P_{data.name}"

    def update_data(self, data: ProgramData) -> None:
        """Set variable value on CCU/Homegear."""
        do_update: bool = False
        if self.is_active != data.is_active:
            self.is_active = data.is_active
            do_update = True
        if self.is_internal != data.is_internal:
            self.is_internal = data.is_internal
            do_update = True
        if self.last_execute_time != data.last_execute_time:
            self.last_execute_time = data.last_execute_time
            do_update = True
        if do_update:
            self.fire_data_point_updated_callback()

    @service()
    async def press(self) -> None:
        """Handle the button press."""
        await self.central.execute_program(pid=self.pid)
