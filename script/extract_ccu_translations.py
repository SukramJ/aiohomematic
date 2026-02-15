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
    "translate.lang.extension.js",
    "translate.lang.js",
    "translate.lang.channelDescription.js",
    "translate.lang.deviceDescription.js",
)

# Device-specific MASTER parameter translation files
_MASTER_LANG_DIR = "config/easymodes/MASTER_LANG"

# Stringtable mapping file (same for all locales)
_STRINGTABLE_MAPPING_PATH = "config/stringtable_de.txt"

# PNAME files with direct parameter name -> label mappings (per locale)
_PNAME_DIR = "config/easymodes/etc/localization/{locale}"
_PNAME_FILES = ("PNAME.txt",)

# Easymode TCL directory for extracting parameter -> template var mappings
_EASYMODE_DIR = "config/easymodes"

# Supported locales
_LOCALES = ("de", "en")

# Sentinel keys to exclude
_SENTINEL_KEYS = frozenset({"theEnd", "The END", "dummy", "comment", "noMoreKeys"})

# Default output directory (relative to project root)
_DEFAULT_OUTPUT_DIR = "aiohomematic/translations/ccu_extract"

# Regex to extract the outer JSON object from jQuery.extend(true, langJSON, { ... })
# Specifically targets langJSON (not HMIdentifier or other targets)
# Captures the full outer object: { "de": {...}, "en": {...} }
_JQUERY_EXTEND_RE = re.compile(
    r"jQuery\.extend\s*\(\s*true\s*,\s*langJSON\s*,\s*(\{.*\})\s*\)",
    re.DOTALL,
)

# Regex to find ${templateVar} references
_TEMPLATE_VAR_RE = re.compile(r"\$\{(\w+)\}")

# Regex to parse langJSON alias assignments: langJSON.de.key = langJSON.de.otherKey;
_ALIAS_ASSIGNMENT_RE = re.compile(
    r"langJSON\.(?:de|en)\.(\w+)\s*=\s*langJSON\.(?:de|en)\.(\w+)\s*;",
)


_VALID_JSON_ESCAPES = frozenset(
    {
        '\\"',
        "\\\\",
        "\\/",
        "\\b",
        "\\f",
        "\\n",
        "\\r",
        "\\t",
    }
)


def _fix_js_escape(match: re.Match[str]) -> str:
    """Fix a JS escape sequence for JSON compatibility."""
    escape = match.group(0)
    # Keep valid JSON escapes and unicode escapes (\uXXXX)
    if escape in _VALID_JSON_ESCAPES or escape.startswith("\\u"):
        return escape
    # Invalid JSON escape (e.g. \', \.) - remove the backslash
    return escape[1:]


def parse_jquery_extend(content: str, *, locale: str) -> dict[str, str]:
    """
    Extract key-value pairs from a jQuery.extend JavaScript file.

    The regex captures the outer object from jQuery.extend(true, langJSON, {...}).
    This outer object contains locale sub-keys (e.g. {"de": {...}, "en": {...}}).
    The ``locale`` parameter selects which sub-dict to return.
    """
    match = _JQUERY_EXTEND_RE.search(content)
    if not match:
        return {}

    json_str = match.group(1)

    # Fix JS-specific issues for JSON parsing:
    # Remove trailing commas before }
    json_str = re.sub(r",\s*}", "}", json_str)
    # Remove JS comments (// ...) but preserve :// in URLs
    json_str = re.sub(r"(?<!:)//.*$", "", json_str, flags=re.MULTILINE)
    # Replace bare JS variable references as values with empty strings
    # (e.g., HMIdentifier.de.BidCosRF or langJSON.de.dialogHint)
    json_str = re.sub(
        r":\s*(?:HMIdentifier|langJSON)\.\w+\.\w+",
        ': ""',
        json_str,
    )
    # Handle string concatenation with JS variables ("str" + Identifier.x -> "str")
    json_str = re.sub(r'"\s*\+\s*[A-Za-z_]\w*(?:\.\w+)*', '"', json_str)
    # Handle string concatenation ("a" + "b" -> "ab")
    json_str = re.sub(r'"\s*\+\s*"', "", json_str)
    # Fix JS escape sequences invalid in JSON (\' -> ', \. -> .)
    # Process escape pairs as units: \\ stays (valid JSON), \' -> ', etc.
    json_str = re.sub(r"\\(?:\\|.)", _fix_js_escape, json_str)

    try:
        raw: dict[str, object] = json.loads(json_str)
    except json.JSONDecodeError as err:
        print(f"  WARNING: JSON parse error: {err}", file=sys.stderr)
        return {}

    # Extract locale-specific sub-dict from the outer object
    if locale in raw and isinstance(raw[locale], dict):
        translations: dict[str, str] = raw[locale]
    else:
        # Fallback: treat as flat dict (shouldn't happen with langJSON target)
        translations = {k: v for k, v in raw.items() if isinstance(v, str)}

    # Filter sentinel entries and empty values
    return {k: v for k, v in translations.items() if k not in _SENTINEL_KEYS and v}


