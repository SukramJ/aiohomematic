"""
Validation schemas for aiohomematic.

This module contains voluptuous schemas used for validating event data
and other structured inputs. Moved here to avoid circular dependencies.
"""

from __future__ import annotations

import voluptuous as vol

from aiohomematic import validator as val
from aiohomematic.const import (
    CDPD,
    DEFAULT_INCLUDE_DEFAULT_DPS,
    DeviceProfile,
    EventKey,
    Field,
    InterfaceEventType,
    Parameter,
)

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

_SCHEMA_ADDITIONAL_DPS = vol.Schema(
    {vol.Required(vol.Any(int, tuple[int, ...])): vol.Schema((vol.Optional(Parameter),))}
)

_SCHEMA_FIELD_DETAILS = vol.Schema({vol.Required(Field): Parameter})

_SCHEMA_FIELD = vol.Schema({vol.Required(vol.Any(int, None)): _SCHEMA_FIELD_DETAILS})

_SCHEMA_DEVICE_GROUP = vol.Schema(
    {
        vol.Required(CDPD.PRIMARY_CHANNEL.value, default=0): vol.Any(val.positive_int, None),
        vol.Required(CDPD.ALLOW_UNDEFINED_GENERIC_DPS.value, default=False): bool,
        vol.Optional(CDPD.STATE_CHANNEL.value): vol.Any(int, None),
        vol.Optional(CDPD.SECONDARY_CHANNELS.value): (val.positive_int,),
        vol.Optional(CDPD.REPEATABLE_FIELDS.value): _SCHEMA_FIELD_DETAILS,
        vol.Optional(CDPD.VISIBLE_REPEATABLE_FIELDS.value): _SCHEMA_FIELD_DETAILS,
        vol.Optional(CDPD.FIELDS.value): _SCHEMA_FIELD,
        vol.Optional(CDPD.VISIBLE_FIELDS.value): _SCHEMA_FIELD,
    }
)

_SCHEMA_DEVICE_GROUPS = vol.Schema(
    {
        vol.Required(CDPD.DEVICE_GROUP.value): _SCHEMA_DEVICE_GROUP,
        vol.Optional(CDPD.ADDITIONAL_DPS.value): _SCHEMA_ADDITIONAL_DPS,
        vol.Optional(CDPD.INCLUDE_DEFAULT_DPS.value, default=DEFAULT_INCLUDE_DEFAULT_DPS): bool,
    }
)

SCHEMA_DEVICE_DESCRIPTION = vol.Schema(
    {
        vol.Required(CDPD.DEFAULT_DPS.value): _SCHEMA_ADDITIONAL_DPS,
        vol.Required(CDPD.DEVICE_DEFINITIONS.value): vol.Schema(
            {
                vol.Required(DeviceProfile): _SCHEMA_DEVICE_GROUPS,
            }
        ),
    }
)
