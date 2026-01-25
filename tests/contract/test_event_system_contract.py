# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract tests for the event system.

STABILITY GUARANTEE
-------------------
These tests define the stable API contract for the event system.
Any change that breaks these tests requires a MAJOR version bump.

The contract ensures that:
1. All event types have required fields
2. Event types are immutable (frozen=True)
3. Event keys are correctly implemented
4. Integration events aggregate correctly
5. Event types can be instantiated with expected parameters

See ADR-0018 for architectural context.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from datetime import datetime

import pytest

from aiohomematic.central.events import (
    CentralStateChangedEvent,
    CircuitBreakerStateChangedEvent,
    CircuitBreakerTrippedEvent,
    ClientStateChangedEvent,
    DataFetchCompletedEvent,
    DataFetchOperation,
    DataPointsCreatedEvent,
    DeviceLifecycleEvent,
    DeviceLifecycleEventType,
    DeviceTriggerEvent,
    Event,
    EventPriority,
    HealthRecordedEvent,
    IntegrationIssue,
    SystemStatusChangedEvent,
)
from aiohomematic.const import (
    CentralState,
    CircuitState,
    ClientState,
    DeviceTriggerEventType,
    FailureReason,
    IntegrationIssueSeverity,
    IntegrationIssueType,
)

# =============================================================================
# Contract: Event Base Class
# =============================================================================


class TestEventBaseClassContract:
    """Contract: Event base class must have required structure."""

    def test_event_has_key_property(self) -> None:
        """Contract: Event must have abstract key property."""
        assert hasattr(Event, "key")

    def test_event_has_timestamp_field(self) -> None:
        """Contract: Event must have timestamp field."""
        field_names = [f.name for f in fields(Event)]
        assert "timestamp" in field_names

    def test_event_is_abstract(self) -> None:
        """Contract: Event base class cannot be instantiated directly."""
        with pytest.raises(TypeError):
            Event(timestamp=datetime.now())  # type: ignore[abstract]


# =============================================================================
# Contract: EventPriority Enum
# =============================================================================


class TestEventPriorityEnumContract:
    """Contract: EventPriority enum must have expected values."""

    def test_event_priority_has_critical(self) -> None:
        """Contract: EventPriority.CRITICAL must exist with value 200."""
        assert hasattr(EventPriority, "CRITICAL")
        assert EventPriority.CRITICAL.value == 200

    def test_event_priority_has_high(self) -> None:
        """Contract: EventPriority.HIGH must exist with value 100."""
        assert hasattr(EventPriority, "HIGH")
        assert EventPriority.HIGH.value == 100

    def test_event_priority_has_low(self) -> None:
        """Contract: EventPriority.LOW must exist with value 0."""
        assert hasattr(EventPriority, "LOW")
        assert EventPriority.LOW.value == 0

    def test_event_priority_has_normal(self) -> None:
        """Contract: EventPriority.NORMAL must exist with value 50."""
        assert hasattr(EventPriority, "NORMAL")
        assert EventPriority.NORMAL.value == 50

    def test_event_priority_ordering(self) -> None:
        """Contract: Priority ordering is LOW < NORMAL < HIGH < CRITICAL."""
        assert EventPriority.LOW < EventPriority.NORMAL
        assert EventPriority.NORMAL < EventPriority.HIGH
        assert EventPriority.HIGH < EventPriority.CRITICAL


# =============================================================================
# Contract: ClientStateChangedEvent
# =============================================================================


class TestClientStateChangedEventContract:
    """Contract: ClientStateChangedEvent must have correct structure."""

    def test_event_can_be_created_with_states(self) -> None:
        """Contract: Event accepts all ClientState values."""
        for old_state in ClientState:
            for new_state in ClientState:
                event = ClientStateChangedEvent(
                    timestamp=datetime.now(),
                    interface_id="test",
                    old_state=old_state,
                    new_state=new_state,
                    trigger=None,
                )
                assert event.old_state == old_state
                assert event.new_state == new_state

    def test_event_has_required_fields(self) -> None:
        """Contract: ClientStateChangedEvent has all required fields."""
        field_names = [f.name for f in fields(ClientStateChangedEvent)]
        assert "timestamp" in field_names
        assert "interface_id" in field_names
        assert "old_state" in field_names
        assert "new_state" in field_names
        assert "trigger" in field_names

    def test_event_is_frozen(self) -> None:
        """Contract: ClientStateChangedEvent is immutable."""
        event = ClientStateChangedEvent(
            timestamp=datetime.now(),
            interface_id="test-interface",
            old_state=ClientState.CREATED,
            new_state=ClientState.INITIALIZING,
            trigger="test",
        )
        with pytest.raises(FrozenInstanceError):
            event.interface_id = "new-value"  # type: ignore[misc]

    def test_event_key_is_interface_id(self) -> None:
        """Contract: key property returns interface_id."""
        event = ClientStateChangedEvent(
            timestamp=datetime.now(),
            interface_id="test-interface",
            old_state=ClientState.CREATED,
            new_state=ClientState.INITIALIZING,
            trigger=None,
        )
        assert event.key == "test-interface"


