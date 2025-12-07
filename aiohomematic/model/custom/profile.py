# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Profile configuration dataclasses for custom data points.

This module provides type-safe dataclass definitions for device profiles,
offering a cleaner alternative to the nested dictionary structure in definition.py.

Key types:
- ChannelGroupConfig: Configuration for channel structure and field mappings
- ProfileConfig: Complete profile configuration including channel groups
- ProfileRegistry: Type alias for the profile configuration mapping

Example usage:
    from aiohomematic.model.custom.profile import ProfileConfig, ChannelGroupConfig

    MY_PROFILE = ProfileConfig(
        profile_type=ProfileType.HMIP_THERMOSTAT,
        channel_group=ChannelGroupConfig(
            repeating_fields={Field.SETPOINT: Parameter.SET_POINT_TEMPERATURE},
        ),
    )
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final, TypeAlias

from aiohomematic.const import CDPD, ChannelOffset, DeviceProfile, Field, Parameter

if TYPE_CHECKING:
    from typing import Any

__all__ = [
    "ChannelGroupConfig",
    "DEFAULT_DATA_POINTS",
    "ProfileConfig",
    "ProfileRegistry",
    "PROFILE_CONFIGS",
    "get_profile_config",
    "profile_config_to_dict",
]


@dataclass(frozen=True, kw_only=True, slots=True)
class ChannelGroupConfig:
    """
    Configuration for a channel group within a profile.

    A channel group defines the structure of channels for a device type,
    including which fields are available on each channel.
    """

    # Channel structure
    primary_channel: int | None = 0
    secondary_channels: tuple[int, ...] = ()
    state_channel_offset: int | None = None
    allow_undefined_generic_data_points: bool = False

    # Field mappings (applied to each channel in group)
    repeating_fields: Mapping[Field, Parameter] = field(default_factory=dict)
    visible_repeating_fields: Mapping[Field, Parameter] = field(default_factory=dict)

    # Channel-specific field mappings {channel_no: {field: parameter}}
    # Use ChannelOffset enum values (e.g., ChannelOffset.STATE) for semantic offsets
    channel_fields: Mapping[int | None, Mapping[Field, Parameter]] = field(default_factory=dict)
    visible_channel_fields: Mapping[int | None, Mapping[Field, Parameter]] = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True, slots=True)
class ProfileConfig:
    """Complete profile configuration for a device type."""

    profile_type: DeviceProfile
    channel_group: ChannelGroupConfig
    additional_data_points: Mapping[int, tuple[Parameter, ...]] = field(default_factory=dict)
    include_default_data_points: bool = True


# Type alias for the profile registry
ProfileRegistry: TypeAlias = Mapping[DeviceProfile, ProfileConfig]


def profile_config_to_dict(config: ProfileConfig) -> dict[str, Any]:
    """Convert a ProfileConfig to the legacy dictionary format."""
    channel_group = config.channel_group

    device_group: dict[str, Any] = {
        CDPD.PRIMARY_CHANNEL: channel_group.primary_channel,
        CDPD.ALLOW_UNDEFINED_GENERIC_DPS: channel_group.allow_undefined_generic_data_points,
    }

    if channel_group.secondary_channels:
        device_group[CDPD.SECONDARY_CHANNELS] = channel_group.secondary_channels

    if channel_group.state_channel_offset is not None:
        device_group[CDPD.STATE_CHANNEL] = channel_group.state_channel_offset

    if channel_group.repeating_fields:
        device_group[CDPD.REPEATABLE_FIELDS] = dict(channel_group.repeating_fields)

    if channel_group.visible_repeating_fields:
        device_group[CDPD.VISIBLE_REPEATABLE_FIELDS] = dict(channel_group.visible_repeating_fields)

    if channel_group.channel_fields:
        device_group[CDPD.FIELDS] = {ch: dict(fields) for ch, fields in channel_group.channel_fields.items()}

    if channel_group.visible_channel_fields:
        device_group[CDPD.VISIBLE_FIELDS] = {
            ch: dict(fields) for ch, fields in channel_group.visible_channel_fields.items()
        }

    result: dict[str, Any] = {
        CDPD.DEVICE_GROUP: device_group,
    }

    if config.additional_data_points:
        result[CDPD.ADDITIONAL_DPS] = dict(config.additional_data_points)

    if not config.include_default_data_points:
        result[CDPD.INCLUDE_DEFAULT_DPS] = False

    return result


