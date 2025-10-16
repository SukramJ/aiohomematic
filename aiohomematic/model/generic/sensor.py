# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Module for data points implemented using the sensor category."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any, Final, cast

from aiohomematic.const import DataPointCategory, Parameter, ParameterType
from aiohomematic.model.generic.data_point import GenericDataPoint
from aiohomematic.model.support import check_length_and_log, get_value_from_value_list
from aiohomematic.property_decorators import state_property

_LOGGER: Final = logging.getLogger(__name__)


class DpSensor[SensorT: float | int | str | None](GenericDataPoint[SensorT, None]):
    """
    Implementation of a sensor.

    This is a default data point that gets automatically generated.
    """

    __slots__ = ()

    _category = DataPointCategory.SENSOR

    @state_property
    def value(self) -> SensorT:
        """Return the value."""
        if (value := get_value_from_value_list(value=self._value, value_list=self.values)) is not None:
            return cast(SensorT, value)
        if convert_func := self._get_converter_func():
            return cast(SensorT, convert_func(value=self._value))
        return cast(
            SensorT,
            check_length_and_log(name=self.name, value=self._value)
            if self._type == ParameterType.STRING
            else self._value,
        )

    def _get_converter_func(self) -> Any:
        """Return a converter based on sensor."""
        if convert_func := _VALUE_CONVERTERS_BY_PARAM.get(self.parameter):
            return convert_func
        return None


def _fix_rssi(*, value: Any) -> int | None:
    """
    Fix rssi value.

    See https://github.com/sukramj/aiohomematic/blob/devel/docs/rssi_fix.md.
    """
    if value is None:
        return None
    if isinstance(value, int):
        if -127 < value < 0:
            return value
        if 1 < value < 127:
            return value * -1
        if -256 < value < -129:
            return (value * -1) - 256
        if 129 < value < 256:
            return value - 256
    return None


_VALUE_CONVERTERS_BY_PARAM: Mapping[str, Any] = {
    Parameter.RSSI_PEER: _fix_rssi,
    Parameter.RSSI_DEVICE: _fix_rssi,
}