def parse_alias_assignments(content: str, translations: dict[str, str]) -> dict[str, str]:
    """
    Parse langJSON.locale.key = langJSON.locale.otherKey; assignments.

    Resolve aliases against the existing translations dict and return new entries.
    """
    aliases: dict[str, str] = {}
    for match in _ALIAS_ASSIGNMENT_RE.finditer(content):
        target_key = match.group(1)
        source_key = match.group(2)
        if (resolved := translations.get(source_key)) is not None:
            aliases[target_key] = resolved
    return aliases


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
    decoded = decoded.replace("&quot;", '"')
    decoded = decoded.replace("&lt;", "<")
    decoded = decoded.replace("&gt;", ">")
    # Normalize whitespace
    decoded = " ".join(decoded.split())
    return decoded.strip()


# Regex to extract "KEY" : "VALUE" pairs from PNAME-style files
# Values may contain escaped quotes (\") so we match \\ or \" as valid content
_PNAME_ENTRY_RE = re.compile(r'"([^"]+)"\s*:\s*"((?:[^"\\]|\\.)*)"')

# Regex to extract 'set param PARAM_NAME' from easymode TCL files
_TCL_SET_PARAM_RE = re.compile(r"set\s+param\s+([A-Z][A-Z0-9_]*)")

# Regex to extract ${stringTableXxx} or ${lblXxx} template references in TCL
_TCL_TEMPLATE_REF_RE = re.compile(r"\$\{((?:stringTable|lbl)\w+)\}")


def parse_pname_file(content: str) -> dict[str, str]:
    r"""
    Parse a PNAME.txt file with direct parameter name -> label mappings.

    Format: "PARAMETER_NAME" : "<span class=\\"translated\\">Label text</span>",
    Return cleaned parameter -> label dict.
    """
    result: dict[str, str] = {}
    for match in _PNAME_ENTRY_RE.finditer(content):
        key = match.group(1).strip()
        value = match.group(2).strip()
        if not key or not value or key == "at":
            continue
        # Unescape JS string escapes (\" -> ", \\ -> \)
        value = value.replace('\\"', '"').replace("\\\\", "\\")
        cleaned = clean_value(value)
        if cleaned:
            result[key] = cleaned
    return result


def parse_easymode_tcl_mappings(easymode_dir: Path) -> dict[str, str]:
    """
    Extract parameter -> template variable mappings from easymode TCL files.

    Parse all *_master.tcl files for 'set param PARAM_NAME' followed by
    a ${stringTableXxx} or ${lblXxx} template reference within the next
    few lines. Return a mapping from parameter name to template variable name.
    """
    mappings: dict[str, str] = {}

    for tcl_file in sorted(easymode_dir.rglob("*_master.tcl")):
        try:
            content = tcl_file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = tcl_file.read_text(encoding="iso-8859-1")

        lines = content.splitlines()
        for i, line in enumerate(lines):
            param_match = _TCL_SET_PARAM_RE.search(line)
            if not param_match:
                continue
            param_name = param_match.group(1)
            if param_name in mappings:
                continue

            # Search next 10 lines for the template variable reference
            for j in range(i + 1, min(i + 11, len(lines))):
                # Stop if we hit the next 'set param'
                if _TCL_SET_PARAM_RE.search(lines[j]):
                    break
                template_match = _TCL_TEMPLATE_REF_RE.search(lines[j])
                if template_match:
                    mappings[param_name] = template_match.group(1)
                    break

    return mappings


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


