# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract: aiohomematic sources its categorization enums from aiohomematic-contract.

`DataPointCategory` / `DataPointType` / `CommandPriority` are defined canonically
in the shared ``aiohomematic-contract`` package and re-exported by aiohomematic
(``const.py`` / ``aiohomematic_contract``). This guards that aiohomematic keeps
*importing* them (identity), rather than re-introducing a local copy that could
drift, and that the values still match the package's golden fixtures — the
aiohomematic half of the "both repos assert" rule in ``docs/contract-gaps.md`` (P2).
"""

import json
from typing import Any, cast

import aiohomematic_contract
from aiohomematic_contract import golden_fixture_path

from aiohomematic.const import DataPointCategory, DataPointType


def _load(name: str) -> dict[str, Any]:
    """Load a name→value golden fixture from the contract package."""
    return cast("dict[str, Any]", json.loads(golden_fixture_path(name).read_text(encoding="utf-8")))


def test_enums_are_sourced_from_contract() -> None:
    """Verify the enums are the contract objects, not a local duplicate."""
    assert DataPointCategory is aiohomematic_contract.DataPointCategory
    assert DataPointType is aiohomematic_contract.DataPointType


def test_category_values_match_contract_golden() -> None:
    """Verify the enum values still match the shared golden fixture."""
    data = _load("category")
    assert {m.name: m.value for m in DataPointCategory} == data["DataPointCategory"]
    assert {m.name: m.value for m in DataPointType} == data["DataPointType"]
