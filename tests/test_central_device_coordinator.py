"""Tests for aiohomematic.central.device_coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aiohomematic.central.device_coordinator import DeviceCoordinator
from aiohomematic.const import DeviceDescription


class _FakeChannel:
    """Minimal fake Channel for testing."""

    def __init__(self, *, address: str) -> None:
        """Initialize a fake channel."""
        self.address = address


class _FakeDevice:
    """Minimal fake Device for testing."""

    def __init__(
        self,
        *,
        address: str,
        channels: dict[str, _FakeChannel] | None = None,
        is_updatable: bool = False,
    ) -> None:
        """Initialize a fake device."""
        self.address = address
        self.channels = channels or {}
        self.is_updatable = is_updatable
        self.client = MagicMock()

    async def create_central_links(self) -> None:
        """Create central links."""

    def refresh_firmware_data(self) -> None:
        """Refresh firmware data."""

    def remove(self) -> None:
        """Remove device."""

    async def remove_central_links(self) -> None:
        """Remove central links."""


class _FakeDeviceRegistry:
    """Minimal fake DeviceRegistry for testing."""

    def __init__(self) -> None:
        """Initialize a fake device registry."""
        self._devices: dict[str, _FakeDevice] = {}

    @property
    def devices(self) -> tuple[_FakeDevice, ...]:
        """Return all devices."""
        return tuple(self._devices.values())

    def add_device(self, *, device: _FakeDevice) -> None:
        """Add device to registry."""
        self._devices[device.address] = device

    def get_channel(self, *, channel_address: str) -> _FakeChannel | None:
        """Get channel by address."""
        device_address = channel_address.split(":")[0]
        if device := self._devices.get(device_address):
            return device.channels.get(channel_address)
        return None

    def get_device(self, *, address: str) -> _FakeDevice | None:
        """Get device by address."""
        # Handle channel addresses
        if ":" in address:
            address = address.split(":")[0]
        return self._devices.get(address)

    def get_virtual_remotes(self) -> tuple[_FakeDevice, ...]:
        """Get virtual remotes."""
        return ()

    def has_device(self, *, address: str) -> bool:
        """Check if device exists."""
        return address in self._devices

    def identify_channel(self, *, text: str) -> _FakeChannel | None:
        """Identify channel in text."""
        for device in self._devices.values():
            for channel in device.channels.values():
                if channel.address in text:
                    return channel
        return None

    def remove_device(self, *, device_address: str) -> None:
        """Remove device from registry."""
        if device_address in self._devices:
            del self._devices[device_address]


class _FakeClient:
    """Minimal fake Client for testing."""

    def __init__(self, *, interface_id: str) -> None:
        """Initialize a fake client."""
        self.interface_id = interface_id

    async def accept_device_in_inbox(self, *, device_address: str) -> bool:
        """Accept a device from the inbox."""
        return True

    async def get_all_device_descriptions(
        self,
        *,
        device_address: str | None = None,
    ) -> tuple[DeviceDescription, ...]:
        """Get all device descriptions."""
        if device_address == "VCU0000001":
            return (
                DeviceDescription(
                    interface_id=self.interface_id,
                    address="VCU0000001",
                    type="HM-LC-Sw1-Pl",
                    paramsets=["MASTER", "VALUES"],
                ),
            )
        return ()


class _FakeCacheCoordinator:
    """Minimal fake CacheCoordinator for testing."""

    def __init__(self) -> None:
        """Initialize fake cache coordinator."""
        self.device_descriptions = MagicMock()
        self.device_descriptions.has_device_descriptions = MagicMock(return_value=True)
        self.device_descriptions.get_raw_device_descriptions = MagicMock(return_value=[])
        self.remove_device_from_caches = MagicMock()
        self.save_all = AsyncMock()


class _FakeClientCoordinator:
    """Minimal fake ClientCoordinator for testing."""

    def __init__(self) -> None:
        """Initialize fake client coordinator."""
        self._clients: dict[str, _FakeClient] = {}

    @property
    def clients(self) -> tuple[_FakeClient, ...]:
        """Return all clients."""
        return tuple(self._clients.values())

    def add_client(self, *, client: _FakeClient) -> None:
        """Add client."""
        self._clients[client.interface_id] = client

    def get_client(self, *, interface_id: str) -> _FakeClient:
        """Get client by interface ID."""
        return self._clients[interface_id]

    def has_client(self, *, interface_id: str) -> bool:
        """Check if client exists."""
        return interface_id in self._clients


class _FakeCentral:
    """Minimal fake CentralUnit for testing."""

    def __init__(self, *, name: str = "test_central") -> None:
        """Initialize a fake central."""
        self.name = name
        self.device_registry = _FakeDeviceRegistry()
        self.cache_coordinator = _FakeCacheCoordinator()
        self.client_coordinator = _FakeClientCoordinator()
        # Add protocol interface mocks
        self.data_cache = MagicMock()
        self.device_descriptions = MagicMock()
        self.device_details = MagicMock()
        self.event_bus = MagicMock()
        self.parameter_visibility = MagicMock()
        self.paramset_descriptions = MagicMock()
        self.looper = MagicMock()


class TestDeviceCoordinatorBasics:
    """Test basic DeviceCoordinator functionality."""

    def test_device_coordinator_initialization(self) -> None:
        """DeviceCoordinator should initialize with central instance."""
        central = _FakeCentral()
        coordinator = DeviceCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            coordinator_provider=central,
            data_cache_provider=central.data_cache,
            data_point_provider=central,
            device_data_refresher=central,
            device_description_provider=central.device_descriptions,
            device_details_provider=central.device_details,
            event_bus_provider=central,
            event_publisher=central,
            event_subscription_manager=central,
            file_operations=central,
            parameter_visibility_provider=central.parameter_visibility,
            paramset_description_provider=central.paramset_descriptions,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        assert coordinator._central_info == central
        assert coordinator._device_add_semaphore is not None

    def test_device_registry_property(self) -> None:
        """Device registry property should return the registry."""
        central = _FakeCentral()
        coordinator = DeviceCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            coordinator_provider=central,
            data_cache_provider=central.data_cache,
            data_point_provider=central,
            device_data_refresher=central,
            device_description_provider=central.device_descriptions,
            device_details_provider=central.device_details,
            event_bus_provider=central,
            event_publisher=central,
            event_subscription_manager=central,
            file_operations=central,
            parameter_visibility_provider=central.parameter_visibility,
            paramset_description_provider=central.paramset_descriptions,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        registry = coordinator.device_registry
        assert registry == central.device_registry

    def test_devices_property(self) -> None:
        """Devices property should return all devices from registry."""
        central = _FakeCentral()
        coordinator = DeviceCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            coordinator_provider=central,
            data_cache_provider=central.data_cache,
            data_point_provider=central,
            device_data_refresher=central,
            device_description_provider=central.device_descriptions,
            device_details_provider=central.device_details,
            event_bus_provider=central,
            event_publisher=central,
            event_subscription_manager=central,
            file_operations=central,
            parameter_visibility_provider=central.parameter_visibility,
            paramset_description_provider=central.paramset_descriptions,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        device1 = _FakeDevice(address="VCU0000001")
        device2 = _FakeDevice(address="VCU0000002")

        central.device_registry.add_device(device=device1)
        central.device_registry.add_device(device=device2)

        devices = coordinator.devices
        assert len(devices) == 2
        assert device1 in devices  # type: ignore[comparison-overlap]
        assert device2 in devices  # type: ignore[comparison-overlap]


class TestDeviceCoordinatorGetOperations:
    """Test device and channel retrieval operations."""

    def test_get_channel_not_found(self) -> None:
        """Get channel should return None when channel doesn't exist."""
        central = _FakeCentral()
        coordinator = DeviceCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            coordinator_provider=central,
            data_cache_provider=central.data_cache,
            data_point_provider=central,
            device_data_refresher=central,
            device_description_provider=central.device_descriptions,
            device_details_provider=central.device_details,
            event_bus_provider=central,
            event_publisher=central,
            event_subscription_manager=central,
            file_operations=central,
            parameter_visibility_provider=central.parameter_visibility,
            paramset_description_provider=central.paramset_descriptions,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        retrieved = coordinator.get_channel(channel_address="VCU9999999:1")
        assert retrieved is None

    def test_get_channel_success(self) -> None:
        """Get channel should return the channel when it exists."""
        central = _FakeCentral()
        coordinator = DeviceCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            coordinator_provider=central,
            data_cache_provider=central.data_cache,
            data_point_provider=central,
            device_data_refresher=central,
            device_description_provider=central.device_descriptions,
            device_details_provider=central.device_details,
            event_bus_provider=central,
            event_publisher=central,
            event_subscription_manager=central,
            file_operations=central,
            parameter_visibility_provider=central.parameter_visibility,
            paramset_description_provider=central.paramset_descriptions,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        channel = _FakeChannel(address="VCU0000001:1")
        device = _FakeDevice(address="VCU0000001", channels={"VCU0000001:1": channel})
        central.device_registry.add_device(device=device)

        retrieved = coordinator.get_channel(channel_address="VCU0000001:1")
        assert retrieved == channel

    def test_get_device_not_found(self) -> None:
        """Get device should return None when device doesn't exist."""
        central = _FakeCentral()
        coordinator = DeviceCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            coordinator_provider=central,
            data_cache_provider=central.data_cache,
            data_point_provider=central,
            device_data_refresher=central,
            device_description_provider=central.device_descriptions,
            device_details_provider=central.device_details,
            event_bus_provider=central,
            event_publisher=central,
            event_subscription_manager=central,
            file_operations=central,
            parameter_visibility_provider=central.parameter_visibility,
            paramset_description_provider=central.paramset_descriptions,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        retrieved = coordinator.get_device(address="VCU9999999")
        assert retrieved is None

    def test_get_device_success(self) -> None:
        """Get device should return the device when it exists."""
        central = _FakeCentral()
        coordinator = DeviceCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            coordinator_provider=central,
            data_cache_provider=central.data_cache,
            data_point_provider=central,
            device_data_refresher=central,
            device_description_provider=central.device_descriptions,
            device_details_provider=central.device_details,
            event_bus_provider=central,
            event_publisher=central,
            event_subscription_manager=central,
            file_operations=central,
            parameter_visibility_provider=central.parameter_visibility,
            paramset_description_provider=central.paramset_descriptions,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        device = _FakeDevice(address="VCU0000001")
        central.device_registry.add_device(device=device)

        retrieved = coordinator.get_device(address="VCU0000001")
        assert retrieved == device

    def test_get_virtual_remotes(self) -> None:
        """Get virtual remotes should return virtual remote devices."""
        central = _FakeCentral()
        coordinator = DeviceCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            coordinator_provider=central,
            data_cache_provider=central.data_cache,
            data_point_provider=central,
            device_data_refresher=central,
            device_description_provider=central.device_descriptions,
            device_details_provider=central.device_details,
            event_bus_provider=central,
            event_publisher=central,
            event_subscription_manager=central,
            file_operations=central,
            parameter_visibility_provider=central.parameter_visibility,
            paramset_description_provider=central.paramset_descriptions,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        remotes = coordinator.get_virtual_remotes()
        assert isinstance(remotes, tuple)

    def test_identify_channel_not_found(self) -> None:
        """Identify channel should return None when no match found."""
        central = _FakeCentral()
        coordinator = DeviceCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            coordinator_provider=central,
            data_cache_provider=central.data_cache,
            data_point_provider=central,
            device_data_refresher=central,
            device_description_provider=central.device_descriptions,
            device_details_provider=central.device_details,
            event_bus_provider=central,
            event_publisher=central,
            event_subscription_manager=central,
            file_operations=central,
            parameter_visibility_provider=central.parameter_visibility,
            paramset_description_provider=central.paramset_descriptions,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        identified = coordinator.identify_channel(text="No channel address here")
        assert identified is None

    def test_identify_channel_success(self) -> None:
        """Identify channel should find channel in text."""
        central = _FakeCentral()
        coordinator = DeviceCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            coordinator_provider=central,
            data_cache_provider=central.data_cache,
            data_point_provider=central,
            device_data_refresher=central,
            device_description_provider=central.device_descriptions,
            device_details_provider=central.device_details,
            event_bus_provider=central,
            event_publisher=central,
            event_subscription_manager=central,
            file_operations=central,
            parameter_visibility_provider=central.parameter_visibility,
            paramset_description_provider=central.paramset_descriptions,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        channel = _FakeChannel(address="VCU0000001:1")
        device = _FakeDevice(address="VCU0000001", channels={"VCU0000001:1": channel})
        central.device_registry.add_device(device=device)

        identified = coordinator.identify_channel(text="Channel VCU0000001:1 is active")
        assert identified == channel