# =============================================================================
# Profile Configurations
# =============================================================================
# These configurations mirror the definitions in definition.py but use
# type-safe dataclasses instead of nested dictionaries.


# --- Button Lock Profiles ---

IP_BUTTON_LOCK_CONFIG: Final = ProfileConfig(
    profile_type=DeviceProfile.IP_BUTTON_LOCK,
    channel_group=ChannelGroupConfig(
        allow_undefined_generic_data_points=True,
        repeating_fields={
            Field.BUTTON_LOCK: Parameter.GLOBAL_BUTTON_LOCK,
        },
    ),
)

RF_BUTTON_LOCK_CONFIG: Final = ProfileConfig(
    profile_type=DeviceProfile.RF_BUTTON_LOCK,
    channel_group=ChannelGroupConfig(
        primary_channel=None,
        allow_undefined_generic_data_points=True,
        repeating_fields={
            Field.BUTTON_LOCK: Parameter.GLOBAL_BUTTON_LOCK,
        },
    ),
)


# --- Cover Profiles ---

IP_COVER_CONFIG: Final = ProfileConfig(
    profile_type=DeviceProfile.IP_COVER,
    channel_group=ChannelGroupConfig(
        secondary_channels=(1, 2),
        state_channel_offset=ChannelOffset.STATE,
        repeating_fields={
            Field.COMBINED_PARAMETER: Parameter.COMBINED_PARAMETER,
            Field.LEVEL: Parameter.LEVEL,
            Field.LEVEL_2: Parameter.LEVEL_2,
            Field.STOP: Parameter.STOP,
        },
        channel_fields={
            ChannelOffset.STATE: {
                Field.DIRECTION: Parameter.ACTIVITY_STATE,
                Field.OPERATION_MODE: Parameter.CHANNEL_OPERATION_MODE,
            },
        },
        visible_channel_fields={
            ChannelOffset.STATE: {
                Field.GROUP_LEVEL: Parameter.LEVEL,
                Field.GROUP_LEVEL_2: Parameter.LEVEL_2,
            },
        },
    ),
)

RF_COVER_CONFIG: Final = ProfileConfig(
    profile_type=DeviceProfile.RF_COVER,
    channel_group=ChannelGroupConfig(
        repeating_fields={
            Field.DIRECTION: Parameter.DIRECTION,
            Field.LEVEL: Parameter.LEVEL,
            Field.LEVEL_2: Parameter.LEVEL_SLATS,
            Field.LEVEL_COMBINED: Parameter.LEVEL_COMBINED,
            Field.STOP: Parameter.STOP,
        },
    ),
)

IP_HDM_CONFIG: Final = ProfileConfig(
    profile_type=DeviceProfile.IP_HDM,
    channel_group=ChannelGroupConfig(
        channel_fields={
            0: {
                Field.DIRECTION: Parameter.ACTIVITY_STATE,
                Field.LEVEL: Parameter.LEVEL,
                Field.LEVEL_2: Parameter.LEVEL_2,
                Field.STOP: Parameter.STOP,
            },
        },
    ),
)

IP_GARAGE_CONFIG: Final = ProfileConfig(
    profile_type=DeviceProfile.IP_GARAGE,
    channel_group=ChannelGroupConfig(
        repeating_fields={
            Field.DOOR_COMMAND: Parameter.DOOR_COMMAND,
            Field.SECTION: Parameter.SECTION,
        },
        visible_repeating_fields={
            Field.DOOR_STATE: Parameter.DOOR_STATE,
        },
    ),
    additional_data_points={
        1: (Parameter.STATE,),
    },
)


# --- Dimmer/Light Profiles ---

IP_DIMMER_CONFIG: Final = ProfileConfig(
    profile_type=DeviceProfile.IP_DIMMER,
    channel_group=ChannelGroupConfig(
        secondary_channels=(1, 2),
        state_channel_offset=ChannelOffset.STATE,
        repeating_fields={
            Field.LEVEL: Parameter.LEVEL,
            Field.ON_TIME_VALUE: Parameter.ON_TIME,
            Field.RAMP_TIME_VALUE: Parameter.RAMP_TIME,
        },
        visible_channel_fields={
            ChannelOffset.STATE: {
                Field.GROUP_LEVEL: Parameter.LEVEL,
            },
        },
    ),
)

