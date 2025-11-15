# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Module for data points implemented using the climate category."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Mapping
from datetime import datetime, timedelta
from enum import IntEnum, StrEnum
import logging
from typing import Any, Final, cast

from aiohomematic import i18n
from aiohomematic.const import (
    BIDCOS_DEVICE_CHANNEL_DUMMY,
    CLIMATE_PROFILE_DICT,
    CLIMATE_SIMPLE_PROFILE_DICT,
    CLIMATE_SIMPLE_WEEKDAY_LIST,
    CLIMATE_WEEKDAY_DICT,
    DataPointCategory,
    DeviceProfile,
    Field,
    InternalCustomID,
    OptionalSettings,
    Parameter,
    ParamsetKey,
    ScheduleProfile,
    WeekdayStr,
)
from aiohomematic.decorators import inspector
from aiohomematic.exceptions import ValidationException
from aiohomematic.model import device as hmd, week_profile as wp
from aiohomematic.model.custom import definition as hmed
from aiohomematic.model.custom.data_point import CustomDataPoint
from aiohomematic.model.custom.support import CustomConfig
from aiohomematic.model.data_point import CallParameterCollector, bind_collector
from aiohomematic.model.generic import (
    DpAction,
    DpBinarySensor,
    DpFloat,
    DpInteger,
    DpSelect,
    DpSensor,
    DpSwitch,
    GenericDataPointAny,
)
from aiohomematic.property_decorators import config_property, state_property
from aiohomematic.type_aliases import UnregisterCallback

_LOGGER: Final = logging.getLogger(__name__)

_CLOSED_LEVEL: Final = 0.0
_DEFAULT_TEMPERATURE_STEP: Final = 0.5
_OFF_TEMPERATURE: Final = 4.5
_PARTY_DATE_FORMAT: Final = "%Y_%m_%d %H:%M"
_PARTY_INIT_DATE: Final = "2000_01_01 00:00"
_TEMP_CELSIUS: Final = "°C"
PROFILE_PREFIX: Final = "week_program_"


class _ModeHm(StrEnum):
    """Enum with the HM modes."""

    AUTO = "AUTO-MODE"  # 0
    AWAY = "PARTY-MODE"  # 2
    BOOST = "BOOST-MODE"  # 3
    MANU = "MANU-MODE"  # 1


class _ModeHmIP(IntEnum):
    """Enum with the HmIP modes."""

    AUTO = 0
    AWAY = 2
    MANU = 1


class _StateChangeArg(StrEnum):
    """Enum with climate state change arguments."""

    MODE = "mode"
    PROFILE = "profile"
    TEMPERATURE = "temperature"


class ClimateActivity(StrEnum):
    """Enum with the climate activities."""

    COOL = "cooling"
    HEAT = "heating"
    IDLE = "idle"
    OFF = "off"


class ClimateHeatingValveType(StrEnum):
    """Enum with the climate heating valve types."""

    NORMALLY_CLOSE = "NORMALLY_CLOSE"
    NORMALLY_OPEN = "NORMALLY_OPEN"


class ClimateMode(StrEnum):
    """Enum with the thermostat modes."""

    AUTO = "auto"
    COOL = "cool"
    HEAT = "heat"
    OFF = "off"


class ClimateProfile(StrEnum):
    """Enum with profiles."""

    AWAY = "away"
    BOOST = "boost"
    COMFORT = "comfort"
    ECO = "eco"
    NONE = "none"
    WEEK_PROGRAM_1 = "week_program_1"
    WEEK_PROGRAM_2 = "week_program_2"
    WEEK_PROGRAM_3 = "week_program_3"
    WEEK_PROGRAM_4 = "week_program_4"
    WEEK_PROGRAM_5 = "week_program_5"
    WEEK_PROGRAM_6 = "week_program_6"


_HM_WEEK_PROFILE_POINTERS_TO_NAMES: Final = {
    0: "WEEK PROGRAM 1",
    1: "WEEK PROGRAM 2",
    2: "WEEK PROGRAM 3",
    3: "WEEK PROGRAM 4",
    4: "WEEK PROGRAM 5",
    5: "WEEK PROGRAM 6",
}
_HM_WEEK_PROFILE_POINTERS_TO_IDX: Final = {v: k for k, v in _HM_WEEK_PROFILE_POINTERS_TO_NAMES.items()}


