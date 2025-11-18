"""Tests for aiohomematic.central.device_registry."""

from __future__ import annotations

from aiohomematic.central.device_registry import DeviceRegistry


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
    ) -> None:
        """Initialize a fake device."""
        self.address = address
        self._channels = channels or {}

    def get_channel(self, *, channel_address: str) -> _FakeChannel | None:
        """Get a channel by address."""
        return self._channels.get(channel_address)

    def identify_channel(self, *, text: str) -> _FakeChannel | None:
        """Identify a channel within text."""
        for channel in self._channels.values():
            if channel.address in text:
                return channel
        return None


class _FakeCentral:
    """Minimal fake CentralUnit for testing."""

    def __init__(self, *, name: str = "test_central") -> None:
        """Initialize a fake central."""
        self.name = name
        self.clients: list[_FakeClient] = []


class _FakeClient:
    """Minimal fake Client for testing."""

    def __init__(self, *, virtual_remote: _FakeDevice | None = None) -> None:
        """Initialize a fake client."""
        self._virtual_remote = virtual_remote

    def get_virtual_remote(self) -> _FakeDevice | None:
        """Get the virtual remote device."""
        return self._virtual_remote


class TestDeviceRegistryBasics:
    """Test basic DeviceRegistry functionality."""

    def test_add_device(self) -> None:
        """Add a device to the registry."""
        central = _FakeCentral()
        registry = DeviceRegistry(central=central)  # type: ignore[arg-type]

        device = _FakeDevice(address="VCU0000001")
        registry.add_device(device=device)  # type: ignore[arg-type]

        assert registry.device_count == 1
        assert len(registry.devices) == 1
        assert registry.devices[0].address == "VCU0000001"

    def test_add_device_overwrites_existing(self) -> None:
        """Adding a device with same address should overwrite the existing one."""
        central = _FakeCentral()
        registry = DeviceRegistry(central=central)  # type: ignore[arg-type]

        device1 = _FakeDevice(address="VCU0000001")
        device2 = _FakeDevice(address="VCU0000001")

        registry.add_device(device=device1)  # type: ignore[arg-type]
        assert registry.device_count == 1

        registry.add_device(device=device2)  # type: ignore[arg-type]
        assert registry.device_count == 1  # Still 1, not 2
        assert registry.get_device(address="VCU0000001") is device2  # type: ignore[arg-type]

    def test_add_multiple_devices(self) -> None:
        """Add multiple devices to the registry."""
        central = _FakeCentral()
        registry = DeviceRegistry(central=central)  # type: ignore[arg-type]

        device1 = _FakeDevice(address="VCU0000001")
        device2 = _FakeDevice(address="VCU0000002")
        device3 = _FakeDevice(address="VCU0000003")

        registry.add_device(device=device1)  # type: ignore[arg-type]
        registry.add_device(device=device2)  # type: ignore[arg-type]
        registry.add_device(device=device3)  # type: ignore[arg-type]

        assert registry.device_count == 3
        assert len(registry.devices) == 3

    def test_clear(self) -> None:
        """Clear all devices from the registry."""
        central = _FakeCentral()
        registry = DeviceRegistry(central=central)  # type: ignore[arg-type]

        # Add multiple devices
        for i in range(5):
            device = _FakeDevice(address=f"VCU000000{i}")
            registry.add_device(device=device)  # type: ignore[arg-type]

        assert registry.device_count == 5

        # Clear the registry
        registry.clear()

        assert registry.device_count == 0
        assert registry.devices == ()
        assert registry.get_device_addresses() == frozenset()

    def test_device_count_property(self) -> None:
        """Device count property should return correct count."""
        central = _FakeCentral()
        registry = DeviceRegistry(central=central)  # type: ignore[arg-type]

        assert registry.device_count == 0

        registry.add_device(device=_FakeDevice(address="VCU0000001"))  # type: ignore[arg-type]
        assert registry.device_count == 1

        registry.add_device(device=_FakeDevice(address="VCU0000002"))  # type: ignore[arg-type]
        assert registry.device_count == 2

        registry.remove_device(device_address="VCU0000001")
        assert registry.device_count == 1

        registry.clear()
        assert registry.device_count == 0

    def test_devices_property(self) -> None:
        """Devices property should return all devices as a tuple."""
        central = _FakeCentral()
        registry = DeviceRegistry(central=central)  # type: ignore[arg-type]

        device1 = _FakeDevice(address="VCU0000001")
        device2 = _FakeDevice(address="VCU0000002")

        registry.add_device(device=device1)  # type: ignore[arg-type]
        registry.add_device(device=device2)  # type: ignore[arg-type]

        devices = registry.devices
        assert isinstance(devices, tuple)
        assert len(devices) == 2
        assert device1 in devices  # type: ignore[comparison-overlap]
        assert device2 in devices  # type: ignore[comparison-overlap]

    def test_devices_property_returns_new_tuple(self) -> None:
        """Devices property should return a new tuple each time."""
        central = _FakeCentral()
        registry = DeviceRegistry(central=central)  # type: ignore[arg-type]

        device = _FakeDevice(address="VCU0000001")
        registry.add_device(device=device)  # type: ignore[arg-type]

        devices1 = registry.devices
        devices2 = registry.devices

        # Should be equal but not the same object
        assert devices1 == devices2
        assert devices1 is not devices2

    def test_initialization(self) -> None:
        """DeviceRegistry should initialize with empty device collection."""
        central = _FakeCentral()
        registry = DeviceRegistry(central=central)  # type: ignore[arg-type]

        assert registry.device_count == 0
        assert registry.devices == ()
        assert registry.get_device_addresses() == frozenset()


