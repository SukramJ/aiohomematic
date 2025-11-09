# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Module for data points implemented using the number category."""

from __future__ import annotations

import logging
from typing import Final

from aiohomematic import i18n
from aiohomematic.const import DataPointCategory
from aiohomematic.decorators import inspector
from aiohomematic.model.hub.data_point import GenericSysvarDataPoint

_LOGGER: Final = logging.getLogger(__name__)


class SysvarDpNumber(GenericSysvarDataPoint):
    """Implementation of a sysvar number."""

    __slots__ = ()

    _category = DataPointCategory.HUB_NUMBER
    _is_extended = True

    @inspector
    async def send_variable(self, *, value: float) -> None:
        """Set the value of the data_point."""
        if value is not None and self.max is not None and self.min is not None:
            if self.min <= float(value) <= self.max:
                await super().send_variable(value=value)
            else:
                _LOGGER.error(
                    i18n.tr(
                        "exception.model.hub.number.invalid_value",
                        value=value,
                        min=self.min,
                        max=self.max,
                    )
                )
            return
        await super().send_variable(value=value)
