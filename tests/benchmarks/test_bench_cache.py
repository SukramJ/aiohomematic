# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Performance benchmarks for CommandTracker cache operations."""

import pytest

from aiohomematic.const import DataPointKey, ParamsetKey
from aiohomematic.store.dynamic import CommandTracker

from .conftest import BenchmarkTimer


@pytest.fixture
def tracker() -> CommandTracker:
    """Create a CommandTracker for benchmarking."""
    return CommandTracker(interface_id="bench-iface")


@pytest.mark.benchmark
def test_command_tracker_add_set_value(bench: BenchmarkTimer, tracker: CommandTracker) -> None:
    """Benchmark: adding commands via set_value with address reuse."""
    iterations = 5000

    with bench.measure(name="add_set_value", iterations=iterations):
        for i in range(iterations):
            # Reuse addresses to stay within size limits (realistic: updates to same devices)
            tracker.add_set_value(
                channel_address=f"VCU{i % 100:07d}:1",
                parameter="STATE",
                value=i % 2 == 0,
            )

    result = bench.last()
    assert result.ops_per_sec > 5000, f"Expected >5k ops/s, got {result.ops_per_sec:.0f}"


@pytest.mark.benchmark
def test_command_tracker_get_last_value(bench: BenchmarkTimer, tracker: CommandTracker) -> None:
    """Benchmark: looking up cached command values."""
    # Pre-populate with data (within size limits)
    for i in range(200):
        tracker.add_set_value(
            channel_address=f"VCU{i:07d}:1",
            parameter="STATE",
            value=True,
        )

    iterations = 10_000

    with bench.measure(name="get_last_value", iterations=iterations):
        for i in range(iterations):
            idx = i % 200
            dpk = DataPointKey(
                interface_id="bench-iface",
                channel_address=f"VCU{idx:07d}:1",
                paramset_key=ParamsetKey.VALUES,
                parameter="STATE",
            )
            tracker.get_last_value_send(dpk=dpk)

    result = bench.last()
    assert result.ops_per_sec > 50_000, f"Expected >50k ops/s, got {result.ops_per_sec:.0f}"


@pytest.mark.benchmark
def test_command_tracker_add_put_paramset(bench: BenchmarkTimer, tracker: CommandTracker) -> None:
    """Benchmark: adding commands via put_paramset (batch)."""
    iterations = 2000
    values = {"TEMPERATURE": 21.5, "HUMIDITY": 65, "STATE": True}

    with bench.measure(name="add_put_paramset", iterations=iterations):
        for i in range(iterations):
            # Reuse addresses to stay within size limits
            tracker.add_put_paramset(
                channel_address=f"VCU{i % 50:07d}:1",
                paramset_key=ParamsetKey.VALUES,
                values=values,
            )

    result = bench.last()
    assert result.ops_per_sec > 1000, f"Expected >1k ops/s, got {result.ops_per_sec:.0f}"
