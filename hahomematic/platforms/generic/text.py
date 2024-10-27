"""
Module for data points implemented using the text platform.

See https://www.home-assistant.io/integrations/text/.
"""

from __future__ import annotations

from hahomematic.const import HmPlatform
from hahomematic.platforms.generic.data_point import GenericDataPoint


class HmText(GenericDataPoint[str, str]):
    """
    Implementation of a text.

    This is a default platform that gets automatically generated.
    """

    _platform = HmPlatform.TEXT
