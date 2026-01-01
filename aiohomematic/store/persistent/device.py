# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Device description registry for persisting device/channel metadata.

This module provides DeviceDescriptionRegistry which persists device descriptions
per interface, including the mapping of device/channels and model metadata.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
import logging
from typing import TYPE_CHECKING, Any, Final

from aiohomematic import i18n
from aiohomematic.const import ADDRESS_SEPARATOR, DeviceDescription
from aiohomematic.exceptions import DescriptionNotFoundException
from aiohomematic.interfaces import DeviceDescriptionProviderProtocol, DeviceDescriptionsAccessProtocol
from aiohomematic.interfaces.model import DeviceRemovalInfoProtocol
from aiohomematic.store.persistent.base import BasePersistentCache
from aiohomematic.support import get_device_address

if TYPE_CHECKING:
    from aiohomematic.interfaces import ConfigProviderProtocol
    from aiohomematic.store.storage import StorageProtocol

_LOGGER: Final = logging.getLogger(__name__)


class DeviceDescriptionRegistry(
    BasePersistentCache, DeviceDescriptionProviderProtocol, DeviceDescriptionsAccessProtocol
):
    """Registry for device/channel descriptions."""

    __slots__ = (
        "_addresses",
        "_device_descriptions",
    )

    def __init__(
        self,
        *,
        storage: StorageProtocol,
        config_provider: ConfigProviderProtocol,
    ) -> None:
        """
        Initialize the device description cache.

        Args:
            storage: Storage instance for persistence.
            config_provider: Provider for configuration access.

        """
        # {interface_id, {device_address, [channel_address]}}
        self._addresses: Final[dict[str, dict[str, set[str]]]] = defaultdict(lambda: defaultdict(set))
        # {interface_id, {address, device_descriptions}}
        self._device_descriptions: Final[dict[str, dict[str, DeviceDescription]]] = defaultdict(dict)
        super().__init__(
            storage=storage,
            config_provider=config_provider,
        )

    @property
    def _raw_device_descriptions(self) -> dict[str, list[DeviceDescription]]:
        """Return the raw device descriptions (alias to _content)."""
        return self._content

    @property
    def size(self) -> int:
        """Return total number of device descriptions in cache."""
        return sum(len(descriptions) for descriptions in self._raw_device_descriptions.values())

    def add_device(self, *, interface_id: str, device_description: DeviceDescription) -> None:
        """Add a device to the cache."""
        # Fast-path: If the address is not yet known, skip costly removal operations.
        if (address := device_description["ADDRESS"]) not in self._device_descriptions[interface_id]:
            self._raw_device_descriptions[interface_id].append(device_description)
            self._process_device_description(interface_id=interface_id, device_description=device_description)
            return
        # Address exists: remove old entries before adding the new description.
        self._remove_device(
            interface_id=interface_id,
            addresses_to_remove=[address],
        )
        self._raw_device_descriptions[interface_id].append(device_description)
        self._process_device_description(interface_id=interface_id, device_description=device_description)

    def find_device_description(self, *, interface_id: str, device_address: str) -> DeviceDescription | None:
        """Return the device description by interface and device_address."""
        return self._device_descriptions[interface_id].get(device_address)

    def get_addresses(self, *, interface_id: str | None = None) -> frozenset[str]:
        """Return the addresses by interface as a set."""
        if interface_id:
            return frozenset(self._addresses[interface_id])
        return frozenset(addr for interface_id in self.get_interface_ids() for addr in self._addresses[interface_id])

    def get_device_description(self, *, interface_id: str, address: str) -> DeviceDescription:
        """Return the device description by interface and device_address."""
        try:
            return self._device_descriptions[interface_id][address]
        except KeyError as exc:
            raise DescriptionNotFoundException(
                i18n.tr(
                    key="exception.store.device_description.not_found",
                    address=address,
                    interface_id=interface_id,
                )
            ) from exc

    def get_device_descriptions(self, *, interface_id: str) -> Mapping[str, DeviceDescription]:
        """Return the devices by interface."""
        return self._device_descriptions[interface_id]

    def get_device_with_channels(self, *, interface_id: str, device_address: str) -> Mapping[str, DeviceDescription]:
        """Return the device dict by interface and device_address."""
        device_descriptions: dict[str, DeviceDescription] = {
            device_address: self.get_device_description(interface_id=interface_id, address=device_address)
        }
        children = device_descriptions[device_address]["CHILDREN"]
        for channel_address in children:
            device_descriptions[channel_address] = self.get_device_description(
                interface_id=interface_id, address=channel_address
            )
        return device_descriptions

    def get_interface_ids(self) -> tuple[str, ...]:
        """Return the interface ids."""
        return tuple(self._raw_device_descriptions.keys())

    def get_model(self, *, device_address: str) -> str | None:
        """Return the device type."""
        for data in self._device_descriptions.values():
            if items := data.get(device_address):
                return items["TYPE"]
        return None

    def get_raw_device_descriptions(self, *, interface_id: str) -> list[DeviceDescription]:
        """Retrieve raw device descriptions from the cache."""
        return self._raw_device_descriptions[interface_id]

    def has_device_descriptions(self, *, interface_id: str) -> bool:
        """Return the devices by interface."""
        return interface_id in self._device_descriptions

    def remove_device(self, *, device: DeviceRemovalInfoProtocol) -> None:
        """Remove device from cache."""
        self._remove_device(
            interface_id=device.interface_id,
            addresses_to_remove=[device.address, *device.channels.keys()],
        )

    def _convert_device_descriptions(self, *, interface_id: str, device_descriptions: list[DeviceDescription]) -> None:
        """Convert provided list of device descriptions."""
        for device_description in device_descriptions:
            self._process_device_description(interface_id=interface_id, device_description=device_description)

    def _create_empty_content(self) -> dict[str, Any]:
        """Create empty content structure."""
        return defaultdict(list)

    def _process_device_description(self, *, interface_id: str, device_description: DeviceDescription) -> None:
        """Convert provided dict of device descriptions."""
        address = device_description["ADDRESS"]
        device_address = get_device_address(address=address)
        self._device_descriptions[interface_id][address] = device_description

        # Avoid redundant membership checks; set.add is idempotent and cheaper than check+add
        addr_set = self._addresses[interface_id][device_address]
        addr_set.add(device_address)
        addr_set.add(address)

    def _process_loaded_content(self, *, data: dict[str, Any]) -> None:
        """Rebuild indexes from loaded data."""
        self._addresses.clear()
        self._device_descriptions.clear()
        for interface_id, device_descriptions in data.items():
            self._convert_device_descriptions(
                interface_id=interface_id,
                device_descriptions=device_descriptions,
            )

    def _remove_device(self, *, interface_id: str, addresses_to_remove: list[str]) -> None:
        """Remove a device from the cache."""
        # Use a set for faster membership checks
        addresses_set = set(addresses_to_remove)
        self._raw_device_descriptions[interface_id] = [
            device for device in self._raw_device_descriptions[interface_id] if device["ADDRESS"] not in addresses_set
        ]
        addr_map = self._addresses[interface_id]
        desc_map = self._device_descriptions[interface_id]
        for address in addresses_set:
            # Pop with default to avoid KeyError and try/except overhead
            if ADDRESS_SEPARATOR not in address:
                addr_map.pop(address, None)
            desc_map.pop(address, None)
