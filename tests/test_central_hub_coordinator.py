# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Tests for aiohomematic.central.hub_coordinator."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from aiohomematic.central.hub_coordinator import HubCoordinator
from aiohomematic.const import DataPointCategory, Interface


class _FakeProgramDataPoint:
    """Minimal fake ProgramDataPoint for testing."""

    def __init__(self, *, pid: str, name: str, category: DataPointCategory) -> None:
        """Initialize a fake program data point."""
        self.pid = pid
        self.name = name
        self.category = category
        self.legacy_name = f"program_{name}"
        self.is_registered = True
        self.state_path = f"/pd_{pid}/"

    def publish_device_removed_event(self) -> None:
        """Publish device removed event."""


class _FakeProgramDpType:
    """Minimal fake ProgramDpType for testing."""

    def __init__(self, *, pid: str) -> None:
        """Initialize a fake program DP type."""
        self.pid = pid
        self.button = _FakeProgramDataPoint(pid=pid, name=f"button_{pid}", category=DataPointCategory.HUB_BUTTON)
        self.switch = _FakeProgramDataPoint(pid=pid, name=f"switch_{pid}", category=DataPointCategory.HUB_SWITCH)


class _FakeSysvarDataPoint:
    """Minimal fake SysvarDataPoint for testing."""

    def __init__(self, *, vid: str, name: str, category: DataPointCategory) -> None:
        """Initialize a fake sysvar data point."""
        self.vid = vid
        self.name = name
        self.category = category
        self.legacy_name = f"sysvar_{name}"
        self.state_path = f"sv_{vid}"
        self.is_registered = True

    async def event(self, *, value: Any, received_at: Any) -> None:
        """Handle event."""

    def publish_device_removed_event(self) -> None:
        """Publish device removed event."""

    async def send_variable(self, *, value: Any) -> None:
        """Send variable."""


class _FakeEventCoordinator:
    """Minimal fake EventCoordinator for testing."""

    def __init__(self) -> None:
        """Initialize fake event coordinator."""
        self.sysvar_subscriptions: dict[str, Any] = {}

    def add_sysvar_subscription(self, *, state_path: str, callback: Any) -> None:
        """Add sysvar subscription."""
        self.sysvar_subscriptions[state_path] = callback

    def remove_sysvar_subscription(self, *, state_path: str) -> None:
        """Remove sysvar subscription."""
        if state_path in self.sysvar_subscriptions:
            del self.sysvar_subscriptions[state_path]


class _FakeHub:
    """Minimal fake Hub for testing."""

    def __init__(self) -> None:
        """Initialize fake hub."""

    async def fetch_program_data(self, *, scheduled: bool) -> None:
        """Fetch program data."""

    async def fetch_sysvar_data(self, *, scheduled: bool) -> None:
        """Fetch sysvar data."""

    async def init_install_mode(self) -> dict:
        """Initialize install mode."""
        return {}


class _FakeClient:
    """Minimal fake Client for testing."""

    def __init__(self) -> None:
        """Initialize fake client."""

    async def execute_program(self, *, pid: str) -> bool:
        """Execute program."""
        return True

    async def get_system_variable(self, *, name: str) -> Any:
        """Get system variable."""
        return 42

    async def set_program_state(self, *, pid: str, state: bool) -> bool:
        """Set program state."""
        return True


