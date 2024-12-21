"""Module for data points implemented using the cover category."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from enum import IntEnum, StrEnum
import logging
from typing import Any, Final

from hahomematic.const import DataPointCategory, DataPointUsage, Parameter
from hahomematic.converter import convert_hm_level_to_cpv
from hahomematic.model import device as hmd
from hahomematic.model.custom import definition as hmed
from hahomematic.model.custom.const import DeviceProfile, Field
from hahomematic.model.custom.data_point import CustomDataPoint
from hahomematic.model.custom.support import CustomConfig, ExtendedConfig
from hahomematic.model.data_point import CallParameterCollector, bind_collector
from hahomematic.model.decorators import state_property
from hahomematic.model.generic import DpAction, DpFloat, DpSelect, DpSensor

_LOGGER: Final = logging.getLogger(__name__)

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


class CustomDpCover(CustomDataPoint):
    """Class for HomeMatic cover data point."""

    _category = DataPointCategory.COVER
    _closed_level: float = _CLOSED_LEVEL
    _open_level: float = _OPEN_LEVEL

    def _init_data_point_fields(self) -> None:
        """Init the data point fields."""
        super()._init_data_point_fields()
        self._command_processing_lock = asyncio.Lock()
        self._dp_direction: DpSensor[str | None] = self._get_data_point(
            field=Field.DIRECTION, data_point_type=DpSensor[str | None]
        )
        self._dp_level: DpFloat = self._get_data_point(field=Field.LEVEL, data_point_type=DpFloat)
        self._dp_stop: DpAction = self._get_data_point(field=Field.STOP, data_point_type=DpAction)
        self._dp_channel_level: DpSensor[float | None] = self._get_data_point(
            field=Field.CHANNEL_LEVEL, data_point_type=DpSensor[float | None]
        )

    @property
    def _channel_level(self) -> float:
        """Return the channel level of the cover."""
        if self._dp_channel_level.value is not None and self.usage == DataPointUsage.CDP_PRIMARY:
            return float(self._dp_channel_level.value)
        return self._dp_level.value if self._dp_level.value is not None else self._closed_level

    @state_property
    def current_position(self) -> int:
        """Return current position of cover."""
        return int(self._channel_level * _LEVEL_TO_POSITION_MULTIPLIER)

    @bind_collector()
    async def set_position(
        self,
        position: int | None = None,
        tilt_position: int | None = None,
        collector: CallParameterCollector | None = None,
    ) -> None:
        """Move the cover to a specific position."""
        if not self.is_state_change(position=position):
            return
        level = (
            min(_MAX_LEVEL_POSITION, max(_MIN_LEVEL_POSITION, position)) / _MAX_LEVEL_POSITION
            if position is not None
            else None
        )
        await self._set_level(level=level, collector=collector)

    async def _set_level(
        self,
        level: float | None = None,
        tilt_level: float | None = None,
        collector: CallParameterCollector | None = None,
    ) -> None:
        """Move the cover to a specific position. Value range is 0.0 to 1.01."""
        if level is None:
            return
        await self._dp_level.send_value(value=level, collector=collector)

    @state_property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        return self._channel_level == self._closed_level

    @state_property
    def is_opening(self) -> bool | None:
        """Return if the cover is opening."""
        if self._dp_direction.value is not None:
            return str(self._dp_direction.value) == _CoverActivity.OPENING
        return None

    @state_property
    def is_closing(self) -> bool | None:
        """Return if the cover is closing."""
        if self._dp_direction.value is not None:
            return str(self._dp_direction.value) == _CoverActivity.CLOSING
        return None

    @bind_collector()
    async def open(self, collector: CallParameterCollector | None = None) -> None:
        """Open the cover."""
        if not self.is_state_change(open=True):
            return
        await self._set_level(level=self._open_level, collector=collector)

    @bind_collector()
    async def close(self, collector: CallParameterCollector | None = None) -> None:
        """Close the cover."""
        if not self.is_state_change(close=True):
            return
        await self._set_level(level=self._closed_level, collector=collector)

    @bind_collector(enabled=False)
    async def stop(self, collector: CallParameterCollector | None = None) -> None:
        """Stop the device if in motion."""
        await self._dp_stop.send_value(value=True, collector=collector)

    def is_state_change(self, **kwargs: Any) -> bool:
        """Check if the state changes due to kwargs."""
        if kwargs.get(_StateChangeArg.OPEN) is not None and self._channel_level != self._open_level:
            return True
        if kwargs.get(_StateChangeArg.CLOSE) is not None and self._channel_level != self._closed_level:
            return True
        if (position := kwargs.get(_StateChangeArg.POSITION)) is not None and position != self.current_position:
            return True
        return super().is_state_change(**kwargs)


class CustomDpWindowDrive(CustomDpCover):
    """Class for Homematic window drive."""

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
        return int(level * _LEVEL_TO_POSITION_MULTIPLIER)

    async def _set_level(
        self,
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
    """Class for HomeMatic blind data point."""

    _open_tilt_level: float = _OPEN_TILT_LEVEL

    def _init_data_point_fields(self) -> None:
        """Init the data point fields."""
        super()._init_data_point_fields()
        self._dp_channel_level_2: DpSensor[float | None] = self._get_data_point(
            field=Field.CHANNEL_LEVEL_2, data_point_type=DpSensor[float | None]
        )
        self._dp_level_2: DpFloat = self._get_data_point(field=Field.LEVEL_2, data_point_type=DpFloat)
        self._dp_combined: DpAction = self._get_data_point(field=Field.LEVEL_COMBINED, data_point_type=DpAction)

    @property
    def _channel_tilt_level(self) -> float:
        """Return the channel level of the tilt."""
        if self._dp_channel_level_2.value is not None and self.usage == DataPointUsage.CDP_PRIMARY:
            return float(self._dp_channel_level_2.value)
        return self._dp_level_2.value if self._dp_level_2.value is not None else self._closed_level

    @state_property
    def current_tilt_position(self) -> int:
        """Return current tilt position of cover."""
        return int(self._channel_tilt_level * _LEVEL_TO_POSITION_MULTIPLIER)

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

    @bind_collector(enabled=False)
    async def set_position(
        self,
        position: int | None = None,
        tilt_position: int | None = None,
        collector: CallParameterCollector | None = None,
    ) -> None:
        """Move the blind to a specific position."""
        if not self.is_state_change(position=position, tilt_position=tilt_position):
            return
        level = (
            min(_MAX_LEVEL_POSITION, max(_MIN_LEVEL_POSITION, position)) / _MAX_LEVEL_POSITION
            if position is not None
            else None
        )
        tilt_level = (
            min(_MAX_LEVEL_POSITION, max(_MIN_LEVEL_POSITION, tilt_position)) / _MAX_LEVEL_POSITION
            if tilt_position is not None
            else None
        )
        await self._set_level(level=level, tilt_level=tilt_level, collector=collector)

    async def _set_level(
        self,
        level: float | None = None,
        tilt_level: float | None = None,
        collector: CallParameterCollector | None = None,
    ) -> None:
        """
        Move the cover to a specific tilt level. Value range is 0.0 to 1.00.

        level or tilt_level may be set to None for no change.
        """
        currently_moving = False

        async with self._command_processing_lock:
            if level is not None:
                _level = level
            elif self._target_level is not None:
                # The blind moves and the target blind height is known
                currently_moving = True
                _level = self._target_level
            else:  # The blind is at a standstill and no level is explicitly requested => we remain at the current level
                _level = self._channel_level

            if tilt_level is not None:
                _tilt_level = tilt_level
            elif self._target_tilt_level is not None:
                # The blind moves and the target slat position is known
                currently_moving = True
                _tilt_level = self._target_tilt_level
            else:  # The blind is at a standstill and no tilt is explicitly desired => we remain at the current angle
                _tilt_level = self._channel_tilt_level

            if currently_moving:
                # Blind actors are buggy when sending new coordinates while they are moving. So we stop them first.
                await self._stop()

            await self._send_level(level=_level, tilt_level=_tilt_level, collector=collector)

    @bind_collector()
    async def _send_level(
        self,
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

    @bind_collector(enabled=False)
    async def open(self, collector: CallParameterCollector | None = None) -> None:
        """Open the cover and open the tilt."""
        if not self.is_state_change(open=True, tilt_open=True):
            return
        await self._set_level(
            level=self._open_level,
            tilt_level=self._open_tilt_level,
            collector=collector,
        )

    @bind_collector(enabled=False)
    async def close(self, collector: CallParameterCollector | None = None) -> None:
        """Close the cover and close the tilt."""
        if not self.is_state_change(close=True, tilt_close=True):
            return
        await self._set_level(
            level=self._closed_level,
            tilt_level=self._closed_level,
            collector=collector,
        )

    @bind_collector(enabled=False)
    async def stop(self, collector: CallParameterCollector | None = None) -> None:
        """Stop the device if in motion."""
        async with self._command_processing_lock:
            await self._stop(collector=collector)

    @bind_collector(enabled=False)
    async def _stop(self, collector: CallParameterCollector | None = None) -> None:
        """Stop the device if in motion. Do only call with _command_processing_lock held."""
        await super().stop(collector=collector)

    @bind_collector(enabled=False)
    async def open_tilt(self, collector: CallParameterCollector | None = None) -> None:
        """Open the tilt."""
        if not self.is_state_change(tilt_open=True):
            return
        await self._set_level(tilt_level=self._open_tilt_level, collector=collector)

    @bind_collector(enabled=False)
    async def close_tilt(self, collector: CallParameterCollector | None = None) -> None:
        """Close the tilt."""
        if not self.is_state_change(tilt_close=True):
            return
        await self._set_level(tilt_level=self._closed_level, collector=collector)

    @bind_collector(enabled=False)
    async def stop_tilt(self, collector: CallParameterCollector | None = None) -> None:
        """Stop the device if in motion. Use only when command_processing_lock is held."""
        await self.stop(collector=collector)

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

    def _get_combined_value(self, level: float | None = None, tilt_level: float | None = None) -> str | None:
        """Return the combined parameter."""
        if level is None and tilt_level is None:
            return None
        levels: list[str] = []
        # the resulting hex value is based on the doubled position
        if level is not None:
            levels.append(convert_hm_level_to_cpv(hm_level=level))
        if tilt_level is not None:
            levels.append(convert_hm_level_to_cpv(hm_level=tilt_level))

        if levels:
            return ",".join(levels)
        return None


class CustomDpIpBlind(CustomDpBlind):
    """Class for HomematicIP blind data point."""

    def _init_data_point_fields(self) -> None:
        """Init the data point fields."""
        super()._init_data_point_fields()
        self._dp_operation_mode: DpSelect = self._get_data_point(field=Field.OPERATION_MODE, data_point_type=DpSelect)
        self._dp_combined: DpAction = self._get_data_point(field=Field.COMBINED_PARAMETER, data_point_type=DpAction)

    @property
    def operation_mode(self) -> str | None:
        """Return operation mode of cover."""
        return self._dp_operation_mode.value

    def _get_combined_value(self, level: float | None = None, tilt_level: float | None = None) -> str | None:
        """Return the combined parameter."""
        if level is None and tilt_level is None:
            return None
        levels: list[str] = []
        if tilt_level is not None:
            levels.append(f"L2={int(tilt_level * _LEVEL_TO_POSITION_MULTIPLIER)}")
        if level is not None:
            levels.append(f"L={int(level * _LEVEL_TO_POSITION_MULTIPLIER)}")

        if levels:
            return ",".join(levels)
        return None


class CustomDpGarage(CustomDataPoint):
    """Class for HomeMatic garage data point."""

    _category = DataPointCategory.COVER

    def _init_data_point_fields(self) -> None:
        """Init the data point fields."""
        super()._init_data_point_fields()
        self._dp_door_state: DpSensor[str | None] = self._get_data_point(
            field=Field.DOOR_STATE, data_point_type=DpSensor[str | None]
        )
        self._dp_door_command: DpAction = self._get_data_point(field=Field.DOOR_COMMAND, data_point_type=DpAction)
        self._dp_section: DpSensor[str | None] = self._get_data_point(
            field=Field.SECTION, data_point_type=DpSensor[str | None]
        )

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

    @bind_collector()
    async def set_position(
        self,
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

    @state_property
    def is_closed(self) -> bool | None:
        """Return if the garage door is closed."""
        if self._dp_door_state.value is not None:
            return str(self._dp_door_state.value) == _GarageDoorState.CLOSED
        return None

    @state_property
    def is_opening(self) -> bool | None:
        """Return if the garage door is opening."""
        if self._dp_section.value is not None:
            return int(self._dp_section.value) == _GarageDoorActivity.OPENING
        return None

    @state_property
    def is_closing(self) -> bool | None:
        """Return if the garage door is closing."""
        if self._dp_section.value is not None:
            return int(self._dp_section.value) == _GarageDoorActivity.CLOSING
        return None

    @bind_collector()
    async def open(self, collector: CallParameterCollector | None = None) -> None:
        """Open the garage door."""
        if not self.is_state_change(open=True):
            return
        await self._dp_door_command.send_value(value=_GarageDoorCommand.OPEN, collector=collector)

    @bind_collector()
    async def close(self, collector: CallParameterCollector | None = None) -> None:
        """Close the garage door."""
        if not self.is_state_change(close=True):
            return
        await self._dp_door_command.send_value(value=_GarageDoorCommand.CLOSE, collector=collector)

    @bind_collector(enabled=False)
    async def stop(self, collector: CallParameterCollector | None = None) -> None:
        """Stop the device if in motion."""
        await self._dp_door_command.send_value(value=_GarageDoorCommand.STOP, collector=collector)

    @bind_collector()
    async def vent(self, collector: CallParameterCollector | None = None) -> None:
        """Move the garage door to vent position."""
        if not self.is_state_change(vent=True):
            return
        await self._dp_door_command.send_value(value=_GarageDoorCommand.PARTIAL_OPEN, collector=collector)

    def is_state_change(self, **kwargs: Any) -> bool:
        """Check if the state changes due to kwargs."""
        if kwargs.get(_StateChangeArg.OPEN) is not None and self.current_position != _CoverPosition.OPEN:
            return True
        if kwargs.get(_StateChangeArg.VENT) is not None and self.current_position != _CoverPosition.VENT:
            return True
        if kwargs.get(_StateChangeArg.CLOSE) is not None and self.current_position != _CoverPosition.CLOSED:
            return True
        return super().is_state_change(**kwargs)


def make_ip_cover(
    channel: hmd.Channel,
    custom_config: CustomConfig,
) -> None:
    """Create HomematicIP cover data point."""
    hmed.make_custom_data_point(
        channel=channel,
        data_point_class=CustomDpCover,
        device_profile=DeviceProfile.IP_COVER,
        custom_config=custom_config,
    )


def make_rf_cover(
    channel: hmd.Channel,
    custom_config: CustomConfig,
) -> None:
    """Create HomeMatic classic cover data point."""
    hmed.make_custom_data_point(
        channel=channel,
        data_point_class=CustomDpCover,
        device_profile=DeviceProfile.RF_COVER,
        custom_config=custom_config,
    )


def make_ip_blind(
    channel: hmd.Channel,
    custom_config: CustomConfig,
) -> None:
    """Create HomematicIP cover data point."""
    hmed.make_custom_data_point(
        channel=channel,
        data_point_class=CustomDpIpBlind,
        device_profile=DeviceProfile.IP_COVER,
        custom_config=custom_config,
    )


def make_ip_garage(
    channel: hmd.Channel,
    custom_config: CustomConfig,
) -> None:
    """Create HomematicIP garage data point."""
    hmed.make_custom_data_point(
        channel=channel,
        data_point_class=CustomDpGarage,
        device_profile=DeviceProfile.IP_GARAGE,
        custom_config=custom_config,
    )


def make_ip_hdm(
    channel: hmd.Channel,
    custom_config: CustomConfig,
) -> None:
    """Create HomematicIP cover data point."""
    hmed.make_custom_data_point(
        channel=channel,
        data_point_class=CustomDpIpBlind,
        device_profile=DeviceProfile.IP_HDM,
        custom_config=custom_config,
    )


def make_rf_blind(
    channel: hmd.Channel,
    custom_config: CustomConfig,
) -> None:
    """Create HomeMatic classic cover data point."""
    hmed.make_custom_data_point(
        channel=channel,
        data_point_class=CustomDpBlind,
        device_profile=DeviceProfile.RF_COVER,
        custom_config=custom_config,
    )


def make_rf_window_drive(
    channel: hmd.Channel,
    custom_config: CustomConfig,
) -> None:
    """Create HomeMatic classic window drive data point."""
    hmed.make_custom_data_point(
        channel=channel,
        data_point_class=CustomDpWindowDrive,
        device_profile=DeviceProfile.RF_COVER,
        custom_config=custom_config,
    )


# Case for device model is not relevant.
# HomeBrew (HB-) devices are always listed as HM-.
DEVICES: Mapping[str, CustomConfig | tuple[CustomConfig, ...]] = {
    "263 146": CustomConfig(make_ce_func=make_rf_cover),
    "263 147": CustomConfig(make_ce_func=make_rf_cover),
    "HM-LC-Bl1-Velux": CustomConfig(make_ce_func=make_rf_cover),  # HB-LC-Bl1-Velux
    "HM-LC-Bl1-FM": CustomConfig(make_ce_func=make_rf_cover),
    "HM-LC-Bl1-FM-2": CustomConfig(make_ce_func=make_rf_cover),
    "HM-LC-Bl1-PB-FM": CustomConfig(make_ce_func=make_rf_cover),
    "HM-LC-Bl1-SM": CustomConfig(make_ce_func=make_rf_cover),
    "HM-LC-Bl1-SM-2": CustomConfig(make_ce_func=make_rf_cover),
    "HM-LC-Bl1PBU-FM": CustomConfig(make_ce_func=make_rf_cover),
    "HM-LC-BlX": CustomConfig(make_ce_func=make_rf_cover),
    "HM-LC-Ja1PBU-FM": CustomConfig(make_ce_func=make_rf_blind),
    "HM-LC-JaX": CustomConfig(make_ce_func=make_rf_blind),
    "HM-Sec-Win": CustomConfig(
        make_ce_func=make_rf_window_drive,
        channels=(1,),
        extended=ExtendedConfig(
            additional_data_points={
                1: (
                    Parameter.DIRECTION,
                    Parameter.WORKING,
                    Parameter.ERROR,
                ),
                2: (
                    Parameter.LEVEL,
                    Parameter.STATUS,
                ),
            }
        ),
    ),
    "HMW-LC-Bl1": CustomConfig(make_ce_func=make_rf_cover, channels=(3,)),
    "HmIP-BBL": CustomConfig(make_ce_func=make_ip_blind, channels=(4,)),
    "HmIP-BROLL": CustomConfig(make_ce_func=make_ip_cover, channels=(4,)),
    "HmIP-DRBLI4": CustomConfig(
        make_ce_func=make_ip_blind,
        channels=(10, 14, 18, 22),
        extended=ExtendedConfig(
            additional_data_points={
                0: (Parameter.ACTUAL_TEMPERATURE,),
            }
        ),
    ),
    "HmIP-FBL": CustomConfig(make_ce_func=make_ip_blind, channels=(4,)),
    "HmIP-FROLL": CustomConfig(make_ce_func=make_ip_cover, channels=(4,)),
    "HmIP-HDM": CustomConfig(make_ce_func=make_ip_hdm),
    "HmIP-MOD-HO": CustomConfig(make_ce_func=make_ip_garage),
    "HmIP-MOD-TM": CustomConfig(make_ce_func=make_ip_garage),
    "HmIPW-DRBL4": CustomConfig(
        make_ce_func=make_ip_blind,
        channels=(2, 6, 10, 14),
        extended=ExtendedConfig(
            additional_data_points={
                0: (Parameter.ACTUAL_TEMPERATURE,),
            }
        ),
    ),
    "ZEL STG RM FEP 230V": CustomConfig(make_ce_func=make_rf_cover),
}
hmed.ALL_DEVICES[DataPointCategory.COVER] = DEVICES
