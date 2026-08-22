# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for cover data points of aiohomematic."""

import asyncio
from datetime import datetime
from typing import cast
from unittest.mock import DEFAULT, call

import pytest

from aiohomematic.client import CommandPriority
from aiohomematic.const import (
    WAIT_FOR_CALLBACK,
    DataPointCategory,
    DataPointUsage,
    GarageDoorActivity,
    GarageDoorCommand,
    GarageDoorState,
    ParamsetKey,
)
from aiohomematic.model.combined import CombinedDpGarageDoorMode
from aiohomematic.model.custom import CustomDpBlind, CustomDpCover, CustomDpGarage, CustomDpIpBlind, CustomDpWindowDrive
from aiohomematic.model.custom.capabilities.cover import BLIND_CAPABILITIES, COVER_CAPABILITIES, GARAGE_CAPABILITIES
from aiohomematic.model.custom.cover import _CLOSED_LEVEL, _OPEN_LEVEL, _OPEN_TILT_LEVEL, _WD_CLOSED_LEVEL
from aiohomematic_test_support import const
from aiohomematic_test_support.helper import get_prepared_custom_data_point

TEST_DEVICES: set[str] = {
    "VCU0000045",
    "VCU0000144",
    "VCU0000350",
    "VCU1223813",
    "VCU3560967",
    "VCU3574044",
    "VCU6166407",
    "VCU7807849",
    "VCU8537918",
}

# pylint: disable=protected-access


