# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract tests for command priority system.

STABILITY GUARANTEE
-------------------
These tests define the stable API contract for the priority-based command
throttling system. Any change that breaks these tests requires a MAJOR
version bump and coordination with plugin maintainers.

The contract ensures that:
1. CommandPriority enum has exactly 3 values: CRITICAL (0), HIGH (1), LOW (2)
2. CRITICAL priority bypasses throttle (interval = 0)
3. HIGH/LOW priorities respect throttle interval
4. CRITICAL priority is declared at the service-method level via @bind_collector
5. Client.set_value() accepts priority parameter
6. Client.put_paramset() accepts priority parameter

See docs/adr/0020-command-throttling-priority-and-optimistic-updates.md for details.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from aiohomematic.client import CommandPriority, CommandThrottle
from aiohomematic.const import Parameter
from aiohomematic.model.data_point import BaseParameterDataPoint, CallParameterCollector

# pylint: disable=protected-access


# =============================================================================
# Contract 1: CommandPriority Enum Stability
# =============================================================================


class TestCommandPriorityEnumContract:
    """Contract tests for CommandPriority enum."""

    def test_priority_critical_has_value_zero(self) -> None:
        """
        STABILITY CONTRACT: CRITICAL must have value 0 (highest priority).

        This is used for sorting and comparison.
        """
        assert CommandPriority.CRITICAL.value == 0, "CRITICAL must have value 0 (highest priority)"

    def test_priority_enum_has_exactly_three_values(self) -> None:
        """
        STABILITY CONTRACT: CommandPriority must have exactly 3 values.

        Adding/removing priority levels is a breaking change.
        """
        assert len(CommandPriority) == 3, f"CommandPriority must have exactly 3 values, got {len(CommandPriority)}"

    def test_priority_high_has_value_one(self) -> None:
        """
        STABILITY CONTRACT: HIGH must have value 1 (middle priority).

        This is the default for interactive commands.
        """
        assert CommandPriority.HIGH.value == 1, "HIGH must have value 1 (middle priority)"

    def test_priority_low_has_value_two(self) -> None:
        """
        STABILITY CONTRACT: LOW must have value 2 (lowest priority).

        This is used for bulk operations.
        """
        assert CommandPriority.LOW.value == 2, "LOW must have value 2 (lowest priority)"

    def test_priority_ordering_works_correctly(self) -> None:
        """
        STABILITY CONTRACT: Priority comparison must work via < operator.

        Lower value = higher priority.
        """
        assert CommandPriority.CRITICAL < CommandPriority.HIGH
        assert CommandPriority.HIGH < CommandPriority.LOW
        assert CommandPriority.CRITICAL < CommandPriority.LOW


# =============================================================================
# Contract 2: bind_collector Priority Floor
# =============================================================================


class TestBindCollectorPriorityContract:
    """Contract tests for @bind_collector priority parameter."""

    def test_collector_accepts_priority_parameter(self) -> None:
        """
        STABILITY CONTRACT: CallParameterCollector must accept priority parameter.

        This is the mechanism for service methods to declare CRITICAL priority.
        """
        mock_client = MagicMock()
        collector = CallParameterCollector(client=mock_client, priority=CommandPriority.CRITICAL)

        assert collector._priority == CommandPriority.CRITICAL

    def test_collector_priority_defaults_to_none(self) -> None:
        """
        STABILITY CONTRACT: CallParameterCollector priority defaults to None.

        None means no floor -- priority is determined entirely by data points.
        """
        mock_client = MagicMock()
        collector = CallParameterCollector(client=mock_client)

        assert collector._priority is None

    def test_collector_priority_floor_cannot_be_lowered_by_data_points(self) -> None:
        """
        STABILITY CONTRACT: Data points can elevate priority but not lower it below the floor.

        When a collector is created with priority=CRITICAL, adding HIGH data points
        must not lower the priority.
        """
        mock_client = MagicMock()
        collector = CallParameterCollector(client=mock_client, priority=CommandPriority.CRITICAL)

        # Simulate adding a HIGH-priority data point
        dp = MagicMock()
        dp.paramset_key = "VALUES"
        dp.channel.address = "TEST:1"
        dp.parameter = "LEVEL"
        dp.get_command_priority.return_value = CommandPriority.HIGH

        collector.add_data_point(data_point=dp, value=0.5, collector_order=50)

        # Priority must remain CRITICAL (floor)
        assert collector._priority == CommandPriority.CRITICAL


# =============================================================================
# Contract 3: Priority Detection at Data-Point Level
# =============================================================================


