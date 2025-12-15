# SPDX-License-Identifier: MIT
"""
Tests for aiohomematic.model.hub.update.HmUpdate progress tracking.

Covers in_progress property, install() with progress monitoring,
version change detection, and timeout handling.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from aiohomematic.const import SystemUpdateData
from aiohomematic.model.hub.update import HmUpdate


class _FakeConfig:
    """Minimal fake config for testing."""

    def __init__(self) -> None:
        """Initialize fake config."""
        self.central_id = "TestCentral"


class _FakeConfigProvider:
    """Minimal fake ConfigProviderProtocol for testing."""

    def __init__(self) -> None:
        """Initialize fake config provider."""
        self.config = _FakeConfig()


class _FakeCentralInfo:
    """Minimal fake CentralInfoProtocol for testing."""

    def __init__(self) -> None:
        """Initialize fake central info."""
        self.name = "TestCentral"
        self.available = True


class _FakeEventBus:
    """Minimal fake EventBus for testing."""

    async def publish(self, *, event: Any) -> None:
        """Do nothing for publish in tests."""

    def subscribe(self, *, event_type: type, event_key: Any, handler: Callable[..., Any]) -> Callable[[], None]:
        """Return a no-op unsubscribe function."""
        return lambda: None


class _FakeEventBusProvider:
    """Minimal fake EventBusProviderProtocol for testing."""

    def __init__(self) -> None:
        """Initialize fake event bus provider."""
        self.event_bus = _FakeEventBus()


class _FakeEventPublisher:
    """Minimal fake EventPublisherProtocol for testing."""

    def publish_device_trigger_event(self, **kwargs: Any) -> None:
        """Do nothing for publish in tests."""

    def publish_system_event(self, **kwargs: Any) -> None:
        """Do nothing for publish in tests."""


class _FakeTaskScheduler:
    """Minimal fake TaskScheduler for testing."""

    def __init__(self) -> None:
        """Initialize fake task scheduler."""
        self._tasks: list[asyncio.Task[Any]] = []

    def create_task(self, *, target: Coroutine[Any, Any, None], name: str) -> None:
        """Create and track a task."""
        task = asyncio.create_task(target, name=name)
        self._tasks.append(task)


class _FakeParamsetDescriptionProvider:
    """Minimal fake ParamsetDescriptionProviderProtocol for testing."""


class _FakeParameterVisibilityProvider:
    """Minimal fake ParameterVisibilityProviderProtocol for testing."""


class _FakeClient:
    """Minimal fake Client for testing."""

    def __init__(self) -> None:
        """Initialize fake client."""
        self.trigger_firmware_update_result = True
        self.system_update_info = SystemUpdateData(
            current_firmware="3.75.6",
            available_firmware="3.77.0",
            update_available=True,
            check_script_available=True,
        )
        self.circuit_breakers_reset = False

    async def get_system_update_info(self) -> SystemUpdateData:
        """Get system update info."""
        return self.system_update_info

    def reset_circuit_breakers(self) -> None:
        """Reset circuit breakers."""
        self.circuit_breakers_reset = True

    async def trigger_firmware_update(self) -> bool:
        """Trigger firmware update."""
        return self.trigger_firmware_update_result


class _FakePrimaryClientProvider:
    """Minimal fake PrimaryClientProviderProtocol for testing."""

    def __init__(self) -> None:
        """Initialize fake primary client provider."""
        self._client: _FakeClient | None = _FakeClient()

    @property
    def primary_client(self) -> _FakeClient | None:
        """Return primary client."""
        return self._client


def _create_hm_update() -> tuple[HmUpdate, _FakePrimaryClientProvider, _FakeTaskScheduler]:
    """Create HmUpdate instance with fake dependencies."""
    config_provider = _FakeConfigProvider()
    central_info = _FakeCentralInfo()
    event_bus_provider = _FakeEventBusProvider()
    event_publisher = _FakeEventPublisher()
    task_scheduler = _FakeTaskScheduler()
    paramset_description_provider = _FakeParamsetDescriptionProvider()
    parameter_visibility_provider = _FakeParameterVisibilityProvider()
    primary_client_provider = _FakePrimaryClientProvider()

    hm_update = HmUpdate(
        config_provider=config_provider,  # type: ignore[arg-type]
        central_info=central_info,  # type: ignore[arg-type]
        event_bus_provider=event_bus_provider,  # type: ignore[arg-type]
        event_publisher=event_publisher,
        task_scheduler=task_scheduler,  # type: ignore[arg-type]
        paramset_description_provider=paramset_description_provider,  # type: ignore[arg-type]
        parameter_visibility_provider=parameter_visibility_provider,  # type: ignore[arg-type]
        primary_client_provider=primary_client_provider,  # type: ignore[arg-type]
    )

    return hm_update, primary_client_provider, task_scheduler


class TestHmUpdateProgressTracking:
    """Tests for HmUpdate progress tracking functionality."""

    def test_in_progress_initially_false(self) -> None:
        """Test that in_progress is False initially."""
        hm_update, _, _ = _create_hm_update()
        assert hm_update.in_progress is False

    def test_initial_properties(self) -> None:
        """Test initial state of HmUpdate properties."""
        hm_update, _, _ = _create_hm_update()

        assert hm_update.current_firmware == ""
        assert hm_update.available_firmware == ""
        assert hm_update.update_available is False
        assert hm_update.in_progress is False
        assert hm_update.state_uncertain is True

    @pytest.mark.asyncio
    async def test_install_no_client(self) -> None:
        """Test install() returns False when no client is available."""
        hm_update, primary_client_provider, _ = _create_hm_update()
        primary_client_provider._client = None

        result = await hm_update.install()

        assert result is False
        assert hm_update.in_progress is False

    @pytest.mark.asyncio
    async def test_install_sets_in_progress(self) -> None:
        """Test that install() sets in_progress to True."""
        hm_update, primary_client_provider, task_scheduler = _create_hm_update()

        # Set initial firmware version
        hm_update.update_data(
            data=SystemUpdateData(
                current_firmware="3.75.6",
                available_firmware="3.77.0",
                update_available=True,
                check_script_available=True,
            ),
            write_at=datetime.now(),
        )

        # Patch sleep to avoid waiting
        with patch("aiohomematic.model.hub.update.asyncio.sleep", new_callable=AsyncMock):
            result = await hm_update.install()

        assert result is True
        assert hm_update.in_progress is True
        assert hm_update._version_before_update == "3.75.6"

    @pytest.mark.asyncio
    async def test_install_trigger_failed(self) -> None:
        """Test install() when trigger_firmware_update fails."""
        hm_update, primary_client_provider, _ = _create_hm_update()
        assert primary_client_provider._client is not None
        primary_client_provider._client.trigger_firmware_update_result = False

        result = await hm_update.install()

        assert result is False
        assert hm_update.in_progress is False

    @pytest.mark.asyncio
    async def test_monitor_detects_version_change(self) -> None:
        """Test that progress monitor detects firmware version change."""
        hm_update, primary_client_provider, _ = _create_hm_update()

        # Set initial firmware version
        hm_update.update_data(
            data=SystemUpdateData(
                current_firmware="3.75.6",
                available_firmware="3.77.0",
                update_available=True,
                check_script_available=True,
            ),
            write_at=datetime.now(),
        )

        # Simulate version before update
        hm_update._version_before_update = "3.75.6"
        hm_update._update_in_progress = True

        # Update client to return new version
        assert primary_client_provider._client is not None
        primary_client_provider._client.system_update_info = SystemUpdateData(
            current_firmware="3.77.0",
            available_firmware="3.77.0",
            update_available=False,
            check_script_available=True,
        )

        # Run monitor with patched sleep (immediate return)
        with patch(
            "aiohomematic.model.hub.update.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await hm_update._monitor_update_progress()

        # Progress should be complete
        assert hm_update.in_progress is False
        assert hm_update.current_firmware == "3.77.0"
        assert hm_update.update_available is False
        # Circuit breakers should be reset after successful update
        assert primary_client_provider._client.circuit_breakers_reset is True

    @pytest.mark.asyncio
    async def test_monitor_handles_poll_error(self) -> None:
        """Test that progress monitor handles poll errors gracefully."""
        hm_update, primary_client_provider, _ = _create_hm_update()

        # Set initial state
        hm_update._version_before_update = "3.75.6"
        hm_update._update_in_progress = True

        # Make get_system_update_info raise exception first, then succeed
        assert primary_client_provider._client is not None
        call_count = 0

        async def mock_get_system_update_info() -> SystemUpdateData:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("CCU offline during reboot")
            return SystemUpdateData(
                current_firmware="3.77.0",
                available_firmware="3.77.0",
                update_available=False,
                check_script_available=True,
            )

        primary_client_provider._client.get_system_update_info = mock_get_system_update_info  # type: ignore[method-assign]

        # Run monitor with patched sleep
        with patch(
            "aiohomematic.model.hub.update.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await hm_update._monitor_update_progress()

        # Should have recovered and completed
        assert hm_update.in_progress is False
        assert call_count >= 2

    @pytest.mark.asyncio
    async def test_monitor_no_client_during_poll(self) -> None:
        """Test monitor handles client becoming unavailable."""
        hm_update, primary_client_provider, _ = _create_hm_update()

        # Set initial state
        hm_update._version_before_update = "3.75.6"
        hm_update._update_in_progress = True

        # Remove client after first poll attempt
        poll_count = 0

        original_sleep = asyncio.sleep

        async def mock_sleep(seconds: float) -> None:
            nonlocal poll_count
            poll_count += 1
            if poll_count >= 1:
                primary_client_provider._client = None
            await original_sleep(0)

        # Patch with short timeout
        with (
            patch("aiohomematic.model.hub.update.SYSTEM_UPDATE_PROGRESS_TIMEOUT", 0.1),
            patch(
                "aiohomematic.model.hub.update.asyncio.sleep",
                side_effect=mock_sleep,
            ),
        ):
            await hm_update._monitor_update_progress()

        # Should have cleaned up even without client
        assert hm_update.in_progress is False

    @pytest.mark.asyncio
    async def test_monitor_timeout(self) -> None:
        """Test that progress monitor times out correctly."""
        hm_update, primary_client_provider, _ = _create_hm_update()

        # Set initial state
        hm_update._version_before_update = "3.75.6"
        hm_update._update_in_progress = True

        # Client always returns same version (no update completion)
        assert primary_client_provider._client is not None
        primary_client_provider._client.system_update_info = SystemUpdateData(
            current_firmware="3.75.6",
            available_firmware="3.77.0",
            update_available=True,
            check_script_available=True,
        )

        # Patch timeout to be very short and sleep to be instant
        with (
            patch("aiohomematic.model.hub.update.SYSTEM_UPDATE_PROGRESS_TIMEOUT", 0.1),
            patch(
                "aiohomematic.model.hub.update.asyncio.sleep",
                new_callable=AsyncMock,
            ) as mock_sleep,
        ):
            # Make sleep simulate time passing
            async def advance_time(seconds: float) -> None:
                pass

            mock_sleep.side_effect = advance_time

            await hm_update._monitor_update_progress()

        # Should have timed out but cleaned up
        assert hm_update.in_progress is False
        assert hm_update._version_before_update is None

    def test_update_data_sets_properties(self) -> None:
        """Test that update_data correctly sets properties."""
        hm_update, _, _ = _create_hm_update()

        data = SystemUpdateData(
            current_firmware="3.75.6",
            available_firmware="3.77.0",
            update_available=True,
            check_script_available=True,
        )

        hm_update.update_data(data=data, write_at=datetime.now())

        assert hm_update.current_firmware == "3.75.6"
        assert hm_update.available_firmware == "3.77.0"
        assert hm_update.update_available is True
        assert hm_update.state_uncertain is False