RF_DIMMER_CONFIG: Final = ProfileConfig(
    profile_type=DeviceProfile.RF_DIMMER,
    channel_group=ChannelGroupConfig(
        repeating_fields={
            Field.LEVEL: Parameter.LEVEL,
            Field.ON_TIME_VALUE: Parameter.ON_TIME,
            Field.RAMP_TIME_VALUE: Parameter.RAMP_TIME,
        },
    ),
)

RF_DIMMER_COLOR_CONFIG: Final = ProfileConfig(
    profile_type=DeviceProfile.RF_DIMMER_COLOR,
    channel_group=ChannelGroupConfig(
        repeating_fields={
            Field.LEVEL: Parameter.LEVEL,
            Field.ON_TIME_VALUE: Parameter.ON_TIME,
            Field.RAMP_TIME_VALUE: Parameter.RAMP_TIME,
        },
        channel_fields={
            1: {Field.COLOR: Parameter.COLOR},
            2: {Field.PROGRAM: Parameter.PROGRAM},
        },
    ),
)

RF_DIMMER_COLOR_FIXED_CONFIG: Final = ProfileConfig(
    profile_type=DeviceProfile.RF_DIMMER_COLOR_FIXED,
    channel_group=ChannelGroupConfig(
        repeating_fields={
            Field.LEVEL: Parameter.LEVEL,
            Field.ON_TIME_VALUE: Parameter.ON_TIME,
            Field.RAMP_TIME_VALUE: Parameter.RAMP_TIME,
        },
    ),
)

RF_DIMMER_COLOR_TEMP_CONFIG: Final = ProfileConfig(
    profile_type=DeviceProfile.RF_DIMMER_COLOR_TEMP,
    channel_group=ChannelGroupConfig(
        repeating_fields={
            Field.LEVEL: Parameter.LEVEL,
            Field.ON_TIME_VALUE: Parameter.ON_TIME,
            Field.RAMP_TIME_VALUE: Parameter.RAMP_TIME,
        },
        channel_fields={
            1: {Field.COLOR_LEVEL: Parameter.LEVEL},
        },
    ),
)

RF_DIMMER_WITH_VIRT_CHANNEL_CONFIG: Final = ProfileConfig(
    profile_type=DeviceProfile.RF_DIMMER_WITH_VIRT_CHANNEL,
    channel_group=ChannelGroupConfig(
        secondary_channels=(1, 2),
        repeating_fields={
            Field.LEVEL: Parameter.LEVEL,
            Field.ON_TIME_VALUE: Parameter.ON_TIME,
            Field.RAMP_TIME_VALUE: Parameter.RAMP_TIME,
        },
    ),
)

IP_FIXED_COLOR_LIGHT_CONFIG: Final = ProfileConfig(
    profile_type=DeviceProfile.IP_FIXED_COLOR_LIGHT,
    channel_group=ChannelGroupConfig(
        secondary_channels=(1, 2),
        state_channel_offset=ChannelOffset.STATE,
        repeating_fields={
            Field.COLOR: Parameter.COLOR,
            Field.COLOR_BEHAVIOUR: Parameter.COLOR_BEHAVIOUR,
            Field.LEVEL: Parameter.LEVEL,
            Field.ON_TIME_UNIT: Parameter.DURATION_UNIT,
            Field.ON_TIME_VALUE: Parameter.DURATION_VALUE,
            Field.RAMP_TIME_UNIT: Parameter.RAMP_TIME_UNIT,
            Field.RAMP_TIME_VALUE: Parameter.RAMP_TIME_VALUE,
        },
        visible_channel_fields={
            ChannelOffset.STATE: {
                Field.CHANNEL_COLOR: Parameter.COLOR,
                Field.GROUP_LEVEL: Parameter.LEVEL,
            },
        },
    ),
)

