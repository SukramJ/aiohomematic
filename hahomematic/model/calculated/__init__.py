"""
Calculated data points for HaHomematic.

This subpackage provides derived data points computed from one or more base
parameters (e.g., dew point, apparent temperature, frost point, operating
voltage level, vapor concentration).

Factory:
- create_calculated_data_points: Iterates over the known calculated data point
  implementations, checks their relevance against a channel, and attaches them
  to the channel when applicable.

Calculated data points complement generic and custom data points by adding
useful metrics that are not directly provided by the device.
"""

from __future__ import annotations

import logging
from typing import Final

from hahomematic.decorators import inspector
from hahomematic.model import device as hmd
from hahomematic.model.calculated.climate import ApparentTemperature, DewPoint, FrostPoint, VaporConcentration
from hahomematic.model.calculated.data_point import CalculatedDataPoint
from hahomematic.model.calculated.operating_voltage_level import OperatingVoltageLevel

__all__ = [
    "ApparentTemperature",
    "CalculatedDataPoint",
    "DewPoint",
    "FrostPoint",
    "OperatingVoltageLevel",
    "VaporConcentration",
    "create_calculated_data_points",
]

_CALCULATED_DATA_POINTS: Final = (ApparentTemperature, DewPoint, FrostPoint, OperatingVoltageLevel, VaporConcentration)
_LOGGER: Final = logging.getLogger(__name__)


@inspector()
def create_calculated_data_points(channel: hmd.Channel) -> None:
    """Decides which data point category should be used, and creates the required data points."""
    for cdp in _CALCULATED_DATA_POINTS:
        if cdp.is_relevant_for_model(channel=channel):
            channel.add_data_point(data_point=cdp(channel=channel))
