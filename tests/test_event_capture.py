# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Tests for EventCapture and EventSequenceAssertion."""

from __future__ import annotations

from datetime import datetime

import pytest

from aiohomematic.central.event_bus import (
    CircuitBreakerStateChangedEvent,
    CircuitBreakerTrippedEvent,
    ConnectionStageEvent,
    DataRefreshCompletedEvent,
    EventBus,
)
from aiohomematic.client.circuit_breaker import CircuitState
from aiohomematic.const import ConnectionStage
from aiohomematic_test_support.event_capture import EventCapture, EventSequenceAssertion


class TestEventCapture:
    """Tests for EventCapture."""

    def test_assert_event_emitted_failure(self) -> None:
        """Test assert_event_emitted fails when event missing."""
        capture = EventCapture()

        with pytest.raises(AssertionError, match="No CircuitBreakerTrippedEvent"):
            capture.assert_event_emitted(event_type=CircuitBreakerTrippedEvent)

    @pytest.mark.asyncio
    async def test_assert_event_emitted_success(self) -> None:
        """Test assert_event_emitted passes when event exists."""
        event_bus = EventBus()
        capture = EventCapture()
        capture.subscribe_to(event_bus, CircuitBreakerTrippedEvent)

        await event_bus.publish(
            event=CircuitBreakerTrippedEvent(
                timestamp=datetime.now(),
                interface_id="rf",
                failure_count=5,
                last_failure_reason=None,
                cooldown_seconds=30.0,
            )
        )

        # Should not raise
        capture.assert_event_emitted(
            event_type=CircuitBreakerTrippedEvent,
            interface_id="rf",
            failure_count=5,
        )
        capture.cleanup()

    @pytest.mark.asyncio
    async def test_assert_event_emitted_with_count(self) -> None:
        """Test assert_event_emitted with count parameter."""
        event_bus = EventBus()
        capture = EventCapture()
        capture.subscribe_to(event_bus, CircuitBreakerTrippedEvent)

        for i in range(3):
            await event_bus.publish(
                event=CircuitBreakerTrippedEvent(
                    timestamp=datetime.now(),
                    interface_id="rf",
                    failure_count=i,
                    last_failure_reason=None,
                    cooldown_seconds=30.0,
                )
            )

        capture.assert_event_emitted(event_type=CircuitBreakerTrippedEvent, count=3)

        with pytest.raises(AssertionError, match="Expected 5"):
            capture.assert_event_emitted(event_type=CircuitBreakerTrippedEvent, count=5)
        capture.cleanup()

    @pytest.mark.asyncio
    async def test_assert_event_emitted_wrong_attrs(self) -> None:
        """Test assert_event_emitted fails with wrong attributes."""
        event_bus = EventBus()
        capture = EventCapture()
        capture.subscribe_to(event_bus, CircuitBreakerTrippedEvent)

        await event_bus.publish(
            event=CircuitBreakerTrippedEvent(
                timestamp=datetime.now(),
                interface_id="rf",
                failure_count=5,
                last_failure_reason=None,
                cooldown_seconds=30.0,
            )
        )

        with pytest.raises(AssertionError, match="No CircuitBreakerTrippedEvent found"):
            capture.assert_event_emitted(
                event_type=CircuitBreakerTrippedEvent,
                interface_id="wrong",
            )
        capture.cleanup()

    @pytest.mark.asyncio
    async def test_assert_no_event(self) -> None:
        """Test assert_no_event."""
        event_bus = EventBus()
        capture = EventCapture()
        capture.subscribe_to(event_bus, CircuitBreakerTrippedEvent)

        # Should pass - no events emitted
        capture.assert_no_event(event_type=CircuitBreakerTrippedEvent)

        # Emit an event
        await event_bus.publish(
            event=CircuitBreakerTrippedEvent(
                timestamp=datetime.now(),
                interface_id="rf",
                failure_count=5,
                last_failure_reason=None,
                cooldown_seconds=30.0,
            )
        )

        # Now should fail
        with pytest.raises(AssertionError, match="Expected no"):
            capture.assert_no_event(event_type=CircuitBreakerTrippedEvent)
        capture.cleanup()

    @pytest.mark.asyncio
    async def test_capture_multiple_event_types(self) -> None:
        """Test capturing multiple event types."""
        event_bus = EventBus()
        capture = EventCapture()
        capture.subscribe_to(
            event_bus,
            CircuitBreakerTrippedEvent,
            CircuitBreakerStateChangedEvent,
        )

        event1 = CircuitBreakerTrippedEvent(
            timestamp=datetime.now(),
            interface_id="test",
            failure_count=5,
            last_failure_reason=None,
            cooldown_seconds=30.0,
        )
        event2 = CircuitBreakerStateChangedEvent(
            timestamp=datetime.now(),
            interface_id="test",
            old_state=CircuitState.CLOSED,
            new_state=CircuitState.OPEN,
            failure_count=5,
            success_count=0,
            last_failure_time=datetime.now(),
        )
        await event_bus.publish(event=event1)
        await event_bus.publish(event=event2)

        assert len(capture.captured_events) == 2
        capture.cleanup()

    @pytest.mark.asyncio
    async def test_capture_single_event(self) -> None:
        """Test capturing a single event."""
        event_bus = EventBus()
        capture = EventCapture()
        capture.subscribe_to(event_bus, CircuitBreakerTrippedEvent)

        event = CircuitBreakerTrippedEvent(
            timestamp=datetime.now(),
            interface_id="test",
            failure_count=5,
            last_failure_reason="Connection refused",
            cooldown_seconds=30.0,
        )
        await event_bus.publish(event=event)

        assert len(capture.captured_events) == 1
        assert capture.captured_events[0] == event
        capture.cleanup()

    @pytest.mark.asyncio
    async def test_cleanup_unsubscribes(self) -> None:
        """Test cleanup properly unsubscribes from events."""
        event_bus = EventBus()
        capture = EventCapture()
        capture.subscribe_to(event_bus, CircuitBreakerTrippedEvent)

        await event_bus.publish(
            event=CircuitBreakerTrippedEvent(
                timestamp=datetime.now(),
                interface_id="rf",
                failure_count=1,
                last_failure_reason=None,
                cooldown_seconds=30.0,
            )
        )
        assert len(capture.captured_events) == 1

        capture.cleanup()

        # After cleanup, new events should not be captured
        await event_bus.publish(
            event=CircuitBreakerTrippedEvent(
                timestamp=datetime.now(),
                interface_id="rf",
                failure_count=2,
                last_failure_reason=None,
                cooldown_seconds=30.0,
            )
        )
        assert len(capture.captured_events) == 0

    @pytest.mark.asyncio
    async def test_clear(self) -> None:
        """Test clearing captured events."""
        event_bus = EventBus()
        capture = EventCapture()
        capture.subscribe_to(event_bus, CircuitBreakerTrippedEvent)

        await event_bus.publish(
            event=CircuitBreakerTrippedEvent(
                timestamp=datetime.now(),
                interface_id="rf",
                failure_count=5,
                last_failure_reason=None,
                cooldown_seconds=30.0,
            )
        )

        assert len(capture.captured_events) == 1
        capture.clear()
        assert len(capture.captured_events) == 0
        capture.cleanup()

    @pytest.mark.asyncio
    async def test_get_event_count(self) -> None:
        """Test counting events by type."""
        event_bus = EventBus()
        capture = EventCapture()
        capture.subscribe_to(event_bus, CircuitBreakerTrippedEvent)

        for i in range(3):
            await event_bus.publish(
                event=CircuitBreakerTrippedEvent(
                    timestamp=datetime.now(),
                    interface_id="test",
                    failure_count=i,
                    last_failure_reason=None,
                    cooldown_seconds=30.0,
                )
            )

        assert capture.get_event_count(event_type=CircuitBreakerTrippedEvent) == 3
        assert capture.get_event_count(event_type=CircuitBreakerStateChangedEvent) == 0
        capture.cleanup()

    @pytest.mark.asyncio
    async def test_get_events_of_type(self) -> None:
        """Test filtering events by type."""
        event_bus = EventBus()
        capture = EventCapture()
        # Subscribe to specific event types (EventBus requires exact type matching)
        capture.subscribe_to(
            event_bus,
            CircuitBreakerTrippedEvent,
            CircuitBreakerStateChangedEvent,
        )

        await event_bus.publish(
            event=CircuitBreakerTrippedEvent(
                timestamp=datetime.now(),
                interface_id="test",
                failure_count=5,
                last_failure_reason=None,
                cooldown_seconds=30.0,
            )
        )
        await event_bus.publish(
            event=CircuitBreakerStateChangedEvent(
                timestamp=datetime.now(),
                interface_id="test",
                old_state=CircuitState.CLOSED,
                new_state=CircuitState.OPEN,
                failure_count=5,
                success_count=0,
                last_failure_time=None,
            )
        )

        tripped = capture.get_events_of_type(event_type=CircuitBreakerTrippedEvent)
        assert len(tripped) == 1
        assert tripped[0].failure_count == 5

        state_changes = capture.get_events_of_type(event_type=CircuitBreakerStateChangedEvent)
        assert len(state_changes) == 1
        capture.cleanup()


