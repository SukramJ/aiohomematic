# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Core data point model for AioHomematic.

This module defines the abstract base classes and concrete building blocks for
representing Homematic parameters as data points, handling their lifecycle,
I/O, and event propagation.

Highlights:
- CallbackDataPoint: Base for objects that expose callbacks and timestamps
  (modified/refreshed) and manage registration of update and removal listeners.
- BaseDataPoint/ BaseParameterDataPoint: Concrete foundations for channel-bound
  data points, including type/flag handling, unit and multiplier normalization,
  value conversion, temporary write buffering, and path/name metadata.
- CallParameterCollector: Helper to batch multiple set/put operations and wait
  for callbacks, optimizing command dispatch.
- bind_collector: Decorator to bind a collector to service methods conveniently.

The classes here are used by generic, custom, calculated, and hub data point
implementations to provide a uniform API for reading, writing, and observing
parameter values across all supported devices.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Callable, Mapping
from contextvars import Token
from datetime import datetime, timedelta
from functools import partial, wraps
from inspect import getfullargspec
import logging
from typing import Any, Final, TypeAlias, TypeVar, cast, overload

import voluptuous as vol

from aiohomematic import central as hmcu, client as hmcl, i18n, support as hms, validator as val
from aiohomematic.async_support import loop_check
from aiohomematic.const import (
    DEFAULT_MULTIPLIER,
    DP_KEY_VALUE,
    INIT_DATETIME,
    KEY_CHANNEL_OPERATION_MODE_VISIBILITY,
    KWARGS_ARG_CUSTOM_ID,
    KWARGS_ARG_DATA_POINT,
    NO_CACHE_ENTRY,
    WAIT_FOR_CALLBACK,
    CallSource,
    DataPointCategory,
    DataPointKey,
    DataPointUsage,
    EventKey,
    Flag,
    InternalCustomID,
    Operations,
    Parameter,
    ParameterData,
    ParameterType,
    ParamsetKey,
    ProductGroup,
    check_ignore_parameter_on_initial_load,
)
from aiohomematic.context import IN_SERVICE_VAR
from aiohomematic.decorators import get_service_calls
from aiohomematic.exceptions import AioHomematicException, BaseHomematicException
from aiohomematic.model import device as hmd
from aiohomematic.model.support import DataPointNameData, DataPointPathData, PathData, convert_value, generate_unique_id
from aiohomematic.property_decorators import config_property, hm_property, state_property
from aiohomematic.support import LogContextMixin, PayloadMixin, extract_exc_args, log_boundary_error
from aiohomematic.type_aliases import (
    CallableAny,
    DataPointUpdatedCallback,
    DeviceRemovedCallback,
    ParamType,
    ServiceMethodMap,
    UnregisterCallback,
)

__all__ = [
    "BaseDataPoint",
    "BaseParameterDataPoint",
    "CallParameterCollector",
    "CallbackDataPoint",
    "bind_collector",
]
# Type variable used for decorator typing
CallableT = TypeVar("CallableT", bound=CallableAny)

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


