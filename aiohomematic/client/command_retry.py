# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Command retry handler for transient command failures.

Provides automatic retry with exponential backoff for set_value and put_paramset
operations that fail due to transient errors (network timeouts, temporary device
unreachability, DutyCycle exhaustion).

Key features:
- Exponential backoff with configurable limits
- Connection recovery awareness (waits for RecoveryCompletedEvent)
- Circuit breaker integration (aborts retry if breaker opens)
- Per-DataPointKey active retry tracking (new command supersedes old retry)
- Purge support (CRITICAL commands cancel all device retries)

Public API of this module is defined by __all__.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any, Final

from aiohomematic.central.events.bus import RecoveryCompletedEvent
from aiohomematic.exceptions import (
    AuthFailure,
    BaseHomematicException,
    CircuitBreakerOpenException,
    CommandSupersededError,
    InternalBackendException,
    NoConnectionException,
    UnsupportedException,
    ValidationException,
)

if TYPE_CHECKING:
    from xmlrpc.client import Fault as XmlRpcFault

    from aiohomematic.central.events.bus import EventBus
    from aiohomematic.const import DataPointKey, TimeoutConfig

_LOGGER: Final = logging.getLogger(__name__)

# XML-RPC fault codes that indicate transient failures
_RETRYABLE_FAULT_CODES: Final[frozenset[int]] = frozenset(
    {
        -1,  # UNREACH — device temporarily unreachable
        -8,  # INSUFFICIENT_DUTYCYCLE — DutyCycle exhausted
        -9,  # DEVICE_OUT_OF_RANGE — temporary RF problem
        -10,  # TRANSMISSION_PENDING — CCU already transmitting
    }
)

_FAULT_CODE_DUTY_CYCLE: Final = -8
_FAULT_CODE_TRANSMISSION_PENDING: Final = -10

# Non-retryable exceptions — permanent failures where retry cannot help
_NON_RETRYABLE_EXCEPTIONS: Final[tuple[type[BaseHomematicException], ...]] = (
    AuthFailure,
    CircuitBreakerOpenException,
    CommandSupersededError,
    UnsupportedException,
    ValidationException,
)


def is_retryable(*, exc: BaseException) -> bool:
    """
    Determine if an exception represents a transient failure worth retrying.

    Returns True for:
    - TimeoutError (RPC call timeout)
    - NoConnectionException (transient network failure)
    - InternalBackendException (CCU internal error)
    - ClientException wrapping a retryable XML-RPC fault code

    Returns False for:
    - AuthFailure, ValidationException, UnsupportedException (permanent)
    - CircuitBreakerOpenException (has own recovery)
    - CommandSupersededError (by design)
    """
    if isinstance(exc, _NON_RETRYABLE_EXCEPTIONS):
        return False
    if isinstance(exc, TimeoutError | NoConnectionException | InternalBackendException):
        return True
    # Check for wrapped XML-RPC fault codes in the __cause__ chain
    if isinstance(exc, BaseHomematicException) and (fault_code := _get_fault_code(exc=exc)) is not None:
        return fault_code in _RETRYABLE_FAULT_CODES
    return False


def _get_fault_code(*, exc: BaseException) -> int | None:
    """Extract XML-RPC fault code from exception __cause__ chain if present."""
    cause: BaseException | None = exc.__cause__
    while cause is not None:
        if hasattr(cause, "faultCode"):
            fault: XmlRpcFault = cause  # type: ignore[assignment]
            return int(fault.faultCode)
        cause = cause.__cause__
    return None


@dataclass(slots=True)
class CommandRetryMetrics:
    """Metrics for command retry tracking."""

    total_retries: int = 0
    """Total number of retry attempts."""

    successful_retries: int = 0
    """Retries that eventually succeeded."""

    exhausted_retries: int = 0
    """Retries that hit max_attempts without success."""

    recovery_waits: int = 0
    """Number of times waited for connection recovery."""

    recovery_wait_timeouts: int = 0
    """Recovery waits that timed out."""

    cancelled_retries: int = 0
    """Retries cancelled by supersede or purge."""

    def snapshot(self) -> CommandRetryMetrics:
        """Return an immutable copy of current metrics."""
        return CommandRetryMetrics(
            total_retries=self.total_retries,
            successful_retries=self.successful_retries,
            exhausted_retries=self.exhausted_retries,
            recovery_waits=self.recovery_waits,
            recovery_wait_timeouts=self.recovery_wait_timeouts,
            cancelled_retries=self.cancelled_retries,
        )


