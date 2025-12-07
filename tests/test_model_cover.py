"""Tests for cover data points of aiohomematic."""

from __future__ import annotations

import asyncio
from typing import cast
from unittest.mock import DEFAULT, call

import pytest

from aiohomematic.const import WAIT_FOR_CALLBACK, DataPointUsage, ParamsetKey
from aiohomematic.model.custom import CustomDpBlind, CustomDpCover, CustomDpGarage, CustomDpIpBlind, CustomDpWindowDrive
from aiohomematic.model.custom.cover import (
    _CLOSED_LEVEL,
    _OPEN_LEVEL,
    _OPEN_TILT_LEVEL,
    _WD_CLOSED_LEVEL,
    _GarageDoorActivity,
)
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
        assert cover.current_position == 0
        assert cover._group_level == _CLOSED_LEVEL
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
        )
        assert cover.current_position == 100
        await cover.close()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU8537918:4",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=_CLOSED_LEVEL,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert cover.current_position == 0

        assert cover.is_opening is None
        assert cover.is_closing is None
        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU8537918:3", parameter="ACTIVITY_STATE", value=1
        )
        assert cover.is_opening is True
        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU8537918:3", parameter="ACTIVITY_STATE", value=2
        )
        assert cover.is_closing is True
        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU8537918:3", parameter="ACTIVITY_STATE", value=0
        )

        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU8537918:3", parameter="LEVEL", value=0.5
        )
        assert cover._group_level == 0.5
        assert cover.current_position == 50

        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU8537918:3", parameter="LEVEL", value=_CLOSED_LEVEL
        )
        call_count = len(mock_client.method_calls)
        await cover.close()
        assert call_count == len(mock_client.method_calls)

        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU8537918:3", parameter="LEVEL", value=_OPEN_LEVEL
        )
        call_count = len(mock_client.method_calls)
        await cover.open()
        assert call_count == len(mock_client.method_calls)

        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU8537918:3", parameter="LEVEL", value=0.4
        )
        call_count = len(mock_client.method_calls)
        await cover.set_position(position=40)
        assert call_count == len(mock_client.method_calls)


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
        )
        assert cover.current_position == 100
        await cover.close()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000350:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=_WD_CLOSED_LEVEL,
            wait_for_callback=WAIT_FOR_CALLBACK,
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
    async def test_ceblind(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test CustomDpBlind."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        cover: CustomDpBlind = cast(CustomDpBlind, get_prepared_custom_data_point(central, "VCU0000144", 1))
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
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000144:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL_COMBINED",
            value="0xa2,0x00",
        )
        await central.data_point_event(
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
        )
        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000144:1", parameter="LEVEL", value=_OPEN_LEVEL
        )
        await central.data_point_event(
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
        )
        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000144:1", parameter="LEVEL", value=_CLOSED_LEVEL
        )
        await central.data_point_event(
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
        )
        await central.data_point_event(
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
        )
        await central.data_point_event(
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
        )
        await central.data_point_event(
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
        )
        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000144:1", parameter="LEVEL", value=0.1
        )
        await central.data_point_event(
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
        )
        await cover.stop_tilt()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000144:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STOP",
            value=True,
        )

        await cover.open_tilt()
        await central.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU0000144:1",
            parameter="LEVEL_SLATS",
            value=_OPEN_TILT_LEVEL,
        )
        call_count = len(mock_client.method_calls)
        await cover.open_tilt()
        await central.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU0000144:1",
            parameter="LEVEL_SLATS",
            value=_OPEN_TILT_LEVEL,
        )
        assert call_count == len(mock_client.method_calls)

        await cover.close_tilt()
        await central.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU0000144:1",
            parameter="LEVEL_SLATS",
            value=_CLOSED_LEVEL,
        )
        call_count = len(mock_client.method_calls)
        await cover.close_tilt()
        await central.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU0000144:1",
            parameter="LEVEL_SLATS",
            value=_CLOSED_LEVEL,
        )
        assert call_count == len(mock_client.method_calls)

        await central.data_point_event(
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
            await central.data_point_event(
                interface_id=const.INTERFACE_ID, channel_address="VCU0000144:1", parameter="LEVEL", value=0
            )
            await central.data_point_event(
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
            )
            await central.data_point_event(
                interface_id=const.INTERFACE_ID, channel_address="VCU0000144:1", parameter="LEVEL", value=0.81
            )
            await central.data_point_event(
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

        assert cover.current_position == 0
        assert cover.current_tilt_position == 0
        await cover.set_position(position=81)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU1223813:4",
            paramset_key=ParamsetKey.VALUES,
            parameter="COMBINED_PARAMETER",
            value="L2=0,L=81",
        )
        await central.data_point_event(
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
        )
        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1223813:4", parameter="LEVEL_2", value=_OPEN_TILT_LEVEL
        )
        await central.data_point_event(
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
        )
        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1223813:4", parameter="LEVEL_2", value=_CLOSED_LEVEL
        )
        await central.data_point_event(
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
        )
        await central.data_point_event(
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
        )
        await central.data_point_event(
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
        )
        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1223813:4", parameter="LEVEL_2", value=_CLOSED_LEVEL
        )
        await central.data_point_event(
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
        )
        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1223813:4", parameter="LEVEL", value=0.1
        )
        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1223813:4", parameter="LEVEL_2", value=0.2
        )
        assert cover.current_position == 10
        assert cover.current_tilt_position == 20

        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1223813:3", parameter="LEVEL", value=0.5
        )
        assert cover._group_level == 0.5
        assert cover.current_position == 50

        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1223813:3", parameter="LEVEL_2", value=0.8
        )
        assert cover._group_tilt_level == 0.8
        assert cover.current_tilt_position == 80

        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1223813:3", parameter="LEVEL", value=_CLOSED_LEVEL
        )
        assert cover._group_level == _CLOSED_LEVEL
        assert cover.current_position == 0

        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1223813:3", parameter="LEVEL_2", value=_CLOSED_LEVEL
        )
        assert cover._group_tilt_level == _CLOSED_LEVEL
        assert cover.current_tilt_position == 0

        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1223813:3", parameter="ACTIVITY_STATE", value=1
        )
        assert cover.is_opening

        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1223813:3", parameter="ACTIVITY_STATE", value=2
        )
        assert cover.is_closing

        await central.data_point_event(
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
        assert cover._group_level == _CLOSED_LEVEL
        assert cover.operation_mode == "SHUTTER"
        assert cover.is_closed is True
        await cover.set_position(position=81)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU7807849:14",
            paramset_key=ParamsetKey.VALUES,
            parameter="COMBINED_PARAMETER",
            value="L2=0,L=81",
        )

        # test unconfirmed values
        assert cover._dp_level.unconfirmed_last_value_send == 0.81
        assert cover._dp_level_2.unconfirmed_last_value_send == _CLOSED_LEVEL
        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU7807849:14", parameter="LEVEL", value=0.81
        )
        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU7807849:14", parameter="LEVEL_2", value=_CLOSED_LEVEL
        )
        assert cover._dp_level.unconfirmed_last_value_send is None
        assert cover._dp_level_2.unconfirmed_last_value_send is None

        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU7807849:13", parameter="LEVEL", value=0.81
        )
        await central.data_point_event(
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
        )
        assert cover._dp_level.unconfirmed_last_value_send == _OPEN_LEVEL
        assert cover._dp_level_2.unconfirmed_last_value_send == _OPEN_TILT_LEVEL
        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU7807849:13", parameter="LEVEL", value=_OPEN_LEVEL
        )
        await central.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU7807849:13",
            parameter="LEVEL_2",
            value=_OPEN_TILT_LEVEL,
        )
        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU7807849:14", parameter="LEVEL", value=_OPEN_LEVEL
        )
        await central.data_point_event(
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
        )
        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU7807849:13", parameter="LEVEL", value=_CLOSED_LEVEL
        )
        assert cover.is_opening is None
        assert cover.is_closing is None
        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU7807849:13", parameter="ACTIVITY_STATE", value=1
        )
        assert cover.is_opening is True
        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU7807849:13", parameter="ACTIVITY_STATE", value=2
        )
        assert cover.is_closing is True

        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU7807849:13", parameter="LEVEL", value=0.5
        )
        assert cover._group_level == 0.5
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
        )
        await central.data_point_event(
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
        )
        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3560967:1", parameter="LEVEL_2", value=_OPEN_TILT_LEVEL
        )
        await central.data_point_event(
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
        )
        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3560967:1", parameter="LEVEL_2", value=_CLOSED_LEVEL
        )
        await central.data_point_event(
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
        )
        await central.data_point_event(
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
        )
        await central.data_point_event(
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
        )
        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3560967:1", parameter="LEVEL_2", value=_CLOSED_LEVEL
        )
        await central.data_point_event(
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
        )
        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3560967:1", parameter="LEVEL", value=0.1
        )
        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3560967:1", parameter="LEVEL_2", value=0.2
        )
        assert cover.current_position == 10
        assert cover.current_tilt_position == 20

        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3560967:1", parameter="ACTIVITY_STATE", value=1
        )
        assert cover.is_opening

        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3560967:1", parameter="ACTIVITY_STATE", value=2
        )
        assert cover.is_closing

        await central.data_point_event(
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
            value=1,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3574044:1", parameter="DOOR_STATE", value=1
        )
        assert cover.current_position == 100
        await cover.close()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU3574044:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="DOOR_COMMAND",
            value=3,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3574044:1", parameter="DOOR_STATE", value=0
        )
        assert cover.current_position == 0
        assert cover.is_closed is True
        await cover.set_position(position=11)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU3574044:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="DOOR_COMMAND",
            value=4,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3574044:1", parameter="DOOR_STATE", value=2
        )
        assert cover.current_position == 10

        await cover.set_position(position=5)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU3574044:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="DOOR_COMMAND",
            value=3,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3574044:1", parameter="DOOR_STATE", value=0
        )
        assert cover.current_position == 0

        await cover.open()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU3574044:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="DOOR_COMMAND",
            value=1,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        await cover.stop()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU3574044:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="DOOR_COMMAND",
            value=2,
        )

        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3574044:1", parameter="DOOR_STATE", value=1
        )
        assert cover.current_position == 100

        await central.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU3574044:1",
            parameter="SECTION",
            value=_GarageDoorActivity.OPENING.value,
        )
        assert cover.is_opening is True
        await central.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU3574044:1",
            parameter="SECTION",
            value=_GarageDoorActivity.CLOSING.value,
        )
        assert cover.is_closing is True

        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3574044:1", parameter="SECTION", value=None
        )
        assert cover.is_opening is None
        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3574044:1", parameter="SECTION", value=None
        )
        assert cover.is_closing is None
        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3574044:1", parameter="DOOR_STATE", value=None
        )
        assert cover.is_closed is None

        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3574044:1", parameter="DOOR_STATE", value=0
        )
        call_count = len(mock_client.method_calls)
        await cover.close()
        assert call_count == len(mock_client.method_calls)

        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3574044:1", parameter="DOOR_STATE", value=1
        )
        call_count = len(mock_client.method_calls)
        await cover.open()
        assert call_count == len(mock_client.method_calls)

        await central.data_point_event(
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
            value=1,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU6166407:1", parameter="DOOR_STATE", value=1
        )
        assert cover.current_position == 100
        await cover.close()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU6166407:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="DOOR_COMMAND",
            value=3,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU6166407:1", parameter="DOOR_STATE", value=0
        )
        assert cover.current_position == 0
        assert cover.is_closed is True
        await cover.set_position(position=11)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU6166407:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="DOOR_COMMAND",
            value=4,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU6166407:1", parameter="DOOR_STATE", value=2
        )
        assert cover.current_position == 10

        await cover.set_position(position=5)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU6166407:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="DOOR_COMMAND",
            value=3,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU6166407:1", parameter="DOOR_STATE", value=0
        )
        assert cover.current_position == 0

        await cover.open()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU6166407:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="DOOR_COMMAND",
            value=1,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        await cover.stop()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU6166407:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="DOOR_COMMAND",
            value=2,
        )

        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU6166407:1", parameter="DOOR_STATE", value=1
        )
        assert cover.current_position == 100

        await central.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU6166407:1",
            parameter="SECTION",
            value=_GarageDoorActivity.OPENING,
        )
        assert cover.is_opening is True
        await central.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU6166407:1",
            parameter="SECTION",
            value=_GarageDoorActivity.CLOSING,
        )
        assert cover.is_closing is True

        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU6166407:1", parameter="SECTION", value=None
        )
        assert cover.is_opening is None
        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU6166407:1", parameter="SECTION", value=None
        )
        assert cover.is_closing is None
        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU6166407:1", parameter="DOOR_STATE", value=None
        )
        assert cover.is_closed is None
