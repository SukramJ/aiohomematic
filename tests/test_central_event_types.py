# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for aiohomematic event types validation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from aiohomematic.central.events import (
    CacheInvalidatedEvent,
    CentralStateChangedEvent,
    ClientStateChangedEvent,
    ConnectionHealthChangedEvent,
    ConnectionStageChangedEvent,
    DataPointsCreatedEvent,
    DataPointStateChangedEvent,
    DataPointStatusReceivedEvent,
    DataPointValueReceivedEvent,
    DataRefreshCompletedEvent,
    DataRefreshTriggeredEvent,
    DeviceLifecycleEvent,
    DeviceLifecycleEventType,
    DeviceRemovedEvent,
    DeviceStateChangedEvent,
    DeviceTriggerEvent,
    Event,
    RecoveryCompletedEvent,
    RecoveryFailedEvent,
    RecoveryStageChangedEvent,
    RpcParameterReceivedEvent,
    SystemStatusChangedEvent,
    SysvarStateChangedEvent,
)
from aiohomematic.const import (
    CacheInvalidationReason,
    CacheType,
    CentralState,
    ClientState,
    ConnectionStage,
    DataPointCategory,
    DataPointKey,
    DataRefreshType,
    DeviceTriggerEventType,
    FailureReason,
    ParamsetKey,
    RecoveryStage,
)


class TestEventBase:
    """Test Event base class properties."""

    def test_event_is_abstract(self) -> None:
        """Event should be abstract and not directly instantiable."""
        # Event is abstract due to @abstractmethod key property
        # We can only test via concrete implementations
        event = DataPointValueReceivedEvent(
            timestamp=datetime.now(),
            dpk=DataPointKey(
                interface_id="BidCos-RF",
                channel_address="VCU0000001:1",
                paramset_key=ParamsetKey.VALUES,
                parameter="STATE",
            ),
            value=True,
            received_at=datetime.now(),
        )
        # Verify it's a subclass of Event
        assert isinstance(event, Event)

    def test_event_timestamp_required(self) -> None:
        """All events should have a timestamp field."""
        now = datetime.now()
        event = DeviceLifecycleEvent(
            timestamp=now,
            event_type=DeviceLifecycleEventType.CREATED,
            device_addresses=("VCU0000001",),
        )
        assert event.timestamp == now


class TestDataPointEvents:
    """Test data point-related event types."""

    def test_data_point_state_changed_event(self) -> None:
        """DataPointStateChangedEvent should contain unique_id, custom_id, old/new values."""
        event = DataPointStateChangedEvent(
            timestamp=datetime.now(),
            unique_id="device_001_STATE",
            custom_id="my_custom_id",
            old_value=False,
            new_value=True,
        )

        assert event.unique_id == "device_001_STATE"
        assert event.custom_id == "my_custom_id"
        assert event.old_value is False
        assert event.new_value is True
        assert event.key == "device_001_STATE"

    def test_data_point_status_received_event(self) -> None:
        """DataPointStatusReceivedEvent should contain dpk and status_value."""
        dpk = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )
        now = datetime.now()
        event = DataPointStatusReceivedEvent(
            timestamp=now,
            dpk=dpk,
            status_value=0,
            received_at=now,
        )

        assert event.dpk == dpk
        assert event.status_value == 0
        assert event.key == dpk

    def test_data_point_value_received_event(self) -> None:
        """DataPointValueReceivedEvent should contain dpk, value, and received_at."""
        dpk = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )
        now = datetime.now()
        event = DataPointValueReceivedEvent(
            timestamp=now,
            dpk=dpk,
            value=True,
            received_at=now,
        )

        assert event.dpk == dpk
        assert event.value is True
        assert event.received_at == now
        assert event.key == dpk  # key property returns dpk

    def test_data_point_value_received_event_immutable(self) -> None:
        """DataPointValueReceivedEvent should be immutable (frozen dataclass)."""
        dpk = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )
        event = DataPointValueReceivedEvent(
            timestamp=datetime.now(),
            dpk=dpk,
            value=True,
            received_at=datetime.now(),
        )

        with pytest.raises(AttributeError):
            event.value = False  # type: ignore[misc]

    def test_rpc_parameter_received_event(self) -> None:
        """RpcParameterReceivedEvent should contain interface_id, channel_address, parameter, value."""
        now = datetime.now()
        event = RpcParameterReceivedEvent(
            timestamp=now,
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            parameter="STATE",
            value=True,
        )

        assert event.interface_id == "BidCos-RF"
        assert event.channel_address == "VCU0000001:1"
        assert event.parameter == "STATE"
        assert event.value is True
        # key is a DataPointKey constructed from fields
        expected_key = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )
        assert event.key == expected_key


