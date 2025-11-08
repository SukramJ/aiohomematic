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

from dataclasses import dataclass
from importlib.resources import files as ir_files
import json
import logging
from threading import RLock
from typing import Any, Final

_LOGGER: Final = logging.getLogger(__name__)

_TRANSLATIONS_PKG = "aiohomematic.translations"
_DEFAULT_LOCALE: Final = "en"

_lock: Final = RLock()
_current_locale: str = _DEFAULT_LOCALE
_cache: dict[str, dict[str, str]] = {}
_base_cache_loaded: bool = False
_base_catalog: dict[str, str] = {}


@dataclass(frozen=True)
class _Catalog:
    data: dict[str, str]


def _load_json_resource(package: str, resource: str) -> dict[str, str]:
    """Load a JSON resource from a package."""
    try:
        path = ir_files(package).joinpath(resource)
        if not path.is_file():
            return {}
        with path.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
        # ensure keys and values are str
        return {str(k): str(v) for k, v in data.items()}
    except Exception as exc:  # pragma: no cover - defensive
        _LOGGER.debug("Failed to load translation resource %s/%s: %s", package, resource, exc)
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
        merged: dict[str, str] = {**_base_catalog, **localized}
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