IP_SIMPLE_FIXED_COLOR_LIGHT_WIRED_CONFIG: Final = ProfileConfig(
    profile_type=DeviceProfile.IP_SIMPLE_FIXED_COLOR_LIGHT_WIRED,
    channel_group=ChannelGroupConfig(
        repeating_fields={
            Field.COLOR: Parameter.COLOR,
            Field.COLOR_BEHAVIOUR: Parameter.COLOR_BEHAVIOUR,
            Field.LEVEL: Parameter.LEVEL,
            Field.ON_TIME_UNIT: Parameter.DURATION_UNIT,
            Field.ON_TIME_VALUE: Parameter.DURATION_VALUE,
            Field.RAMP_TIME_UNIT: Parameter.RAMP_TIME_UNIT,
            Field.RAMP_TIME_VALUE: Parameter.RAMP_TIME_VALUE,
        },
    ),
)

IP_SIMPLE_FIXED_COLOR_LIGHT_CONFIG: Final = ProfileConfig(
    profile_type=DeviceProfile.IP_SIMPLE_FIXED_COLOR_LIGHT,
    channel_group=ChannelGroupConfig(
        repeating_fields={
            Field.COLOR: Parameter.COLOR,
            Field.LEVEL: Parameter.LEVEL,
            Field.ON_TIME_UNIT: Parameter.DURATION_UNIT,
            Field.ON_TIME_VALUE: Parameter.DURATION_VALUE,
            Field.RAMP_TIME_UNIT: Parameter.RAMP_TIME_UNIT,
            Field.RAMP_TIME_VALUE: Parameter.RAMP_TIME_VALUE,
        },
    ),
)

IP_RGBW_LIGHT_CONFIG: Final = ProfileConfig(
    profile_type=DeviceProfile.IP_RGBW_LIGHT,
    channel_group=ChannelGroupConfig(
        secondary_channels=(1, 2, 3),
        repeating_fields={
            Field.COLOR_TEMPERATURE: Parameter.COLOR_TEMPERATURE,
            Field.DIRECTION: Parameter.ACTIVITY_STATE,
            Field.ON_TIME_VALUE: Parameter.DURATION_VALUE,
            Field.ON_TIME_UNIT: Parameter.DURATION_UNIT,
            Field.EFFECT: Parameter.EFFECT,
            Field.HUE: Parameter.HUE,
            Field.LEVEL: Parameter.LEVEL,
            Field.RAMP_TIME_TO_OFF_UNIT: Parameter.RAMP_TIME_TO_OFF_UNIT,
            Field.RAMP_TIME_TO_OFF_VALUE: Parameter.RAMP_TIME_TO_OFF_VALUE,
            Field.RAMP_TIME_UNIT: Parameter.RAMP_TIME_UNIT,
            Field.RAMP_TIME_VALUE: Parameter.RAMP_TIME_VALUE,
            Field.SATURATION: Parameter.SATURATION,
        },
        channel_fields={
            ChannelOffset.STATE: {
                Field.DEVICE_OPERATION_MODE: Parameter.DEVICE_OPERATION_MODE,
            },
        },
    ),
)

IP_DRG_DALI_CONFIG: Final = ProfileConfig(
    profile_type=DeviceProfile.IP_DRG_DALI,
    channel_group=ChannelGroupConfig(
        repeating_fields={
            Field.COLOR_TEMPERATURE: Parameter.COLOR_TEMPERATURE,
            Field.ON_TIME_VALUE: Parameter.DURATION_VALUE,
            Field.ON_TIME_UNIT: Parameter.DURATION_UNIT,
            Field.EFFECT: Parameter.EFFECT,
            Field.HUE: Parameter.HUE,
            Field.LEVEL: Parameter.LEVEL,
            Field.RAMP_TIME_TO_OFF_UNIT: Parameter.RAMP_TIME_TO_OFF_UNIT,
            Field.RAMP_TIME_TO_OFF_VALUE: Parameter.RAMP_TIME_TO_OFF_VALUE,
            Field.RAMP_TIME_UNIT: Parameter.RAMP_TIME_UNIT,
            Field.RAMP_TIME_VALUE: Parameter.RAMP_TIME_VALUE,
            Field.SATURATION: Parameter.SATURATION,
        },
    ),
)


# --- Switch Profiles ---