class TestCustomDpCover:
    """Tests for CustomDpCover data points."""

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
    async def test_cecover(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test CustomDpCover."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        cover: CustomDpCover = cast(CustomDpCover, get_prepared_custom_data_point(central, "VCU8537918", 4))
        assert cover.usage == DataPointUsage.CDP_PRIMARY
        assert cover.capabilities is COVER_CAPABILITIES
        assert cover.capabilities.position is True
        assert cover.capabilities.tilt is False
        assert cover.capabilities.stop is True
        assert cover.capabilities.vent is False
        assert cover.current_position == 0
        assert cover.is_closed is True
        await cover.set_position(position=81)
        assert cover.service_method_names == (
            "close",
            "load_data_point_value",
            "open",
            "set_position",
            "stop",
        )
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU8537918:4",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=0.81,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert cover.current_position == 81
        assert cover.is_closed is False
        await cover.open()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU8537918:4",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=_OPEN_LEVEL,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert cover.current_position == 100
        await cover.close()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU8537918:4",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=_CLOSED_LEVEL,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert cover.current_position == 0

        assert cover.is_opening is None
        assert cover.is_closing is None
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU8537918:3", parameter="ACTIVITY_STATE", value=1
        )
        assert cover.is_opening is True
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU8537918:3", parameter="ACTIVITY_STATE", value=2
        )
        assert cover.is_closing is True
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU8537918:3", parameter="ACTIVITY_STATE", value=0
        )

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU8537918:3", parameter="LEVEL", value=0.5
        )
        # Verify position through public API
        assert cover.current_position == 50

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU8537918:3", parameter="LEVEL", value=_CLOSED_LEVEL
        )
        call_count = len(mock_client.method_calls)
        await cover.close()
        assert call_count == len(mock_client.method_calls)

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU8537918:3", parameter="LEVEL", value=_OPEN_LEVEL
        )
        call_count = len(mock_client.method_calls)
        await cover.open()
        assert call_count == len(mock_client.method_calls)

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU8537918:3", parameter="LEVEL", value=0.4
        )
        call_count = len(mock_client.method_calls)
        await cover.set_position(position=40)
        assert call_count == len(mock_client.method_calls)

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
    async def test_cover_validity_gated_by_level_only(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """DIRECTION/GROUP_LEVEL must not block cover is_valid after a CCU restart."""
        central, _mock_client, _ = central_client_factory_with_homegear_client
        cover = cast(CustomDpCover, get_prepared_custom_data_point(central, "VCU8537918", 4))
        # Preconditions: DIRECTION is a real, readable data point on this device.
        assert cover._dp_direction.is_readable
        # Secondary fields must not gate validity.
        assert cover._dp_direction not in cover._relevant_data_points
        assert cover._dp_group_level not in cover._relevant_data_points
        # Nothing refreshed yet -> invalid.
        assert cover.is_valid is False
        # Simulate a post-CCU-restart init where only LEVEL arrives (bulk fetch).
        cover._dp_level._set_refreshed_at(refreshed_at=datetime.now())
        # The cover must be valid even though DIRECTION/GROUP_LEVEL never refreshed.
        assert cover.is_valid is True


class TestCustomDpWindowDrive:
    """Tests for CustomDpWindowDrive data points."""

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
    async def test_cewindowdrive(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test CustomDpWindowDrive."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        cover: CustomDpWindowDrive = cast(CustomDpWindowDrive, get_prepared_custom_data_point(central, "VCU0000350", 1))
        assert cover.usage == DataPointUsage.CDP_PRIMARY
        assert cover.capabilities is COVER_CAPABILITIES
        assert cover.current_position == 0
        assert cover._group_level == _WD_CLOSED_LEVEL
        assert cover.is_closed is True
        await cover.set_position(position=81)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000350:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=0.81,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert cover.current_position == 81
        assert cover.is_closed is False

        await cover.open()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000350:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=_OPEN_LEVEL,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert cover.current_position == 100
        await cover.close()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000350:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=_WD_CLOSED_LEVEL,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert cover.current_position == 0
        assert cover._group_level == _WD_CLOSED_LEVEL
        assert cover.is_closed is True

        await cover.set_position(position=1)
        assert cover.current_position == 1
        assert cover._group_level == _CLOSED_LEVEL
        assert cover.is_closed is False

        await cover.set_position(position=_WD_CLOSED_LEVEL)
        assert cover.current_position == 0
        assert cover._group_level == _WD_CLOSED_LEVEL
        assert cover.is_closed is True


class TestCustomDpBlind:
    """Tests for CustomDpBlind data points."""

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
    async def test_blind_validity_not_gated_by_level_2(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """LEVEL_2 (optional slats level) must not block blind is_valid (ADR-0025)."""
        central, _mock_client, _ = central_client_factory_with_homegear_client
        cover = cast(CustomDpBlind, get_prepared_custom_data_point(central, "VCU0000144", 1))
        assert cover._dp_level_2.is_readable
        assert cover._dp_level_2 not in cover._relevant_data_points
        assert cover.is_valid is False
        cover._dp_level._set_refreshed_at(refreshed_at=datetime.now())
        assert cover.is_valid is True

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
    async def test_ceblind(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test CustomDpBlind."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        cover: CustomDpBlind = cast(CustomDpBlind, get_prepared_custom_data_point(central, "VCU0000144", 1))
        assert cover.usage == DataPointUsage.CDP_PRIMARY
        assert cover.capabilities is BLIND_CAPABILITIES
        assert cover.capabilities.position is True
        assert cover.capabilities.tilt is True
        assert cover.capabilities.stop is True
        assert cover.capabilities.vent is False
        assert cover.service_method_names == (
            "close",
            "close_tilt",
            "load_data_point_value",
            "open",
            "open_tilt",
            "set_position",
            "stop",
            "stop_tilt",
        )
        assert cover.current_position == 0
        assert cover.current_tilt_position == 0

        await cover.set_position(position=81)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000144:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL_COMBINED",
            value="0xa2,0x00",
            priority=CommandPriority.HIGH,
            retry=True,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000144:1", parameter="LEVEL", value=0.81
        )
        assert cover.current_position == 81
        assert cover.current_tilt_position == 0

        await cover.open()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000144:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL_COMBINED",
            value="0xc8,0xc8",
            priority=CommandPriority.HIGH,
            retry=True,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000144:1", parameter="LEVEL", value=_OPEN_LEVEL
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU0000144:1",
            parameter="LEVEL_SLATS",
            value=_OPEN_TILT_LEVEL,
        )
        assert cover.current_position == 100
        assert cover.current_tilt_position == 100

        await cover.close()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000144:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL_COMBINED",
            value="0x00,0x00",
            priority=CommandPriority.HIGH,
            retry=True,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000144:1", parameter="LEVEL", value=_CLOSED_LEVEL
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU0000144:1",
            parameter="LEVEL_SLATS",
            value=_CLOSED_LEVEL,
        )
        assert cover.current_position == 0
        assert cover.current_tilt_position == 0

        await cover.open_tilt()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000144:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL_COMBINED",
            value="0x00,0xc8",
            priority=CommandPriority.HIGH,
            retry=True,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU0000144:1",
            parameter="LEVEL_SLATS",
            value=_OPEN_TILT_LEVEL,
        )
        assert cover.current_position == 0
        assert cover.current_tilt_position == 100

        await cover.set_position(tilt_position=45)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000144:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL_COMBINED",
            value="0x00,0x5a",
            priority=CommandPriority.HIGH,
            retry=True,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000144:1", parameter="LEVEL_SLATS", value=0.45
        )
        assert cover.current_position == 0
        assert cover.current_tilt_position == 45

        await cover.close_tilt()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000144:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL_COMBINED",
            value="0x00,0x00",
            priority=CommandPriority.HIGH,
            retry=True,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU0000144:1",
            parameter="LEVEL_SLATS",
            value=_CLOSED_LEVEL,
        )
        assert cover.current_position == 0
        assert cover.current_tilt_position == 0

        await cover.set_position(position=10, tilt_position=20)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000144:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL_COMBINED",
            value="0x14,0x28",
            priority=CommandPriority.HIGH,
            retry=True,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000144:1", parameter="LEVEL", value=0.1
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000144:1", parameter="LEVEL_SLATS", value=0.2
        )
        assert cover.current_position == 10
        assert cover.current_tilt_position == 20

        await cover.stop()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000144:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STOP",
            value=True,
            priority=CommandPriority.CRITICAL,
            purge_addresses=frozenset({"VCU0000144:1"}),
            retry=False,
        )
        await cover.stop_tilt()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000144:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STOP",
            value=True,
            priority=CommandPriority.CRITICAL,
            purge_addresses=frozenset({"VCU0000144:1"}),
            retry=False,
        )

        await cover.open_tilt()
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU0000144:1",
            parameter="LEVEL_SLATS",
            value=_OPEN_TILT_LEVEL,
        )
        call_count = len(mock_client.method_calls)
        await cover.open_tilt()
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU0000144:1",
            parameter="LEVEL_SLATS",
            value=_OPEN_TILT_LEVEL,
        )
        assert call_count == len(mock_client.method_calls)

        await cover.close_tilt()
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU0000144:1",
            parameter="LEVEL_SLATS",
            value=_CLOSED_LEVEL,
        )
        call_count = len(mock_client.method_calls)
        await cover.close_tilt()
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU0000144:1",
            parameter="LEVEL_SLATS",
            value=_CLOSED_LEVEL,
        )
        assert call_count == len(mock_client.method_calls)

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000144:1", parameter="LEVEL_SLATS", value=0.4
        )
        call_count = len(mock_client.method_calls)
        await cover.set_position(tilt_position=40)
        assert call_count == len(mock_client.method_calls)

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
    async def test_ceblind_separate_level_and_tilt_change(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test if CustomDpBlind sends correct commands even when rapidly changing level and tilt via separate service calls."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        cover: CustomDpBlind = cast(
            CustomDpBlind, get_prepared_custom_data_point(central=central, address="VCU0000144", channel_no=1)
        )

        # In order for this test to make sense, communication with CCU must take some amount of time.
        # This is not the case with the default local client used during testing, so we add a slight delay.
        async def delay_communication(*args, **kwargs):
            await asyncio.sleep(0.1)
            return DEFAULT

        mock_client.set_value.side_effect = delay_communication

        # We test for the absence of race conditions.
        # We repeat the test a few times so that it becomes unlikely for the race condition to remain undetected.
        for _ in range(10):
            await central.event_coordinator.data_point_event(
                interface_id=const.INTERFACE_ID, channel_address="VCU0000144:1", parameter="LEVEL", value=0
            )
            await central.event_coordinator.data_point_event(
                interface_id=const.INTERFACE_ID, channel_address="VCU0000144:1", parameter="LEVEL_SLATS", value=0
            )
            assert cover.current_position == 0
            assert cover.current_tilt_position == 0

            await asyncio.gather(
                cover.set_position(position=81),
                cover.set_position(tilt_position=19),
            )

            assert mock_client.method_calls[-1] == call.set_value(
                channel_address="VCU0000144:1",
                paramset_key=ParamsetKey.VALUES,
                parameter="LEVEL_COMBINED",
                value="0xa2,0x26",
                priority=CommandPriority.HIGH,
                retry=True,
            )
            await central.event_coordinator.data_point_event(
                interface_id=const.INTERFACE_ID, channel_address="VCU0000144:1", parameter="LEVEL", value=0.81
            )
            await central.event_coordinator.data_point_event(
                interface_id=const.INTERFACE_ID, channel_address="VCU0000144:1", parameter="LEVEL_SLATS", value=0.19
            )
            assert cover.current_position == 81
            assert cover.current_tilt_position == 19