def load_master_lang_files(
    occu_path: Path,
    locale: str,
) -> dict[str, str]:
    """
    Load device-specific MASTER parameter translations from MASTER_LANG JS files.

    Parse all .js files in config/easymodes/MASTER_LANG/ that contain
    jQuery.extend(true, langJSON, ...) blocks for the given locale.
    """
    master_lang_dir = occu_path / "WebUI" / "www" / _MASTER_LANG_DIR
    merged: dict[str, str] = {}

    if not master_lang_dir.is_dir():
        return merged

    for js_file in sorted(master_lang_dir.glob("*.js")):
        try:
            content = js_file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = js_file.read_text(encoding="iso-8859-1")

        parsed = parse_jquery_extend(content, locale=locale)
        if parsed:
            merged.update(parsed)

    return merged


def load_pname_files(
    occu_path: Path,
    locale: str,
) -> dict[str, str]:
    """
    Load direct parameter name -> label mappings from PNAME files.

    Parse PNAME.txt files in config/easymodes/etc/localization/{locale}/.
    """
    pname_dir = occu_path / "WebUI" / "www" / _PNAME_DIR.format(locale=locale)
    merged: dict[str, str] = {}

    for pname_file in _PNAME_FILES:
        file_path = pname_dir / pname_file
        if not file_path.is_file():
            continue
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = file_path.read_text(encoding="iso-8859-1")

        parsed = parse_pname_file(content)
        if parsed:
            merged.update(parsed)
            print(f"  {locale}/PNAME/{pname_file}: {len(parsed)} entries")

    return merged


def load_sources_local(
    occu_path: Path,
) -> tuple[dict[str, dict[str, dict[str, str]]], dict[str, str], dict[str, dict[str, str]], dict[str, str]]:
    """
    Load all translation sources from a local OCCU checkout.

    Return (locale_data, stringtable_mapping, pname_data, easymode_mappings).
    """
    locale_data: dict[str, dict[str, dict[str, str]]] = {}
    pname_data: dict[str, dict[str, str]] = {}

    for locale in _LOCALES:
        locale_data[locale] = {}
        lang_dir = _JS_LANG_DIR.format(locale=locale)

        # Track raw file contents for alias parsing
        raw_contents: dict[str, str] = {}

        for js_file in _JS_FILES:
            relative_path = f"{lang_dir}/{js_file}"
            try:
                content = load_local_file(occu_path, relative_path)
                raw_contents[js_file] = content
                parsed = parse_jquery_extend(content, locale=locale)
                locale_data[locale][js_file] = parsed
                print(f"  {locale}/{js_file}: {len(parsed)} entries")
            except FileNotFoundError:
                print(f"  WARNING: {relative_path} not found, skipping", file=sys.stderr)
                locale_data[locale][js_file] = {}

        # Parse alias assignments from stringtable.js (langJSON.de.x = langJSON.de.y)
        if st_content := raw_contents.get("translate.lang.stringtable.js"):
            # Build lookup from all parsed translations so far
            all_parsed: dict[str, str] = {}
            for parsed_dict in locale_data[locale].values():
                all_parsed.update(parsed_dict)
            aliases = parse_alias_assignments(st_content, all_parsed)
            if aliases:
                locale_data[locale]["translate.lang.stringtable.js"].update(aliases)
                print(f"  {locale}/stringtable aliases: {len(aliases)} entries")

        # Load MASTER_LANG device-specific translations
        master_translations = load_master_lang_files(occu_path, locale)
        if master_translations:
            locale_data[locale]["_master_lang"] = master_translations
            print(f"  {locale}/MASTER_LANG: {len(master_translations)} entries")

        # Load PNAME direct parameter label files
        pname_translations = load_pname_files(occu_path, locale)
        if pname_translations:
            pname_data[locale] = pname_translations

    # Load stringtable mapping
    mapping_content = load_local_file(occu_path, _STRINGTABLE_MAPPING_PATH)
    stringtable_mapping = parse_stringtable_mapping(mapping_content)
    print(f"  stringtable mapping: {len(stringtable_mapping)} entries")

    # Parse easymode TCL files for parameter -> template variable mappings
    easymode_dir = occu_path / "WebUI" / "www" / _EASYMODE_DIR
    easymode_mappings = parse_easymode_tcl_mappings(easymode_dir)
    print(f"  easymode TCL mappings: {len(easymode_mappings)} entries")

    return locale_data, stringtable_mapping, pname_data, easymode_mappings