IP_SWITCH_CONFIG: Final = ProfileConfig(
    profile_type=DeviceProfile.IP_SWITCH,
    channel_group=ChannelGroupConfig(
        secondary_channels=(1, 2),
        state_channel_offset=ChannelOffset.STATE,
        repeating_fields={
            Field.STATE: Parameter.STATE,
            Field.ON_TIME_VALUE: Parameter.ON_TIME,
        },
        visible_channel_fields={
            ChannelOffset.STATE: {
                Field.GROUP_STATE: Parameter.STATE,
            },
        },
    ),
    additional_data_points={
        3: (
            Parameter.CURRENT,
            Parameter.ENERGY_COUNTER,
            Parameter.ENERGY_COUNTER_FEED_IN,
            Parameter.FREQUENCY,
            Parameter.POWER,
            Parameter.ACTUAL_TEMPERATURE,
            Parameter.VOLTAGE,
        ),
    },
)

RF_SWITCH_CONFIG: Final = ProfileConfig(
    profile_type=DeviceProfile.RF_SWITCH,
    channel_group=ChannelGroupConfig(
        repeating_fields={
            Field.STATE: Parameter.STATE,
            Field.ON_TIME_VALUE: Parameter.ON_TIME,
        },
    ),
    additional_data_points={
        1: (
            Parameter.CURRENT,
            Parameter.ENERGY_COUNTER,
            Parameter.FREQUENCY,
            Parameter.POWER,
            Parameter.VOLTAGE,
        ),
    },
)

IP_IRRIGATION_VALVE_CONFIG: Final = ProfileConfig(
    profile_type=DeviceProfile.IP_IRRIGATION_VALVE,
    channel_group=ChannelGroupConfig(
        secondary_channels=(1, 2),
        repeating_fields={
            Field.STATE: Parameter.STATE,
            Field.ON_TIME_VALUE: Parameter.ON_TIME,
        },
        visible_channel_fields={
            ChannelOffset.STATE: {
                Field.GROUP_STATE: Parameter.STATE,
            },
        },
    ),
    additional_data_points={
        ChannelOffset.SENSOR: (
            Parameter.WATER_FLOW,
            Parameter.WATER_VOLUME,
            Parameter.WATER_VOLUME_SINCE_OPEN,
        ),
    },
)


# --- Lock Profiles ---

IP_LOCK_CONFIG: Final = ProfileConfig(
    profile_type=DeviceProfile.IP_LOCK,
    channel_group=ChannelGroupConfig(
        repeating_fields={
            Field.DIRECTION: Parameter.ACTIVITY_STATE,
            Field.LOCK_STATE: Parameter.LOCK_STATE,
            Field.LOCK_TARGET_LEVEL: Parameter.LOCK_TARGET_LEVEL,
        },
        channel_fields={
            ChannelOffset.STATE: {
                Field.ERROR: Parameter.ERROR_JAMMED,
            },
        },
    ),
)

RF_LOCK_CONFIG: Final = ProfileConfig(
    profile_type=DeviceProfile.RF_LOCK,
    channel_group=ChannelGroupConfig(
        repeating_fields={
            Field.DIRECTION: Parameter.DIRECTION,
            Field.OPEN: Parameter.OPEN,
            Field.STATE: Parameter.STATE,
            Field.ERROR: Parameter.ERROR,
        },
    ),
)


# --- Siren Profiles ---

IP_SIREN_CONFIG: Final = ProfileConfig(
    profile_type=DeviceProfile.IP_SIREN,
    channel_group=ChannelGroupConfig(
        repeating_fields={
            Field.ACOUSTIC_ALARM_ACTIVE: Parameter.ACOUSTIC_ALARM_ACTIVE,
            Field.OPTICAL_ALARM_ACTIVE: Parameter.OPTICAL_ALARM_ACTIVE,
            Field.ACOUSTIC_ALARM_SELECTION: Parameter.ACOUSTIC_ALARM_SELECTION,
            Field.OPTICAL_ALARM_SELECTION: Parameter.OPTICAL_ALARM_SELECTION,
            Field.DURATION: Parameter.DURATION_VALUE,
            Field.DURATION_UNIT: Parameter.DURATION_UNIT,
        },
    ),
)

IP_SIREN_SMOKE_CONFIG: Final = ProfileConfig(
    profile_type=DeviceProfile.IP_SIREN_SMOKE,
    channel_group=ChannelGroupConfig(
        repeating_fields={
            Field.SMOKE_DETECTOR_COMMAND: Parameter.SMOKE_DETECTOR_COMMAND,
        },
        visible_repeating_fields={
            Field.SMOKE_DETECTOR_ALARM_STATUS: Parameter.SMOKE_DETECTOR_ALARM_STATUS,
        },
    ),
)


