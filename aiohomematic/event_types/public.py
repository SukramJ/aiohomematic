# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Public event payload types published on the EventBus.

These dataclasses are defined separately from the EventBus dispatch machinery
(``aiohomematic.central.events.bus``) so the domain model and metrics layers
can consume them without importing ``aiohomematic.central``.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from aiohomematic.const import DataPointKey, FailureReason, ParamsetKey, RecoveryStage
from aiohomematic.event_types.base import Event

__all__ = [
    "DataPointStateChangedEvent",
    "DeviceRemovedEvent",
    "OptimisticRollbackEvent",
    "RecoveryCompletedEvent",
    "RecoveryFailedEvent",
    "RecoveryStageChangedEvent",
    "RpcParameterReceivedEvent",
    "SysvarStateChangedEvent",
]


@dataclass(frozen=True, slots=True)
class RpcParameterReceivedEvent(Event):
    """
    Raw parameter update event from backend (re-published from RPC callbacks).

    Key is DataPointKey(
                interface_id=self.interface_id,
                channel_address=self.channel_address,
                paramset_key=ParamsetKey.VALUES,
                parameter=self.parameter,
            )
    """

    interface_id: str
    channel_address: str
    parameter: str
    value: Any

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return DataPointKey(
            interface_id=self.interface_id,
            channel_address=self.channel_address,
            paramset_key=ParamsetKey.VALUES,
            parameter=self.parameter,
        )


@dataclass(frozen=True, slots=True)
class SysvarStateChangedEvent(Event):
    """
    System variable state has changed.

    Key is the state path.
    """

    state_path: str
    value: Any
    received_at: datetime

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return self.state_path


@dataclass(frozen=True, slots=True)
class DataPointStateChangedEvent(Event):
    """
    Data point value updated callback event.

    Key is unique_id.

    This event is fired when a data point's value changes and external
    consumers (like Home Assistant data points) need to be notified.
    Unlike DataPointValueReceivedEvent which handles internal backend updates,
    this event is for external integration points.

    The old_value and new_value fields allow consumers to track what changed
    without having to maintain their own previous state. These may be None
    if the values are unknown (e.g., during initial load or for non-value updates).
    """

    unique_id: str
    old_value: Any = None
    new_value: Any = None
    device_name: str | None = None
    """Human-readable device name."""

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return self.unique_id


@dataclass(frozen=True, slots=True)
class OptimisticRollbackEvent(Event):
    """
    Optimistic value was rolled back.

    Key is the DataPointKey.

    This event is fired when an optimistic value is rolled back to the previous
    confirmed value due to:
    - CCU timeout (no confirmation within optimistic_update_timeout)
    - Send error (exception during set_value)
    - Value mismatch (CCU confirmed different value than sent)

    Consumers (Home Assistant integration) can use this event to:
    - Create persistent notifications for users
    - Log warnings in system log
    - Update device diagnostics
    """

    dpk: DataPointKey
    """Data point key identifying the affected parameter."""

    reason: str
    """Reason for rollback (RollbackReason enum value)."""

    rolled_back_value: Any
    """Value that was rolled back (optimistic value that failed)."""

    restored_value: Any
    """Value that was restored (previous confirmed value)."""

    error: str | None = None
    """Error message (only set if reason is SEND_ERROR)."""

    age_seconds: float = 0.0
    """Age of optimistic value when rolled back (in seconds)."""

    device_name: str | None = None
    """Human-readable device name."""

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return self.dpk


@dataclass(frozen=True, slots=True)
class DeviceRemovedEvent(Event):
    """
    Device or data point has been removed from the system.

    Key is device_address (for device removal) or unique_id (for data point removal).

    When used for device removal (device_address is set):
    - Enables decoupled cache invalidation via EventBus subscription
    - Caches subscribe and react independently instead of direct calls

    When used for data point removal (only unique_id is set):
    - Signals that a data point entity should be cleaned up
    """

    unique_id: str
    """Unique identifier of the device or data point."""

    device_address: str | None = None
    """Address of the removed device (None for data point removal)."""

    interface_id: str | None = None
    """Interface ID the device belonged to (None for data point removal)."""

    channel_addresses: tuple[str, ...] = ()
    """Addresses of all channels that were part of this device."""

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return self.device_address or self.unique_id


@dataclass(frozen=True, slots=True)
class RecoveryStageChangedEvent(Event):
    """
    Recovery stage transition.

    Key is interface_id.

    Emitted when the ConnectionRecoveryCoordinator transitions between
    recovery stages. Enables fine-grained observability of the recovery process.
    """

    interface_id: str
    old_stage: RecoveryStage
    new_stage: RecoveryStage
    duration_in_old_stage_ms: float
    attempt_number: int

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return self.interface_id


@dataclass(frozen=True, slots=True)
class RecoveryCompletedEvent(Event):
    """
    Recovery completed successfully.

    Key is interface_id (or central_name for batch recovery).

    Emitted when recovery succeeds for an interface or all interfaces.
    """

    interface_id: str | None
    """Interface ID (None for batch recovery of multiple interfaces)."""

    central_name: str
    """Name of the central unit."""

    total_attempts: int
    total_duration_ms: float
    stages_completed: tuple[RecoveryStage, ...]
    interfaces_recovered: tuple[str, ...] | None = None
    """List of recovered interfaces (for batch recovery)."""

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return self.interface_id or self.central_name


@dataclass(frozen=True, slots=True)
class RecoveryFailedEvent(Event):
    """
    Recovery failed after max retries.

    Key is interface_id (or central_name for batch recovery).

    Emitted when recovery fails for an interface or all interfaces,
    indicating transition to FAILED state with heartbeat retry.
    """

    interface_id: str | None
    """Interface ID (None for batch failure of multiple interfaces)."""

    central_name: str
    """Name of the central unit."""

    total_attempts: int
    total_duration_ms: float
    last_stage_reached: RecoveryStage
    failure_reason: FailureReason
    requires_manual_intervention: bool
    failed_interfaces: tuple[str, ...] | None = None
    """List of failed interfaces (for batch recovery)."""

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return self.interface_id or self.central_name
