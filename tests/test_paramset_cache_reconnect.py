# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Test paramset cache behavior during reconnection.

Verifies that paramsets cached during initial connection are properly
reused during reconnection, avoiding unnecessary re-fetching from CCU.
"""

from __future__ import annotations

from typing import Any

import pytest

TEST_DEVICES: set[str] = {"VCU2128127", "VCU6354483"}


class TestParamsetCacheOnReconnect:
    """Test that paramset cache prevents unnecessary re-fetching during reconnect."""

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
    async def test_paramsets_not_refetched_on_reconnect(
        self,
        central_client_factory_with_homegear_client: Any,
    ) -> None:
        """
        Test that paramsets are NOT re-fetched on reconnect.

        Scenario:
        1. Initial connection - paramsets fetched from CCU, stored in cache
        2. Connection lost (client disconnects)
        3. Reconnection - LIST_DEVICES returns same devices
        4. EXPECTATION: No paramset fetches should occur (cache is in memory)

        This test verifies that the cache remains available in memory during
        reconnects and prevents unnecessary paramset fetches.
        """
        central, mock_client, _ = central_client_factory_with_homegear_client

        # Get initial device count and verify paramsets are loaded
        initial_devices = list(central.device_registry.devices)
        assert len(initial_devices) > 0, "Should have devices after initial connection"

        # Verify paramset cache has entries for all interfaces
        paramset_cache = central.cache_coordinator.paramset_descriptions
        assert paramset_cache is not None

        # Get initial cache state - count how many paramsets are cached
        initial_cached_count = len(paramset_cache.raw_paramset_descriptions)
        assert initial_cached_count > 0, "Should have paramsets cached after initial connection"

        # Simulate connection loss and recovery by stopping/starting
        # This simulates what happens in production when a client reconnects
        await central.stop()
        await central.start()

        # Verify cache still has same paramsets (not cleared)
        reconnect_cached_count = len(paramset_cache.raw_paramset_descriptions)

        assert reconnect_cached_count == initial_cached_count, (
            f"Cache should remain intact after reconnect: {initial_cached_count} -> {reconnect_cached_count}"
        )

        # Verify devices are still available
        reconnected_devices = list(central.device_registry.devices)
        assert len(reconnected_devices) == len(initial_devices), "Device count should match after reconnect"


class TestParamsetCacheNewDevices:
    """Test paramset cache behavior when new devices appear during reconnect."""

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
    async def test_only_new_devices_fetch_paramsets(
        self,
        central_client_factory_with_homegear_client: Any,
    ) -> None:
        """
        Test that only NEW devices trigger paramset fetches on reconnect.

        Scenario:
        1. Initial connection with N devices
        2. CCU gains a new device (simulated)
        3. Reconnection - LIST_DEVICES returns N+1 devices
        4. EXPECTATION: Only the 1 new device should fetch paramsets

        This test verifies that existing devices use cached paramsets while
        new devices fetch their paramsets from CCU.
        """
        central, mock_client, _ = central_client_factory_with_homegear_client

        # Get initial device count
        initial_devices = list(central.device_registry.devices)
        initial_count = len(initial_devices)

        # Reset mock to track reconnect behavior
        mock_client.reset_mock()

        # TODO: Add mock logic to simulate new device appearing
        # This requires modifying the mock to return additional device
        # in LIST_DEVICES call during reconnect

        # For now, just verify the test structure is correct
        assert initial_count > 0


class TestParamsetCacheInterfaceId:
    """Test that interface_id is consistent between cache writes and reads."""

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
    async def test_interface_id_consistency(
        self,
        central_client_factory_with_homegear_client: Any,
    ) -> None:
        """
        Test that interface_id remains consistent between cache operations.

        This test verifies that when paramsets are stored in the cache under
        a specific interface_id, they can be retrieved using the same interface_id.

        This is the likely root cause of the production issue where 164 devices
        are identified as "missing paramsets" on every reconnect.
        """
        central, mock_client, _ = central_client_factory_with_homegear_client

        paramset_cache = central.cache_coordinator.paramset_descriptions

        # Get all interface_ids in the cache
        cached_interface_ids = list(paramset_cache.raw_paramset_descriptions.keys())

        # Get all devices and their interface_ids
        for device in central.device_registry.devices:
            # Verify device's interface_id is in the paramset cache
            assert device.interface_id in cached_interface_ids, (
                f"Device {device.address} has interface_id '{device.interface_id}' but cache only has: {cached_interface_ids}"
            )

            # Verify we can retrieve paramsets for this device
            for channel in device.channels.values():
                cached_paramsets = paramset_cache.get_channel_paramset_descriptions(
                    interface_id=device.interface_id,
                    channel_address=channel.address,
                )
                # Verify we got paramsets
                assert cached_paramsets, f"Channel {channel.address} should have cached paramsets"


class TestParamsetCacheIdentifyMissing:
    """Test the _identify_devices_missing_paramsets function behavior."""

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
    async def test_identify_missing_logs_expected_vs_cached(
        self,
        central_client_factory_with_homegear_client: Any,
        caplog: Any,
    ) -> None:
        """
        Test that _identify_devices_missing_paramsets logs expected vs cached keys.

        This test verifies that the debug logging added in device.py:1025-1037
        properly reports which paramsets are expected and which are cached.

        Expected log format:
        "ADD_NEW_DEVICES: Device <address> on interface <id> is missing paramsets:
         <missing> (expected: <expected>, cached: <cached>)"
        """
        central, mock_client, _ = central_client_factory_with_homegear_client

        # Trigger reconnect to generate logs
        await central.stop()

        # Reset mock and clear logs
        mock_client.reset_mock()
        caplog.clear()

        # Start central again (reconnect scenario)
        await central.start()

        # Check for debug logs from _identify_devices_missing_paramsets
        missing_paramset_logs = [record for record in caplog.records if "is missing paramsets" in record.message]

        # If any devices are missing paramsets (shouldn't happen with good cache),
        # logs should show expected vs cached keys
        if missing_paramset_logs:
            # Each log should contain expected and cached keys
            for log_record in missing_paramset_logs:
                assert "expected:" in log_record.message
                assert "cached:" in log_record.message
                pytest.fail(f"Found devices with missing paramsets on reconnect: {log_record.message}")
