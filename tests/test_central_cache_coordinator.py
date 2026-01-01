# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for aiohomematic.central.cache_coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aiohomematic.central.coordinators import CacheCoordinator
from aiohomematic.central.events import CacheInvalidatedEvent, EventBus
from aiohomematic.const import CacheInvalidationReason, CacheType
from aiohomematic.store import LocalStorageFactory
from aiohomematic.store.dynamic import CentralDataCache, DeviceDetailsCache
from aiohomematic.store.persistent import DeviceDescriptionCache, ParamsetDescriptionCache, SessionRecorder
from aiohomematic_test_support.event_capture import EventCapture


class _FakeCentral:
    """Minimal fake CentralUnit for testing - implements all required protocols."""

    def __init__(self, *, name: str = "test_central", tmp_dir: str = "/tmp/test") -> None:  # noqa: S108  # nosec B108
        """Initialize a fake central."""
        self.name = name
        self.available = True
        self.model = "Test"
        self.config = MagicMock()
        self.config.cache_dir = "/tmp/test_cache"  # noqa: S108  # nosec B108
        self.config.enable_session_recording = False
        self.config.storage_directory = tmp_dir
        self.config.session_recorder_start = False
        self.config.use_caches = True
        self.primary_client = None
        self.clients = []
        self.looper = MagicMock()
        self.looper.async_add_executor_job = AsyncMock()
        # For protocol compatibility
        self.devices = ()
        self.interface_ids = frozenset()
        self.interfaces = {}  # Required by CentralDataCache.clear()
        # EventBusProviderProtocol
        self.event_bus = MagicMock()
        self.event_bus.publish = AsyncMock()
        self.event_bus.publish_sync = MagicMock()
        # Storage factory for cache coordinator
        self.storage_factory = LocalStorageFactory(
            base_directory=tmp_dir,
            central_name=name,
            task_scheduler=self.looper,
        )

    def get_client(self, *, interface_id: str) -> MagicMock | None:
        """Get client by interface_id."""
        return None

    def get_data_point(self, *, dpk: str) -> MagicMock | None:
        """Get data point by key."""
        return None

    def get_device(self, *, address: str) -> MagicMock | None:
        """Get device by address."""
        return None


