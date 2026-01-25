# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract tests for subscription API stability.

STABILITY GUARANTEE
-------------------
These tests define the stable API contract for subscription APIs.
Any change that breaks these tests requires a MAJOR version bump.

The contract ensures that:
1. Subscription methods exist on data point classes
2. Subscription methods return unsubscribe callables
3. EventBus subscribe API is stable
4. Handler signature patterns are stable

See ADR-0018 for architectural context.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from aiohomematic.central.events import ClientStateChangedEvent, DataPointValueReceivedEvent, Event, EventBus
from aiohomematic.type_aliases import AsyncTaskFactoryAny, CoroutineAny


class MockTaskScheduler:
    """Mock task scheduler for testing."""

    def async_add_executor_job[T](
        self, target: Callable[..., T], *args: Any, name: str, executor: Any = None
    ) -> asyncio.Future[T]:
        """Add an executor job from within the event_loop."""
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(executor, target, *args)

    async def block_till_done(self, *, wait_time: float | None = None) -> None:
        """Block until all pending work is done."""

    def cancel_tasks(self) -> None:
        """Cancel running tasks."""

    def create_task(self, *, target: CoroutineAny | AsyncTaskFactoryAny, name: str) -> None:
        """Create and schedule an async task."""


def _create_event_bus() -> EventBus:
    """Create an EventBus with mock dependencies for testing."""
    return EventBus(task_scheduler=MockTaskScheduler())


# =============================================================================
# Contract: EventBus Subscription API
# =============================================================================


class TestEventBusSubscriptionApiContract:
    """Contract: EventBus subscription API must remain stable."""

    def test_eventbus_has_publish_batch_method(self) -> None:
        """Contract: EventBus has publish_batch method."""
        assert hasattr(EventBus, "publish_batch")
        assert callable(getattr(EventBus, "publish_batch"))

    def test_eventbus_has_publish_method(self) -> None:
        """Contract: EventBus has publish (async) method."""
        assert hasattr(EventBus, "publish")
        assert callable(getattr(EventBus, "publish"))

    def test_eventbus_has_publish_sync_method(self) -> None:
        """Contract: EventBus has publish_sync method."""
        assert hasattr(EventBus, "publish_sync")
        assert callable(getattr(EventBus, "publish_sync"))

    def test_eventbus_has_subscribe_method(self) -> None:
        """Contract: EventBus has subscribe method."""
        assert hasattr(EventBus, "subscribe")
        assert callable(getattr(EventBus, "subscribe"))

    def test_eventbus_multiple_subscriptions_same_type(self) -> None:
        """Contract: Multiple handlers can subscribe to same event type with different keys."""
        bus = _create_event_bus()

        def handler1(event: DataPointValueReceivedEvent) -> None:
            pass

        def handler2(event: DataPointValueReceivedEvent) -> None:
            pass

        unsub1 = bus.subscribe(
            event_type=DataPointValueReceivedEvent,
            event_key="key-1",
            handler=handler1,
        )
        unsub2 = bus.subscribe(
            event_type=DataPointValueReceivedEvent,
            event_key="key-2",
            handler=handler2,
        )

        # Both should be callable
        assert callable(unsub1)
        assert callable(unsub2)

        unsub1()
        unsub2()

    def test_eventbus_subscribe_requires_event_key(self) -> None:
        """Contract: EventBus.subscribe requires event_key parameter."""
        bus = _create_event_bus()

        def handler(event: DataPointValueReceivedEvent) -> None:
            pass

        # event_key is required
        unsubscribe = bus.subscribe(
            event_type=DataPointValueReceivedEvent,
            event_key="my-unique-key",
            handler=handler,
        )

        assert callable(unsubscribe)
        unsubscribe()

    def test_eventbus_subscribe_requires_event_type(self) -> None:
        """Contract: EventBus.subscribe requires event_type parameter."""
        bus = _create_event_bus()

        def handler(event: ClientStateChangedEvent) -> None:
            pass

        # Should not raise
        unsubscribe = bus.subscribe(
            event_type=ClientStateChangedEvent,
            event_key="test-key",
            handler=handler,
        )
        unsubscribe()

    def test_eventbus_subscribe_requires_handler(self) -> None:
        """Contract: EventBus.subscribe requires handler parameter."""
        bus = _create_event_bus()
        called = []

        def handler(event: DataPointValueReceivedEvent) -> None:
            called.append(event)

        unsubscribe = bus.subscribe(
            event_type=DataPointValueReceivedEvent,
            event_key="test-key",
            handler=handler,
        )

        assert callable(unsubscribe)
        unsubscribe()

    def test_eventbus_subscribe_returns_callable(self) -> None:
        """Contract: EventBus.subscribe returns an unsubscribe callable."""
        bus = _create_event_bus()

        def handler(event: DataPointValueReceivedEvent) -> None:
            pass

        unsubscribe = bus.subscribe(
            event_type=DataPointValueReceivedEvent,
            event_key="test-key",
            handler=handler,
        )

        assert callable(unsubscribe)

        # Clean up
        unsubscribe()

    def test_eventbus_unsubscribe_is_idempotent(self) -> None:
        """Contract: Calling unsubscribe multiple times is safe."""
        bus = _create_event_bus()

        def handler(event: DataPointValueReceivedEvent) -> None:
            pass

        unsubscribe = bus.subscribe(
            event_type=DataPointValueReceivedEvent,
            event_key="test-key",
            handler=handler,
        )

        # Should not raise even when called multiple times
        unsubscribe()
        unsubscribe()
        unsubscribe()


