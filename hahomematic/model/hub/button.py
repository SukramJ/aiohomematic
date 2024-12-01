"""Module for hub data points implemented using the button category."""

from __future__ import annotations

from typing import Final

from hahomematic import central as hmcu
from hahomematic.const import PROGRAM_ADDRESS, DataPointCategory, HubData, ProgramData
from hahomematic.decorators import get_service_calls, service
from hahomematic.model.decorators import config_property, state_property
from hahomematic.model.hub.data_point import GenericHubDataPoint
from hahomematic.model.support import PathData, ProgramPathData


class ProgramDpButton(GenericHubDataPoint):
    """Class for a HomeMatic program button."""

    _category = DataPointCategory.HUB_BUTTON

    def __init__(
        self,
        central: hmcu.CentralUnit,
        data: ProgramData,
    ) -> None:
        """Initialize the data_point."""
        self._pid: Final = data.pid
        super().__init__(
            central=central,
            address=PROGRAM_ADDRESS,
            data=data,
        )
        self._ccu_program_name: Final = data.name
        self._description = data.description
        self._is_active: bool = data.is_active
        self._is_internal: bool = data.is_internal
        self._last_execute_time: str = data.last_execute_time
        self._service_methods = get_service_calls(obj=self)

    @state_property
    def available(self) -> bool:
        """Return the availability of the device."""
        return self._is_active

    @config_property
    def ccu_program_name(self) -> str:
        """Return the ccu program name."""
        return self._ccu_program_name

    @config_property
    def description(self) -> str | None:
        """Return sysvar description."""
        return self._description

    @state_property
    def is_active(self) -> bool:
        """Return the program is active."""
        return self._is_active

    @config_property
    def is_internal(self) -> bool:
        """Return the program is internal."""
        return self._is_internal

    @state_property
    def last_execute_time(self) -> str:
        """Return the last execute time."""
        return self._last_execute_time

    @config_property
    def pid(self) -> str:
        """Return the program id."""
        return self._pid

    def get_name(self, data: HubData) -> str:
        """Return the name of the program button data_point."""
        if data.name.lower().startswith(tuple({"p_", "prg_"})):
            return data.name
        return f"P_{data.name}"

    def update_data(self, data: ProgramData) -> None:
        """Set variable value on CCU/Homegear."""
        do_update: bool = False
        if self._is_active != data.is_active:
            self._is_active = data.is_active
            do_update = True
        if self._is_internal != data.is_internal:
            self._is_internal = data.is_internal
            do_update = True
        if self._last_execute_time != data.last_execute_time:
            self._last_execute_time = data.last_execute_time
            do_update = True
        if do_update:
            self.fire_data_point_updated_callback()

    @service()
    async def press(self) -> None:
        """Handle the button press."""
        await self.central.execute_program(pid=self.pid)

    def _get_path_data(self) -> PathData:
        """Return the path data of the data_point."""
        return ProgramPathData(pid=self.pid)
