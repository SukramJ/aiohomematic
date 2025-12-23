# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Descriptor-based field definitions for calculated data points.

This module provides a declarative way to define data point fields,
eliminating boilerplate in _post_init() methods.

Public API of this module is defined by __all__.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final, cast, overload

from aiohomematic.const import ParamsetKey
from aiohomematic.interfaces.model import GenericDataPointProtocolAny
from aiohomematic.property_decorators import DelegatedProperty

if TYPE_CHECKING:
    from typing import Self

    from aiohomematic.model.calculated.data_point import CalculatedDataPoint

__all__ = ["CalculatedDataPointField"]

# Key type for calculated data point dictionary
type _DataPointKey = tuple[str, ParamsetKey | None]


class CalculatedDataPointField[DataPointT: GenericDataPointProtocolAny]:
    """
    Descriptor for declarative calculated data point field definitions.

    This descriptor eliminates the need for explicit _post_init()
    boilerplate by lazily resolving data points on first access.

    Usage:
        class MyCalculatedSensor(CalculatedDataPoint):
            # Simple field
            _dp_wind_speed: Final = CalculatedDataPointField(
                parameter=Parameter.WIND_SPEED,
                paramset_key=ParamsetKey.VALUES,
                dpt=DpSensor,
            )

            # Field with fallback parameters
            _dp_temperature: Final = CalculatedDataPointField(
                parameter=Parameter.TEMPERATURE,
                paramset_key=ParamsetKey.VALUES,
                dpt=DpSensor,
                fallback_parameters=[Parameter.ACTUAL_TEMPERATURE],
            )

            # Field with device fallback (tries device address if not on channel)
            _dp_low_bat_limit: Final = CalculatedDataPointField(
                parameter=Parameter.LOW_BAT_LIMIT,
                paramset_key=ParamsetKey.MASTER,
                dpt=DpFloat,
                use_device_fallback=True,
            )

    The descriptor:
    - Resolves the data point from _data_points dict on each access (O(1) lookup)
    - Tries fallback_parameters in order if primary parameter doesn't exist
    - Tries device address if use_device_fallback=True and not found on channel
    - Returns a DpDummy fallback if no data point exists
    - Subscribes to data point updates automatically
    - Provides correct type information to mypy
    """

    __slots__ = ("_parameter", "_paramset_key", "_data_point_type", "_fallback_parameters", "_use_device_fallback")

    def __init__(
        self,
        *,
        parameter: str,
        paramset_key: ParamsetKey | None,
        dpt: type[DataPointT],
        fallback_parameters: list[str] | None = None,
        use_device_fallback: bool = False,
    ) -> None:
        """
        Initialize the calculated data point field descriptor.

        Args:
            parameter: The parameter name identifying this data point
            paramset_key: The paramset key (VALUES, MASTER, etc.)
            dpt: The expected data point type (e.g., DpSensor, DpFloat)
            fallback_parameters: Optional list of fallback parameter names to try if primary not found
            use_device_fallback: If True, try device address (channel 0) if not found on current channel

        """
        self._parameter: Final = parameter
        self._paramset_key: Final = paramset_key
        self._data_point_type: Final = dpt
        self._fallback_parameters: Final = fallback_parameters or []
        self._use_device_fallback: Final = use_device_fallback

    @overload
    def __get__(self, instance: None, owner: type) -> Self: ...  # kwonly: disable

    @overload
    def __get__(self, instance: CalculatedDataPoint[Any], owner: type) -> DataPointT: ...  # kwonly: disable

    def __get__(self, instance: CalculatedDataPoint[Any] | None, owner: type) -> Self | DataPointT:  # kwonly: disable
        """
        Get the data point for this field.

        On class-level access (instance=None), returns the descriptor itself.
        On instance access, looks up the data point from _data_points dict.
        """
        if instance is None:
            return self  # Class-level access returns descriptor

        key: _DataPointKey = (self._parameter, self._paramset_key)

        # Resolve from _data_points dict (O(1) lookup)
        if found_dp := instance._data_points.get(key):
            return cast(DataPointT, found_dp)

        # Try primary parameter first, then fallbacks on current channel
        for param in (self._parameter, *self._fallback_parameters):
            if instance._channel.get_generic_data_point(parameter=param, paramset_key=self._paramset_key):
                dp = instance._resolve_data_point(parameter=param, paramset_key=self._paramset_key)
                instance._data_points[key] = dp
                return cast(DataPointT, dp)

        # Try device address (channel 0) if enabled
        if self._use_device_fallback:
            dp = instance._add_device_data_point(
                channel_address=instance._channel.device.address,
                parameter=self._parameter,
                paramset_key=self._paramset_key,
                dpt=self._data_point_type,
            )
            instance._data_points[key] = dp
            return cast(DataPointT, dp)

        # No data point found - resolve DpDummy for primary parameter
        dp = instance._resolve_data_point(parameter=self._parameter, paramset_key=self._paramset_key)
        instance._data_points[key] = dp
        return cast(DataPointT, dp)

    data_point_type: Final = DelegatedProperty[type[DataPointT]](path="_data_point_type")
    parameter: Final = DelegatedProperty[str](path="_parameter")
    paramset_key: Final = DelegatedProperty[ParamsetKey | None](path="_paramset_key")
