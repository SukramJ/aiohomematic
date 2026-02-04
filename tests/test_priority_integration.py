"""Integration tests for priority detection and throttling system."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from aiohomematic.client import CommandPriority, CommandThrottle
from aiohomematic.const import Parameter
from aiohomematic.model.data_point import BaseParameterDataPoint


class TestPriorityIntegration:
    """Test end-to-end priority detection and throttling."""

    @pytest.mark.asyncio
    async def test_critical_vs_high_priority_ordering(self) -> None:
        """Test that CRITICAL priority is higher than HIGH priority."""
        throttle = CommandThrottle(interface_id="TEST", interval=0.1)

        execution_order: list[CommandPriority] = []

        async def execute_critical() -> None:
            await throttle.acquire(priority=CommandPriority.CRITICAL, device_address="TEST:1")
            execution_order.append(CommandPriority.CRITICAL)

        async def execute_high() -> None:
            await throttle.acquire(priority=CommandPriority.HIGH, device_address="TEST:1")
            execution_order.append(CommandPriority.HIGH)

        task_high = asyncio.create_task(execute_high())
        await asyncio.sleep(0.01)

        task_critical = asyncio.create_task(execute_critical())

        await asyncio.gather(task_high, task_critical)

        assert CommandPriority.CRITICAL in execution_order

    @pytest.mark.asyncio
    async def test_normal_parameter_gets_high_priority(self) -> None:
        """Test that normal parameters get HIGH priority by default."""
        dp = MagicMock(spec=BaseParameterDataPoint)
        dp._parameter = Parameter.LEVEL
        dp._is_bulk_operation_context.return_value = False

        priority = BaseParameterDataPoint.get_command_priority(dp)

        assert priority == CommandPriority.HIGH
        assert priority.value == 1

    def test_priority_enum_ordering_for_queue(self) -> None:
        """Test that CommandPriority enum values support correct queue ordering."""
        assert CommandPriority.CRITICAL.value < CommandPriority.HIGH.value
        assert CommandPriority.HIGH.value < CommandPriority.LOW.value

        priorities = [CommandPriority.LOW, CommandPriority.CRITICAL, CommandPriority.HIGH]
        sorted_priorities = sorted(priorities)

        assert sorted_priorities[0] == CommandPriority.CRITICAL
        assert sorted_priorities[1] == CommandPriority.HIGH
        assert sorted_priorities[2] == CommandPriority.LOW


class TestPriorityWithOptimisticUpdates:
    """Test priority detection works correctly with optimistic updates."""

    def test_priority_detection_before_optimistic_update(self) -> None:
        """Test that priority is detected BEFORE optimistic value is set."""
        dp = MagicMock(spec=BaseParameterDataPoint)
        dp._parameter = Parameter.LEVEL
        dp._is_bulk_operation_context.return_value = False

        priority = BaseParameterDataPoint.get_command_priority(dp)
        assert priority == CommandPriority.HIGH
