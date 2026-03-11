# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Performance benchmarks for RequestCoalescer."""

import asyncio

import pytest

from aiohomematic.client import RequestCoalescer

from .conftest import BenchmarkTimer


@pytest.mark.benchmark
async def test_coalescer_throughput(bench: BenchmarkTimer) -> None:
    """Benchmark: throughput of unique requests through the coalescer."""
    coalescer = RequestCoalescer(name="bench")
    iterations = 1000

    async def dummy_executor() -> str:
        return "result"

    with bench.measure(name="coalescer_throughput", iterations=iterations):
        for i in range(iterations):
            await coalescer.execute(key=f"unique-{i}", executor=dummy_executor)

    result = bench.last()
    assert result.ops_per_sec > 100, f"Expected >100 ops/s, got {result.ops_per_sec:.0f}"


@pytest.mark.benchmark
async def test_coalescer_deduplication(bench: BenchmarkTimer) -> None:
    """Benchmark: deduplication of concurrent identical requests."""
    coalescer = RequestCoalescer(name="bench")
    iterations = 100
    concurrent_per_key = 10

    call_count = 0

    async def counting_executor() -> str:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.001)
        return "result"

    with bench.measure(name="coalescer_dedup", iterations=iterations * concurrent_per_key):
        for i in range(iterations):
            tasks = [
                coalescer.execute(key=f"shared-{i}", executor=counting_executor) for _ in range(concurrent_per_key)
            ]
            await asyncio.gather(*tasks)

    # Verify deduplication: should have exactly `iterations` actual calls
    assert call_count == iterations
    result = bench.last()
    assert result.ops_per_sec > 50, f"Expected >50 ops/s, got {result.ops_per_sec:.0f}"


@pytest.mark.benchmark
async def test_coalescer_contention(bench: BenchmarkTimer) -> None:
    """Benchmark: lock contention with many concurrent unique requests."""
    coalescer = RequestCoalescer(name="bench")
    concurrent = 200

    async def slow_executor() -> str:
        await asyncio.sleep(0.001)
        return "result"

    with bench.measure(name="coalescer_contention", iterations=concurrent):
        tasks = [coalescer.execute(key=f"contention-{i}", executor=slow_executor) for i in range(concurrent)]
        await asyncio.gather(*tasks)

    result = bench.last()
    # All 200 should complete within ~0.01s (parallel sleep)
    assert result.total_s < 2.0, f"Expected <2s for parallel execution, got {result.total_s:.2f}s"


@pytest.mark.benchmark
async def test_coalescer_burst(bench: BenchmarkTimer) -> None:
    """Benchmark: burst of requests arriving simultaneously for same key."""
    coalescer = RequestCoalescer(name="bench")
    burst_size = 500

    async def instant_executor() -> str:
        return "result"

    with bench.measure(name="coalescer_burst", iterations=burst_size):
        tasks = [coalescer.execute(key="single-key", executor=instant_executor) for _ in range(burst_size)]
        await asyncio.gather(*tasks)

    result = bench.last()
    assert result.ops_per_sec > 1000, f"Expected >1000 ops/s, got {result.ops_per_sec:.0f}"