class TestDeviceCoordinatorRemoveOperations:
    """Test device removal operations."""

    @pytest.mark.asyncio
    async def test_delete_device(self) -> None:
        """Delete device should remove device and its channels."""
        central = _FakeCentral()

        channel = _FakeChannel(address="VCU0000001:1")
        device = _FakeDevice(address="VCU0000001", channels={"VCU0000001:1": channel})
        device.remove = MagicMock()  # type: ignore[method-assign]

        central.device_registry.add_device(device=device)

        # Mock delete_devices at class level
        with patch.object(DeviceCoordinator, "delete_devices", new=AsyncMock()) as mock_delete:
            coordinator = DeviceCoordinator(
                central_info=central,
                channel_lookup=central,
                client_provider=central,
                config_provider=central,
                coordinator_provider=central,
                data_cache_provider=central.data_cache,
                data_point_provider=central,
                device_data_refresher=central,
                device_description_provider=central.device_descriptions,
                device_details_provider=central.device_details,
                event_bus_provider=central,
                event_publisher=central,
                event_subscription_manager=central,
                file_operations=central,
                parameter_visibility_provider=central.parameter_visibility,
                paramset_description_provider=central.paramset_descriptions,
                task_scheduler=central.looper,
            )  # type: ignore[arg-type]
            await coordinator.delete_device(interface_id="BidCos-RF", device_address="VCU0000001")

            # Should have called delete_devices with device and channel addresses
            mock_delete.assert_called_once()
            call_args = mock_delete.call_args
            assert "VCU0000001" in call_args.kwargs["addresses"]
            assert "VCU0000001:1" in call_args.kwargs["addresses"]

    @pytest.mark.asyncio
    async def test_delete_device_not_found(self) -> None:
        """Delete device should handle device not found gracefully."""
        central = _FakeCentral()
        coordinator = DeviceCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            coordinator_provider=central,
            data_cache_provider=central.data_cache,
            data_point_provider=central,
            device_data_refresher=central,
            device_description_provider=central.device_descriptions,
            device_details_provider=central.device_details,
            event_bus_provider=central,
            event_publisher=central,
            event_subscription_manager=central,
            file_operations=central,
            parameter_visibility_provider=central.parameter_visibility,
            paramset_description_provider=central.paramset_descriptions,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        # Should not raise
        await coordinator.delete_device(interface_id="BidCos-RF", device_address="VCU9999999")

    @pytest.mark.asyncio
    async def test_delete_devices(self) -> None:
        """Delete devices should remove multiple devices."""
        central = _FakeCentral()
        coordinator = DeviceCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            coordinator_provider=central,
            data_cache_provider=central.data_cache,
            data_point_provider=central,
            device_data_refresher=central,
            device_description_provider=central.device_descriptions,
            device_details_provider=central.device_details,
            event_bus_provider=central,
            event_publisher=central,
            event_subscription_manager=central,
            file_operations=central,
            parameter_visibility_provider=central.parameter_visibility,
            paramset_description_provider=central.paramset_descriptions,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        device1 = _FakeDevice(address="VCU0000001")
        device2 = _FakeDevice(address="VCU0000002")

        device1.remove = MagicMock()  # type: ignore[method-assign]
        device2.remove = MagicMock()  # type: ignore[method-assign]

        central.device_registry.add_device(device=device1)
        central.device_registry.add_device(device=device2)

        await coordinator.delete_devices(
            interface_id="BidCos-RF",
            addresses=("VCU0000001", "VCU0000002"),
        )

        # Both devices should be removed
        assert central.device_registry.has_device(address="VCU0000001") is False
        assert central.device_registry.has_device(address="VCU0000002") is False

        # Caches should be saved
        central.cache_coordinator.save_all.assert_called_once()

    def test_remove_device_not_registered(self) -> None:
        """Remove device should handle device not in registry gracefully."""
        central = _FakeCentral()
        coordinator = DeviceCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            coordinator_provider=central,
            data_cache_provider=central.data_cache,
            data_point_provider=central,
            device_data_refresher=central,
            device_description_provider=central.device_descriptions,
            device_details_provider=central.device_details,
            event_bus_provider=central,
            event_publisher=central,
            event_subscription_manager=central,
            file_operations=central,
            parameter_visibility_provider=central.parameter_visibility,
            paramset_description_provider=central.paramset_descriptions,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        device = _FakeDevice(address="VCU9999999")

        # Should not raise
        coordinator.remove_device(device=device)

    def test_remove_device_success(self) -> None:
        """Remove device should remove device from registry and caches."""
        central = _FakeCentral()
        coordinator = DeviceCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            coordinator_provider=central,
            data_cache_provider=central.data_cache,
            data_point_provider=central,
            device_data_refresher=central,
            device_description_provider=central.device_descriptions,
            device_details_provider=central.device_details,
            event_bus_provider=central,
            event_publisher=central,
            event_subscription_manager=central,
            file_operations=central,
            parameter_visibility_provider=central.parameter_visibility,
            paramset_description_provider=central.paramset_descriptions,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        device = _FakeDevice(address="VCU0000001")
        device.remove = MagicMock()  # type: ignore[method-assign]

        central.device_registry.add_device(device=device)
        assert central.device_registry.has_device(address="VCU0000001") is True

        coordinator.remove_device(device=device)

        # Device should be removed from registry
        assert central.device_registry.has_device(address="VCU0000001") is False
        # Remove method should have been called
        device.remove.assert_called_once()
        # Caches should have been updated
        central.cache_coordinator.remove_device_from_caches.assert_called_once()


