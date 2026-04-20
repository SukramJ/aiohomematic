#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Lint script for translation_custom override files.

Validate that every key in aiohomematic/ccu_data/translation_custom/*.json
either:

1. Exists in the extracted translation archive (real override or supplement
   for an already-known CCU key),
2. Uses the channel-scoped ``channel_type|parameter`` format,
3. Uses the parameter value format ``param=value`` or ``channel|param=value``,
4. Names an aiohomematic-internal parameter (from the ``Parameter`` enum
   in aiohomematic/const.py — e.g. calculated or combined data points that
   the CCU does not know).

If none of these apply, the key is almost certainly a typo (e.g.
``door_lock_disable_acoustic_channelstate`` where the author meant to write
the channel-scoped ``door_lock_transceiver|disable_acoustic_channelstate``
or simply the global ``disable_acoustic_channelstate``). The script reports
such keys with a suggestion and exits non-zero.

Usage:
    python script/lint_translation_custom.py

Exit codes:
    0 - All custom override keys are well-formed
    1 - One or more custom keys look like typos (see output for details)
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
import re
import sys
from typing import Final

_PROJECT_ROOT: Final = Path(__file__).resolve().parent.parent
_ARCHIVE_PATH: Final = _PROJECT_ROOT / "aiohomematic" / "ccu_data" / "translation_extract.json.gz"
_CUSTOM_DIR: Final = _PROJECT_ROOT / "aiohomematic" / "ccu_data" / "translation_custom"
_CONST_PATH: Final = _PROJECT_ROOT / "aiohomematic" / "const.py"

# Map custom-file stem -> archive key
_FILES_TO_CHECK: Final[tuple[tuple[str, str], ...]] = (
    ("parameters_de", "parameters_de"),
    ("parameters_en", "parameters_en"),
    ("parameter_values_de", "parameter_values_de"),
    ("parameter_values_en", "parameter_values_en"),
)

_PARAM_ENUM_RE: Final = re.compile(r'^\s+([A-Z][A-Z0-9_]+)\s*=\s*"([A-Z][A-Z0-9_]+)"', re.MULTILINE)


def _load_archive() -> dict[str, dict[str, str]]:
    """Load the gzip-compressed translation extract archive."""
    with gzip.open(_ARCHIVE_PATH, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def _load_parameter_enum_values() -> set[str]:
    """Return lowercase Parameter enum values from aiohomematic/const.py."""
    source = _CONST_PATH.read_text(encoding="utf-8")
    return {match.group(2).lower() for match in _PARAM_ENUM_RE.finditer(source)}


def _collect_channel_prefixes(archive: dict[str, dict[str, str]]) -> set[str]:
    """Return all known channel-type prefixes (lowercase)."""
    prefixes: set[str] = set()
    for locale in ("de", "en"):
        for key in archive.get(f"parameters_{locale}", {}):
            if "|" in key:
                prefixes.add(key.split("|", 1)[0].lower())
        for key in archive.get(f"channel_types_{locale}", {}):
            prefixes.add(key.lower())
    return prefixes


def _collect_known_parameters(archive: dict[str, dict[str, str]]) -> set[str]:
    """
    Return all known CCU parameter names (lowercase).

    Includes global keys (no pipe) and the right-hand side of every
    channel-scoped key, so that a custom override for a channel-specific
    parameter can also be written as a global supplement.
    """
    known: set[str] = set()
    for locale in ("de", "en"):
        for key in archive.get(f"parameters_{locale}", {}):
            if "|" in key:
                known.add(key.split("|", 1)[1].lower())
            else:
                known.add(key.lower())
    return known


def _suggest_fix(
    *,
    key: str,
    archive_keys: set[str],
    param_enum: set[str],
    channel_prefixes: set[str],
) -> str | None:
    """
    Return a human-readable suggestion if the key looks like a typo.

    The main class of typo we want to catch is ``channel_prefix_parameter``
    written with an underscore where a pipe ``|`` was required.
    """
    kl = key.lower()
    for prefix in sorted(channel_prefixes, key=len, reverse=True):
        stem = f"{prefix}_"
        if not kl.startswith(stem):
            continue
        remainder = kl[len(stem) :]
        if not remainder:
            continue
        if remainder in archive_keys or remainder in param_enum:
            scoped = f"{prefix}|{remainder}"
            return (
                f"looks like a typo. The stem {remainder!r} is a known parameter; "
                f"use the global key {remainder!r} or the channel-scoped key {scoped!r}."
            )
    return None


def _validate_file(
    *,
    custom_path: Path,
    archive_section: dict[str, str],
    param_enum: set[str],
    channel_prefixes: set[str],
    known_params: set[str],
) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for the given custom file."""
    with custom_path.open(encoding="utf-8") as fh:
        custom: dict[str, str] = json.load(fh)

    archive_keys = {k.lower() for k in archive_section}
    errors: list[str] = []
    warnings: list[str] = []

    for raw_key, raw_value in custom.items():
        key = raw_key.lower()

        # Noop: identical to extract - flag as warning so the file stays tidy.
        if archive_section.get(raw_key) == raw_value or archive_section.get(key) == raw_value:
            warnings.append(f"{custom_path.name}: {raw_key!r} is identical to the extract value (noop override).")
            continue
        # Channel-scoped or value-scoped keys are always accepted as supplements.
        if "|" in key or "=" in key:
            continue
        # Key already present in the same-section archive (real override).
        if key in archive_keys:
            continue
        # Internal aiohomematic parameter (Parameter enum member) or a known
        # CCU parameter name reused as a global supplement.
        if key in param_enum or key in known_params:
            continue
        # Potential typo — report as error if we can suggest a fix.
        if (
            suggestion := _suggest_fix(
                key=key,
                archive_keys=archive_keys,
                param_enum=param_enum,
                channel_prefixes=channel_prefixes,
            )
        ) is not None:
            errors.append(f"{custom_path.name}: {raw_key!r} {suggestion}")

    return errors, warnings


def main() -> int:
    """Run the translation_custom lint."""
    if not _ARCHIVE_PATH.is_file():
        print(f"ERROR: Archive not found: {_ARCHIVE_PATH}", file=sys.stderr)
        return 1

    archive = _load_archive()
    param_enum = _load_parameter_enum_values()
    channel_prefixes = _collect_channel_prefixes(archive)
    known_params = _collect_known_parameters(archive)

    all_errors: list[str] = []
    all_warnings: list[str] = []
    for file_stem, archive_key in _FILES_TO_CHECK:
        custom_path = _CUSTOM_DIR / f"{file_stem}.json"
        if not custom_path.is_file():
            continue
        section = archive.get(archive_key, {})
        errors, warnings = _validate_file(
            custom_path=custom_path,
            archive_section=section,
            param_enum=param_enum,
            channel_prefixes=channel_prefixes,
            known_params=known_params,
        )
        all_errors.extend(errors)
        all_warnings.extend(warnings)

    if all_warnings:
        print(f"translation_custom: {len(all_warnings)} warning(s):")
        for warning in all_warnings:
            print(f"  - {warning}")

    if all_errors:
        print(f"\ntranslation_custom: {len(all_errors)} error(s):", file=sys.stderr)
        for err in all_errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print("translation_custom: all keys well-formed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
