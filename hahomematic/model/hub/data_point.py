"""Module for HaHomematic hub data points."""

from __future__ import annotations

from abc import abstractmethod
from typing import Any, Final

from slugify import slugify

from hahomematic import central as hmcu
from hahomematic.const import SYSVAR_ADDRESS, HubData, SystemVariableData
from hahomematic.model.data_point import CallbackDataPoint
from hahomematic.model.decorators import (
    config_property,
    get_service_calls,
    service,
    state_property,
)
from hahomematic.model.support import (
    PathData,
    PayloadMixin,
    ProgramPathData,
    SysvarPathData,
    generate_unique_id,
)
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
        self._name: Final = self.get_name(data=data)
        super().__init__(central=central, unique_id=unique_id)
        self._full_name: Final = f"{self._central.name}_{self._name}"

    @abstractmethod
    def get_name(self, data: HubData) -> str:
        """Return the name of the hub data_point."""

    @property
    def full_name(self) -> str:
        """Return the fullname of the data_point."""
        return self._full_name

    @config_property
    def name(self) -> str | None:
        """Return the name of the data_point."""
        return self._name

    def _get_path_data(self) -> PathData:
        """Return the path data of the data_point."""
        return ProgramPathData(name=self._name)


class GenericSysvarDataPoint(GenericHubDataPoint):
    """Class for a HomeMatic system variable."""

    _is_extended = False

    def __init__(
        self,
        central: hmcu.CentralUnit,
        data: SystemVariableData,
    ) -> None:
        """Initialize the data_point."""
        self.ccu_var_name: Final = data.name
        super().__init__(central=central, address=SYSVAR_ADDRESS, data=data)
        self.data_type: Final = data.data_type
        self._values: Final[tuple[str, ...] | None] = tuple(data.values) if data.values else None
        self._max: Final = data.max_value
        self._min: Final = data.min_value
        self._unit: Final = data.unit
        self._value = data.value
        self._old_value: bool | float | int | str | None = None
        self._service_methods = get_service_calls(obj=self)

    @state_property
    def available(self) -> bool:
        """Return the availability of the device."""
        return self.central.available

    @property
    def old_value(self) -> Any | None:
        """Return the old value."""
        return self._old_value

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
        return SysvarPathData(name=self.ccu_var_name)

    def get_name(self, data: HubData) -> str:
        """Return the name of the sysvar data_point."""
        if data.name.lower().startswith(tuple({"v_", "sv_", "sv"})):
            return data.name
        return f"Sv_{data.name}"

    def write_value(self, value: Any) -> None:
        """Set variable value on CCU/Homegear."""
        old_value = self._value
        if self.data_type:
            value = parse_sys_var(data_type=self.data_type, raw_value=value)
        elif isinstance(old_value, bool):
            value = bool(value)
        elif isinstance(old_value, int):
            value = int(value)
        elif isinstance(old_value, str):
            value = str(value)
        elif isinstance(old_value, float):
            value = float(value)

        if old_value == value:
            self._set_refreshed_at()
        else:
            self._set_modified_at()
            self._old_value = old_value
            self._value = value

        self.fire_data_point_updated_callback()

    @service()
    async def send_variable(self, value: Any) -> None:
        """Set variable value on CCU/Homegear."""
        if client := self.central.primary_client:
            await client.set_system_variable(
                name=self.ccu_var_name, value=parse_sys_var(self.data_type, value)
            )
        self.write_value(value=value)
