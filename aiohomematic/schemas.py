"""
Validation schemas for aiohomematic.

This module contains voluptuous schemas used for validating event data
and other structured inputs. Moved here to avoid circular dependencies.
"""

from __future__ import annotations

import voluptuous as vol

from aiohomematic import validator as val
from aiohomematic.const import EventKey, InterfaceEventType

EVENT_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(str(EventKey.ADDRESS)): val.device_address,
        vol.Required(str(EventKey.CHANNEL_NO)): val.channel_no,
        vol.Required(str(EventKey.MODEL)): str,
        vol.Required(str(EventKey.INTERFACE_ID)): str,
        vol.Required(str(EventKey.PARAMETER)): str,
        vol.Optional(str(EventKey.VALUE)): vol.Any(bool, int),
    }
)

INTERFACE_EVENT_SCHEMA = vol.Schema(
    {
        vol.Required(str(EventKey.INTERFACE_ID)): str,
        vol.Required(str(EventKey.TYPE)): InterfaceEventType,
        vol.Required(str(EventKey.DATA)): vol.Schema(
            {vol.Required(vol.Any(EventKey)): vol.Schema(vol.Any(str, int, bool))}
        ),
    }
)