# --- Thermostat Profiles ---

IP_THERMOSTAT_CONFIG: Final = ProfileConfig(
    profile_type=DeviceProfile.IP_THERMOSTAT,
    channel_group=ChannelGroupConfig(
        repeating_fields={
            Field.ACTIVE_PROFILE: Parameter.ACTIVE_PROFILE,
            Field.BOOST_MODE: Parameter.BOOST_MODE,
            Field.CONTROL_MODE: Parameter.CONTROL_MODE,
            Field.MIN_MAX_VALUE_NOT_RELEVANT_FOR_MANU_MODE: Parameter.MIN_MAX_VALUE_NOT_RELEVANT_FOR_MANU_MODE,
            Field.OPTIMUM_START_STOP: Parameter.OPTIMUM_START_STOP,
            Field.PARTY_MODE: Parameter.PARTY_MODE,
            Field.SETPOINT: Parameter.SET_POINT_TEMPERATURE,
            Field.SET_POINT_MODE: Parameter.SET_POINT_MODE,
            Field.TEMPERATURE_MAXIMUM: Parameter.TEMPERATURE_MAXIMUM,
            Field.TEMPERATURE_MINIMUM: Parameter.TEMPERATURE_MINIMUM,
            Field.TEMPERATURE_OFFSET: Parameter.TEMPERATURE_OFFSET,
        },
        visible_repeating_fields={
            Field.HEATING_COOLING: Parameter.HEATING_COOLING,
            Field.HUMIDITY: Parameter.HUMIDITY,
            Field.TEMPERATURE: Parameter.ACTUAL_TEMPERATURE,
        },
        visible_channel_fields={
            0: {
                Field.LEVEL: Parameter.LEVEL,
                Field.CONCENTRATION: Parameter.CONCENTRATION,
            },
            8: {  # BWTH
                Field.STATE: Parameter.STATE,
            },
        },
        channel_fields={
            7: {
                Field.HEATING_VALVE_TYPE: Parameter.HEATING_VALVE_TYPE,
            },
            ChannelOffset.CONFIG: {  # WGTC
                Field.STATE: Parameter.STATE,
            },
        },
    ),
)

IP_THERMOSTAT_GROUP_CONFIG: Final = ProfileConfig(
    profile_type=DeviceProfile.IP_THERMOSTAT_GROUP,
    channel_group=ChannelGroupConfig(
        repeating_fields={
            Field.ACTIVE_PROFILE: Parameter.ACTIVE_PROFILE,
            Field.BOOST_MODE: Parameter.BOOST_MODE,
            Field.CONTROL_MODE: Parameter.CONTROL_MODE,
            Field.HEATING_VALVE_TYPE: Parameter.HEATING_VALVE_TYPE,
            Field.MIN_MAX_VALUE_NOT_RELEVANT_FOR_MANU_MODE: Parameter.MIN_MAX_VALUE_NOT_RELEVANT_FOR_MANU_MODE,
            Field.OPTIMUM_START_STOP: Parameter.OPTIMUM_START_STOP,
            Field.PARTY_MODE: Parameter.PARTY_MODE,
            Field.SETPOINT: Parameter.SET_POINT_TEMPERATURE,
            Field.SET_POINT_MODE: Parameter.SET_POINT_MODE,
            Field.TEMPERATURE_MAXIMUM: Parameter.TEMPERATURE_MAXIMUM,
            Field.TEMPERATURE_MINIMUM: Parameter.TEMPERATURE_MINIMUM,
            Field.TEMPERATURE_OFFSET: Parameter.TEMPERATURE_OFFSET,
        },
        visible_repeating_fields={
            Field.HEATING_COOLING: Parameter.HEATING_COOLING,
            Field.HUMIDITY: Parameter.HUMIDITY,
            Field.TEMPERATURE: Parameter.ACTUAL_TEMPERATURE,
        },
        channel_fields={
            0: {
                Field.LEVEL: Parameter.LEVEL,
            },
            3: {
                Field.STATE: Parameter.STATE,
            },
        },
    ),
    include_default_data_points=False,
)

