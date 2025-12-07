# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Custom valve data points for heating valve controls.

Public API of this module is defined by __all__.
"""

from __future__ import annotations

import logging
from typing import Any, Final

from aiohomematic.const import DataPointCategory, DeviceProfile, Field
from aiohomematic.model.custom.data_point import CustomDataPoint
from aiohomematic.model.custom.mixins import GroupStateMixin, StateChangeTimerMixin
from aiohomematic.model.custom.registry import DeviceProfileRegistry
from aiohomematic.model.data_point import CallParameterCollector, bind_collector
from aiohomematic.model.generic import DpAction, DpBinarySensor, DpSwitch
from aiohomematic.property_decorators import state_property

_LOGGER: Final = logging.getLogger(__name__)


class CustomDpIpIrrigationValve(StateChangeTimerMixin, GroupStateMixin, CustomDataPoint):
    """Class for Homematic irrigation valve data point."""

    __slots__ = (
        "_dp_group_state",
        "_dp_on_time_value",
        "_dp_state",
    )

    _category = DataPointCategory.VALVE

    @state_property
    def value(self) -> bool | None:
        """Return the current value of the valve."""
        return self._dp_state.value

    @bind_collector
    async def close(self, *, collector: CallParameterCollector | None = None) -> None:
        """Turn the valve off."""
        self.reset_timer_on_time()
        if not self.is_state_change(off=True):
            return
        await self._dp_state.turn_off(collector=collector)

    def is_state_change(self, **kwargs: Any) -> bool:
        """Check if the state changes due to kwargs."""
        if self.is_state_change_for_on_off(**kwargs):
            return True
        return super().is_state_change(**kwargs)

    @bind_collector
    async def open(self, *, on_time: float | None = None, collector: CallParameterCollector | None = None) -> None:
        """Turn the valve on."""
        if on_time is not None:
            self.set_timer_on_time(on_time=on_time)
        if not self.is_state_change(on=True):
            return

        if (timer := self.get_and_start_timer()) is not None:
            await self._dp_on_time_value.send_value(value=timer, collector=collector, do_validate=False)
        await self._dp_state.turn_on(collector=collector)

    def _init_data_point_fields(self) -> None:
        """Initialize the data_point fields."""
        super()._init_data_point_fields()

        self._dp_state: DpSwitch = self._get_data_point(field=Field.STATE, data_point_type=DpSwitch)
        self._dp_on_time_value: DpAction = self._get_data_point(field=Field.ON_TIME_VALUE, data_point_type=DpAction)
        self._dp_group_state: DpBinarySensor = self._get_data_point(
            field=Field.GROUP_STATE, data_point_type=DpBinarySensor
        )


# =============================================================================
# DeviceProfileRegistry Registration
# =============================================================================

# IP Irrigation Valve
DeviceProfileRegistry.register(
    category=DataPointCategory.VALVE,
    models=("ELV-SH-WSM", "HmIP-WSM"),
    data_point_class=CustomDpIpIrrigationValve,
    profile_type=DeviceProfile.IP_IRRIGATION_VALVE,
    channels=(4,),
)
