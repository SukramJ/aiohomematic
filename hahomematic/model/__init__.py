"""Module for the HaHomematic model."""

from __future__ import annotations

import logging
from typing import Final

from hahomematic.const import (
    CLICK_EVENTS,
    DEVICE_ERROR_EVENTS,
    IMPULSE_EVENTS,
    Flag,
    Operations,
    Parameter,
    ParameterData,
    ParamsetKey,
)
from hahomematic.decorators import inspector
from hahomematic.model import device as hmd
from hahomematic.model.calculated import create_calculated_data_points
from hahomematic.model.event import create_event_and_append_to_channel
from hahomematic.model.generic import create_data_point_and_append_to_channel

__all__ = ["create_data_points_and_events"]

# Some parameters are marked as INTERNAL in the paramset and not considered by default,
# but some are required and should be added here.
_ALLOWED_INTERNAL_PARAMETERS: Final[tuple[Parameter, ...]] = (Parameter.DIRECTION,)
_LOGGER: Final = logging.getLogger(__name__)


@inspector()
def create_data_points_and_events(device: hmd.Device) -> None:
    """Create the data points associated to this device."""
    for channel in device.channels.values():
        for paramset_key, paramsset_key_descriptions in channel.paramset_descriptions.items():
            if not device.central.parameter_visibility.is_relevant_paramset(
                channel=channel,
                paramset_key=paramset_key,
            ):
                continue
            for (
                parameter,
                parameter_data,
            ) in paramsset_key_descriptions.items():
                parameter_is_un_ignored = channel.device.central.parameter_visibility.parameter_is_un_ignored(
                    channel=channel,
                    paramset_key=paramset_key,
                    parameter=parameter,
                )
                if channel.device.central.parameter_visibility.should_skip_parameter(
                    channel=channel,
                    paramset_key=paramset_key,
                    parameter=parameter,
                    parameter_is_un_ignored=parameter_is_un_ignored,
                ):
                    continue
                _process_parameter(
                    channel=channel,
                    paramset_key=paramset_key,
                    parameter=parameter,
                    parameter_data=parameter_data,
                    parameter_is_un_ignored=parameter_is_un_ignored,
                )

        create_calculated_data_points(channel=channel)


def _process_parameter(
    channel: hmd.Channel,
    paramset_key: ParamsetKey,
    parameter: str,
    parameter_data: ParameterData,
    parameter_is_un_ignored: bool,
) -> None:
    """Process individual parameter to create data points and events."""

    if paramset_key == ParamsetKey.MASTER and parameter_data["OPERATIONS"] == 0:
        # required to fix hm master paramset operation values
        parameter_data["OPERATIONS"] = 3

    if _should_create_event(parameter_data=parameter_data, parameter=parameter):
        create_event_and_append_to_channel(
            channel=channel,
            parameter=parameter,
            parameter_data=parameter_data,
        )
    if _should_skip_data_point(
        parameter_data=parameter_data, parameter=parameter, parameter_is_un_ignored=parameter_is_un_ignored
    ):
        _LOGGER.debug(
            "CREATE_DATA_POINTS: Skipping %s (no event or internal)",
            parameter,
        )
        return
    # CLICK_EVENTS are allowed for Buttons
    if parameter not in IMPULSE_EVENTS and (not parameter.startswith(DEVICE_ERROR_EVENTS) or parameter_is_un_ignored):
        create_data_point_and_append_to_channel(
            channel=channel,
            paramset_key=paramset_key,
            parameter=parameter,
            parameter_data=parameter_data,
        )


def _should_create_event(parameter_data: ParameterData, parameter: str) -> bool:
    """Determine if an event should be created for the parameter."""
    return bool(
        parameter_data["OPERATIONS"] & Operations.EVENT
        and (parameter in CLICK_EVENTS or parameter.startswith(DEVICE_ERROR_EVENTS) or parameter in IMPULSE_EVENTS)
    )


def _should_skip_data_point(parameter_data: ParameterData, parameter: str, parameter_is_un_ignored: bool) -> bool:
    """Determine if a data point should be skipped."""
    return bool(
        (not parameter_data["OPERATIONS"] & Operations.EVENT and not parameter_data["OPERATIONS"] & Operations.WRITE)
        or (
            parameter_data["FLAGS"] & Flag.INTERNAL
            and parameter not in _ALLOWED_INTERNAL_PARAMETERS
            and not parameter_is_un_ignored
        )
    )
