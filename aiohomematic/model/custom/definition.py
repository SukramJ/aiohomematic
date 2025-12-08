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
import logging
from typing import Final, cast

from aiohomematic import i18n
from aiohomematic.const import DataPointCategory, DeviceProfile, Parameter
from aiohomematic.exceptions import AioHomematicException
from aiohomematic.interfaces.model import ChannelProtocol, DeviceProtocol
from aiohomematic.model.custom.profile import (
    DEFAULT_DATA_POINTS,
    PROFILE_CONFIGS,
    ProfileConfig,
    RebasedChannelGroup,
    get_profile_config,
    rebase_channel_group,
)
from aiohomematic.model.custom.registry import DeviceConfig, DeviceProfileRegistry
from aiohomematic.model.support import generate_unique_id
from aiohomematic.support import extract_exc_args

_LOGGER: Final = logging.getLogger(__name__)


def create_custom_data_point(
    *,
    channel: ChannelProtocol,
    device_config: DeviceConfig,
) -> None:
    """
    Create a custom data point for a channel.

    This is the main entry point for creating custom data points. It handles
    channel group setup, determines the relevant channels, and creates the
    actual data point instance.

    Args:
        channel: The channel to create the data point for.
        device_config: The device configuration from DeviceProfileRegistry.

    """
    device_profile = device_config.profile_type
    profile_config = get_profile_config(device_profile)

    # Set up channel groups on the device
    _add_channel_groups_to_device(
        device=channel.device,
        profile_config=profile_config,
        device_config=device_config,
    )

    # Get the group number for this channel
    group_no = channel.device.get_channel_group_no(channel_no=channel.no)

    # Determine which channels are relevant for this data point
    relevant = _get_relevant_channels(
        profile_config=profile_config,
        device_config=device_config,
    )

    if channel.no not in relevant:
        return

    # Create the rebased channel group
    channel_group = rebase_channel_group(profile_config=profile_config, group_no=group_no)

    # Get rebased additional data points
    custom_data_point_def = _rebase_additional_data_points(
        profile_config=profile_config,
        group_no=group_no,
    )

    # Rebase the device config channels
    rebased_device_config = _rebase_device_config_channels(
        profile_config=profile_config,
        device_config=device_config,
    )

    # Create the data point instance
    _instantiate_custom_data_point(
        channel=channel,
        device_config=rebased_device_config,
        device_profile=device_profile,
        channel_group=channel_group,
        custom_data_point_def=custom_data_point_def,
        group_no=group_no,
    )


def _instantiate_custom_data_point(
    *,
    channel: ChannelProtocol,
    device_config: DeviceConfig,
    device_profile: DeviceProfile,
    channel_group: RebasedChannelGroup,
    custom_data_point_def: Mapping[int | tuple[int, ...], tuple[Parameter, ...]],
    group_no: int | None,
) -> None:
    """Instantiate and add a custom data point to the channel."""

    unique_id = generate_unique_id(config_provider=channel.device.config_provider, address=channel.address)

    try:
        dp = device_config.data_point_class(
            channel=channel,
            unique_id=unique_id,
            device_profile=device_profile,
            channel_group=channel_group,
            custom_data_point_def=custom_data_point_def,
            group_no=group_no,
            device_config=device_config,
        )
        if dp.has_data_points:
            channel.add_data_point(data_point=dp)
    except Exception as exc:
        raise AioHomematicException(
            i18n.tr(
                "exception.model.custom.definition.create_custom_data_point.failed",
                reason=extract_exc_args(exc=exc),
            )
        ) from exc