class TestDeviceRegistryGetDevice:
    """Test get_device functionality."""

    def test_get_device_after_removal(self) -> None:
        """Get device after it's been removed should return None."""
        central = _FakeCentral()
        registry = DeviceRegistry(central=central)  # type: ignore[arg-type]

        device = _FakeDevice(address="VCU0000001")
        registry.add_device(device=device)  # type: ignore[arg-type]

        registry.remove_device(device_address="VCU0000001")

        retrieved = registry.get_device(address="VCU0000001")
        assert retrieved is None

    def test_get_device_not_found(self) -> None:
        """Get device that doesn't exist should return None."""
        central = _FakeCentral()
        registry = DeviceRegistry(central=central)  # type: ignore[arg-type]

        device = _FakeDevice(address="VCU0000001")
        registry.add_device(device=device)  # type: ignore[arg-type]

        retrieved = registry.get_device(address="VCU9999999")
        assert retrieved is None

    def test_get_device_with_channel_address(self) -> None:
        """Get device using channel address (should extract device part)."""
        central = _FakeCentral()
        registry = DeviceRegistry(central=central)  # type: ignore[arg-type]

        device = _FakeDevice(address="VCU0000001")
        registry.add_device(device=device)  # type: ignore[arg-type]

        # Should work with channel address too
        retrieved = registry.get_device(address="VCU0000001:1")
        assert retrieved is device  # type: ignore[comparison-overlap]

    def test_get_device_with_device_address(self) -> None:
        """Get device using device address."""
        central = _FakeCentral()
        registry = DeviceRegistry(central=central)  # type: ignore[arg-type]

        device = _FakeDevice(address="VCU0000001")
        registry.add_device(device=device)  # type: ignore[arg-type]

        retrieved = registry.get_device(address="VCU0000001")
        assert retrieved is device  # type: ignore[comparison-overlap]


