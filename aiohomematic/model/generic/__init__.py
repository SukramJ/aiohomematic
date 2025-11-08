# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Generic data points for AioHomematic.

Overview
- This subpackage provides the default, device-agnostic data point classes
  (switch, number, sensor, select, text, button, binary_sensor) used for most
  parameters across Homematic devices.
- It also exposes a central factory function that selects the appropriate data
  point class for a parameter based on its description provided by the backend.

Factory
- create_data_point_and_append_to_channel(channel, paramset_key, parameter, parameter_data)
  inspects ParameterData (TYPE, OPERATIONS, FLAGS, etc.) to determine which
  GenericDataPoint subclass to instantiate, creates it safely and appends it to
  the given channel.

Mapping rules (simplified)
- TYPE==ACTION:
  - OPERATIONS==WRITE -> DpButton (for specific button-like actions or virtual
    remotes) else DpAction; otherwise, when also readable, treat as DpSwitch.
- TYPE in {BOOL, ENUM, FLOAT, INTEGER, STRING} with WRITE capabilities ->
  DpSwitch, DpSelect, DpFloat, DpInteger, DpText respectively.
- Read-only parameters (no WRITE) become sensors; BOOL-like sensors are mapped
  to DpBinarySensor when heuristics indicate binary semantics.

Special cases
- Virtual remote models and click parameters are recognized and mapped to
  button-style data points.
- Certain device/parameter combinations may be wrapped into a different
  category (e.g., switch shown as sensor) when the parameter is not meant to be
  user-visible or is better represented as a sensor, depending on configuration
  and device model.

Exports
- Generic data point base and concrete types: GenericDataPoint, DpSwitch,
  DpAction, DpButton, DpBinarySensor, DpSelect, DpFloat, DpInteger, DpText,
  DpSensor, BaseDpNumber.
- Factory: create_data_point_and_append_to_channel.

See Also
- aiohomematic.model.custom: Custom data points for specific devices/features.
- aiohomematic.model.calculated: Calculated/derived data points.
- aiohomematic.model.device: Device and channel abstractions used here.

