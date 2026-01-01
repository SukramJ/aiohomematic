# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Central data cache for device/channel parameter values.

This module provides CentralDataCache which stores recently fetched device/channel
parameter values from interfaces for quick lookup and periodic refresh.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
import logging
from typing import Any, Final

from aiohomematic.const import INIT_DATETIME, MAX_CACHE_AGE, NO_CACHE_ENTRY, CallSource, Interface, ParamsetKey
from aiohomematic.interfaces import (
    CentralInfoProtocol,
    ClientProviderProtocol,
    DataCacheWriterProtocol,
    DataPointProviderProtocol,
    DeviceProviderProtocol,
    EventBusProviderProtocol,
)
from aiohomematic.metrics import MetricKeys, emit_counter
from aiohomematic.support import changed_within_seconds

_LOGGER: Final = logging.getLogger(__name__)


class CentralDataCache(DataCacheWriterProtocol):
    """Central cache for device/channel initial data."""

    __slots__ = (
        "_central_info",
        "_client_provider",
        "_data_point_provider",
        "_device_provider",
        "_event_bus_provider",
        "_refreshed_at",
        "_value_cache",
    )

    def __init__(
        self,
        *,
        device_provider: DeviceProviderProtocol,
        client_provider: ClientProviderProtocol,
        data_point_provider: DataPointProviderProtocol,
        central_info: CentralInfoProtocol,
        event_bus_provider: EventBusProviderProtocol,
    ) -> None:
        """Initialize the central data cache."""
        self._device_provider: Final = device_provider
        self._client_provider: Final = client_provider
        self._data_point_provider: Final = data_point_provider
        self._central_info: Final = central_info
        self._event_bus_provider: Final = event_bus_provider
        # { key, value}
        self._value_cache: Final[dict[Interface, Mapping[str, Any]]] = {}
        self._refreshed_at: Final[dict[Interface, datetime]] = {}

    @property
    def size(self) -> int:
        """Return total number of entries in cache."""
        return sum(len(cache) for cache in self._value_cache.values())

    def add_data(self, *, interface: Interface, all_device_data: Mapping[str, Any]) -> None:
        """Add data to cache."""
        self._value_cache[interface] = all_device_data
        self._refreshed_at[interface] = datetime.now()

    def clear(self, *, interface: Interface | None = None) -> None:
        """Clear the cache."""
        if interface:
            self._value_cache[interface] = {}
            self._refreshed_at[interface] = INIT_DATETIME
        else:
            for _interface in self._device_provider.interfaces:
                self.clear(interface=_interface)

    def get_data(
        self,
        *,
        interface: Interface,
        channel_address: str,
        parameter: str,
    ) -> Any:
        """Get data from cache."""
        if not self._is_empty(interface=interface) and (iface_cache := self._value_cache.get(interface)) is not None:
            result = iface_cache.get(f"{interface}.{channel_address}.{parameter}", NO_CACHE_ENTRY)
            if result != NO_CACHE_ENTRY:
                emit_counter(
                    event_bus=self._event_bus_provider.event_bus,
                    key=MetricKeys.cache_hit(),
                    delta=1,
                )
            else:
                emit_counter(
                    event_bus=self._event_bus_provider.event_bus,
                    key=MetricKeys.cache_miss(),
                    delta=1,
                )
            return result
        emit_counter(
            event_bus=self._event_bus_provider.event_bus,
            key=MetricKeys.cache_miss(),
            delta=1,
        )
        return NO_CACHE_ENTRY

    async def load(self, *, direct_call: bool = False, interface: Interface | None = None) -> None:
        """Fetch data from the backend."""
        _LOGGER.debug("load: Loading device data for %s", self._central_info.name)
        for client in self._client_provider.clients:
            if interface and interface != client.interface:
                continue
            if direct_call is False and changed_within_seconds(
                last_change=self._get_refreshed_at(interface=client.interface),
                max_age=int(MAX_CACHE_AGE / 3),
            ):
                return
            await client.fetch_all_device_data()

    async def refresh_data_point_data(
        self,
        *,
        paramset_key: ParamsetKey | None = None,
        interface: Interface | None = None,
        direct_call: bool = False,
    ) -> None:
        """Refresh data_point data."""
        for dp in self._data_point_provider.get_readable_generic_data_points(
            paramset_key=paramset_key, interface=interface
        ):
            await dp.load_data_point_value(call_source=CallSource.HM_INIT, direct_call=direct_call)

    def _get_refreshed_at(self, *, interface: Interface) -> datetime:
        """Return when cache has been refreshed."""
        return self._refreshed_at.get(interface, INIT_DATETIME)

    def _is_empty(self, *, interface: Interface) -> bool:
        """Return if cache is empty for the given interface."""
        # If there is no data stored for the requested interface, treat as empty.
        if not self._value_cache.get(interface):
            return True
        # Auto-expire stale cache by interface.
        if not changed_within_seconds(last_change=self._get_refreshed_at(interface=interface)):
            # Track eviction before clearing
            if (evicted_count := len(self._value_cache.get(interface, {}))) > 0:
                emit_counter(
                    event_bus=self._event_bus_provider.event_bus,
                    key=MetricKeys.cache_eviction(),
                    delta=evicted_count,
                )
            self.clear(interface=interface)
            return True
        return False
