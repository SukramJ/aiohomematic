# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Event-driven verification tests.

This module implements the test patterns from concept_event_utilization.md sections 3.1, 3.2, and 3.3:
- 3.1: Replace internal state checks with event assertions
- 3.2: Integration test patterns using events
- 3.3: Timing and performance tests with events
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from aiohomematic.central.event_bus import (
    CircuitBreakerStateChangedEvent,
    CircuitBreakerTrippedEvent,
    DataRefreshCompletedEvent,
    DataRefreshTriggeredEvent,
    EventBus,
    RequestCoalescedEvent,
)
from aiohomematic.client.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState
from aiohomematic.client.request_coalescer import RequestCoalescer
from aiohomematic_test_support.event_capture import EventCapture, EventSequenceAssertion

if TYPE_CHECKING:
    pass


# =============================================================================
# Section 3.1: Replace Internal State Checks with Event Assertions
# =============================================================================


class TestCircuitBreakerEventVerification:
    """
    Event-based circuit breaker tests.

    These tests verify behavior through emitted events rather than internal state inspection,
    making them more robust and less coupled to implementation details.
    """

    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery_emits_state_change(self) -> None:
        """Test circuit breaker emits state change events during recovery cycle."""
        event_bus = EventBus()
        capture = EventCapture()
        capture.subscribe_to(event_bus, CircuitBreakerStateChangedEvent)

        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=0.1,
            success_threshold=2,
        )
        breaker = CircuitBreaker(
            config=config,
            interface_id="test-hmip",
            event_bus=event_bus,
        )

        # Trip the circuit
        breaker.record_failure()
        breaker.record_failure()

        # Simulate recovery timeout
        breaker._last_failure_time = datetime.now() - timedelta(seconds=1)
        _ = breaker.is_available  # Triggers HALF_OPEN transition

        # Record successes to close circuit
        breaker.record_success()
        breaker.record_success()

        await asyncio.sleep(0.02)

        # Verify full state transition sequence through events
        events = capture.get_events_of_type(event_type=CircuitBreakerStateChangedEvent)
        assert len(events) == 3

        # CLOSED -> OPEN
        assert events[0].old_state == CircuitState.CLOSED
        assert events[0].new_state == CircuitState.OPEN

        # OPEN -> HALF_OPEN
        assert events[1].old_state == CircuitState.OPEN
        assert events[1].new_state == CircuitState.HALF_OPEN

        # HALF_OPEN -> CLOSED
        assert events[2].old_state == CircuitState.HALF_OPEN
        assert events[2].new_state == CircuitState.CLOSED

        capture.cleanup()

    @pytest.mark.asyncio
    async def test_circuit_breaker_trips_emits_event(self) -> None:
        """Test circuit breaker emits CircuitBreakerTrippedEvent when tripping."""
        event_bus = EventBus()
        capture = EventCapture()
        capture.subscribe_to(
            event_bus,
            CircuitBreakerTrippedEvent,
            CircuitBreakerStateChangedEvent,
        )

        config = CircuitBreakerConfig(failure_threshold=5)
        breaker = CircuitBreaker(
            config=config,
            interface_id="test-rf",
            event_bus=event_bus,
        )

        # Simulate failures until circuit trips
        for _ in range(5):
            breaker.record_failure()

        # Allow async event publishing to complete
        await asyncio.sleep(0.02)

        # Assert behavior through events (not internal state)
        capture.assert_event_emitted(
            event_type=CircuitBreakerTrippedEvent,
            interface_id="test-rf",
            failure_count=5,
        )

        # Verify state change event was also emitted
        capture.assert_event_emitted(
            event_type=CircuitBreakerStateChangedEvent,
            interface_id="test-rf",
            old_state=CircuitState.CLOSED,
            new_state=CircuitState.OPEN,
        )

        capture.cleanup()

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens_circuit_via_events(self) -> None:
        """Test half-open failure reopens circuit, verified via events."""
        event_bus = EventBus()
        capture = EventCapture()
        capture.subscribe_to(event_bus, CircuitBreakerStateChangedEvent)

        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=0.1)
        breaker = CircuitBreaker(
            config=config,
            interface_id="test",
            event_bus=event_bus,
        )

        # Open circuit
        breaker.record_failure()

        # Transition to half-open
        breaker._last_failure_time = datetime.now() - timedelta(seconds=1)
        _ = breaker.is_available

        # Fail in half-open
        breaker.record_failure()

        await asyncio.sleep(0.02)

        # Verify via events: should have CLOSED->OPEN, OPEN->HALF_OPEN, HALF_OPEN->OPEN
        events = capture.get_events_of_type(event_type=CircuitBreakerStateChangedEvent)
        assert len(events) == 3

        # Last transition should be back to OPEN
        assert events[2].old_state == CircuitState.HALF_OPEN
        assert events[2].new_state == CircuitState.OPEN

        capture.cleanup()