class TestDeviceCoordinatorDeviceCreation:
    """Test device creation operations."""

    @pytest.mark.asyncio
    async def test_add_new_device_manually_no_client(self) -> None:
        """Add new device manually should fail gracefully when client doesn't exist."""
        central = _FakeCentral()

        # Mock _add_new_devices to ensure it's not called
        with patch.object(DeviceCoordinator, "_add_new_devices", new=AsyncMock()) as mock_add:
            coordinator = DeviceCoordinator(
                central_info=central,
                channel_lookup=central,
                client_provider=central,
                config_provider=central,
                coordinator_provider=central,
                data_cache_provider=central.data_cache,
                data_point_provider=central,
                device_data_refresher=central,
                device_description_provider=central.device_descriptions,
                device_details_provider=central.device_details,
                event_bus_provider=central,
                event_publisher=central,
                event_subscription_manager=central,
                file_operations=central,
                parameter_visibility_provider=central.parameter_visibility,
                paramset_description_provider=central.paramset_descriptions,
                task_scheduler=central.looper,
            )  # type: ignore[arg-type]
            await coordinator.add_new_devices_manually(
                interface_id="NonExistent",
                address_names={"VCU0000001": None},
            )

            # Should not have called _add_new_devices
            mock_add.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_new_device_manually_no_descriptions(self) -> None:
        """Add new device manually should fail gracefully when no descriptions found."""
        central = _FakeCentral()

        client = _FakeClient(interface_id="BidCos-RF")
        central.client_coordinator.add_client(client=client)

        # Mock _add_new_devices to ensure it's not called
        with patch.object(DeviceCoordinator, "_add_new_devices", new=AsyncMock()) as mock_add:
            coordinator = DeviceCoordinator(
                central_info=central,
                channel_lookup=central,
                client_provider=central,
                config_provider=central,
                coordinator_provider=central,
                data_cache_provider=central.data_cache,
                data_point_provider=central,
                device_data_refresher=central,
                device_description_provider=central.device_descriptions,
                device_details_provider=central.device_details,
                event_bus_provider=central,
                event_publisher=central,
                event_subscription_manager=central,
                file_operations=central,
                parameter_visibility_provider=central.parameter_visibility,
                paramset_description_provider=central.paramset_descriptions,
                task_scheduler=central.looper,
            )  # type: ignore[arg-type]
            # Try to add device that doesn't exist
            await coordinator.add_new_devices_manually(
                interface_id="BidCos-RF",
                address_names={"VCU9999999": None},
            )

            # Should not have called _add_new_devices
            mock_add.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_new_device_manually_success(self) -> None:
        """Add new device manually should use delayed descriptions and create device."""
        central = _FakeCentral()

        client = _FakeClient(interface_id="BidCos-RF")
        central.client_coordinator.add_client(client=client)

        # Mock _add_new_devices
        with patch.object(DeviceCoordinator, "_add_new_devices", new=AsyncMock()) as mock_add:
            coordinator = DeviceCoordinator(
                central_info=central,
                channel_lookup=central,
                client_provider=central,
                config_provider=central,
                coordinator_provider=central,
                data_cache_provider=central.data_cache,
                data_point_provider=central,
                device_data_refresher=central,
                device_description_provider=central.device_descriptions,
                device_details_provider=central.device_details,
                event_bus_provider=central,
                event_publisher=central,
                event_subscription_manager=central,
                file_operations=central,
                parameter_visibility_provider=central.parameter_visibility,
                paramset_description_provider=central.paramset_descriptions,
                task_scheduler=central.looper,
            )  # type: ignore[arg-type]

            # Pre-populate delayed device descriptions (simulates delayed device creation)
            coordinator._delayed_device_descriptions["VCU0000001"] = [
                {"ADDRESS": "VCU0000001", "PARENT": "", "TYPE": "HM-Test", "CHILDREN": ["VCU0000001:1"]}
            ]

            await coordinator.add_new_devices_manually(
                interface_id="BidCos-RF",
                address_names={"VCU0000001": None},
            )

            # Should have called _add_new_devices
            mock_add.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_new_devices(self) -> None:
        """Add new devices should determine source and call _add_new_devices."""
        central = _FakeCentral()

        # Mock _add_new_devices
        with patch.object(DeviceCoordinator, "_add_new_devices", new=AsyncMock()) as mock_add:
            coordinator = DeviceCoordinator(
                central_info=central,
                channel_lookup=central,
                client_provider=central,
                config_provider=central,
                coordinator_provider=central,
                data_cache_provider=central.data_cache,
                data_point_provider=central,
                device_data_refresher=central,
                device_description_provider=central.device_descriptions,
                device_details_provider=central.device_details,
                event_bus_provider=central,
                event_publisher=central,
                event_subscription_manager=central,
                file_operations=central,
                parameter_visibility_provider=central.parameter_visibility,
                paramset_description_provider=central.paramset_descriptions,
                task_scheduler=central.looper,
            )  # type: ignore[arg-type]
            device_descriptions = (
                DeviceDescription(
                    interface_id="BidCos-RF",
                    address="VCU0000001",
                    type="HM-LC-Sw1-Pl",
                    paramsets=["MASTER", "VALUES"],
                ),
            )

            await coordinator.add_new_devices(
                interface_id="BidCos-RF",
                device_descriptions=device_descriptions,
            )

            # Should have called _add_new_devices
            mock_add.assert_called_once()


