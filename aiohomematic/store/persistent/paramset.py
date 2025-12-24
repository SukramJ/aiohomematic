# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
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
from typing import Any, Final

from aiohomematic.const import (
    ADDRESS_SEPARATOR,
    FILE_PARAMSETS,
    SUB_DIRECTORY_CACHE,
    DataOperationResult,
    ParameterData,
    ParamsetKey,
)
from aiohomematic.interfaces.central import CentralInfoProtocol, ConfigProviderProtocol, DeviceProviderProtocol
from aiohomematic.interfaces.client import ParamsetDescriptionWriterProtocol
from aiohomematic.interfaces.model import DeviceRemovalInfoProtocol
from aiohomematic.interfaces.operations import ParamsetDescriptionProviderProtocol, TaskSchedulerProtocol
from aiohomematic.property_decorators import DelegatedProperty
from aiohomematic.store.persistent.base import BasePersistentFile
from aiohomematic.store.types import InterfaceParamsetMap
from aiohomematic.support import get_split_channel_address

_LOGGER: Final = logging.getLogger(__name__)


class ParamsetDescriptionCache(
    BasePersistentFile, ParamsetDescriptionProviderProtocol, ParamsetDescriptionWriterProtocol
):
    """Cache for paramset descriptions."""

    __slots__ = (
        "_address_parameter_cache",
        "_raw_paramset_descriptions",
    )

    _file_postfix = FILE_PARAMSETS
    _sub_directory = SUB_DIRECTORY_CACHE

    def __init__(
        self,
        *,
        config_provider: ConfigProviderProtocol,
        task_scheduler: TaskSchedulerProtocol,
        central_info: CentralInfoProtocol,
        device_provider: DeviceProviderProtocol,
    ) -> None:
        """Initialize the paramset description cache."""
        # {interface_id, {channel_address, paramsets}}
        self._raw_paramset_descriptions: Final[InterfaceParamsetMap] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(dict))
        )
        super().__init__(
            config_provider=config_provider,
            task_scheduler=task_scheduler,
            central_info=central_info,
            device_provider=device_provider,
            persistent_content=self._raw_paramset_descriptions,
        )

        # {(device_address, parameter), [channel_no]}
        self._address_parameter_cache: Final[dict[tuple[str, str], set[int | None]]] = {}

    raw_paramset_descriptions: Final = DelegatedProperty[
        Mapping[str, Mapping[str, Mapping[ParamsetKey, Mapping[str, ParameterData]]]]
    ](path="_raw_paramset_descriptions")

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

    async def load(self, *, file_path: str | None = None) -> DataOperationResult:
        """Load paramset descriptions from disk into paramset cache."""
        if not self._config_provider.config.use_caches:
            _LOGGER.debug("load: not caching device descriptions for %s", self._central_info.name)
            return DataOperationResult.NO_LOAD
        if (result := await super().load(file_path=file_path)) == DataOperationResult.LOAD_SUCCESS:
            self._init_address_parameter_list()
        return result

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

    def _init_address_parameter_list(self) -> None:
        """
        Initialize a device_address/parameter list.

        Used to identify, if a parameter name exists is in multiple channels.
        """
        for channel_paramsets in self._raw_paramset_descriptions.values():
            for channel_address, paramsets in channel_paramsets.items():
                self._add_address_parameter(channel_address=channel_address, paramsets=list(paramsets.values()))
