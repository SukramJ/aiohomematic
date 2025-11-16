"""Tests for select data points of aiohomematic."""

from __future__ import annotations

from typing import cast
from unittest.mock import call

import pytest

from aiohomematic.const import DataPointUsage, ParamsetKey
from aiohomematic.model.generic import DpSelect
from aiohomematic.model.hub import SysvarDpSelect
from aiohomematic_test_support import const

TEST_DEVICES: set[str] = {"VCU6354483"}

# pylint: disable=protected-access


class TestGenericSelect:
    """Tests for generic select data points."""

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
    async def test_hmselect_basic_operations(self, central_client_factory_with_homegear_client) -> None:
        """Test basic HmSelect operations."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        select: DpSelect = cast(
            DpSelect,
            central.get_generic_data_point(channel_address="VCU6354483:1", parameter="WINDOW_STATE"),
        )
        assert select.usage == DataPointUsage.NO_CREATE
        assert select.unit is None
        assert select.min == "CLOSED"
        assert select.max == "OPEN"
        assert select.values == ("CLOSED", "OPEN")
        assert select.value == "CLOSED"

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
    async def test_hmselect_invalid_value(self, central_client_factory_with_homegear_client) -> None:
        """Test sending invalid value."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        select: DpSelect = cast(
            DpSelect,
            central.get_generic_data_point(channel_address="VCU6354483:1", parameter="WINDOW_STATE"),
        )

        await select.send_value(value=3)
        # do not write. value above max
        assert select.value == "CLOSED"

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
    async def test_hmselect_no_update_when_same_value(self, central_client_factory_with_homegear_client) -> None:
        """Test that no update is sent when value is same."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        select: DpSelect = cast(
            DpSelect,
            central.get_generic_data_point(channel_address="VCU6354483:1", parameter="WINDOW_STATE"),
        )

        await select.send_value(value=1)
        call_count = len(mock_client.method_calls)
        await select.send_value(value=1)
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
    async def test_hmselect_send_value_by_int(self, central_client_factory_with_homegear_client) -> None:
        """Test sending value by integer index."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        select: DpSelect = cast(
            DpSelect,
            central.get_generic_data_point(channel_address="VCU6354483:1", parameter="WINDOW_STATE"),
        )

        await select.send_value(value=1)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU6354483:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="WINDOW_STATE",
            value=1,
        )
        assert select.value == "OPEN"

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
    async def test_hmselect_send_value_by_string(self, central_client_factory_with_homegear_client) -> None:
        """Test sending value by string."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        select: DpSelect = cast(
            DpSelect,
            central.get_generic_data_point(channel_address="VCU6354483:1", parameter="WINDOW_STATE"),
        )

        await select.send_value(value="OPEN")
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU6354483:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="WINDOW_STATE",
            value=1,
        )
        assert select.value == "OPEN"

        await central.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU6354483:1", parameter="WINDOW_STATE", value=0
        )
        assert select.value == "CLOSED"


class TestSysvarSelect:
    """Tests for sysvar select data points."""

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
    async def test_hmsysvarselect_basic_operations(self, central_client_factory_with_ccu_client) -> None:
        """Test basic HmSysvarSelect operations."""
        central, mock_client, _ = central_client_factory_with_ccu_client
        select: SysvarDpSelect = cast(SysvarDpSelect, central.get_sysvar_data_point(legacy_name="list_ext"))
        assert select.usage == DataPointUsage.DATA_POINT
        assert select.unit is None
        assert select.min is None
        assert select.max is None
        assert select.values == ("v1", "v2", "v3")
        assert select.value == "v1"

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
    async def test_hmsysvarselect_invalid_int_value(self, central_client_factory_with_ccu_client) -> None:
        """Test sending invalid int value (out of range)."""
        central, mock_client, _ = central_client_factory_with_ccu_client
        select: SysvarDpSelect = cast(SysvarDpSelect, central.get_sysvar_data_point(legacy_name="list_ext"))

        # Send invalid int (out of range)
        await select.send_variable(value=10)
        # Should not update
        assert select.value == "v1"

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
    async def test_hmsysvarselect_invalid_string_value(self, central_client_factory_with_ccu_client) -> None:
        """Test sending invalid string value (not in values list)."""
        central, mock_client, _ = central_client_factory_with_ccu_client
        select: SysvarDpSelect = cast(SysvarDpSelect, central.get_sysvar_data_point(legacy_name="list_ext"))

        # Send invalid string (not in values)
        await select.send_variable(value="invalid_value")
        # Should log error but not update
        assert select.value == "v1"

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
    async def test_hmsysvarselect_send_variable_by_int(self, central_client_factory_with_ccu_client) -> None:
        """Test sending variable by integer index."""
        central, mock_client, _ = central_client_factory_with_ccu_client
        select: SysvarDpSelect = cast(SysvarDpSelect, central.get_sysvar_data_point(legacy_name="list_ext"))

        # Send by valid int index
        await select.send_variable(value=1)
        assert mock_client.method_calls[-1] == call.set_system_variable(legacy_name="list_ext", value=1)
        assert select.value == "v2"

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
    async def test_hmsysvarselect_send_variable_by_string(self, central_client_factory_with_ccu_client) -> None:
        """Test sending variable by string value."""
        central, mock_client, _ = central_client_factory_with_ccu_client
        select: SysvarDpSelect = cast(SysvarDpSelect, central.get_sysvar_data_point(legacy_name="list_ext"))

        await select.send_variable(value="v2")
        assert mock_client.method_calls[-1] == call.set_system_variable(legacy_name="list_ext", value=1)
        assert select.value == "v2"
