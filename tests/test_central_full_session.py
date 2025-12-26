# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Test the AioHomematic central."""

from __future__ import annotations

import collections

import pytest

from aiohomematic.const import ADDRESS_SEPARATOR, DataPointUsage
from aiohomematic.model.generic import GenericDataPoint
from aiohomematic.property_decorators import Kind, get_hm_property_by_kind
from aiohomematic_test_support import const

# pylint: disable=protected-access


class TestCentralFullSession:
    """Test central unit with full device session."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (None, True, None, None),
        ],
    )
    async def test_central_full(self, central_client_factory_with_homegear_client) -> None:  # noqa: C901
        """Test the central."""
        central, _, _ = central_client_factory_with_homegear_client
        assert central
        assert central.name == const.CENTRAL_NAME
        assert central.model == "PyDevCCU"
        assert central.client_coordinator.get_client(interface_id=const.INTERFACE_ID).model == "PyDevCCU"
        assert central.client_coordinator.primary_client.model == "PyDevCCU"
        assert len(central.device_registry.devices) == 395

        data = {}
        for device in central.device_registry.devices:
            if device.model in ("HmIP-BSM", "HmIP-BDT", "HmIP-PSM", "HmIP-FSM", "HmIP-WSM", "HmIP-SMO230-A"):
                assert device.has_sub_devices is False
            if device.model in ("HmIP-DRSI4", "HmIP-DRDI3", "HmIP-BSL"):
                assert device.has_sub_devices is True

            if device.model not in data:
                data[device.model] = {}
            for dp in device.generic_data_points:
                if dp.parameter not in data[device.model]:
                    data[device.model][dp.parameter] = f"{dp.hmtype}"
            pub_state_props = get_hm_property_by_kind(data_object=device, kind=Kind.STATE)
            assert pub_state_props
            info_config_props = get_hm_property_by_kind(data_object=device, kind=Kind.INFO)
            assert info_config_props

        # channel.type_name, device.model
        channel_type_device = {}
        for device in central.device_registry.devices:
            for channel in device.channels.values():
                if channel.no is None:
                    continue
                if channel.type_name not in channel_type_device:
                    channel_type_device[channel.type_name] = set()
                channel_type_device[channel.type_name].add(device.model)

        assert len(channel_type_device) == 162

        # channel.type_name, parameter, device.model
        channel_parameter_devices = {}
        for device in central.device_registry.devices:
            for channel in device.channels.values():
                if channel.no is None:
                    continue
                if channel.type_name not in channel_parameter_devices:
                    channel_parameter_devices[channel.type_name] = {}
                for ge in channel.generic_data_points:
                    if ge.parameter not in channel_parameter_devices[channel.type_name]:
                        channel_parameter_devices[channel.type_name][ge.parameter] = set()
                    channel_parameter_devices[channel.type_name][ge.parameter].add(device.model)

        assert len(channel_parameter_devices) == 162

        _channel_parameter_devices = collections.OrderedDict(sorted(channel_parameter_devices.items()))

        custom_dps = []
        channel_type_names = set()
        for device in central.device_registry.devices:
            custom_dps.extend(device.custom_data_points)
            for channel in device.channels.values():
                channel_type_names.add(channel.type_name)

        channel_type_names = sorted(channel_type_names)
        assert len(channel_type_names) == 557
        ce_channels = {}
        for cdp in custom_dps:
            if cdp.device.model not in ce_channels:
                ce_channels[cdp.device.model] = []
            ce_channels[cdp.device.model].append(cdp.channel.no)
            pub_state_props = get_hm_property_by_kind(data_object=cdp, kind=Kind.STATE)
            assert pub_state_props
            pub_config_props = get_hm_property_by_kind(data_object=cdp, kind=Kind.CONFIG)
            assert pub_config_props

        data_point_types = {}
        for dp in central.get_data_points(exclude_no_create=False):
            if hasattr(dp, "hmtype"):
                if dp.hmtype not in data_point_types:
                    data_point_types[dp.hmtype] = {}
                if type(dp).__name__ not in data_point_types[dp.hmtype]:
                    data_point_types[dp.hmtype][type(dp).__name__] = []

                data_point_types[dp.hmtype][type(dp).__name__].append(dp)

            if isinstance(dp, GenericDataPoint):
                pub_state_props = get_hm_property_by_kind(data_object=dp, kind=Kind.STATE)
                assert pub_state_props
                pub_config_props = get_hm_property_by_kind(data_object=dp, kind=Kind.CONFIG)
                assert pub_config_props

        parameters: list[tuple[str, int]] = []
        for dp in central.get_data_points(exclude_no_create=False):
            if hasattr(dp, "parameter") and (dp.parameter, dp._operations) not in parameters:
                parameters.append((dp.parameter, dp._operations))
        parameters = sorted(parameters)

        units = set()
        for dp in central.get_data_points(exclude_no_create=False):
            if hasattr(dp, "unit"):
                units.add(dp.unit)

        usage_types: dict[DataPointUsage, int] = {}
        for dp in central.get_data_points(exclude_no_create=False):
            if hasattr(dp, "usage"):
                if dp.usage not in usage_types:
                    usage_types[dp.usage] = 0
                counter = usage_types[dp.usage]
                usage_types[dp.usage] = counter + 1

        # check __dict__ / __slots__
        for device in central.device_registry.devices:
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
        for prg in central.hub_coordinator.program_data_points:
            assert hasattr(prg, "__dict__") is False
        for sv in central.hub_coordinator.sysvar_data_points:
            assert hasattr(sv, "__dict__") is False

        target_roles: set[str] = set()
        source_roles: set[str] = set()
        for dev in central.device_registry.devices:
            for ch in dev.channels.values():
                target_roles.update(ch._link_target_roles)
                source_roles.update(ch._link_source_roles)

        for dev in central.device_registry.devices:
            if dev.model == "HmIP-WRCD":
                pass

        assert usage_types[DataPointUsage.CDP_PRIMARY] == 277
        assert usage_types[DataPointUsage.CDP_SECONDARY] == 162
        assert usage_types[DataPointUsage.CDP_VISIBLE] == 150
        assert usage_types[DataPointUsage.DATA_POINT] == 3993
        assert usage_types[DataPointUsage.NO_CREATE] == 4374

        assert len(ce_channels) == 133
        assert len(data_point_types) == 6
        assert len(parameters) == 249

        assert len(central.device_registry.devices) == 395
        virtual_remotes = ["VCU4264293", "VCU0000057", "VCU0000001"]
        await central.device_coordinator.delete_devices(interface_id=const.INTERFACE_ID, addresses=virtual_remotes)
        assert len(central.device_registry.devices) == 392
        del_addresses = list(
            central.cache_coordinator.device_descriptions.get_device_descriptions(interface_id=const.INTERFACE_ID)
        )
        del_addresses = [adr for adr in del_addresses if ADDRESS_SEPARATOR not in adr]
        await central.device_coordinator.delete_devices(interface_id=const.INTERFACE_ID, addresses=del_addresses)
        assert len(central.device_registry.devices) == 0
        assert len(central.get_data_points(exclude_no_create=False)) == 0