RF_THERMOSTAT_CONFIG: Final = ProfileConfig(
    profile_type=DeviceProfile.RF_THERMOSTAT,
    channel_group=ChannelGroupConfig(
        repeating_fields={
            Field.AUTO_MODE: Parameter.AUTO_MODE,
            Field.BOOST_MODE: Parameter.BOOST_MODE,
            Field.COMFORT_MODE: Parameter.COMFORT_MODE,
            Field.CONTROL_MODE: Parameter.CONTROL_MODE,
            Field.LOWERING_MODE: Parameter.LOWERING_MODE,
            Field.MANU_MODE: Parameter.MANU_MODE,
            Field.SETPOINT: Parameter.SET_TEMPERATURE,
        },
        channel_fields={
            None: {
                Field.MIN_MAX_VALUE_NOT_RELEVANT_FOR_MANU_MODE: Parameter.MIN_MAX_VALUE_NOT_RELEVANT_FOR_MANU_MODE,
                Field.TEMPERATURE_MAXIMUM: Parameter.TEMPERATURE_MAXIMUM,
                Field.TEMPERATURE_MINIMUM: Parameter.TEMPERATURE_MINIMUM,
                Field.TEMPERATURE_OFFSET: Parameter.TEMPERATURE_OFFSET,
                Field.WEEK_PROGRAM_POINTER: Parameter.WEEK_PROGRAM_POINTER,
            },
        },
        visible_repeating_fields={
            Field.HUMIDITY: Parameter.ACTUAL_HUMIDITY,
            Field.TEMPERATURE: Parameter.ACTUAL_TEMPERATURE,
        },
        visible_channel_fields={
            0: {
                Field.VALVE_STATE: Parameter.VALVE_STATE,
            },
        },
    ),
)

RF_THERMOSTAT_GROUP_CONFIG: Final = ProfileConfig(
    profile_type=DeviceProfile.RF_THERMOSTAT_GROUP,
    channel_group=ChannelGroupConfig(
        repeating_fields={
            Field.AUTO_MODE: Parameter.AUTO_MODE,
            Field.BOOST_MODE: Parameter.BOOST_MODE,
            Field.COMFORT_MODE: Parameter.COMFORT_MODE,
            Field.CONTROL_MODE: Parameter.CONTROL_MODE,
            Field.LOWERING_MODE: Parameter.LOWERING_MODE,
            Field.MANU_MODE: Parameter.MANU_MODE,
            Field.SETPOINT: Parameter.SET_TEMPERATURE,
        },
        channel_fields={
            None: {
                Field.MIN_MAX_VALUE_NOT_RELEVANT_FOR_MANU_MODE: Parameter.MIN_MAX_VALUE_NOT_RELEVANT_FOR_MANU_MODE,
                Field.TEMPERATURE_MAXIMUM: Parameter.TEMPERATURE_MAXIMUM,
                Field.TEMPERATURE_MINIMUM: Parameter.TEMPERATURE_MINIMUM,
                Field.TEMPERATURE_OFFSET: Parameter.TEMPERATURE_OFFSET,
                Field.WEEK_PROGRAM_POINTER: Parameter.WEEK_PROGRAM_POINTER,
            },
        },
        visible_repeating_fields={
            Field.HUMIDITY: Parameter.ACTUAL_HUMIDITY,
            Field.TEMPERATURE: Parameter.ACTUAL_TEMPERATURE,
        },
        visible_channel_fields={
            0: {
                Field.VALVE_STATE: Parameter.VALVE_STATE,
            },
        },
    ),
    include_default_data_points=False,
)

SIMPLE_RF_THERMOSTAT_CONFIG: Final = ProfileConfig(
    profile_type=DeviceProfile.SIMPLE_RF_THERMOSTAT,
    channel_group=ChannelGroupConfig(
        visible_repeating_fields={
            Field.HUMIDITY: Parameter.HUMIDITY,
            Field.TEMPERATURE: Parameter.TEMPERATURE,
        },
        channel_fields={
            1: {
                Field.SETPOINT: Parameter.SETPOINT,
            },
        },
    ),
)


# =============================================================================
# Default Data Points
# =============================================================================