class _FakeCentral:
    """Minimal fake CentralUnit for testing."""

    def __init__(self, *, name: str = "test_central") -> None:
        """Initialize a fake central."""
        self.name = name
        self.config = MagicMock()
        self.event_coordinator = _FakeEventCoordinator()
        self.event_bus = MagicMock()
        self.event_bus.subscribe = MagicMock(return_value=lambda: None)
        self._primary_client: _FakeClient | None = None
        self._clients: tuple[_FakeClient, ...] = ()
        # Add protocol interfaces required by HubCoordinator
        self.looper = MagicMock()
        self.paramset_descriptions = MagicMock()
        self.parameter_visibility = MagicMock()

    @property
    def cache_coordinator(self):  # noqa: D401,ANN201
        """Return a mock cache coordinator."""
        from types import SimpleNamespace

        return SimpleNamespace(
            paramset_descriptions=self.paramset_descriptions,
            parameter_visibility=self.parameter_visibility,
        )

    @property
    def clients(self) -> tuple[_FakeClient, ...]:
        """Return all clients."""
        return self._clients

    @property
    def has_clients(self) -> bool:
        """Check if any clients exist."""
        return len(self._clients) > 0

    @property
    def interface_ids(self) -> frozenset[str]:
        """Return all interface IDs."""
        return frozenset()

    @property
    def primary_client(self) -> _FakeClient | None:
        """Return primary client."""
        return self._primary_client

    def get_client(self, *, interface_id: str | None = None, interface: Interface | None = None) -> _FakeClient | None:
        """Get client by interface_id or interface type."""
        return None


class TestHubCoordinatorBasics:
    """Test basic HubCoordinator functionality."""

    def test_hub_coordinator_initialization(self) -> None:
        """HubCoordinator should initialize with protocol interfaces."""
        central = _FakeCentral()
        coordinator = HubCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            event_bus_provider=central,
            event_publisher=central,
            parameter_visibility_provider=central.cache_coordinator.parameter_visibility,
            paramset_description_provider=central.cache_coordinator.paramset_descriptions,
            primary_client_provider=central,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        assert coordinator._hub is not None
        assert len(coordinator._program_data_points) == 0
        assert len(coordinator._sysvar_data_points) == 0

    def test_program_data_points_property(self) -> None:
        """Program data points property should return all program data points."""
        central = _FakeCentral()
        coordinator = HubCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            event_bus_provider=central,
            event_publisher=central,
            parameter_visibility_provider=central.cache_coordinator.parameter_visibility,
            paramset_description_provider=central.cache_coordinator.paramset_descriptions,
            primary_client_provider=central,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        program_dp = _FakeProgramDpType(pid="123")
        coordinator._program_data_points["123"] = program_dp  # type: ignore[assignment]

        data_points = coordinator.program_data_points
        assert len(data_points) == 2  # button and switch
        assert program_dp.button in data_points
        assert program_dp.switch in data_points

    def test_sysvar_data_points_property(self) -> None:
        """Sysvar data points property should return all sysvar data points."""
        central = _FakeCentral()
        coordinator = HubCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            event_bus_provider=central,
            event_publisher=central,
            parameter_visibility_provider=central.cache_coordinator.parameter_visibility,
            paramset_description_provider=central.cache_coordinator.paramset_descriptions,
            primary_client_provider=central,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        sysvar_dp = _FakeSysvarDataPoint(vid="123", name="test", category=DataPointCategory.HUB_SENSOR)
        coordinator._sysvar_data_points["123"] = sysvar_dp  # type: ignore[assignment]

        data_points = coordinator.sysvar_data_points
        assert len(data_points) == 1
        assert sysvar_dp in data_points


