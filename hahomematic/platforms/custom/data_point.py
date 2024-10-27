"""Module with base class for custom data points."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
import logging
from typing import Any, Final, cast

from hahomematic.const import (
    CALLBACK_TYPE,
    DATA_POINT_KEY,
    INIT_DATETIME,
    CallSource,
    DataPointUsage,
)
from hahomematic.platforms import device as hmd
from hahomematic.platforms.custom import definition as hmed
from hahomematic.platforms.custom.const import ED, DeviceProfile, Field
from hahomematic.platforms.custom.support import CustomConfig
from hahomematic.platforms.data_point import BaseDataPoint, CallParameterCollector
from hahomematic.platforms.decorators import get_service_calls, state_property
from hahomematic.platforms.generic import data_point as hmge
from hahomematic.platforms.support import (
    DataPointNameData,
    check_channel_is_the_only_primary_channel,
    get_custom_data_point_name,
)
from hahomematic.support import get_channel_address

_LOGGER: Final = logging.getLogger(__name__)


class CustomDataPoint(BaseDataPoint):
    """Base class for custom data points."""

    def __init__(
        self,
        channel: hmd.HmChannel,
        unique_id: str,
        device_profile: DeviceProfile,
        device_def: Mapping[str, Any],
        data_point_def: Mapping[int | tuple[int, ...], tuple[str, ...]],
        base_channel_no: int,
        custom_config: CustomConfig,
    ) -> None:
        """Initialize the data_point."""
        self._unregister_callbacks: list[CALLBACK_TYPE] = []
        self._device_profile: Final = device_profile
        # required for name in BaseDataPoint
        self._device_def: Final = device_def
        self._data_point_def: Final = data_point_def
        self._base_no: int = base_channel_no
        self._custom_config: Final = custom_config
        self._extended: Final = custom_config.extended
        super().__init__(
            channel=channel,
            unique_id=unique_id,
            is_in_multiple_channels=hmed.is_multi_channel_device(
                model=channel.device.model, platform=self.platform
            ),
        )
        self._allow_undefined_generic_data_points: Final[bool] = self._device_def[
            ED.ALLOW_UNDEFINED_GENERIC_DATA_POINTS
        ]
        self._data_data_points: Final[dict[Field, hmge.GenericDataPoint]] = {}
        self._init_data_points()
        self._init_data_point_fields()
        self._service_methods = get_service_calls(obj=self)

    @property
    def allow_undefined_generic_data_points(self) -> bool:
        """Return if undefined generic data points of this device are allowed."""
        return self._allow_undefined_generic_data_points

    @property
    def base_no(self) -> int | None:
        """Return the base channel no of the data_point."""
        return self._base_no

    def _init_data_point_fields(self) -> None:
        """Init the data_point fields."""
        _LOGGER.debug(
            "INIT_DATA_POINT_FIELDS: Initialising the custom data_point fields for %s",
            self.full_name,
        )

    @state_property
    def modified_at(self) -> datetime:
        """Return the latest last update timestamp."""
        modified_at: datetime = INIT_DATETIME
        for data_point in self._readable_data_points:
            if (
                data_point_modified_at := data_point.modified_at
            ) and data_point_modified_at > modified_at:
                modified_at = data_point_modified_at
        return modified_at

    @state_property
    def refreshed_at(self) -> datetime:
        """Return the latest last refresh timestamp."""
        refreshed_at: datetime = INIT_DATETIME
        for data_point in self._readable_data_points:
            if (
                data_point_refreshed_at := data_point.refreshed_at
            ) and data_point_refreshed_at > refreshed_at:
                refreshed_at = data_point_refreshed_at
        return refreshed_at

    @property
    def unconfirmed_last_values_send(self) -> dict[Field, Any]:
        """Return the unconfirmed values send for the data_point."""
        unconfirmed_values: dict[Field, Any] = {}
        for field, data_point in self._data_data_points.items():
            if (unconfirmed_value := data_point.unconfirmed_last_value_send) is not None:
                unconfirmed_values[field] = unconfirmed_value
        return unconfirmed_values

    @property
    def has_data_data_points(self) -> bool:
        """Return if there are data data points."""
        return len(self._data_data_points) > 0

    @property
    def is_valid(self) -> bool:
        """Return if the state is valid."""
        return all(data_point.is_valid for data_point in self._relevant_data_points)

    @property
    def state_uncertain(self) -> bool:
        """Return, if the state is uncertain."""
        return any(data_point.state_uncertain for data_point in self._relevant_data_points)

    @property
    def _readable_data_points(self) -> tuple[hmge.GenericDataPoint, ...]:
        """Returns the list of readable data points."""
        return tuple(ge for ge in self._data_data_points.values() if ge.is_readable)

    @property
    def _relevant_data_points(self) -> tuple[hmge.GenericDataPoint, ...]:
        """Returns the list of relevant data points. To be overridden by subclasses."""
        return self._readable_data_points

    @property
    def data_point_name_postfix(self) -> str:
        """Return the data_point name postfix."""
        return ""

    def _get_data_point_name(self) -> DataPointNameData:
        """Create the name for the data_point."""
        is_only_primary_channel = check_channel_is_the_only_primary_channel(
            current_channel_no=self._channel.no,
            device_def=self._device_def,
            device_has_multiple_channels=self.is_in_multiple_channels,
        )
        return get_custom_data_point_name(
            channel=self._channel,
            is_only_primary_channel=is_only_primary_channel,
            usage=self._get_data_point_usage(),
            postfix=self.data_point_name_postfix.replace("_", " ").title(),
        )

    def _get_data_point_usage(self) -> DataPointUsage:
        """Generate the usage for the data_point."""
        if self._forced_usage:
            return self._forced_usage
        if self._channel.no in self._custom_config.channels:
            return DataPointUsage.CE_PRIMARY
        return DataPointUsage.CE_SECONDARY

    async def load_data_point_value(
        self, call_source: CallSource, direct_call: bool = False
    ) -> None:
        """Init the data_point values."""
        for data_point in self._readable_data_points:
            await data_point.load_data_point_value(
                call_source=call_source, direct_call=direct_call
            )
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

    def _init_data_points(self) -> None:
        """Init data_point collection."""
        # Add repeating fields
        for field_name, parameter in self._device_def.get(hmed.ED.REPEATABLE_FIELDS, {}).items():
            data_point = self._device.get_generic_data_point(
                channel_address=self._channel.address, parameter=parameter
            )
            self._add_data_point(field=field_name, data_point=data_point, is_visible=False)

        # Add visible repeating fields
        for field_name, parameter in self._device_def.get(
            hmed.ED.VISIBLE_REPEATABLE_FIELDS, {}
        ).items():
            data_point = self._device.get_generic_data_point(
                channel_address=self._channel.address, parameter=parameter
            )
            self._add_data_point(field=field_name, data_point=data_point, is_visible=True)

        if self._extended:
            if fixed_channels := self._extended.fixed_channels:
                for channel_no, mapping in fixed_channels.items():
                    for field_name, parameter in mapping.items():
                        channel_address = get_channel_address(
                            device_address=self._device.address, channel_no=channel_no
                        )
                        data_point = self._device.get_generic_data_point(
                            channel_address=channel_address, parameter=parameter
                        )
                        self._add_data_point(field=field_name, data_point=data_point)
            if additional_data_points := self._extended.additional_data_points:
                self._mark_data_points(data_point_def=additional_data_points)

        # Add device fields
        self._add_data_points(
            field_dict_name=hmed.ED.FIELDS,
        )
        # Add visible device fields
        self._add_data_points(
            field_dict_name=hmed.ED.VISIBLE_FIELDS,
            is_visible=True,
        )

        # Add default device data points
        self._mark_data_points(data_point_def=self._data_point_def)
        # add default data points
        if hmed.get_include_default_data_points(device_profile=self._device_profile):
            self._mark_data_points(data_point_def=hmed.get_default_data_points())

    def _add_data_points(self, field_dict_name: hmed.ED, is_visible: bool | None = None) -> None:
        """Add data points to custom data_point."""
        fields = self._device_def.get(field_dict_name, {})
        for channel_no, channel in fields.items():
            for field, parameter in channel.items():
                channel_address = get_channel_address(
                    device_address=self._device.address, channel_no=channel_no
                )
                if data_point := self._device.get_generic_data_point(
                    channel_address=channel_address, parameter=parameter
                ):
                    self._add_data_point(field=field, data_point=data_point, is_visible=is_visible)

    def _add_data_point(
        self,
        field: Field,
        data_point: hmge.GenericDataPoint | None,
        is_visible: bool | None = None,
    ) -> None:
        """Add data_point to collection and register callback."""
        if not data_point:
            return
        if is_visible is True and data_point.is_forced_sensor is False:
            data_point.force_usage(forced_usage=DataPointUsage.CE_VISIBLE)
        elif is_visible is False and data_point.is_forced_sensor is False:
            data_point.force_usage(forced_usage=DataPointUsage.NO_CREATE)

        self._unregister_callbacks.append(
            data_point.register_internal_data_point_updated_callback(
                cb=self.fire_data_point_updated_callback
            )
        )
        self._data_data_points[field] = data_point

    def _unregister_data_point_updated_callback(self, cb: Callable, custom_id: str) -> None:
        """Unregister update callback."""
        for unregister in self._unregister_callbacks:
            if unregister is not None:
                unregister()

        super()._unregister_data_point_updated_callback(cb=cb, custom_id=custom_id)

    def _mark_data_points(
        self, data_point_def: Mapping[int | tuple[int, ...], tuple[str, ...]]
    ) -> None:
        """Mark data points to be created in HA."""
        if not data_point_def:
            return
        for channel_nos, parameters in data_point_def.items():
            if isinstance(channel_nos, int):
                self._mark_data_point(channel_no=channel_nos, parameters=parameters)
            else:
                for channel_no in channel_nos:
                    self._mark_data_point(channel_no=channel_no, parameters=parameters)

    def _mark_data_point(self, channel_no: int | None, parameters: tuple[str, ...]) -> None:
        """Mark data_point to be created in HA."""
        channel_address = get_channel_address(
            device_address=self._device.address, channel_no=channel_no
        )

        for parameter in parameters:
            if data_point := self._device.get_generic_data_point(
                channel_address=channel_address, parameter=parameter
            ):
                data_point.force_usage(forced_usage=DataPointUsage.DATA_POINT)

    def _get_data_point[_DataPointT: hmge.GenericDataPoint](
        self, field: Field, data_point_type: type[_DataPointT]
    ) -> _DataPointT:
        """Get data_point."""
        if data_point := self._data_data_points.get(field):
            if type(data_point).__name__ != data_point_type.__name__:
                # not isinstance(data_point, data_point_type): # does not work with generic type
                _LOGGER.debug(  # pragma: no cover
                    "GET_DATA_POINT: type mismatch for requested sub data_point: "
                    "expected: %s, but is %s for field name %s of data_point %s",
                    data_point_type.name,
                    type(data_point),
                    field,
                    self.name,
                )
            return cast(data_point_type, data_point)  # type: ignore[valid-type]
        return cast(
            data_point_type,  # type:ignore[valid-type]
            NoneTypeDataPoint(),
        )

    def has_data_point_key(self, data_point_keys: set[DATA_POINT_KEY]) -> bool:
        """Return if a data_point with one of the data points is part of this data_point."""
        result = [
            data_point
            for data_point in self._data_data_points.values()
            if data_point.data_point_key in data_point_keys
        ]
        return len(result) > 0


class NoneTypeDataPoint:
    """DataPoint to return an empty value."""

    default: Any = None
    hmtype: Any = None
    is_valid: bool = False
    max: Any = None
    min: Any = None
    unit: Any = None
    value: Any = None
    values: list[Any] = []
    visible: Any = None
    channel_operation_mode: str | None = None
    is_hmtype = False

    async def send_value(
        self,
        value: Any,
        collector: CallParameterCollector | None = None,
        do_validate: bool = True,
    ) -> None:
        """Send value dummy method."""