# These parameters are added to all custom data points by default
# (unless include_default_data_points=False in ProfileConfig)
DEFAULT_DATA_POINTS: Final[Mapping[int | tuple[int, ...], tuple[Parameter, ...]]] = {
    0: (
        Parameter.ACTUAL_TEMPERATURE,
        Parameter.DUTY_CYCLE,
        Parameter.DUTYCYCLE,
        Parameter.LOW_BAT,
        Parameter.LOWBAT,
        Parameter.OPERATING_VOLTAGE,
        Parameter.RSSI_DEVICE,
        Parameter.RSSI_PEER,
        Parameter.SABOTAGE,
        Parameter.TIME_OF_OPERATION,
    ),
    2: (Parameter.BATTERY_STATE,),
    4: (Parameter.BATTERY_STATE,),
}


# =============================================================================
# Profile Registry
# =============================================================================

PROFILE_CONFIGS: Final[ProfileRegistry] = {
    # Button Lock
    DeviceProfile.IP_BUTTON_LOCK: IP_BUTTON_LOCK_CONFIG,
    DeviceProfile.RF_BUTTON_LOCK: RF_BUTTON_LOCK_CONFIG,
    # Cover
    DeviceProfile.IP_COVER: IP_COVER_CONFIG,
    DeviceProfile.IP_GARAGE: IP_GARAGE_CONFIG,
    DeviceProfile.IP_HDM: IP_HDM_CONFIG,
    DeviceProfile.RF_COVER: RF_COVER_CONFIG,
    # Dimmer/Light
    DeviceProfile.IP_DIMMER: IP_DIMMER_CONFIG,
    DeviceProfile.IP_DRG_DALI: IP_DRG_DALI_CONFIG,
    DeviceProfile.IP_FIXED_COLOR_LIGHT: IP_FIXED_COLOR_LIGHT_CONFIG,
    DeviceProfile.IP_RGBW_LIGHT: IP_RGBW_LIGHT_CONFIG,
    DeviceProfile.IP_SIMPLE_FIXED_COLOR_LIGHT: IP_SIMPLE_FIXED_COLOR_LIGHT_CONFIG,
    DeviceProfile.IP_SIMPLE_FIXED_COLOR_LIGHT_WIRED: IP_SIMPLE_FIXED_COLOR_LIGHT_WIRED_CONFIG,
    DeviceProfile.RF_DIMMER: RF_DIMMER_CONFIG,
    DeviceProfile.RF_DIMMER_COLOR: RF_DIMMER_COLOR_CONFIG,
    DeviceProfile.RF_DIMMER_COLOR_FIXED: RF_DIMMER_COLOR_FIXED_CONFIG,
    DeviceProfile.RF_DIMMER_COLOR_TEMP: RF_DIMMER_COLOR_TEMP_CONFIG,
    DeviceProfile.RF_DIMMER_WITH_VIRT_CHANNEL: RF_DIMMER_WITH_VIRT_CHANNEL_CONFIG,
    # Switch
    DeviceProfile.IP_IRRIGATION_VALVE: IP_IRRIGATION_VALVE_CONFIG,
    DeviceProfile.IP_SWITCH: IP_SWITCH_CONFIG,
    DeviceProfile.RF_SWITCH: RF_SWITCH_CONFIG,
    # Lock
    DeviceProfile.IP_LOCK: IP_LOCK_CONFIG,
    DeviceProfile.RF_LOCK: RF_LOCK_CONFIG,
    # Siren
    DeviceProfile.IP_SIREN: IP_SIREN_CONFIG,
    DeviceProfile.IP_SIREN_SMOKE: IP_SIREN_SMOKE_CONFIG,
    # Thermostat
    DeviceProfile.IP_THERMOSTAT: IP_THERMOSTAT_CONFIG,
    DeviceProfile.IP_THERMOSTAT_GROUP: IP_THERMOSTAT_GROUP_CONFIG,
    DeviceProfile.RF_THERMOSTAT: RF_THERMOSTAT_CONFIG,
    DeviceProfile.RF_THERMOSTAT_GROUP: RF_THERMOSTAT_GROUP_CONFIG,
    DeviceProfile.SIMPLE_RF_THERMOSTAT: SIMPLE_RF_THERMOSTAT_CONFIG,
}


def get_profile_config(profile_type: DeviceProfile) -> ProfileConfig:
    """Return the profile configuration for a given profile type."""
    return PROFILE_CONFIGS[profile_type]
