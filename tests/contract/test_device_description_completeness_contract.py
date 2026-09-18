# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract tests for the completeness of cached device descriptions.

STABILITY GUARANTEE
-------------------
``getDeviceDescription`` returns the device level only. Every path that drops a
device from the caches and re-fetches it by address must therefore fetch the
channel descriptions as well, because a device without cached channel
descriptions is built without a single channel: everything except the device
level data points is lost, and the gap is persisted.

The backend never closes such a gap on its own — ``listDevices`` reports the
device as known, so no ``newDevices`` callback follows and the loss survives
every restart.

These tests pin the contract:

1. ``updateDevice`` (firmware update) and ``readdedDevice`` (re-pairing) keep
   every channel of the device. ``replaceDevice`` shares the same code path.
2. A cache that already lost channel descriptions is repaired from the backend
   before the devices are created.

See ADR-0018 for architectural context.
"""

from typing import Any

import pytest

TEST_DEVICES: set[str] = {"VCU2128127"}
TEST_DEVICE_ADDRESS = "VCU2128127"


def _channel_addresses(central: Any, interface_id: str, device_address: str) -> tuple[str, ...]:
    """Return the cached channel addresses of a device."""
    device_description = central.cache_coordinator.device_descriptions.get_device_description(
        interface_id=interface_id, address=device_address
    )
    return tuple(address for address in device_description.get("CHILDREN", []) if address)


class TestDeviceDescriptionCompleteness:
    """Tests for the completeness of cached device descriptions."""

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
    async def test_incomplete_cache_is_repaired(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test that missing channel descriptions are re-fetched before devices are created."""
        central, _client, _ = central_client_factory_with_homegear_client
        device = central.device_coordinator.get_device(address=TEST_DEVICE_ADDRESS)
        assert device
        interface_id = device.interface_id
        channel_count = len(device.channels)
        channel_addresses = _channel_addresses(central, interface_id, TEST_DEVICE_ADDRESS)
        assert channel_addresses

        # Simulate the damaged cache: device description present, channels gone.
        device_descriptions = central.cache_coordinator.device_descriptions
        device_description = device_descriptions.get_device_description(
            interface_id=interface_id, address=TEST_DEVICE_ADDRESS
        )
        await central.device_coordinator.remove_device(device=device)
        device_descriptions.add_device(interface_id=interface_id, device_description=device_description)
        assert (
            device_descriptions.get_missing_channel_addresses(
                interface_id=interface_id, device_address=TEST_DEVICE_ADDRESS
            )
            == channel_addresses
        )
        assert central.device_coordinator.get_device(address=TEST_DEVICE_ADDRESS) is None

        await central.device_coordinator.check_and_create_devices_from_cache()

        repaired_device = central.device_coordinator.get_device(address=TEST_DEVICE_ADDRESS)
        assert repaired_device
        assert len(repaired_device.channels) == channel_count
        assert not device_descriptions.get_missing_channel_addresses(
            interface_id=interface_id, device_address=TEST_DEVICE_ADDRESS
        )

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
    async def test_readd_device_keeps_channels(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test that a re-pairing callback does not drop the channels of a device."""
        central, _client, _ = central_client_factory_with_homegear_client
        device = central.device_coordinator.get_device(address=TEST_DEVICE_ADDRESS)
        assert device
        interface_id = device.interface_id
        channel_count = len(device.channels)

        await central.device_coordinator.readd_device(
            interface_id=interface_id, device_addresses=(TEST_DEVICE_ADDRESS,)
        )

        readded_device = central.device_coordinator.get_device(address=TEST_DEVICE_ADDRESS)
        assert readded_device
        assert len(readded_device.channels) == channel_count

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
    async def test_update_device_keeps_channels(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test that a firmware update callback does not drop the channels of a device."""
        central, _client, _ = central_client_factory_with_homegear_client
        device = central.device_coordinator.get_device(address=TEST_DEVICE_ADDRESS)
        assert device
        interface_id = device.interface_id
        channel_count = len(device.channels)
        assert channel_count > 1

        await central.device_coordinator.update_device(interface_id=interface_id, device_address=TEST_DEVICE_ADDRESS)

        updated_device = central.device_coordinator.get_device(address=TEST_DEVICE_ADDRESS)
        assert updated_device
        assert len(updated_device.channels) == channel_count
        assert updated_device.generic_data_points
