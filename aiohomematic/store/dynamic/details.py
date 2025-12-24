# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Device details cache for runtime device metadata.

This module provides DeviceDetailsCache which enriches devices with human-readable
names, interface mapping, rooms, functions, and address IDs fetched via the backend.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from datetime import datetime
import logging
from typing import Final, cast

from aiohomematic.const import INIT_DATETIME, MAX_CACHE_AGE, Interface
from aiohomematic.interfaces.central import CentralInfoProtocol
from aiohomematic.interfaces.client import DeviceDetailsWriterProtocol, PrimaryClientProviderProtocol
from aiohomematic.interfaces.model import DeviceRemovalInfoProtocol
from aiohomematic.interfaces.operations import DeviceDetailsProviderProtocol
from aiohomematic.property_decorators import DelegatedProperty
from aiohomematic.support import changed_within_seconds, get_device_address

_LOGGER: Final = logging.getLogger(__name__)


class DeviceDetailsCache(DeviceDetailsProviderProtocol, DeviceDetailsWriterProtocol):
    """Cache for device/channel details."""

    __slots__ = (
        "_central_info",
        "_channel_rooms",
        "_device_channel_rega_ids",
        "_device_rooms",
        "_functions",
        "_interface_cache",
        "_names_cache",
        "_primary_client_provider",
        "_refreshed_at",
    )

    def __init__(
        self,
        *,
        central_info: CentralInfoProtocol,
        primary_client_provider: PrimaryClientProviderProtocol,
    ) -> None:
        """Initialize the device details cache."""
        self._central_info: Final = central_info
        self._primary_client_provider: Final = primary_client_provider
        self._channel_rooms: Final[dict[str, set[str]]] = defaultdict(set)
        self._device_channel_rega_ids: Final[dict[str, int]] = {}
        self._device_rooms: Final[dict[str, set[str]]] = defaultdict(set)
        self._functions: Final[dict[str, set[str]]] = {}
        self._interface_cache: Final[dict[str, Interface]] = {}
        self._names_cache: Final[dict[str, str]] = {}
        self._refreshed_at = INIT_DATETIME

    device_channel_rega_ids: Final = DelegatedProperty[Mapping[str, int]](path="_device_channel_rega_ids")

    def add_address_rega_id(self, *, address: str, rega_id: int) -> None:
        """Add channel id for a channel."""
        self._device_channel_rega_ids[address] = rega_id

    def add_interface(self, *, address: str, interface: Interface) -> None:
        """Add interface to cache."""
        self._interface_cache[address] = interface

    def add_name(self, *, address: str, name: str) -> None:
        """Add name to cache."""
        self._names_cache[address] = name

    def clear(self) -> None:
        """Clear the cache."""
        self._names_cache.clear()
        self._channel_rooms.clear()
        self._device_rooms.clear()
        self._functions.clear()
        self._refreshed_at = INIT_DATETIME

    def get_address_id(self, *, address: str) -> int:
        """Get id for address."""
        return self._device_channel_rega_ids.get(address) or 0

    def get_channel_rooms(self, *, channel_address: str) -> set[str]:
        """Return rooms by channel_address."""
        return self._channel_rooms[channel_address]

    def get_device_rooms(self, *, device_address: str) -> set[str]:
        """Return all rooms by device_address."""
        return set(self._device_rooms.get(device_address, ()))

    def get_function_text(self, *, address: str) -> str | None:
        """Return function by address."""
        if functions := self._functions.get(address):
            return ",".join(functions)
        return None

    def get_interface(self, *, address: str) -> Interface:
        """Get interface from cache."""
        return self._interface_cache.get(address) or Interface.BIDCOS_RF

    def get_name(self, *, address: str) -> str | None:
        """Get name from cache."""
        return self._names_cache.get(address)

    async def load(self, *, direct_call: bool = False) -> None:
        """Fetch names from the backend."""
        if direct_call is False and changed_within_seconds(
            last_change=self._refreshed_at, max_age=int(MAX_CACHE_AGE / 3)
        ):
            return
        self.clear()
        _LOGGER.debug("LOAD: Loading names for %s", self._central_info.name)
        if client := self._primary_client_provider.primary_client:
            await client.fetch_device_details()
        _LOGGER.debug("LOAD: Loading rooms for %s", self._central_info.name)
        self._channel_rooms.clear()
        self._channel_rooms.update(await self._get_all_rooms())
        self._device_rooms.clear()
        self._device_rooms.update(self._prepare_device_rooms())
        _LOGGER.debug("LOAD: Loading functions for %s", self._central_info.name)
        self._functions.clear()
        self._functions.update(await self._get_all_functions())
        self._refreshed_at = datetime.now()

    def remove_device(self, *, device: DeviceRemovalInfoProtocol) -> None:
        """Remove device data from all caches."""
        # Clean device-level entries
        self._names_cache.pop(device.address, None)
        self._interface_cache.pop(device.address, None)
        self._device_channel_rega_ids.pop(device.address, None)
        self._device_rooms.pop(device.address, None)
        self._functions.pop(device.address, None)

        # Clean channel-level entries
        for channel_address in device.channels:
            self._names_cache.pop(channel_address, None)
            self._interface_cache.pop(channel_address, None)
            self._device_channel_rega_ids.pop(channel_address, None)
            self._channel_rooms.pop(channel_address, None)
            self._functions.pop(channel_address, None)

    async def _get_all_functions(self) -> Mapping[str, set[str]]:
        """Get all functions, if available."""
        if client := self._primary_client_provider.primary_client:
            return cast(
                Mapping[str, set[str]],
                await client.get_all_functions(),
            )
        return {}

    async def _get_all_rooms(self) -> Mapping[str, set[str]]:
        """Get all rooms, if available."""
        if client := self._primary_client_provider.primary_client:
            return cast(
                Mapping[str, set[str]],
                await client.get_all_rooms(),
            )
        return {}

    def _prepare_device_rooms(self) -> dict[str, set[str]]:
        """
        Return rooms by device_address.

        Aggregation algorithm:
            The CCU stores room assignments at the channel level (e.g., "ABC123:1" is in "Living Room").
            Devices themselves don't have direct room assignments - they inherit from their channels.
            This method aggregates channel rooms to the device level by:
            1. Iterating all channel_address -> rooms mappings
            2. Extracting the device_address from each channel_address
            3. Merging all channel rooms into a set per device

        Result: A device is considered "in" all rooms that any of its channels are in.
        """
        _device_rooms: Final[dict[str, set[str]]] = defaultdict(set)
        for channel_address, rooms in self._channel_rooms.items():
            if rooms:
                # Extract device address (e.g., "ABC123:1" -> "ABC123")
                # and merge this channel's rooms into the device's room set
                _device_rooms[get_device_address(address=channel_address)].update(rooms)
        return _device_rooms
