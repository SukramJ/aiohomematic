# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Loader for CCU-sourced translation data.

Provide access to human-readable translations for channel types, device models,
parameter names, and parameter enum values extracted from the OpenCCU WebUI.

The auto-generated JSON files live in ``translations/ccu_extract/`` and are
produced by ``script/extract_ccu_translations.py``.  Hand-maintained overrides
go into ``translations/ccu_custom/`` (same file names).  At load time the two
layers are merged: custom keys override or supplement extracted keys.

All public functions are pure dict lookups after first access (no I/O),
making them safe to call from the asyncio event loop. Thread safety is
ensured via double-checked locking during lazy initialization.

Public API of this module is defined by __all__.
"""

from __future__ import annotations

import contextlib
import json
import logging
import pkgutil
import threading
from typing import Final

__all__ = [
    "get_channel_type_translation",
    "get_device_icon",
    "get_device_model_description",
    "get_parameter_help",
    "get_parameter_translation",
    "get_parameter_value_translation",
]

_LOGGER: Final = logging.getLogger(__name__)
_PACKAGE: Final = "aiohomematic"

_SUPPORTED_LOCALES: Final = frozenset({"de", "en"})
_DEFAULT_LOCALE: Final = "en"
_CATEGORIES: Final = ("channel_types", "device_models", "parameter_help", "parameters", "parameter_values")
_LOCALE_INDEPENDENT_CATEGORIES: Final = ("device_icons",)
_SUBDIRS: Final = ("ccu_extract", "ccu_custom")

# Prefixes used in LINK paramset parameter names (e.g. SHORT_ON_LEVEL, LONG_RAMPON_TIME).
# The CCU WebUI strips these when looking up translations; we do the same as fallback
# and append a parenthesized suffix to the resolved base translation.
_LINK_PREFIX_LABELS: Final[dict[str, dict[str, str]]] = {
    "short_": {"de": "kurz", "en": "short"},
    "long_": {"de": "lang", "en": "long"},
}


class _TranslationStore:
    """
    Thread-safe, lazily loaded store for CCU translation data.

    Load all JSON files on first access and serve from memory afterwards.
    After initialization, all lookups are pure dict reads with no I/O,
    making them safe to call from the asyncio event loop.
    """

    __slots__ = ("_data", "_loaded", "_lock", "_value_indices")

    def __init__(self) -> None:
        self._data: Final[dict[str, dict[str, str]]] = {}
        self._value_indices: Final[dict[str, dict[str, str]]] = {}
        self._loaded: bool = False
        self._lock: Final = threading.Lock()

    def get(self, *, category: str, locale: str) -> dict[str, str]:
        """Return translation dict for category and locale."""
        if not self._loaded:
            self.load()
        return self._data.get(f"{category}_{locale}", {})

    def get_locale_independent(self, *, category: str) -> dict[str, str]:
        """Return translation dict for a locale-independent category."""
        if not self._loaded:
            self.load()
        return self._data.get(category, {})

    def get_value_fallback(self, *, value: str, locale: str) -> str | None:
        """Return a generic translation for a standalone value."""
        return self._value_indices.get(f"parameter_values_{locale}", {}).get(value.lower())

    def load(self) -> None:
        """
        Load all translation files (double-checked locking).

        For each category/locale pair, load from ``ccu_extract/`` first,
        then merge ``ccu_custom/`` on top so that custom keys override or
        supplement extracted keys.

        Use pkgutil.get_data() instead of Path.read_text() to avoid
        blocking file I/O detection in Home Assistant's event loop.
        """
        with self._lock:
            if self._loaded:
                return
            for category in _CATEGORIES:
                for locale in _SUPPORTED_LOCALES:
                    key = f"{category}_{locale}"
                    filename = f"{key}.json"
                    merged: dict[str, str] = {}
                    for subdir in _SUBDIRS:
                        resource = f"translations/{subdir}/{filename}"
                        try:
                            if not (data_bytes := pkgutil.get_data(package=_PACKAGE, resource=resource)):
                                continue
                            raw: dict[str, str] = json.loads(data_bytes)
                            merged.update({k.lower(): v for k, v in raw.items()})
                        except (FileNotFoundError, json.JSONDecodeError) as err:
                            _LOGGER.debug("Failed to load %s/%s: %s", _PACKAGE, resource, err)
                    self._data[key] = merged
            # Load locale-independent categories (single file, no locale suffix)
            for category in _LOCALE_INDEPENDENT_CATEGORIES:
                filename = f"{category}.json"
                li_merged: dict[str, str] = {}
                for subdir in _SUBDIRS:
                    resource = f"translations/{subdir}/{filename}"
                    try:
                        if not (data_bytes := pkgutil.get_data(package=_PACKAGE, resource=resource)):
                            continue
                        li_raw: dict[str, str] = json.loads(data_bytes)
                        li_merged.update({k.lower(): v for k, v in li_raw.items()})
                    except (FileNotFoundError, json.JSONDecodeError) as err:
                        _LOGGER.debug("Failed to load %s/%s: %s", _PACKAGE, resource, err)
                self._data[category] = li_merged
            # Build value-only indices for parameter_values:
            # Maps each enum value to its shortest (most generic) translation.
            for locale in _SUPPORTED_LOCALES:
                if (pv_key := f"parameter_values_{locale}") in self._data:
                    value_index: dict[str, str] = {}
                    for k, v in self._data[pv_key].items():
                        if "=" not in k:
                            continue
                        val = k.rsplit("=", maxsplit=1)[1]
                        if val not in value_index or len(v) < len(value_index[val]):
                            value_index[val] = v
                    self._value_indices[pv_key] = value_index
            self._loaded = True


_store: Final = _TranslationStore()

# Eager initialization at import time to avoid any later I/O on first use.
with contextlib.suppress(Exception):
    _store.load()


def _get_locale(*, locale: str) -> str:
    """Normalize locale to supported value."""
    lang = locale.split("-", maxsplit=1)[0].split("_", maxsplit=1)[0].lower()
    return lang if lang in _SUPPORTED_LOCALES else _DEFAULT_LOCALE


def get_channel_type_translation(*, channel_type: str, locale: str = "en") -> str | None:
    """Return human-readable translation for a channel type."""
    lang = _get_locale(locale=locale)
    return _store.get(category="channel_types", locale=lang).get(channel_type.lower())


def get_device_model_description(
    *,
    model: str,
    sub_model: str | None = None,
    locale: str = "en",
) -> str | None:
    """
    Return human-readable description for a device model.

    Try full model ID first (e.g. ``HmIP-SWDO``), then fall back
    to sub_model (e.g. ``PS``, ``SMO``, ``BSM``) which corresponds
    to the ``SUBTYPE`` field in the device description.
    """
    lang = _get_locale(locale=locale)
    translations = _store.get(category="device_models", locale=lang)

    if (label := translations.get(model.lower())) is not None:
        return label

    # Fall back to sub_model (SUBTYPE) - many HmIP devices use abbreviated keys
    if sub_model:
        return translations.get(sub_model.lower())

    return None


def get_device_icon(*, model: str) -> str | None:
    """Return icon filename for a device model."""
    return _store.get_locale_independent(category="device_icons").get(model.lower())


def _match_link_prefix(*, parameter: str) -> tuple[str, str] | None:
    """Match a LINK paramset prefix and return (prefix, base_name) or None."""
    lower = parameter.lower()
    for prefix in _LINK_PREFIX_LABELS:
        if lower.startswith(prefix):
            return prefix, lower[len(prefix) :]
    return None


def get_parameter_translation(
    *,
    parameter: str,
    channel_type: str | None = None,
    locale: str = "en",
) -> str | None:
    """
    Return human-readable translation for a parameter.

    Try channel-specific lookup first (CHANNEL_TYPE|PARAMETER),
    then fall back to global parameter lookup, then strip
    SHORT_/LONG_ prefixes (used by LINK paramsets) and retry
    with a parenthesized suffix appended.
    """
    lang = _get_locale(locale=locale)
    translations = _store.get(category="parameters", locale=lang)
    param_lower = parameter.lower()
    ct_lower = channel_type.lower() if channel_type else None

    # Try channel-specific first
    if ct_lower and (label := translations.get(f"{ct_lower}|{param_lower}")) is not None:
        return label

    # Fall back to global
    if (label := translations.get(param_lower)) is not None:
        return label

    # Strip SHORT_/LONG_ prefix (LINK paramset parameters) and retry
    if (match := _match_link_prefix(parameter=param_lower)) is not None:
        prefix, base = match
        base_label: str | None = None
        if ct_lower and (label := translations.get(f"{ct_lower}|{base}")) is not None:
            base_label = label
        else:
            base_label = translations.get(base)
        if base_label is not None:
            return f"{base_label} ({_LINK_PREFIX_LABELS[prefix][lang]})"

    return None


def get_parameter_help(
    *,
    parameter: str,
    locale: str = "en",
) -> str | None:
    """Return Markdown-formatted help text for a parameter."""
    lang = _get_locale(locale=locale)
    translations = _store.get(category="parameter_help", locale=lang)
    param_lower = parameter.lower()

    if (label := translations.get(param_lower)) is not None:
        return label

    # Strip SHORT_/LONG_ prefix (LINK paramset parameters) and retry
    if (match := _match_link_prefix(parameter=param_lower)) is not None:
        _prefix, base = match
        return translations.get(base)

    return None


def get_parameter_value_translation(
    *,
    parameter: str,
    value: str,
    channel_type: str | None = None,
    locale: str = "en",
) -> str | None:
    """
    Return human-readable translation for a parameter enum value.

    Try channel-specific lookup first (CHANNEL_TYPE|PARAMETER=VALUE),
    then fall back to global lookup (PARAMETER=VALUE), then strip
    SHORT_/LONG_ prefixes and retry, then fall back to value-only
    lookup (shortest match for VALUE).
    """
    lang = _get_locale(locale=locale)
    translations = _store.get(category="parameter_values", locale=lang)
    param_lower = parameter.lower()
    value_lower = value.lower()
    ct_lower = channel_type.lower() if channel_type else None

    # Try channel-specific first
    if ct_lower and (label := translations.get(f"{ct_lower}|{param_lower}={value_lower}")) is not None:
        return label

    # Fall back to parameter-specific
    if (label := translations.get(f"{param_lower}={value_lower}")) is not None:
        return label

    # Strip SHORT_/LONG_ prefix (LINK paramset parameters) and retry
    if (match := _match_link_prefix(parameter=param_lower)) is not None:
        _prefix, base = match
        if ct_lower and (label := translations.get(f"{ct_lower}|{base}={value_lower}")) is not None:
            return label
        if (label := translations.get(f"{base}={value_lower}")) is not None:
            return label

    # Fall back to value-only (generic, shortest translation)
    return _store.get_value_fallback(value=value, locale=lang)
