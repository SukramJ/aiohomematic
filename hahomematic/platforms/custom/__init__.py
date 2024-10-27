"""Module for HaHomematic custom platforms."""

from __future__ import annotations

import logging
from typing import Final

from hahomematic.platforms import device as hmd
from hahomematic.platforms.custom.climate import (
    HM_PRESET_MODE_PREFIX,
    PROFILE_DICT,
    SIMPLE_PROFILE_DICT,
    SIMPLE_WEEKDAY_LIST,
    WEEKDAY_DICT,
    BaseClimateDataPoint,
    CeIpThermostat,
    CeRfThermostat,
    CeSimpleRfThermostat,
    HmHvacAction,
    HmHvacMode,
    HmPresetMode,
)
from hahomematic.platforms.custom.cover import CeBlind, CeCover, CeGarage, CeIpBlind, CeWindowDrive
from hahomematic.platforms.custom.data_point import CustomDataPoint
from hahomematic.platforms.custom.definition import (
    data_point_definition_exists,
    get_custom_configs,
    get_required_parameters,
    validate_custom_data_point_definition,
)
from hahomematic.platforms.custom.light import (
    CeColorDimmer,
    CeColorDimmerEffect,
    CeColorTempDimmer,
    CeDimmer,
    CeIpDrgDaliLight,
    CeIpFixedColorLight,
    CeIpRGBWLight,
    LightOffArgs,
    LightOnArgs,
)
from hahomematic.platforms.custom.lock import BaseLock, CeButtonLock, CeIpLock, CeRfLock, LockState
from hahomematic.platforms.custom.siren import BaseSiren, CeIpSiren, CeIpSirenSmoke, SirenOnArgs
from hahomematic.platforms.custom.switch import CeSwitch

__all__ = [
    "BaseClimateDataPoint",
    "BaseLock",
    "BaseSiren",
    "CeBlind",
    "CeButtonLock",
    "CeColorDimmer",
    "CeColorDimmerEffect",
    "CeColorTempDimmer",
    "CeCover",
    "CeDimmer",
    "CeGarage",
    "CeIpBlind",
    "CeIpDrgDaliLight",
    "CeIpFixedColorLight",
    "CeIpLock",
    "CeIpRGBWLight",
    "CeIpSiren",
    "CeIpSirenSmoke",
    "CeIpThermostat",
    "CeRfLock",
    "CeRfThermostat",
    "CeSimpleRfThermostat",
    "CeSwitch",
    "CeWindowDrive",
    "CustomDataPoint",
    "HM_PRESET_MODE_PREFIX",
    "HmHvacAction",
    "HmHvacMode",
    "HmPresetMode",
    "LightOffArgs",
    "LightOnArgs",
    "LockState",
    "SirenOnArgs",
    "WEEKDAY_DICT",
    "PROFILE_DICT",
    "SIMPLE_PROFILE_DICT",
    "SIMPLE_WEEKDAY_LIST",
    "create_custom_data_points",
    "get_required_parameters",
    "validate_custom_data_point_definition",
]

_LOGGER: Final = logging.getLogger(__name__)


def create_custom_data_points(device: hmd.HmDevice) -> None:
    """Decides which default platform should be used, and creates the required data points."""

    if device.ignore_for_custom_data_point:
        _LOGGER.debug(
            "CREATE_CUSTOM_DATA_POINTS: Ignoring for custom data point: %s, %s, %s due to ignored",
            device.interface_id,
            device,
            device.model,
        )
        return
    if data_point_definition_exists(device.model):
        _LOGGER.debug(
            "CREATE_CUSTOM_DATA_POINTS: Handling custom data point integration: %s, %s, %s",
            device.interface_id,
            device,
            device.model,
        )

        # Call the custom creation function.
        for custom_config in get_custom_configs(model=device.model):
            for channel in device.channels.values():
                custom_config.make_ce_func(channel, custom_config)