class CallbackDataPoint(ABC, LogContextMixin):
    """Base class for callback data point."""

    __slots__ = (
        "_cached_enabled_default",
        "_cached_service_methods",
        "_cached_service_method_names",
        "_central",
        "_custom_id",
        "_data_point_updated_callbacks",
        "_device_removed_callbacks",
        "_emitted_event_at",
        "_modified_at",
        "_path_data",
        "_refreshed_at",
        "_signature",
        "_temporary_modified_at",
        "_temporary_refreshed_at",
        "_unique_id",
    )

    _category = DataPointCategory.UNDEFINED

    def __init__(self, *, central: hmcu.CentralUnit, unique_id: str) -> None:
        """Init the callback data_point."""
        self._central: Final = central
        self._unique_id: Final = unique_id
        self._data_point_updated_callbacks: dict[str, set[DataPointUpdatedCallback]] = defaultdict(set)
        self._device_removed_callbacks: list[DeviceRemovedCallback] = []
        self._custom_id: str | None = None
        self._path_data = self._get_path_data()
        self._emitted_event_at: datetime = INIT_DATETIME
        self._modified_at: datetime = INIT_DATETIME
        self._refreshed_at: datetime = INIT_DATETIME
        self._signature: Final = self._get_signature()
        self._temporary_modified_at: datetime = INIT_DATETIME
        self._temporary_refreshed_at: datetime = INIT_DATETIME

    def __str__(self) -> str:
        """Provide some useful information."""
        return f"path: {self.state_path}, name: {self.full_name}"

    @classmethod
    def default_category(cls) -> DataPointCategory:
        """Return, the default category of the data_point."""
        return cls._category

    @property
    def _should_emit_data_point_updated_callback(self) -> bool:
        """Check if a data point has been updated or refreshed."""
        return True

    @property
    def category(self) -> DataPointCategory:
        """Return, the category of the data point."""
        return self._category

    @property
    def central(self) -> hmcu.CentralUnit:
        """Return the central unit."""
        return self._central

    @property
    def custom_id(self) -> str | None:
        """Return the custom id."""
        return self._custom_id

    @property
    def emitted_event_at(self) -> datetime:
        """Return the data point updated emitted an event at."""
        return self._emitted_event_at

    @property
    @abstractmethod
    def full_name(self) -> str:
        """Return the full name of the data_point."""

    @property
    def is_registered(self) -> bool:
        """Return if data_point is registered externally."""
        return self._custom_id is not None

    @property
    def is_valid(self) -> bool:
        """Return, if the value of the data_point is valid based on the refreshed at datetime."""
        return self._refreshed_at > INIT_DATETIME

    @property
    def set_path(self) -> str:
        """Return the base set path of the data_point."""
        return self._path_data.set_path

    @property
    def signature(self) -> str:
        """Return the data_point signature."""
        return self._signature

    @property
    def state_path(self) -> str:
        """Return the base state path of the data_point."""
        return self._path_data.state_path

    @property
    def usage(self) -> DataPointUsage:
        """Return the data_point usage."""
        return DataPointUsage.DATA_POINT

    @config_property
    @abstractmethod
    def name(self) -> str:
        """Return the name of the data_point."""

    @config_property
    def unique_id(self) -> str:
        """Return the unique_id."""
        return self._unique_id

    @state_property
    def additional_information(self) -> dict[str, Any]:
        """Return additional information about the entity."""
        return {}

    @state_property
    @abstractmethod
    def available(self) -> bool:
        """Return the availability of the device."""

    @state_property
    def emitted_event_recently(self) -> bool:
        """Return the data point emitted an event within 500 milliseconds."""
        if self._emitted_event_at == INIT_DATETIME:
            return False
        return (datetime.now() - self._emitted_event_at).total_seconds() < 0.5

    @state_property
    def modified_at(self) -> datetime:
        """Return the last update datetime value."""
        if self._temporary_modified_at > self._modified_at:
            return self._temporary_modified_at
        return self._modified_at

    @state_property
    def modified_recently(self) -> bool:
        """Return the data point modified within 500 milliseconds."""
        if self._modified_at == INIT_DATETIME:
            return False
        return (datetime.now() - self._modified_at).total_seconds() < 0.5

    @state_property
    def refreshed_at(self) -> datetime:
        """Return the last refresh datetime value."""
        if self._temporary_refreshed_at > self._refreshed_at:
            return self._temporary_refreshed_at
        return self._refreshed_at

    @state_property
    def refreshed_recently(self) -> bool:
        """Return the data point refreshed within 500 milliseconds."""
        if self._refreshed_at == INIT_DATETIME:
            return False
        return (datetime.now() - self._refreshed_at).total_seconds() < 0.5

    @hm_property(cached=True)
    def enabled_default(self) -> bool:
        """Return, if data_point should be enabled based on usage attribute."""
        return self.usage in (
            DataPointUsage.CDP_PRIMARY,
            DataPointUsage.CDP_VISIBLE,
            DataPointUsage.DATA_POINT,
            DataPointUsage.EVENT,
        )

    @hm_property(cached=True)
    def service_method_names(self) -> tuple[str, ...]:
        """Return all service methods."""
        return tuple(self.service_methods.keys())

    @hm_property(cached=True)
    def service_methods(self) -> ServiceMethodMap:
        """Return all service methods."""
        return get_service_calls(obj=self)

    @loop_check
    def emit_data_point_updated_event(self, **kwargs: Any) -> None:
        """Do what is needed when the value of the data_point has been updated/refreshed."""
        if not self._should_emit_data_point_updated_callback:
            return
        self._emitted_event_at = datetime.now()
        for custom_id, callback_handlers in self._data_point_updated_callbacks.items():
            for callback_handler in callback_handlers:
                try:
                    # Add the data_point reference once to kwargs to avoid per-callback writes.
                    kwargs[KWARGS_ARG_DATA_POINT] = self
                    kwargs[KWARGS_ARG_CUSTOM_ID] = custom_id
                    callback_handler(**kwargs)
                except Exception as exc:
                    _LOGGER.error(  # i18n-log: ignore
                        "EMIT_DATA_POINT_UPDATED_EVENT failed: %s", extract_exc_args(exc=exc)
                    )

    @loop_check
    def emit_device_removed_event(self) -> None:
        """Do what is needed when the data_point has been removed."""
        for callback_handler in self._device_removed_callbacks:
            try:
                callback_handler()
            except Exception as exc:
                _LOGGER.error("EMIT_DEVICE_REMOVED_EVENT failed: %s", extract_exc_args(exc=exc))  # i18n-log: ignore

    async def finalize_init(self) -> None:
        """Finalize the data point init action after model setup."""

    def register_data_point_updated_callback(
        self, *, cb: DataPointUpdatedCallback, custom_id: str
    ) -> UnregisterCallback:
        """Register data_point updated callback."""
        if custom_id not in InternalCustomID:
            if self._custom_id is not None and self._custom_id != custom_id:
                raise AioHomematicException(
                    i18n.tr(
                        "exception.model.data_point.register_callback.already_registered",
                        full_name=self.full_name,
                        custom_id=self._custom_id,
                    )
                )
            self._custom_id = custom_id

        if callable(cb) and cb not in self._data_point_updated_callbacks[custom_id]:
            self._data_point_updated_callbacks[custom_id].add(cb)
            return partial(self._unregister_data_point_updated_callback, cb=cb, custom_id=custom_id)
        return None

    def register_device_removed_callback(self, *, cb: DeviceRemovedCallback) -> UnregisterCallback:
        """Register the device removed callback."""
        if callable(cb) and cb not in self._device_removed_callbacks:
            self._device_removed_callbacks.append(cb)
            return partial(self._unregister_device_removed_callback, cb=cb)
        return None

    def register_internal_data_point_updated_callback(self, *, cb: DataPointUpdatedCallback) -> UnregisterCallback:
        """Register internal data_point updated callback."""
        return self.register_data_point_updated_callback(cb=cb, custom_id=InternalCustomID.DEFAULT)

    @abstractmethod
    def _get_path_data(self) -> PathData:
        """Return the path data."""

    @abstractmethod
    def _get_signature(self) -> str:
        """Return the signature of the data_point."""

    def _reset_temporary_timestamps(self) -> None:
        """Reset the temporary timestamps."""
        self._set_temporary_modified_at(modified_at=INIT_DATETIME)
        self._set_temporary_refreshed_at(refreshed_at=INIT_DATETIME)

    def _set_modified_at(self, *, modified_at: datetime) -> None:
        """Set modified_at to current datetime."""
        self._modified_at = modified_at
        self._set_refreshed_at(refreshed_at=modified_at)

    def _set_refreshed_at(self, *, refreshed_at: datetime) -> None:
        """Set refreshed_at to current datetime."""
        self._refreshed_at = refreshed_at

    def _set_temporary_modified_at(self, *, modified_at: datetime) -> None:
        """Set temporary_modified_at to current datetime."""
        self._temporary_modified_at = modified_at
        self._set_temporary_refreshed_at(refreshed_at=modified_at)

    def _set_temporary_refreshed_at(self, *, refreshed_at: datetime) -> None:
        """Set temporary_refreshed_at to current datetime."""
        self._temporary_refreshed_at = refreshed_at

    def _unregister_data_point_updated_callback(self, *, cb: DataPointUpdatedCallback, custom_id: str) -> None:
        """Unregister data_point updated callback."""
        if cb in self._data_point_updated_callbacks[custom_id]:
            self._data_point_updated_callbacks[custom_id].remove(cb)
        if self.custom_id == custom_id:
            self._custom_id = None

    def _unregister_device_removed_callback(self, *, cb: DeviceRemovedCallback) -> None:
        """Unregister the device removed callback."""
        if cb in self._device_removed_callbacks:
            self._device_removed_callbacks.remove(cb)


