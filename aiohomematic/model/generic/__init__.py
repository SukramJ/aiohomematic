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
--------
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
    ServiceScope,
)
from aiohomematic.decorators import inspector
from aiohomematic.exceptions import AioHomematicException
from aiohomematic.interfaces.model import ChannelProtocol, GenericDataPointProtocol
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
    "DataPointTypeResolver",
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
    "_determine_data_point_type",
    "create_data_point_and_append_to_channel",
]

_LOGGER: Final = logging.getLogger(__name__)
_BUTTON_ACTIONS: Final[tuple[str, ...]] = ("RESET_MOTION", "RESET_PRESENCE")


class DataPointTypeResolver:
    """
    Resolver for determining data point types based on parameter characteristics.

    Uses a lookup table strategy for extensible parameter type mapping.
    This class centralizes the logic for determining which GenericDataPoint
    subclass should be used for a given parameter.
    """

    # Mapping of parameter types to data point classes for writable parameters
    _WRITABLE_TYPE_MAP: Final[Mapping[ParameterType, type[GenericDataPointAny]]] = {
        ParameterType.BOOL: DpSwitch,
        ParameterType.ENUM: DpSelect,
        ParameterType.FLOAT: DpFloat,
        ParameterType.INTEGER: DpInteger,
        ParameterType.STRING: DpText,
    }

    @classmethod
    def _resolve_action(
        cls,
        *,
        channel: ChannelProtocol,
        parameter: str,
        p_operations: int,
    ) -> type[GenericDataPointAny]:
        """Resolve data point type for ACTION parameters."""
        if p_operations == Operations.WRITE:
            # Write-only action
            if parameter in _BUTTON_ACTIONS or channel.device.model in VIRTUAL_REMOTE_MODELS:
                return DpButton
            return DpAction

        if parameter in CLICK_EVENTS:
            return DpButton

        # Read+write action treated as switch
        return DpSwitch

    @classmethod
    def _resolve_readonly(
        cls,
        *,
        parameter: str,
        parameter_data: ParameterData,
    ) -> type[GenericDataPointAny] | None:
        """Resolve data point type for read-only parameters."""
        if parameter in CLICK_EVENTS:
            return None

        if is_binary_sensor(parameter_data):
            parameter_data["TYPE"] = ParameterType.BOOL
            return DpBinarySensor

        return DpSensor

    @classmethod
    def _resolve_writable(
        cls,
        *,
        channel: ChannelProtocol,
        parameter: str,
        p_type: ParameterType,
        p_operations: int,
    ) -> type[GenericDataPointAny] | None:
        """Resolve data point type for writable parameters."""
        # Handle ACTION type specially
        if p_type == ParameterType.ACTION:
            return cls._resolve_action(
                channel=channel,
                parameter=parameter,
                p_operations=p_operations,
            )

        # Write-only non-ACTION parameters
        if p_operations == Operations.WRITE:
            return DpAction

        # Use lookup table for standard types
        return cls._WRITABLE_TYPE_MAP.get(p_type)

    @classmethod
    def resolve(
        cls,
        *,
        channel: ChannelProtocol,
        parameter: str,
        parameter_data: ParameterData,
    ) -> type[GenericDataPointAny] | None:
        """
        Determine the appropriate data point type for a parameter.

        Args:
            channel: The channel the data point belongs to.
            parameter: The parameter name.
            parameter_data: The parameter description from the backend.

        Returns:
            The data point class to use, or None if no match.

        """
        p_type = parameter_data["TYPE"]
        p_operations = parameter_data["OPERATIONS"]

        if p_operations & Operations.WRITE:
            return cls._resolve_writable(
                channel=channel,
                parameter=parameter,
                p_type=p_type,
                p_operations=p_operations,
            )
        return cls._resolve_readonly(parameter=parameter, parameter_data=parameter_data)


# data points that should be wrapped in a new data point on a new category.
_SWITCH_DP_TO_SENSOR: Final[Mapping[str | tuple[str, ...], Parameter]] = {
    ("HmIP-eTRV", "HmIP-HEATING"): Parameter.LEVEL,
}


@inspector(scope=ServiceScope.INTERNAL)
def create_data_point_and_append_to_channel(
    *,
    channel: ChannelProtocol,
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
    *, channel: ChannelProtocol, parameter: str, parameter_data: ParameterData
) -> type[GenericDataPointAny] | None:
    """
    Determine the type of data point based on parameter and operations.

    Delegates to DataPointTypeResolver for extensible type resolution.
    """
    return DataPointTypeResolver.resolve(
        channel=channel,
        parameter=parameter,
        parameter_data=parameter_data,
    )


def _safe_create_data_point(
    *,
    dp_t: type[GenericDataPointAny],
    channel: ChannelProtocol,
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


def _check_switch_to_sensor(*, data_point: GenericDataPointProtocol) -> bool:
    """Check if parameter of a device should be wrapped to a different category."""
    if data_point.device.parameter_visibility_provider.parameter_is_un_ignored(
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
