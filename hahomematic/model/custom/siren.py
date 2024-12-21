"""Module for data points implemented using the siren category."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Mapping
from enum import StrEnum
from typing import Final, TypedDict, Unpack

from hahomematic.const import DataPointCategory
from hahomematic.model import device as hmd
from hahomematic.model.custom import definition as hmed
from hahomematic.model.custom.const import DeviceProfile, Field
from hahomematic.model.custom.data_point import CustomDataPoint
from hahomematic.model.custom.support import CustomConfig
from hahomematic.model.data_point import CallParameterCollector, bind_collector
from hahomematic.model.decorators import state_property
from hahomematic.model.generic import DpAction, DpBinarySensor, DpSensor

_SMOKE_DETECTOR_ALARM_STATUS_IDLE_OFF: Final = "IDLE_OFF"


class _SirenCommand(StrEnum):
    """Enum with siren commands."""

    OFF = "INTRUSION_ALARM_OFF"
    ON = "INTRUSION_ALARM"


class SirenOnArgs(TypedDict, total=False):
    """Matcher for the siren arguments."""

    acoustic_alarm: str
    optical_alarm: str
    duration: str


class BaseCustomDpSiren(CustomDataPoint):
    """Class for HomeMatic siren data point."""

    _category = DataPointCategory.SIREN

    @state_property
    @abstractmethod
    def is_on(self) -> bool:
        """Return true if siren is on."""

    @state_property
    @abstractmethod
    def available_tones(self) -> tuple[str, ...] | None:
        """Return available tones."""

    @state_property
    @abstractmethod
    def available_lights(self) -> tuple[str, ...] | None:
        """Return available lights."""

    @property
    @abstractmethod
    def supports_duration(self) -> bool:
        """Flag if siren supports duration."""

    @property
    def supports_tones(self) -> bool:
        """Flag if siren supports tones."""
        return self.available_tones is not None

    @property
    def supports_lights(self) -> bool:
        """Flag if siren supports lights."""
        return self.available_lights is not None

    @abstractmethod
    @bind_collector()
    async def turn_on(
        self,
        collector: CallParameterCollector | None = None,
        **kwargs: Unpack[SirenOnArgs],
    ) -> None:
        """Turn the device on."""

    @abstractmethod
    @bind_collector()
    async def turn_off(self, collector: CallParameterCollector | None = None) -> None:
        """Turn the device off."""


class CustomDpIpSiren(BaseCustomDpSiren):
    """Class for HomematicIP siren data point."""

    def _init_data_point_fields(self) -> None:
        """Init the data_point fields."""
        super()._init_data_point_fields()
        self._dp_acoustic_alarm_active: DpBinarySensor = self._get_data_point(
            field=Field.ACOUSTIC_ALARM_ACTIVE, data_point_type=DpBinarySensor
        )
        self._dp_acoustic_alarm_selection: DpAction = self._get_data_point(
            field=Field.ACOUSTIC_ALARM_SELECTION, data_point_type=DpAction
        )
        self._dp_optical_alarm_active: DpBinarySensor = self._get_data_point(
            field=Field.OPTICAL_ALARM_ACTIVE, data_point_type=DpBinarySensor
        )
        self._dp_optical_alarm_selection: DpAction = self._get_data_point(
            field=Field.OPTICAL_ALARM_SELECTION, data_point_type=DpAction
        )
        self._dp_duration: DpAction = self._get_data_point(field=Field.DURATION, data_point_type=DpAction)
        self._dp_duration_unit: DpAction = self._get_data_point(field=Field.DURATION_UNIT, data_point_type=DpAction)

    @state_property
    def is_on(self) -> bool:
        """Return true if siren is on."""
        return self._dp_acoustic_alarm_active.value is True or self._dp_optical_alarm_active.value is True

    @state_property
    def available_tones(self) -> tuple[str, ...] | None:
        """Return available tones."""
        return self._dp_acoustic_alarm_selection.values

    @state_property
    def available_lights(self) -> tuple[str, ...] | None:
        """Return available lights."""
        return self._dp_optical_alarm_selection.values

    @property
    def supports_duration(self) -> bool:
        """Flag if siren supports duration."""
        return True

    @bind_collector()
    async def turn_on(
        self,
        collector: CallParameterCollector | None = None,
        **kwargs: Unpack[SirenOnArgs],
    ) -> None:
        """Turn the device on."""

        acoustic_alarm = kwargs.get("acoustic_alarm", self._dp_acoustic_alarm_selection.default)
        if self.available_tones and acoustic_alarm and acoustic_alarm not in self.available_tones:
            raise ValueError(
                f"Invalid tone specified for data_point {self.full_name}: {acoustic_alarm}, "
                "check the available_tones attribute for valid tones to pass in"
            )

        optical_alarm = kwargs.get("optical_alarm", self._dp_optical_alarm_selection.default)
        if self.available_lights and optical_alarm and optical_alarm not in self.available_lights:
            raise ValueError(
                f"Invalid light specified for data_point {self.full_name}: {optical_alarm}, "
                "check the available_lights attribute for valid tones to pass in"
            )

        await self._dp_acoustic_alarm_selection.send_value(value=acoustic_alarm, collector=collector)
        await self._dp_optical_alarm_selection.send_value(value=optical_alarm, collector=collector)
        await self._dp_duration_unit.send_value(value=self._dp_duration_unit.default, collector=collector)
        duration = kwargs.get("duration", self._dp_duration.default)
        await self._dp_duration.send_value(value=duration, collector=collector)

    @bind_collector()
    async def turn_off(self, collector: CallParameterCollector | None = None) -> None:
        """Turn the device off."""
        await self._dp_acoustic_alarm_selection.send_value(
            value=self._dp_acoustic_alarm_selection.default, collector=collector
        )
        await self._dp_optical_alarm_selection.send_value(
            value=self._dp_optical_alarm_selection.default, collector=collector
        )
        await self._dp_duration_unit.send_value(value=self._dp_duration_unit.default, collector=collector)
        await self._dp_duration.send_value(value=self._dp_duration.default, collector=collector)


class CustomDpIpSirenSmoke(BaseCustomDpSiren):
    """Class for HomematicIP siren smoke data point."""

    def _init_data_point_fields(self) -> None:
        """Init the data_point fields."""
        super()._init_data_point_fields()
        self._dp_smoke_detector_alarm_status: DpSensor[str | None] = self._get_data_point(
            field=Field.SMOKE_DETECTOR_ALARM_STATUS, data_point_type=DpSensor[str | None]
        )
        self._dp_smoke_detector_command: DpAction = self._get_data_point(
            field=Field.SMOKE_DETECTOR_COMMAND, data_point_type=DpAction
        )

    @state_property
    def is_on(self) -> bool:
        """Return true if siren is on."""
        if not self._dp_smoke_detector_alarm_status.value:
            return False
        return bool(self._dp_smoke_detector_alarm_status.value != _SMOKE_DETECTOR_ALARM_STATUS_IDLE_OFF)

    @state_property
    def available_tones(self) -> tuple[str, ...] | None:
        """Return available tones."""
        return None

    @state_property
    def available_lights(self) -> tuple[str, ...] | None:
        """Return available lights."""
        return None

    @property
    def supports_duration(self) -> bool:
        """Flag if siren supports duration."""
        return False

    @bind_collector()
    async def turn_on(
        self,
        collector: CallParameterCollector | None = None,
        **kwargs: Unpack[SirenOnArgs],
    ) -> None:
        """Turn the device on."""
        await self._dp_smoke_detector_command.send_value(value=_SirenCommand.ON, collector=collector)

    @bind_collector()
    async def turn_off(self, collector: CallParameterCollector | None = None) -> None:
        """Turn the device off."""
        await self._dp_smoke_detector_command.send_value(value=_SirenCommand.OFF, collector=collector)


def make_ip_siren(
    channel: hmd.Channel,
    custom_config: CustomConfig,
) -> None:
    """Create HomematicIP siren data point."""
    hmed.make_custom_data_point(
        channel=channel,
        data_point_class=CustomDpIpSiren,
        device_profile=DeviceProfile.IP_SIREN,
        custom_config=custom_config,
    )


def make_ip_siren_smoke(
    channel: hmd.Channel,
    custom_config: CustomConfig,
) -> None:
    """Create HomematicIP siren data point."""
    hmed.make_custom_data_point(
        channel=channel,
        data_point_class=CustomDpIpSirenSmoke,
        device_profile=DeviceProfile.IP_SIREN_SMOKE,
        custom_config=custom_config,
    )


# Case for device model is not relevant.
# HomeBrew (HB-) devices are always listed as HM-.
DEVICES: Mapping[str, CustomConfig | tuple[CustomConfig, ...]] = {
    "HmIP-ASIR": CustomConfig(make_ce_func=make_ip_siren, channels=(3,)),
    "HmIP-SWSD": CustomConfig(make_ce_func=make_ip_siren_smoke),
}
hmed.ALL_DEVICES[DataPointCategory.SIREN] = DEVICES
