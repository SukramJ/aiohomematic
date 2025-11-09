# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Module for hub data points implemented using the select category."""

from __future__ import annotations

import logging
from typing import Final

from aiohomematic import i18n
from aiohomematic.const import DataPointCategory
from aiohomematic.decorators import inspector
from aiohomematic.model.hub.data_point import GenericSysvarDataPoint
from aiohomematic.model.support import get_value_from_value_list
from aiohomematic.property_decorators import state_property

_LOGGER: Final = logging.getLogger(__name__)


class SysvarDpSelect(GenericSysvarDataPoint):
    """Implementation of a sysvar select data_point."""

    __slots__ = ()

    _category = DataPointCategory.HUB_SELECT
    _is_extended = True

    @state_property
    def value(self) -> str | None:
        """Get the value of the data_point."""
        if (value := get_value_from_value_list(value=self._value, value_list=self.values)) is not None:
            return value
        return None

    @inspector
    async def send_variable(self, *, value: int | str) -> None:
        """Set the value of the data_point."""
        # We allow setting the value via index as well, just in case.
        if isinstance(value, int) and self._values:
            if 0 <= value < len(self._values):
                await super().send_variable(value=value)
        elif self._values:
            if value in self._values:
                await super().send_variable(value=self._values.index(value))
        else:
            _LOGGER.error(
                i18n.tr(
                    "exception.model.select.value_not_in_value_list",
                    name=self.name,
                    unique_id=self.unique_id,
                )
            )