class TestHubCoordinatorProgramOperations:
    """Test program-related operations."""

    def test_add_program_data_point(self) -> None:
        """Add program data point should register the program."""
        central = _FakeCentral()
        coordinator = HubCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            event_bus_provider=central,
            event_publisher=central,
            parameter_visibility_provider=central.cache_coordinator.parameter_visibility,
            paramset_description_provider=central.cache_coordinator.paramset_descriptions,
            primary_client_provider=central,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        program_dp = _FakeProgramDpType(pid="123")
        coordinator.add_program_data_point(program_dp=program_dp)

        # Should be registered
        assert "123" in coordinator._program_data_points
        assert coordinator._program_data_points["123"] == program_dp

    @pytest.mark.asyncio
    async def test_execute_program_no_client(self) -> None:
        """Execute program should return False when no primary client."""
        central = _FakeCentral()
        coordinator = HubCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            event_bus_provider=central,
            event_publisher=central,
            parameter_visibility_provider=central.cache_coordinator.parameter_visibility,
            paramset_description_provider=central.cache_coordinator.paramset_descriptions,
            primary_client_provider=central,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        result = await coordinator.execute_program(pid="123")
        assert result is False

    @pytest.mark.asyncio
    async def test_execute_program_success(self) -> None:
        """Execute program should call client method."""
        central = _FakeCentral()
        central._primary_client = _FakeClient()

        coordinator = HubCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            event_bus_provider=central,
            event_publisher=central,
            parameter_visibility_provider=central.cache_coordinator.parameter_visibility,
            paramset_description_provider=central.cache_coordinator.paramset_descriptions,
            primary_client_provider=central,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        result = await coordinator.execute_program(pid="123")
        assert result is True

    @pytest.mark.asyncio
    async def test_fetch_program_data(self) -> None:
        """Fetch program data should call hub method."""
        central = _FakeCentral()
        coordinator = HubCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            event_bus_provider=central,
            event_publisher=central,
            parameter_visibility_provider=central.cache_coordinator.parameter_visibility,
            paramset_description_provider=central.cache_coordinator.paramset_descriptions,
            primary_client_provider=central,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        coordinator._hub = _FakeHub()
        coordinator._hub.fetch_program_data = AsyncMock()  # type: ignore[method-assign]

        await coordinator.fetch_program_data(scheduled=True)

        coordinator._hub.fetch_program_data.assert_called_once_with(scheduled=True)

    def test_get_program_data_point_by_legacy_name(self) -> None:
        """Get program data point should return program by legacy name."""
        central = _FakeCentral()
        coordinator = HubCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            event_bus_provider=central,
            event_publisher=central,
            parameter_visibility_provider=central.cache_coordinator.parameter_visibility,
            paramset_description_provider=central.cache_coordinator.paramset_descriptions,
            primary_client_provider=central,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        program_dp = _FakeProgramDpType(pid="123")
        coordinator.add_program_data_point(program_dp=program_dp)

        retrieved = coordinator.get_program_data_point(legacy_name=program_dp.button.legacy_name)
        assert retrieved == program_dp

    def test_get_program_data_point_by_pid(self) -> None:
        """Get program data point should return program by PID."""
        central = _FakeCentral()
        coordinator = HubCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            event_bus_provider=central,
            event_publisher=central,
            parameter_visibility_provider=central.cache_coordinator.parameter_visibility,
            paramset_description_provider=central.cache_coordinator.paramset_descriptions,
            primary_client_provider=central,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        program_dp = _FakeProgramDpType(pid="123")
        coordinator.add_program_data_point(program_dp=program_dp)

        retrieved = coordinator.get_program_data_point(pid="123")
        assert retrieved == program_dp

    def test_get_program_data_point_not_found(self) -> None:
        """Get program data point should return None when not found."""
        central = _FakeCentral()
        coordinator = HubCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            event_bus_provider=central,
            event_publisher=central,
            parameter_visibility_provider=central.cache_coordinator.parameter_visibility,
            paramset_description_provider=central.cache_coordinator.paramset_descriptions,
            primary_client_provider=central,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        retrieved = coordinator.get_program_data_point(pid="999")
        assert retrieved is None

    def test_remove_program_button(self) -> None:
        """Remove program button should unsubscribe the program."""
        central = _FakeCentral()
        coordinator = HubCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            event_bus_provider=central,
            event_publisher=central,
            parameter_visibility_provider=central.cache_coordinator.parameter_visibility,
            paramset_description_provider=central.cache_coordinator.paramset_descriptions,
            primary_client_provider=central,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        program_dp = _FakeProgramDpType(pid="123")
        program_dp.button.publish_device_removed_event = MagicMock()  # type: ignore[method-assign]
        program_dp.switch.publish_device_removed_event = MagicMock()  # type: ignore[method-assign]

        coordinator.add_program_data_point(program_dp=program_dp)
        assert "123" in coordinator._program_data_points

        coordinator.remove_program_button(pid="123")

        # Should be removed
        assert "123" not in coordinator._program_data_points
        # Device removed events should have been published
        program_dp.button.publish_device_removed_event.assert_called_once()
        program_dp.switch.publish_device_removed_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_program_state_no_client(self) -> None:
        """Set program state should return False when no primary client."""
        central = _FakeCentral()
        coordinator = HubCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            event_bus_provider=central,
            event_publisher=central,
            parameter_visibility_provider=central.cache_coordinator.parameter_visibility,
            paramset_description_provider=central.cache_coordinator.paramset_descriptions,
            primary_client_provider=central,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        result = await coordinator.set_program_state(pid="123", state=True)
        assert result is False

    @pytest.mark.asyncio
    async def test_set_program_state_success(self) -> None:
        """Set program state should call client method."""
        central = _FakeCentral()
        central._primary_client = _FakeClient()

        coordinator = HubCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            event_bus_provider=central,
            event_publisher=central,
            parameter_visibility_provider=central.cache_coordinator.parameter_visibility,
            paramset_description_provider=central.cache_coordinator.paramset_descriptions,
            primary_client_provider=central,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        result = await coordinator.set_program_state(pid="123", state=True)
        assert result is True


