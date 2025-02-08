"""Module for the persistent caches."""

from __future__ import annotations

from abc import ABC
import asyncio
from collections import defaultdict
from collections.abc import Mapping
from datetime import datetime
import json
import logging
import os
from typing import Any, Final

import orjson
from slugify import slugify

from hahomematic import central as hmcu
from hahomematic.const import (
    ADDRESS_SEPARATOR,
    CACHE_PATH,
    FILE_DEVICES,
    FILE_PARAMSETS,
    INIT_DATETIME,
    UTF_8,
    DataOperationResult,
    DeviceDescription,
    ParameterData,
    ParamsetKey,
)
from hahomematic.model.device import Device
from hahomematic.support import (
    check_or_create_directory,
    delete_file,
    get_device_address,
    get_split_channel_address,
    hash_sha256,
    regular_to_default_dict_hook,
)

_LOGGER: Final = logging.getLogger(__name__)


class BasePersistentCache(ABC):
    """Cache for files."""

    _file_postfix: str

    def __init__(
        self,
        central: hmcu.CentralUnit,
        persistent_cache: dict[str, Any],
    ) -> None:
        """Initialize the base class of the persistent cache."""
        self._save_load_semaphore: Final = asyncio.Semaphore()
        self._central: Final = central
        self._cache_dir: Final = _get_cache_path(storage_folder=central.config.storage_folder)
        self._filename: Final = _get_filename(central_name=central.name, file_name=self._file_postfix)
        self._persistent_cache: Final = persistent_cache
        self.last_save_triggered: datetime = INIT_DATETIME
        self.last_hash_saved = hash_sha256(value=persistent_cache)

    @property
    def cache_hash(self) -> str:
        """Return the hash of the cache."""
        return hash_sha256(value=self._persistent_cache)

    @property
    def data_changed(self) -> bool:
        """Return if the data has changed."""
        return self.cache_hash != self.last_hash_saved

    @property
    def _file_path(self) -> str:
        """Return the full file path."""
        return os.path.join(self._cache_dir, self._filename)

    async def save(self) -> DataOperationResult:
        """Save current data to disk."""
        if not self._should_save:
            return DataOperationResult.NO_SAVE

        def _perform_save() -> DataOperationResult:
            try:
                with open(file=self._file_path, mode="wb") as file_pointer:
                    file_pointer.write(
                        orjson.dumps(
                            self._persistent_cache,
                            option=orjson.OPT_NON_STR_KEYS,
                        )
                    )
                self.last_hash_saved = self.cache_hash
            except json.JSONDecodeError:
                return DataOperationResult.SAVE_FAIL
            return DataOperationResult.SAVE_SUCCESS

        async with self._save_load_semaphore:
            return await self._central.looper.async_add_executor_job(
                _perform_save, name=f"save-persistent-cache-{self._filename}"
            )

    @property
    def _should_save(self) -> bool:
        """Determine if save operation should proceed."""
        self.last_save_triggered = datetime.now()
        return (
            check_or_create_directory(self._cache_dir)
            and self._central.config.use_caches
            and self.cache_hash != self.last_hash_saved
        )

    async def load(self) -> DataOperationResult:
        """Load data from disk into the dictionary."""
        if not check_or_create_directory(self._cache_dir) or not os.path.exists(self._file_path):
            return DataOperationResult.NO_LOAD

        def _perform_load() -> DataOperationResult:
            with open(file=self._file_path, encoding=UTF_8) as file_pointer:
                try:
                    data = json.loads(file_pointer.read(), object_hook=regular_to_default_dict_hook)
                    if (converted_hash := hash_sha256(value=data)) == self.last_hash_saved:
                        return DataOperationResult.NO_LOAD
                    self._persistent_cache.clear()
                    self._persistent_cache.update(data)
                    self.last_hash_saved = converted_hash
                except json.JSONDecodeError:
                    return DataOperationResult.LOAD_FAIL
            return DataOperationResult.LOAD_SUCCESS

        async with self._save_load_semaphore:
            return await self._central.looper.async_add_executor_job(
                _perform_load, name=f"load-persistent-cache-{self._filename}"
            )

    async def clear(self) -> None:
        """Remove stored file from disk."""

        def _perform_clear() -> None:
            delete_file(folder=self._cache_dir, file_name=self._filename)
            self._persistent_cache.clear()

        async with self._save_load_semaphore:
            await self._central.looper.async_add_executor_job(_perform_clear, name="clear-persistent-cache")


