"""Tests for switch data points of aiohomematic."""

from __future__ import annotations

from typing import cast
from unittest.mock import call

import pytest

from aiohomematic.const import DataPointUsage, EventType
from aiohomematic.model.event import ClickEvent, DeviceErrorEvent, ImpulseEvent
from aiohomematic_test_support import const

TEST_DEVICES: set[str] = {"VCU2128127", "VCU0000263"}

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
async def test_clickevent(
    central_client_factory_with_homegear_client,
) -> None:
    """Test ClickEvent."""
    central, _, factory = central_client_factory_with_homegear_client
    event: ClickEvent = cast(ClickEvent, central.get_event(channel_address="VCU2128127:1", parameter="PRESS_SHORT"))
    assert event.usage == DataPointUsage.EVENT
    assert event.event_type == EventType.KEYPRESS
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU2128127:1", parameter="PRESS_SHORT", value=True
    )
    assert factory.ha_event_mock.call_args_list[-1] == call(
        event_type="homematic.keypress",
        event_data={
            "interface_id": const.INTERFACE_ID,
            "address": "VCU2128127",
            "channel_no": 1,
            "model": "HmIP-BSM",
            "parameter": "PRESS_SHORT",
            "value": True,
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
async def test_impulseevent(
    central_client_factory_with_homegear_client,
) -> None:
    """Test ImpulseEvent."""
    central, _, factory = central_client_factory_with_homegear_client
    event: ImpulseEvent = cast(ImpulseEvent, central.get_event(channel_address="VCU0000263:1", parameter="SEQUENCE_OK"))
    assert event.usage == DataPointUsage.EVENT
    assert event.event_type == EventType.IMPULSE
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU0000263:1", parameter="SEQUENCE_OK", value=True
    )
    assert factory.ha_event_mock.call_args_list[-1] == call(
        event_type="homematic.impulse",
        event_data={
            "interface_id": const.INTERFACE_ID,
            "address": "VCU0000263",
            "channel_no": 1,
            "model": "HM-Sen-EP",
            "parameter": "SEQUENCE_OK",
            "value": True,
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
async def test_deviceerrorevent(
    central_client_factory_with_homegear_client,
) -> None:
    """Test DeviceErrorEvent."""
    central, _, factory = central_client_factory_with_homegear_client
    event: DeviceErrorEvent = cast(
        DeviceErrorEvent,
        central.get_event(channel_address="VCU2128127:0", parameter="ERROR_OVERHEAT"),
    )
    assert event.usage == DataPointUsage.EVENT
    assert event.event_type == EventType.DEVICE_ERROR
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU2128127:0", parameter="ERROR_OVERHEAT", value=True
    )
    assert factory.ha_event_mock.call_args_list[-1] == call(
        event_type="homematic.device_error",
        event_data={
            "interface_id": const.INTERFACE_ID,
            "address": "VCU2128127",
            "channel_no": 0,
            "model": "HmIP-BSM",
            "parameter": "ERROR_OVERHEAT",
            "value": True,
        },
    )
