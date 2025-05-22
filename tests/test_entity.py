"""Tests for switch data points of hahomematic."""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock, Mock, call

import pytest

from hahomematic.caches.visibility import check_ignore_parameters_is_clean
from hahomematic.central import CentralUnit
from hahomematic.client import Client
from hahomematic.const import CallSource, DataPointUsage, ParamsetKey
from hahomematic.model.custom import CustomDpSwitch, get_required_parameters, validate_custom_data_point_definition
from hahomematic.model.generic import DpSensor, DpSwitch

from tests import const, helper

TEST_DEVICES: dict[str, str] = {
    "VCU2128127": "HmIP-BSM.json",
    "VCU3609622": "HmIP-eTRV-2.json",
}

# pylint: disable=protected-access


def test_validate_data_point_definition() -> None:
    """Test validate_data_point_definition."""
    assert validate_custom_data_point_definition() is not None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "address_device_translation",
        "do_mock_client",
        "add_sysvars",
        "add_programs",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [
        (TEST_DEVICES, True, False, False, None, None),
    ],
)
async def test_custom_data_point_callback(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test CustomDpSwitch."""
    central, _, factory = central_client_factory
    switch: CustomDpSwitch = cast(CustomDpSwitch, helper.get_prepared_custom_data_point(central, "VCU2128127", 4))
    assert switch.usage == DataPointUsage.CDP_PRIMARY

    device_updated_mock = MagicMock()
    device_removed_mock = MagicMock()

    unregister_data_point_updated_callback = switch.register_data_point_updated_callback(
        cb=device_updated_mock, custom_id="some_id"
    )
    unregister_device_removed_callback = switch.register_device_removed_callback(cb=device_removed_mock)
    assert switch.value is None
    assert str(switch) == "path: device/status/VCU2128127/4/SWITCH, name: HmIP-BSM_VCU2128127"
    await central.data_point_event(const.INTERFACE_ID, "VCU2128127:4", "STATE", 1)
    assert switch.value is True
    await central.data_point_event(const.INTERFACE_ID, "VCU2128127:4", "STATE", 0)
    assert switch.value is False
    await central.delete_devices(interface_id=const.INTERFACE_ID, addresses=[switch.device.address])
    assert factory.system_event_mock.call_args_list[-1] == call(
        "deleteDevices", interface_id="CentralTest-BidCos-RF", addresses=["VCU2128127"]
    )
    unregister_data_point_updated_callback()
    unregister_device_removed_callback()

    device_updated_mock.assert_called_with(data_point=switch)
    device_removed_mock.assert_called_with()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "address_device_translation",
        "do_mock_client",
        "add_sysvars",
        "add_programs",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [
        (TEST_DEVICES, True, False, False, None, None),
    ],
)
async def test_generic_data_point_callback(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test CustomDpSwitch."""
    central, _, factory = central_client_factory
    switch: DpSwitch = cast(DpSwitch, central.get_generic_data_point("VCU2128127:4", "STATE"))
    assert switch.usage == DataPointUsage.NO_CREATE

    device_updated_mock = MagicMock()
    device_removed_mock = MagicMock()

    switch.register_data_point_updated_callback(cb=device_updated_mock, custom_id="some_id")
    switch.register_device_removed_callback(cb=device_removed_mock)
    assert switch.value is None
    assert str(switch) == "path: device/status/VCU2128127/4/STATE, name: HmIP-BSM_VCU2128127 State ch4"
    await central.data_point_event(const.INTERFACE_ID, "VCU2128127:4", "STATE", 1)
    assert switch.value is True
    await central.data_point_event(const.INTERFACE_ID, "VCU2128127:4", "STATE", 0)
    assert switch.value is False
    await central.delete_devices(interface_id=const.INTERFACE_ID, addresses=[switch.device.address])
    assert factory.system_event_mock.call_args_list[-1] == call(
        "deleteDevices", interface_id="CentralTest-BidCos-RF", addresses=["VCU2128127"]
    )
    switch._unregister_data_point_updated_callback(cb=device_updated_mock, custom_id="some_id")
    switch._unregister_device_removed_callback(cb=device_removed_mock)

    device_updated_mock.assert_called_with(data_point=switch)
    device_removed_mock.assert_called_with()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "address_device_translation",
        "do_mock_client",
        "add_sysvars",
        "add_programs",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [
        (TEST_DEVICES, True, False, False, None, None),
    ],
)
async def test_load_custom_data_point(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test load custom_data_point."""
    central, mock_client, _ = central_client_factory
    switch: DpSwitch = cast(DpSwitch, helper.get_prepared_custom_data_point(central, "VCU2128127", 4))
    await switch.load_data_point_value(call_source=CallSource.MANUAL_OR_SCHEDULED)
    assert mock_client.method_calls[-2] == call.get_value(
        channel_address="VCU2128127:4",
        paramset_key=ParamsetKey.VALUES,
        parameter="STATE",
        call_source="hm_init",
    )
    assert mock_client.method_calls[-1] == call.get_value(
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
        "add_sysvars",
        "add_programs",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [
        (TEST_DEVICES, True, False, False, None, None),
    ],
)
async def test_load_generic_data_point(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test load generic_data_point."""
    central, mock_client, _ = central_client_factory
    switch: DpSwitch = cast(DpSwitch, central.get_generic_data_point("VCU2128127:4", "STATE"))
    await switch.load_data_point_value(call_source=CallSource.MANUAL_OR_SCHEDULED)
    assert mock_client.method_calls[-1] == call.get_value(
        channel_address="VCU2128127:4",
        paramset_key=ParamsetKey.VALUES,
        parameter="STATE",
        call_source="hm_init",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "address_device_translation",
        "do_mock_client",
        "add_sysvars",
        "add_programs",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [
        (TEST_DEVICES, True, False, False, None, None),
    ],
)
async def test_generic_wrapped_data_point(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test wrapped data_point."""
    central, _, _ = central_client_factory
    wrapped_data_point: DpSensor = cast(DpSensor, central.get_generic_data_point("VCU3609622:1", "LEVEL"))
    assert wrapped_data_point.default_category() == "number"
    assert wrapped_data_point._is_forced_sensor is True
    assert wrapped_data_point.category == "sensor"
    assert wrapped_data_point.usage == DataPointUsage.DATA_POINT


def test_custom_required_data_points() -> None:
    """Test required parameters from data_point definitions."""
    required_parameters = get_required_parameters()
    assert len(required_parameters) == 84
    assert check_ignore_parameters_is_clean() is True
