# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Custom data points for AioHomematic.

This subpackage provides higher-level, device-specific data points that combine
multiple backend parameters into single, meaningful entities (for example: a
thermostat, a blind with tilt, a fixed-color light, a lock, a siren, a switch,
or an irrigation valve). It also contains discovery helpers and a schema-based
validation for model-specific configurations.

What this package does
- Discovery: create_custom_data_points() inspects a device model and, if a
  matching custom definition exists and the device is not ignored for customs,
  creates the appropriate custom data point(s) and attaches them to the device.
- Definitions: The definition module holds the catalog of supported models and
  the rules that describe which parameters form each custom entity. It exposes
  helpers to query availability, enumerate required parameters, and validate the
  definition schema.
- Specializations: Rich custom data point classes for climate, light, cover,
  lock, siren, switch, and irrigation valve provide tailored behavior and an API
  focused on user intent (e.g., set_temperature, open_tilt, set_profile,
  turn_on with effect, lock/open, vent, etc.).

How it relates to the generic layer
Custom data points build on top of generic data points. While the generic layer
maps one backend parameter to one data point, this package groups multiple
parameters across channels (where needed) into a single higher-level entity. The
result is a simpler interface for automations and UIs, while still allowing the
underlying generic data points to be created when desired.

Public API entry points commonly used by integrators
- create_custom_data_points(device): Run discovery and attach custom data points.
- data_point_definition_exists(model): Check if a custom definition is available.
- get_custom_configs(model, category=None): Retrieve the CustomConfig entries
  used to create custom data points for a model (optionally filtered by
  category).
- get_required_parameters(): Return all parameters that must be fetched to allow
  custom data points to function properly.
- validate_custom_data_point_definition(): Validate the internal definition
  schema; useful in tests and development.
"""

from __future__ import annotations

import logging
from typing import Final

from aiohomematic.decorators import inspector
from aiohomematic.model import device as hmd
from aiohomematic.model.custom.climate import (
    PROFILE_PREFIX,
    BaseCustomDpClimate,
    ClimateActivity,
    ClimateMode,
    ClimateProfile,
    CustomDpIpThermostat,
    CustomDpRfThermostat,
    CustomDpSimpleRfThermostat,
)
from aiohomematic.model.custom.cover import (
    CustomDpBlind,
    CustomDpCover,
    CustomDpGarage,
    CustomDpIpBlind,
    CustomDpWindowDrive,
)
from aiohomematic.model.custom.data_point import CustomDataPoint
from aiohomematic.model.custom.definition import (
    data_point_definition_exists,
    get_custom_configs,
    get_required_parameters,
    validate_custom_data_point_definition,
)
from aiohomematic.model.custom.light import (
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
from aiohomematic.model.custom.lock import (
    BaseCustomDpLock,
    CustomDpButtonLock,
    CustomDpIpLock,
    CustomDpRfLock,
    LockState,
)
from aiohomematic.model.custom.siren import BaseCustomDpSiren, CustomDpIpSiren, CustomDpIpSirenSmoke, SirenOnArgs
from aiohomematic.model.custom.switch import CustomDpSwitch
from aiohomematic.model.custom.valve import CustomDpIpIrrigationValve

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
    "PROFILE_PREFIX",
    "SirenOnArgs",
    "create_custom_data_points",
    "data_point_definition_exists",
    "get_custom_configs",
    "get_required_parameters",
    "validate_custom_data_point_definition",
]

_LOGGER: Final = logging.getLogger(__name__)


@inspector
def create_custom_data_points(*, device: hmd.Device) -> None:
    """Decides which data point category should be used, and creates the required data points."""

    if device.ignore_for_custom_data_point:
        _LOGGER.debug(
            "CREATE_CUSTOM_DATA_POINTS: Ignoring for custom data point: %s, %s, %s due to ignored",
            device.interface_id,
            device,
            device.model,
        )
        return
    if data_point_definition_exists(model=device.model):
        _LOGGER.debug(
            "CREATE_CUSTOM_DATA_POINTS: Handling custom data point integration: %s, %s, %s",
            device.interface_id,
            device,
            device.model,
        )

        # Call the custom creation function.
        for custom_config in get_custom_configs(model=device.model):
            for channel in device.channels.values():
                custom_config.make_ce_func(channel=channel, custom_config=custom_config)
