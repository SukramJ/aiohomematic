# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025 Daniel Perna, SukramJ
"""
Validator functions used within aiohomematic.

Public API of this module is defined by __all__.
"""

from __future__ import annotations

import inspect

import voluptuous as vol

from aiohomematic.const import BLOCKED_CATEGORIES, CATEGORIES, HUB_CATEGORIES, MAX_WAIT_FOR_CALLBACK, DataPointCategory
from aiohomematic.model.custom import definition as hmed
from aiohomematic.support import (
    check_password,
    is_channel_address,
    is_device_address,
    is_hostname,
    is_ipv4_address,
    is_paramset_key,
)

channel_no = vol.All(vol.Coerce(int), vol.Range(min=0, max=999))
positive_int = vol.All(vol.Coerce(int), vol.Range(min=0))
wait_for = vol.All(vol.Coerce(int), vol.Range(min=1, max=MAX_WAIT_FOR_CALLBACK))


def channel_address(value: str) -> str:
    """Validate channel_address."""
    if is_channel_address(address=value):
        return value
    raise vol.Invalid("channel_address is invalid")


def device_address(value: str) -> str:
    """Validate channel_address."""
    if is_device_address(address=value):
        return value
    raise vol.Invalid("device_address is invalid")


def hostname(value: str) -> str:
    """Validate hostname."""
    if is_hostname(hostname=value):
        return value
    raise vol.Invalid("hostname is invalid")


def ipv4_address(value: str) -> str:
    """Validate ipv4_address."""
    if is_ipv4_address(address=value):
        return value
    raise vol.Invalid("ipv4_address is invalid")


def password(value: str) -> str:
    """Validate password."""
    if check_password(password=value):
        return value
    raise vol.Invalid("password is invalid")


def paramset_key(value: str) -> str:
    """Validate paramset_key."""
    if is_paramset_key(paramset_key=value):
        return value
    raise vol.Invalid("paramset_key is invalid")


address = vol.All(vol.Coerce(str), vol.Any(device_address, channel_address))
host = vol.All(vol.Coerce(str), vol.Any(hostname, ipv4_address))


def validate_startup() -> None:
    """
    Validate enum and mapping exhaustiveness at startup.

    - Ensure DataPointCategory coverage: all categories except UNDEFINED must be present
      in either HUB_CATEGORIES or CATEGORIES. UNDEFINED must not appear in those lists.
    """
    categories_in_lists = set(BLOCKED_CATEGORIES) | set(CATEGORIES) | set(HUB_CATEGORIES)
    all_categories = set(DataPointCategory)
    if DataPointCategory.UNDEFINED in categories_in_lists:
        raise vol.Invalid(
            "DataPointCategory.UNDEFINED must not be present in BLOCKED_CATEGORIES/CATEGORIES/HUB_CATEGORIES"
        )

    if missing := all_categories - {DataPointCategory.UNDEFINED} - categories_in_lists:
        missing_str = ", ".join(sorted(c.value for c in missing))
        raise vol.Invalid(
            f"BLOCKED_CATEGORIES/CATEGORIES/HUB_CATEGORIES are not exhaustive. Missing categories: {missing_str}"
        )

    # Validate custom definition mapping schema (Field <-> Parameter mappings)
    # This ensures Field mappings are valid and consistent at startup.
    if hmed.validate_custom_data_point_definition() is None:
        raise vol.Invalid("Custom data point definition schema is invalid")


# Define public API for this module
__all__ = tuple(
    sorted(
        name
        for name, obj in globals().items()
        if not name.startswith("_")
        and (inspect.isfunction(obj) or inspect.isclass(obj))
        and getattr(obj, "__module__", __name__) == __name__
    )
)
