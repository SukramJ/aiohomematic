#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Extract CCU easymode metadata and generate a gzip-compressed JSON archive.

Parse TCL easymode configuration files from the OpenCCU/RaspberryMatic WebUI
and output a single ``easymode_extract.json.gz`` archive containing channel
metadata, option presets, and cross-validation rules.

Usage:
    # From local OCCU checkout (preferred)
    OCCU_PATH=/path/to/occu python script/extract_ccu_easymodes.py

    # From remote CCU via HTTP
    CCU_URL=https://my-ccu.local python script/extract_ccu_easymodes.py

    # Custom output directory
    OCCU_PATH=/path/to/occu OUTPUT_DIR=custom/path python script/extract_ccu_easymodes.py

Environment Variables:
    OCCU_PATH   Path to local OCCU checkout (preferred)
    CCU_URL     URL of a live CCU instance (alternative)
    OUTPUT_DIR  Output directory (default: aiohomematic/ccu_data)
"""

from __future__ import annotations

import gzip
import json
import os
from pathlib import Path
import re
import ssl
import sys
from typing import Any
import urllib.request

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_EASYMODE_DIR = "config/easymodes"
_OPTIONS_TCL_PATH = f"{_EASYMODE_DIR}/etc/options.tcl"
_HMIP_CHANNEL_DIALOGS_PATH = f"{_EASYMODE_DIR}/etc/hmipChannelConfigDialogs.tcl"
_HMIP_MASTER_DIR = f"{_EASYMODE_DIR}/hmip"

_DEFAULT_OUTPUT_DIR = "aiohomematic/ccu_data"

# Sender type key for MASTER paramset metadata
_MASTER_SENDER_TYPE = "_MASTER"

# Directories/files to skip when scanning easymode directories
_SKIP_DIRS = frozenset(
    {
        "etc",
        "hmip",
        "js",
        "MASTER_LANG",
        "localization",
        "mapping",
    }
)
_SKIP_EXTENSIONS = frozenset({".js", ".sh", ".md", ".txt"})

# Regex patterns
_RE_PROFILES_MAP = re.compile(r"^set\s+PROFILES_MAP\((\d+)\)\s+(.+)$", re.MULTILINE)
_RE_PROFILE_PARAM = re.compile(r"^set\s+PROFILE_(\d+)\(([A-Z_0-9]+)\)\s+(.+)$", re.MULTILINE)
_RE_SUBSET = re.compile(r"^set\s+SUBSET_(\d+)\(([A-Z_0-9]+)\)\s+(.+)$", re.MULTILINE)
_RE_CONSTANT = re.compile(r"^set\s+([A-Z_]+)\s+(\d+)\s*$", re.MULTILINE)
_RE_LOCALIZATION_KEY = re.compile(r"\\?\$\{([a-zA-Z0-9_]+)\}")
_RE_RANGE_VALUE = re.compile(r"^\{(.+?)\s+range\s+(.+?)\s+-\s+(.+?)\}$")
_RE_LIST_VALUE = re.compile(r"^\{(.+)\}$")
_RE_VARIABLE_REF = re.compile(r"^\$([A-Z_]+)$")

# HTML_PARAMS patterns for extracting parameter order and widget info
_RE_GET_COMBOBOX = re.compile(r"get_ComboBox\s+options\s+(\w+)\s", re.MULTILINE)
_RE_GET_TIME_SELECTOR = re.compile(
    r"getTimeSelector\s+\w+\s+\w+\s+\w+\s+(\w+)\s+\S+\s+\S+\s+(\w+)\s+(\w+)",
    re.MULTILINE,
)
_RE_SUBSET2COMBOBOX = re.compile(r"subset2combobox\s+\{([^}]+)\}", re.MULTILINE)
_RE_OPTION_SET = re.compile(r"^\s*set\s+options\(([^)]+)\)\s+(.+)$", re.MULTILINE)
_RE_OPTION_TYPE = re.compile(r'"([A-Z_0-9a-z]+)"\s*\{', re.MULTILINE)

# Special sentinel values in option presets
_SPECIAL_OPTION_VALUES = frozenset({99999990, 99999998, 99999999})

# Patterns for parsing hmipChannelConfigDialogs.tcl proc bodies
_RE_SET_PARAM = re.compile(r"^\s+set\s+param\s+([A-Z_0-9]+)\s*$", re.MULTILINE)
_RE_HORIZONTAL_LINE = re.compile(r'append\s+html\s+"\[getHorizontalLine\]"', re.MULTILINE)
_RE_INLINE_OPTION = re.compile(r'^\s+set\s+options\((\d+)\)\s+"?(.+?)"?\s*$', re.MULTILINE)
_RE_OPTION_CALL = re.compile(r"^\s+option\s+([A-Z_0-9]+)\s*$", re.MULTILINE)
_RE_LABEL_REF = re.compile(r"\$\{([a-zA-Z0-9_]+)\}")
_RE_HIDDEN_CLASS = re.compile(r'class=\\"hidden\\"')
_RE_GET_OPTION_BOX = re.compile(
    r"getOptionBox\s+'?\$?'?param'?\s+options\s+\S+\s+\S+\s+\S+",
    re.MULTILINE,
)
_RE_GET_CHECKBOX = re.compile(
    r"getCheckBox\s+'?\$?'?param'?\s+",
    re.MULTILINE,
)
_RE_GET_TEXTFIELD = re.compile(
    r"getTextField\s+\$?param\s+",
    re.MULTILINE,
)
_RE_PROC_DEF = re.compile(
    r"^proc\s+(get[A-Za-z_]+)\s+\{([^}]*)\}\s*\{",
    re.MULTILINE,
)
_RE_HMIP_FUNC_CALL = re.compile(
    r"\[(get[A-Za-z_]+)\s+\$chn\b",
)

# Cross-validation rules (manually curated, derived from TCL logic)
_CROSS_VALIDATION_RULES: list[dict[str, Any]] = [
    {
        "id": "dim_max_gte_min",
        "applies_to_params": ["DIM_MAX_LEVEL", "DIM_MIN_LEVEL"],
        "rule": "gte",
        "param_a": "DIM_MAX_LEVEL",
        "param_b": "DIM_MIN_LEVEL",
        "error_key": "cross_validation.max_must_be_gte_min",
    },
    {
        "id": "short_on_level_in_dim_range",
        "applies_to_params": ["SHORT_ON_LEVEL", "DIM_MIN_LEVEL", "DIM_MAX_LEVEL"],
        "rule": "between",
        "param": "SHORT_ON_LEVEL",
        "min_param": "DIM_MIN_LEVEL",
        "max_param": "DIM_MAX_LEVEL",
        "error_key": "cross_validation.level_must_be_in_range",
    },
    {
        "id": "long_on_level_in_dim_range",
        "applies_to_params": ["LONG_ON_LEVEL", "DIM_MIN_LEVEL", "DIM_MAX_LEVEL"],
        "rule": "between",
        "param": "LONG_ON_LEVEL",
        "min_param": "DIM_MIN_LEVEL",
        "max_param": "DIM_MAX_LEVEL",
        "error_key": "cross_validation.level_must_be_in_range",
    },
    {
        "id": "short_cond_hi_gte_lo",
        "applies_to_params": ["SHORT_COND_VALUE_HI", "SHORT_COND_VALUE_LO"],
        "rule": "gte",
        "param_a": "SHORT_COND_VALUE_HI",
        "param_b": "SHORT_COND_VALUE_LO",
        "error_key": "cross_validation.hi_must_be_gte_lo",
    },
    {
        "id": "long_cond_hi_gte_lo",
        "applies_to_params": ["LONG_COND_VALUE_HI", "LONG_COND_VALUE_LO"],
        "rule": "gte",
        "param_a": "LONG_COND_VALUE_HI",
        "param_b": "LONG_COND_VALUE_LO",
        "error_key": "cross_validation.hi_must_be_gte_lo",
    },
]


# ---------------------------------------------------------------------------
# .env loader (same as extract_ccu_translations.py)
# ---------------------------------------------------------------------------


def _load_dotenv(env_file: Path) -> None:
    """Load environment variables from a .env file (stdlib-only)."""
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


# ---------------------------------------------------------------------------
# TCL Parsing
# ---------------------------------------------------------------------------


def _read_file(path: Path) -> str:
    """Read file with UTF-8, fallback to ISO-8859-1."""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="iso-8859-1")


def _parse_tcl_value(
    raw: str,
    *,
    constants: dict[str, int],
) -> dict[str, Any]:
    """Parse a TCL parameter value into a constraint dict."""
    raw = raw.strip()

    # Range: {default range min - max}
    if m := _RE_RANGE_VALUE.match(raw):
        return {
            "constraint_type": "range",
            "default": _to_number(m.group(1).strip()),
            "min_value": _to_number(m.group(2).strip()),
            "max_value": _to_number(m.group(3).strip()),
        }

    # Variable reference: $ON_DELAY
    if m := _RE_VARIABLE_REF.match(raw):
        var_name = m.group(1)
        if var_name in constants:
            return {"constraint_type": "fixed", "value": constants[var_name]}
        return {"constraint_type": "fixed", "value": var_name}

    # List: {1 2 5}
    if m := _RE_LIST_VALUE.match(raw):
        inner = m.group(1).strip()
        # Check if it's a subst expression
        if inner.startswith("$") or "[" in inner:
            parts = inner.replace("[subst {", "").replace("}]", "").split()
            values = []
            for p in parts:
                p = p.strip()
                if p.startswith("$"):
                    vname = p[1:]
                    values.append(constants.get(vname, vname))
                else:
                    values.append(_to_number(p))
            return {"constraint_type": "list", "values": values}
        parts = inner.split()
        if len(parts) > 1:
            return {
                "constraint_type": "list",
                "values": [_to_number(p) for p in parts],
            }
        return {"constraint_type": "fixed", "value": _to_number(parts[0])}

    # Scalar
    return {"constraint_type": "fixed", "value": _to_number(raw)}


def _to_number(s: str) -> int | float | str:
    """Convert string to int, float, or keep as string."""
    s = s.strip().strip('"')
    try:
        if "." in s:
            return float(s)
        return int(s)
    except ValueError:
        return s


def _clean_localization_key(raw: str) -> str:
    r"""Extract localization key from TCL string like '\\${key}'."""
    raw = raw.strip().strip('"')
    if m := _RE_LOCALIZATION_KEY.search(raw):
        return m.group(1)
    return raw


def parse_tcl_easymode(content: str) -> dict[str, Any]:
    """Parse a single TCL easymode file and extract metadata."""
    result: dict[str, Any] = {}

    # 1. Extract constants (set ON_DELAY 1)
    constants: dict[str, int] = {}
    for m in _RE_CONSTANT.finditer(content):
        constants[m.group(1)] = int(m.group(2))

    # 2. Extract PROFILES_MAP
    profiles_map: dict[int, str] = {}
    for m in _RE_PROFILES_MAP.finditer(content):
        profile_id = int(m.group(1))
        label_key = _clean_localization_key(m.group(2))
        profiles_map[profile_id] = label_key

    # 3. Extract PROFILE_X parameters
    profile_params: dict[int, dict[str, Any]] = {}
    for m in _RE_PROFILE_PARAM.finditer(content):
        profile_id = int(m.group(1))
        param_name = m.group(2)
        raw_value = m.group(3).strip()
        if profile_id not in profile_params:
            profile_params[profile_id] = {}
        profile_params[profile_id][param_name] = raw_value

    # 4. Build profiles
    profiles = []
    for pid in sorted(profiles_map):
        label_key = profiles_map[pid]
        params_raw = profile_params.get(pid, {})

        # Extract UI metadata
        params_raw.pop("UI_HINT", None)
        ui_description = params_raw.pop("UI_DESCRIPTION", "")
        params_raw.pop("UI_TEMPLATE", "")
        whitelist_raw = params_raw.pop("UI_WHITELIST", None)
        blacklist_raw = params_raw.pop("UI_BLACKLIST", None)

        # Parse visible/hidden params from whitelist/blacklist
        visible_params = None
        hidden_params = None
        if whitelist_raw:
            wl = whitelist_raw.strip().strip("{}")
            visible_params = [p.strip() for p in wl.split() if p.strip()]
        if blacklist_raw:
            bl = blacklist_raw.strip().strip("{}")
            hidden_params = [p.strip() for p in bl.split() if p.strip()]

        # Parse parameter constraints
        params: dict[str, Any] = {}
        for pname, pval in params_raw.items():
            params[pname] = _parse_tcl_value(pval, constants=constants)

        desc = ui_description.strip().strip('"')
        # Clean description from TCL variable references
        desc = re.sub(r"\$PROFILE_\d+\([^)]+\)", "", desc).strip()

        profile: dict[str, Any] = {
            "id": pid,
            "name_key": label_key,
            "params": params,
        }
        if desc and desc != '""':
            profile["description"] = desc
        if visible_params:
            profile["visible_params"] = visible_params
        if hidden_params:
            profile["hidden_params"] = hidden_params

        profiles.append(profile)

    if profiles:
        result["profiles"] = profiles

    # 5. Extract SUBSET_X
    subset_data: dict[int, dict[str, Any]] = {}
    for m in _RE_SUBSET.finditer(content):
        sid = int(m.group(1))
        key = m.group(2)
        raw = m.group(3).strip()
        if sid not in subset_data:
            subset_data[sid] = {}
        subset_data[sid][key] = raw

    subsets = []
    for sid in sorted(subset_data):
        sd = subset_data[sid]
        name_raw = sd.pop("NAME", None)
        if not name_raw:
            continue
        name_key = _clean_localization_key(name_raw)
        option_value = sd.pop("SUBSET_OPTION_VALUE", None)

        member_params = sorted(sd.keys())
        values: dict[str, int | float | str] = {}
        for pname, pval in sd.items():
            pval = pval.strip()
            if pval.startswith("$"):
                var = pval[1:]
                values[pname] = constants.get(var, var)
            else:
                values[pname] = _to_number(pval)

        subset: dict[str, Any] = {
            "id": sid,
            "name_key": name_key,
            "member_params": member_params,
            "values": values,
        }
        if option_value is not None:
            subset["option_value"] = _to_number(option_value)
        subsets.append(subset)

    if subsets:
        result["subsets"] = subsets

    # 6. Extract parameter order and widget hints from set_htmlParams
    param_order, option_preset_refs = _extract_html_params_info(content)
    if param_order:
        result["parameter_order"] = param_order
    if option_preset_refs:
        result["option_presets"] = option_preset_refs

    return result


def _extract_html_params_info(
    content: str,
) -> tuple[list[str], dict[str, str]]:
    """Extract parameter display order and option preset references from HTML_PARAMS."""
    params_seen: list[str] = []
    seen_set: set[str] = set()
    option_presets: dict[str, str] = {}

    # Extract get_ComboBox calls: parameter name and option type
    for m in _RE_GET_COMBOBOX.finditer(content):
        param = m.group(1)
        if param not in seen_set:
            params_seen.append(param)
            seen_set.add(param)

    # Extract getTimeSelector calls: parameter name and timebase type
    for m in _RE_GET_TIME_SELECTOR.finditer(content):
        m.group(1)  # e.g., timeOnOff, delay
        param = m.group(2)  # e.g., SHORT_ON_TIME
        timebase = m.group(3)  # e.g., TIMEBASE_LONG
        if param not in seen_set:
            params_seen.append(param)
            seen_set.add(param)
        # Time parameters reference their timebase
        option_presets[param] = timebase

    # Look for inline option calls before get_ComboBox
    # Pattern: option BLIND_LEVEL ... get_ComboBox options SHORT_ON_LEVEL
    option_calls = list(re.finditer(r"option\s+(\w+)", content))
    combobox_calls = list(_RE_GET_COMBOBOX.finditer(content))

    for cb in combobox_calls:
        cb_pos = cb.start()
        param = cb.group(1)
        # Find the closest preceding option call
        closest_option = None
        for oc in option_calls:
            if oc.start() < cb_pos:
                closest_option = oc.group(1)
        if closest_option and param not in option_presets:
            option_presets[param] = closest_option

    return params_seen, option_presets


# ---------------------------------------------------------------------------
# hmipChannelConfigDialogs.tcl parsing (MASTER paramset metadata)
# ---------------------------------------------------------------------------


def _split_procs(content: str) -> dict[str, str]:
    """Split TCL file content into {proc_name: proc_body} mapping."""
    procs: dict[str, str] = {}
    matches = list(_RE_PROC_DEF.finditer(content))
    for i, m in enumerate(matches):
        name = m.group(1)
        body_start = m.end()
        # Body extends until the next proc definition or end of file
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        procs[name] = content[body_start:body_end]
    return procs


def _merge_unlabeled_groups(
    groups: list[tuple[list[str], str]],
) -> list[tuple[list[str], str]]:
    """
    Merge parameter groups without a label into the next labeled group.

    A CCU easymode TCL dialog may split semantically related parameters with
    decorative ``getHorizontalLine`` calls that don't carry their own label
    reference. The extractor sees these as separate groups with an empty
    ``label_key``, which would leak as raw ``group_N`` titles in the UI.

    Strategy: attach any unlabeled group to the next labeled group (preserving
    parameter order). Unlabeled groups at the tail are attached to the last
    labeled group; if there is no labeled group at all, the input is returned
    unchanged so callers can decide how to handle the fully-anonymous case.
    """
    if not groups:
        return groups

    has_any_label = any(label for _, label in groups)
    if not has_any_label:
        return groups

    merged: list[tuple[list[str], str]] = []
    pending: list[str] = []
    for params, label in groups:
        if not label:
            pending.extend(params)
            continue
        merged.append((pending + list(params), label))
        pending = []

    # Attach any trailing unlabeled params to the last labeled group
    if pending:
        last_params, last_label = merged[-1]
        merged[-1] = (last_params + pending, last_label)

    return merged


def _parse_dialog_proc(proc_body: str) -> dict[str, Any] | None:
    """
    Parse a single dialog proc body and extract MASTER metadata.

    Extract parameter order, parameter groups (separated by getHorizontalLine),
    option preset references (both from options.tcl and inline), and
    conditional visibility hints.
    """
    lines = proc_body.split("\n")

    # Track parameters in order, grouped by horizontal lines
    groups: list[list[str]] = [[]]
    group_labels: list[str] = [""]
    current_param: str = ""
    param_order: list[str] = []
    seen_params: set[str] = set()
    option_presets: dict[str, str] = {}
    inline_options: dict[str, dict[str, Any]] = {}
    conditional_visibility: list[dict[str, Any]] = []

    # State for inline option parsing
    current_inline_options: dict[int, str] = {}
    pending_option_type: str = ""
    first_label_in_group: str = ""

    i = 0
    while i < len(lines):
        line = lines[i]

        # Detect horizontal line → new group
        if _RE_HORIZONTAL_LINE.search(line):
            groups.append([])
            group_labels.append("")
            first_label_in_group = ""
            i += 1
            continue

        # Detect set param PARAM_NAME
        param_match = _RE_SET_PARAM.match(line)
        if param_match:
            current_param = param_match.group(1)
            if current_param not in seen_params:
                seen_params.add(current_param)
                param_order.append(current_param)
                groups[-1].append(current_param)
            # Reset inline options state for new param
            current_inline_options = {}
            pending_option_type = ""
            i += 1
            continue

        # Detect option PRESET_TYPE (from options.tcl)
        option_match = _RE_OPTION_CALL.match(line)
        if option_match:
            pending_option_type = option_match.group(1)
            i += 1
            continue

        # Detect inline set options(N) "label"
        inline_match = _RE_INLINE_OPTION.match(line)
        if inline_match and current_param:
            key = int(inline_match.group(1))
            raw_label = inline_match.group(2).strip().strip('"')
            label = raw_label
            # Extract localization key if present
            lk_match = _RE_LABEL_REF.search(raw_label)
            if lk_match:
                label = lk_match.group(1)
            current_inline_options[key] = label
            i += 1
            continue

        # When we see getOptionBox after collecting options, finalize
        if current_param and (_RE_GET_OPTION_BOX.search(line) or "getOptionBox" in line):
            if pending_option_type:
                # Link to options.tcl preset
                option_presets[current_param] = pending_option_type
                pending_option_type = ""
            elif current_inline_options:
                # Store inline options
                inline_options[current_param] = dict(current_inline_options)
            current_inline_options = {}
            i += 1
            continue

        # Detect getComboBox calls (time selectors)
        combobox_match = re.search(r'getComboBox\s+\$chn\s+\$prn\s+"?\$?specialID"?\s+"(\w+)"', line)
        if combobox_match and current_param:
            # The current_param's UNIT/VALUE pair is associated with this time selector
            # We don't need to store this as a preset - the time pair handling in the
            # frontend already deals with this
            i += 1
            continue

        # Capture first label reference per group for group labeling
        if not first_label_in_group and current_param and groups[-1]:
            label_match = _RE_LABEL_REF.search(line)
            if label_match and "td>" in line:
                first_label_in_group = label_match.group(1)
                if not group_labels[-1]:
                    group_labels[-1] = first_label_in_group

        # Detect conditional visibility (class="hidden" for timeFactor rows)
        if _RE_HIDDEN_CLASS.search(line) and current_param:
            # The VALUE parameter of a UNIT/VALUE pair is hidden by default
            # It becomes visible when the time unit selector changes
            value_param = current_param
            # Try to find the associated UNIT param
            unit_param = value_param.replace("_VALUE", "_UNIT")
            if unit_param != value_param and unit_param in seen_params:
                conditional_visibility.append(
                    {
                        "trigger": unit_param,
                        "trigger_value": "custom",
                        "show": [value_param],
                    }
                )

        i += 1

    # Filter out empty groups
    non_empty_groups = [(params, label) for params, label in zip(groups, group_labels, strict=False) if params]
    pre_merge_count = len(non_empty_groups)

    # Merge groups without a label into the next labeled group. A group without
    # a label_key typically means the CCU TCL split a semantic section with a
    # decorative getHorizontalLine that has no lblXYZ reference — the resulting
    # sub-group is not a standalone section and belongs with the next labeled
    # one (e.g. HmIP-PSM-CO's "Wohnort": LONGITUDE has no label, LATITUDE has
    # lblLocation → merge so both land under "Wohnort").
    non_empty_groups = _merge_unlabeled_groups(non_empty_groups)

    if not param_order:
        return None

    result: dict[str, Any] = {"parameter_order": param_order}

    # Build parameter_groups. The original rule is "emit only when we have more
    # than one non-empty group" — a single TCL sub-group carries no extra
    # structure worth persisting. We also emit when the merge collapsed a
    # multi-group dialog down to a single *labeled* group, so its label isn't
    # lost (e.g. OPTICAL_SIGNAL_RECEIVER).
    should_emit = len(non_empty_groups) > 1 or (
        len(non_empty_groups) == 1 and pre_merge_count > 1 and non_empty_groups[0][1]
    )
    if should_emit:
        param_groups: list[dict[str, Any]] = []
        for idx, (params, label) in enumerate(non_empty_groups):
            param_groups.append(
                {
                    "id": f"group_{idx}",
                    "label_key": label,
                    "parameters": params,
                }
            )
        result["parameter_groups"] = param_groups

    # Store option presets
    if option_presets:
        result["option_presets"] = option_presets

    # Store inline options as new option preset types
    if inline_options:
        result["inline_options"] = inline_options

    # Store conditional visibility (deduplicated)
    if conditional_visibility:
        seen_cv: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for cv in conditional_visibility:
            key = (
                f"{cv['trigger']}:{cv.get('trigger_value')}:"
                f"{','.join(sorted(cv.get('show', [])))}:"
                f"{','.join(sorted(cv.get('hide', [])))}"
            )
            if key not in seen_cv:
                seen_cv.add(key)
                deduped.append(cv)
        result["conditional_visibility"] = deduped

    return result


def parse_hmip_channel_dialogs(
    content: str,
) -> dict[str, dict[str, Any]]:
    """
    Parse hmipChannelConfigDialogs.tcl and extract metadata per dialog function.

    Returns {function_name: metadata_dict}.
    """
    procs = _split_procs(content)
    results: dict[str, dict[str, Any]] = {}

    for proc_name, proc_body in procs.items():
        if proc_name == "getNoParametersToSet":
            continue
        parsed = _parse_dialog_proc(proc_body)
        if parsed:
            results[proc_name] = parsed

    return results


def _map_hmip_master_files(
    hmip_dir: Path,
) -> dict[str, str]:
    """
    Map channel types to dialog function names by parsing hmip/*.tcl files.

    Returns {channel_type: function_name}.
    """
    mapping: dict[str, str] = {}
    for tcl_file in sorted(hmip_dir.glob("*.tcl")):
        name = tcl_file.stem
        # Skip device-model-specific master files (e.g., hmip-ps_1_master)
        if name.startswith("hmip") and "_master" in name:
            continue
        content = _read_file(tcl_file)
        func_match = _RE_HMIP_FUNC_CALL.search(content)
        if func_match:
            func_name = func_match.group(1)
            mapping[name] = func_name
    return mapping


def _merge_master_metadata(
    channel_metadata: dict[str, dict[str, Any]],
    dialog_metadata: dict[str, dict[str, Any]],
    channel_to_func: dict[str, str],
    option_presets: dict[str, Any],
) -> None:
    """Merge MASTER dialog metadata into channel_metadata under _MASTER sender type."""
    for channel_type, func_name in channel_to_func.items():
        func_meta = dialog_metadata.get(func_name)
        if not func_meta:
            continue

        # Build sender type metadata for _MASTER
        master_meta: dict[str, Any] = {}

        if "parameter_order" in func_meta:
            master_meta["parameter_order"] = func_meta["parameter_order"]

        if "parameter_groups" in func_meta:
            master_meta["parameter_groups"] = func_meta["parameter_groups"]

        if "conditional_visibility" in func_meta:
            master_meta["conditional_visibility"] = func_meta["conditional_visibility"]

        # Merge option presets from dialog function
        merged_presets: dict[str, str] = {}
        if "option_presets" in func_meta:
            merged_presets.update(func_meta["option_presets"])

        # Convert inline options to new option preset types
        if "inline_options" in func_meta:
            for param, options_dict in func_meta["inline_options"].items():
                preset_type = f"_INLINE_{channel_type}_{param}"
                presets_list = [{"value": k, "label_key": v} for k, v in sorted(options_dict.items())]
                option_presets[preset_type] = {
                    "presets": presets_list,
                    "allow_custom": False,
                }
                merged_presets[param] = preset_type

        if merged_presets:
            master_meta["option_presets"] = merged_presets

        if not master_meta:
            continue

        # Ensure channel_metadata entry exists
        if channel_type not in channel_metadata:
            channel_metadata[channel_type] = {
                "channel_type": channel_type,
                "sender_types": {},
            }

        channel_metadata[channel_type]["sender_types"][_MASTER_SENDER_TYPE] = master_meta

    merged_count = sum(1 for ct in channel_metadata.values() if _MASTER_SENDER_TYPE in ct.get("sender_types", {}))
    print(f"  Merged _MASTER metadata for {merged_count} channel types")


# ---------------------------------------------------------------------------
# Options.tcl parsing
# ---------------------------------------------------------------------------


def parse_options_tcl(content: str) -> dict[str, Any]:
    """Parse options.tcl and extract all option preset definitions."""
    option_sets: dict[str, Any] = {}

    # Parse by finding "TYPE" { lines and their matching closing }
    # Line-based parsing avoids issues with } inside ${...} localization keys.
    type_header_re = re.compile(r'^\s+"([A-Z_0-9a-z]+)"\s*\{', re.MULTILINE)
    lines = content.split("\n")
    sections: list[tuple[str, str]] = []

    for m in type_header_re.finditer(content):
        option_type = m.group(1)
        start_line_idx = content[: m.start()].count("\n")

        # Find matching closing } at indent level 4
        body_lines: list[str] = []
        for li in range(start_line_idx + 1, len(lines)):
            line = lines[li]
            # Closing brace: exactly 4 spaces followed by } and optional whitespace
            if re.match(r"^ {4}\}\s*$", line):
                break
            body_lines.append(line)

        body = "\n".join(body_lines)
        sections.append((option_type, body))

    for option_type, body in sections:
        presets: dict[str, dict[str, Any]] = {}
        allow_custom = False

        for om in _RE_OPTION_SET.finditer(body):
            raw_key = om.group(1).strip()
            raw_label = om.group(2).strip().strip('"')

            key_num = _to_number(raw_key)

            # Check for special sentinel values (enterValue, etc.)
            if isinstance(key_num, (int, float)) and key_num in _SPECIAL_OPTION_VALUES:
                allow_custom = True
                continue

            entry: dict[str, Any] = {"value": key_num}
            if lk := _RE_LOCALIZATION_KEY.search(raw_label):
                entry["label_key"] = lk.group(1)
            else:
                # Resolve unit variables ($s, $m, $h, $d, $p)
                label = raw_label
                label = label.replace("$s", "s").replace("$m", "min")
                label = label.replace("$h", "h").replace("$d", "d")
                label = label.replace("$p", "%")
                entry["label"] = label

            presets[raw_key] = entry

        # Sort presets by numeric value
        sorted_presets = [presets[k] for k in sorted(presets, key=lambda x: float(_to_number(x)))]

        if sorted_presets:
            option_sets[option_type] = {
                "presets": sorted_presets,
                "allow_custom": allow_custom,
            }

    return option_sets


# ---------------------------------------------------------------------------
# Source loading (local + remote)
# ---------------------------------------------------------------------------


def _get_channel_type_dirs(easymode_dir: Path) -> dict[str, Path]:
    """Return {channel_type: path} for all channel type directories."""
    result: dict[str, Path] = {}
    for entry in sorted(easymode_dir.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name in _SKIP_DIRS:
            continue
        if entry.name.startswith("."):
            continue
        result[entry.name] = entry
    return result


def load_local(occu_path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """
    Load easymode data from local OCCU checkout.

    Returns (channel_metadata, option_presets).
    """
    webui_www = occu_path / "WebUI" / "www"
    easymode_dir = webui_www / _EASYMODE_DIR

    if not easymode_dir.is_dir():
        print(f"ERROR: Easymode directory not found: {easymode_dir}", file=sys.stderr)
        return {}, {}

    # Parse options.tcl
    options_path = webui_www / _OPTIONS_TCL_PATH
    option_presets: dict[str, Any] = {}
    if options_path.is_file():
        option_presets = parse_options_tcl(_read_file(options_path))
        print(f"  Parsed options.tcl: {len(option_presets)} option types")

    # Parse channel type directories (LINK easymode profiles)
    channel_metadata: dict[str, dict[str, Any]] = {}
    ct_dirs = _get_channel_type_dirs(easymode_dir)
    print(f"  Found {len(ct_dirs)} channel type directories")

    for ct_name, ct_dir in ct_dirs.items():
        tcl_files = sorted(ct_dir.glob("*.tcl"))
        if not tcl_files:
            continue

        # Merge all TCL files for this channel type
        merged: dict[str, Any] = {
            "channel_type": ct_name,
            "sender_types": {},
        }

        for tcl_file in tcl_files:
            sender_type = tcl_file.stem
            content = _read_file(tcl_file)
            parsed = parse_tcl_easymode(content)
            if parsed:
                merged["sender_types"][sender_type] = parsed

        if merged["sender_types"]:
            channel_metadata[ct_name] = merged

    print(f"  Parsed {len(channel_metadata)} channel types with LINK easymode data")

    # Parse hmipChannelConfigDialogs.tcl for MASTER paramset metadata
    dialogs_path = webui_www / _HMIP_CHANNEL_DIALOGS_PATH
    hmip_dir = webui_www / _HMIP_MASTER_DIR

    if dialogs_path.is_file() and hmip_dir.is_dir():
        print(f"\n  Parsing HmIP MASTER dialogs from {dialogs_path.name} ...")
        dialog_content = _read_file(dialogs_path)
        dialog_metadata = parse_hmip_channel_dialogs(dialog_content)
        print(f"  Parsed {len(dialog_metadata)} dialog functions")

        channel_to_func = _map_hmip_master_files(hmip_dir)
        print(f"  Mapped {len(channel_to_func)} channel types to dialog functions")

        _merge_master_metadata(
            channel_metadata=channel_metadata,
            dialog_metadata=dialog_metadata,
            channel_to_func=channel_to_func,
            option_presets=option_presets,
        )
    else:
        print("  Note: hmipChannelConfigDialogs.tcl or hmip/ directory not found, skipping MASTER metadata")

    return channel_metadata, option_presets


def load_remote(ccu_url: str) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """
    Load easymode data from remote CCU via HTTP.

    Returns (channel_metadata, option_presets).
    """
    # Create SSL context that ignores certificate errors (self-signed CCU certs)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    base_url = ccu_url.rstrip("/")

    def fetch(path: str) -> str | None:
        url = f"{base_url}/{path}"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:  # nosec B310 - dev-only CCU data extraction
                data = resp.read()
                try:
                    return data.decode("utf-8")
                except UnicodeDecodeError:
                    return data.decode("iso-8859-1")
        except Exception as exc:
            print(f"  Warning: Failed to fetch {url}: {exc}")
            return None

    # Parse options.tcl
    option_presets: dict[str, Any] = {}
    options_content = fetch(_OPTIONS_TCL_PATH)
    if options_content:
        option_presets = parse_options_tcl(options_content)
        print(f"  Parsed remote options.tcl: {len(option_presets)} option types")

    # Remote mode: we can't list directories, so we try known channel types
    # This is a best-effort approach; local mode is preferred for completeness
    channel_metadata: dict[str, dict[str, Any]] = {}
    print("  Note: Remote mode cannot discover all channel types. Use OCCU_PATH for full extraction.")

    return channel_metadata, option_presets


def _merge_sources(
    base: tuple[dict[str, dict[str, Any]], dict[str, Any]],
    overlay: tuple[dict[str, dict[str, Any]], dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Merge two data sources. Overlay takes precedence."""
    base_meta, base_presets = base
    overlay_meta, overlay_presets = overlay

    merged_meta = dict(base_meta)
    merged_meta.update(overlay_meta)

    merged_presets = dict(base_presets)
    merged_presets.update(overlay_presets)

    return merged_meta, merged_presets


# ---------------------------------------------------------------------------
# Output generation
# ---------------------------------------------------------------------------


def generate_output(
    channel_metadata: dict[str, dict[str, Any]],
    option_presets: dict[str, Any],
    output_dir: Path,
) -> None:
    """Generate a single gzip-compressed JSON archive."""
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / "easymode_extract.json.gz"

    archive = {
        "channel_metadata": dict(sorted(channel_metadata.items())),
        "option_presets": dict(sorted(option_presets.items())),
        "cross_validations": {"rules": _CROSS_VALIDATION_RULES},
    }

    raw = json.dumps(archive, separators=(",", ":"), ensure_ascii=False, sort_keys=True).encode()
    with gzip.open(archive_path, "wb", compresslevel=9) as gz:
        gz.write(raw)

    size_kb = archive_path.stat().st_size / 1024
    print(f"\nWriting output to {archive_path}")
    print(f"  {len(channel_metadata)} channel types")
    print(f"  {len(option_presets)} option preset types")
    print(f"  {len(_CROSS_VALIDATION_RULES)} cross-validation rules")
    print(f"  Archive size: {size_kb:.0f} KB")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    """Run the extraction pipeline."""
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

    output_dir = Path(output_dir_str)
    if not output_dir.is_absolute():
        output_dir = project_root / output_dir

    # Load sources
    sources: list[tuple[dict[str, dict[str, Any]], dict[str, Any]]] = []

    if occu_path:
        resolved_occu = Path(occu_path)
        if not resolved_occu.is_absolute():
            resolved_occu = project_root / resolved_occu
        resolved_occu = resolved_occu.resolve()
        print(f"Loading easymode data from {resolved_occu} ...")
        sources.append(load_local(resolved_occu))

    if ccu_url:
        print(f"\nLoading easymode data from {ccu_url} ...")
        sources.append(load_remote(ccu_url))

    if len(sources) == 1:
        channel_metadata, option_presets = sources[0]
    else:
        channel_metadata, option_presets = _merge_sources(sources[0], sources[1])
        print("\nMerged local and remote sources.")

    if not channel_metadata and not option_presets:
        print("ERROR: No data extracted.", file=sys.stderr)
        return 1

    generate_output(channel_metadata, option_presets, output_dir)

    print(f"\nDone. Easymode archive written to {output_dir}/easymode_extract.json.gz")
    return 0


if __name__ == "__main__":
    sys.exit(main())
