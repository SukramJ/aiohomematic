"""
Module for hub entities implemented using the binary_sensor platform.

See https://www.home-assistant.io/integrations/binary_sensor/.
"""
from __future__ import annotations

from hahomematic.const import HmPlatform
from hahomematic.entity_support import value_property
from hahomematic.hub_platforms.entity import GenericSystemVariable


class HmSysvarBinarySensor(GenericSystemVariable):
    """Implementation of a sysvar binary_sensor."""

    _attr_platform = HmPlatform.HUB_BINARY_SENSOR

    @value_property
    def value(self) -> bool | None:
        """Return the value of the entity."""
        if self._attr_value is not None:
            return bool(self._attr_value)
        return None