class TestEventSequenceAssertion:
    """Tests for EventSequenceAssertion."""

    def test_empty_sequence_non_strict(self) -> None:
        """Test empty expected sequence with non-strict mode."""
        sequence = EventSequenceAssertion(expected_sequence=[])
        sequence.captured_types = [ConnectionStageEvent, CircuitBreakerStateChangedEvent]

        # Empty expected sequence should pass in non-strict mode
        sequence.verify(strict=False)

    def test_empty_sequence_strict_with_no_captures(self) -> None:
        """Test empty expected sequence with strict mode and no captures."""
        sequence = EventSequenceAssertion(expected_sequence=[])
        sequence.captured_types = []

        # Empty expected and empty captured should pass
        sequence.verify(strict=True)

    def test_reset(self) -> None:
        """Test resetting captured types."""
        sequence = EventSequenceAssertion(expected_sequence=[])
        sequence.captured_types = [ConnectionStageEvent]
        sequence.reset()
        assert len(sequence.captured_types) == 0

    def test_strict_sequence_fail_missing_event(self) -> None:
        """Test strict sequence fails with missing event."""
        sequence = EventSequenceAssertion(
            expected_sequence=[
                ConnectionStageEvent,
                CircuitBreakerStateChangedEvent,
            ]
        )
        sequence.captured_types = [ConnectionStageEvent]

        with pytest.raises(AssertionError, match="Expected 2 events, got 1"):
            sequence.verify(strict=True)

    def test_strict_sequence_fail_wrong_order(self) -> None:
        """Test strict sequence fails with wrong order."""
        sequence = EventSequenceAssertion(
            expected_sequence=[
                ConnectionStageEvent,
                CircuitBreakerStateChangedEvent,
            ]
        )
        # Simulate capturing in wrong order
        sequence.captured_types = [
            CircuitBreakerStateChangedEvent,
            ConnectionStageEvent,
        ]

        with pytest.raises(AssertionError, match="Event 0: expected"):
            sequence.verify(strict=True)

    @pytest.mark.asyncio
    async def test_strict_sequence_pass(self) -> None:
        """Test strict sequence verification passes."""
        event_bus = EventBus()
        sequence = EventSequenceAssertion(
            expected_sequence=[
                ConnectionStageEvent,
                CircuitBreakerStateChangedEvent,
            ]
        )
        event_bus.subscribe(
            event_type=ConnectionStageEvent,
            event_key=None,
            handler=sequence.on_event,
        )
        event_bus.subscribe(
            event_type=CircuitBreakerStateChangedEvent,
            event_key=None,
            handler=sequence.on_event,
        )

        await event_bus.publish(
            event=ConnectionStageEvent(
                timestamp=datetime.now(),
                interface_id="rf",
                stage=ConnectionStage.TCP_AVAILABLE,
                previous_stage=ConnectionStage.LOST,
                duration_in_previous_stage_ms=100.0,
            )
        )
        await event_bus.publish(
            event=CircuitBreakerStateChangedEvent(
                timestamp=datetime.now(),
                interface_id="rf",
                old_state=CircuitState.CLOSED,
                new_state=CircuitState.OPEN,
                failure_count=5,
                success_count=0,
                last_failure_time=None,
            )
        )

        # Should not raise
        sequence.verify(strict=True)

    def test_subsequence_fail(self) -> None:
        """Test non-strict subsequence fails when event missing."""
        sequence = EventSequenceAssertion(
            expected_sequence=[
                ConnectionStageEvent,
                CircuitBreakerStateChangedEvent,
            ]
        )
        sequence.captured_types = [
            ConnectionStageEvent,
            DataRefreshCompletedEvent,
        ]

        with pytest.raises(AssertionError, match="Missing expected events"):
            sequence.verify(strict=False)

    def test_subsequence_pass(self) -> None:
        """Test non-strict subsequence verification passes."""
        sequence = EventSequenceAssertion(
            expected_sequence=[
                ConnectionStageEvent,
                CircuitBreakerStateChangedEvent,
            ]
        )
        # Extra events interspersed
        sequence.captured_types = [
            ConnectionStageEvent,
            DataRefreshCompletedEvent,
            CircuitBreakerStateChangedEvent,
            DataRefreshCompletedEvent,
        ]

        # Should not raise - expected events appear in order
        sequence.verify(strict=False)