class TestCacheCoordinatorBasics:
    """Test basic CacheCoordinator functionality."""

    def test_cache_coordinator_initialization(self, tmp_path) -> None:
        """CacheCoordinator should initialize with protocol interfaces."""
        central = _FakeCentral(tmp_dir=str(tmp_path))
        coordinator = CacheCoordinator(
            central_info=central,
            device_provider=central,
            client_provider=central,
            data_point_provider=central,
            event_bus_provider=central,
            primary_client_provider=central,
            config_provider=central,
            storage_factory=central.storage_factory,
            task_scheduler=central.looper,
            session_recorder_active=False,
        )  # type: ignore[arg-type]

        # Verify all cache properties are available (use public API)
        assert coordinator.data_cache is not None
        assert coordinator.device_details is not None
        assert coordinator.device_descriptions is not None
        assert coordinator.paramset_descriptions is not None

    def test_data_cache_property(self, tmp_path) -> None:
        """Data cache property should return the cache instance."""
        central = _FakeCentral(tmp_dir=str(tmp_path))
        coordinator = CacheCoordinator(
            central_info=central,
            device_provider=central,
            client_provider=central,
            data_point_provider=central,
            event_bus_provider=central,
            primary_client_provider=central,
            config_provider=central,
            storage_factory=central.storage_factory,
            task_scheduler=central.looper,
            session_recorder_active=False,
        )  # type: ignore[arg-type]

        cache = coordinator.data_cache
        assert cache is not None
        # Verify property returns same instance (consistent identity)
        assert cache is coordinator.data_cache

    def test_device_descriptions_property(self, tmp_path) -> None:
        """Device descriptions property should return the cache instance."""
        central = _FakeCentral(tmp_dir=str(tmp_path))
        coordinator = CacheCoordinator(
            central_info=central,
            device_provider=central,
            client_provider=central,
            data_point_provider=central,
            event_bus_provider=central,
            primary_client_provider=central,
            config_provider=central,
            storage_factory=central.storage_factory,
            task_scheduler=central.looper,
            session_recorder_active=False,
        )  # type: ignore[arg-type]

        cache = coordinator.device_descriptions
        assert cache is not None
        # Verify property returns same instance (consistent identity)
        assert cache is coordinator.device_descriptions

    def test_device_details_property(self, tmp_path) -> None:
        """Device details property should return the cache instance."""
        central = _FakeCentral(tmp_dir=str(tmp_path))
        coordinator = CacheCoordinator(
            central_info=central,
            device_provider=central,
            client_provider=central,
            data_point_provider=central,
            event_bus_provider=central,
            primary_client_provider=central,
            config_provider=central,
            storage_factory=central.storage_factory,
            task_scheduler=central.looper,
            session_recorder_active=False,
        )  # type: ignore[arg-type]

        cache = coordinator.device_details
        assert cache is not None
        # Verify property returns same instance (consistent identity)
        assert cache is coordinator.device_details

    def test_paramset_descriptions_property(self, tmp_path) -> None:
        """Paramset descriptions property should return the cache instance."""
        central = _FakeCentral(tmp_dir=str(tmp_path))
        coordinator = CacheCoordinator(
            central_info=central,
            device_provider=central,
            client_provider=central,
            data_point_provider=central,
            event_bus_provider=central,
            primary_client_provider=central,
            config_provider=central,
            storage_factory=central.storage_factory,
            task_scheduler=central.looper,
            session_recorder_active=False,
        )  # type: ignore[arg-type]

        cache = coordinator.paramset_descriptions
        assert cache is not None
        # Verify property returns same instance (consistent identity)
        assert cache is coordinator.paramset_descriptions


class TestCacheCoordinatorClearOperations:
    """Test cache clearing operations."""

    @pytest.mark.asyncio
    async def test_clear_all(self, tmp_path) -> None:
        """Clear all caches."""
        central = _FakeCentral(tmp_dir=str(tmp_path))

        # Mock all cache clear methods at class level
        with (
            patch.object(CentralDataCache, "clear", new=MagicMock()) as mock_data_clear,
            patch.object(DeviceDetailsCache, "clear", new=MagicMock()) as mock_details_clear,
            patch.object(DeviceDescriptionCache, "clear", new=AsyncMock()) as mock_desc_clear,
            patch.object(ParamsetDescriptionCache, "clear", new=AsyncMock()) as mock_param_clear,
            patch.object(SessionRecorder, "clear", new=AsyncMock()),
        ):
            coordinator = CacheCoordinator(
                central_info=central,
                device_provider=central,
                client_provider=central,
                data_point_provider=central,
                event_bus_provider=central,
                primary_client_provider=central,
                config_provider=central,
                storage_factory=central.storage_factory,
                task_scheduler=central.looper,
                session_recorder_active=False,
            )  # type: ignore[arg-type]
            await coordinator.clear_all()

            # All caches should have been cleared
            mock_data_clear.assert_called_once()
            mock_details_clear.assert_called_once()
            mock_desc_clear.assert_called_once()
            mock_param_clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_all_handles_exceptions(self, tmp_path) -> None:
        """Clear all should handle exceptions gracefully."""
        central = _FakeCentral(tmp_dir=str(tmp_path))

        # Mock one cache to raise an exception
        with (
            patch.object(CentralDataCache, "clear", new=MagicMock(side_effect=RuntimeError("Cache error"))),
            patch.object(DeviceDetailsCache, "clear", new=MagicMock()),
            patch.object(SessionRecorder, "clear", new=AsyncMock()),
        ):
            coordinator = CacheCoordinator(
                central_info=central,
                device_provider=central,
                client_provider=central,
                data_point_provider=central,
                event_bus_provider=central,
                primary_client_provider=central,
                config_provider=central,
                storage_factory=central.storage_factory,
                task_scheduler=central.looper,
                session_recorder_active=False,
            )  # type: ignore[arg-type]
            # Should raise the exception since there's no exception handling
            with pytest.raises(RuntimeError, match="Cache error"):
                await coordinator.clear_all()


