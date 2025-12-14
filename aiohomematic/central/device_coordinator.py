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
from collections import defaultdict
from collections.abc import Mapping, Set as AbstractSet
import logging
from typing import TYPE_CHECKING, Final

from aiohomematic import i18n
from aiohomematic.central.decorators import callback_backend_system
from aiohomematic.const import (
    CATEGORIES,
    DATA_POINT_EVENTS,
    BackendSystemEvent,
    DataPointCategory,
    DeviceDescription,
    DeviceFirmwareState,
    SourceOfDeviceCreation,
)
from aiohomematic.decorators import inspector
from aiohomematic.exceptions import AioHomematicException
from aiohomematic.interfaces.central import (
    CentralInfo,
    ConfigProvider,
    DataCacheProvider,
    DataPointProvider,
    EventBusProvider,
    EventPublisher,
    EventSubscriptionManager,
    FileOperations,
    FirmwareDataRefresher,
)
from aiohomematic.interfaces.client import ClientProvider, DeviceDiscoveryAndMetadata, DeviceDiscoveryWithIdentity
from aiohomematic.interfaces.coordinators import CoordinatorProvider
from aiohomematic.interfaces.model import (
    CallbackDataPointProtocol,
    ChannelProtocol,
    DeviceProtocol,
    GenericEventProtocol,
)
from aiohomematic.interfaces.operations import (
    DeviceDescriptionProvider,
    DeviceDetailsProvider,
    ParameterVisibilityProvider,
    ParamsetDescriptionProvider,
    TaskScheduler,
)
from aiohomematic.model import create_data_points_and_events
from aiohomematic.model.custom import create_custom_data_points
from aiohomematic.model.device import Device
from aiohomematic.support import extract_exc_args

if TYPE_CHECKING:
    from aiohomematic.central.device_registry import DeviceRegistry

_LOGGER: Final = logging.getLogger(__name__)


