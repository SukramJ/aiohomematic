"""Module for hub data points implemented using the sensor category."""

from __future__ import annotations

import logging
from typing import Any, Final

from hahomematic.const import DataPointCategory, SysvarType
from hahomematic.model.decorators import state_property
from hahomematic.model.hub.data_point import GenericSysvarDataPoint
from hahomematic.model.support import check_length_and_log, get_value_from_value_list

_LOGGER: Final = logging.getLogger(__name__)


class SysvarDpSensor(GenericSysvarDataPoint):
    """Implementation of a sysvar sensor."""

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
