"""Module for data points implemented using the switch category."""

from __future__ import annotations

from typing import cast

from hahomematic.const import DataPointCategory, Parameter, ParameterType
from hahomematic.decorators import inspector
from hahomematic.model.data_point import CallParameterCollector
from hahomematic.model.decorators import state_property
from hahomematic.model.generic.data_point import GenericDataPoint


class DpSwitch(GenericDataPoint[bool | None, bool]):
    """
    Implementation of a switch.

    This is a default data point that gets automatically generated.
    """

    _category = DataPointCategory.SWITCH

    @state_property
    def value(self) -> bool | None:
        """Get the value of the data_point."""
        if self._type == ParameterType.ACTION:
            return False
        return cast(bool | None, self._value)

    @inspector()
    async def turn_on(self, collector: CallParameterCollector | None = None, on_time: float | None = None) -> None:
        """Turn the switch on."""
        if on_time is not None:
            await self.set_on_time(on_time=on_time)
        await self.send_value(value=True, collector=collector)

    @inspector()
    async def turn_off(self, collector: CallParameterCollector | None = None) -> None:
        """Turn the switch off."""
        await self.send_value(value=False, collector=collector)

    @inspector()
    async def set_on_time(self, on_time: float) -> None:
        """Set the on time value in seconds."""
        await self._client.set_value(
            channel_address=self._channel.address,
            paramset_key=self._paramset_key,
            parameter=Parameter.ON_TIME,
            value=float(on_time),
        )
