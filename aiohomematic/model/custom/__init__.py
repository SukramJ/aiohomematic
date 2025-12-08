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
- get_required_parameters(): Return all parameters that must be fetched to allow
  custom data points to function properly.
"""

from __future__ import annotations

import logging
from typing import Final

from aiohomematic.const import ServiceScope
from aiohomematic.decorators import inspector
from aiohomematic.interfaces.model import DeviceProtocol
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
    create_custom_data_points as _create_custom_data_points_for_channel,
    data_point_definition_exists,
    get_required_parameters,
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

# New type-safe profile and registry modules
from aiohomematic.model.custom.profile import (
    DEFAULT_DATA_POINTS,
    PROFILE_CONFIGS,
    ChannelGroupConfig,
    ProfileConfig,
    ProfileRegistry,
    RebasedChannelGroup,
    get_profile_config,
    rebase_channel_group,
)
from aiohomematic.model.custom.registry import DeviceConfig, DeviceProfileRegistry, ExtendedDeviceConfig
from aiohomematic.model.custom.siren import BaseCustomDpSiren, CustomDpIpSiren, CustomDpIpSirenSmoke, SirenOnArgs
from aiohomematic.model.custom.switch import CustomDpSwitch
from aiohomematic.model.custom.valve import CustomDpIpIrrigationValve

__all__ = [
    # Climate
    "BaseCustomDpClimate",
    "ClimateActivity",
    "ClimateMode",
    "ClimateProfile",
    "CustomDpIpThermostat",
    "CustomDpRfThermostat",
    "CustomDpSimpleRfThermostat",
    "PROFILE_PREFIX",
    # Cover
    "CustomDpBlind",
    "CustomDpCover",
    "CustomDpGarage",
    "CustomDpIpBlind",
    "CustomDpWindowDrive",
    # Data Point
    "CustomDataPoint",
    # Light
    "CustomDpColorDimmer",
    "CustomDpColorDimmerEffect",
    "CustomDpColorTempDimmer",
    "CustomDpDimmer",
    "CustomDpIpDrgDaliLight",
    "CustomDpIpFixedColorLight",
    "CustomDpIpRGBWLight",
    "LightOffArgs",
    "LightOnArgs",
    # Lock
    "BaseCustomDpLock",
    "CustomDpButtonLock",
    "CustomDpIpLock",
    "CustomDpRfLock",
    "LockState",
    # Siren
    "BaseCustomDpSiren",
    "CustomDpIpSiren",
    "CustomDpIpSirenSmoke",
    "SirenOnArgs",
    # Switch
    "CustomDpSwitch",
    # Valve
    "CustomDpIpIrrigationValve",
    # Definition
    "create_custom_data_points",
    "data_point_definition_exists",
    "get_required_parameters",
    # Profile (type-safe)
    "ChannelGroupConfig",
    "DEFAULT_DATA_POINTS",
    "ProfileConfig",
    "ProfileRegistry",
    "PROFILE_CONFIGS",
    "RebasedChannelGroup",
    "get_profile_config",
    "rebase_channel_group",
    # Registry (new type-safe approach)
    "DeviceConfig",
    "DeviceProfileRegistry",
    "ExtendedDeviceConfig",
]

_LOGGER: Final = logging.getLogger(__name__)


@inspector(scope=ServiceScope.INTERNAL)
def create_custom_data_points(*, device: DeviceProtocol) -> None:
    """Decide which data point category should be used, and create the required data points."""
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

        # Create custom data points for each channel
        for channel in device.channels.values():
            _create_custom_data_points_for_channel(channel=channel)
