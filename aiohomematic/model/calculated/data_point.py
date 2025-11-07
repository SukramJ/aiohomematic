# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Module with base class for calculated data points."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any, Final, cast

from aiohomematic.const import (
    INIT_DATETIME,
    CallSource,
    CalulatedParameter,
    DataPointKey,
    DataPointUsage,
    Operations,
    ParameterType,
    ParamsetKey,
)
from aiohomematic.model import device as hmd
from aiohomematic.model.custom import definition as hmed
from aiohomematic.model.data_point import BaseDataPoint
from aiohomematic.model.generic import DpDummy, data_point as hmge
from aiohomematic.model.support import (
    DataPointNameData,
    DataPointPathData,
    PathData,
    generate_unique_id,
    get_data_point_name_data,
)
from aiohomematic.property_decorators import config_property, hm_property, state_property
from aiohomematic.type_aliases import DataPointUpdatedCallback, ParamType, UnregisterCallback

_LOGGER: Final = logging.getLogger(__name__)


class CalculatedDataPoint[ParameterT: ParamType](BaseDataPoint):
    """Base class for calculated data point."""

    __slots__ = (
        "_data_points",
        "_default",
        "_max",
        "_min",
        "_multiplier",
        "_operations",
        "_service",
        "_type",
        "_unit",
        "_unregister_callbacks",
        "_values",
        "_visible",
    )

    _calculated_parameter: CalulatedParameter = None  # type: ignore[assignment]

    def __init__(
        self,
        *,
        channel: hmd.Channel,
    ) -> None:
        """Initialize the data point."""
        self._unregister_callbacks: list[UnregisterCallback] = []
        unique_id = generate_unique_id(
            central=channel.central, address=channel.address, parameter=self._calculated_parameter, prefix="calculated"
        )
        super().__init__(
            channel=channel,
            unique_id=unique_id,
            is_in_multiple_channels=hmed.is_multi_channel_device(model=channel.device.model, category=self.category),
        )
        self._data_points: Final[list[hmge.GenericDataPointAny]] = []
        self._type: ParameterType = None  # type: ignore[assignment]
        self._values: tuple[str, ...] | None = None
        self._max: ParameterT = None  # type: ignore[assignment]
        self._min: ParameterT = None  # type: ignore[assignment]
        self._default: ParameterT = None  # type: ignore[assignment]
        self._visible: bool = True
        self._service: bool = False
        self._operations: int = 5
        self._unit: str | None = None
        self._multiplier: float = 1.0
        self._init_data_point_fields()
        self._post_init_data_point_fields()

    @staticmethod
    def is_relevant_for_model(*, channel: hmd.Channel) -> bool:
        """Return if this calculated data point is relevant for the channel."""
        return False

    @property
    def _readable_data_points(self) -> tuple[hmge.GenericDataPointAny, ...]:
        """Returns the list of readable data points."""
        return tuple(dp for dp in self._data_points if dp.is_readable)

    @property
    def _relevant_data_points(self) -> tuple[hmge.GenericDataPointAny, ...]:
        """Returns the list of relevant data points. To be overridden by subclasses."""
        return self._readable_data_points

    @property
    def _relevant_values_data_points(self) -> tuple[hmge.GenericDataPointAny, ...]:
        """Returns the list of relevant VALUES data points. To be overridden by subclasses."""
        return tuple(dp for dp in self._readable_data_points if dp.paramset_key == ParamsetKey.VALUES)

    @property
    def _should_emit_data_point_updated_callback(self) -> bool:
        """Check if a data point has been updated or refreshed."""
        if self.emitted_event_recently:  # pylint: disable=using-constant-test
            return False

        if (relevant_values_data_point := self._relevant_values_data_points) is not None and len(
            relevant_values_data_point
        ) <= 1:
            return True

        return all(dp.emitted_event_recently for dp in relevant_values_data_point)

    @property
    def data_point_name_postfix(self) -> str:
        """Return the data point name postfix."""
        return ""

    @property
    def default(self) -> ParameterT:
        """Return default value."""
        return self._default

    @property
    def has_data_points(self) -> bool:
        """Return if there are data points."""
        return len(self._data_points) > 0

    @property
    def hmtype(self) -> ParameterType:
        """Return the Homematic type."""
        return self._type

    @property
    def is_readable(self) -> bool:
        """Return, if data_point is readable."""
        return bool(self._operations & Operations.READ)

    @property
    def is_valid(self) -> bool:
        """Return if the state is valid."""
        return all(dp.is_valid for dp in self._relevant_data_points)

    @property
    def is_writeable(self) -> bool:
        """Return, if data_point is writeable."""
        return bool(self._operations & Operations.WRITE)

    @property
    def multiplier(self) -> float:
        """Return multiplier value."""
        return self._multiplier

    @property
    def parameter(self) -> str:
        """Return parameter name."""
        return self._calculated_parameter

    @property
    def paramset_key(self) -> ParamsetKey:
        """Return paramset_key name."""
        return ParamsetKey.CALCULATED

    @property
    def service(self) -> bool:
        """Return the if data_point is visible in ccu."""
        return self._service

    @property
    def state_uncertain(self) -> bool:
        """Return, if the state is uncertain."""
        return any(dp.state_uncertain for dp in self._relevant_data_points)

    @property
    def supports_events(self) -> bool:
        """Return, if data_point is supports events."""
        return bool(self._operations & Operations.EVENT)

    @property
    def visible(self) -> bool:
        """Return the if data_point is visible in ccu."""
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
    def unit(self) -> str | None:
        """Return unit value."""
        return self._unit

    @config_property
    def values(self) -> tuple[str, ...] | None:
        """Return the values."""
        return self._values

    @state_property
    def modified_at(self) -> datetime:
        """Return the latest last update timestamp."""
        modified_at: datetime = INIT_DATETIME
        for dp in self._readable_data_points:
            if (data_point_modified_at := dp.modified_at) and data_point_modified_at > modified_at:
                modified_at = data_point_modified_at
        return modified_at

    @state_property
    def refreshed_at(self) -> datetime:
        """Return the latest last refresh timestamp."""
        refreshed_at: datetime = INIT_DATETIME
        for dp in self._readable_data_points:
            if (data_point_refreshed_at := dp.refreshed_at) and data_point_refreshed_at > refreshed_at:
                refreshed_at = data_point_refreshed_at
        return refreshed_at

    @hm_property(cached=True)
    def dpk(self) -> DataPointKey:
        """Return data_point key value."""
        return DataPointKey(
            interface_id=self._device.interface_id,
            channel_address=self._channel.address,
            paramset_key=ParamsetKey.CALCULATED,
            parameter=self._calculated_parameter,
        )

    def is_state_change(self, **kwargs: Any) -> bool:
        """
        Check if the state changes due to kwargs.

        If the state is uncertain, the state should also marked as changed.
        """
        if self.state_uncertain:
            return True
        _LOGGER.debug("NO_STATE_CHANGE: %s", self.name)
        return False

    async def load_data_point_value(self, *, call_source: CallSource, direct_call: bool = False) -> None:
        """Init the data point values."""
        for dp in self._readable_data_points:
            await dp.load_data_point_value(call_source=call_source, direct_call=direct_call)
        self.emit_data_point_updated_event()

    def _add_data_point[DataPointT: hmge.GenericDataPointAny](
        self, *, parameter: str, paramset_key: ParamsetKey | None, data_point_type: type[DataPointT]
    ) -> DataPointT:
        """Add a new data point."""
        if generic_data_point := self._channel.get_generic_data_point(parameter=parameter, paramset_key=paramset_key):
            self._data_points.append(generic_data_point)
            self._unregister_callbacks.append(
                generic_data_point.register_internal_data_point_updated_callback(cb=self.emit_data_point_updated_event)
            )
            return cast(data_point_type, generic_data_point)  # type: ignore[valid-type]
        return cast(
            data_point_type,  # type:ignore[valid-type]
            DpDummy(channel=self._channel, param_field=parameter),
        )

    def _add_device_data_point[DataPointT: hmge.GenericDataPointAny](
        self,
        *,
        channel_address: str,
        parameter: str,
        paramset_key: ParamsetKey | None,
        data_point_type: type[DataPointT],
    ) -> DataPointT:
        """Add a new data point."""
        if generic_data_point := self._channel.device.get_generic_data_point(
            channel_address=channel_address, parameter=parameter, paramset_key=paramset_key
        ):
            self._data_points.append(generic_data_point)
            self._unregister_callbacks.append(
                generic_data_point.register_internal_data_point_updated_callback(cb=self.emit_data_point_updated_event)
            )
            return cast(data_point_type, generic_data_point)  # type: ignore[valid-type]
        return cast(
            data_point_type,  # type:ignore[valid-type]
            DpDummy(channel=self._channel, param_field=parameter),
        )

    def _get_data_point_name(self) -> DataPointNameData:
        """Create the name for the data point."""
        return get_data_point_name_data(channel=self._channel, parameter=self._calculated_parameter)

    def _get_data_point_usage(self) -> DataPointUsage:
        """Generate the usage for the data point."""
        return DataPointUsage.DATA_POINT

    def _get_path_data(self) -> PathData:
        """Return the path data of the data_point."""
        return DataPointPathData(
            interface=self._device.client.interface,
            address=self._device.address,
            channel_no=self._channel.no,
            kind=self._category,
        )

    def _get_signature(self) -> str:
        """Return the signature of the data_point."""
        return f"{self._category}/{self._channel.device.model}/{self._calculated_parameter}"

    def _init_data_point_fields(self) -> None:
        """Init the data point fields."""
        _LOGGER.debug(
            "INIT_DATA_POINT_FIELDS: Initialising the data point fields for %s",
            self.full_name,
        )

    def _post_init_data_point_fields(self) -> None:
        """Post action after initialisation of the data point fields."""
        _LOGGER.debug(
            "POST_INIT_DATA_POINT_FIELDS: Post action after initialisation of the data point fields for %s",
            self.full_name,
        )

    def _unregister_data_point_updated_callback(self, *, cb: DataPointUpdatedCallback, custom_id: str) -> None:
        """Unregister update callback."""
        for unregister in self._unregister_callbacks:
            if unregister is not None:
                unregister()

        super()._unregister_data_point_updated_callback(cb=cb, custom_id=custom_id)
