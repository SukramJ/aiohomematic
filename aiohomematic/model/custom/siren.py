# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Custom siren data points for alarm and notification devices.

Public API of this module is defined by __all__.
"""

from __future__ import annotations

from abc import abstractmethod
import contextlib
from enum import StrEnum
from typing import Final, TypedDict, Unpack

from aiohomematic import i18n
from aiohomematic.const import DataPointCategory, DeviceProfile, Field
from aiohomematic.exceptions import ValidationException
from aiohomematic.model.custom.data_point import CustomDataPoint
from aiohomematic.model.custom.field import DataPointField
from aiohomematic.model.custom.mixins import TimerUnitMixin
from aiohomematic.model.custom.registry import DeviceProfileRegistry
from aiohomematic.model.data_point import CallParameterCollector, bind_collector
from aiohomematic.model.generic import DpAction, DpActionSelect, DpBinarySensor, DpSelect, DpSensor
from aiohomematic.property_decorators import DelegatedProperty, Kind, state_property

_SMOKE_DETECTOR_ALARM_STATUS_IDLE_OFF: Final = "IDLE_OFF"

# Activity states indicating playback is active
_ACTIVITY_STATES_ACTIVE: Final[frozenset[str]] = frozenset({"UP", "DOWN"})

# Repetitions constants
_NO_REPETITION: Final = "NO_REPETITION"
_INFINITE_REPETITIONS: Final = "INFINITE_REPETITIONS"
_MAX_REPETITIONS: Final = 18


def _convert_repetitions(*, repetitions: int | None) -> str:
    """
    Convert repetitions count to REPETITIONS VALUE_LIST value.

    Args:
        repetitions: Number of repetitions (0=none, 1-18=count, -1=infinite, None=none).

    Returns:
        VALUE_LIST string (NO_REPETITION, REPETITIONS_001-018, or INFINITE_REPETITIONS).

    Raises:
        ValueError: If repetitions is outside valid range (-1 to 18).

    """
    if repetitions is None or repetitions == 0:
        return _NO_REPETITION

    if repetitions == -1:
        return _INFINITE_REPETITIONS

    if repetitions < -1 or repetitions > _MAX_REPETITIONS:
        msg = f"Repetitions must be -1 (infinite), 0 (none), or 1-{_MAX_REPETITIONS}, got {repetitions}"
        raise ValueError(msg)

    return f"REPETITIONS_{repetitions:03d}"


class _SirenCommand(StrEnum):
    """Enum with siren commands."""

    OFF = "INTRUSION_ALARM_OFF"
    ON = "INTRUSION_ALARM"


class SirenOnArgs(TypedDict, total=False):
    """Matcher for the siren arguments."""

    acoustic_alarm: str
    optical_alarm: str
    duration: str


class PlaySoundArgs(TypedDict, total=False):
    """Arguments for play_sound method (comparable to SirenOnArgs)."""

    soundfile: str | int  # Soundfile from available_soundfiles or index (1-189)
    volume: float  # Volume level 0.0-1.0 (default: 0.5)
    on_time: float  # Duration in seconds (auto unit conversion via TimerUnitMixin)
    ramp_time: float  # Ramp time in seconds (auto unit conversion via TimerUnitMixin)
    repetitions: int  # 0=none, 1-18=count, -1=infinite (converted to VALUE_LIST entry)


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
                    key="exception.model.custom.siren.invalid_tone",
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
                    key="exception.model.custom.siren.invalid_light",
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


class CustomDpSoundPlayer(TimerUnitMixin, BaseCustomDpSiren):
    """Class for HomematicIP sound player data point (HmIP-MP3P channel 2)."""

    __slots__ = ()  # Required to prevent __dict__ creation (descriptors are class-level)

    # Declarative data point field definitions for sound channel
    # Map on_time to DURATION_VALUE/UNIT for TimerUnitMixin compatibility (no Final for overrides)
    _dp_level: Final = DataPointField(field=Field.LEVEL, dpt=DpAction)
    _dp_on_time_value = DataPointField(field=Field.DURATION_VALUE, dpt=DpAction)
    _dp_on_time_unit = DataPointField(field=Field.DURATION_UNIT, dpt=DpActionSelect)
    _dp_ramp_time_value = DataPointField(field=Field.RAMP_TIME_VALUE, dpt=DpAction)
    _dp_ramp_time_unit = DataPointField(field=Field.RAMP_TIME_UNIT, dpt=DpActionSelect)
    _dp_soundfile: Final = DataPointField(field=Field.SOUNDFILE, dpt=DpSelect)
    _dp_repetitions: Final = DataPointField(field=Field.REPETITIONS, dpt=DpActionSelect)
    _dp_direction: Final = DataPointField(field=Field.DIRECTION, dpt=DpSensor[str | None])

    # Expose available options via DelegatedProperty (from ActionSelect VALUE_LISTs)
    @staticmethod
    def _convert_soundfile_index(index: int) -> str:
        """Convert integer index to soundfile name."""
        if index < 1 or index > 189:
            raise ValueError(i18n.tr(key="exception.model.custom.siren.invalid_soundfile_index", index=index))
        return f"SOUNDFILE_{index:03d}"

    available_soundfiles: Final = DelegatedProperty[tuple[str, ...] | None](
        path="_dp_soundfile.values", kind=Kind.STATE
    )

    @property
    def supports_duration(self) -> bool:
        """Flag if siren supports duration."""
        return True

    @state_property
    def available_lights(self) -> tuple[str, ...] | None:
        """Return available lights (not supported for sound player)."""
        return None

    @state_property
    def available_tones(self) -> tuple[str, ...] | None:
        """Return available tones (soundfiles for sound player)."""
        return self.available_soundfiles

    @state_property
    def current_soundfile(self) -> str | None:
        """Return currently selected soundfile."""
        if (value := self._dp_soundfile.value) is None:
            return None
        return str(value)

    @state_property
    def is_on(self) -> bool:
        """Return true if sound is currently playing."""
        activity = self._dp_direction.value
        return activity is not None and activity in _ACTIVITY_STATES_ACTIVE

    @state_property
    def supports_soundfiles(self) -> bool:
        """Return true if device supports soundfile selection."""
        return self.available_soundfiles is not None

    @bind_collector
    async def play_sound(
        self,
        *,
        collector: CallParameterCollector | None = None,
        **kwargs: Unpack[PlaySoundArgs],
    ) -> None:
        """
        Play a sound file on the device.

        API is comparable to other siren classes, using on_time/ramp_time in seconds
        with automatic unit conversion via TimerUnitMixin.

        Args:
            collector: Optional call parameter collector.
            **kwargs: Sound parameters from PlaySoundArgs:
                soundfile: Soundfile from available_soundfiles or index (1-189).
                volume: Volume level 0.0-1.0 (default: 0.5).
                on_time: Duration in seconds (auto unit conversion, default: 10).
                ramp_time: Ramp time in seconds (auto unit conversion, default: 0).
                repetitions: 0=none, 1-18=count, -1=infinite (converted to VALUE_LIST).

        """
        soundfile = kwargs.get("soundfile", "INTERNAL_SOUNDFILE")
        volume = kwargs.get("volume", 0.5)
        on_time = kwargs.get("on_time", 10.0)
        ramp_time = kwargs.get("ramp_time", 0.0)
        repetitions_value = _convert_repetitions(repetitions=kwargs.get("repetitions"))

        # Convert integer to soundfile name if needed
        if isinstance(soundfile, int):
            soundfile = self._convert_soundfile_index(soundfile)

        # Validate volume
        if not 0.0 <= volume <= 1.0:
            raise ValidationException(
                i18n.tr(
                    key="exception.model.custom.siren.invalid_volume",
                    full_name=self.full_name,
                    value=volume,
                )
            )

        # Validate soundfile against available options
        if self.available_soundfiles and soundfile not in self.available_soundfiles:
            raise ValidationException(
                i18n.tr(
                    key="exception.model.custom.siren.invalid_soundfile",
                    full_name=self.full_name,
                    value=soundfile,
                )
            )

        # Send parameters - order matters for batching
        await self._dp_level.send_value(value=volume, collector=collector)
        await self._dp_soundfile.send_value(value=soundfile, collector=collector)
        await self._dp_repetitions.send_value(value=repetitions_value, collector=collector)
        # Use mixin methods for automatic unit conversion
        await self._set_ramp_time_on_value(ramp_time=ramp_time, collector=collector)
        await self._set_on_time_value(on_time=on_time, collector=collector)

    @bind_collector
    async def stop_sound(
        self,
        *,
        collector: CallParameterCollector | None = None,
    ) -> None:
        """Stop current sound playback."""
        await self._dp_level.send_value(value=0.0, collector=collector)
        await self._dp_on_time_value.send_value(value=0, collector=collector)

    @bind_collector
    async def turn_off(self, *, collector: CallParameterCollector | None = None) -> None:
        """Turn the device off."""
        await self.stop_sound(collector=collector)

    @bind_collector
    async def turn_on(
        self,
        *,
        collector: CallParameterCollector | None = None,
        **kwargs: Unpack[SirenOnArgs],
    ) -> None:
        """Turn the device on."""
        # Map SirenOnArgs to PlaySoundArgs
        play_kwargs: PlaySoundArgs = {}
        if "acoustic_alarm" in kwargs:
            play_kwargs["soundfile"] = kwargs["acoustic_alarm"]
        if "duration" in kwargs:
            # Duration in SirenOnArgs is a string, try to parse as float (seconds)
            with contextlib.suppress(ValueError, TypeError):
                play_kwargs["on_time"] = float(kwargs["duration"])
        await self.play_sound(collector=collector, **play_kwargs)


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

# HmIP-MP3P Sound Player (channel 2)
DeviceProfileRegistry.register(
    category=DataPointCategory.SIREN,
    models="HmIP-MP3P",
    data_point_class=CustomDpSoundPlayer,
    profile_type=DeviceProfile.IP_SOUND_PLAYER,
    channels=(2,),
)
