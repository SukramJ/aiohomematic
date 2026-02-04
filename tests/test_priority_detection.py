"""Tests for command priority detection."""

from __future__ import annotations

from unittest.mock import MagicMock

from aiohomematic.client import CommandPriority
from aiohomematic.const import Parameter
from aiohomematic.model.data_point import BaseParameterDataPoint


class TestPriorityDetection:
    """Test priority detection in BaseParameterDataPoint."""

    def test_get_command_priority_high_default(self) -> None:
        """Test get_command_priority returns HIGH for normal parameters."""
        dp = MagicMock(spec=BaseParameterDataPoint)
        dp._parameter = Parameter.LEVEL

        result = BaseParameterDataPoint.get_command_priority(dp)

        assert result == CommandPriority.HIGH

    def test_get_command_priority_high_for_lock_parameters(self) -> None:
        """
        Test get_command_priority returns HIGH at data-point level for lock parameters.

        CRITICAL priority for locks is declared at the service-method level
        via ``@bind_collector(priority=CommandPriority.CRITICAL)``.
        """
        dp = MagicMock(spec=BaseParameterDataPoint)
        dp._parameter = Parameter.LOCK_TARGET_LEVEL

        result = BaseParameterDataPoint.get_command_priority(dp)

        assert result == CommandPriority.HIGH

    def test_get_command_priority_high_for_siren_parameters(self) -> None:
        """
        Test get_command_priority returns HIGH at data-point level for siren parameters.

        CRITICAL priority for sirens is declared at the service-method level
        via ``@bind_collector(priority=CommandPriority.CRITICAL)``.
        """
        dp = MagicMock(spec=BaseParameterDataPoint)
        dp._parameter = Parameter.ACOUSTIC_ALARM_ACTIVE

        result = BaseParameterDataPoint.get_command_priority(dp)

        assert result == CommandPriority.HIGH


class TestPriorityEnum:
    """Test CommandPriority enum semantics."""

    def test_critical_is_highest_priority(self) -> None:
        """Test that CRITICAL has the lowest numeric value (highest priority)."""
        assert CommandPriority.CRITICAL.value == 0

    def test_high_is_middle_priority(self) -> None:
        """Test that HIGH has middle numeric value."""
        assert CommandPriority.HIGH.value == 1

    def test_low_is_lowest_priority(self) -> None:
        """Test that LOW has the highest numeric value (lowest priority)."""
        assert CommandPriority.LOW.value == 2

    def test_priority_comparison_ordering(self) -> None:
        """Test that priorities can be compared correctly."""
        priorities = [CommandPriority.LOW, CommandPriority.CRITICAL, CommandPriority.HIGH]
        sorted_priorities = sorted(priorities)

        assert sorted_priorities == [
            CommandPriority.CRITICAL,
            CommandPriority.HIGH,
            CommandPriority.LOW,
        ]

    def test_priority_enum_has_three_values(self) -> None:
        """Test that we have exactly three priority levels."""
        assert len(CommandPriority) == 3
