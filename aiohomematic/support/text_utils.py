# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Text encoding utilities for aiohomematic.

Provides helpers for handling encoding issues when communicating
with the Homematic CCU via XML-RPC (ISO-8859-1 transport).
"""

import inspect


def fix_xml_rpc_encoding(*, text: str) -> str:
    """
    Fix UTF-8 strings that were incorrectly decoded as ISO-8859-1.

    The CCU XML-RPC interface uses ISO-8859-1 encoding, but user-defined
    strings (e.g., link names) may be stored as UTF-8 on the CCU.  When
    the XML-RPC client decodes these bytes as ISO-8859-1, multi-byte
    UTF-8 sequences are misinterpreted (e.g., 'ü' becomes 'Ã¼').

    This function reverses the misinterpretation by re-encoding as
    ISO-8859-1 (to recover the original bytes) and then decoding as UTF-8.
    If the string is already correct (pure ASCII or genuine ISO-8859-1),
    the fallback returns the original string unchanged.
    """
    try:
        return text.encode("iso-8859-1").decode("utf-8")
    except UnicodeDecodeError, UnicodeEncodeError:
        return text


__all__ = tuple(
    sorted(
        name
        for name, obj in globals().items()
        if not name.startswith("_")
        and (inspect.isfunction(obj) or inspect.isclass(obj))
        and getattr(obj, "__module__", __name__) == __name__
    )
)