def load_sources_remote(
    ccu_url: str,
) -> tuple[dict[str, dict[str, dict[str, str]]], dict[str, str], dict[str, dict[str, str]], dict[str, str]]:
    """
    Load all translation sources from a remote CCU via HTTP.

    Return (locale_data, stringtable_mapping, pname_data, easymode_mappings).
    Easymode TCL parsing is not supported for remote sources.
    """
    locale_data: dict[str, dict[str, dict[str, str]]] = {}
    pname_data: dict[str, dict[str, str]] = {}

    for locale in _LOCALES:
        locale_data[locale] = {}
        lang_dir = _JS_LANG_DIR.format(locale=locale)

        raw_contents: dict[str, str] = {}

        for js_file in _JS_FILES:
            relative_path = f"{lang_dir}/{js_file}"
            try:
                content = fetch_remote_file(ccu_url, relative_path)
                raw_contents[js_file] = content
                parsed = parse_jquery_extend(content, locale=locale)
                locale_data[locale][js_file] = parsed
                print(f"  {locale}/{js_file}: {len(parsed)} entries")
            except Exception as err:
                print(f"  WARNING: Failed to fetch {relative_path}: {err}", file=sys.stderr)
                locale_data[locale][js_file] = {}

        # Parse alias assignments
        if st_content := raw_contents.get("translate.lang.stringtable.js"):
            all_parsed: dict[str, str] = {}
            for parsed_dict in locale_data[locale].values():
                all_parsed.update(parsed_dict)
            aliases = parse_alias_assignments(st_content, all_parsed)
            if aliases:
                locale_data[locale]["translate.lang.stringtable.js"].update(aliases)
                print(f"  {locale}/stringtable aliases: {len(aliases)} entries")

        # Load MASTER_LANG files from remote
        for js_filename in _MASTER_LANG_JS_FILES:
            relative_path = f"{_MASTER_LANG_DIR}/{js_filename}"
            try:
                content = fetch_remote_file(ccu_url, relative_path)
                parsed = parse_jquery_extend(content, locale=locale)
                if parsed:
                    locale_data[locale].setdefault("_master_lang", {}).update(parsed)
            except Exception:
                pass  # MASTER_LANG files are optional

        # Load PNAME files from remote
        for pname_file in _PNAME_FILES:
            relative_path = f"{_PNAME_DIR.format(locale=locale)}/{pname_file}"
            try:
                content = fetch_remote_file(ccu_url, relative_path)
                parsed = parse_pname_file(content)
                if parsed:
                    pname_data.setdefault(locale, {}).update(parsed)
                    print(f"  {locale}/PNAME/{pname_file}: {len(parsed)} entries")
            except Exception:
                pass  # PNAME files are optional

    # Load stringtable mapping
    try:
        mapping_content = fetch_remote_file(ccu_url, _STRINGTABLE_MAPPING_PATH)
        stringtable_mapping = parse_stringtable_mapping(mapping_content)
        print(f"  stringtable mapping: {len(stringtable_mapping)} entries")
    except Exception as err:
        print(f"  WARNING: Failed to fetch stringtable mapping: {err}", file=sys.stderr)
        stringtable_mapping = {}

    return locale_data, stringtable_mapping, pname_data, {}


# Known MASTER_LANG JS files (for remote fetching where glob is not available)
_MASTER_LANG_JS_FILES = (
    "HEATINGTHERMOSTATE_2ND_GEN.js",
    "HEATINGTHERMOSTATE_2ND_GEN_HELP.js",
    "HM-LC-BLIND.js",
    "HM_CC_TC.js",
    "HM_ES_PMSw.js",
    "HM_ES_TX_WM.js",
    "HM_ES_TX_WM_HELP.js",
    "HM_SEC_SIR_WM.js",
    "HmIP-FAL_MIOB.js",
    "HmIP-ParamHelp.js",
    "HmIP-Weather.js",
    "HmIPW_WGD.js",
    "HmIPWeeklyDeviceProgram.js",
    "KEY_4Dis.js",
    "MOTION_DETECTOR.js",
    "UNIVERSAL_LIGHT_EFFECT.js",
)


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
        "translate.lang.extension.js",
        "translate.lang.js",
        "translate.lang.channelDescription.js",
        "translate.lang.deviceDescription.js",
        "_master_lang",
    ):
        if js_file in locale_data:
            merged.update(locale_data[js_file])
    return merged