class TestDeviceRegistryGetChannel:
    """Test get_channel functionality."""

    def test_get_channel_device_not_found(self) -> None:
        """Get channel when device doesn't exist should return None."""
        central = _FakeCentral()
        registry = DeviceRegistry(central=central)  # type: ignore[arg-type]

        retrieved = registry.get_channel(channel_address="VCU9999999:1")
        assert retrieved is None

    def test_get_channel_multiple_devices(self) -> None:
        """Get channel from correct device when multiple devices exist."""
        central = _FakeCentral()
        registry = DeviceRegistry(central=central)  # type: ignore[arg-type]

        channel1 = _FakeChannel(address="VCU0000001:1")
        channel2 = _FakeChannel(address="VCU0000002:1")

        device1 = _FakeDevice(
            address="VCU0000001",
            channels={"VCU0000001:1": channel1},
        )
        device2 = _FakeDevice(
            address="VCU0000002",
            channels={"VCU0000002:1": channel2},
        )

        registry.add_device(device=device1)  # type: ignore[arg-type]
        registry.add_device(device=device2)  # type: ignore[arg-type]

        retrieved1 = registry.get_channel(channel_address="VCU0000001:1")
        retrieved2 = registry.get_channel(channel_address="VCU0000002:1")

        assert retrieved1 is channel1  # type: ignore[comparison-overlap]
        assert retrieved2 is channel2  # type: ignore[comparison-overlap]

    def test_get_channel_not_found(self) -> None:
        """Get channel that doesn't exist on device should return None."""
        central = _FakeCentral()
        registry = DeviceRegistry(central=central)  # type: ignore[arg-type]

        device = _FakeDevice(address="VCU0000001", channels={})
        registry.add_device(device=device)  # type: ignore[arg-type]

        retrieved = registry.get_channel(channel_address="VCU0000001:1")
        assert retrieved is None

    def test_get_channel_success(self) -> None:
        """Get channel from device."""
        central = _FakeCentral()
        registry = DeviceRegistry(central=central)  # type: ignore[arg-type]

        channel = _FakeChannel(address="VCU0000001:1")
        device = _FakeDevice(
            address="VCU0000001",
            channels={"VCU0000001:1": channel},
        )
        registry.add_device(device=device)  # type: ignore[arg-type]

        retrieved = registry.get_channel(channel_address="VCU0000001:1")
        assert retrieved is channel  # type: ignore[comparison-overlap]


class TestDeviceRegistryHasDevice:
    """Test has_device functionality."""

    def test_has_device_after_add_and_remove(self) -> None:
        """Has device should reflect add and remove operations."""
        central = _FakeCentral()
        registry = DeviceRegistry(central=central)  # type: ignore[arg-type]

        device = _FakeDevice(address="VCU0000001")

        # Initially not present
        assert registry.has_device(address="VCU0000001") is False

        # After adding
        registry.add_device(device=device)  # type: ignore[arg-type]
        assert registry.has_device(address="VCU0000001") is True

        # After removing
        registry.remove_device(device_address="VCU0000001")
        assert registry.has_device(address="VCU0000001") is False

    def test_has_device_false(self) -> None:
        """Has device should return False for non-existing device."""
        central = _FakeCentral()
        registry = DeviceRegistry(central=central)  # type: ignore[arg-type]

        assert registry.has_device(address="VCU9999999") is False

    def test_has_device_true(self) -> None:
        """Has device should return True for existing device."""
        central = _FakeCentral()
        registry = DeviceRegistry(central=central)  # type: ignore[arg-type]

        device = _FakeDevice(address="VCU0000001")
        registry.add_device(device=device)  # type: ignore[arg-type]

        assert registry.has_device(address="VCU0000001") is True