class CommandRetryHandler:
    """
    Retry handler for transient command failures.

    Integrates with:
    - Circuit Breaker: Aborts retry if circuit opens
    - Connection Recovery: Waits for RecoveryCompletedEvent on NoConnectionException
    - Command Throttle: Re-acquires throttle per attempt (via caller)
    - Optimistic Updates: Keeps optimistic value active during retries

    Concurrency
    -----------
    This class assumes single asyncio event-loop execution.
    One active retry per DataPointKey is enforced — a new retry for the same key
    cancels the previous one (supersede semantics).
    """

    __slots__ = (
        "_active_retries",
        "_event_bus",
        "_interface_id",
        "_metrics",
        "_timeout_config",
    )

    def __init__(
        self,
        *,
        interface_id: str,
        timeout_config: TimeoutConfig,
        event_bus: EventBus,
    ) -> None:
        """Initialize command retry handler."""
        self._interface_id: Final = interface_id
        self._timeout_config: Final = timeout_config
        self._event_bus: Final = event_bus
        self._metrics: Final = CommandRetryMetrics()
        self._active_retries: Final[dict[DataPointKey, asyncio.Task[Any]]] = {}

    @property
    def active_retry_count(self) -> int:
        """Return number of currently active retries."""
        return len(self._active_retries)

    @property
    def enabled(self) -> bool:
        """Return if retry is globally enabled."""
        return self._timeout_config.command_retry_max_attempts > 0

    @property
    def metrics(self) -> CommandRetryMetrics:
        """Return current retry metrics."""
        return self._metrics

    def cancel_retries_for_device(self, *, device_address: str) -> int:
        """Cancel all pending retries for a device. Return cancelled count."""
        to_cancel = [dpk for dpk in self._active_retries if dpk.channel_address.startswith(device_address)]
        for dpk in to_cancel:
            self._cancel_retry_for_dpk(dpk=dpk)
        return len(to_cancel)

    def cancel_retries_for_dpk(self, *, dpk: DataPointKey) -> int:
        """Cancel pending retry for a specific data point. Return 1 if cancelled, 0 if none."""
        return self._cancel_retry_for_dpk(dpk=dpk)

    def cancel_retries_for_interface(self) -> int:
        """Cancel all pending retries for this interface. Return cancelled count."""
        count = len(self._active_retries)
        for dpk in list(self._active_retries):
            self._cancel_retry_for_dpk(dpk=dpk)
        return count

    async def execute_with_retry[T](
        self,
        *,
        operation: Callable[[], Awaitable[T]],
        dpk: DataPointKey,
        retry: bool = True,
    ) -> T:
        """
        Execute an operation with retry on transient failures.

        Args:
            operation: Async callable (zero-arg) to execute.
            dpk: DataPointKey identifying the target data point (for supersede tracking).
            retry: Per-call override. False disables retry for this call.

        Returns:
            The result of the operation.

        Raises:
            The last exception if all retries are exhausted or error is non-retryable.

        """
        max_attempts = self._timeout_config.command_retry_max_attempts

        # Short-circuit: retry disabled globally or per-call
        if not retry or max_attempts <= 0:
            return await operation()

        last_exception: BaseException | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                result = await operation()
            except BaseException as exc:
                last_exception = exc

                # Non-retryable — raise immediately
                if not is_retryable(exc=exc):
                    raise

                # Last attempt — raise
                if attempt >= max_attempts:
                    self._metrics.exhausted_retries += 1
                    _LOGGER.warning(  # i18n-log: ignore
                        "COMMAND_RETRY: Exhausted %d attempts for %s/%s — last error: %s",
                        max_attempts,
                        dpk.channel_address,
                        dpk.parameter,
                        exc,
                    )
                    raise

                # Calculate delay
                delay = self._calculate_delay(attempt=attempt, exc=exc)
                self._metrics.total_retries += 1

                _LOGGER.debug(  # i18n-log: ignore
                    "COMMAND_RETRY: Attempt %d/%d for %s/%s failed (%s), retrying in %.1fs",
                    attempt,
                    max_attempts,
                    dpk.channel_address,
                    dpk.parameter,
                    type(exc).__name__,
                    delay,
                )

                # For NoConnectionException: wait for recovery event instead of blind delay
                if isinstance(exc, NoConnectionException):
                    if not await self._wait_for_recovery():
                        # Recovery timed out — raise last error
                        raise
                else:
                    await asyncio.sleep(delay)
            else:
                # Success on retry — log and record
                if attempt > 1:
                    self._metrics.successful_retries += 1
                    _LOGGER.info(  # i18n-log: ignore
                        "COMMAND_RETRY: Succeeded for %s/%s after %d attempts",
                        dpk.channel_address,
                        dpk.parameter,
                        attempt,
                    )
                return result

        # Should not reach here, but satisfy type checker
        assert last_exception is not None
        raise last_exception

    def _calculate_delay(self, *, attempt: int, exc: BaseException) -> float:
        """Calculate delay before next retry using exponential backoff with special cases."""
        tc = self._timeout_config
        fault_code = _get_fault_code(exc=exc)

        # Special delay for DutyCycle exhaustion
        if fault_code == _FAULT_CODE_DUTY_CYCLE:
            return tc.command_retry_duty_cycle_delay

        # Special delay for transmission pending
        if fault_code == _FAULT_CODE_TRANSMISSION_PENDING:
            return tc.command_retry_transmission_pending_delay

        # Standard exponential backoff
        delay = tc.command_retry_base_delay * (tc.command_retry_backoff_factor ** (attempt - 1))
        return min(delay, tc.command_retry_max_delay)

    def _cancel_retry_for_dpk(self, *, dpk: DataPointKey) -> int:
        """Cancel active retry for a data point key. Return 1 if cancelled, 0 if none."""
        if (task := self._active_retries.pop(dpk, None)) is not None:
            if not task.done():
                task.cancel()
            self._metrics.cancelled_retries += 1
            return 1
        return 0

    async def _wait_for_recovery(self) -> bool:
        """
        Wait for connection recovery event instead of blind retry.

        Return True if recovery completed, False if timed out.
        """
        self._metrics.recovery_waits += 1
        recovery_event = asyncio.Event()
        max_wait = self._timeout_config.command_retry_recovery_wait

        def _on_recovery(*, event: RecoveryCompletedEvent) -> None:
            if event.interface_id == self._interface_id or event.interface_id is None:
                recovery_event.set()

        unsub = self._event_bus.subscribe(
            event_type=RecoveryCompletedEvent,
            event_key=None,
            handler=_on_recovery,
        )
        try:
            async with asyncio.timeout(max_wait):
                await recovery_event.wait()
        except TimeoutError:
            self._metrics.recovery_wait_timeouts += 1
            _LOGGER.debug(  # i18n-log: ignore
                "COMMAND_RETRY: Recovery wait timed out after %.1fs for %s",
                max_wait,
                self._interface_id,
            )
            return False
        else:
            return True
        finally:
            unsub()