class BaseDataPoint(CallbackDataPoint, PayloadMixin):
    """Base class for regular data point."""

    __slots__ = (
        "_cached_dpk",
        "_cached_requires_polling",
        "_channel",
        "_client",
        "_data_point_name_data",
        "_device",
        "_forced_usage",
        "_is_in_multiple_channels",
        "_timer_on_time",
        "_timer_on_time_end",
    )

    _ignore_multiple_channels_for_name: bool = False

    def __init__(
        self,
        *,
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
        self._timer_on_time: float | None = None
        self._timer_on_time_end: datetime = INIT_DATETIME

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
    def timer_on_time(self) -> float | None:
        """Return the on_time."""
        return self._timer_on_time

    @property
    def timer_on_time_running(self) -> bool:
        """Return if on_time is running."""
        return datetime.now() <= self._timer_on_time_end

    @property
    def usage(self) -> DataPointUsage:
        """Return the data_point usage."""
        return self._get_data_point_usage()

    @config_property
    def name(self) -> str:
        """Return the name of the data_point."""
        return self._data_point_name_data.name

    @state_property
    def available(self) -> bool:
        """Return the availability of the device."""
        return self._device.available

    @hm_property(log_context=True)
    def channel(self) -> hmd.Channel:
        """Return the channel the data_point."""
        return self._channel

    def force_usage(self, *, forced_usage: DataPointUsage) -> None:
        """Set the data_point usage."""
        self._forced_usage = forced_usage

    def get_and_start_timer(self) -> float | None:
        """Return the on_time and set the end time."""
        if self.timer_on_time_running and self._timer_on_time is not None and self._timer_on_time <= 0:
            self.reset_timer_on_time()
            return -1
        if self._timer_on_time is None:
            self.reset_timer_on_time()
            return None
        on_time = self._timer_on_time
        self._timer_on_time = None
        self._timer_on_time_end = datetime.now() + timedelta(seconds=on_time)
        return on_time

    @abstractmethod
    async def load_data_point_value(self, *, call_source: CallSource, direct_call: bool = False) -> None:
        """Init the data_point data."""

    async def on_config_changed(self) -> None:
        """Do what is needed on device config change."""

    def reset_timer_on_time(self) -> None:
        """Set the on_time."""
        self._timer_on_time = None
        self._timer_on_time_end = INIT_DATETIME

    def set_timer_on_time(self, *, on_time: float) -> None:
        """Set the on_time."""
        self._timer_on_time = on_time
        self._timer_on_time_end = INIT_DATETIME

    @abstractmethod
    def _get_data_point_name(self) -> DataPointNameData:
        """Generate the name for the data_point."""

    @abstractmethod
    def _get_data_point_usage(self) -> DataPointUsage:
        """Generate the usage for the data_point."""


class BaseParameterDataPoint[
    ParameterT: ParamType,
    InputParameterT: ParamType,
](BaseDataPoint):
    """Base class for stateless data point."""

    __slots__ = (
        "_cached__enabled_by_channel_operation_mode",
        "_current_value",
        "_default",
        "_ignore_on_initial_load",
        "_is_forced_sensor",
        "_is_un_ignored",
        "_max",
        "_min",
        "_multiplier",
        "_operations",
        "_parameter",
        "_paramset_key",
        "_previous_value",
        "_raw_unit",
        "_service",
        "_special",
        "_state_uncertain",
        "_temporary_value",
        "_type",
        "_unit",
        "_values",
        "_visible",
    )

    def __init__(
        self,
        *,
        channel: hmd.Channel,
        paramset_key: ParamsetKey,
        parameter: str,
        parameter_data: ParameterData,
        unique_id_prefix: str = "",
    ) -> None:
        """Initialize the data_point."""
        self._paramset_key: Final = paramset_key
        # required for name in BaseDataPoint
        self._parameter: Final[str] = parameter
        self._ignore_on_initial_load: Final[bool] = check_ignore_parameter_on_initial_load(parameter=parameter)

        super().__init__(
            channel=channel,
            unique_id=generate_unique_id(
                central=channel.central,
                address=channel.address,
                parameter=parameter,
                prefix=unique_id_prefix,
            ),
            is_in_multiple_channels=channel.device.central.paramset_descriptions.is_in_multiple_channels(
                channel_address=channel.address, parameter=parameter
            ),
        )
        self._is_un_ignored: Final[bool] = self._central.parameter_visibility.parameter_is_un_ignored(
            channel=channel,
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

    @property
    def _value(self) -> ParameterT:
        """Return the value of the data_point."""
        return self._temporary_value if self._temporary_refreshed_at > self._refreshed_at else self._current_value

    @property
    def category(self) -> DataPointCategory:
        """Return, the category of the data_point."""
        return DataPointCategory.SENSOR if self._is_forced_sensor else self._category

    @property
    def default(self) -> ParameterT:
        """Return default value."""
        return self._default

    @property
    def hmtype(self) -> ParameterType:
        """Return the Homematic type."""
        return self._type

    @property
    def ignore_on_initial_load(self) -> bool:
        """Return if parameter should be ignored on initial load."""
        return self._ignore_on_initial_load

    @property
    def is_forced_sensor(self) -> bool:
        """Return, if data_point is forced to read only."""
        return self._is_forced_sensor

    @property
    def is_readable(self) -> bool:
        """Return, if data_point is readable."""
        return bool(self._operations & Operations.READ)

    @property
    def is_un_ignored(self) -> bool:
        """Return if the parameter is un ignored."""
        return self._is_un_ignored

    @property
    def is_unit_fixed(self) -> bool:
        """Return if the unit is fixed."""
        return self._raw_unit != self._unit

    @property
    def is_writeable(self) -> bool:
        """Return, if data_point is writeable."""
        return False if self._is_forced_sensor else bool(self._operations & Operations.WRITE)

    @property
    def multiplier(self) -> float:
        """Return multiplier value."""
        return self._multiplier

    @property
    def paramset_key(self) -> ParamsetKey:
        """Return paramset_key name."""
        return self._paramset_key

    @property
    def previous_value(self) -> ParameterT:
        """Return the previous value of the data_point."""
        return self._previous_value

    @property
    def raw_unit(self) -> str | None:
        """Return raw unit value."""
        return self._raw_unit

    @property
    def service(self) -> bool:
        """Return the if data_point is relevant for service messages in the backend."""
        return self._service

    @property
    def state_uncertain(self) -> bool:
        """Return, if the state is uncertain."""
        return self._state_uncertain

    @property
    def supports_events(self) -> bool:
        """Return, if data_point is supports events."""
        return bool(self._operations & Operations.EVENT)

    @property
    def unconfirmed_last_value_send(self) -> ParameterT:
        """Return the unconfirmed value send for the data_point."""
        return cast(
            ParameterT,
            self._client.last_value_send_cache.get_last_value_send(dpk=self.dpk),
        )

    @property
    def visible(self) -> bool:
        """Return the if data_point is visible in the backend."""
        return self._visible

    @config_property
    def max(self) -> ParameterT:
        """Return max value."""
        return self._max

    @config_property
    def min(self) -> ParameterT:
        """Return min value."""
        return self._min

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

    @state_property
    def value(self) -> ParameterT:
        """Return the value of the data_point."""
        return self._value

    @hm_property(cached=True)
    def _enabled_by_channel_operation_mode(self) -> bool | None:
        """Return, if the data_point/event must be enabled."""
        if self._channel.type_name not in _CONFIGURABLE_CHANNEL:
            return None
        if self._parameter not in KEY_CHANNEL_OPERATION_MODE_VISIBILITY:
            return None
        if (cop := self._channel.operation_mode) is None:
            return None
        return cop in KEY_CHANNEL_OPERATION_MODE_VISIBILITY[self._parameter]

    @hm_property(cached=True)
    def dpk(self) -> DataPointKey:
        """Return data_point key value."""
        return DataPointKey(
            interface_id=self._device.interface_id,
            channel_address=self._channel.address,
            paramset_key=self._paramset_key,
            parameter=self._parameter,
        )

    @hm_property(log_context=True)
    def parameter(self) -> str:
        """Return parameter name."""
        return self._parameter

    @hm_property(cached=True)
    def requires_polling(self) -> bool:
        """Return whether the data_point requires polling."""
        return not self._channel.device.client.supports_push_updates or (
            self._channel.device.product_group in (ProductGroup.HM, ProductGroup.HMW)
            and self._paramset_key == ParamsetKey.MASTER
        )

    @abstractmethod
    async def event(self, *, value: Any, received_at: datetime) -> None:
        """Handle event for which this handler has subscribed."""

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

    def get_event_data(self, *, value: Any = None) -> dict[EventKey, Any]:
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

    async def load_data_point_value(self, *, call_source: CallSource, direct_call: bool = False) -> None:
        """Init the data_point data."""
        if (self._ignore_on_initial_load or self._channel.device.ignore_on_initial_load) and call_source in (
            CallSource.HM_INIT,
            CallSource.HA_INIT,
        ):
            return

        if direct_call is False and hms.changed_within_seconds(last_change=self._refreshed_at):
            return

        # Check, if data_point is readable
        if not self.is_readable:
            return

        self.write_value(
            value=await self._device.value_cache.get_value(
                dpk=self.dpk,
                call_source=call_source,
                direct_call=direct_call,
            ),
            write_at=datetime.now(),
        )

    async def on_config_changed(self) -> None:
        """Do what is needed on device config change."""
        await super().on_config_changed()

        # update parameter_data
        self.update_parameter_data()
        # reload master data
        if self.is_readable and self._paramset_key == ParamsetKey.MASTER:
            await self.load_data_point_value(call_source=CallSource.MANUAL_OR_SCHEDULED, direct_call=True)

    def update_parameter_data(self) -> None:
        """Update parameter data."""
        if parameter_data := self._central.paramset_descriptions.get_parameter_data(
            interface_id=self._device.interface_id,
            channel_address=self._channel.address,
            paramset_key=self._paramset_key,
            parameter=self._parameter,
        ):
            self._assign_parameter_data(parameter_data=parameter_data)

    def write_temporary_value(self, *, value: Any, write_at: datetime) -> None:
        """Update the temporary value of the data_point."""
        self._reset_temporary_value()

        temp_value = self._convert_value(value=value)
        if self._value == temp_value:
            self._set_temporary_refreshed_at(refreshed_at=write_at)
        else:
            self._set_temporary_modified_at(modified_at=write_at)
            self._temporary_value = temp_value
            self._state_uncertain = True
        self.emit_data_point_updated_event()

    def write_value(self, *, value: Any, write_at: datetime) -> tuple[ParameterT, ParameterT]:
        """Update value of the data_point."""
        self._reset_temporary_value()

        old_value = self._current_value
        if value == NO_CACHE_ENTRY:
            if self.refreshed_at != INIT_DATETIME:
                self._state_uncertain = True
                self.emit_data_point_updated_event()
            return (old_value, None)  # type: ignore[return-value]

        new_value = self._convert_value(value=value)
        if old_value == new_value:
            self._set_refreshed_at(refreshed_at=write_at)
        else:
            self._set_modified_at(modified_at=write_at)
            self._previous_value = old_value
            self._current_value = new_value
        self._state_uncertain = False
        self.emit_data_point_updated_event()
        return (old_value, new_value)

    def _assign_parameter_data(self, *, parameter_data: ParameterData) -> None:
        """Assign parameter data to instance variables."""
        self._type: ParameterType = ParameterType(parameter_data["TYPE"])
        self._values = tuple(parameter_data["VALUE_LIST"]) if parameter_data.get("VALUE_LIST") else None
        self._max: ParameterT = self._convert_value(value=parameter_data["MAX"])
        self._min: ParameterT = self._convert_value(value=parameter_data["MIN"])
        self._default: ParameterT = self._convert_value(value=parameter_data.get("DEFAULT")) or self._min
        flags: int = parameter_data["FLAGS"]
        self._visible: bool = flags & Flag.VISIBLE == Flag.VISIBLE
        self._service: bool = flags & Flag.SERVICE == Flag.SERVICE
        self._operations: int = parameter_data["OPERATIONS"]
        self._special: Mapping[str, Any] | None = parameter_data.get("SPECIAL")
        self._raw_unit: str | None = parameter_data.get("UNIT")
        self._unit: str | None = self._cleanup_unit(raw_unit=self._raw_unit)
        self._multiplier: float = self._get_multiplier(raw_unit=self._raw_unit)

    def _cleanup_unit(self, *, raw_unit: str | None) -> str | None:
        """Replace given unit."""
        if new_unit := _FIX_UNIT_BY_PARAM.get(self._parameter):
            return new_unit
        if not raw_unit:
            return None
        for check, fix in _FIX_UNIT_REPLACE.items():
            if check in raw_unit:
                return fix
        return raw_unit

    def _convert_value(self, *, value: Any) -> ParameterT:
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
                return cast(
                    ParameterT,
                    convert_value(
                        value=self._values.index(value),
                        target_type=self._type,
                        value_list=self.values,
                    ),
                )
            return cast(ParameterT, convert_value(value=value, target_type=self._type, value_list=self.values))
        except (ValueError, TypeError):  # pragma: no cover
            _LOGGER.debug(
                "CONVERT_VALUE: conversion failed for %s, %s, %s, value: [%s]",
                self._device.interface_id,
                self._channel.address,
                self._parameter,
                value,
            )
            return None  # type: ignore[return-value]

    def _get_multiplier(self, *, raw_unit: str | None) -> float:
        """Replace given unit."""
        if not raw_unit:
            return DEFAULT_MULTIPLIER
        if multiplier := _MULTIPLIER_UNIT.get(raw_unit):
            return multiplier
        return DEFAULT_MULTIPLIER

    def _get_path_data(self) -> PathData:
        """Return the path data of the data_point."""
        return DataPointPathData(
            interface=self._device.client.interface,
            address=self._device.address,
            channel_no=self._channel.no,
            kind=self._parameter,
        )

    def _get_signature(self) -> str:
        """Return the signature of the data_point."""
        return f"{self._category}/{self._channel.device.model}/{self._parameter}"

    def _reset_temporary_value(self) -> None:
        """Reset the temp storage."""
        self._temporary_value = None  # type: ignore[assignment]
        self._reset_temporary_timestamps()


BaseParameterDataPointAny: TypeAlias = BaseParameterDataPoint[Any, Any]


class CallParameterCollector:
    """Create a Paramset based on given generic data point."""

    __slots__ = (
        "_central",
        "_client",
        "_paramsets",
    )

    def __init__(self, *, client: hmcl.Client) -> None:
        """Init the generator."""
        self._client: Final = client
        self._central: Final = client.central
        # {"VALUES": {50: {"00021BE9957782:3": {"STATE3": True}}}}
        self._paramsets: Final[dict[ParamsetKey, dict[int, dict[str, dict[str, Any]]]]] = {}

    def add_data_point(
        self,
        *,
        data_point: BaseParameterDataPointAny,
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

    async def send_data(self, *, wait_for_callback: int | None) -> set[DP_KEY_VALUE]:
        """Send data to the backend."""
        dpk_values: set[DP_KEY_VALUE] = set()
        for paramset_key, paramsets in self._paramsets.items():
            for _, paramset_no in sorted(paramsets.items()):
                for channel_address, paramset in paramset_no.items():
                    if len(paramset) == 1:
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
                                paramset_key_or_link_address=paramset_key,
                                values=paramset,
                                wait_for_callback=wait_for_callback,
                            )
                        )
        return dpk_values


@overload
def bind_collector[CallableBC: CallableAny](
    func: CallableBC,
    *,
    wait_for_callback: int | None = WAIT_FOR_CALLBACK,
    enabled: bool = True,
    log_level: int = logging.ERROR,
) -> CallableBC: ...


@overload
def bind_collector[CallableBC: CallableAny](
    *,
    wait_for_callback: int | None = WAIT_FOR_CALLBACK,
    enabled: bool = True,
    log_level: int = logging.ERROR,
) -> Callable[[CallableBC], CallableBC]: ...


def bind_collector[CallableBC: CallableAny](
    func: CallableBC | None = None,
    *,
    wait_for_callback: int | None = WAIT_FOR_CALLBACK,
    enabled: bool = True,
    log_level: int = logging.ERROR,
) -> Callable[[CallableBC], CallableBC] | CallableBC:
    """
    Decorate function to automatically add collector if not set.

    Usage:
    - With parentheses: `@bind_collector()`
    - Without parentheses: `@bind_collector`

    Additionally, thrown exceptions are logged.
    """

    def bind_decorator(func: CallableBC) -> CallableBC:
        """Decorate function to automatically add collector if not set."""
        spec = getfullargspec(func)
        # Support both positional and keyword-only 'collector' parameters
        if _COLLECTOR_ARGUMENT_NAME in spec.args:
            argument_index: int | None = spec.args.index(_COLLECTOR_ARGUMENT_NAME)
        else:
            argument_index = None

        @wraps(func)
        async def bind_wrapper(*args: Any, **kwargs: Any) -> Any:
            """Wrap method to add collector."""
            token: Token[bool] | None = None
            if not IN_SERVICE_VAR.get():
                token = IN_SERVICE_VAR.set(True)
            try:
                if not enabled:
                    return_value = await func(*args, **kwargs)
                    if token:
                        IN_SERVICE_VAR.reset(token)
                    return return_value
                try:
                    collector_exists = (
                        argument_index is not None and len(args) > argument_index and args[argument_index] is not None
                    ) or kwargs.get(_COLLECTOR_ARGUMENT_NAME) is not None
                except Exception:
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
            except BaseHomematicException as bhexc:
                if token:
                    IN_SERVICE_VAR.reset(token)
                in_service = IN_SERVICE_VAR.get()
                if not in_service and log_level > logging.NOTSET:
                    context_obj = args[0]
                    logger = logging.getLogger(context_obj.__module__)
                    log_context = context_obj.log_context if isinstance(context_obj, LogContextMixin) else None
                    # Reuse centralized boundary logging to ensure consistent 'extra' structure
                    log_boundary_error(
                        logger=logger,
                        boundary="service",
                        action=func.__name__,
                        err=bhexc,
                        level=log_level,
                        log_context=log_context,
                    )
                # Re-raise domain-specific exceptions so callers and tests can handle them
                raise
            else:
                if token:
                    IN_SERVICE_VAR.reset(token)
                return return_value

        setattr(bind_wrapper, "ha_service", True)
        return cast(CallableBC, bind_wrapper)

    # If used without parentheses: @bind_collector
    if func is not None:
        return bind_decorator(func)
    # If used with parentheses: @bind_collector(...)
    return bind_decorator