# =============================================================================
# Section 3.2: Integration Test Patterns
# =============================================================================


class TestIntegrationEventPatterns:
    """
    Integration test patterns using events.

    These tests demonstrate how to use events to coordinate and verify
    multi-component test scenarios.
    """

    @pytest.mark.asyncio
    async def test_data_refresh_events_integration(self) -> None:
        """Test data refresh events are properly emitted."""
        event_bus = EventBus()
        capture = EventCapture()
        capture.subscribe_to(
            event_bus,
            DataRefreshTriggeredEvent,
            DataRefreshCompletedEvent,
        )

        # Simulate a refresh cycle by manually publishing events
        # (In real tests, this would come from scheduler or central)
        await event_bus.publish(
            event=DataRefreshTriggeredEvent(
                timestamp=datetime.now(),
                refresh_type="client_data",
                interface_id="test-rf",
                scheduled=True,
            )
        )

        # Simulate some processing time
        await asyncio.sleep(0.01)

        await event_bus.publish(
            event=DataRefreshCompletedEvent(
                timestamp=datetime.now(),
                refresh_type="client_data",
                interface_id="test-rf",
                success=True,
                duration_ms=42.5,
                items_refreshed=100,
                error_message=None,
            )
        )

        # Verify refresh triggered
        triggered_events = capture.get_events_of_type(event_type=DataRefreshTriggeredEvent)
        assert len(triggered_events) == 1
        assert triggered_events[0].refresh_type == "client_data"
        assert triggered_events[0].scheduled is True

        # Verify refresh completed successfully
        completed_events = capture.get_events_of_type(event_type=DataRefreshCompletedEvent)
        assert len(completed_events) == 1
        assert completed_events[0].success is True
        assert completed_events[0].duration_ms > 0
        assert completed_events[0].items_refreshed == 100

        capture.cleanup()

    @pytest.mark.asyncio
    async def test_event_sequence_verification(self) -> None:
        """Test verifying event sequences using EventSequenceAssertion."""
        event_bus = EventBus()

        # Set up sequence assertion for expected state transitions
        sequence = EventSequenceAssertion(
            expected_sequence=[
                CircuitBreakerStateChangedEvent,  # CLOSED -> OPEN
                CircuitBreakerTrippedEvent,  # Trip notification
            ]
        )
        event_bus.subscribe(
            event_type=CircuitBreakerStateChangedEvent,
            event_key=None,
            handler=sequence.on_event,
        )
        event_bus.subscribe(
            event_type=CircuitBreakerTrippedEvent,
            event_key=None,
            handler=sequence.on_event,
        )

        config = CircuitBreakerConfig(failure_threshold=1)
        breaker = CircuitBreaker(
            config=config,
            interface_id="test",
            event_bus=event_bus,
        )

        # Trigger state change
        breaker.record_failure()

        await asyncio.sleep(0.02)

        # Verify sequence (non-strict allows other events to be interspersed)
        sequence.verify(strict=False)

    @pytest.mark.asyncio
    async def test_no_events_assertion(self) -> None:
        """Test asserting no events of a type were emitted."""
        event_bus = EventBus()
        capture = EventCapture()
        capture.subscribe_to(event_bus, CircuitBreakerTrippedEvent)

        config = CircuitBreakerConfig(failure_threshold=5)
        breaker = CircuitBreaker(
            config=config,
            interface_id="test",
            event_bus=event_bus,
        )

        # Record failures below threshold
        for _ in range(4):
            breaker.record_failure()

        await asyncio.sleep(0.02)

        # Verify no trip event was emitted (circuit didn't trip)
        capture.assert_no_event(event_type=CircuitBreakerTrippedEvent)

        capture.cleanup()


# =============================================================================
# Section 3.3: Timing and Performance Tests
# =============================================================================


