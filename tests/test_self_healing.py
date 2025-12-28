# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Tests for SelfHealingCoordinator."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from aiohomematic.central.event_bus import CircuitBreakerStateChangedEvent, CircuitBreakerTrippedEvent, EventBus
from aiohomematic.central.self_healing import SelfHealingCoordinator
from aiohomematic.client.circuit_breaker import CircuitState
from aiohomematic.metrics.events import SelfHealingDataRefreshEvent, SelfHealingTriggeredEvent
from aiohomematic_test_support.event_capture import EventCapture

if TYPE_CHECKING:
    pass


class MockDeviceDataRefresher:
    """Mock device data refresher for testing."""

    def __init__(self) -> None:
        """Initialize mock."""
        self.load_and_refresh_data_point_data = AsyncMock()


class MockTaskScheduler:
    """Mock task scheduler for testing."""

    def __init__(self) -> None:
        """Initialize mock."""
        self.created_tasks: list[tuple[str, MagicMock]] = []

    def create_task(self, *, target: MagicMock, name: str) -> None:
        """Record task creation and execute the target."""
        self.created_tasks.append((name, target))


class TestSelfHealingCoordinator:
    """Tests for SelfHealingCoordinator."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery_emits_event_and_schedules_refresh(self) -> None:
        """Test that circuit breaker recovery emits event and schedules data refresh."""
        event_bus = EventBus()
        refresher = MockDeviceDataRefresher()
        scheduler = MockTaskScheduler()

        # Capture emitted events
        capture = EventCapture()
        capture.subscribe_to(event_bus, SelfHealingTriggeredEvent)

        coordinator = SelfHealingCoordinator(
            event_bus=event_bus,
            device_data_refresher=refresher,
            task_scheduler=scheduler,
        )

        # Publish a recovery event (HALF_OPEN -> CLOSED)
        await event_bus.publish(
            event=CircuitBreakerStateChangedEvent(
                timestamp=datetime.now(),
                interface_id="test-BidCos-RF",
                old_state=CircuitState.HALF_OPEN,
                new_state=CircuitState.CLOSED,
                failure_count=0,
                success_count=2,
                last_failure_time=None,
            )
        )

        # Allow async event to complete
        import asyncio

        await asyncio.sleep(0.05)

        capture.assert_event_emitted(
            event_type=SelfHealingTriggeredEvent,
            action="recovery_initiated",
            interface_id="test-BidCos-RF",
        )

        # Task should be scheduled
        assert len(scheduler.created_tasks) == 1
        assert "self_healing_refresh" in scheduler.created_tasks[0][0]

        capture.cleanup()
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_circuit_breaker_tripped_emits_event(self) -> None:
        """Test that circuit breaker trip events emit SelfHealingTriggeredEvent."""
        event_bus = EventBus()
        refresher = MockDeviceDataRefresher()
        scheduler = MockTaskScheduler()

        # Capture emitted events
        capture = EventCapture()
        capture.subscribe_to(event_bus, SelfHealingTriggeredEvent)

        coordinator = SelfHealingCoordinator(
            event_bus=event_bus,
            device_data_refresher=refresher,
            task_scheduler=scheduler,
        )

        # Publish a trip event
        await event_bus.publish(
            event=CircuitBreakerTrippedEvent(
                timestamp=datetime.now(),
                interface_id="test-rf",
                failure_count=5,
                last_failure_reason="Connection refused",
                cooldown_seconds=30.0,
            )
        )

        # Allow async event to complete
        import asyncio

        await asyncio.sleep(0.05)

        capture.assert_event_emitted(
            event_type=SelfHealingTriggeredEvent,
            action="trip_logged",
            interface_id="test-rf",
        )

        capture.cleanup()
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_multiple_trips_emit_multiple_events(self) -> None:
        """Test that multiple trip events emit multiple events."""
        event_bus = EventBus()
        refresher = MockDeviceDataRefresher()
        scheduler = MockTaskScheduler()

        # Capture emitted events
        capture = EventCapture()
        capture.subscribe_to(event_bus, SelfHealingTriggeredEvent)

        coordinator = SelfHealingCoordinator(
            event_bus=event_bus,
            device_data_refresher=refresher,
            task_scheduler=scheduler,
        )

        # Publish multiple trip events
        for i in range(3):
            await event_bus.publish(
                event=CircuitBreakerTrippedEvent(
                    timestamp=datetime.now(),
                    interface_id=f"interface-{i}",
                    failure_count=5,
                    last_failure_reason=None,
                    cooldown_seconds=30.0,
                )
            )

        # Allow async events to complete
        import asyncio

        await asyncio.sleep(0.05)

        trip_events = [
            e for e in capture.get_events_of_type(event_type=SelfHealingTriggeredEvent) if e.action == "trip_logged"
        ]
        assert len(trip_events) == 3

        capture.cleanup()
        coordinator.stop()

    @pytest.mark.asyncio
    async def test_non_recovery_state_change_does_not_emit_event(self) -> None:
        """Test that non-recovery state changes don't emit recovery events."""
        event_bus = EventBus()
        refresher = MockDeviceDataRefresher()
        scheduler = MockTaskScheduler()

        # Capture emitted events
        capture = EventCapture()
        capture.subscribe_to(event_bus, SelfHealingTriggeredEvent)

        coordinator = SelfHealingCoordinator(
            event_bus=event_bus,
            device_data_refresher=refresher,
            task_scheduler=scheduler,
        )

        # CLOSED -> OPEN is not a recovery
        await event_bus.publish(
            event=CircuitBreakerStateChangedEvent(
                timestamp=datetime.now(),
                interface_id="test-rf",
                old_state=CircuitState.CLOSED,
                new_state=CircuitState.OPEN,
                failure_count=5,
                success_count=0,
                last_failure_time=datetime.now(),
            )
        )

        # OPEN -> HALF_OPEN is not a recovery
        await event_bus.publish(
            event=CircuitBreakerStateChangedEvent(
                timestamp=datetime.now(),
                interface_id="test-rf",
                old_state=CircuitState.OPEN,
                new_state=CircuitState.HALF_OPEN,
                failure_count=5,
                success_count=0,
                last_failure_time=datetime.now(),
            )
        )

        # Allow async events to complete
        import asyncio

        await asyncio.sleep(0.05)

        # No recovery events should be emitted
        recovery_events = [
            e
            for e in capture.get_events_of_type(event_type=SelfHealingTriggeredEvent)
            if e.action == "recovery_initiated"
        ]
        assert len(recovery_events) == 0
        assert len(scheduler.created_tasks) == 0

        capture.cleanup()
        coordinator.stop()

    def test_stop_unsubscribes(self) -> None:
        """Test that stop() unsubscribes from events."""
        event_bus = EventBus()
        refresher = MockDeviceDataRefresher()
        scheduler = MockTaskScheduler()

        coordinator = SelfHealingCoordinator(
            event_bus=event_bus,
            device_data_refresher=refresher,
            task_scheduler=scheduler,
        )

        # Verify subscriptions exist
        assert event_bus.get_subscription_count(event_type=CircuitBreakerTrippedEvent) >= 1
        assert event_bus.get_subscription_count(event_type=CircuitBreakerStateChangedEvent) >= 1

        coordinator.stop()

        # Subscriptions should be cleared (or at least coordinator's handlers)
        # Note: We only verify no exception is raised