class BaseCustomDpClimate(CustomDataPoint):
    """Base Homematic climate data_point."""

    __slots__ = (
        "_dp_humidity",
        "_dp_min_max_value_not_relevant_for_manu_mode",
        "_dp_setpoint",
        "_dp_temperature",
        "_dp_temperature_maximum",
        "_dp_temperature_minimum",
        "_old_manu_setpoint",
        "_peer_level_dp",
        "_peer_state_dp",
        "_peer_unregister_callbacks",
    )
    _category = DataPointCategory.CLIMATE

    def __init__(
        self,
        *,
        channel: hmd.Channel,
        unique_id: str,
        device_profile: DeviceProfile,
        device_def: Mapping[str, Any],
        custom_data_point_def: Mapping[int | tuple[int, ...], tuple[str, ...]],
        group_no: int,
        custom_config: CustomConfig,
    ) -> None:
        """Initialize base climate data_point."""
        self._peer_level_dp: DpFloat | None = None
        self._peer_state_dp: DpBinarySensor | None = None
        self._peer_unregister_callbacks: list[UnregisterCallback] = []
        super().__init__(
            channel=channel,
            unique_id=unique_id,
            device_profile=device_profile,
            device_def=device_def,
            custom_data_point_def=custom_data_point_def,
            group_no=group_no,
            custom_config=custom_config,
        )
        self._old_manu_setpoint: float | None = None

    @property
    def _temperature_for_heat_mode(self) -> float:
        """
        Return a safe temperature to use when setting mode to HEAT.

        If the current target temperature is None or represents the special OFF value,
        fall back to the device's minimum valid temperature. Otherwise, return the
        current target temperature clipped to the valid [min, max] range.
        """
        temp = self._old_manu_setpoint or self.target_temperature
        # Treat None or OFF sentinel as invalid/unsafe to restore.
        if temp is None or temp <= _OFF_TEMPERATURE or temp < self.min_temp:
            return self.min_temp if self.min_temp > _OFF_TEMPERATURE else _OFF_TEMPERATURE + 0.5
        if temp > self.max_temp:
            return self.max_temp
        return temp

    @property
    def available_schedule_profiles(self) -> tuple[ScheduleProfile, ...]:
        """Return available schedule profiles."""
        if self._device.week_profile and isinstance(self._device.week_profile, wp.ClimeateWeekProfile):
            return self._device.week_profile.available_schedule_profiles
        return ()

    @property
    def schedule_profile_nos(self) -> int:
        """Return the number of supported profiles."""
        return 0

    @property
    def supports_profiles(self) -> bool:
        """Flag if climate supports profiles."""
        return False

    @config_property
    def target_temperature_step(self) -> float:
        """Return the supported step of target temperature."""
        return _DEFAULT_TEMPERATURE_STEP

    @config_property
    def temperature_unit(self) -> str:
        """Return temperature unit."""
        return _TEMP_CELSIUS

    @state_property
    def activity(self) -> ClimateActivity | None:
        """Return the current activity."""
        return None

    @state_property
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        return self._dp_humidity.value

    @state_property
    def current_temperature(self) -> float | None:
        """Return current temperature."""
        return self._dp_temperature.value

    @state_property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        if self._dp_temperature_maximum.value is not None:
            return float(self._dp_temperature_maximum.value)
        return cast(float, self._dp_setpoint.max)

    @state_property
    def min_max_value_not_relevant_for_manu_mode(self) -> bool:
        """Return the maximum temperature."""
        if self._dp_min_max_value_not_relevant_for_manu_mode.value is not None:
            return self._dp_min_max_value_not_relevant_for_manu_mode.value
        return False

    @state_property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        if self._dp_temperature_minimum.value is not None:
            min_temp = float(self._dp_temperature_minimum.value)
        else:
            min_temp = float(self._dp_setpoint.min) if self._dp_setpoint.min is not None else 0.0

        if min_temp == _OFF_TEMPERATURE:
            return min_temp + _DEFAULT_TEMPERATURE_STEP
        return min_temp

    @state_property
    def mode(self) -> ClimateMode:
        """Return current operation mode."""
        return ClimateMode.HEAT

    @state_property
    def modes(self) -> tuple[ClimateMode, ...]:
        """Return the available operation modes."""
        return (ClimateMode.HEAT,)

    @state_property
    def profile(self) -> ClimateProfile:
        """Return the current profile."""
        return ClimateProfile.NONE

    @state_property
    def profiles(self) -> tuple[ClimateProfile, ...]:
        """Return available profiles."""
        return (ClimateProfile.NONE,)

    @state_property
    def target_temperature(self) -> float | None:
        """Return target temperature."""
        return self._dp_setpoint.value

    @inspector
    async def copy_schedule(self, *, target_climate_data_point: BaseCustomDpClimate) -> None:
        """Copy schedule to target device (delegates to week profile)."""
        if self._device.week_profile and isinstance(self._device.week_profile, wp.ClimeateWeekProfile):
            await self._device.week_profile.copy_schedule(target_climate_data_point=target_climate_data_point)

    @inspector
    async def copy_schedule_profile(
        self,
        *,
        source_profile: ScheduleProfile,
        target_profile: ScheduleProfile,
        target_climate_data_point: BaseCustomDpClimate | None = None,
    ) -> None:
        """Copy schedule profile to target device (delegates to week profile)."""
        if self._device.week_profile and isinstance(self._device.week_profile, wp.ClimeateWeekProfile):
            await self._device.week_profile.copy_schedule_profile(
                source_profile=source_profile,
                target_profile=target_profile,
                target_climate_data_point=target_climate_data_point,
            )

    @inspector
    async def disable_away_mode(self) -> None:
        """Disable the away mode on thermostat."""

    @inspector
    async def enable_away_mode_by_calendar(self, *, start: datetime, end: datetime, away_temperature: float) -> None:
        """Enable the away mode by calendar on thermostat."""

    @inspector
    async def enable_away_mode_by_duration(self, *, hours: int, away_temperature: float) -> None:
        """Enable the away mode by duration on thermostat."""

    @inspector
    async def get_schedule_profile(self, *, profile: ScheduleProfile, force_load: bool = False) -> CLIMATE_PROFILE_DICT:
        """Return a schedule by climate profile (delegates to week profile)."""
        if self._device.week_profile and isinstance(self._device.week_profile, wp.ClimeateWeekProfile):
            return await self._device.week_profile.get_schedule_profile(profile=profile, force_load=force_load)
        return {}

    @inspector
    async def get_schedule_profile_weekday(
        self, *, profile: ScheduleProfile, weekday: WeekdayStr, force_load: bool = False
    ) -> CLIMATE_WEEKDAY_DICT:
        """Return a schedule by climate profile and weekday (delegates to week profile)."""
        if self._device.week_profile and isinstance(self._device.week_profile, wp.ClimeateWeekProfile):
            return await self._device.week_profile.get_schedule_profile_weekday(
                profile=profile, weekday=weekday, force_load=force_load
            )
        return {}

    def is_state_change(self, **kwargs: Any) -> bool:
        """Check if the state changes due to kwargs."""
        if (
            temperature := kwargs.get(_StateChangeArg.TEMPERATURE)
        ) is not None and temperature != self.target_temperature:
            return True
        if (mode := kwargs.get(_StateChangeArg.MODE)) is not None and mode != self.mode:
            return True
        if (profile := kwargs.get(_StateChangeArg.PROFILE)) is not None and profile != self.profile:
            return True
        return super().is_state_change(**kwargs)

    @bind_collector
    async def set_mode(self, *, mode: ClimateMode, collector: CallParameterCollector | None = None) -> None:
        """Set new target mode."""

    @bind_collector
    async def set_profile(self, *, profile: ClimateProfile, collector: CallParameterCollector | None = None) -> None:
        """Set new profile."""

    @inspector
    async def set_schedule_profile(
        self, *, profile: ScheduleProfile, profile_data: CLIMATE_PROFILE_DICT, do_validate: bool = True
    ) -> None:
        """Set a profile to device (delegates to week profile)."""
        if self._device.week_profile and isinstance(self._device.week_profile, wp.ClimeateWeekProfile):
            await self._device.week_profile.set_schedule_profile(
                profile=profile, profile_data=profile_data, do_validate=do_validate
            )

    @inspector
    async def set_schedule_profile_weekday(
        self,
        *,
        profile: ScheduleProfile,
        weekday: WeekdayStr,
        weekday_data: CLIMATE_WEEKDAY_DICT,
        do_validate: bool = True,
    ) -> None:
        """Store a profile weekday to device (delegates to week profile)."""
        if self._device.week_profile and isinstance(self._device.week_profile, wp.ClimeateWeekProfile):
            await self._device.week_profile.set_schedule_profile_weekday(
                profile=profile, weekday=weekday, weekday_data=weekday_data, do_validate=do_validate
            )

    @inspector
    async def set_simple_schedule_profile(
        self,
        *,
        profile: ScheduleProfile,
        base_temperature: float,
        simple_profile_data: CLIMATE_SIMPLE_PROFILE_DICT,
    ) -> None:
        """Set a profile to device using simple format (delegates to week profile)."""
        if self._device.week_profile and isinstance(self._device.week_profile, wp.ClimeateWeekProfile):
            await self._device.week_profile.set_simple_schedule_profile(
                profile=profile, base_temperature=base_temperature, simple_profile_data=simple_profile_data
            )

    @inspector
    async def set_simple_schedule_profile_weekday(
        self,
        *,
        profile: ScheduleProfile,
        weekday: WeekdayStr,
        base_temperature: float,
        simple_weekday_list: CLIMATE_SIMPLE_WEEKDAY_LIST,
    ) -> None:
        """Store a simple weekday profile to device (delegates to week profile)."""
        if self._device.week_profile and isinstance(self._device.week_profile, wp.ClimeateWeekProfile):
            await self._device.week_profile.set_simple_schedule_profile_weekday(
                profile=profile,
                weekday=weekday,
                base_temperature=base_temperature,
                simple_weekday_list=simple_weekday_list,
            )

    @bind_collector
    async def set_temperature(
        self,
        *,
        temperature: float,
        collector: CallParameterCollector | None = None,
        do_validate: bool = True,
    ) -> None:
        """Set new target temperature. The temperature must be set in all cases, even if the values are identical."""
        if do_validate and self.mode == ClimateMode.HEAT and self.min_max_value_not_relevant_for_manu_mode:
            do_validate = False

        if do_validate and not (self.min_temp <= temperature <= self.max_temp):
            raise ValidationException(
                i18n.tr(
                    "exception.model.custom.climate.set_temperature.invalid",
                    temperature=temperature,
                    min=self.min_temp,
                    max=self.max_temp,
                )
            )

        await self._dp_setpoint.send_value(value=temperature, collector=collector, do_validate=do_validate)

    def _init_data_point_fields(self) -> None:
        """Init the data_point fields."""
        super()._init_data_point_fields()

        self._dp_humidity: DpSensor[int | None] = self._get_data_point(
            field=Field.HUMIDITY, data_point_type=DpSensor[int | None]
        )
        self._dp_min_max_value_not_relevant_for_manu_mode: DpSwitch = self._get_data_point(
            field=Field.MIN_MAX_VALUE_NOT_RELEVANT_FOR_MANU_MODE, data_point_type=DpSwitch
        )
        self._dp_setpoint: DpFloat = self._get_data_point(field=Field.SETPOINT, data_point_type=DpFloat)
        self._dp_temperature: DpSensor[float | None] = self._get_data_point(
            field=Field.TEMPERATURE, data_point_type=DpSensor[float | None]
        )
        self._dp_temperature_maximum: DpFloat = self._get_data_point(
            field=Field.TEMPERATURE_MAXIMUM, data_point_type=DpFloat
        )
        self._dp_temperature_minimum: DpFloat = self._get_data_point(
            field=Field.TEMPERATURE_MINIMUM, data_point_type=DpFloat
        )

    @abstractmethod
    def _manu_temp_changed(self, *, data_point: GenericDataPointAny | None = None, **kwargs: Any) -> None:
        """Handle device state changes."""

    def _on_link_peer_changed(self) -> None:
        """
        Handle a change of the link peer channel.

        Refresh references to `STATE`/`LEVEL` on the peer and emit an update so
        consumers can re-evaluate `activity`.
        """
        self._refresh_link_peer_activity_sources()
        # Inform listeners that relevant inputs may have changed
        self.emit_data_point_updated_event()

    def _post_init_data_point_fields(self) -> None:
        """Post action after initialisation of the data point fields."""
        super()._post_init_data_point_fields()

        self._unregister_callbacks.append(
            self._dp_setpoint.register_data_point_updated_callback(
                cb=self._manu_temp_changed, custom_id=InternalCustomID.MANU_TEMP
            )
        )

        if OptionalSettings.ENABLE_LINKED_ENTITY_CLIMATE_ACTIVITY not in self._device.central.config.optional_settings:
            return

        for ch in self._device.channels.values():
            # register link-peer change callback; store unregister handle
            if (unreg := ch.register_link_peer_changed_callback(cb=self._on_link_peer_changed)) is not None:
                self._unregister_callbacks.append(unreg)
        # pre-populate peer references (if any) once
        self._refresh_link_peer_activity_sources()

    def _refresh_link_peer_activity_sources(self) -> None:
        """
        Refresh peer data point references used for `activity` fallback.

        - Unregister any previously registered peer callbacks.
        - Grab its `STATE` and `LEVEL` generic data points from any available linked channel (if available).
        - Subscribe to their updates to keep `activity` current.
        """
        # Unsubscribe from previous peer DPs
        for unreg in self._peer_unregister_callbacks:
            if unreg is not None:
                try:
                    unreg()
                finally:
                    self._peer_unregister_callbacks.remove(unreg)
                    if unreg in self._unregister_callbacks:
                        self._unregister_callbacks.remove(unreg)

        self._peer_unregister_callbacks.clear()
        self._peer_level_dp = None
        self._peer_state_dp = None

        try:
            # Go thru all link peer channels of the device
            for link_channels in self._device.link_peer_channels.values():
                # Some channels have multiple link peers
                for link_channel in link_channels:
                    # Continue if LEVEL or STATE dp found and ignore the others
                    if not link_channel.has_link_target_category(category=DataPointCategory.CLIMATE):
                        continue
                    if level_dp := link_channel.get_generic_data_point(parameter=Parameter.LEVEL):
                        self._peer_level_dp = cast(DpFloat, level_dp)
                        break
                    if state_dp := link_channel.get_generic_data_point(parameter=Parameter.STATE):
                        self._peer_state_dp = cast(DpBinarySensor, state_dp)
                        break
        except Exception:  # pragma: no cover - defensive
            self._peer_level_dp = None
            self._peer_state_dp = None
            return

        # Subscribe to updates of peer DPs to forward update events
        for dp in (self._peer_level_dp, self._peer_state_dp):
            if dp is None:
                continue
            unreg = dp.register_data_point_updated_callback(
                cb=self.emit_data_point_updated_event, custom_id=InternalCustomID.LINK_PEER
            )
            if unreg is not None:
                # Track for both refresh-time cleanup and object removal cleanup
                self._peer_unregister_callbacks.append(unreg)
                self._unregister_callbacks.append(unreg)