class TestDeviceEvents:
    """Test device-related event types."""

    def test_device_lifecycle_event(self) -> None:
        """DeviceLifecycleEvent should contain event_type and device_addresses."""
        event = DeviceLifecycleEvent(
            timestamp=datetime.now(),
            event_type=DeviceLifecycleEventType.CREATED,
            device_addresses=("VCU0000001", "VCU0000002"),
            interface_id="BidCos-RF",
        )

        assert event.event_type == DeviceLifecycleEventType.CREATED
        assert event.device_addresses == ("VCU0000001", "VCU0000002")
        assert event.interface_id == "BidCos-RF"
        assert event.key is None

    def test_device_lifecycle_event_types(self) -> None:
        """DeviceLifecycleEvent should support all lifecycle event types."""
        for event_type in DeviceLifecycleEventType:
            event = DeviceLifecycleEvent(
                timestamp=datetime.now(),
                event_type=event_type,
                device_addresses=("VCU0000001",),
            )
            assert event.event_type == event_type

    def test_device_removed_event(self) -> None:
        """DeviceRemovedEvent should contain unique_id and optional fields."""
        event = DeviceRemovedEvent(
            timestamp=datetime.now(),
            unique_id="device_001",
            device_address="VCU0000001",
            interface_id="BidCos-RF",
            channel_addresses=("VCU0000001:0", "VCU0000001:1"),
        )

        assert event.unique_id == "device_001"
        assert event.device_address == "VCU0000001"
        assert event.interface_id == "BidCos-RF"
        assert event.channel_addresses == ("VCU0000001:0", "VCU0000001:1")
        # Key is device_address when set, otherwise unique_id
        assert event.key == "VCU0000001"

    def test_device_removed_event_minimal(self) -> None:
        """DeviceRemovedEvent should work with only required fields."""
        event = DeviceRemovedEvent(
            timestamp=datetime.now(),
            unique_id="device_001",
        )

        assert event.unique_id == "device_001"
        assert event.device_address is None
        assert event.interface_id is None
        assert event.channel_addresses == ()

    def test_device_state_changed_event(self) -> None:
        """DeviceStateChangedEvent should contain device_address."""
        event = DeviceStateChangedEvent(
            timestamp=datetime.now(),
            device_address="VCU0000001",
        )

        assert event.device_address == "VCU0000001"
        assert event.key == "VCU0000001"

    def test_device_trigger_event(self) -> None:
        """DeviceTriggerEvent should contain all trigger-related fields."""
        event = DeviceTriggerEvent(
            timestamp=datetime.now(),
            trigger_type=DeviceTriggerEventType.KEYPRESS,
            model="HmIP-BWTH",
            interface_id="HmIP-RF",
            device_address="VCU0000001",
            channel_no=1,
            parameter="PRESS_SHORT",
            value=True,
        )

        assert event.trigger_type == DeviceTriggerEventType.KEYPRESS
        assert event.model == "HmIP-BWTH"
        assert event.interface_id == "HmIP-RF"
        assert event.device_address == "VCU0000001"
        assert event.channel_no == 1
        assert event.parameter == "PRESS_SHORT"
        assert event.value is True
        assert event.key is None


class TestConnectionEvents:
    """Test connection-related event types."""

    def test_connection_health_changed_event(self) -> None:
        """ConnectionHealthChangedEvent should contain health status details."""
        last_contact = datetime.now()
        event = ConnectionHealthChangedEvent(
            timestamp=datetime.now(),
            interface_id="BidCos-RF",
            is_healthy=False,
            failure_reason=FailureReason.TIMEOUT,
            consecutive_failures=3,
            last_successful_contact=last_contact,
        )

        assert event.interface_id == "BidCos-RF"
        assert event.is_healthy is False
        assert event.failure_reason == FailureReason.TIMEOUT
        assert event.consecutive_failures == 3
        assert event.last_successful_contact == last_contact
        assert event.key == "BidCos-RF"

    def test_connection_health_changed_event_healthy(self) -> None:
        """ConnectionHealthChangedEvent for healthy connection."""
        event = ConnectionHealthChangedEvent(
            timestamp=datetime.now(),
            interface_id="BidCos-RF",
            is_healthy=True,
            failure_reason=None,
            consecutive_failures=0,
            last_successful_contact=datetime.now(),
        )

        assert event.is_healthy is True
        assert event.failure_reason is None
        assert event.consecutive_failures == 0

    def test_connection_stage_changed_event(self) -> None:
        """ConnectionStageChangedEvent should contain stage transition details."""
        event = ConnectionStageChangedEvent(
            timestamp=datetime.now(),
            interface_id="BidCos-RF",
            stage=ConnectionStage.ESTABLISHED,
            previous_stage=ConnectionStage.WARMUP,
            duration_in_previous_stage_ms=150.5,
        )

        assert event.interface_id == "BidCos-RF"
        assert event.stage == ConnectionStage.ESTABLISHED
        assert event.previous_stage == ConnectionStage.WARMUP
        assert event.duration_in_previous_stage_ms == 150.5
        assert event.key == "BidCos-RF"


