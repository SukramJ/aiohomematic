"""Tests for model/generic action data points of aiohomematic."""

from __future__ import annotations

from typing import cast
from unittest.mock import call

import pytest

from aiohomematic.const import DataPointUsage, ParamsetKey
from aiohomematic.model.generic import DpAction

TEST_DEVICES: set[str] = {"VCU9724704"}

# pylint: disable=protected-access


class TestActionDataPoint:
    """Tests for DpAction data points."""

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
    async def test_action_basic_functionality(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test DpAction basic functionality and value sending."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        action: DpAction = cast(
            DpAction,
            central.get_generic_data_point(channel_address="VCU9724704:1", parameter="LOCK_TARGET_LEVEL"),
        )
        assert action.usage == DataPointUsage.NO_CREATE
        assert action.is_readable is False
        assert action.value is None
        assert action.values == ("LOCKED", "UNLOCKED", "OPEN")
        assert action.hmtype == "ENUM"
        await action.send_value(value="OPEN")
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU9724704:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LOCK_TARGET_LEVEL",
            value=2,
        )
        await action.send_value(value=1)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU9724704:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LOCK_TARGET_LEVEL",
            value=1,
        )

        call_count = len(mock_client.method_calls)
        await action.send_value(value=1)
        assert (call_count + 1) == len(mock_client.method_calls)
