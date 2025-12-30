# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Cache coordinator for managing all cache operations.

This module provides centralized cache management for device descriptions,
paramset descriptions, device details, data cache, and session recording.

The CacheCoordinator provides:
- Unified cache loading and saving
- Cache clearing operations
- Device-specific cache management
- Session recording coordination
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Final

from aiohomematic.central.event_bus import CacheInvalidatedEvent, DeviceRemovedEvent
from aiohomematic.const import CacheInvalidationReason, CacheType, DataOperationResult, Interface
from aiohomematic.interfaces import (
    CentralInfoProtocol,
    ClientProviderProtocol,
    ConfigProviderProtocol,
    DataPointProviderProtocol,
    DeviceProviderProtocol,
    EventBusProviderProtocol,
    PrimaryClientProviderProtocol,
    SessionRecorderProviderProtocol,
    TaskSchedulerProtocol,
)
from aiohomematic.interfaces.model import DeviceRemovalInfoProtocol
from aiohomematic.property_decorators import DelegatedProperty
from aiohomematic.store import (
    CentralDataCache,
    DeviceDescriptionCache,
    DeviceDetailsCache,
    ParameterVisibilityCache,
    ParamsetDescriptionCache,
    SessionRecorder,
)

_LOGGER: Final = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class _DeviceRemovalAdapter:
    """
    Adapter to satisfy DeviceRemovalInfoProtocol from event data.

    This lightweight adapter allows cache removal methods to work with
    data extracted from DeviceRemovedEvent without requiring a full Device object.
    """

    address: str
    """Device address."""

    interface_id: str
    """Interface ID."""

    channel_addresses: tuple[str, ...]
    """Channel addresses."""

    @property
    def channels(self) -> Mapping[str, None]:
        """Return channel addresses as a mapping (keys only used)."""
        return dict.fromkeys(self.channel_addresses)