"""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Final

from aiohomematic import i18n, support as hms
from aiohomematic.const import (
    CLICK_EVENTS,
    VIRTUAL_REMOTE_MODELS,
    Operations,
    Parameter,
    ParameterData,
    ParameterType,
    ParamsetKey,
)
from aiohomematic.decorators import inspector
from aiohomematic.exceptions import AioHomematicException
from aiohomematic.model import device as hmd
from aiohomematic.model.generic.action import DpAction
from aiohomematic.model.generic.binary_sensor import DpBinarySensor
from aiohomematic.model.generic.button import DpButton
from aiohomematic.model.generic.data_point import GenericDataPoint, GenericDataPointAny
from aiohomematic.model.generic.dummy import DpDummy
from aiohomematic.model.generic.number import BaseDpNumber, DpFloat, DpInteger
from aiohomematic.model.generic.select import DpSelect
from aiohomematic.model.generic.sensor import DpSensor
from aiohomematic.model.generic.switch import DpSwitch
from aiohomematic.model.generic.text import DpText
from aiohomematic.model.support import is_binary_sensor

__all__ = [
    "BaseDpNumber",
    "DpAction",
    "DpBinarySensor",
    "DpButton",
    "DpDummy",
    "DpFloat",
    "DpInteger",
    "DpSelect",
    "DpSensor",
    "DpSwitch",
    "DpText",
    "GenericDataPoint",
    "GenericDataPointAny",
    "create_data_point_and_append_to_channel",
]

_LOGGER: Final = logging.getLogger(__name__)
_BUTTON_ACTIONS: Final[tuple[str, ...]] = ("RESET_MOTION", "RESET_PRESENCE")

# data points that should be wrapped in a new data point on a new category.
_SWITCH_DP_TO_SENSOR: Final[Mapping[str | tuple[str, ...], Parameter]] = {
    ("HmIP-eTRV", "HmIP-HEATING"): Parameter.LEVEL,
}


@inspector
def create_data_point_and_append_to_channel(
    *,
    channel: hmd.Channel,
    paramset_key: ParamsetKey,
    parameter: str,
    parameter_data: ParameterData,
) -> None:
    """Decides which generic category should be used, and creates the required data points."""
    _LOGGER.debug(
        "CREATE_DATA_POINTS: Creating data_point for %s, %s, %s",
        channel.address,
        parameter,
        channel.device.interface_id,
    )

    if (dp_t := _determine_data_point_type(channel=channel, parameter=parameter, parameter_data=parameter_data)) and (
        dp := _safe_create_data_point(
            dp_t=dp_t, channel=channel, paramset_key=paramset_key, parameter=parameter, parameter_data=parameter_data
        )
    ):
        _LOGGER.debug(
            "CREATE_DATA_POINT_AND_APPEND_TO_CHANNEL: %s: %s %s",
            dp.category,
            channel.address,
            parameter,
        )
        channel.add_data_point(data_point=dp)
        if _check_switch_to_sensor(data_point=dp):
            dp.force_to_sensor()


def _determine_data_point_type(
    *, channel: hmd.Channel, parameter: str, parameter_data: ParameterData
) -> type[GenericDataPointAny] | None:
    """Determine the type of data point based on parameter and operations."""
    p_type = parameter_data["TYPE"]
    p_operations = parameter_data["OPERATIONS"]
    dp_t: type[GenericDataPointAny] | None = None
    if p_operations & Operations.WRITE:
        if p_type == ParameterType.ACTION:
            if p_operations == Operations.WRITE:
                if parameter in _BUTTON_ACTIONS or channel.device.model in VIRTUAL_REMOTE_MODELS:
                    dp_t = DpButton
                else:
                    dp_t = DpAction
            elif parameter in CLICK_EVENTS:
                dp_t = DpButton
            else:
                dp_t = DpSwitch
        elif p_operations == Operations.WRITE:
            dp_t = DpAction
        elif p_type == ParameterType.BOOL:
            dp_t = DpSwitch
        elif p_type == ParameterType.ENUM:
            dp_t = DpSelect
        elif p_type == ParameterType.FLOAT:
            dp_t = DpFloat
        elif p_type == ParameterType.INTEGER:
            dp_t = DpInteger
        elif p_type == ParameterType.STRING:
            dp_t = DpText
    elif parameter not in CLICK_EVENTS:
        # Also check, if sensor could be a binary_sensor due to.
        if is_binary_sensor(parameter_data):
            parameter_data["TYPE"] = ParameterType.BOOL
            dp_t = DpBinarySensor
        else:
            dp_t = DpSensor

    return dp_t


def _safe_create_data_point(
    *,
    dp_t: type[GenericDataPointAny],
    channel: hmd.Channel,
    paramset_key: ParamsetKey,
    parameter: str,
    parameter_data: ParameterData,
) -> GenericDataPointAny:
    """Safely create a data point and handle exceptions."""
    try:
        return dp_t(
            channel=channel,
            paramset_key=paramset_key,
            parameter=parameter,
            parameter_data=parameter_data,
        )
    except Exception as exc:
        raise AioHomematicException(
            i18n.tr(
                "exception.model.generic.create_data_point.failed",
                reason=hms.extract_exc_args(exc=exc),
            )
        ) from exc


def _check_switch_to_sensor(*, data_point: GenericDataPointAny) -> bool:
    """Check if parameter of a device should be wrapped to a different category."""
    if data_point.device.central.parameter_visibility.parameter_is_un_ignored(
        channel=data_point.channel,
        paramset_key=data_point.paramset_key,
        parameter=data_point.parameter,
    ):
        return False
    for devices, parameter in _SWITCH_DP_TO_SENSOR.items():
        if (
            hms.element_matches_key(
                search_elements=devices,
                compare_with=data_point.device.model,
            )
            and data_point.parameter == parameter
        ):
            return True
    return False
