"""Module for HaHomematic custom data point."""

from __future__ import annotations

import logging
from typing import Final

from hahomematic.decorators import inspector
from hahomematic.model import device as hmd
from hahomematic.model.custom.climate import (
    PROFILE_DICT,
    PROFILE_PREFIX,
    SIMPLE_PROFILE_DICT,
    SIMPLE_WEEKDAY_LIST,
    WEEKDAY_DICT,
    BaseCustomDpClimate,
    ClimateActivity,
    ClimateMode,
    ClimateProfile,
    CustomDpIpThermostat,
    CustomDpRfThermostat,
    CustomDpSimpleRfThermostat,
    ScheduleProfile,
    ScheduleWeekday,
)
from hahomematic.model.custom.cover import (
    CustomDpBlind,
    CustomDpCover,
    CustomDpGarage,
    CustomDpIpBlind,
    CustomDpWindowDrive,
)
from hahomematic.model.custom.data_point import CustomDataPoint
from hahomematic.model.custom.definition import (
    data_point_definition_exists,
    get_custom_configs,
    get_required_parameters,
    validate_custom_data_point_definition,
)
from hahomematic.model.custom.light import (
    CustomDpColorDimmer,
    CustomDpColorDimmerEffect,
    CustomDpColorTempDimmer,
    CustomDpDimmer,
    CustomDpIpDrgDaliLight,
    CustomDpIpFixedColorLight,
    CustomDpIpRGBWLight,
    LightOffArgs,
    LightOnArgs,
)
from hahomematic.model.custom.lock import (
    BaseCustomDpLock,
    CustomDpButtonLock,
    CustomDpIpLock,
    CustomDpRfLock,
    LockState,
)
from hahomematic.model.custom.siren import BaseCustomDpSiren, CustomDpIpSiren, CustomDpIpSirenSmoke, SirenOnArgs
from hahomematic.model.custom.switch import CustomDpSwitch
from hahomematic.model.custom.valve import CustomDpIpIrrigationValve

__all__ = [
    "BaseCustomDpClimate",
    "BaseCustomDpLock",
    "BaseCustomDpSiren",
    "ClimateActivity",
    "ClimateMode",
    "ClimateProfile",
    "CustomDataPoint",
    "CustomDpBlind",
    "CustomDpButtonLock",
    "CustomDpColorDimmer",
    "CustomDpColorDimmerEffect",
    "CustomDpColorTempDimmer",
    "CustomDpCover",
    "CustomDpDimmer",
    "CustomDpGarage",
    "CustomDpIpBlind",
    "CustomDpIpDrgDaliLight",
    "CustomDpIpFixedColorLight",
    "CustomDpIpIrrigationValve",
    "CustomDpIpLock",
    "CustomDpIpRGBWLight",
    "CustomDpIpSiren",
    "CustomDpIpSirenSmoke",
    "CustomDpIpThermostat",
    "CustomDpRfLock",
    "CustomDpRfThermostat",
    "CustomDpSimpleRfThermostat",
    "CustomDpSwitch",
    "CustomDpWindowDrive",
    "LightOffArgs",
    "LightOnArgs",
    "LockState",
    "PROFILE_DICT",
    "PROFILE_PREFIX",
    "SIMPLE_PROFILE_DICT",
    "SIMPLE_WEEKDAY_LIST",
    "ScheduleProfile",
    "ScheduleWeekday",
    "SirenOnArgs",
    "WEEKDAY_DICT",
    "create_custom_data_points",
    "get_required_parameters",
    "validate_custom_data_point_definition",
]

_LOGGER: Final = logging.getLogger(__name__)


@inspector()
def create_custom_data_points(device: hmd.Device) -> None:
    """Decides which data point category should be used, and creates the required data points."""

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
