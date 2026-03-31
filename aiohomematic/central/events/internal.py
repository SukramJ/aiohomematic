# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Internal event types for coordinator communication within aiohomematic.

These events are **not part of the public API**. External consumers
(Home Assistant integration, MQTT bridge, Matter bridge) must not
subscribe to or import these events. Use the public events from
``aiohomematic.central.events`` instead.

Internal events are used for:

- Backend data point value routing (DataPointValueReceivedEvent)
- Connection health and recovery coordination
- Cache invalidation signaling
- Circuit breaker state tracking
- Data refresh lifecycle
- Request coalescing metrics

Public API of this module is defined by __all__.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from aiohomematic.central.events.types import (
    CircuitBreakerStateChangedEvent,
    CircuitBreakerTrippedEvent,
    DataFetchCompletedEvent,
    DataFetchOperation,
    Event,
    HealthRecordedEvent,
)
from aiohomematic.const import (
    CacheInvalidationReason,
    CacheType,
    ConnectionStage,
    DataPointKey,
    DataRefreshType,
    FailureReason,
    ProgramTrigger,
    RecoveryStage,
)

__all__ = [
    # Re-exported from types.py (canonical location for internal use)
    "CircuitBreakerStateChangedEvent",
    "CircuitBreakerTrippedEvent",
    "DataFetchCompletedEvent",
    "DataFetchOperation",
    "HealthRecordedEvent",
    # Data point value routing
    "DataPointStatusReceivedEvent",
    "DataPointValueReceivedEvent",
    # Device/channel state
    "DeviceStateChangedEvent",
    "FirmwareStateChangedEvent",
    "LinkPeerChangedEvent",
    # Connection health
    "ConnectionHealthChangedEvent",
    "ConnectionLostEvent",
    "ConnectionStageChangedEvent",
    # Cache
    "CacheInvalidatedEvent",
    # Data refresh
    "DataRefreshCompletedEvent",
    "DataRefreshTriggeredEvent",
    # Program execution
    "ProgramExecutedEvent",
    # Request coalescing
    "RequestCoalescedEvent",
    # Recovery (internal-only)
    "HeartbeatTimerFiredEvent",
    "RecoveryAttemptedEvent",
]


# =============================================================================
# Data Point Value Routing Events
# =============================================================================


@dataclass(frozen=True, slots=True)
class DataPointValueReceivedEvent(Event):
    """
    Fired when a data point value is updated from the backend.

    Key is the DataPointKey.

    The dpk (DataPointKey) contains:
    - interface_id: Interface identifier (e.g., "BidCos-RF")
    - channel_address: Full channel address (e.g., "VCU0000001:1")
    - paramset_key: Paramset type (e.g., ParamsetKey.VALUES)
    - parameter: Parameter name (e.g., "STATE")
    """

    dpk: DataPointKey
    value: Any
    received_at: datetime

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return self.dpk


@dataclass(frozen=True, slots=True)
class DataPointStatusReceivedEvent(Event):
    """
    Fired when a STATUS parameter value is updated from the backend.

    Key is the DataPointKey of the MAIN parameter (not the STATUS parameter).

    This event is routed to the main parameter's data point to update
    its status attribute. For example, a LEVEL_STATUS event is routed
    to the LEVEL data point.
    """

    dpk: DataPointKey
    status_value: int | str
    received_at: datetime

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return self.dpk


# =============================================================================
# Device/Channel State Events
# =============================================================================


@dataclass(frozen=True, slots=True)
class DeviceStateChangedEvent(Event):
    """
    Device state has changed.

    Key is device_address.
    """

    device_address: str

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return self.device_address


@dataclass(frozen=True, slots=True)
class FirmwareStateChangedEvent(Event):
    """
    Device firmware state has changed.

    Key is device_address.
    """

    device_address: str

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return self.device_address


@dataclass(frozen=True, slots=True)
class LinkPeerChangedEvent(Event):
    """
    Channel link peer addresses have changed.

    Key is channel_address.
    """

    channel_address: str

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return self.channel_address


# =============================================================================
# Connection Health Events
# =============================================================================


