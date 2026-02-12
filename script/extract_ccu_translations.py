#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Extract CCU WebUI translations and generate JSON files for aiohomematic.

Parse JavaScript translation files from the OpenCCU/RaspberryMatic WebUI
and the stringtable mapping file, then output structured JSON translation
files for channel types, device models, parameter names, and parameter values.

Usage:
    # From local OCCU checkout (preferred)
    OCCU_PATH=/path/to/occu python script/extract_ccu_translations.py

    # From remote CCU via HTTP
    CCU_URL=https://my-ccu.local python script/extract_ccu_translations.py

    # Custom output directory
    OCCU_PATH=/path/to/occu OUTPUT_DIR=custom/path python script/extract_ccu_translations.py

Environment Variables:
    OCCU_PATH   Path to local OCCU checkout (preferred)
    CCU_URL     URL of a live CCU instance (alternative)
    OUTPUT_DIR  Output directory (default: aiohomematic/translations/ccu_extract)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import ssl
import sys
from urllib.parse import unquote
import urllib.request

# JS translation files to parse (relative to WebUI/www/ for local, or root for HTTP)
_JS_LANG_DIR = "webui/js/lang/{locale}"
_JS_FILES = (
    "translate.lang.stringtable.js",
    "translate.lang.notTranslated.js",
    "translate.lang.label.js",
    "translate.lang.option.js",
    "translate.lang.channelDescription.js",
    "translate.lang.deviceDescription.js",
)

# Stringtable mapping file (same for all locales)
_STRINGTABLE_MAPPING_PATH = "config/stringtable_de.txt"

# Supported locales
_LOCALES = ("de", "en")

# Sentinel keys to exclude
_SENTINEL_KEYS = frozenset({"theEnd", "The END", "dummy", "comment"})

# Default output directory (relative to project root)
_DEFAULT_OUTPUT_DIR = "aiohomematic/translations/ccu_extract"

# Regex to extract the inner JSON object from jQuery.extend(true, langJSON, { "locale": { ... } })
_JQUERY_EXTEND_RE = re.compile(
    r'jQuery\.extend\s*\(\s*true\s*,\s*\w+\s*,\s*\{\s*"(?:de|en)"\s*:\s*(\{.*\})\s*\}\s*\)',
    re.DOTALL,
)

# Regex to find ${templateVar} references
_TEMPLATE_VAR_RE = re.compile(r"\$\{(\w+)\}")


def parse_jquery_extend(content: str) -> dict[str, str]:
    """Extract key-value pairs from a jQuery.extend JavaScript file."""
    match = _JQUERY_EXTEND_RE.search(content)
    if not match:
        return {}

    json_str = match.group(1)

    # Fix JS-specific issues for JSON parsing:
    # Remove trailing commas before }
    json_str = re.sub(r",\s*}", "}", json_str)
    # Remove single-line comments
    json_str = re.sub(r"//.*?$", "", json_str, flags=re.MULTILINE)
    # Handle string concatenation with JS variables ("str" + Identifier.x -> "str")
    json_str = re.sub(r'"\s*\+\s*[A-Za-z_]\w*(?:\.\w+)*', '"', json_str)
    # Handle string concatenation ("a" + "b" -> "ab")
    json_str = re.sub(r'"\s*\+\s*"', "", json_str)

    try:
        raw: dict[str, str] = json.loads(json_str)
    except json.JSONDecodeError as err:
        print(f"  WARNING: JSON parse error: {err}", file=sys.stderr)
        return {}

    # Filter sentinel entries
    return {k: v for k, v in raw.items() if k not in _SENTINEL_KEYS and v}


def clean_value(value: str) -> str:
    """URL-decode, strip HTML, and normalize whitespace."""
    # URL-decode (%FC -> ü, etc.) using Latin-1 encoding
    decoded = unquote(value, encoding="latin-1")
    # Strip HTML tags: <br/> -> space, other tags removed
    decoded = re.sub(r"<br\s*/?>", " ", decoded)
    decoded = re.sub(r"</?\w+[^>]*>", "", decoded)
    # Decode HTML entities
    decoded = decoded.replace("&nbsp;", " ")
    decoded = decoded.replace("&amp;", "&")
    decoded = decoded.replace("&auml;", "ä")
    decoded = decoded.replace("&ouml;", "ö")
    decoded = decoded.replace("&uuml;", "ü")
    decoded = decoded.replace("&Auml;", "Ä")
    decoded = decoded.replace("&Ouml;", "Ö")
    decoded = decoded.replace("&Uuml;", "Ü")
    decoded = decoded.replace("&szlig;", "ß")
    # Normalize whitespace
    decoded = " ".join(decoded.split())
    return decoded.strip()


