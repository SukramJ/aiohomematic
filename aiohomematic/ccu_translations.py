# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Loader for CCU-sourced translation data.

Provide access to human-readable translations for channel types, device models,
parameter names, and parameter enum values extracted from the OpenCCU WebUI.

Both the extracted archive and the curated custom overrides ship with the
`openccu-data <https://github.com/sukramj/openccu-data>`_ package
(``openccu_data/data/translation_extract.json.gz`` and
``openccu_data/data/translation_custom/*.json``) and are accessed here via
``importlib.resources``.  At load time the two layers are merged: custom keys
override or supplement extracted keys.

All public functions are pure dict lookups after first access (no I/O),
making them safe to call from the asyncio event loop. Thread safety is
ensured via double-checked locking during lazy initialization.

Public API of this module is defined by __all__.
"""

import contextlib
import gzip
from importlib.resources import files
import json
import logging
import threading
from typing import Any, Final

__all__ = [
    "get_channel_type_translation",
    "get_device_icon",
    "get_device_model_description",
    "get_parameter_help",
    "get_parameter_translation",
    "get_parameter_value_translation",
    "get_ui_label_translation",
    "resolve_channel_type",
]

_LOGGER: Final = logging.getLogger(__name__)
_DATA_PACKAGE: Final = "openccu_data.data"
_CUSTOM_PACKAGE: Final = "openccu_data.data.translation_custom"

_SUPPORTED_LOCALES: Final = frozenset({"de", "en"})
_DEFAULT_LOCALE: Final = "en"
_CATEGORIES: Final = (
    "channel_types",
    "device_models",
    "parameter_help",
    "parameters",
    "parameter_values",
    "ui_labels",
)
_LOCALE_INDEPENDENT_CATEGORIES: Final = ("device_icons",)
_EXTRACT_ARCHIVE_FILENAME: Final = "translation_extract.json.gz"

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

    @staticmethod
    def _load_extract_archive() -> dict[str, Any]:
        """Load the gzip-compressed translation extract archive from openccu-data."""
        try:
            data_bytes = files(_DATA_PACKAGE).joinpath(_EXTRACT_ARCHIVE_FILENAME).read_bytes()
            raw_json = gzip.decompress(data_bytes)
            result: dict[str, Any] = json.loads(raw_json)
        except (FileNotFoundError, ModuleNotFoundError, json.JSONDecodeError, OSError) as err:
            _LOGGER.debug("Failed to load %s/%s: %s", _DATA_PACKAGE, _EXTRACT_ARCHIVE_FILENAME, err)
            return {}
        else:
            return result

    @staticmethod
    def _merge_custom_file(*, target: dict[str, str], filename: str) -> None:
        """Merge a custom override JSON file from openccu-data into the target dict."""
        try:
            data_bytes = files(_CUSTOM_PACKAGE).joinpath(filename).read_bytes()
            raw: dict[str, str] = json.loads(data_bytes)
            target.update({k.lower(): v for k, v in raw.items()})
        except (FileNotFoundError, ModuleNotFoundError, json.JSONDecodeError) as err:
            _LOGGER.debug("Failed to load %s/%s: %s", _CUSTOM_PACKAGE, filename, err)

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

        Load extracted translations from the gzip archive, then merge
        custom overrides from individual JSON files on top so that
        custom keys override or supplement extracted keys.

        Use pkgutil.get_data() instead of Path.read_text() to avoid
        blocking file I/O detection in Home Assistant's event loop.
        """
        with self._lock:
            if self._loaded:
                return
            extract_data = self._load_extract_archive()
            for category in _CATEGORIES:
                for locale in _SUPPORTED_LOCALES:
                    key = f"{category}_{locale}"
                    merged: dict[str, str] = {}
                    # Layer 1: extracted data from archive
                    if (extracted := extract_data.get(key)) is not None:
                        merged.update({k.lower(): v for k, v in extracted.items()})
                    # Layer 2: custom overrides from individual files
                    self._merge_custom_file(target=merged, filename=f"{key}.json")
                    self._data[key] = merged
            # Load locale-independent categories (single file, no locale suffix)
            for category in _LOCALE_INDEPENDENT_CATEGORIES:
                li_merged: dict[str, str] = {}
                if (extracted := extract_data.get(category)) is not None:
                    li_merged.update({k.lower(): v for k, v in extracted.items()})
                self._merge_custom_file(target=li_merged, filename=f"{category}.json")
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
    use_fallback: bool = True,
) -> str | None:
    """
    Return human-readable translation for a parameter enum value.

    Try channel-specific lookup first (CHANNEL_TYPE|PARAMETER=VALUE),
    then fall back to global lookup (PARAMETER=VALUE), then strip
    SHORT_/LONG_ prefixes and retry, then fall back to value-only
    lookup (shortest match for VALUE).

    If use_fallback is False, skip the value-only fallback and only
    try parameter-specific lookups.
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

    if not use_fallback:
        return None

    # Fall back to value-only (generic, shortest translation)
    return _store.get_value_fallback(value=value, locale=lang)


def get_ui_label_translation(
    *,
    label_key: str,
    locale: str = "en",
) -> str | None:
    """
    Return translated text for a UI label key.

    UI label keys are JavaScript variable names from the CCU WebUI translation
    files (e.g., 'stringTableAutoRelockDelay', 'optionOpenOnly', 'lblRight').
    They are referenced by easymode parameter_groups and option_presets.
    """
    lang = _get_locale(locale=locale)
    return _store.get(category="ui_labels", locale=lang).get(label_key.lower())


def resolve_channel_type(
    *,
    channel_type: str,
    is_hmip: bool = False,
) -> str:
    """
    Resolve the effective channel type for translation lookups.

    The CCU uses the same channel type (e.g., SHUTTER_CONTACT) for both
    HM and HmIP devices, but HmIP devices may have different parameter
    semantics (e.g., position A/B meanings are swapped). The CCU WebUI
    handles this by appending _HMIP to the channel type for translation
    lookups. This function replicates that behavior.
    """
    if not is_hmip or not channel_type:
        return channel_type
    hmip_type = f"{channel_type}_HMIP"
    # Check if any translation exists for the _HMIP variant
    for locale in _SUPPORTED_LOCALES:
        translations = _store.get(category="parameters", locale=locale)
        if any(key.startswith(f"{hmip_type.lower()}|") for key in translations):
            return hmip_type
    return channel_type
