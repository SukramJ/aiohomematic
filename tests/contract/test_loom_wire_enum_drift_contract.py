# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Drift guard: aiohomematic enums vs. the openccu-loom wire catalogue.

STABILITY GUARANTEE
-------------------
The openccu-loom daemon ships the data-point ``category`` and
``data_point_type`` on the wire (Strategy B). The ``homematicip_local``
Home Assistant integration filters entities on ``aiohomematic.const``
enum values; when it runs against the daemon (via the
``py-openccu-loom-client`` drop-in) those same values arrive as wire
strings. The two catalogues are therefore one shared contract and must
stay set-equal — a value added, dropped or renamed on either side is a
breaking change for the drop-in.

This guard complements ``test_enum_constants_contract.py``: that file
pins individual aiohomematic enum members; this file asserts the *whole
set* matches the daemon's published catalogue.

The daemon catalogue is vendored as ``loom_wire_enums.json`` (aiohomematic
takes no dependency on the openccu-loom ecosystem). Refresh it with
``tests/contract/refresh_loom_wire_enums.py`` when the wire contract
changes; see ``openccu-loom/docs/external-clients/drop-in-optimizations.md``.

A failure here is intentional friction, not a flaky test: reconcile the
two catalogues (and the vendored snapshot) before shipping.
"""

from __future__ import annotations

import json
from pathlib import Path

from aiohomematic.const import DataPointCategory, DataPointType

_WIRE_CATALOGUE = json.loads((Path(__file__).parent / "loom_wire_enums.json").read_text())


def _aiohomematic_values(enum: type) -> set[str]:
    return {member.value for member in enum}


def _wire_values(name: str) -> set[str]:
    return set(_WIRE_CATALOGUE[name])


class TestLoomWireEnumDriftContract:
    """Contract: aiohomematic's category/type enums equal the daemon wire set."""

    def test_data_point_category_matches_wire(self) -> None:
        """Contract: DataPointCategory value set equals the daemon wire catalogue."""
        aioh = _aiohomematic_values(DataPointCategory)
        wire = _wire_values("DataPointCategory")
        assert aioh == wire, (
            "DataPointCategory drifted from the openccu-loom wire contract.\n"
            f"  only in aiohomematic: {sorted(aioh - wire)}\n"
            f"  only on the wire:     {sorted(wire - aioh)}\n"
            "Reconcile both repos, then refresh the vendored snapshot via "
            "tests/contract/refresh_loom_wire_enums.py."
        )

    def test_data_point_type_matches_wire(self) -> None:
        """Contract: DataPointType value set equals the daemon wire catalogue."""
        aioh = _aiohomematic_values(DataPointType)
        wire = _wire_values("DataPointType")
        assert aioh == wire, (
            "DataPointType drifted from the openccu-loom wire contract.\n"
            f"  only in aiohomematic: {sorted(aioh - wire)}\n"
            f"  only on the wire:     {sorted(wire - aioh)}\n"
            "Reconcile both repos, then refresh the vendored snapshot via "
            "tests/contract/refresh_loom_wire_enums.py."
        )

    def test_vendored_snapshot_is_non_empty(self) -> None:
        """Guard the guard: a truncated/empty snapshot must not pass silently."""
        assert _wire_values("DataPointCategory"), "vendored DataPointCategory snapshot is empty"
        assert _wire_values("DataPointType"), "vendored DataPointType snapshot is empty"