class CustomDpSimpleRfThermostat(BaseCustomDpClimate):
    """Simple classic Homematic thermostat HM-CC-TC."""

    __slots__ = ()

    def _manu_temp_changed(self, *, data_point: GenericDataPointAny | None = None, **kwargs: Any) -> None:
        """Handle device state changes."""


class CustomDpRfThermostat(BaseCustomDpClimate):
    """Classic Homematic thermostat like HM-CC-RT-DN."""

    __slots__ = (
        "_dp_auto_mode",
        "_dp_boost_mode",
        "_dp_comfort_mode",
        "_dp_control_mode",
        "_dp_lowering_mode",
        "_dp_manu_mode",
        "_dp_temperature_offset",
        "_dp_valve_state",
        "_dp_week_program_pointer",
    )

    @property
    def _current_profile_name(self) -> ClimateProfile | None:
        """Return a profile index by name."""
        inv_profiles = {v: k for k, v in self._profiles.items()}
        sp = str(self._dp_week_program_pointer.value)
        idx = int(sp) if sp.isnumeric() else _HM_WEEK_PROFILE_POINTERS_TO_IDX.get(sp)
        return inv_profiles.get(idx) if idx is not None else None

    @property
    def _profile_names(self) -> tuple[ClimateProfile, ...]:
        """Return a collection of profile names."""
        return tuple(self._profiles.keys())

    @property
    def _profiles(self) -> Mapping[ClimateProfile, int]:
        """Return the profile groups."""
        profiles: dict[ClimateProfile, int] = {}
        if self._dp_week_program_pointer.min is not None and self._dp_week_program_pointer.max is not None:
            for i in range(int(self._dp_week_program_pointer.min) + 1, int(self._dp_week_program_pointer.max) + 2):
                profiles[ClimateProfile(f"{PROFILE_PREFIX}{i}")] = i - 1

        return profiles

    @property
    def supports_profiles(self) -> bool:
        """Flag if climate supports profiles."""
        return True

    @state_property
    def activity(self) -> ClimateActivity | None:
        """Return the current activity."""
        if self._dp_valve_state.value is None:
            return None
        if self.mode == ClimateMode.OFF:
            return ClimateActivity.OFF
        if self._dp_valve_state.value and self._dp_valve_state.value > 0:
            return ClimateActivity.HEAT
        return ClimateActivity.IDLE

    @state_property
    def mode(self) -> ClimateMode:
        """Return current operation mode."""
        if self.target_temperature and self.target_temperature <= _OFF_TEMPERATURE:
            return ClimateMode.OFF
        if self._dp_control_mode.value == _ModeHm.MANU:
            return ClimateMode.HEAT
        return ClimateMode.AUTO

    @state_property
    def modes(self) -> tuple[ClimateMode, ...]:
        """Return the available operation modes."""
        return (ClimateMode.AUTO, ClimateMode.HEAT, ClimateMode.OFF)

    @state_property
    def profile(self) -> ClimateProfile:
        """Return the current profile."""
        if self._dp_control_mode.value is None:
            return ClimateProfile.NONE
        if self._dp_control_mode.value == _ModeHm.BOOST:
            return ClimateProfile.BOOST
        if self._dp_control_mode.value == _ModeHm.AWAY:
            return ClimateProfile.AWAY
        if self.mode == ClimateMode.AUTO:
            return self._current_profile_name if self._current_profile_name else ClimateProfile.NONE
        return ClimateProfile.NONE

    @state_property
    def profiles(self) -> tuple[ClimateProfile, ...]:
        """Return available profile."""
        control_modes = [ClimateProfile.BOOST, ClimateProfile.COMFORT, ClimateProfile.ECO, ClimateProfile.NONE]
        if self.mode == ClimateMode.AUTO:
            control_modes.extend(self._profile_names)
        return tuple(control_modes)

    @state_property
    def temperature_offset(self) -> str | None:
        """Return the maximum temperature."""
        val = self._dp_temperature_offset.value
        return val if isinstance(val, str) else None

    @inspector
    async def disable_away_mode(self) -> None:
        """Disable the away mode on thermostat."""
        start = datetime.now() - timedelta(hours=11)
        end = datetime.now() - timedelta(hours=10)

        await self._client.set_value(
            channel_address=self._channel.address,
            paramset_key=ParamsetKey.VALUES,
            parameter=Parameter.PARTY_MODE_SUBMIT,
            value=_party_mode_code(start=start, end=end, away_temperature=12.0),
        )

    @inspector
    async def enable_away_mode_by_calendar(self, *, start: datetime, end: datetime, away_temperature: float) -> None:
        """Enable the away mode by calendar on thermostat."""
        await self._client.set_value(
            channel_address=self._channel.address,
            paramset_key=ParamsetKey.VALUES,
            parameter=Parameter.PARTY_MODE_SUBMIT,
            value=_party_mode_code(start=start, end=end, away_temperature=away_temperature),
        )

    @inspector
    async def enable_away_mode_by_duration(self, *, hours: int, away_temperature: float) -> None:
        """Enable the away mode by duration on thermostat."""
        start = datetime.now() - timedelta(minutes=10)
        end = datetime.now() + timedelta(hours=hours)
        await self.enable_away_mode_by_calendar(start=start, end=end, away_temperature=away_temperature)

    @bind_collector
    async def set_mode(self, *, mode: ClimateMode, collector: CallParameterCollector | None = None) -> None:
        """Set new mode."""
        if not self.is_state_change(mode=mode):
            return
        if mode == ClimateMode.AUTO:
            await self._dp_auto_mode.send_value(value=True, collector=collector)
        elif mode == ClimateMode.HEAT:
            await self._dp_manu_mode.send_value(value=self._temperature_for_heat_mode, collector=collector)
        elif mode == ClimateMode.OFF:
            await self._dp_manu_mode.send_value(value=self.target_temperature, collector=collector)
            # Disable validation here to allow setting a value,
            # that is out of the validation range.
            await self.set_temperature(temperature=_OFF_TEMPERATURE, collector=collector, do_validate=False)

    @bind_collector
    async def set_profile(self, *, profile: ClimateProfile, collector: CallParameterCollector | None = None) -> None:
        """Set new profile."""
        if not self.is_state_change(profile=profile):
            return
        if profile == ClimateProfile.BOOST:
            await self._dp_boost_mode.send_value(value=True, collector=collector)
        elif profile == ClimateProfile.COMFORT:
            await self._dp_comfort_mode.send_value(value=True, collector=collector)
        elif profile == ClimateProfile.ECO:
            await self._dp_lowering_mode.send_value(value=True, collector=collector)
        elif profile in self._profile_names:
            if self.mode != ClimateMode.AUTO:
                await self.set_mode(mode=ClimateMode.AUTO, collector=collector)
                await self._dp_boost_mode.send_value(value=False, collector=collector)
            if (profile_idx := self._profiles.get(profile)) is not None:
                await self._dp_week_program_pointer.send_value(
                    value=_HM_WEEK_PROFILE_POINTERS_TO_NAMES[profile_idx], collector=collector
                )

    def _init_data_point_fields(self) -> None:
        """Init the data_point fields."""
        super()._init_data_point_fields()

        self._dp_boost_mode: DpAction = self._get_data_point(field=Field.BOOST_MODE, data_point_type=DpAction)
        self._dp_auto_mode: DpAction = self._get_data_point(field=Field.AUTO_MODE, data_point_type=DpAction)
        self._dp_manu_mode: DpAction = self._get_data_point(field=Field.MANU_MODE, data_point_type=DpAction)
        self._dp_comfort_mode: DpAction = self._get_data_point(field=Field.COMFORT_MODE, data_point_type=DpAction)
        self._dp_lowering_mode: DpAction = self._get_data_point(field=Field.LOWERING_MODE, data_point_type=DpAction)
        self._dp_control_mode: DpSensor[str | None] = self._get_data_point(
            field=Field.CONTROL_MODE, data_point_type=DpSensor[str | None]
        )
        self._dp_temperature_offset: DpSelect = self._get_data_point(
            field=Field.TEMPERATURE_OFFSET, data_point_type=DpSelect
        )
        self._dp_valve_state: DpSensor[int | None] = self._get_data_point(
            field=Field.VALVE_STATE, data_point_type=DpSensor[int | None]
        )
        self._dp_week_program_pointer: DpSelect = self._get_data_point(
            field=Field.WEEK_PROGRAM_POINTER, data_point_type=DpSelect
        )

    def _manu_temp_changed(self, *, data_point: GenericDataPointAny | None = None, **kwargs: Any) -> None:
        """Handle device state changes."""
        if (
            data_point == self._dp_control_mode
            and self.mode == ClimateMode.HEAT
            and self._dp_setpoint.refreshed_recently
        ):
            self._old_manu_setpoint = self.target_temperature

        if (
            data_point == self._dp_setpoint
            and self.mode == ClimateMode.HEAT
            and self._dp_control_mode.refreshed_recently
        ):
            self._old_manu_setpoint = self.target_temperature

    def _post_init_data_point_fields(self) -> None:
        """Post action after initialisation of the data point fields."""
        super()._post_init_data_point_fields()

        # register callback for control_mode to track manual target temp
        self._unregister_callbacks.append(
            self._dp_control_mode.register_data_point_updated_callback(
                cb=self._manu_temp_changed, custom_id=InternalCustomID.MANU_TEMP
            )
        )


