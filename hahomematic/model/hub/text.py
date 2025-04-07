"""Module for hub data points implemented using the text category."""

from __future__ import annotations

from typing import cast

from hahomematic.const import DataPointCategory
from hahomematic.model.decorators import state_property
from hahomematic.model.hub.data_point import GenericSysvarDataPoint
from hahomematic.model.support import check_length_and_log


class SysvarDpText(GenericSysvarDataPoint):
    """Implementation of a sysvar text data_point."""

    _category = DataPointCategory.HUB_TEXT
    _is_extended = True

    @state_property
    def value(self) -> str | None:
        """Get the value of the data_point."""
        return cast(str | None, check_length_and_log(name=self._legacy_name, value=self._value))

    async def send_variable(self, value: str | None) -> None:
        """Set the value of the data_point."""
        await super().send_variable(value)
