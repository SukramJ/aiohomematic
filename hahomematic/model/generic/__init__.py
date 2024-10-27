"""Module for HaHomematic generic data points."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Final

from hahomematic import support as hms
from hahomematic.const import (
    CLICK_EVENTS,
    VIRTUAL_REMOTE_MODELS,
    Operations,
    Parameter,
    ParameterData,
    ParameterType,
    ParamsetKey,
)
from hahomematic.exceptions import HaHomematicException
from hahomematic.model import device as hmd
from hahomematic.model.generic.action import DpAction
from hahomematic.model.generic.binary_sensor import DpBinarySensor
from hahomematic.model.generic.button import DpButton
from hahomematic.model.generic.data_point import GenericDataPoint
from hahomematic.model.generic.number import BaseDpNumber, DpFloat, DpInteger
from hahomematic.model.generic.select import DpSelect
from hahomematic.model.generic.sensor import DpSensor
from hahomematic.model.generic.switch import DpSwitch
from hahomematic.model.generic.text import DpText
from hahomematic.model.support import is_binary_sensor

__all__ = [
    "BaseDpNumber",
    "DpAction",
    "DpBinarySensor",
    "DpButton",
    "DpFloat",
    "DpInteger",
    "DpSelect",
    "DpSensor",
    "DpSwitch",
    "DpText",
    "GenericDataPoint",
    "create_data_point_and_append_to_channel",
]

_LOGGER: Final = logging.getLogger(__name__)
_BUTTON_ACTIONS: Final[tuple[str, ...]] = ("RESET_MOTION", "RESET_PRESENCE")

# data points that should be wrapped in a new data point on a new category.
_SWITCH_DP_TO_SENSOR: Final[Mapping[str | tuple[str, ...], Parameter]] = {
    ("HmIP-eTRV", "HmIP-HEATING"): Parameter.LEVEL,
}


def create_data_point_and_append_to_channel(
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
    p_type = parameter_data["TYPE"]
    p_operations = parameter_data["OPERATIONS"]
    dp_t: type[GenericDataPoint] | None = None
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

    if dp_t:
        try:
            dp = dp_t(
                channel=channel,
                paramset_key=paramset_key,
                parameter=parameter,
                parameter_data=parameter_data,
            )
        except Exception as ex:
            raise HaHomematicException(
                f"CREATE_DATA_POINT_AND_APPEND_TO_CHANNEL: Unable to create data_point:{hms.reduce_args(args=ex.args)}"
            ) from ex
        _LOGGER.debug(
            "CREATE_DATA_POINT_AND_APPEND_TO_CHANNEL: %s: %s %s",
            dp.category,
            channel.address,
            parameter,
        )
        channel.add_data_point(dp)
        if _check_switch_to_sensor(data_point=dp):
            dp.force_to_sensor()


def _check_switch_to_sensor(data_point: GenericDataPoint) -> bool:
    """Check if parameter of a device should be wrapped to a different category."""
    if data_point.device.central.parameter_visibility.parameter_is_un_ignored(
        model=data_point.device.model,
        channel_no=data_point.channel.no,
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
