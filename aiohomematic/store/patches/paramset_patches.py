# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Paramset description patch definitions.

This module contains declarative patch definitions for correcting incorrect
paramset descriptions returned by the CCU. Each patch specifies matching
criteria and the fields to correct.

Public API of this module is defined by __all__.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from aiohomematic.const import Parameter, ParamsetKey

__all__ = [
    "PARAMSET_PATCHES",
    "ParamsetPatch",
]


@dataclass(frozen=True, slots=True)
class ParamsetPatch:
    """
    Definition of a paramset description patch.

    A patch specifies matching criteria and the fields to correct in the
    parameter data. Patches are applied at ingestion time when fetching
    paramset descriptions from the CCU.
    """

    # Matching criteria
    device_type: str
    """Device TYPE from DeviceDescription (e.g., "HM-CC-VG-1")."""

    channel_no: int | None
    """Channel number to match. None matches all channels."""

    paramset_key: ParamsetKey | None
    """Paramset key to match. None matches all paramset keys."""

    parameter: Parameter
    """Parameter to match (e.g., Parameter.SET_TEMPERATURE)."""

    # Fields to patch
    patches: dict[str, Any]
    """Fields to patch with their correct values (e.g., {"MIN": 4.5, "MAX": 30.5})."""

    # Metadata
    reason: str
    """Justification for this patch."""

    ticket: str | None = None
    """Issue/ticket reference for traceability."""


# =============================================================================
# Central Registry of Paramset Patches
# =============================================================================
#
# Add new patches here. Each patch must include:
# - Specific matching criteria (device_type is required)
# - The fields to correct with their proper values
# - A clear reason explaining why the patch is needed
# - Optionally a ticket reference for traceability
#
# Patches are matched in priority order: most specific first.

PARAMSET_PATCHES: Final[tuple[ParamsetPatch, ...]] = (
    # -------------------------------------------------------------------------
    # HM-CC-VG-1: Virtual Heating Group
    # -------------------------------------------------------------------------
    # The CCU returns invalid MIN/MAX bounds for SET_TEMPERATURE in virtual
    # heating groups. The values are either 0/0 or returned as strings.
    ParamsetPatch(
        device_type="HM-CC-VG-1",
        channel_no=1,
        paramset_key=ParamsetKey.VALUES,
        parameter=Parameter.SET_TEMPERATURE,
        patches={"MIN": 4.5, "MAX": 30.5},
        reason="CCU returns invalid MIN/MAX bounds for virtual heating groups",
        ticket=None,
    ),
    # -------------------------------------------------------------------------
    # Add more patches below as needed
    # -------------------------------------------------------------------------
)
