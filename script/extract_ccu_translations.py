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

import contextlib
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

# Device icon database (locale-independent)
_DEVDB_PATH = "config/devdescr/DEVDB.tcl"

# Supported locales
_LOCALES = ("de", "en")

# Sentinel keys to exclude
_SENTINEL_KEYS = frozenset({"theEnd", "The END", "dummy", "comment", "noMoreKeys"})

# Sentinel keys to exclude from help text files
_HELP_SENTINEL_KEYS: frozenset[str] = frozenset({"HelpTitle", "noHelpAvailable", "noMoreHelp"})

# Known help text files in MASTER_LANG directory
_HELP_FILE_NAMES: frozenset[str] = frozenset(
    {
        "HmIP-ParamHelp.js",
        "HEATINGTHERMOSTATE_2ND_GEN_HELP.js",
        "HM_ES_TX_WM_HELP.js",
    }
)


def _is_help_file(filename: str) -> bool:
    """Return True if the filename is a known help text file."""
    return filename in _HELP_FILE_NAMES


# Default output directory (relative to project root)
_DEFAULT_OUTPUT_DIR = "aiohomematic/translations/ccu_extract"

# Mapping from options.tcl type name to VALUE_LIST strings.
# These are the enum values as returned by the CCU API for each parameter.
# Sources: full_session_randomized_ccu.json, full_session_randomized_pydevccu.json,
# and rftypes XML <option id="..."/> definitions.
# None entries represent indices without a VALUE_LIST mapping (e.g. sparse DALI_EFFECTS
# indices or LOGIC_COMBINATION_SWITCH which starts at index 1).
_OPTION_VALUE_LISTS: dict[str, list[str | None]] = {
    "LOGIC_COMBINATION": [
        "LOGIC_INACTIVE",
        "LOGIC_OR",
        "LOGIC_AND",
        "LOGIC_XOR",
        "LOGIC_NOR",
        "LOGIC_NAND",
        "LOGIC_ORINVERS",
        "LOGIC_ANDINVERS",
        "LOGIC_PLUS",
        "LOGIC_MINUS",
        "LOGIC_MUL",
        "LOGIC_PLUSINVERS",
        "LOGIC_MINUSINVERS",
        "LOGIC_MULINVERS",
        "LOGIC_INVERSPLUS",
        "LOGIC_INVERSMINUS",
        "LOGIC_INVERSMUL",
    ],
    "LOGIC_COMBINATION_SWITCH": [
        None,
        "LOGIC_OR",
        "LOGIC_AND",
        "LOGIC_XOR",
        "LOGIC_NOR",
        "LOGIC_NAND",
        "LOGIC_ORINVERS",
        "LOGIC_ANDINVERS",
    ],
    "LOGIC_COMBINATION_NO_AND_OR": ["LOGIC_INACTIVE", "LOGIC_OR", "LOGIC_AND"],
    "POWERUP_JUMPTARGET": ["OFF", "ON_DELAY", "ON", "OFF_DELAY"],
    "POWERUP_JUMPTARGET_HMIP": ["OFF", "ON_DELAY", "ON", "OFF_DELAY"],
    "POWERUP_JUMPTARGET_OnOff": ["OFF", "ON_DELAY", "ON", "OFF_DELAY"],
    "POWERUP_JUMPTARGET_BLIND_OnOff": ["OFF", "ON_DELAY", "ON", "OFF_DELAY"],
    "POWERUP_JUMPTARGET_WINDOW_DRIVE_RECEIVER_OnOff": ["OFF", "ON_DELAY", "ON", "OFF_DELAY"],
    "POWERUP_JUMPTARGET_wo_ONDELAY": ["OFF", "ON_DELAY", "ON", "OFF_DELAY"],
    "CURRENTDETECTION_BEHAVIOR": [
        "CURRENTDETECTION_ACTIVE",
        "CURRENTDETECTION_INACTIVE_VALUE_OUTPUT_1",
        "CURRENTDETECTION_INACTIVE_VALUE_OUTPUT_2",
    ],
    "HEATING_LOAD_TYPE": ["LOAD_BALANCING", "LOAD_COLLECTION"],
    "HEATING_PUMP_CONTROL": ["LOCAL_PUMP_CONTROL", "GLOBAL_PUMP_CONTROL"],
    "NORMALLY_CLOSE_OPEN": ["NORMALLY_CLOSE", "NORMALLY_OPEN"],
    "NORMALLY_OPEN_CLOSE": ["NORMALLY_OPEN", "NORMALLY_CLOSE"],
    "MIOB_DIN_CONFIG": [
        "CHANGE_OVER",
        "TEMPERATURE_LIMITER",
        "EXTERNAL_CLOCK",
        "HUMIDITY_LIMITER",
        "TACTILE_SWITCH",
    ],
    "HEATING_MODE_SELECTION": ["STANDARD_ROOM", "ROOM_WITH_FIREPLACE", "ROOM_WITH_TOWEL_RAIL"],
    "FLOOR_HEATING_MODE": [
        "FLOOR_HEATING_STANDARD",
        "FLOOR_HEATING_LOW_ENERGY",
        "RADIATOR",
        "CONVECTOR_PASSIV",
        "CONVECTOR_ACTIVE",
    ],
    "OPTION_DISABLE_ENABLE": ["DISABLE", "ENABLE"],
    "DALI_EFFECTS": [
        None,
        "NO_EFFECT",
        None,
        "RAINBOW",
        None,
        "SUNRISE",
        None,
        "SUNSET",
        None,
        None,
        None,
        "FORREST",
        None,
        None,
        None,
        None,
        None,
        "SIGNALING_RED",
        None,
        "GREEN_BILLOW",
    ],
}

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


