# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Module for data points implemented using the switch category."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
import logging
from typing import Any, Final

from aiohomematic.const import DataPointCategory, DeviceProfile, Field, Parameter
from aiohomematic.model import device as hmd
from aiohomematic.model.custom import definition as hmed
from aiohomematic.model.custom.data_point import CustomDataPoint
from aiohomematic.model.custom.support import CustomConfig, ExtendedConfig
from aiohomematic.model.data_point import CallParameterCollector, bind_collector
from aiohomematic.model.generic import DpAction, DpBinarySensor, DpSwitch
from aiohomematic.property_decorators import state_property

_LOGGER: Final = logging.getLogger(__name__)


class _StateChangeArg(StrEnum):
    """Enum with switch state change arguments."""

    OFF = "off"
    ON = "on"


class CustomDpSwitch(CustomDataPoint):
    """Class for Homematic switch data point."""

    __slots__ = (
        "_dp_group_state",
        "_dp_on_time_value",
        "_dp_state",
    )

    _category = DataPointCategory.SWITCH

    @property
    def group_value(self) -> bool | None:
        """Return the current group value of the switch."""
        return self._dp_group_state.value

    @state_property
    def value(self) -> bool | None:
        """Return the current channel value of the switch."""
        return self._dp_state.value

    def is_state_change(self, **kwargs: Any) -> bool:
        """Check if the state changes due to kwargs."""
        if (on_time_running := self.timer_on_time_running) is not None and on_time_running is True:
            return True
        if self.timer_on_time is not None:
            return True
        if kwargs.get(_StateChangeArg.ON) is not None and self.value is not True:
            return True
        if kwargs.get(_StateChangeArg.OFF) is not None and self.value is not False:
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
        """Init the data_point fields."""
        super()._init_data_point_fields()

        self._dp_state: DpSwitch = self._get_data_point(field=Field.STATE, data_point_type=DpSwitch)
        self._dp_on_time_value: DpAction = self._get_data_point(field=Field.ON_TIME_VALUE, data_point_type=DpAction)
        self._dp_group_state: DpBinarySensor = self._get_data_point(
            field=Field.GROUP_STATE, data_point_type=DpBinarySensor
        )


def make_ip_switch(
    *,
    channel: hmd.Channel,
    custom_config: CustomConfig,
) -> None:
    """Create HomematicIP switch data point."""
    hmed.make_custom_data_point(
        channel=channel,
        data_point_class=CustomDpSwitch,
        device_profile=DeviceProfile.IP_SWITCH,
        custom_config=custom_config,
    )


# Case for device model is not relevant.
# HomeBrew (HB-) devices are always listed as HM-.
DEVICES: Mapping[str, CustomConfig | tuple[CustomConfig, ...]] = {
    "ELV-SH-BS2": CustomConfig(make_ce_func=make_ip_switch, channels=(4, 8)),
    "ELV-SH-PSMCI": CustomConfig(make_ce_func=make_ip_switch, channels=(3,)),
    "ELV-SH-SW1-BAT": CustomConfig(make_ce_func=make_ip_switch, channels=(3,)),
    "HmIP-BS2": CustomConfig(make_ce_func=make_ip_switch, channels=(4, 8)),
    "HmIP-BSL": CustomConfig(make_ce_func=make_ip_switch, channels=(4,)),
    "HmIP-BSM": CustomConfig(make_ce_func=make_ip_switch, channels=(4,)),
    "HmIP-DRSI1": CustomConfig(
        make_ce_func=make_ip_switch,
        channels=(3,),
    ),
    "HmIP-DRSI4": CustomConfig(
        make_ce_func=make_ip_switch,
        channels=(6, 10, 14, 18),
    ),
    "HmIP-FSI": CustomConfig(make_ce_func=make_ip_switch, channels=(3,)),
    "HmIP-FSM": CustomConfig(make_ce_func=make_ip_switch, channels=(2,)),
    "HmIP-MOD-OC8": CustomConfig(make_ce_func=make_ip_switch, channels=(10, 14, 18, 22, 26, 30, 34, 38)),
    "HmIP-PCBS": CustomConfig(make_ce_func=make_ip_switch, channels=(3,)),
    "HmIP-PCBS-BAT": CustomConfig(make_ce_func=make_ip_switch, channels=(3,)),
    "HmIP-PCBS2": CustomConfig(make_ce_func=make_ip_switch, channels=(4, 8)),
    "HmIP-PS": CustomConfig(make_ce_func=make_ip_switch, channels=(3,)),
    "HmIP-SCTH230": CustomConfig(make_ce_func=make_ip_switch, channels=(8,)),
    "HmIP-SMO230": CustomConfig(
        make_ce_func=make_ip_switch,
        channels=(10,),
        extended=ExtendedConfig(
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
    ),
    "HmIP-USBSM": CustomConfig(make_ce_func=make_ip_switch, channels=(3,)),
    "HmIP-WGC": CustomConfig(make_ce_func=make_ip_switch, channels=(3,)),
    "HmIP-WGT": CustomConfig(make_ce_func=make_ip_switch, channels=(4,)),
    "HmIP-WHS2": CustomConfig(make_ce_func=make_ip_switch, channels=(2, 6)),
    "HmIPW-DRS": CustomConfig(
        make_ce_func=make_ip_switch,
        channels=(2, 6, 10, 14, 18, 22, 26, 30),
    ),
    "HmIPW-FIO6": CustomConfig(make_ce_func=make_ip_switch, channels=(8, 12, 16, 20, 24, 28)),
}

hmed.ALL_DEVICES[DataPointCategory.SWITCH] = DEVICES
