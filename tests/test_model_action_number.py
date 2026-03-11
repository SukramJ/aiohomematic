# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for model/generic action number data points of aiohomematic."""

from typing import cast
from unittest.mock import call

import pytest

from aiohomematic.client import CommandPriority
from aiohomematic.const import DataPointCategory, DataPointUsage, ParamsetKey
from aiohomematic.model.generic import DpActionFloat, DpActionInteger

# VCU0000121 = HM-LC-Dim1L-Pl (dimmer with write-only FLOAT params ON_TIME, RAMP_TIME)
# VCU0000198 = HM-RC-19-B (remote with write-only INTEGER param ALARM_COUNT on ch 18)
TEST_DEVICES: set[str] = {"VCU0000121", "VCU0000198"}

# pylint: disable=protected-access


class TestDpActionFloat:
    """Tests for DpActionFloat data points."""

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
    async def test_action_float_basic_functionality(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test DpActionFloat basic functionality."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        action_float: DpActionFloat = cast(
            DpActionFloat,
            central.query_facade.get_generic_data_point(channel_address="VCU0000121:1", parameter="RAMP_TIME"),
        )
        assert action_float.category == DataPointCategory.ACTION_NUMBER
        assert action_float.usage == DataPointUsage.NO_CREATE
        assert action_float.is_readable is False
        assert action_float.hmtype == "FLOAT"

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
    async def test_action_float_no_state_change_validation(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test DpActionFloat sends repeated values (no state change dedup)."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        action_float: DpActionFloat = cast(
            DpActionFloat,
            central.query_facade.get_generic_data_point(channel_address="VCU0000121:1", parameter="RAMP_TIME"),
        )
        await action_float.send_value(value=1.5)
        call_count = len(mock_client.method_calls)
        # Same value should still be sent (no dedup for actions)
        await action_float.send_value(value=1.5)
        assert len(mock_client.method_calls) == call_count + 1

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
    async def test_action_float_send_value(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test DpActionFloat value sending."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        action_float: DpActionFloat = cast(
            DpActionFloat,
            central.query_facade.get_generic_data_point(channel_address="VCU0000121:1", parameter="RAMP_TIME"),
        )
        await action_float.send_value(value=1.5)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000121:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="RAMP_TIME",
            value=1.5,
            priority=CommandPriority.HIGH,
        )


class TestDpActionInteger:
    """Tests for DpActionInteger data points."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, ["ALARM_COUNT"]),
        ],
    )
    async def test_action_integer_basic_functionality(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test DpActionInteger basic functionality."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        action_int: DpActionInteger = cast(
            DpActionInteger,
            central.query_facade.get_generic_data_point(channel_address="VCU0000198:18", parameter="ALARM_COUNT"),
        )
        assert action_int.category == DataPointCategory.ACTION_NUMBER
        assert action_int.is_readable is False
        assert action_int.hmtype == "INTEGER"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, ["ALARM_COUNT"]),
        ],
    )
    async def test_action_integer_no_state_change_validation(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test DpActionInteger sends repeated values (no state change dedup)."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        action_int: DpActionInteger = cast(
            DpActionInteger,
            central.query_facade.get_generic_data_point(channel_address="VCU0000198:18", parameter="ALARM_COUNT"),
        )
        await action_int.send_value(value=1)
        call_count = len(mock_client.method_calls)
        # Same value should still be sent (no dedup for actions)
        await action_int.send_value(value=1)
        assert len(mock_client.method_calls) == call_count + 1

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, ["ALARM_COUNT"]),
        ],
    )
    async def test_action_integer_send_value(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test DpActionInteger value sending."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        action_int: DpActionInteger = cast(
            DpActionInteger,
            central.query_facade.get_generic_data_point(channel_address="VCU0000198:18", parameter="ALARM_COUNT"),
        )
        await action_int.send_value(value=128)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000198:18",
            paramset_key=ParamsetKey.VALUES,
            parameter="ALARM_COUNT",
            value=128,
            priority=CommandPriority.HIGH,
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
            (TEST_DEVICES, True, None, ["ALARM_COUNT"]),
        ],
    )
    async def test_action_integer_validates_min_max(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test DpActionInteger rejects values outside MIN/MAX."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        action_int: DpActionInteger = cast(
            DpActionInteger,
            central.query_facade.get_generic_data_point(channel_address="VCU0000198:18", parameter="ALARM_COUNT"),
        )
        call_count = len(mock_client.method_calls)
        # Value outside range (max=255) should be rejected (no RPC call made)
        await action_int.send_value(value=999)
        assert len(mock_client.method_calls) == call_count
