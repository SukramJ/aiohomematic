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
            fields={Field.SETPOINT: Parameter.SET_POINT_TEMPERATURE},
        ),
    )
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final, TypeAlias

from aiohomematic.const import ChannelOffset, DeviceProfile, Field, Parameter

__all__ = [
    "ChannelGroupConfig",
    "DEFAULT_DATA_POINTS",
    "ProfileConfig",
    "ProfileRegistry",
    "PROFILE_CONFIGS",
    "RebasedChannelGroupConfig",
    "get_profile_config",
    "rebase_channel_group",
]


@dataclass(frozen=True, kw_only=True, slots=True)
class ChannelGroupConfig:
    """
    Configuration for a channel group within a profile.

    A channel group defines the structure of channels for a device type,
    including which fields are available on each channel.

    Channel Number Convention
    -------------------------
    This configuration uses two types of channel numbers:

    **Relative channel numbers** (used in most fields):
    - `primary_channel`, `secondary_channels`, `state_channel_offset`
    - `channel_fields`, `visible_channel_fields`

    These are **offsets from a base channel** (group_no). The base channel is
    determined at device registration time via DeviceProfileRegistry.register(channels=(...)).

    For example, with a configuration of:
        primary_channel=1, secondary_channels=(2, 3)

    And registration with channels=(4,):
        - group_no becomes 4
        - Actual primary_channel = 4 + 1 = 5
        - Actual secondary_channels = (4 + 2, 4 + 3) = (6, 7)

    The conversion from relative to absolute channel numbers is performed by
    rebase_channel_group(), which produces a RebasedChannelGroupConfig.

    **Absolute channel numbers** (fixed, not rebased):
    - `fixed_channel_fields`, `visible_fixed_channel_fields`

    These are used for fields that must always reference specific device channels,
    regardless of which channel group is being created. Common use case: channel 0
    parameters that apply to the entire device.

    Special Values
    --------------
    - primary_channel=0: The primary channel is the base channel itself (group_no)
    - primary_channel=None: No primary channel defined
    - ChannelOffset enum values can be used for semantic offsets in channel_fields
    """

    # Channel structure (relative to group_no base channel)
    primary_channel: int | None = 0
    secondary_channels: tuple[int, ...] = ()
    state_channel_offset: int | None = None
    allow_undefined_generic_data_points: bool = False

    # Field mappings applied to the primary channel (not channel-specific)
    fields: Mapping[Field, Parameter] = field(default_factory=dict)
    visible_fields: Mapping[Field, Parameter] = field(default_factory=dict)

    # Channel-specific field mappings with RELATIVE channel offsets
    # {channel_offset: {field: parameter}} - channel numbers are offsets from group_no
    # Use ChannelOffset enum values (e.g., ChannelOffset.STATE) for semantic offsets.
    channel_fields: Mapping[int | None, Mapping[Field, Parameter]] = field(default_factory=dict)
    visible_channel_fields: Mapping[int | None, Mapping[Field, Parameter]] = field(default_factory=dict)

    # Channel-specific field mappings with ABSOLUTE (fixed) channel numbers
    # {channel_no: {field: parameter}} - channel numbers are NOT rebased
    # Use for fields that must always reference specific device channels (e.g., channel 0).
    fixed_channel_fields: Mapping[int, Mapping[Field, Parameter]] = field(default_factory=dict)
    visible_fixed_channel_fields: Mapping[int, Mapping[Field, Parameter]] = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True, slots=True)
class ProfileConfig:
    """Complete profile configuration for a device type."""

    profile_type: DeviceProfile
    channel_group: ChannelGroupConfig
    additional_data_points: Mapping[int, tuple[Parameter, ...]] = field(default_factory=dict)
    include_default_data_points: bool = True