class TestDeviceCoordinatorFirmwareOperations:
    """Test firmware-related operations."""

    @pytest.mark.asyncio
    async def test_refresh_firmware_data_all_devices(self) -> None:
        """Refresh firmware data for all devices."""
        central = _FakeCentral()

        device1 = _FakeDevice(address="VCU0000001", is_updatable=True)
        device2 = _FakeDevice(address="VCU0000002", is_updatable=True)

        device1.refresh_firmware_data = MagicMock()  # type: ignore[method-assign]
        device2.refresh_firmware_data = MagicMock()  # type: ignore[method-assign]

        central.device_registry.add_device(device=device1)
        central.device_registry.add_device(device=device2)

        client = _FakeClient(interface_id="BidCos-RF")
        central.client_coordinator.add_client(client=client)

        # Mock refresh_device_descriptions_and_create_missing_devices
        with patch.object(DeviceCoordinator, "refresh_device_descriptions_and_create_missing_devices", new=AsyncMock()):
            coordinator = DeviceCoordinator(
                central_info=central,
                channel_lookup=central,
                client_provider=central,
                config_provider=central,
                coordinator_provider=central,
                data_cache_provider=central.data_cache,
                data_point_provider=central,
                device_data_refresher=central,
                device_description_provider=central.device_descriptions,
                device_details_provider=central.device_details,
                event_bus_provider=central,
                event_publisher=central,
                event_subscription_manager=central,
                file_operations=central,
                parameter_visibility_provider=central.parameter_visibility,
                paramset_description_provider=central.paramset_descriptions,
                task_scheduler=central.looper,
            )  # type: ignore[arg-type]
            await coordinator.refresh_firmware_data()

        # Should have refreshed firmware data for all devices
        device1.refresh_firmware_data.assert_called_once()
        device2.refresh_firmware_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_firmware_data_specific_device(self) -> None:
        """Refresh firmware data for a specific device."""
        central = _FakeCentral()

        device = _FakeDevice(address="VCU0000001", is_updatable=True)
        device.refresh_firmware_data = MagicMock()  # type: ignore[method-assign]

        central.device_registry.add_device(device=device)

        # Mock refresh_device_descriptions_and_create_missing_devices
        with patch.object(
            DeviceCoordinator, "refresh_device_descriptions_and_create_missing_devices", new=AsyncMock()
        ) as mock_refresh:
            coordinator = DeviceCoordinator(
                central_info=central,
                channel_lookup=central,
                client_provider=central,
                config_provider=central,
                coordinator_provider=central,
                data_cache_provider=central.data_cache,
                data_point_provider=central,
                device_data_refresher=central,
                device_description_provider=central.device_descriptions,
                device_details_provider=central.device_details,
                event_bus_provider=central,
                event_publisher=central,
                event_subscription_manager=central,
                file_operations=central,
                parameter_visibility_provider=central.parameter_visibility,
                paramset_description_provider=central.paramset_descriptions,
                task_scheduler=central.looper,
            )  # type: ignore[arg-type]
            await coordinator.refresh_firmware_data(device_address="VCU0000001")

        # Should have refreshed firmware data for the device
        device.refresh_firmware_data.assert_called_once()
        mock_refresh.assert_called_once()


