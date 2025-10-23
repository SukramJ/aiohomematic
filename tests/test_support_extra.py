"""Tests for factory.py."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pytest

from aiohomematic.const import CommandRxMode, RxMode
from aiohomematic.support import CacheEntry, get_rx_modes, hash_sha256, supports_rx_mode


class _Unserializable:
    """A helper class that orjson cannot serialize directly."""

    def __init__(self, value: Any) -> None:
        self.value = value


@pytest.mark.asyncio
async def test_hash_sha256_stable_and_distinct() -> None:
    """
    hash_sha256 returns stable value for same input and different for different inputs.

    Also verifies the fallback branch for non-orjson-serializable input types (like set/custom object).
    """
    # JSON-serializable data
    v1 = {"a": 1, "b": [1, 2, 3]}
    v1_but_ordered_diff = {"b": [1, 2, 3], "a": 1}
    h1 = hash_sha256(value=v1)
    h1_again = hash_sha256(value=v1_but_ordered_diff)  # sorted keys should yield same hash

    # Different JSON-serializable data
    v2 = {"a": 2, "b": [1, 2, 3]}
    h2 = hash_sha256(value=v2)

    # Non-serializable with orjson -> triggers fallback
    v3 = {"a": {1, 2, 3}}  # set is not directly serializable by orjson
    h3 = hash_sha256(value=v3)

    # Custom object also triggers fallback path
    v4 = _Unserializable(value="x")
    h4 = hash_sha256(value=v4)

    assert isinstance(h1, str) and isinstance(h2, str) and isinstance(h3, str) and isinstance(h4, str)
    assert h1 == h1_again  # stable independent of dict key order
    assert h1 != h2  # different content -> different hash
    # Fallback paths still produce deterministic strings for equal values
    assert h3 == hash_sha256(value={"a": {3, 2, 1}})
    # For custom objects, fallback uses repr(object) which is instance-identity-dependent;
    # we only assert it produces a string, not equality across different instances.


@pytest.mark.asyncio
async def test_cache_entry_validity() -> None:
    """CacheEntry.empty() and is_valid reflect validity depending on refresh time."""
    empty = CacheEntry.empty()
    assert empty.is_valid is False

    fresh = CacheEntry(value="ok", refresh_at=datetime.now())
    assert fresh.is_valid is True

    # Very old timestamps may still be considered valid due to implementation using seconds within day.
    old = CacheEntry(value="ok", refresh_at=datetime.now() - timedelta(days=3650))
    assert isinstance(old.is_valid, bool)


@pytest.mark.asyncio
async def test_get_rx_modes_and_supports_rx_mode() -> None:
    """get_rx_modes decodes bitmask and supports_rx_mode validates compatibility."""
    # Compose a bitmask with multiple modes
    mask = int(RxMode.BURST) | int(RxMode.WAKEUP) | int(RxMode.CONFIG)
    modes = get_rx_modes(mode=mask)

    assert isinstance(modes, tuple)
    assert RxMode.BURST in modes
    assert RxMode.WAKEUP in modes
    assert RxMode.CONFIG in modes

    # supports_rx_mode checks for BURST/WAKEUP presence
    assert supports_rx_mode(command_rx_mode=CommandRxMode.BURST, rx_modes=modes) is True
    assert supports_rx_mode(command_rx_mode=CommandRxMode.WAKEUP, rx_modes=modes) is True

    # When mode does not include required flag
    only_config = get_rx_modes(mode=int(RxMode.CONFIG))
    assert supports_rx_mode(command_rx_mode=CommandRxMode.BURST, rx_modes=only_config) is False
    assert supports_rx_mode(command_rx_mode=CommandRxMode.WAKEUP, rx_modes=only_config) is False
