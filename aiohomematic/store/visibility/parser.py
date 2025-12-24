# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Un-ignore configuration line parser.

This module provides parsing functionality for un-ignore configuration entries
that allow users to override default parameter visibility rules.

Supported formats:
- Simple: "PARAMETER_NAME" (applies to all VALUES paramsets)
- Complex: "PARAMETER:PARAMSET_KEY@MODEL:CHANNEL_NO"

Example complex entries:
- "TEMPERATURE_OFFSET:MASTER@HmIP-eTRV:1"
- "LEVEL:VALUES@HmIP-BROLL:3"
- "STATE:VALUES@*:*" (wildcard for all models/channels)
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Final

from aiohomematic.const import UN_IGNORE_WILDCARD, ParamsetKey
from aiohomematic.store.visibility.rules import ChannelNo, ModelName, ParameterName

# Type alias for channel numbers in un-ignore entries (can include wildcard string)
UnIgnoreChannelNo = ChannelNo | str

# Regex pattern for parsing un-ignore configuration lines.
# Format: PARAMETER:PARAMSET_KEY@MODEL:CHANNEL_NO
_UN_IGNORE_LINE_PATTERN: Final = re.compile(
    r"^(?P<parameter>[^:@]+):(?P<paramset_key>[^@]+)@(?P<model>[^:]+):(?P<channel_no>.*)$"
)


@dataclass(frozen=True, slots=True)
class UnIgnoreEntry:
    """Parsed un-ignore configuration entry."""

    model: ModelName
    channel_no: UnIgnoreChannelNo
    paramset_key: ParamsetKey
    parameter: ParameterName


@dataclass(frozen=True, slots=True)
class ParsedUnIgnoreLine:
    """Result of parsing an un-ignore configuration line."""

    entry: UnIgnoreEntry | None = None
    simple_parameter: ParameterName | None = None
    error: str | None = None

    @property
    def is_complex(self) -> bool:
        """Return True if this is a complex model/channel/paramset un-ignore."""
        return self.entry is not None

    @property
    def is_error(self) -> bool:
        """Return True if parsing failed."""
        return self.error is not None

    @property
    def is_simple(self) -> bool:
        """Return True if this is a simple VALUES parameter un-ignore."""
        return self.simple_parameter is not None


def parse_un_ignore_line(*, line: str) -> ParsedUnIgnoreLine:
    """
    Parse an un-ignore configuration line.

    Supported formats:
    - Simple: "PARAMETER_NAME" (applies to all VALUES paramsets)
    - Complex: "PARAMETER:PARAMSET_KEY@MODEL:CHANNEL_NO"

    Args:
        line: The configuration line to parse.

    Returns:
        ParsedUnIgnoreLine with either entry, simple_parameter, or error set.

    """
    if not (line := line.strip()):
        return ParsedUnIgnoreLine(error="Empty line")

    # Check for complex format with @ separator
    if "@" not in line:
        # Simple format - just a parameter name (no : allowed)
        if ":" in line:
            return ParsedUnIgnoreLine(error=f"Invalid format: ':' without '@' in '{line}'")
        return ParsedUnIgnoreLine(simple_parameter=line)

    # Complex format - parse with regex
    if not (match := _UN_IGNORE_LINE_PATTERN.match(line)):
        return ParsedUnIgnoreLine(
            error=f"Invalid complex format: '{line}'. Expected 'PARAMETER:PARAMSET@MODEL:CHANNEL'"
        )

    parameter = match.group("parameter")
    paramset_key_str = match.group("paramset_key")
    model = match.group("model").lower()
    channel_no_str = match.group("channel_no")

    # Validate paramset key
    try:
        paramset_key = ParamsetKey(paramset_key_str)
    except ValueError:
        return ParsedUnIgnoreLine(error=f"Invalid paramset key '{paramset_key_str}' in '{line}'")

    # Parse channel number
    channel_no: UnIgnoreChannelNo
    if channel_no_str == "":
        channel_no = None
    elif channel_no_str.isnumeric():
        channel_no = int(channel_no_str)
    else:
        channel_no = channel_no_str  # Could be wildcard "*"

    # Check for simple wildcard case (all models, all channels, VALUES)
    if model == UN_IGNORE_WILDCARD and channel_no == UN_IGNORE_WILDCARD and paramset_key == ParamsetKey.VALUES:
        return ParsedUnIgnoreLine(simple_parameter=parameter)

    # Validate MASTER paramset constraints
    if paramset_key == ParamsetKey.MASTER:
        if not isinstance(channel_no, int) and channel_no is not None:
            return ParsedUnIgnoreLine(error=f"Channel must be numeric or empty for MASTER paramset in '{line}'")
        if model == UN_IGNORE_WILDCARD:
            return ParsedUnIgnoreLine(error=f"Model must be specified for MASTER paramset in '{line}'")

    return ParsedUnIgnoreLine(
        entry=UnIgnoreEntry(
            model=model,
            channel_no=channel_no,
            paramset_key=paramset_key,
            parameter=parameter,
        )
    )
