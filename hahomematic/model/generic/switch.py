"""Module for data points implemented using the switch category."""

from __future__ import annotations

from typing import Final

from hahomematic.const import DataPointCategory, ParameterType
from hahomematic.decorators import service
from hahomematic.model.data_point import CallParameterCollector
from hahomematic.model.decorators import state_property
from hahomematic.model.generic.data_point import GenericDataPoint

_PARAM_ON_TIME: Final = "ON_TIME"


class DpSwitch(GenericDataPoint[bool | None, bool]):
    """
    Implementation of a switch.

    This is a default data point that gets automatically generated.
    """

    _category = DataPointCategory.SWITCH

    @state_property
    def value(self) -> bool | None:  # type: ignore[override]
        """Get the value of the data_point."""
        if self._type == ParameterType.ACTION:
            return False
        return self._value  # type: ignore[no-any-return]

    @service()
    async def turn_on(self, collector: CallParameterCollector | None = None, on_time: float | None = None) -> None:
        """Turn the switch on."""
        if on_time is not None:
            await self.set_on_time(on_time=on_time)
        await self.send_value(value=True, collector=collector)

    @service()
    async def turn_off(self, collector: CallParameterCollector | None = None) -> None:
        """Turn the switch off."""
        await self.send_value(value=False, collector=collector)

    @service()
    async def set_on_time(self, on_time: float) -> None:
        """Set the on time value in seconds."""
        await self._client.set_value(
            channel_address=self._channel.address,
            paramset_key=self._paramset_key,
            parameter=_PARAM_ON_TIME,
            value=float(on_time),
        )
