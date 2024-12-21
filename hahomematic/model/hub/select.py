"""Module for hub data points implemented using the select category."""

from __future__ import annotations

import logging
from typing import Final

from hahomematic.const import DataPointCategory
from hahomematic.decorators import service
from hahomematic.model.decorators import state_property
from hahomematic.model.hub.data_point import GenericSysvarDataPoint
from hahomematic.model.support import get_value_from_value_list

_LOGGER: Final = logging.getLogger(__name__)


class SysvarDpSelect(GenericSysvarDataPoint):
    """Implementation of a sysvar select data_point."""

    _category = DataPointCategory.HUB_SELECT
    _is_extended = True

    @state_property
    def value(self) -> str | None:
        """Get the value of the data_point."""
        if (value := get_value_from_value_list(value=self._value, value_list=self.values)) is not None:
            return value
        return None

    @service()
    async def send_variable(self, value: int | str) -> None:
        """Set the value of the data_point."""
        # We allow setting the value via index as well, just in case.
        if isinstance(value, int) and self._values:
            if 0 <= value < len(self._values):
                await super().send_variable(value)
        elif self._values:
            if value in self._values:
                await super().send_variable(self._values.index(value))
        else:
            _LOGGER.warning(
                "Value not in value_list for %s/%s",
                self.name,
                self.unique_id,
            )
