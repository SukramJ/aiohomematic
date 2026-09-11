# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract tests for availability re-sync after a reconnect.

STABILITY GUARANTEE
-------------------
The backend announces UN_REACH only when the value changes. A transition that
happens while the connection is down is therefore never delivered, and the
device would keep the stale value for the whole lifetime of the central.

These tests pin the contract that closes that gap:

1. ``Device.reload_availability_state()`` re-reads channel 0 from the backend
   and applies UN_REACH / STICKY_UN_REACH / CONFIG_PENDING.
2. The value is *measured*, never defaulted: a failed or incomplete read leaves
   the data points untouched.
3. Connection recovery performs that re-read — in the staged data load as well
   as in the circuit breaker recovery.

See ADR-0018 for architectural context.
"""

from typing import Any
from unittest.mock import patch

import pytest

from aiohomematic.const import Parameter, ParamsetKey
from aiohomematic.exceptions import ClientException
from aiohomematic_test_support import const

TEST_DEVICES: set[str] = {"VCU2128127"}
TEST_DEVICE_ADDRESS = "VCU2128127"


async def _mark_unreachable(central: Any, device: Any) -> None:
    """Let the backend report the device as unreachable."""
    await central.event_coordinator.data_point_event(
        interface_id=const.INTERFACE_ID,
        channel_address=f"{device.address}:0",
        parameter=Parameter.UN_REACH,
        value=1,
    )


class TestAvailabilityResyncContract:
    """Contract: availability is re-measured after a reconnect."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("address_device_translation", "do_mock_client", "ignore_devices_on_create", "un_ignore_list"),
        [(TEST_DEVICES, True, None, None)],
    )
    async def test_reload_does_not_default_on_absent_parameter(
        self, central_client_factory_with_homegear_client
    ) -> None:
        """Contract: a paramset without UN_REACH must not flip the device to available."""
        central, client, _ = central_client_factory_with_homegear_client
        device = central.device_coordinator.get_device(address=TEST_DEVICE_ADDRESS)

        await _mark_unreachable(central=central, device=device)

        with patch.object(client, "get_paramset", return_value={"STATE": False}):
            await device.reload_availability_state()

        assert device.available is False, "an absent UN_REACH must not be treated as 'reachable'"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("address_device_translation", "do_mock_client", "ignore_devices_on_create", "un_ignore_list"),
        [(TEST_DEVICES, True, None, None)],
    )
    async def test_reload_does_not_default_on_failed_read(self, central_client_factory_with_homegear_client) -> None:
        """Contract: a failed read must not flip the device to available."""
        central, client, _ = central_client_factory_with_homegear_client
        device = central.device_coordinator.get_device(address=TEST_DEVICE_ADDRESS)

        await _mark_unreachable(central=central, device=device)

        with patch.object(client, "get_paramset", side_effect=ClientException("boom")):
            await device.reload_availability_state()

        assert device.available is False, "a failed read must not be treated as 'reachable'"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("address_device_translation", "do_mock_client", "ignore_devices_on_create", "un_ignore_list"),
        [(TEST_DEVICES, True, None, None)],
    )
    async def test_reload_keeps_unavailable_when_backend_still_reports_unreachable(
        self, central_client_factory_with_homegear_client
    ) -> None:
        """Contract: a device the backend still reports as unreachable stays unavailable."""
        central, client, _ = central_client_factory_with_homegear_client
        device = central.device_coordinator.get_device(address=TEST_DEVICE_ADDRESS)

        await _mark_unreachable(central=central, device=device)

        with patch.object(client, "get_paramset", return_value={Parameter.UN_REACH: True}):
            await device.reload_availability_state()

        assert device.available is False

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("address_device_translation", "do_mock_client", "ignore_devices_on_create", "un_ignore_list"),
        [(TEST_DEVICES, True, None, None)],
    )
    async def test_reload_notifies_data_points(self, central_client_factory_with_homegear_client) -> None:
        """Contract: the recovered availability reaches the data points of other channels."""
        central, client, _ = central_client_factory_with_homegear_client
        device = central.device_coordinator.get_device(address=TEST_DEVICE_ADDRESS)

        other_channel_dp = next(dp for dp in device.generic_data_points if dp.channel.no not in (None, 0))

        await _mark_unreachable(central=central, device=device)
        assert other_channel_dp.available is False

        updates: list[str] = []
        unsubscribe = device.subscribe_to_device_updated(handler=lambda **kwargs: updates.append("updated"))
        try:
            with patch.object(client, "get_paramset", return_value={Parameter.UN_REACH: False}):
                await device.reload_availability_state()
        finally:
            unsubscribe()

        assert other_channel_dp.available is True
        assert updates, "a recovered availability must publish a device updated event"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("address_device_translation", "do_mock_client", "ignore_devices_on_create", "un_ignore_list"),
        [(TEST_DEVICES, True, None, None)],
    )
    async def test_reload_reads_channel_zero_values_paramset(self, central_client_factory_with_homegear_client) -> None:
        """Contract: the re-read fetches the channel 0 VALUES paramset from the backend."""
        central, client, _ = central_client_factory_with_homegear_client
        device = central.device_coordinator.get_device(address=TEST_DEVICE_ADDRESS)

        await _mark_unreachable(central=central, device=device)
        assert device.available is False

        with patch.object(
            client, "get_paramset", return_value={Parameter.UN_REACH: False, Parameter.STICKY_UN_REACH: False}
        ) as get_paramset_mock:
            await device.reload_availability_state()

        get_paramset_mock.assert_awaited_once()
        kwargs = get_paramset_mock.await_args.kwargs
        assert kwargs["channel_address"] == f"{TEST_DEVICE_ADDRESS}:0"
        assert kwargs["paramset_key"] == ParamsetKey.VALUES
        assert device.available is True


class TestRecoveryResyncContract:
    """Contract: connection recovery re-measures availability before refreshing data."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("address_device_translation", "do_mock_client", "ignore_devices_on_create", "un_ignore_list"),
        [(TEST_DEVICES, True, None, None)],
    )
    async def test_data_load_stage_reloads_availability(self, central_client_factory_with_homegear_client) -> None:
        """Contract: the data-load stage re-reads availability for every device of the interface."""
        central, _, _ = central_client_factory_with_homegear_client
        device = central.device_coordinator.get_device(address=TEST_DEVICE_ADDRESS)
        recovery = central.connection_recovery_coordinator

        with patch.object(type(device), "reload_availability_state") as reload_mock:
            assert await recovery._stage_data_load(interface_id=const.INTERFACE_ID) is True

        reload_mock.assert_awaited()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("address_device_translation", "do_mock_client", "ignore_devices_on_create", "un_ignore_list"),
        [(TEST_DEVICES, True, None, None)],
    )
    async def test_interface_data_refresh_reloads_availability(
        self, central_client_factory_with_homegear_client
    ) -> None:
        """Contract: the circuit-breaker recovery refresh re-reads availability as well."""
        central, _, _ = central_client_factory_with_homegear_client
        device = central.device_coordinator.get_device(address=TEST_DEVICE_ADDRESS)
        recovery = central.connection_recovery_coordinator

        with patch.object(type(device), "reload_availability_state") as reload_mock:
            await recovery._refresh_interface_data(interface_id=const.INTERFACE_ID)

        reload_mock.assert_awaited()
