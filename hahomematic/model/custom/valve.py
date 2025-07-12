"""Module for data points implemented using the valve category."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
import logging
from typing import Any, Final

from hahomematic.const import DataPointCategory
from hahomematic.model import device as hmd
from hahomematic.model.custom import definition as hmed
from hahomematic.model.custom.const import DeviceProfile, Field
from hahomematic.model.custom.data_point import CustomDataPoint
from hahomematic.model.custom.support import CustomConfig
from hahomematic.model.data_point import CallParameterCollector, bind_collector
from hahomematic.model.decorators import state_property
from hahomematic.model.generic import DpAction, DpBinarySensor, DpSwitch
from hahomematic.model.support import TimerMixin

_LOGGER: Final = logging.getLogger(__name__)


class _StateChangeArg(StrEnum):
    """Enum with valve state change arguments."""

    OFF = "off"
    ON = "on"


class CustomDpIpIrrigationValve(CustomDataPoint, TimerMixin):
    """Class for HomeMatic irrigation valve data point."""

    _category = DataPointCategory.VALVE

    def _init_data_point_fields(self) -> None:
        """Init the data_point fields."""
        TimerMixin.__init__(self)
        super()._init_data_point_fields()
        self._dp_state: DpSwitch = self._get_data_point(field=Field.STATE, data_point_type=DpSwitch)
        self._dp_on_time_value: DpAction = self._get_data_point(field=Field.ON_TIME_VALUE, data_point_type=DpAction)
        self._dp_group_state: DpBinarySensor = self._get_data_point(
            field=Field.GROUP_STATE, data_point_type=DpBinarySensor
        )

    @property
    def group_value(self) -> bool | None:
        """Return the current channel value of the valve."""
        return self._dp_group_state.value

    @state_property
    def value(self) -> bool | None:
        """Return the current value of the valve."""
        return self._dp_state.value

    @bind_collector()
    async def open(self, collector: CallParameterCollector | None = None, on_time: float | None = None) -> None:
        """Turn the valve on."""
        if on_time is not None:
            self.set_timer_on_time(on_time=on_time)
        if not self.is_state_change(on=True):
            return

        if (timer := self.get_and_start_timer()) is not None:
            await self._dp_on_time_value.send_value(value=timer, collector=collector, do_validate=False)
        await self._dp_state.turn_on(collector=collector)

    @bind_collector()
    async def close(self, collector: CallParameterCollector | None = None) -> None:
        """Turn the valve off."""
        self.reset_timer_on_time()
        if not self.is_state_change(off=True):
            return
        await self._dp_state.turn_off(collector=collector)

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


def make_ip_irrigation_valve(
    channel: hmd.Channel,
    custom_config: CustomConfig,
) -> None:
    """Create HomematicIP irrigation valve data point."""
    hmed.make_custom_data_point(
        channel=channel,
        data_point_class=CustomDpIpIrrigationValve,
        device_profile=DeviceProfile.IP_IRRIGATION_VALVE,
        custom_config=custom_config,
    )


# Case for device model is not relevant.
# HomeBrew (HB-) devices are always listed as HM-.
DEVICES: Mapping[str, CustomConfig | tuple[CustomConfig, ...]] = {
    "ELV-SH-WSM": CustomConfig(make_ce_func=make_ip_irrigation_valve, channels=(4,)),
    "HmIP-WSM": CustomConfig(make_ce_func=make_ip_irrigation_valve, channels=(4,)),
}
hmed.ALL_DEVICES[DataPointCategory.VALVE] = DEVICES
