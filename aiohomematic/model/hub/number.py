# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025 Daniel Perna, SukramJ
"""Module for data points implemented using the number category."""

from __future__ import annotations

import logging
from typing import Final

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
    async def send_variable(self, value: float) -> None:
        """Set the value of the data_point."""
        if value is not None and self.max is not None and self.min is not None:
            if self.min <= float(value) <= self.max:
                await super().send_variable(value)
            else:
                _LOGGER.warning(
                    "SYSVAR.NUMBER failed: Invalid value: %s (min: %s, max: %s)",
                    value,
                    self.min,
                    self.max,
                )
            return
        await super().send_variable(value)
