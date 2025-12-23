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

import logging
from typing import Final

from aiohomematic.const import DataOperationResult, Interface
from aiohomematic.interfaces.central import (
    CentralInfoProtocol,
    ConfigProviderProtocol,
    DataPointProviderProtocol,
    DeviceProviderProtocol,
)
from aiohomematic.interfaces.client import (
    ClientProviderProtocol,
    PrimaryClientProviderProtocol,
    SessionRecorderProviderProtocol,
)
from aiohomematic.interfaces.model import DeviceRemovalInfoProtocol
from aiohomematic.interfaces.operations import TaskSchedulerProtocol
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


class CacheCoordinator(SessionRecorderProviderProtocol):
    """Coordinator for all cache operations in the central unit."""

    __slots__ = (
        "_central_info",
        "_data_cache",
        "_device_descriptions_cache",
        "_device_details_cache",
        "_parameter_visibility_cache",
        "_paramset_descriptions_cache",
        "_session_recorder",
    )

    def __init__(
        self,
        *,
        central_info: CentralInfoProtocol,
        client_provider: ClientProviderProtocol,
        config_provider: ConfigProviderProtocol,
        data_point_provider: DataPointProviderProtocol,
        device_provider: DeviceProviderProtocol,
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
            primary_client_provider: Provider for primary client access
            config_provider: Provider for configuration access
            task_scheduler: Provider for task scheduling
            session_recorder_active: Whether session recording should be active

        """
        self._central_info: Final = central_info

        # Initialize all caches with protocol interfaces
        self._data_cache: Final = CentralDataCache(
            device_provider=device_provider,
            client_provider=client_provider,
            data_point_provider=data_point_provider,
            central_info=central_info,
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

    data_cache: Final = DelegatedProperty[CentralDataCache](path="_data_cache")
    device_descriptions: Final = DelegatedProperty[DeviceDescriptionCache](path="_device_descriptions_cache")
    device_details: Final = DelegatedProperty[DeviceDetailsCache](path="_device_details_cache")
    parameter_visibility: Final = DelegatedProperty[ParameterVisibilityCache](path="_parameter_visibility_cache")
    paramset_descriptions: Final = DelegatedProperty[ParamsetDescriptionCache](path="_paramset_descriptions_cache")
    recorder: Final = DelegatedProperty[SessionRecorder](path="_session_recorder")

    async def clear_all(self) -> None:
        """Clear all caches and remove stored files."""
        _LOGGER.debug("CLEAR_ALL: Clearing all caches for %s", self._central_info.name)
        await self._device_descriptions_cache.clear()
        await self._paramset_descriptions_cache.clear()
        await self._session_recorder.clear()
        self._device_details_cache.clear()
        self._data_cache.clear()

    def clear_on_stop(self) -> None:
        """Clear in-memory caches on shutdown to free memory."""
        _LOGGER.debug("CLEAR_ON_STOP: Clearing in-memory caches for %s", self._central_info.name)
        self._device_details_cache.clear()
        self._data_cache.clear()
        self._parameter_visibility_cache.clear_memoization_caches()

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