@dataclass(frozen=True, slots=True)
class ConnectionStageChangedEvent(Event):
    """
    Connection reconnection stage progression.

    Key is interface_id.

    Emitted during staged reconnection when connection is lost and recovered.
    Tracks progression through TCP check, RPC check, warmup, and establishment.
    """

    interface_id: str
    stage: ConnectionStage
    previous_stage: ConnectionStage
    duration_in_previous_stage_ms: float

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return self.interface_id

    @property
    def stage_name(self) -> str:
        """Return human-readable stage name."""
        return self.stage.display_name


@dataclass(frozen=True, slots=True)
class ConnectionHealthChangedEvent(Event):
    """
    Connection health status update.

    Key is interface_id.

    Emitted when connection health status changes for an interface.
    """

    interface_id: str
    is_healthy: bool
    failure_reason: FailureReason | None
    consecutive_failures: int
    last_successful_contact: datetime | None

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return self.interface_id


@dataclass(frozen=True, slots=True)
class ConnectionLostEvent(Event):
    """
    Connection loss detected for an interface.

    Key is interface_id.

    Emitted when the BackgroundScheduler detects a connection loss,
    triggering the ConnectionRecoveryCoordinator to start recovery.
    """

    interface_id: str
    reason: str
    detected_at: datetime

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return self.interface_id


# =============================================================================
# Cache Events
# =============================================================================


@dataclass(frozen=True, slots=True)
class CacheInvalidatedEvent(Event):
    """
    Cache invalidation notification.

    Key is scope (device_address, interface_id, or None for full cache).

    Emitted when cache entries are invalidated or cleared.
    """

    cache_type: CacheType
    reason: CacheInvalidationReason
    scope: str | None
    entries_affected: int

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return self.scope


# =============================================================================
# Data Refresh Events
# =============================================================================


@dataclass(frozen=True, slots=True)
class DataRefreshTriggeredEvent(Event):
    """
    Data refresh operation triggered.

    Key is interface_id (or None for hub-level refreshes).

    Emitted when a data refresh operation starts.
    """

    refresh_type: DataRefreshType
    interface_id: str | None
    scheduled: bool

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return self.interface_id


@dataclass(frozen=True, slots=True)
class DataRefreshCompletedEvent(Event):
    """
    Data refresh operation completed.

    Key is interface_id (or None for hub-level refreshes).

    Emitted when a data refresh operation completes (success or failure).
    """

    refresh_type: DataRefreshType
    interface_id: str | None
    success: bool
    duration_ms: float
    items_refreshed: int
    error_message: str | None

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return self.interface_id


# =============================================================================
# Program Execution Events
# =============================================================================


@dataclass(frozen=True, slots=True)
class ProgramExecutedEvent(Event):
    """
    Backend program was executed.

    Key is program_id.

    Emitted when a Homematic program is executed.
    """

    program_id: str
    program_name: str
    triggered_by: ProgramTrigger
    success: bool

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return self.program_id


# =============================================================================
# Request Coalescer Events
# =============================================================================


@dataclass(frozen=True, slots=True)
class RequestCoalescedEvent(Event):
    """
    Multiple requests were coalesced into one.

    Key is interface_id.

    Emitted when duplicate requests are merged to reduce backend load.
    """

    request_key: str
    coalesced_count: int
    interface_id: str

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return self.interface_id


# =============================================================================
# Recovery Events (internal-only)
# =============================================================================


@dataclass(frozen=True, slots=True)
class RecoveryAttemptedEvent(Event):
    """
    Recovery attempt completed.

    Key is interface_id.

    Emitted after each recovery attempt, regardless of success or failure.
    """

    interface_id: str
    attempt_number: int
    max_attempts: int
    stage_reached: RecoveryStage
    success: bool
    error_message: str | None

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return self.interface_id


@dataclass(frozen=True, slots=True)
class HeartbeatTimerFiredEvent(Event):
    """
    Heartbeat timer fired in FAILED state.

    Key is central_name.

    Emitted by the heartbeat timer when the system is in FAILED state,
    triggering a retry attempt for failed interfaces.
    """

    central_name: str
    interface_ids: tuple[str, ...]

    @property
    def key(self) -> Any:
        """Key identifier for this event."""
        return self.central_name
