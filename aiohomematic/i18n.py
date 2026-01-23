# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Simple i18n helper to localize exceptions.

Thread-safe implementation using immutable state snapshots for free-threading compatibility.

Usage:
- Call set_locale("de") early (CentralUnit will do this from CentralConfig).
- Use tr("key", name="value") to render localized strings with Python str.format.

Lookup order:
1) translations/<locale>.json
2) strings.json (base) in package root `aiohomematic/`
3) Fallback to the key itself
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
import logging
import pkgutil
from typing import Any, Final

from aiohomematic import compat
from aiohomematic.const import DEFAULT_LOCALE

_LOGGER: Final = logging.getLogger(__name__)
_TRANSLATIONS_PKG: Final = "aiohomematic"


@dataclass(frozen=True, slots=True)
class _LocaleState:
    """
    Immutable snapshot of locale state for thread-safe access.

    By using a frozen dataclass, we ensure that:
    1. State cannot be mutated after creation
    2. All state changes require creating a new instance
    3. Reads are always consistent (no partial updates)
    """

    current_locale: str = DEFAULT_LOCALE
    active_catalog: dict[str, str] = field(default_factory=dict)
    base_catalog: dict[str, str] = field(default_factory=dict)
    cache: dict[str, dict[str, str]] = field(default_factory=dict)
    base_loaded: bool = False


# Single atomic reference to immutable state
# Assignment in Python is atomic, so no lock needed for reads
_state: _LocaleState = _LocaleState()


class _SafeDict(dict[str, str]):
    """Dict that leaves unknown placeholders untouched during format_map."""

    def __missing__(self, k: str) -> str:  # kwonly: disable
        """Return the key as-is if not found in the dict."""
        return "{" + k + "}"


def _load_json_resource(*, package: str, resource: str, in_translations: bool = True) -> dict[str, str]:
    """Load a JSON resource from the package."""
    resource_path = f"translations/{resource}" if in_translations else resource
    try:
        if not (data_bytes := pkgutil.get_data(package=package, resource=resource_path)):
            return {}
        data = compat.loads(data=data_bytes)
        return {str(k): str(v) for k, v in data.items()}
    except Exception as exc:  # pragma: no cover - defensive
        _LOGGER.debug("Failed to load translation resource %s/%s: %s", package, resource_path, exc)
        return {}


def _ensure_base_loaded() -> _LocaleState:
    """Ensure base catalog is loaded, return current state."""
    global _state  # noqa: PLW0603  # pylint: disable=global-statement

    current = _state
    if current.base_loaded:
        return current

    # Load base catalog
    base_catalog = _load_json_resource(package=_TRANSLATIONS_PKG, resource="strings.json", in_translations=False)

    # Create new immutable state with base loaded
    new_state = _LocaleState(
        current_locale=current.current_locale,
        active_catalog={**base_catalog},
        base_catalog=base_catalog,
        cache=dict(current.cache),
        base_loaded=True,
    )

    # Atomic assignment (may race, but result is consistent - both threads load same data)
    _state = new_state
    return new_state


def _get_catalog(*, locale: str) -> dict[str, str]:
    """Get the catalog for a locale (cached)."""
    global _state  # noqa: PLW0603  # pylint: disable=global-statement

    state = _ensure_base_loaded()

    # Check cache first
    if locale in state.cache:
        return state.cache[locale]

    # Load and merge locale
    localized = _load_json_resource(package=_TRANSLATIONS_PKG, resource=f"{locale}.json")
    merged: dict[str, str] = {**state.base_catalog, **(localized or {})}

    # Update cache atomically via new state
    new_cache = dict(state.cache)
    new_cache[locale] = merged

    new_state = _LocaleState(
        current_locale=state.current_locale,
        active_catalog=merged if locale == state.current_locale else state.active_catalog,
        base_catalog=state.base_catalog,
        cache=new_cache,
        base_loaded=True,
    )
    _state = new_state

    return merged


def set_locale(*, locale: str | None = None) -> None:
    """
    Set the current locale used for translations.

    None or empty -> defaults to "en".
    Updates the active catalog reference immediately so subsequent `tr()` calls
    reflect the new locale without requiring background preload.
    """
    global _state  # noqa: PLW0603  # pylint: disable=global-statement

    new_locale = (locale or DEFAULT_LOCALE).strip() or DEFAULT_LOCALE
    merged = _get_catalog(locale=new_locale)

    state = _state
    new_state = _LocaleState(
        current_locale=new_locale,
        active_catalog=merged,
        base_catalog=state.base_catalog,
        cache=state.cache,
        base_loaded=state.base_loaded,
    )
    _state = new_state


def get_locale() -> str:
    """Return the currently active locale code (e.g. 'en', 'de')."""
    return _state.current_locale


def tr(*, key: str, **kwargs: Any) -> str:
    """
    Translate the given key using the active locale with Python str.format kwargs.

    Fallback order: <locale>.json -> strings.json -> key.
    Unknown placeholders are ignored (left as-is by format_map with default dict).
    Optimized for the hot path: use an active-catalog reference and avoid formatting
    when not needed.
    """
    # Read state once (atomic) - ensures consistent view
    state = _state

    if (template := state.active_catalog.get(key)) is None:
        # Fallback to base without additional loading
        template = state.base_catalog.get(key, key)

    # If no formatting arguments, or template has no placeholders, return as-is
    if not kwargs or ("{" not in template):
        return template

    try:
        safe_kwargs: dict[str, str] = {str(k): str(v) for k, v in kwargs.items()}
        return template.format_map(_SafeDict(safe_kwargs))
    except Exception:  # pragma: no cover - keep robust against bad format strings
        return template


async def preload_locale(*, locale: str) -> None:
    """
    Asynchronously preload and cache a locale catalog.

    This avoids doing synchronous package resource loading in the event loop by
    offloading the work to a thread via asyncio.to_thread. Safe to call multiple
    times; uses cache.
    """
    normalized = (locale or DEFAULT_LOCALE).strip() or DEFAULT_LOCALE
    await asyncio.to_thread(_get_catalog, locale=normalized)


def schedule_preload_locale(*, locale: str) -> asyncio.Task[None] | None:
    """
    Schedule a background task to preload a locale if an event loop is running.

    If called when no loop is running, it will load synchronously and return None.
    Returns the created Task when scheduled.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # no running loop; load synchronously
        _get_catalog(locale=(locale or DEFAULT_LOCALE).strip() or DEFAULT_LOCALE)
        return None

    return loop.create_task(preload_locale(locale=locale))


# Eager initialization at import time to avoid any later I/O on first use
# If eager load fails for any reason, lazy load will occur on first access.
with contextlib.suppress(Exception):  # pragma: no cover - trivial import-time path
    _ensure_base_loaded()
