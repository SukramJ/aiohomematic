# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Serialization utilities for session recording.

This module provides functions to freeze and unfreeze Python objects for use
as dictionary keys in session caching. These utilities handle complex nested
structures including dicts, lists, sets, and datetime objects.

Public API
----------
- freeze_params: Convert any structure to a hashable string key
- unfreeze_params: Reconstruct original structure from frozen string
- cleanup_params_for_session: Clean script content in params for lookup
"""

from __future__ import annotations

import ast
from datetime import datetime
from typing import Any, Final

from aiohomematic.support import cleanup_script_for_session_recorder

_SCRIPT_KEY: Final = "script"


def cleanup_params_for_session(*, params: Any) -> Any:
    """Clean script in params for session lookup, keeping only !# name: and !# param: lines."""
    if isinstance(params, dict) and _SCRIPT_KEY in params:
        cleaned_params = dict(params)
        cleaned_params[_SCRIPT_KEY] = cleanup_script_for_session_recorder(script=params[_SCRIPT_KEY])
        return cleaned_params
    return params


def freeze_params(*, params: Any) -> str:
    """
    Recursively freeze any structure so it can be used as a dictionary key.

    Purpose:
        Session recording needs to cache RPC responses keyed by their parameters.
        Python dicts require hashable keys, but RPC params can contain unhashable
        types (dict, list, set, datetime). This function converts any structure
        into a string representation suitable for use as a dict key.

    Transformation rules:
        - dict → dict with recursively frozen values, keys sorted for determinism
        - list/tuple → tuple of frozen elements (tuples are hashable)
        - set/frozenset → tagged tuple ("__set__", sorted frozen elements)
        - datetime → tagged tuple ("__datetime__", ISO 8601 string)
        - other types → unchanged (assumed hashable: str, int, bool, None)

    Tagged tuples:
        Sets and datetimes use a tag prefix ("__set__", "__datetime__") so that
        unfreeze_params can reconstruct the original type during deserialization.

    Why sort?
        Sorting dict keys and set elements ensures deterministic output.
        Without sorting, {"a":1, "b":2} and {"b":2, "a":1} would produce
        different frozen strings, breaking cache lookups.

    Returns:
        String representation of the frozen structure, suitable for dict keys.

    """
    res: Any = ""
    match params:
        case datetime():
            # orjson cannot serialize datetime objects as dict keys even with OPT_NON_STR_KEYS.
            # Use a tagged ISO string to preserve value and guarantee a stable, hashable key.
            res = ("__datetime__", params.isoformat())
        case dict():
            # Sort by key for deterministic output regardless of insertion order
            res = {k: freeze_params(params=v) for k, v in sorted(params.items())}
        case list() | tuple():
            # Convert to tuple (hashable) while preserving element order
            res = tuple(freeze_params(params=x) for x in params)
        case set() | frozenset():
            # Sets are unordered, so sort by repr for determinism.
            # Tag with "__set__" so unfreeze_params can reconstruct.
            frozen_elems = tuple(sorted((freeze_params(params=x) for x in params), key=repr))
            res = ("__set__", frozen_elems)
        case _:
            # Primitives (str, int, bool, None) pass through unchanged
            res = params

    return str(res)


def unfreeze_params(*, frozen_params: str) -> Any:
    """
    Reverse the freeze_params transformation.

    Purpose:
        Reconstruct the original parameter structure from a frozen string.
        Used when loading cached session data to get back the original params.

    Algorithm:
        1. Parse the frozen string using ast.literal_eval (safe eval for literals)
        2. Recursively walk the parsed structure
        3. Detect tagged tuples and reconstruct original types:
           - ("__set__", items) → set(items)
           - ("__datetime__", iso_string) → datetime object
        4. Recursively process nested dicts, lists, and tuples

    Error handling:
        If ast.literal_eval fails (malformed string), return the original string.
        This provides graceful degradation for corrupted cache entries.

    The _walk helper:
        Performs depth-first traversal, checking each node for tagged tuples
        before recursively processing children. Order matters: check tags first,
        then handle generic containers.
    """
    try:
        obj = ast.literal_eval(frozen_params)
    except Exception:
        # Malformed frozen string - return as-is for graceful degradation
        return frozen_params

    def _walk(o: Any) -> Any:
        """Recursively reconstruct original types from frozen representation."""
        if o and isinstance(o, tuple):
            tag = o[0]
            # Check for tagged set: ("__set__", (item1, item2, ...))
            if tag == "__set__" and len(o) == 2 and isinstance(o[1], tuple):
                return {_walk(x) for x in o[1]}
            # Check for tagged datetime: ("__datetime__", "2024-01-01T00:00:00")
            if tag == "__datetime__" and len(o) == 2 and isinstance(o[1], str):
                try:
                    return datetime.fromisoformat(o[1])
                except Exception:
                    # Invalid ISO format - return the string value
                    return o[1]
            # Generic tuple - recursively process elements
            return tuple(_walk(x) for x in o)
        if isinstance(o, dict):
            # Recursively process dict values (keys are always strings)
            return {k: _walk(v) for k, v in o.items()}
        if isinstance(o, list):
            return [_walk(x) for x in o]
        if isinstance(o, tuple):
            return tuple(_walk(x) for x in o)
        # Handle string that looks like a dict literal (edge case from old format)
        if isinstance(o, str) and o.startswith("{") and o.endswith("}"):
            return ast.literal_eval(o)
        return o

    return _walk(obj)