class TestCacheCoordinatorLoadOperations:
    """Test cache loading operations."""

    @pytest.mark.asyncio
    async def test_load_all(self, tmp_path) -> None:
        """Load all caches."""
        central = _FakeCentral(tmp_dir=str(tmp_path))

        # Mock all cache load methods
        with (
            patch.object(DeviceDescriptionCache, "load", new=AsyncMock()) as mock_desc_load,
            patch.object(ParamsetDescriptionCache, "load", new=AsyncMock()) as mock_param_load,
            patch.object(DeviceDetailsCache, "load", new=AsyncMock()),
            patch.object(CentralDataCache, "load", new=AsyncMock()),
        ):
            coordinator = CacheCoordinator(
                central_info=central,
                device_provider=central,
                client_provider=central,
                data_point_provider=central,
                event_bus_provider=central,
                primary_client_provider=central,
                config_provider=central,
                storage_factory=central.storage_factory,
                task_scheduler=central.looper,
                session_recorder_active=False,
            )  # type: ignore[arg-type]
            await coordinator.load_all()

            # Persistent caches should have been loaded
            mock_desc_load.assert_called_once()
            mock_param_load.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_all_handles_exceptions(self, tmp_path) -> None:
        """Load all should raise exceptions from cache loads."""
        central = _FakeCentral(tmp_dir=str(tmp_path))

        # Mock one cache to raise an exception
        with (
            patch.object(DeviceDescriptionCache, "load", new=AsyncMock(side_effect=RuntimeError("Load error"))),
            patch.object(ParamsetDescriptionCache, "load", new=AsyncMock()),
            patch.object(DeviceDetailsCache, "load", new=AsyncMock()),
            patch.object(CentralDataCache, "load", new=AsyncMock()),
        ):
            coordinator = CacheCoordinator(
                central_info=central,
                device_provider=central,
                client_provider=central,
                data_point_provider=central,
                event_bus_provider=central,
                primary_client_provider=central,
                config_provider=central,
                storage_factory=central.storage_factory,
                task_scheduler=central.looper,
                session_recorder_active=False,
            )  # type: ignore[arg-type]
            # Should raise the exception since there's no exception handling
            with pytest.raises(RuntimeError, match="Load error"):
                await coordinator.load_all()


class TestCacheCoordinatorSaveOperations:
    """Test cache saving operations."""

    @pytest.mark.asyncio
    async def test_save_all(self, tmp_path) -> None:
        """Save all caches."""
        central = _FakeCentral(tmp_dir=str(tmp_path))

        # Mock all cache save methods
        with (
            patch.object(DeviceDescriptionCache, "save", new=AsyncMock()) as mock_desc_save,
            patch.object(ParamsetDescriptionCache, "save", new=AsyncMock()) as mock_param_save,
        ):
            coordinator = CacheCoordinator(
                central_info=central,
                device_provider=central,
                client_provider=central,
                data_point_provider=central,
                event_bus_provider=central,
                primary_client_provider=central,
                config_provider=central,
                storage_factory=central.storage_factory,
                task_scheduler=central.looper,
                session_recorder_active=False,
            )  # type: ignore[arg-type]
            await coordinator.save_all(
                save_device_descriptions=True,
                save_paramset_descriptions=True,
            )

            # Persistent caches should have been saved
            mock_desc_save.assert_called_once()
            mock_param_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_all_handles_exceptions(self, tmp_path) -> None:
        """Save all should raise exceptions from cache saves."""
        central = _FakeCentral(tmp_dir=str(tmp_path))

        # Mock one cache to raise an exception
        with (
            patch.object(DeviceDescriptionCache, "save", new=AsyncMock(side_effect=RuntimeError("Save error"))),
            patch.object(ParamsetDescriptionCache, "save", new=AsyncMock()),
        ):
            coordinator = CacheCoordinator(
                central_info=central,
                device_provider=central,
                client_provider=central,
                data_point_provider=central,
                event_bus_provider=central,
                primary_client_provider=central,
                config_provider=central,
                storage_factory=central.storage_factory,
                task_scheduler=central.looper,
                session_recorder_active=False,
            )  # type: ignore[arg-type]
            # Should raise the exception since there's no exception handling
            with pytest.raises(RuntimeError, match="Save error"):
                await coordinator.save_all(
                    save_device_descriptions=True,
                    save_paramset_descriptions=True,
                )


