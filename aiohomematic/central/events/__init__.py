# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Events sub-package for the central event system.

This package contains the event bus infrastructure and event type definitions:

- EventBus: Core event bus for type-safe event subscription and publishing
- Public events: Stable API for external consumers (integrations, bridges)
- Internal events: Coordinator communication (import from ``events.internal``)

Public API of this module is defined by __all__.

Internal events are available via ``aiohomematic.central.events.internal``
and are re-exported here for backward compatibility, but they are **not**
part of the stable public API.
"""

from aiohomematic.central.events.bus import (
    DataPointStateChangedEvent,
    DeviceRemovedEvent,
    EventBatch,
    EventBus,
    HandlerStats,
    OptimisticRollbackEvent,
    RecoveryCompletedEvent,
    RecoveryFailedEvent,
    RecoveryStageChangedEvent,
    RpcParameterReceivedEvent,
    SubscriptionGroup,
    SysvarStateChangedEvent,
)
from aiohomematic.central.events.integration import (
    DataPointsCreatedEvent,
    DeviceLifecycleEvent,
    DeviceLifecycleEventType,
    DeviceTriggerEvent,
    IntegrationIssue,
    SystemStatusChangedEvent,
)
from aiohomematic.central.events.internal import (
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
from aiohomematic.central.events.types import (
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

# Only public events and EventBus infrastructure are part of the stable API.
# Internal events are re-exported for backward compatibility but external
# consumers should not depend on them.
__all__ = [
    # Data point state events
    "DataPointStateChangedEvent",
    "DeviceRemovedEvent",
    "OptimisticRollbackEvent",
    "SysvarStateChangedEvent",
    # EventBus core
    "Event",
    "EventBatch",
    "EventBus",
    "EventPriority",
    "HandlerStats",
    "SubscriptionGroup",
    # Integration events
    "DataPointsCreatedEvent",
    "DeviceLifecycleEvent",
    "DeviceLifecycleEventType",
    "DeviceTriggerEvent",
    "IntegrationIssue",
    "SystemStatusChangedEvent",
    # RPC callback events
    "RpcParameterReceivedEvent",
    # Recovery events
    "RecoveryCompletedEvent",
    "RecoveryFailedEvent",
    "RecoveryStageChangedEvent",
    # State machine events
    "CacheInvalidatedEvent",
    "CentralStateChangedEvent",
    "CircuitBreakerStateChangedEvent",
    "CircuitBreakerTrippedEvent",
    "ClientStateChangedEvent",
    "ConnectionHealthChangedEvent",
    "ConnectionLostEvent",
    "ConnectionStageChangedEvent",
    "DataFetchCompletedEvent",
    "DataFetchOperation",
    "DataPointStatusReceivedEvent",
    "DataPointValueReceivedEvent",
    "DataRefreshCompletedEvent",
    "DataRefreshTriggeredEvent",
    "DeviceStateChangedEvent",
    "FirmwareStateChangedEvent",
    "HealthRecordedEvent",
    "HeartbeatTimerFiredEvent",
    "LinkPeerChangedEvent",
    "ProgramExecutedEvent",
    "RecoveryAttemptedEvent",
    "RequestCoalescedEvent",
]
