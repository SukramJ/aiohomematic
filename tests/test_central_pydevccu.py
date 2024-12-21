"""Test the HaHomematic central."""

from __future__ import annotations

import os

import orjson
import pytest

from hahomematic.const import DataPointUsage
from hahomematic.model.decorators import (
    get_public_attributes_for_config_property,
    get_public_attributes_for_info_property,
    get_public_attributes_for_state_property,
)
from hahomematic.model.generic import GenericDataPoint

from tests import const

# pylint: disable=protected-access


@pytest.mark.enable_socket
@pytest.mark.asyncio
async def test_central_mini(central_unit_mini) -> None:
    """Test the central."""
    assert central_unit_mini
    assert central_unit_mini.name == const.CENTRAL_NAME
    assert central_unit_mini.model == "PyDevCCU"
    assert central_unit_mini.get_client(const.INTERFACE_ID).model == "PyDevCCU"
    assert central_unit_mini.primary_client.model == "PyDevCCU"
    assert len(central_unit_mini._devices) == 2
    assert len(central_unit_mini.get_data_points(exclude_no_create=False)) == 63


@pytest.mark.enable_socket
@pytest.mark.asyncio
async def test_central_full(central_unit_full) -> None:
    """Test the central."""
    assert central_unit_full
    assert central_unit_full.name == const.CENTRAL_NAME
    assert central_unit_full.model == "PyDevCCU"
    assert central_unit_full.get_client(const.INTERFACE_ID).model == "PyDevCCU"
    assert central_unit_full.primary_client.model == "PyDevCCU"

    data = {}
    for device in central_unit_full.devices:
        if device.model not in data:
            data[device.model] = {}
        for data_point in device.generic_data_points:
            if data_point.parameter not in data[device.model]:
                data[device.model][data_point.parameter] = f"{data_point.hmtype}"
        pub_state_props = get_public_attributes_for_state_property(data_object=device)
        assert pub_state_props
        info_config_props = get_public_attributes_for_info_property(data_object=device)
        assert info_config_props

    custom_dps = []
    channel_type_names = set()
    for device in central_unit_full.devices:
        custom_dps.extend(device.custom_data_points)
        for channel in device.channels.values():
            channel_type_names.add(channel.type_name)
    channel_type_names = sorted(channel_type_names)
    assert len(channel_type_names) == 541
    ce_channels = {}
    for cdp in custom_dps:
        if cdp.device.model not in ce_channels:
            ce_channels[cdp.device.model] = []
        ce_channels[cdp.device.model].append(cdp.channel.no)
        pub_value_props = get_public_attributes_for_state_property(data_object=cdp)
        assert pub_value_props
        pub_config_props = get_public_attributes_for_config_property(data_object=cdp)
        assert pub_config_props

    data_point_types = {}
    for data_point in central_unit_full.get_data_points(exclude_no_create=False):
        if hasattr(data_point, "hmtype"):
            if data_point.hmtype not in data_point_types:
                data_point_types[data_point.hmtype] = {}
            if type(data_point).__name__ not in data_point_types[data_point.hmtype]:
                data_point_types[data_point.hmtype][type(data_point).__name__] = []

            data_point_types[data_point.hmtype][type(data_point).__name__].append(data_point)

        if isinstance(data_point, GenericDataPoint):
            pub_value_props = get_public_attributes_for_state_property(data_object=data_point)
            assert pub_value_props
            pub_config_props = get_public_attributes_for_config_property(data_object=data_point)
            assert pub_config_props

    parameters: list[tuple[str, int]] = []
    for data_point in central_unit_full.get_data_points(exclude_no_create=False):
        if hasattr(data_point, "parameter") and (data_point.parameter, data_point._operations) not in parameters:
            parameters.append((data_point.parameter, data_point._operations))
    parameters = sorted(parameters)

    units = set()
    for data_point in central_unit_full.get_data_points(exclude_no_create=False):
        if hasattr(data_point, "unit"):
            units.add(data_point.unit)

    usage_types: dict[DataPointUsage, int] = {}
    for data_point in central_unit_full.get_data_points(exclude_no_create=False):
        if hasattr(data_point, "usage"):
            if data_point.usage not in usage_types:
                usage_types[data_point.usage] = 0
            counter = usage_types[data_point.usage]
            usage_types[data_point.usage] = counter + 1

    addresses: dict[str, str] = {}
    for address, device in central_unit_full._devices.items():
        addresses[address] = f"{device.model}.json"

    with open(
        file=os.path.join(central_unit_full.config.storage_folder, "all_devices.json"),
        mode="wb",
    ) as fptr:
        fptr.write(orjson.dumps(addresses, option=orjson.OPT_INDENT_2 | orjson.OPT_NON_STR_KEYS))

    assert usage_types[DataPointUsage.NO_CREATE] == 4090
    assert usage_types[DataPointUsage.CDP_PRIMARY] == 261
    assert usage_types[DataPointUsage.DATA_POINT] == 3688
    assert usage_types[DataPointUsage.CDP_VISIBLE] == 133
    assert usage_types[DataPointUsage.CDP_SECONDARY] == 154

    assert len(ce_channels) == 124
    assert len(data_point_types) == 6
    assert len(parameters) == 221

    assert len(central_unit_full._devices) == 386
    virtual_remotes = ["VCU4264293", "VCU0000057", "VCU0000001"]
    await central_unit_full.delete_devices(interface_id=const.INTERFACE_ID, addresses=virtual_remotes)
    assert len(central_unit_full._devices) == 383
    del_addresses = list(central_unit_full.device_descriptions.get_device_descriptions(const.INTERFACE_ID))
    del_addresses = [adr for adr in del_addresses if ":" not in adr]
    await central_unit_full.delete_devices(interface_id=const.INTERFACE_ID, addresses=del_addresses)
    assert len(central_unit_full._devices) == 0
    assert len(central_unit_full.get_data_points(exclude_no_create=False)) == 0
