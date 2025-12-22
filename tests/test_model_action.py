"""Tests for model/generic action data points of aiohomematic."""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock, call

import pytest

from aiohomematic.const import DataPointCategory, DataPointUsage, ParamsetKey
from aiohomematic.model.generic import DpActionSelect

TEST_DEVICES: set[str] = {"VCU9724704"}

# pylint: disable=protected-access


class TestActionSelectDataPoint:
    """Tests for DpActionSelect data points."""

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
    async def test_action_select_basic_functionality(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test DpActionSelect basic functionality and value sending."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        action_select: DpActionSelect = cast(
            DpActionSelect,
            central.get_generic_data_point(channel_address="VCU9724704:1", parameter="LOCK_TARGET_LEVEL"),
        )
        assert action_select.category == DataPointCategory.ACTION_SELECT
        assert action_select.usage == DataPointUsage.NO_CREATE
        assert action_select.is_readable is False
        assert action_select.values == ("LOCKED", "UNLOCKED", "OPEN")
        assert action_select.hmtype == "ENUM"
        # Before setting value, default is returned
        assert action_select.value == action_select._default
        await action_select.send_value(value="OPEN")
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU9724704:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LOCK_TARGET_LEVEL",
            value="OPEN",
        )
        await action_select.send_value(value=1)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU9724704:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LOCK_TARGET_LEVEL",
            value=1,
        )

        call_count = len(mock_client.method_calls)
        await action_select.send_value(value=1)
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
    async def test_action_select_value_setter(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test DpActionSelect value setter for local state."""
        central, _, _ = central_client_factory_with_homegear_client
        action_select: DpActionSelect = cast(
            DpActionSelect,
            central.get_generic_data_point(channel_address="VCU9724704:1", parameter="LOCK_TARGET_LEVEL"),
        )
        # Set value locally
        action_select.value = "UNLOCKED"
        assert action_select.value == "UNLOCKED"

        # Set by index
        action_select.value = 2
        # When using index, value returns the string representation
        assert action_select.value == "OPEN"

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
    async def test_action_select_value_setter_emits_event(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test DpActionSelect value setter emits update event."""
        central, _, _ = central_client_factory_with_homegear_client
        action_select: DpActionSelect = cast(
            DpActionSelect,
            central.get_generic_data_point(channel_address="VCU9724704:1", parameter="LOCK_TARGET_LEVEL"),
        )

        # Track event emissions
        event_handler = MagicMock()
        unregister = action_select.subscribe_to_data_point_updated(handler=event_handler, custom_id="test_event")

        # Set value - should emit event
        action_select.value = "UNLOCKED"
        await central.looper.block_till_done()
        assert event_handler.call_count == 1

        # Set another value - should emit another event
        action_select.value = "OPEN"
        await central.looper.block_till_done()
        assert event_handler.call_count == 2

        # Set by index - should also emit event
        action_select.value = 0
        await central.looper.block_till_done()
        assert event_handler.call_count == 3

        # Cleanup
        unregister()