class TestRecoveryEvents:
    """Test recovery-related event types."""

    def test_recovery_completed_event(self) -> None:
        """RecoveryCompletedEvent should contain recovery completion details."""
        event = RecoveryCompletedEvent(
            timestamp=datetime.now(),
            interface_id="BidCos-RF",
            central_name="ccu-main",
            total_attempts=2,
            total_duration_ms=5000.0,
            stages_completed=(RecoveryStage.TCP_CHECKING, RecoveryStage.RPC_CHECKING),
            interfaces_recovered=("BidCos-RF",),
        )

        assert event.interface_id == "BidCos-RF"
        assert event.central_name == "ccu-main"
        assert event.total_attempts == 2
        assert event.total_duration_ms == 5000.0
        assert event.stages_completed == (RecoveryStage.TCP_CHECKING, RecoveryStage.RPC_CHECKING)
        assert event.interfaces_recovered == ("BidCos-RF",)

    def test_recovery_failed_event(self) -> None:
        """RecoveryFailedEvent should contain recovery failure details."""
        event = RecoveryFailedEvent(
            timestamp=datetime.now(),
            interface_id="BidCos-RF",
            central_name="ccu-main",
            total_attempts=5,
            total_duration_ms=30000.0,
            last_stage_reached=RecoveryStage.RPC_CHECKING,
            failure_reason=FailureReason.NETWORK,
            requires_manual_intervention=True,
            failed_interfaces=("BidCos-RF",),
        )

        assert event.interface_id == "BidCos-RF"
        assert event.central_name == "ccu-main"
        assert event.total_attempts == 5
        assert event.total_duration_ms == 30000.0
        assert event.last_stage_reached == RecoveryStage.RPC_CHECKING
        assert event.failure_reason == FailureReason.NETWORK
        assert event.requires_manual_intervention is True
        assert event.failed_interfaces == ("BidCos-RF",)

    def test_recovery_stage_changed_event(self) -> None:
        """RecoveryStageChangedEvent should contain recovery stage transition details."""
        event = RecoveryStageChangedEvent(
            timestamp=datetime.now(),
            interface_id="BidCos-RF",
            old_stage=RecoveryStage.IDLE,
            new_stage=RecoveryStage.TCP_CHECKING,
            duration_in_old_stage_ms=0.0,
            attempt_number=1,
        )

        assert event.interface_id == "BidCos-RF"
        assert event.old_stage == RecoveryStage.IDLE
        assert event.new_stage == RecoveryStage.TCP_CHECKING
        assert event.duration_in_old_stage_ms == 0.0
        assert event.attempt_number == 1
        assert event.key == "BidCos-RF"


class TestStateMachineEvents:
    """Test state machine-related event types."""

    def test_central_state_changed_event(self) -> None:
        """CentralStateChangedEvent should contain central state transition details."""
        event = CentralStateChangedEvent(
            timestamp=datetime.now(),
            central_name="ccu-main",
            old_state=CentralState.STOPPED,
            new_state=CentralState.STARTING,
            trigger="user_start",
        )

        assert event.central_name == "ccu-main"
        assert event.old_state == CentralState.STOPPED
        assert event.new_state == CentralState.STARTING
        assert event.trigger == "user_start"
        assert event.key == "ccu-main"

    def test_client_state_changed_event(self) -> None:
        """ClientStateChangedEvent should contain client state transition details."""
        event = ClientStateChangedEvent(
            timestamp=datetime.now(),
            interface_id="BidCos-RF",
            old_state=ClientState.CREATED,
            new_state=ClientState.CONNECTED,
            trigger="start",
        )

        assert event.interface_id == "BidCos-RF"
        assert event.old_state == ClientState.CREATED
        assert event.new_state == ClientState.CONNECTED
        assert event.trigger == "start"
        assert event.key == "BidCos-RF"

    def test_client_state_changed_event_with_failure(self) -> None:
        """ClientStateChangedEvent should handle trigger reason."""
        event = ClientStateChangedEvent(
            timestamp=datetime.now(),
            interface_id="BidCos-RF",
            old_state=ClientState.CONNECTED,
            new_state=ClientState.FAILED,
            trigger="connection_lost",
        )

        assert event.new_state == ClientState.FAILED
        assert event.trigger == "connection_lost"


