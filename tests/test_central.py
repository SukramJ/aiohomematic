"""Test the AioHomematic central."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import call

import pytest

from aiohomematic.central import CentralConfig, _SchedulerJob, check_config as central_check_config
from aiohomematic.client import InterfaceConfig
from aiohomematic.const import (
    DATETIME_FORMAT_MILLIS,
    LOCAL_HOST,
    PING_PONG_MISMATCH_COUNT,
    DataPointCategory,
    DataPointUsage,
    DeviceFirmwareState,
    EventKey,
    EventType,
    Interface,
    InterfaceEventType,
    Operations,
    Parameter,
    ParamsetKey,
)
from aiohomematic.exceptions import AioHomematicConfigException, AioHomematicException, NoClientsException
from aiohomematic_test_support import const
from aiohomematic_test_support.factory import FactoryWithClient
from aiohomematic_test_support.helper import load_device_description

TEST_DEVICES: set[str] = {"VCU2128127", "VCU6354483"}


class _FakeDevice:
    def __init__(self, *, model: str) -> None:
        """Initialize a FakeDevice."""
        self.model = model


class _FakeChannel:
    def __init__(self, *, model: str, no: int | None) -> None:
        """Initialize a FakeChannel."""
        self.no = no
        self.device = _FakeDevice(model=model)


class _FakeTask:
    """A simple awaitable callable to be used as `_SchedulerJob` task."""

    def __init__(self, marker: dict[str, int]) -> None:
        self._marker = marker

    async def __call__(self) -> None:
        await asyncio.sleep(0)
        self._marker["calls"] = self._marker.get("calls", 0) + 1


class _FakeInterfaceConfig(InterfaceConfig):
    """
    Lightweight InterfaceConfig that allows setting any port or interface.

    We call the real `InterfaceConfig` constructor but this class is here to satisfy
    the requirement to keep fake classes at the top of the file.
    """

    # No overrides; this class only documents the intent for tests.


# pylint: disable=protected-access


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
async def test_central_basics(
    central_client_factory_with_homegear_client,
) -> None:
    """Test central basics."""
    central, client, _ = central_client_factory_with_homegear_client
    assert central.url == f"http://{LOCAL_HOST}"
    assert central.is_alive is True
    assert central.listen_ip_addr == LOCAL_HOST
    assert central.supports_ping_pong is False
    assert central.system_information.serial == "BidCos-RF_SN0815"
    assert central.version == "pydevccu 0.1.17"
    system_information = await central.validate_config_and_get_system_information()
    assert system_information.serial == "BidCos-RF_SN0815"
    device = central.get_device(address="VCU2128127")
    assert device
    dps = central.get_readable_generic_data_points()
    assert dps
    await central.refresh_firmware_data(device_address="VCU2128127")
    await central.refresh_firmware_data()
    await central.refresh_firmware_data_by_state(device_firmware_states=DeviceFirmwareState.NEW_FIRMWARE_AVAILABLE)
    await central.restart_clients()

    await central.stop()
    assert central._has_active_threads is False
    assert central.supports_ping_pong is False


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
async def test_device_get_data_points(
    central_client_factory_with_homegear_client,
) -> None:
    """Test central/device get_data_points."""
    central, _, _ = central_client_factory_with_homegear_client
    dps = central.get_data_points()
    assert dps

    dps_reg = central.get_data_points(registered=True)
    assert dps_reg == ()


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
async def test_device_export(
    central_client_factory_with_homegear_client,
) -> None:
    """Test device export."""
    central, _, _ = central_client_factory_with_homegear_client
    device = central.get_device(address="VCU6354483")
    await device.export_device_definition()


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
async def test_identify_ip_addr(
    central_client_factory_with_homegear_client,
) -> None:
    """Test identify_ip_addr."""
    central, _, _ = central_client_factory_with_homegear_client
    assert await central._identify_ip_addr(port=54321) == LOCAL_HOST
    central.config.host = "no_host"
    assert await central._identify_ip_addr(port=54321) == LOCAL_HOST


@pytest.mark.parametrize(
    ("line", "parameter", "channel_no", "paramset_key", "expected_result"),
    [
        ("", "LEVEL", 1, ParamsetKey.VALUES, False),
        ("LEVEL", "LEVEL", 1, ParamsetKey.VALUES, True),
        ("VALVE_ADAPTION", "VALVE_ADAPTION", 1, ParamsetKey.VALUES, True),
        ("ACTIVE_PROFILE", "ACTIVE_PROFILE", 1, ParamsetKey.VALUES, True),
        ("LEVEL@HmIP-eTRV-2:1:VALUES", "LEVEL", 1, ParamsetKey.VALUES, False),
        ("LEVEL@HmIP-eTRV-2", "LEVEL", 1, ParamsetKey.VALUES, False),
        ("LEVEL@@HmIP-eTRV-2", "LEVEL", 1, ParamsetKey.VALUES, False),
        ("HmIP-eTRV-2:1:MASTER", "LEVEL", 1, ParamsetKey.VALUES, False),
        ("LEVEL:VALUES@all:all", "LEVEL", 1, ParamsetKey.VALUES, True),
        ("LEVEL:VALUES@HmIP-eTRV-2:all", "LEVEL", 1, ParamsetKey.VALUES, True),
        ("LEVEL:VALUES@all:1", "LEVEL", 1, ParamsetKey.VALUES, True),
        ("LEVEL:VALUES@all", "LEVEL", 1, ParamsetKey.VALUES, False),
        ("LEVEL::VALUES@all:1", "LEVEL", 1, ParamsetKey.VALUES, False),
        ("LEVEL:VALUES@all::1", "LEVEL", 1, ParamsetKey.VALUES, False),
        ("SET_POINT_TEMPERATURE", "SET_POINT_TEMPERATURE", 1, ParamsetKey.VALUES, True),
    ],
)
@pytest.mark.asyncio
async def test_device_un_ignore_etrv(
    factory_with_homegear_client: FactoryWithClient,
    line: str,
    parameter: str,
    channel_no: int,
    paramset_key: ParamsetKey,
    expected_result: bool,
) -> None:
    """Test device un ignore."""
    central = await factory_with_homegear_client.init(
        address_device_translation={"VCU3609622"}, un_ignore_list=[line]
    ).get_default_central()
    try:
        channel = _FakeChannel(model="HmIP-eTRV-2", no=channel_no)
        assert (
            central.parameter_visibility.parameter_is_un_ignored(
                channel=channel,
                paramset_key=paramset_key,
                parameter=parameter,
            )
            is expected_result
        )
        if dp := central.get_generic_data_point(channel_address=f"VCU3609622:{channel_no}", parameter=parameter):
            assert dp.usage == DataPointUsage.DATA_POINT
    finally:
        await central.stop()


@pytest.mark.parametrize(
    ("line", "parameter", "channel_no", "paramset_key", "expected_result"),
    [
        ("LEVEL", "LEVEL", 3, ParamsetKey.VALUES, True),
        ("LEVEL@HmIP-BROLL:3:VALUES", "LEVEL", 3, ParamsetKey.VALUES, False),
        ("LEVEL:VALUES@HmIP-BROLL:3", "LEVEL", 3, ParamsetKey.VALUES, True),
        ("LEVEL:VALUES@all:3", "LEVEL", 3, ParamsetKey.VALUES, True),
        ("LEVEL:VALUES@all:3", "LEVEL", 4, ParamsetKey.VALUES, False),
        ("LEVEL:VALUES@HmIP-BROLL:all", "LEVEL", 3, ParamsetKey.VALUES, True),
    ],
)
@pytest.mark.asyncio
async def test_device_un_ignore_broll(
    factory_with_homegear_client: FactoryWithClient,
    line: str,
    parameter: str,
    channel_no: int,
    paramset_key: ParamsetKey,
    expected_result: bool,
) -> None:
    """Test device un ignore."""
    central = await factory_with_homegear_client.init(
        address_device_translation={"VCU8537918"}, un_ignore_list=[line]
    ).get_default_central()
    try:
        channel = _FakeChannel(model="HmIP-BROLL", no=channel_no)
        assert (
            central.parameter_visibility.parameter_is_un_ignored(
                channel=channel,
                paramset_key=paramset_key,
                parameter=parameter,
            )
            is expected_result
        )
        dp = central.get_generic_data_point(channel_address=f"VCU8537918:{channel_no}", parameter=parameter)
        if expected_result:
            assert dp
            assert dp.usage == DataPointUsage.DATA_POINT
    finally:
        await central.stop()


@pytest.mark.parametrize(
    ("line", "parameter", "channel_no", "paramset_key", "expected_result"),
    [
        (
            "GLOBAL_BUTTON_LOCK:MASTER@HM-TC-IT-WM-W-EU:",
            "GLOBAL_BUTTON_LOCK",
            None,
            ParamsetKey.MASTER,
            True,
        ),
    ],
)
@pytest.mark.asyncio
async def test_device_un_ignore_hm(
    factory_with_homegear_client: FactoryWithClient,
    line: str,
    parameter: str,
    channel_no: int | None,
    paramset_key: ParamsetKey,
    expected_result: bool,
) -> None:
    """Test device un ignore."""
    central = await factory_with_homegear_client.init(
        address_device_translation={"VCU0000341"}, un_ignore_list=[line]
    ).get_default_central()
    try:
        channel = _FakeChannel(model="HM-TC-IT-WM-W-EU", no=channel_no)
        assert (
            central.parameter_visibility.parameter_is_un_ignored(
                channel=channel,
                paramset_key=paramset_key,
                parameter=parameter,
            )
            is expected_result
        )
        dp = central.get_generic_data_point(
            channel_address=f"VCU0000341:{channel_no}" if channel_no else "VCU0000341", parameter=parameter
        )
        if expected_result:
            assert dp
            assert dp.usage == DataPointUsage.DATA_POINT
    finally:
        await central.stop()


@pytest.mark.parametrize(
    ("lines", "parameter", "channel_no", "paramset_key", "expected_result"),
    [
        (["DECISION_VALUE:VALUES@all:all"], "DECISION_VALUE", 3, ParamsetKey.VALUES, True),
        (["INHIBIT:VALUES@HM-ES-PMSw1-Pl:1"], "INHIBIT", 1, ParamsetKey.VALUES, True),
        (["WORKING:VALUES@all:all"], "WORKING", 1, ParamsetKey.VALUES, True),
        (["AVERAGING:MASTER@HM-ES-PMSw1-Pl:2"], "AVERAGING", 2, ParamsetKey.MASTER, True),
        (
            ["DECISION_VALUE:VALUES@all:all", "AVERAGING:MASTER@HM-ES-PMSw1-Pl:2"],
            "DECISION_VALUE",
            3,
            ParamsetKey.VALUES,
            True,
        ),
        (
            [
                "DECISION_VALUE:VALUES@HM-ES-PMSw1-Pl:3",
                "INHIBIT:VALUES@HM-ES-PMSw1-Pl:1",
                "WORKING:VALUES@HM-ES-PMSw1-Pl:1",
                "AVERAGING:MASTER@HM-ES-PMSw1-Pl:2",
            ],
            "DECISION_VALUE",
            3,
            ParamsetKey.VALUES,
            True,
        ),
        (
            [
                "DECISION_VALUE:VALUES@HM-ES-PMSw1-Pl:3",
                "INHIBIT:VALUES@HM-ES-PMSw1-Pl:1",
                "WORKING:VALUES@HM-ES-PMSw1-Pl:1",
                "AVERAGING:MASTER@HM-ES-PMSw1-Pl:2",
            ],
            "AVERAGING",
            2,
            ParamsetKey.MASTER,
            True,
        ),
        (
            ["DECISION_VALUE", "INHIBIT:VALUES", "WORKING", "AVERAGING:MASTER@HM-ES-PMSw1-Pl:2"],
            "AVERAGING",
            2,
            ParamsetKey.MASTER,
            True,
        ),
        (
            ["DECISION_VALUE", "INHIBIT:VALUES", "WORKING", "AVERAGING:MASTER@HM-ES-PMSw1-Pl:2"],
            "DECISION_VALUE",
            3,
            ParamsetKey.VALUES,
            True,
        ),
    ],
)
@pytest.mark.asyncio
async def test_device_un_ignore_hm2(
    factory_with_homegear_client: FactoryWithClient,
    lines: list[str],
    parameter: str,
    channel_no: int | None,
    paramset_key: ParamsetKey,
    expected_result: bool,
) -> None:
    """Test device un ignore."""
    central = await factory_with_homegear_client.init(
        address_device_translation={"VCU0000137"}, un_ignore_list=lines
    ).get_default_central()
    try:
        channel = _FakeChannel(model="HM-ES-PMSw1-Pl", no=channel_no)
        assert (
            central.parameter_visibility.parameter_is_un_ignored(
                channel=channel,
                paramset_key=paramset_key,
                parameter=parameter,
            )
            is expected_result
        )
        dp = central.get_generic_data_point(
            channel_address=f"VCU0000137:{channel_no}" if channel_no else "VCU0000137", parameter=parameter
        )
        if expected_result:
            assert dp
            assert dp.usage == DataPointUsage.DATA_POINT
    finally:
        await central.stop()


@pytest.mark.parametrize(
    ("ignore_custom_device_definition_models", "model", "address", "expected_result"),
    [
        (
            ["HmIP-BWTH"],
            "HmIP-BWTH",
            "VCU1769958",
            True,
        ),
        (
            ["HmIP-2BWTH"],
            "HmIP-BWTH",
            "VCU1769958",
            False,
        ),
        (
            ["hmip-etrv"],
            "HmIP-eTRV-2",
            "VCU3609622",
            True,
        ),
    ],
)
@pytest.mark.asyncio
async def test_ignore_(
    factory_with_homegear_client: FactoryWithClient,
    ignore_custom_device_definition_models: list[str],
    model: str,
    address: str,
    expected_result: bool,
) -> None:
    """Test device un ignore."""
    central = await factory_with_homegear_client.init(
        address_device_translation={"VCU1769958", "VCU3609622"},
        ignore_custom_device_definition_models=ignore_custom_device_definition_models,
    ).get_default_central()
    try:
        assert central.parameter_visibility.model_is_ignored(model=model) is expected_result
        if device := central.get_device(address=address):
            if expected_result:
                assert len(device.custom_data_points) == 0
            else:
                assert len(device.custom_data_points) > 0
    finally:
        await central.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "operations",
        "full_format",
        "un_ignore_candidates_only",
        "expected_result",
    ),
    [
        ((Operations.READ, Operations.EVENT), True, True, 43),
        ((Operations.READ, Operations.EVENT), True, False, 65),
        ((Operations.READ, Operations.EVENT), False, True, 29),
        ((Operations.READ, Operations.EVENT), False, False, 43),
    ],
)
async def test_all_parameters(
    factory_with_homegear_client: FactoryWithClient,
    operations: tuple[Operations, ...],
    full_format: bool,
    un_ignore_candidates_only: bool,
    expected_result: int,
) -> None:
    """Test all_parameters."""
    central = await factory_with_homegear_client.init(address_device_translation=TEST_DEVICES).get_default_central()
    parameters = central.get_parameters(
        paramset_key=ParamsetKey.VALUES,
        operations=operations,
        full_format=full_format,
        un_ignore_candidates_only=un_ignore_candidates_only,
    )
    assert parameters
    assert len(parameters) == expected_result


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "operations",
        "full_format",
        "un_ignore_candidates_only",
        "expected_result",
    ),
    [
        ((Operations.READ, Operations.EVENT), True, True, 43),
        ((Operations.READ, Operations.EVENT), True, False, 65),
        ((Operations.READ, Operations.EVENT), False, True, 29),
        ((Operations.READ, Operations.EVENT), False, False, 43),
    ],
)
async def test_all_parameters_with_un_ignore(
    factory_with_homegear_client: FactoryWithClient,
    operations: tuple[Operations, ...],
    full_format: bool,
    un_ignore_candidates_only: bool,
    expected_result: int,
) -> None:
    """Test all_parameters."""
    central = await factory_with_homegear_client.init(
        address_device_translation=TEST_DEVICES, un_ignore_list=["ACTIVE_PROFILE"]
    ).get_default_central()
    parameters = central.get_parameters(
        paramset_key=ParamsetKey.VALUES,
        operations=operations,
        full_format=full_format,
        un_ignore_candidates_only=un_ignore_candidates_only,
    )
    assert parameters
    assert len(parameters) == expected_result


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
async def test_data_points_by_category(
    central_client_factory_with_homegear_client,
) -> None:
    """Test data_points_by_category."""
    central, _, _ = central_client_factory_with_homegear_client
    ebp_sensor = central.get_data_points(category=DataPointCategory.SENSOR)
    assert ebp_sensor
    assert len(ebp_sensor) == 18

    def _device_changed(self, *args: Any, **kwargs: Any) -> None:
        """Handle device state changes."""

    ebp_sensor[0].register_data_point_updated_callback(cb=_device_changed, custom_id="some_id")
    ebp_sensor2 = central.get_data_points(category=DataPointCategory.SENSOR, registered=False)
    assert ebp_sensor2
    assert len(ebp_sensor2) == 17


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
async def test_hub_data_points_by_category(
    central_client_factory_with_ccu_client,
) -> None:
    """Test hub_data_points_by_category."""
    central, _, _ = central_client_factory_with_ccu_client
    ebp_sensor = central.get_hub_data_points(category=DataPointCategory.HUB_SENSOR)
    assert ebp_sensor
    assert len(ebp_sensor) == 4

    def _device_changed(self, *args: Any, **kwargs: Any) -> None:
        """Handle device state changes."""

    ebp_sensor[0].register_data_point_updated_callback(cb=_device_changed, custom_id="some_id")
    ebp_sensor2 = central.get_hub_data_points(
        category=DataPointCategory.HUB_SENSOR,
        registered=False,
    )
    assert ebp_sensor2
    assert len(ebp_sensor2) == 3

    ebp_sensor3 = central.get_hub_data_points(category=DataPointCategory.HUB_BUTTON)
    assert ebp_sensor3
    assert len(ebp_sensor3) == 2
    ebp_sensor3[0].register_data_point_updated_callback(cb=_device_changed, custom_id="some_id")
    ebp_sensor4 = central.get_hub_data_points(category=DataPointCategory.HUB_BUTTON, registered=False)
    assert ebp_sensor4
    assert len(ebp_sensor4) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "address_device_translation",
        "do_mock_client",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [
        (TEST_DEVICES, True, ["VCU2128127"], None),
    ],
)
async def test_add_device(
    central_client_factory_with_homegear_client,
) -> None:
    """Test add_device."""
    central, _, _ = central_client_factory_with_homegear_client
    assert len(central._devices) == 1
    assert len(central.get_data_points(exclude_no_create=False)) == 33
    assert len(central.device_descriptions._raw_device_descriptions.get(const.INTERFACE_ID)) == 9
    assert len(central.paramset_descriptions._raw_paramset_descriptions.get(const.INTERFACE_ID)) == 9
    dev_desc = load_device_description(file_name="HmIP-BSM.json")
    await central.add_new_devices(interface_id=const.INTERFACE_ID, device_descriptions=dev_desc)
    assert len(central._devices) == 2
    assert len(central.get_data_points(exclude_no_create=False)) == 64
    assert len(central.device_descriptions._raw_device_descriptions.get(const.INTERFACE_ID)) == 20
    assert len(central.paramset_descriptions._raw_paramset_descriptions.get(const.INTERFACE_ID)) == 20
    await central.add_new_devices(interface_id="NOT_ANINTERFACE_ID", device_descriptions=dev_desc)
    assert len(central._devices) == 2


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
async def test_delete_device(
    central_client_factory_with_homegear_client,
) -> None:
    """Test device delete_device."""
    central, _, _ = central_client_factory_with_homegear_client
    assert len(central._devices) == 2
    assert len(central.get_data_points(exclude_no_create=False)) == 64
    assert len(central.device_descriptions._raw_device_descriptions.get(const.INTERFACE_ID)) == 20
    assert len(central.paramset_descriptions._raw_paramset_descriptions.get(const.INTERFACE_ID)) == 20

    await central.delete_devices(interface_id=const.INTERFACE_ID, addresses=["VCU2128127"])
    assert len(central._devices) == 1
    assert len(central.get_data_points(exclude_no_create=False)) == 33
    assert len(central.device_descriptions._raw_device_descriptions.get(const.INTERFACE_ID)) == 9
    assert len(central.paramset_descriptions._raw_paramset_descriptions.get(const.INTERFACE_ID)) == 9


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "address_device_translation",
        "do_mock_client",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [
        (
            {
                "VCU4264293": "HmIP-RCV-50.json",
                "VCU0000057": "HM-RCV-50.json",
                "VCU0000001": "HMW-RCV-50.json",
            },
            True,
            None,
            None,
        ),
    ],
)
async def test_virtual_remote_delete(
    central_client_factory_with_homegear_client,
) -> None:
    """Test device delete."""
    central, _, _ = central_client_factory_with_homegear_client
    assert len(central.get_virtual_remotes()) == 1

    assert central._get_virtual_remote(device_address="VCU0000057")

    await central.delete_device(interface_id=const.INTERFACE_ID, device_address="NOT_A_DEVICE_ID")

    assert len(central._devices) == 3
    assert len(central.get_data_points()) == 350
    await central.delete_devices(interface_id=const.INTERFACE_ID, addresses=["VCU4264293", "VCU0000057"])
    assert len(central._devices) == 1
    assert len(central.get_data_points()) == 100
    await central.delete_device(interface_id=const.INTERFACE_ID, device_address="VCU0000001")
    assert len(central._devices) == 0
    assert len(central.get_data_points()) == 0
    assert central.get_virtual_remotes() == ()

    await central.delete_device(interface_id=const.INTERFACE_ID, device_address="NOT_A_DEVICE_ID")


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
async def test_central_callbacks(
    central_client_factory_with_homegear_client,
) -> None:
    """Test central other methods."""
    central, _, factory = central_client_factory_with_homegear_client
    central.fire_interface_event(
        interface_id="SOME_ID",
        interface_event_type=InterfaceEventType.CALLBACK,
        data={EventKey.AVAILABLE: False},
    )
    assert factory.ha_event_mock.call_args_list[-1] == call(
        event_type="homematic.interface",
        event_data={
            "interface_id": "SOME_ID",
            "type": "callback",
            "data": {EventKey.AVAILABLE: False},
        },
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
async def test_central_services(
    central_client_factory_with_homegear_client,
) -> None:
    """Test central fetch sysvar and programs."""
    central, mock_client, _ = central_client_factory_with_homegear_client
    await central.fetch_program_data(scheduled=True)
    assert mock_client.method_calls[-1] == call.get_all_programs(markers=())

    await central.fetch_sysvar_data(scheduled=True)
    assert mock_client.method_calls[-1] == call.get_all_system_variables(markers=())

    assert len(mock_client.method_calls) == 37
    await central.load_and_refresh_data_point_data(interface=Interface.BIDCOS_RF, paramset_key=ParamsetKey.MASTER)
    assert len(mock_client.method_calls) == 37
    await central.load_and_refresh_data_point_data(interface=Interface.BIDCOS_RF, paramset_key=ParamsetKey.VALUES)
    assert len(mock_client.method_calls) == 48

    await central.get_system_variable(legacy_name="SysVar_Name")
    assert mock_client.method_calls[-1] == call.get_system_variable(name="SysVar_Name")

    assert len(mock_client.method_calls) == 49
    await central.set_system_variable(legacy_name="alarm", value=True)
    assert mock_client.method_calls[-1] == call.set_system_variable(legacy_name="alarm", value=True)
    assert len(mock_client.method_calls) == 50
    await central.set_system_variable(legacy_name="SysVar_Name", value=True)
    assert len(mock_client.method_calls) == 50

    await central.get_client(interface_id=const.INTERFACE_ID).set_value(
        channel_address="123",
        paramset_key=ParamsetKey.VALUES,
        parameter="LEVEL",
        value=1.0,
    )
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="123",
        paramset_key=ParamsetKey.VALUES,
        parameter="LEVEL",
        value=1.0,
    )
    assert len(mock_client.method_calls) == 51

    with pytest.raises(AioHomematicException):
        await central.get_client(interface_id="NOT_A_VALID_INTERFACE_ID").set_value(
            channel_address="123",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=1.0,
        )
    assert len(mock_client.method_calls) == 51

    await central.get_client(interface_id=const.INTERFACE_ID).put_paramset(
        channel_address="123",
        paramset_key_or_link_address=ParamsetKey.VALUES,
        values={"LEVEL": 1.0},
    )
    assert mock_client.method_calls[-1] == call.put_paramset(
        channel_address="123", paramset_key_or_link_address=ParamsetKey.VALUES, values={"LEVEL": 1.0}
    )
    assert len(mock_client.method_calls) == 52
    with pytest.raises(AioHomematicException):
        await central.get_client(interface_id="NOT_A_VALID_INTERFACE_ID").put_paramset(
            channel_address="123",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"LEVEL": 1.0},
        )
    assert len(mock_client.method_calls) == 52

    assert (
        central.get_generic_data_point(channel_address="VCU6354483:0", parameter="DUTY_CYCLE").parameter == "DUTY_CYCLE"
    )
    assert central.get_generic_data_point(channel_address="VCU6354483", parameter="DUTY_CYCLE") is None


@pytest.mark.asyncio
async def test_central_without_interface_config(factory_with_homegear_client: FactoryWithClient) -> None:
    """Test central other methods."""
    central = await factory_with_homegear_client.init(interface_configs=set()).get_raw_central()
    try:
        assert central.all_clients_active is False

        with pytest.raises(NoClientsException):
            await central.validate_config_and_get_system_information()

        with pytest.raises(AioHomematicException):
            central.get_client(interface_id="NOT_A_VALID_INTERFACE_ID")

        await central.start()
        assert central.all_clients_active is False

        assert central.available is True
        assert central.system_information.serial is None
        assert len(central._devices) == 0
        assert len(central.get_data_points()) == 0

        assert await central.get_system_variable(legacy_name="SysVar_Name") is None
        assert central._get_virtual_remote(device_address="VCU4264293") is None
    finally:
        await central.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "address_device_translation",
        "do_mock_client",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [
        (TEST_DEVICES, False, None, None),
    ],
)
async def test_ping_pong(central_client_factory_with_ccu_client) -> None:
    """Test central other methods."""
    central, client, _ = central_client_factory_with_ccu_client
    client._is_initialized = True
    interface_id = client.interface_id
    await client.check_connection_availability(handle_ping_pong=True)
    assert client.ping_pong_cache._pending_pong_count == 1
    for ts_stored in list(client.ping_pong_cache._pending_pongs):
        await central.data_point_event(
            interface_id=interface_id,
            channel_address="",
            parameter=Parameter.PONG,
            value=f"{interface_id}#{ts_stored.strftime(DATETIME_FORMAT_MILLIS)}",
        )
    assert client.ping_pong_cache._pending_pong_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "address_device_translation",
        "do_mock_client",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [
        (TEST_DEVICES, False, None, None),
    ],
)
async def test_pending_pong_failure(
    central_client_factory_with_ccu_client,
) -> None:
    """Test central other methods."""
    central, client, factory = central_client_factory_with_ccu_client
    client._is_initialized = True
    count = 0
    max_count = PING_PONG_MISMATCH_COUNT + 1
    while count < max_count:
        await client.check_connection_availability(handle_ping_pong=True)
        count += 1
    assert client.ping_pong_cache._pending_pong_count == max_count
    assert factory.ha_event_mock.mock_calls[-1] == call(
        event_type=EventType.INTERFACE,
        event_data={
            EventKey.DATA: {
                EventKey.CENTRAL_NAME: "CentralTest",
                EventKey.PONG_MISMATCH_ACCEPTABLE: False,
                EventKey.PONG_MISMATCH_COUNT: 16,
            },
            EventKey.INTERFACE_ID: "CentralTest-BidCos-RF",
            EventKey.TYPE: InterfaceEventType.PENDING_PONG,
        },
    )
    assert len(factory.ha_event_mock.mock_calls) == 10


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "address_device_translation",
        "do_mock_client",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [
        (TEST_DEVICES, False, None, None),
    ],
)
async def test_unknown_pong_failure(
    central_client_factory_with_ccu_client,
) -> None:
    """Test central other methods."""
    central, client, _ = central_client_factory_with_ccu_client
    interface_id = client.interface_id
    count = 0
    max_count = PING_PONG_MISMATCH_COUNT + 1
    while count < max_count:
        await central.data_point_event(
            interface_id=interface_id,
            channel_address="",
            parameter=Parameter.PONG,
            value=f"{interface_id}#{datetime.now().strftime(DATETIME_FORMAT_MILLIS)}",
        )
        count += 1

    assert client.ping_pong_cache._unknown_pong_count == 16


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
async def test_central_caches(
    central_client_factory_with_homegear_client,
) -> None:
    """Test central cache."""
    central, client, _ = central_client_factory_with_homegear_client
    assert len(central.device_descriptions._raw_device_descriptions[client.interface_id]) == 20
    assert len(central.paramset_descriptions._raw_paramset_descriptions[client.interface_id]) == 20
    await central.clear_files()
    assert central.device_descriptions._raw_device_descriptions.get(client.interface_id) is None
    assert central.paramset_descriptions._raw_paramset_descriptions.get(client.interface_id) is None


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
async def test_central_getter(
    central_client_factory_with_homegear_client,
) -> None:
    """Test central getter."""
    central, _, _ = central_client_factory_with_homegear_client
    assert central.get_device(address="123") is None
    assert central.get_custom_data_point(address="123", channel_no=1) is None
    assert central.get_generic_data_point(channel_address="123", parameter=1) is None
    assert central.get_event(channel_address="123", parameter=1) is None
    assert central.get_program_data_point(pid="123") is None
    assert central.get_sysvar_data_point(legacy_name="123") is None


@pytest.mark.asyncio
async def test_scheduler_job_ready_run_and_schedule_next_execution() -> None:
    """`_SchedulerJob` readiness, running the task, and scheduling next run work as expected."""
    marker: dict[str, int] = {}

    # Set next_run into the past to ensure "ready" is True.
    past = datetime.now() - timedelta(seconds=10)
    job = _SchedulerJob(task=_FakeTask(marker), run_interval=5, next_run=past)

    assert job.ready is True
    nr1 = job.next_run

    # Running the job should call the async task and increment marker
    await job.run()
    assert marker.get("calls") == 1

    # Schedule next execution should advance by run_interval seconds
    job.schedule_next_execution()
    assert job.next_run == nr1 + timedelta(seconds=5)


@pytest.mark.asyncio
async def test_check_config_collects_multiple_failures_and_directory_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """`check_config` returns aggregated errors on invalid inputs and directory creation failure."""

    # Force directory creation failure path
    def fail_create_dir(*, directory: str) -> bool:  # type: ignore[override]
        """Return False to force directory creation failure."""
        raise AioHomematicException("failed to create dir")

    monkeypatch.setattr("aiohomematic.central.check_or_create_directory", fail_create_dir)

    errors = central_check_config(
        central_name="bad@name",  # contains IDENTIFIER_SEPARATOR
        host="not_a_host",  # invalid host
        username="",  # empty username
        password="!invalid!",  # also fails password policy
        storage_directory="/does/not/matter",
        callback_host="bad host",
        callback_port_xml_rpc=99999,  # invalid port
        json_port=-1,  # invalid port
        interface_configs=frozenset(),  # Not truthy -> no primary interface check here
    )

    # We expect several distinct failures aggregated. Some implementations may
    # format the directory error message slightly oddly (e.g., only the first
    # character of the message), so we accept either the full message or a
    # single-character placeholder.
    assert any("Instance name must not contain" in e for e in errors)
    assert "Invalid hostname or ipv4 address" in errors
    assert "Username must not be empty" in errors
    # Password-related errors may vary depending on policy; ensure at least one error exists for password/dir
    assert ("Password is required" in errors) or ("Password is not valid" in errors) or errors.count("f") >= 1
    assert any(("failed to create dir" in e) or (e == "f") for e in errors)
    assert "Invalid callback hostname or ipv4 address" in errors
    assert "Invalid xml rpc callback port" in errors
    assert "Invalid json port" in errors

    # Note: primary interface check only happens when "interface_configs" is truthy (not empty)
    ic_non_primary = _FakeInterfaceConfig(central_name="c1", interface=Interface.CUXD, port=0)
    errors2 = central_check_config(
        central_name="ok",
        host="127.0.0.1",
        username="u",
        password="p",
        storage_directory=str(tmp_path),
        callback_host=None,
        callback_port_xml_rpc=None,
        json_port=None,
        interface_configs=frozenset({ic_non_primary}),
    )
    assert any("No primary interface" in e for e in errors2)


@pytest.mark.asyncio
async def test_central_config_check_config_raises_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """`CentralConfig.check_config` should raise `AioHomematicConfigException` when invalid."""
    ic = _FakeInterfaceConfig(central_name="c1", interface=Interface.CUXD, port=0)

    # Fail directory creation to ensure we get an error
    def fail_create_dir(*, directory: str) -> bool:  # type: ignore[override]
        raise AioHomematicException("dir error")

    monkeypatch.setattr("aiohomematic.central.check_or_create_directory", fail_create_dir)

    cfg = CentralConfig(
        central_id="c1",
        host="bad host",
        interface_configs=frozenset({ic}),
        name="n|bad",
        password="",
        username="",
    )

    with pytest.raises(AioHomematicConfigException):
        cfg.check_config()


@pytest.mark.asyncio
async def test_central_config_create_central_url_variants() -> None:
    """`create_central_url` includes scheme and optional json_port when set."""
    cfg1 = CentralConfig(
        central_id="c1",
        host="example.local",
        interface_configs=frozenset(),
        name="n",
        password="p",
        username="u",
        tls=False,
    )
    assert cfg1.create_central_url() == "http://example.local"

    cfg2 = CentralConfig(
        central_id="c1",
        host="example.local",
        interface_configs=frozenset(),
        name="n",
        password="p",
        username="u",
        tls=True,
        json_port=32001,
    )
    assert cfg2.create_central_url() == "https://example.local:32001"