def _party_mode_code(*, start: datetime, end: datetime, away_temperature: float) -> str:
    """
    Create the party mode code.

    e.g. 21.5,1200,20,10,16,1380,20,10,16
    away_temperature,start_minutes_of_day, day(2), month(2), year(2), end_minutes_of_day, day(2), month(2), year(2)
    """
    return f"{away_temperature:.1f},{start.hour * 60 + start.minute},{start.strftime('%d,%m,%y')},{end.hour * 60 + end.minute},{end.strftime('%d,%m,%y')}"


class CustomDpIpThermostat(BaseCustomDpClimate):
    """HomematicIP thermostat like HmIP-BWTH, HmIP-eTRV-X."""

    __slots__ = (
        "_dp_active_profile",
        "_dp_boost_mode",
        "_dp_control_mode",
        "_dp_heating_mode",
        "_dp_heating_valve_type",
        "_dp_level",
        "_dp_optimum_start_stop",
        "_dp_party_mode",
        "_dp_set_point_mode",
        "_dp_state",
        "_dp_temperature_offset",
    )

    @property
    def _current_profile_name(self) -> ClimateProfile | None:
        """Return a profile index by name."""
        inv_profiles = {v: k for k, v in self._profiles.items()}
        if self._dp_active_profile.value is not None:
            return inv_profiles.get(int(self._dp_active_profile.value))
        return None

    @property
    def _is_heating_mode(self) -> bool:
        """Return the heating_mode of the device."""
        val = self._dp_heating_mode.value
        return True if val is None else str(val) == "HEATING"

    @property
    def _profile_names(self) -> tuple[ClimateProfile, ...]:
        """Return a collection of profile names."""
        return tuple(self._profiles.keys())

    @property
    def _profiles(self) -> Mapping[ClimateProfile, int]:
        """Return the profile groups."""
        profiles: dict[ClimateProfile, int] = {}
        if self._dp_active_profile.min and self._dp_active_profile.max:
            for i in range(self._dp_active_profile.min, self._dp_active_profile.max + 1):
                profiles[ClimateProfile(f"{PROFILE_PREFIX}{i}")] = i

        return profiles

    @property
    def optimum_start_stop(self) -> bool | None:
        """Return if optimum_start_stop is enabled."""
        return self._dp_optimum_start_stop.value

    @property
    def schedule_profile_nos(self) -> int:
        """Return the number of supported profiles."""
        return len(self._profiles)

    @property
    def supports_profiles(self) -> bool:
        """Flag if climate supports control modes."""
        return True

    @state_property
    def activity(self) -> ClimateActivity | None:
        """
        Return the current activity.

        The preferred sources for determining the activity are this channel's `LEVEL` and `STATE` data points.
        Some devices don't expose one or both; in that case we try to use the same datapoints from the linked peer channels instead.
        """
        # Determine effective data point values for LEVEL and STATE.
        level_dp = self._dp_level if self._dp_level.is_hmtype else None
        state_dp = self._dp_state if self._dp_state.is_hmtype else None

        eff_level = None
        eff_state = None

        # Use own DP values as-is when available to preserve legacy behavior.
        if level_dp is not None and level_dp.value is not None:
            eff_level = level_dp.value
        elif self._peer_level_dp is not None and self._peer_level_dp.value is not None:
            eff_level = self._peer_level_dp.value

        if state_dp is not None and state_dp.value is not None:
            eff_state = state_dp.value
        elif self._peer_state_dp is not None and self._peer_state_dp.value is not None:
            eff_state = self._peer_state_dp.value

        if eff_state is None and eff_level is None:
            return None
        if self.mode == ClimateMode.OFF:
            return ClimateActivity.OFF
        if eff_level is not None and eff_level > _CLOSED_LEVEL:
            return ClimateActivity.HEAT
        valve = self._dp_heating_valve_type.value
        # Determine heating/cooling based on valve type and state
        is_active = False
        if eff_state is True:
            # Valve open means active when NC or valve type unknown
            is_active = valve is None or valve == ClimateHeatingValveType.NORMALLY_CLOSE
        elif eff_state is False:
            # Valve closed means active for NO type
            is_active = valve == ClimateHeatingValveType.NORMALLY_OPEN
        if is_active:
            return ClimateActivity.HEAT if self._is_heating_mode else ClimateActivity.COOL
        return ClimateActivity.IDLE

    @state_property
    def mode(self) -> ClimateMode:
        """Return current operation mode."""
        if self.target_temperature and self.target_temperature <= _OFF_TEMPERATURE:
            return ClimateMode.OFF
        if self._dp_set_point_mode.value == _ModeHmIP.MANU:
            return ClimateMode.HEAT if self._is_heating_mode else ClimateMode.COOL
        if self._dp_set_point_mode.value == _ModeHmIP.AUTO:
            return ClimateMode.AUTO
        return ClimateMode.AUTO

    @state_property
    def modes(self) -> tuple[ClimateMode, ...]:
        """Return the available operation modes."""
        return (
            ClimateMode.AUTO,
            ClimateMode.HEAT if self._is_heating_mode else ClimateMode.COOL,
            ClimateMode.OFF,
        )

    @state_property
    def profile(self) -> ClimateProfile:
        """Return the current control mode."""
        if self._dp_boost_mode.value:
            return ClimateProfile.BOOST
        if self._dp_set_point_mode.value == _ModeHmIP.AWAY:
            return ClimateProfile.AWAY
        if self.mode == ClimateMode.AUTO:
            return self._current_profile_name if self._current_profile_name else ClimateProfile.NONE
        return ClimateProfile.NONE

    @state_property
    def profiles(self) -> tuple[ClimateProfile, ...]:
        """Return available control modes."""
        control_modes = [ClimateProfile.BOOST, ClimateProfile.NONE]
        if self.mode == ClimateMode.AUTO:
            control_modes.extend(self._profile_names)
        return tuple(control_modes)

    @state_property
    def temperature_offset(self) -> float | None:
        """Return the maximum temperature."""
        return self._dp_temperature_offset.value

    @inspector
    async def disable_away_mode(self) -> None:
        """Disable the away mode on thermostat."""
        await self._client.put_paramset(
            channel_address=self._channel.address,
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                Parameter.SET_POINT_MODE: _ModeHmIP.AWAY,
                Parameter.PARTY_TIME_START: _PARTY_INIT_DATE,
                Parameter.PARTY_TIME_END: _PARTY_INIT_DATE,
            },
        )

    @inspector
    async def enable_away_mode_by_calendar(self, *, start: datetime, end: datetime, away_temperature: float) -> None:
        """Enable the away mode by calendar on thermostat."""
        await self._client.put_paramset(
            channel_address=self._channel.address,
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                Parameter.SET_POINT_MODE: _ModeHmIP.AWAY,
                Parameter.SET_POINT_TEMPERATURE: away_temperature,
                Parameter.PARTY_TIME_START: start.strftime(_PARTY_DATE_FORMAT),
                Parameter.PARTY_TIME_END: end.strftime(_PARTY_DATE_FORMAT),
            },
        )

    @inspector
    async def enable_away_mode_by_duration(self, *, hours: int, away_temperature: float) -> None:
        """Enable the away mode by duration on thermostat."""
        start = datetime.now() - timedelta(minutes=10)
        end = datetime.now() + timedelta(hours=hours)
        await self.enable_away_mode_by_calendar(start=start, end=end, away_temperature=away_temperature)

    @bind_collector
    async def set_mode(self, *, mode: ClimateMode, collector: CallParameterCollector | None = None) -> None:
        """Set new target mode."""
        if not self.is_state_change(mode=mode):
            return
        # if switching mode then disable boost_mode
        if self._dp_boost_mode.value:
            await self.set_profile(profile=ClimateProfile.NONE, collector=collector)

        if mode == ClimateMode.AUTO:
            await self._dp_control_mode.send_value(value=_ModeHmIP.AUTO, collector=collector)
        elif mode in (ClimateMode.HEAT, ClimateMode.COOL):
            await self._dp_control_mode.send_value(value=_ModeHmIP.MANU, collector=collector)
            await self.set_temperature(temperature=self._temperature_for_heat_mode, collector=collector)
        elif mode == ClimateMode.OFF:
            await self._dp_control_mode.send_value(value=_ModeHmIP.MANU, collector=collector)
            await self.set_temperature(temperature=_OFF_TEMPERATURE, collector=collector, do_validate=False)

    @bind_collector
    async def set_profile(self, *, profile: ClimateProfile, collector: CallParameterCollector | None = None) -> None:
        """Set new control mode."""
        if not self.is_state_change(profile=profile):
            return
        if profile == ClimateProfile.BOOST:
            await self._dp_boost_mode.send_value(value=True, collector=collector)
        elif profile == ClimateProfile.NONE:
            await self._dp_boost_mode.send_value(value=False, collector=collector)
        elif profile in self._profile_names:
            if self.mode != ClimateMode.AUTO:
                await self.set_mode(mode=ClimateMode.AUTO, collector=collector)
                await self._dp_boost_mode.send_value(value=False, collector=collector)
            if profile_idx := self._profiles.get(profile):
                await self._dp_active_profile.send_value(value=profile_idx, collector=collector)

    def _init_data_point_fields(self) -> None:
        """Init the data_point fields."""
        super()._init_data_point_fields()

        self._dp_active_profile: DpInteger = self._get_data_point(field=Field.ACTIVE_PROFILE, data_point_type=DpInteger)
        self._dp_boost_mode: DpSwitch = self._get_data_point(field=Field.BOOST_MODE, data_point_type=DpSwitch)
        self._dp_control_mode: DpAction = self._get_data_point(field=Field.CONTROL_MODE, data_point_type=DpAction)
        self._dp_heating_mode: DpSelect = self._get_data_point(field=Field.HEATING_COOLING, data_point_type=DpSelect)
        self._dp_heating_valve_type: DpSelect = self._get_data_point(
            field=Field.HEATING_VALVE_TYPE, data_point_type=DpSelect
        )
        self._dp_level: DpFloat = self._get_data_point(field=Field.LEVEL, data_point_type=DpFloat)
        self._dp_optimum_start_stop: DpSwitch = self._get_data_point(
            field=Field.OPTIMUM_START_STOP, data_point_type=DpSwitch
        )
        self._dp_party_mode: DpBinarySensor = self._get_data_point(
            field=Field.PARTY_MODE, data_point_type=DpBinarySensor
        )
        self._dp_set_point_mode: DpInteger = self._get_data_point(field=Field.SET_POINT_MODE, data_point_type=DpInteger)
        self._dp_state: DpBinarySensor = self._get_data_point(field=Field.STATE, data_point_type=DpBinarySensor)
        self._dp_temperature_offset: DpFloat = self._get_data_point(
            field=Field.TEMPERATURE_OFFSET, data_point_type=DpFloat
        )

    def _manu_temp_changed(self, *, data_point: GenericDataPointAny | None = None, **kwargs: Any) -> None:
        """Handle device state changes."""
        if (
            data_point == self._dp_set_point_mode
            and self.mode == ClimateMode.HEAT
            and self._dp_setpoint.refreshed_recently
        ):
            self._old_manu_setpoint = self.target_temperature

        if (
            data_point == self._dp_setpoint
            and self.mode == ClimateMode.HEAT
            and self._dp_set_point_mode.refreshed_recently
        ):
            self._old_manu_setpoint = self.target_temperature

    def _post_init_data_point_fields(self) -> None:
        """Post action after initialisation of the data point fields."""
        super()._post_init_data_point_fields()

        # register callback for set_point_mode to track manual target temp
        self._unregister_callbacks.append(
            self._dp_set_point_mode.register_data_point_updated_callback(
                cb=self._manu_temp_changed, custom_id=InternalCustomID.MANU_TEMP
            )
        )


