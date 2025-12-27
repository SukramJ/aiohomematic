# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Central data cache for device/channel parameter values.

This module provides CentralDataCache which stores recently fetched device/channel
parameter values from interfaces for quick lookup and periodic refresh.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any, Final

from aiohomematic.const import INIT_DATETIME, MAX_CACHE_AGE, NO_CACHE_ENTRY, CallSource, Interface, ParamsetKey
from aiohomematic.interfaces.central import CentralInfoProtocol, DataPointProviderProtocol, DeviceProviderProtocol
from aiohomematic.interfaces.client import ClientProviderProtocol, DataCacheWriterProtocol
from aiohomematic.support import changed_within_seconds

_LOGGER: Final = logging.getLogger(__name__)


@dataclass(slots=True)
class CacheStats:
    """Statistics for cache performance monitoring."""

    hits: int = 0
    """Number of successful cache lookups."""

    misses: int = 0
    """Number of cache misses."""

    @property
    def size(self) -> int:
        """Return current cache size (set externally)."""
        return self._size

    @size.setter
    def size(self, value: int) -> None:
        """Set current cache size."""
        self._size = value

    _size: int = 0

    @property
    def hit_rate(self) -> float:
        """Return hit rate as percentage."""
        if (total := self.hits + self.misses) == 0:
            return 100.0
        return (self.hits / total) * 100

    def reset(self) -> None:
        """Reset statistics counters."""
        self.hits = 0
        self.misses = 0


class CentralDataCache(DataCacheWriterProtocol):
    """Central cache for device/channel initial data."""

    __slots__ = (
        "_central_info",
        "_client_provider",
        "_data_point_provider",
        "_device_provider",
        "_refreshed_at",
        "_stats",
        "_value_cache",
    )

    def __init__(
        self,
        *,
        device_provider: DeviceProviderProtocol,
        client_provider: ClientProviderProtocol,
        data_point_provider: DataPointProviderProtocol,
        central_info: CentralInfoProtocol,
    ) -> None:
        """Initialize the central data cache."""
        self._device_provider: Final = device_provider
        self._client_provider: Final = client_provider
        self._data_point_provider: Final = data_point_provider
        self._central_info: Final = central_info
        # { key, value}
        self._value_cache: Final[dict[Interface, Mapping[str, Any]]] = {}
        self._refreshed_at: Final[dict[Interface, datetime]] = {}
        self._stats: Final = CacheStats()

    @property
    def stats(self) -> CacheStats:
        """Return cache statistics."""
        # Update size before returning
        total_size = sum(len(cache) for cache in self._value_cache.values())
        self._stats.size = total_size
        return self._stats

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
                self._stats.hits += 1
            else:
                self._stats.misses += 1
            return result
        self._stats.misses += 1
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
            self.clear(interface=interface)
            return True
        return False
