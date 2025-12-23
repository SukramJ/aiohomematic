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
from aiohomematic.model.custom.field import DataPointField
from aiohomematic.model.custom.registry import DeviceProfileRegistry
from aiohomematic.model.data_point import CallParameterCollector, bind_collector
from aiohomematic.model.generic import DpAction, DpActionSelect, DpBinarySensor, DpSensor
from aiohomematic.property_decorators import DelegatedProperty, Kind, state_property

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

    __slots__ = ()  # Required to prevent __dict__ creation (descriptors are class-level)

    # Declarative data point field definitions
    _dp_acoustic_alarm_active: Final = DataPointField(field=Field.ACOUSTIC_ALARM_ACTIVE, dpt=DpBinarySensor)
    _dp_acoustic_alarm_selection: Final = DataPointField(field=Field.ACOUSTIC_ALARM_SELECTION, dpt=DpActionSelect)
    _dp_duration: Final = DataPointField(field=Field.DURATION, dpt=DpAction)
    _dp_duration_unit: Final = DataPointField(field=Field.DURATION_UNIT, dpt=DpActionSelect)
    _dp_optical_alarm_active: Final = DataPointField(field=Field.OPTICAL_ALARM_ACTIVE, dpt=DpBinarySensor)
    _dp_optical_alarm_selection: Final = DataPointField(field=Field.OPTICAL_ALARM_SELECTION, dpt=DpActionSelect)

    available_lights: Final = DelegatedProperty[tuple[str, ...] | None](
        path="_dp_optical_alarm_selection.values", kind=Kind.STATE
    )
    available_tones: Final = DelegatedProperty[tuple[str, ...] | None](
        path="_dp_acoustic_alarm_selection.values", kind=Kind.STATE
    )

    @property
    def supports_duration(self) -> bool:
        """Flag if siren supports duration."""
        return True

    @state_property
    def is_on(self) -> bool:
        """Return true if siren is on."""
        return self._dp_acoustic_alarm_active.value is True or self._dp_optical_alarm_active.value is True

    @bind_collector
    async def turn_off(self, *, collector: CallParameterCollector | None = None) -> None:
        """Turn the device off."""
        if (acoustic_default := self._dp_acoustic_alarm_selection.default) is not None:
            await self._dp_acoustic_alarm_selection.send_value(value=acoustic_default, collector=collector)
        if (optical_default := self._dp_optical_alarm_selection.default) is not None:
            await self._dp_optical_alarm_selection.send_value(value=optical_default, collector=collector)
        if (duration_unit_default := self._dp_duration_unit.default) is not None:
            await self._dp_duration_unit.send_value(value=duration_unit_default, collector=collector)
        await self._dp_duration.send_value(value=self._dp_duration.default, collector=collector)

    @bind_collector
    async def turn_on(
        self,
        *,
        collector: CallParameterCollector | None = None,
        **kwargs: Unpack[SirenOnArgs],
    ) -> None:
        """Turn the device on."""
        acoustic_alarm = (
            kwargs.get("acoustic_alarm")
            or self._dp_acoustic_alarm_selection.value
            or self._dp_acoustic_alarm_selection.default
        )
        if self.available_tones and acoustic_alarm and acoustic_alarm not in self.available_tones:
            raise ValidationException(
                i18n.tr(
                    "exception.model.custom.siren.invalid_tone",
                    full_name=self.full_name,
                    value=acoustic_alarm,
                )
            )

        optical_alarm = (
            kwargs.get("optical_alarm")
            or self._dp_optical_alarm_selection.value
            or self._dp_optical_alarm_selection.default
        )
        if self.available_lights and optical_alarm and optical_alarm not in self.available_lights:
            raise ValidationException(
                i18n.tr(
                    "exception.model.custom.siren.invalid_light",
                    full_name=self.full_name,
                    value=optical_alarm,
                )
            )

        if acoustic_alarm is not None:
            await self._dp_acoustic_alarm_selection.send_value(value=acoustic_alarm, collector=collector)
        if optical_alarm is not None:
            await self._dp_optical_alarm_selection.send_value(value=optical_alarm, collector=collector)
        if (duration_unit_default := self._dp_duration_unit.default) is not None:
            await self._dp_duration_unit.send_value(value=duration_unit_default, collector=collector)
        duration = kwargs.get("duration") or self._dp_duration.default
        await self._dp_duration.send_value(value=duration, collector=collector)


class CustomDpIpSirenSmoke(BaseCustomDpSiren):
    """Class for HomematicIP siren smoke data point."""

    __slots__ = ()  # Required to prevent __dict__ creation (descriptors are class-level)

    # Declarative data point field definitions
    _dp_smoke_detector_alarm_status: Final = DataPointField(
        field=Field.SMOKE_DETECTOR_ALARM_STATUS, dpt=DpSensor[str | None]
    )
    _dp_smoke_detector_command: Final = DataPointField(field=Field.SMOKE_DETECTOR_COMMAND, dpt=DpActionSelect)

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