def _merge_sources(
    base: tuple[dict[str, dict[str, dict[str, str]]], dict[str, str], dict[str, dict[str, str]], dict[str, str]],
    overlay: tuple[dict[str, dict[str, dict[str, str]]], dict[str, str], dict[str, dict[str, str]], dict[str, str]],
) -> tuple[dict[str, dict[str, dict[str, str]]], dict[str, str], dict[str, dict[str, str]], dict[str, str]]:
    """Merge two source tuples. Overlay entries take precedence over base."""
    b_locale, b_stmap, b_pname, b_easy = base
    o_locale, o_stmap, o_pname, o_easy = overlay

    # Merge locale_data (deep merge per locale per js_file)
    merged_locale: dict[str, dict[str, dict[str, str]]] = {}
    for locale in set(b_locale) | set(o_locale):
        merged_locale[locale] = {}
        b_ld = b_locale.get(locale, {})
        o_ld = o_locale.get(locale, {})
        for js_file in set(b_ld) | set(o_ld):
            merged = dict(b_ld.get(js_file, {}))
            merged.update(o_ld.get(js_file, {}))
            merged_locale[locale][js_file] = merged

    # Merge stringtable mapping
    merged_stmap = dict(b_stmap)
    merged_stmap.update(o_stmap)

    # Merge PNAME data
    merged_pname: dict[str, dict[str, str]] = {}
    for locale in set(b_pname) | set(o_pname):
        merged = dict(b_pname.get(locale, {}))
        merged.update(o_pname.get(locale, {}))
        merged_pname[locale] = merged

    # Merge easymode mappings
    merged_easy = dict(b_easy)
    merged_easy.update(o_easy)

    return merged_locale, merged_stmap, merged_pname, merged_easy


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

    # Phase 1: Load sources (both can be set; results are merged)
    sources: list[
        tuple[dict[str, dict[str, dict[str, str]]], dict[str, str], dict[str, dict[str, str]], dict[str, str]]
    ] = []

    if occu_path:
        resolved_occu = Path(occu_path).resolve()
        print(f"Loading sources from {resolved_occu} ...")
        sources.append(load_sources_local(resolved_occu))

    if ccu_url:
        print(f"\nLoading sources from {ccu_url} ...")
        sources.append(load_sources_remote(ccu_url))

    if len(sources) == 1:
        locale_data, stringtable_mapping, pname_data, easymode_mappings = sources[0]
    else:
        # Merge: OCCU local as base, remote CCU as overlay
        locale_data, stringtable_mapping, pname_data, easymode_mappings = _merge_sources(sources[0], sources[1])
        print("\nMerged local and remote sources.")

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

        # Resolve easymode TCL mappings (param -> template var -> translation)
        easymode_count = 0
        existing_lower = {k.lower() for k in parameters}
        for param_name, template_var in easymode_mappings.items():
            if param_name.lower() in existing_lower:
                continue
            resolved = all_translations.get(template_var)
            if resolved:
                cleaned = clean_value(resolved)
                if cleaned:
                    parameters[param_name] = cleaned
                    existing_lower.add(param_name.lower())
                    easymode_count += 1

        # Merge PNAME direct parameter labels (lower priority than stringtable + easymode)
        pname_count = 0
        if locale in pname_data:
            for key, value in pname_data[locale].items():
                if key.lower() not in existing_lower:
                    parameters[key] = value
                    existing_lower.add(key.lower())
                    pname_count += 1

        count = write_json(output_dir, f"parameters_{locale}.json", parameters)
        print(f"  parameters_{locale}.json: {count} entries (+{easymode_count} easymode, +{pname_count} PNAME)")
        count = write_json(output_dir, f"parameter_values_{locale}.json", parameter_values)
        print(f"  parameter_values_{locale}.json: {count} entries")

        if unresolved:
            print(f"  ({unresolved} unresolved template references)")

    print(f"\nDone. Translations written to {output_dir}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
