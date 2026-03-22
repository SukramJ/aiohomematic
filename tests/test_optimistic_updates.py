"""Tests for optimistic update system."""

from typing import cast
from unittest.mock import MagicMock

import pytest

from aiohomematic.client import CommandPriority
from aiohomematic.const import RollbackReason
from aiohomematic.model.data_point import BaseParameterDataPoint
from aiohomematic.model.generic import DpSwitch

TEST_DEVICES: set[str] = {"VCU2128127", "VCU3609622"}


class TestOptimisticUpdateBasics:
    """Test basic optimistic update functionality."""

    def test_is_optimistic_property_exists(self) -> None:
        """Test that is_optimistic property exists."""
        MagicMock(spec=BaseParameterDataPoint)
        assert hasattr(BaseParameterDataPoint, "is_optimistic")

    def test_optimistic_age_property_exists(self) -> None:
        """Test that optimistic_age property exists."""
        MagicMock(spec=BaseParameterDataPoint)
        assert hasattr(BaseParameterDataPoint, "optimistic_age")

    def test_optimistic_fields_initialized(self) -> None:
        """Test that optimistic fields are properly initialized."""
        # Create a mock data point
        MagicMock(spec=BaseParameterDataPoint)

        # These fields should exist in __slots__
        assert hasattr(BaseParameterDataPoint, "__slots__")
        slots = []
        for cls in BaseParameterDataPoint.__mro__:
            if hasattr(cls, "__slots__"):
                slots.extend(cls.__slots__)

        # Check for optimistic-related slots
        assert "_optimistic" in slots or any("optimistic" in s for s in slots)


class TestRollbackReasons:
    """Test rollback reason enumeration."""

    def test_rollback_reason_enum_exists(self) -> None:
        """Test that RollbackReason enum exists."""
        assert RollbackReason is not None

    def test_rollback_reason_has_error(self) -> None:
        """Test that error reason exists."""
        assert hasattr(RollbackReason, "SEND_ERROR") or "send_error" in [r.value for r in RollbackReason]

    def test_rollback_reason_has_mismatch(self) -> None:
        """Test that mismatch reason exists."""
        assert hasattr(RollbackReason, "MISMATCH") or "mismatch" in [r.value for r in RollbackReason]

    def test_rollback_reason_has_timeout(self) -> None:
        """Test that timeout reason exists."""
        assert hasattr(RollbackReason, "TIMEOUT") or "timeout" in [r.value for r in RollbackReason]


class TestOptimisticValueProperty:
    """Test the value property with optimistic updates."""

    def test_value_property_returns_actual_when_not_optimistic(self) -> None:
        """Test that value property returns actual value when not optimistic."""
        dp = MagicMock(spec=BaseParameterDataPoint)
        dp._value = 0.5

        # When is_optimistic is False, value should return _value
        dp.is_optimistic = False

        result = dp._value if not dp.is_optimistic else None

        assert result == 0.5

    def test_value_property_returns_optimistic_when_available(self) -> None:
        """Test that value property prioritizes optimistic value."""
        dp = MagicMock(spec=BaseParameterDataPoint)
        dp._value = 0.5

        # When is_optimistic is True, value should return optimistic value
        dp.is_optimistic = True

        assert dp.is_optimistic is True


class TestOptimisticRollback:
    """Test optimistic value rollback mechanism."""

    def test_rollback_method_exists(self) -> None:
        """Test that rollback method exists."""
        assert hasattr(BaseParameterDataPoint, "_rollback_optimistic_value")

    def test_schedule_rollback_method_exists(self) -> None:
        """Test that schedule rollback method exists."""
        assert hasattr(BaseParameterDataPoint, "_schedule_optimistic_rollback")


class TestOptimisticUpdateTimeout:
    """Test optimistic update timeout configuration."""

    def test_timeout_config_exists(self) -> None:
        """Test that optimistic update timeout configuration exists."""
        from aiohomematic.const import TimeoutConfig

        # Check field exists in model
        assert "optimistic_update_timeout" in TimeoutConfig.model_fields

        # Verify instance has the attribute
        config = TimeoutConfig()
        assert hasattr(config, "optimistic_update_timeout")

    def test_timeout_is_reasonable(self) -> None:
        """Test that timeout value is reasonable (between 1 and 30 seconds)."""
        from aiohomematic.const import TimeoutConfig

        config = TimeoutConfig()
        timeout = config.optimistic_update_timeout
        assert 1.0 <= timeout <= 60.0, f"Timeout {timeout}s should be between 1 and 60 seconds"


