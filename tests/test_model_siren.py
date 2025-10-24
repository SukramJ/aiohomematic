"""Tests for siren data points of aiohomematic."""

from __future__ import annotations

from typing import cast
from unittest.mock import call

import pytest

from aiohomematic.const import WAIT_FOR_CALLBACK, DataPointUsage, ParamsetKey
from aiohomematic.model.custom import CustomDpIpSiren, CustomDpIpSirenSmoke
from aiohomematic_test_support import const
from aiohomematic_test_support.helper import get_prepared_custom_data_point

TEST_DEVICES: set[str] = {"VCU8249617", "VCU2822385"}

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
async def test_ceipsiren(
    central_client_factory_with_homegear_client,
) -> None:
    """Test CustomDpIpSiren."""
    central, mock_client, _ = central_client_factory_with_homegear_client
    siren: CustomDpIpSiren = cast(CustomDpIpSiren, get_prepared_custom_data_point(central, "VCU8249617", 3))
    assert siren.usage == DataPointUsage.CDP_PRIMARY
    assert siren.service_method_names == ("turn_off", "turn_on")

    assert siren.is_on is False
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU8249617:3", parameter="ACOUSTIC_ALARM_ACTIVE", value=1
    )
    assert siren.is_on is True
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU8249617:3", parameter="ACOUSTIC_ALARM_ACTIVE", value=0
    )
    assert siren.is_on is False
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU8249617:3", parameter="OPTICAL_ALARM_ACTIVE", value=1
    )
    assert siren.is_on is True
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU8249617:3", parameter="OPTICAL_ALARM_ACTIVE", value=0
    )
    assert siren.is_on is False

    await siren.turn_on(
        acoustic_alarm="FREQUENCY_RISING_AND_FALLING",
        optical_alarm="BLINKING_ALTERNATELY_REPEATING",
        duration=30,
    )
    assert mock_client.method_calls[-1] == call.put_paramset(
        channel_address="VCU8249617:3",
        paramset_key_or_link_address=ParamsetKey.VALUES,
        values={
            "ACOUSTIC_ALARM_SELECTION": 3,
            "OPTICAL_ALARM_SELECTION": 1,
            "DURATION_UNIT": 0,
            "DURATION_VALUE": 30,
        },
        wait_for_callback=WAIT_FOR_CALLBACK,
    )

    await siren.turn_on(
        acoustic_alarm="FREQUENCY_RISING_AND_FALLING",
        optical_alarm="BLINKING_ALTERNATELY_REPEATING",
        duration=30,
    )
    assert mock_client.method_calls[-2] == call.put_paramset(
        channel_address="VCU8249617:3",
        paramset_key_or_link_address=ParamsetKey.VALUES,
        values={
            "ACOUSTIC_ALARM_SELECTION": 3,
            "OPTICAL_ALARM_SELECTION": 1,
            "DURATION_UNIT": 0,
            "DURATION_VALUE": 30,
        },
        wait_for_callback=WAIT_FOR_CALLBACK,
    )

    from aiohomematic.exceptions import ValidationException

    with pytest.raises(ValidationException):
        await siren.turn_on(
            acoustic_alarm="not_in_list",
            optical_alarm="BLINKING_ALTERNATELY_REPEATING",
            duration=30,
        )

    with pytest.raises(ValidationException):
        await siren.turn_on(
            acoustic_alarm="FREQUENCY_RISING_AND_FALLING",
            optical_alarm="not_in_list",
            duration=30,
        )

    await siren.turn_off()
    assert mock_client.method_calls[-1] == call.put_paramset(
        channel_address="VCU8249617:3",
        paramset_key_or_link_address=ParamsetKey.VALUES,
        values={
            "ACOUSTIC_ALARM_SELECTION": 0,
            "OPTICAL_ALARM_SELECTION": 0,
            "DURATION_UNIT": 0,
            "DURATION_VALUE": 0,
        },
        wait_for_callback=WAIT_FOR_CALLBACK,
    )

    await siren.turn_off()
    call_count = len(mock_client.method_calls)
    await siren.turn_off()
    assert (call_count + 1) == len(mock_client.method_calls)


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
async def test_ceipsirensmoke(
    central_client_factory_with_homegear_client,
) -> None:
    """Test CustomDpIpSirenSmoke."""
    central, mock_client, _ = central_client_factory_with_homegear_client
    siren: CustomDpIpSirenSmoke = cast(CustomDpIpSirenSmoke, get_prepared_custom_data_point(central, "VCU2822385", 1))
    assert siren.usage == DataPointUsage.CDP_PRIMARY

    assert siren.is_on is False
    await central.data_point_event(
        interface_id=const.INTERFACE_ID,
        channel_address="VCU2822385:1",
        parameter="SMOKE_DETECTOR_ALARM_STATUS",
        value=1,
    )
    assert siren.is_on is True
    await central.data_point_event(
        interface_id=const.INTERFACE_ID,
        channel_address="VCU2822385:1",
        parameter="SMOKE_DETECTOR_ALARM_STATUS",
        value=2,
    )
    assert siren.is_on is True
    await central.data_point_event(
        interface_id=const.INTERFACE_ID,
        channel_address="VCU2822385:1",
        parameter="SMOKE_DETECTOR_ALARM_STATUS",
        value=3,
    )
    assert siren.is_on is True
    await central.data_point_event(
        interface_id=const.INTERFACE_ID,
        channel_address="VCU2822385:1",
        parameter="SMOKE_DETECTOR_ALARM_STATUS",
        value=0,
    )
    assert siren.is_on is False

    await siren.turn_on()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU2822385:1",
        paramset_key=ParamsetKey.VALUES,
        parameter="SMOKE_DETECTOR_COMMAND",
        value=2,
        wait_for_callback=WAIT_FOR_CALLBACK,
    )

    await siren.turn_off()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU2822385:1",
        paramset_key=ParamsetKey.VALUES,
        parameter="SMOKE_DETECTOR_COMMAND",
        value=1,
        wait_for_callback=WAIT_FOR_CALLBACK,
    )

    call_count = len(mock_client.method_calls)
    await siren.turn_off()
    assert (call_count + 1) == len(mock_client.method_calls)