class TestCustomDpIpBlind:
    """Tests for CustomDpIpBlind data points."""

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
    async def test_ceipblind(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test CustomDpIpBlind."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        cover: CustomDpIpBlind = cast(
            CustomDpIpBlind, get_prepared_custom_data_point(central=central, address="VCU1223813", channel_no=4)
        )
        assert cover.usage == DataPointUsage.CDP_PRIMARY
        assert cover.capabilities is BLIND_CAPABILITIES

        assert cover.current_position == 0
        assert cover.current_tilt_position == 0
        await cover.set_position(position=81)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU1223813:4",
            paramset_key=ParamsetKey.VALUES,
            parameter="COMBINED_PARAMETER",
            value="L2=0,L=81",
            priority=CommandPriority.HIGH,
            retry=True,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1223813:4", parameter="LEVEL", value=0.81
        )
        assert cover.current_position == 81
        assert cover.current_tilt_position == 0

        await cover.open()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU1223813:4",
            paramset_key=ParamsetKey.VALUES,
            parameter="COMBINED_PARAMETER",
            value="L2=100,L=100",
            priority=CommandPriority.HIGH,
            retry=True,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1223813:4", parameter="LEVEL_2", value=_OPEN_TILT_LEVEL
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1223813:4", parameter="LEVEL", value=_OPEN_LEVEL
        )
        assert cover.current_position == 100
        assert cover.current_tilt_position == 100

        await cover.close()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU1223813:4",
            paramset_key=ParamsetKey.VALUES,
            parameter="COMBINED_PARAMETER",
            value="L2=0,L=0",
            priority=CommandPriority.HIGH,
            retry=True,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1223813:4", parameter="LEVEL_2", value=_CLOSED_LEVEL
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1223813:4", parameter="LEVEL", value=_CLOSED_LEVEL
        )
        assert cover.current_position == 0
        assert cover.current_tilt_position == 0

        await cover.open_tilt()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU1223813:4",
            paramset_key=ParamsetKey.VALUES,
            parameter="COMBINED_PARAMETER",
            value="L2=100,L=0",
            priority=CommandPriority.HIGH,
            retry=True,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1223813:4", parameter="LEVEL_2", value=1.0
        )
        assert cover.current_position == 0
        assert cover.current_tilt_position == 100

        await cover.set_position(tilt_position=45)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU1223813:4",
            paramset_key=ParamsetKey.VALUES,
            parameter="COMBINED_PARAMETER",
            value="L2=45,L=0",
            priority=CommandPriority.HIGH,
            retry=True,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1223813:4", parameter="LEVEL_2", value=0.45
        )
        assert cover.current_position == 0
        assert cover.current_tilt_position == 45

        await cover.close_tilt()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU1223813:4",
            paramset_key=ParamsetKey.VALUES,
            parameter="COMBINED_PARAMETER",
            value="L2=0,L=0",
            priority=CommandPriority.HIGH,
            retry=True,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1223813:4", parameter="LEVEL_2", value=_CLOSED_LEVEL
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1223813:4", parameter="LEVEL", value=_CLOSED_LEVEL
        )
        assert cover.current_position == 0
        assert cover.current_tilt_position == 0

        await cover.set_position(position=10, tilt_position=20)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU1223813:4",
            paramset_key=ParamsetKey.VALUES,
            parameter="COMBINED_PARAMETER",
            value="L2=20,L=10",
            priority=CommandPriority.HIGH,
            retry=True,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1223813:4", parameter="LEVEL", value=0.1
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1223813:4", parameter="LEVEL_2", value=0.2
        )
        assert cover.current_position == 10
        assert cover.current_tilt_position == 20

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1223813:3", parameter="LEVEL", value=0.5
        )
        # Verify position through public API
        assert cover.current_position == 50

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1223813:3", parameter="LEVEL_2", value=0.8
        )
        # Verify tilt through public API
        assert cover.current_tilt_position == 80

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1223813:3", parameter="LEVEL", value=_CLOSED_LEVEL
        )
        # Verify position through public API
        assert cover.current_position == 0

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1223813:3", parameter="LEVEL_2", value=_CLOSED_LEVEL
        )
        # Verify tilt through public API
        assert cover.current_tilt_position == 0

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1223813:3", parameter="ACTIVITY_STATE", value=1
        )
        assert cover.is_opening

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1223813:3", parameter="ACTIVITY_STATE", value=2
        )
        assert cover.is_closing

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1223813:3", parameter="ACTIVITY_STATE", value=3
        )
        assert cover.is_opening is False
        assert cover.is_closing is False

        await cover.stop()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU1223813:4",
            paramset_key=ParamsetKey.VALUES,
            parameter="STOP",
            value=True,
            priority=CommandPriority.CRITICAL,
            purge_addresses=frozenset({"VCU1223813:3", "VCU1223813:4", "VCU1223813:5", "VCU1223813:6"}),
            retry=False,
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
    async def test_ceipblind_dr(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test CustomDpIpBlind DIN Rail."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        cover: CustomDpIpBlind = cast(CustomDpIpBlind, get_prepared_custom_data_point(central, "VCU7807849", 14))
        assert cover.usage == DataPointUsage.CDP_PRIMARY
        assert cover.service_method_names == (
            "close",
            "close_tilt",
            "load_data_point_value",
            "open",
            "open_tilt",
            "set_position",
            "stop",
            "stop_tilt",
        )

        assert cover.current_position == 0
        assert cover.operation_mode == "SHUTTER"
        assert cover.is_closed is True
        await cover.set_position(position=81)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU7807849:14",
            paramset_key=ParamsetKey.VALUES,
            parameter="COMBINED_PARAMETER",
            value="L2=0,L=81",
            priority=CommandPriority.HIGH,
            retry=True,
        )

        # test unconfirmed values
        assert cover._dp_level.unconfirmed_last_value_send == 0.81
        assert cover._dp_level_2.unconfirmed_last_value_send == _CLOSED_LEVEL
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU7807849:14", parameter="LEVEL", value=0.81
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU7807849:14", parameter="LEVEL_2", value=_CLOSED_LEVEL
        )
        assert cover._dp_level.unconfirmed_last_value_send is None
        assert cover._dp_level_2.unconfirmed_last_value_send is None

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU7807849:13", parameter="LEVEL", value=0.81
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU7807849:13", parameter="LEVEL_2", value=_CLOSED_LEVEL
        )
        assert cover.current_position == 81
        assert cover.is_closed is False
        await cover.open()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU7807849:14",
            paramset_key=ParamsetKey.VALUES,
            parameter="COMBINED_PARAMETER",
            value="L2=100,L=100",
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert cover._dp_level.unconfirmed_last_value_send == _OPEN_LEVEL
        assert cover._dp_level_2.unconfirmed_last_value_send == _OPEN_TILT_LEVEL
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU7807849:13", parameter="LEVEL", value=_OPEN_LEVEL
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU7807849:13",
            parameter="LEVEL_2",
            value=_OPEN_TILT_LEVEL,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU7807849:14", parameter="LEVEL", value=_OPEN_LEVEL
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU7807849:14",
            parameter="LEVEL_2",
            value=_OPEN_TILT_LEVEL,
        )
        assert cover._dp_level.unconfirmed_last_value_send is None
        assert cover._dp_level_2.unconfirmed_last_value_send is None
        assert cover.current_position == 100
        assert cover.current_tilt_position == 100
        await cover.close()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU7807849:14",
            paramset_key=ParamsetKey.VALUES,
            parameter="COMBINED_PARAMETER",
            value="L2=0,L=0",
            priority=CommandPriority.HIGH,
            retry=True,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU7807849:13", parameter="LEVEL", value=_CLOSED_LEVEL
        )
        assert cover.is_opening is None
        assert cover.is_closing is None
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU7807849:13", parameter="ACTIVITY_STATE", value=1
        )
        assert cover.is_opening is True
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU7807849:13", parameter="ACTIVITY_STATE", value=2
        )
        assert cover.is_closing is True

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU7807849:13", parameter="LEVEL", value=0.5
        )
        # Verify position through public API
        assert cover.current_position == 50

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
    async def test_ceipblind_hdm(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test CustomDpIpBlind HDM."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        cover: CustomDpIpBlind = cast(
            CustomDpIpBlind, get_prepared_custom_data_point(central=central, address="VCU3560967", channel_no=1)
        )
        assert cover.usage == DataPointUsage.CDP_PRIMARY
        assert cover.service_method_names == (
            "close",
            "close_tilt",
            "load_data_point_value",
            "open",
            "open_tilt",
            "set_position",
            "stop",
            "stop_tilt",
        )

        assert cover.current_position == 0
        assert cover.current_tilt_position == 0
        await cover.set_position(position=81)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU3560967:1",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"LEVEL_2": _CLOSED_LEVEL, "LEVEL": 0.81},
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3560967:1", parameter="LEVEL", value=0.81
        )
        assert cover.current_position == 81
        assert cover.current_tilt_position == 0

        await cover.open()
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU3560967:1",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"LEVEL_2": _OPEN_TILT_LEVEL, "LEVEL": _OPEN_LEVEL},
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3560967:1", parameter="LEVEL_2", value=_OPEN_TILT_LEVEL
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3560967:1", parameter="LEVEL", value=_OPEN_LEVEL
        )
        assert cover.current_position == 100
        assert cover.current_tilt_position == 100

        await cover.close()
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU3560967:1",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"LEVEL_2": _CLOSED_LEVEL, "LEVEL": _CLOSED_LEVEL},
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3560967:1", parameter="LEVEL_2", value=_CLOSED_LEVEL
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3560967:1", parameter="LEVEL", value=_CLOSED_LEVEL
        )
        assert cover.current_position == 0
        assert cover.current_tilt_position == 0

        await cover.open_tilt()
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU3560967:1",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"LEVEL_2": _OPEN_TILT_LEVEL, "LEVEL": _CLOSED_LEVEL},
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3560967:1", parameter="LEVEL_2", value=1.0
        )
        assert cover.current_position == 0
        assert cover.current_tilt_position == 100

        await cover.set_position(tilt_position=45)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU3560967:1",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"LEVEL_2": 0.45, "LEVEL": _CLOSED_LEVEL},
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3560967:1", parameter="LEVEL_2", value=0.45
        )
        assert cover.current_position == 0
        assert cover.current_tilt_position == 45

        await cover.close_tilt()
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU3560967:1",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"LEVEL_2": _CLOSED_LEVEL, "LEVEL": _CLOSED_LEVEL},
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3560967:1", parameter="LEVEL_2", value=_CLOSED_LEVEL
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3560967:1", parameter="LEVEL", value=_CLOSED_LEVEL
        )
        assert cover.current_position == 0
        assert cover.current_tilt_position == 0

        await cover.set_position(position=10, tilt_position=20)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU3560967:1",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"LEVEL_2": 0.2, "LEVEL": 0.1},
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3560967:1", parameter="LEVEL", value=0.1
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3560967:1", parameter="LEVEL_2", value=0.2
        )
        assert cover.current_position == 10
        assert cover.current_tilt_position == 20

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3560967:1", parameter="ACTIVITY_STATE", value=1
        )
        assert cover.is_opening

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3560967:1", parameter="ACTIVITY_STATE", value=2
        )
        assert cover.is_closing

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3560967:1", parameter="ACTIVITY_STATE", value=3
        )
        assert cover.is_opening is False
        assert cover.is_closing is False

        await cover.stop()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU3560967:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STOP",
            value=True,
            priority=CommandPriority.CRITICAL,
            purge_addresses=frozenset({"VCU3560967:1"}),
            retry=False,
        )


