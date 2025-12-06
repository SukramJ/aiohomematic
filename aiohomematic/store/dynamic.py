# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Dynamic store used at runtime by the central unit and clients.

This module provides short-lived, in-memory store that support robust and efficient
communication with Homematic interfaces:

- CommandCache: Tracks recently sent commands and their values per data point,
  allowing suppression of immediate echo updates or reconciliation with incoming
  events. Supports set_value, put_paramset, and combined parameters.
- DeviceDetailsCache: Enriches devices with human-readable names, interface
  mapping, rooms, functions, and address IDs fetched via the backend.
- CentralDataCache: Stores recently fetched device/channel parameter values from
  interfaces for quick lookup and periodic refresh.
- PingPongCache: Tracks ping/pong timestamps to detect connection health issues
  and publishes interface events on mismatch thresholds.

The store are intentionally ephemeral and cleared/aged according to the rules in
constants to keep memory footprint predictable while improving responsiveness.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Mapping
from datetime import datetime
import logging
import time
from typing import Any, Final, cast

from aiohomematic import i18n
from aiohomematic.const import (
    COMMAND_CACHE_MAX_SIZE,
    COMMAND_CACHE_WARNING_THRESHOLD,
    DP_KEY_VALUE,
    INIT_DATETIME,
    LAST_COMMAND_SEND_CACHE_CLEANUP_THRESHOLD,
    LAST_COMMAND_SEND_STORE_TIMEOUT,
    MAX_CACHE_AGE,
    NO_CACHE_ENTRY,
    PING_PONG_CACHE_MAX_SIZE,
    PING_PONG_MISMATCH_COUNT,
    PING_PONG_MISMATCH_COUNT_TTL,
    CallSource,
    DataPointKey,
    EventKey,
    EventType,
    Interface,
    InterfaceEventType,
    ParamsetKey,
)
from aiohomematic.converter import CONVERTABLE_PARAMETERS, convert_combined_parameter_to_paramset
from aiohomematic.interfaces import (
    CentralInfo,
    ClientProvider,
    DataCacheProvider,
    DataPointProvider,
    DeviceDetailsProvider,
    DeviceProtocol,
    DeviceProvider,
    EventPublisher,
    PrimaryClientProvider,
)
from aiohomematic.schemas import INTERFACE_EVENT_SCHEMA
from aiohomematic.support import changed_within_seconds, get_device_address

_LOGGER: Final = logging.getLogger(__name__)