# =============================================================================
# Contract: CentralStateChangedEvent
# =============================================================================


class TestCentralStateChangedEventContract:
    """Contract: CentralStateChangedEvent must have correct structure."""

    def test_event_can_be_created_with_states(self) -> None:
        """Contract: Event accepts all CentralState values."""
        for old_state in CentralState:
            for new_state in CentralState:
                event = CentralStateChangedEvent(
                    timestamp=datetime.now(),
                    central_name="test",
                    old_state=old_state,
                    new_state=new_state,
                    trigger=None,
                )
                assert event.old_state == old_state
                assert event.new_state == new_state

    def test_event_has_required_fields(self) -> None:
        """Contract: CentralStateChangedEvent has all required fields."""
        field_names = [f.name for f in fields(CentralStateChangedEvent)]
        assert "timestamp" in field_names
        assert "central_name" in field_names
        assert "old_state" in field_names
        assert "new_state" in field_names
        assert "trigger" in field_names

    def test_event_is_frozen(self) -> None:
        """Contract: CentralStateChangedEvent is immutable."""
        event = CentralStateChangedEvent(
            timestamp=datetime.now(),
            central_name="test-central",
            old_state=CentralState.STARTING,
            new_state=CentralState.INITIALIZING,
            trigger="test",
        )
        with pytest.raises(FrozenInstanceError):
            event.central_name = "new-value"  # type: ignore[misc]

    def test_event_key_is_central_name(self) -> None:
        """Contract: key property returns central_name."""
        event = CentralStateChangedEvent(
            timestamp=datetime.now(),
            central_name="my-central",
            old_state=CentralState.STARTING,
            new_state=CentralState.INITIALIZING,
            trigger=None,
        )
        assert event.key == "my-central"


# =============================================================================
# Contract: CircuitBreakerStateChangedEvent
# =============================================================================


class TestCircuitBreakerStateChangedEventContract:
    """Contract: CircuitBreakerStateChangedEvent must have correct structure."""

    def test_event_has_required_fields(self) -> None:
        """Contract: CircuitBreakerStateChangedEvent has all required fields."""
        field_names = [f.name for f in fields(CircuitBreakerStateChangedEvent)]
        assert "timestamp" in field_names
        assert "interface_id" in field_names
        assert "old_state" in field_names
        assert "new_state" in field_names
        assert "failure_count" in field_names
        assert "success_count" in field_names
        assert "last_failure_time" in field_names

    def test_event_is_frozen(self) -> None:
        """Contract: CircuitBreakerStateChangedEvent is immutable."""
        event = CircuitBreakerStateChangedEvent(
            timestamp=datetime.now(),
            interface_id="test-interface",
            old_state=CircuitState.CLOSED,
            new_state=CircuitState.OPEN,
            failure_count=5,
            success_count=0,
            last_failure_time=datetime.now(),
        )
        with pytest.raises(FrozenInstanceError):
            event.failure_count = 10  # type: ignore[misc]

    def test_event_key_is_interface_id(self) -> None:
        """Contract: key property returns interface_id."""
        event = CircuitBreakerStateChangedEvent(
            timestamp=datetime.now(),
            interface_id="test-interface",
            old_state=CircuitState.CLOSED,
            new_state=CircuitState.OPEN,
            failure_count=5,
            success_count=0,
            last_failure_time=None,
        )
        assert event.key == "test-interface"


# =============================================================================
# Contract: CircuitBreakerTrippedEvent
# =============================================================================


