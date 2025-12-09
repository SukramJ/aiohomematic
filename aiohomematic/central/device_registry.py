# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Device registry for managing device and channel collections.

This module provides a centralized registry for device management within the central unit.
It separates device storage concerns from device lifecycle management.

The DeviceRegistry provides:
- Device storage and lookup by address
- Channel lookup by channel address
- Device iteration and filtering
- Channel identification within text
- Virtual remote device access
"""

from __future__ import annotations

import asyncio
import logging
from typing import Final

from aiohomematic.interfaces.central import CentralInfo
from aiohomematic.interfaces.client import ClientProvider
from aiohomematic.interfaces.model import ChannelProtocol, DeviceProtocol
from aiohomematic.support import get_device_address

_LOGGER: Final = logging.getLogger(__name__)


class DeviceRegistry:
    """Registry for device and channel management."""

    __slots__ = (
        "_central_info",
        "_client_provider",
        "_devices",
        "_lock",
    )

    def __init__(
        self,
        *,
        central_info: CentralInfo,
        client_provider: ClientProvider,
    ) -> None:
        """
        Initialize the device registry.

        Args:
        ----
            central_info: Provider for central system information
            client_provider: Provider for client access

        """
        self._central_info: Final = central_info
        self._client_provider: Final = client_provider
        # {device_address, device}
        self._devices: Final[dict[str, DeviceProtocol]] = {}
        self._lock: Final = asyncio.Lock()

    @property
    def device_count(self) -> int:
        """
        Return the count of devices in the registry.

        Returns
        -------
            Number of devices

        """
        return len(self._devices)

    @property
    def devices(self) -> tuple[DeviceProtocol, ...]:
        """
        Return all devices as a tuple.

        Returns
        -------
            Tuple of all Device instances

        """
        return tuple(self._devices.values())

    async def add_device(self, *, device: DeviceProtocol) -> None:
        """
        Add a device to the registry.

        Args:
        ----
            device: Device instance to add

        """
        async with self._lock:
            self._devices[device.address] = device
        _LOGGER.debug(
            "ADD_DEVICE: Added device %s to registry for %s",
            device.address,
            self._central_info.name,
        )

    async def clear(self) -> None:
        """Clear all devices from the registry."""
        async with self._lock:
            self._devices.clear()
        _LOGGER.debug("CLEAR: Cleared device registry for %s", self._central_info.name)

    def get_channel(self, *, channel_address: str) -> ChannelProtocol | None:
        """
        Get a channel by channel address.

        Args:
        ----
            channel_address: Channel address (e.g., "VCU0000001:1")

        Returns:
        -------
            Channel instance or None if not found

        """
        if device := self.get_device(address=channel_address):
            return device.get_channel(channel_address=channel_address)
        return None

    def get_device(self, *, address: str) -> DeviceProtocol | None:
        """
        Get a device by address.

        Args:
        ----
            address: Device address or channel address

        Returns:
        -------
            Device instance or None if not found

        """
        d_address = get_device_address(address=address)
        return self._devices.get(d_address)

    def get_device_addresses(self) -> frozenset[str]:
        """
        Get all device addresses in the registry.

        Returns
        -------
            Frozen set of device addresses

        """
        return frozenset(self._devices.keys())

    def get_virtual_remotes(self) -> tuple[DeviceProtocol, ...]:
        """
        Get all virtual remote devices from clients.

        Returns
        -------
            Tuple of virtual remote Device instances

        """
        return tuple(vr for cl in self._client_provider.clients if (vr := cl.get_virtual_remote()) is not None)

    def has_device(self, *, address: str) -> bool:
        """
        Check if a device exists in the registry.

        Args:
        ----
            address: Device address

        Returns:
        -------
            True if device exists, False otherwise

        """
        return address in self._devices

    def identify_channel(self, *, text: str) -> ChannelProtocol | None:
        """
        Identify a channel within a text string.

        Args:
        ----
            text: Text to search for channel identification

        Returns:
        -------
            Channel instance or None if not found

        """
        for device in self._devices.values():
            if channel := device.identify_channel(text=text):
                return channel
        return None

    async def remove_device(self, *, device_address: str) -> None:
        """
        Remove a device from the registry.

        Args:
        ----
            device_address: Address of the device to remove

        """
        async with self._lock:
            if device_address not in self._devices:
                _LOGGER.debug(
                    "REMOVE_DEVICE: Device %s not found in registry for %s",
                    device_address,
                    self._central_info.name,
                )
                return
            del self._devices[device_address]
        _LOGGER.debug(
            "REMOVE_DEVICE: Removed device %s from registry for %s",
            device_address,
            self._central_info.name,
        )
