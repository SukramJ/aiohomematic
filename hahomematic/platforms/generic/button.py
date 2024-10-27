"""
Module for data points implemented using the button platform.

See https://www.home-assistant.io/integrations/boton/.
"""

from __future__ import annotations

from hahomematic.const import HmPlatform
from hahomematic.platforms.decorators import service
from hahomematic.platforms.generic.data_point import GenericDataPoint


class HmButton(GenericDataPoint[None, bool]):
    """
    Implementation of a button.

    This is a default platform that gets automatically generated.
    """

    _platform = HmPlatform.BUTTON
    _validate_state_change = False

    @service()
    async def press(self) -> None:
        """Handle the button press."""
        await self.send_value(value=True)