@dataclass(frozen=True, kw_only=True, slots=True)
class RebasedChannelGroupConfig:
    """
    Channel group configuration with rebased channel numbers.

    This dataclass contains channel configuration with all relative channel numbers
    adjusted by the group offset. Used by CustomDataPoint to access field
    mappings without dictionary-based lookups.

    All channel numbers in this config are **absolute** (actual device channels):
    - `primary_channel`, `secondary_channels`, `state_channel` - rebased from offsets
    - `channel_fields`, `visible_channel_fields` - rebased from offsets
    - `fixed_channel_fields`, `visible_fixed_channel_fields` - already absolute (unchanged)
    """

    # Rebased channel structure (actual channel numbers after applying group_no)
    primary_channel: int | None
    secondary_channels: tuple[int, ...]
    state_channel: int | None
    allow_undefined_generic_data_points: bool

    # Field mappings applied to the primary channel
    fields: Mapping[Field, Parameter]
    visible_fields: Mapping[Field, Parameter]

    # Channel-specific field mappings (rebased to actual channel numbers)
    channel_fields: Mapping[int | None, Mapping[Field, Parameter]]
    visible_channel_fields: Mapping[int | None, Mapping[Field, Parameter]]

    # Fixed channel field mappings (absolute channel numbers, not rebased)
    fixed_channel_fields: Mapping[int, Mapping[Field, Parameter]]
    visible_fixed_channel_fields: Mapping[int, Mapping[Field, Parameter]]


def rebase_channel_group(
    *,
    profile_config: ProfileConfig,
    group_no: int | None,
) -> RebasedChannelGroupConfig:
    """
    Create a rebased channel group from a ProfileConfig.

    Applies the group offset to relative channel numbers in the configuration,
    producing a RebasedChannelGroupConfig with actual channel numbers.

    Fixed channel fields are passed through unchanged (they use absolute channel numbers).

    Args:
        profile_config: The profile configuration to rebase.
        group_no: The group offset to apply (None means no offset).

    Returns:
        RebasedChannelGroupConfig with rebased channel numbers.

    """
    cg = profile_config.channel_group
    offset = group_no or 0

    # Rebase primary channel
    primary = cg.primary_channel
    if primary is not None and offset:
        primary = primary + offset

    # Rebase secondary channels
    secondary = tuple(ch + offset for ch in cg.secondary_channels) if offset else cg.secondary_channels

    # Rebase state channel
    state = None
    if cg.state_channel_offset is not None:
        state = cg.state_channel_offset + offset if offset else cg.state_channel_offset

    # Rebase channel_fields (relative -> absolute)
    channel_fields: dict[int | None, Mapping[Field, Parameter]] = {}
    for ch_no, ch_fields in cg.channel_fields.items():
        if ch_no is None:
            channel_fields[None] = ch_fields
        else:
            channel_fields[ch_no + offset] = ch_fields

    # Rebase visible_channel_fields (relative -> absolute)
    visible_channel_fields: dict[int | None, Mapping[Field, Parameter]] = {}
    for ch_no, ch_fields in cg.visible_channel_fields.items():
        if ch_no is None:
            visible_channel_fields[None] = ch_fields
        else:
            visible_channel_fields[ch_no + offset] = ch_fields

    # Fixed channel fields are NOT rebased (already absolute)
    return RebasedChannelGroupConfig(
        primary_channel=primary,
        secondary_channels=secondary,
        state_channel=state,
        allow_undefined_generic_data_points=cg.allow_undefined_generic_data_points,
        fields=cg.fields,
        visible_fields=cg.visible_fields,
        channel_fields=channel_fields,
        visible_channel_fields=visible_channel_fields,
        fixed_channel_fields=cg.fixed_channel_fields,
        visible_fixed_channel_fields=cg.visible_fixed_channel_fields,
    )


# Type alias for the profile registry
ProfileRegistry: TypeAlias = Mapping[DeviceProfile, ProfileConfig]


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
        fields={
            Field.BUTTON_LOCK: Parameter.GLOBAL_BUTTON_LOCK,
        },
    ),
)

