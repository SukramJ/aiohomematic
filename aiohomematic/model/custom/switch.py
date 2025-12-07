# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Custom switch data points for advanced switching devices.

Public API of this module is defined by __all__.
"""

from __future__ import annotations

import logging
from typing import Any, Final

from aiohomematic.const import DataPointCategory, DeviceProfile, Field, Parameter
from aiohomematic.model.custom.data_point import CustomDataPoint
from aiohomematic.model.custom.mixins import GroupStateMixin, StateChangeTimerMixin
from aiohomematic.model.custom.registry import DeviceProfileRegistry, ExtendedDeviceConfig
from aiohomematic.model.data_point import CallParameterCollector, bind_collector
from aiohomematic.model.generic import DpAction, DpBinarySensor, DpSwitch
from aiohomematic.property_decorators import state_property

_LOGGER: Final = logging.getLogger(__name__)


class CustomDpSwitch(StateChangeTimerMixin, GroupStateMixin, CustomDataPoint):
    """Class for Homematic switch data point."""

    __slots__ = (
        "_dp_group_state",
        "_dp_on_time_value",
        "_dp_state",
    )

    _category = DataPointCategory.SWITCH

    @state_property
    def value(self) -> bool | None:
        """Return the current channel value of the switch."""
        return self._dp_state.value

    def is_state_change(self, **kwargs: Any) -> bool:
        """Check if the state changes due to kwargs."""
        if self.is_state_change_for_on_off(**kwargs):
            return True
        return super().is_state_change(**kwargs)

    @bind_collector
    async def turn_off(self, *, collector: CallParameterCollector | None = None) -> None:
        """Turn the switch off."""
        self.reset_timer_on_time()
        if not self.is_state_change(off=True):
            return
        await self._dp_state.turn_off(collector=collector)

    @bind_collector
    async def turn_on(self, *, on_time: float | None = None, collector: CallParameterCollector | None = None) -> None:
        """Turn the switch on."""
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

# IP Switch (various channel configurations)
DeviceProfileRegistry.register(
    category=DataPointCategory.SWITCH,
    models=("ELV-SH-BS2", "HmIP-BS2", "HmIP-PCBS2"),
    data_point_class=CustomDpSwitch,
    profile_type=DeviceProfile.IP_SWITCH,
    channels=(4, 8),
)
DeviceProfileRegistry.register(
    category=DataPointCategory.SWITCH,
    models=(
        "ELV-SH-PSMCI",
        "ELV-SH-SW1-BAT",
        "HmIP-DRSI1",
        "HmIP-FSI",
        "HmIP-PCBS",
        "HmIP-PCBS-BAT",
        "HmIP-PS",
        "HmIP-USBSM",
        "HmIP-WGC",
    ),
    data_point_class=CustomDpSwitch,
    profile_type=DeviceProfile.IP_SWITCH,
    channels=(3,),
)
DeviceProfileRegistry.register(
    category=DataPointCategory.SWITCH,
    models=("HmIP-BSL", "HmIP-BSM"),
    data_point_class=CustomDpSwitch,
    profile_type=DeviceProfile.IP_SWITCH,
    channels=(4,),
)
DeviceProfileRegistry.register(
    category=DataPointCategory.SWITCH,
    models="HmIP-DRSI4",
    data_point_class=CustomDpSwitch,
    profile_type=DeviceProfile.IP_SWITCH,
    channels=(6, 10, 14, 18),
)
DeviceProfileRegistry.register(
    category=DataPointCategory.SWITCH,
    models="HmIP-FSM",
    data_point_class=CustomDpSwitch,
    profile_type=DeviceProfile.IP_SWITCH,
    channels=(2,),
)
DeviceProfileRegistry.register(
    category=DataPointCategory.SWITCH,
    models="HmIP-MOD-OC8",
    data_point_class=CustomDpSwitch,
    profile_type=DeviceProfile.IP_SWITCH,
    channels=(10, 14, 18, 22, 26, 30, 34, 38),
)
DeviceProfileRegistry.register(
    category=DataPointCategory.SWITCH,
    models="HmIP-SCTH230",
    data_point_class=CustomDpSwitch,
    profile_type=DeviceProfile.IP_SWITCH,
    channels=(8,),
)
DeviceProfileRegistry.register(
    category=DataPointCategory.SWITCH,
    models="HmIP-WGT",
    data_point_class=CustomDpSwitch,
    profile_type=DeviceProfile.IP_SWITCH,
    channels=(4,),
)
DeviceProfileRegistry.register(
    category=DataPointCategory.SWITCH,
    models="HmIP-WHS2",
    data_point_class=CustomDpSwitch,
    profile_type=DeviceProfile.IP_SWITCH,
    channels=(2, 6),
)
DeviceProfileRegistry.register(
    category=DataPointCategory.SWITCH,
    models="HmIPW-DRS",
    data_point_class=CustomDpSwitch,
    profile_type=DeviceProfile.IP_SWITCH,
    channels=(2, 6, 10, 14, 18, 22, 26, 30),
)
DeviceProfileRegistry.register(
    category=DataPointCategory.SWITCH,
    models="HmIPW-FIO6",
    data_point_class=CustomDpSwitch,
    profile_type=DeviceProfile.IP_SWITCH,
    channels=(8, 12, 16, 20, 24, 28),
)

# HmIP-SMO230 (Switch with motion sensor)
DeviceProfileRegistry.register(
    category=DataPointCategory.SWITCH,
    models="HmIP-SMO230",
    data_point_class=CustomDpSwitch,
    profile_type=DeviceProfile.IP_SWITCH,
    channels=(10,),
    extended=ExtendedDeviceConfig(
        additional_data_points={
            1: (
                Parameter.ILLUMINATION,
                Parameter.MOTION,
                Parameter.MOTION_DETECTION_ACTIVE,
                Parameter.RESET_MOTION,
            ),
            2: (
                Parameter.ILLUMINATION,
                Parameter.MOTION,
                Parameter.MOTION_DETECTION_ACTIVE,
                Parameter.RESET_MOTION,
            ),
            3: (
                Parameter.ILLUMINATION,
                Parameter.MOTION,
                Parameter.MOTION_DETECTION_ACTIVE,
                Parameter.RESET_MOTION,
            ),
            4: (
                Parameter.ILLUMINATION,
                Parameter.MOTION,
                Parameter.MOTION_DETECTION_ACTIVE,
                Parameter.RESET_MOTION,
            ),
        }
    ),
)
