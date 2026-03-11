# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for model/generic action string data points of aiohomematic."""

from typing import cast
from unittest.mock import call

import pytest

from aiohomematic.client import CommandPriority
from aiohomematic.const import DataPointCategory, DataPointUsage, ParamsetKey
from aiohomematic.model.generic import DpActionString

# VCU3756007 = HmIP-WRCD (text display, ch3 has DISPLAY_DATA_STRING: TYPE=STRING, OPERATIONS=WRITE)
TEST_DEVICES: set[str] = {"VCU3756007"}

# pylint: disable=protected-access


class TestDpActionString:
    """Tests for DpActionString data points."""

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
    async def test_action_string_basic_functionality(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test DpActionString basic functionality."""
        central, mock_client, _ = central_client_factory_with_ccu_client
        action_str: DpActionString = cast(
            DpActionString,
            central.query_facade.get_generic_data_point(
                channel_address="VCU3756007:3", parameter="DISPLAY_DATA_STRING"
            ),
        )
        assert action_str.category == DataPointCategory.ACTION
        assert action_str.usage == DataPointUsage.NO_CREATE
        assert action_str.is_readable is False
        assert action_str.hmtype == "STRING"

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
    async def test_action_string_no_state_change_validation(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test DpActionString sends repeated values (no state change dedup)."""
        central, mock_client, _ = central_client_factory_with_ccu_client
        action_str: DpActionString = cast(
            DpActionString,
            central.query_facade.get_generic_data_point(
                channel_address="VCU3756007:3", parameter="DISPLAY_DATA_STRING"
            ),
        )
        await action_str.send_value(value="Hello")
        call_count = len(mock_client.method_calls)
        # Same value should still be sent (no dedup for actions)
        await action_str.send_value(value="Hello")
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
    async def test_action_string_send_value(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test DpActionString value sending."""
        central, mock_client, _ = central_client_factory_with_ccu_client
        action_str: DpActionString = cast(
            DpActionString,
            central.query_facade.get_generic_data_point(
                channel_address="VCU3756007:3", parameter="DISPLAY_DATA_STRING"
            ),
        )
        await action_str.send_value(value="L2=50,L=100")
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU3756007:3",
            paramset_key=ParamsetKey.VALUES,
            parameter="DISPLAY_DATA_STRING",
            value="L2=50,L=100",
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
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_action_string_value_is_none_before_send(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test DpActionString value is None before first send (write-only)."""
        central, _, _ = central_client_factory_with_ccu_client
        action_str: DpActionString = cast(
            DpActionString,
            central.query_facade.get_generic_data_point(
                channel_address="VCU3756007:3", parameter="DISPLAY_DATA_STRING"
            ),
        )
        assert action_str.value is None
