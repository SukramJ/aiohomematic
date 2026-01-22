# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Module for hub data points implemented using the sensor category."""

from __future__ import annotations

import logging
from typing import Any, Final

from aiohomematic.const import DataPointCategory, HubValueType
from aiohomematic.model.hub.data_point import GenericSysvarDataPoint
from aiohomematic.model.mixins.sensor_value import SensorValueMixin
from aiohomematic.property_decorators import state_property

_LOGGER: Final = logging.getLogger(__name__)


class SysvarDpSensor(SensorValueMixin, GenericSysvarDataPoint):
    """Implementation of a sysvar sensor."""

    __slots__ = ()

    _category = DataPointCategory.HUB_SENSOR

    @state_property
    def value(self) -> Any | None:
        """Return the value."""
        return self._transform_sensor_value(
            raw_value=self._value,
            value_list=self.values if self._data_type == HubValueType.LIST else None,
            check_name=self._legacy_name,
            is_string=self._data_type == HubValueType.STRING,
        )