class TestHubCoordinatorSysvarOperations:
    """Test system variable-related operations."""

    def test_add_sysvar_data_point(self) -> None:
        """Add sysvar data point should register the sysvar and subscribe to events."""
        central = _FakeCentral()
        coordinator = HubCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            event_bus_provider=central,
            event_publisher=central,
            parameter_visibility_provider=central.cache_coordinator.parameter_visibility,
            paramset_description_provider=central.cache_coordinator.paramset_descriptions,
            primary_client_provider=central,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        sysvar_dp = _FakeSysvarDataPoint(vid="123", name="test", category=DataPointCategory.HUB_SENSOR)
        coordinator.add_sysvar_data_point(sysvar_data_point=sysvar_dp)

        # Should be registered
        assert "123" in coordinator._sysvar_data_points
        assert coordinator._sysvar_data_points["123"] == sysvar_dp

        # Should have subscribed via EventBus (using the new pattern)
        from aiohomematic.central.event_bus import SysvarUpdatedEvent

        central.event_bus.subscribe.assert_called_once()
        call_args = central.event_bus.subscribe.call_args
        assert call_args.kwargs["event_type"] == SysvarUpdatedEvent

    @pytest.mark.asyncio
    async def test_fetch_sysvar_data(self) -> None:
        """Fetch sysvar data should call hub method."""
        central = _FakeCentral()
        coordinator = HubCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            event_bus_provider=central,
            event_publisher=central,
            parameter_visibility_provider=central.cache_coordinator.parameter_visibility,
            paramset_description_provider=central.cache_coordinator.paramset_descriptions,
            primary_client_provider=central,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        coordinator._hub = _FakeHub()
        coordinator._hub.fetch_sysvar_data = AsyncMock()  # type: ignore[method-assign]

        await coordinator.fetch_sysvar_data(scheduled=True)

        coordinator._hub.fetch_sysvar_data.assert_called_once_with(scheduled=True)

    @pytest.mark.asyncio
    async def test_get_system_variable_no_client(self) -> None:
        """Get system variable should return None when no primary client."""
        central = _FakeCentral()
        coordinator = HubCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            event_bus_provider=central,
            event_publisher=central,
            parameter_visibility_provider=central.cache_coordinator.parameter_visibility,
            paramset_description_provider=central.cache_coordinator.paramset_descriptions,
            primary_client_provider=central,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        result = await coordinator.get_system_variable(legacy_name="test_var")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_system_variable_success(self) -> None:
        """Get system variable should call client method."""
        central = _FakeCentral()
        central._primary_client = _FakeClient()

        coordinator = HubCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            event_bus_provider=central,
            event_publisher=central,
            parameter_visibility_provider=central.cache_coordinator.parameter_visibility,
            paramset_description_provider=central.cache_coordinator.paramset_descriptions,
            primary_client_provider=central,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        result = await coordinator.get_system_variable(legacy_name="test_var")
        assert result == 42

    def test_get_sysvar_data_point_by_legacy_name(self) -> None:
        """Get sysvar data point should return sysvar by legacy name."""
        central = _FakeCentral()
        coordinator = HubCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            event_bus_provider=central,
            event_publisher=central,
            parameter_visibility_provider=central.cache_coordinator.parameter_visibility,
            paramset_description_provider=central.cache_coordinator.paramset_descriptions,
            primary_client_provider=central,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        sysvar_dp = _FakeSysvarDataPoint(vid="123", name="test", category=DataPointCategory.HUB_SENSOR)
        coordinator.add_sysvar_data_point(sysvar_data_point=sysvar_dp)

        retrieved = coordinator.get_sysvar_data_point(legacy_name=sysvar_dp.legacy_name)
        assert retrieved == sysvar_dp

    def test_get_sysvar_data_point_by_vid(self) -> None:
        """Get sysvar data point should return sysvar by VID."""
        central = _FakeCentral()
        coordinator = HubCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            event_bus_provider=central,
            event_publisher=central,
            parameter_visibility_provider=central.cache_coordinator.parameter_visibility,
            paramset_description_provider=central.cache_coordinator.paramset_descriptions,
            primary_client_provider=central,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        sysvar_dp = _FakeSysvarDataPoint(vid="123", name="test", category=DataPointCategory.HUB_SENSOR)
        coordinator.add_sysvar_data_point(sysvar_data_point=sysvar_dp)

        retrieved = coordinator.get_sysvar_data_point(vid="123")
        assert retrieved == sysvar_dp

    def test_get_sysvar_data_point_not_found(self) -> None:
        """Get sysvar data point should return None when not found."""
        central = _FakeCentral()
        coordinator = HubCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            event_bus_provider=central,
            event_publisher=central,
            parameter_visibility_provider=central.cache_coordinator.parameter_visibility,
            paramset_description_provider=central.cache_coordinator.paramset_descriptions,
            primary_client_provider=central,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        retrieved = coordinator.get_sysvar_data_point(vid="999")
        assert retrieved is None

    def test_remove_sysvar_data_point(self) -> None:
        """Remove sysvar data point should unsubscribe the sysvar and publish removed event."""
        central = _FakeCentral()
        coordinator = HubCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            event_bus_provider=central,
            event_publisher=central,
            parameter_visibility_provider=central.cache_coordinator.parameter_visibility,
            paramset_description_provider=central.cache_coordinator.paramset_descriptions,
            primary_client_provider=central,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        sysvar_dp = _FakeSysvarDataPoint(vid="123", name="test", category=DataPointCategory.HUB_SENSOR)
        sysvar_dp.publish_device_removed_event = MagicMock()  # type: ignore[method-assign]

        coordinator.add_sysvar_data_point(sysvar_data_point=sysvar_dp)
        assert "123" in coordinator._sysvar_data_points

        coordinator.remove_sysvar_data_point(vid="123")

        # Should be removed
        assert "123" not in coordinator._sysvar_data_points
        # Device removed event should have been published
        sysvar_dp.publish_device_removed_event.assert_called_once()
        # Event subscription is automatically cleaned up when sysvar_dp is deleted

    @pytest.mark.asyncio
    async def test_set_system_variable_not_found(self) -> None:
        """Set system variable should log error when sysvar not found."""
        central = _FakeCentral()
        coordinator = HubCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            event_bus_provider=central,
            event_publisher=central,
            parameter_visibility_provider=central.cache_coordinator.parameter_visibility,
            paramset_description_provider=central.cache_coordinator.paramset_descriptions,
            primary_client_provider=central,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        # Should not raise
        await coordinator.set_system_variable(legacy_name="nonexistent", value=100)

    @pytest.mark.asyncio
    async def test_set_system_variable_success(self) -> None:
        """Set system variable should call data point method."""
        central = _FakeCentral()
        coordinator = HubCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            event_bus_provider=central,
            event_publisher=central,
            parameter_visibility_provider=central.cache_coordinator.parameter_visibility,
            paramset_description_provider=central.cache_coordinator.paramset_descriptions,
            primary_client_provider=central,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        sysvar_dp = _FakeSysvarDataPoint(vid="123", name="test", category=DataPointCategory.HUB_SENSOR)
        sysvar_dp.send_variable = AsyncMock()  # type: ignore[method-assign]

        coordinator.add_sysvar_data_point(sysvar_data_point=sysvar_dp)

        await coordinator.set_system_variable(legacy_name=sysvar_dp.legacy_name, value=100)

        sysvar_dp.send_variable.assert_called_once_with(value=100)


