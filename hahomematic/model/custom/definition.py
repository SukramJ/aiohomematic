"""The module contains device descriptions for custom data points."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import logging
from typing import Any, Final, cast

import voluptuous as vol

from hahomematic import support as hms, validator as val
from hahomematic.const import DataPointCategory, Parameter
from hahomematic.exceptions import HaHomematicException
from hahomematic.model import device as hmd
from hahomematic.model.custom.const import CDPD, DeviceProfile, Field
from hahomematic.model.custom.support import CustomConfig
from hahomematic.model.support import generate_unique_id
from hahomematic.support import reduce_args

_LOGGER: Final = logging.getLogger(__name__)

DEFAULT_INCLUDE_DEFAULT_DPS: Final = True

ALL_DEVICES: dict[DataPointCategory, Mapping[str, CustomConfig | tuple[CustomConfig, ...]]] = {}
ALL_BLACKLISTED_DEVICES: list[tuple[str, ...]] = []

_SCHEMA_ADDITIONAL_DPS = vol.Schema(
    {vol.Required(vol.Any(val.positive_int, tuple[int, ...])): vol.Schema((vol.Optional(Parameter),))}
)

_SCHEMA_FIELD_DETAILS = vol.Schema({vol.Required(Field): Parameter})

_SCHEMA_FIELD = vol.Schema({vol.Required(int): _SCHEMA_FIELD_DETAILS})

_SCHEMA_DEVICE_GROUP = vol.Schema(
    {
        vol.Required(CDPD.PRIMARY_CHANNEL.value, default=0): vol.Any(val.positive_int, None),
        vol.Required(CDPD.ALLOW_UNDEFINED_GENERIC_DPS.value, default=False): bool,
        vol.Optional(CDPD.SECONDARY_CHANNELS.value): (val.positive_int,),
        vol.Optional(CDPD.REPEATABLE_FIELDS.value): _SCHEMA_FIELD_DETAILS,
        vol.Optional(CDPD.VISIBLE_REPEATABLE_FIELDS.value): _SCHEMA_FIELD_DETAILS,
        vol.Optional(CDPD.FIELDS.value): _SCHEMA_FIELD,
        vol.Optional(CDPD.VISIBLE_FIELDS.value): _SCHEMA_FIELD,
    }
)

_SCHEMA_DEVICE_GROUPS = vol.Schema(
    {
        vol.Required(CDPD.DEVICE_GROUP.value): _SCHEMA_DEVICE_GROUP,
        vol.Optional(CDPD.ADDITIONAL_DPS.value): _SCHEMA_ADDITIONAL_DPS,
        vol.Optional(CDPD.INCLUDE_DEFAULT_DPS.value, default=DEFAULT_INCLUDE_DEFAULT_DPS): bool,
    }
)

_SCHEMA_DEVICE_DESCRIPTION = vol.Schema(
    {
        vol.Required(CDPD.DEFAULT_DPS.value): _SCHEMA_ADDITIONAL_DPS,
        vol.Required(CDPD.DEVICE_DEFINITIONS.value): vol.Schema(
            {
                vol.Required(DeviceProfile): _SCHEMA_DEVICE_GROUPS,
            }
        ),
    }
)

_CUSTOM_DATA_POINT_DEFINITION: Mapping[CDPD, Mapping[int | DeviceProfile, Any]] = {
    CDPD.DEFAULT_DPS: {
        0: (
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
    },
    CDPD.DEVICE_DEFINITIONS: {
        DeviceProfile.IP_BUTTON_LOCK: {
            CDPD.DEVICE_GROUP: {
                CDPD.ALLOW_UNDEFINED_GENERIC_DPS: True,
                CDPD.REPEATABLE_FIELDS: {
                    Field.BUTTON_LOCK: Parameter.GLOBAL_BUTTON_LOCK,
                },
            },
        },
        DeviceProfile.IP_COVER: {
            CDPD.DEVICE_GROUP: {
                CDPD.SECONDARY_CHANNELS: (1, 2),
                CDPD.REPEATABLE_FIELDS: {
                    Field.COMBINED_PARAMETER: Parameter.COMBINED_PARAMETER,
                    Field.LEVEL: Parameter.LEVEL,
                    Field.LEVEL_2: Parameter.LEVEL_2,
                    Field.STOP: Parameter.STOP,
                },
                CDPD.FIELDS: {
                    -1: {
                        Field.DIRECTION: Parameter.ACTIVITY_STATE,
                        Field.OPERATION_MODE: Parameter.CHANNEL_OPERATION_MODE,
                    },
                },
                CDPD.VISIBLE_FIELDS: {
                    -1: {
                        Field.CHANNEL_LEVEL: Parameter.LEVEL,
                        Field.CHANNEL_LEVEL_2: Parameter.LEVEL_2,
                    },
                },
            },
        },
        DeviceProfile.IP_DIMMER: {
            CDPD.DEVICE_GROUP: {
                CDPD.SECONDARY_CHANNELS: (1, 2),
                CDPD.REPEATABLE_FIELDS: {
                    Field.LEVEL: Parameter.LEVEL,
                    Field.ON_TIME_VALUE: Parameter.ON_TIME,
                    Field.RAMP_TIME_VALUE: Parameter.RAMP_TIME,
                },
                CDPD.VISIBLE_FIELDS: {
                    -1: {
                        Field.CHANNEL_LEVEL: Parameter.LEVEL,
                    },
                },
            },
        },
        DeviceProfile.IP_GARAGE: {
            CDPD.DEVICE_GROUP: {
                CDPD.REPEATABLE_FIELDS: {
                    Field.DOOR_COMMAND: Parameter.DOOR_COMMAND,
                    Field.SECTION: Parameter.SECTION,
                },
                CDPD.VISIBLE_REPEATABLE_FIELDS: {
                    Field.DOOR_STATE: Parameter.DOOR_STATE,
                },
            },
            CDPD.ADDITIONAL_DPS: {
                1: (Parameter.STATE,),
            },
        },
        DeviceProfile.IP_HDM: {
            CDPD.DEVICE_GROUP: {
                CDPD.FIELDS: {
                    0: {
                        Field.DIRECTION: Parameter.ACTIVITY_STATE,
                        Field.LEVEL: Parameter.LEVEL,
                        Field.LEVEL_2: Parameter.LEVEL_2,
                        Field.STOP: Parameter.STOP,
                    },
                },
            },
        },
        DeviceProfile.IP_FIXED_COLOR_LIGHT: {
            CDPD.DEVICE_GROUP: {
                CDPD.SECONDARY_CHANNELS: (1, 2),
                CDPD.REPEATABLE_FIELDS: {
                    Field.COLOR: Parameter.COLOR,
                    Field.COLOR_BEHAVIOUR: Parameter.COLOR_BEHAVIOUR,
                    Field.LEVEL: Parameter.LEVEL,
                    Field.ON_TIME_UNIT: Parameter.DURATION_UNIT,
                    Field.ON_TIME_VALUE: Parameter.DURATION_VALUE,
                    Field.RAMP_TIME_UNIT: Parameter.RAMP_TIME_UNIT,
                    Field.RAMP_TIME_VALUE: Parameter.RAMP_TIME_VALUE,
                },
                CDPD.VISIBLE_FIELDS: {
                    -1: {
                        Field.CHANNEL_COLOR: Parameter.COLOR,
                        Field.CHANNEL_LEVEL: Parameter.LEVEL,
                    },
                },
            },
        },
        DeviceProfile.IP_SIMPLE_FIXED_COLOR_LIGHT_WIRED: {
            CDPD.DEVICE_GROUP: {
                CDPD.REPEATABLE_FIELDS: {
                    Field.COLOR: Parameter.COLOR,
                    Field.COLOR_BEHAVIOUR: Parameter.COLOR_BEHAVIOUR,
                    Field.LEVEL: Parameter.LEVEL,
                    Field.ON_TIME_UNIT: Parameter.DURATION_UNIT,
                    Field.ON_TIME_VALUE: Parameter.DURATION_VALUE,
                    Field.RAMP_TIME_UNIT: Parameter.RAMP_TIME_UNIT,
                    Field.RAMP_TIME_VALUE: Parameter.RAMP_TIME_VALUE,
                },
            },
        },
        DeviceProfile.IP_SIMPLE_FIXED_COLOR_LIGHT: {
            CDPD.DEVICE_GROUP: {
                CDPD.REPEATABLE_FIELDS: {
                    Field.COLOR: Parameter.COLOR,
                    Field.LEVEL: Parameter.LEVEL,
                    Field.ON_TIME_UNIT: Parameter.DURATION_UNIT,
                    Field.ON_TIME_VALUE: Parameter.DURATION_VALUE,
                    Field.RAMP_TIME_UNIT: Parameter.RAMP_TIME_UNIT,
                    Field.RAMP_TIME_VALUE: Parameter.RAMP_TIME_VALUE,
                },
            },
        },
        DeviceProfile.IP_RGBW_LIGHT: {
            CDPD.DEVICE_GROUP: {
                CDPD.SECONDARY_CHANNELS: (1, 2, 3),
                CDPD.REPEATABLE_FIELDS: {
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
                CDPD.FIELDS: {
                    -1: {
                        Field.DEVICE_OPERATION_MODE: Parameter.DEVICE_OPERATION_MODE,
                    },
                },
            },
        },
        DeviceProfile.IP_DRG_DALI: {
            CDPD.DEVICE_GROUP: {
                CDPD.REPEATABLE_FIELDS: {
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
            },
        },
        DeviceProfile.IP_SWITCH: {
            CDPD.DEVICE_GROUP: {
                CDPD.SECONDARY_CHANNELS: (1, 2),
                CDPD.REPEATABLE_FIELDS: {
                    Field.STATE: Parameter.STATE,
                    Field.ON_TIME_VALUE: Parameter.ON_TIME,
                },
                CDPD.VISIBLE_FIELDS: {
                    -1: {
                        Field.CHANNEL_STATE: Parameter.STATE,
                    },
                },
            },
            CDPD.ADDITIONAL_DPS: {
                3: (
                    Parameter.CURRENT,
                    Parameter.ENERGY_COUNTER,
                    Parameter.FREQUENCY,
                    Parameter.POWER,
                    Parameter.ACTUAL_TEMPERATURE,
                    Parameter.VOLTAGE,
                ),
            },
        },
        DeviceProfile.IP_LOCK: {
            CDPD.DEVICE_GROUP: {
                CDPD.REPEATABLE_FIELDS: {
                    Field.DIRECTION: Parameter.ACTIVITY_STATE,
                    Field.LOCK_STATE: Parameter.LOCK_STATE,
                    Field.LOCK_TARGET_LEVEL: Parameter.LOCK_TARGET_LEVEL,
                },
                CDPD.FIELDS: {
                    -1: {
                        Field.ERROR: Parameter.ERROR_JAMMED,
                    },
                },
            },
        },
        DeviceProfile.IP_SIREN: {
            CDPD.DEVICE_GROUP: {
                CDPD.REPEATABLE_FIELDS: {
                    Field.ACOUSTIC_ALARM_ACTIVE: Parameter.ACOUSTIC_ALARM_ACTIVE,
                    Field.OPTICAL_ALARM_ACTIVE: Parameter.OPTICAL_ALARM_ACTIVE,
                    Field.ACOUSTIC_ALARM_SELECTION: Parameter.ACOUSTIC_ALARM_SELECTION,
                    Field.OPTICAL_ALARM_SELECTION: Parameter.OPTICAL_ALARM_SELECTION,
                    Field.DURATION: Parameter.DURATION_VALUE,
                    Field.DURATION_UNIT: Parameter.DURATION_UNIT,
                },
            },
        },
        DeviceProfile.IP_SIREN_SMOKE: {
            CDPD.DEVICE_GROUP: {
                CDPD.REPEATABLE_FIELDS: {
                    Field.SMOKE_DETECTOR_COMMAND: Parameter.SMOKE_DETECTOR_COMMAND,
                },
                CDPD.VISIBLE_REPEATABLE_FIELDS: {
                    Field.SMOKE_DETECTOR_ALARM_STATUS: Parameter.SMOKE_DETECTOR_ALARM_STATUS,
                },
            },
        },
        DeviceProfile.IP_THERMOSTAT: {
            CDPD.DEVICE_GROUP: {
                CDPD.REPEATABLE_FIELDS: {
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
                CDPD.VISIBLE_REPEATABLE_FIELDS: {
                    Field.HEATING_COOLING: Parameter.HEATING_COOLING,
                    Field.HUMIDITY: Parameter.HUMIDITY,
                    Field.TEMPERATURE: Parameter.ACTUAL_TEMPERATURE,
                },
                CDPD.VISIBLE_FIELDS: {
                    0: {
                        Field.LEVEL: Parameter.LEVEL,
                        Field.CONCENTRATION: Parameter.CONCENTRATION,
                    },
                    8: {
                        Field.STATE: Parameter.STATE,
                    },
                },
            },
        },
        DeviceProfile.IP_THERMOSTAT_GROUP: {
            CDPD.DEVICE_GROUP: {
                CDPD.REPEATABLE_FIELDS: {
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
                CDPD.VISIBLE_REPEATABLE_FIELDS: {
                    Field.HEATING_COOLING: Parameter.HEATING_COOLING,
                    Field.HUMIDITY: Parameter.HUMIDITY,
                    Field.TEMPERATURE: Parameter.ACTUAL_TEMPERATURE,
                },
                CDPD.FIELDS: {
                    0: {
                        Field.LEVEL: Parameter.LEVEL,
                    },
                    3: {
                        Field.STATE: Parameter.STATE,
                    },
                },
            },
            CDPD.INCLUDE_DEFAULT_DPS: False,
        },
        DeviceProfile.RF_BUTTON_LOCK: {
            CDPD.DEVICE_GROUP: {
                CDPD.PRIMARY_CHANNEL: None,
                CDPD.ALLOW_UNDEFINED_GENERIC_DPS: True,
                CDPD.REPEATABLE_FIELDS: {
                    Field.BUTTON_LOCK: Parameter.GLOBAL_BUTTON_LOCK,
                },
            },
        },
        DeviceProfile.RF_COVER: {
            CDPD.DEVICE_GROUP: {
                CDPD.REPEATABLE_FIELDS: {
                    Field.DIRECTION: Parameter.DIRECTION,
                    Field.LEVEL: Parameter.LEVEL,
                    Field.LEVEL_2: Parameter.LEVEL_SLATS,
                    Field.LEVEL_COMBINED: Parameter.LEVEL_COMBINED,
                    Field.STOP: Parameter.STOP,
                },
            },
        },
        DeviceProfile.RF_DIMMER: {
            CDPD.DEVICE_GROUP: {
                CDPD.REPEATABLE_FIELDS: {
                    Field.LEVEL: Parameter.LEVEL,
                    Field.ON_TIME_VALUE: Parameter.ON_TIME,
                    Field.RAMP_TIME_VALUE: Parameter.RAMP_TIME,
                },
            },
        },
        DeviceProfile.RF_DIMMER_COLOR: {
            CDPD.DEVICE_GROUP: {
                CDPD.REPEATABLE_FIELDS: {
                    Field.LEVEL: Parameter.LEVEL,
                    Field.ON_TIME_VALUE: Parameter.ON_TIME,
                    Field.RAMP_TIME_VALUE: Parameter.RAMP_TIME,
                },
                CDPD.FIELDS: {
                    1: {
                        Field.COLOR: Parameter.COLOR,
                    },
                    2: {
                        Field.PROGRAM: Parameter.PROGRAM,
                    },
                },
            },
        },
        DeviceProfile.RF_DIMMER_COLOR_FIXED: {
            CDPD.DEVICE_GROUP: {
                CDPD.REPEATABLE_FIELDS: {
                    Field.LEVEL: Parameter.LEVEL,
                    Field.ON_TIME_VALUE: Parameter.ON_TIME,
                    Field.RAMP_TIME_VALUE: Parameter.RAMP_TIME,
                },
            },
        },
        DeviceProfile.RF_DIMMER_COLOR_TEMP: {
            CDPD.DEVICE_GROUP: {
                CDPD.REPEATABLE_FIELDS: {
                    Field.LEVEL: Parameter.LEVEL,
                    Field.ON_TIME_VALUE: Parameter.ON_TIME,
                    Field.RAMP_TIME_VALUE: Parameter.RAMP_TIME,
                },
                CDPD.FIELDS: {
                    1: {
                        Field.COLOR_LEVEL: Parameter.LEVEL,
                    },
                },
            },
        },
        DeviceProfile.RF_DIMMER_WITH_VIRT_CHANNEL: {
            CDPD.DEVICE_GROUP: {
                CDPD.SECONDARY_CHANNELS: (1, 2),
                CDPD.REPEATABLE_FIELDS: {
                    Field.LEVEL: Parameter.LEVEL,
                    Field.ON_TIME_VALUE: Parameter.ON_TIME,
                    Field.RAMP_TIME_VALUE: Parameter.RAMP_TIME,
                },
            },
        },
        DeviceProfile.RF_LOCK: {
            CDPD.DEVICE_GROUP: {
                CDPD.REPEATABLE_FIELDS: {
                    Field.DIRECTION: Parameter.DIRECTION,
                    Field.OPEN: Parameter.OPEN,
                    Field.STATE: Parameter.STATE,
                    Field.ERROR: Parameter.ERROR,
                },
            },
        },
        DeviceProfile.RF_SWITCH: {
            CDPD.DEVICE_GROUP: {
                CDPD.REPEATABLE_FIELDS: {
                    Field.STATE: Parameter.STATE,
                    Field.ON_TIME_VALUE: Parameter.ON_TIME,
                },
            },
            CDPD.ADDITIONAL_DPS: {
                1: (
                    Parameter.CURRENT,
                    Parameter.ENERGY_COUNTER,
                    Parameter.FREQUENCY,
                    Parameter.POWER,
                    Parameter.VOLTAGE,
                ),
            },
        },
        DeviceProfile.RF_THERMOSTAT: {
            CDPD.DEVICE_GROUP: {
                CDPD.REPEATABLE_FIELDS: {
                    Field.AUTO_MODE: Parameter.AUTO_MODE,
                    Field.BOOST_MODE: Parameter.BOOST_MODE,
                    Field.COMFORT_MODE: Parameter.COMFORT_MODE,
                    Field.CONTROL_MODE: Parameter.CONTROL_MODE,
                    Field.LOWERING_MODE: Parameter.LOWERING_MODE,
                    Field.MANU_MODE: Parameter.MANU_MODE,
                    Field.MIN_MAX_VALUE_NOT_RELEVANT_FOR_MANU_MODE: Parameter.MIN_MAX_VALUE_NOT_RELEVANT_FOR_MANU_MODE,
                    Field.SETPOINT: Parameter.SET_TEMPERATURE,
                    Field.TEMPERATURE_MAXIMUM: Parameter.TEMPERATURE_MAXIMUM,
                    Field.TEMPERATURE_MINIMUM: Parameter.TEMPERATURE_MINIMUM,
                    Field.TEMPERATURE_OFFSET: Parameter.TEMPERATURE_OFFSET,
                },
                CDPD.VISIBLE_REPEATABLE_FIELDS: {
                    Field.HUMIDITY: Parameter.ACTUAL_HUMIDITY,
                    Field.TEMPERATURE: Parameter.ACTUAL_TEMPERATURE,
                },
                CDPD.VISIBLE_FIELDS: {
                    0: {
                        Field.VALVE_STATE: Parameter.VALVE_STATE,
                    },
                },
            },
        },
        DeviceProfile.RF_THERMOSTAT_GROUP: {
            CDPD.DEVICE_GROUP: {
                CDPD.REPEATABLE_FIELDS: {
                    Field.AUTO_MODE: Parameter.AUTO_MODE,
                    Field.BOOST_MODE: Parameter.BOOST_MODE,
                    Field.COMFORT_MODE: Parameter.COMFORT_MODE,
                    Field.CONTROL_MODE: Parameter.CONTROL_MODE,
                    Field.LOWERING_MODE: Parameter.LOWERING_MODE,
                    Field.MANU_MODE: Parameter.MANU_MODE,
                    Field.MIN_MAX_VALUE_NOT_RELEVANT_FOR_MANU_MODE: Parameter.MIN_MAX_VALUE_NOT_RELEVANT_FOR_MANU_MODE,
                    Field.SETPOINT: Parameter.SET_TEMPERATURE,
                    Field.TEMPERATURE_MAXIMUM: Parameter.TEMPERATURE_MAXIMUM,
                    Field.TEMPERATURE_MINIMUM: Parameter.TEMPERATURE_MINIMUM,
                    Field.TEMPERATURE_OFFSET: Parameter.TEMPERATURE_OFFSET,
                },
                CDPD.VISIBLE_REPEATABLE_FIELDS: {
                    Field.HUMIDITY: Parameter.ACTUAL_HUMIDITY,
                    Field.TEMPERATURE: Parameter.ACTUAL_TEMPERATURE,
                },
                CDPD.FIELDS: {
                    0: {
                        Field.VALVE_STATE: Parameter.VALVE_STATE,
                    },
                },
            },
            CDPD.INCLUDE_DEFAULT_DPS: False,
        },
        DeviceProfile.SIMPLE_RF_THERMOSTAT: {
            CDPD.DEVICE_GROUP: {
                CDPD.VISIBLE_REPEATABLE_FIELDS: {
                    Field.HUMIDITY: Parameter.HUMIDITY,
                    Field.TEMPERATURE: Parameter.TEMPERATURE,
                },
                CDPD.FIELDS: {
                    1: {
                        Field.SETPOINT: Parameter.SETPOINT,
                    },
                },
            },
        },
    },
}

VALID_CUSTOM_DATA_POINT_DEFINITION = _SCHEMA_DEVICE_DESCRIPTION(_CUSTOM_DATA_POINT_DEFINITION)


def validate_custom_data_point_definition() -> Any:
    """Validate the custom data point definition."""
    try:
        return _SCHEMA_DEVICE_DESCRIPTION(_CUSTOM_DATA_POINT_DEFINITION)
    except vol.Invalid as err:  # pragma: no cover
        _LOGGER.error("The custom data point definition could not be validated. %s, %s", err.path, err.msg)
        return None


def make_custom_data_point(
    channel: hmd.Channel,
    data_point_class: type,
    device_profile: DeviceProfile,
    custom_config: CustomConfig,
) -> None:
    """
    Create custom data point.

    We use a helper-function to avoid raising exceptions during object-init.
    """
    add_sub_device_channels_to_device(device=channel.device, device_profile=device_profile, custom_config=custom_config)
    base_channel_no = get_sub_device_base_channel(device=channel.device, channel_no=channel.no)
    channels = _relevant_channels(device_profile=device_profile, custom_config=custom_config)
    if channel.no in set(channels):
        _create_custom_data_point(
            channel=channel,
            custom_data_point_class=data_point_class,
            device_profile=device_profile,
            device_def=_get_device_group(device_profile, base_channel_no),
            custom_data_point_def=_get_device_data_points(device_profile, base_channel_no),
            base_channel_no=base_channel_no,
            custom_config=_rebase_pri_channels(device_profile=device_profile, custom_config=custom_config),
        )


def _create_custom_data_point(
    channel: hmd.Channel,
    custom_data_point_class: type,
    device_profile: DeviceProfile,
    device_def: Mapping[CDPD, Any],
    custom_data_point_def: Mapping[int, tuple[Parameter, ...]],
    base_channel_no: int | None,
    custom_config: CustomConfig,
) -> None:
    """Create custom data point."""
    unique_id = generate_unique_id(central=channel.central, address=channel.address)

    try:
        if (
            dp := custom_data_point_class(
                channel=channel,
                unique_id=unique_id,
                device_profile=device_profile,
                device_def=device_def,
                custom_data_point_def=custom_data_point_def,
                base_channel_no=base_channel_no,
                custom_config=custom_config,
            )
        ) and dp.has_data_points:
            channel.add_data_point(data_point=dp)
    except Exception as ex:
        raise HaHomematicException(
            f"_CREATE_CUSTOM_DATA_POINT: unable to create custom data point: {reduce_args(args=ex.args)}"
        ) from ex


def _rebase_pri_channels(device_profile: DeviceProfile, custom_config: CustomConfig) -> CustomConfig:
    """Re base primary channel of custom config."""
    device_def = _get_device_group(device_profile, 0)
    if (pri_def := device_def[CDPD.PRIMARY_CHANNEL]) is None:
        return custom_config
    pri_channels = [cu + pri_def for cu in custom_config.channels]
    return CustomConfig(
        make_ce_func=custom_config.make_ce_func,
        channels=tuple(pri_channels),
        extended=custom_config.extended,
    )


def _relevant_channels(device_profile: DeviceProfile, custom_config: CustomConfig) -> tuple[int | None, ...]:
    """Return the relevant channels."""
    device_def = _get_device_group(device_profile, 0)
    def_channels = [device_def[CDPD.PRIMARY_CHANNEL]]
    if sec_channels := device_def.get(CDPD.SECONDARY_CHANNELS):
        def_channels.extend(sec_channels)

    channels: set[int | None] = set()
    for def_ch in def_channels:
        for conf_ch in custom_config.channels:
            if def_ch is not None and conf_ch is not None:
                channels.add(def_ch + conf_ch)
            else:
                channels.add(None)
    return tuple(channels)


def add_sub_device_channels_to_device(
    device: hmd.Device, device_profile: DeviceProfile, custom_config: CustomConfig
) -> None:
    """Return the relevant channels."""
    device_def = _get_device_group(device_profile, 0)
    pri_channel = device_def[CDPD.PRIMARY_CHANNEL]
    sec_channels = device_def.get(CDPD.SECONDARY_CHANNELS)
    if pri_channel is None:
        return
    for conf_channel in custom_config.channels:
        if conf_channel is None:
            continue
        rebased_pri_channel = conf_channel + pri_channel
        device.add_sub_device_channel(channel_no=rebased_pri_channel, base_channel_no=rebased_pri_channel)
        if sec_channels:
            for sec_channel in sec_channels:
                device.add_sub_device_channel(
                    channel_no=conf_channel + sec_channel, base_channel_no=rebased_pri_channel
                )


def get_sub_device_base_channel(device: hmd.Device, channel_no: int | None) -> int | None:
    """Get base channel of sub_device."""
    return device.get_sub_device_base_channel(channel_no=channel_no)


def get_default_data_points() -> Mapping[int | tuple[int, ...], tuple[Parameter, ...]]:
    """Return the default data point."""
    return VALID_CUSTOM_DATA_POINT_DEFINITION[CDPD.DEFAULT_DPS]  # type: ignore[no-any-return]


def get_include_default_data_points(device_profile: DeviceProfile) -> bool:
    """Return if default data points should be included."""
    device = _get_device_definition(device_profile)
    return device.get(CDPD.INCLUDE_DEFAULT_DPS, DEFAULT_INCLUDE_DEFAULT_DPS)


def _get_device_definition(device_profile: DeviceProfile) -> Mapping[CDPD, Any]:
    """Return device from data_point definitions."""
    return cast(
        Mapping[CDPD, Any],
        VALID_CUSTOM_DATA_POINT_DEFINITION[CDPD.DEVICE_DEFINITIONS][device_profile],
    )


def _get_device_group(device_profile: DeviceProfile, base_channel_no: int | None) -> Mapping[CDPD, Any]:
    """Return the device group."""
    device = _get_device_definition(device_profile)
    group = cast(dict[CDPD, Any], device[CDPD.DEVICE_GROUP])
    # Create a deep copy of the group due to channel rebase
    group = deepcopy(group)
    if not base_channel_no:
        return group
    # Add base_channel_no to the primary_channel to get the real primary_channel number
    if (primary_channel := group[CDPD.PRIMARY_CHANNEL]) is not None:
        group[CDPD.PRIMARY_CHANNEL] = primary_channel + base_channel_no

    # Add base_channel_no to the secondary_channels
    # to get the real secondary_channel numbers
    if secondary_channel := group.get(CDPD.SECONDARY_CHANNELS):
        group[CDPD.SECONDARY_CHANNELS] = [x + base_channel_no for x in secondary_channel]

    group[CDPD.VISIBLE_FIELDS] = _rebase_data_point_dict(
        data_point_dict=CDPD.VISIBLE_FIELDS, group=group, base_channel_no=base_channel_no
    )
    group[CDPD.FIELDS] = _rebase_data_point_dict(
        data_point_dict=CDPD.FIELDS, group=group, base_channel_no=base_channel_no
    )
    return group


def _rebase_data_point_dict(
    data_point_dict: CDPD, group: Mapping[CDPD, Any], base_channel_no: int
) -> Mapping[int, Any]:
    """Rebase data_point_dict with base_channel_no."""
    new_fields = {}
    if fields := group.get(data_point_dict):
        for channel_no, field in fields.items():
            new_fields[channel_no + base_channel_no] = field
    return new_fields


def _get_device_data_points(
    device_profile: DeviceProfile, base_channel_no: int | None
) -> Mapping[int, tuple[Parameter, ...]]:
    """Return the device data points."""
    additional_dps = (
        VALID_CUSTOM_DATA_POINT_DEFINITION[CDPD.DEVICE_DEFINITIONS].get(device_profile, {}).get(CDPD.ADDITIONAL_DPS, {})
    )
    if not base_channel_no:
        return additional_dps  # type: ignore[no-any-return]
    new_dps: dict[int, tuple[Parameter, ...]] = {}
    if additional_dps:
        for channel_no, field in additional_dps.items():
            new_dps[channel_no + base_channel_no] = field
    return new_dps


def get_custom_configs(
    model: str,
    category: DataPointCategory | None = None,
) -> tuple[CustomConfig, ...]:
    """Return the data_point configs to create custom data points."""
    model = model.lower().replace("hb-", "hm-")
    custom_configs: list[CustomConfig] = []
    for category_blacklisted_devices in ALL_BLACKLISTED_DEVICES:
        if hms.element_matches_key(
            search_elements=category_blacklisted_devices,
            compare_with=model,
        ):
            return ()

    for pf, category_devices in ALL_DEVICES.items():
        if category is not None and pf != category:
            continue
        if func := _get_data_point_config_by_category(
            category_devices=category_devices,
            model=model,
        ):
            if isinstance(func, tuple):
                custom_configs.extend(func)  # noqa:PERF401
            else:
                custom_configs.append(func)
    return tuple(custom_configs)


def _get_data_point_config_by_category(
    category_devices: Mapping[str, CustomConfig | tuple[CustomConfig, ...]],
    model: str,
) -> CustomConfig | tuple[CustomConfig, ...] | None:
    """Return the data_point configs to create custom data points."""
    for d_type, custom_configs in category_devices.items():
        if model.lower() == d_type.lower():
            return custom_configs

    for d_type, custom_configs in category_devices.items():
        if model.lower().startswith(d_type.lower()):
            return custom_configs

    return None


def is_multi_channel_device(model: str, category: DataPointCategory) -> bool:
    """Return true, if device has multiple channels."""
    channels: list[int | None] = []
    for custom_config in get_custom_configs(model=model, category=category):
        channels.extend(custom_config.channels)
    return len(channels) > 1


def data_point_definition_exists(model: str) -> bool:
    """Check if device desc exits."""
    return len(get_custom_configs(model)) > 0


def get_required_parameters() -> tuple[Parameter, ...]:
    """Return all required parameters for custom data points."""
    required_parameters: list[Parameter] = []
    for channel in VALID_CUSTOM_DATA_POINT_DEFINITION[CDPD.DEFAULT_DPS]:
        required_parameters.extend(VALID_CUSTOM_DATA_POINT_DEFINITION[CDPD.DEFAULT_DPS][channel])
    for device in VALID_CUSTOM_DATA_POINT_DEFINITION[CDPD.DEVICE_DEFINITIONS]:
        device_def = VALID_CUSTOM_DATA_POINT_DEFINITION[CDPD.DEVICE_DEFINITIONS][device][CDPD.DEVICE_GROUP]
        required_parameters.extend(list(device_def.get(CDPD.REPEATABLE_FIELDS, {}).values()))
        required_parameters.extend(list(device_def.get(CDPD.VISIBLE_REPEATABLE_FIELDS, {}).values()))
        required_parameters.extend(list(device_def.get(CDPD.REPEATABLE_FIELDS, {}).values()))
        for additional_data_points in list(
            VALID_CUSTOM_DATA_POINT_DEFINITION[CDPD.DEVICE_DEFINITIONS][device].get(CDPD.ADDITIONAL_DPS, {}).values()
        ):
            required_parameters.extend(additional_data_points)

    for category_spec in ALL_DEVICES.values():
        for custom_configs in category_spec.values():
            if isinstance(custom_configs, CustomConfig):
                if extended := custom_configs.extended:
                    required_parameters.extend(extended.required_parameters)
            else:
                for custom_config in custom_configs:
                    if extended := custom_config.extended:
                        required_parameters.extend(extended.required_parameters)

    return tuple(sorted(set(required_parameters)))
