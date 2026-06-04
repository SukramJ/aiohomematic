# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Golden cross-implementation test for ``generate_unique_id``.

The ``unique_id`` is the routing key for every Home Assistant value-change
subscription. ``py-openccu-loom-client`` rebuilds it independently, so the two
implementations must produce **bit-identical** output. This test pins the
format against a shared fixture (``tests/fixtures/unique_id_golden.json``); the
client repo vendors the same fixture and runs the equivalent assertion, so the
format cannot silently drift across the two repos.

The canonical home of this fixture (and a dependency-free reference
implementation) is the ``aiohomematic-contract`` package
(``aiohomematic_contract/data/unique_id_golden.json``). The copy here is
vendored from there and must stay byte-identical to it.

See ``aiohomematic/model/support.py:generate_unique_id`` and
``docs/drop-in-optimizations.md``.
"""

from dataclasses import dataclass
import json
from pathlib import Path
from typing import cast

import pytest

from aiohomematic.interfaces import ConfigProviderProtocol
from aiohomematic.model.support import generate_unique_id

_GOLDEN_FIXTURE: Path = Path(__file__).parent / "fixtures" / "unique_id_golden.json"


@dataclass(frozen=True, kw_only=True, slots=True)
class _StubConfig:
    """Minimal config exposing only the ``central_id`` that the routing key needs."""

    central_id: str


@dataclass(frozen=True, kw_only=True, slots=True)
class _StubConfigProvider:
    """Minimal config provider standing in for a full ``CentralUnit`` in the golden test."""

    config: _StubConfig


def _load_cases() -> list[dict[str, str | None]]:
    """Load the golden cases from the shared fixture."""
    data = json.loads(_GOLDEN_FIXTURE.read_text(encoding="utf-8"))
    return list(data["cases"])


@pytest.mark.parametrize("case", _load_cases())
def test_generate_unique_id_matches_golden(case: dict[str, str | None]) -> None:
    """Verify ``generate_unique_id`` reproduces the shared golden output exactly."""
    provider = cast(
        ConfigProviderProtocol,
        _StubConfigProvider(config=_StubConfig(central_id=cast(str, case["central_id"]))),
    )
    result = generate_unique_id(
        config_provider=provider,
        address=cast(str, case["address"]),
        parameter=case["parameter"],
        prefix=case["prefix"],
    )
    assert result == case["expected"]
