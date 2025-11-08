# SPDX-License-Identifier: MIT
"""
Simple i18n helper to localize exceptions (first iteration).

Usage:
- Call set_locale("de") early (CentralUnit will do this from CentralConfig).
- Use tr("key", name="value") to render localized strings with Python str.format.

Lookup order:
1) translations/<locale>.json
2) translations/strings.json (base)
3) Fallback to the key itself
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import logging
import pkgutil
from threading import RLock
from typing import Any, Final

_LOGGER: Final = logging.getLogger(__name__)

_TRANSLATIONS_PKG = "aiohomematic"
_DEFAULT_LOCALE: Final = "en"

_lock: Final = RLock()
_current_locale: str = _DEFAULT_LOCALE
_cache: dict[str, dict[str, str]] = {}
_base_cache_loaded: bool = False
_base_catalog: dict[str, str] = {}

# Eagerly load the base catalog at import time to avoid any later I/O on first use
# and to satisfy environments that prefer initialization-time loading.
try:  # pragma: no cover - trivial import-time path
    # This will load packaged resources via pkgutil without using builtins.open in our code.
    # Protected by the lock to keep thread safety consistent.
    def _eager_init_base() -> None:
        if not _base_cache_loaded:
            _load_base_catalog()

    _eager_init_base()
except Exception:  # pragma: no cover - defensive
    # If eager load fails for any reason, lazy load will occur on first access.
    pass


@dataclass(frozen=True)
class _Catalog:
    data: dict[str, str]


def _load_json_resource(package: str, resource: str) -> dict[str, str]:
    """
    Load a JSON resource from the package's translations directory without builtins.open.

    Uses pkgutil.get_data to read packaged data (works in editable installs and wheels).
    """
    try:
        if not (data_bytes := pkgutil.get_data(package, f"translations/{resource}")):
            return {}
        data = json.loads(data_bytes.decode("utf-8"))
        return {str(k): str(v) for k, v in data.items()}
    except Exception as exc:  # pragma: no cover - defensive
        _LOGGER.debug("Failed to load translation resource %s/translations/%s: %s", package, resource, exc)
        return {}


def _load_base_catalog() -> None:
    """Load the base catalog (strings.json) once."""
    global _base_cache_loaded, _base_catalog  # noqa: PLW0603  # pylint: disable=global-statement
    with _lock:
        if _base_cache_loaded:
            return
        _base_catalog = _load_json_resource(_TRANSLATIONS_PKG, "strings.json")
        _base_cache_loaded = True


def _get_catalog(locale: str) -> _Catalog:
    """Get the catalog for a locale."""
    _load_base_catalog()
    if locale in _cache:
        return _Catalog(_cache[locale])
    with _lock:
        if locale in _cache:
            return _Catalog(_cache[locale])
        localized = _load_json_resource(_TRANSLATIONS_PKG, f"{locale}.json")
        # merge with base; localized should override base
        merged: dict[str, str] = {**_base_catalog, **(localized or {})}
        _cache[locale] = merged
        return _Catalog(merged)


def set_locale(locale: str | None) -> None:
    """
    Set the current locale used for translations.

    None or empty -> defaults to "en".
    """
    global _current_locale  # noqa: PLW0603  # pylint: disable=global-statement
    new_locale = (locale or _DEFAULT_LOCALE).strip() or _DEFAULT_LOCALE
    with _lock:
        _current_locale = new_locale


def get_locale() -> str:
    """Return the currently active locale code (e.g. 'en', 'de')."""
    return _current_locale


def tr(key: str, /, **kwargs: Any) -> str:
    """
    Translate the given key using the active locale with Python str.format kwargs.

    Fallback order: <locale>.json -> strings.json -> key.
    Unknown placeholders are ignored (left as-is by format_map with default dict).
    """
    catalog = _get_catalog(_current_locale).data
    if (template := catalog.get(key)) is None:
        # try base
        _load_base_catalog()
        template = _base_catalog.get(key, key)
    try:
        # tolerant formatting: use dict that returns '{name}' if missing
        class _SafeDict(dict[str, str]):
            def __missing__(self, k: str) -> str:
                return "{" + k + "}"

        safe_kwargs: dict[str, str] = {str(k): str(v) for k, v in kwargs.items()}
        return template.format_map(_SafeDict(safe_kwargs))
    except Exception:  # pragma: no cover - keep robust against bad format strings
        return template


async def preload_locale(locale: str) -> None:
    """
    Asynchronously preload and cache a locale catalog.

    This avoids doing synchronous package resource loading in the event loop by offloading
    the work to a thread via asyncio.to_thread. Safe to call multiple times; uses cache.
    """
    # Normalize locale like set_locale does
    normalized = (locale or _DEFAULT_LOCALE).strip() or _DEFAULT_LOCALE

    def _load_sync() -> None:
        # Just call the normal loader which handles locking and caching
        _get_catalog(normalized)

    # Offload synchronous resource loading to thread to avoid blocking the loop
    await asyncio.to_thread(_load_sync)


def schedule_preload_locale(locale: str) -> asyncio.Task[None] | None:
    """
    Schedule a background task to preload a locale if an event loop is running.

    If called when no loop is running, it will load synchronously and return None.
    Returns the created Task when scheduled.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # no running loop; load synchronously
        _get_catalog((locale or _DEFAULT_LOCALE).strip() or _DEFAULT_LOCALE)
        return None

    return loop.create_task(preload_locale(locale))