class TestCustomDpGarage:
    """Tests for CustomDpGarage data points."""

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
    async def test_cegarage_door_mode_select(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test the garage door mode is exposed as a SELECT and stays in sync with cover commands."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        cover: CustomDpGarage = cast(
            CustomDpGarage, get_prepared_custom_data_point(central=central, address="VCU3574044", channel_no=1)
        )

        # The select is registered on the channel, not just reachable via the descriptor.
        selects = [dp for dp in cover.channel.get_data_points() if dp.category == DataPointCategory.SELECT]
        assert len(selects) == 1
        mode = selects[0]
        assert isinstance(mode, CombinedDpGarageDoorMode)
        assert mode is cover._dp_door_mode
        # DOOR_MODE is the combined data point's own parameter — it must not borrow
        # the identity of DOOR_STATE, whose name ("Door State") reads as a read-only
        # state rather than the writable mode control this entity is.
        assert mode.unique_id == "combined_vcu3574044_1_door_mode"
        assert mode.parameter == "DOOR_MODE"
        assert mode.dpk.parameter == "DOOR_MODE"
        assert mode.translation_key == "door_mode"
        assert mode.name == "Door Mode"
        assert mode.usage == DataPointUsage.CDP_VISIBLE
        assert mode.values == ("CLOSED", "OPEN", "VENTILATION_POSITION")
        assert mode.value is None

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3574044:1", parameter="DOOR_STATE", value=0
        )
        assert mode.value == GarageDoorState.CLOSED

        # Selecting the ventilation mode issues PARTIAL_OPEN.
        await mode.send_value(value=GarageDoorState.VENTILATION_POSITION)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU3574044:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="DOOR_COMMAND",
            value=GarageDoorCommand.PARTIAL_OPEN,
            priority=CommandPriority.HIGH,
            retry=True,
        )

        # While travelling the door reports POSITION_UNKNOWN; the commanded mode is held.
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3574044:1", parameter="DOOR_STATE", value=3
        )
        assert mode.value == GarageDoorState.VENTILATION_POSITION
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3574044:1", parameter="DOOR_STATE", value=2
        )
        assert mode.value == GarageDoorState.VENTILATION_POSITION

        # A command issued through the cover entity must update the held mode too,
        # otherwise the select keeps reporting the previously selected mode.
        await cover.open()
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3574044:1", parameter="DOOR_STATE", value=3
        )
        assert mode.value == GarageDoorState.OPEN

        # STOP has no resulting mode and DOOR_STATE stays at POSITION_UNKNOWN,
        # so the select must not keep claiming the door is open.
        await cover.stop()
        assert mode.value is None
        assert cover.current_position is None

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
    async def test_cegarageho(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test CustomDpGarageHO."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        cover: CustomDpGarage = cast(
            CustomDpGarage, get_prepared_custom_data_point(central=central, address="VCU3574044", channel_no=1)
        )
        assert cover.usage == DataPointUsage.CDP_PRIMARY
        assert cover.capabilities is GARAGE_CAPABILITIES
        assert cover.capabilities.position is True
        assert cover.capabilities.tilt is False
        assert cover.capabilities.stop is True
        assert cover.capabilities.vent is True
        assert cover.service_method_names == (
            "close",
            "load_data_point_value",
            "open",
            "set_position",
            "stop",
            "vent",
        )

        assert cover.current_position is None
        await cover.set_position(position=81)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU3574044:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="DOOR_COMMAND",
            value=GarageDoorCommand.OPEN,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3574044:1", parameter="DOOR_STATE", value=1
        )
        assert cover.current_position == 100
        await cover.close()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU3574044:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="DOOR_COMMAND",
            value=GarageDoorCommand.CLOSE,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3574044:1", parameter="DOOR_STATE", value=0
        )
        assert cover.current_position == 0
        assert cover.is_closed is True
        await cover.set_position(position=11)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU3574044:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="DOOR_COMMAND",
            value=GarageDoorCommand.PARTIAL_OPEN,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3574044:1", parameter="DOOR_STATE", value=2
        )
        assert cover.current_position == 10

        await cover.set_position(position=5)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU3574044:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="DOOR_COMMAND",
            value=GarageDoorCommand.CLOSE,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3574044:1", parameter="DOOR_STATE", value=0
        )
        assert cover.current_position == 0

        await cover.open()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU3574044:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="DOOR_COMMAND",
            value=GarageDoorCommand.OPEN,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        await cover.stop()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU3574044:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="DOOR_COMMAND",
            value=GarageDoorCommand.STOP,
            priority=CommandPriority.CRITICAL,
            purge_addresses=frozenset({"VCU3574044:1"}),
            retry=True,
        )

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3574044:1", parameter="DOOR_STATE", value=1
        )
        assert cover.current_position == 100

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU3574044:1",
            parameter="SECTION",
            value=GarageDoorActivity.OPENING.value,
        )
        assert cover.is_opening is True
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU3574044:1",
            parameter="SECTION",
            value=GarageDoorActivity.CLOSING.value,
        )
        assert cover.is_closing is True

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3574044:1", parameter="SECTION", value=None
        )
        assert cover.is_opening is None
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3574044:1", parameter="SECTION", value=None
        )
        assert cover.is_closing is None
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3574044:1", parameter="DOOR_STATE", value=None
        )
        assert cover.is_closed is None

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3574044:1", parameter="DOOR_STATE", value=0
        )
        call_count = len(mock_client.method_calls)
        await cover.close()
        assert call_count == len(mock_client.method_calls)

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3574044:1", parameter="DOOR_STATE", value=1
        )
        call_count = len(mock_client.method_calls)
        await cover.open()
        assert call_count == len(mock_client.method_calls)

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3574044:1", parameter="DOOR_STATE", value=2
        )
        call_count = len(mock_client.method_calls)
        await cover.vent()
        assert call_count == len(mock_client.method_calls)

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
    async def test_cegaragetm(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test CustomDpGarageTM."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        cover: CustomDpGarage = cast(
            CustomDpGarage, get_prepared_custom_data_point(central=central, address="VCU6166407", channel_no=1)
        )
        assert cover.usage == DataPointUsage.CDP_PRIMARY

        assert cover.current_position is None
        await cover.set_position(position=81)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU6166407:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="DOOR_COMMAND",
            value=GarageDoorCommand.OPEN,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU6166407:1", parameter="DOOR_STATE", value=1
        )
        assert cover.current_position == 100
        await cover.close()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU6166407:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="DOOR_COMMAND",
            value=GarageDoorCommand.CLOSE,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU6166407:1", parameter="DOOR_STATE", value=0
        )
        assert cover.current_position == 0
        assert cover.is_closed is True
        await cover.set_position(position=11)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU6166407:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="DOOR_COMMAND",
            value=GarageDoorCommand.PARTIAL_OPEN,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU6166407:1", parameter="DOOR_STATE", value=2
        )
        assert cover.current_position == 10

        await cover.set_position(position=5)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU6166407:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="DOOR_COMMAND",
            value=GarageDoorCommand.CLOSE,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU6166407:1", parameter="DOOR_STATE", value=0
        )
        assert cover.current_position == 0

        await cover.open()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU6166407:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="DOOR_COMMAND",
            value=GarageDoorCommand.OPEN,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        await cover.stop()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU6166407:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="DOOR_COMMAND",
            value=GarageDoorCommand.STOP,
            priority=CommandPriority.CRITICAL,
            purge_addresses=frozenset({"VCU6166407:1"}),
            retry=True,
        )

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU6166407:1", parameter="DOOR_STATE", value=1
        )
        assert cover.current_position == 100

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU6166407:1",
            parameter="SECTION",
            value=GarageDoorActivity.OPENING,
        )
        assert cover.is_opening is True
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU6166407:1",
            parameter="SECTION",
            value=GarageDoorActivity.CLOSING,
        )
        assert cover.is_closing is True

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU6166407:1", parameter="SECTION", value=None
        )
        assert cover.is_opening is None
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU6166407:1", parameter="SECTION", value=None
        )
        assert cover.is_closing is None
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU6166407:1", parameter="DOOR_STATE", value=None
        )
        assert cover.is_closed is None