# Regex to parse DEVDB.tcl icon entries — two patterns:
# Unbraced: MODEL_NAME {{50 /path/thumb.png} {250 /path/full.png}}
# Braced:   {MODEL NAME} {{50 /path/thumb.png} {250 /path/full.png}}
_DEVDB_ENTRY_RE = re.compile(r"(?:\{([^}]+)\}|(\S+))\s+\{\{50\s+([^}]+)\}\s+\{250\s+([^}]+)\}\}")

# Path prefix to strip from DEVDB icon paths
_DEVDB_ICON_PREFIX = "/config/img/devices/250/"


def parse_devdb_icon_mapping(content: str) -> dict[str, str]:
    """
    Parse DEVDB.tcl to extract device model -> icon filename mapping.

    Return {model_lowercase: icon_filename} where icon_filename is relative
    to img/devices/250/.
    """
    result: dict[str, str] = {}
    for match in _DEVDB_ENTRY_RE.finditer(content):
        # Group 1 = braced model name, group 2 = unbraced model name
        model = match.group(1) or match.group(2)
        # Strip stray TCL array braces from unbraced matches (e.g. first entry
        # after 'array set DEV_PATHS {' may start with '{')
        model = model.strip("{}")
        icon_path = match.group(4).strip()
        # Strip the prefix to get just the filename (or subdir/filename for coupling)
        if icon_path.startswith(_DEVDB_ICON_PREFIX):
            icon_filename = icon_path[len(_DEVDB_ICON_PREFIX) :]
        else:
            # Fallback: use full path after last /config/img/devices/250/
            icon_filename = icon_path.lstrip("/")
        result[model.lower()] = icon_filename
    return result


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


# Regex patterns for HTML-to-Markdown conversion in help texts
_HTML_TAG_BOLD_RE = re.compile(r"<b>(.*?)</b>", re.DOTALL)
_HTML_TAG_ITALIC_RE = re.compile(r"<(?:i|u)>(.*?)</(?:i|u)>", re.DOTALL)
_HTML_TAG_BR_RE = re.compile(r"<br\s*/?>")
_HTML_TAG_LI_RE = re.compile(r"<li[^>]*>(.*?)</li>", re.DOTALL)
_HTML_TAG_HEADING_RE = re.compile(r"<h[1-6][^>]*>(.*?)</h[1-6]>", re.DOTALL)
_HTML_TAG_PRE_RE = re.compile(r"<pre[^>]*>(.*?)</pre>", re.DOTALL)
_HTML_TAG_TD_TH_RE = re.compile(r"<(?:td|th)[^>]*>(.*?)</(?:td|th)>", re.DOTALL)
_HTML_TAG_BLOCK_RE = re.compile(r"</?(?:ul|ol|div|table|tr|thead|tbody)[^>]*>")
_HTML_TAG_ANY_RE = re.compile(r"</?[a-zA-Z][^>]*>")
_HTML_ENTITY_MAP: dict[str, str] = {
    "&nbsp;": " ",
    "&amp;": "&",
    "&auml;": "ä",
    "&ouml;": "ö",
    "&uuml;": "ü",
    "&Auml;": "Ä",
    "&Ouml;": "Ö",
    "&Uuml;": "Ü",
    "&szlig;": "ß",
    "&quot;": '"',
    "&lt;": "<",
    "&gt;": ">",
    "&plusmn;": "±",
    "&deg;": "°",
}
_HTML_ENTITY_RE = re.compile(r"&(?:#(\d+)|#x([0-9a-fA-F]+)|(\w+));")


