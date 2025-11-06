# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Module for data points implemented using the switch category."""

from __future__ import annotations

from aiohomematic.const import DataPointCategory, Parameter, ParameterType
from aiohomematic.decorators import inspector
from aiohomematic.model.data_point import CallParameterCollector
from aiohomematic.model.generic.data_point import GenericDataPoint
from aiohomematic.property_decorators import state_property


class DpSwitch(GenericDataPoint[bool | None, bool]):
    """
    Implementation of a switch.

    This is a default data point that gets automatically generated.
    """

    __slots__ = ()

    _category = DataPointCategory.SWITCH

    @state_property
    def value(self) -> bool | None:
        """Get the value of the data_point."""
        if self._type == ParameterType.ACTION:
            return False
        return self._value

    @inspector
    async def set_on_time(self, *, on_time: float) -> None:
        """Set the on time value in seconds."""
        await self._client.set_value(
            channel_address=self._channel.address,
            paramset_key=self._paramset_key,
            parameter=Parameter.ON_TIME,
            value=float(on_time),
        )

    @inspector
    async def turn_off(self, *, collector: CallParameterCollector | None = None) -> None:
        """Turn the switch off."""
        await self.send_value(value=False, collector=collector)

    @inspector
    async def turn_on(self, *, on_time: float | None = None, collector: CallParameterCollector | None = None) -> None:
        """Turn the switch on."""
        if on_time is not None:
            await self.set_on_time(on_time=on_time)
        await self.send_value(value=True, collector=collector)
