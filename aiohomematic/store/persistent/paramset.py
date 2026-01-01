# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Paramset description cache for persisting parameter metadata.

This module provides ParamsetDescriptionCache which persists paramset descriptions
per interface and channel, and offers helpers to query parameters, paramset keys
and related channel addresses.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
import logging
from typing import TYPE_CHECKING, Any, Final

from aiohomematic.const import ADDRESS_SEPARATOR, ParameterData, ParamsetKey
from aiohomematic.interfaces import ParamsetDescriptionProviderProtocol, ParamsetDescriptionWriterProtocol
from aiohomematic.interfaces.model import DeviceRemovalInfoProtocol
from aiohomematic.property_decorators import DelegatedProperty
from aiohomematic.store.persistent.base import BasePersistentCache
from aiohomematic.store.types import InterfaceParamsetMap
from aiohomematic.support import get_split_channel_address

if TYPE_CHECKING:
    from aiohomematic.interfaces import ConfigProviderProtocol
    from aiohomematic.store.storage import StorageProtocol

_LOGGER: Final = logging.getLogger(__name__)


class ParamsetDescriptionCache(
    BasePersistentCache, ParamsetDescriptionProviderProtocol, ParamsetDescriptionWriterProtocol
):
    """Cache for paramset descriptions."""

    __slots__ = ("_address_parameter_cache",)

    def __init__(
        self,
        *,
        storage: StorageProtocol,
        config_provider: ConfigProviderProtocol,
    ) -> None:
        """
        Initialize the paramset description cache.

        Args:
            storage: Storage instance for persistence.
            config_provider: Provider for configuration access.

        """
        # {(device_address, parameter), [channel_no]}
        self._address_parameter_cache: Final[dict[tuple[str, str], set[int | None]]] = {}
        super().__init__(
            storage=storage,
            config_provider=config_provider,
        )

    raw_paramset_descriptions: Final = DelegatedProperty[
        Mapping[str, Mapping[str, Mapping[ParamsetKey, Mapping[str, ParameterData]]]]
    ](path="_raw_paramset_descriptions")

    @property
    def _raw_paramset_descriptions(self) -> InterfaceParamsetMap:
        """Return the raw paramset descriptions (alias to _content)."""
        return self._content

    @property
    def size(self) -> int:
        """Return total number of paramset descriptions in cache."""
        return sum(
            len(channel_paramsets)
            for interface_paramsets in self._raw_paramset_descriptions.values()
            for channel_paramsets in interface_paramsets.values()
        )

    def add(
        self,
        *,
        interface_id: str,
        channel_address: str,
        paramset_key: ParamsetKey,
        paramset_description: dict[str, ParameterData],
    ) -> None:
        """Add paramset description to cache."""
        self._raw_paramset_descriptions[interface_id][channel_address][paramset_key] = paramset_description
        self._add_address_parameter(channel_address=channel_address, paramsets=[paramset_description])

    def get_channel_addresses_by_paramset_key(
        self, *, interface_id: str, device_address: str
    ) -> Mapping[ParamsetKey, list[str]]:
        """Get device channel addresses."""
        channel_addresses: dict[ParamsetKey, list[str]] = {}
        interface_paramset_descriptions = self._raw_paramset_descriptions[interface_id]
        for (
            channel_address,
            paramset_descriptions,
        ) in interface_paramset_descriptions.items():
            if channel_address.startswith(device_address):
                for p_key in paramset_descriptions:
                    if (paramset_key := ParamsetKey(p_key)) not in channel_addresses:
                        channel_addresses[paramset_key] = []
                    channel_addresses[paramset_key].append(channel_address)

        return channel_addresses

    def get_channel_paramset_descriptions(
        self, *, interface_id: str, channel_address: str
    ) -> Mapping[ParamsetKey, Mapping[str, ParameterData]]:
        """Get paramset descriptions for a channel from cache."""
        return self._raw_paramset_descriptions[interface_id].get(channel_address, {})

    def get_parameter_data(
        self, *, interface_id: str, channel_address: str, paramset_key: ParamsetKey, parameter: str
    ) -> ParameterData | None:
        """Get parameter_data from cache."""
        return self._raw_paramset_descriptions[interface_id][channel_address][paramset_key].get(parameter)

    def get_paramset_descriptions(
        self, *, interface_id: str, channel_address: str, paramset_key: ParamsetKey
    ) -> Mapping[str, ParameterData]:
        """Get paramset descriptions from cache."""
        return self._raw_paramset_descriptions[interface_id][channel_address][paramset_key]

    def get_paramset_keys(self, *, interface_id: str, channel_address: str) -> tuple[ParamsetKey, ...]:
        """Get paramset_keys from paramset descriptions cache."""
        return tuple(self._raw_paramset_descriptions[interface_id][channel_address])

    def has_interface_id(self, *, interface_id: str) -> bool:
        """Return if interface is in paramset_descriptions cache."""
        return interface_id in self._raw_paramset_descriptions

    def has_parameter(
        self, *, interface_id: str, channel_address: str, paramset_key: ParamsetKey, parameter: str
    ) -> bool:
        """Check if a parameter exists in the paramset description."""
        try:
            return parameter in self._raw_paramset_descriptions[interface_id][channel_address][paramset_key]
        except KeyError:
            return False

    def is_in_multiple_channels(self, *, channel_address: str, parameter: str) -> bool:
        """Check if parameter is in multiple channels per device."""
        if ADDRESS_SEPARATOR not in channel_address:
            return False
        if channels := self._address_parameter_cache.get(
            (get_split_channel_address(channel_address=channel_address)[0], parameter)
        ):
            return len(channels) > 1
        return False

    def remove_device(self, *, device: DeviceRemovalInfoProtocol) -> None:
        """Remove device paramset descriptions from cache."""
        if interface := self._raw_paramset_descriptions.get(device.interface_id):
            for channel_address in device.channels:
                if channel_address in interface:
                    del self._raw_paramset_descriptions[device.interface_id][channel_address]

    def _add_address_parameter(self, *, channel_address: str, paramsets: list[dict[str, Any]]) -> None:
        """Add address parameter to cache."""
        device_address, channel_no = get_split_channel_address(channel_address=channel_address)
        cache = self._address_parameter_cache
        for paramset in paramsets:
            if not paramset:
                continue
            for parameter in paramset:
                cache.setdefault((device_address, parameter), set()).add(channel_no)

    def _create_empty_content(self) -> dict[str, Any]:
        """Create empty content structure."""
        return defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))

    def _init_address_parameter_list(self) -> None:
        """
        Initialize a device_address/parameter list.

        Used to identify, if a parameter name exists is in multiple channels.
        """
        for channel_paramsets in self._raw_paramset_descriptions.values():
            for channel_address, paramsets in channel_paramsets.items():
                self._add_address_parameter(channel_address=channel_address, paramsets=list(paramsets.values()))

    def _process_loaded_content(self, *, data: dict[str, Any]) -> None:
        """Rebuild indexes from loaded data."""
        self._address_parameter_cache.clear()
        self._init_address_parameter_list()
