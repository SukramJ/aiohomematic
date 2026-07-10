# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract tests for the Quantity and ValueBehavior enums.

STABILITY GUARANTEE
-------------------
Quantity and ValueBehavior are consumed by downstream integrations
(homematicip_local) for unit-of-measurement and state-class mapping. These
tests guard against silent removal of essential enum members.
"""

from __future__ import annotations

from aiohomematic.const import Quantity, ValueBehavior


def test_quantity_enum_covers_essential_types():
    """Verify Quantity enum includes all essential measurement types."""
    essential = {
        "temperature",
        "humidity",
        "voltage",
        "current",
        "power",
        "energy",
        "pressure",
        "illuminance",
        "signal_strength",
        "wind_speed",
        "battery",
        "motion",
        "smoke",
        "window",
    }
    quantity_values = {q.value for q in Quantity}
    missing = essential - quantity_values
    assert not missing, f"Quantity enum missing essential types: {missing}"


def test_value_behavior_enum_values():
    """Verify ValueBehavior enum has exactly the expected values."""
    assert set(ValueBehavior) == {
        ValueBehavior.INSTANTANEOUS,
        ValueBehavior.CUMULATIVE,
        ValueBehavior.MONOTONIC,
    }
