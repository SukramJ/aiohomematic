"""Tests for sensor data points of aiohomematic."""

from __future__ import annotations

from typing import cast

from aiohomematic_test_support import const
import pytest

from aiohomematic.const import DataPointUsage
from aiohomematic.model.generic import DpSensor
from aiohomematic.model.hub import SysvarDpSensor

TEST_DEVICES: dict[str, str] = {
    "VCU7981740": "HmIP-SRH.json",
    "VCU3941846": "HMIP-PSM.json",
    "VCU8205532": "HmIP-SCTH230.json",
}

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
async def test_hmsensor_psm(
    central_client_factory_with_pydevccu_client,
) -> None:
    """Test HmSensor."""
    central, _, _ = central_client_factory_with_pydevccu_client
    sensor: DpSensor = cast(
        DpSensor, central.get_generic_data_point(channel_address="VCU3941846:6", parameter="VOLTAGE")
    )
    assert sensor.usage == DataPointUsage.DATA_POINT
    assert sensor.unit == "V"
    assert sensor.values is None
    assert sensor.value is None
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU3941846:6", parameter="VOLTAGE", value=120
    )
    assert sensor.value == 120.0
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU3941846:6", parameter="VOLTAGE", value=234.00
    )
    assert sensor.value == 234.00

    sensor2: DpSensor = cast(
        DpSensor,
        central.get_generic_data_point(channel_address="VCU3941846:0", parameter="RSSI_DEVICE"),
    )
    assert sensor2.usage == DataPointUsage.DATA_POINT
    assert sensor2.unit == "dBm"
    assert sensor2.values is None
    assert sensor2.value is None
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU3941846:0", parameter="RSSI_DEVICE", value=24
    )
    assert sensor2.value == -24
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU3941846:0", parameter="RSSI_DEVICE", value=-40
    )
    assert sensor2.value == -40
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU3941846:0", parameter="RSSI_DEVICE", value=-160
    )
    assert sensor2.value == -96
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU3941846:0", parameter="RSSI_DEVICE", value=160
    )
    assert sensor2.value == -96
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU3941846:0", parameter="RSSI_DEVICE", value=400
    )
    assert sensor2.value is None

    sensor3: DpSensor = cast(
        DpSensor,
        central.get_generic_data_point(channel_address="VCU8205532:1", parameter="CONCENTRATION"),
    )
    assert sensor3.usage == DataPointUsage.DATA_POINT
    assert sensor3.unit == "ppm"
    assert sensor3.values is None
    assert sensor3.value is None


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
async def test_hmsensor_srh(
    central_client_factory_with_pydevccu_client,
) -> None:
    """Test HmSensor."""
    central, _, _ = central_client_factory_with_pydevccu_client
    sensor: DpSensor = cast(DpSensor, central.get_generic_data_point(channel_address="VCU7981740:1", parameter="STATE"))
    assert sensor.usage == DataPointUsage.DATA_POINT
    assert sensor.unit is None
    assert sensor.values == ("CLOSED", "TILTED", "OPEN")
    assert sensor.value is None
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU7981740:1", parameter="STATE", value=0
    )
    assert sensor.value == "CLOSED"
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU7981740:1", parameter="STATE", value=2
    )
    assert sensor.value == "OPEN"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "port",
        "address_device_translation",
        "do_mock_client",
        "add_sysvars",
        "add_programs",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [
        (const.CCU_MINI_PORT, {}, True, True, False, None, None),
    ],
)
async def test_hmsysvarsensor(
    central_client_factory_with_local_client,
) -> None:
    """Test HmSysvarSensor."""
    central, _, _ = central_client_factory_with_local_client
    sensor: SysvarDpSensor = cast(SysvarDpSensor, central.get_sysvar_data_point(legacy_name="list"))
    assert sensor.usage == DataPointUsage.DATA_POINT
    assert sensor.available is True
    assert sensor.unit is None
    assert sensor.values == ("v1", "v2", "v3")
    assert sensor.value == "v1"

    sensor2: SysvarDpSensor = cast(SysvarDpSensor, central.get_sysvar_data_point(legacy_name="float"))
    assert sensor2.usage == DataPointUsage.DATA_POINT
    assert sensor2.unit is None
    assert sensor2.values is None
    assert sensor2.value == 23.2