class DeviceDescriptionCache(BasePersistentCache):
    """Cache for device/channel names."""

    _file_postfix = FILE_DEVICES

    def __init__(self, central: hmcu.CentralUnit) -> None:
        """Initialize the device description cache."""
        # {interface_id, [device_descriptions]}
        self._raw_device_descriptions: Final[dict[str, list[DeviceDescription]]] = defaultdict(list)
        super().__init__(
            central=central,
            persistent_cache=self._raw_device_descriptions,
        )
        # {interface_id, {device_address, [channel_address]}}
        self._addresses: Final[dict[str, dict[str, set[str]]]] = defaultdict(lambda: defaultdict(set))
        # {interface_id, {address, device_descriptions}}
        self._device_descriptions: Final[dict[str, dict[str, DeviceDescription]]] = defaultdict(dict)

    def add_device(self, interface_id: str, device_description: DeviceDescription) -> None:
        """Add a device to the cache."""
        self._remove_device(
            interface_id=interface_id,
            addresses_to_remove=[device_description["ADDRESS"]],
        )
        self._raw_device_descriptions[interface_id].append(device_description)
        self._process_device_description(interface_id=interface_id, device_description=device_description)

    def get_raw_device_descriptions(self, interface_id: str) -> list[DeviceDescription]:
        """Retrieve raw device descriptions from the cache."""
        return self._raw_device_descriptions[interface_id]

    def remove_device(self, device: Device) -> None:
        """Remove device from cache."""
        self._remove_device(
            interface_id=device.interface_id,
            addresses_to_remove=[device.address, *device.channels.keys()],
        )

    def _remove_device(self, interface_id: str, addresses_to_remove: list[str]) -> None:
        """Remove a device from the cache."""
        self._raw_device_descriptions[interface_id] = [
            device
            for device in self._raw_device_descriptions[interface_id]
            if device["ADDRESS"] not in addresses_to_remove
        ]
        for address in addresses_to_remove:
            try:
                if ADDRESS_SEPARATOR not in address and self._addresses[interface_id].get(address):
                    del self._addresses[interface_id][address]
                if self._device_descriptions[interface_id].get(address):
                    del self._device_descriptions[interface_id][address]
            except KeyError:
                _LOGGER.warning("REMOVE_DEVICE failed: Unable to delete: %s", address)

    def get_addresses(self, interface_id: str) -> tuple[str, ...]:
        """Return the addresses by interface."""
        return tuple(self._addresses[interface_id].keys())

    def get_device_descriptions(self, interface_id: str) -> Mapping[str, DeviceDescription]:
        """Return the devices by interface."""
        return self._device_descriptions[interface_id]

    def find_device_description(self, interface_id: str, device_address: str) -> DeviceDescription | None:
        """Return the device description by interface and device_address."""
        return self._device_descriptions[interface_id].get(device_address)

    def get_device_description(self, interface_id: str, address: str) -> DeviceDescription:
        """Return the device description by interface and device_address."""
        return self._device_descriptions[interface_id][address]

    def get_device_with_channels(self, interface_id: str, device_address: str) -> Mapping[str, DeviceDescription]:
        """Return the device dict by interface and device_address."""
        device_descriptions: dict[str, DeviceDescription] = {
            device_address: self.get_device_description(interface_id=interface_id, address=device_address)
        }
        children = device_descriptions[device_address]["CHILDREN"]
        for channel_address in children:
            device_descriptions[channel_address] = self.get_device_description(
                interface_id=interface_id, address=channel_address
            )
        return device_descriptions

    def get_model(self, device_address: str) -> str | None:
        """Return the device type."""
        for data in self._device_descriptions.values():
            if items := data.get(device_address):
                return items["TYPE"]
        return None

    def _convert_device_descriptions(self, interface_id: str, device_descriptions: list[DeviceDescription]) -> None:
        """Convert provided list of device descriptions."""
        for device_description in device_descriptions:
            self._process_device_description(interface_id=interface_id, device_description=device_description)

    def _process_device_description(self, interface_id: str, device_description: DeviceDescription) -> None:
        """Convert provided dict of device descriptions."""
        address = device_description["ADDRESS"]
        device_address = get_device_address(address)
        self._device_descriptions[interface_id][address] = device_description

        if device_address not in self._addresses[interface_id][device_address]:
            self._addresses[interface_id][device_address].add(device_address)
        self._addresses[interface_id][device_address].add(address)

    async def load(self) -> DataOperationResult:
        """Load device data from disk into _device_description_cache."""
        if not self._central.config.use_caches:
            _LOGGER.debug("load: not caching paramset descriptions for %s", self._central.name)
            return DataOperationResult.NO_LOAD
        if (result := await super().load()) == DataOperationResult.LOAD_SUCCESS:
            for (
                interface_id,
                device_descriptions,
            ) in self._raw_device_descriptions.items():
                self._convert_device_descriptions(interface_id, device_descriptions)
        return result