class DeviceCoordinator(FirmwareDataRefresher):
    """Coordinator for device lifecycle and operations."""

    __slots__ = (
        "_central_info",
        "_client_provider",
        "_config_provider",
        "_coordinator_provider",
        "_data_cache_provider",
        "_data_point_provider",
        "_delayed_device_descriptions",
        "_device_add_semaphore",
        "_device_description_provider",
        "_device_details_provider",
        "_event_bus_provider",
        "_event_publisher",
        "_event_subscription_manager",
        "_file_operations",
        "_parameter_visibility_provider",
        "_paramset_description_provider",
        "_task_scheduler",
    )

    def __init__(
        self,
        *,
        central_info: CentralInfo,
        client_provider: ClientProvider,
        config_provider: ConfigProvider,
        coordinator_provider: CoordinatorProvider,
        data_cache_provider: DataCacheProvider,
        data_point_provider: DataPointProvider,
        device_description_provider: DeviceDescriptionProvider,
        device_details_provider: DeviceDetailsProvider,
        event_bus_provider: EventBusProvider,
        event_publisher: EventPublisher,
        event_subscription_manager: EventSubscriptionManager,
        file_operations: FileOperations,
        parameter_visibility_provider: ParameterVisibilityProvider,
        paramset_description_provider: ParamsetDescriptionProvider,
        task_scheduler: TaskScheduler,
    ) -> None:
        """
        Initialize the device coordinator.

        Args:
        ----
            central_info: Provider for central system information
            client_provider: Provider for client access
            config_provider: Provider for configuration access
            coordinator_provider: Provider for accessing other coordinators
            data_cache_provider: Provider for data cache access
            data_point_provider: Provider for data point access
            device_description_provider: Provider for device descriptions
            device_details_provider: Provider for device details
            event_bus_provider: Provider for event bus access
            event_publisher: Provider for event publisher access
            event_subscription_manager: Manager for event subscriptions
            file_operations: Provider for file operations
            parameter_visibility_provider: Provider for parameter visibility rules
            paramset_description_provider: Provider for paramset descriptions
            task_scheduler: Scheduler for async tasks

        """
        self._central_info: Final = central_info
        self._client_provider = client_provider
        self._config_provider: Final = config_provider
        self._coordinator_provider: Final = coordinator_provider
        self._data_cache_provider = data_cache_provider
        self._data_point_provider = data_point_provider
        self._device_description_provider = device_description_provider
        self._device_details_provider = device_details_provider
        self._event_bus_provider = event_bus_provider
        self._event_publisher = event_publisher
        self._event_subscription_manager = event_subscription_manager
        self._file_operations = file_operations
        self._parameter_visibility_provider = parameter_visibility_provider
        self._paramset_description_provider = paramset_description_provider
        self._task_scheduler = task_scheduler
        self._delayed_device_descriptions: Final[dict[str, list[DeviceDescription]]] = defaultdict(list)
        self._device_add_semaphore: Final = asyncio.Semaphore()

    @property
    def device_registry(self) -> DeviceRegistry:
        """Return the device registry."""
        return self._coordinator_provider.device_registry

    @property
    def devices(self) -> tuple[DeviceProtocol, ...]:
        """Return all devices."""
        return self.device_registry.devices

    @callback_backend_system(system_event=BackendSystemEvent.NEW_DEVICES)
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

    async def add_new_devices_manually(self, *, interface_id: str, address_names: Mapping[str, str | None]) -> None:
        """
        Add new devices manually triggered to central unit.

        Args:
            interface_id: Interface identifier.
            address_names: Device addresses and their names.

        """
        if not self._coordinator_provider.client_coordinator.has_client(interface_id=interface_id):
            _LOGGER.error(  # i18n-log: ignore
                "ADD_NEW_DEVICES_MANUALLY failed: Missing client for interface_id %s",
                interface_id,
            )
            return

        client = self._coordinator_provider.client_coordinator.get_client(interface_id=interface_id)
        device_descriptions: list[DeviceDescription] = []
        for address, device_name in address_names.items():
            if not (dds := self._delayed_device_descriptions.pop(address, None)):
                _LOGGER.error(  # i18n-log: ignore
                    "ADD_NEW_DEVICES_MANUALLY failed: No device description found for address %s on interface_id %s",
                    address,
                    interface_id,
                )
                return
            device_descriptions.extend(dds)

            await client.accept_device_in_inbox(device_address=address)

            if device_name:
                await self._rename_new_device(
                    client=client,
                    device_descriptions=tuple(dds),
                    device_name=device_name,
                )

        await self._add_new_devices(
            interface_id=interface_id,
            device_descriptions=tuple(device_descriptions),
            source=SourceOfDeviceCreation.MANUAL,
        )

    def check_for_new_device_addresses(self, *, interface_id: str | None = None) -> Mapping[str, set[str]]:
        """
        Check if there are new devices that need to be created.

        Algorithm:
            This method identifies device addresses that exist in the cache
            (from device descriptions) but haven't been created as Device objects yet.

            1. Get all existing device addresses from device registry (O(1) lookup set)
            2. For each interface, get cached addresses from device descriptions
            3. Compute set difference: cached_addresses - existing_addresses
            4. Non-empty differences indicate devices that need creation

        Why use a helper function?
            The helper function allows the same logic to work for:
            - Single interface check (when interface_id is provided)
            - All interfaces check (when interface_id is None)
            This avoids code duplication while keeping the interface flexible.

        Performance note:
            Set difference (addresses - existing_addresses) is O(n) where n is the
            smaller set, making this efficient even for large device counts.

        Args:
        ----
            interface_id: Optional interface identifier to check

        Returns:
        -------
            Mapping of interface IDs to sets of new device addresses

        """
        new_device_addresses: dict[str, set[str]] = {}

        # Cache existing device addresses once - this set is used for all difference operations
        existing_addresses = self.device_registry.get_device_addresses()

        def _check_for_new_device_addresses_helper(*, iid: str) -> None:
            """
            Check a single interface for new devices.

            Encapsulates the per-interface logic to avoid duplication between
            single-interface and all-interfaces code paths.
            """
            # Skip interfaces without paramset descriptions (not fully initialized)
            if not self._coordinator_provider.cache_coordinator.paramset_descriptions.has_interface_id(
                interface_id=iid
            ):
                _LOGGER.debug(
                    "CHECK_FOR_NEW_DEVICE_ADDRESSES: Skipping interface %s, missing paramsets",
                    iid,
                )
                return

            # Convert to set once for efficient set difference operation
            addresses = set(
                self._coordinator_provider.cache_coordinator.device_descriptions.get_addresses(interface_id=iid)
            )

            # Set difference: addresses in cache but not yet created as Device objects
            if new_set := addresses - existing_addresses:
                new_device_addresses[iid] = new_set

        # Dispatch: single interface or all interfaces
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

        new_devices = set[DeviceProtocol]()

        for interface_id, device_addresses in new_device_addresses.items():
            for device_address in device_addresses:
                # Do we check for duplicates here? For now, we do.
                if self.device_registry.has_device(address=device_address):
                    continue
                device: DeviceProtocol | None = None
                try:
                    device = Device(
                        interface_id=interface_id,
                        device_address=device_address,
                        central_info=self._central_info,
                        channel_lookup=self,
                        client_provider=self._client_provider,
                        config_provider=self._config_provider,
                        data_cache_provider=self._data_cache_provider,
                        data_point_provider=self._data_point_provider,
                        device_data_refresher=self,
                        device_description_provider=self._device_description_provider,
                        device_details_provider=self._device_details_provider,
                        event_bus_provider=self._event_bus_provider,
                        event_publisher=self._event_publisher,
                        event_subscription_manager=self._event_subscription_manager,
                        file_operations=self._file_operations,
                        parameter_visibility_provider=self._parameter_visibility_provider,
                        paramset_description_provider=self._paramset_description_provider,
                        task_scheduler=self._task_scheduler,
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
                        await self.device_registry.add_device(device=device)
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
            self._coordinator_provider.event_coordinator.publish_backend_system_event(
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

    @callback_backend_system(system_event=BackendSystemEvent.DELETE_DEVICES)
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
                await self.remove_device(device=device)

        await self._coordinator_provider.cache_coordinator.save_all(
            save_device_descriptions=True,
            save_paramset_descriptions=True,
        )

    def get_channel(self, *, channel_address: str) -> ChannelProtocol | None:
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

    def get_device(self, *, address: str) -> DeviceProtocol | None:
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

    def get_virtual_remotes(self) -> tuple[DeviceProtocol, ...]:
        """Get the virtual remotes for all clients."""
        return self.device_registry.get_virtual_remotes()

    def identify_channel(self, *, text: str) -> ChannelProtocol | None:
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

    @callback_backend_system(system_event=BackendSystemEvent.LIST_DEVICES)
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
        return result

    async def refresh_device_descriptions_and_create_missing_devices(
        self, *, client: DeviceDiscoveryWithIdentity, refresh_only_existing: bool, device_address: str | None = None
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
            and (device_description := await client.get_device_description(address=device_address)) is not None
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

    @inspector(re_raise=False)
    async def refresh_firmware_data_by_state(self, *, device_firmware_states: tuple[DeviceFirmwareState, ...]) -> None:
        """Refresh firmware by state (internal use - use device_coordinator for external access)."""
        for device in [
            device_in_state
            for device_in_state in self.devices
            if device_in_state.firmware_update_state in device_firmware_states
        ]:
            await self.refresh_firmware_data(device_address=device.address)

    @inspector
    async def remove_central_links(self) -> None:
        """Remove central links."""
        for device in self.devices:
            await device.remove_central_links()

    async def remove_device(self, *, device: DeviceProtocol) -> None:
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
        await self.device_registry.remove_device(device_address=device.address)

    @inspector(measure_performance=True)
    async def _add_new_devices(
        self, *, interface_id: str, device_descriptions: tuple[DeviceDescription, ...], source: SourceOfDeviceCreation
    ) -> None:
        """
        Add new devices to central unit.

        Device creation pipeline:
            This is a multi-step orchestration process:

            1. Validation: Skip if no descriptions or client missing
            2. Semaphore: Acquire lock to prevent concurrent device creation
            3. Filtering: Identify truly new devices (not already known)
            4. Delay check: Optionally defer creation for user confirmation
            5. Cache population:
               - Add device descriptions to cache
               - Fetch paramset descriptions from backend
            6. Persistence: Save updated caches to disk
            7. Device creation: Create Device objects from cached descriptions

        Semaphore pattern:
            The _device_add_semaphore ensures only one device addition operation
            runs at a time. This prevents race conditions when multiple interfaces
            report new devices simultaneously.

        Delayed device creation:
            When delay_new_device_creation is enabled, newly discovered devices
            are stored in _delayed_device_descriptions instead of being created.
            This allows the user to review and approve new devices before they
            appear in Home Assistant.

        Args:
        ----
            interface_id: Interface identifier
            device_descriptions: Tuple of device descriptions
            source: Source of device creation (STARTUP, NEW, MANUAL)

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
            new_device_descriptions = self._identify_new_device_descriptions(
                device_descriptions=device_descriptions, interface_id=interface_id
            )

            # For REFRESH operations, we need to update the cache even for existing devices
            # (e.g., firmware data may have changed)
            descriptions_to_cache = (
                device_descriptions if source == SourceOfDeviceCreation.REFRESH else new_device_descriptions
            )

            if not descriptions_to_cache:
                _LOGGER.debug("ADD_NEW_DEVICES: Nothing to add/update for interface_id %s", interface_id)
                return

            # Here we block the automatic creation of new devices, if required
            if self._config_provider.config.delay_new_device_creation and source == SourceOfDeviceCreation.NEW:
                self._store_delayed_device_descriptions(device_descriptions=new_device_descriptions)
                self._coordinator_provider.event_coordinator.publish_backend_system_event(
                    system_event=BackendSystemEvent.DEVICES_DELAYED,
                    new_addresses=tuple(self._delayed_device_descriptions.keys()),
                    interface_id=interface_id,
                    source=source,
                )
                return

            client = self._coordinator_provider.client_coordinator.get_client(interface_id=interface_id)
            save_descriptions = False
            for dev_desc in descriptions_to_cache:
                try:
                    self._coordinator_provider.cache_coordinator.device_descriptions.add_device(
                        interface_id=interface_id, device_description=dev_desc
                    )
                    # Only fetch paramset descriptions for new devices (not needed for refresh)
                    if source != SourceOfDeviceCreation.REFRESH or dev_desc in new_device_descriptions:
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

        Address resolution with PARENT fallback:
            Device descriptions come in two forms:
            - Device entries: ADDRESS is the device address, PARENT is empty/missing
            - Channel entries: ADDRESS is channel address (e.g., "ABC:1"), PARENT is device address

            When checking if a device is new, we need to check the device address,
            not the channel address. The expression:
                dev_desc["ADDRESS"] if not parent_address else parent_address
            Handles both cases:
            - For device entries: Use ADDRESS (PARENT is empty)
            - For channel entries: Use PARENT (the actual device address)

            This ensures we don't treat the same device as "new" multiple times
            when we receive descriptions for both the device and its channels.

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
            # Use PARENT if present (channel entry), else ADDRESS (device entry)
            if (dev_desc["ADDRESS"] if not (parent_address := dev_desc.get("PARENT")) else parent_address)
            not in known_addresses
        )

    async def _rename_new_device(
        self,
        *,
        client: DeviceDiscoveryAndMetadata,
        device_descriptions: tuple[DeviceDescription, ...],
        device_name: str,
    ) -> None:
        """
        Rename a new device and its channels before adding to the system.

        Args:
            client: The client to use for renaming.
            device_descriptions: Tuple of device descriptions (device + channels).
            device_name: The new name for the device.

        """
        await client.fetch_device_details()
        for device_desc in device_descriptions:
            address = device_desc["ADDRESS"]
            parent = device_desc.get("PARENT")

            if (rega_id := await client.get_rega_id_by_address(address=address)) is None:
                _LOGGER.warning(  # i18n-log: ignore
                    "RENAME_NEW_DEVICE: Could not get rega_id for address %s",
                    address,
                )
                continue

            if not parent:
                # This is the device itself
                await client.rename_device(rega_id=rega_id, new_name=device_name)
            elif (channel_no := address.split(":")[-1] if ":" in address else None) is not None:
                # This is a channel - extract channel number from address
                channel_name = f"{device_name}:{channel_no}"
                await client.rename_channel(rega_id=rega_id, new_name=channel_name)

            await asyncio.sleep(0.1)

    def _store_delayed_device_descriptions(self, *, device_descriptions: tuple[DeviceDescription, ...]) -> None:
        """Store device descriptions for delayed creation."""
        for dev_desc in device_descriptions:
            device_address = dev_desc["PARENT"] or dev_desc["ADDRESS"]
            self._delayed_device_descriptions[device_address].append(dev_desc)


def _get_new_channel_events(*, new_devices: set[DeviceProtocol]) -> tuple[tuple[GenericEventProtocol, ...], ...]:
    """
    Return new channel events.

    Args:
    ----
        new_devices: Set of new devices

    Returns:
    -------
        Tuple of channel event tuples

    """
    channel_events: list[tuple[GenericEventProtocol, ...]] = []

    for device in new_devices:
        for event_type in DATA_POINT_EVENTS:
            if (hm_channel_events := list(device.get_events(event_type=event_type, registered=False).values())) and len(
                hm_channel_events
            ) > 0:
                channel_events.append(hm_channel_events)  # type: ignore[arg-type] # noqa: PERF401

    return tuple(channel_events)


def _get_new_data_points(
    *,
    new_devices: set[DeviceProtocol],
) -> Mapping[DataPointCategory, AbstractSet[CallbackDataPointProtocol]]:
    """
    Return new data points by category.

    Args:
    ----
        new_devices: Set of new devices

    Returns:
    -------
        Mapping of categories to data points

    """
    data_points_by_category: dict[DataPointCategory, set[CallbackDataPointProtocol]] = {
        category: set() for category in CATEGORIES if category != DataPointCategory.EVENT
    }

    for device in new_devices:
        for category, data_points in data_points_by_category.items():
            data_points.update(device.get_data_points(category=category, exclude_no_create=True, registered=False))

    return data_points_by_category
