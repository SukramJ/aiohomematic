"""Tests for valve data points of hahomematic."""

from __future__ import annotations

from typing import cast
from unittest.mock import Mock, call

import pytest

from hahomematic.central import CentralUnit
from hahomematic.client import Client
from hahomematic.const import WAIT_FOR_CALLBACK, DataPointUsage, ParamsetKey
from hahomematic.model.custom import CustomDpIpIrrigationValve

from tests import helper

TEST_DEVICES: dict[str, str] = {
    "VCU8976407": "ELV-SH-WSM.json",
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
async def test_ceipirrigationvalve(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test CustomDpValve."""
    central, mock_client, _ = central_client_factory
    valve: CustomDpIpIrrigationValve = cast(
        CustomDpIpIrrigationValve, helper.get_prepared_custom_data_point(central, "VCU8976407", 4)
    )
    assert valve.usage == DataPointUsage.CDP_PRIMARY
    assert valve.service_method_names == ("close", "open")

    await valve.close()
    assert valve.value is False
    assert valve.group_value is False
    await valve.open()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU8976407:4",
        paramset_key=ParamsetKey.VALUES,
        parameter="STATE",
        value=True,
        wait_for_callback=None,
    )
    assert valve.value is True
    await valve.close()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU8976407:4",
        paramset_key=ParamsetKey.VALUES,
        parameter="STATE",
        value=False,
        wait_for_callback=WAIT_FOR_CALLBACK,
    )
    assert valve.value is False
    await valve.open(on_time=60)
    assert mock_client.method_calls[-1] == call.put_paramset(
        channel_address="VCU8976407:4",
        paramset_key_or_link_address=ParamsetKey.VALUES,
        values={"ON_TIME": 60.0, "STATE": True},
        wait_for_callback=WAIT_FOR_CALLBACK,
    )
    assert valve.value is True

    await valve.close()
    valve.set_timer_on_time(35.4)
    await valve.open()
    assert mock_client.method_calls[-1] == call.put_paramset(
        channel_address="VCU8976407:4",
        paramset_key_or_link_address=ParamsetKey.VALUES,
        values={"ON_TIME": 35.4, "STATE": True},
        wait_for_callback=WAIT_FOR_CALLBACK,
    )

    await valve.open()
    call_count = len(mock_client.method_calls)
    await valve.open()
    assert call_count == len(mock_client.method_calls)

    await valve.close()
    call_count = len(mock_client.method_calls)
    await valve.close()
    assert call_count == len(mock_client.method_calls)