RF_BUTTON_LOCK_CONFIG: Final = ProfileConfig(
    profile_type=DeviceProfile.RF_BUTTON_LOCK,
    channel_group=ChannelGroupConfig(
        primary_channel=None,
        allow_undefined_generic_data_points=True,
        fields={
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
        fields={
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
        fields={
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
        fields={
            Field.DOOR_COMMAND: Parameter.DOOR_COMMAND,
            Field.SECTION: Parameter.SECTION,
        },
        visible_fields={
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
        fields={
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
        fields={
            Field.LEVEL: Parameter.LEVEL,
            Field.ON_TIME_VALUE: Parameter.ON_TIME,
            Field.RAMP_TIME_VALUE: Parameter.RAMP_TIME,
        },
    ),
)

RF_DIMMER_COLOR_CONFIG: Final = ProfileConfig(
    profile_type=DeviceProfile.RF_DIMMER_COLOR,
    channel_group=ChannelGroupConfig(
        fields={
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
        fields={
            Field.LEVEL: Parameter.LEVEL,
            Field.ON_TIME_VALUE: Parameter.ON_TIME,
            Field.RAMP_TIME_VALUE: Parameter.RAMP_TIME,
        },
    ),
)

RF_DIMMER_COLOR_TEMP_CONFIG: Final = ProfileConfig(
    profile_type=DeviceProfile.RF_DIMMER_COLOR_TEMP,
    channel_group=ChannelGroupConfig(
        fields={
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
        fields={
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
        fields={
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
        fields={
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
        fields={
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
        fields={
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
        fields={
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
        fields={
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
        fields={
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
        fields={
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
        fields={
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
        fields={
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
        fields={
            Field.ACOUSTIC_ALARM_ACTIVE: Parameter.ACOUSTIC_ALARM_ACTIVE,
            Field.OPTICAL_ALARM_ACTIVE: Parameter.OPTICAL_ALARM_ACTIVE,
            Field.DURATION: Parameter.DURATION_VALUE,
            Field.DURATION_UNIT: Parameter.DURATION_UNIT,
        },
        visible_fields={
            Field.ACOUSTIC_ALARM_SELECTION: Parameter.ACOUSTIC_ALARM_SELECTION,
            Field.OPTICAL_ALARM_SELECTION: Parameter.OPTICAL_ALARM_SELECTION,
        },
    ),
)

IP_SIREN_SMOKE_CONFIG: Final = ProfileConfig(
    profile_type=DeviceProfile.IP_SIREN_SMOKE,
    channel_group=ChannelGroupConfig(
        fields={
            Field.SMOKE_DETECTOR_COMMAND: Parameter.SMOKE_DETECTOR_COMMAND,
        },
        visible_fields={
            Field.SMOKE_DETECTOR_ALARM_STATUS: Parameter.SMOKE_DETECTOR_ALARM_STATUS,
        },
    ),
)


# --- Sound Player Profiles ---

IP_SOUND_PLAYER_CONFIG: Final = ProfileConfig(
    profile_type=DeviceProfile.IP_SOUND_PLAYER,
    channel_group=ChannelGroupConfig(
        fields={
            Field.DIRECTION: Parameter.ACTIVITY_STATE,
            Field.DURATION_UNIT: Parameter.DURATION_UNIT,
            Field.DURATION_VALUE: Parameter.DURATION_VALUE,
            Field.LEVEL: Parameter.LEVEL,
            Field.RAMP_TIME_UNIT: Parameter.RAMP_TIME_UNIT,
            Field.RAMP_TIME_VALUE: Parameter.RAMP_TIME_VALUE,
            Field.REPETITIONS: Parameter.REPETITIONS,
            Field.SOUNDFILE: Parameter.SOUNDFILE,
        },
    ),
)

IP_SOUND_PLAYER_LED_CONFIG: Final = ProfileConfig(
    profile_type=DeviceProfile.IP_SOUND_PLAYER_LED,
    channel_group=ChannelGroupConfig(
        fields={
            Field.COLOR: Parameter.COLOR,
            Field.DIRECTION: Parameter.ACTIVITY_STATE,
            Field.DURATION_UNIT: Parameter.DURATION_UNIT,
            Field.DURATION_VALUE: Parameter.DURATION_VALUE,
            Field.LEVEL: Parameter.LEVEL,
            Field.ON_TIME_LIST: Parameter.ON_TIME_LIST_1,
            Field.RAMP_TIME_UNIT: Parameter.RAMP_TIME_UNIT,
            Field.RAMP_TIME_VALUE: Parameter.RAMP_TIME_VALUE,
            Field.REPETITIONS: Parameter.REPETITIONS,
        },
    ),
)


# --- Text Display Profiles ---

IP_TEXT_DISPLAY_CONFIG: Final = ProfileConfig(
    profile_type=DeviceProfile.IP_TEXT_DISPLAY,
    channel_group=ChannelGroupConfig(
        fields={
            Field.ACOUSTIC_NOTIFICATION_SELECTION: Parameter.ACOUSTIC_NOTIFICATION_SELECTION,
            Field.DISPLAY_DATA_ALIGNMENT: Parameter.DISPLAY_DATA_ALIGNMENT,
            Field.DISPLAY_DATA_BACKGROUND_COLOR: Parameter.DISPLAY_DATA_BACKGROUND_COLOR,
            Field.DISPLAY_DATA_COMMIT: Parameter.DISPLAY_DATA_COMMIT,
            Field.DISPLAY_DATA_ICON: Parameter.DISPLAY_DATA_ICON,
            Field.DISPLAY_DATA_ID: Parameter.DISPLAY_DATA_ID,
            Field.DISPLAY_DATA_STRING: Parameter.DISPLAY_DATA_STRING,
            Field.DISPLAY_DATA_TEXT_COLOR: Parameter.DISPLAY_DATA_TEXT_COLOR,
            Field.INTERVAL: Parameter.INTERVAL,
            Field.REPETITIONS: Parameter.REPETITIONS,
        },
        visible_fixed_channel_fields={
            0: {Field.BURST_LIMIT_WARNING: Parameter.BURST_LIMIT_WARNING},
        },
    ),
)


# --- Thermostat Profiles ---

IP_THERMOSTAT_CONFIG: Final = ProfileConfig(
    profile_type=DeviceProfile.IP_THERMOSTAT,
    channel_group=ChannelGroupConfig(
        fields={
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
        visible_fields={
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
        fields={
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
        visible_fields={
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
        fields={
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
        visible_fields={
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
        fields={
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
        visible_fields={
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
        visible_fields={
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
    # Sound Player
    DeviceProfile.IP_SOUND_PLAYER: IP_SOUND_PLAYER_CONFIG,
    DeviceProfile.IP_SOUND_PLAYER_LED: IP_SOUND_PLAYER_LED_CONFIG,
    # Text Display
    DeviceProfile.IP_TEXT_DISPLAY: IP_TEXT_DISPLAY_CONFIG,
    # Thermostat
    DeviceProfile.IP_THERMOSTAT: IP_THERMOSTAT_CONFIG,
    DeviceProfile.IP_THERMOSTAT_GROUP: IP_THERMOSTAT_GROUP_CONFIG,
    DeviceProfile.RF_THERMOSTAT: RF_THERMOSTAT_CONFIG,
    DeviceProfile.RF_THERMOSTAT_GROUP: RF_THERMOSTAT_GROUP_CONFIG,
    DeviceProfile.SIMPLE_RF_THERMOSTAT: SIMPLE_RF_THERMOSTAT_CONFIG,
}


def get_profile_config(*, profile_type: DeviceProfile) -> ProfileConfig:
    """Return the profile configuration for a given profile type."""
    return PROFILE_CONFIGS[profile_type]
