# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Unified connection recovery coordinator.

Overview
--------
This module provides the ConnectionRecoveryCoordinator which consolidates:
- SelfHealingCoordinator (event-driven triggers)
- RecoveryCoordinator (retry tracking, state transitions)
- BackgroundScheduler._check_connection (staged reconnection)

Into a single, event-driven recovery system.

Architecture
------------
The coordinator:
1. Subscribes to connection-related events (ConnectionLostEvent, CircuitBreakerTrippedEvent)
2. Executes staged recovery (TCP check → RPC check → warmup → reconnect → data load)
3. Tracks retry attempts with exponential backoff
4. Manages central state transitions (RECOVERING, RUNNING, DEGRADED, FAILED)
5. Provides heartbeat retry in FAILED state

Event Flow
----------
::

    ConnectionLostEvent / CircuitBreakerTrippedEvent
        │
        ▼
    ConnectionRecoveryCoordinator
        │
        ├─► RecoveryStageChangedEvent (per stage transition)
        │
        ├─► RecoveryAttemptedEvent (per attempt)
        │
        └─► RecoveryCompletedEvent / RecoveryFailedEvent

Public API
----------
- ConnectionRecoveryCoordinator: Main coordinator class
- MAX_RECOVERY_ATTEMPTS: Maximum retry attempts before FAILED state
- HEARTBEAT_RETRY_INTERVAL: Interval between heartbeat retries
- MAX_CONCURRENT_RECOVERIES: Maximum parallel recovery operations
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
import logging
import time
from typing import TYPE_CHECKING, Final

from aiohomematic.central.event_bus import (
    CircuitBreakerStateChangedEvent,
    CircuitBreakerTrippedEvent,
    ConnectionLostEvent,
    HeartbeatTimerFiredEvent,
    RecoveryAttemptedEvent,
    RecoveryCompletedEvent,
    RecoveryFailedEvent,
    RecoveryStageChangedEvent,
)
from aiohomematic.client.circuit_breaker import CircuitState
from aiohomematic.const import CentralState, FailureReason, RecoveryStage

if TYPE_CHECKING:
    from collections.abc import Callable

    from aiohomematic.central.event_bus import EventBus
    from aiohomematic.central.state_machine import CentralStateMachine
    from aiohomematic.interfaces.central import CentralInfoProtocol, ConfigProviderProtocol, DeviceDataRefresherProtocol
    from aiohomematic.interfaces.client import ClientProviderProtocol
    from aiohomematic.interfaces.coordinators import CoordinatorProviderProtocol
    from aiohomematic.interfaces.operations import TaskSchedulerProtocol

_LOGGER: Final = logging.getLogger(__name__)

# Maximum number of recovery attempts before transitioning to FAILED
MAX_RECOVERY_ATTEMPTS: Final[int] = 8

# Interval between heartbeat retries in FAILED state (seconds)
HEARTBEAT_RETRY_INTERVAL: Final[float] = 60.0

# Base delay between recovery attempts (seconds)
BASE_RETRY_DELAY: Final[float] = 5.0

# Maximum delay between recovery attempts (seconds)
MAX_RETRY_DELAY: Final[float] = 60.0

# Maximum concurrent recovery operations
MAX_CONCURRENT_RECOVERIES: Final[int] = 2


