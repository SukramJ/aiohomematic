# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Device coordinator for managing device lifecycle and operations.

This module provides centralized device management including creation,
registration, removal, and device-related operations.

The DeviceCoordinator provides:
- Device creation and initialization
- Device registration via DeviceRegistry
- Device removal and cleanup
- Device description management
- Data point and event creation for devices
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Set as AbstractSet
import logging
from typing import TYPE_CHECKING, Any, Final, cast

from aiohomematic import i18n
from aiohomematic.const import (
    CATEGORIES,
    DATA_POINT_EVENTS,
    BackendSystemEvent,
    DataPointCategory,
    DeviceDescription,
    SourceOfDeviceCreation,
)
from aiohomematic.decorators import inspector
from aiohomematic.exceptions import AioHomematicException
from aiohomematic.model import create_data_points_and_events
from aiohomematic.model.custom import create_custom_data_points
from aiohomematic.model.data_point import CallbackDataPoint
from aiohomematic.model.device import Device
from aiohomematic.model.event import GenericEvent
from aiohomematic.model.interfaces import CentralInfo, ConfigProvider, CoordinatorProvider
from aiohomematic.support import extract_device_addresses_from_device_descriptions, extract_exc_args

if TYPE_CHECKING:
    from aiohomematic.central.device_registry import DeviceRegistry
    from aiohomematic.client import Client
    from aiohomematic.model.device import Channel

_LOGGER: Final = logging.getLogger(__name__)