class TestCacheCoordinatorDeviceRemoval:
    """Test device removal from caches."""

    @pytest.mark.asyncio
    async def test_remove_device_from_caches(self, tmp_path) -> None:
        """Remove device from all caches."""
        central = _FakeCentral(tmp_dir=str(tmp_path))

        # Create a mock device
        mock_device = MagicMock()
        mock_device.address = "VCU0000001"

        # Mock cache removal methods
        with (
            patch.object(DeviceDetailsCache, "remove_device", new=MagicMock()) as mock_details_remove,
            patch.object(DeviceDescriptionCache, "remove_device", new=MagicMock()) as mock_desc_remove,
            patch.object(ParamsetDescriptionCache, "remove_device", new=MagicMock()) as mock_param_remove,
        ):
            coordinator = CacheCoordinator(
                central_info=central,
                device_provider=central,
                client_provider=central,
                data_point_provider=central,
                event_bus_provider=central,
                primary_client_provider=central,
                config_provider=central,
                storage_factory=central.storage_factory,
                task_scheduler=central.looper,
                session_recorder_active=False,
            )  # type: ignore[arg-type]
            coordinator.remove_device_from_caches(device=mock_device)  # type: ignore[arg-type]

            # All caches should have had the device removed
            mock_details_remove.assert_called_once_with(device=mock_device)
            mock_desc_remove.assert_called_once_with(device=mock_device)
            mock_param_remove.assert_called_once_with(device=mock_device)

    @pytest.mark.asyncio
    async def test_remove_device_handles_exceptions(self, tmp_path) -> None:
        """Remove device should handle exceptions gracefully."""
        central = _FakeCentral(tmp_dir=str(tmp_path))

        # Create a mock device
        mock_device = MagicMock()
        mock_device.address = "VCU0000001"

        # Mock one cache to raise an exception, others succeed
        with (
            patch.object(DeviceDetailsCache, "remove_device", new=MagicMock(side_effect=KeyError("Not found"))),
        ):
            coordinator = CacheCoordinator(
                central_info=central,
                device_provider=central,
                client_provider=central,
                data_point_provider=central,
                event_bus_provider=central,
                primary_client_provider=central,
                config_provider=central,
                storage_factory=central.storage_factory,
                task_scheduler=central.looper,
                session_recorder_active=False,
            )  # type: ignore[arg-type]
            # Should raise since there's no exception handling
            with pytest.raises(KeyError):
                coordinator.remove_device_from_caches(device=mock_device)  # type: ignore[arg-type]


