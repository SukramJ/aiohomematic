# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Device profile definitions for custom data point implementations.

This module provides profile definitions and factory functions for creating
custom data points. Device-to-profile mappings are managed by DeviceProfileRegistry
in registry.py.

Public API of this module is defined by __all__.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import logging
from typing import Any, Final, cast

from aiohomematic import i18n
from aiohomematic.const import CDPD, DataPointCategory, DeviceProfile, Parameter
from aiohomematic.exceptions import AioHomematicException
from aiohomematic.interfaces.model import ChannelProtocol, DeviceProtocol
from aiohomematic.model.custom.profile import (
    DEFAULT_DATA_POINTS,
    PROFILE_CONFIGS,
    get_profile_config,
    profile_config_to_dict,
)
from aiohomematic.model.custom.registry import DeviceConfig, DeviceProfileRegistry
from aiohomematic.model.custom.support import CustomConfig, ExtendedConfig
from aiohomematic.model.support import generate_unique_id
from aiohomematic.support import extract_exc_args

_LOGGER: Final = logging.getLogger(__name__)


def _device_config_to_custom_config(device_config: DeviceConfig) -> CustomConfig:
    """Convert a DeviceConfig to a CustomConfig for backward compatibility."""

    def _make_func(
        *,
        channel: ChannelProtocol,
        custom_config: CustomConfig,
    ) -> None:
        """Create custom data point using DeviceConfig settings."""
        make_custom_data_point(
            channel=channel,
            data_point_class=device_config.data_point_class,
            device_profile=device_config.profile_type,
            custom_config=custom_config,
        )

    # Convert ExtendedDeviceConfig to ExtendedConfig if present
    extended: ExtendedConfig | None = None
    if device_config.extended:
        extended = ExtendedConfig(
            fixed_channels=device_config.extended.fixed_channel_fields,
            additional_data_points=device_config.extended.additional_data_points,
        )

    return CustomConfig(
        make_ce_func=_make_func,
        channels=device_config.channels,
        extended=extended,
        schedule_channel_no=device_config.schedule_channel_no,
    )


def make_custom_data_point(
    *,
    channel: ChannelProtocol,
    data_point_class: type,
    device_profile: DeviceProfile,
    custom_config: CustomConfig,
) -> None:
    """
    Create custom data point.

    We use a helper-function to avoid raising exceptions during object-init.
    """
    add_channel_groups_to_device(device=channel.device, device_profile=device_profile, custom_config=custom_config)
    group_no = get_channel_group_no(device=channel.device, channel_no=channel.no)
    channels = _relevant_channels(device_profile=device_profile, custom_config=custom_config)
    if channel.no in set(channels):
        _create_custom_data_point(
            channel=channel,
            custom_data_point_class=data_point_class,
            device_profile=device_profile,
            device_def=_get_device_group(device_profile=device_profile, group_no=group_no),
            custom_data_point_def=_get_device_data_points(device_profile=device_profile, group_no=group_no),
            group_no=group_no,
            custom_config=_rebase_pri_channels(device_profile=device_profile, custom_config=custom_config),
        )


def _create_custom_data_point(
    *,
    channel: ChannelProtocol,
    custom_data_point_class: type,
    device_profile: DeviceProfile,
    device_def: Mapping[CDPD, Any],
    custom_data_point_def: Mapping[int, tuple[Parameter, ...]],
    group_no: int | None,
    custom_config: CustomConfig,
) -> None:
    """Create custom data point."""
    unique_id = generate_unique_id(config_provider=channel.device.config_provider, address=channel.address)

    try:
        if (
            dp := custom_data_point_class(
                channel=channel,
                unique_id=unique_id,
                device_profile=device_profile,
                device_def=device_def,
                custom_data_point_def=custom_data_point_def,
                group_no=group_no,
                custom_config=custom_config,
            )
        ) and dp.has_data_points:
            channel.add_data_point(data_point=dp)
    except Exception as exc:
        raise AioHomematicException(
            i18n.tr(
                "exception.model.custom.definition.create_custom_data_point.failed",
                reason=extract_exc_args(exc=exc),
            )
        ) from exc


def _rebase_pri_channels(*, device_profile: DeviceProfile, custom_config: CustomConfig) -> CustomConfig:
    """Re base primary channel of custom config."""
    device_def = _get_device_group(device_profile=device_profile, group_no=0)
    if (pri_def := device_def[CDPD.PRIMARY_CHANNEL]) is None:
        return custom_config
    pri_channels = [cu + pri_def for cu in custom_config.channels]
    return CustomConfig(
        make_ce_func=custom_config.make_ce_func,
        channels=tuple(pri_channels),
        extended=custom_config.extended,
        schedule_channel_no=custom_config.schedule_channel_no,
    )


def _relevant_channels(*, device_profile: DeviceProfile, custom_config: CustomConfig) -> tuple[int | None, ...]:
    """Return the relevant channels."""
    device_def = _get_device_group(device_profile=device_profile, group_no=0)
    def_channels = [device_def[CDPD.PRIMARY_CHANNEL]]
    if sec_channels := device_def.get(CDPD.SECONDARY_CHANNELS):
        def_channels.extend(sec_channels)

    channels: set[int | None] = set()
    for def_ch in def_channels:
        for conf_ch in custom_config.channels:
            if def_ch is not None and conf_ch is not None:
                channels.add(def_ch + conf_ch)
            else:
                channels.add(None)
    return tuple(channels)


