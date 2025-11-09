# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Persistent content used to persist Homematic metadata between runs.

This module provides on-disk store that complement the short‑lived, in‑memory
store from aiohomematic.store.dynamic. The goal is to minimize expensive data
retrieval from the backend by storing stable metadata such as device and
paramset descriptions in JSON files inside a dedicated cache directory.

Overview
- BasePersistentFile: Abstract base for file‑backed content. It encapsulates
  file path resolution, change detection via hashing, and thread‑safe save/load
  operations delegated to the CentralUnit looper.
- DeviceDescriptionCache: Persists device descriptions per interface, including
  the mapping of device/channels and model metadata.
- ParamsetDescriptionCache: Persists paramset descriptions per interface and
  channel, and offers helpers to query parameters, paramset keys and related
  channel addresses.
- SessionRecorder: Persists session recorder data

Key behaviors
- Saves only if store are enabled (CentralConfig.use_caches) and content has
  changed (hash comparison), keeping I/O minimal and predictable.
- Uses orjson for fast binary writes and json for reads with a custom
  object_hook to rebuild nested defaultdict structures.
- Save/load/clear operations are synchronized via a semaphore and executed via
  the CentralUnit looper to avoid blocking the event loop.

Helper functions are provided to build content paths and file names and to
optionally clean up stale content directories.
"""

from __future__ import annotations

from abc import ABC
import ast
import asyncio
from collections import defaultdict
from collections.abc import Mapping
from datetime import UTC, datetime
import json
import logging
import os
from typing import Any, Final, Self
import zipfile

import orjson
from slugify import slugify

from aiohomematic import central as hmcu, i18n
from aiohomematic.async_support import loop_check
from aiohomematic.const import (
    ADDRESS_SEPARATOR,
    FILE_DEVICES,
    FILE_NAME_TS_PATTERN,
    FILE_PARAMSETS,
    FILE_SESSION_RECORDER,
    INIT_DATETIME,
    SUB_DIRECTORY_CACHE,
    SUB_DIRECTORY_SESSION,
    UTF_8,
    DataOperationResult,
    DeviceDescription,
    ParameterData,
    ParamsetKey,
    RPCType,
)
from aiohomematic.model.device import Device
from aiohomematic.support import (
    check_or_create_directory,
    create_random_device_addresses,
    delete_file,
    extract_exc_args,
    get_device_address,
    get_split_channel_address,
    hash_sha256,
    regular_to_default_dict_hook,
)

_LOGGER: Final = logging.getLogger(__name__)


class BasePersistentFile(ABC):
    """Cache for files."""

    __slots__ = (
        "_central",
        "_directory",
        "_file_postfix",
        "_persistent_content",
        "_save_load_semaphore",
        "_sub_directory",
        "_use_ts_in_file_names",
        "last_hash_saved",
        "last_save_triggered",
    )

    _file_postfix: str
    _sub_directory: str

    def __init__(
        self,
        *,
        central: hmcu.CentralUnit,
        persistent_content: dict[str, Any],
    ) -> None:
        """Initialize the base class of the persistent content."""
        self._save_load_semaphore: Final = asyncio.Semaphore()
        self._central: Final = central
        self._persistent_content: Final = persistent_content
        self._directory: Final = _get_file_path(
            storage_directory=central.config.storage_directory, sub_directory=self._sub_directory
        )
        self.last_save_triggered: datetime = INIT_DATETIME
        self.last_hash_saved = hash_sha256(value=persistent_content)

    @property
    def _should_save(self) -> bool:
        """Determine if save operation should proceed."""
        self.last_save_triggered = datetime.now()
        return (
            check_or_create_directory(directory=self._directory)
            and self._central.config.use_caches
            and self.content_hash != self.last_hash_saved
        )

    @property
    def content_hash(self) -> str:
        """Return the hash of the content."""
        return hash_sha256(value=self._persistent_content)

    @property
    def data_changed(self) -> bool:
        """Return if the data has changed."""
        return self.content_hash != self.last_hash_saved

    async def clear(self) -> None:
        """Remove stored file from disk."""

        def _perform_clear() -> None:
            delete_file(directory=self._directory, file_name=f"{self._central.name}*.json".lower())
            self._persistent_content.clear()

        async with self._save_load_semaphore:
            await self._central.looper.async_add_executor_job(_perform_clear, name="clear-persistent-content")

    async def load(self, *, file_path: str | None = None) -> DataOperationResult:
        """
        Load data from disk into the dictionary.

        Supports plain JSON files and ZIP archives containing a JSON file.
        When a ZIP archive is provided, the first JSON member inside the archive
        will be loaded.
        """
        if not file_path and not check_or_create_directory(directory=self._directory):
            return DataOperationResult.NO_LOAD

        if (file_path := file_path or self._get_file_path()) and not os.path.exists(file_path):
            return DataOperationResult.NO_LOAD

        def _perform_load() -> DataOperationResult:
            try:
                if zipfile.is_zipfile(file_path):
                    with zipfile.ZipFile(file_path, mode="r") as zf:
                        # Prefer json files; pick the first .json entry if available
                        if not (json_members := [n for n in zf.namelist() if n.lower().endswith(".json")]):
                            return DataOperationResult.LOAD_FAIL
                        raw = zf.read(json_members[0]).decode(UTF_8)
                        data = json.loads(raw, object_hook=regular_to_default_dict_hook)
                else:
                    with open(file=file_path, encoding=UTF_8) as file_pointer:
                        data = json.loads(file_pointer.read(), object_hook=regular_to_default_dict_hook)

                if (converted_hash := hash_sha256(value=data)) == self.last_hash_saved:
                    return DataOperationResult.NO_LOAD
                self._persistent_content.clear()
                self._persistent_content.update(data)
                self.last_hash_saved = converted_hash
            except (json.JSONDecodeError, zipfile.BadZipFile, UnicodeDecodeError, OSError):
                return DataOperationResult.LOAD_FAIL
            return DataOperationResult.LOAD_SUCCESS

        async with self._save_load_semaphore:
            return await self._central.looper.async_add_executor_job(
                _perform_load, name=f"load-persistent-content-{self._get_file_name()}"
            )

    async def save(self, *, randomize_output: bool = False, use_ts_in_file_name: bool = False) -> DataOperationResult:
        """Save current data to disk."""
        if not self._should_save:
            return DataOperationResult.NO_SAVE

        if not check_or_create_directory(directory=self._directory):
            return DataOperationResult.NO_SAVE

        def _perform_save() -> DataOperationResult:
            try:
                with open(
                    file=self._get_file_path(use_ts_in_file_name=use_ts_in_file_name),
                    mode="wb",
                ) as file_pointer:
                    file_pointer.write(
                        self._manipulate_content(
                            content=orjson.dumps(
                                self._persistent_content,
                                option=orjson.OPT_NON_STR_KEYS,
                            ),
                            randomize_output=randomize_output,
                        )
                    )
                self.last_hash_saved = self.content_hash
            except json.JSONDecodeError:
                return DataOperationResult.SAVE_FAIL
            return DataOperationResult.SAVE_SUCCESS

        async with self._save_load_semaphore:
            return await self._central.looper.async_add_executor_job(
                _perform_save, name=f"save-persistent-content-{self._get_file_name()}"
            )

    def _get_file_name(
        self,
        *,
        use_ts_in_file_name: bool = False,
    ) -> str:
        """Return the file name."""
        return _get_file_name(
            central_name=self._central.name,
            file_name=self._file_postfix,
            ts=datetime.now() if use_ts_in_file_name else None,
        )

    def _get_file_path(
        self,
        *,
        use_ts_in_file_name: bool = False,
    ) -> str:
        """Return the full file path."""
        return os.path.join(self._directory, self._get_file_name(use_ts_in_file_name=use_ts_in_file_name))

    def _manipulate_content(self, *, content: bytes, randomize_output: bool = False) -> bytes:
        """Manipulate the content of the file. Optionally randomize addresses."""
        if not randomize_output:
            return content

        addresses = [device.address for device in self._central.devices]
        text = content.decode(encoding=UTF_8)
        for device_address, rnd_address in create_random_device_addresses(addresses=addresses).items():
            text = text.replace(device_address, rnd_address)
        return text.encode(encoding=UTF_8)


class DeviceDescriptionCache(BasePersistentFile):
    """Cache for device/channel names."""

    __slots__ = (
        "_addresses",
        "_device_descriptions",
        "_raw_device_descriptions",
    )

    _file_postfix = FILE_DEVICES
    _sub_directory = SUB_DIRECTORY_CACHE

    def __init__(self, *, central: hmcu.CentralUnit) -> None:
        """Initialize the device description cache."""
        # {interface_id, [device_descriptions]}
        self._raw_device_descriptions: Final[dict[str, list[DeviceDescription]]] = defaultdict(list)
        super().__init__(
            central=central,
            persistent_content=self._raw_device_descriptions,
        )
        # {interface_id, {device_address, [channel_address]}}
        self._addresses: Final[dict[str, dict[str, set[str]]]] = defaultdict(lambda: defaultdict(set))
        # {interface_id, {address, device_descriptions}}
        self._device_descriptions: Final[dict[str, dict[str, DeviceDescription]]] = defaultdict(dict)

    def add_device(self, *, interface_id: str, device_description: DeviceDescription) -> None:
        """Add a device to the cache."""
        # Fast-path: If the address is not yet known, skip costly removal operations.
        if (address := device_description["ADDRESS"]) not in self._device_descriptions[interface_id]:
            self._raw_device_descriptions[interface_id].append(device_description)
            self._process_device_description(interface_id=interface_id, device_description=device_description)
            return
        # Address exists: remove old entries before adding the new description.
        self._remove_device(
            interface_id=interface_id,
            addresses_to_remove=[address],
        )
        self._raw_device_descriptions[interface_id].append(device_description)
        self._process_device_description(interface_id=interface_id, device_description=device_description)

    def find_device_description(self, *, interface_id: str, device_address: str) -> DeviceDescription | None:
        """Return the device description by interface and device_address."""
        return self._device_descriptions[interface_id].get(device_address)

    def get_addresses(self, *, interface_id: str | None = None) -> frozenset[str]:
        """Return the addresses by interface as a set."""
        if interface_id:
            return frozenset(self._addresses[interface_id])
        return frozenset(addr for interface_id in self.get_interface_ids() for addr in self._addresses[interface_id])

    def get_device_description(self, *, interface_id: str, address: str) -> DeviceDescription:
        """Return the device description by interface and device_address."""
        return self._device_descriptions[interface_id][address]

    def get_device_descriptions(self, *, interface_id: str) -> Mapping[str, DeviceDescription]:
        """Return the devices by interface."""
        return self._device_descriptions[interface_id]

    def get_device_with_channels(self, *, interface_id: str, device_address: str) -> Mapping[str, DeviceDescription]:
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

    def get_interface_ids(self) -> tuple[str, ...]:
        """Return the interface ids."""
        return tuple(self._raw_device_descriptions.keys())

    def get_model(self, *, device_address: str) -> str | None:
        """Return the device type."""
        for data in self._device_descriptions.values():
            if items := data.get(device_address):
                return items["TYPE"]
        return None

    def get_raw_device_descriptions(self, *, interface_id: str) -> list[DeviceDescription]:
        """Retrieve raw device descriptions from the cache."""
        return self._raw_device_descriptions[interface_id]

    def has_device_descriptions(self, *, interface_id: str) -> bool:
        """Return the devices by interface."""
        return interface_id in self._device_descriptions

    async def load(self, *, file_path: str | None = None) -> DataOperationResult:
        """Load device data from disk into _device_description_cache."""
        if not self._central.config.use_caches:
            _LOGGER.debug("load: not caching paramset descriptions for %s", self._central.name)
            return DataOperationResult.NO_LOAD
        if (result := await super().load(file_path=file_path)) == DataOperationResult.LOAD_SUCCESS:
            for (
                interface_id,
                device_descriptions,
            ) in self._raw_device_descriptions.items():
                self._convert_device_descriptions(interface_id=interface_id, device_descriptions=device_descriptions)
        return result

    def remove_device(self, *, device: Device) -> None:
        """Remove device from cache."""
        self._remove_device(
            interface_id=device.interface_id,
            addresses_to_remove=[device.address, *device.channels.keys()],
        )

    def _convert_device_descriptions(self, *, interface_id: str, device_descriptions: list[DeviceDescription]) -> None:
        """Convert provided list of device descriptions."""
        for device_description in device_descriptions:
            self._process_device_description(interface_id=interface_id, device_description=device_description)

    def _process_device_description(self, *, interface_id: str, device_description: DeviceDescription) -> None:
        """Convert provided dict of device descriptions."""
        address = device_description["ADDRESS"]
        device_address = get_device_address(address=address)
        self._device_descriptions[interface_id][address] = device_description

        # Avoid redundant membership checks; set.add is idempotent and cheaper than check+add
        addr_set = self._addresses[interface_id][device_address]
        addr_set.add(device_address)
        addr_set.add(address)

    def _remove_device(self, *, interface_id: str, addresses_to_remove: list[str]) -> None:
        """Remove a device from the cache."""
        # Use a set for faster membership checks
        addresses_set = set(addresses_to_remove)
        self._raw_device_descriptions[interface_id] = [
            device for device in self._raw_device_descriptions[interface_id] if device["ADDRESS"] not in addresses_set
        ]
        addr_map = self._addresses[interface_id]
        desc_map = self._device_descriptions[interface_id]
        for address in addresses_set:
            # Pop with default to avoid KeyError and try/except overhead
            if ADDRESS_SEPARATOR not in address:
                addr_map.pop(address, None)
            desc_map.pop(address, None)


class ParamsetDescriptionCache(BasePersistentFile):
    """Cache for paramset descriptions."""

    __slots__ = (
        "_address_parameter_cache",
        "_raw_paramset_descriptions",
    )

    _file_postfix = FILE_PARAMSETS
    _sub_directory = SUB_DIRECTORY_CACHE

    def __init__(self, *, central: hmcu.CentralUnit) -> None:
        """Init the paramset description cache."""
        # {interface_id, {channel_address, paramsets}}
        self._raw_paramset_descriptions: Final[dict[str, dict[str, dict[ParamsetKey, dict[str, ParameterData]]]]] = (
            defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
        )
        super().__init__(
            central=central,
            persistent_content=self._raw_paramset_descriptions,
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
        """Get paramset descriptions for a channelfrom cache."""
        return self._raw_paramset_descriptions[interface_id].get(channel_address, {})

    def get_parameter_data(
        self, *, interface_id: str, channel_address: str, paramset_key: ParamsetKey, parameter: str
    ) -> ParameterData | None:
        """Get parameter_data  from cache."""
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

    def is_in_multiple_channels(self, *, channel_address: str, parameter: str) -> bool:
        """Check if parameter is in multiple channels per device."""
        if ADDRESS_SEPARATOR not in channel_address:
            return False
        if channels := self._address_parameter_cache.get((get_device_address(address=channel_address), parameter)):
            return len(channels) > 1
        return False

    async def load(self, *, file_path: str | None = None) -> DataOperationResult:
        """Load paramset descriptions from disk into paramset cache."""
        if not self._central.config.use_caches:
            _LOGGER.debug("load: not caching device descriptions for %s", self._central.name)
            return DataOperationResult.NO_LOAD
        if (result := await super().load(file_path=file_path)) == DataOperationResult.LOAD_SUCCESS:
            self._init_address_parameter_list()
        return result

    def remove_device(self, *, device: Device) -> None:
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


class SessionRecorder(BasePersistentFile):
    """
    Session recorder for central unit.

    Nested cache with TTL support.
    Structure:
        store[rpc_type][method][params][ts: datetime] = response: Any

    - Expiration is lazy (checked on access/update).
    - Optional refresh_on_get extends TTL when reading.
    """

    __slots__ = (
        "_active",
        "_ttl",
        "_is_recording",
        "_refresh_on_get",
        "_store",
    )

    _file_postfix = FILE_SESSION_RECORDER
    _sub_directory = SUB_DIRECTORY_SESSION

    def __init__(
        self,
        *,
        central: hmcu.CentralUnit,
        active: bool,
        ttl_seconds: float,
        refresh_on_get: bool = False,
    ):
        """Init the cache."""
        self._active = active
        if ttl_seconds < 0:
            raise ValueError(i18n.tr("exception.store.session_recorder.ttl_positive"))
        self._ttl: Final = float(ttl_seconds)
        self._is_recording: bool = False
        self._refresh_on_get: Final = refresh_on_get
        # Use nested defaultdicts: rpc_type -> method -> params -> ts(int) -> response
        # Annotate as defaultdict to match the actual type and satisfy mypy.
        self._store: dict[str, dict[str, dict[str, dict[int, Any]]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(dict))
        )
        super().__init__(
            central=central,
            persistent_content=self._store,
        )

    def __repr__(self) -> str:
        """Return the representation."""
        self.cleanup()
        return f"{self.__class__.__name__}({self._store})"

    @property
    def _should_save(self) -> bool:
        """Determine if save operation should proceed."""
        self.cleanup()
        return len(self._store.items()) > 0

    @property
    def active(self) -> bool:
        """Return if session recorder is active."""
        return self._active

    async def activate(
        self, *, on_time: int = 0, auto_save: bool, randomize_output: bool, use_ts_in_file_name: bool
    ) -> bool:
        """Activate the session recorder. Disable after on_time(seconds)."""
        if self._is_recording:
            _LOGGER.info(i18n.tr("log.store.session_recorder.activate.already_running"))
            return False
        self._store.clear()
        self._active = True
        if on_time > 0:
            self._central.looper.create_task(
                target=self._deactivate_after_delay(
                    delay=on_time,
                    auto_save=auto_save,
                    randomize_output=randomize_output,
                    use_ts_in_file_name=use_ts_in_file_name,
                ),
                name=f"session_recorder_{self._central.name}",
            )
        return True

    def add_json_rpc_session(
        self,
        *,
        method: str,
        params: dict[str, Any],
        response: dict[str, Any] | None = None,
        session_exc: Exception | None = None,
    ) -> None:
        """Add json rpc session to content."""
        try:
            if session_exc:
                self.set(
                    rpc_type=str(RPCType.JSON_RPC),
                    method=method,
                    params=params,
                    response=extract_exc_args(exc=session_exc),
                )
                return
            self.set(rpc_type=str(RPCType.JSON_RPC), method=method, params=params, response=response)
        except Exception as exc:
            _LOGGER.debug("ADD_JSON_RPC_SESSION: failed with %s", extract_exc_args(exc=exc))

    def add_xml_rpc_session(
        self, *, method: str, params: tuple[Any, ...], response: Any | None = None, session_exc: Exception | None = None
    ) -> None:
        """Add rpc session to content."""
        try:
            if session_exc:
                self.set(
                    rpc_type=str(RPCType.XML_RPC),
                    method=method,
                    params=params,
                    response=extract_exc_args(exc=session_exc),
                )
                return
            self.set(rpc_type=str(RPCType.XML_RPC), method=method, params=params, response=response)
        except Exception as exc:
            _LOGGER.debug("ADD_XML_RPC_SESSION: failed with %s", extract_exc_args(exc=exc))

    def cleanup(self) -> None:
        """Purge all expired entries globally."""
        for rpc_type in list(self._store.keys()):
            for method in list(self._store[rpc_type].keys()):
                self._purge_expired_at(rpc_type=rpc_type, method=method)

    async def deactivate(
        self, *, delay: int, auto_save: bool, randomize_output: bool, use_ts_in_file_name: bool
    ) -> bool:
        """Deactivate the session recorder. Optionally after a delay(seconds)."""
        if self._is_recording:
            _LOGGER.info(i18n.tr("log.store.session_recorder.deactivate.already_running"))
            return False
        if delay > 0:
            self._central.looper.create_task(
                target=self._deactivate_after_delay(
                    delay=delay,
                    auto_save=auto_save,
                    randomize_output=randomize_output,
                    use_ts_in_file_name=use_ts_in_file_name,
                ),
                name=f"session_recorder_{self._central.name}",
            )
        else:
            self._active = False
            self._is_recording = False
        return True

    def delete(self, *, rpc_type: str, method: str, params: Any) -> bool:
        """
        Delete an entry if it exists. Returns True if removed.

        Avoid creating buckets when the target does not exist.
        Clean up empty parent buckets on successful deletion.
        """
        if not (bucket_by_method := self._store.get(rpc_type)):
            return False
        if not (bucket_by_parameter := bucket_by_method.get(method)):
            return False
        if (frozen_param := _freeze_params(params)) not in bucket_by_parameter:
            return False
        # Perform deletion
        bucket_by_parameter.pop(frozen_param, None)
        if not bucket_by_parameter:
            bucket_by_method.pop(method, None)
            if not bucket_by_method:
                self._store.pop(rpc_type, None)
        return True

    def get(
        self,
        *,
        rpc_type: str,
        method: str,
        params: Any,
        default: Any = None,
    ) -> Any:
        """
        Return a cached response if still valid, else default.

        This method must avoid creating buckets when the entry is missing.
        It purges expired entries first, then returns the response at the
        latest timestamp for the given params. If refresh_on_get is enabled,
        it appends a new timestamp with the same response/ttl.
        """
        self._purge_expired_at(rpc_type=rpc_type, method=method)
        # Access store safely to avoid side effects from creating buckets.
        if not (bucket_by_method := self._store.get(rpc_type)):
            return default
        if not (bucket_by_parameter := bucket_by_method.get(method)):
            return default
        frozen_param = _freeze_params(params)
        if not (bucket_by_ts := bucket_by_parameter.get(frozen_param)):
            return default
        try:
            latest_ts = max(bucket_by_ts.keys())
        except ValueError:
            return default
        resp = bucket_by_ts[latest_ts]
        if self._refresh_on_get:
            bucket_by_ts[_now()] = resp
        return resp

    def get_latest_response_by_method(self, *, rpc_type: str, method: str) -> list[tuple[Any, Any]]:
        """Return latest non-expired responses for a given (rpc_type, method)."""
        # Purge expired entries first without creating any new buckets.
        self._purge_expired_at(rpc_type=rpc_type, method=method)
        result: list[Any] = []
        # Access store safely to avoid side effects from creating buckets.
        if not (bucket_by_method := self._store.get(rpc_type)):
            return result
        if not (bucket_by_parameter := bucket_by_method.get(method)):
            return result
        # For each parameter, choose the response at the latest timestamp.
        for frozen_params, bucket_by_ts in bucket_by_parameter.items():
            if not bucket_by_ts:
                continue
            try:
                latest_ts = max(bucket_by_ts.keys())
            except ValueError:
                continue
            resp = bucket_by_ts[latest_ts]
            params = _unfreeze_params(frozen_params=frozen_params)

            result.append((params, resp))
        return result

    def get_latest_response_by_params(
        self,
        *,
        rpc_type: str,
        method: str,
        params: Any,
    ) -> Any:
        """Return latest non-expired responses for a given (rpc_type, method, params)."""
        # Purge expired entries first without creating any new buckets.
        self._purge_expired_at(rpc_type=rpc_type, method=method)

        # Access store safely to avoid side effects from creating buckets.
        if not (bucket_by_method := self._store.get(rpc_type)):
            return None
        if not (bucket_by_parameter := bucket_by_method.get(method)):
            return None
        frozen_params = _freeze_params(params=params)

        # For each parameter, choose the response at the latest timestamp.
        if (bucket_by_ts := bucket_by_parameter.get(frozen_params)) is None:
            return None

        try:
            latest_ts = max(bucket_by_ts.keys())
            return bucket_by_ts[latest_ts]
        except ValueError:
            return None

    def peek_ts(self, *, rpc_type: str, method: str, params: Any) -> datetime | None:
        """
        Return the most recent timestamp for a live entry, else None.

        This method must not create buckets as a side effect. It purges expired
        entries first and then returns the newest timestamp for the given
        (rpc_type, method, params) if present.
        """
        self._purge_expired_at(rpc_type=rpc_type, method=method)
        # Do NOT create buckets here — use .get chaining only.
        if not (bucket_by_method := self._store.get(rpc_type)):
            return None
        if not (bucket_by_parameter := bucket_by_method.get(method)):
            return None
        frozen_param = _freeze_params(params)
        if (bucket_by_ts := bucket_by_parameter.get(frozen_param)) is None or not bucket_by_ts:
            return None
        # After purge, remaining entries are alive; return the latest timestamp.
        try:
            latest_ts_int = max(bucket_by_ts.keys())
        except ValueError:
            # bucket was empty (shouldn't happen due to check), be safe
            return None
        return datetime.fromtimestamp(latest_ts_int, tz=UTC)

    def set(
        self,
        *,
        rpc_type: str,
        method: str,
        params: Any,
        response: Any,
        ts: int | datetime | None = None,
    ) -> Self:
        """Insert or update an entry."""
        self._purge_expired_at(rpc_type=rpc_type, method=method)
        frozen_param = _freeze_params(params)
        # Normalize timestamp to int epoch seconds
        if isinstance(ts, datetime):
            ts_int = int(ts.timestamp())
        elif isinstance(ts, int):
            ts_int = ts
        else:
            ts_int = _now()
        self._bucket(rpc_type=rpc_type, method=method)[frozen_param][ts_int] = response
        return self

    def _bucket(self, *, rpc_type: str, method: str) -> dict[str, dict[int, tuple[Any, float]]]:
        """Ensure and return the innermost bucket."""
        return self._store[rpc_type][method]

    async def _deactivate_after_delay(
        self, *, delay: int, auto_save: bool, randomize_output: bool, use_ts_in_file_name: bool
    ) -> None:
        """Change the state of the session recorder after a delay."""
        self._is_recording = True
        await asyncio.sleep(delay)
        self._active = False
        self._is_recording = False
        if auto_save:
            await self.save(randomize_output=randomize_output, use_ts_in_file_name=use_ts_in_file_name)
        _LOGGER.debug("Deactivated session recorder after %s seconds", {delay})

    def _is_expired(self, *, ts: int, now: int | None = None) -> bool:
        """Check whether an entry has expired given epoch seconds."""
        if self._ttl == 0:
            return False
        now = now if now is not None else _now()
        return (now - ts) > self._ttl

    def _purge_expired_at(
        self,
        *,
        rpc_type: str,
        method: str,
    ) -> None:
        """Remove expired entries for a given (rpc_type, method) bucket without creating new ones."""
        if self._ttl == 0:
            return
        if not (bucket_by_method := self._store.get(rpc_type)):
            return
        if not (bucket_by_parameter := bucket_by_method.get(method)):
            return
        now = _now()
        empty_params: list[str] = []
        for p, bucket_by_ts in bucket_by_parameter.items():
            expired_ts = [ts for ts, _r in list(bucket_by_ts.items()) if self._is_expired(ts=ts, now=now)]
            for ts in expired_ts:
                del bucket_by_ts[ts]
            if not bucket_by_ts:
                empty_params.append(p)
        for p in empty_params:
            bucket_by_parameter.pop(p, None)
        if not bucket_by_parameter:
            bucket_by_method.pop(method, None)
            if not bucket_by_method:
                self._store.pop(rpc_type, None)


def _freeze_params(params: Any) -> str:
    """
    Recursively freeze any structure so it can be used as a dictionary key.

    - dict → tuple of (key, frozen(value)) sorted by key.
    - list/tuple → tuple of frozen elements.
    - set/frozenset → tagged tuple ("__set__", tuple(sorted(frozen elements by repr))) to ensure JSON-serializable keys.
    - datetime → tagged ISO 8601 string to ensure JSON-serializable keys.
    """
    res: Any = ""
    match params:
        case datetime():
            # orjson cannot serialize datetime objects as dict keys even with OPT_NON_STR_KEYS.
            # Use a tagged ISO string to preserve value and guarantee a stable, hashable key.
            res = ("__datetime__", params.isoformat())
        case dict():
            res = {k: _freeze_params(v) for k, v in sorted(params.items())}
        case list() | tuple():
            res = tuple(_freeze_params(x) for x in params)
        case set() | frozenset():
            # Convert to a deterministically ordered, JSON-serializable representation.
            frozen_elems = tuple(sorted((_freeze_params(x) for x in params), key=repr))
            res = ("__set__", frozen_elems)
        case _:
            res = params

    return str(res)


def _unfreeze_params(frozen_params: str) -> Any:
    """
    Reverse the _freeze_params transformation.

    Tries to parse the frozen string with ast.literal_eval and then recursively
    reconstructs original structures:
    - ("__set__", (<items>...)) -> set of items
    - ("__datetime__", iso_string) -> datetime.fromisoformat(iso_string)
    - dict values and tuple elements are processed recursively

    If parsing fails, return the original string.
    """
    try:
        obj = ast.literal_eval(frozen_params)
    except Exception:
        return frozen_params

    def _walk(o: Any) -> Any:
        if o and isinstance(o, tuple):
            tag = o[0]
            # Tagged set
            if tag == "__set__" and len(o) == 2 and isinstance(o[1], tuple):
                return {_walk(x) for x in o[1]}
            # Tagged datetime
            if tag == "__datetime__" and len(o) == 2 and isinstance(o[1], str):
                try:
                    return datetime.fromisoformat(o[1])
                except Exception:
                    return o[1]
            # Generic tuple
            return tuple(_walk(x) for x in o)
        if isinstance(o, dict):
            return {k: _walk(v) for k, v in o.items()}
        if isinstance(o, list):
            return [_walk(x) for x in o]
        if isinstance(o, tuple):
            return tuple(_walk(x) for x in o)
        if o.startswith("{") and o.endswith("}"):
            return ast.literal_eval(o)
        return o

    return _walk(obj)


def _get_file_path(*, storage_directory: str, sub_directory: str) -> str:
    """Return the content path."""
    return f"{storage_directory}/{sub_directory}"


def _get_file_name(*, central_name: str, file_name: str, ts: datetime | None = None) -> str:
    """Return the content file_name."""
    fn = f"{slugify(central_name)}_{file_name}"
    if ts:
        fn += f"_{ts.strftime(FILE_NAME_TS_PATTERN)}"
    return f"{fn}.json"


def _now() -> int:
    """Return current UTC time as epoch seconds (int)."""
    return int(datetime.now(tz=UTC).timestamp())


@loop_check
def cleanup_files(*, central_name: str, storage_directory: str) -> None:
    """Clean up the used files."""
    loop = asyncio.get_running_loop()
    cache_dir = _get_file_path(storage_directory=storage_directory, sub_directory=SUB_DIRECTORY_CACHE)
    loop.run_in_executor(None, delete_file, cache_dir, f"{central_name}*.json".lower())
    session_dir = _get_file_path(storage_directory=storage_directory, sub_directory=SUB_DIRECTORY_SESSION)
    loop.run_in_executor(None, delete_file, session_dir, f"{central_name}*.json".lower())