class TestCacheEvents:
    """Test cache-related event types."""

    def test_cache_invalidated_event(self) -> None:
        """CacheInvalidatedEvent should contain cache invalidation details."""
        event = CacheInvalidatedEvent(
            timestamp=datetime.now(),
            cache_type=CacheType.PARAMSET_DESCRIPTION,
            reason=CacheInvalidationReason.DEVICE_REMOVED,
            scope="VCU0000001",
            entries_affected=5,
        )

        assert event.cache_type == CacheType.PARAMSET_DESCRIPTION
        assert event.reason == CacheInvalidationReason.DEVICE_REMOVED
        assert event.scope == "VCU0000001"
        assert event.entries_affected == 5

    def test_cache_invalidated_event_no_scope(self) -> None:
        """CacheInvalidatedEvent should work without scope."""
        event = CacheInvalidatedEvent(
            timestamp=datetime.now(),
            cache_type=CacheType.DEVICE_DESCRIPTION,
            reason=CacheInvalidationReason.MANUAL,
            scope=None,
            entries_affected=100,
        )

        assert event.scope is None
        assert event.entries_affected == 100


class TestDataRefreshEvents:
    """Test data refresh-related event types."""

    def test_data_refresh_completed_event_failure(self) -> None:
        """DataRefreshCompletedEvent should contain failure details."""
        event = DataRefreshCompletedEvent(
            timestamp=datetime.now(),
            refresh_type=DataRefreshType.CLIENT_DATA,
            interface_id="BidCos-RF",
            success=False,
            duration_ms=500.0,
            items_refreshed=0,
            error_message="Connection timeout",
        )

        assert event.success is False
        assert event.items_refreshed == 0
        assert event.error_message == "Connection timeout"

    def test_data_refresh_completed_event_success(self) -> None:
        """DataRefreshCompletedEvent should contain successful completion details."""
        event = DataRefreshCompletedEvent(
            timestamp=datetime.now(),
            refresh_type=DataRefreshType.CLIENT_DATA,
            interface_id="BidCos-RF",
            success=True,
            duration_ms=1500.0,
            items_refreshed=25,
            error_message=None,
        )

        assert event.refresh_type == DataRefreshType.CLIENT_DATA
        assert event.interface_id == "BidCos-RF"
        assert event.success is True
        assert event.duration_ms == 1500.0
        assert event.items_refreshed == 25
        assert event.error_message is None

    def test_data_refresh_triggered_event(self) -> None:
        """DataRefreshTriggeredEvent should contain refresh trigger details."""
        event = DataRefreshTriggeredEvent(
            timestamp=datetime.now(),
            refresh_type=DataRefreshType.CLIENT_DATA,
            interface_id="BidCos-RF",
            scheduled=True,
        )

        assert event.refresh_type == DataRefreshType.CLIENT_DATA
        assert event.interface_id == "BidCos-RF"
        assert event.scheduled is True