class TestSelfHealingEvents:
    """Tests for SelfHealing event types."""

    def test_self_healing_data_refresh_event(self) -> None:
        """Test SelfHealingDataRefreshEvent properties."""
        event = SelfHealingDataRefreshEvent(
            timestamp=datetime.now(),
            interface_id="test-rf",
            success=True,
            error_message=None,
        )
        assert event.key == "test-rf"
        assert event.success is True
        assert event.error_message is None

    def test_self_healing_triggered_event(self) -> None:
        """Test SelfHealingTriggeredEvent properties."""
        event = SelfHealingTriggeredEvent(
            timestamp=datetime.now(),
            interface_id="test-rf",
            action="trip_logged",
            details="failure_count=5",
        )
        assert event.key == "test-rf"
        assert event.action == "trip_logged"
        assert event.details == "failure_count=5"


class TestCreateSelfHealingCoordinator:
    """Tests for the factory function."""

    def test_create_self_healing_coordinator(self) -> None:
        """Test factory function creates coordinator."""
        from aiohomematic.central.self_healing import create_self_healing_coordinator

        event_bus = EventBus()
        refresher = MockDeviceDataRefresher()
        scheduler = MockTaskScheduler()

        coordinator = create_self_healing_coordinator(
            event_bus=event_bus,
            device_data_refresher=refresher,
            task_scheduler=scheduler,
        )

        assert isinstance(coordinator, SelfHealingCoordinator)
        coordinator.stop()
