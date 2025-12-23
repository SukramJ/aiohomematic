# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Module for AioHomematic hub data points."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Final

from slugify import slugify

from aiohomematic.const import (
    PROGRAM_ADDRESS,
    SYSVAR_ADDRESS,
    SYSVAR_TYPE,
    HubData,
    HubValueType,
    ProgramData,
    SystemVariableData,
)
from aiohomematic.decorators import inspector
from aiohomematic.interfaces.central import (
    CentralInfoProtocol,
    ChannelLookupProtocol,
    ConfigProviderProtocol,
    EventBusProviderProtocol,
    EventPublisherProtocol,
    HubDataFetcherProtocol,
)
from aiohomematic.interfaces.client import PrimaryClientProviderProtocol
from aiohomematic.interfaces.model import (
    ChannelProtocol,
    GenericHubDataPointProtocol,
    GenericProgramDataPointProtocol,
    GenericSysvarDataPointProtocol,
)
from aiohomematic.interfaces.operations import (
    ParameterVisibilityProviderProtocol,
    ParamsetDescriptionProviderProtocol,
    TaskSchedulerProtocol,
)
from aiohomematic.model.data_point import CallbackDataPoint
from aiohomematic.model.support import (
    PathData,
    ProgramPathData,
    SysvarPathData,
    generate_unique_id,
    get_hub_data_point_name_data,
)
from aiohomematic.property_decorators import DelegatedProperty, Kind, state_property
from aiohomematic.support import PayloadMixin, parse_sys_var


class GenericHubDataPoint(CallbackDataPoint, GenericHubDataPointProtocol, PayloadMixin):
    """Class for a Homematic system variable."""

    __slots__ = (
        "_channel",
        "_description",
        "_enabled_default",
        "_legacy_name",
        "_name_data",
        "_primary_client_provider",
        "_state_uncertain",
    )

    def __init__(
        self,
        *,
        config_provider: ConfigProviderProtocol,
        central_info: CentralInfoProtocol,
        event_bus_provider: EventBusProviderProtocol,
        event_publisher: EventPublisherProtocol,
        task_scheduler: TaskSchedulerProtocol,
        paramset_description_provider: ParamsetDescriptionProviderProtocol,
        parameter_visibility_provider: ParameterVisibilityProviderProtocol,
        channel_lookup: ChannelLookupProtocol,
        primary_client_provider: PrimaryClientProviderProtocol,
        address: str,
        data: HubData,
    ) -> None:
        """Initialize the data_point."""
        PayloadMixin.__init__(self)
        unique_id: Final = generate_unique_id(
            config_provider=config_provider,
            address=address,
            parameter=slugify(data.legacy_name),
        )
        self._legacy_name = data.legacy_name
        self._channel = channel_lookup.identify_channel(text=data.legacy_name)
        self._name_data: Final = get_hub_data_point_name_data(
            channel=self._channel, legacy_name=data.legacy_name, central_name=central_info.name
        )
        self._description = data.description
        super().__init__(
            unique_id=unique_id,
            central_info=central_info,
            event_bus_provider=event_bus_provider,
            event_publisher=event_publisher,
            task_scheduler=task_scheduler,
            paramset_description_provider=paramset_description_provider,
            parameter_visibility_provider=parameter_visibility_provider,
        )
        self._enabled_default: Final = data.enabled_default
        self._state_uncertain: bool = True
        self._primary_client_provider: Final = primary_client_provider

    channel: Final = DelegatedProperty[ChannelProtocol | None](path="_channel")
    description: Final = DelegatedProperty[str | None](path="_description", kind=Kind.CONFIG)
    enabled_default: Final = DelegatedProperty[bool](path="_enabled_default")
    full_name: Final = DelegatedProperty[str](path="_name_data.full_name")
    legacy_name: Final = DelegatedProperty[str | None](path="_legacy_name")
    name: Final = DelegatedProperty[str](path="_name_data.name", kind=Kind.CONFIG)
    state_uncertain: Final = DelegatedProperty[bool](path="_state_uncertain")

    @state_property
    def available(self) -> bool:
        """Return the availability of the device."""
        return self._central_info.available

    def _get_signature(self) -> str:
        """Return the signature of the data_point."""
        return f"{self._category}/{self.name}"


