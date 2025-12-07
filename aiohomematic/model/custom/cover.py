# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Custom cover data points for blinds, shutters, and garage doors.

Public API of this module is defined by __all__.
"""

from __future__ import annotations

import asyncio
from enum import IntEnum, StrEnum
import logging
from typing import Any, Final

from aiohomematic.const import DataPointCategory, DataPointUsage, DeviceProfile, Field, Parameter
from aiohomematic.converter import convert_hm_level_to_cpv
from aiohomematic.model.custom.data_point import CustomDataPoint
from aiohomematic.model.custom.mixins import PositionMixin
from aiohomematic.model.custom.registry import DeviceProfileRegistry, ExtendedDeviceConfig
from aiohomematic.model.data_point import CallParameterCollector, bind_collector
from aiohomematic.model.generic import DpAction, DpFloat, DpSelect, DpSensor
from aiohomematic.property_decorators import state_property

_LOGGER: Final = logging.getLogger(__name__)

# Timeout for acquiring the per-instance command processing lock to avoid
# potential deadlocks or indefinite serialization if an awaited call inside
# the critical section stalls.
_COMMAND_LOCK_TIMEOUT: Final[float] = 5.0

_CLOSED_LEVEL: Final = 0.0
_COVER_VENT_MAX_POSITION: Final = 50
_LEVEL_TO_POSITION_MULTIPLIER: Final = 100.0
_MAX_LEVEL_POSITION: Final = 100.0
_MIN_LEVEL_POSITION: Final = 0.0
_OPEN_LEVEL: Final = 1.0
_OPEN_TILT_LEVEL: Final = 1.0
_WD_CLOSED_LEVEL: Final = -0.005


class _CoverActivity(StrEnum):
    """Enum with cover activities."""

    CLOSING = "DOWN"
    OPENING = "UP"


class _CoverPosition(IntEnum):
    """Enum with cover positions."""

    OPEN = 100
    VENT = 10
    CLOSED = 0


class _GarageDoorActivity(IntEnum):
    """Enum with garage door commands."""

    CLOSING = 5
    OPENING = 2


class _GarageDoorCommand(StrEnum):
    """Enum with garage door commands."""

    CLOSE = "CLOSE"
    NOP = "NOP"
    OPEN = "OPEN"
    PARTIAL_OPEN = "PARTIAL_OPEN"
    STOP = "STOP"


class _GarageDoorState(StrEnum):
    """Enum with garage door states."""

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    VENTILATION_POSITION = "VENTILATION_POSITION"
    POSITION_UNKNOWN = "_POSITION_UNKNOWN"


class _StateChangeArg(StrEnum):
    """Enum with cover state change arguments."""

    CLOSE = "close"
    OPEN = "open"
    POSITION = "position"
    TILT_CLOSE = "tilt_close"
    TILT_OPEN = "tilt_open"
    TILT_POSITION = "tilt_position"
    VENT = "vent"


class CustomDpCover(PositionMixin, CustomDataPoint):
    """Class for Homematic cover data point."""

    __slots__ = (
        "_command_processing_lock",
        "_dp_direction",
        "_dp_group_level",
        "_dp_level",
        "_dp_stop",
        "_use_group_channel_for_cover_state",
    )
    _category = DataPointCategory.COVER
    _closed_level: float = _CLOSED_LEVEL
    _closed_position: int = int(_CLOSED_LEVEL * _LEVEL_TO_POSITION_MULTIPLIER)
    _open_level: float = _OPEN_LEVEL

    @property
    def _group_level(self) -> float:
        """Return the channel level of the cover."""
        if (
            self._use_group_channel_for_cover_state
            and self._dp_group_level.value is not None
            and self.usage == DataPointUsage.CDP_PRIMARY
        ):
            return float(self._dp_group_level.value)
        return self._dp_level.value if self._dp_level.value is not None else self._closed_level

    @state_property
    def current_channel_position(self) -> int:
        """Return current channel position of cover."""
        return self.level_to_position(self._dp_level.value) or self._closed_position

    @state_property
    def current_position(self) -> int:
        """Return current group position of cover."""
        return self.level_to_position(self._group_level) or self._closed_position

    @state_property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        return self._group_level == self._closed_level

    @state_property
    def is_closing(self) -> bool | None:
        """Return if the cover is closing."""
        if self._dp_direction.value is not None:
            return str(self._dp_direction.value) == _CoverActivity.CLOSING
        return None

    @state_property
    def is_opening(self) -> bool | None:
        """Return if the cover is opening."""
        if self._dp_direction.value is not None:
            return str(self._dp_direction.value) == _CoverActivity.OPENING
        return None

    @bind_collector
    async def close(self, *, collector: CallParameterCollector | None = None) -> None:
        """Close the cover."""
        if not self.is_state_change(close=True):
            return
        await self._set_level(level=self._closed_level, collector=collector)

    def is_state_change(self, **kwargs: Any) -> bool:
        """Check if the state changes due to kwargs."""
        if kwargs.get(_StateChangeArg.OPEN) is not None and self._group_level != self._open_level:
            return True
        if kwargs.get(_StateChangeArg.CLOSE) is not None and self._group_level != self._closed_level:
            return True
        if (position := kwargs.get(_StateChangeArg.POSITION)) is not None and position != self.current_position:
            return True
        return super().is_state_change(**kwargs)

    @bind_collector
    async def open(self, *, collector: CallParameterCollector | None = None) -> None:
        """Open the cover."""
        if not self.is_state_change(open=True):
            return
        await self._set_level(level=self._open_level, collector=collector)

    @bind_collector
    async def set_position(
        self,
        *,
        position: int | None = None,
        tilt_position: int | None = None,
        collector: CallParameterCollector | None = None,
    ) -> None:
        """Move the cover to a specific position."""
        if not self.is_state_change(position=position):
            return
        level = (
            self.position_to_level(int(min(_MAX_LEVEL_POSITION, max(_MIN_LEVEL_POSITION, position))))
            if position is not None
            else None
        )
        await self._set_level(level=level, collector=collector)

    @bind_collector(enabled=False)
    async def stop(self, *, collector: CallParameterCollector | None = None) -> None:
        """Stop the device if in motion."""
        await self._dp_stop.send_value(value=True, collector=collector)

    def _init_data_point_fields(self) -> None:
        """Initialize the data point fields."""
        super()._init_data_point_fields()

        self._command_processing_lock = asyncio.Lock()
        self._dp_direction: DpSensor[str | None] = self._get_data_point(
            field=Field.DIRECTION, data_point_type=DpSensor[str | None]
        )
        self._dp_level: DpFloat = self._get_data_point(field=Field.LEVEL, data_point_type=DpFloat)
        self._dp_stop: DpAction = self._get_data_point(field=Field.STOP, data_point_type=DpAction)
        self._dp_group_level: DpSensor[float | None] = self._get_data_point(
            field=Field.GROUP_LEVEL, data_point_type=DpSensor[float | None]
        )
        self._use_group_channel_for_cover_state = self._device.config_provider.config.use_group_channel_for_cover_state

    async def _set_level(
        self,
        *,
        level: float | None = None,
        tilt_level: float | None = None,
        collector: CallParameterCollector | None = None,
    ) -> None:
        """Move the cover to a specific position. Value range is 0.0 to 1.01."""
        if level is None:
            return
        await self._dp_level.send_value(value=level, collector=collector)


class CustomDpWindowDrive(CustomDpCover):
    """Class for Homematic window drive."""

    __slots__ = ()

    _closed_level: float = _WD_CLOSED_LEVEL
    _open_level: float = _OPEN_LEVEL

    @state_property
    def current_position(self) -> int:
        """Return current position of cover."""
        level = self._dp_level.value if self._dp_level.value is not None else self._closed_level
        if level == _WD_CLOSED_LEVEL:
            level = _CLOSED_LEVEL
        elif level == _CLOSED_LEVEL:
            level = 0.01
        return self.level_to_position(level) or self._closed_position

    async def _set_level(
        self,
        *,
        level: float | None = None,
        tilt_level: float | None = None,
        collector: CallParameterCollector | None = None,
    ) -> None:
        """Move the window drive to a specific position. Value range is -0.005 to 1.01."""
        if level is None:
            return

        if level == _CLOSED_LEVEL:
            wd_level = _WD_CLOSED_LEVEL
        elif _CLOSED_LEVEL < level <= 0.01:
            wd_level = 0
        else:
            wd_level = level
        await self._dp_level.send_value(value=wd_level, collector=collector, do_validate=False)


class CustomDpBlind(CustomDpCover):
    """Class for Homematic blind data point."""

    __slots__ = (
        "_dp_combined",
        "_dp_group_level_2",
        "_dp_level_2",
    )
    _open_tilt_level: float = _OPEN_TILT_LEVEL

    @property
    def _group_tilt_level(self) -> float:
        """Return the group level of the tilt."""
        if (
            self._use_group_channel_for_cover_state
            and self._dp_group_level_2.value is not None
            and self.usage == DataPointUsage.CDP_PRIMARY
        ):
            return float(self._dp_group_level_2.value)
        return self._dp_level_2.value if self._dp_level_2.value is not None else self._closed_level

    @property
    def _target_level(self) -> float | None:
        """Return the level of last service call."""
        if (last_value_send := self._dp_level.unconfirmed_last_value_send) is not None:
            return float(last_value_send)
        return None

    @property
    def _target_tilt_level(self) -> float | None:
        """Return the tilt level of last service call."""
        if (last_value_send := self._dp_level_2.unconfirmed_last_value_send) is not None:
            return float(last_value_send)
        return None

    @state_property
    def current_channel_tilt_position(self) -> int:
        """Return current channel_tilt position of cover."""
        return self.level_to_position(self._dp_level_2.value) or self._closed_position

    @state_property
    def current_tilt_position(self) -> int:
        """Return current tilt position of cover."""
        return self.level_to_position(self._group_tilt_level) or self._closed_position

    @bind_collector(enabled=False)
    async def close(self, *, collector: CallParameterCollector | None = None) -> None:
        """Close the cover and close the tilt."""
        if not self.is_state_change(close=True, tilt_close=True):
            return
        await self._set_level(
            level=self._closed_level,
            tilt_level=self._closed_level,
            collector=collector,
        )

    @bind_collector(enabled=False)
    async def close_tilt(self, *, collector: CallParameterCollector | None = None) -> None:
        """Close the tilt."""
        if not self.is_state_change(tilt_close=True):
            return
        await self._set_level(tilt_level=self._closed_level, collector=collector)

    def is_state_change(self, **kwargs: Any) -> bool:
        """Check if the state changes due to kwargs."""
        if (
            tilt_position := kwargs.get(_StateChangeArg.TILT_POSITION)
        ) is not None and tilt_position != self.current_tilt_position:
            return True
        if kwargs.get(_StateChangeArg.TILT_OPEN) is not None and self.current_tilt_position != _CoverPosition.OPEN:
            return True
        if kwargs.get(_StateChangeArg.TILT_CLOSE) is not None and self.current_tilt_position != _CoverPosition.CLOSED:
            return True
        return super().is_state_change(**kwargs)

    @bind_collector(enabled=False)
    async def open(self, *, collector: CallParameterCollector | None = None) -> None:
        """Open the cover and open the tilt."""
        if not self.is_state_change(open=True, tilt_open=True):
            return
        await self._set_level(
            level=self._open_level,
            tilt_level=self._open_tilt_level,
            collector=collector,
        )

    @bind_collector(enabled=False)
    async def open_tilt(self, *, collector: CallParameterCollector | None = None) -> None:
        """Open the tilt."""
        if not self.is_state_change(tilt_open=True):
            return
        await self._set_level(tilt_level=self._open_tilt_level, collector=collector)

    @bind_collector(enabled=False)
    async def set_position(
        self,
        *,
        position: int | None = None,
        tilt_position: int | None = None,
        collector: CallParameterCollector | None = None,
    ) -> None:
        """Move the blind to a specific position."""
        if not self.is_state_change(position=position, tilt_position=tilt_position):
            return
        level = (
            self.position_to_level(int(min(_MAX_LEVEL_POSITION, max(_MIN_LEVEL_POSITION, position))))
            if position is not None
            else None
        )
        tilt_level = (
            self.position_to_level(int(min(_MAX_LEVEL_POSITION, max(_MIN_LEVEL_POSITION, tilt_position))))
            if tilt_position is not None
            else None
        )
        await self._set_level(level=level, tilt_level=tilt_level, collector=collector)

    @bind_collector(enabled=False)
    async def stop(self, *, collector: CallParameterCollector | None = None) -> None:
        """Stop the device if in motion."""
        try:
            acquired: bool = await asyncio.wait_for(
                self._command_processing_lock.acquire(), timeout=_COMMAND_LOCK_TIMEOUT
            )
        except TimeoutError:
            acquired = False
            _LOGGER.warning(  # i18n-log: ignore
                "%s: command lock acquisition timed out; proceeding without lock", self
            )
        try:
            await self._stop(collector=collector)
        finally:
            if acquired:
                self._command_processing_lock.release()

    @bind_collector(enabled=False)
    async def stop_tilt(self, *, collector: CallParameterCollector | None = None) -> None:
        """Stop the device if in motion. Use only when command_processing_lock is held."""
        await self.stop(collector=collector)

    def _get_combined_value(self, *, level: float | None = None, tilt_level: float | None = None) -> str | None:
        """Return the combined parameter."""
        if level is None and tilt_level is None:
            return None
        levels: list[str] = []
        # the resulting hex value is based on the doubled position
        if level is not None:
            levels.append(convert_hm_level_to_cpv(value=level))
        if tilt_level is not None:
            levels.append(convert_hm_level_to_cpv(value=tilt_level))

        if levels:
            return ",".join(levels)
        return None

    def _init_data_point_fields(self) -> None:
        """Initialize the data point fields."""
        super()._init_data_point_fields()

        self._dp_group_level_2: DpSensor[float | None] = self._get_data_point(
            field=Field.GROUP_LEVEL_2, data_point_type=DpSensor[float | None]
        )
        self._dp_level_2: DpFloat = self._get_data_point(field=Field.LEVEL_2, data_point_type=DpFloat)
        self._dp_combined: DpAction = self._get_data_point(field=Field.LEVEL_COMBINED, data_point_type=DpAction)

    @bind_collector
    async def _send_level(
        self,
        *,
        level: float,
        tilt_level: float,
        collector: CallParameterCollector | None = None,
    ) -> None:
        """Transmit a new target level to the device."""
        if self._dp_combined.is_hmtype and (
            combined_parameter := self._get_combined_value(level=level, tilt_level=tilt_level)
        ):
            # don't use collector for blind combined parameter
            await self._dp_combined.send_value(value=combined_parameter, collector=None)
            return

        await self._dp_level_2.send_value(value=tilt_level, collector=collector)
        await super()._set_level(level=level, collector=collector)

    async def _set_level(
        self,
        *,
        level: float | None = None,
        tilt_level: float | None = None,
        collector: CallParameterCollector | None = None,
    ) -> None:
        """
        Move the cover to a specific tilt level. Value range is 0.0 to 1.00.

        level or tilt_level may be set to None for no change.
        """
        currently_moving = False

        try:
            acquired: bool = await asyncio.wait_for(
                self._command_processing_lock.acquire(), timeout=_COMMAND_LOCK_TIMEOUT
            )
        except TimeoutError:
            acquired = False
            _LOGGER.warning(  # i18n-log: ignore
                "%s: command lock acquisition timed out; proceeding without lock", self
            )

        try:
            if level is not None:
                _level = level
            elif self._target_level is not None:
                # The blind moves and the target blind height is known
                currently_moving = True
                _level = self._target_level
            else:  # The blind is at a standstill and no level is explicitly requested => we remain at the current level
                _level = self._group_level

            if tilt_level is not None:
                _tilt_level = tilt_level
            elif self._target_tilt_level is not None:
                # The blind moves and the target slat position is known
                currently_moving = True
                _tilt_level = self._target_tilt_level
            else:  # The blind is at a standstill and no tilt is explicitly desired => we remain at the current angle
                _tilt_level = self._group_tilt_level

            if currently_moving:
                # Blind actors are buggy when sending new coordinates while they are moving. So we stop them first.
                await self._stop()

            await self._send_level(level=_level, tilt_level=_tilt_level, collector=collector)
        finally:
            if acquired:
                self._command_processing_lock.release()

    @bind_collector(enabled=False)
    async def _stop(self, *, collector: CallParameterCollector | None = None) -> None:
        """Stop the device if in motion. Do only call with _command_processing_lock held."""
        await super().stop(collector=collector)


class CustomDpIpBlind(CustomDpBlind):
    """Class for HomematicIP blind data point."""

    __slots__ = ("_dp_operation_mode",)

    @property
    def operation_mode(self) -> str | None:
        """Return operation mode of cover."""
        val = self._dp_operation_mode.value
        return val if isinstance(val, str) else None

    def _get_combined_value(self, *, level: float | None = None, tilt_level: float | None = None) -> str | None:
        """Return the combined parameter."""
        if level is None and tilt_level is None:
            return None
        levels: list[str] = []
        if (tilt_pos := self.level_to_position(tilt_level)) is not None:
            levels.append(f"L2={tilt_pos}")
        if (level_pos := self.level_to_position(level)) is not None:
            levels.append(f"L={level_pos}")

        if levels:
            return ",".join(levels)
        return None

    def _init_data_point_fields(self) -> None:
        """Initialize the data point fields."""
        super()._init_data_point_fields()

        self._dp_operation_mode: DpSelect = self._get_data_point(field=Field.OPERATION_MODE, data_point_type=DpSelect)
        self._dp_combined: DpAction = self._get_data_point(field=Field.COMBINED_PARAMETER, data_point_type=DpAction)


class CustomDpGarage(PositionMixin, CustomDataPoint):
    """Class for Homematic garage data point."""

    __slots__ = (
        "_dp_door_command",
        "_dp_door_state",
        "_dp_section",
    )
    _category = DataPointCategory.COVER

    @state_property
    def current_position(self) -> int | None:
        """Return current position of the garage door ."""
        if self._dp_door_state.value == _GarageDoorState.OPEN:
            return _CoverPosition.OPEN
        if self._dp_door_state.value == _GarageDoorState.VENTILATION_POSITION:
            return _CoverPosition.VENT
        if self._dp_door_state.value == _GarageDoorState.CLOSED:
            return _CoverPosition.CLOSED
        return None

    @state_property
    def is_closed(self) -> bool | None:
        """Return if the garage door is closed."""
        if self._dp_door_state.value is not None:
            return str(self._dp_door_state.value) == _GarageDoorState.CLOSED
        return None

    @state_property
    def is_closing(self) -> bool | None:
        """Return if the garage door is closing."""
        if self._dp_section.value is not None:
            return int(self._dp_section.value) == _GarageDoorActivity.CLOSING
        return None

    @state_property
    def is_opening(self) -> bool | None:
        """Return if the garage door is opening."""
        if self._dp_section.value is not None:
            return int(self._dp_section.value) == _GarageDoorActivity.OPENING
        return None

    @bind_collector
    async def close(self, *, collector: CallParameterCollector | None = None) -> None:
        """Close the garage door."""
        if not self.is_state_change(close=True):
            return
        await self._dp_door_command.send_value(value=_GarageDoorCommand.CLOSE, collector=collector)

    def is_state_change(self, **kwargs: Any) -> bool:
        """Check if the state changes due to kwargs."""
        if kwargs.get(_StateChangeArg.OPEN) is not None and self.current_position != _CoverPosition.OPEN:
            return True
        if kwargs.get(_StateChangeArg.VENT) is not None and self.current_position != _CoverPosition.VENT:
            return True
        if kwargs.get(_StateChangeArg.CLOSE) is not None and self.current_position != _CoverPosition.CLOSED:
            return True
        return super().is_state_change(**kwargs)

    @bind_collector
    async def open(self, *, collector: CallParameterCollector | None = None) -> None:
        """Open the garage door."""
        if not self.is_state_change(open=True):
            return
        await self._dp_door_command.send_value(value=_GarageDoorCommand.OPEN, collector=collector)

    @bind_collector
    async def set_position(
        self,
        *,
        position: int | None = None,
        tilt_position: int | None = None,
        collector: CallParameterCollector | None = None,
    ) -> None:
        """Move the garage door to a specific position."""
        if position is None:
            return
        if _COVER_VENT_MAX_POSITION < position <= _CoverPosition.OPEN:
            await self.open(collector=collector)
        if _CoverPosition.VENT < position <= _COVER_VENT_MAX_POSITION:
            await self.vent(collector=collector)
        if _CoverPosition.CLOSED <= position <= _CoverPosition.VENT:
            await self.close(collector=collector)

    @bind_collector(enabled=False)
    async def stop(self, *, collector: CallParameterCollector | None = None) -> None:
        """Stop the device if in motion."""
        await self._dp_door_command.send_value(value=_GarageDoorCommand.STOP, collector=collector)

    @bind_collector
    async def vent(self, *, collector: CallParameterCollector | None = None) -> None:
        """Move the garage door to vent position."""
        if not self.is_state_change(vent=True):
            return
        await self._dp_door_command.send_value(value=_GarageDoorCommand.PARTIAL_OPEN, collector=collector)

    def _init_data_point_fields(self) -> None:
        """Initialize the data point fields."""
        super()._init_data_point_fields()

        self._dp_door_state: DpSensor[str | None] = self._get_data_point(
            field=Field.DOOR_STATE, data_point_type=DpSensor[str | None]
        )
        self._dp_door_command: DpAction = self._get_data_point(field=Field.DOOR_COMMAND, data_point_type=DpAction)
        self._dp_section: DpSensor[str | None] = self._get_data_point(
            field=Field.SECTION, data_point_type=DpSensor[str | None]
        )


# =============================================================================
# DeviceProfileRegistry Registration
# =============================================================================

# RF Cover
DeviceProfileRegistry.register(
    category=DataPointCategory.COVER,
    models=(
        "263 146",
        "263 147",
        "HM-LC-Bl1-Velux",
        "HM-LC-Bl1-FM",
        "HM-LC-Bl1-FM-2",
        "HM-LC-Bl1-PB-FM",
        "HM-LC-Bl1-SM",
        "HM-LC-Bl1-SM-2",
        "HM-LC-Bl1PBU-FM",
        "HM-LC-BlX",
        "ZEL STG RM FEP 230V",
    ),
    data_point_class=CustomDpCover,
    profile_type=DeviceProfile.RF_COVER,
)
DeviceProfileRegistry.register(
    category=DataPointCategory.COVER,
    models="HMW-LC-Bl1",
    data_point_class=CustomDpCover,
    profile_type=DeviceProfile.RF_COVER,
    channels=(3,),
)

# RF Blind
DeviceProfileRegistry.register(
    category=DataPointCategory.COVER,
    models=("HM-LC-Ja1PBU-FM", "HM-LC-JaX"),
    data_point_class=CustomDpBlind,
    profile_type=DeviceProfile.RF_COVER,
)

# RF Window Drive
DeviceProfileRegistry.register(
    category=DataPointCategory.COVER,
    models="HM-Sec-Win",
    data_point_class=CustomDpWindowDrive,
    profile_type=DeviceProfile.RF_COVER,
    channels=(1,),
    extended=ExtendedDeviceConfig(
        additional_data_points={
            1: (Parameter.DIRECTION, Parameter.WORKING, Parameter.ERROR),
            2: (Parameter.LEVEL, Parameter.STATUS),
        }
    ),
)

# IP Cover
DeviceProfileRegistry.register(
    category=DataPointCategory.COVER,
    models=("HmIP-BROLL", "HmIP-FROLL"),
    data_point_class=CustomDpCover,
    profile_type=DeviceProfile.IP_COVER,
    channels=(4,),
)

# IP Blind
DeviceProfileRegistry.register(
    category=DataPointCategory.COVER,
    models=("HmIP-BBL", "HmIP-FBL"),
    data_point_class=CustomDpIpBlind,
    profile_type=DeviceProfile.IP_COVER,
    channels=(4,),
)
DeviceProfileRegistry.register(
    category=DataPointCategory.COVER,
    models="HmIP-DRBLI4",
    data_point_class=CustomDpIpBlind,
    profile_type=DeviceProfile.IP_COVER,
    channels=(10, 14, 18, 22),
)
DeviceProfileRegistry.register(
    category=DataPointCategory.COVER,
    models="HmIPW-DRBL4",
    data_point_class=CustomDpIpBlind,
    profile_type=DeviceProfile.IP_COVER,
    channels=(2, 6, 10, 14),
)

# IP HDM
DeviceProfileRegistry.register(
    category=DataPointCategory.COVER,
    models="HmIP-HDM",
    data_point_class=CustomDpIpBlind,
    profile_type=DeviceProfile.IP_HDM,
)

# IP Garage
DeviceProfileRegistry.register(
    category=DataPointCategory.COVER,
    models=("HmIP-MOD-HO", "HmIP-MOD-TM"),
    data_point_class=CustomDpGarage,
    profile_type=DeviceProfile.IP_GARAGE,
)