def parse_stringtable_mapping(content: str) -> dict[str, str]:
    """
    Parse stringtable_de.txt to build KEY -> template_string mapping.

    The template_string may contain one or more ${templateVar} references.
    """
    mapping: dict[str, str] = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        key, template = parts
        template = template.strip()
        if template:
            mapping[key] = template
    return mapping


def resolve_template(template: str, translations: dict[str, str]) -> str | None:
    """
    Resolve all ${templateVar} references in a template string.

    Return None if any variable cannot be resolved.
    """
    unresolved = False

    def replace_var(match: re.Match[str]) -> str:
        nonlocal unresolved
        var_name = match.group(1)
        resolved = translations.get(var_name)
        if resolved is None:
            unresolved = True
            return match.group(0)
        return resolved

    result = _TEMPLATE_VAR_RE.sub(replace_var, template)
    if unresolved:
        return None
    return result


def extract_channel_types(raw: dict[str, str]) -> dict[str, str]:
    """Extract channel type translations, stripping 'chType_' prefix."""
    result: dict[str, str] = {}
    prefix = "chType_"
    for key, value in raw.items():
        if key.startswith(prefix):
            channel_type = key[len(prefix) :]
            cleaned = clean_value(value)
            if cleaned:
                result[channel_type] = cleaned
        elif key not in _SENTINEL_KEYS and key.isupper():
            # HmIP group channel types (e.g. REMOTE_CONTROL, RADIATOR_THERMOSTAT)
            cleaned = clean_value(value)
            if cleaned:
                result[key] = cleaned
    return result


def extract_device_models(raw: dict[str, str]) -> dict[str, str]:
    """Extract device model translations."""
    result: dict[str, str] = {}
    for key, value in raw.items():
        cleaned = clean_value(value)
        if cleaned:
            result[key] = cleaned
    return result


def resolve_parameter_translations(
    stringtable_mapping: dict[str, str],
    all_translations: dict[str, str],
) -> tuple[dict[str, str], dict[str, str], int]:
    """
    Resolve stringtable mapping through merged translation dictionaries.

    Return (parameters, parameter_values, unresolved_count).
    """
    parameters: dict[str, str] = {}
    parameter_values: dict[str, str] = {}
    unresolved_count = 0

    for key, template in stringtable_mapping.items():
        resolved = resolve_template(template, all_translations)
        if resolved is None:
            unresolved_count += 1
            continue
        cleaned = clean_value(resolved)
        if not cleaned:
            continue

        if "=" in key:
            parameter_values[key] = cleaned
        else:
            parameters[key] = cleaned

    return parameters, parameter_values, unresolved_count


def load_local_file(occu_path: Path, relative_path: str) -> str:
    """Load a file from the local OCCU checkout."""
    file_path = occu_path / "WebUI" / "www" / relative_path
    # Some files use ISO-8859-1 encoding (e.g. notTranslated.js)
    try:
        return file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return file_path.read_text(encoding="iso-8859-1")


def fetch_remote_file(ccu_url: str, relative_path: str) -> str:
    """Fetch a file from a remote CCU via HTTP."""
    url = f"{ccu_url.rstrip('/')}/{relative_path}"
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(url, context=ctx) as response:
        raw: bytes = response.read()
        # Some CCU files use ISO-8859-1 encoding
        try:
            result: str = raw.decode("utf-8")
        except UnicodeDecodeError:
            result = raw.decode("iso-8859-1")
        return result


