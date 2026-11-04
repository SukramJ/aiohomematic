# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for lock data points of aiohomematic."""

from typing import cast
from unittest.mock import call

import pytest

from aiohomematic.client import CommandPriority
from aiohomematic.const import WAIT_FOR_CALLBACK, DataPointUsage, ParamsetKey
from aiohomematic.model.custom import CustomDpIpLock, CustomDpRfLock
from aiohomematic.model.custom.lock import _LockTargetLevel
from aiohomematic_test_support import const
from aiohomematic_test_support.helper import get_prepared_custom_data_point

TEST_DEVICES: set[str] = {"VCU9724704", "VCU0000146", "VCU3609622", "VCU0000341"}

# pylint: disable=protected-access


class TestRfLock:
    """Tests for CustomDpRfLock data points."""

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
    async def test_rf_lock_functionality(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test CustomDpRfLock lock/unlock/open operations and state handling."""
        central, mock_client, _ = central_client_factory_with_homegear_client
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
            priority=CommandPriority.CRITICAL,
            purge_addresses=frozenset({"VCU0000146:1"}),
            retry=True,
        )
        assert lock.is_locked is False
        await lock.lock()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000146:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
            value=False,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.CRITICAL,
            purge_addresses=frozenset({"VCU0000146:1"}),
            retry=True,
        )
        assert lock.is_locked is True
        await lock.open()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000146:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="OPEN",
            value=True,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.CRITICAL,
            purge_addresses=frozenset({"VCU0000146:1"}),
            retry=False,
        )

        assert lock.is_locking is None
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000146:1", parameter="DIRECTION", value=2
        )
        assert lock.is_locking is True
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000146:1", parameter="DIRECTION", value=0
        )
        assert lock.is_locking is False

        assert lock.is_unlocking is False
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000146:1", parameter="DIRECTION", value=1
        )
        assert lock.is_unlocking is True
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000146:1", parameter="DIRECTION", value=0
        )
        assert lock.is_unlocking is False

        assert lock.is_jammed is False
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000146:1", parameter="ERROR", value=2
        )
        assert lock.is_jammed is True

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000146:1", parameter="ERROR", value=0
        )

        await lock.open()
        call_count = len(mock_client.method_calls)
        await lock.open()
        assert (call_count + 1) == len(mock_client.method_calls)


class TestIpLock:
    """Tests for CustomDpIpLock data points."""

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
    async def test_ip_lock_functionality(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test CustomDpIpLock lock/unlock/open operations and activity state handling."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        lock: CustomDpIpLock = cast(CustomDpIpLock, get_prepared_custom_data_point(central, "VCU9724704", 1))
        assert lock.usage == DataPointUsage.CDP_PRIMARY
        assert lock.service_method_names == (
            "load_data_point_value",
            "lock",
            "open",
            "unlock",
        )

        assert lock.is_locked is False
        await lock.lock()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU9724704:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LOCK_TARGET_LEVEL",
            value=_LockTargetLevel.LOCKED,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.CRITICAL,
            purge_addresses=frozenset({"VCU9724704:0", "VCU9724704:1"}),
            retry=True,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU9724704:1", parameter="LOCK_STATE", value=1
        )
        assert lock.is_locked is True
        await lock.unlock()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU9724704:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LOCK_TARGET_LEVEL",
            value=_LockTargetLevel.UNLOCKED,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.CRITICAL,
            purge_addresses=frozenset({"VCU9724704:0", "VCU9724704:1"}),
            retry=True,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU9724704:1", parameter="LOCK_STATE", value=2
        )
        assert lock.is_locked is False
        await lock.open()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU9724704:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LOCK_TARGET_LEVEL",
            value=_LockTargetLevel.OPEN,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.CRITICAL,
            purge_addresses=frozenset({"VCU9724704:0", "VCU9724704:1"}),
            retry=True,
        )

        assert lock.is_locking is None
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU9724704:1", parameter="ACTIVITY_STATE", value=2
        )
        assert lock.is_locking is True
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU9724704:1", parameter="ACTIVITY_STATE", value=0
        )
        assert lock.is_locking is False

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU9724704:1", parameter="LOCK_STATE", value=1
        )
        assert lock.is_unlocking is False
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU9724704:1", parameter="ACTIVITY_STATE", value=1
        )
        assert lock.is_unlocking is True
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU9724704:1", parameter="ACTIVITY_STATE", value=0
        )
        assert lock.is_unlocking is False

        assert lock.is_jammed is False

        await lock.open()
        call_count = len(mock_client.method_calls)
        await lock.open()
        assert (call_count + 1) == len(mock_client.method_calls)


# HmIP-DLD channel 1 event sequences recorded in homematicip_local#1343.
# Each step is (LOCK_STATE, ACTIVITY_STATE, expected (is_locking, is_unlocking, is_opening)).
# LOCK_STATE: 1=LOCKED, 2=UNLOCKED. ACTIVITY_STATE: 0=UNKNOWN, 1=UP, 2=DOWN, 3=STABLE.
_DLD_LOCK_SEQUENCE: tuple[tuple[int, int, tuple[bool, bool, bool]], ...] = (
    (2, 2, (True, False, False)),
    (1, 3, (False, False, False)),
)
_DLD_UNLOCK_SEQUENCE: tuple[tuple[int, int, tuple[bool, bool, bool]], ...] = (
    (1, 1, (False, True, False)),
    (2, 3, (False, False, False)),
)
_DLD_OPEN_FROM_UNLOCKED_SEQUENCE: tuple[tuple[int, int, tuple[bool, bool, bool]], ...] = (
    (2, 1, (False, False, True)),
    (2, 1, (False, False, True)),
    (2, 2, (False, False, True)),
    (2, 3, (False, False, False)),
)
_DLD_OPEN_FROM_LOCKED_SEQUENCE: tuple[tuple[int, int, tuple[bool, bool, bool]], ...] = (
    (2, 1, (False, False, True)),
    (2, 2, (False, False, True)),
    (2, 3, (False, False, False)),
)


class TestIpLockMovement:
    """Tests for the movement interpretation of CustomDpIpLock (HmIP-DLD)."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
            "initial_lock_state",
            "sequence",
        ),
        [
            (TEST_DEVICES, True, None, None, 2, _DLD_LOCK_SEQUENCE),
            (TEST_DEVICES, True, None, None, 1, _DLD_UNLOCK_SEQUENCE),
            (TEST_DEVICES, True, None, None, 2, _DLD_OPEN_FROM_UNLOCKED_SEQUENCE),
            (TEST_DEVICES, True, None, None, 1, _DLD_OPEN_FROM_LOCKED_SEQUENCE),
        ],
        ids=["lock", "unlock", "open_from_unlocked", "open_from_locked"],
    )
    async def test_ip_lock_movement_sequences(
        self,
        central_client_factory_with_homegear_client,
        initial_lock_state: int,
        sequence: tuple[tuple[int, int, tuple[bool, bool, bool]], ...],
    ) -> None:
        """Replay recorded DLD event sequences and check locking/unlocking/opening per step."""
        central, _, _ = central_client_factory_with_homegear_client
        lock: CustomDpIpLock = cast(CustomDpIpLock, get_prepared_custom_data_point(central, "VCU9724704", 1))

        async def _send(*, parameter: str, value: int) -> None:
            await central.event_coordinator.data_point_event(
                interface_id=const.INTERFACE_ID, channel_address="VCU9724704:1", parameter=parameter, value=value
            )
            await central.looper.block_till_done()

        await _send(parameter="LOCK_STATE", value=initial_lock_state)
        await _send(parameter="ACTIVITY_STATE", value=3)
        assert lock.is_opening is False

        for lock_state, activity_state, expected in sequence:
            # The backend sends LOCK_STATE before ACTIVITY_STATE within one multicall.
            await _send(parameter="LOCK_STATE", value=lock_state)
            await _send(parameter="ACTIVITY_STATE", value=activity_state)
            assert (lock.is_locking, lock.is_unlocking, lock.is_opening) == expected

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
    async def test_ip_lock_open_movement_reset_by_unknown(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """An UNKNOWN activity ends an open movement, so a following DOWN is a lock movement again."""
        central, _, _ = central_client_factory_with_homegear_client
        lock: CustomDpIpLock = cast(CustomDpIpLock, get_prepared_custom_data_point(central, "VCU9724704", 1))

        async def _send(*, parameter: str, value: int) -> None:
            await central.event_coordinator.data_point_event(
                interface_id=const.INTERFACE_ID, channel_address="VCU9724704:1", parameter=parameter, value=value
            )
            await central.looper.block_till_done()

        await _send(parameter="LOCK_STATE", value=2)
        await _send(parameter="ACTIVITY_STATE", value=1)
        assert lock.is_opening is True
        await _send(parameter="ACTIVITY_STATE", value=0)
        assert lock.is_opening is False
        await _send(parameter="ACTIVITY_STATE", value=2)
        assert lock.is_locking is True
        assert lock.is_opening is False