class TestDeviceRegistryRemoveDevice:
    """Test remove_device functionality."""

    def test_remove_device_leaves_others(self) -> None:
        """Remove device should only remove specified device."""
        central = _FakeCentral()
        registry = DeviceRegistry(central=central)  # type: ignore[arg-type]

        device1 = _FakeDevice(address="VCU0000001")
        device2 = _FakeDevice(address="VCU0000002")
        device3 = _FakeDevice(address="VCU0000003")

        registry.add_device(device=device1)  # type: ignore[arg-type]
        registry.add_device(device=device2)  # type: ignore[arg-type]
        registry.add_device(device=device3)  # type: ignore[arg-type]

        registry.remove_device(device_address="VCU0000002")

        assert registry.device_count == 2
        assert registry.has_device(address="VCU0000001") is True
        assert registry.has_device(address="VCU0000002") is False
        assert registry.has_device(address="VCU0000003") is True

    def test_remove_device_multiple_times(self) -> None:
        """Remove same device multiple times should not raise error."""
        central = _FakeCentral()
        registry = DeviceRegistry(central=central)  # type: ignore[arg-type]

        device = _FakeDevice(address="VCU0000001")
        registry.add_device(device=device)  # type: ignore[arg-type]

        registry.remove_device(device_address="VCU0000001")
        # Should not raise on second removal
        registry.remove_device(device_address="VCU0000001")

        assert registry.device_count == 0

    def test_remove_device_not_found(self) -> None:
        """Remove device that doesn't exist should not raise error."""
        central = _FakeCentral()
        registry = DeviceRegistry(central=central)  # type: ignore[arg-type]

        # Should not raise
        registry.remove_device(device_address="VCU9999999")

        assert registry.device_count == 0

    def test_remove_device_success(self) -> None:
        """Remove device should remove the device from registry."""
        central = _FakeCentral()
        registry = DeviceRegistry(central=central)  # type: ignore[arg-type]

        device = _FakeDevice(address="VCU0000001")
        registry.add_device(device=device)  # type: ignore[arg-type]

        assert registry.device_count == 1

        registry.remove_device(device_address="VCU0000001")

        assert registry.device_count == 0
        assert registry.has_device(address="VCU0000001") is False


class TestDeviceRegistryGetDeviceAddresses:
    """Test get_device_addresses functionality."""

    def test_get_device_addresses_empty(self) -> None:
        """Get device addresses should return empty frozenset for empty registry."""
        central = _FakeCentral()
        registry = DeviceRegistry(central=central)  # type: ignore[arg-type]

        addresses = registry.get_device_addresses()
        assert isinstance(addresses, frozenset)
        assert len(addresses) == 0

    def test_get_device_addresses_immutable(self) -> None:
        """Get device addresses should return frozenset (immutable)."""
        central = _FakeCentral()
        registry = DeviceRegistry(central=central)  # type: ignore[arg-type]

        device = _FakeDevice(address="VCU0000001")
        registry.add_device(device=device)  # type: ignore[arg-type]

        addresses = registry.get_device_addresses()
        assert isinstance(addresses, frozenset)

    def test_get_device_addresses_multiple(self) -> None:
        """Get device addresses should return all device addresses."""
        central = _FakeCentral()
        registry = DeviceRegistry(central=central)  # type: ignore[arg-type]

        device1 = _FakeDevice(address="VCU0000001")
        device2 = _FakeDevice(address="VCU0000002")
        device3 = _FakeDevice(address="VCU0000003")

        registry.add_device(device=device1)  # type: ignore[arg-type]
        registry.add_device(device=device2)  # type: ignore[arg-type]
        registry.add_device(device=device3)  # type: ignore[arg-type]

        addresses = registry.get_device_addresses()
        assert len(addresses) == 3
        assert "VCU0000001" in addresses
        assert "VCU0000002" in addresses
        assert "VCU0000003" in addresses

    def test_get_device_addresses_single(self) -> None:
        """Get device addresses should return all addresses."""
        central = _FakeCentral()
        registry = DeviceRegistry(central=central)  # type: ignore[arg-type]

        device = _FakeDevice(address="VCU0000001")
        registry.add_device(device=device)  # type: ignore[arg-type]

        addresses = registry.get_device_addresses()
        assert len(addresses) == 1
        assert "VCU0000001" in addresses


