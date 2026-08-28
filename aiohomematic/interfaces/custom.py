# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Category-specific protocol interfaces for custom data points.

While ``CustomDataPointProtocol`` describes what every custom data point has in
common, consumers that dispatch on *capabilities* instead of on concrete class
identity need a typed surface per category. This module provides that surface:
one base protocol per custom category, each carrying the category's
``capabilities`` dataclass plus the public API shared by every implementation of
that category.

Protocol Hierarchy
------------------

Categories whose capability flags gate an *optional* method surface get a
sub-protocol for that surface, so a consumer can move from ``isinstance`` on a
concrete class to a capability flag without losing its typing basis:

- ``CoverDataPointProtocol``: position + stop (``CoverCapabilities``)
    - ``TiltCoverDataPointProtocol``: adds the tilt surface (``capabilities.tilt``)
    - ``GarageDataPointProtocol``: adds the ventilation surface (``capabilities.vent``)
- ``SirenDataPointProtocol``: on/off, tones, lights (``SirenCapabilities``)
    - ``SoundPlayerDataPointProtocol``: adds the soundfile surface (``capabilities.soundfiles``)
- ``ClimateDataPointProtocol``: ``ClimateCapabilities``
- ``LightDataPointProtocol``: ``LightCapabilities``
- ``LockDataPointProtocol``: ``LockCapabilities``

Climate, light and lock need no sub-protocol: every surface their capability
flags gate is already declared on the category base class.

