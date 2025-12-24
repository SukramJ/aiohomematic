# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Tests for number data points of aiohomematic."""

from __future__ import annotations

from typing import cast
from unittest.mock import call

import pytest

from aiohomematic.const import DataPointUsage, ParamsetKey
from aiohomematic.model.generic import DpFloat, DpInteger
from aiohomematic.model.hub import SysvarDpNumber
from aiohomematic_test_support import const

TEST_DEVICES: set[str] = {"VCU4984404", "VCU0000011", "VCU0000054"}

# pylint: disable=protected-access


class TestGenericNumber:
    """Tests for DpFloat and DpInteger data points."""

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
    async def test_float_special_value_handling(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test DpFloat special value conversion like VENT_OPEN."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        efloat: DpFloat = cast(
            DpFloat,
            central.get_generic_data_point(channel_address="VCU0000054:2", parameter="SETPOINT"),
        )
        assert efloat.usage == DataPointUsage.NO_CREATE
        assert efloat.unit == "°C"
        assert efloat.values is None
        assert efloat.value is None
        await efloat.send_value(value=8.0)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000054:2",
            paramset_key=ParamsetKey.VALUES,
            parameter="SETPOINT",
            value=8.0,
        )
        assert efloat.value == 8.0

        await efloat.send_value(value="VENT_OPEN")
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000054:2",
            paramset_key=ParamsetKey.VALUES,
            parameter="SETPOINT",
            value=100.0,
        )
        assert efloat.value == 100.0

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
    async def test_float_value_handling(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test DpFloat value handling and validation."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        efloat: DpFloat = cast(
            DpFloat,
            central.get_generic_data_point(channel_address="VCU0000011:3", parameter="LEVEL"),
        )
        assert efloat.usage == DataPointUsage.NO_CREATE
        assert efloat.unit == "%"
        assert efloat.values is None
        assert efloat.value is None
        await efloat.send_value(value=0.3)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000011:3",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=0.3,
        )
        assert efloat.value == 0.3
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000011:3", parameter="LEVEL", value=0.5
        )
        assert efloat.value == 0.5
        # do not write. value above max
        await efloat.send_value(value=45.0)
        assert efloat.value == 0.5

        call_count = len(mock_client.method_calls)
        await efloat.send_value(value=45.0)
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
    async def test_integer_value_handling(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test DpInteger value handling and type conversion."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        einteger: DpInteger = cast(
            DpInteger,
            central.get_generic_data_point(channel_address="VCU4984404:1", parameter="SET_POINT_MODE"),
        )
        assert einteger.usage == DataPointUsage.NO_CREATE
        assert einteger.unit is None
        assert einteger.min == 0
        assert einteger.max == 3
        assert einteger.values is None
        assert einteger.value is None
        await einteger.send_value(value=3)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU4984404:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="SET_POINT_MODE",
            value=3,
        )
        assert einteger.value == 3

        await einteger.send_value(value=1.0)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU4984404:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="SET_POINT_MODE",
            value=1,
        )
        assert einteger.value == 1

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU4984404:1", parameter="SET_POINT_MODE", value=2
        )
        assert einteger.value == 2
        await einteger.send_value(value=6)
        assert mock_client.method_calls[-1] != call.set_value(
            channel_address="VCU4984404:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="SET_POINT_MODE",
            value=6,
        )
        # do not write. value above max
        assert einteger.value == 2

        call_count = len(mock_client.method_calls)
        await einteger.send_value(value=6)
        assert call_count == len(mock_client.method_calls)


class TestSysvarNumber:
    """Tests for SysvarDpNumber data points."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            ({}, True, None, None),
        ],
    )
    async def test_sysvar_number_functionality(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test SysvarDpNumber value handling and validation."""
        central, mock_client, _ = central_client_factory_with_ccu_client
        enumber: SysvarDpNumber = cast(
            SysvarDpNumber,
            central.hub_coordinator.get_sysvar_data_point(legacy_name="float_ext"),
        )
        assert enumber.usage == DataPointUsage.DATA_POINT
        assert enumber.unit == "°C"
        assert enumber.min == 5.0
        assert enumber.max == 30.0
        assert enumber.values is None
        assert enumber.value == 23.2

        await enumber.send_variable(value=23.0)
        assert mock_client.method_calls[-1] == call.set_system_variable(legacy_name="float_ext", value=23.0)
        assert enumber.value == 23.0

        await enumber.send_variable(value=35.0)
        # value over max won't change value
        assert enumber.value == 23.0

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            ({}, True, None, None),
        ],
    )
    async def test_sysvar_number_without_min_max(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test SysvarDpNumber when min/max are not set."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        enumber: SysvarDpNumber = cast(
            SysvarDpNumber,
            central.hub_coordinator.get_sysvar_data_point(legacy_name="integer_ext"),
        )
        assert enumber.usage == DataPointUsage.DATA_POINT

        # For numbers without explicit min/max, any value should work
        if enumber:
            await enumber.send_variable(value=42.0)
            assert any(
                c == call.set_system_variable(legacy_name="integer_ext", value=42.0) for c in mock_client.method_calls
            )