class TestDeviceRegistryIdentifyChannel:
    """Test identify_channel functionality."""

    def test_identify_channel_empty_registry(self) -> None:
        """Identify channel should return None for empty registry."""
        central = _FakeCentral()
        registry = DeviceRegistry(central=central)  # type: ignore[arg-type]

        identified = registry.identify_channel(text="VCU0000001:1")
        assert identified is None

    def test_identify_channel_multiple_devices(self) -> None:
        """Identify channel should work with multiple devices."""
        central = _FakeCentral()
        registry = DeviceRegistry(central=central)  # type: ignore[arg-type]

        channel1 = _FakeChannel(address="VCU0000001:1")
        channel2 = _FakeChannel(address="VCU0000002:1")

        device1 = _FakeDevice(
            address="VCU0000001",
            channels={"VCU0000001:1": channel1},
        )
        device2 = _FakeDevice(
            address="VCU0000002",
            channels={"VCU0000002:1": channel2},
        )

        registry.add_device(device=device1)  # type: ignore[arg-type]
        registry.add_device(device=device2)  # type: ignore[arg-type]

        identified = registry.identify_channel(text="Channel VCU0000002:1 triggered")
        assert identified is channel2  # type: ignore[comparison-overlap]

    def test_identify_channel_not_found(self) -> None:
        """Identify channel should return None when no channel matches."""
        central = _FakeCentral()
        registry = DeviceRegistry(central=central)  # type: ignore[arg-type]

        channel = _FakeChannel(address="VCU0000001:1")
        device = _FakeDevice(
            address="VCU0000001",
            channels={"VCU0000001:1": channel},
        )
        registry.add_device(device=device)  # type: ignore[arg-type]

        identified = registry.identify_channel(text="No channel address here")
        assert identified is None

    def test_identify_channel_success(self) -> None:
        """Identify channel should find channel in text."""
        central = _FakeCentral()
        registry = DeviceRegistry(central=central)  # type: ignore[arg-type]

        channel = _FakeChannel(address="VCU0000001:1")
        device = _FakeDevice(
            address="VCU0000001",
            channels={"VCU0000001:1": channel},
        )
        registry.add_device(device=device)  # type: ignore[arg-type]

        identified = registry.identify_channel(text="The device VCU0000001:1 is active")
        assert identified is channel  # type: ignore[comparison-overlap]


class TestDeviceRegistryVirtualRemotes:
    """Test get_virtual_remotes functionality."""

    def test_get_virtual_remotes_multiple(self) -> None:
        """Get virtual remotes should return all remotes from all clients."""
        central = _FakeCentral()
        remote1 = _FakeDevice(address="VCU_REMOTE_001")
        remote2 = _FakeDevice(address="VCU_REMOTE_002")
        remote3 = _FakeDevice(address="VCU_REMOTE_003")

        client1 = _FakeClient(virtual_remote=remote1)
        client2 = _FakeClient(virtual_remote=remote2)
        client3 = _FakeClient(virtual_remote=remote3)
        client4 = _FakeClient(virtual_remote=None)

        central.clients = [client1, client2, client3, client4]  # type: ignore[list-item]

        registry = DeviceRegistry(central=central)  # type: ignore[arg-type]

        remotes = registry.get_virtual_remotes()
        assert len(remotes) == 3
        assert remote1 in remotes  # type: ignore[comparison-overlap]
        assert remote2 in remotes  # type: ignore[comparison-overlap]
        assert remote3 in remotes  # type: ignore[comparison-overlap]

    def test_get_virtual_remotes_no_clients(self) -> None:
        """Get virtual remotes should return empty tuple when no clients."""
        central = _FakeCentral()
        central.clients = []

        registry = DeviceRegistry(central=central)  # type: ignore[arg-type]

        remotes = registry.get_virtual_remotes()
        assert isinstance(remotes, tuple)
        assert len(remotes) == 0

    def test_get_virtual_remotes_none(self) -> None:
        """Get virtual remotes should return empty tuple when no clients have remotes."""
        central = _FakeCentral()
        client1 = _FakeClient(virtual_remote=None)
        client2 = _FakeClient(virtual_remote=None)
        central.clients = [client1, client2]  # type: ignore[list-item]

        registry = DeviceRegistry(central=central)  # type: ignore[arg-type]

        remotes = registry.get_virtual_remotes()
        assert isinstance(remotes, tuple)
        assert len(remotes) == 0

    def test_get_virtual_remotes_single(self) -> None:
        """Get virtual remotes should return remote from client."""
        central = _FakeCentral()
        remote1 = _FakeDevice(address="VCU_REMOTE_001")
        client1 = _FakeClient(virtual_remote=remote1)
        client2 = _FakeClient(virtual_remote=None)
        central.clients = [client1, client2]  # type: ignore[list-item]

        registry = DeviceRegistry(central=central)  # type: ignore[arg-type]

        remotes = registry.get_virtual_remotes()
        assert len(remotes) == 1
        assert remote1 in remotes  # type: ignore[comparison-overlap]