def add_channel_groups_to_device(
    *, device: DeviceProtocol, device_profile: DeviceProfile, custom_config: CustomConfig
) -> None:
    """Return the relevant channels."""
    device_def = _get_device_group(device_profile=device_profile, group_no=0)
    if (pri_channel := device_def[CDPD.PRIMARY_CHANNEL]) is None:
        return
    for conf_channel in custom_config.channels:
        if conf_channel is None:
            continue
        group_no = conf_channel + pri_channel
        device.add_channel_to_group(channel_no=group_no, group_no=group_no)
        if state_channel := device_def.get(CDPD.STATE_CHANNEL):
            device.add_channel_to_group(channel_no=conf_channel + state_channel, group_no=group_no)
        if sec_channels := device_def.get(CDPD.SECONDARY_CHANNELS):
            for sec_channel in sec_channels:
                device.add_channel_to_group(channel_no=conf_channel + sec_channel, group_no=group_no)


def get_channel_group_no(*, device: DeviceProtocol, channel_no: int | None) -> int | None:
    """Get channel group of sub_device."""
    return device.get_channel_group_no(channel_no=channel_no)


def get_default_data_points() -> Mapping[int | tuple[int, ...], tuple[Parameter, ...]]:
    """Return the default data points."""
    return DEFAULT_DATA_POINTS


def get_include_default_data_points(*, device_profile: DeviceProfile) -> bool:
    """Return if default data points should be included."""
    return get_profile_config(device_profile).include_default_data_points


def _get_device_definition(*, device_profile: DeviceProfile) -> Mapping[CDPD, Any]:
    """Return device from data_point definitions."""
    profile_config = get_profile_config(device_profile)
    return cast(Mapping[CDPD, Any], profile_config_to_dict(profile_config))


def _get_device_group(*, device_profile: DeviceProfile, group_no: int | None) -> Mapping[CDPD, Any]:
    """Return the device group."""
    device = _get_device_definition(device_profile=device_profile)
    group = cast(dict[CDPD, Any], device[CDPD.DEVICE_GROUP])
    # Create a deep copy of the group due to channel rebase
    group = deepcopy(group)
    if not group_no:
        return group
    # Add group_no to the primary_channel to get the real primary_channel number
    if (primary_channel := group[CDPD.PRIMARY_CHANNEL]) is not None:
        group[CDPD.PRIMARY_CHANNEL] = primary_channel + group_no

    # Add group_no to the secondary_channels
    # to get the real secondary_channel numbers
    if secondary_channel := group.get(CDPD.SECONDARY_CHANNELS):
        group[CDPD.SECONDARY_CHANNELS] = [x + group_no for x in secondary_channel]

    group[CDPD.VISIBLE_FIELDS] = _rebase_data_point_dict(
        data_point_dict=CDPD.VISIBLE_FIELDS, group=group, group_no=group_no
    )
    group[CDPD.FIELDS] = _rebase_data_point_dict(data_point_dict=CDPD.FIELDS, group=group, group_no=group_no)
    return group


def _rebase_data_point_dict(
    *, data_point_dict: CDPD, group: Mapping[CDPD, Any], group_no: int
) -> Mapping[int | None, Any]:
    """Rebase data_point_dict with group_no."""
    new_fields: dict[int | None, Any] = {}
    if fields := group.get(data_point_dict):
        for channel_no, field in fields.items():
            if channel_no is None:
                new_fields[channel_no] = field
            else:
                new_fields[channel_no + group_no] = field
    return new_fields


def _get_device_data_points(
    *, device_profile: DeviceProfile, group_no: int | None
) -> Mapping[int, tuple[Parameter, ...]]:
    """Return the device data points."""
    profile = get_profile_config(device_profile)
    additional_dps = profile.additional_data_points
    if not group_no:
        return additional_dps
    new_dps: dict[int, tuple[Parameter, ...]] = {}
    for channel_no, params in additional_dps.items():
        new_dps[channel_no + group_no] = params
    return new_dps


def get_custom_configs(
    *,
    model: str,
    category: DataPointCategory | None = None,
) -> tuple[CustomConfig, ...]:
    """Return the data_point configs to create custom data points."""
    # Query DeviceProfileRegistry (includes blacklist check)
    if device_configs := DeviceProfileRegistry.get_configs(model=model, category=category):
        return tuple(_device_config_to_custom_config(dc) for dc in device_configs)
    return ()


def is_multi_channel_device(*, model: str, category: DataPointCategory) -> bool:
    """Return true, if device has multiple channels."""
    channels: list[int | None] = []
    for custom_config in get_custom_configs(model=model, category=category):
        channels.extend(custom_config.channels)
    return len(channels) > 1


def data_point_definition_exists(*, model: str) -> bool:
    """Check if device desc exits."""
    return len(get_custom_configs(model=model)) > 0


def get_required_parameters() -> tuple[Parameter, ...]:
    """Return all required parameters for custom data points."""
    required_parameters: list[Parameter] = []

    # Add default data points
    for params in DEFAULT_DATA_POINTS.values():
        required_parameters.extend(params)

    # Add parameters from profile configurations
    for profile_config in PROFILE_CONFIGS.values():
        group = profile_config.channel_group
        required_parameters.extend(group.repeating_fields.values())
        required_parameters.extend(group.visible_repeating_fields.values())
        for field_map in group.channel_fields.values():
            required_parameters.extend(field_map.values())
        for field_map in group.visible_channel_fields.values():
            required_parameters.extend(field_map.values())
        for params in profile_config.additional_data_points.values():
            required_parameters.extend(params)

    # Add required parameters from DeviceProfileRegistry extended configs
    for extended_config in DeviceProfileRegistry.get_all_extended_configs():
        required_parameters.extend(extended_config.required_parameters)

    return tuple(sorted(set(required_parameters)))
