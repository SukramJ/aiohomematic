# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Recovery coordinator for orchestrating client reconnection.

This module provides the RecoveryCoordinator which manages the recovery
process for failed or degraded client connections.

Overview
--------
The RecoveryCoordinator provides:
- Coordinated recovery for multiple clients
- Max retry tracking with transition to FAILED state
- Multi-stage data load verification
- Heartbeat retry in FAILED state
- Adaptive retry timing (prepared for Phase 5)

Recovery Process
----------------
1. Detect failed/degraded client (via health tracking)
2. Transition Central to RECOVERING state
3. For each failed client:
   a. Attempt reconnection
   b. If connected, perform basic data load test
   c. If basic test passes, verify full data load
4. Update central state based on results:
   - All recovered → RUNNING
   - Partial recovery → DEGRADED
   - Max retries reached → FAILED (with heartbeat retry)

Max Retry Behavior
------------------
After MAX_RECOVERY_ATTEMPTS failures:
- Central transitions to FAILED state
- Heartbeat retry every HEARTBEAT_RETRY_INTERVAL
- Manual intervention message is logged
- Recovery can still succeed during heartbeat retry

Example:
    coordinator = RecoveryCoordinator(
        central_name="ccu-main",
        state_machine=central_state_machine,
        health_tracker=health_tracker,
    )

    # Start recovery for a failed client
    await coordinator.recover_client(interface_id="ccu-main-HmIP-RF")

    # Or recover all failed clients
    await coordinator.recover_all_failed()

"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
import logging
from typing import TYPE_CHECKING, Any, Final

from aiohomematic.const import CentralState

if TYPE_CHECKING:
    from aiohomematic.central.health import HealthTracker
    from aiohomematic.central.state_machine import CentralStateMachine

_LOGGER: Final = logging.getLogger(__name__)

# Maximum number of recovery attempts before transitioning to FAILED
MAX_RECOVERY_ATTEMPTS: Final[int] = 8

# Interval between heartbeat retries in FAILED state (seconds)
HEARTBEAT_RETRY_INTERVAL: Final[float] = 60.0

# Base delay between recovery attempts (seconds)
BASE_RETRY_DELAY: Final[float] = 5.0

# Maximum delay between recovery attempts (seconds)
MAX_RETRY_DELAY: Final[float] = 60.0


class RecoveryResult(StrEnum):
    """Result of a recovery attempt."""

    SUCCESS = "success"
    """Recovery was fully successful."""

    PARTIAL = "partial"
    """Some clients recovered, others still failed."""

    FAILED = "failed"
    """Recovery failed for all clients."""

    MAX_RETRIES = "max_retries"
    """Maximum retry attempts reached."""

    CANCELLED = "cancelled"
    """Recovery was cancelled (e.g., during shutdown)."""


class DataLoadStage(StrEnum):
    """Stages of data load verification."""

    BASIC = "basic"
    """Basic connectivity test (ping/pong, simple query)."""

    DEVICES = "devices"
    """Device list can be retrieved."""

    PARAMSETS = "paramsets"
    """Paramset descriptions can be fetched."""

    VALUES = "values"
    """Current values can be read."""

    FULL = "full"
    """All data successfully loaded."""


@dataclass(slots=True)
class RecoveryAttempt:
    """Record of a single recovery attempt."""

    interface_id: str
    attempt_number: int
    started_at: datetime
    completed_at: datetime | None = None
    result: RecoveryResult = RecoveryResult.FAILED
    data_load_stage: DataLoadStage = DataLoadStage.BASIC
    error_message: str | None = None


@dataclass(slots=True)
class RecoveryState:
    """
    State tracking for recovery of a single interface.

    Tracks attempt count, timing, and history for recovery decisions.
    """

    interface_id: str
    attempt_count: int = 0
    last_attempt: datetime | None = None
    last_success: datetime | None = None
    consecutive_failures: int = 0
    history: list[RecoveryAttempt] = field(default_factory=list)

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

    def record_attempt(self, *, result: RecoveryResult, stage: DataLoadStage, error: str | None = None) -> None:
        """
        Record a recovery attempt.

        Args:
            result: The outcome of the attempt
            stage: The data load stage reached
            error: Optional error message

        """
        now = datetime.now()
        attempt = RecoveryAttempt(
            interface_id=self.interface_id,
            attempt_number=self.attempt_count + 1,
            started_at=self.last_attempt or now,
            completed_at=now,
            result=result,
            data_load_stage=stage,
            error_message=error,
        )
        self.history.append(attempt)
        self.attempt_count += 1
        self.last_attempt = now

        if result == RecoveryResult.SUCCESS:
            self.consecutive_failures = 0
            self.last_success = now
        else:
            self.consecutive_failures += 1

        # Keep only last 20 attempts in history
        if len(self.history) > 20:
            self.history = self.history[-20:]

    def reset(self) -> None:
        """Reset recovery state after successful recovery."""
        self.attempt_count = 0
        self.consecutive_failures = 0


