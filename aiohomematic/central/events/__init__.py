# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Events sub-package for the central event system.

This package contains the event bus infrastructure and event type definitions:

- EventBus: Core event bus for type-safe event subscription and publishing
- Event types: DataPointValueReceivedEvent, DeviceStateChangedEvent, etc.
- Integration events: SystemStatusChangedEvent for Home Assistant integration

Public API of this module is defined by __all__.
"""

from __future__ import annotations

from aiohomematic.central.events.bus import (
    CacheInvalidatedEvent,
    CentralStateChangedEvent,
    CircuitBreakerStateChangedEvent,
    CircuitBreakerTrippedEvent,
    ClientStateChangedEvent,
    ConnectionHealthChangedEvent,
    ConnectionLostEvent,
    ConnectionStageChangedEvent,
    DataPointStateChangedEvent,
    DataPointStatusReceivedEvent,
    DataPointValueReceivedEvent,
    DataRefreshCompletedEvent,
    DataRefreshTriggeredEvent,
    DeviceRemovedEvent,
    DeviceStateChangedEvent,
    Event,
    EventBatch,
    EventBus,
    EventPriority,
    FirmwareStateChangedEvent,
    HandlerStats,
    HealthRecordedEvent,
    HeartbeatTimerFiredEvent,
    LinkPeerChangedEvent,
    ProgramExecutedEvent,
    RecoveryAttemptedEvent,
    RecoveryCompletedEvent,
    RecoveryFailedEvent,
    RecoveryStageChangedEvent,
    RequestCoalescedEvent,
    RpcParameterReceivedEvent,
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

__all__ = [
    # Event types
    "CacheInvalidatedEvent",
    "CentralStateChangedEvent",
    "CircuitBreakerStateChangedEvent",
    "CircuitBreakerTrippedEvent",
    "ClientStateChangedEvent",
    "ConnectionHealthChangedEvent",
    "ConnectionLostEvent",
    "ConnectionStageChangedEvent",
    "DataPointStateChangedEvent",
    "DataPointStatusReceivedEvent",
    "DataPointValueReceivedEvent",
    "DataRefreshCompletedEvent",
    "DataRefreshTriggeredEvent",
    "DeviceRemovedEvent",
    "DeviceStateChangedEvent",
    "FirmwareStateChangedEvent",
    "HealthRecordedEvent",
    "HeartbeatTimerFiredEvent",
    "LinkPeerChangedEvent",
    "ProgramExecutedEvent",
    "RecoveryAttemptedEvent",
    "RecoveryCompletedEvent",
    "RecoveryFailedEvent",
    "RecoveryStageChangedEvent",
    "RequestCoalescedEvent",
    "RpcParameterReceivedEvent",
    "SysvarStateChangedEvent",
    # EventBus core
    "Event",
    "EventBatch",
    "EventBus",
    "EventPriority",
    "HandlerStats",
    # Integration events
    "DataPointsCreatedEvent",
    "DeviceLifecycleEvent",
    "DeviceLifecycleEventType",
    "DeviceTriggerEvent",
    "IntegrationIssue",
    "SystemStatusChangedEvent",
]
