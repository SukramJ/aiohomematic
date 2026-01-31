# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
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
from collections.abc import Mapping
from datetime import datetime
import logging
from typing import TYPE_CHECKING, Any, Final

from aiohomematic import i18n
from aiohomematic.central.decorators import callback_backend_system
from aiohomematic.central.events import (
    DataFetchCompletedEvent,
    DataFetchOperation,
    DeviceRemovedEvent,
    IntegrationIssue,
    SystemStatusChangedEvent,
)
from aiohomematic.const import (
    CATEGORIES,
    DataPointCategory,
    DeviceDescription,
    DeviceFirmwareState,
    IntegrationIssueSeverity,
    IntegrationIssueType,
    ParamsetKey,
    SourceOfDeviceCreation,
    SystemEventType,
)
from aiohomematic.decorators import inspector
from aiohomematic.exceptions import AioHomematicException
from aiohomematic.interfaces import (
    CallbackDataPointProtocol,
    CentralInfoProtocol,
    ChannelEventGroupProtocol,
    ChannelProtocol,
    ClientProviderProtocol,
    ConfigProviderProtocol,
    CoordinatorProviderProtocol,
    DataCacheProviderProtocol,
    DataPointProviderProtocol,
    DeviceDescriptionProviderProtocol,
    DeviceDetailsProviderProtocol,
    DeviceProtocol,
    EventBusProviderProtocol,
    EventPublisherProtocol,
    EventSubscriptionManagerProtocol,
    FileOperationsProtocol,
    ParameterVisibilityProviderProtocol,
    ParamsetDescriptionProviderProtocol,
    TaskSchedulerProtocol,
)
from aiohomematic.interfaces.central import FirmwareDataRefresherProtocol
from aiohomematic.interfaces.client import DeviceDiscoveryAndMetadataProtocol, DeviceDiscoveryWithIdentityProtocol
from aiohomematic.model import create_data_points_and_events
from aiohomematic.model.custom import create_custom_data_points
from aiohomematic.model.device import Device
from aiohomematic.model.device_context import DeviceContext
from aiohomematic.property_decorators import DelegatedProperty
from aiohomematic.support import extract_exc_args

if TYPE_CHECKING:
    from aiohomematic.central import DeviceRegistry  # noqa: F401

_LOGGER: Final = logging.getLogger(__name__)


