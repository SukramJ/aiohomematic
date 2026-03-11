# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Combined timer data point for value+unit timer pairs.

Public API of this module is defined by __all__.
"""

from typing import Any, Final, cast

from aiohomematic.const import DataPointCategory, Field, ParameterType
from aiohomematic.interfaces import ChannelProtocol, CombinedDataPointProtocol, GenericDataPointProtocolAny
from aiohomematic.model.combined.data_point import CombinedDataPoint
from aiohomematic.model.custom.mixins import recalc_unit_timer
from aiohomematic.model.data_point import CallParameterCollector
from aiohomematic.model.generic import DpDummy
from aiohomematic.property_decorators import state_property

__all__ = ["CombinedDpTimerAction"]

# Seconds per hour — used to compute max seconds from raw max hours
_TIME_UNIT_THRESHOLD_HOURS: Final = 3600


class CombinedDpTimerAction(CombinedDataPoint[float | None], CombinedDataPointProtocol):
    """Combined data point for timer value+unit pairs with automatic unit conversion."""

    __slots__ = ("_unit_dp", "_value_dp")

    _category = DataPointCategory.ACTION_NUMBER

    def __init__(
        self,
        *,
        channel: ChannelProtocol,
        value_field: Field,
        unit_field: Field | None = None,
        value_dp: GenericDataPointProtocolAny,
        unit_dp: GenericDataPointProtocolAny,
        visible: bool = False,
    ) -> None:
        """Initialize the combined timer data point."""
        super().__init__(
            channel=channel,
            combined_parameter=value_field.value,
            visible=visible,
        )
        self._value_dp: Final = value_dp
        self._unit_dp: Final = unit_dp
        self._data_points[value_field] = value_dp
        if unit_field is not None:
            self._data_points[unit_field] = unit_dp

        # Subscribe to underlying DPs
        self._subscribe_to_data_point(data_point=value_dp)
        self._subscribe_to_data_point(data_point=unit_dp)

        # Configure type info for HA entity
        self._type = ParameterType.FLOAT
        self._unit = "s"
        self._min = 0.0

        # Compute max: if unit DP exists, max = raw_max * 3600 (hours->seconds)
        if not isinstance(unit_dp, DpDummy):
            raw_max = value_dp.max
            self._max = float(raw_max * _TIME_UNIT_THRESHOLD_HOURS) if raw_max is not None else None
        else:
            self._max = float(value_dp.max) if value_dp.max is not None else None

    @property
    def default(self) -> float | None:
        """Return the default value of the underlying value data point."""
        default: Any = self._value_dp.default
        return cast(float | None, default)

    @property
    def is_valid(self) -> bool:
        """Return True if the value data point is not a dummy."""
        return not isinstance(self._value_dp, DpDummy)

    @state_property
    def value(self) -> float | None:
        """Return the stored seconds value."""
        return self._current_value

    async def send_default(self, *, collector: CallParameterCollector | None = None) -> None:
        """Send default values for both unit and value data points."""
        if not isinstance(self._unit_dp, DpDummy) and (unit_default := self._unit_dp.default) is not None:
            await self._unit_dp.send_value(value=unit_default, collector=collector)
        if (value_default := self._value_dp.default) is not None:
            await self._value_dp.send_value(value=value_default, collector=collector)

    async def send_value(
        self,
        *,
        value: float,
        collector: CallParameterCollector | None = None,
    ) -> None:
        """Send timer value in seconds with automatic unit conversion."""
        if isinstance(self._unit_dp, DpDummy):
            # No unit data point — send seconds directly
            await self._value_dp.send_value(value=value, collector=collector, do_validate=False)
        else:
            # Has unit — convert seconds to value+unit
            converted_value, unit = recalc_unit_timer(time=value)
            await self._unit_dp.send_value(value=unit, collector=collector)
            await self._value_dp.send_value(value=converted_value, collector=collector, do_validate=False)
        # Persist seconds value (ACTION params have no CCU events to overwrite)
        self._current_value = value