def make_simple_thermostat(
    *,
    channel: hmd.Channel,
    custom_config: CustomConfig,
) -> None:
    """Create SimpleRfThermostat data point."""
    hmed.make_custom_data_point(
        channel=channel,
        data_point_class=CustomDpSimpleRfThermostat,
        device_profile=DeviceProfile.SIMPLE_RF_THERMOSTAT,
        custom_config=custom_config,
    )


def make_thermostat(
    *,
    channel: hmd.Channel,
    custom_config: CustomConfig,
) -> None:
    """Create RfThermostat data point."""
    hmed.make_custom_data_point(
        channel=channel,
        data_point_class=CustomDpRfThermostat,
        device_profile=DeviceProfile.RF_THERMOSTAT,
        custom_config=custom_config,
    )


def make_thermostat_group(
    *,
    channel: hmd.Channel,
    custom_config: CustomConfig,
) -> None:
    """Create RfThermostat group data point."""
    hmed.make_custom_data_point(
        channel=channel,
        data_point_class=CustomDpRfThermostat,
        device_profile=DeviceProfile.RF_THERMOSTAT_GROUP,
        custom_config=custom_config,
    )


def make_ip_thermostat(
    *,
    channel: hmd.Channel,
    custom_config: CustomConfig,
) -> None:
    """Create IPThermostat data point."""
    hmed.make_custom_data_point(
        channel=channel,
        data_point_class=CustomDpIpThermostat,
        device_profile=DeviceProfile.IP_THERMOSTAT,
        custom_config=custom_config,
    )