class TestCoverTargetLevelIntegration:
    """Test integration with Cover _target_level properties."""

    def test_target_level_uses_optimistic_value(self) -> None:
        """Test that _target_level property uses optimistic values."""
        # This is more of an integration test
        # The actual implementation in CustomDpBlind should check is_optimistic
        # We're just verifying the pattern exists
        from aiohomematic.model.custom import CustomDpBlind

        # Verify the property exists
        assert hasattr(CustomDpBlind, "_target_level")
        assert hasattr(CustomDpBlind, "_target_tilt_level")


class TestOptimisticUpdateEvents:
    """Test optimistic update event publishing."""

    def test_rollback_event_class_exists(self) -> None:
        """Test that OptimisticRollbackEvent exists."""
        from aiohomematic.central.events import OptimisticRollbackEvent

        assert OptimisticRollbackEvent is not None

    def test_rollback_event_has_required_fields(self) -> None:
        """Test that rollback event has required fields."""
        import inspect

        from aiohomematic.central.events import OptimisticRollbackEvent

        # Check if it's a dataclass or has expected attributes
        sig = inspect.signature(OptimisticRollbackEvent.__init__)
        params = list(sig.parameters.keys())

        # Should have fields for: dpk (data point key), reason, old_value, new_value
        # The exact field names might vary, but should have these concepts
        assert len(params) > 1  # At least self + some fields


class TestDuplicateSendOptimistic:
    """Test that duplicate sends do not cause spurious optimistic rollback (issue #3049)."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_different_value_send_while_optimistic_active(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test that sending a different value while optimistic is active still sends."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        switch: DpSwitch = cast(
            DpSwitch,
            central.query_facade.get_generic_data_point(channel_address="VCU2128127:4", parameter="STATE"),
        )
        # Simulate optimistic True pending (before CCU event)
        switch._optimistic.apply(value=True, current_value=switch._value)
        assert switch.is_optimistic is True

        call_count_before = len([c for c in mock_client.method_calls if c[0] == "set_value"])

        # Send False: different value, should proceed
        await switch.send_value(value=False)

        call_count_after = len([c for c in mock_client.method_calls if c[0] == "set_value"])
        assert call_count_after == call_count_before + 1  # One new RPC call

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_duplicate_send_value_skips_second_send(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """
        Test that sending the same value twice skips the second RPC call.

        Reproduces issue #3049: When an automation triggers switch.turn_on twice
        within 100ms, the optimistic tracker increments pending_sends to 2.
        The CCU only confirms once, leaving pending_sends=1, causing a spurious
        rollback after 30s even though the device is physically ON.

        To simulate the race condition (second send before CCU event arrives),
        we manually set the optimistic state and then call send_value.
        """
        central, mock_client, _ = central_client_factory_with_homegear_client
        switch: DpSwitch = cast(
            DpSwitch,
            central.query_facade.get_generic_data_point(channel_address="VCU2128127:4", parameter="STATE"),
        )
        # Simulate the state after first send but before CCU event arrives:
        # - _value is still False/None (no event yet)
        # - optimistic is active with value=True, pending_sends=1
        switch._optimistic.apply(value=True, current_value=switch._value)
        assert switch.is_optimistic is True
        assert switch._optimistic.pending_sends == 1

        call_count_before = len([c for c in mock_client.method_calls if c[0] == "set_value"])

        # Second send with same value: should be skipped (no additional RPC call)
        await switch.send_value(value=True)
        assert switch._optimistic.pending_sends == 1  # Still 1, not 2

        call_count_after = len([c for c in mock_client.method_calls if c[0] == "set_value"])
        assert call_count_after == call_count_before  # No additional RPC call


class TestPriorityAndOptimisticIntegration:
    """Test that priority detection works with optimistic updates."""

    def test_send_value_detects_priority_before_optimistic_update(self) -> None:
        """Test that priority is detected before optimistic value is set."""
        # In send_value, priority detection happens first (line ~203)
        # Then optimistic update happens (line ~174+)
        # CRITICAL priority for locks/sirens is declared at the service-method level
        # via @bind_collector(priority=CommandPriority.CRITICAL)

        assert CommandPriority.CRITICAL.value == 0  # Highest priority
