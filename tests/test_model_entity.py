"""Tests for entity and data point functionality of aiohomematic."""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock, call

import pytest

from aiohomematic.const import CallSource, DataPointUsage, ParamsetKey
from aiohomematic.model.custom import CustomDpSwitch, get_required_parameters, validate_custom_data_point_definition
from aiohomematic.model.generic import DpSensor, DpSwitch
from aiohomematic.store import check_ignore_parameters_is_clean
from aiohomematic_test_support import const
from aiohomematic_test_support.helper import get_prepared_custom_data_point

TEST_DEVICES: set[str] = {"VCU2128127", "VCU3609622"}

# pylint: disable=protected-access


class TestDataPointDefinition:
    """Tests for data point definition validation."""

    def test_custom_required_data_points(self) -> None:
        """Test required parameters from data point definitions."""
        required_parameters = get_required_parameters()
        assert len(required_parameters) == 88
        assert check_ignore_parameters_is_clean() is True

    def test_validate_data_point_definition(self) -> None:
        """Test custom data point definition validation."""
        assert validate_custom_data_point_definition() is not None


class TestDataPointCallbacks:
    """Tests for data point handler functionality."""

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
    async def test_custom_data_point_handler(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test CustomDpSwitch handler registration and events."""
        central, _, factory = central_client_factory_with_homegear_client
        switch: CustomDpSwitch = cast(CustomDpSwitch, get_prepared_custom_data_point(central, "VCU2128127", 4))
        assert switch.usage == DataPointUsage.CDP_PRIMARY

        device_updated_mock = MagicMock()
        device_removed_mock = MagicMock()

        unregister_data_point_updated_handler = switch.subscribe_to_data_point_updated(
            handler=device_updated_mock, custom_id="some_id"
        )
        unregister_device_removed_handler = switch.subscribe_to_device_removed(handler=device_removed_mock)
        assert switch.value is None
        assert str(switch) == "path: device/status/VCU2128127/4/SWITCH, name: HmIP-BSM_VCU2128127"
        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU2128127:4", parameter="STATE", value=1
        )
        assert switch.value is True
        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU2128127:4", parameter="STATE", value=0
        )
        assert switch.value is False
        # Wait for async event bus publish to complete for data point updates
        import asyncio

        await asyncio.sleep(0.1)
        await central.delete_devices(interface_id=const.INTERFACE_ID, addresses=[switch.device.address])
        # Wait for async event bus publish to complete for delete events
        await asyncio.sleep(0.1)
        # Verify the system event mock received a BackendSystemEventData event
        assert factory.system_event_mock.called
        call_args = factory.system_event_mock.call_args_list[-1]
        event = call_args[0][0]  # First positional argument
        assert event.system_event == "deleteDevices"
        assert event.data.get("interface_id") == "CentralTest-BidCos-RF"
        assert event.data.get("addresses") == ["VCU2128127"]
        unregister_data_point_updated_handler()
        unregister_device_removed_handler()

        device_updated_mock.assert_called_with(data_point=switch, custom_id="some_id")
        device_removed_mock.assert_called_with()

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
    async def test_generic_data_point_handler(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test generic data point handler registration and events."""
        central, _, factory = central_client_factory_with_homegear_client
        switch: DpSwitch = cast(
            DpSwitch, central.get_generic_data_point(channel_address="VCU2128127:4", parameter="STATE")
        )
        assert switch.usage == DataPointUsage.NO_CREATE

        device_updated_mock = MagicMock()
        device_removed_mock = MagicMock()

        unregister_updated = switch.subscribe_to_data_point_updated(handler=device_updated_mock, custom_id="some_id")
        unregister_removed = switch.subscribe_to_device_removed(handler=device_removed_mock)
        assert switch.value is None
        assert str(switch) == "path: device/status/VCU2128127/4/STATE, name: HmIP-BSM_VCU2128127 State ch4"
        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU2128127:4", parameter="STATE", value=1
        )
        assert switch.value is True
        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU2128127:4", parameter="STATE", value=0
        )
        assert switch.value is False
        # Wait for async event bus publish to complete for data point updates
        import asyncio

        await asyncio.sleep(0.1)
        await central.delete_devices(interface_id=const.INTERFACE_ID, addresses=[switch.device.address])
        # Wait for async event bus publish to complete for delete events
        await asyncio.sleep(0.1)
        # Verify the system event mock received a BackendSystemEventData event
        assert factory.system_event_mock.called
        call_args = factory.system_event_mock.call_args_list[-1]
        event = call_args[0][0]  # First positional argument
        assert event.system_event == "deleteDevices"
        assert event.data.get("interface_id") == "CentralTest-BidCos-RF"
        assert event.data.get("addresses") == ["VCU2128127"]
        # Call the unregister handler to clean up
        if unregister_updated:
            unregister_updated()
        if unregister_removed:
            unregister_removed()

        device_updated_mock.assert_called_with(data_point=switch, custom_id="some_id")
        device_removed_mock.assert_called_with()


class TestDataPointLoading:
    """Tests for data point value loading."""

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
    async def test_load_custom_data_point(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test custom data point value loading."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        switch: DpSwitch = cast(DpSwitch, get_prepared_custom_data_point(central, "VCU2128127", 4))
        await switch.load_data_point_value(call_source=CallSource.MANUAL_OR_SCHEDULED)
        assert mock_client.method_calls[-3] == call.get_value(
            channel_address="VCU2128127:4",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
            call_source="hm_init",
        )
        assert mock_client.method_calls[-2] == call.get_value(
            channel_address="VCU2128127:3",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
            call_source="hm_init",
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
    async def test_load_generic_data_point(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test generic data point value loading."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        switch: DpSwitch = cast(
            DpSwitch, central.get_generic_data_point(channel_address="VCU2128127:4", parameter="STATE")
        )
        await switch.load_data_point_value(call_source=CallSource.MANUAL_OR_SCHEDULED)
        assert mock_client.method_calls[-1] == call.get_value(
            channel_address="VCU2128127:4",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
            call_source="hm_init",
        )


class TestWrappedDataPoint:
    """Tests for wrapped data point functionality."""

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
    async def test_generic_wrapped_data_point(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test wrapped data point category and forced sensor behavior."""
        central, _, _ = central_client_factory_with_homegear_client
        wrapped_data_point: DpSensor = cast(
            DpSensor, central.get_generic_data_point(channel_address="VCU3609622:1", parameter="LEVEL")
        )
        assert wrapped_data_point.default_category() == "number"
        assert wrapped_data_point._is_forced_sensor is True
        assert wrapped_data_point.category == "sensor"
        assert wrapped_data_point.usage == DataPointUsage.DATA_POINT