class CacheCoordinator(SessionRecorderProviderProtocol):
    """Coordinator for all cache operations in the central unit."""

    __slots__ = (
        "_central_info",
        "_data_cache",
        "_device_descriptions_cache",
        "_device_details_cache",
        "_event_bus_provider",
        "_parameter_visibility_cache",
        "_paramset_descriptions_cache",
        "_session_recorder",
        "_unsubscribers",
    )

    def __init__(
        self,
        *,
        central_info: CentralInfoProtocol,
        client_provider: ClientProviderProtocol,
        config_provider: ConfigProviderProtocol,
        data_point_provider: DataPointProviderProtocol,
        device_provider: DeviceProviderProtocol,
        event_bus_provider: EventBusProviderProtocol,
        primary_client_provider: PrimaryClientProviderProtocol,
        session_recorder_active: bool,
        task_scheduler: TaskSchedulerProtocol,
    ) -> None:
        """
        Initialize the cache coordinator.

        Args:
        ----
            central_info: Provider for central system information
            device_provider: Provider for device access
            client_provider: Provider for client access
            data_point_provider: Provider for data point access
            event_bus_provider: Provider for event bus access
            primary_client_provider: Provider for primary client access
            config_provider: Provider for configuration access
            task_scheduler: Provider for task scheduling
            session_recorder_active: Whether session recording should be active

        """
        self._central_info: Final = central_info
        self._event_bus_provider: Final = event_bus_provider

        # Initialize all caches with protocol interfaces
        self._data_cache: Final = CentralDataCache(
            device_provider=device_provider,
            client_provider=client_provider,
            data_point_provider=data_point_provider,
            central_info=central_info,
            event_bus_provider=event_bus_provider,
        )
        self._device_details_cache: Final = DeviceDetailsCache(
            central_info=central_info,
            primary_client_provider=primary_client_provider,
        )
        self._device_descriptions_cache: Final = DeviceDescriptionCache(
            central_info=central_info,
            config_provider=config_provider,
            device_provider=device_provider,
            task_scheduler=task_scheduler,
        )
        self._paramset_descriptions_cache: Final = ParamsetDescriptionCache(
            central_info=central_info,
            config_provider=config_provider,
            device_provider=device_provider,
            task_scheduler=task_scheduler,
        )
        self._parameter_visibility_cache: Final = ParameterVisibilityCache(
            config_provider=config_provider,
        )
        self._session_recorder: Final = SessionRecorder(
            central_info=central_info,
            config_provider=config_provider,
            device_provider=device_provider,
            task_scheduler=task_scheduler,
            ttl_seconds=600,
            active=session_recorder_active,
        )

        # Subscribe to device removal events for decoupled cache invalidation
        self._unsubscribers: list[Callable[[], None]] = []
        self._unsubscribers.append(
            event_bus_provider.event_bus.subscribe(
                event_type=DeviceRemovedEvent,
                event_key=None,
                handler=self._on_device_removed,
            )
        )

    data_cache: Final = DelegatedProperty[CentralDataCache](path="_data_cache")
    device_descriptions: Final = DelegatedProperty[DeviceDescriptionCache](path="_device_descriptions_cache")
    device_details: Final = DelegatedProperty[DeviceDetailsCache](path="_device_details_cache")
    parameter_visibility: Final = DelegatedProperty[ParameterVisibilityCache](path="_parameter_visibility_cache")
    paramset_descriptions: Final = DelegatedProperty[ParamsetDescriptionCache](path="_paramset_descriptions_cache")
    recorder: Final = DelegatedProperty[SessionRecorder](path="_session_recorder")

    async def clear_all(
        self,
        *,
        reason: CacheInvalidationReason = CacheInvalidationReason.MANUAL,
    ) -> None:
        """
        Clear all caches and remove stored files.

        Args:
        ----
            reason: Reason for cache invalidation

        """
        _LOGGER.debug("CLEAR_ALL: Clearing all caches for %s", self._central_info.name)

        await self._device_descriptions_cache.clear()
        await self._paramset_descriptions_cache.clear()
        await self._session_recorder.clear()
        data_cache_size = self._data_cache.size
        self._device_details_cache.clear()
        self._data_cache.clear()

        # Emit single consolidated cache invalidation event
        await self._event_bus_provider.event_bus.publish(
            event=CacheInvalidatedEvent(
                timestamp=datetime.now(),
                cache_type=CacheType.DATA,  # Representative of full clear
                reason=reason,
                scope=None,  # Full cache clear
                entries_affected=data_cache_size,
            )
        )

    def clear_on_stop(self) -> None:
        """Clear in-memory caches on shutdown to free memory."""
        _LOGGER.debug("CLEAR_ON_STOP: Clearing in-memory caches for %s", self._central_info.name)
        data_cache_size = self._data_cache.size
        self._device_details_cache.clear()
        self._data_cache.clear()
        self._parameter_visibility_cache.clear_memoization_caches()

        # Emit cache invalidation event (sync publish)
        self._event_bus_provider.event_bus.publish_sync(
            event=CacheInvalidatedEvent(
                timestamp=datetime.now(),
                cache_type=CacheType.DATA,
                reason=CacheInvalidationReason.SHUTDOWN,
                scope=None,
                entries_affected=data_cache_size,
            )
        )

    async def load_all(self) -> bool:
        """
        Load all persistent caches from disk.

        Returns
        -------
            True if loading succeeded, False if any cache failed to load

        """
        _LOGGER.debug("LOAD_ALL: Loading caches for %s", self._central_info.name)

        if DataOperationResult.LOAD_FAIL in (
            await self._device_descriptions_cache.load(),
            await self._paramset_descriptions_cache.load(),
        ):
            _LOGGER.warning(  # i18n-log: ignore
                "LOAD_ALL failed: Unable to load caches for %s. Clearing files",
                self._central_info.name,
            )
            await self.clear_all()
            return False

        await self._device_details_cache.load()
        await self._data_cache.load()
        return True

    async def load_data_cache(self, *, interface: Interface | None = None) -> None:
        """
        Load data cache for a specific interface or all interfaces.

        Args:
        ----
            interface: Interface to load cache for, or None for all

        """
        await self._data_cache.load(interface=interface)

    def remove_device_from_caches(self, *, device: DeviceRemovalInfoProtocol) -> None:
        """
        Remove a device from all relevant caches.

        Note: This method is deprecated for direct calls. Prefer publishing
        DeviceRemovedEvent which triggers automatic cache invalidation.

        Args:
        ----
            device: Device to remove from caches

        """
        _LOGGER.debug(
            "REMOVE_DEVICE_FROM_CACHES: Removing device %s from caches",
            device.address,
        )
        self._device_descriptions_cache.remove_device(device=device)
        self._paramset_descriptions_cache.remove_device(device=device)
        self._device_details_cache.remove_device(device=device)

    async def save_all(
        self,
        *,
        save_device_descriptions: bool = False,
        save_paramset_descriptions: bool = False,
    ) -> None:
        """
        Save persistent caches to disk.

        Args:
        ----
            save_device_descriptions: Whether to save device descriptions
            save_paramset_descriptions: Whether to save paramset descriptions

        """
        _LOGGER.debug(
            "SAVE_ALL: Saving caches for %s (device_desc=%s, paramset_desc=%s)",
            self._central_info.name,
            save_device_descriptions,
            save_paramset_descriptions,
        )

        if save_device_descriptions:
            await self._device_descriptions_cache.save()
        if save_paramset_descriptions:
            await self._paramset_descriptions_cache.save()

    def stop(self) -> None:
        """Stop the coordinator and unsubscribe from events."""
        for unsub in self._unsubscribers:
            unsub()
        self._unsubscribers.clear()

    def _on_device_removed(self, *, event: DeviceRemovedEvent) -> None:
        """
        Handle DeviceRemovedEvent for decoupled cache invalidation.

        This handler is triggered when a device is removed, allowing caches
        to react independently without direct coupling to the device coordinator.

        Only processes device-level removal events (where device_address is set).
        Data point removal events (only unique_id set) are ignored.

        Args:
        ----
            event: The device removed event

        """
        # Only process device-level removal events
        if event.device_address is None or event.interface_id is None:
            return

        _LOGGER.debug(
            "CACHE_COORDINATOR: Received DeviceRemovedEvent for %s, invalidating caches",
            event.device_address,
        )
        # Create adapter for cache removal methods
        removal_info = _DeviceRemovalAdapter(
            address=event.device_address,
            interface_id=event.interface_id,
            channel_addresses=event.channel_addresses,
        )
        self._device_descriptions_cache.remove_device(device=removal_info)  # type: ignore[arg-type]
        self._paramset_descriptions_cache.remove_device(device=removal_info)  # type: ignore[arg-type]
        self._device_details_cache.remove_device(device=removal_info)  # type: ignore[arg-type]