def _decode_html_entity(match: re.Match[str]) -> str:
    """Decode a single HTML entity match."""
    if match.group(1):
        return chr(int(match.group(1)))
    if match.group(2):
        return chr(int(match.group(2), 16))
    named = f"&{match.group(3)};"
    return _HTML_ENTITY_MAP.get(named, named)


def clean_value_markdown(value: str) -> str:
    """Convert HTML help text to Markdown, URL-decode, and normalize whitespace."""
    # URL-decode (%FC -> ü, etc.) using Latin-1 encoding
    decoded = unquote(value, encoding="latin-1")

    # Decode HTML entities
    decoded = _HTML_ENTITY_RE.sub(_decode_html_entity, decoded)
    for entity, char in _HTML_ENTITY_MAP.items():
        decoded = decoded.replace(entity, char)

    # Convert HTML tags to Markdown (order matters)
    # Bold
    decoded = _HTML_TAG_BOLD_RE.sub(r"**\1**", decoded)
    # Italic/underline
    decoded = _HTML_TAG_ITALIC_RE.sub(r"*\1*", decoded)
    # Line breaks -> newline
    decoded = _HTML_TAG_BR_RE.sub("\n", decoded)
    # Headings
    decoded = _HTML_TAG_HEADING_RE.sub(r"# \1\n", decoded)
    # Pre/code
    decoded = _HTML_TAG_PRE_RE.sub(r"`\1`", decoded)
    # Table cells -> inline text with space
    decoded = _HTML_TAG_TD_TH_RE.sub(r"\1 ", decoded)
    # List items -> Markdown list
    decoded = _HTML_TAG_LI_RE.sub(r"- \1\n", decoded)
    # Block-level tags -> newline
    decoded = _HTML_TAG_BLOCK_RE.sub("\n", decoded)
    # Strip all remaining HTML tags
    decoded = _HTML_TAG_ANY_RE.sub("", decoded)

    # Normalize whitespace per line, max 2 consecutive newlines
    lines = [" ".join(line.split()) for line in decoded.splitlines()]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# Regex to extract "KEY" : "VALUE" pairs from PNAME-style files
# Values may contain escaped quotes (\") so we match \\ or \" as valid content
_PNAME_ENTRY_RE = re.compile(r'"([^"]+)"\s*:\s*"((?:[^"\\]|\\.)*)"')

# Regex to extract 'set param PARAM_NAME' from easymode TCL files
_TCL_SET_PARAM_RE = re.compile(r"set\s+param\s+([A-Z][A-Z0-9_]*)")

