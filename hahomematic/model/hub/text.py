"""Module for hub data points implemented using the text category."""

from __future__ import annotations

from hahomematic.const import DataPointCategory
from hahomematic.model.hub.data_point import GenericSysvarDataPoint


class SysvarDpText(GenericSysvarDataPoint):
    """Implementation of a sysvar text data_point."""

    _category = DataPointCategory.HUB_TEXT
    _is_extended = True

    async def send_variable(self, value: str | None) -> None:
        """Set the value of the data_point."""
        await super().send_variable(value)
