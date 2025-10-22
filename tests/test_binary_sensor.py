"""Tests for binary_sensor data points of aiohomematic."""

from __future__ import annotations

from datetime import datetime
from typing import cast

import pytest

from aiohomematic.const import DataPointUsage
from aiohomematic.model.generic import DpBinarySensor
from aiohomematic.model.hub import SysvarDpBinarySensor
from aiohomematic_support import const

TEST_DEVICES: dict[str, str] = {
    "VCU5864966": "HmIP-SWDO-I.json",
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
async def test_hmbinarysensor(
    central_client_factory_with_pydevccu_client,
) -> None:
    """Test HmBinarySensor."""
    central, mock_client, _ = central_client_factory_with_pydevccu_client
    binary_sensor: DpBinarySensor = cast(
        DpBinarySensor,
        central.get_generic_data_point(channel_address="VCU5864966:1", parameter="STATE"),
    )
    assert binary_sensor.usage == DataPointUsage.DATA_POINT
    assert binary_sensor.value is False
    assert binary_sensor.is_writeable is False
    assert binary_sensor.visible is True
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU5864966:1", parameter="STATE", value=1
    )
    assert binary_sensor.value is True
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU5864966:1", parameter="STATE", value=0
    )
    assert binary_sensor.value is False
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU5864966:1", parameter="STATE", value=None
    )
    assert binary_sensor.value is False

    call_count = len(mock_client.method_calls)
    await binary_sensor.send_value(value=True)
    assert call_count == len(mock_client.method_calls)


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
async def test_hmsysvarbinarysensor(
    central_client_factory_with_local_client,
) -> None:
    """Test HmSysvarBinarySensor."""
    central, _, _ = central_client_factory_with_local_client
    binary_sensor: SysvarDpBinarySensor = cast(
        SysvarDpBinarySensor,
        central.get_sysvar_data_point(legacy_name="logic"),
    )
    assert binary_sensor.name == "logic"
    assert binary_sensor.full_name == "CentralTest logic"
    assert binary_sensor.value is False
    assert binary_sensor.is_extended is False
    assert binary_sensor._data_type == "LOGIC"
    assert binary_sensor.value is False
    binary_sensor.write_value(value=True, write_at=datetime.now())
    assert binary_sensor.value is True
