"""Tests for binary_sensor data points of hahomematic."""

from __future__ import annotations

from typing import cast
from unittest.mock import Mock

import pytest

from hahomematic.central import CentralUnit
from hahomematic.client import Client
from hahomematic.const import DataPointUsage
from hahomematic.model.generic import DpBinarySensor
from hahomematic.model.hub import SysvarDpBinarySensor

from tests import const, helper

TEST_DEVICES: dict[str, str] = {
    "VCU5864966": "HmIP-SWDO-I.json",
}

# pylint: disable=protected-access


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
async def test_hmbinarysensor(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test HmBinarySensor."""
    central, mock_client, _ = central_client_factory
    binary_sensor: DpBinarySensor = cast(
        DpBinarySensor,
        central.get_generic_data_point("VCU5864966:1", "STATE"),
    )
    assert binary_sensor.usage == DataPointUsage.DATA_POINT
    assert binary_sensor.value is False
    assert binary_sensor.is_writeable is False
    assert binary_sensor.visible is True
    await central.data_point_event(const.INTERFACE_ID, "VCU5864966:1", "STATE", 1)
    assert binary_sensor.value is True
    await central.data_point_event(const.INTERFACE_ID, "VCU5864966:1", "STATE", 0)
    assert binary_sensor.value is False
    await central.data_point_event(const.INTERFACE_ID, "VCU5864966:1", "STATE", None)
    assert binary_sensor.value is False

    call_count = len(mock_client.method_calls)
    await binary_sensor.send_value(True)
    assert call_count == len(mock_client.method_calls)


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
        ({}, True, True, False, None, None),
    ],
)
async def test_hmsysvarbinarysensor(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test HmSysvarBinarySensor."""
    central, _, _ = central_client_factory
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
    binary_sensor.write_value(True)
    assert binary_sensor.value is True
