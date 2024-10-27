"""
Module for hub data points implemented using the text platform.

See https://www.home-assistant.io/integrations/text/.
"""

from __future__ import annotations

from hahomematic.const import HmPlatform
from hahomematic.platforms.hub.data_point import GenericSysvarDataPoint


class SysvarDpText(GenericSysvarDataPoint):
    """Implementation of a sysvar text data_point."""

    _platform = HmPlatform.HUB_TEXT
    _is_extended = True

    async def send_variable(self, value: str | None) -> None:
        """Set the value of the data_point."""
        await super().send_variable(value)