class CommandCache:
    """
    Cache for send commands with resource limits.

    Tracks recently sent commands per data point with automatic expiry
    and configurable size limits to prevent unbounded memory growth.
    """

    __slots__ = (
        "_interface_id",
        "_last_send_command",
        "_warning_logged",
    )

    def __init__(self, *, interface_id: str) -> None:
        """Initialize command cache."""
        self._interface_id: Final = interface_id
        # (paramset_key, device_address, channel_no, parameter)
        self._last_send_command: Final[dict[DataPointKey, tuple[Any, datetime]]] = {}
        self._warning_logged: bool = False

    @property
    def size(self) -> int:
        """Return the current cache size."""
        return len(self._last_send_command)

    def add_combined_parameter(
        self, *, parameter: str, channel_address: str, combined_parameter: str
    ) -> set[DP_KEY_VALUE]:
        """Add data from combined parameter."""
        if values := convert_combined_parameter_to_paramset(parameter=parameter, value=combined_parameter):
            return self.add_put_paramset(
                channel_address=channel_address,
                paramset_key=ParamsetKey.VALUES,
                values=values,
            )
        return set()

    def add_put_paramset(
        self, *, channel_address: str, paramset_key: ParamsetKey, values: dict[str, Any]
    ) -> set[DP_KEY_VALUE]:
        """Add data from put paramset command."""
        # Cleanup expired entries when cache size exceeds threshold
        if len(self._last_send_command) > LAST_COMMAND_SEND_CACHE_CLEANUP_THRESHOLD:
            self.cleanup_expired()

        # Enforce hard size limit
        self._enforce_size_limit()

        dpk_values: set[DP_KEY_VALUE] = set()
        now_ts = datetime.now()
        for parameter, value in values.items():
            dpk = DataPointKey(
                interface_id=self._interface_id,
                channel_address=channel_address,
                paramset_key=paramset_key,
                parameter=parameter,
            )
            self._last_send_command[dpk] = (value, now_ts)
            dpk_values.add((dpk, value))
        return dpk_values

    def add_set_value(
        self,
        *,
        channel_address: str,
        parameter: str,
        value: Any,
    ) -> set[DP_KEY_VALUE]:
        """Add data from set value command."""
        if parameter in CONVERTABLE_PARAMETERS:
            return self.add_combined_parameter(
                parameter=parameter, channel_address=channel_address, combined_parameter=value
            )

        # Cleanup expired entries when cache size exceeds threshold
        if len(self._last_send_command) > LAST_COMMAND_SEND_CACHE_CLEANUP_THRESHOLD:
            self.cleanup_expired()

        # Enforce hard size limit
        self._enforce_size_limit()

        now_ts = datetime.now()
        dpk = DataPointKey(
            interface_id=self._interface_id,
            channel_address=channel_address,
            paramset_key=ParamsetKey.VALUES,
            parameter=parameter,
        )
        self._last_send_command[dpk] = (value, now_ts)
        return {(dpk, value)}

    def cleanup_expired(self, *, max_age: int = LAST_COMMAND_SEND_STORE_TIMEOUT) -> int:
        """
        Remove expired command cache entries.

        Returns the number of entries removed.
        """
        expired_keys = [
            dpk
            for dpk, (_, last_send_dt) in self._last_send_command.items()
            if not changed_within_seconds(last_change=last_send_dt, max_age=max_age)
        ]
        for dpk in expired_keys:
            del self._last_send_command[dpk]
        return len(expired_keys)

    def clear(self) -> None:
        """Clear all cached command entries."""
        self._last_send_command.clear()

    def get_last_value_send(self, *, dpk: DataPointKey, max_age: int = LAST_COMMAND_SEND_STORE_TIMEOUT) -> Any:
        """Return the last send values."""
        if result := self._last_send_command.get(dpk):
            value, last_send_dt = result
            if last_send_dt and changed_within_seconds(last_change=last_send_dt, max_age=max_age):
                return value
            self.remove_last_value_send(
                dpk=dpk,
                max_age=max_age,
            )
        return None

    def remove_last_value_send(
        self,
        *,
        dpk: DataPointKey,
        value: Any = None,
        max_age: int = LAST_COMMAND_SEND_STORE_TIMEOUT,
    ) -> None:
        """Remove the last send value."""
        if result := self._last_send_command.get(dpk):
            stored_value, last_send_dt = result
            if not changed_within_seconds(last_change=last_send_dt, max_age=max_age) or (
                value is not None and stored_value == value
            ):
                del self._last_send_command[dpk]

    def _enforce_size_limit(self) -> None:
        """Enforce size limits on the cache to prevent unbounded growth."""
        current_size = len(self._last_send_command)

        # Log warning when approaching limit
        if current_size >= COMMAND_CACHE_WARNING_THRESHOLD and not self._warning_logged:
            _LOGGER.warning(  # i18n-log: ignore
                "CommandCache for %s approaching size limit: %d/%d entries",
                self._interface_id,
                current_size,
                COMMAND_CACHE_MAX_SIZE,
            )
            self._warning_logged = True
        elif current_size < COMMAND_CACHE_WARNING_THRESHOLD:
            self._warning_logged = False

        # Enforce hard limit by removing oldest entries
        if current_size >= COMMAND_CACHE_MAX_SIZE:
            # Sort by timestamp and remove oldest entries
            sorted_entries = sorted(
                self._last_send_command.items(),
                key=lambda item: item[1][1],  # Sort by datetime
            )
            # Remove oldest 20% of entries
            remove_count = max(1, current_size // 5)
            for dpk, _ in sorted_entries[:remove_count]:
                del self._last_send_command[dpk]
            _LOGGER.debug(
                "CommandCache for %s evicted %d oldest entries (size was %d)",
                self._interface_id,
                remove_count,
                current_size,
            )


class DeviceDetailsCache(DeviceDetailsProvider):
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
        central_info: CentralInfo,
        primary_client_provider: PrimaryClientProvider,
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

    @property
    def device_channel_rega_ids(self) -> Mapping[str, int]:
        """Return device channel ids."""
        return self._device_channel_rega_ids

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

    def remove_device(self, *, device: DeviceProtocol) -> None:
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
        """Return rooms by device_address."""
        _device_rooms: Final[dict[str, set[str]]] = defaultdict(set)
        for channel_address, rooms in self._channel_rooms.items():
            if rooms:
                _device_rooms[get_device_address(address=channel_address)].update(rooms)
        return _device_rooms


class CentralDataCache(DataCacheProvider):
    """Central cache for device/channel initial data."""

    __slots__ = (
        "_central_info",
        "_client_provider",
        "_data_point_provider",
        "_device_provider",
        "_refreshed_at",
        "_value_cache",
    )

    def __init__(
        self,
        *,
        device_provider: DeviceProvider,
        client_provider: ClientProvider,
        data_point_provider: DataPointProvider,
        central_info: CentralInfo,
    ) -> None:
        """Initialize the central data cache."""
        self._device_provider: Final = device_provider
        self._client_provider: Final = client_provider
        self._data_point_provider: Final = data_point_provider
        self._central_info: Final = central_info
        # { key, value}
        self._value_cache: Final[dict[Interface, Mapping[str, Any]]] = {}
        self._refreshed_at: Final[dict[Interface, datetime]] = {}

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
            return iface_cache.get(f"{interface}.{channel_address}.{parameter}", NO_CACHE_ENTRY)
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


class PingPongCache:
    """Cache to collect ping/pong events with ttl."""

    __slots__ = (
        "_allowed_delta",
        "_central_info",
        "_event_publisher",
        "_interface_id",
        "_pending_pong_logged",
        "_pending_pongs",
        "_pending_seen_at",
        "_retry_at",
        "_ttl",
        "_unknown_pong_logged",
        "_unknown_pongs",
        "_unknown_seen_at",
    )

    def __init__(
        self,
        *,
        event_publisher: EventPublisher,
        central_info: CentralInfo,
        interface_id: str,
        allowed_delta: int = PING_PONG_MISMATCH_COUNT,
        ttl: int = PING_PONG_MISMATCH_COUNT_TTL,
    ):
        """Initialize the cache with ttl."""
        assert ttl > 0
        self._event_publisher: Final = event_publisher
        self._central_info: Final = central_info
        self._interface_id: Final = interface_id
        self._allowed_delta: Final = allowed_delta
        self._ttl: Final = ttl
        self._pending_pong_logged: bool = False
        self._pending_pongs: Final[set[str]] = set()
        self._pending_seen_at: Final[dict[str, float]] = {}
        self._retry_at: Final[set[str]] = set()
        self._unknown_pong_logged: bool = False
        self._unknown_pongs: Final[set[str]] = set()
        self._unknown_seen_at: Final[dict[str, float]] = {}

    @property
    def _pending_pong_count(self) -> int:
        """Return the pending pong count."""
        return len(self._pending_pongs)

    @property
    def _unknown_pong_count(self) -> int:
        """Return the unknown pong count."""
        return len(self._unknown_pongs)

    @property
    def allowed_delta(self) -> int:
        """Return the allowed delta."""
        return self._allowed_delta

    @property
    def size(self) -> int:
        """Return total size of pending and unknown pong sets."""
        return self._pending_pong_count + self._unknown_pong_count

    def clear(self) -> None:
        """Clear the cache."""
        self._pending_pongs.clear()
        self._unknown_pongs.clear()
        self._pending_seen_at.clear()
        self._unknown_seen_at.clear()
        self._pending_pong_logged = False
        self._unknown_pong_logged = False

    def handle_received_pong(self, *, pong_token: str) -> None:
        """Handle received pong token."""
        if pong_token in self._pending_pongs:
            self._pending_pongs.remove(pong_token)
            self._pending_seen_at.pop(pong_token, None)
            self._cleanup_pending_pongs()
            count = self._pending_pong_count
            self._check_and_publish_pong_event(event_type=InterfaceEventType.PENDING_PONG)
            _LOGGER.debug(
                "PING PONG CACHE: Reduce pending PING count: %s - %i for token: %s",
                self._interface_id,
                count,
                pong_token,
            )
        else:
            # Track unknown pong with monotonic insertion time for TTL expiry.
            self._unknown_pongs.add(pong_token)
            self._unknown_seen_at[pong_token] = time.monotonic()
            self._cleanup_unknown_pongs()
            count = self._unknown_pong_count
            self._check_and_publish_pong_event(event_type=InterfaceEventType.UNKNOWN_PONG)
            _LOGGER.debug(
                "PING PONG CACHE: Increase unknown PONG count: %s - %i for token: %s",
                self._interface_id,
                count,
                pong_token,
            )
            # Schedule a single retry after 15s to try reconciling this PONG with a possible late PING.
            self._schedule_unknown_pong_retry(token=pong_token, delay=15.0)

    def handle_send_ping(self, *, ping_token: str) -> None:
        """Handle send ping token by tracking it as pending and publishing events."""
        self._pending_pongs.add(ping_token)
        self._pending_seen_at[ping_token] = time.monotonic()
        self._cleanup_pending_pongs()
        # Throttle event emission to every second ping to avoid spamming callbacks,
        # but always publish when crossing the high threshold.
        count = self._pending_pong_count
        if (count > self._allowed_delta) or (count % 2 == 0):
            self._check_and_publish_pong_event(event_type=InterfaceEventType.PENDING_PONG)
        _LOGGER.debug(
            "PING PONG CACHE: Increase pending PING count: %s - %i for token: %s",
            self._interface_id,
            count,
            ping_token,
        )

    def _check_and_publish_pong_event(self, *, event_type: InterfaceEventType) -> None:
        """Publish an event about the pong status."""

        def _publish_event(mismatch_count: int) -> None:
            """Publish event."""
            self._event_publisher.publish_homematic_event(
                event_type=EventType.INTERFACE,
                event_data=cast(
                    dict[EventKey, Any],
                    INTERFACE_EVENT_SCHEMA(
                        {
                            EventKey.INTERFACE_ID: self._interface_id,
                            EventKey.TYPE: event_type,
                            EventKey.DATA: {
                                EventKey.CENTRAL_NAME: self._central_info.name,
                                EventKey.PONG_MISMATCH_ACCEPTABLE: mismatch_count <= self._allowed_delta,
                                EventKey.PONG_MISMATCH_COUNT: mismatch_count,
                            },
                        }
                    ),
                ),
            )
            _LOGGER.debug(
                "PING PONG CACHE: Emitting event %s for %s with mismatch_count: %i with %i acceptable",
                event_type,
                self._interface_id,
                mismatch_count,
                self._allowed_delta,
            )

        if event_type == InterfaceEventType.PENDING_PONG:
            self._cleanup_pending_pongs()
            if (count := self._pending_pong_count) > self._allowed_delta:
                # Publish interface event to inform subscribers about high pending pong count.
                _publish_event(mismatch_count=count)
                if self._pending_pong_logged is False:
                    _LOGGER.warning(
                        i18n.tr(
                            "log.store.dynamic.pending_pong_mismatch",
                            interface_id=self._interface_id,
                        )
                    )
                self._pending_pong_logged = True
            # In low state:
            # - If we previously logged a high state, publish a reset event (mismatch=0) exactly once.
            # - Otherwise, throttle emission to every second ping (even counts > 0) to avoid spamming.
            elif self._pending_pong_logged:
                _publish_event(mismatch_count=0)
                self._pending_pong_logged = False
            elif count > 0 and count % 2 == 0:
                _publish_event(mismatch_count=count)
        elif event_type == InterfaceEventType.UNKNOWN_PONG:
            self._cleanup_unknown_pongs()
            count = self._unknown_pong_count
            if self._unknown_pong_count > self._allowed_delta:
                # Publish interface event to inform subscribers about high unknown pong count.
                _publish_event(mismatch_count=count)
                if self._unknown_pong_logged is False:
                    _LOGGER.warning(
                        i18n.tr(
                            "log.store.dynamic.unknown_pong_mismatch",
                            interface_id=self._interface_id,
                        )
                    )
                self._unknown_pong_logged = True
            else:
                # For unknown pongs, only reset the logged flag when we drop below the threshold.
                # We do not publish an event here since there is no explicit expectation for a reset notification.
                self._unknown_pong_logged = False

    def _cleanup_pending_pongs(self) -> None:
        """Cleanup too old pending pongs, using monotonic time and enforce size limit."""
        now = time.monotonic()
        for pp_pong_ts in list(self._pending_pongs):
            seen_at = self._pending_seen_at.get(pp_pong_ts)
            expired = False
            if seen_at is not None:
                expired = (now - seen_at) > self._ttl
            if expired:
                self._pending_pongs.remove(pp_pong_ts)
                self._pending_seen_at.pop(pp_pong_ts, None)
                _LOGGER.debug(
                    "PING PONG CACHE: Removing expired pending PONG: %s - %i for ts: %s",
                    self._interface_id,
                    self._pending_pong_count,
                    pp_pong_ts,
                )

        # Enforce size limit by removing oldest entries
        if self._pending_pong_count > PING_PONG_CACHE_MAX_SIZE:
            sorted_entries = sorted(
                self._pending_seen_at.items(),
                key=lambda item: item[1],
            )
            remove_count = self._pending_pong_count - PING_PONG_CACHE_MAX_SIZE
            for token, _ in sorted_entries[:remove_count]:
                self._pending_pongs.discard(token)
                self._pending_seen_at.pop(token, None)
            _LOGGER.debug(
                "PING PONG CACHE: Evicted %d oldest pending entries on %s (limit: %d)",
                remove_count,
                self._interface_id,
                PING_PONG_CACHE_MAX_SIZE,
            )

    def _cleanup_unknown_pongs(self) -> None:
        """Cleanup too old unknown pongs, using monotonic time and enforce size limit."""
        now = time.monotonic()
        for up_pong_ts in list(self._unknown_pongs):
            seen_at = self._unknown_seen_at.get(up_pong_ts)
            expired = False
            if seen_at is not None:
                expired = (now - seen_at) > self._ttl
            if expired:
                self._unknown_pongs.remove(up_pong_ts)
                self._unknown_seen_at.pop(up_pong_ts, None)
                _LOGGER.debug(
                    "PING PONG CACHE: Removing expired unknown PONG: %s - %i or ts: %s",
                    self._interface_id,
                    self._unknown_pong_count,
                    up_pong_ts,
                )

        # Enforce size limit by removing oldest entries
        if self._unknown_pong_count > PING_PONG_CACHE_MAX_SIZE:
            sorted_entries = sorted(
                self._unknown_seen_at.items(),
                key=lambda item: item[1],
            )
            remove_count = self._unknown_pong_count - PING_PONG_CACHE_MAX_SIZE
            for token, _ in sorted_entries[:remove_count]:
                self._unknown_pongs.discard(token)
                self._unknown_seen_at.pop(token, None)
            _LOGGER.debug(
                "PING PONG CACHE: Evicted %d oldest unknown entries on %s (limit: %d)",
                remove_count,
                self._interface_id,
                PING_PONG_CACHE_MAX_SIZE,
            )

    async def _retry_reconcile_pong(self, *, token: str) -> None:
        """Attempt to reconcile a previously-unknown PONG with a late pending PING."""
        # Always allow another schedule after the retry completes
        try:
            # Cleanup any expired entries first to avoid outdated counts
            self._cleanup_pending_pongs()
            self._cleanup_unknown_pongs()

            if token in self._pending_pongs:
                # Remove from pending
                self._pending_pongs.remove(token)
                self._pending_seen_at.pop(token, None)

                # If still marked unknown, clear it
                unknown_before = self._unknown_pong_count
                if token in self._unknown_pongs:
                    self._unknown_pongs.remove(token)
                    self._unknown_seen_at.pop(token, None)

                # Re-publish events to reflect new counts (respecting existing throttling)
                self._check_and_publish_pong_event(event_type=InterfaceEventType.PENDING_PONG)
                if self._unknown_pong_count != unknown_before:
                    self._check_and_publish_pong_event(event_type=InterfaceEventType.UNKNOWN_PONG)

                _LOGGER.debug(
                    "PING PONG CACHE: Retry reconciled PONG on %s for token: %s (pending now: %i, unknown now: %i)",
                    self._interface_id,
                    token,
                    self._pending_pong_count,
                    self._unknown_pong_count,
                )
            else:
                _LOGGER.debug(
                    "PING PONG CACHE: Retry found no pending PING on %s for token: %s (unknown: %s)",
                    self._interface_id,
                    token,
                    token in self._unknown_pongs,
                )
        finally:
            self._retry_at.discard(token)

    def _schedule_unknown_pong_retry(self, *, token: str, delay: float) -> None:
        """
        Schedule a one-shot retry to reconcile an unknown PONG after delay seconds.

        If no looper is available on the central (e.g. in unit tests), skip scheduling.
        """
        # Coalesce multiple schedules for the same token
        if token in self._retry_at:
            return
        self._retry_at.add(token)

        if (looper := getattr(self._central_info, "looper", None)) is None:
            # In testing contexts without a looper, we cannot schedule — leave to TTL expiry.
            _LOGGER.debug(
                "PING PONG CACHE: Skip scheduling retry for token %s on %s (no looper)",
                token,
                self._interface_id,
            )
            # Allow a future attempt to schedule if environment changes
            self._retry_at.discard(token)
            return

        async def _retry() -> None:
            try:
                await asyncio.sleep(delay)
                await self._retry_reconcile_pong(token=token)
            except Exception as err:  # pragma: no cover
                _LOGGER.debug(
                    "PING PONG CACHE: Retry task error for token %s on %s: %s",
                    token,
                    self._interface_id,
                    err,
                )
                # Ensure token can be rescheduled if needed
                self._retry_at.discard(token)

        looper.create_task(target=_retry, name=f"ppc_retry_{self._interface_id}_{token}")
