# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Performance benchmarks for CircuitBreaker."""

import pytest

from aiohomematic.async_support import Looper
from aiohomematic.client import CircuitBreaker, CircuitBreakerConfig
from aiohomematic.const import CircuitState

from .conftest import BenchmarkTimer


@pytest.fixture
def circuit_breaker() -> CircuitBreaker:
    """Create a CircuitBreaker for benchmarking."""
    looper = Looper()
    return CircuitBreaker(
        config=CircuitBreakerConfig(failure_threshold=5, recovery_timeout=30.0, success_threshold=2),
        interface_id="bench-iface",
        task_scheduler=looper,
    )


@pytest.mark.benchmark
def test_circuit_breaker_state_transitions(bench: BenchmarkTimer, circuit_breaker: CircuitBreaker) -> None:
    """Benchmark: full state transition cycle (CLOSED -> OPEN -> HALF_OPEN -> CLOSED)."""
    iterations = 200

    with bench.measure(name="state_transitions", iterations=iterations):
        for _ in range(iterations):
            # CLOSED -> OPEN: record failures up to threshold
            for _ in range(5):
                circuit_breaker.record_failure()
            assert circuit_breaker.state == CircuitState.OPEN

            # Reset for next iteration
            circuit_breaker.reset()

    result = bench.last()
    assert result.ops_per_sec > 500, f"Expected >500 cycles/s, got {result.ops_per_sec:.0f}"


@pytest.mark.benchmark
def test_circuit_breaker_success_recording(bench: BenchmarkTimer, circuit_breaker: CircuitBreaker) -> None:
    """Benchmark: recording successes in CLOSED state."""
    iterations = 10_000

    with bench.measure(name="success_recording", iterations=iterations):
        for _ in range(iterations):
            circuit_breaker.record_success()

    result = bench.last()
    assert result.ops_per_sec > 100_000, f"Expected >100k ops/s, got {result.ops_per_sec:.0f}"