class TestDeviceRegistryIntegration:
    """Integration tests for DeviceRegistry with multiple operations."""

    def test_concurrent_operations(self) -> None:
        """Test that concurrent operations work correctly."""
        central = _FakeCentral()
        registry = DeviceRegistry(central=central)  # type: ignore[arg-type]

        # Add multiple devices
        for i in range(10):
            device = _FakeDevice(address=f"VCU00000{i:02d}")
            registry.add_device(device=device)  # type: ignore[arg-type]

        # Query while iterating
        count = 0
        for device in registry.devices:
            count += 1
            # These operations shouldn't affect the iteration
            assert registry.has_device(address=device.address)  # type: ignore[union-attr]
            assert registry.get_device(address=device.address) is device  # type: ignore[arg-type,union-attr]

        assert count == 10

    def test_full_lifecycle(self) -> None:
        """Test full lifecycle of device registry operations."""
        central = _FakeCentral(name="integration_test")
        registry = DeviceRegistry(central=central)  # type: ignore[arg-type]

        # Start empty
        assert registry.device_count == 0

        # Add devices
        devices = []
        for i in range(5):
            channel = _FakeChannel(address=f"VCU000000{i}:1")
            device = _FakeDevice(
                address=f"VCU000000{i}",
                channels={f"VCU000000{i}:1": channel},
            )
            devices.append(device)
            registry.add_device(device=device)  # type: ignore[arg-type]

        assert registry.device_count == 5

        # Get devices
        for i in range(5):
            device = registry.get_device(address=f"VCU000000{i}")
            assert device is not None
            assert device.address == f"VCU000000{i}"  # type: ignore[union-attr]

        # Get channels
        for i in range(5):
            channel = registry.get_channel(channel_address=f"VCU000000{i}:1")
            assert channel is not None
            assert channel.address == f"VCU000000{i}:1"  # type: ignore[union-attr]

        # Check addresses
        addresses = registry.get_device_addresses()
        assert len(addresses) == 5

        # Remove some devices
        registry.remove_device(device_address="VCU0000001")
        registry.remove_device(device_address="VCU0000003")

        assert registry.device_count == 3
        assert registry.has_device(address="VCU0000000") is True
        assert registry.has_device(address="VCU0000001") is False
        assert registry.has_device(address="VCU0000002") is True
        assert registry.has_device(address="VCU0000003") is False
        assert registry.has_device(address="VCU0000004") is True

        # Clear all
        registry.clear()
        assert registry.device_count == 0
        assert registry.devices == ()

    def test_virtual_remotes_integration(self) -> None:
        """Test virtual remotes with full integration."""
        central = _FakeCentral()

        # Add some regular devices
        device1 = _FakeDevice(address="VCU0000001")
        device2 = _FakeDevice(address="VCU0000002")

        registry = DeviceRegistry(central=central)  # type: ignore[arg-type]
        registry.add_device(device=device1)  # type: ignore[arg-type]
        registry.add_device(device=device2)  # type: ignore[arg-type]

        # Add clients with virtual remotes
        remote1 = _FakeDevice(address="VCU_REMOTE_001")
        remote2 = _FakeDevice(address="VCU_REMOTE_002")

        client1 = _FakeClient(virtual_remote=remote1)
        client2 = _FakeClient(virtual_remote=remote2)
        client3 = _FakeClient(virtual_remote=None)

        central.clients = [client1, client2, client3]  # type: ignore[list-item]

        # Virtual remotes should be separate from regular devices
        remotes = registry.get_virtual_remotes()
        assert len(remotes) == 2
        assert remote1 in remotes  # type: ignore[comparison-overlap]
        assert remote2 in remotes  # type: ignore[comparison-overlap]

        # Regular devices should still be accessible
        assert registry.device_count == 2
        assert registry.has_device(address="VCU0000001") is True
        assert registry.has_device(address="VCU0000002") is True
