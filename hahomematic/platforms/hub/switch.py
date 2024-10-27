"""
Module for hub data points implemented using the switch platform.

See https://www.home-assistant.io/integrations/switch/.
"""

from __future__ import annotations

from hahomematic.const import HmPlatform
from hahomematic.platforms.hub.data_point import GenericSystemVariable


class HmSysvarSwitch(GenericSystemVariable):
    """Implementation of a sysvar switch data_point."""

    _platform = HmPlatform.HUB_SWITCH
    _is_extended = True
