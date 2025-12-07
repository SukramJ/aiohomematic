# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Custom siren data points for alarm and notification devices.

Public API of this module is defined by __all__.
"""

from __future__ import annotations

from abc import abstractmethod
from enum import StrEnum
from typing import Final, TypedDict, Unpack

from aiohomematic import i18n
from aiohomematic.const import DataPointCategory, DeviceProfile, Field
from aiohomematic.exceptions import ValidationException
from aiohomematic.model.custom.data_point import CustomDataPoint
from aiohomematic.model.custom.registry import DeviceProfileRegistry
from aiohomematic.model.data_point import CallParameterCollector, bind_collector
from aiohomematic.model.generic import DpAction, DpBinarySensor, DpSensor
from aiohomematic.property_decorators import state_property

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
    """Class for Homematic siren data point."""

    __slots__ = ()

    _category = DataPointCategory.SIREN

    @property
    @abstractmethod
    def supports_duration(self) -> bool:
        """Flag if siren supports duration."""

    @property
    def supports_lights(self) -> bool:
        """Flag if siren supports lights."""
        return self.available_lights is not None

    @property
    def supports_tones(self) -> bool:
        """Flag if siren supports tones."""
        return self.available_tones is not None

    @state_property
    @abstractmethod
    def available_lights(self) -> tuple[str, ...] | None:
        """Return available lights."""

    @state_property
    @abstractmethod
    def available_tones(self) -> tuple[str, ...] | None:
        """Return available tones."""

    @state_property
    @abstractmethod
    def is_on(self) -> bool:
        """Return true if siren is on."""

    @abstractmethod
    @bind_collector
    async def turn_off(self, *, collector: CallParameterCollector | None = None) -> None:
        """Turn the device off."""

    @abstractmethod
    @bind_collector
    async def turn_on(
        self,
        *,
        collector: CallParameterCollector | None = None,
        **kwargs: Unpack[SirenOnArgs],
    ) -> None:
        """Turn the device on."""


class CustomDpIpSiren(BaseCustomDpSiren):
    """Class for HomematicIP siren data point."""

    __slots__ = (
        "_dp_acoustic_alarm_active",
        "_dp_acoustic_alarm_selection",
        "_dp_duration",
        "_dp_duration_unit",
        "_dp_optical_alarm_active",
        "_dp_optical_alarm_selection",
    )

    @property
    def supports_duration(self) -> bool:
        """Flag if siren supports duration."""
        return True

    @state_property
    def available_lights(self) -> tuple[str, ...] | None:
        """Return available lights."""
        return self._dp_optical_alarm_selection.values

    @state_property
    def available_tones(self) -> tuple[str, ...] | None:
        """Return available tones."""
        return self._dp_acoustic_alarm_selection.values

    @state_property
    def is_on(self) -> bool:
        """Return true if siren is on."""
        return self._dp_acoustic_alarm_active.value is True or self._dp_optical_alarm_active.value is True

    @bind_collector
    async def turn_off(self, *, collector: CallParameterCollector | None = None) -> None:
        """Turn the device off."""
        await self._dp_acoustic_alarm_selection.send_value(
            value=self._dp_acoustic_alarm_selection.default, collector=collector
        )
        await self._dp_optical_alarm_selection.send_value(
            value=self._dp_optical_alarm_selection.default, collector=collector
        )
        await self._dp_duration_unit.send_value(value=self._dp_duration_unit.default, collector=collector)
        await self._dp_duration.send_value(value=self._dp_duration.default, collector=collector)

    @bind_collector
    async def turn_on(
        self,
        *,
        collector: CallParameterCollector | None = None,
        **kwargs: Unpack[SirenOnArgs],
    ) -> None:
        """Turn the device on."""
        acoustic_alarm = kwargs.get("acoustic_alarm", self._dp_acoustic_alarm_selection.default)
        if self.available_tones and acoustic_alarm and acoustic_alarm not in self.available_tones:
            raise ValidationException(
                i18n.tr(
                    "exception.model.custom.siren.invalid_tone",
                    full_name=self.full_name,
                    value=acoustic_alarm,
                )
            )

        optical_alarm = kwargs.get("optical_alarm", self._dp_optical_alarm_selection.default)
        if self.available_lights and optical_alarm and optical_alarm not in self.available_lights:
            raise ValidationException(
                i18n.tr(
                    "exception.model.custom.siren.invalid_light",
                    full_name=self.full_name,
                    value=optical_alarm,
                )
            )

        await self._dp_acoustic_alarm_selection.send_value(value=acoustic_alarm, collector=collector)
        await self._dp_optical_alarm_selection.send_value(value=optical_alarm, collector=collector)
        await self._dp_duration_unit.send_value(value=self._dp_duration_unit.default, collector=collector)
        duration = kwargs.get("duration", self._dp_duration.default)
        await self._dp_duration.send_value(value=duration, collector=collector)

    def _init_data_point_fields(self) -> None:
        """Initialize the data_point fields."""
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


class CustomDpIpSirenSmoke(BaseCustomDpSiren):
    """Class for HomematicIP siren smoke data point."""

    __slots__ = (
        "_dp_smoke_detector_alarm_status",
        "_dp_smoke_detector_command",
    )

    @property
    def supports_duration(self) -> bool:
        """Flag if siren supports duration."""
        return False

    @state_property
    def available_lights(self) -> tuple[str, ...] | None:
        """Return available lights."""
        return None

    @state_property
    def available_tones(self) -> tuple[str, ...] | None:
        """Return available tones."""
        return None

    @state_property
    def is_on(self) -> bool:
        """Return true if siren is on."""
        if not self._dp_smoke_detector_alarm_status.value:
            return False
        return bool(self._dp_smoke_detector_alarm_status.value != _SMOKE_DETECTOR_ALARM_STATUS_IDLE_OFF)

    @bind_collector
    async def turn_off(self, *, collector: CallParameterCollector | None = None) -> None:
        """Turn the device off."""
        await self._dp_smoke_detector_command.send_value(value=_SirenCommand.OFF, collector=collector)

    @bind_collector
    async def turn_on(
        self,
        *,
        collector: CallParameterCollector | None = None,
        **kwargs: Unpack[SirenOnArgs],
    ) -> None:
        """Turn the device on."""
        await self._dp_smoke_detector_command.send_value(value=_SirenCommand.ON, collector=collector)

    def _init_data_point_fields(self) -> None:
        """Initialize the data_point fields."""
        super()._init_data_point_fields()

        self._dp_smoke_detector_alarm_status: DpSensor[str | None] = self._get_data_point(
            field=Field.SMOKE_DETECTOR_ALARM_STATUS, data_point_type=DpSensor[str | None]
        )
        self._dp_smoke_detector_command: DpAction = self._get_data_point(
            field=Field.SMOKE_DETECTOR_COMMAND, data_point_type=DpAction
        )


# =============================================================================
# DeviceProfileRegistry Registration
# =============================================================================

# IP Siren
DeviceProfileRegistry.register(
    category=DataPointCategory.SIREN,
    models="HmIP-ASIR",
    data_point_class=CustomDpIpSiren,
    profile_type=DeviceProfile.IP_SIREN,
    channels=(3,),
)

# IP Siren Smoke
DeviceProfileRegistry.register(
    category=DataPointCategory.SIREN,
    models="HmIP-SWSD",
    data_point_class=CustomDpIpSirenSmoke,
    profile_type=DeviceProfile.IP_SIREN_SMOKE,
)