class TestDeviceCoordinatorCentralLinks:
    """Test central links operations."""

    @pytest.mark.asyncio
    async def test_create_central_links(self) -> None:
        """Create central links should call create_central_links on all devices."""
        central = _FakeCentral()
        coordinator = DeviceCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            coordinator_provider=central,
            data_cache_provider=central.data_cache,
            data_point_provider=central,
            device_data_refresher=central,
            device_description_provider=central.device_descriptions,
            device_details_provider=central.device_details,
            event_bus_provider=central,
            event_publisher=central,
            event_subscription_manager=central,
            file_operations=central,
            parameter_visibility_provider=central.parameter_visibility,
            paramset_description_provider=central.paramset_descriptions,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        device1 = _FakeDevice(address="VCU0000001")
        device2 = _FakeDevice(address="VCU0000002")

        device1.create_central_links = AsyncMock()  # type: ignore[method-assign]
        device2.create_central_links = AsyncMock()  # type: ignore[method-assign]

        central.device_registry.add_device(device=device1)
        central.device_registry.add_device(device=device2)

        await coordinator.create_central_links()

        # Should have called create_central_links on all devices
        device1.create_central_links.assert_called_once()
        device2.create_central_links.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_central_links(self) -> None:
        """Remove central links should call remove_central_links on all devices."""
        central = _FakeCentral()
        coordinator = DeviceCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            coordinator_provider=central,
            data_cache_provider=central.data_cache,
            data_point_provider=central,
            device_data_refresher=central,
            device_description_provider=central.device_descriptions,
            device_details_provider=central.device_details,
            event_bus_provider=central,
            event_publisher=central,
            event_subscription_manager=central,
            file_operations=central,
            parameter_visibility_provider=central.parameter_visibility,
            paramset_description_provider=central.paramset_descriptions,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        device1 = _FakeDevice(address="VCU0000001")
        device2 = _FakeDevice(address="VCU0000002")

        device1.remove_central_links = AsyncMock()  # type: ignore[method-assign]
        device2.remove_central_links = AsyncMock()  # type: ignore[method-assign]

        central.device_registry.add_device(device=device1)
        central.device_registry.add_device(device=device2)

        await coordinator.remove_central_links()

        # Should have called remove_central_links on all devices
        device1.remove_central_links.assert_called_once()
        device2.remove_central_links.assert_called_once()


