# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Calculated (derived) data points for AioHomematic.

This subpackage provides data points whose values are computed from one or more
underlying device data points. Typical examples include climate-related metrics
(such as dew point, apparent temperature, frost point, vapor concentration) and
battery/voltage related assessments (such as operating voltage level).

How it works:
- Each calculated data point is a lightweight model that subscribes to one or
  more generic data points of a channel and recomputes its value when any of
  the source data points change.
- Relevance is determined per channel. A calculated data point class exposes an
  "is_relevant_for_model" method that decides if the channel provides the
  necessary inputs.
- Creation is handled centrally via the factory function below.

Factory:
- create_calculated_data_points(channel): Iterates over the known calculated
  implementations, checks their relevance against the given channel, and, if
  applicable, creates and attaches instances to the channel so they behave like
  normal read-only data points.

Modules/classes:
- ApparentTemperature, DewPoint, DewPointSpread, Enthalphy, FrostPoint, VaporConcentration: Climate-related
  sensors implemented in climate.py using well-known formulas (see
  aiohomematic.model.calculated.support for details and references).
- OperatingVoltageLevel: Interprets battery/voltage values and exposes a human
  readable operating level classification.

These calculated data points complement generic and custom data points by
exposing useful metrics not directly provided by the device/firmware.
"""

from __future__ import annotations

import logging
from typing import Final

from aiohomematic.decorators import inspector
from aiohomematic.model import device as hmd
from aiohomematic.model.calculated.climate import (
    ApparentTemperature,
    DewPoint,
    DewPointSpread,
    Enthalpy,
    FrostPoint,
    VaporConcentration,
)
from aiohomematic.model.calculated.data_point import CalculatedDataPoint
from aiohomematic.model.calculated.operating_voltage_level import OperatingVoltageLevel

__all__ = [
    "ApparentTemperature",
    "CalculatedDataPoint",
    "DewPoint",
    "DewPointSpread",
    "Enthalpy",
    "FrostPoint",
    "OperatingVoltageLevel",
    "VaporConcentration",
    "create_calculated_data_points",
]

_CALCULATED_DATA_POINTS: Final = (
    ApparentTemperature,
    DewPoint,
    DewPointSpread,
    Enthalpy,
    FrostPoint,
    OperatingVoltageLevel,
    VaporConcentration,
)
_LOGGER: Final = logging.getLogger(__name__)


@inspector
def create_calculated_data_points(*, channel: hmd.Channel) -> None:
    """Decides which data point category should be used, and creates the required data points."""
    for dp in _CALCULATED_DATA_POINTS:
        if dp.is_relevant_for_model(channel=channel):
            channel.add_data_point(data_point=dp(channel=channel))