def make_ip_thermostat_group(
    *,
    channel: hmd.Channel,
    custom_config: CustomConfig,
) -> None:
    """Create IPThermostat group data point."""
    hmed.make_custom_data_point(
        channel=channel,
        data_point_class=CustomDpIpThermostat,
        device_profile=DeviceProfile.IP_THERMOSTAT_GROUP,
        custom_config=custom_config,
    )


# Case for device model is not relevant.
# HomeBrew (HB-) devices are always listed as HM-.
DEVICES: Mapping[str, CustomConfig | tuple[CustomConfig, ...]] = {
    "ALPHA-IP-RBG": CustomConfig(make_ce_func=make_ip_thermostat),
    "BC-RT-TRX-CyG": CustomConfig(make_ce_func=make_thermostat),
    "BC-RT-TRX-CyN": CustomConfig(make_ce_func=make_thermostat),
    "BC-TC-C-WM": CustomConfig(make_ce_func=make_thermostat),
    "HM-CC-RT-DN": CustomConfig(make_ce_func=make_thermostat, channels=(4,)),
    "HM-CC-TC": CustomConfig(make_ce_func=make_simple_thermostat),
    "HM-CC-VG-1": CustomConfig(make_ce_func=make_thermostat_group),
    "HM-TC-IT-WM-W-EU": CustomConfig(
        make_ce_func=make_thermostat, channels=(2,), schedule_channel_no=BIDCOS_DEVICE_CHANNEL_DUMMY
    ),
    "HmIP-BWTH": CustomConfig(make_ce_func=make_ip_thermostat, schedule_channel_no=1),
    "HmIP-HEATING": CustomConfig(make_ce_func=make_ip_thermostat_group, schedule_channel_no=1),
    "HmIP-STH": CustomConfig(make_ce_func=make_ip_thermostat, schedule_channel_no=1),
    "HmIP-WTH": CustomConfig(make_ce_func=make_ip_thermostat, schedule_channel_no=1),
    "HmIP-WGT": CustomConfig(make_ce_func=make_ip_thermostat, channels=(8,), schedule_channel_no=1),
    "HmIP-eTRV": CustomConfig(make_ce_func=make_ip_thermostat, schedule_channel_no=1),
    "HmIPW-SCTHD": CustomConfig(make_ce_func=make_ip_thermostat, schedule_channel_no=1),
    "HmIPW-STH": CustomConfig(make_ce_func=make_ip_thermostat, schedule_channel_no=1),
    "HmIPW-WTH": CustomConfig(make_ce_func=make_ip_thermostat, schedule_channel_no=1),
    "Thermostat AA": CustomConfig(make_ce_func=make_ip_thermostat),
    "ZEL STG RM FWT": CustomConfig(make_ce_func=make_simple_thermostat),
}
hmed.ALL_DEVICES[DataPointCategory.CLIMATE] = DEVICES
BLACKLISTED_DEVICES: tuple[str, ...] = ("HmIP-STHO",)
hmed.ALL_BLACKLISTED_DEVICES.append(BLACKLISTED_DEVICES)
