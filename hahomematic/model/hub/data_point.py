"""Module for HaHomematic hub data points."""

from __future__ import annotations

from typing import Any, Final

from slugify import slugify

from hahomematic import central as hmcu
from hahomematic.const import (
    PROGRAM_ADDRESS,
    SYSVAR_ADDRESS,
    SYSVAR_TYPE,
    HubData,
    ProgramData,
    SystemVariableData,
    SysvarType,
)
from hahomematic.decorators import get_service_calls, service
from hahomematic.model.data_point import CallbackDataPoint
from hahomematic.model.decorators import config_property, state_property
from hahomematic.model.support import PathData, PayloadMixin, ProgramPathData, SysvarPathData, generate_unique_id
from hahomematic.support import parse_sys_var


class GenericHubDataPoint(CallbackDataPoint, PayloadMixin):
    """Class for a HomeMatic system variable."""

    def __init__(
        self,
        central: hmcu.CentralUnit,
        address: str,
        data: HubData,
    ) -> None:
        """Initialize the data_point."""
        PayloadMixin.__init__(self)
        unique_id: Final = generate_unique_id(
            central=central,
            address=address,
            parameter=slugify(data.name),
        )
        self._name: Final = data.name
        self._description = data.description
        super().__init__(central=central, unique_id=unique_id)
        self._full_name: Final = f"{self._central.name}_{self._name}"
        self._enabled_default: Final = data.enabled_default

        self._state_uncertain: bool = True

    @state_property
    def available(self) -> bool:
        """Return the availability of the device."""
        return self.central.available

    @config_property
    def description(self) -> str | None:
        """Return sysvar description."""
        return self._description

    @property
    def full_name(self) -> str:
        """Return the fullname of the data_point."""
        return self._full_name

    @property
    def enabled_default(self) -> bool:
        """Return if the data_point should be enabled."""
        return self._enabled_default

    @config_property
    def name(self) -> str:
        """Return the name of the data_point."""
        return self._name

    @property
    def state_uncertain(self) -> bool:
        """Return, if the state is uncertain."""
        return self._state_uncertain


class GenericSysvarDataPoint(GenericHubDataPoint):
    """Class for a HomeMatic system variable."""

    _is_extended = False

    def __init__(
        self,
        central: hmcu.CentralUnit,
        data: SystemVariableData,
    ) -> None:
        """Initialize the data_point."""
        self._vid: Final = data.vid
        super().__init__(central=central, address=SYSVAR_ADDRESS, data=data)
        self._data_type = data.data_type
        self._values: Final[tuple[str, ...] | None] = tuple(data.values) if data.values else None
        self._max: Final = data.max_value
        self._min: Final = data.min_value
        self._unit: Final = data.unit
        self._current_value: SYSVAR_TYPE = data.value
        self._previous_value: SYSVAR_TYPE = None
        self._temporary_value: SYSVAR_TYPE = None
        self._service_methods = get_service_calls(obj=self)

    @property
    def data_type(self) -> SysvarType | None:
        """Return the availability of the device."""
        return self._data_type

    @data_type.setter
    def data_type(self, data_type: SysvarType) -> None:
        """Write data_type."""
        self._data_type = data_type

    @config_property
    def vid(self) -> str:
        """Return sysvar id."""
        return self._vid

    @property
    def previous_value(self) -> SYSVAR_TYPE:
        """Return the previous value."""
        return self._previous_value

    @property
    def _value(self) -> Any | None:
        """Return the value."""
        if self._temporary_refreshed_at > self._refreshed_at:
            return self._temporary_value
        return self._current_value

    @state_property
    def value(self) -> Any | None:
        """Return the value."""
        return self._value

    @state_property
    def values(self) -> tuple[str, ...] | None:
        """Return the value_list."""
        return self._values

    @config_property
    def max(self) -> float | int | None:
        """Return the max value."""
        return self._max

    @config_property
    def min(self) -> float | int | None:
        """Return the min value."""
        return self._min

    @config_property
    def unit(self) -> str | None:
        """Return the unit of the data_point."""
        return self._unit

    @property
    def is_extended(self) -> bool:
        """Return if the data_point is an extended type."""
        return self._is_extended

    def _get_path_data(self) -> PathData:
        """Return the path data of the data_point."""
        return SysvarPathData(vid=self._vid)

    async def event(self, value: Any) -> None:
        """Handle event for which this data_point has subscribed."""
        self.write_value(value=value)

    def _reset_temporary_value(self) -> None:
        """Reset the temp storage."""
        self._temporary_value = None
        self._reset_temporary_timestamps()

    def write_value(self, value: Any) -> None:
        """Set variable value on CCU/Homegear."""
        self._reset_temporary_value()

        old_value = self._current_value
        new_value = self._convert_value(old_value=old_value, new_value=value)
        if old_value == new_value:
            self._set_refreshed_at()
        else:
            self._set_modified_at()
            self._previous_value = old_value
            self._current_value = new_value
        self._state_uncertain = False
        self.fire_data_point_updated_callback()

    def _write_temporary_value(self, value: Any) -> None:
        """Update the temporary value of the data_point."""
        self._reset_temporary_value()

        temp_value = self._convert_value(old_value=self._current_value, new_value=value)
        if self._value == temp_value:
            self._set_temporary_refreshed_at()
        else:
            self._set_temporary_modified_at()
            self._temporary_value = temp_value
            self._state_uncertain = True
        self.fire_data_point_updated_callback()

    def _convert_value(self, old_value: Any, new_value: Any) -> Any:
        """Convert to value to SYSVAR_TYPE."""
        if new_value is None:
            return None
        value = new_value
        if self._data_type:
            value = parse_sys_var(data_type=self._data_type, raw_value=new_value)
        elif isinstance(old_value, bool):
            value = bool(new_value)
        elif isinstance(old_value, int):
            value = int(new_value)
        elif isinstance(old_value, str):
            value = str(new_value)
        elif isinstance(old_value, float):
            value = float(new_value)
        return value

    @service()
    async def send_variable(self, value: Any) -> None:
        """Set variable value on CCU/Homegear."""
        if client := self.central.primary_client:
            await client.set_system_variable(name=self._name, value=parse_sys_var(self._data_type, value))
        self._write_temporary_value(value=value)


class GenericProgramDataPoint(GenericHubDataPoint):
    """Class for a generic HomeMatic progran data point."""

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
        self._is_active: bool = data.is_active
        self._is_internal: bool = data.is_internal
        self._last_execute_time: str = data.last_execute_time
        self._state_uncertain: bool = True
        self._service_methods = get_service_calls(obj=self)

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

    def _get_path_data(self) -> PathData:
        """Return the path data of the data_point."""
        return ProgramPathData(pid=self.pid)