def write_json(output_dir: Path, filename: str, data: dict[str, str]) -> int:
    """Write sorted JSON file with lowercase keys. Return entry count."""
    sorted_data = dict(sorted((k.lower(), v) for k, v in data.items()))
    file_path = output_dir / filename
    file_path.write_text(
        json.dumps(sorted_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return len(sorted_data)


def load_sources_local(
    occu_path: Path,
) -> tuple[dict[str, dict[str, dict[str, str]]], dict[str, str]]:
    """
    Load all translation sources from a local OCCU checkout.

    Return (locale_data, stringtable_mapping).
    """
    locale_data: dict[str, dict[str, dict[str, str]]] = {}

    for locale in _LOCALES:
        locale_data[locale] = {}
        lang_dir = _JS_LANG_DIR.format(locale=locale)
        for js_file in _JS_FILES:
            relative_path = f"{lang_dir}/{js_file}"
            try:
                content = load_local_file(occu_path, relative_path)
                parsed = parse_jquery_extend(content)
                locale_data[locale][js_file] = parsed
                print(f"  {locale}/{js_file}: {len(parsed)} entries")
            except FileNotFoundError:
                print(f"  WARNING: {relative_path} not found, skipping", file=sys.stderr)
                locale_data[locale][js_file] = {}

    # Load stringtable mapping
    mapping_content = load_local_file(occu_path, _STRINGTABLE_MAPPING_PATH)
    stringtable_mapping = parse_stringtable_mapping(mapping_content)
    print(f"  stringtable mapping: {len(stringtable_mapping)} entries")

    return locale_data, stringtable_mapping


def load_sources_remote(
    ccu_url: str,
) -> tuple[dict[str, dict[str, dict[str, str]]], dict[str, str]]:
    """
    Load all translation sources from a remote CCU via HTTP.

    Return (locale_data, stringtable_mapping).
    """
    locale_data: dict[str, dict[str, dict[str, str]]] = {}

    for locale in _LOCALES:
        locale_data[locale] = {}
        lang_dir = _JS_LANG_DIR.format(locale=locale)
        for js_file in _JS_FILES:
            relative_path = f"{lang_dir}/{js_file}"
            try:
                content = fetch_remote_file(ccu_url, relative_path)
                parsed = parse_jquery_extend(content)
                locale_data[locale][js_file] = parsed
                print(f"  {locale}/{js_file}: {len(parsed)} entries")
            except Exception as err:
                print(f"  WARNING: Failed to fetch {relative_path}: {err}", file=sys.stderr)
                locale_data[locale][js_file] = {}

    # Load stringtable mapping
    try:
        mapping_content = fetch_remote_file(ccu_url, _STRINGTABLE_MAPPING_PATH)
        stringtable_mapping = parse_stringtable_mapping(mapping_content)
        print(f"  stringtable mapping: {len(stringtable_mapping)} entries")
    except Exception as err:
        print(f"  WARNING: Failed to fetch stringtable mapping: {err}", file=sys.stderr)
        stringtable_mapping = {}

    return locale_data, stringtable_mapping


def merge_translation_dicts(
    locale_data: dict[str, dict[str, str]],
) -> dict[str, str]:
    """Merge all translation JS files for a locale into a single lookup dict."""
    merged: dict[str, str] = {}
    for js_file in (
        "translate.lang.stringtable.js",
        "translate.lang.label.js",
        "translate.lang.option.js",
        "translate.lang.notTranslated.js",
    ):
        if js_file in locale_data:
            merged.update(locale_data[js_file])
    return merged


def main() -> int:
    """Run the extraction pipeline."""
    occu_path = os.environ.get("OCCU_PATH")
    ccu_url = os.environ.get("CCU_URL")
    output_dir_str = os.environ.get("OUTPUT_DIR", _DEFAULT_OUTPUT_DIR)

    if not occu_path and not ccu_url:
        print(
            "ERROR: Set OCCU_PATH (local checkout) or CCU_URL (remote CCU) environment variable.",
            file=sys.stderr,
        )
        return 1

    # Resolve output directory relative to project root
    project_root = Path(__file__).resolve().parent.parent
    output_dir = project_root / output_dir_str
    output_dir.mkdir(parents=True, exist_ok=True)

    # Phase 1: Load sources
    if occu_path:
        resolved_occu = Path(occu_path).resolve()
        print(f"Loading sources from {resolved_occu} ...")
        locale_data, stringtable_mapping = load_sources_local(resolved_occu)
    else:
        assert ccu_url is not None
        print(f"Loading sources from {ccu_url} ...")
        locale_data, stringtable_mapping = load_sources_remote(ccu_url)

    print()

    # Phase 2 & 3: Process and output per locale
    for locale in _LOCALES:
        ld = locale_data[locale]
        print(f"Processing locale '{locale}'...")

        # Channel types
        channel_raw = ld.get("translate.lang.channelDescription.js", {})
        channel_types = extract_channel_types(channel_raw)
        count = write_json(output_dir, f"channel_types_{locale}.json", channel_types)
        print(f"  channel_types_{locale}.json: {count} entries")

        # Device models
        device_raw = ld.get("translate.lang.deviceDescription.js", {})
        device_models = extract_device_models(device_raw)
        count = write_json(output_dir, f"device_models_{locale}.json", device_models)
        print(f"  device_models_{locale}.json: {count} entries")

        # Parameter names and values (resolved via stringtable mapping)
        all_translations = merge_translation_dicts(ld)
        parameters, parameter_values, unresolved = resolve_parameter_translations(stringtable_mapping, all_translations)
        count = write_json(output_dir, f"parameters_{locale}.json", parameters)
        print(f"  parameters_{locale}.json: {count} entries")
        count = write_json(output_dir, f"parameter_values_{locale}.json", parameter_values)
        print(f"  parameter_values_{locale}.json: {count} entries")

        if unresolved:
            print(f"  ({unresolved} unresolved template references)")

    print(f"\nDone. Translations written to {output_dir}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
