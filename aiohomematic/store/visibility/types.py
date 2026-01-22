# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Type definitions for the visibility system.

This module contains shared type aliases and data classes used across
the visibility system components.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, NamedTuple

from aiohomematic.const import ParamsetKey

# =============================================================================
# Type Aliases
# =============================================================================

ModelName = str
ChannelNo = int | None
ParameterName = str


# =============================================================================
# Cache Key Types
# =============================================================================


class IgnoreCacheKey(NamedTuple):
    """Cache key for parameter_is_ignored lookups."""

    model: ModelName
    channel_no: ChannelNo
    paramset_key: ParamsetKey
    parameter: ParameterName


class UnIgnoreCacheKey(NamedTuple):
    """Cache key for parameter_is_un_ignored lookups."""

    model: ModelName
    channel_no: ChannelNo
    paramset_key: ParamsetKey
    parameter: ParameterName
    custom_only: bool


# =============================================================================
# Parsed Rules Container
# =============================================================================


@dataclass(frozen=True, slots=True)
class ParsedUnIgnoreRules:
    """
    Container for parsed un-ignore rules.

    This dataclass holds the result of parsing un-ignore configuration
    entries and device-specific rules.

    Attributes:
        custom_un_ignore_rules: User-provided model-specific un-ignore rules (ModelRules).
        custom_un_ignore_values_parameters: Simple parameter names for VALUES paramsets.
        device_un_ignore_rules: Device-specific rules from RELEVANT_MASTER_PARAMSETS_BY_DEVICE.
        relevant_master_channels: Mapping of model to channels requiring MASTER paramset.

    """

    # Using Any to avoid circular import with ModelRules from registry.py
    # At runtime, these will be ModelRules instances
    custom_un_ignore_rules: Any
    custom_un_ignore_values_parameters: frozenset[ParameterName]
    device_un_ignore_rules: Any
    relevant_master_channels: dict[ModelName, set[ChannelNo]]
