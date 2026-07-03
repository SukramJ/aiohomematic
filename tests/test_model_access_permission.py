# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for access permission data points of aiohomematic."""

from typing import cast
from unittest.mock import call

import pytest

from aiohomematic.client import CommandPriority
from aiohomematic.const import DataPointCategory, DataPointUsage, ParamsetKey
from aiohomematic.model.custom import CustomDpIpAccessPermission
from aiohomematic_test_support import const
from aiohomematic_test_support.helper import get_prepared_custom_data_point

TEST_DEVICES: set[str] = {"VCU9724704"}

# pylint: disable=protected-access


class TestIpAccessPermission:
    """Tests for CustomDpIpAccessPermission data points (HmIP-DLD / HmIP-FWI user access channels)."""

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
    async def test_ip_access_permission(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test that the HmIP-DLD exposes a permission switch per user channel 2-9."""
        central, mock_client, _ = central_client_factory_with_homegear_client

        # One permission switch per user channel 2..9.
        full_names: set[str] = set()
        for channel_no in range(2, 10):
            perm = cast(
                CustomDpIpAccessPermission,
                get_prepared_custom_data_point(central, "VCU9724704", channel_no),
            )
            assert perm is not None
            assert perm.category == DataPointCategory.SWITCH
            assert perm.usage == DataPointUsage.CDP_PRIMARY
            # Each user channel must be individually named (mirrors HmIP-DLP `chN`).
            assert perm.full_name.endswith(f"ch{channel_no}")
            full_names.add(perm.full_name)
        assert len(full_names) == 8

        perm = cast(
            CustomDpIpAccessPermission,
            get_prepared_custom_data_point(central, "VCU9724704", 2),
        )

        # value mirrors the read-only STATE parameter.
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU9724704:2", parameter="STATE", value=True
        )
        assert perm.value is True

        # turn_off writes ACCESS_AUTHORIZATION=DISABLE.
        await perm.turn_off()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU9724704:2",
            paramset_key=ParamsetKey.VALUES,
            parameter="ACCESS_AUTHORIZATION",
            value="DISABLE",
            wait_for_callback=None,
            priority=CommandPriority.HIGH,
            retry=True,
        )

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU9724704:2", parameter="STATE", value=False
        )
        assert perm.value is False

        # turn_on writes ACCESS_AUTHORIZATION=ENABLE.
        await perm.turn_on()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU9724704:2",
            paramset_key=ParamsetKey.VALUES,
            parameter="ACCESS_AUTHORIZATION",
            value="ENABLE",
            wait_for_callback=None,
            priority=CommandPriority.HIGH,
            retry=True,
        )

    @pytest.mark.enable_socket
    @pytest.mark.asyncio
    @pytest.mark.xdist_group("pydevccu")
    async def test_ip_access_permission_fwi(self, central_unit_pydevccu_full) -> None:
        """
        Test that the HmIP-FWI exposes permission switches (ch 1-8) without losing its other data points.

        The HmIP-FWI is not part of the recorded homegear session, so the virtual
        PyDevCCU instance is used here (turn_on/turn_off/value are already covered by
        the shared CustomDpIpAccessPermission logic in the HmIP-DLD test above).
        """
        central = central_unit_pydevccu_full

        # One permission switch per user channel 1..8, each individually named.
        full_names: set[str] = set()
        for channel_no in range(1, 9):
            perm = cast(
                CustomDpIpAccessPermission,
                get_prepared_custom_data_point(central, "VCU4820995", channel_no),
            )
            assert perm is not None
            assert perm.category == DataPointCategory.SWITCH
            assert perm.usage == DataPointUsage.CDP_PRIMARY
            assert perm.full_name.endswith(f"ch{channel_no}")
            full_names.add(perm.full_name)
        assert len(full_names) == 8

        # Regression guard: the FWI keeps its unrelated generic data points (the custom
        # profile must not suppress them). Channel-0 access-code sensor and a channel-9
        # output switch remain present.
        assert central.query_facade.get_generic_data_point(channel_address="VCU4820995:0", parameter="CODE_STATE")
        assert central.query_facade.get_generic_data_point(channel_address="VCU4820995:9", parameter="STATE")