class TestCircuitBreakerTrippedEventContract:
    """Contract: CircuitBreakerTrippedEvent must have correct structure."""

    def test_event_has_required_fields(self) -> None:
        """Contract: CircuitBreakerTrippedEvent has all required fields."""
        field_names = [f.name for f in fields(CircuitBreakerTrippedEvent)]
        assert "timestamp" in field_names
        assert "interface_id" in field_names
        assert "failure_count" in field_names
        assert "last_failure_reason" in field_names
        assert "cooldown_seconds" in field_names

    def test_event_is_frozen(self) -> None:
        """Contract: CircuitBreakerTrippedEvent is immutable."""
        event = CircuitBreakerTrippedEvent(
            timestamp=datetime.now(),
            interface_id="test-interface",
            failure_count=5,
            last_failure_reason="Connection refused",
            cooldown_seconds=30.0,
        )
        with pytest.raises(FrozenInstanceError):
            event.cooldown_seconds = 60.0  # type: ignore[misc]

    def test_event_key_is_interface_id(self) -> None:
        """Contract: key property returns interface_id."""
        event = CircuitBreakerTrippedEvent(
            timestamp=datetime.now(),
            interface_id="test-interface",
            failure_count=5,
            last_failure_reason=None,
            cooldown_seconds=30.0,
        )
        assert event.key == "test-interface"


# =============================================================================
# Contract: DataFetchCompletedEvent
# =============================================================================


class TestDataFetchCompletedEventContract:
    """Contract: DataFetchCompletedEvent must have correct structure."""

    def test_data_fetch_operation_has_fetch_device_descriptions(self) -> None:
        """Contract: DataFetchOperation.FETCH_DEVICE_DESCRIPTIONS exists."""
        assert hasattr(DataFetchOperation, "FETCH_DEVICE_DESCRIPTIONS")
        assert DataFetchOperation.FETCH_DEVICE_DESCRIPTIONS.value == "fetch_device_descriptions"

    def test_data_fetch_operation_has_fetch_paramset_descriptions(self) -> None:
        """Contract: DataFetchOperation.FETCH_PARAMSET_DESCRIPTIONS exists."""
        assert hasattr(DataFetchOperation, "FETCH_PARAMSET_DESCRIPTIONS")
        assert DataFetchOperation.FETCH_PARAMSET_DESCRIPTIONS.value == "fetch_paramset_descriptions"

    def test_event_has_required_fields(self) -> None:
        """Contract: DataFetchCompletedEvent has all required fields."""
        field_names = [f.name for f in fields(DataFetchCompletedEvent)]
        assert "timestamp" in field_names
        assert "interface_id" in field_names
        assert "operation" in field_names


# =============================================================================
# Contract: HealthRecordedEvent
# =============================================================================


class TestHealthRecordedEventContract:
    """Contract: HealthRecordedEvent must have correct structure."""

    def test_event_can_record_failure(self) -> None:
        """Contract: Event can record failed health check."""
        event = HealthRecordedEvent(
            timestamp=datetime.now(),
            interface_id="test-interface",
            success=False,
        )
        assert event.success is False

    def test_event_can_record_success(self) -> None:
        """Contract: Event can record successful health check."""
        event = HealthRecordedEvent(
            timestamp=datetime.now(),
            interface_id="test-interface",
            success=True,
        )
        assert event.success is True

    def test_event_has_required_fields(self) -> None:
        """Contract: HealthRecordedEvent has all required fields."""
        field_names = [f.name for f in fields(HealthRecordedEvent)]
        assert "timestamp" in field_names
        assert "interface_id" in field_names
        assert "success" in field_names


# =============================================================================
# Contract: SystemStatusChangedEvent (Integration)
# =============================================================================


