"""Functions for data_point creation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from contextvars import Token
from datetime import datetime
from functools import partial, wraps
from inspect import getfullargspec
import logging
from typing import Any, Final, cast

import voluptuous as vol

from hahomematic import central as hmcu, client as hmcl, support as hms, validator as val
from hahomematic.async_support import loop_check
from hahomematic.const import (
    CALLBACK_TYPE,
    DEFAULT_CUSTOM_ID,
    DEFAULT_MULTIPLIER,
    DP_KEY_VALUE,
    INIT_DATETIME,
    KEY_CHANNEL_OPERATION_MODE_VISIBILITY,
    KWARGS_ARG_DATA_POINT,
    NO_CACHE_ENTRY,
    WAIT_FOR_CALLBACK,
    CallSource,
    DataPointCategory,
    DataPointKey,
    DataPointUsage,
    EventKey,
    Flag,
    Operations,
    Parameter,
    ParameterData,
    ParameterType,
    ParamsetKey,
)
from hahomematic.context import IN_SERVICE_VAR
from hahomematic.decorators import get_service_calls
from hahomematic.exceptions import BaseHomematicException, HaHomematicException
from hahomematic.model import device as hmd
from hahomematic.model.decorators import config_property, state_property
from hahomematic.model.support import (
    DataPointNameData,
    DataPointPathData,
    GenericParameterType,
    PathData,
    PayloadMixin,
    convert_value,
    generate_unique_id,
)
from hahomematic.support import reduce_args

__all__ = [
    "BaseDataPoint",
    "BaseParameterDataPoint",
    "CallParameterCollector",
    "CallbackDataPoint",
    "EVENT_DATA_SCHEMA",
    "bind_collector",
]

_LOGGER: Final = logging.getLogger(__name__)

_CONFIGURABLE_CHANNEL: Final[tuple[str, ...]] = (
    "KEY_TRANSCEIVER",
    "MULTI_MODE_INPUT_TRANSMITTER",
)
_COLLECTOR_ARGUMENT_NAME: Final = "collector"
_FIX_UNIT_REPLACE: Final[Mapping[str, str]] = {
    '"': "",
    "100%": "%",
    "% rF": "%",
    "degree": "°C",
    "Lux": "lx",
    "m3": "m³",
}
_FIX_UNIT_BY_PARAM: Final[Mapping[str, str]] = {
    Parameter.ACTUAL_TEMPERATURE: "°C",
    Parameter.CURRENT_ILLUMINATION: "lx",
    Parameter.HUMIDITY: "%",
    Parameter.ILLUMINATION: "lx",
    Parameter.LEVEL: "%",
    Parameter.MASS_CONCENTRATION_PM_10_24H_AVERAGE: "µg/m³",
    Parameter.MASS_CONCENTRATION_PM_1_24H_AVERAGE: "µg/m³",
    Parameter.MASS_CONCENTRATION_PM_2_5_24H_AVERAGE: "µg/m³",
    Parameter.OPERATING_VOLTAGE: "V",
    Parameter.RSSI_DEVICE: "dBm",
    Parameter.RSSI_PEER: "dBm",
    Parameter.SUNSHINE_DURATION: "min",
    Parameter.WIND_DIRECTION: "°",
    Parameter.WIND_DIRECTION_RANGE: "°",
}
_MULTIPLIER_UNIT: Final[Mapping[str, float]] = {
    "100%": 100.0,
}

EVENT_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(str(EventKey.ADDRESS)): val.device_address,
        vol.Required(str(EventKey.CHANNEL_NO)): val.channel_no,
        vol.Required(str(EventKey.MODEL)): str,
        vol.Required(str(EventKey.INTERFACE_ID)): str,
        vol.Required(str(EventKey.PARAMETER)): str,
        vol.Optional(str(EventKey.VALUE)): vol.Any(bool, int),
    }
)


class CallbackDataPoint(ABC):
    """Base class for callback data point."""

    _category: DataPointCategory

    def __init__(self, central: hmcu.CentralUnit, unique_id: str) -> None:
        """Init the callback data_point."""
        self._central: Final = central
        self._unique_id: Final = unique_id
        self._data_point_updated_callbacks: dict[Callable, str] = {}
        self._device_removed_callbacks: list[Callable] = []
        self._custom_id: str | None = None
        self._path_data = self._get_path_data()
        self._modified_at: datetime = INIT_DATETIME
        self._refreshed_at: datetime = INIT_DATETIME
        self._temporary_modified_at: datetime = INIT_DATETIME
        self._temporary_refreshed_at: datetime = INIT_DATETIME
        self._service_methods: dict[str, Callable] = {}

    @state_property
    @abstractmethod
    def available(self) -> bool:
        """Return the availability of the device."""

    @property
    def category(self) -> DataPointCategory:
        """Return, the category of the data point."""
        return self._category

    @property
    def custom_id(self) -> str | None:
        """Return the custom id."""
        return self._custom_id

    @classmethod
    def default_category(cls) -> DataPointCategory:
        """Return, the default category of the data_point."""
        return cls._category

    @property
    def central(self) -> hmcu.CentralUnit:
        """Return the central unit."""
        return self._central

    @property
    @abstractmethod
    def full_name(self) -> str:
        """Return the full name of the data_point."""

    @property
    def is_valid(self) -> bool:
        """Return, if the value of the data_point is valid based on the refreshed at datetime."""
        return self._refreshed_at > INIT_DATETIME

    @state_property
    def modified_at(self) -> datetime:
        """Return the last update datetime value."""
        if self._temporary_modified_at > self._modified_at:
            return self._temporary_modified_at
        return self._modified_at

    @state_property
    def refreshed_at(self) -> datetime:
        """Return the last refresh datetime value."""
        if self._temporary_refreshed_at > self._refreshed_at:
            return self._temporary_refreshed_at
        return self._refreshed_at

    @config_property
    @abstractmethod
    def name(self) -> str:
        """Return the name of the data_point."""

    @config_property
    def unique_id(self) -> str:
        """Return the unique_id."""
        return self._unique_id

    @property
    def usage(self) -> DataPointUsage:
        """Return the data_point usage."""
        return DataPointUsage.DATA_POINT

    @property
    def enabled_default(self) -> bool:
        """Return, if data_point should be enabled based on usage attribute."""
        return self.usage in (
            DataPointUsage.CDP_PRIMARY,
            DataPointUsage.CDP_VISIBLE,
            DataPointUsage.DATA_POINT,
            DataPointUsage.EVENT,
        )

    @property
    def is_registered(self) -> bool:
        """Return if data_point is registered externally."""
        return self._custom_id is not None

    @property
    def set_path(self) -> str:
        """Return the base set path of the data_point."""
        return self._path_data.set_path

    @property
    def state_path(self) -> str:
        """Return the base state path of the data_point."""
        return self._path_data.state_path

    # @property
    @property
    def service_methods(self) -> Mapping[str, Callable]:
        """Return all service methods."""
        return self._service_methods

    @property
    def service_method_names(self) -> tuple[str, ...]:
        """Return all service methods."""
        return tuple(self._service_methods.keys())

    def register_internal_data_point_updated_callback(self, cb: Callable) -> CALLBACK_TYPE:
        """Register internal data_point updated callback."""
        return self.register_data_point_updated_callback(cb=cb, custom_id=DEFAULT_CUSTOM_ID)

    def register_data_point_updated_callback(self, cb: Callable, custom_id: str) -> CALLBACK_TYPE:
        """Register data_point updated callback."""
        if custom_id != DEFAULT_CUSTOM_ID:
            if self._custom_id is not None and self._custom_id != custom_id:
                raise HaHomematicException(
                    f"REGISTER_data_point_updated_CALLBACK failed: hm_data_point: {self.full_name} is already registered by {self._custom_id}"
                )
            self._custom_id = custom_id

        if callable(cb) and cb not in self._data_point_updated_callbacks:
            self._data_point_updated_callbacks[cb] = custom_id
            return partial(self._unregister_data_point_updated_callback, cb=cb, custom_id=custom_id)
        return None

    def _reset_temporary_timestamps(self) -> None:
        """Reset the temporary timestamps."""
        self._set_temporary_modified_at(now=INIT_DATETIME)
        self._set_temporary_refreshed_at(now=INIT_DATETIME)

    @abstractmethod
    def _get_path_data(self) -> PathData:
        """Return the path data."""

    def _unregister_data_point_updated_callback(self, cb: Callable, custom_id: str) -> None:
        """Unregister data_point updated callback."""
        if cb in self._data_point_updated_callbacks:
            del self._data_point_updated_callbacks[cb]
        if self.custom_id == custom_id:
            self._custom_id = None

    def register_device_removed_callback(self, cb: Callable) -> CALLBACK_TYPE:
        """Register the device removed callback."""
        if callable(cb) and cb not in self._device_removed_callbacks:
            self._device_removed_callbacks.append(cb)
            return partial(self._unregister_device_removed_callback, cb=cb)
        return None

    def _unregister_device_removed_callback(self, cb: Callable) -> None:
        """Unregister the device removed callback."""
        if cb in self._device_removed_callbacks:
            self._device_removed_callbacks.remove(cb)

    @loop_check
    def fire_data_point_updated_callback(self, *args: Any, **kwargs: Any) -> None:
        """Do what is needed when the value of the data_point has been updated/refreshed."""
        for callback_handler in self._data_point_updated_callbacks:
            try:
                kwargs[KWARGS_ARG_DATA_POINT] = self
                callback_handler(*args, **kwargs)
            except Exception as ex:
                _LOGGER.warning("FIRE_DATA_POINT_UPDATED_EVENT failed: %s", reduce_args(args=ex.args))

    @loop_check
    def fire_device_removed_callback(self, *args: Any) -> None:
        """Do what is needed when the data_point has been removed."""
        for callback_handler in self._device_removed_callbacks:
            try:
                callback_handler(*args)
            except Exception as ex:
                _LOGGER.warning("FIRE_DEVICE_REMOVED_EVENT failed: %s", reduce_args(args=ex.args))

    def _set_modified_at(self, now: datetime = datetime.now()) -> None:
        """Set modified_at to current datetime."""
        self._modified_at = now
        self._set_refreshed_at(now=now)

    def _set_refreshed_at(self, now: datetime = datetime.now()) -> None:
        """Set refreshed_at to current datetime."""
        self._refreshed_at = now

    def _set_temporary_modified_at(self, now: datetime = datetime.now()) -> None:
        """Set temporary_modified_at to current datetime."""
        self._temporary_modified_at = now
        self._set_temporary_refreshed_at(now=now)

    def _set_temporary_refreshed_at(self, now: datetime = datetime.now()) -> None:
        """Set temporary_refreshed_at to current datetime."""
        self._temporary_refreshed_at = now

    def __str__(self) -> str:
        """Provide some useful information."""
        return f"path: {self.state_path}, name: {self.full_name}"


class BaseDataPoint(CallbackDataPoint, PayloadMixin):
    """Base class for regular data point."""

    def __init__(
        self,
        channel: hmd.Channel,
        unique_id: str,
        is_in_multiple_channels: bool,
    ) -> None:
        """Initialize the data_point."""
        PayloadMixin.__init__(self)
        self._channel: Final[hmd.Channel] = channel
        self._device: Final[hmd.Device] = channel.device
        super().__init__(central=channel.central, unique_id=unique_id)
        self._is_in_multiple_channels: Final = is_in_multiple_channels
        self._client: Final[hmcl.Client] = channel.device.client
        self._forced_usage: DataPointUsage | None = None
        self._data_point_name_data: Final = self._get_data_point_name()

    @state_property
    def available(self) -> bool:
        """Return the availability of the device."""
        return self._device.available

    @property
    def channel(self) -> hmd.Channel:
        """Return the channel the data_point."""
        return self._channel

    @property
    def device(self) -> hmd.Device:
        """Return the device of the data_point."""
        return self._device

    @property
    def full_name(self) -> str:
        """Return the full name of the data_point."""
        return self._data_point_name_data.full_name

    @property
    def function(self) -> str | None:
        """Return the function."""
        return self._channel.function

    @property
    def is_in_multiple_channels(self) -> bool:
        """Return the parameter/CE is also in multiple channels."""
        return self._is_in_multiple_channels

    @config_property
    def name(self) -> str:
        """Return the name of the data_point."""
        return self._data_point_name_data.name

    @property
    def name_data(self) -> DataPointNameData:
        """Return the data_point name data of the data_point."""
        return self._data_point_name_data

    @property
    def room(self) -> str | None:
        """Return the room, if only one exists."""
        return self._channel.room

    @property
    def rooms(self) -> set[str]:
        """Return the rooms assigned to a data_point."""
        return self._channel.rooms

    @property
    def usage(self) -> DataPointUsage:
        """Return the data_point usage."""
        return self._get_data_point_usage()

    def force_usage(self, forced_usage: DataPointUsage) -> None:
        """Set the data_point usage."""
        self._forced_usage = forced_usage

    @abstractmethod
    async def load_data_point_value(self, call_source: CallSource, direct_call: bool = False) -> None:
        """Init the data_point data."""

    @abstractmethod
    def _get_data_point_name(self) -> DataPointNameData:
        """Generate the name for the data_point."""

    @abstractmethod
    def _get_data_point_usage(self) -> DataPointUsage:
        """Generate the usage for the data_point."""


class BaseParameterDataPoint[
    ParameterT: GenericParameterType,
    InputParameterT: GenericParameterType,
](BaseDataPoint):
    """Base class for stateless data point."""

    _unique_id_prefix: str = ""

    def __init__(
        self,
        channel: hmd.Channel,
        paramset_key: ParamsetKey,
        parameter: str,
        parameter_data: ParameterData,
    ) -> None:
        """Initialize the data_point."""
        self._paramset_key: Final = paramset_key
        # required for name in BaseDataPoint
        self._parameter: Final[str] = parameter

        super().__init__(
            channel=channel,
            unique_id=generate_unique_id(
                central=channel.central,
                address=channel.address,
                parameter=parameter,
                prefix=self._unique_id_prefix,
            ),
            is_in_multiple_channels=channel.device.central.paramset_descriptions.is_in_multiple_channels(
                channel_address=channel.address, parameter=parameter
            ),
        )
        self._is_un_ignored: Final[bool] = self._central.parameter_visibility.parameter_is_un_ignored(
            model=self._device.model,
            channel_no=self._channel.no,
            paramset_key=self._paramset_key,
            parameter=self._parameter,
            custom_only=True,
        )
        self._current_value: ParameterT = None  # type: ignore[assignment]
        self._previous_value: ParameterT = None  # type: ignore[assignment]
        self._temporary_value: ParameterT = None  # type: ignore[assignment]

        self._state_uncertain: bool = True
        self._is_forced_sensor: bool = False
        self._assign_parameter_data(parameter_data=parameter_data)
        self._service_methods = get_service_calls(obj=self)

    def _assign_parameter_data(self, parameter_data: ParameterData) -> None:
        """Assign parameter data to instance variables."""
        self._type: ParameterType = ParameterType(parameter_data["TYPE"])
        self._values = tuple(parameter_data["VALUE_LIST"]) if parameter_data.get("VALUE_LIST") else None
        self._max: ParameterT = self._convert_value(parameter_data["MAX"])
        self._min: ParameterT = self._convert_value(parameter_data["MIN"])
        self._default: ParameterT = self._convert_value(parameter_data.get("DEFAULT")) or self._min
        flags: int = parameter_data["FLAGS"]
        self._visible: bool = flags & Flag.VISIBLE == Flag.VISIBLE
        self._service: bool = flags & Flag.SERVICE == Flag.SERVICE
        self._operations: int = parameter_data["OPERATIONS"]
        self._special: Mapping[str, Any] | None = parameter_data.get("SPECIAL")
        self._raw_unit: str | None = parameter_data.get("UNIT")
        self._unit: str | None = self._cleanup_unit(raw_unit=self._raw_unit)
        self._multiplier: float = self._get_multiplier(raw_unit=self._raw_unit)

    @property
    def default(self) -> ParameterT:
        """Return default value."""
        return self._default

    @property
    def hmtype(self) -> ParameterType:
        """Return the HomeMatic type."""
        return self._type

    @property
    def is_unit_fixed(self) -> bool:
        """Return if the unit is fixed."""
        return self._raw_unit != self._unit

    @property
    def is_un_ignored(self) -> bool:
        """Return if the parameter is un ignored."""
        return self._is_un_ignored

    @property
    def dpk(self) -> DataPointKey:
        """Return data_point key value."""
        return DataPointKey(
            interface_id=self._device.interface_id,
            channel_address=self._channel.address,
            paramset_key=self._paramset_key,
            parameter=self._parameter,
        )

    @config_property
    def max(self) -> ParameterT:
        """Return max value."""
        return self._max

    @config_property
    def min(self) -> ParameterT:
        """Return min value."""
        return self._min

    @property
    def multiplier(self) -> float:
        """Return multiplier value."""
        return self._multiplier

    @property
    def parameter(self) -> str:
        """Return parameter name."""
        return self._parameter

    @property
    def paramset_key(self) -> ParamsetKey:
        """Return paramset_key name."""
        return self._paramset_key

    @property
    def raw_unit(self) -> str | None:
        """Return raw unit value."""
        return self._raw_unit

    @property
    def is_forced_sensor(self) -> bool:
        """Return, if data_point is forced to read only."""
        return self._is_forced_sensor

    @property
    def is_readable(self) -> bool:
        """Return, if data_point is readable."""
        return bool(self._operations & Operations.READ)

    @property
    def is_writeable(self) -> bool:
        """Return, if data_point is writeable."""
        return False if self._is_forced_sensor else bool(self._operations & Operations.WRITE)

    @property
    def unconfirmed_last_value_send(self) -> ParameterT:
        """Return the unconfirmed value send for the data_point."""
        return cast(
            ParameterT,
            self._client.last_value_send_cache.get_last_value_send(dpk=self.dpk),
        )

    @property
    def previous_value(self) -> ParameterT:
        """Return the previous value of the data_point."""
        return self._previous_value

    @property
    def category(self) -> DataPointCategory:
        """Return, the category of the data_point."""
        return DataPointCategory.SENSOR if self._is_forced_sensor else self._category

    @property
    def state_uncertain(self) -> bool:
        """Return, if the state is uncertain."""
        return self._state_uncertain

    @property
    def _value(self) -> ParameterT:
        """Return the value of the data_point."""
        if self._temporary_refreshed_at > self._refreshed_at:
            return self._temporary_value
        return self._current_value

    @state_property
    def value(self) -> ParameterT:
        """Return the value of the data_point."""
        return self._value

    @property
    def supports_events(self) -> bool:
        """Return, if data_point is supports events."""
        return bool(self._operations & Operations.EVENT)

    @config_property
    def unique_id(self) -> str:
        """Return the unique_id."""
        return f"{self._unique_id}_{DataPointCategory.SENSOR}" if self._is_forced_sensor else self._unique_id

    @config_property
    def unit(self) -> str | None:
        """Return unit value."""
        return self._unit

    @config_property
    def values(self) -> tuple[str, ...] | None:
        """Return the values."""
        return self._values

    @property
    def visible(self) -> bool:
        """Return the if data_point is visible in ccu."""
        return self._visible

    @property
    def _enabled_by_channel_operation_mode(self) -> bool | None:
        """Return, if the data_point/event must be enabled."""
        if self._channel.type_name not in _CONFIGURABLE_CHANNEL:
            return None
        if self._parameter not in KEY_CHANNEL_OPERATION_MODE_VISIBILITY:
            return None
        if (cop := self._channel.operation_mode) is None:
            return None
        return cop in KEY_CHANNEL_OPERATION_MODE_VISIBILITY[self._parameter]

    def _get_path_data(self) -> PathData:
        """Return the path data of the data_point."""
        return DataPointPathData(
            interface=self._device.client.interface,
            address=self._device.address,
            channel_no=self._channel.no,
            kind=self._parameter,
        )

    def force_to_sensor(self) -> None:
        """Change the category of the data_point."""
        if self.category == DataPointCategory.SENSOR:
            _LOGGER.debug(
                "Category for %s is already %s. Doing nothing",
                self.full_name,
                DataPointCategory.SENSOR,
            )
            return
        if self.category not in (
            DataPointCategory.NUMBER,
            DataPointCategory.SELECT,
            DataPointCategory.TEXT,
        ):
            _LOGGER.debug(
                "Category %s for %s cannot be changed to %s",
                self.category,
                self.full_name,
                DataPointCategory.SENSOR,
            )
        _LOGGER.debug(
            "Changing the category of %s to %s (read-only)",
            self.full_name,
            DataPointCategory.SENSOR,
        )
        self._is_forced_sensor = True

    def _cleanup_unit(self, raw_unit: str | None) -> str | None:
        """Replace given unit."""
        if new_unit := _FIX_UNIT_BY_PARAM.get(self._parameter):
            return new_unit
        if not raw_unit:
            return None
        for check, fix in _FIX_UNIT_REPLACE.items():
            if check in raw_unit:
                return fix
        return raw_unit

    def _get_multiplier(self, raw_unit: str | None) -> float:
        """Replace given unit."""
        if not raw_unit:
            return DEFAULT_MULTIPLIER
        if multiplier := _MULTIPLIER_UNIT.get(raw_unit):
            return multiplier
        return DEFAULT_MULTIPLIER

    @abstractmethod
    async def event(self, value: Any) -> None:
        """Handle event for which this handler has subscribed."""

    async def load_data_point_value(self, call_source: CallSource, direct_call: bool = False) -> None:
        """Init the data_point data."""
        if direct_call is False and hms.changed_within_seconds(last_change=self._refreshed_at):
            return

        # Check, if data_point is readable
        if not self.is_readable:
            return

        self.write_value(
            value=await self._device.value_cache.get_value(
                channel_address=self._channel.address,
                paramset_key=self._paramset_key,
                parameter=self._parameter,
                call_source=call_source,
                direct_call=direct_call,
            )
        )

    def write_value(self, value: Any) -> tuple[ParameterT, ParameterT]:
        """Update value of the data_point."""
        self._reset_temporary_value()

        old_value = self._current_value
        if value == NO_CACHE_ENTRY:
            if self.refreshed_at != INIT_DATETIME:
                self._state_uncertain = True
                self.fire_data_point_updated_callback()
            return (old_value, None)  # type: ignore[return-value]

        new_value = self._convert_value(value)
        if old_value == new_value:
            self._set_refreshed_at()
        else:
            self._set_modified_at()
            self._previous_value = old_value
            self._current_value = new_value
        self._state_uncertain = False
        self.fire_data_point_updated_callback()
        return (old_value, new_value)

    def write_temporary_value(self, value: Any) -> None:
        """Update the temporary value of the data_point."""
        self._reset_temporary_value()

        temp_value = self._convert_value(value)
        if self._value == temp_value:
            self._set_temporary_refreshed_at()
        else:
            self._set_temporary_modified_at()
            self._temporary_value = temp_value
            self._state_uncertain = True
        self.fire_data_point_updated_callback()

    def update_parameter_data(self) -> None:
        """Update parameter data."""
        if parameter_data := self._central.paramset_descriptions.get_parameter_data(
            interface_id=self._device.interface_id,
            channel_address=self._channel.address,
            paramset_key=self._paramset_key,
            parameter=self._parameter,
        ):
            self._assign_parameter_data(parameter_data=parameter_data)

    def _convert_value(self, value: Any) -> ParameterT:
        """Convert to value to ParameterT."""
        if value is None:
            return None  # type: ignore[return-value]
        try:
            if (
                self._type == ParameterType.BOOL
                and self._values is not None
                and value is not None
                and isinstance(value, str)
            ):
                return convert_value(  # type: ignore[no-any-return]
                    value=self._values.index(value),
                    target_type=self._type,
                    value_list=self.values,
                )
            return convert_value(  # type: ignore[no-any-return]
                value=value, target_type=self._type, value_list=self.values
            )
        except (ValueError, TypeError):  # pragma: no cover
            _LOGGER.debug(
                "CONVERT_VALUE: conversion failed for %s, %s, %s, value: [%s]",
                self._device.interface_id,
                self._channel.address,
                self._parameter,
                value,
            )
            return None  # type: ignore[return-value]

    def _reset_temporary_value(self) -> None:
        """Reset the temp storage."""
        self._temporary_value = None  # type: ignore[assignment]
        self._reset_temporary_timestamps()

    def get_event_data(self, value: Any = None) -> dict[EventKey, Any]:
        """Get the event_data."""
        event_data = {
            EventKey.ADDRESS: self._device.address,
            EventKey.CHANNEL_NO: self._channel.no,
            EventKey.MODEL: self._device.model,
            EventKey.INTERFACE_ID: self._device.interface_id,
            EventKey.PARAMETER: self._parameter,
        }
        if value is not None:
            event_data[EventKey.VALUE] = value
        return cast(dict[EventKey, Any], EVENT_DATA_SCHEMA(event_data))


class CallParameterCollector:
    """Create a Paramset based on given generic data point."""

    def __init__(self, client: hmcl.Client) -> None:
        """Init the generator."""
        self._client: Final = client
        self._central: Final = client.central
        # {"VALUES": {50: {"00021BE9957782:3": {"STATE3": True}}}}
        self._paramsets: Final[dict[ParamsetKey, dict[int, dict[str, dict[str, Any]]]]] = {}

    def add_data_point(
        self,
        data_point: BaseParameterDataPoint,
        value: Any,
        collector_order: int,
    ) -> None:
        """Add a generic data_point."""
        if data_point.paramset_key not in self._paramsets:
            self._paramsets[data_point.paramset_key] = {}
        if collector_order not in self._paramsets[data_point.paramset_key]:
            self._paramsets[data_point.paramset_key][collector_order] = {}
        if data_point.channel.address not in self._paramsets[data_point.paramset_key][collector_order]:
            self._paramsets[data_point.paramset_key][collector_order][data_point.channel.address] = {}
        self._paramsets[data_point.paramset_key][collector_order][data_point.channel.address][data_point.parameter] = (
            value
        )

    async def send_data(self, wait_for_callback: int | None) -> set[DP_KEY_VALUE]:
        """Send data to backend."""
        dpk_values: set[DP_KEY_VALUE] = set()
        for paramset_key, paramsets in self._paramsets.items():
            for paramset_no in dict(sorted(paramsets.items())).values():
                for channel_address, paramset in paramset_no.items():
                    if len(paramset.values()) == 1:
                        for parameter, value in paramset.items():
                            dpk_values.update(
                                await self._client.set_value(
                                    channel_address=channel_address,
                                    paramset_key=paramset_key,
                                    parameter=parameter,
                                    value=value,
                                    wait_for_callback=wait_for_callback,
                                )
                            )
                    else:
                        dpk_values.update(
                            await self._client.put_paramset(
                                channel_address=channel_address,
                                paramset_key=paramset_key,
                                values=paramset,
                                wait_for_callback=wait_for_callback,
                            )
                        )
        return dpk_values


def bind_collector(
    wait_for_callback: int | None = WAIT_FOR_CALLBACK,
    enabled: bool = True,
    log_level: int = logging.ERROR,
) -> Callable:
    """
    Decorate function to automatically add collector if not set.

    Additionally, thrown exceptions are logged.
    """

    def bind_decorator[_CallableT: Callable[..., Any]](func: _CallableT) -> _CallableT:
        """Decorate function to automatically add collector if not set."""
        argument_index = getfullargspec(func).args.index(_COLLECTOR_ARGUMENT_NAME)

        @wraps(func)
        async def bind_wrapper(*args: Any, **kwargs: Any) -> Any:
            """Wrap method to add collector."""
            token: Token | None = None
            if not IN_SERVICE_VAR.get():
                token = IN_SERVICE_VAR.set(True)
            try:
                if not enabled:
                    return_value = await func(*args, **kwargs)
                    if token:
                        IN_SERVICE_VAR.reset(token)
                    return return_value
                try:
                    collector_exists = args[argument_index] is not None
                except IndexError:
                    collector_exists = kwargs.get(_COLLECTOR_ARGUMENT_NAME) is not None

                if collector_exists:
                    return_value = await func(*args, **kwargs)
                    if token:
                        IN_SERVICE_VAR.reset(token)
                    return return_value
                collector = CallParameterCollector(client=args[0].channel.device.client)
                kwargs[_COLLECTOR_ARGUMENT_NAME] = collector
                return_value = await func(*args, **kwargs)
                await collector.send_data(wait_for_callback=wait_for_callback)
            except BaseHomematicException as bhe:
                if token:
                    IN_SERVICE_VAR.reset(token)
                in_service = IN_SERVICE_VAR.get()
                if not in_service and log_level > logging.NOTSET:
                    logging.getLogger(args[0].__module__).log(level=log_level, msg=reduce_args(args=bhe.args))
            else:
                if token:
                    IN_SERVICE_VAR.reset(token)
                return return_value
            return None

        setattr(bind_wrapper, "ha_service", True)
        return bind_wrapper  # type: ignore[return-value]

    return bind_decorator
