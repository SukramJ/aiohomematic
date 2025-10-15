# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Module for hub data points implemented using the sensor category."""

from __future__ import annotations

import logging
from typing import Any, Final

from aiohomematic.const import DataPointCategory, SysvarType
from aiohomematic.model.hub.data_point import GenericSysvarDataPoint
from aiohomematic.model.support import check_length_and_log, get_value_from_value_list
from aiohomematic.property_decorators import state_property

_LOGGER: Final = logging.getLogger(__name__)


class SysvarDpSensor(GenericSysvarDataPoint):
    """Implementation of a sysvar sensor."""

    __slots__ = ()

    _category = DataPointCategory.HUB_SENSOR

    @state_property
    def value(self) -> Any | None:
        """Return the value."""
        if (
            self._data_type == SysvarType.LIST
            and (value := get_value_from_value_list(value=self._value, value_list=self.values)) is not None
        ):
            return value
        return (
            check_length_and_log(name=self._legacy_name, value=self._value)
            if self._data_type == SysvarType.STRING
            else self._value
        )