class DeviceCoordinator:
    """Coordinator for device lifecycle and operations."""

    __slots__ = (
        "_central",
        "_coordinator_provider",
        "_central_info",
        "_config_provider",
        "_device_add_semaphore",
    )

    def __init__(
        self,
        *,
        central: Any,  # CentralUnit at runtime, but avoid circular import
        coordinator_provider: CoordinatorProvider,
        central_info: CentralInfo,
        config_provider: ConfigProvider,
    ) -> None:
        """
        Initialize the device coordinator.

        Args:
        ----
            central: The central unit instance (required for device creation)
            coordinator_provider: Provider for accessing other coordinators
            central_info: Provider for central system information
            config_provider: Provider for configuration access

        """
        self._central: Final = central
        self._coordinator_provider: Final = coordinator_provider
        self._central_info: Final = central_info
        self._config_provider: Final = config_provider
        self._device_add_semaphore: Final = asyncio.Semaphore()

    @property
    def device_registry(self) -> DeviceRegistry:
        """Return the device registry."""
        return self._coordinator_provider.device_registry  # type: ignore[no-any-return]

    @property
    def devices(self) -> tuple[Device, ...]:
        """Return all devices."""
        return self.device_registry.devices

    async def add_new_device_manually(self, *, interface_id: str, address: str) -> None:
        """
        Add new device manually triggered to central unit.

        Args:
        ----
            interface_id: Interface identifier
            address: Device address

        """
        if not self._coordinator_provider.client_coordinator.has_client(interface_id=interface_id):
            _LOGGER.error(  # i18n-log: ignore
                "ADD_NEW_DEVICES_MANUALLY failed: Missing client for interface_id %s",
                interface_id,
            )
            return

        client = self._coordinator_provider.client_coordinator.get_client(interface_id=interface_id)
        if not (device_descriptions := await client.get_all_device_descriptions(device_address=address)):
            _LOGGER.error(  # i18n-log: ignore
                "ADD_NEW_DEVICES_MANUALLY failed: No device description found for address %s on interface_id %s",
                address,
                interface_id,
            )
            return

        await self._add_new_devices(
            interface_id=interface_id,
            device_descriptions=device_descriptions,
            source=SourceOfDeviceCreation.MANUAL,
        )

    async def add_new_devices(self, *, interface_id: str, device_descriptions: tuple[DeviceDescription, ...]) -> None:
        """
        Add new devices to central unit (callback from backend).

        Args:
        ----
            interface_id: Interface identifier
            device_descriptions: Tuple of device descriptions

        """
        source = (
            SourceOfDeviceCreation.NEW
            if self._coordinator_provider.cache_coordinator.device_descriptions.has_device_descriptions(
                interface_id=interface_id
            )
            else SourceOfDeviceCreation.INIT
        )
        await self._add_new_devices(interface_id=interface_id, device_descriptions=device_descriptions, source=source)

    def check_for_new_device_addresses(self, *, interface_id: str | None = None) -> Mapping[str, set[str]]:
        """
        Check if there are new devices that need to be created.

        Args:
        ----
            interface_id: Optional interface identifier to check

        Returns:
        -------
            Mapping of interface IDs to sets of new device addresses

        """
        new_device_addresses: dict[str, set[str]] = {}

        # Cache existing device addresses once to avoid repeated mapping lookups
        existing_addresses = self.device_registry.get_device_addresses()

        def _check_for_new_device_addresses_helper(*, iid: str) -> None:
            """Check if there are new devices that need to be created."""
            if not self._coordinator_provider.cache_coordinator.paramset_descriptions.has_interface_id(
                interface_id=iid
            ):
                _LOGGER.debug(
                    "CHECK_FOR_NEW_DEVICE_ADDRESSES: Skipping interface %s, missing paramsets",
                    iid,
                )
                return
            # Build the set locally and assign only if non-empty to avoid add-then-delete pattern
            # Use set difference for speed on large collections
            addresses = set(
                self._coordinator_provider.cache_coordinator.device_descriptions.get_addresses(interface_id=iid)
            )
            # get_addresses returns an iterable (likely tuple); convert to set once for efficient diff
            if new_set := addresses - existing_addresses:
                new_device_addresses[iid] = new_set

        if interface_id:
            _check_for_new_device_addresses_helper(iid=interface_id)
        else:
            for iid in self._coordinator_provider.client_coordinator.interface_ids:
                _check_for_new_device_addresses_helper(iid=iid)

        if _LOGGER.isEnabledFor(level=logging.DEBUG):
            count = sum(len(item) for item in new_device_addresses.values())
            _LOGGER.debug(
                "CHECK_FOR_NEW_DEVICE_ADDRESSES: %s: %i.",
                "Found new device addresses" if new_device_addresses else "Did not find any new device addresses",
                count,
            )

        return new_device_addresses

    @inspector
    async def create_central_links(self) -> None:
        """Create central links to support press events on all channels with click events."""
        for device in self.devices:
            await device.create_central_links()

    async def create_devices(
        self, *, new_device_addresses: Mapping[str, set[str]], source: SourceOfDeviceCreation
    ) -> None:
        """
        Trigger creation of the objects that expose the functionality.

        Args:
        ----
            new_device_addresses: Mapping of interface IDs to device addresses
            source: Source of device creation

        """
        if not self._coordinator_provider.client_coordinator.has_clients:
            raise AioHomematicException(
                i18n.tr(
                    "exception.central.create_devices.no_clients",
                    name=self._central_info.name,
                )
            )
        _LOGGER.debug("CREATE_DEVICES: Starting to create devices for %s", self._central_info.name)

        new_devices = set[Device]()

        for interface_id, device_addresses in new_device_addresses.items():
            for device_address in device_addresses:
                # Do we check for duplicates here? For now, we do.
                if self.device_registry.has_device(address=device_address):
                    continue
                device: Device | None = None
                try:
                    device = Device(
                        central=cast(Any, self._central),  # Central is CentralUnit at runtime
                        interface_id=interface_id,
                        device_address=device_address,
                    )
                except Exception as exc:
                    _LOGGER.error(  # i18n-log: ignore
                        "CREATE_DEVICES failed: %s [%s] Unable to create device: %s, %s",
                        type(exc).__name__,
                        extract_exc_args(exc=exc),
                        interface_id,
                        device_address,
                    )
                try:
                    if device:
                        create_data_points_and_events(device=device)
                        create_custom_data_points(device=device)
                        new_devices.add(device)
                        self.device_registry.add_device(device=device)
                except Exception as exc:
                    _LOGGER.error(  # i18n-log: ignore
                        "CREATE_DEVICES failed: %s [%s] Unable to create data points: %s, %s",
                        type(exc).__name__,
                        extract_exc_args(exc=exc),
                        interface_id,
                        device_address,
                    )
        _LOGGER.debug("CREATE_DEVICES: Finished creating devices for %s", self._central_info.name)

        if new_devices:
            for device in new_devices:
                await device.finalize_init()
            new_dps = _get_new_data_points(new_devices=new_devices)
            new_channel_events = _get_new_channel_events(new_devices=new_devices)
            self._coordinator_provider.event_coordinator.emit_backend_system_callback(
                system_event=BackendSystemEvent.DEVICES_CREATED,
                new_data_points=new_dps,
                new_channel_events=new_channel_events,
                source=source,
            )

    async def delete_device(self, *, interface_id: str, device_address: str) -> None:
        """
        Delete a device from central.

        Args:
        ----
            interface_id: Interface identifier
            device_address: Device address

        """
        _LOGGER.debug(
            "DELETE_DEVICE: interface_id = %s, device_address = %s",
            interface_id,
            device_address,
        )

        if (device := self.device_registry.get_device(address=device_address)) is None:
            return

        await self.delete_devices(interface_id=interface_id, addresses=(device_address, *tuple(device.channels.keys())))

    async def delete_devices(self, *, interface_id: str, addresses: tuple[str, ...]) -> None:
        """
        Delete multiple devices from central.

        Args:
        ----
            interface_id: Interface identifier
            addresses: Tuple of addresses to delete

        """
        _LOGGER.debug(
            "DELETE_DEVICES: interface_id = %s, addresses = %s",
            interface_id,
            str(addresses),
        )

        for address in addresses:
            if device := self.device_registry.get_device(address=address):
                self.remove_device(device=device)

        await self._coordinator_provider.cache_coordinator.save_all(
            save_device_descriptions=True,
            save_paramset_descriptions=True,
        )

    def get_channel(self, *, channel_address: str) -> Channel | None:
        """
        Return Homematic channel.

        Args:
        ----
            channel_address: Channel address

        Returns:
        -------
            Channel instance or None if not found

        """
        return self.device_registry.get_channel(channel_address=channel_address)

    def get_device(self, *, address: str) -> Device | None:
        """
        Return Homematic device.

        Args:
        ----
            address: Device address

        Returns:
        -------
            Device instance or None if not found

        """
        return self.device_registry.get_device(address=address)

    def get_virtual_remotes(self) -> tuple[Device, ...]:
        """Get the virtual remotes for all clients."""
        return self.device_registry.get_virtual_remotes()

    def identify_channel(self, *, text: str) -> Channel | None:
        """
        Identify channel within a text.

        Args:
        ----
            text: Text to search for channel identification

        Returns:
        -------
            Channel instance or None if not found

        """
        return self.device_registry.identify_channel(text=text)

    def list_devices(self, *, interface_id: str) -> list[DeviceDescription]:
        """
        Return already existing devices to the backend.

        Args:
        ----
            interface_id: Interface identifier

        Returns:
        -------
            List of device descriptions

        """
        result = self._coordinator_provider.cache_coordinator.device_descriptions.get_raw_device_descriptions(
            interface_id=interface_id
        )
        _LOGGER.debug("LIST_DEVICES: interface_id = %s, channel_count = %i", interface_id, len(result))
        return cast(list[DeviceDescription], result)

    async def refresh_device_descriptions_and_create_missing_devices(
        self, *, client: Client, refresh_only_existing: bool, device_address: str | None = None
    ) -> None:
        """
        Refresh device descriptions and create missing devices.

        Args:
        ----
            client: Client to use for refreshing
            refresh_only_existing: Whether to only refresh existing devices
            device_address: Optional device address to refresh

        """
        device_descriptions: tuple[DeviceDescription, ...] | None = None

        if (
            device_address
            and (device_description := await client.get_device_description(device_address=device_address)) is not None
        ):
            device_descriptions = (device_description,)
        else:
            device_descriptions = await client.list_devices()

        if (
            device_descriptions
            and refresh_only_existing
            and (
                existing_device_descriptions := tuple(
                    dev_desc
                    for dev_desc in list(device_descriptions)
                    if dev_desc["ADDRESS"]
                    in self._coordinator_provider.cache_coordinator.device_descriptions.get_device_descriptions(
                        interface_id=client.interface_id
                    )
                )
            )
        ):
            device_descriptions = existing_device_descriptions

        if device_descriptions:
            await self._add_new_devices(
                interface_id=client.interface_id,
                device_descriptions=device_descriptions,
                source=SourceOfDeviceCreation.REFRESH,
            )

    @inspector(re_raise=False)
    async def refresh_firmware_data(self, *, device_address: str | None = None) -> None:
        """
        Refresh device firmware data.

        Args:
        ----
            device_address: Optional device address to refresh, or None for all devices

        """
        if device_address and (device := self.get_device(address=device_address)) is not None and device.is_updatable:
            await self.refresh_device_descriptions_and_create_missing_devices(
                client=device.client, refresh_only_existing=True, device_address=device_address
            )
            device.refresh_firmware_data()
        else:
            for client in self._coordinator_provider.client_coordinator.clients:
                await self.refresh_device_descriptions_and_create_missing_devices(
                    client=client, refresh_only_existing=True
                )
            for device in self.devices:
                if device.is_updatable:
                    device.refresh_firmware_data()

    @inspector
    async def remove_central_links(self) -> None:
        """Remove central links."""
        for device in self.devices:
            await device.remove_central_links()

    def remove_device(self, *, device: Device) -> None:
        """
        Remove device from central collections.

        Args:
        ----
            device: Device to remove

        """
        if not self.device_registry.has_device(address=device.address):
            _LOGGER.debug(
                "REMOVE_DEVICE: device %s not registered in central",
                device.address,
            )
            return

        device.remove()
        self._coordinator_provider.cache_coordinator.remove_device_from_caches(device=device)
        self.device_registry.remove_device(device_address=device.address)

    @inspector(measure_performance=True)
    async def _add_new_devices(
        self, *, interface_id: str, device_descriptions: tuple[DeviceDescription, ...], source: SourceOfDeviceCreation
    ) -> None:
        """
        Add new devices to central unit.

        Args:
        ----
            interface_id: Interface identifier
            device_descriptions: Tuple of device descriptions
            source: Source of device creation

        """
        if not device_descriptions:
            _LOGGER.debug(
                "ADD_NEW_DEVICES: Nothing to add for interface_id %s",
                interface_id,
            )
            return

        _LOGGER.debug(
            "ADD_NEW_DEVICES: interface_id = %s, device_descriptions = %s",
            interface_id,
            len(device_descriptions),
        )

        if not self._coordinator_provider.client_coordinator.has_client(interface_id=interface_id):
            _LOGGER.error(  # i18n-log: ignore
                "ADD_NEW_DEVICES failed: Missing client for interface_id %s",
                interface_id,
            )
            return

        async with self._device_add_semaphore:
            if not (
                new_device_descriptions := self._identify_new_device_descriptions(
                    device_descriptions=device_descriptions, interface_id=interface_id
                )
            ):
                _LOGGER.debug("ADD_NEW_DEVICES: Nothing to add for interface_id %s", interface_id)
                return

            # Here we block the automatic creation of new devices, if required
            if (
                self._config_provider.config.delay_new_device_creation
                and source == SourceOfDeviceCreation.NEW
                and (
                    new_addresses := extract_device_addresses_from_device_descriptions(
                        device_descriptions=new_device_descriptions
                    )
                )
            ):
                self._coordinator_provider.event_coordinator.emit_backend_system_callback(
                    system_event=BackendSystemEvent.DEVICES_DELAYED,
                    new_addresses=new_addresses,
                    interface_id=interface_id,
                    source=source,
                )
                return

            client = self._coordinator_provider.client_coordinator.get_client(interface_id=interface_id)
            save_descriptions = False
            for dev_desc in new_device_descriptions:
                try:
                    self._coordinator_provider.cache_coordinator.device_descriptions.add_device(
                        interface_id=interface_id, device_description=dev_desc
                    )
                    await client.fetch_paramset_descriptions(device_description=dev_desc)
                    save_descriptions = True
                except Exception as exc:  # pragma: no cover
                    save_descriptions = False
                    _LOGGER.error(  # i18n-log: ignore
                        "UPDATE_CACHES_WITH_NEW_DEVICES failed: %s [%s]",
                        type(exc).__name__,
                        extract_exc_args(exc=exc),
                    )

            await self._coordinator_provider.cache_coordinator.save_all(
                save_device_descriptions=save_descriptions,
                save_paramset_descriptions=save_descriptions,
            )

        if new_device_addresses := self.check_for_new_device_addresses(interface_id=interface_id):
            await self._coordinator_provider.cache_coordinator.device_details.load()
            await self._coordinator_provider.cache_coordinator.load_data_cache(interface=client.interface)
            await self.create_devices(new_device_addresses=new_device_addresses, source=source)

    def _identify_new_device_descriptions(
        self, *, device_descriptions: tuple[DeviceDescription, ...], interface_id: str | None = None
    ) -> tuple[DeviceDescription, ...]:
        """
        Identify devices whose ADDRESS isn't already known on any interface.

        Args:
        ----
            device_descriptions: Tuple of device descriptions
            interface_id: Optional interface identifier

        Returns:
        -------
            Tuple of new device descriptions

        """
        known_addresses = self._coordinator_provider.cache_coordinator.device_descriptions.get_addresses(
            interface_id=interface_id
        )
        return tuple(
            dev_desc
            for dev_desc in device_descriptions
            if (dev_desc["ADDRESS"] if not (parent_address := dev_desc.get("PARENT")) else parent_address)
            not in known_addresses
        )