class TestPerformanceEventPatterns:
    """
    Performance tests using events.

    These tests use events to measure and verify performance characteristics.
    """

    @pytest.mark.asyncio
    async def test_coalescing_effectiveness(self) -> None:
        """Test that request coalescing is working via events."""
        event_bus = EventBus()
        capture = EventCapture()
        capture.subscribe_to(event_bus, RequestCoalescedEvent)

        coalescer = RequestCoalescer(
            name="test",
            interface_id="test-rf",
            event_bus=event_bus,
        )

        execution_started = asyncio.Event()
        execution_count = 0

        async def slow_executor():
            nonlocal execution_count
            execution_count += 1
            execution_started.set()
            await asyncio.sleep(0.1)
            return "result"

        # Trigger many concurrent requests for same key
        tasks = [asyncio.create_task(coalescer.execute(key="same-key", executor=slow_executor)) for _ in range(10)]

        # Wait for execution to start before gathering
        await execution_started.wait()

        await asyncio.gather(*tasks)

        # Allow events to be published
        await asyncio.sleep(0.02)

        # Verify coalescing occurred via events
        coalesce_events = capture.get_events_of_type(event_type=RequestCoalescedEvent)
        total_coalesced = sum(e.coalesced_count for e in coalesce_events)

        # At least 9 of 10 requests should be coalesced
        assert total_coalesced >= 9, f"Expected at least 9 coalesced, got {total_coalesced}"

        # Verify only one execution occurred
        assert execution_count == 1

        capture.cleanup()

    @pytest.mark.asyncio
    async def test_coalescing_reports_correct_interface(self) -> None:
        """Test coalescing events include correct interface_id."""
        event_bus = EventBus()
        capture = EventCapture()
        capture.subscribe_to(event_bus, RequestCoalescedEvent)

        coalescer = RequestCoalescer(
            name="test",
            interface_id="ccu-BidCos-RF",
            event_bus=event_bus,
        )

        execution_started = asyncio.Event()

        async def slow_executor():
            execution_started.set()
            await asyncio.sleep(0.05)
            return "result"

        # Start concurrent requests
        task1 = asyncio.create_task(coalescer.execute(key="key", executor=slow_executor))
        await execution_started.wait()
        task2 = asyncio.create_task(coalescer.execute(key="key", executor=slow_executor))

        await asyncio.gather(task1, task2)
        await asyncio.sleep(0.02)

        # Verify event contains correct interface_id
        # coalesced_count is 2 because both tasks share the result
        capture.assert_event_emitted(
            event_type=RequestCoalescedEvent,
            interface_id="ccu-BidCos-RF",
            coalesced_count=2,
        )

        capture.cleanup()

    @pytest.mark.asyncio
    async def test_coalescing_with_different_keys(self) -> None:
        """Test that different keys are not coalesced, verified via events."""
        event_bus = EventBus()
        capture = EventCapture()
        capture.subscribe_to(event_bus, RequestCoalescedEvent)

        coalescer = RequestCoalescer(
            name="test",
            interface_id="test-rf",
            event_bus=event_bus,
        )

        async def executor():
            return "result"

        # Execute with different keys - no coalescing should occur
        await coalescer.execute(key="key-1", executor=executor)
        await coalescer.execute(key="key-2", executor=executor)
        await coalescer.execute(key="key-3", executor=executor)

        await asyncio.sleep(0.02)

        # No coalesce events should be emitted for different keys
        capture.assert_no_event(event_type=RequestCoalescedEvent)

        capture.cleanup()


class TestEventCaptureUtilities:
    """Tests for EventCapture utility methods."""

    @pytest.mark.asyncio
    async def test_assert_event_emitted_with_count(self) -> None:
        """Test asserting exact number of events."""
        event_bus = EventBus()
        capture = EventCapture()
        capture.subscribe_to(event_bus, CircuitBreakerTrippedEvent)

        config = CircuitBreakerConfig(failure_threshold=1)
        breaker = CircuitBreaker(
            config=config,
            interface_id="test",
            event_bus=event_bus,
        )

        # Trip once
        breaker.record_failure()

        await asyncio.sleep(0.02)

        # Assert exactly 1 event
        capture.assert_event_emitted(event_type=CircuitBreakerTrippedEvent, count=1)

        # Assert wrong count fails
        with pytest.raises(AssertionError, match="Expected 2"):
            capture.assert_event_emitted(event_type=CircuitBreakerTrippedEvent, count=2)

        capture.cleanup()

    def test_clear_events(self) -> None:
        """Test clear method removes captured events."""
        capture = EventCapture()
        # Manually add some events for testing
        from aiohomematic.central.event_bus import Event

        class DummyEvent(Event):
            @property
            def key(self):
                return None

        capture.captured_events.append(DummyEvent(timestamp=datetime.now()))
        capture.captured_events.append(DummyEvent(timestamp=datetime.now()))

        assert len(capture.captured_events) == 2

        capture.clear()

        assert len(capture.captured_events) == 0

    @pytest.mark.asyncio
    async def test_event_count(self) -> None:
        """Test get_event_count method."""
        event_bus = EventBus()
        capture = EventCapture()
        capture.subscribe_to(event_bus, CircuitBreakerStateChangedEvent)

        config = CircuitBreakerConfig(failure_threshold=1, success_threshold=1)
        breaker = CircuitBreaker(
            config=config,
            interface_id="test",
            event_bus=event_bus,
        )

        # Trigger multiple state changes
        breaker.record_failure()  # CLOSED -> OPEN
        breaker._last_failure_time = datetime.now() - timedelta(seconds=100)
        _ = breaker.is_available  # OPEN -> HALF_OPEN
        breaker.record_success()  # HALF_OPEN -> CLOSED

        await asyncio.sleep(0.02)

        assert capture.get_event_count(event_type=CircuitBreakerStateChangedEvent) == 3

        capture.cleanup()
