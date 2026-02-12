# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Loader for CCU-sourced translation data.

Provide access to human-readable labels for channel types, device models,
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

import json
import logging
from pathlib import Path
import threading
from typing import Final

__all__ = [
    "get_channel_type_label",
    "get_device_model_label",
    "get_parameter_label",
    "get_parameter_value_label",
]

_LOGGER: Final = logging.getLogger(__name__)
_TRANSLATIONS_DIR: Final = Path(__file__).parent / "translations"
_EXTRACT_DIR: Final = _TRANSLATIONS_DIR / "ccu_extract"
_CUSTOM_DIR: Final = _TRANSLATIONS_DIR / "ccu_custom"

_SUPPORTED_LOCALES: Final = frozenset({"de", "en"})
_DEFAULT_LOCALE: Final = "en"
_CATEGORIES: Final = ("channel_types", "device_models", "parameters", "parameter_values")


class _TranslationStore:
    """
    Thread-safe, lazily loaded store for CCU translation data.

    Load all JSON files on first access and serve from memory afterwards.
    After initialization, all lookups are pure dict reads with no I/O,
    making them safe to call from the asyncio event loop.
    """

    __slots__ = ("_data", "_loaded", "_lock")

    def __init__(self) -> None:
        self._data: Final[dict[str, dict[str, str]]] = {}
        self._loaded: bool = False
        self._lock: Final = threading.Lock()

    def get(self, *, category: str, locale: str) -> dict[str, str]:
        """Return translation dict for category and locale."""
        if not self._loaded:
            self._load()
        return self._data.get(f"{category}_{locale}", {})

    def _load(self) -> None:
        """
        Load all translation files (double-checked locking).

        For each category/locale pair, load from ``ccu_extract/`` first,
        then merge ``ccu_custom/`` on top so that custom keys override or
        supplement extracted keys.
        """
        with self._lock:
            if self._loaded:
                return
            for category in _CATEGORIES:
                for locale in _SUPPORTED_LOCALES:
                    key = f"{category}_{locale}"
                    filename = f"{key}.json"
                    merged: dict[str, str] = {}
                    for directory in (_EXTRACT_DIR, _CUSTOM_DIR):
                        file_path = directory / filename
                        try:
                            raw: dict[str, str] = json.loads(file_path.read_text(encoding="utf-8"))
                            merged.update({k.lower(): v for k, v in raw.items()})
                        except (FileNotFoundError, json.JSONDecodeError) as err:
                            _LOGGER.debug("Failed to load %s: %s", file_path, err)
                    self._data[key] = merged
            self._loaded = True


_store: Final = _TranslationStore()


def _get_locale(*, locale: str) -> str:
    """Normalize locale to supported value."""
    lang = locale.split("-", maxsplit=1)[0].split("_")[0].lower()
    return lang if lang in _SUPPORTED_LOCALES else _DEFAULT_LOCALE


def get_channel_type_label(*, channel_type: str, locale: str = "en") -> str | None:
    """Return human-readable label for a channel type."""
    lang = _get_locale(locale=locale)
    return _store.get(category="channel_types", locale=lang).get(channel_type.lower())


def get_device_model_label(
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


def get_parameter_label(
    *,
    parameter: str,
    channel_type: str | None = None,
    locale: str = "en",
) -> str | None:
    """
    Return human-readable label for a parameter.

    Try channel-specific lookup first (CHANNEL_TYPE|PARAMETER),
    then fall back to global parameter lookup.
    """
    lang = _get_locale(locale=locale)
    translations = _store.get(category="parameters", locale=lang)

    # Try channel-specific first
    if channel_type and (label := translations.get(f"{channel_type}|{parameter}".lower())) is not None:
        return label

    # Fall back to global
    return translations.get(parameter.lower())


def get_parameter_value_label(
    *,
    parameter: str,
    value: str,
    channel_type: str | None = None,
    locale: str = "en",
) -> str | None:
    """
    Return human-readable label for a parameter enum value.

    Try channel-specific lookup first (CHANNEL_TYPE|PARAMETER=VALUE),
    then fall back to global lookup (PARAMETER=VALUE).
    """
    lang = _get_locale(locale=locale)
    translations = _store.get(category="parameter_values", locale=lang)

    # Try channel-specific first
    if channel_type and (label := translations.get(f"{channel_type}|{parameter}={value}".lower())) is not None:
        return label

    # Fall back to global
    return translations.get(f"{parameter}={value}".lower())