class TestPriorityDetectionContract:
    """Contract tests for priority detection logic."""

    def test_normal_parameters_get_high_priority_by_default(self) -> None:
        """
        STABILITY CONTRACT: Non-critical parameters get HIGH priority by default.

        This is the default for interactive user commands.
        """
        normal_params = [
            Parameter.LEVEL,
            Parameter.STATE,
            Parameter.ON_TIME,
        ]

        for param in normal_params:
            dp = MagicMock(spec=BaseParameterDataPoint)
            dp._parameter = param

            priority = BaseParameterDataPoint.get_command_priority(dp)
            assert priority == CommandPriority.HIGH, f"{param} should get HIGH priority (default), got {priority}"


# =============================================================================
# Contract 4: Throttle Behavior
# =============================================================================


class TestThrottleBehaviorContract:
    """Contract tests for command throttle behavior."""

    @pytest.mark.asyncio
    async def test_critical_priority_bypasses_throttle(self) -> None:
        """
        STABILITY CONTRACT: CRITICAL commands must bypass throttle entirely.

        This ensures security-critical commands execute immediately.
        """
        throttle = CommandThrottle(interface_id="TEST", interval=1.0)

        import asyncio

        start = asyncio.get_event_loop().time()

        # Send 5 CRITICAL commands
        for _ in range(5):
            await throttle.acquire(priority=CommandPriority.CRITICAL, device_address="TEST:1")

        elapsed = asyncio.get_event_loop().time() - start

        # Should complete in < 100ms (not 4+ seconds if throttled)
        assert elapsed < 0.1, f"CRITICAL commands must bypass throttle, took {elapsed}s"

    @pytest.mark.asyncio
    async def test_high_priority_respects_throttle(self) -> None:
        """
        STABILITY CONTRACT: HIGH priority commands must respect throttle interval.

        This prevents flooding the CCU with commands.
        """
        throttle = CommandThrottle(interface_id="TEST", interval=0.05)

        import asyncio

        start = asyncio.get_event_loop().time()

        # Send 3 HIGH commands
        for _ in range(3):
            await throttle.acquire(priority=CommandPriority.HIGH, device_address="TEST:1")

        elapsed = asyncio.get_event_loop().time() - start

        # Should take at least 2 intervals (3 commands = 2 waits)
        assert elapsed >= 0.09, f"HIGH commands must respect throttle, took {elapsed}s"

    @pytest.mark.asyncio
    async def test_throttle_disabled_when_interval_zero(self) -> None:
        """
        STABILITY CONTRACT: interval=0 must disable throttle entirely.

        This allows testing and high-performance scenarios.
        """
        throttle = CommandThrottle(interface_id="TEST", interval=0.0)

        import asyncio

        start = asyncio.get_event_loop().time()

        # Send 10 commands
        for _ in range(10):
            await throttle.acquire(priority=CommandPriority.HIGH, device_address="TEST:1")

        elapsed = asyncio.get_event_loop().time() - start

        # Should complete immediately
        assert elapsed < 0.05, f"interval=0 must disable throttle, took {elapsed}s"


# =============================================================================
# Contract 5: Client API Stability
# =============================================================================


class TestClientPriorityAPIContract:
    """Contract tests for client priority parameter."""

    def test_interface_client_put_paramset_accepts_priority(self) -> None:
        """
        STABILITY CONTRACT: InterfaceClient.put_paramset() must accept priority parameter.

        This is used for bulk parameter updates.
        """
        import inspect

        from aiohomematic.client import InterfaceClient

        sig = inspect.signature(InterfaceClient.put_paramset)
        assert "priority" in sig.parameters, "InterfaceClient.put_paramset() must accept priority parameter"

        # Check type hint
        param = sig.parameters["priority"]
        assert param.default is None, "priority parameter must default to None"

    def test_interface_client_set_value_accepts_priority(self) -> None:
        """
        STABILITY CONTRACT: InterfaceClient.set_value() must accept priority parameter.

        This is the primary API for sending commands with priority.
        """
        import inspect

        from aiohomematic.client import InterfaceClient

        sig = inspect.signature(InterfaceClient.set_value)
        assert "priority" in sig.parameters, "InterfaceClient.set_value() must accept priority parameter"

        # Check type hint
        param = sig.parameters["priority"]
        assert param.default is None, "priority parameter must default to None"

    def test_protocol_interfaces_include_priority(self) -> None:
        """
        STABILITY CONTRACT: Protocol interfaces must include priority parameter.

        This ensures mocks and type checking work correctly.
        """
        import inspect

        from aiohomematic.interfaces.client import ParamsetOperationsProtocol, ValueOperationsProtocol

        # Check ValueOperationsProtocol.set_value
        sig = inspect.signature(ValueOperationsProtocol.set_value)
        assert "priority" in sig.parameters, "ValueOperationsProtocol.set_value() must include priority"

        # Check ParamsetOperationsProtocol.put_paramset
        sig = inspect.signature(ParamsetOperationsProtocol.put_paramset)
        assert "priority" in sig.parameters, "ParamsetOperationsProtocol.put_paramset() must include priority"