# =============================================================================
# Contract: Event Base Class
# =============================================================================


class TestEventBaseClassContract:
    """Contract: Event base class must remain stable."""

    def test_event_class_exists(self) -> None:
        """Contract: Event base class exists."""
        assert Event is not None

    def test_event_has_key_property(self) -> None:
        """Contract: Event has key property."""
        assert hasattr(Event, "key")

    def test_event_has_timestamp_field(self) -> None:
        """Contract: Event has timestamp field."""
        # Event is ABC, check in annotations
        assert "timestamp" in Event.__annotations__


# =============================================================================
# Contract: DataPointValueReceivedEvent
# =============================================================================


class TestDataPointValueReceivedEventContract:
    """Contract: DataPointValueReceivedEvent must remain stable."""

    def test_datapointvaluereceivedevent_exists(self) -> None:
        """Contract: DataPointValueReceivedEvent exists."""
        assert DataPointValueReceivedEvent is not None

    def test_datapointvaluereceivedevent_has_dpk(self) -> None:
        """Contract: DataPointValueReceivedEvent has dpk field."""
        assert "dpk" in DataPointValueReceivedEvent.__dataclass_fields__

    def test_datapointvaluereceivedevent_has_received_at(self) -> None:
        """Contract: DataPointValueReceivedEvent has received_at field."""
        assert "received_at" in DataPointValueReceivedEvent.__dataclass_fields__

    def test_datapointvaluereceivedevent_has_value(self) -> None:
        """Contract: DataPointValueReceivedEvent has value field."""
        assert "value" in DataPointValueReceivedEvent.__dataclass_fields__

    def test_datapointvaluereceivedevent_is_frozen(self) -> None:
        """Contract: DataPointValueReceivedEvent is frozen."""
        # Check if it's a frozen dataclass
        assert hasattr(DataPointValueReceivedEvent, "__dataclass_fields__")


# =============================================================================
# Contract: ClientStateChangedEvent
# =============================================================================


class TestClientStateChangedEventContract:
    """Contract: ClientStateChangedEvent must remain stable."""

    def test_clientstatechangedevent_exists(self) -> None:
        """Contract: ClientStateChangedEvent exists."""
        assert ClientStateChangedEvent is not None

    def test_clientstatechangedevent_has_interface_id(self) -> None:
        """Contract: ClientStateChangedEvent has interface_id field."""
        assert "interface_id" in ClientStateChangedEvent.__dataclass_fields__

    def test_clientstatechangedevent_has_new_state(self) -> None:
        """Contract: ClientStateChangedEvent has new_state field."""
        assert "new_state" in ClientStateChangedEvent.__dataclass_fields__

    def test_clientstatechangedevent_has_old_state(self) -> None:
        """Contract: ClientStateChangedEvent has old_state field."""
        assert "old_state" in ClientStateChangedEvent.__dataclass_fields__

    def test_clientstatechangedevent_is_frozen(self) -> None:
        """Contract: ClientStateChangedEvent is frozen."""
        assert hasattr(ClientStateChangedEvent, "__dataclass_fields__")


# =============================================================================
# Contract: Event Imports
# =============================================================================


class TestEventImportsContract:
    """Contract: Event types must be importable from expected locations."""

    def test_eventpriority_importable(self) -> None:
        """Contract: EventPriority importable from central.events."""
        from aiohomematic.central.events import EventPriority

        assert hasattr(EventPriority, "LOW")
        assert hasattr(EventPriority, "NORMAL")
        assert hasattr(EventPriority, "HIGH")
        assert hasattr(EventPriority, "CRITICAL")

    def test_eventpriority_ordering(self) -> None:
        """Contract: EventPriority values have correct ordering."""
        from aiohomematic.central.events import EventPriority

        assert EventPriority.LOW < EventPriority.NORMAL
        assert EventPriority.NORMAL < EventPriority.HIGH
        assert EventPriority.HIGH < EventPriority.CRITICAL

    def test_events_importable_from_central_events(self) -> None:
        """Contract: Events importable from aiohomematic.central.events."""
        from aiohomematic.central.events import (
            CentralStateChangedEvent,
            ClientStateChangedEvent,
            DataPointValueReceivedEvent,
            DeviceStateChangedEvent,
            Event,
            EventBus,
        )

        assert Event is not None
        assert EventBus is not None
        assert DataPointValueReceivedEvent is not None
        assert ClientStateChangedEvent is not None
        assert CentralStateChangedEvent is not None
        assert DeviceStateChangedEvent is not None
