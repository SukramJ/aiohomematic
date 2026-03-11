# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Address parsing and validation utilities for Homematic device/channel addresses.

Public API of this module is defined by __all__.
"""

from functools import lru_cache

from aiohomematic.const import ADDRESS_SEPARATOR, CHANNEL_ADDRESS_PATTERN, DEVICE_ADDRESS_PATTERN, ParamsetKey

__all__ = [
    "get_channel_address",
    "get_channel_no",
    "get_device_address",
    "get_split_channel_address",
    "is_channel_address",
    "is_device_address",
    "is_paramset_key",
]


def get_channel_address(*, device_address: str, channel_no: int | None) -> str:
    """Return the channel address."""
    return device_address if channel_no is None else f"{device_address}:{channel_no}"


def get_device_address(*, address: str) -> str:
    """Return the device part of an address."""
    return get_split_channel_address(channel_address=address)[0]


def get_channel_no(*, address: str) -> int | None:
    """Return the channel part of an address."""
    return get_split_channel_address(channel_address=address)[1]


def is_channel_address(*, address: str) -> bool:
    """Check if it is a channel address."""
    return CHANNEL_ADDRESS_PATTERN.match(address) is not None


def is_device_address(*, address: str) -> bool:
    """Check if it is a device address."""
    return DEVICE_ADDRESS_PATTERN.match(address) is not None


def is_paramset_key(*, paramset_key: ParamsetKey | str) -> bool:
    """Check if it is a paramset key."""
    return isinstance(paramset_key, ParamsetKey) or (isinstance(paramset_key, str) and paramset_key in ParamsetKey)


@lru_cache(maxsize=4096)
def get_split_channel_address(*, channel_address: str) -> tuple[str, int | None]:
    """
    Return the device part of an address.

    Cached to avoid redundant parsing across layers when repeatedly handling
    the same channel addresses.
    """
    if ADDRESS_SEPARATOR in channel_address:
        device_address, channel_no = channel_address.split(ADDRESS_SEPARATOR)
        if channel_no in (None, "None"):
            return device_address, None
        return device_address, int(channel_no)
    return channel_address, None