def _get_new_channel_events(*, new_devices: set[Device]) -> tuple[tuple[GenericEvent, ...], ...]:
    """
    Return new channel events.

    Args:
    ----
        new_devices: Set of new devices

    Returns:
    -------
        Tuple of channel event tuples

    """
    channel_events: list[tuple[GenericEvent, ...]] = []

    for device in new_devices:
        for event_type in DATA_POINT_EVENTS:
            if (hm_channel_events := list(device.get_events(event_type=event_type, registered=False).values())) and len(
                hm_channel_events
            ) > 0:
                channel_events.append(hm_channel_events)  # type: ignore[arg-type] # noqa: PERF401

    return tuple(channel_events)


def _get_new_data_points(
    *,
    new_devices: set[Device],
) -> Mapping[DataPointCategory, AbstractSet[CallbackDataPoint]]:
    """
    Return new data points by category.

    Args:
    ----
        new_devices: Set of new devices

    Returns:
    -------
        Mapping of categories to data points

    """
    data_points_by_category: dict[DataPointCategory, set[CallbackDataPoint]] = {
        category: set() for category in CATEGORIES if category != DataPointCategory.EVENT
    }

    for device in new_devices:
        for category, data_points in data_points_by_category.items():
            data_points.update(device.get_data_points(category=category, exclude_no_create=True, registered=False))

    return data_points_by_category
