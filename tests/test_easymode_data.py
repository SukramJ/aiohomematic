# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for the easymode metadata loader."""

from __future__ import annotations

from aiohomematic import easymode_data


class TestEagerInitialization:
    """Verify the store is loaded at import time to avoid event-loop I/O."""

    def test_public_access_does_not_reload(self) -> None:
        """A public lookup after import performs no I/O (store already loaded)."""
        # Lookups are pure dict reads; an unknown key simply returns None.
        assert easymode_data.get_channel_metadata(channel_type="__unknown__") is None
        assert easymode_data._store._loaded is True

    def test_store_loaded_at_import(self) -> None:
        """
        Verify the module-level store is loaded eagerly at import time.

        The first ``get_*()`` access must not trigger blocking file I/O,
        because that access can happen inside the asyncio event loop (e.g.
        Home Assistant's ``ws_get_form_schema``). Eager initialization at
        import time moves the archive read out of the loop.
        """
        assert easymode_data._store._loaded is True