@dataclass(slots=True)
class InterfaceRecoveryState:
    """
    State tracking for recovery of a single interface.

    Tracks attempt count, timing, stage progression, and history.
    """

    interface_id: str
    attempt_count: int = 0
    last_attempt: datetime | None = None
    last_success: datetime | None = None
    consecutive_failures: int = 0
    current_stage: RecoveryStage = RecoveryStage.IDLE
    stage_entered_at: datetime = field(default_factory=datetime.now)
    stages_completed: list[RecoveryStage] = field(default_factory=list)
    recovery_start_time: float | None = None

    @property
    def can_retry(self) -> bool:
        """Check if another retry attempt is allowed."""
        return self.attempt_count < MAX_RECOVERY_ATTEMPTS

    @property
    def next_retry_delay(self) -> float:
        """Calculate delay before next retry using exponential backoff."""
        if self.consecutive_failures == 0:
            return BASE_RETRY_DELAY
        # Exponential backoff: BASE * 2^(failures-1), capped at MAX
        delay: float = BASE_RETRY_DELAY * (2 ** (self.consecutive_failures - 1))
        return float(min(delay, MAX_RETRY_DELAY))

    def record_failure(self) -> None:
        """Record a failed recovery attempt."""
        self.consecutive_failures += 1
        self.last_attempt = datetime.now()
        self.attempt_count += 1

    def record_success(self) -> None:
        """Record a successful recovery attempt."""
        self.consecutive_failures = 0
        self.last_success = datetime.now()
        self.last_attempt = datetime.now()
        self.attempt_count += 1

    def reset(self) -> None:
        """Reset recovery state after successful recovery."""
        self.attempt_count = 0
        self.consecutive_failures = 0
        self.current_stage = RecoveryStage.IDLE
        self.stages_completed.clear()
        self.recovery_start_time = None

    def start_recovery(self) -> None:
        """Start a new recovery cycle."""
        self.recovery_start_time = time.perf_counter()
        self.stages_completed.clear()

    def transition_to_stage(self, *, new_stage: RecoveryStage) -> float:
        """
        Transition to a new recovery stage.

        Args:
            new_stage: The new stage to transition to

        Returns:
            Duration in the old stage in milliseconds.

        """
        duration_ms = (datetime.now() - self.stage_entered_at).total_seconds() * 1000
        if self.current_stage not in (RecoveryStage.IDLE, RecoveryStage.RECOVERED, RecoveryStage.FAILED):
            self.stages_completed.append(self.current_stage)
        self.current_stage = new_stage
        self.stage_entered_at = datetime.now()
        return duration_ms


