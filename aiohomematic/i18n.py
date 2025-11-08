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

from aiohomematic.const import DEFAULT_LOCALE

_BASE_CACHE_LOADED: bool = False
_BASE_CATALOG: dict[str, str] = {}
_CACHE: dict[str, dict[str, str]] = {}
_CURRENT_LOCALE: str = DEFAULT_LOCALE
_LOCK: Final = RLock()
_TRANSLATIONS_PKG = "aiohomematic.translations"

_LOGGER: Final = logging.getLogger(__name__)

# Eagerly load the base catalog at import time to avoid any later I/O on first use
# and to satisfy environments that prefer initialization-time loading.
try:  # pragma: no cover - trivial import-time path
    # This will load packaged resources via pkgutil without using builtins.open in our code.
    # Protected by the lock to keep thread safety consistent.
    def _eager_init_base() -> None:
        if not _BASE_CACHE_LOADED:
            _load_base_catalog()

    _eager_init_base()
except Exception:  # pragma: no cover - defensive
    # If eager load fails for any reason, lazy load will occur on first access.
    pass


@dataclass(frozen=True)
class _Catalog:
    data: dict[str, str]


def _load_json_resource(*, package: str, resource: str) -> dict[str, str]:
    """
    Load a JSON resource from the package's translations directory without builtins.open.

    Uses pkgutil.get_data to read packaged data (works in editable installs and wheels).
    """
    try:
        if not (data_bytes := pkgutil.get_data(package=package, resource=f"translations/{resource}")):
            return {}
        data = json.loads(data_bytes.decode(encoding="utf-8"))
        return {str(k): str(v) for k, v in data.items()}
    except Exception as exc:  # pragma: no cover - defensive
        _LOGGER.debug("Failed to load translation resource %s/translations/%s: %s", package, resource, exc)
        return {}


def _load_base_catalog() -> None:
    """Load the base catalog (strings.json) once."""
    global _BASE_CACHE_LOADED, _BASE_CATALOG  # noqa: PLW0603  # pylint: disable=global-statement
    with _LOCK:
        if _BASE_CACHE_LOADED:
            return
        _BASE_CATALOG = _load_json_resource(package=_TRANSLATIONS_PKG, resource="strings.json")
        _BASE_CACHE_LOADED = True


def _get_catalog(*, locale: str) -> _Catalog:
    """Get the catalog for a locale."""
    _load_base_catalog()
    if locale in _CACHE:
        return _Catalog(_CACHE[locale])
    with _LOCK:
        if locale in _CACHE:
            return _Catalog(_CACHE[locale])
        localized = _load_json_resource(package=_TRANSLATIONS_PKG, resource=f"{locale}.json")
        # merge with base; localized should override base
        merged: dict[str, str] = {**_BASE_CATALOG, **(localized or {})}
        _CACHE[locale] = merged
        return _Catalog(merged)


def set_locale(*, locale: str | None) -> None:
    """
    Set the current locale used for translations.

    None or empty -> defaults to "en".
    """
    global _CURRENT_LOCALE  # noqa: PLW0603  # pylint: disable=global-statement
    new_locale = (locale or DEFAULT_LOCALE).strip() or DEFAULT_LOCALE
    with _LOCK:
        _CURRENT_LOCALE = new_locale


def get_locale() -> str:
    """Return the currently active locale code (e.g. 'en', 'de')."""
    return _CURRENT_LOCALE


def tr(key: str, /, **kwargs: Any) -> str:
    """
    Translate the given key using the active locale with Python str.format kwargs.

    Fallback order: <locale>.json -> strings.json -> key.
    Unknown placeholders are ignored (left as-is by format_map with default dict).
    """
    catalog = _get_catalog(locale=_CURRENT_LOCALE).data
    if (template := catalog.get(key)) is None:
        # try base
        _load_base_catalog()
        template = _BASE_CATALOG.get(key, key)
    try:
        # tolerant formatting: use dict that returns '{name}' if missing
        class _SafeDict(dict[str, str]):
            def __missing__(self, k: str) -> str:
                return "{" + k + "}"

        safe_kwargs: dict[str, str] = {str(k): str(v) for k, v in kwargs.items()}
        return template.format_map(_SafeDict(safe_kwargs))
    except Exception:  # pragma: no cover - keep robust against bad format strings
        return template


async def preload_locale(*, locale: str) -> None:
    """
    Asynchronously preload and cache a locale catalog.

    This avoids doing synchronous package resource loading in the event loop by offloading
    the work to a thread via asyncio.to_thread. Safe to call multiple times; uses cache.
    """
    # Normalize locale like set_locale does
    normalized = (locale or DEFAULT_LOCALE).strip() or DEFAULT_LOCALE

    def _load_sync() -> None:
        # Just call the normal loader which handles locking and caching
        _get_catalog(locale=normalized)

    # Offload synchronous resource loading to thread to avoid blocking the loop
    await asyncio.to_thread(_load_sync)


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