class TestDeviceCoordinatorListDevices:
    """Test list devices operation."""

    def test_list_devices(self) -> None:
        """List devices should return device descriptions from cache."""
        central = _FakeCentral()
        coordinator = DeviceCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            coordinator_provider=central,
            data_cache_provider=central.data_cache,
            data_point_provider=central,
            device_data_refresher=central,
            device_description_provider=central.device_descriptions,
            device_details_provider=central.device_details,
            event_bus_provider=central,
            event_publisher=central,
            event_subscription_manager=central,
            file_operations=central,
            parameter_visibility_provider=central.parameter_visibility,
            paramset_description_provider=central.paramset_descriptions,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        # Mock device descriptions cache
        expected_descriptions = [
            DeviceDescription(
                interface_id="BidCos-RF",
                address="VCU0000001",
                type="HM-LC-Sw1-Pl",
                paramsets=["MASTER", "VALUES"],
            ),
        ]
        central.cache_coordinator.device_descriptions.get_raw_device_descriptions = MagicMock(
            return_value=expected_descriptions
        )

        result = coordinator.list_devices(interface_id="BidCos-RF")

        assert result == expected_descriptions
        central.cache_coordinator.device_descriptions.get_raw_device_descriptions.assert_called_once_with(
            interface_id="BidCos-RF"
        )


