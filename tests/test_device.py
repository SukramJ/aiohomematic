"""Tests for devices of aiohomematic."""

from __future__ import annotations

import asyncio

import pytest

from tests import const

TEST_DEVICES: dict[str, str] = {
    "VCU2128127": "HmIP-BSM.json",
    "VCU6354483": "HmIP-STHD.json",
}

# pylint: disable=protected-access


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
async def test_device_general(
    central_client_factory_with_pydevccu_client,
) -> None:
    """Test device availability."""
    central, _, _ = central_client_factory_with_pydevccu_client
    device = central.get_device(address="VCU2128127")
    assert device.address == "VCU2128127"
    assert device.name == "HmIP-BSM VCU2128127"
    assert (
        str(device) == "address: VCU2128127, "
        "model: HmIP-BSM, "
        "name: HmIP-BSM VCU2128127, "
        "generic dps: 27, "
        "calculated dps: 0, "
        "custom dps: 3, "
        "events: 6"
    )
    assert device.model == "HmIP-BSM"
    assert device.interface == "BidCos-RF"
    assert device.interface_id == const.INTERFACE_ID
    assert device.has_custom_data_point_definition is True
    assert len(device.custom_data_points) == 3
    assert len(device.channels) == 11


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
async def test_device_availability(
    central_client_factory_with_pydevccu_client,
) -> None:
    """Test device availability."""
    central, _, _ = central_client_factory_with_pydevccu_client
    device = central.get_device(address="VCU6354483")
    assert device.available is True
    for gdp in device.generic_data_points:
        assert gdp.available is True
    for cdp in device.custom_data_points:
        assert cdp.available is True

    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU6354483:0", parameter="UNREACH", value=1
    )
    assert device.available is False
    for gdp in device.generic_data_points:
        assert gdp.available is False
    for cdp in device.custom_data_points:
        assert cdp.available is False

    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU6354483:0", parameter="UNREACH", value=0
    )
    assert device.available is True
    for gdp in device.generic_data_points:
        assert gdp.available is True
    for cdp in device.custom_data_points:
        assert cdp.available is True


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
async def test_device_config_pending(
    central_client_factory_with_pydevccu_client,
) -> None:
    """Test device availability."""
    central, _, _ = central_client_factory_with_pydevccu_client
    device = central.get_device(address="VCU2128127")
    assert device._dp_config_pending.value is False
    cache_hash = central.paramset_descriptions.content_hash
    last_save_triggered = central.paramset_descriptions.last_save_triggered
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU2128127:0", parameter="CONFIG_PENDING", value=True
    )
    assert device._dp_config_pending.value is True
    assert cache_hash == central.paramset_descriptions.content_hash
    assert last_save_triggered == central.paramset_descriptions.last_save_triggered
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU2128127:0", parameter="CONFIG_PENDING", value=False
    )
    assert device._dp_config_pending.value is False
    await asyncio.sleep(2)
    # Save triggered, but data not changed
    assert cache_hash == central.paramset_descriptions.content_hash
    assert last_save_triggered != central.paramset_descriptions.last_save_triggered