class TestSystemStatusChangedEventContract:
    """Contract: SystemStatusChangedEvent must have correct structure."""

    def test_event_accepts_degraded_interfaces(self) -> None:
        """Contract: Event accepts degraded_interfaces mapping."""
        degraded = {
            "BidCos-RF": FailureReason.NETWORK,
            "HmIP-RF": FailureReason.TIMEOUT,
        }
        event = SystemStatusChangedEvent(
            timestamp=datetime.now(),
            central_state=CentralState.DEGRADED,
            degraded_interfaces=degraded,
        )
        assert event.degraded_interfaces == degraded

    def test_event_accepts_failure_reason(self) -> None:
        """Contract: Event accepts all FailureReason values."""
        for reason in FailureReason:
            event = SystemStatusChangedEvent(
                timestamp=datetime.now(),
                central_state=CentralState.FAILED,
                failure_reason=reason,
            )
            assert event.failure_reason == reason

    def test_event_has_central_state_field(self) -> None:
        """Contract: SystemStatusChangedEvent has central_state field."""
        field_names = [f.name for f in fields(SystemStatusChangedEvent)]
        assert "central_state" in field_names

    def test_event_has_degraded_interfaces_field(self) -> None:
        """Contract: SystemStatusChangedEvent has degraded_interfaces field."""
        field_names = [f.name for f in fields(SystemStatusChangedEvent)]
        assert "degraded_interfaces" in field_names

    def test_event_has_failure_fields(self) -> None:
        """Contract: SystemStatusChangedEvent has failure tracking fields."""
        field_names = [f.name for f in fields(SystemStatusChangedEvent)]
        assert "failure_reason" in field_names
        assert "failure_interface_id" in field_names

    def test_event_has_infrastructure_fields(self) -> None:
        """Contract: SystemStatusChangedEvent has infrastructure fields."""
        field_names = [f.name for f in fields(SystemStatusChangedEvent)]
        assert "connection_state" in field_names
        assert "client_state" in field_names
        assert "callback_state" in field_names

    def test_event_has_issues_field(self) -> None:
        """Contract: SystemStatusChangedEvent has issues field."""
        field_names = [f.name for f in fields(SystemStatusChangedEvent)]
        assert "issues" in field_names

    def test_event_key_is_none(self) -> None:
        """Contract: key property returns None (global event)."""
        event = SystemStatusChangedEvent(
            timestamp=datetime.now(),
            central_state=CentralState.RUNNING,
        )
        assert event.key is None


# =============================================================================
# Contract: DeviceLifecycleEvent (Integration)
# =============================================================================


class TestDeviceLifecycleEventContract:
    """Contract: DeviceLifecycleEvent must have correct structure."""

    def test_event_created_with_device_addresses(self) -> None:
        """Contract: Event accepts device_addresses tuple."""
        event = DeviceLifecycleEvent(
            timestamp=datetime.now(),
            event_type=DeviceLifecycleEventType.CREATED,
            device_addresses=("DEV1", "DEV2", "DEV3"),
            includes_virtual_remotes=True,
        )
        assert len(event.device_addresses) == 3
        assert event.includes_virtual_remotes is True

    def test_event_has_required_fields(self) -> None:
        """Contract: DeviceLifecycleEvent has all required fields."""
        field_names = [f.name for f in fields(DeviceLifecycleEvent)]
        assert "timestamp" in field_names
        assert "event_type" in field_names
        assert "device_addresses" in field_names
        assert "availability_changes" in field_names
        assert "includes_virtual_remotes" in field_names
        assert "interface_id" in field_names

    def test_event_key_is_none(self) -> None:
        """Contract: key property returns None (global event)."""
        event = DeviceLifecycleEvent(
            timestamp=datetime.now(),
            event_type=DeviceLifecycleEventType.CREATED,
            device_addresses=("ABC123",),
        )
        assert event.key is None

    def test_lifecycle_event_types_exist(self) -> None:
        """Contract: All DeviceLifecycleEventType values exist."""
        assert hasattr(DeviceLifecycleEventType, "CREATED")
        assert hasattr(DeviceLifecycleEventType, "DELAYED")
        assert hasattr(DeviceLifecycleEventType, "UPDATED")
        assert hasattr(DeviceLifecycleEventType, "REMOVED")
        assert hasattr(DeviceLifecycleEventType, "AVAILABILITY_CHANGED")


# =============================================================================
# Contract: DataPointsCreatedEvent (Integration)
# =============================================================================


class TestDataPointsCreatedEventContract:
    """Contract: DataPointsCreatedEvent must have correct structure."""

    def test_event_has_new_data_points_field(self) -> None:
        """Contract: DataPointsCreatedEvent has new_data_points field."""
        field_names = [f.name for f in fields(DataPointsCreatedEvent)]
        assert "new_data_points" in field_names

    def test_event_key_is_none(self) -> None:
        """Contract: key property returns None (global event)."""
        event = DataPointsCreatedEvent(
            timestamp=datetime.now(),
            new_data_points={},
        )
        assert event.key is None


# =============================================================================
# Contract: DeviceTriggerEvent (Integration)
# =============================================================================


