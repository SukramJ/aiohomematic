# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Base class for persistent file-backed caches.

This module provides the abstract base class for all persistent caches that
store data to disk as JSON files.

Key behaviors:
- Saves only if caches are enabled and content has changed (hash comparison)
- Uses orjson for fast binary writes and json for reads
- Save/load/clear operations are synchronized via a semaphore
- Supports both plain JSON and ZIP archive formats
"""

from __future__ import annotations

from abc import ABC
import asyncio
from datetime import datetime
import json
import logging
import os
from typing import Any, Final
import zipfile

import orjson
from slugify import slugify

from aiohomematic.const import FILE_NAME_TS_PATTERN, INIT_DATETIME, UTF_8, DataOperationResult
from aiohomematic.interfaces.central import CentralInfoProtocol, ConfigProviderProtocol, DeviceProviderProtocol
from aiohomematic.interfaces.operations import TaskSchedulerProtocol
from aiohomematic.support import (
    check_or_create_directory,
    create_random_device_addresses,
    delete_file,
    hash_sha256,
    regular_to_default_dict_hook,
)

_LOGGER: Final = logging.getLogger(__name__)


class BasePersistentFile(ABC):
    """Cache for files."""

    __slots__ = (
        "_central_info",
        "_config_provider",
        "_device_provider",
        "_directory",
        "_file_postfix",
        "_persistent_content",
        "_save_load_semaphore",
        "_sub_directory",
        "_task_scheduler",
        "_use_ts_in_file_names",
        "last_hash_saved",
        "last_save_triggered",
    )

    _file_postfix: str
    _sub_directory: str

    def __init__(
        self,
        *,
        central_info: CentralInfoProtocol,
        config_provider: ConfigProviderProtocol,
        device_provider: DeviceProviderProtocol,
        task_scheduler: TaskSchedulerProtocol,
        persistent_content: dict[str, Any],
    ) -> None:
        """Initialize the base class of the persistent content."""
        self._save_load_semaphore: Final = asyncio.Semaphore()
        self._config_provider: Final = config_provider
        self._task_scheduler: Final = task_scheduler
        self._central_info: Final = central_info
        self._device_provider: Final = device_provider
        self._persistent_content: Final = persistent_content
        self._directory: Final = get_file_path(
            storage_directory=config_provider.config.storage_directory, sub_directory=self._sub_directory
        )
        self.last_save_triggered: datetime = INIT_DATETIME
        self.last_hash_saved = hash_sha256(value=persistent_content)

    @property
    def _should_save(self) -> bool:
        """Determine if save operation should proceed."""
        self.last_save_triggered = datetime.now()
        return (
            check_or_create_directory(directory=self._directory)
            and self._config_provider.config.use_caches
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
            delete_file(directory=self._directory, file_name=f"{self._central_info.name}*.json".lower())
            self._persistent_content.clear()

        async with self._save_load_semaphore:
            await self._task_scheduler.async_add_executor_job(_perform_clear, name="clear-persistent-content")

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
            return await self._task_scheduler.async_add_executor_job(_perform_load, name="load-persistent-content")

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
            return await self._task_scheduler.async_add_executor_job(_perform_save, name="save-persistent-content")

    def _get_file_name(
        self,
        *,
        use_ts_in_file_name: bool = False,
    ) -> str:
        """Return the file name."""
        return get_file_name(
            central_name=self._central_info.name,
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

        addresses = [device.address for device in self._device_provider.devices]
        text = content.decode(encoding=UTF_8)
        for device_address, rnd_address in create_random_device_addresses(addresses=addresses).items():
            text = text.replace(device_address, rnd_address)
        return text.encode(encoding=UTF_8)


def get_file_path(*, storage_directory: str, sub_directory: str) -> str:
    """Return the content path."""
    return f"{storage_directory}/{sub_directory}"


def get_file_name(*, central_name: str, file_name: str, ts: datetime | None = None) -> str:
    """Return the content file_name."""
    fn = f"{slugify(central_name)}_{file_name}"
    if ts:
        fn += f"_{ts.strftime(FILE_NAME_TS_PATTERN)}"
    return f"{fn}.json"