class TestCacheCoordinatorIntegration:
    """Integration tests for CacheCoordinator."""

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, tmp_path) -> None:
        """Test concurrent cache operations."""
        import asyncio

        central = _FakeCentral(tmp_dir=str(tmp_path))

        # Mock methods with async delay
        async def mock_load() -> None:
            await asyncio.sleep(0.01)

        async def mock_save() -> None:
            await asyncio.sleep(0.01)

        with (
            patch.object(DeviceDescriptionCache, "load", new=AsyncMock(side_effect=mock_load)) as mock_desc_load,
            patch.object(ParamsetDescriptionCache, "load", new=AsyncMock(side_effect=mock_load)) as mock_param_load,
            patch.object(DeviceDetailsCache, "load", new=AsyncMock()),
            patch.object(CentralDataCache, "load", new=AsyncMock()),
            patch.object(DeviceDescriptionCache, "save", new=AsyncMock(side_effect=mock_save)) as mock_desc_save,
            patch.object(ParamsetDescriptionCache, "save", new=AsyncMock(side_effect=mock_save)) as mock_param_save,
        ):
            coordinator = CacheCoordinator(
                central_info=central,
                device_provider=central,
                client_provider=central,
                data_point_provider=central,
                event_bus_provider=central,
                primary_client_provider=central,
                config_provider=central,
                storage_factory=central.storage_factory,
                task_scheduler=central.looper,
                session_recorder_active=False,
            )  # type: ignore[arg-type]
            # Run load and save concurrently
            await asyncio.gather(
                coordinator.load_all(),
                coordinator.save_all(
                    save_device_descriptions=True,
                    save_paramset_descriptions=True,
                ),
            )

            # All operations should have completed
            mock_desc_load.assert_called_once()
            mock_param_load.assert_called_once()
            mock_desc_save.assert_called_once()
            mock_param_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_full_cache_lifecycle(self, tmp_path) -> None:
        """Test full cache lifecycle (load, use, save, clear)."""
        central = _FakeCentral(tmp_dir=str(tmp_path))

        # Mock all methods
        with (
            patch.object(DeviceDescriptionCache, "load", new=AsyncMock()) as mock_desc_load,
            patch.object(ParamsetDescriptionCache, "load", new=AsyncMock()) as mock_param_load,
            patch.object(DeviceDetailsCache, "load", new=AsyncMock()),
            patch.object(CentralDataCache, "load", new=AsyncMock()),
            patch.object(DeviceDescriptionCache, "save", new=AsyncMock()) as mock_desc_save,
            patch.object(ParamsetDescriptionCache, "save", new=AsyncMock()) as mock_param_save,
            patch.object(CentralDataCache, "clear", new=MagicMock()) as mock_data_clear,
            patch.object(DeviceDetailsCache, "clear", new=MagicMock()) as mock_details_clear,
            patch.object(DeviceDescriptionCache, "clear", new=AsyncMock()) as mock_desc_clear,
            patch.object(ParamsetDescriptionCache, "clear", new=AsyncMock()) as mock_param_clear,
            patch.object(SessionRecorder, "clear", new=AsyncMock()),
        ):
            coordinator = CacheCoordinator(
                central_info=central,
                device_provider=central,
                client_provider=central,
                data_point_provider=central,
                event_bus_provider=central,
                primary_client_provider=central,
                config_provider=central,
                storage_factory=central.storage_factory,
                task_scheduler=central.looper,
                session_recorder_active=False,
            )  # type: ignore[arg-type]

            # Load
            await coordinator.load_all()
            mock_desc_load.assert_called_once()
            mock_param_load.assert_called_once()

            # Save
            await coordinator.save_all(
                save_device_descriptions=True,
                save_paramset_descriptions=True,
            )
            mock_desc_save.assert_called_once()
            mock_param_save.assert_called_once()

            # Clear
            await coordinator.clear_all()
            mock_data_clear.assert_called_once()
            mock_details_clear.assert_called_once()
            mock_desc_clear.assert_called_once()
            mock_param_clear.assert_called_once()


