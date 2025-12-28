# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Self-healing coordinator for automatic recovery based on circuit breaker events.

Overview
--------
This module provides event-driven recovery coordination that reacts to circuit
breaker events. It complements the scheduler's polling-based health checks with
immediate, event-triggered recovery actions.

The SelfHealingCoordinator:
- Logs warnings when circuit breakers trip
- Triggers data refresh when circuit breakers recover (HALF_OPEN → CLOSED)
- Emits events for observability (no internal stat tracking)

Design Philosophy
-----------------
The coordinator is intentionally lightweight and non-invasive:
- It does not interfere with the scheduler's reconnection logic
- It provides supplementary recovery actions (data refresh after recovery)
- It emits events for metrics tracking by subscribers (MetricsAggregator)
- It does NOT maintain internal statistics - that's the subscriber's job

Public API
----------
- SelfHealingCoordinator: Main coordinator class
- create_self_healing_coordinator: Factory function
"""

from __future__ import annotations

from datetime import datetime
import logging
from typing import TYPE_CHECKING, Final

from aiohomematic.central.event_bus import CircuitBreakerStateChangedEvent, CircuitBreakerTrippedEvent
from aiohomematic.client.circuit_breaker import CircuitState
from aiohomematic.metrics.emitter import emit_counter
from aiohomematic.metrics.events import SelfHealingDataRefreshEvent, SelfHealingTriggeredEvent
from aiohomematic.metrics.keys import MetricKeys

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine
    from typing import Any

    from aiohomematic.central.event_bus import EventBus
    from aiohomematic.interfaces.central import DeviceDataRefresherProtocol
    from aiohomematic.interfaces.operations import TaskSchedulerProtocol

_LOGGER: Final = logging.getLogger(__name__)


class SelfHealingCoordinator:
    """
    Coordinate automatic recovery actions based on circuit breaker events.

    This coordinator provides event-driven recovery that supplements the
    scheduler's polling-based health checks. When a circuit breaker recovers
    (transitions from HALF_OPEN to CLOSED), it triggers a data refresh for
    the recovered interface to ensure data consistency.

    The coordinator does NOT maintain internal statistics. Instead, it emits
    events that subscribers (like MetricsAggregator) can use to track stats.

    Example Usage
    -------------
        coordinator = SelfHealingCoordinator(
            event_bus=central.event_bus,
            device_data_refresher=central,
            task_scheduler=central,
        )

        # Subscribe to self-healing events for metrics
        event_bus.subscribe(
            event_type=SelfHealingTriggeredEvent,
            event_key=None,
            handler=my_metrics_handler,
        )

        # Later, to stop:
        coordinator.stop()

    Thread Safety
    -------------
    This class is designed for single-threaded asyncio use.
    All event handlers run in the same event loop.
    """

    __slots__ = (
        "_device_data_refresher",
        "_event_bus",
        "_task_scheduler",
        "_unsubscribers",
    )

    def __init__(
        self,
        *,
        event_bus: EventBus,
        device_data_refresher: DeviceDataRefresherProtocol,
        task_scheduler: TaskSchedulerProtocol,
    ) -> None:
        """
        Initialize the self-healing coordinator.

        Args:
        ----
            event_bus: EventBus to subscribe to circuit breaker events
            device_data_refresher: Refresher for device data after recovery
            task_scheduler: Scheduler for async task management

        """
        self._event_bus: Final = event_bus
        self._device_data_refresher: Final = device_data_refresher
        self._task_scheduler: Final = task_scheduler
        self._unsubscribers: list[Callable[[], None]] = []

        # Subscribe to circuit breaker events
        self._unsubscribers.append(
            event_bus.subscribe(
                event_type=CircuitBreakerTrippedEvent,
                event_key=None,
                handler=self._on_circuit_breaker_tripped,
            )
        )
        self._unsubscribers.append(
            event_bus.subscribe(
                event_type=CircuitBreakerStateChangedEvent,
                event_key=None,
                handler=self._on_circuit_breaker_state_changed,
            )
        )

        _LOGGER.debug("SELF_HEALING: Coordinator initialized")

    def stop(self) -> None:
        """Stop the coordinator and unsubscribe from events."""
        for unsub in self._unsubscribers:
            unsub()
        self._unsubscribers.clear()
        _LOGGER.debug("SELF_HEALING: Coordinator stopped")

    def _create_refresh_task(self, *, interface_id: str) -> Callable[[], Coroutine[Any, Any, None]]:
        """
        Create a coroutine factory for refreshing interface data.

        This method creates a properly typed closure that captures the interface_id
        for later async execution by the task scheduler.

        Args:
        ----
            interface_id: The interface ID to refresh

        Returns:
        -------
            A callable that returns a coroutine for refreshing interface data

        """

        async def refresh_task() -> None:
            await self._refresh_interface_data(interface_id=interface_id)

        return refresh_task

    def _on_circuit_breaker_state_changed(self, *, event: CircuitBreakerStateChangedEvent) -> None:
        """
        Handle circuit breaker state change event.

        When a circuit breaker recovers (HALF_OPEN → CLOSED), we trigger a
        data refresh for the interface to ensure data consistency after
        the connection was restored.

        Args:
        ----
            event: The circuit breaker state changed event

        """
        # Only act on recovery: HALF_OPEN → CLOSED
        if event.old_state == CircuitState.HALF_OPEN and event.new_state == CircuitState.CLOSED:
            _LOGGER.info(  # i18n-log: ignore
                "SELF_HEALING: Circuit breaker recovered for %s, scheduling data refresh",
                event.interface_id,
            )

            # Emit counter metric for recovery
            emit_counter(
                event_bus=self._event_bus,
                key=MetricKeys.self_healing_recovery(interface_id=event.interface_id),
            )

            # Emit event for metrics tracking
            self._event_bus.publish_sync(
                event=SelfHealingTriggeredEvent(
                    timestamp=datetime.now(),
                    interface_id=event.interface_id,
                    action="recovery_initiated",
                    details=None,
                )
            )

            # Schedule data refresh for the recovered interface
            # Use a helper to capture interface_id properly for type inference
            interface_id = event.interface_id
            self._task_scheduler.create_task(
                target=self._create_refresh_task(interface_id=interface_id),
                name=f"self_healing_refresh_{interface_id}",
            )

    def _on_circuit_breaker_tripped(self, *, event: CircuitBreakerTrippedEvent) -> None:
        """
        Handle circuit breaker tripped event.

        This is called when a circuit breaker opens due to repeated failures.
        We log a warning and emit an event for observability.

        Args:
        ----
            event: The circuit breaker tripped event

        """
        _LOGGER.warning(  # i18n-log: ignore
            "SELF_HEALING: Circuit breaker tripped for %s after %d failures (cooldown: %.1fs)",
            event.interface_id,
            event.failure_count,
            event.cooldown_seconds,
        )

        # Emit counter metric for trip
        emit_counter(
            event_bus=self._event_bus,
            key=MetricKeys.self_healing_trip(interface_id=event.interface_id),
        )

        # Emit event for metrics tracking
        self._event_bus.publish_sync(
            event=SelfHealingTriggeredEvent(
                timestamp=datetime.now(),
                interface_id=event.interface_id,
                action="trip_logged",
                details=f"failure_count={event.failure_count}",
            )
        )

    async def _refresh_interface_data(self, *, interface_id: str) -> None:
        """
        Refresh data for a specific interface after recovery.

        This ensures data consistency after a connection was restored.

        Args:
        ----
            interface_id: The interface to refresh data for

        """
        try:
            # Get the interface from the interface_id
            # The interface_id is in format "central_name-Interface.NAME"
            # We need to extract the Interface enum value
            from aiohomematic.const import Interface  # noqa: PLC0415

            # Parse interface from interface_id (e.g., "ccu-BidCos-RF" → Interface.BIDCOS_RF)
            interface_name = interface_id.split("-", 1)[-1] if "-" in interface_id else interface_id
            interface: Interface | None = None
            for iface in Interface:
                if iface.value == interface_name:
                    interface = iface
                    break

            if interface is None:
                _LOGGER.warning(  # i18n-log: ignore
                    "SELF_HEALING: Could not determine interface from %s",
                    interface_id,
                )
                # Emit counter metric for failure
                emit_counter(
                    event_bus=self._event_bus,
                    key=MetricKeys.self_healing_refresh_failure(interface_id=interface_id),
                )
                await self._event_bus.publish(
                    event=SelfHealingDataRefreshEvent(
                        timestamp=datetime.now(),
                        interface_id=interface_id,
                        success=False,
                        error_message=f"Unknown interface: {interface_id}",
                    )
                )
                return

            await self._device_data_refresher.load_and_refresh_data_point_data(interface=interface)

            _LOGGER.debug(
                "SELF_HEALING: Data refresh completed for %s",
                interface_id,
            )

            # Emit counter metric for success
            emit_counter(
                event_bus=self._event_bus,
                key=MetricKeys.self_healing_refresh_success(interface_id=interface_id),
            )

            # Emit success event
            await self._event_bus.publish(
                event=SelfHealingDataRefreshEvent(
                    timestamp=datetime.now(),
                    interface_id=interface_id,
                    success=True,
                    error_message=None,
                )
            )

        except Exception as exc:
            _LOGGER.exception(  # i18n-log: ignore
                "SELF_HEALING: Data refresh failed for %s",
                interface_id,
            )
            # Emit counter metric for failure
            emit_counter(
                event_bus=self._event_bus,
                key=MetricKeys.self_healing_refresh_failure(interface_id=interface_id),
            )
            # Emit failure event
            await self._event_bus.publish(
                event=SelfHealingDataRefreshEvent(
                    timestamp=datetime.now(),
                    interface_id=interface_id,
                    success=False,
                    error_message=str(exc),
                )
            )


def create_self_healing_coordinator(
    *,
    event_bus: EventBus,
    device_data_refresher: DeviceDataRefresherProtocol,
    task_scheduler: TaskSchedulerProtocol,
) -> SelfHealingCoordinator:
    """
    Create a SelfHealingCoordinator instance.

    Factory function for creating a self-healing coordinator with all
    required dependencies.

    Args:
    ----
        event_bus: EventBus to subscribe to circuit breaker events
        device_data_refresher: Refresher for device data after recovery
        task_scheduler: Scheduler for async task management

    Returns:
    -------
        Configured SelfHealingCoordinator instance

    """
    return SelfHealingCoordinator(
        event_bus=event_bus,
        device_data_refresher=device_data_refresher,
        task_scheduler=task_scheduler,
    )
