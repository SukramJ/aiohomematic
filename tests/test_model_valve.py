# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for model/custom valve data points of aiohomematic."""

from typing import cast
from unittest.mock import AsyncMock, call

import pytest

from aiohomematic.client import CommandPriority
from aiohomematic.const import WAIT_FOR_CALLBACK, DataPointUsage, DeviceProfile, Field, Parameter, ParamsetKey
from aiohomematic.model.combined.field import CombinedTimerField
from aiohomematic.model.custom import CustomDpIpIrrigationValve, get_profile_config
from aiohomematic_test_support.helper import get_prepared_custom_data_point

TEST_DEVICES: set[str] = {"VCU8976407"}

# pylint: disable=protected-access


class TestIpIrrigationValve:
    """Tests for CustomDpIpIrrigationValve data points."""

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
    async def test_irrigation_valve_functionality(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test CustomDpIpIrrigationValve open/close operations and timer control."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        valve: CustomDpIpIrrigationValve = cast(
            CustomDpIpIrrigationValve, get_prepared_custom_data_point(central, "VCU8976407", 4)
        )
        assert valve.usage == DataPointUsage.CDP_PRIMARY
        assert valve.service_method_names == (
            "close",
            "load_data_point_value",
            "open",
        )

        await valve.close()
        assert valve.value is False
        assert valve.group_value is False
        await valve.open()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU8976407:4",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
            value=True,
            wait_for_callback=None,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert valve.value is True
        await valve.close()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU8976407:4",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
            value=False,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert valve.value is False
        await valve.open(on_time=60)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU8976407:4",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"ON_TIME": 60.0, "STATE": True},
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert valve.value is True

        await valve.close()
        valve.set_timer_on_time(on_time=35.4)
        await valve.open()
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU8976407:4",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"ON_TIME": 35.4, "STATE": True},
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )

        await valve.open()
        call_count = len(mock_client.method_calls)
        await valve.open()
        assert call_count == len(mock_client.method_calls)

        await valve.close()
        call_count = len(mock_client.method_calls)
        await valve.close()
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
    async def test_open_uses_duration_without_on_time(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Send the timer via DURATION_VALUE when the firmware has no ON_TIME."""
        central, _, _ = central_client_factory_with_homegear_client
        valve: CustomDpIpIrrigationValve = cast(
            CustomDpIpIrrigationValve, get_prepared_custom_data_point(central, "VCU8976407", 4)
        )
        await valve.close()

        # The fixture has firmware 1.0.10, so the current firmware is simulated: ON_TIME is absent.
        valve._combined_data_points[Field.ON_TIME_VALUE] = CombinedTimerField(
            value_field=Field.ON_TIME_VALUE
        ).create_combined_dp(channel=valve._channel, data_points={})
        duration = AsyncMock()
        valve._combined_data_points[Field.DURATION_VALUE] = duration

        await valve.open(on_time=120)

        duration.send_value.assert_awaited_once()
        assert duration.send_value.await_args.kwargs["value"] == 120.0

    def test_profile_maps_duration_parameters(self) -> None:
        """Firmware 1.3.4 and later has DURATION_VALUE and DURATION_UNIT instead of ON_TIME."""
        fields = get_profile_config(profile_type=DeviceProfile.IP_IRRIGATION_VALVE).channel_group.fields
        assert fields[Field.DURATION_UNIT] == Parameter.DURATION_UNIT
        assert fields[Field.DURATION_VALUE] == Parameter.DURATION_VALUE
        assert fields[Field.ON_TIME_VALUE] == Parameter.ON_TIME