class RecoveryCoordinator:
    """
    Coordinator for client recovery operations.

    This class orchestrates the recovery of failed or degraded clients,
    managing retry attempts, data load verification, and central state
    transitions.

    Thread Safety
    -------------
    This class is NOT thread-safe. All calls should happen from the same
    event loop/thread.

    Example:
        coordinator = RecoveryCoordinator(
            central_name="ccu-main",
            state_machine=central_state_machine,
            health_tracker=health_tracker,
        )

        # Recover a specific client
        result = await coordinator.recover_client(interface_id="ccu-main-HmIP-RF")

        # Recover all failed clients
        result = await coordinator.recover_all_failed()

    """

    __slots__ = (
        "_central_name",
        "_health_tracker",
        "_in_recovery",
        "_recovery_states",
        "_shutdown",
        "_state_machine",
    )

    def __init__(
        self,
        *,
        central_name: str,
        state_machine: CentralStateMachine | None = None,
        health_tracker: HealthTracker | None = None,
    ) -> None:
        """
        Initialize the recovery coordinator.

        Args:
            central_name: Name of the central unit
            state_machine: Optional central state machine reference
            health_tracker: Optional health tracker reference

        """
        self._central_name: Final = central_name
        self._state_machine = state_machine
        self._health_tracker = health_tracker
        self._recovery_states: dict[str, RecoveryState] = {}
        self._in_recovery: bool = False
        self._shutdown: bool = False

    @property
    def in_recovery(self) -> bool:
        """Return True if recovery is in progress."""
        return self._in_recovery

    @property
    def recovery_states(self) -> dict[str, RecoveryState]:
        """Return recovery states for all tracked interfaces."""
        return self._recovery_states.copy()

    def get_recovery_state(self, *, interface_id: str) -> RecoveryState | None:
        """
        Get recovery state for a specific interface.

        Args:
            interface_id: The interface ID to look up

        Returns:
            RecoveryState for the interface, or None if not tracked

        """
        return self._recovery_states.get(interface_id)

    async def heartbeat_retry(
        self,
        *,
        get_reconnect_func: Any | None = None,
        get_verify_func: Any | None = None,
    ) -> RecoveryResult:
        """
        Perform a heartbeat retry when in FAILED state.

        This method should be called periodically when central is in FAILED state
        to attempt recovery without resetting retry counters.

        Args:
            get_reconnect_func: Function that takes interface_id and returns reconnect coroutine
            get_verify_func: Function that takes interface_id and returns verify coroutine

        Returns:
            RecoveryResult indicating outcome

        """
        if self._shutdown:
            return RecoveryResult.CANCELLED

        if self._state_machine is None or self._state_machine.state != CentralState.FAILED:
            return RecoveryResult.SUCCESS

        _LOGGER.info(  # i18n-log: ignore
            "RECOVERY: %s: Heartbeat retry attempt in FAILED state",
            self._central_name,
        )

        # Reset attempt counters to allow retry
        for state in self._recovery_states.values():
            if not state.can_retry:
                state.attempt_count = MAX_RECOVERY_ATTEMPTS - 1  # Allow one more attempt

        return await self.recover_all_failed(
            get_reconnect_func=get_reconnect_func,
            get_verify_func=get_verify_func,
        )

    async def recover_all_failed(
        self,
        *,
        get_reconnect_func: Any | None = None,
        get_verify_func: Any | None = None,
    ) -> RecoveryResult:
        """
        Attempt to recover all failed clients.

        Args:
            get_reconnect_func: Function that takes interface_id and returns reconnect coroutine
            get_verify_func: Function that takes interface_id and returns verify coroutine

        Returns:
            RecoveryResult indicating overall outcome

        """
        if self._shutdown:
            return RecoveryResult.CANCELLED

        if self._health_tracker is None:
            _LOGGER.warning("RECOVERY: %s: No health tracker available", self._central_name)  # i18n-log: ignore
            return RecoveryResult.FAILED

        if not (failed_clients := self._health_tracker.health.failed_clients):
            _LOGGER.debug("RECOVERY: %s: No failed clients to recover", self._central_name)
            return RecoveryResult.SUCCESS

        self._in_recovery = True
        _LOGGER.info(  # i18n-log: ignore
            "RECOVERY: %s: Starting recovery for %d failed client(s): %s",
            self._central_name,
            len(failed_clients),
            ", ".join(failed_clients),
        )

        # Transition to RECOVERING state
        if self._state_machine is not None and self._state_machine.can_transition_to(target=CentralState.RECOVERING):
            self._state_machine.transition_to(
                target=CentralState.RECOVERING,
                reason=f"Recovering {len(failed_clients)} failed client(s)",
            )

        success_count = 0
        failed_count = 0
        max_retries_count = 0

        try:
            for interface_id in failed_clients:
                # Check for shutdown signal during loop (may change during await)
                if self._shutdown:
                    return RecoveryResult.CANCELLED  # type: ignore[unreachable]

                reconnect_func = get_reconnect_func(interface_id) if get_reconnect_func else None
                verify_func = get_verify_func(interface_id) if get_verify_func else None

                result = await self.recover_client(
                    interface_id=interface_id,
                    reconnect_func=reconnect_func,
                    verify_func=verify_func,
                )

                if result == RecoveryResult.SUCCESS:
                    success_count += 1
                    self.reset_interface(interface_id=interface_id)
                elif result == RecoveryResult.MAX_RETRIES:
                    max_retries_count += 1
                else:
                    failed_count += 1

                # Wait before next attempt
                if interface_id != failed_clients[-1]:  # Not the last client
                    state = self._recovery_states.get(interface_id)
                    delay = state.next_retry_delay if state else BASE_RETRY_DELAY
                    await asyncio.sleep(delay)

        finally:
            self._in_recovery = False

        # Determine overall result and update central state
        return self._determine_and_set_final_state(
            success_count=success_count,
            failed_count=failed_count,
            max_retries_count=max_retries_count,
            total_count=len(failed_clients),
        )

    async def recover_client(
        self,
        *,
        interface_id: str,
        reconnect_func: Any | None = None,
        verify_func: Any | None = None,
    ) -> RecoveryResult:
        """
        Attempt to recover a single client.

        Args:
            interface_id: The interface ID to recover
            reconnect_func: Optional async function to call for reconnection
            verify_func: Optional async function to verify data load

        Returns:
            RecoveryResult indicating the outcome

        """
        if self._shutdown:
            return RecoveryResult.CANCELLED

        # Get or create recovery state
        if (state := self._recovery_states.get(interface_id)) is None:
            state = self.register_interface(interface_id=interface_id)

        # Check if max retries reached
        if not state.can_retry:
            _LOGGER.warning(  # i18n-log: ignore
                "RECOVERY: %s: Max retries (%d) reached for %s",
                self._central_name,
                MAX_RECOVERY_ATTEMPTS,
                interface_id,
            )
            return RecoveryResult.MAX_RETRIES

        # Mark attempt start
        state.last_attempt = datetime.now()

        _LOGGER.info(  # i18n-log: ignore
            "RECOVERY: %s: Attempting recovery for %s (attempt %d/%d)",
            self._central_name,
            interface_id,
            state.attempt_count + 1,
            MAX_RECOVERY_ATTEMPTS,
        )

        try:
            # Stage 1: Basic reconnection
            if reconnect_func is not None and not await reconnect_func():
                state.record_attempt(
                    result=RecoveryResult.FAILED,
                    stage=DataLoadStage.BASIC,
                    error="Reconnection failed",
                )
                return RecoveryResult.FAILED

            # Stage 2: Data load verification
            if verify_func is not None:
                stage = await self._verify_data_load(
                    interface_id=interface_id,
                    verify_func=verify_func,
                )
                if stage != DataLoadStage.FULL:
                    state.record_attempt(
                        result=RecoveryResult.PARTIAL,
                        stage=stage,
                        error=f"Data load verification failed at stage {stage}",
                    )
                    return RecoveryResult.PARTIAL

        except asyncio.CancelledError:
            state.record_attempt(
                result=RecoveryResult.CANCELLED,
                stage=DataLoadStage.BASIC,
                error="Recovery cancelled",
            )
            raise
        except Exception as ex:
            state.record_attempt(
                result=RecoveryResult.FAILED,
                stage=DataLoadStage.BASIC,
                error=str(ex),
            )
            _LOGGER.exception(  # i18n-log: ignore
                "RECOVERY: %s: Exception during recovery of %s",
                self._central_name,
                interface_id,
            )
            return RecoveryResult.FAILED
        else:
            # Recovery successful (no exceptions)
            state.record_attempt(
                result=RecoveryResult.SUCCESS,
                stage=DataLoadStage.FULL,
            )
            _LOGGER.info(  # i18n-log: ignore
                "RECOVERY: %s: Successfully recovered %s",
                self._central_name,
                interface_id,
            )
            return RecoveryResult.SUCCESS

    def register_interface(self, *, interface_id: str) -> RecoveryState:
        """
        Register an interface for recovery tracking.

        Args:
            interface_id: The interface ID to register

        Returns:
            The created RecoveryState

        """
        if interface_id not in self._recovery_states:
            self._recovery_states[interface_id] = RecoveryState(interface_id=interface_id)
        return self._recovery_states[interface_id]

    def reset_interface(self, *, interface_id: str) -> None:
        """
        Reset recovery state for an interface.

        Called after successful recovery to clear attempt tracking.

        Args:
            interface_id: The interface ID to reset

        """
        if (state := self._recovery_states.get(interface_id)) is not None:
            state.reset()

    def set_health_tracker(self, *, health_tracker: HealthTracker) -> None:
        """
        Set the health tracker reference.

        Args:
            health_tracker: The health tracker

        """
        self._health_tracker = health_tracker

    def set_state_machine(self, *, state_machine: CentralStateMachine) -> None:
        """
        Set the state machine reference.

        Args:
            state_machine: The central state machine

        """
        self._state_machine = state_machine

    def shutdown(self) -> None:
        """Signal that recovery should be cancelled."""
        self._shutdown = True

    def unregister_interface(self, *, interface_id: str) -> None:
        """
        Remove an interface from recovery tracking.

        Args:
            interface_id: The interface ID to remove

        """
        self._recovery_states.pop(interface_id, None)

    def _determine_and_set_final_state(
        self,
        *,
        success_count: int,
        failed_count: int,
        max_retries_count: int,
        total_count: int,
    ) -> RecoveryResult:
        """
        Determine final state and update central state machine.

        Args:
            success_count: Number of successful recoveries
            failed_count: Number of failed recoveries
            max_retries_count: Number of clients that hit max retries
            total_count: Total number of clients attempted

        Returns:
            The final RecoveryResult

        """
        if self._state_machine is None:
            return RecoveryResult.SUCCESS if success_count == total_count else RecoveryResult.FAILED

        if success_count == total_count:
            # All recovered
            if self._state_machine.can_transition_to(target=CentralState.RUNNING):
                self._state_machine.transition_to(
                    target=CentralState.RUNNING,
                    reason="All clients recovered successfully",
                )
            return RecoveryResult.SUCCESS

        if max_retries_count > 0 and success_count == 0:
            # All failed with max retries
            if self._state_machine.can_transition_to(target=CentralState.FAILED):
                self._state_machine.transition_to(
                    target=CentralState.FAILED,
                    reason=f"Max retries reached for {max_retries_count} client(s) - manual intervention required",
                )
            _LOGGER.error(  # i18n-log: ignore
                "RECOVERY: %s: FAILED state entered - max retries reached. Will retry every %d seconds via heartbeat.",
                self._central_name,
                int(HEARTBEAT_RETRY_INTERVAL),
            )
            return RecoveryResult.MAX_RETRIES

        if success_count > 0:
            # Partial recovery
            if self._state_machine.can_transition_to(target=CentralState.DEGRADED):
                self._state_machine.transition_to(
                    target=CentralState.DEGRADED,
                    reason=f"Partial recovery: {success_count}/{total_count} clients recovered",
                )
            return RecoveryResult.PARTIAL

        # All failed but not max retries yet
        if self._state_machine.can_transition_to(target=CentralState.DEGRADED):
            self._state_machine.transition_to(
                target=CentralState.DEGRADED,
                reason=f"Recovery failed for {failed_count} client(s), will retry",
            )
        return RecoveryResult.FAILED

    async def _verify_data_load(
        self,
        *,
        interface_id: str,
        verify_func: Any,
    ) -> DataLoadStage:
        """
        Verify data load for a client through multiple stages.

        Args:
            interface_id: The interface ID being verified
            verify_func: Async function for verification

        Returns:
            The highest stage reached

        """
        try:
            # Call the verification function
            result = await verify_func()
        except Exception:
            _LOGGER.exception(  # i18n-log: ignore
                "RECOVERY: %s: Data load verification failed for %s",
                self._central_name,
                interface_id,
            )
            return DataLoadStage.BASIC
        else:
            return DataLoadStage.FULL if result else DataLoadStage.BASIC