class TestDeviceTriggerEventContract:
    """Contract: DeviceTriggerEvent must have correct structure."""

    def test_event_has_required_fields(self) -> None:
        """Contract: DeviceTriggerEvent has all required fields."""
        field_names = [f.name for f in fields(DeviceTriggerEvent)]
        assert "timestamp" in field_names
        assert "trigger_type" in field_names
        assert "model" in field_names
        assert "interface_id" in field_names
        assert "device_address" in field_names
        assert "channel_no" in field_names
        assert "parameter" in field_names
        assert "value" in field_names

    def test_event_is_frozen(self) -> None:
        """Contract: DeviceTriggerEvent is immutable."""
        event = DeviceTriggerEvent(
            timestamp=datetime.now(),
            trigger_type=DeviceTriggerEventType.KEYPRESS,
            model="HmIP-BSM",
            interface_id="test-interface",
            device_address="ABC123",
            channel_no=1,
            parameter="PRESS_SHORT",
            value=True,
        )
        with pytest.raises(FrozenInstanceError):
            event.parameter = "PRESS_LONG"  # type: ignore[misc]

    def test_event_key_is_none(self) -> None:
        """Contract: key property returns None (global event)."""
        event = DeviceTriggerEvent(
            timestamp=datetime.now(),
            trigger_type=DeviceTriggerEventType.KEYPRESS,
            model="HmIP-BSM",
            interface_id="test-interface",
            device_address="ABC123",
            channel_no=1,
            parameter="PRESS_SHORT",
            value=True,
        )
        assert event.key is None


# =============================================================================
# Contract: IntegrationIssue
# =============================================================================


class TestIntegrationIssueContract:
    """Contract: IntegrationIssue must have correct structure."""

    def test_issue_has_optional_fields(self) -> None:
        """Contract: IntegrationIssue has optional fields."""
        field_names = [f.name for f in fields(IntegrationIssue)]
        assert "mismatch_type" in field_names
        assert "mismatch_count" in field_names
        assert "device_addresses" in field_names

    def test_issue_has_required_fields(self) -> None:
        """Contract: IntegrationIssue has all required fields."""
        field_names = [f.name for f in fields(IntegrationIssue)]
        assert "issue_type" in field_names
        assert "severity" in field_names
        assert "interface_id" in field_names

    def test_issue_id_property(self) -> None:
        """Contract: issue_id combines issue_type and interface_id."""
        issue = IntegrationIssue(
            issue_type=IntegrationIssueType.PING_PONG_MISMATCH,
            severity=IntegrationIssueSeverity.WARNING,
            interface_id="ccu-HmIP-RF",
        )
        assert issue.issue_id == "ping_pong_mismatch_ccu-HmIP-RF"

    def test_translation_key_property(self) -> None:
        """Contract: translation_key returns issue_type value."""
        issue = IntegrationIssue(
            issue_type=IntegrationIssueType.FETCH_DATA_FAILED,
            severity=IntegrationIssueSeverity.WARNING,
            interface_id="test",
        )
        assert issue.translation_key == "fetch_data_failed"

    def test_translation_placeholders_property(self) -> None:
        """Contract: translation_placeholders returns dict with interface_id."""
        issue = IntegrationIssue(
            issue_type=IntegrationIssueType.INCOMPLETE_DEVICE_DATA,
            severity=IntegrationIssueSeverity.ERROR,
            interface_id="ccu-CUxD",
            device_addresses=("DEV1", "DEV2"),
        )
        placeholders = issue.translation_placeholders
        assert placeholders["interface_id"] == "ccu-CUxD"
        assert placeholders["device_count"] == "2"
        assert "DEV1" in placeholders["device_addresses"]


# =============================================================================
# Contract: CircuitState Enum
# =============================================================================


class TestCircuitStateEnumContract:
    """Contract: CircuitState enum values must remain stable."""

    def test_circuit_state_has_closed(self) -> None:
        """Contract: CircuitState.CLOSED must exist."""
        assert hasattr(CircuitState, "CLOSED")
        assert CircuitState.CLOSED.value == "closed"

    def test_circuit_state_has_half_open(self) -> None:
        """Contract: CircuitState.HALF_OPEN must exist."""
        assert hasattr(CircuitState, "HALF_OPEN")
        assert CircuitState.HALF_OPEN.value == "half_open"

    def test_circuit_state_has_open(self) -> None:
        """Contract: CircuitState.OPEN must exist."""
        assert hasattr(CircuitState, "OPEN")
        assert CircuitState.OPEN.value == "open"