class GenericSysvarDataPoint(GenericHubDataPoint, GenericSysvarDataPointProtocol):
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
        *,
        config_provider: ConfigProviderProtocol,
        central_info: CentralInfoProtocol,
        event_bus_provider: EventBusProviderProtocol,
        event_publisher: EventPublisherProtocol,
        task_scheduler: TaskSchedulerProtocol,
        paramset_description_provider: ParamsetDescriptionProviderProtocol,
        parameter_visibility_provider: ParameterVisibilityProviderProtocol,
        channel_lookup: ChannelLookupProtocol,
        primary_client_provider: PrimaryClientProviderProtocol,
        data: SystemVariableData,
    ) -> None:
        """Initialize the data_point."""
        self._vid: Final = data.vid
        super().__init__(
            config_provider=config_provider,
            central_info=central_info,
            event_bus_provider=event_bus_provider,
            event_publisher=event_publisher,
            task_scheduler=task_scheduler,
            paramset_description_provider=paramset_description_provider,
            parameter_visibility_provider=parameter_visibility_provider,
            channel_lookup=channel_lookup,
            primary_client_provider=primary_client_provider,
            address=SYSVAR_ADDRESS,
            data=data,
        )
        self._data_type = data.data_type
        self._values: Final[tuple[str, ...] | None] = tuple(data.values) if data.values else None
        self._max: Final = data.max_value
        self._min: Final = data.min_value
        self._unit: Final = data.unit
        self._current_value: SYSVAR_TYPE = data.value
        self._previous_value: SYSVAR_TYPE = None
        self._temporary_value: SYSVAR_TYPE = None

    is_extended: Final = DelegatedProperty[bool](path="_is_extended")
    max: Final = DelegatedProperty[float | int | None](path="_max", kind=Kind.CONFIG)
    min: Final = DelegatedProperty[float | int | None](path="_min", kind=Kind.CONFIG)
    previous_value: Final = DelegatedProperty[SYSVAR_TYPE](path="_previous_value")
    unit: Final = DelegatedProperty[str | None](path="_unit", kind=Kind.CONFIG)
    values: Final = DelegatedProperty[tuple[str, ...] | None](path="_values", kind=Kind.STATE)
    vid: Final = DelegatedProperty[str](path="_vid", kind=Kind.CONFIG)

    @property
    def _value(self) -> Any | None:
        """Return the value."""
        return self._temporary_value if self._temporary_refreshed_at > self._refreshed_at else self._current_value

    @property
    def data_type(self) -> HubValueType | None:
        """Return the data type."""
        return self._data_type

    @data_type.setter
    def data_type(self, data_type: HubValueType) -> None:
        """Write data_type."""
        self._data_type = data_type

    @state_property
    def value(self) -> Any | None:
        """Return the value."""
        return self._value

    async def event(self, *, value: Any, received_at: datetime) -> None:
        """Handle event for which this data_point has subscribed."""
        self.write_value(value=value, write_at=received_at)

    @inspector
    async def send_variable(self, *, value: Any) -> None:
        """Set variable value on the backend."""
        if client := self._primary_client_provider.primary_client:
            await client.set_system_variable(
                legacy_name=self._legacy_name, value=parse_sys_var(data_type=self._data_type, raw_value=value)
            )
        self._write_temporary_value(value=value, write_at=datetime.now())

    def write_value(self, *, value: Any, write_at: datetime) -> None:
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
        self.publish_data_point_updated_event()

    def _convert_value(self, *, old_value: Any, new_value: Any) -> Any:
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

    def _get_path_data(self) -> PathData:
        """Return the path data of the data_point."""
        return SysvarPathData(vid=self._vid)

    def _reset_temporary_value(self) -> None:
        """Reset the temp storage."""
        self._temporary_value = None
        self._reset_temporary_timestamps()

    def _write_temporary_value(self, *, value: Any, write_at: datetime) -> None:
        """Update the temporary value of the data_point."""
        self._reset_temporary_value()

        temp_value = self._convert_value(old_value=self._current_value, new_value=value)
        if self._value == temp_value:
            self._set_temporary_refreshed_at(refreshed_at=write_at)
        else:
            self._set_temporary_modified_at(modified_at=write_at)
            self._temporary_value = temp_value
            self._state_uncertain = True
        self.publish_data_point_updated_event()


class GenericProgramDataPoint(GenericHubDataPoint, GenericProgramDataPointProtocol):
    """Class for a generic Homematic progran data point."""

    __slots__ = (
        "_hub_data_fetcher",
        "_is_active",
        "_is_internal",
        "_last_execute_time",
        "_pid",
    )

    def __init__(
        self,
        *,
        config_provider: ConfigProviderProtocol,
        central_info: CentralInfoProtocol,
        event_bus_provider: EventBusProviderProtocol,
        event_publisher: EventPublisherProtocol,
        task_scheduler: TaskSchedulerProtocol,
        paramset_description_provider: ParamsetDescriptionProviderProtocol,
        parameter_visibility_provider: ParameterVisibilityProviderProtocol,
        channel_lookup: ChannelLookupProtocol,
        primary_client_provider: PrimaryClientProviderProtocol,
        hub_data_fetcher: HubDataFetcherProtocol,
        data: ProgramData,
    ) -> None:
        """Initialize the data_point."""
        self._pid: Final = data.pid
        super().__init__(
            config_provider=config_provider,
            central_info=central_info,
            event_bus_provider=event_bus_provider,
            event_publisher=event_publisher,
            task_scheduler=task_scheduler,
            paramset_description_provider=paramset_description_provider,
            parameter_visibility_provider=parameter_visibility_provider,
            channel_lookup=channel_lookup,
            primary_client_provider=primary_client_provider,
            address=PROGRAM_ADDRESS,
            data=data,
        )
        self._is_active: bool = data.is_active
        self._is_internal: bool = data.is_internal
        self._last_execute_time: str = data.last_execute_time
        self._state_uncertain: bool = True
        self._hub_data_fetcher: Final = hub_data_fetcher

    is_active: Final = DelegatedProperty[bool](path="_is_active", kind=Kind.STATE)
    is_internal: Final = DelegatedProperty[bool](path="_is_internal", kind=Kind.CONFIG)
    last_execute_time: Final = DelegatedProperty[str](path="_last_execute_time", kind=Kind.STATE)
    pid: Final = DelegatedProperty[str](path="_pid", kind=Kind.CONFIG)

    def update_data(self, *, data: ProgramData) -> None:
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
            self.publish_data_point_updated_event()

    def _get_path_data(self) -> PathData:
        """Return the path data of the data_point."""
        return ProgramPathData(pid=self.pid)
