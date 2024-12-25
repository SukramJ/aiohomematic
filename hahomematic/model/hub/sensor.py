"""Module for hub data points implemented using the sensor category."""

from __future__ import annotations

import logging
from typing import Any, Final

from hahomematic.const import DataPointCategory, SysvarType
from hahomematic.model.decorators import state_property
from hahomematic.model.hub.data_point import GenericSysvarDataPoint
from hahomematic.model.support import get_value_from_value_list

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
        return _check_length_and_log(name=self._name, value=self._value)


def _check_length_and_log(name: str | None, value: Any) -> Any:
    """Check the length of a variable and log if too long."""
    if isinstance(value, str) and len(value) > 255:
        _LOGGER.debug(
            "Value of sysvar %s exceedes maximum allowed length of 255 chars. Value will be limited to 255 chars",
            name,
        )
        return value[0:255:1]
    return value