class DeviceCoordinator(FirmwareDataRefresherProtocol):
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
        central_info: CentralInfoProtocol,
        client_provider: ClientProviderProtocol,
        config_provider: ConfigProviderProtocol,
        coordinator_provider: CoordinatorProviderProtocol,
        data_cache_provider: DataCacheProviderProtocol,
        data_point_provider: DataPointProviderProtocol,
        device_description_provider: DeviceDescriptionProviderProtocol,
        device_details_provider: DeviceDetailsProviderProtocol,
        event_bus_provider: EventBusProviderProtocol,
        event_publisher: EventPublisherProtocol,
        event_subscription_manager: EventSubscriptionManagerProtocol,
        file_operations: FileOperationsProtocol,
        parameter_visibility_provider: ParameterVisibilityProviderProtocol,
        paramset_description_provider: ParamsetDescriptionProviderProtocol,
        task_scheduler: TaskSchedulerProtocol,
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
        self._client_provider: Final = client_provider
        self._config_provider: Final = config_provider
        self._coordinator_provider: Final = coordinator_provider
        self._data_cache_provider: Final = data_cache_provider
        self._data_point_provider: Final = data_point_provider
        self._device_description_provider: Final = device_description_provider
        self._device_details_provider: Final = device_details_provider
        self._event_bus_provider: Final = event_bus_provider
        self._event_publisher: Final = event_publisher
        self._event_subscription_manager: Final = event_subscription_manager
        self._file_operations: Final = file_operations
        self._parameter_visibility_provider: Final = parameter_visibility_provider
        self._paramset_description_provider: Final = paramset_description_provider
        self._task_scheduler: Final = task_scheduler
        self._delayed_device_descriptions: Final[dict[str, list[DeviceDescription]]] = defaultdict(list)
        self._device_add_semaphore: Final = asyncio.Semaphore()

    device_registry: Final = DelegatedProperty["DeviceRegistry"](path="_coordinator_provider.device_registry")

    @property
    def devices(self) -> tuple[DeviceProtocol, ...]:
        """Return all devices."""
        return self.device_registry.devices

    @callback_backend_system(system_event=SystemEventType.NEW_DEVICES)
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

    async def check_and_create_devices_from_cache(self) -> None:
        """
        Check for new devices in cache and create them atomically.

        Race condition prevention:
            This method acquires the device_add_semaphore to ensure it doesn't
            race with _add_new_devices() which is populating the cache from
            newDevices callbacks. Without this synchronization, the startup
            code could try to create devices while descriptions are still
            being added, resulting in devices with missing channels.

        """
        async with self._device_add_semaphore:
            if new_device_addresses := self.check_for_new_device_addresses():
                await self.create_devices(
                    new_device_addresses=new_device_addresses,
                    source=SourceOfDeviceCreation.CACHE,
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
                    key="exception.central.create_devices.no_clients",
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
                    context = DeviceContext(
                        interface_id=interface_id,
                        device_address=device_address,
                        central_info=self._central_info,
                        config_provider=self._config_provider,
                        file_operations=self._file_operations,
                        device_data_refresher=self,
                        device_description_provider=self._device_description_provider,
                        device_details_provider=self._device_details_provider,
                        paramset_description_provider=self._paramset_description_provider,
                        parameter_visibility_provider=self._parameter_visibility_provider,
                        event_bus_provider=self._event_bus_provider,
                        event_publisher=self._event_publisher,
                        event_subscription_manager=self._event_subscription_manager,
                        task_scheduler=self._task_scheduler,
                        client_provider=self._client_provider,
                        data_cache_provider=self._data_cache_provider,
                        data_point_provider=self._data_point_provider,
                        channel_lookup=self,
                    )
                    device = Device(context=context)
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
            new_dps: dict[DataPointCategory, Any] = _get_new_data_points(new_devices=new_devices)
            new_dps[DataPointCategory.EVENT_GROUP] = _get_new_event_groups(new_devices=new_devices)
            self._coordinator_provider.event_coordinator.publish_system_event(
                system_event=SystemEventType.DEVICES_CREATED,
                new_data_points=new_dps,
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

    @callback_backend_system(system_event=SystemEventType.DELETE_DEVICES)
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

    @callback_backend_system(system_event=SystemEventType.LIST_DEVICES)
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

    @callback_backend_system(system_event=SystemEventType.RE_ADDED_DEVICE)
    async def readd_device(self, *, interface_id: str, device_addresses: tuple[str, ...]) -> None:
        """
        Handle re-added device after re-pairing in learn mode.

        This method is called when the CCU sends a readdedDevice callback, which
        occurs when a known device is put into learn-mode while installation mode
        is active (re-pairing). The device parameters may have changed, so we
        refresh the device data.

        Args:
        ----
            interface_id: Interface identifier
            device_addresses: Addresses of the re-added devices

        """
        _LOGGER.debug(
            "READD_DEVICE: interface_id = %s, device_addresses = %s",
            interface_id,
            str(device_addresses),
        )

        if not self._coordinator_provider.client_coordinator.has_client(interface_id=interface_id):
            _LOGGER.error(  # i18n-log: ignore
                "READD_DEVICE failed: Missing client for interface_id %s",
                interface_id,
            )
            return

        client = self._coordinator_provider.client_coordinator.get_client(interface_id=interface_id)

        for device_address in device_addresses:
            # Get existing device
            if device := self.device_registry.get_device(address=device_address):
                # Remove from caches to force refresh
                self._coordinator_provider.cache_coordinator.device_descriptions.remove_device(device=device)
                self._coordinator_provider.cache_coordinator.paramset_descriptions.remove_device(device=device)
                await self.remove_device(device=device)

            # Fetch fresh device descriptions and recreate
            await self.refresh_device_descriptions_and_create_missing_devices(
                client=client, refresh_only_existing=False, device_address=device_address
            )

        # Save updated caches
        await self._coordinator_provider.cache_coordinator.save_all(
            save_device_descriptions=True,
            save_paramset_descriptions=True,
        )

    async def refresh_device_descriptions_and_create_missing_devices(
        self,
        *,
        client: DeviceDiscoveryWithIdentityProtocol,
        refresh_only_existing: bool,
        device_address: str | None = None,
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

    async def refresh_device_link_peers(self, *, device_address: str) -> None:
        """
        Refresh link peer information for a device after link partner change.

        This method is called when the CCU sends an updateDevice callback with
        hint=1 (link partner change). It refreshes the link peer addresses for
        all channels of the device.

        Args:
        ----
            device_address: Device address to refresh link peers for

        """
        _LOGGER.debug(
            "REFRESH_DEVICE_LINK_PEERS: device_address = %s",
            device_address,
        )

        if (device := self.device_registry.get_device(address=device_address)) is None:
            _LOGGER.debug(
                "REFRESH_DEVICE_LINK_PEERS: Device %s not found in registry",
                device_address,
            )
            return

        # Refresh link peers for all channels
        for channel in device.channels.values():
            await channel.init_link_peer()

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

        Emits DeviceRemovedEvent to trigger decoupled cache invalidation.

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

        # Capture data before removal for event emission
        device_address = device.address
        interface_id = device.interface_id
        channel_addresses = tuple(device.channels.keys())
        identifier = device.identifier

        device.remove()

        # Emit event for decoupled cache invalidation
        await self._event_bus_provider.event_bus.publish(
            event=DeviceRemovedEvent(
                timestamp=datetime.now(),
                unique_id=identifier,
                device_address=device_address,
                interface_id=interface_id,
                channel_addresses=channel_addresses,
            )
        )

        await self.device_registry.remove_device(device_address=device_address)

    @callback_backend_system(system_event=SystemEventType.REPLACE_DEVICE)
    async def replace_device(self, *, interface_id: str, old_device_address: str, new_device_address: str) -> None:
        """
        Replace an old device with a new device after CCU device replacement.

        This method is called when the CCU sends a replaceDevice callback, which
        occurs when a user replaces a broken device with a new one using the CCU's
        "Replace device" function. The CCU transfers configuration from the old
        device to the new one.

        Args:
        ----
            interface_id: Interface identifier
            old_device_address: Address of the device being replaced
            new_device_address: Address of the replacement device

        """
        _LOGGER.debug(
            "REPLACE_DEVICE: interface_id = %s, old_device_address = %s, new_device_address = %s",
            interface_id,
            old_device_address,
            new_device_address,
        )

        if not self._coordinator_provider.client_coordinator.has_client(interface_id=interface_id):
            _LOGGER.error(  # i18n-log: ignore
                "REPLACE_DEVICE failed: Missing client for interface_id %s",
                interface_id,
            )
            return

        # Remove old device from registry and caches
        if old_device := self.device_registry.get_device(address=old_device_address):
            self._coordinator_provider.cache_coordinator.device_descriptions.remove_device(device=old_device)
            self._coordinator_provider.cache_coordinator.paramset_descriptions.remove_device(device=old_device)
            await self.remove_device(device=old_device)

        # Fetch and create new device
        client = self._coordinator_provider.client_coordinator.get_client(interface_id=interface_id)
        await self.refresh_device_descriptions_and_create_missing_devices(
            client=client, refresh_only_existing=False, device_address=new_device_address
        )

        # Save updated caches
        await self._coordinator_provider.cache_coordinator.save_all(
            save_device_descriptions=True,
            save_paramset_descriptions=True,
        )

    @callback_backend_system(system_event=SystemEventType.UPDATE_DEVICE)
    async def update_device(self, *, interface_id: str, device_address: str) -> None:
        """
        Update device after firmware update by invalidating cache and reloading.

        This method is called when the CCU sends an updateDevice callback with
        hint=0 (firmware update). It invalidates the cached device and paramset
        descriptions, fetches fresh data from the backend, and recreates the
        Device object.

        Args:
        ----
            interface_id: Interface identifier
            device_address: Device address to update

        """
        _LOGGER.debug(
            "UPDATE_DEVICE: interface_id = %s, device_address = %s",
            interface_id,
            device_address,
        )

        if not self._coordinator_provider.client_coordinator.has_client(interface_id=interface_id):
            _LOGGER.error(  # i18n-log: ignore
                "UPDATE_DEVICE failed: Missing client for interface_id %s",
                interface_id,
            )
            return

        # Get existing device to collect all channel addresses for cache invalidation
        if device := self.device_registry.get_device(address=device_address):
            # Remove device from caches using the device's channel information
            self._coordinator_provider.cache_coordinator.device_descriptions.remove_device(device=device)
            self._coordinator_provider.cache_coordinator.paramset_descriptions.remove_device(device=device)
            # Remove the Device object from registry
            await self.remove_device(device=device)

        # Fetch fresh device descriptions from backend
        client = self._coordinator_provider.client_coordinator.get_client(interface_id=interface_id)
        await self.refresh_device_descriptions_and_create_missing_devices(
            client=client, refresh_only_existing=False, device_address=device_address
        )

        # Save updated caches
        await self._coordinator_provider.cache_coordinator.save_all(
            save_device_descriptions=True,
            save_paramset_descriptions=True,
        )

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
                # Check if there are devices with missing paramset descriptions
                # This can happen when device_descriptions were cached but paramsets weren't
                # (e.g., previous run was interrupted after saving device_descriptions)
                devices_missing_paramsets = self._identify_devices_missing_paramsets(
                    interface_id=interface_id, device_descriptions=device_descriptions
                )
                if not devices_missing_paramsets:
                    _LOGGER.debug("ADD_NEW_DEVICES: Nothing to add/update for interface_id %s", interface_id)
                    return

                # Fetch missing paramset descriptions
                _LOGGER.debug(
                    "ADD_NEW_DEVICES: Fetching missing paramsets for %s device/channel descriptions on interface_id %s",
                    len(devices_missing_paramsets),
                    interface_id,
                )
                client = self._coordinator_provider.client_coordinator.get_client(interface_id=interface_id)
                for dev_desc in devices_missing_paramsets:
                    # Ensure interface is registered for device address (may be missing from older caches)
                    self._coordinator_provider.cache_coordinator.device_details.add_interface(
                        address=dev_desc["ADDRESS"], interface=client.interface
                    )
                    await client.fetch_paramset_descriptions(device_description=dev_desc)

                # Emit event ONCE after batch to trigger automatic cache persistence
                await self._event_bus_provider.event_bus.publish(
                    event=DataFetchCompletedEvent(
                        timestamp=datetime.now(),
                        interface_id=interface_id,
                        operation=DataFetchOperation.FETCH_PARAMSET_DESCRIPTIONS,
                    )
                )

                # CRITICAL: Verify all paramsets are now in cache before proceeding
                # This ensures device creation only starts with complete paramset data
                still_missing = self._identify_devices_missing_paramsets(
                    device_descriptions=devices_missing_paramsets,
                    interface_id=interface_id,
                )
                if still_missing:
                    _LOGGER.warning(  # i18n-log: ignore
                        "ADD_NEW_DEVICES: %d device/channel addresses still missing paramsets after fetch on interface_id %s - aborting device creation",
                        len(still_missing),
                        interface_id,
                    )
                    # Persist what we have fetched so far
                    await self._coordinator_provider.cache_coordinator.save_if_changed(save_paramset_descriptions=True)

                    # Publish integration issue for Home Assistant repair
                    issue = IntegrationIssue(
                        issue_type=IntegrationIssueType.INCOMPLETE_DEVICE_DATA,
                        severity=IntegrationIssueSeverity.ERROR,
                        interface_id=interface_id,
                        device_addresses=tuple(desc["ADDRESS"] for desc in still_missing),
                    )
                    await self._event_bus_provider.event_bus.publish(
                        event=SystemStatusChangedEvent(timestamp=datetime.now(), issues=(issue,))
                    )

                    return

                # All paramsets fetched successfully - persist before device creation
                # (Event-based auto-save should have already handled this, but we ensure it's complete)
                await self._coordinator_provider.cache_coordinator.save_if_changed(save_paramset_descriptions=True)

                # Now safe to create devices - all paramsets are guaranteed to be in cache
                if new_device_addresses := self.check_for_new_device_addresses(interface_id=interface_id):
                    await self._coordinator_provider.cache_coordinator.device_details.load()
                    await self._coordinator_provider.cache_coordinator.load_data_cache(interface=client.interface)
                    await self.create_devices(new_device_addresses=new_device_addresses, source=source)
                return

            # Here we block the automatic creation of new devices, if required
            if self._config_provider.config.delay_new_device_creation and source == SourceOfDeviceCreation.NEW:
                self._store_delayed_device_descriptions(device_descriptions=new_device_descriptions)
                self._coordinator_provider.event_coordinator.publish_system_event(
                    system_event=SystemEventType.DEVICES_DELAYED,
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
                    # Register interface for device address so Device.interface is correct.
                    # This is critical for JSON-RPC-only backends (CUxD, CCU-Jack) where
                    # fetch_device_details() returns None and interface would default to BIDCOS_RF.
                    self._coordinator_provider.cache_coordinator.device_details.add_interface(
                        address=dev_desc["ADDRESS"], interface=client.interface
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

            # Emit event ONCE after batch to trigger automatic cache persistence
            if save_descriptions:
                await self._event_bus_provider.event_bus.publish(
                    event=DataFetchCompletedEvent(
                        timestamp=datetime.now(),
                        interface_id=interface_id,
                        operation=DataFetchOperation.FETCH_PARAMSET_DESCRIPTIONS,
                    )
                )

            await self._coordinator_provider.cache_coordinator.save_all(
                save_device_descriptions=save_descriptions,
                save_paramset_descriptions=save_descriptions,
            )

            # Device creation MUST be inside semaphore to prevent race condition:
            # Without this, startup code can call check_for_new_device_addresses()
            # while callback is still adding descriptions, causing incomplete devices.
            if new_device_addresses := self.check_for_new_device_addresses(interface_id=interface_id):
                await self._coordinator_provider.cache_coordinator.device_details.load()
                await self._coordinator_provider.cache_coordinator.load_data_cache(interface=client.interface)
                await self.create_devices(new_device_addresses=new_device_addresses, source=source)

    def _identify_devices_missing_paramsets(
        self, *, interface_id: str, device_descriptions: tuple[DeviceDescription, ...]
    ) -> tuple[DeviceDescription, ...]:
        """
        Identify devices that have device_descriptions but missing paramset_descriptions.

        This handles the case where device_descriptions were persisted but paramset_descriptions
        weren't (e.g., previous run was interrupted, or paramset fetch failed).

        Synchronization check:
            For each device_description, we verify that ALL expected paramsets (from the
            PARAMSETS field) are present in the paramset_descriptions cache. This ensures
            both caches are synchronized - not just that "some" paramset exists.

        Args:
        ----
            interface_id: Interface identifier
            device_descriptions: Tuple of device descriptions to check

        Returns:
        -------
            Tuple of device descriptions that need paramset fetching

        """
        paramset_cache = self._coordinator_provider.cache_coordinator.paramset_descriptions
        missing: list[DeviceDescription] = []

        for dev_desc in device_descriptions:
            address = dev_desc["ADDRESS"]

            # Skip if no paramsets expected (shouldn't happen, but be safe)
            if not (expected_paramsets := dev_desc.get("PARAMSETS", [])):
                continue

            # Get cached paramsets for this address
            cached_paramsets = paramset_cache.get_channel_paramset_descriptions(
                interface_id=interface_id, channel_address=address
            )

            # Check if required paramsets are present in cache
            # LINK paramsets are excluded because:
            # - They only exist when device linking is configured
            # - They are fetched dynamically when links are created
            # - They are not required for device creation
            cached_keys = set(cached_paramsets.keys())
            expected_keys = {ParamsetKey(p) for p in expected_paramsets} - {ParamsetKey.LINK}

            if not expected_keys.issubset(cached_keys):
                missing_keys = expected_keys - cached_keys
                _LOGGER.debug(
                    "ADD_NEW_DEVICES: Device %s on interface %s is missing paramsets: %s (expected: %s, cached: %s)",
                    address,
                    interface_id,
                    sorted(str(k) for k in missing_keys),
                    sorted(str(k) for k in expected_keys),
                    sorted(str(k) for k in cached_keys),
                )
                missing.append(dev_desc)

        return tuple(missing)

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
            if (parent_address if (parent_address := dev_desc.get("PARENT")) else dev_desc["ADDRESS"])
            not in known_addresses
        )

    async def _rename_new_device(
        self,
        *,
        client: DeviceDiscoveryAndMetadataProtocol,
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
            device_address = dev_desc.get("PARENT") or dev_desc["ADDRESS"]
            self._delayed_device_descriptions[device_address].append(dev_desc)


def _get_new_event_groups(*, new_devices: set[DeviceProtocol]) -> tuple[ChannelEventGroupProtocol, ...]:
    """
    Return new channel event groups.

    Args:
    ----
        new_devices: Set of new devices

    Returns:
    -------
        Tuple of channel event groups

    """
    return tuple(
        event_group
        for device in new_devices
        for channel in device.channels.values()
        for event_group in channel.event_groups.values()
        if not event_group.is_registered
    )


def _get_new_data_points(
    *,
    new_devices: set[DeviceProtocol],
) -> dict[DataPointCategory, set[CallbackDataPointProtocol]]:
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
        category: set()
        for category in CATEGORIES
        if category not in (DataPointCategory.EVENT, DataPointCategory.EVENT_GROUP)
    }

    for device in new_devices:
        for category, data_points in data_points_by_category.items():
            data_points.update(device.get_data_points(category=category, exclude_no_create=True, registered=False))

    return data_points_by_category