class TestCacheCoordinatorSessionRecording:
    """Test session recording cache functionality."""

    def test_session_recording_cache_when_disabled(self, tmp_path) -> None:
        """Session recording cache should be inactive when disabled."""
        central = _FakeCentral(tmp_dir=str(tmp_path))
        central.config.enable_session_recording = False
        coordinator = CacheCoordinator(
            central_info=central,
            device_provider=central,
            client_provider=central,
            data_point_provider=central,
            event_bus_provider=central,
            primary_client_provider=central,
            config_provider=central,
            storage_factory=central.storage_factory,
            task_scheduler=central.looper,
            session_recorder_active=False,
        )  # type: ignore[arg-type]

        # When session recording is disabled, recorder should be inactive (use public API)
        assert coordinator.recorder is not None
        assert coordinator.recorder.active is False

    def test_session_recording_cache_when_enabled(self, tmp_path) -> None:
        """Session recording cache should be created when enabled."""
        central = _FakeCentral(tmp_dir=str(tmp_path))
        central.config.enable_session_recording = True

        with patch("aiohomematic.central.coordinators.cache.SessionRecorder"):
            _ = CacheCoordinator(
                central_info=central,
                device_provider=central,
                client_provider=central,
                data_point_provider=central,
                event_bus_provider=central,
                primary_client_provider=central,
                config_provider=central,
                storage_factory=central.storage_factory,
                task_scheduler=central.looper,
                session_recorder_active=False,
            )  # type: ignore[arg-type]

            # When enabled, cache should be created (if implementation supports it)
            # This depends on actual implementation in cache_coordinator.py


class TestCacheCoordinatorEvents:
    """Test event emission from CacheCoordinator."""

    @pytest.mark.asyncio
    async def test_clear_emits_cache_invalidated_event(self, event_capture: EventCapture, tmp_path) -> None:
        """Clear should emit CacheInvalidatedEvent."""
        event_bus = EventBus()
        event_capture.subscribe_to(event_bus, CacheInvalidatedEvent)

        central = _FakeCentral(tmp_dir=str(tmp_path))
        central.event_bus = event_bus

        with (
            patch.object(CentralDataCache, "clear", new=MagicMock()),
            patch.object(DeviceDetailsCache, "clear", new=MagicMock()),
            patch.object(DeviceDescriptionCache, "clear", new=AsyncMock()),
            patch.object(ParamsetDescriptionCache, "clear", new=AsyncMock()),
            patch.object(SessionRecorder, "clear", new=AsyncMock()),
        ):
            coordinator = CacheCoordinator(
                central_info=central,
                device_provider=central,
                client_provider=central,
                data_point_provider=central,
                event_bus_provider=central,
                primary_client_provider=central,
                config_provider=central,
                storage_factory=central.storage_factory,
                task_scheduler=central.looper,
                session_recorder_active=False,
            )  # type: ignore[arg-type]

            await coordinator.clear_all(reason=CacheInvalidationReason.MANUAL)

            # Verify CacheInvalidatedEvent was emitted
            event_capture.assert_event_emitted(
                event_type=CacheInvalidatedEvent,
                cache_type=CacheType.DATA,
                reason=CacheInvalidationReason.MANUAL,
            )

    @pytest.mark.asyncio
    async def test_clear_on_stop_emits_cache_invalidated_event(self, event_capture: EventCapture, tmp_path) -> None:
        """Clear on stop should emit CacheInvalidatedEvent with SHUTDOWN reason."""
        import asyncio

        event_bus = EventBus()
        event_capture.subscribe_to(event_bus, CacheInvalidatedEvent)

        central = _FakeCentral(tmp_dir=str(tmp_path))
        central.event_bus = event_bus

        coordinator = CacheCoordinator(
            central_info=central,
            device_provider=central,
            client_provider=central,
            data_point_provider=central,
            event_bus_provider=central,
            primary_client_provider=central,
            config_provider=central,
            storage_factory=central.storage_factory,
            task_scheduler=central.looper,
            session_recorder_active=False,
        )  # type: ignore[arg-type]

        coordinator.clear_on_stop()

        # Give the event loop a chance to process the scheduled publish
        await asyncio.sleep(0.02)

        # Verify CacheInvalidatedEvent was emitted with SHUTDOWN reason
        event_capture.assert_event_emitted(
            event_type=CacheInvalidatedEvent,
            cache_type=CacheType.DATA,
            reason=CacheInvalidationReason.SHUTDOWN,
        )
