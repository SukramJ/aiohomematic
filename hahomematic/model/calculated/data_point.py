"""Module with base class for calculated data points."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from functools import cached_property
import logging
from typing import Any, Final, cast

from hahomematic.const import (
    CALLBACK_TYPE,
    INIT_DATETIME,
    CallSource,
    CalulatedParameter,
    DataPointKey,
    DataPointUsage,
    Operations,
    ParameterType,
    ParamsetKey,
)
from hahomematic.model import device as hmd
from hahomematic.model.custom import definition as hmed
from hahomematic.model.data_point import BaseDataPoint, NoneTypeDataPoint
from hahomematic.model.decorators import config_property, state_property
from hahomematic.model.generic import data_point as hmge
from hahomematic.model.support import (
    DataPointNameData,
    DataPointPathData,
    GenericParameterType,
    PathData,
    generate_unique_id,
    get_data_point_name_data,
)

_LOGGER: Final = logging.getLogger(__name__)


class CalculatedDataPoint[ParameterT: GenericParameterType](BaseDataPoint):
    """Base class for calculated data point."""

    _calculated_parameter: CalulatedParameter = None  # type: ignore[assignment]

    def __init__(
        self,
        channel: hmd.Channel,
    ) -> None:
        """Initialize the data point."""
        self._unregister_callbacks: list[CALLBACK_TYPE] = []
        unique_id = generate_unique_id(
            central=channel.central, address=channel.address, parameter=self._calculated_parameter, prefix="calculated"
        )
        super().__init__(
            channel=channel,
            unique_id=unique_id,
            is_in_multiple_channels=hmed.is_multi_channel_device(model=channel.device.model, category=self.category),
        )
        self._data_points: Final[list[hmge.GenericDataPoint]] = []
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

    def _init_data_point_fields(self) -> None:
        """Init the data point fields."""
        _LOGGER.debug(
            "INIT_DATA_POINT_FIELDS: Initialising the data point fields for %s",
            self.full_name,
        )

    def _add_data_point[DataPointT: hmge.GenericDataPoint](
        self, parameter: str, paramset_key: ParamsetKey | None, data_point_type: type[DataPointT]
    ) -> DataPointT:
        """Add a new data point."""
        if generic_data_point := self._channel.get_generic_data_point(parameter=parameter, paramset_key=paramset_key):
            self._data_points.append(generic_data_point)
            self._unregister_callbacks.append(
                generic_data_point.register_internal_data_point_updated_callback(
                    cb=self.fire_data_point_updated_callback
                )
            )
            return cast(data_point_type, generic_data_point)  # type: ignore[valid-type]
        return cast(
            data_point_type,  # type:ignore[valid-type]
            NoneTypeDataPoint(),
        )

    def _add_device_data_point[DataPointT: hmge.GenericDataPoint](
        self, channel_address: str, parameter: str, paramset_key: ParamsetKey | None, data_point_type: type[DataPointT]
    ) -> DataPointT:
        """Add a new data point."""
        if generic_data_point := self._channel.device.get_generic_data_point(
            channel_address=channel_address, parameter=parameter, paramset_key=paramset_key
        ):
            self._data_points.append(generic_data_point)
            self._unregister_callbacks.append(
                generic_data_point.register_internal_data_point_updated_callback(
                    cb=self.fire_data_point_updated_callback
                )
            )
            return cast(data_point_type, generic_data_point)  # type: ignore[valid-type]
        return cast(
            data_point_type,  # type:ignore[valid-type]
            NoneTypeDataPoint(),
        )

    @property
    def is_readable(self) -> bool:
        """Return, if data_point is readable."""
        return bool(self._operations & Operations.READ)

    @staticmethod
    def is_relevant_for_model(channel: hmd.Channel) -> bool:
        """Return if this calculated data point is relevant for the channel."""
        return False

    @property
    def is_writeable(self) -> bool:
        """Return, if data_point is writeable."""
        return bool(self._operations & Operations.WRITE)

    @property
    def default(self) -> ParameterT:
        """Return default value."""
        return self._default

    @cached_property
    def dpk(self) -> DataPointKey:
        """Return data_point key value."""
        return DataPointKey(
            interface_id=self._device.interface_id,
            channel_address=self._channel.address,
            paramset_key=ParamsetKey.CALCULATED,
            parameter=self._calculated_parameter,
        )

    @property
    def hmtype(self) -> ParameterType:
        """Return the HomeMatic type."""
        return self._type

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
    def supports_events(self) -> bool:
        """Return, if data_point is supports events."""
        return bool(self._operations & Operations.EVENT)

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

    @state_property
    def modified_at(self) -> datetime:
        """Return the latest last update timestamp."""
        modified_at: datetime = INIT_DATETIME
        for data_point in self._readable_data_points:
            if (data_point_modified_at := data_point.modified_at) and data_point_modified_at > modified_at:
                modified_at = data_point_modified_at
        return modified_at

    @state_property
    def refreshed_at(self) -> datetime:
        """Return the latest last refresh timestamp."""
        refreshed_at: datetime = INIT_DATETIME
        for data_point in self._readable_data_points:
            if (data_point_refreshed_at := data_point.refreshed_at) and data_point_refreshed_at > refreshed_at:
                refreshed_at = data_point_refreshed_at
        return refreshed_at

    @property
    def has_data_points(self) -> bool:
        """Return if there are data points."""
        return len(self._data_points) > 0

    @property
    def is_valid(self) -> bool:
        """Return if the state is valid."""
        return all(dp.is_valid for dp in self._relevant_data_points)

    @property
    def state_uncertain(self) -> bool:
        """Return, if the state is uncertain."""
        return any(dp.state_uncertain for dp in self._relevant_data_points)

    @property
    def _readable_data_points(self) -> tuple[hmge.GenericDataPoint, ...]:
        """Returns the list of readable data points."""
        return tuple(dp for dp in self._data_points if dp.is_readable)

    @property
    def _relevant_data_points(self) -> tuple[hmge.GenericDataPoint, ...]:
        """Returns the list of relevant data points. To be overridden by subclasses."""
        return self._readable_data_points

    @property
    def data_point_name_postfix(self) -> str:
        """Return the data point name postfix."""
        return ""

    @property
    def _data_points_received_shortly(self) -> bool:
        """Check if all data points have been received shortly."""
        min_received: datetime | None = None
        max_received: datetime | None = None
        for data_point in self._relevant_data_points:
            if refreshed_at := data_point.refreshed_at:
                if min_received is None or refreshed_at < min_received:
                    min_received = refreshed_at
                if max_received is None or refreshed_at > max_received:
                    max_received = refreshed_at

        if min_received and max_received:
            return (max_received - min_received).total_seconds() < 1
        return False

    def _get_path_data(self) -> PathData:
        """Return the path data of the data_point."""
        return DataPointPathData(
            interface=self._device.client.interface,
            address=self._device.address,
            channel_no=self._channel.no,
            kind=self._category,
        )

    def _get_data_point_name(self) -> DataPointNameData:
        """Create the name for the data point."""
        return get_data_point_name_data(channel=self._channel, parameter=self._calculated_parameter)

    def _get_data_point_usage(self) -> DataPointUsage:
        """Generate the usage for the data point."""
        return DataPointUsage.DATA_POINT

    async def load_data_point_value(self, call_source: CallSource, direct_call: bool = False) -> None:
        """Init the data point values."""
        for data_point in self._readable_data_points:
            await data_point.load_data_point_value(call_source=call_source, direct_call=direct_call)
        self.fire_data_point_updated_callback()

    def is_state_change(self, **kwargs: Any) -> bool:
        """
        Check if the state changes due to kwargs.

        If the state is uncertain, the state should also marked as changed.
        """
        if self.state_uncertain:
            return True
        _LOGGER.debug("NO_STATE_CHANGE: %s", self.name)
        return False

    @property
    def _should_fire_data_point_updated_callback(self) -> bool:
        """Check if a data point has been updated or refreshed."""
        return self._data_points_received_shortly

    def _unregister_data_point_updated_callback(self, cb: Callable, custom_id: str) -> None:
        """Unregister update callback."""
        for unregister in self._unregister_callbacks:
            if unregister is not None:
                unregister()

        super()._unregister_data_point_updated_callback(cb=cb, custom_id=custom_id)