class ConnectionRecoveryCoordinator:
    """
    Unified coordinator for connection recovery.

    Consolidates:
    - SelfHealingCoordinator (event-driven triggers)
    - RecoveryCoordinator (retry tracking, state transitions)
    - BackgroundScheduler._check_connection (staged reconnection)

    Thread Safety
    -------------
    This class is designed for single-threaded asyncio use.
    All event handlers and recovery operations run in the same event loop.

    Example Usage
    -------------
        coordinator = ConnectionRecoveryCoordinator(
            central_info=central,
            config_provider=central,
            client_provider=central,
            coordinator_provider=central,
            device_data_refresher=central,
            event_bus=central.event_bus,
            task_scheduler=central,
            state_machine=central.state_machine,
        )

        # Recovery happens automatically via events

        # To stop:
        coordinator.stop()

    """

    __slots__ = (
        "_active_recoveries",
        "_central_info",
        "_client_provider",
        "_config_provider",
        "_coordinator_provider",
        "_device_data_refresher",
        "_event_bus",
        "_heartbeat_task",
        "_in_failed_state",
        "_recovery_semaphore",
        "_recovery_states",
        "_shutdown",
        "_state_machine",
        "_task_scheduler",
        "_unsubscribers",
    )

    def __init__(
        self,
        *,
        central_info: CentralInfoProtocol,
        config_provider: ConfigProviderProtocol,
        client_provider: ClientProviderProtocol,
        coordinator_provider: CoordinatorProviderProtocol,
        device_data_refresher: DeviceDataRefresherProtocol,
        event_bus: EventBus,
        task_scheduler: TaskSchedulerProtocol,
        state_machine: CentralStateMachine | None = None,
    ) -> None:
        """
        Initialize the connection recovery coordinator.

        Args:
            central_info: Central system information
            config_provider: Configuration provider
            client_provider: Client lookup provider
            coordinator_provider: Coordinator provider for client coordinator access
            device_data_refresher: Device data refresh operations
            event_bus: Event bus for subscriptions and publishing
            task_scheduler: Task scheduler for async operations
            state_machine: Optional central state machine

        """
        self._central_info: Final = central_info
        self._config_provider: Final = config_provider
        self._client_provider: Final = client_provider
        self._coordinator_provider: Final = coordinator_provider
        self._device_data_refresher: Final = device_data_refresher
        self._event_bus: Final = event_bus
        self._task_scheduler: Final = task_scheduler
        self._state_machine = state_machine

        # Recovery state tracking
        self._recovery_states: dict[str, InterfaceRecoveryState] = {}
        self._active_recoveries: set[str] = set()
        self._recovery_semaphore = asyncio.Semaphore(MAX_CONCURRENT_RECOVERIES)
        self._in_failed_state: bool = False
        self._shutdown: bool = False
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._unsubscribers: list[Callable[[], None]] = []

        # Subscribe to connection-related events
        self._subscribe_to_events()

        _LOGGER.debug("CONNECTION_RECOVERY: Coordinator initialized for %s", self._central_info.name)

    @property
    def in_recovery(self) -> bool:
        """Return True if any recovery is in progress."""
        return bool(self._active_recoveries)

    @property
    def recovery_states(self) -> dict[str, InterfaceRecoveryState]:
        """Return recovery states for all tracked interfaces."""
        return self._recovery_states.copy()

    def get_recovery_state(self, *, interface_id: str) -> InterfaceRecoveryState | None:
        """Return recovery state for a specific interface."""
        return self._recovery_states.get(interface_id)

    def set_state_machine(self, *, state_machine: CentralStateMachine) -> None:
        """Set the state machine reference."""
        self._state_machine = state_machine

    def stop(self) -> None:
        """Stop the coordinator and unsubscribe from events."""
        self._shutdown = True

        # Cancel heartbeat task if running
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()

        # Unsubscribe from all events
        for unsub in self._unsubscribers:
            unsub()
        self._unsubscribers.clear()

        _LOGGER.debug("CONNECTION_RECOVERY: Coordinator stopped for %s", self._central_info.name)

    async def _check_rpc_available(self, *, interface_id: str) -> bool:
        """Check if RPC interface is available via system.listMethods."""
        try:
            client = self._client_provider.get_client(interface_id=interface_id)
            # Access proxy's system.listMethods via XML-RPC magic method
            # pylint: disable=protected-access
            if hasattr(client, "_proxy") and hasattr(client._proxy, "system"):
                result = await client._proxy.system.listMethods()
                return bool(result)
        except Exception:  # noqa: BLE001
            pass
        return False

    async def _check_tcp_port_available(self, *, host: str, port: int) -> bool:
        """Check if a TCP port is available (non-invasive connectivity check)."""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=2.0,
            )
            writer.close()
            await writer.wait_closed()
        except (TimeoutError, OSError):
            return False
        return True

    async def _emit_recovery_attempt(
        self,
        *,
        interface_id: str,
        state: InterfaceRecoveryState,
        success: bool,
        error_message: str | None = None,
    ) -> None:
        """Emit a recovery attempt event."""
        await self._event_bus.publish(
            event=RecoveryAttemptedEvent(
                timestamp=datetime.now(),
                interface_id=interface_id,
                attempt_number=state.attempt_count,
                max_attempts=MAX_RECOVERY_ATTEMPTS,
                stage_reached=state.current_stage,
                success=success,
                error_message=error_message,
            )
        )

    async def _emit_recovery_completed(
        self,
        *,
        interface_id: str,
        state: InterfaceRecoveryState,
    ) -> None:
        """Emit a recovery completed event."""
        duration_ms = (time.perf_counter() - state.recovery_start_time) * 1000 if state.recovery_start_time else 0.0

        await self._event_bus.publish(
            event=RecoveryCompletedEvent(
                timestamp=datetime.now(),
                interface_id=interface_id,
                central_name=self._central_info.name,
                total_attempts=state.attempt_count,
                total_duration_ms=duration_ms,
                stages_completed=tuple(state.stages_completed),
            )
        )

    async def _emit_recovery_failed(
        self,
        *,
        interface_id: str,
        state: InterfaceRecoveryState,
    ) -> None:
        """Emit a recovery failed event."""
        duration_ms = (time.perf_counter() - state.recovery_start_time) * 1000 if state.recovery_start_time else 0.0

        await self._event_bus.publish(
            event=RecoveryFailedEvent(
                timestamp=datetime.now(),
                interface_id=interface_id,
                central_name=self._central_info.name,
                total_attempts=state.attempt_count,
                total_duration_ms=duration_ms,
                last_stage_reached=state.current_stage,
                failure_reason=FailureReason.UNKNOWN,
                requires_manual_intervention=True,
            )
        )

    async def _execute_recovery_stages(self, *, interface_id: str) -> bool:
        """
        Execute staged recovery for an interface.

        Returns True if recovery succeeded, False otherwise.
        """
        if interface_id not in self._recovery_states:
            return False

        timeout_config = self._config_provider.config.timeout_config

        try:
            # Stage: DETECTING → COOLDOWN
            await self._transition_stage(interface_id=interface_id, new_stage=RecoveryStage.COOLDOWN)
            await asyncio.sleep(timeout_config.reconnect_initial_cooldown)

            # Stage: COOLDOWN → TCP_CHECKING
            await self._transition_stage(interface_id=interface_id, new_stage=RecoveryStage.TCP_CHECKING)
            if not await self._stage_tcp_check(interface_id=interface_id):
                return False

            # Stage: TCP_CHECKING → RPC_CHECKING
            await self._transition_stage(interface_id=interface_id, new_stage=RecoveryStage.RPC_CHECKING)
            if not await self._stage_rpc_check(interface_id=interface_id):
                return False

            # Stage: RPC_CHECKING → WARMING_UP
            await self._transition_stage(interface_id=interface_id, new_stage=RecoveryStage.WARMING_UP)
            await asyncio.sleep(timeout_config.reconnect_warmup_delay)

            # Stage: WARMING_UP → STABILITY_CHECK
            await self._transition_stage(interface_id=interface_id, new_stage=RecoveryStage.STABILITY_CHECK)
            if not await self._stage_stability_check(interface_id=interface_id):
                return False

            # Stage: STABILITY_CHECK → RECONNECTING
            await self._transition_stage(interface_id=interface_id, new_stage=RecoveryStage.RECONNECTING)
            if not await self._stage_reconnect(interface_id=interface_id):
                return False

            # Stage: RECONNECTING → DATA_LOADING
            await self._transition_stage(interface_id=interface_id, new_stage=RecoveryStage.DATA_LOADING)
            if not await self._stage_data_load(interface_id=interface_id):
                return False

            # Stage: DATA_LOADING → RECOVERED
            await self._transition_stage(interface_id=interface_id, new_stage=RecoveryStage.RECOVERED)

        except asyncio.CancelledError:
            _LOGGER.debug("CONNECTION_RECOVERY: Recovery cancelled for %s", interface_id)
            raise
        except Exception:
            _LOGGER.exception(  # i18n-log: ignore
                "CONNECTION_RECOVERY: Exception during recovery of %s",
                interface_id,
            )
            return False
        else:
            return True

    def _get_client_port(self, *, interface_id: str) -> int | None:
        """Get the port for a client."""
        try:
            client = self._client_provider.get_client(interface_id=interface_id)
            # Access internal config to get port - pylint: disable=protected-access
            if hasattr(client, "_config") and hasattr(client._config, "interface_config"):
                port = client._config.interface_config.port
                return port if isinstance(port, int) else None
        except Exception:  # noqa: BLE001
            pass
        return None

    async def _handle_max_retries_reached(self, *, interface_id: str) -> None:
        """Handle when max retries are reached for an interface."""
        self._in_failed_state = True
        self._transition_to_failed(interface_id=interface_id)

        if state := self._recovery_states.get(interface_id):
            await self._emit_recovery_failed(interface_id=interface_id, state=state)

        # Start heartbeat timer if not already running
        self._start_heartbeat_timer()

        _LOGGER.error(  # i18n-log: ignore
            "CONNECTION_RECOVERY: FAILED state entered for %s - max retries reached. "
            "Will retry every %d seconds via heartbeat.",
            interface_id,
            int(HEARTBEAT_RETRY_INTERVAL),
        )

    async def _heartbeat_loop(self) -> None:
        """Heartbeat loop for FAILED state retries."""
        while self._in_failed_state and not self._shutdown:
            await asyncio.sleep(HEARTBEAT_RETRY_INTERVAL)

            # Re-check conditions after sleep (state may have changed during await)
            if not self._in_failed_state or self._shutdown:
                return  # type: ignore[unreachable]

            # Get failed interfaces
            failed_interfaces = tuple(iid for iid, state in self._recovery_states.items() if not state.can_retry)

            if failed_interfaces:
                # Reset attempt counts to allow retry
                for iid in failed_interfaces:
                    if (state := self._recovery_states.get(iid)) is not None:
                        state.attempt_count = MAX_RECOVERY_ATTEMPTS - 1

                # Emit heartbeat event
                await self._event_bus.publish(
                    event=HeartbeatTimerFiredEvent(
                        timestamp=datetime.now(),
                        central_name=self._central_info.name,
                        interface_ids=failed_interfaces,
                    )
                )

    def _on_circuit_breaker_state_changed(self, *, event: CircuitBreakerStateChangedEvent) -> None:
        """Handle circuit breaker state change event."""
        if self._shutdown:
            return

        # Only act on recovery: HALF_OPEN → CLOSED
        if event.old_state == CircuitState.HALF_OPEN and event.new_state == CircuitState.CLOSED:
            _LOGGER.info(  # i18n-log: ignore
                "CONNECTION_RECOVERY: Circuit breaker recovered for %s, triggering data refresh",
                event.interface_id,
            )
            # Schedule data refresh for the recovered interface
            iid = event.interface_id

            async def refresh_data() -> None:
                await self._refresh_interface_data(interface_id=iid)

            self._task_scheduler.create_task(
                target=refresh_data,
                name=f"recovery_refresh_{event.interface_id}",
            )

    def _on_circuit_breaker_tripped(self, *, event: CircuitBreakerTrippedEvent) -> None:
        """Handle circuit breaker tripped event."""
        if self._shutdown:
            return

        interface_id = event.interface_id

        _LOGGER.warning(  # i18n-log: ignore
            "CONNECTION_RECOVERY: Circuit breaker tripped for %s after %d failures",
            interface_id,
            event.failure_count,
        )

        # Circuit breaker trip indicates connection issues - start recovery if not already
        if interface_id not in self._active_recoveries:

            async def start_recovery_cb() -> None:
                await self._start_recovery(interface_id=interface_id)

            self._task_scheduler.create_task(
                target=start_recovery_cb,
                name=f"recovery_cb_{interface_id}",
            )

    def _on_connection_lost(self, *, event: ConnectionLostEvent) -> None:
        """Handle connection lost event."""
        if self._shutdown:
            return

        # Skip if already recovering this interface
        if (interface_id := event.interface_id) in self._active_recoveries:
            _LOGGER.debug(
                "CONNECTION_RECOVERY: %s already recovering, skipping duplicate event",
                interface_id,
            )
            return

        _LOGGER.info(  # i18n-log: ignore
            "CONNECTION_RECOVERY: Connection lost for %s (reason: %s), starting recovery",
            interface_id,
            event.reason,
        )

        # Start recovery for this interface
        async def start_recovery() -> None:
            await self._start_recovery(interface_id=interface_id)

        self._task_scheduler.create_task(
            target=start_recovery,
            name=f"recovery_{interface_id}",
        )

    def _on_heartbeat_timer_fired(self, *, event: HeartbeatTimerFiredEvent) -> None:
        """Handle heartbeat timer fired event."""
        if self._shutdown or not self._in_failed_state:
            return

        _LOGGER.info(  # i18n-log: ignore
            "CONNECTION_RECOVERY: Heartbeat retry for %s with %d failed interfaces",
            event.central_name,
            len(event.interface_ids),
        )

        # Start recovery for all failed interfaces
        self._task_scheduler.create_task(
            target=lambda: self._recover_all_interfaces(interface_ids=list(event.interface_ids)),
            name="heartbeat_recovery",
        )

    async def _recover_all_interfaces(self, *, interface_ids: list[str]) -> None:
        """Recover multiple interfaces with throttling."""
        if self._shutdown:
            return

        async def throttled_recovery(interface_id: str) -> bool:
            async with self._recovery_semaphore:
                return await self._execute_recovery_stages(interface_id=interface_id)

        # Run recoveries in parallel with throttling
        tasks = [throttled_recovery(iid) for iid in interface_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        success_count = sum(1 for r in results if r is True)
        failed_count = len(interface_ids) - success_count

        if success_count == len(interface_ids):
            self._in_failed_state = False
            self._transition_to_running()
        elif success_count > 0:
            self._transition_to_degraded(failed_count=failed_count)

    async def _refresh_interface_data(self, *, interface_id: str) -> None:
        """Refresh data for a specific interface after recovery."""
        try:
            client = self._client_provider.get_client(interface_id=interface_id)
            await self._device_data_refresher.load_and_refresh_data_point_data(interface=client.interface)
            _LOGGER.debug("CONNECTION_RECOVERY: Data refresh completed for %s", interface_id)
        except Exception:
            _LOGGER.exception(  # i18n-log: ignore
                "CONNECTION_RECOVERY: Data refresh failed for %s",
                interface_id,
            )

    async def _stage_data_load(self, *, interface_id: str) -> bool:
        """Stage: Load device and paramset data."""
        try:
            client = self._client_provider.get_client(interface_id=interface_id)
            interface = client.interface
            await self._device_data_refresher.load_and_refresh_data_point_data(interface=interface)
        except Exception:
            _LOGGER.exception(  # i18n-log: ignore
                "CONNECTION_RECOVERY: Data load failed for %s",
                interface_id,
            )
            return False

        _LOGGER.info(  # i18n-log: ignore
            "CONNECTION_RECOVERY: Data load completed for %s",
            interface_id,
        )
        return True

    async def _stage_reconnect(self, *, interface_id: str) -> bool:
        """Stage: Perform full client reconnection."""
        try:
            client = self._client_provider.get_client(interface_id=interface_id)
            await client.reconnect()
        except Exception:
            _LOGGER.exception(  # i18n-log: ignore
                "CONNECTION_RECOVERY: Reconnect exception for %s",
                interface_id,
            )
            return False

        if client.available:
            _LOGGER.info(  # i18n-log: ignore
                "CONNECTION_RECOVERY: Reconnect succeeded for %s",
                interface_id,
            )
            return True

        _LOGGER.warning(  # i18n-log: ignore
            "CONNECTION_RECOVERY: Reconnect failed for %s - client not available",
            interface_id,
        )
        return False

    async def _stage_rpc_check(self, *, interface_id: str) -> bool:
        """Stage: Check RPC service availability."""
        if await self._check_rpc_available(interface_id=interface_id):
            _LOGGER.info(  # i18n-log: ignore
                "CONNECTION_RECOVERY: RPC service available for %s",
                interface_id,
            )
            return True
        return False

    async def _stage_stability_check(self, *, interface_id: str) -> bool:
        """Stage: Confirm RPC stability after warmup."""
        if await self._check_rpc_available(interface_id=interface_id):
            _LOGGER.info(  # i18n-log: ignore
                "CONNECTION_RECOVERY: RPC service stable for %s",
                interface_id,
            )
            return True

        _LOGGER.warning(  # i18n-log: ignore
            "CONNECTION_RECOVERY: RPC unstable after warmup for %s",
            interface_id,
        )
        return False

    async def _stage_tcp_check(self, *, interface_id: str) -> bool:
        """Stage: Check TCP port availability."""
        timeout_config = self._config_provider.config.timeout_config
        host = self._config_provider.config.host

        if (port := self._get_client_port(interface_id=interface_id)) is None:
            return False

        start_time = time.perf_counter()
        while (time.perf_counter() - start_time) < timeout_config.reconnect_tcp_check_timeout:
            if await self._check_tcp_port_available(host=host, port=port):
                _LOGGER.info(  # i18n-log: ignore
                    "CONNECTION_RECOVERY: TCP port available for %s (%s:%d)",
                    interface_id,
                    host,
                    port,
                )
                return True
            await asyncio.sleep(2.0)  # Check every 2 seconds

        _LOGGER.warning(  # i18n-log: ignore
            "CONNECTION_RECOVERY: TCP check timeout for %s",
            interface_id,
        )
        return False

    def _start_heartbeat_timer(self) -> None:
        """Start the heartbeat timer for FAILED state retries."""
        if self._heartbeat_task and not self._heartbeat_task.done():
            return  # Already running

        self._task_scheduler.create_task(
            target=self._heartbeat_loop,
            name="heartbeat_timer",
        )

    async def _start_recovery(self, *, interface_id: str) -> None:
        """Start recovery for a single interface."""
        if self._shutdown:
            return

        # Get or create recovery state
        if (state := self._recovery_states.get(interface_id)) is None:
            state = InterfaceRecoveryState(interface_id=interface_id)
            self._recovery_states[interface_id] = state

        # Check if max retries reached
        if not state.can_retry:
            _LOGGER.warning(  # i18n-log: ignore
                "CONNECTION_RECOVERY: Max retries (%d) reached for %s",
                MAX_RECOVERY_ATTEMPTS,
                interface_id,
            )
            await self._handle_max_retries_reached(interface_id=interface_id)
            return

        # Mark as active recovery
        self._active_recoveries.add(interface_id)
        state.start_recovery()

        # Transition central to RECOVERING
        self._transition_to_recovering()

        # Clear JSON-RPC session to force re-authentication
        # This prevents auth errors from stale sessions during recovery
        if client := self._client_provider.get_client(interface_id=interface_id):
            client.clear_json_rpc_session()

        try:
            async with self._recovery_semaphore:
                success = await self._execute_recovery_stages(interface_id=interface_id)

            if success:
                state.record_success()
                state.reset()
                await self._emit_recovery_completed(interface_id=interface_id, state=state)
                self._transition_after_recovery()
            else:
                state.record_failure()
                await self._emit_recovery_attempt(interface_id=interface_id, state=state, success=False)

                # Note: record_failure() above incremented attempt_count, may now exceed max
                if not state.can_retry:
                    await self._handle_max_retries_reached(  # type: ignore[unreachable]
                        interface_id=interface_id
                    )
                else:
                    # Schedule retry with backoff
                    delay = state.next_retry_delay
                    _LOGGER.info(  # i18n-log: ignore
                        "CONNECTION_RECOVERY: Scheduling retry for %s in %.1fs",
                        interface_id,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    if not self._shutdown:
                        await self._start_recovery(interface_id=interface_id)

        finally:
            self._active_recoveries.discard(interface_id)

    def _stop_heartbeat_timer(self) -> None:
        """Stop the heartbeat timer."""
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            self._heartbeat_task = None

    def _subscribe_to_events(self) -> None:
        """Subscribe to connection-related events."""
        self._unsubscribers.append(
            self._event_bus.subscribe(
                event_type=ConnectionLostEvent,
                event_key=None,
                handler=self._on_connection_lost,
            )
        )
        self._unsubscribers.append(
            self._event_bus.subscribe(
                event_type=CircuitBreakerTrippedEvent,
                event_key=None,
                handler=self._on_circuit_breaker_tripped,
            )
        )
        self._unsubscribers.append(
            self._event_bus.subscribe(
                event_type=CircuitBreakerStateChangedEvent,
                event_key=None,
                handler=self._on_circuit_breaker_state_changed,
            )
        )
        self._unsubscribers.append(
            self._event_bus.subscribe(
                event_type=HeartbeatTimerFiredEvent,
                event_key=None,
                handler=self._on_heartbeat_timer_fired,
            )
        )

    def _transition_after_recovery(self) -> None:
        """Transition central state after successful recovery."""
        if self._state_machine is None:
            return

        # Check if all active recoveries are complete
        if not self._active_recoveries:
            self._transition_to_running()
            self._in_failed_state = False
            self._stop_heartbeat_timer()

    async def _transition_stage(self, *, interface_id: str, new_stage: RecoveryStage) -> None:
        """Transition to a new recovery stage and emit event."""
        if (state := self._recovery_states.get(interface_id)) is None:
            return

        if (old_stage := state.current_stage) == new_stage:
            return

        duration_ms = state.transition_to_stage(new_stage=new_stage)

        await self._event_bus.publish(
            event=RecoveryStageChangedEvent(
                timestamp=datetime.now(),
                interface_id=interface_id,
                old_stage=old_stage,
                new_stage=new_stage,
                duration_in_old_stage_ms=duration_ms,
                attempt_number=state.attempt_count + 1,
            )
        )

    def _transition_to_degraded(self, *, failed_count: int) -> None:
        """Transition central to DEGRADED state."""
        if self._state_machine is None:
            return

        if self._state_machine.can_transition_to(target=CentralState.DEGRADED):
            self._state_machine.transition_to(
                target=CentralState.DEGRADED,
                reason=f"Partial recovery: {failed_count} interface(s) still failed",
            )

    def _transition_to_failed(self, *, interface_id: str) -> None:
        """Transition central to FAILED state."""
        if self._state_machine is None:
            return

        if self._state_machine.can_transition_to(target=CentralState.FAILED):
            self._state_machine.transition_to(
                target=CentralState.FAILED,
                reason=f"Max retries reached for {interface_id}",
                failure_reason=FailureReason.UNKNOWN,
                failure_interface_id=interface_id,
            )

    def _transition_to_recovering(self) -> None:
        """Transition central to RECOVERING state."""
        if self._state_machine is None:
            return

        if self._state_machine.can_transition_to(target=CentralState.RECOVERING):
            self._state_machine.transition_to(
                target=CentralState.RECOVERING,
                reason="Connection recovery in progress",
            )

    def _transition_to_running(self) -> None:
        """Transition central to RUNNING state."""
        if self._state_machine is None:
            return

        if self._state_machine.can_transition_to(target=CentralState.RUNNING):
            self._state_machine.transition_to(
                target=CentralState.RUNNING,
                reason="All interfaces recovered successfully",
            )
