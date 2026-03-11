# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Combined HS color data point for hue+saturation pairs.

Public API of this module is defined by __all__.
"""

from typing import Final

from aiohomematic.const import DataPointCategory, Field, Operations, ParameterType
from aiohomematic.interfaces import ChannelProtocol, CombinedDataPointProtocol, GenericDataPointProtocolAny
from aiohomematic.model.combined.data_point import CombinedDataPoint
from aiohomematic.model.data_point import CallParameterCollector
from aiohomematic.model.generic import DpDummy
from aiohomematic.property_decorators import state_property

__all__ = ["CombinedDpHsColor"]

# Saturation multiplier: CCU stores saturation as 0.0–1.0, HA uses 0.0–100.0
_SATURATION_MULTIPLIER: Final = 100


class CombinedDpHsColor(CombinedDataPoint[tuple[float, float] | None], CombinedDataPointProtocol):
    """Combined data point for hue+saturation color pairs."""

    __slots__ = ("_hue_dp", "_saturation_dp")

    _category = DataPointCategory.SENSOR

    def __init__(
        self,
        *,
        channel: ChannelProtocol,
        hue_field: Field,
        saturation_field: Field,
        hue_dp: GenericDataPointProtocolAny,
        saturation_dp: GenericDataPointProtocolAny,
    ) -> None:
        """Initialize the combined HS color data point."""
        super().__init__(
            channel=channel,
            combined_parameter=hue_field.value,
        )
        self._hue_dp: Final = hue_dp
        self._saturation_dp: Final = saturation_dp
        self._data_points[hue_field] = hue_dp
        self._data_points[saturation_field] = saturation_dp

        # Subscribe to underlying DPs
        self._subscribe_to_data_point(data_point=hue_dp)
        self._subscribe_to_data_point(data_point=saturation_dp)

        # Configure type info
        self._type = ParameterType.FLOAT
        self._operations = Operations.READ | Operations.WRITE | Operations.EVENT

    @property
    def default(self) -> None:
        """Return the default value."""
        return None

    @property
    def is_valid(self) -> bool:
        """Return True if neither hue nor saturation is a dummy."""
        return not isinstance(self._hue_dp, DpDummy) and not isinstance(self._saturation_dp, DpDummy)

    @state_property
    def value(self) -> tuple[float, float] | None:
        """Return the hue and saturation color value [float, float]."""
        if self._hue_dp.value is not None and self._saturation_dp.value is not None:
            return self._hue_dp.value, self._saturation_dp.value * _SATURATION_MULTIPLIER
        return None

    async def send_default(self, *, collector: CallParameterCollector | None = None) -> None:
        """Send default values for both hue and saturation data points."""
        if (hue_default := self._hue_dp.default) is not None:
            await self._hue_dp.send_value(value=hue_default, collector=collector)
        if (saturation_default := self._saturation_dp.default) is not None:
            await self._saturation_dp.send_value(value=saturation_default, collector=collector)

    async def send_value(
        self,
        *,
        value: tuple[float, float],
        collector: CallParameterCollector | None = None,
    ) -> None:
        """Send hue and saturation values to the device."""
        hue, saturation = value
        await self._hue_dp.send_value(value=int(hue), collector=collector)
        await self._saturation_dp.send_value(value=saturation / _SATURATION_MULTIPLIER, collector=collector)
