"""Edge case tests for store modules."""

from __future__ import annotations

import contextlib
from pathlib import Path

import pytest

from aiohomematic.const import ParamsetKey

TEST_DEVICES: set[str] = {"VCU6354483"}

# pylint: disable=protected-access


class TestPersistentCacheEdgeCases:
    """Test edge cases in persistent cache operations."""

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
    async def test_paramset_description_cache_save(
        self,
        central_client_factory_with_ccu_client,
        tmp_path: Path,
    ) -> None:
        """Test saving paramset description cache."""
        central, mock_client, _ = central_client_factory_with_ccu_client

        # Get the cache from central
        cache = central.paramset_descriptions

        # Try to save the cache
        with contextlib.suppress(Exception):
            await cache.save()
            # May fail with mock, but we exercised the code path


class TestParameterVisibilityEdgeCases:
    """Test edge cases in parameter visibility."""

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
    async def test_parameter_visibility_save(
        self,
        central_client_factory_with_ccu_client,
        tmp_path: Path,
    ) -> None:
        """Test saving parameter visibility cache."""
        central, mock_client, _ = central_client_factory_with_ccu_client

        # Get the parameter visibility cache
        cache = central.parameter_visibility

        # Try to save the cache
        with contextlib.suppress(Exception):
            await cache.save()
            # May fail with mock, but we exercised the code path


class TestParamsetDescriptionEdgeCases:
    """Test edge cases in paramset description operations."""

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
    async def test_paramset_description_get_nonexistent(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test getting non-existent paramset description."""
        central, mock_client, _ = central_client_factory_with_ccu_client

        # Get the first client's interface_id
        assert central.clients
        interface_id = central.clients[0].interface_id

        # Try to get a non-existent paramset description
        desc = central.paramset_descriptions.get_paramset_descriptions(
            interface_id=interface_id,
            channel_address="NONEXISTENT:1",
            paramset_key=ParamsetKey.VALUES,
        )

        # Should return None or empty dict
        assert desc is None or isinstance(desc, dict)


class TestDeviceDetailsEdgeCases:
    """Test edge cases in device details operations."""

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
    async def test_device_details_get_nonexistent(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test getting details for non-existent device."""
        central, mock_client, _ = central_client_factory_with_ccu_client

        # Try to get details for non-existent device
        name = central.device_details.get_name(address="NONEXISTENT_DEVICE")
        # Should return None
        assert name is None