def _add_channel_groups_to_device(
    *,
    device: DeviceProtocol,
    profile_config: ProfileConfig,
    device_config: DeviceConfig,
) -> None:
    """Add channel group mappings to the device."""
    cg = profile_config.channel_group

    if (primary_channel := cg.primary_channel) is None:
        return

    for conf_channel in device_config.channels:
        if conf_channel is None:
            continue

        group_no = conf_channel + primary_channel
        device.add_channel_to_group(channel_no=group_no, group_no=group_no)

        if cg.state_channel_offset is not None:
            device.add_channel_to_group(channel_no=conf_channel + cg.state_channel_offset, group_no=group_no)

        for sec_channel in cg.secondary_channels:
            device.add_channel_to_group(channel_no=conf_channel + sec_channel, group_no=group_no)


def _get_relevant_channels(
    *,
    profile_config: ProfileConfig,
    device_config: DeviceConfig,
) -> set[int | None]:
    """Return the set of channels that are relevant for this data point."""

    cg = profile_config.channel_group
    primary_channel = cg.primary_channel

    # Collect all definition channels (primary + secondary)
    def_channels: list[int | None] = [primary_channel]
    def_channels.extend(cg.secondary_channels)

    # Calculate relevant channels by combining definition and config channels
    relevant: set[int | None] = set()
    for def_ch in def_channels:
        for conf_ch in device_config.channels:
            if def_ch is not None and conf_ch is not None:
                relevant.add(def_ch + conf_ch)
            else:
                relevant.add(None)

    return relevant


def _rebase_device_config_channels(
    *,
    profile_config: ProfileConfig,
    device_config: DeviceConfig,
) -> DeviceConfig:
    """Rebase device config channels with the primary channel offset."""
    if (primary_channel := profile_config.channel_group.primary_channel) is None:
        return device_config

    rebased_channels = tuple(ch + primary_channel for ch in device_config.channels if ch is not None)

    return DeviceConfig(
        data_point_class=device_config.data_point_class,
        profile_type=device_config.profile_type,
        channels=rebased_channels if rebased_channels else device_config.channels,
        extended=device_config.extended,
        schedule_channel_no=device_config.schedule_channel_no,
    )


def _rebase_additional_data_points(
    *,
    profile_config: ProfileConfig,
    group_no: int | None,
) -> Mapping[int | tuple[int, ...], tuple[Parameter, ...]]:
    """Rebase additional data points with the group offset."""
    additional_dps = profile_config.additional_data_points
    if not group_no:
        # Cast is safe: Mapping[int, T] is a subtype of Mapping[int | tuple[int, ...], T]
        return cast(Mapping[int | tuple[int, ...], tuple[Parameter, ...]], additional_dps)

    new_dps: dict[int | tuple[int, ...], tuple[Parameter, ...]] = {}
    for channel_no, params in additional_dps.items():
        new_dps[channel_no + group_no] = params

    return new_dps


# =============================================================================
# Public API functions
# =============================================================================


def create_custom_data_points(*, channel: ChannelProtocol) -> None:
    """
    Create custom data points for a channel.

    Queries the DeviceProfileRegistry for configurations matching the device model
    and creates custom data points for each configuration.

    Args:
        channel: The channel to create data points for.

    """
    device_configs = DeviceProfileRegistry.get_configs(model=channel.device.model)
    for device_config in device_configs:
        create_custom_data_point(channel=channel, device_config=device_config)


def data_point_definition_exists(*, model: str) -> bool:
    """Check if a device definition exists for the model."""
    return len(DeviceProfileRegistry.get_configs(model=model)) > 0


def get_default_data_points() -> Mapping[int | tuple[int, ...], tuple[Parameter, ...]]:
    """Return the default data points configuration."""
    return DEFAULT_DATA_POINTS


def get_include_default_data_points(*, device_profile: DeviceProfile) -> bool:
    """Return if default data points should be included for this profile."""
    return get_profile_config(device_profile).include_default_data_points


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


def is_multi_channel_device(*, model: str, category: DataPointCategory) -> bool:
    """Return true if device has multiple channels for the given category."""
    device_configs = DeviceProfileRegistry.get_configs(model=model, category=category)
    channels: list[int | None] = []
    for config in device_configs:
        channels.extend(config.channels)
    return len(channels) > 1
