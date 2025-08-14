"""Test the AioHomematic central."""

from __future__ import annotations

from functools import cached_property
import os

import orjson
import pytest

from aiohomematic.const import ADDRESS_SEPARATOR, DataPointUsage
from aiohomematic.model.decorators import (
    get_public_attributes_for_config_property,
    get_public_attributes_for_info_property,
    get_public_attributes_for_state_property,
)
from aiohomematic.model.generic import GenericDataPoint

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
    assert len(central_unit_mini.get_data_points(exclude_no_create=False)) == 68

    usage_types: dict[DataPointUsage, int] = {}
    for dp in central_unit_mini.get_data_points(exclude_no_create=False):
        if hasattr(dp, "usage"):
            if dp.usage not in usage_types:
                usage_types[dp.usage] = 0
            counter = usage_types[dp.usage]
            usage_types[dp.usage] = counter + 1

    assert usage_types[DataPointUsage.NO_CREATE] == 45
    assert usage_types[DataPointUsage.CDP_PRIMARY] == 4
    assert usage_types[DataPointUsage.DATA_POINT] == 14
    assert usage_types[DataPointUsage.CDP_VISIBLE] == 5


@pytest.mark.enable_socket
@pytest.mark.asyncio
async def test_central_full(central_unit_full) -> None:  # noqa: C901
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
        for dp in device.generic_data_points:
            if dp.parameter not in data[device.model]:
                data[device.model][dp.parameter] = f"{dp.hmtype}"
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
    assert len(channel_type_names) == 555
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
    for dp in central_unit_full.get_data_points(exclude_no_create=False):
        if hasattr(dp, "hmtype"):
            if dp.hmtype not in data_point_types:
                data_point_types[dp.hmtype] = {}
            if type(dp).__name__ not in data_point_types[dp.hmtype]:
                data_point_types[dp.hmtype][type(dp).__name__] = []

            data_point_types[dp.hmtype][type(dp).__name__].append(dp)

        if isinstance(dp, GenericDataPoint):
            pub_value_props = get_public_attributes_for_state_property(data_object=dp)
            assert pub_value_props
            pub_config_props = get_public_attributes_for_config_property(data_object=dp)
            assert pub_config_props

    parameters: list[tuple[str, int]] = []
    for dp in central_unit_full.get_data_points(exclude_no_create=False):
        if hasattr(dp, "parameter") and (dp.parameter, dp._operations) not in parameters:
            parameters.append((dp.parameter, dp._operations))
    parameters = sorted(parameters)

    units = set()
    for dp in central_unit_full.get_data_points(exclude_no_create=False):
        if hasattr(dp, "unit"):
            units.add(dp.unit)

    usage_types: dict[DataPointUsage, int] = {}
    for dp in central_unit_full.get_data_points(exclude_no_create=False):
        if hasattr(dp, "usage"):
            if dp.usage not in usage_types:
                usage_types[dp.usage] = 0
            counter = usage_types[dp.usage]
            usage_types[dp.usage] = counter + 1

    addresses: dict[str, str] = {}
    for address, device in central_unit_full._devices.items():
        addresses[address] = f"{device.model}.json"

    with open(
        file=os.path.join(central_unit_full.config.storage_folder, "all_devices.json"),
        mode="wb",
    ) as fptr:
        fptr.write(orjson.dumps(addresses, option=orjson.OPT_INDENT_2 | orjson.OPT_NON_STR_KEYS))

    def is_cached_property(cls: type, attr_name: str) -> bool:
        attr = getattr(cls, attr_name, None)
        return isinstance(attr, cached_property)

    # check __dict__ / __slots__
    for device in central_unit_full.devices:
        assert hasattr(device, "__dict__") is False
        assert hasattr(device.value_cache, "__dict__") is False

        for ch in device.channels.values():
            assert hasattr(ch, "__dict__") is False
        for ge in device.generic_data_points:
            assert hasattr(ge, "__dict__") is False
        for ev in device.generic_events:
            assert hasattr(ev, "__dict__") is False
        for ce in device.custom_data_points:
            assert hasattr(ce, "__dict__") is False
        for cc in device.calculated_data_points:
            assert hasattr(cc, "__dict__") is False
        if device.update_data_point:
            assert hasattr(device.update_data_point, "__dict__") is False
    for prg in central_unit_full.program_data_points:
        assert hasattr(prg, "__dict__") is False
    for sv in central_unit_full.sysvar_data_points:
        assert hasattr(sv, "__dict__") is False

    assert usage_types[DataPointUsage.CDP_PRIMARY] == 271
    assert usage_types[DataPointUsage.CDP_SECONDARY] == 162
    assert usage_types[DataPointUsage.CDP_VISIBLE] == 141
    assert usage_types[DataPointUsage.DATA_POINT] == 3933
    assert usage_types[DataPointUsage.NO_CREATE] == 4271

    assert len(ce_channels) == 129
    assert len(data_point_types) == 6
    assert len(parameters) == 232

    assert len(central_unit_full._devices) == 393
    virtual_remotes = ["VCU4264293", "VCU0000057", "VCU0000001"]
    await central_unit_full.delete_devices(interface_id=const.INTERFACE_ID, addresses=virtual_remotes)
    assert len(central_unit_full._devices) == 390
    del_addresses = list(central_unit_full.device_descriptions.get_device_descriptions(const.INTERFACE_ID))
    del_addresses = [adr for adr in del_addresses if ADDRESS_SEPARATOR not in adr]
    await central_unit_full.delete_devices(interface_id=const.INTERFACE_ID, addresses=del_addresses)
    assert len(central_unit_full._devices) == 0
    assert len(central_unit_full.get_data_points(exclude_no_create=False)) == 0
