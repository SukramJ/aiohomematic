# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Benchmark test infrastructure."""

import asyncio
from collections.abc import AsyncGenerator, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
import time

import pytest


@pytest.fixture(autouse=True)
async def _disable_asyncio_debug() -> AsyncGenerator[None]:
    """
    Disable asyncio debug mode for the benchmark suite.

    The global `asyncio_debug = true` in pyproject.toml adds slow-callback
    logging that roughly halves throughput. Benchmarks measure performance,
    not correctness, so they opt out and restore the prior setting on exit.
    """
    loop = asyncio.get_running_loop()
    previous = loop.get_debug()
    loop.set_debug(False)
    try:
        yield
    finally:
        loop.set_debug(previous)


@dataclass
class TimingResult:
    """Result of a benchmark timing."""

    name: str
    iterations: int
    total_s: float
    samples: list[float] = field(default_factory=list)

    @property
    def avg_ms(self) -> float:
        """Return average time per iteration in milliseconds."""
        return (self.total_s / self.iterations) * 1000

    @property
    def avg_us(self) -> float:
        """Return average time per iteration in microseconds."""
        return (self.total_s / self.iterations) * 1_000_000

    @property
    def ops_per_sec(self) -> float:
        """Return operations per second."""
        return self.iterations / self.total_s if self.total_s > 0 else float("inf")


class BenchmarkTimer:
    """Simple benchmark timer for performance tests."""

    def __init__(self) -> None:
        """Initialize benchmark timer."""
        self._results: list[TimingResult] = []

    @property
    def results(self) -> list[TimingResult]:
        """Return all timing results."""
        return list(self._results)

    def last(self) -> TimingResult:
        """Return the most recent timing result."""
        return self._results[-1]

    @contextmanager
    def measure(self, *, name: str, iterations: int = 1) -> Generator[None]:
        """Measure execution time of a code block."""
        start = time.perf_counter()
        yield
        elapsed = time.perf_counter() - start
        self._results.append(TimingResult(name=name, iterations=iterations, total_s=elapsed))


@pytest.fixture
def bench() -> BenchmarkTimer:
    """Provide a benchmark timer for performance tests."""
    return BenchmarkTimer()