class TestHubCoordinatorGetHubDataPoints:
    """Test get_hub_data_points filtering."""

    def test_get_hub_data_points_filter_by_category(self) -> None:
        """Get hub data points should filter by category."""
        central = _FakeCentral()
        coordinator = HubCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            event_bus_provider=central,
            event_publisher=central,
            parameter_visibility_provider=central.cache_coordinator.parameter_visibility,
            paramset_description_provider=central.cache_coordinator.paramset_descriptions,
            primary_client_provider=central,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        program_dp = _FakeProgramDpType(pid="123")
        sysvar_dp = _FakeSysvarDataPoint(vid="456", name="test", category=DataPointCategory.HUB_SENSOR)

        coordinator.add_program_data_point(program_dp=program_dp)
        coordinator.add_sysvar_data_point(sysvar_data_point=sysvar_dp)

        data_points = coordinator.get_hub_data_points(category=DataPointCategory.HUB_SENSOR)
        assert len(data_points) == 1
        assert sysvar_dp in data_points

    def test_get_hub_data_points_filter_by_registered(self) -> None:
        """Get hub data points should filter by registration status."""
        central = _FakeCentral()
        coordinator = HubCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            event_bus_provider=central,
            event_publisher=central,
            parameter_visibility_provider=central.cache_coordinator.parameter_visibility,
            paramset_description_provider=central.cache_coordinator.paramset_descriptions,
            primary_client_provider=central,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        program_dp = _FakeProgramDpType(pid="123")
        program_dp.button.is_registered = False
        program_dp.switch.is_registered = True

        sysvar_dp = _FakeSysvarDataPoint(vid="456", name="test", category=DataPointCategory.HUB_SENSOR)
        sysvar_dp.is_registered = True

        coordinator.add_program_data_point(program_dp=program_dp)
        coordinator.add_sysvar_data_point(sysvar_data_point=sysvar_dp)

        data_points = coordinator.get_hub_data_points(registered=True)
        assert len(data_points) == 2  # switch + sysvar
        assert program_dp.button not in data_points
        assert program_dp.switch in data_points
        assert sysvar_dp in data_points

    def test_get_hub_data_points_no_filter(self) -> None:
        """Get hub data points should return all data points when no filter."""
        central = _FakeCentral()
        coordinator = HubCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            event_bus_provider=central,
            event_publisher=central,
            parameter_visibility_provider=central.cache_coordinator.parameter_visibility,
            paramset_description_provider=central.cache_coordinator.paramset_descriptions,
            primary_client_provider=central,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        program_dp = _FakeProgramDpType(pid="123")
        sysvar_dp = _FakeSysvarDataPoint(vid="456", name="test", category=DataPointCategory.HUB_SENSOR)

        coordinator.add_program_data_point(program_dp=program_dp)
        coordinator.add_sysvar_data_point(sysvar_data_point=sysvar_dp)

        data_points = coordinator.get_hub_data_points()
        assert len(data_points) == 3  # 2 program (button + switch) + 1 sysvar