class TestIntegrationEvents:
    """Test Home Assistant integration-related event types."""

    def test_data_points_created_event(self) -> None:
        """DataPointsCreatedEvent should contain new data points mapping."""
        new_data_points: dict[DataPointCategory, Any] = {
            DataPointCategory.SENSOR: ["sensor1", "sensor2"],
            DataPointCategory.SWITCH: ["switch1"],
        }
        event = DataPointsCreatedEvent(
            timestamp=datetime.now(),
            new_data_points=new_data_points,
        )

        assert event.new_data_points == new_data_points
        assert event.key is None

    def test_system_status_changed_event(self) -> None:
        """SystemStatusChangedEvent should contain system status details."""
        event = SystemStatusChangedEvent(
            timestamp=datetime.now(),
            callback_state=("BidCos-RF", True),
            client_state=("BidCos-RF", ClientState.STOPPED, ClientState.CONNECTED),
            connection_state=("BidCos-RF", True),
            central_state=CentralState.RUNNING,
        )

        assert event.callback_state == ("BidCos-RF", True)
        assert event.client_state == ("BidCos-RF", ClientState.STOPPED, ClientState.CONNECTED)
        assert event.connection_state == ("BidCos-RF", True)
        assert event.central_state == CentralState.RUNNING
        assert event.key is None

    def test_system_status_changed_event_partial(self) -> None:
        """SystemStatusChangedEvent should work with partial data."""
        event = SystemStatusChangedEvent(
            timestamp=datetime.now(),
            callback_state=("BidCos-RF", False),
        )

        assert event.callback_state == ("BidCos-RF", False)
        assert event.client_state is None
        assert event.issues == ()


class TestSysvarEvent:
    """Test system variable event types."""

    def test_sysvar_state_changed_event(self) -> None:
        """SysvarStateChangedEvent should contain sysvar state details."""
        now = datetime.now()
        event = SysvarStateChangedEvent(
            timestamp=now,
            state_path="sv_12345",
            value=42,
            received_at=now,
        )

        assert event.state_path == "sv_12345"
        assert event.value == 42
        assert event.received_at == now
        assert event.key == "sv_12345"

    def test_sysvar_state_changed_event_string_value(self) -> None:
        """SysvarStateChangedEvent should support string values."""
        event = SysvarStateChangedEvent(
            timestamp=datetime.now(),
            state_path="sv_string_var",
            value="Hello World",
            received_at=datetime.now(),
        )

        assert event.value == "Hello World"


class TestEventKeyProperty:
    """Test the key property for various event types."""

    def test_event_key_for_targeted_events(self) -> None:
        """Events with specific keys should return appropriate key."""
        dpk = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )

        # DataPointValueReceivedEvent key is dpk
        dp_event = DataPointValueReceivedEvent(
            timestamp=datetime.now(),
            dpk=dpk,
            value=True,
            received_at=datetime.now(),
        )
        assert dp_event.key == dpk

        # DeviceStateChangedEvent key is device_address
        device_event = DeviceStateChangedEvent(
            timestamp=datetime.now(),
            device_address="VCU0000001",
        )
        assert device_event.key == "VCU0000001"

        # SysvarStateChangedEvent key is state_path
        sysvar_event = SysvarStateChangedEvent(
            timestamp=datetime.now(),
            state_path="sv_12345",
            value=42,
            received_at=datetime.now(),
        )
        assert sysvar_event.key == "sv_12345"

    def test_event_key_is_none_for_broadcast_events(self) -> None:
        """Events without specific keys should return None."""
        lifecycle_event = DeviceLifecycleEvent(
            timestamp=datetime.now(),
            event_type=DeviceLifecycleEventType.CREATED,
            device_addresses=("VCU0000001",),
        )
        assert lifecycle_event.key is None

        trigger_event = DeviceTriggerEvent(
            timestamp=datetime.now(),
            trigger_type=DeviceTriggerEventType.KEYPRESS,
            model="HmIP-BWTH",
            interface_id="HmIP-RF",
            device_address="VCU0000001",
            channel_no=1,
            parameter="PRESS_SHORT",
            value=True,
        )
        assert trigger_event.key is None


class TestEventSlots:
    """Test that events use __slots__ for memory efficiency."""

    def test_events_cannot_add_attributes(self) -> None:
        """Events should not allow adding new attributes (frozen dataclass)."""
        dpk = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )
        event = DataPointValueReceivedEvent(
            timestamp=datetime.now(),
            dpk=dpk,
            value=True,
            received_at=datetime.now(),
        )

        # Frozen dataclass should raise on attribute modification
        with pytest.raises((AttributeError, TypeError)):
            event.value = False  # type: ignore[misc]

    def test_events_use_slots(self) -> None:
        """Events should use slots (frozen=True, slots=True dataclass)."""
        event = DataPointValueReceivedEvent(
            timestamp=datetime.now(),
            dpk=DataPointKey(
                interface_id="BidCos-RF",
                channel_address="VCU0000001:1",
                paramset_key=ParamsetKey.VALUES,
                parameter="STATE",
            ),
            value=True,
            received_at=datetime.now(),
        )

        # Frozen dataclass with slots should not have __dict__
        assert not hasattr(event, "__dict__")