class TestDeviceCoordinatorIntegration:
    """Integration tests for DeviceCoordinator."""

    @pytest.mark.asyncio
    async def test_full_device_lifecycle(self) -> None:
        """Test full device lifecycle (add, use, remove)."""
        central = _FakeCentral()
        coordinator = DeviceCoordinator(
            central_info=central,
            channel_lookup=central,
            client_provider=central,
            config_provider=central,
            coordinator_provider=central,
            data_cache_provider=central.data_cache,
            data_point_provider=central,
            device_data_refresher=central,
            device_description_provider=central.device_descriptions,
            device_details_provider=central.device_details,
            event_bus_provider=central,
            event_publisher=central,
            event_subscription_manager=central,
            file_operations=central,
            parameter_visibility_provider=central.parameter_visibility,
            paramset_description_provider=central.paramset_descriptions,
            task_scheduler=central.looper,
        )  # type: ignore[arg-type]

        # Add device
        device = _FakeDevice(address="VCU0000001")
        device.remove = MagicMock()  # type: ignore[method-assign]

        central.device_registry.add_device(device=device)

        # Verify device exists
        assert coordinator.get_device(address="VCU0000001") == device
        assert len(coordinator.devices) == 1

        # Remove device
        coordinator.remove_device(device=device)

        # Verify device is removed
        assert coordinator.get_device(address="VCU0000001") is None
        assert len(coordinator.devices) == 0
