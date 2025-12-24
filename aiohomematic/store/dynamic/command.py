# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Command cache for tracking recently sent commands.

This module provides CommandCache which tracks recently sent commands per data point
with automatic expiry and configurable size limits to prevent unbounded memory growth.

Memory management strategy (three-tier approach):
    1. Lazy cleanup: When cache exceeds CLEANUP_THRESHOLD, remove expired entries
    2. Warning threshold: Log warning when approaching MAX_SIZE (hysteresis prevents spam)
    3. Hard limit eviction: When MAX_SIZE reached, remove oldest 20% of entries
"""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any, Final

from aiohomematic.const import (
    COMMAND_CACHE_MAX_SIZE,
    COMMAND_CACHE_WARNING_THRESHOLD,
    DP_KEY_VALUE,
    LAST_COMMAND_SEND_CACHE_CLEANUP_THRESHOLD,
    LAST_COMMAND_SEND_STORE_TIMEOUT,
    DataPointKey,
    ParamsetKey,
)
from aiohomematic.converter import CONVERTABLE_PARAMETERS, convert_combined_parameter_to_paramset
from aiohomematic.store.types import CachedCommand
from aiohomematic.support import changed_within_seconds

_LOGGER: Final = logging.getLogger(__name__)


class CommandCache:
    """
    Cache for send commands with resource limits.

    Tracks recently sent commands per data point with automatic expiry
    and configurable size limits to prevent unbounded memory growth.

    Memory management strategy (three-tier approach):
        1. Lazy cleanup: When cache exceeds CLEANUP_THRESHOLD, remove expired entries
        2. Warning threshold: Log warning when approaching MAX_SIZE (hysteresis prevents spam)
        3. Hard limit eviction: When MAX_SIZE reached, remove oldest 20% of entries

    The 20% eviction rate balances memory reclamation against the cost of repeated
    evictions (avoiding evicting just 1 entry repeatedly).
    """

    __slots__ = (
        "_interface_id",
        "_last_send_command",
        "_warning_logged",
    )

    def __init__(self, *, interface_id: str) -> None:
        """Initialize command cache."""
        self._interface_id: Final = interface_id
        # Maps DataPointKey to CachedCommand for tracking recent commands.
        # Used to detect duplicate sends and for unconfirmed value tracking.
        self._last_send_command: Final[dict[DataPointKey, CachedCommand]] = {}
        # Hysteresis flag to prevent repeated warning logs
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
            self._last_send_command[dpk] = CachedCommand(value=value, sent_at=now_ts)
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
        self._last_send_command[dpk] = CachedCommand(value=value, sent_at=now_ts)
        return {(dpk, value)}

    def cleanup_expired(self, *, max_age: int = LAST_COMMAND_SEND_STORE_TIMEOUT) -> int:
        """
        Remove expired command cache entries.

        Return the number of entries removed.

        Two-pass algorithm (safer than deleting during iteration):
            1. First pass: Collect keys of expired entries into a list
            2. Second pass: Delete collected keys from the dictionary

        This avoids "dictionary changed size during iteration" errors.
        """
        # Pass 1: Identify expired entries without modifying the dict
        expired_keys = [
            dpk
            for dpk, cached in self._last_send_command.items()
            if not changed_within_seconds(last_change=cached.sent_at, max_age=max_age)
        ]
        # Pass 2: Delete expired entries
        for dpk in expired_keys:
            del self._last_send_command[dpk]
        return len(expired_keys)

    def clear(self) -> None:
        """Clear all cached command entries."""
        self._last_send_command.clear()

    def get_last_value_send(self, *, dpk: DataPointKey, max_age: int = LAST_COMMAND_SEND_STORE_TIMEOUT) -> Any:
        """Return the last send values."""
        if cached := self._last_send_command.get(dpk):
            if cached.sent_at and changed_within_seconds(last_change=cached.sent_at, max_age=max_age):
                return cached.value
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
        if (cached := self._last_send_command.get(dpk)) is not None and (
            not changed_within_seconds(last_change=cached.sent_at, max_age=max_age)
            or (value is not None and cached.value == value)
        ):
            del self._last_send_command[dpk]

    def _enforce_size_limit(self) -> None:
        """
        Enforce size limits on the cache to prevent unbounded growth.

        LRU-style eviction algorithm:
            When cache reaches MAX_SIZE, evict the oldest 20% of entries.
            The 20% threshold is a heuristic that balances:
            - Memory reclamation (enough entries removed to be meaningful)
            - Performance (not called too frequently)
            - Data retention (most recent entries are preserved)

        Warning hysteresis:
            The _warning_logged flag prevents log spam when cache size oscillates
            near the warning threshold. Warning is logged once when threshold is
            exceeded, then reset only when size drops below threshold.
        """
        current_size = len(self._last_send_command)

        # Warning with hysteresis: log once when crossing threshold, reset when below
        if current_size >= COMMAND_CACHE_WARNING_THRESHOLD and not self._warning_logged:
            _LOGGER.warning(  # i18n-log: ignore
                "CommandCache for %s approaching size limit: %d/%d entries",
                self._interface_id,
                current_size,
                COMMAND_CACHE_MAX_SIZE,
            )
            self._warning_logged = True
        elif current_size < COMMAND_CACHE_WARNING_THRESHOLD:
            # Reset warning flag when cache shrinks below threshold
            self._warning_logged = False

        # Hard limit enforcement with LRU eviction
        if current_size >= COMMAND_CACHE_MAX_SIZE:
            # Sort entries by timestamp (oldest first) for LRU eviction
            sorted_entries = sorted(
                self._last_send_command.items(),
                key=lambda item: item[1].sent_at,
            )
            # Remove oldest 20% of entries (at least 1)
            remove_count = max(1, current_size // 5)
            for dpk, _ in sorted_entries[:remove_count]:
                del self._last_send_command[dpk]
            _LOGGER.debug(
                "CommandCache for %s evicted %d oldest entries (size was %d)",
                self._interface_id,
                remove_count,
                current_size,
            )