class TestHubCoordinatorInitHub:
    """Test hub initialization."""

    @pytest.mark.asyncio
    async def test_init_hub(self) -> None:
        """Init hub should fetch program and sysvar data."""
        central = _FakeCentral()
        coordinator = HubCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            event_bus_provider=central,
            event_publisher=central,
            parameter_visibility_provider=central.cache_coordinator.parameter_visibility,
            paramset_description_provider=central.cache_coordinator.paramset_descriptions,
            primary_client_provider=central,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        coordinator._hub = _FakeHub()
        coordinator._hub.fetch_program_data = AsyncMock()  # type: ignore[method-assign]
        coordinator._hub.fetch_sysvar_data = AsyncMock()  # type: ignore[method-assign]

        await coordinator.init_hub()

        coordinator._hub.fetch_program_data.assert_called_once_with(scheduled=True)
        coordinator._hub.fetch_sysvar_data.assert_called_once_with(scheduled=True)


class TestHubCoordinatorIntegration:
    """Integration tests for HubCoordinator."""

    @pytest.mark.asyncio
    async def test_full_program_lifecycle(self) -> None:
        """Test full program lifecycle (add, execute, remove)."""
        central = _FakeCentral()
        central._primary_client = _FakeClient()
        coordinator = HubCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            event_bus_provider=central,
            event_publisher=central,
            parameter_visibility_provider=central.cache_coordinator.parameter_visibility,
            paramset_description_provider=central.cache_coordinator.paramset_descriptions,
            primary_client_provider=central,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        # Add program
        program_dp = _FakeProgramDpType(pid="123")
        program_dp.button.publish_device_removed_event = MagicMock()  # type: ignore[method-assign]
        program_dp.switch.publish_device_removed_event = MagicMock()  # type: ignore[method-assign]

        coordinator.add_program_data_point(program_dp=program_dp)

        # Execute program
        result = await coordinator.execute_program(pid="123")
        assert result is True

        # Set program state
        result = await coordinator.set_program_state(pid="123", state=True)
        assert result is True

        # Remove program
        coordinator.remove_program_button(pid="123")
        assert coordinator.get_program_data_point(pid="123") is None

    @pytest.mark.asyncio
    async def test_full_sysvar_lifecycle(self) -> None:
        """Test full sysvar lifecycle (add, get, set, remove)."""
        central = _FakeCentral()
        central._primary_client = _FakeClient()
        coordinator = HubCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            event_bus_provider=central,
            event_publisher=central,
            parameter_visibility_provider=central.cache_coordinator.parameter_visibility,
            paramset_description_provider=central.cache_coordinator.paramset_descriptions,
            primary_client_provider=central,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        # Add sysvar
        sysvar_dp = _FakeSysvarDataPoint(vid="123", name="test", category=DataPointCategory.HUB_SENSOR)
        sysvar_dp.publish_device_removed_event = MagicMock()  # type: ignore[method-assign]
        sysvar_dp.send_variable = AsyncMock()  # type: ignore[method-assign]

        coordinator.add_sysvar_data_point(sysvar_data_point=sysvar_dp)

        # Get system variable
        result = await coordinator.get_system_variable(legacy_name=sysvar_dp.legacy_name)
        assert result == 42

        # Set system variable
        await coordinator.set_system_variable(legacy_name=sysvar_dp.legacy_name, value=100)
        sysvar_dp.send_variable.assert_called_once()

        # Remove sysvar
        coordinator.remove_sysvar_data_point(vid="123")
        assert coordinator.get_sysvar_data_point(vid="123") is None
