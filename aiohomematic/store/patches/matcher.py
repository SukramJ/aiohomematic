# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Paramset patch matcher for applying device-specific corrections.

This module provides the ParamsetPatchMatcher class that matches and applies
patches to paramset descriptions based on device context.

Public API of this module is defined by __all__.
"""

from __future__ import annotations

import logging
from typing import Any, Final, cast

from aiohomematic.const import ParameterData, ParamsetKey
from aiohomematic.store.patches.paramset_patches import PARAMSET_PATCHES, ParamsetPatch
from aiohomematic.support import get_split_channel_address

__all__ = [
    "ParamsetPatchMatcher",
]

_LOGGER: Final = logging.getLogger(__name__)


class ParamsetPatchMatcher:
    """
    Matcher for paramset patches based on device context.

    Pre-filters patches for a specific device type and provides O(1) lookup
    for matching patches during paramset description processing.
    """

    __slots__ = ("_device_type", "_patches_by_key")

    def __init__(self, *, device_type: str) -> None:
        """
        Initialize matcher for a specific device type.

        Args:
            device_type: The device TYPE from DeviceDescription.

        """
        self._device_type: Final = device_type
        # Pre-filter patches for this device type for O(1) lookup
        # Note: Parameter is StrEnum, so it's compatible with str for dict lookup
        # Device type comparison is case-insensitive (consistent with rest of codebase)
        device_type_lower = device_type.lower()
        self._patches_by_key: Final[dict[tuple[int | None, ParamsetKey | None, str], ParamsetPatch]] = {
            (p.channel_no, p.paramset_key, p.parameter): p
            for p in PARAMSET_PATCHES
            if p.device_type.lower() == device_type_lower
        }

    @property
    def has_patches(self) -> bool:
        """Return True if there are patches for this device type."""
        return bool(self._patches_by_key)

    def apply_patches(
        self,
        *,
        channel_address: str,
        paramset_key: ParamsetKey,
        paramset_description: dict[str, ParameterData],
    ) -> dict[str, ParameterData]:
        """
        Apply patches to a paramset description.

        Args:
            channel_address: Channel address (e.g., "VCU0000001:1").
            paramset_key: The paramset key (MASTER, VALUES, etc.).
            paramset_description: The normalized paramset to patch.

        Returns:
            Patched paramset description (same dict, mutated in place).

        """
        if not self._patches_by_key:
            return paramset_description  # No patches for this device type

        _, channel_no = get_split_channel_address(channel_address=channel_address)

        for parameter, param_data in paramset_description.items():
            if (
                patch := self._find_matching_patch(
                    channel_no=channel_no,
                    paramset_key=paramset_key,
                    parameter=parameter,
                )
            ) is not None:
                self._apply_patch(
                    channel_address=channel_address,
                    paramset_key=paramset_key,
                    parameter=parameter,
                    param_data=param_data,
                    patch=patch,
                )

        return paramset_description

    def _apply_patch(
        self,
        *,
        channel_address: str,
        paramset_key: ParamsetKey,
        parameter: str,
        param_data: ParameterData,
        patch: ParamsetPatch,
    ) -> None:
        """Apply a single patch to parameter data."""
        # Cast to dict for dynamic key access (ParameterData is TypedDict)
        data = cast(dict[str, Any], param_data)
        for field, new_value in patch.patches.items():
            if (old_value := data.get(field)) != new_value:
                _LOGGER.debug(
                    "PARAMSET_PATCH: %s %s/%s.%s: %s=%r -> %r (reason: %s)",
                    self._device_type,
                    channel_address,
                    paramset_key.value,
                    parameter,
                    field,
                    old_value,
                    new_value,
                    patch.reason,
                )
                data[field] = new_value

    def _find_matching_patch(
        self,
        *,
        channel_no: int | None,
        paramset_key: ParamsetKey,
        parameter: str,
    ) -> ParamsetPatch | None:
        """
        Find the most specific matching patch.

        Priority order (most specific first):
        1. Exact match: channel_no + paramset_key + parameter
        2. Any channel: None + paramset_key + parameter
        3. Any paramset_key: channel_no + None + parameter
        4. Any channel & paramset_key: None + None + parameter
        """
        lookup_keys = [
            (channel_no, paramset_key, parameter),  # Exact match
            (None, paramset_key, parameter),  # Any channel
            (channel_no, None, parameter),  # Any paramset_key
            (None, None, parameter),  # Any channel & paramset_key
        ]
        for key in lookup_keys:
            if (patch := self._patches_by_key.get(key)) is not None:
                return patch
        return None