class ParamsetDescriptionCache(BasePersistentCache):
    """Cache for paramset descriptions."""

    _file_postfix = FILE_PARAMSETS

    def __init__(self, central: hmcu.CentralUnit) -> None:
        """Init the paramset description cache."""
        # {interface_id, {channel_address, paramsets}}
        self._raw_paramset_descriptions: Final[dict[str, dict[str, dict[ParamsetKey, dict[str, ParameterData]]]]] = (
            defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
        )
        super().__init__(
            central=central,
            persistent_cache=self._raw_paramset_descriptions,
        )

        # {(device_address, parameter), [channel_no]}
        self._address_parameter_cache: Final[dict[tuple[str, str], set[int | None]]] = {}

    @property
    def raw_paramset_descriptions(
        self,
    ) -> Mapping[str, Mapping[str, Mapping[ParamsetKey, Mapping[str, ParameterData]]]]:
        """Return the paramset descriptions."""
        return self._raw_paramset_descriptions

    def add(
        self,
        interface_id: str,
        channel_address: str,
        paramset_key: ParamsetKey,
        paramset_description: dict[str, ParameterData],
    ) -> None:
        """Add paramset description to cache."""
        self._raw_paramset_descriptions[interface_id][channel_address][paramset_key] = paramset_description
        self._add_address_parameter(channel_address=channel_address, paramsets=[paramset_description])

    def remove_device(self, device: Device) -> None:
        """Remove device paramset descriptions from cache."""
        if interface := self._raw_paramset_descriptions.get(device.interface_id):
            for channel_address in device.channels:
                if channel_address in interface:
                    del self._raw_paramset_descriptions[device.interface_id][channel_address]

    def has_interface_id(self, interface_id: str) -> bool:
        """Return if interface is in paramset_descriptions cache."""
        return interface_id in self._raw_paramset_descriptions

    def get_paramset_keys(self, interface_id: str, channel_address: str) -> tuple[ParamsetKey, ...]:
        """Get paramset_keys from paramset descriptions cache."""
        return tuple(self._raw_paramset_descriptions[interface_id][channel_address])

    def get_channel_paramset_descriptions(
        self, interface_id: str, channel_address: str
    ) -> Mapping[ParamsetKey, Mapping[str, ParameterData]]:
        """Get paramset descriptions for a channelfrom cache."""
        return self._raw_paramset_descriptions[interface_id].get(channel_address, {})

    def get_paramset_descriptions(
        self, interface_id: str, channel_address: str, paramset_key: ParamsetKey
    ) -> Mapping[str, ParameterData]:
        """Get paramset descriptions from cache."""
        return self._raw_paramset_descriptions[interface_id][channel_address][paramset_key]

    def get_parameter_data(
        self, interface_id: str, channel_address: str, paramset_key: ParamsetKey, parameter: str
    ) -> ParameterData | None:
        """Get parameter_data  from cache."""
        return self._raw_paramset_descriptions[interface_id][channel_address][paramset_key].get(parameter)

    def is_in_multiple_channels(self, channel_address: str, parameter: str) -> bool:
        """Check if parameter is in multiple channels per device."""
        if ADDRESS_SEPARATOR not in channel_address:
            return False
        if channels := self._address_parameter_cache.get((get_device_address(channel_address), parameter)):
            return len(channels) > 1
        return False

    def get_channel_addresses_by_paramset_key(
        self, interface_id: str, device_address: str
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

    def _init_address_parameter_list(self) -> None:
        """
        Initialize a device_address/parameter list.

        Used to identify, if a parameter name exists is in multiple channels.
        """
        for channel_paramsets in self._raw_paramset_descriptions.values():
            for channel_address, paramsets in channel_paramsets.items():
                self._add_address_parameter(channel_address=channel_address, paramsets=list(paramsets.values()))

    def _add_address_parameter(self, channel_address: str, paramsets: list[dict[str, Any]]) -> None:
        """Add address parameter to cache."""
        device_address, channel_no = get_split_channel_address(channel_address)
        for paramset in paramsets:
            if not paramset:
                continue
            for parameter in paramset:
                if (device_address, parameter) not in self._address_parameter_cache:
                    self._address_parameter_cache[(device_address, parameter)] = set()
                self._address_parameter_cache[(device_address, parameter)].add(channel_no)

    async def load(self) -> DataOperationResult:
        """Load paramset descriptions from disk into paramset cache."""
        if not self._central.config.use_caches:
            _LOGGER.debug("load: not caching device descriptions for %s", self._central.name)
            return DataOperationResult.NO_LOAD
        if (result := await super().load()) == DataOperationResult.LOAD_SUCCESS:
            self._init_address_parameter_list()
        return result

    async def save(self) -> DataOperationResult:
        """Save current paramset descriptions to disk."""
        return await super().save()


def _get_cache_path(storage_folder: str) -> str:
    """Return the cache path."""
    return f"{storage_folder}/{CACHE_PATH}"


def _get_filename(central_name: str, file_name: str) -> str:
    """Return the cache filename."""
    return f"{slugify(central_name)}_{file_name}"


def cleanup_cache_dirs(central_name: str, storage_folder: str) -> None:
    """Clean up the used cached directories."""
    cache_dir = _get_cache_path(storage_folder=storage_folder)
    for file_to_delete in (FILE_DEVICES, FILE_PARAMSETS):
        delete_file(folder=cache_dir, file_name=_get_filename(central_name=central_name, file_name=file_to_delete))
