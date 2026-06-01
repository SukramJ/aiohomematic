# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Backend-agnostic event payload types.

This package holds the event dataclasses and enums that are published on the
EventBus. They depend only on ``aiohomematic.const`` (plus stdlib), so the
domain model (``aiohomematic.model``) and metrics layers can consume them
without importing ``aiohomematic.central`` or ``aiohomematic.client``.

The EventBus dispatch machinery itself lives in
``aiohomematic.central.events.bus``.

Public API of this package is defined by __all__.
"""

from aiohomematic.event_types.base import (
    CentralStateChangedEvent,
    CircuitBreakerStateChangedEvent,
    CircuitBreakerTrippedEvent,
    ClientStateChangedEvent,
    DataFetchCompletedEvent,
    DataFetchOperation,
    Event,
    EventPriority,
    HealthRecordedEvent,
)
from aiohomematic.event_types.integration import (
    DataPointsCreatedEvent,
    DeviceLifecycleEvent,
    DeviceLifecycleEventType,
    DeviceTriggerEvent,
    IntegrationIssue,
    SystemStatusChangedEvent,
)
from aiohomematic.event_types.internal import (
    CacheInvalidatedEvent,
    ConnectionHealthChangedEvent,
    ConnectionLostEvent,
    ConnectionStageChangedEvent,
    DataPointStatusReceivedEvent,
    DataPointValueReceivedEvent,
    DataRefreshCompletedEvent,
    DataRefreshTriggeredEvent,
    DeviceStateChangedEvent,
    FirmwareStateChangedEvent,
    HeartbeatTimerFiredEvent,
    LinkPeerChangedEvent,
    ProgramExecutedEvent,
    RecoveryAttemptedEvent,
    RequestCoalescedEvent,
)
from aiohomematic.event_types.public import (
    DataPointStateChangedEvent,
    DeviceRemovedEvent,
    OptimisticRollbackEvent,
    RecoveryCompletedEvent,
    RecoveryFailedEvent,
    RecoveryStageChangedEvent,
    RpcParameterReceivedEvent,
    SysvarStateChangedEvent,
)

__all__ = [
    # Base
    "CentralStateChangedEvent",
    "CircuitBreakerStateChangedEvent",
    "CircuitBreakerTrippedEvent",
    "ClientStateChangedEvent",
    "DataFetchCompletedEvent",
    "DataFetchOperation",
    "Event",
    "EventPriority",
    "HealthRecordedEvent",
    # Integration
    "DataPointsCreatedEvent",
    "DeviceLifecycleEvent",
    "DeviceLifecycleEventType",
    "DeviceTriggerEvent",
    "IntegrationIssue",
    "SystemStatusChangedEvent",
    # Internal
    "CacheInvalidatedEvent",
    "ConnectionHealthChangedEvent",
    "ConnectionLostEvent",
    "ConnectionStageChangedEvent",
    "DataPointStatusReceivedEvent",
    "DataPointValueReceivedEvent",
    "DataRefreshCompletedEvent",
    "DataRefreshTriggeredEvent",
    "DeviceStateChangedEvent",
    "FirmwareStateChangedEvent",
    "HeartbeatTimerFiredEvent",
    "LinkPeerChangedEvent",
    "ProgramExecutedEvent",
    "RecoveryAttemptedEvent",
    "RequestCoalescedEvent",
    # Public
    "DataPointStateChangedEvent",
    "DeviceRemovedEvent",
    "OptimisticRollbackEvent",
    "RecoveryCompletedEvent",
    "RecoveryFailedEvent",
    "RecoveryStageChangedEvent",
    "RpcParameterReceivedEvent",
    "SysvarStateChangedEvent",
]
