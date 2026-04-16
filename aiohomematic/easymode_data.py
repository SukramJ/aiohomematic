# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Loader for CCU easymode metadata.

Provide access to extracted easymode data (parameter groups, profiles, presets,
subsets, cross-validations) from CCU WebUI TCL configuration files.

The data is stored as a single gzip-compressed JSON archive in
``ccu_data/easymode_extract.json.gz``, produced by
``script/extract_ccu_easymodes.py``.

All public functions are pure dict lookups after first access (no I/O),
making them safe to call from the asyncio event loop. Thread safety is
ensured via double-checked locking during lazy initialization.

Public API of this module is defined by __all__.
"""

from dataclasses import dataclass, field
import gzip
import json
import logging
import pkgutil
import threading
from typing import Any, Final

__all__ = [
    "MASTER_SENDER_TYPE",
    "ChannelMetadata",
    "ConditionalVisibilityRule",
    "CrossValidationRule",
    "MasterProfileDef",
    "OptionPresetDef",
    "OptionPresetEntry",
    "ParameterGroupDef",
    "ProfileParamConstraint",
    "SubsetDef",
    "get_channel_metadata",
    "get_cross_validation_rules",
    "get_option_preset",
    "get_option_presets",
]

_LOGGER: Final = logging.getLogger(__name__)
_PACKAGE: Final = "aiohomematic"

# Sender type key for MASTER paramset metadata (as opposed to LINK easymode profiles).
# Used by the extraction script and downstream consumers to access MASTER-specific
# parameter groups, ordering, option presets, and conditional visibility rules.
MASTER_SENDER_TYPE: Final = "_MASTER"


# ---------------------------------------------------------------------------
# Dataclasses (frozen for thread safety and immutability)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ProfileParamConstraint:
    """Constraint for a parameter within an easymode profile."""

    constraint_type: str  # "fixed", "list", or "range"
    value: int | float | str | None = None
    values: tuple[int | float | str, ...] | None = None
    default: int | float | None = None
    min_value: int | float | None = None
    max_value: int | float | None = None


@dataclass(frozen=True, slots=True)
class MasterProfileDef:
    """Easymode profile definition for a MASTER paramset."""

    id: int
    name_key: str
    params: dict[str, ProfileParamConstraint] = field(default_factory=dict)
    description: str = ""
    visible_params: tuple[str, ...] | None = None
    hidden_params: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class SubsetDef:
    """Subset definition grouping multiple parameters into a single choice."""

    id: int
    name_key: str
    member_params: tuple[str, ...]
    values: dict[str, int | float | str]
    option_value: int | float | None = None


@dataclass(frozen=True, slots=True)
class ConditionalVisibilityRule:
    """Rule for conditionally showing/hiding parameters."""

    trigger: str
    trigger_value: int | float | str
    show: tuple[str, ...] = ()
    hide: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ParameterGroupDef:
    """Group of related parameters for UI display."""

    id: str
    label: dict[str, str]  # locale -> label
    parameters: tuple[str, ...]
    label_key: str | None = None  # JS translation key for label resolution


@dataclass(frozen=True, slots=True)
class OptionPresetEntry:
    """Single preset value in an option set."""

    value: int | float
    label: str | None = None  # Direct label text
    label_key: str | None = None  # Localization key reference


@dataclass(frozen=True, slots=True)
class OptionPresetDef:
    """Definition of an option preset set (e.g. BLIND_LEVEL, DELAY)."""

    presets: tuple[OptionPresetEntry, ...]
    allow_custom: bool = False


@dataclass(frozen=True, slots=True)
class CrossValidationRule:
    """Cross-parameter validation rule."""

    id: str
    applies_to_params: tuple[str, ...]
    rule: str  # "gte", "lte", "between", "not_equal"
    error_key: str
    param_a: str | None = None
    param_b: str | None = None
    param: str | None = None
    min_param: str | None = None
    max_param: str | None = None


@dataclass(frozen=True, slots=True)
class SenderTypeMetadata:
    """Easymode metadata for a specific sender→receiver channel type pair."""

    profiles: tuple[MasterProfileDef, ...] = ()
    subsets: tuple[SubsetDef, ...] = ()
    parameter_order: tuple[str, ...] = ()
    option_presets: dict[str, str] = field(default_factory=dict)  # param -> preset_type
    conditional_visibility: tuple[ConditionalVisibilityRule, ...] = ()
    parameter_groups: tuple[ParameterGroupDef, ...] = ()
    cross_validation_rule_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ChannelMetadata:
    """Easymode metadata for a receiver channel type."""

    channel_type: str
    sender_types: dict[str, SenderTypeMetadata] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


class _EasymodeStore:
    """Thread-safe, lazily loaded store for easymode metadata."""

    __slots__ = (
        "_channel_metadata",
        "_cross_validation_rules",
        "_loaded",
        "_lock",
        "_option_presets",
    )

    _ARCHIVE_RESOURCE: Final = "ccu_data/easymode_extract.json.gz"

    def __init__(self) -> None:
        self._channel_metadata: Final[dict[str, ChannelMetadata]] = {}
        self._option_presets: Final[dict[str, OptionPresetDef]] = {}
        self._cross_validation_rules: list[CrossValidationRule] = []
        self._loaded: bool = False
        self._lock: Final = threading.Lock()

    @staticmethod
    def _load_archive() -> dict[str, Any] | None:
        """Load the gzip-compressed JSON archive from the package."""
        try:
            if not (data_bytes := pkgutil.get_data(package=_PACKAGE, resource=_EasymodeStore._ARCHIVE_RESOURCE)):
                return None
            raw_json = gzip.decompress(data_bytes)
            result: dict[str, Any] = json.loads(raw_json)
        except (FileNotFoundError, json.JSONDecodeError, OSError) as err:
            _LOGGER.debug("Failed to load %s/%s: %s", _PACKAGE, _EasymodeStore._ARCHIVE_RESOURCE, err)
            return None
        else:
            return result

    def get_channel_metadata(self, *, channel_type: str) -> ChannelMetadata | None:
        """Return metadata for a channel type."""
        self._ensure_loaded()
        return self._channel_metadata.get(channel_type)

    def get_cross_validation_rules(self) -> list[CrossValidationRule]:
        """Return all cross-validation rules."""
        self._ensure_loaded()
        return list(self._cross_validation_rules)

    def get_option_preset(self, *, preset_type: str) -> OptionPresetDef | None:
        """Return a single option preset definition by type."""
        self._ensure_loaded()
        return self._option_presets.get(preset_type)

    def get_option_presets(self) -> dict[str, OptionPresetDef]:
        """Return all option preset definitions."""
        self._ensure_loaded()
        return dict(self._option_presets)

    def _ensure_loaded(self) -> None:
        """Load all data from archive if not yet loaded (double-checked locking)."""
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return  # type: ignore[unreachable]
            if (archive := self._load_archive()) is not None:
                self._parse_channel_metadata(raw=archive.get("channel_metadata", {}))
                self._parse_option_presets(raw=archive.get("option_presets", {}))
                self._parse_cross_validations(raw=archive.get("cross_validations", {}))
            self._loaded = True

    def _parse_channel_metadata(self, *, raw: dict[str, Any]) -> None:
        """Parse all channel metadata from the archive."""
        for channel_type, channel_data in raw.items():
            sender_types: dict[str, SenderTypeMetadata] = {}
            for st_name, st_data in channel_data.get("sender_types", {}).items():
                sender_types[st_name] = self._parse_sender_type(data=st_data)
            self._channel_metadata[channel_type] = ChannelMetadata(
                channel_type=channel_type,
                sender_types=sender_types,
            )
        _LOGGER.debug("Loaded %d channel metadata entries", len(self._channel_metadata))

    def _parse_cross_validations(self, *, raw: dict[str, Any]) -> None:
        """Parse cross-validation rules from the archive."""
        self._cross_validation_rules = [
            CrossValidationRule(
                id=r["id"],
                applies_to_params=tuple(r["applies_to_params"]),
                rule=r["rule"],
                error_key=r["error_key"],
                param_a=r.get("param_a"),
                param_b=r.get("param_b"),
                param=r.get("param"),
                min_param=r.get("min_param"),
                max_param=r.get("max_param"),
            )
            for r in raw.get("rules", [])
        ]
        _LOGGER.debug("Loaded %d cross-validation rules", len(self._cross_validation_rules))

    def _parse_option_presets(self, *, raw: dict[str, Any]) -> None:
        """Parse option presets from the archive."""
        for preset_type, data in raw.items():
            presets = tuple(
                OptionPresetEntry(
                    value=p.get("value", 0),
                    label=p.get("label"),
                    label_key=p.get("label_key"),
                )
                for p in data.get("presets", [])
            )
            self._option_presets[preset_type] = OptionPresetDef(
                presets=presets,
                allow_custom=data.get("allow_custom", False),
            )
        _LOGGER.debug("Loaded %d option preset types", len(self._option_presets))

    def _parse_profile(self, *, data: dict[str, Any]) -> MasterProfileDef:
        """Parse a single profile definition."""
        params: dict[str, ProfileParamConstraint] = {}
        for pname, pdata in data.get("params", {}).items():
            ct = pdata.get("constraint_type", "fixed")
            params[pname] = ProfileParamConstraint(
                constraint_type=ct,
                value=pdata.get("value"),
                values=tuple(pdata["values"]) if "values" in pdata else None,
                default=pdata.get("default"),
                min_value=pdata.get("min_value"),
                max_value=pdata.get("max_value"),
            )
        return MasterProfileDef(
            id=data["id"],
            name_key=data["name_key"],
            params=params,
            description=data.get("description", ""),
            visible_params=tuple(data["visible_params"]) if data.get("visible_params") else None,
            hidden_params=tuple(data["hidden_params"]) if data.get("hidden_params") else None,
        )

    def _parse_sender_type(self, *, data: dict[str, Any]) -> SenderTypeMetadata:
        """Parse sender type metadata from raw JSON data."""
        profiles = tuple(self._parse_profile(data=p) for p in data.get("profiles", []))
        subsets = tuple(
            SubsetDef(
                id=s["id"],
                name_key=s["name_key"],
                member_params=tuple(s["member_params"]),
                values=s["values"],
                option_value=s.get("option_value"),
            )
            for s in data.get("subsets", [])
        )
        conditional_visibility = tuple(
            ConditionalVisibilityRule(
                trigger=cv["trigger"],
                trigger_value=cv["trigger_value"],
                show=tuple(cv.get("show", ())),
                hide=tuple(cv.get("hide", ())),
            )
            for cv in data.get("conditional_visibility", [])
        )
        parameter_groups = tuple(
            ParameterGroupDef(
                id=pg["id"],
                label=pg.get("label", {}),
                parameters=tuple(pg["parameters"]),
                label_key=pg.get("label_key"),
            )
            for pg in data.get("parameter_groups", [])
        )
        return SenderTypeMetadata(
            profiles=profiles,
            subsets=subsets,
            parameter_order=tuple(data.get("parameter_order", [])),
            option_presets=data.get("option_presets", {}),
            conditional_visibility=conditional_visibility,
            parameter_groups=parameter_groups,
            cross_validation_rule_ids=tuple(data.get("cross_validation_rule_ids", [])),
        )


# Module-level singleton
_store: Final = _EasymodeStore()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_channel_metadata(*, channel_type: str) -> ChannelMetadata | None:
    """Return easymode metadata for a receiver channel type."""
    return _store.get_channel_metadata(channel_type=channel_type)


def get_option_presets() -> dict[str, OptionPresetDef]:
    """Return all option preset definitions."""
    return _store.get_option_presets()


def get_option_preset(*, preset_type: str) -> OptionPresetDef | None:
    """Return a single option preset definition by type name."""
    return _store.get_option_preset(preset_type=preset_type)


def get_cross_validation_rules() -> list[CrossValidationRule]:
    """Return all cross-parameter validation rules."""
    return _store.get_cross_validation_rules()
