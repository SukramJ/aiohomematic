# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for model/generic action boolean data points of aiohomematic."""

from typing import cast
from unittest.mock import call

import pytest

from aiohomematic.client import CommandPriority
from aiohomematic.const import DataPointCategory, DataPointUsage, ParamsetKey
from aiohomematic.model.generic import DpActionBoolean

# VCU3756007 = HmIP-WRCD (text display, ch3 has DISPLAY_DATA_COMMIT: TYPE=BOOL, OPERATIONS=WRITE)
TEST_DEVICES: set[str] = {"VCU3756007"}

# pylint: disable=protected-access


class TestDpActionBoolean:
    """Tests for DpActionBoolean data points."""

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
    async def test_action_boolean_basic_functionality(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test DpActionBoolean basic functionality."""
        central, _mock_client, _ = central_client_factory_with_ccu_client
        action_bool: DpActionBoolean = cast(
            DpActionBoolean,
            central.query_facade.get_generic_data_point(
                channel_address="VCU3756007:3", parameter="DISPLAY_DATA_COMMIT"
            ),
        )
        assert action_bool.category == DataPointCategory.ACTION
        assert action_bool.usage == DataPointUsage.NO_CREATE
        assert action_bool.is_readable is False
        assert action_bool.hmtype == "BOOL"

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
    async def test_action_boolean_no_state_change_validation(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test DpActionBoolean sends repeated values (no state change dedup)."""
        central, mock_client, _ = central_client_factory_with_ccu_client
        action_bool: DpActionBoolean = cast(
            DpActionBoolean,
            central.query_facade.get_generic_data_point(
                channel_address="VCU3756007:3", parameter="DISPLAY_DATA_COMMIT"
            ),
        )
        await action_bool.send_value(value=True)
        call_count = len(mock_client.method_calls)
        # Same value should still be sent (no dedup for actions)
        await action_bool.send_value(value=True)
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
    async def test_action_boolean_send_value(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test DpActionBoolean value sending."""
        central, mock_client, _ = central_client_factory_with_ccu_client
        action_bool: DpActionBoolean = cast(
            DpActionBoolean,
            central.query_facade.get_generic_data_point(
                channel_address="VCU3756007:3", parameter="DISPLAY_DATA_COMMIT"
            ),
        )
        await action_bool.send_value(value=True)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU3756007:3",
            paramset_key=ParamsetKey.VALUES,
            parameter="DISPLAY_DATA_COMMIT",
            value=True,
            priority=CommandPriority.HIGH,
            retry=True,
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
    async def test_action_boolean_value_is_none_before_send(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test DpActionBoolean value is None before first send (write-only)."""
        central, _, _ = central_client_factory_with_ccu_client
        action_bool: DpActionBoolean = cast(
            DpActionBoolean,
            central.query_facade.get_generic_data_point(
                channel_address="VCU3756007:3", parameter="DISPLAY_DATA_COMMIT"
            ),
        )
        assert action_bool.value is None