All protocols are ``@runtime_checkable``, and every category declares members
beyond ``capabilities``, so an ``isinstance`` check discriminates between
categories rather than merely detecting the presence of a ``capabilities``
attribute.
"""

from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol, Unpack, runtime_checkable

from aiohomematic.interfaces.model import CustomDataPointProtocol

if TYPE_CHECKING:
    from datetime import datetime

    from aiohomematic.model.custom.capabilities import (
        ClimateCapabilities,
        CoverCapabilities,
        LightCapabilities,
        LockCapabilities,
        SirenCapabilities,
    )
    from aiohomematic.model.custom.climate import ClimateActivity, ClimateMode, ClimateProfile
    from aiohomematic.model.custom.light import LightOffArgs, LightOnArgs
    from aiohomematic.model.custom.siren import PlaySoundArgs, SirenOnArgs
    from aiohomematic.model.data_point import CallParameterCollector

__all__ = [
    "ClimateDataPointProtocol",
    "CoverDataPointProtocol",
    "GarageDataPointProtocol",
    "LightDataPointProtocol",
    "LockDataPointProtocol",
    "SirenDataPointProtocol",
    "SoundPlayerDataPointProtocol",
    "TiltCoverDataPointProtocol",
]


# =============================================================================
# Climate
# =============================================================================


@runtime_checkable
class ClimateDataPointProtocol(CustomDataPointProtocol, Protocol):
    """
    Protocol for custom climate data points.

    Carries ``ClimateCapabilities`` and the public API shared by all climate
    implementations.
    """

    __slots__ = ()

    @property
    @abstractmethod
    def activity(self) -> ClimateActivity | None:
        """Return the current activity."""

    @property
    @abstractmethod
    def capabilities(self) -> ClimateCapabilities:
        """Return the climate capabilities."""

    @property
    @abstractmethod
    def current_humidity(self) -> int | None:
        """Return the current humidity."""

    @property
    @abstractmethod
    def current_temperature(self) -> float | None:
        """Return the current temperature."""

    @property
    @abstractmethod
    def max_temp(self) -> float:
        """Return the maximum temperature."""

    @property
    @abstractmethod
    def min_max_value_not_relevant_for_manu_mode(self) -> bool:
        """Return if the min/max value is not relevant for the manual mode."""

    @property
    @abstractmethod
    def min_temp(self) -> float:
        """Return the minimum temperature."""

    @property
    @abstractmethod
    def mode(self) -> ClimateMode:
        """Return the current mode."""

    @property
    @abstractmethod
    def modes(self) -> tuple[ClimateMode, ...]:
        """Return the available modes."""

    @property
    @abstractmethod
    def profile(self) -> ClimateProfile:
        """Return the current profile."""

    @property
    @abstractmethod
    def profiles(self) -> tuple[ClimateProfile, ...]:
        """Return the available profiles."""

    @property
    @abstractmethod
    def target_temperature(self) -> float | None:
        """Return the target temperature."""

    @property
    @abstractmethod
    def target_temperature_step(self) -> float:
        """Return the supported step of the target temperature."""

    @property
    @abstractmethod
    def temperature_unit(self) -> str:
        """Return the temperature unit."""

    @abstractmethod
    async def disable_away_mode(self) -> None:
        """Disable the away mode."""

    @abstractmethod
    async def enable_away_mode_by_calendar(self, *, start: datetime, end: datetime, away_temperature: float) -> None:
        """Enable the away mode by calendar."""

    @abstractmethod
    async def enable_away_mode_by_duration(self, *, hours: int, away_temperature: float) -> None:
        """Enable the away mode by duration."""

    @abstractmethod
    async def set_mode(self, *, mode: ClimateMode, collector: CallParameterCollector | None = None) -> None:
        """Set the mode."""

    @abstractmethod
    async def set_profile(self, *, profile: ClimateProfile, collector: CallParameterCollector | None = None) -> None:
        """Set the profile."""

    @abstractmethod
    async def set_temperature(
        self, *, temperature: float, collector: CallParameterCollector | None = None, do_validate: bool = True
    ) -> None:
        """Set the target temperature."""


# =============================================================================
# Cover
# =============================================================================


@runtime_checkable
class CoverDataPointProtocol(CustomDataPointProtocol, Protocol):
    """
    Protocol for custom cover data points.

    Carries ``CoverCapabilities`` and the position/stop surface shared by all
    cover implementations. The tilt and ventilation surfaces live on
    ``TiltCoverDataPointProtocol`` and ``GarageDataPointProtocol``.
    """

    __slots__ = ()

    @property
    @abstractmethod
    def capabilities(self) -> CoverCapabilities:
        """Return the cover capabilities."""

    @property
    @abstractmethod
    def current_position(self) -> int | None:
        """Return the current position of the cover."""

    @property
    @abstractmethod
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""

    @property
    @abstractmethod
    def is_closing(self) -> bool | None:
        """Return if the cover is closing."""

    @property
    @abstractmethod
    def is_opening(self) -> bool | None:
        """Return if the cover is opening."""

    @abstractmethod
    async def close(self, *, collector: CallParameterCollector | None = None) -> None:
        """Close the cover."""

    @abstractmethod
    async def open(self, *, collector: CallParameterCollector | None = None) -> None:
        """Open the cover."""

    @abstractmethod
    async def set_position(
        self,
        *,
        position: int | None = None,
        tilt_position: int | None = None,
        collector: CallParameterCollector | None = None,
    ) -> None:
        """Move the cover to a specific position."""

    @abstractmethod
    async def stop(self, *, collector: CallParameterCollector | None = None) -> None:
        """Stop the cover if in motion."""


@runtime_checkable
class GarageDataPointProtocol(CoverDataPointProtocol, Protocol):
    """
    Protocol for cover data points that support a ventilation position.

    Implemented by covers whose ``capabilities.vent`` is ``True``.
    """

    __slots__ = ()

    @abstractmethod
    async def vent(self, *, collector: CallParameterCollector | None = None) -> None:
        """Move the cover to the ventilation position."""


@runtime_checkable
class TiltCoverDataPointProtocol(CoverDataPointProtocol, Protocol):
    """
    Protocol for cover data points that support tilt control.

    Implemented by covers whose ``capabilities.tilt`` is ``True``.
    """

    __slots__ = ()

    @property
    @abstractmethod
    def current_channel_tilt_position(self) -> int:
        """Return the current channel tilt position of the cover."""

    @property
    @abstractmethod
    def current_tilt_position(self) -> int:
        """Return the current group tilt position of the cover."""

    @abstractmethod
    async def close_tilt(self, *, collector: CallParameterCollector | None = None) -> None:
        """Close the tilt."""

    @abstractmethod
    async def open_tilt(self, *, collector: CallParameterCollector | None = None) -> None:
        """Open the tilt."""

    @abstractmethod
    async def stop_tilt(self, *, collector: CallParameterCollector | None = None) -> None:
        """Stop the tilt if in motion."""


# =============================================================================
# Light
# =============================================================================


@runtime_checkable
class LightDataPointProtocol(CustomDataPointProtocol, Protocol):
    """
    Protocol for custom light data points.

    Carries ``LightCapabilities`` and the public API shared by all light
    implementations. The color and effect surfaces are always declared; whether
    a concrete device exposes them is answered by ``capabilities`` (static) and
    the ``has_*`` properties (runtime, for devices with an operation mode).
    """

    __slots__ = ()

    @property
    @abstractmethod
    def brightness(self) -> int | None:
        """Return the brightness of the light."""

    @property
    @abstractmethod
    def brightness_pct(self) -> int | None:
        """Return the brightness of the light in percent."""

    @property
    @abstractmethod
    def capabilities(self) -> LightCapabilities:
        """Return the light capabilities."""

    @property
    @abstractmethod
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature in kelvin."""

    @property
    @abstractmethod
    def effect(self) -> str | None:
        """Return the current effect."""

    @property
    @abstractmethod
    def effects(self) -> tuple[str, ...] | None:
        """Return the available effects."""

    @property
    @abstractmethod
    def group_brightness(self) -> int | None:
        """Return the group brightness of the light."""

    @property
    @abstractmethod
    def group_brightness_pct(self) -> int | None:
        """Return the group brightness of the light in percent."""

    @property
    @abstractmethod
    def has_color_temperature(self) -> bool:
        """Return if the light currently supports color temperature."""

    @property
    @abstractmethod
    def has_effects(self) -> bool:
        """Return if the light currently supports effects."""

    @property
    @abstractmethod
    def has_hs_color(self) -> bool:
        """Return if the light currently supports hue/saturation color."""

    @property
    @abstractmethod
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation color value."""

    @property
    @abstractmethod
    def is_on(self) -> bool | None:
        """Return if the light is on."""

    @property
    @abstractmethod
    def last_level(self) -> float | None:
        """Return the last level of the light."""

    @abstractmethod
    def set_last_level(self, *, value: float | None) -> None:
        """Set the last level of the light."""

    @abstractmethod
    async def turn_off(
        self, *, collector: CallParameterCollector | None = None, **kwargs: Unpack[LightOffArgs]
    ) -> None:
        """Turn the light off."""

    @abstractmethod
    async def turn_on(self, *, collector: CallParameterCollector | None = None, **kwargs: Unpack[LightOnArgs]) -> None:
        """Turn the light on."""


# =============================================================================
# Lock
# =============================================================================


@runtime_checkable
class LockDataPointProtocol(CustomDataPointProtocol, Protocol):
    """
    Protocol for custom lock data points.

    Carries ``LockCapabilities`` and the public API shared by all lock
    implementations. ``open`` is declared unconditionally; whether the device
    actually supports it is answered by ``capabilities.open``.
    """

    __slots__ = ()

    @property
    @abstractmethod
    def capabilities(self) -> LockCapabilities:
        """Return the lock capabilities."""

    @property
    @abstractmethod
    def is_jammed(self) -> bool:
        """Return if the lock is jammed."""

    @property
    @abstractmethod
    def is_locked(self) -> bool:
        """Return if the lock is locked."""

    @property
    @abstractmethod
    def is_locking(self) -> bool | None:
        """Return if the lock is locking."""

    @property
    @abstractmethod
    def is_unlocking(self) -> bool | None:
        """Return if the lock is unlocking."""

    @abstractmethod
    async def lock(self, *, collector: CallParameterCollector | None = None) -> None:
        """Lock the lock."""

    @abstractmethod
    async def open(self, *, collector: CallParameterCollector | None = None) -> None:
        """Open the lock."""

    @abstractmethod
    async def unlock(self, *, collector: CallParameterCollector | None = None) -> None:
        """Unlock the lock."""


# =============================================================================
# Siren
# =============================================================================


@runtime_checkable
class SirenDataPointProtocol(CustomDataPointProtocol, Protocol):
    """
    Protocol for custom siren data points.

    Carries ``SirenCapabilities`` and the public API shared by all siren
    implementations. The soundfile surface lives on
    ``SoundPlayerDataPointProtocol``.
    """

    __slots__ = ()

    @property
    @abstractmethod
    def available_lights(self) -> tuple[str, ...] | None:
        """Return the available lights."""

    @property
    @abstractmethod
    def available_tones(self) -> tuple[str, ...] | None:
        """Return the available tones."""

    @property
    @abstractmethod
    def capabilities(self) -> SirenCapabilities:
        """Return the siren capabilities."""

    @property
    @abstractmethod
    def is_on(self) -> bool:
        """Return if the siren is on."""

    @abstractmethod
    async def turn_off(self, *, collector: CallParameterCollector | None = None) -> None:
        """Turn the siren off."""

    @abstractmethod
    async def turn_on(self, *, collector: CallParameterCollector | None = None, **kwargs: Unpack[SirenOnArgs]) -> None:
        """Turn the siren on."""


@runtime_checkable
class SoundPlayerDataPointProtocol(SirenDataPointProtocol, Protocol):
    """
    Protocol for siren data points that support soundfile playback.

    Implemented by sirens whose ``capabilities.soundfiles`` is ``True``.
    """

    __slots__ = ()

    @property
    @abstractmethod
    def available_soundfiles(self) -> tuple[str, ...] | None:
        """Return the available soundfiles."""

    @property
    @abstractmethod
    def current_soundfile(self) -> str | None:
        """Return the currently selected soundfile."""

    @abstractmethod
    async def play_sound(
        self, *, collector: CallParameterCollector | None = None, **kwargs: Unpack[PlaySoundArgs]
    ) -> None:
        """Play a soundfile."""

    @abstractmethod
    async def stop_sound(self, *, collector: CallParameterCollector | None = None) -> None:
        """Stop the soundfile playback."""
