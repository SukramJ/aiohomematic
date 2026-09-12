# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract tests for the ReGa bulk snapshot as an initial value source.

STABILITY GUARANTEE
-------------------
Interfaces in ``INTERFACES_SKIPPING_INIT_GETVALUE_FALLBACK`` have no per-parameter
getValue fallback during init (#3228, #3260, #3274). For them the ReGa bulk snapshot is
the ONLY source of an initial value, so it must still be available when the value is
actually consumed.

The snapshot is taken once during ``start_clients()`` and expires after
``MAX_CACHE_AGE``. Its consumer for channels other than 0 is Home Assistant's
``async_added_to_hass``, which runs after the platforms have been forwarded — reliably
later than that. A data point that never emits an event on its own (a cover's LEVEL, a
switch's STATE) therefore stayed unset until the device was operated by hand (#3398).

CONTRACT: on an expired snapshot the init path MUST refresh it instead of giving up,
and it MUST still not fall back to a per-parameter getValue.

See ADR-0018 for architectural context.
"""

from typing import Any
from unittest.mock import AsyncMock

import pytest

from aiohomematic.const import INTERFACES_SKIPPING_INIT_GETVALUE_FALLBACK, Interface, ParamsetKey
from aiohomematic.interfaces import DataCacheProviderProtocol
from aiohomematic.store.dynamic import CentralDataCache

TEST_DEVICES: set[str] = {"VCU2128127"}

# pylint: disable=protected-access


class TestBulkSnapshotProtocolContract:
    """The refresh entry point must be part of the data cache contract."""

    def test_central_data_cache_implements_refresh_if_expired(self) -> None:
        """CONTRACT: CentralDataCache MUST implement the refresh entry point."""
        assert callable(CentralDataCache.refresh_if_expired)

    def test_data_cache_provider_exposes_refresh_if_expired(self) -> None:
        """CONTRACT: DataCacheProviderProtocol MUST offer refresh_if_expired."""
        assert "refresh_if_expired" in dir(DataCacheProviderProtocol), (
            "DataCacheProviderProtocol MUST expose refresh_if_expired: it is the only way "
            "for the init path to recover an expired bulk snapshot"
        )


class TestBulkSnapshotInitContract:
    """The init path must refresh an expired snapshot for fallback-free interfaces."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [(TEST_DEVICES, True, None, None)],
    )
    @pytest.mark.parametrize("skip_interface", sorted(INTERFACES_SKIPPING_INIT_GETVALUE_FALLBACK))
    async def test_expired_snapshot_is_refreshed_instead_of_abandoned(
        self, central_client_factory_with_homegear_client, monkeypatch, skip_interface: Interface
    ) -> None:
        """CONTRACT: an expired snapshot is refreshed, and getValue stays unused."""
        central, _, _ = central_client_factory_with_homegear_client
        device = central.device_coordinator.get_device(address="VCU2128127")
        assert device is not None

        # Pretend this device lives on the interface under test.
        monkeypatch.setattr(device, "_interface", skip_interface)

        values_dps = [dp for dp in device.generic_data_points if dp.paramset_key == ParamsetKey.VALUES]
        assert values_dps
        dpk = values_dps[0].dpk

        refresh_mock = AsyncMock(return_value=False)
        monkeypatch.setattr(central.cache_coordinator.data_cache, "refresh_if_expired", refresh_mock)

        backend_calls: list[int] = []

        async def _counting_get_value(**kw: Any) -> Any:
            backend_calls.append(1)
            return None

        monkeypatch.setattr(device.client, "get_value", _counting_get_value)

        result = await device.value_cache._get_values_for_cache(dpk=dpk)

        refresh_mock.assert_awaited_once_with(interface=skip_interface)
        assert backend_calls == [], "the per-parameter getValue fallback MUST stay disabled"
        assert result == {dpk.parameter: device.value_cache._NO_VALUE_CACHE_ENTRY}

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [(TEST_DEVICES, True, None, None)],
    )
    async def test_refreshed_snapshot_value_reaches_the_data_point(
        self, central_client_factory_with_homegear_client, monkeypatch
    ) -> None:
        """CONTRACT: a value recovered by the refresh is returned to the caller."""
        central, _, _ = central_client_factory_with_homegear_client
        device = central.device_coordinator.get_device(address="VCU2128127")
        assert device is not None

        monkeypatch.setattr(device, "_interface", Interface.BIDCOS_RF)

        values_dps = [dp for dp in device.generic_data_points if dp.paramset_key == ParamsetKey.VALUES]
        assert values_dps
        dpk = values_dps[0].dpk

        data_cache = central.cache_coordinator.data_cache
        recovered = {f"{Interface.BIDCOS_RF}.{dpk.channel_address}.{dpk.parameter}": 0.5}

        async def _refresh_if_expired(*, interface: Interface) -> bool:
            data_cache.add_data(interface=interface, all_device_data=recovered)
            return True

        monkeypatch.setattr(data_cache, "refresh_if_expired", _refresh_if_expired)

        result = await device.value_cache._get_values_for_cache(dpk=dpk)

        assert result == {dpk.parameter: 0.5}
