# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025 Daniel Perna, SukramJ
"""Module for AioHomematic hub data points."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Final

from slugify import slugify

from aiohomematic import central as hmcu
from aiohomematic.const import (
    PROGRAM_ADDRESS,
    SYSVAR_ADDRESS,
    SYSVAR_TYPE,
    HubData,
    ProgramData,
    SystemVariableData,
    SysvarType,
)
from aiohomematic.decorators import inspector
from aiohomematic.model.data_point import CallbackDataPoint
from aiohomematic.model.device import Channel
from aiohomematic.model.support import (
    PathData,
    ProgramPathData,
    SysvarPathData,
    generate_unique_id,
    get_hub_data_point_name_data,
)
from aiohomematic.property_decorators import config_property, state_property
from aiohomematic.support import PayloadMixin, parse_sys_var


class GenericHubDataPoint(CallbackDataPoint, PayloadMixin):
    """Class for a Homematic system variable."""

    __slots__ = (
        "_channel",
        "_description",
        "_enabled_default",
        "_legacy_name",
        "_name_data",
        "_state_uncertain",
    )

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
            parameter=slugify(data.legacy_name),
        )
        self._legacy_name = data.legacy_name
        self._channel = central.identify_channel(text=data.legacy_name)
        self._name_data: Final = get_hub_data_point_name_data(
            channel=self._channel, legacy_name=data.legacy_name, central_name=central.name
        )
        self._description = data.description
        super().__init__(central=central, unique_id=unique_id)
        self._enabled_default: Final = data.enabled_default
        self._state_uncertain: bool = True

    @state_property
    def available(self) -> bool:
        """Return the availability of the device."""
        return self.central.available

    @property
    def legacy_name(self) -> str | None:
        """Return the original sysvar name."""
        return self._legacy_name

    @property
    def channel(self) -> Channel | None:
        """Return the identified channel."""
        return self._channel

    @config_property
    def description(self) -> str | None:
        """Return sysvar description."""
        return self._description

    @property
    def full_name(self) -> str:
        """Return the fullname of the data_point."""
        return self._name_data.full_name

    @property
    def enabled_default(self) -> bool:
        """Return if the data_point should be enabled."""
        return self._enabled_default

    @config_property
    def name(self) -> str:
        """Return the name of the data_point."""
        return self._name_data.name

    @property
    def state_uncertain(self) -> bool:
        """Return, if the state is uncertain."""
        return self._state_uncertain

    def _get_signature(self) -> str:
        """Return the signature of the data_point."""
        return f"{self._category}/{self.name}"


class GenericSysvarDataPoint(GenericHubDataPoint):
    """Class for a Homematic system variable."""

    __slots__ = (
        "_current_value",
        "_data_type",
        "_max",
        "_min",
        "_previous_value",
        "_temporary_value",
        "_unit",
        "_values",
        "_vid",
    )

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
        return self._temporary_value if self._temporary_refreshed_at > self._refreshed_at else self._current_value

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

    async def event(self, value: Any, received_at: datetime) -> None:
        """Handle event for which this data_point has subscribed."""
        self.write_value(value=value, write_at=received_at)

    def _reset_temporary_value(self) -> None:
        """Reset the temp storage."""
        self._temporary_value = None
        self._reset_temporary_timestamps()

    def write_value(self, value: Any, write_at: datetime) -> None:
        """Set variable value on the backend."""
        self._reset_temporary_value()

        old_value = self._current_value
        new_value = self._convert_value(old_value=old_value, new_value=value)
        if old_value == new_value:
            self._set_refreshed_at(refreshed_at=write_at)
        else:
            self._set_modified_at(modified_at=write_at)
            self._previous_value = old_value
            self._current_value = new_value
        self._state_uncertain = False
        self.fire_data_point_updated_callback()

    def _write_temporary_value(self, value: Any, write_at: datetime) -> None:
        """Update the temporary value of the data_point."""
        self._reset_temporary_value()

        temp_value = self._convert_value(old_value=self._current_value, new_value=value)
        if self._value == temp_value:
            self._set_temporary_refreshed_at(refreshed_at=write_at)
        else:
            self._set_temporary_modified_at(modified_at=write_at)
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

    @inspector
    async def send_variable(self, value: Any) -> None:
        """Set variable value on the backend."""
        if client := self.central.primary_client:
            await client.set_system_variable(legacy_name=self._legacy_name, value=parse_sys_var(self._data_type, value))
        self._write_temporary_value(value=value, write_at=datetime.now())


class GenericProgramDataPoint(GenericHubDataPoint):
    """Class for a generic Homematic progran data point."""

    __slots__ = (
        "_pid",
        "_is_active",
        "_is_internal",
        "_last_execute_time",
    )

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
        """Set variable value on the backend."""
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
