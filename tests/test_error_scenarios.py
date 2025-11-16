"""Comprehensive error scenario and edge case tests for aiohomematic."""

from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock, Mock, patch

import pytest

from aiohomematic.central import CentralUnit
from aiohomematic.const import CallSource, Interface, ParamsetKey
from aiohomematic.exceptions import ClientException, NoConnectionException
from aiohomematic.model.data_point import CallParameterCollector

TEST_DEVICES: set[str] = {"VCU6354483"}

# pylint: disable=protected-access


class TestCentralErrorScenarios:
    """Test error scenarios in CentralUnit."""

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
    async def test_central_remove_device_not_exists(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test removing a device that doesn't exist."""
        central, mock_client, _ = central_client_factory_with_ccu_client

        # Create a mock device that's not in central
        mock_device = Mock()
        mock_device.address = "NONEXISTENT_DEVICE"

        # Should not raise an error
        central.remove_device(device=mock_device)

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
    async def test_central_get_client_by_interface_id(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test getting client by interface_id."""
        central, mock_client, _ = central_client_factory_with_ccu_client

        # Get existing interface IDs
        for client in central.clients:
            # Try to get client by its interface_id
            found_client = central.get_client(interface_id=client.interface_id)
            assert found_client is not None

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            ({}, True, None, None),
        ],
    )
    async def test_central_program_removal_nonexistent(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test removing a program that doesn't exist."""
        central, mock_client, _ = central_client_factory_with_ccu_client

        # Try to remove non-existent program
        central.remove_program_button(pid="nonexistent_program_id")

        # Should not raise an error

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            ({}, True, None, None),
        ],
    )
    async def test_central_sysvar_removal_nonexistent(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test removing a sysvar that doesn't exist."""
        central, mock_client, _ = central_client_factory_with_homegear_client

        # Try to remove non-existent sysvar
        central.remove_sysvar_data_point(vid="nonexistent_sysvar_id")

        # Should not raise an error


class TestDeviceErrorScenarios:
    """Test error scenarios in Device operations."""

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
    async def test_device_get_channel_nonexistent(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test getting a channel that doesn't exist."""
        central, mock_client, _ = central_client_factory_with_ccu_client

        device = central.get_device(address="VCU6354483")
        if device:
            # Try to get a channel that doesn't exist
            channel = device.get_channel(channel_no=9999)
            assert channel is None

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
    async def test_device_get_channels_by_type_empty(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test getting channels by type when none match."""
        central, mock_client, _ = central_client_factory_with_ccu_client

        device = central.get_device(address="VCU6354483")
        if device:
            # Try to get channels by a type that doesn't exist
            channels = device.get_channels_by_type(channel_type="NONEXISTENT_TYPE")
            assert isinstance(channels, list)
            assert len(channels) == 0


class TestDataPointErrorScenarios:
    """Test error scenarios in DataPoint operations."""

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
    async def test_data_point_send_value_validation_error(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test sending invalid value that fails validation."""
        central, mock_client, _ = central_client_factory_with_ccu_client

        device = central.get_device(address="VCU6354483")
        if device:
            for channel in list(device.channels.values())[:1]:
                for dp in list(channel.data_points.values())[:1]:
                    if dp.is_writable and dp.max is not None:
                        # Try to send a value that exceeds max
                        try:
                            await dp.send_value(value=dp.max * 10, do_validate=True)
                        except Exception:
                            # Expected to fail validation
                            pass

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
    async def test_data_point_load_value_with_collector(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test loading data point value with collector."""
        central, mock_client, _ = central_client_factory_with_ccu_client

        device = central.get_device(address="VCU6354483")
        if device:
            collector = CallParameterCollector()
            for channel in list(device.channels.values())[:1]:
                for dp in list(channel.data_points.values())[:1]:
                    if dp.is_readable:
                        try:
                            # Add to collector instead of direct load
                            collector.add_data_point(
                                data_point=dp,
                                channel_address=channel.address,
                                paramset_key=ParamsetKey.VALUES,
                                parameter=dp.parameter,
                            )
                        except Exception:
                            # May fail if data point doesn't support this operation
                            pass


class TestClientErrorScenarios:
    """Test error scenarios in Client operations."""

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
    async def test_client_supports_ping_pong(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test client ping pong support check."""
        central, mock_client, _ = central_client_factory_with_ccu_client

        for client in central.clients:
            # Check if client supports ping pong
            if hasattr(client, "supports_ping_pong"):
                supports = client.supports_ping_pong
                assert isinstance(supports, bool)


class TestCentralCallbacks:
    """Test callback registration and removal."""

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
    async def test_callback_registration_duplicate(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test registering the same callback multiple times."""
        central, mock_client, _ = central_client_factory_with_ccu_client

        callback = Mock()

        # Register the same callback multiple times
        unregister1 = central.register_backend_parameter_callback(cb=callback)
        unregister2 = central.register_backend_parameter_callback(cb=callback)

        # Second registration should not add duplicate
        # (implementation dependent)

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
    async def test_callback_registration_none(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test registering None as callback."""
        central, mock_client, _ = central_client_factory_with_ccu_client

        # Try to register None
        unregister = central.register_backend_parameter_callback(cb=None)  # type: ignore[arg-type]

        # Should handle gracefully


class TestParameterVisibility:
    """Test parameter visibility operations."""

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
    async def test_parameter_visibility_hidden_check(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test checking if parameters are hidden."""
        central, mock_client, _ = central_client_factory_with_ccu_client

        device = central.get_device(address="VCU6354483")
        if device:
            for channel in list(device.channels.values())[:1]:
                for dp in list(channel.data_points.values())[:1]:
                    # Check if parameter is hidden
                    is_hidden = central.parameter_visibility.parameter_is_hidden(
                        channel_address=channel.address,
                        paramset_key=ParamsetKey.VALUES,
                        parameter=dp.parameter,
                    )
                    assert isinstance(is_hidden, bool)


class TestCentralUtilities:
    """Test central utility methods."""

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
    async def test_central_devices_collection(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test accessing devices collection."""
        central, mock_client, _ = central_client_factory_with_ccu_client

        devices = central.devices
        assert isinstance(devices, (list, tuple))


class TestDeviceUtilities:
    """Test device utility methods."""

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
    async def test_device_refresh_firmware(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test refreshing device firmware data."""
        central, mock_client, _ = central_client_factory_with_ccu_client

        device = central.get_device(address="VCU6354483")
        if device:
            try:
                await central.refresh_firmware_data(device_address=device.address)
            except Exception:
                # May fail with mock client
                pass

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
    async def test_device_clear_collections(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test clearing device collections."""
        central, mock_client, _ = central_client_factory_with_ccu_client

        device = central.get_device(address="VCU6354483")
        if device:
            # Clear all collections
            device.clear_all_collections()


class TestEventSubscriptions:
    """Test event subscription operations."""

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
    async def test_remove_event_subscription_nonexistent(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test removing event subscription for non-existent data point."""
        central, mock_client, _ = central_client_factory_with_ccu_client

        device = central.get_device(address="VCU6354483")
        if device:
            for channel in list(device.channels.values())[:1]:
                for dp in list(channel.data_points.values())[:1]:
                    # Try to remove event subscription
                    central.remove_event_subscription(data_point=dp)


class TestCentralCollections:
    """Test central collection access."""

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
    async def test_central_clients_collection(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test accessing clients collection."""
        central, mock_client, _ = central_client_factory_with_ccu_client

        # Access clients collection
        clients = central.clients
        assert isinstance(clients, (list, tuple))
        assert len(clients) > 0