# Regex to extract ${templateVar} references in TCL (label candidates).
# Matches any camelCase variable name (e.g. stringTableXxx, lblXxx, genericXxx).
# Uppercase-only names (e.g. GROUP, PMSwChannel) and short vars (e.g. p, s, m)
# are excluded — they are typically structural, not translatable labels.
_TCL_TEMPLATE_REF_RE = re.compile(r"\$\{([a-z]\w{2,})\}")


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

    Parse all *.tcl files for 'set param PARAM_NAME' followed by
    a ${templateVar} reference within the next few lines.
    Return a mapping from parameter name to template variable name.
    """
    mappings: dict[str, str] = {}

    for tcl_file in sorted(easymode_dir.rglob("*.tcl")):
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


# Regex patterns for options.tcl parsing
_OPTION_TYPE_BLOCK_RE = re.compile(r'"([A-Z][A-Z0-9_]*)"[^{]*\{')
_OPTION_SET_RE = re.compile(r'set\s+options\(([^)]+)\)\s+"([^"]*)"')
_TEMPLATE_VAR_IN_OPTION_RE = re.compile(r"\\?\$\{(\w+)\}")

# Unit/meta vars to ignore - these are display formatting, not translatable labels
_OPTION_SKIP_VARS = frozenset(
    {
        "none",
        "enterValue",
        "lblIgnore",
        "lastValue",
        "unlimited",
        "inactive",
        "after",
        "short",
        "long",
        "minimal",
        "p",
        "s",
        "m",
        "h",
        "d",
    }
)


def parse_options_tcl(content: str) -> dict[str, dict[int, str]]:
    """
    Parse options.tcl to extract option_type -> {index: template_var} mappings.

    Only include entries that reference translatable template variables
    (e.g. stringTableXxx, optionXxx, channelModeXxx), not unit variables.
    """
    result: dict[str, dict[int, str]] = {}
    pos = 0
    while (m := _OPTION_TYPE_BLOCK_RE.search(content, pos)) is not None:
        type_name = m.group(1)
        block_start = m.end()
        # Find matching closing brace
        depth = 1
        i = block_start
        while i < len(content) and depth > 0:
            if content[i] == "{":
                depth += 1
            elif content[i] == "}":
                depth -= 1
            i += 1
        block = content[block_start : i - 1]

        entries: dict[int, str] = {}
        for idx_str, val in _OPTION_SET_RE.findall(block):
            tvars = _TEMPLATE_VAR_IN_OPTION_RE.findall(val)
            if interesting := [v for v in tvars if v not in _OPTION_SKIP_VARS]:
                with contextlib.suppress(ValueError):
                    entries[int(idx_str)] = interesting[0]

        if entries:
            result[type_name] = entries

        pos = i
    return result


def resolve_options_tcl_translations(
    options_data: dict[str, dict[int, str]],
    all_translations: dict[str, str],
) -> tuple[dict[str, str], int]:
    """
    Resolve options.tcl entries to parameter_value translations.

    Map option_type + index -> VALUE_LIST value, then resolve
    template_var -> translated text.

    Return (parameter_values dict, resolved count).
    """
    parameter_values: dict[str, str] = {}
    resolved_count = 0

    for option_type, entries in options_data.items():
        if (value_list := _OPTION_VALUE_LISTS.get(option_type)) is None:
            continue

        for index, template_var in entries.items():
            # Map index to VALUE_LIST string
            if index < 0 or index >= len(value_list):
                continue
            if (raw_value := value_list[index]) is None:
                continue

            # Resolve template variable to translated text
            if (translated := all_translations.get(template_var)) is None:
                continue
            if not (cleaned := clean_value(translated)):
                continue

            # Emit: option_type=raw_value -> translated_text
            key = f"{option_type}={raw_value}"
            parameter_values[key] = cleaned
            resolved_count += 1

    return parameter_values, resolved_count


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
        if _is_help_file(js_file.name):
            continue
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


def load_help_files(
    occu_path: Path,
    locale: str,
) -> dict[str, str]:
    """
    Load parameter help texts from MASTER_LANG help JS files.

    Parse known help JS files in config/easymodes/MASTER_LANG/ that contain
    jQuery.extend(true, langJSON, ...) blocks for the given locale.
    Only loads files listed in _HELP_FILE_NAMES.
    """
    master_lang_dir = occu_path / "WebUI" / "www" / _MASTER_LANG_DIR
    merged: dict[str, str] = {}

    if not master_lang_dir.is_dir():
        return merged

    for help_filename in sorted(_HELP_FILE_NAMES):
        js_file = master_lang_dir / help_filename
        if not js_file.is_file():
            continue
        try:
            content = js_file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = js_file.read_text(encoding="iso-8859-1")

        parsed = parse_jquery_extend(content, locale=locale)
        # Filter sentinel keys
        for key in _HELP_SENTINEL_KEYS:
            parsed.pop(key, None)
        if parsed:
            merged.update(parsed)

    return merged


# Prefixes to filter out from profile localization files (easymode UI descriptions)
_PROFILE_LOC_SKIP_PREFIXES = ("description_", "subset_")


def load_profile_localization_files(
    occu_path: Path,
    locale: str,
) -> dict[str, str]:
    """
    Load parameter translations from profile localization directories.

    Scan config/easymodes/*/localization/{locale}/*.txt and
    config/easymodes/etc/localization/{locale}/*.txt for PNAME-format files.
    Filter out keys starting with description_ or subset_ (easymode UI descriptions).
    """
    merged: dict[str, str] = {}
    base_dir = occu_path / "WebUI" / "www" / "config" / "easymodes"

    if not base_dir.is_dir():
        return merged

    # Scan all subdirectories under easymodes (including etc/)
    for loc_dir in sorted(base_dir.rglob(f"localization/{locale}")):
        if not loc_dir.is_dir():
            continue
        for txt_file in sorted(loc_dir.glob("*.txt")):
            try:
                content = txt_file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                content = txt_file.read_text(encoding="iso-8859-1")

            parsed = parse_pname_file(content)
            for key, value in parsed.items():
                key_lower = key.lower()
                if any(key_lower.startswith(prefix) for prefix in _PROFILE_LOC_SKIP_PREFIXES):
                    continue
                merged[key] = value

    return merged


# Type alias for the 8-tuple returned by load_sources_*
_SourceTuple = tuple[
    dict[str, dict[str, dict[str, str]]],  # locale_data
    dict[str, str],  # stringtable_mapping
    dict[str, dict[str, str]],  # pname_data
    dict[str, str],  # easymode_mappings
    dict[str, dict[int, str]],  # options_tcl_data
    dict[str, dict[str, str]],  # help_data (locale -> {param -> raw_html})
    dict[str, str],  # icon_data (model -> filename, locale-independent)
    dict[str, dict[str, str]],  # profile_localization_data (locale -> {param -> label})
]


def load_sources_local(
    occu_path: Path,
) -> _SourceTuple:
    """
    Load all translation sources from a local OCCU checkout.

    Return 8-tuple of (locale_data, stringtable_mapping, pname_data, easymode_mappings,
    options_tcl_data, help_data, icon_data, profile_localization_data).
    """
    locale_data: dict[str, dict[str, dict[str, str]]] = {}
    pname_data: dict[str, dict[str, str]] = {}
    help_data: dict[str, dict[str, str]] = {}
    profile_localization_data: dict[str, dict[str, str]] = {}

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

        # Load help text files
        help_translations = load_help_files(occu_path, locale)
        if help_translations:
            help_data[locale] = help_translations
            print(f"  {locale}/HELP: {len(help_translations)} entries")

        # Load profile localization files
        profile_loc = load_profile_localization_files(occu_path, locale)
        if profile_loc:
            profile_localization_data[locale] = profile_loc
            print(f"  {locale}/profile localization: {len(profile_loc)} entries")

    # Load stringtable mapping
    mapping_content = load_local_file(occu_path, _STRINGTABLE_MAPPING_PATH)
    stringtable_mapping = parse_stringtable_mapping(mapping_content)
    print(f"  stringtable mapping: {len(stringtable_mapping)} entries")

    # Parse easymode TCL files for parameter -> template variable mappings
    easymode_dir = occu_path / "WebUI" / "www" / _EASYMODE_DIR
    easymode_mappings = parse_easymode_tcl_mappings(easymode_dir)
    print(f"  easymode TCL mappings: {len(easymode_mappings)} entries")

    # Parse options.tcl for option type -> {index: template_var} mappings
    options_tcl_path = occu_path / "WebUI" / "www" / "config" / "easymodes" / "etc" / "options.tcl"
    options_tcl_data: dict[str, dict[int, str]] = {}
    if options_tcl_path.is_file():
        try:
            options_content = options_tcl_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            options_content = options_tcl_path.read_text(encoding="iso-8859-1")
        options_tcl_data = parse_options_tcl(options_content)
        print(f"  options.tcl: {len(options_tcl_data)} option types")

    # Load device icon database (locale-independent)
    devdb_path = occu_path / "WebUI" / "www" / _DEVDB_PATH
    icon_data: dict[str, str] = {}
    if devdb_path.is_file():
        try:
            devdb_content = devdb_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            devdb_content = devdb_path.read_text(encoding="iso-8859-1")
        icon_data = parse_devdb_icon_mapping(devdb_content)
        print(f"  DEVDB.tcl: {len(icon_data)} device icons")

    return (
        locale_data,
        stringtable_mapping,
        pname_data,
        easymode_mappings,
        options_tcl_data,
        help_data,
        icon_data,
        profile_localization_data,
    )


def load_sources_remote(
    ccu_url: str,
) -> _SourceTuple:
    """
    Load all translation sources from a remote CCU via HTTP.

    Return 8-tuple of (locale_data, stringtable_mapping, pname_data, easymode_mappings,
    options_tcl_data, help_data, icon_data, profile_localization_data).
    Easymode/options TCL, profile localization, and DEVDB parsing not supported for remote.
    """
    locale_data: dict[str, dict[str, dict[str, str]]] = {}
    pname_data: dict[str, dict[str, str]] = {}
    help_data: dict[str, dict[str, str]] = {}

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

        # Load MASTER_LANG files from remote (skip help files)
        for js_filename in _MASTER_LANG_JS_FILES:
            if _is_help_file(js_filename):
                continue
            relative_path = f"{_MASTER_LANG_DIR}/{js_filename}"
            try:
                content = fetch_remote_file(ccu_url, relative_path)
                parsed = parse_jquery_extend(content, locale=locale)
                if parsed:
                    locale_data[locale].setdefault("_master_lang", {}).update(parsed)
            except Exception:
                pass  # MASTER_LANG files are optional

        # Load help files from remote
        for help_filename in sorted(_HELP_FILE_NAMES):
            relative_path = f"{_MASTER_LANG_DIR}/{help_filename}"
            try:
                content = fetch_remote_file(ccu_url, relative_path)
                parsed = parse_jquery_extend(content, locale=locale)
                for key in _HELP_SENTINEL_KEYS:
                    parsed.pop(key, None)
                if parsed:
                    help_data.setdefault(locale, {}).update(parsed)
            except Exception:
                pass  # Help files are optional

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

    # Try to load DEVDB.tcl from remote
    icon_data: dict[str, str] = {}
    try:
        devdb_content = fetch_remote_file(ccu_url, _DEVDB_PATH)
        icon_data = parse_devdb_icon_mapping(devdb_content)
        print(f"  DEVDB.tcl: {len(icon_data)} device icons")
    except Exception:
        pass  # DEVDB.tcl is optional for remote

    return locale_data, stringtable_mapping, pname_data, {}, {}, help_data, icon_data, {}


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
    base: _SourceTuple,
    overlay: _SourceTuple,
) -> _SourceTuple:
    """Merge two source tuples. Overlay entries take precedence over base."""
    b_locale, b_stmap, b_pname, b_easy, b_opts, b_help, b_icons, b_ploc = base
    o_locale, o_stmap, o_pname, o_easy, o_opts, o_help, o_icons, o_ploc = overlay

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

    # Merge options.tcl data (deep merge per option type)
    merged_opts: dict[str, dict[int, str]] = {}
    for opt_type in set(b_opts) | set(o_opts):
        merged = dict(b_opts.get(opt_type, {}))
        merged.update(o_opts.get(opt_type, {}))
        merged_opts[opt_type] = merged

    # Merge help data (per locale)
    merged_help: dict[str, dict[str, str]] = {}
    for locale in set(b_help) | set(o_help):
        merged = dict(b_help.get(locale, {}))
        merged.update(o_help.get(locale, {}))
        merged_help[locale] = merged

    # Merge icon data
    merged_icons = dict(b_icons)
    merged_icons.update(o_icons)

    # Merge profile localization data (per locale)
    merged_ploc: dict[str, dict[str, str]] = {}
    for locale in set(b_ploc) | set(o_ploc):
        merged = dict(b_ploc.get(locale, {}))
        merged.update(o_ploc.get(locale, {}))
        merged_ploc[locale] = merged

    return (
        merged_locale,
        merged_stmap,
        merged_pname,
        merged_easy,
        merged_opts,
        merged_help,
        merged_icons,
        merged_ploc,
    )


def _load_dotenv(env_file: Path) -> None:
    """Load environment variables from a .env file (stdlib-only, no python-dotenv needed)."""
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


def main() -> int:
    """Run the extraction pipeline."""
    # Auto-load .env from project root (does not override existing env vars)
    project_root = Path(__file__).resolve().parent.parent
    _load_dotenv(project_root / ".env")

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
    sources: list[_SourceTuple] = []

    if occu_path:
        resolved_occu = Path(occu_path).resolve()
        print(f"Loading sources from {resolved_occu} ...")
        sources.append(load_sources_local(resolved_occu))

    if ccu_url:
        print(f"\nLoading sources from {ccu_url} ...")
        sources.append(load_sources_remote(ccu_url))

    if len(sources) == 1:
        (
            locale_data,
            stringtable_mapping,
            pname_data,
            easymode_mappings,
            options_tcl_data,
            help_data,
            icon_data,
            profile_localization_data,
        ) = sources[0]
    else:
        # Merge: OCCU local as base, remote CCU as overlay
        (
            locale_data,
            stringtable_mapping,
            pname_data,
            easymode_mappings,
            options_tcl_data,
            help_data,
            icon_data,
            profile_localization_data,
        ) = _merge_sources(sources[0], sources[1])
        print("\nMerged local and remote sources.")

    print()

    # Device icons (locale-independent, outside locale loop)
    if icon_data:
        count = write_json(output_dir, "device_icons.json", icon_data)
        print(f"device_icons.json: {count} entries")

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

        # Resolve options.tcl translations (option_type=value -> translated label)
        options_values, options_count = resolve_options_tcl_translations(options_tcl_data, all_translations)
        # Merge: don't override existing entries from stringtable
        existing_pv_lower = {k.lower() for k in parameter_values}
        for key, value in options_values.items():
            if key.lower() not in existing_pv_lower:
                parameter_values[key] = value
                existing_pv_lower.add(key.lower())

        # Merge PNAME direct parameter labels (higher priority than easymode TCL,
        # because PNAME files contain official localization labels while easymode
        # TCL files contain UI-layout descriptions that may include HTML artifacts)
        pname_count = 0
        existing_lower = {k.lower() for k in parameters}
        if locale in pname_data:
            for key, value in pname_data[locale].items():
                if key.lower() not in existing_lower:
                    parameters[key] = value
                    existing_lower.add(key.lower())
                    pname_count += 1

        # Resolve easymode TCL mappings (param -> template var -> translation)
        easymode_count = 0
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

        # Merge profile localization (lowest priority — after easymode)
        profile_count = 0
        if locale in profile_localization_data:
            for key, value in profile_localization_data[locale].items():
                if key.lower() not in existing_lower:
                    parameters[key] = value
                    existing_lower.add(key.lower())
                    profile_count += 1

        count = write_json(output_dir, f"parameters_{locale}.json", parameters)
        print(
            f"  parameters_{locale}.json: {count} entries "
            f"(+{easymode_count} easymode, +{pname_count} PNAME, +{profile_count} profile)"
        )
        count = write_json(output_dir, f"parameter_values_{locale}.json", parameter_values)
        print(f"  parameter_values_{locale}.json: {count} entries (+{options_count} options.tcl)")

        if unresolved:
            print(f"  ({unresolved} unresolved template references)")

        # Parameter help texts (HTML -> Markdown)
        if locale in help_data:
            parameter_help: dict[str, str] = {}
            for key, raw_html in help_data[locale].items():
                # Resolve ${templateVar} references using all translations
                resolved = resolve_template(raw_html, all_translations)
                if resolved is None:
                    # Strip unresolved ${vars} and use remaining text
                    resolved = _TEMPLATE_VAR_RE.sub("", raw_html)
                markdown = clean_value_markdown(resolved)
                if markdown:
                    parameter_help[key] = markdown
            count = write_json(output_dir, f"parameter_help_{locale}.json", parameter_help)
            print(f"  parameter_help_{locale}.json: {count} entries")

    print(f"\nDone. Translations written to {output_dir}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
