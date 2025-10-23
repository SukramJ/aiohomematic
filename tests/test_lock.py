"""Tests for button data points of aiohomematic."""

from __future__ import annotations

from typing import cast
from unittest.mock import call

import pytest

from aiohomematic.const import WAIT_FOR_CALLBACK, DataPointUsage, ParamsetKey
from aiohomematic.model.custom import CustomDpIpLock, CustomDpRfLock
from aiohomematic_test_support import const
from aiohomematic_test_support.helper import get_prepared_custom_data_point

TEST_DEVICES: set[str] = {"VCU9724704", "VCU0000146", "VCU3609622", "VCU0000341"}

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
async def test_cerflock(
    central_client_factory_with_pydevccu_client,
) -> None:
    """Test CustomDpRfLock."""
    central, mock_client, _ = central_client_factory_with_pydevccu_client
    lock: CustomDpRfLock = cast(CustomDpRfLock, get_prepared_custom_data_point(central, "VCU0000146", 1))
    assert lock.usage == DataPointUsage.CDP_PRIMARY

    assert lock.is_locked is True
    await lock.unlock()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000146:1",
        paramset_key=ParamsetKey.VALUES,
        parameter="STATE",
        value=True,
        wait_for_callback=WAIT_FOR_CALLBACK,
    )
    assert lock.is_locked is False
    await lock.lock()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000146:1",
        paramset_key=ParamsetKey.VALUES,
        parameter="STATE",
        value=False,
        wait_for_callback=WAIT_FOR_CALLBACK,
    )
    assert lock.is_locked is True
    await lock.open()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000146:1",
        paramset_key=ParamsetKey.VALUES,
        parameter="OPEN",
        value=True,
        wait_for_callback=WAIT_FOR_CALLBACK,
    )

    assert lock.is_locking is None
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU0000146:1", parameter="DIRECTION", value=2
    )
    assert lock.is_locking is True
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU0000146:1", parameter="DIRECTION", value=0
    )
    assert lock.is_locking is False

    assert lock.is_unlocking is False
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU0000146:1", parameter="DIRECTION", value=1
    )
    assert lock.is_unlocking is True
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU0000146:1", parameter="DIRECTION", value=0
    )
    assert lock.is_unlocking is False

    assert lock.is_jammed is False
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU0000146:1", parameter="ERROR", value=2
    )
    assert lock.is_jammed is True

    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU0000146:1", parameter="ERROR", value=0
    )

    await lock.open()
    call_count = len(mock_client.method_calls)
    await lock.open()
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
async def test_ceiplock(
    central_client_factory_with_pydevccu_client,
) -> None:
    """Test CustomDpIpLock."""
    central, mock_client, _ = central_client_factory_with_pydevccu_client
    lock: CustomDpIpLock = cast(CustomDpIpLock, get_prepared_custom_data_point(central, "VCU9724704", 1))
    assert lock.usage == DataPointUsage.CDP_PRIMARY
    assert lock.service_method_names == ("lock", "open", "unlock")

    assert lock.is_locked is False
    await lock.lock()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU9724704:1",
        paramset_key=ParamsetKey.VALUES,
        parameter="LOCK_TARGET_LEVEL",
        value=0,
        wait_for_callback=WAIT_FOR_CALLBACK,
    )
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU9724704:1", parameter="LOCK_STATE", value=1
    )
    assert lock.is_locked is True
    await lock.unlock()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU9724704:1",
        paramset_key=ParamsetKey.VALUES,
        parameter="LOCK_TARGET_LEVEL",
        value=1,
        wait_for_callback=WAIT_FOR_CALLBACK,
    )
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU9724704:1", parameter="LOCK_STATE", value=2
    )
    assert lock.is_locked is False
    await lock.open()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU9724704:1",
        paramset_key=ParamsetKey.VALUES,
        parameter="LOCK_TARGET_LEVEL",
        value=2,
        wait_for_callback=WAIT_FOR_CALLBACK,
    )

    assert lock.is_locking is None
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU9724704:1", parameter="ACTIVITY_STATE", value=2
    )
    assert lock.is_locking is True
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU9724704:1", parameter="ACTIVITY_STATE", value=0
    )
    assert lock.is_locking is False

    assert lock.is_unlocking is False
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU9724704:1", parameter="ACTIVITY_STATE", value=1
    )
    assert lock.is_unlocking is True
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU9724704:1", parameter="ACTIVITY_STATE", value=0
    )
    assert lock.is_unlocking is False

    assert lock.is_jammed is False

    await lock.open()
    call_count = len(mock_client.method_calls)
    await lock.open()
    assert (call_count + 1) == len(mock_client.method_calls)
