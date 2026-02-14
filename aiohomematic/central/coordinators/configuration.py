# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Configuration coordinator for paramset-level device configuration.

This module provides the ConfigurationCoordinator, a high-level facade
for reading and writing device configuration (MASTER paramsets) without
requiring navigation of internal coordinator structures.

The coordinator combines paramset descriptions, device descriptions, and
client operations behind a clean, consumer-friendly interface.

Public API of this module is defined by __all__.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import inspect
import logging
from typing import Any, Final

from aiohomematic.const import CallSource, Flag, ParameterData, ParamsetKey
from aiohomematic.interfaces import (
    ClientProviderProtocol,
    DeviceDescriptionProviderProtocol,
    ParamsetDescriptionProviderProtocol,
)
from aiohomematic.interfaces.central import ConfigurationFacadeProtocol
from aiohomematic.parameter_tools import validate_paramset
from aiohomematic.support.address import get_device_address

_LOGGER: Final = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ConfigurableChannel:
    """A channel that has configurable paramsets."""

    address: str
    """Channel address (e.g. ``VCU3373841:1``)."""

    channel_type: str
    """Channel TYPE from the device description."""

    paramset_keys: tuple[ParamsetKey, ...]
    """Available paramset keys for this channel."""


@dataclass(frozen=True, slots=True)
class PutParamsetResult:
    """Result of a put_paramset operation."""

    success: bool
    """Whether the operation succeeded."""

    validated: bool
    """Whether validation was performed before writing."""

    validation_errors: Mapping[str, str]
    """Per-parameter validation error messages (empty on success)."""


class ConfigurationCoordinator(ConfigurationFacadeProtocol):
    """
    High-level facade for device configuration operations.

    Provides clean access to paramset descriptions, reading, and writing
    without exposing internal coordinator structure. Intended for consumption
    by configuration UIs, diagnostic tools, and third-party integrations.
    """

    __slots__ = (
        "_client_provider",
        "_device_description_provider",
        "_paramset_description_provider",
    )

    def __init__(
        self,
        *,
        client_provider: ClientProviderProtocol,
        device_description_provider: DeviceDescriptionProviderProtocol,
        paramset_description_provider: ParamsetDescriptionProviderProtocol,
    ) -> None:
        """Initialize the configuration coordinator."""
        self._client_provider: Final = client_provider
        self._device_description_provider: Final = device_description_provider
        self._paramset_description_provider: Final = paramset_description_provider

    def get_all_paramset_descriptions(
        self,
        *,
        interface_id: str,
        channel_address: str,
    ) -> Mapping[ParamsetKey, Mapping[str, ParameterData]]:
        """Return all paramset descriptions for a channel, keyed by paramset key."""
        return self._paramset_description_provider.get_channel_paramset_descriptions(
            interface_id=interface_id,
            channel_address=channel_address,
        )

    def get_configurable_channels(
        self,
        *,
        interface_id: str,
        device_address: str,
    ) -> tuple[ConfigurableChannel, ...]:
        """
        Return all channels of a device that have configurable paramsets.

        A channel is considered configurable when its device description
        lists at least one paramset key (typically MASTER and/or VALUES).

        Channels are filtered using the same rules as the CCU WebUI:
        - Channel FLAGS must have VISIBLE set
        - Channel FLAGS must not have INTERNAL set
        - WEEK_PROGRAM channels are excluded (handled by schedule cards)
        """
        device_with_channels = self._device_description_provider.get_device_with_channels(
            interface_id=interface_id,
            device_address=device_address,
        )
        channels: list[ConfigurableChannel] = []
        for address, description in sorted(device_with_channels.items()):
            # Skip the device-level entry (no colon in address)
            if get_device_address(address=address) == address and ":" not in address:
                continue

            channel_type = description.get("TYPE", "")

            # Skip channels not visible or internal (CCU-compatible FLAGS check)
            channel_flags: int = description.get("FLAGS") or 0
            if not (channel_flags & Flag.VISIBLE) or (channel_flags & Flag.INTERNAL):
                continue

            # Skip WEEK_PROGRAM channels (handled by schedule cards)
            if channel_type == "WEEK_PROGRAM":
                continue

            raw_paramsets = description.get("PARAMSETS", [])
            paramset_keys = tuple(ParamsetKey(ps) for ps in raw_paramsets if ps in {pk.value for pk in ParamsetKey})
            if paramset_keys:
                channels.append(
                    ConfigurableChannel(
                        address=address,
                        channel_type=channel_type,
                        paramset_keys=paramset_keys,
                    )
                )
        return tuple(channels)

    def get_parameter_data(
        self,
        *,
        interface_id: str,
        channel_address: str,
        paramset_key: ParamsetKey,
        parameter: str,
    ) -> ParameterData | None:
        """Return the parameter description for a single parameter."""
        return self._paramset_description_provider.get_parameter_data(
            interface_id=interface_id,
            channel_address=channel_address,
            paramset_key=paramset_key,
            parameter=parameter,
        )

    async def get_paramset(
        self,
        *,
        interface_id: str,
        channel_address: str,
        paramset_key: ParamsetKey,
    ) -> dict[str, Any]:
        """
        Read the current paramset values from the backend.

        Returns the live values for the given channel and paramset key.
        """
        client = self._client_provider.get_client(interface_id=interface_id)
        return await client.get_paramset(
            channel_address=channel_address,
            paramset_key=paramset_key,
            call_source=CallSource.MANUAL_OR_SCHEDULED,
        )

    def get_paramset_description(
        self,
        *,
        interface_id: str,
        channel_address: str,
        paramset_key: ParamsetKey,
    ) -> Mapping[str, ParameterData]:
        """
        Return the paramset description for a channel.

        This is the set of parameter definitions (type, min, max, default, etc.)
        for the given channel and paramset key.
        """
        all_descriptions = self._paramset_description_provider.get_channel_paramset_descriptions(
            interface_id=interface_id,
            channel_address=channel_address,
        )
        return all_descriptions.get(paramset_key, {})

    async def put_paramset(
        self,
        *,
        interface_id: str,
        channel_address: str,
        paramset_key: ParamsetKey,
        values: dict[str, Any],
        validate: bool = True,
    ) -> PutParamsetResult:
        """
        Write paramset values to the backend.

        When *validate* is ``True`` (the default), each value is checked against
        its parameter description before writing. On validation failure the
        write is skipped and the result contains the per-parameter error messages.
        """
        if validate:
            descriptions = self.get_paramset_description(
                interface_id=interface_id,
                channel_address=channel_address,
                paramset_key=paramset_key,
            )
            if failures := validate_paramset(descriptions=descriptions, values=values):
                return PutParamsetResult(
                    success=False,
                    validated=True,
                    validation_errors={param: result.reason for param, result in failures.items()},
                )

        client = self._client_provider.get_client(interface_id=interface_id)
        await client.put_paramset(
            channel_address=channel_address,
            paramset_key_or_link_address=paramset_key,
            values=values,
        )
        return PutParamsetResult(success=True, validated=validate, validation_errors={})


__all__ = tuple(
    sorted(
        name
        for name, obj in globals().items()
        if not name.startswith("_")
        and (name.isupper() or inspect.isfunction(obj) or inspect.isclass(obj))
        and getattr(obj, "__module__", __name__) == __name__
    )
)
