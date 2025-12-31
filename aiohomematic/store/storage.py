# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Storage abstraction for persistent data.

This module provides a storage protocol and local implementation that can be
substituted with Home Assistant's Store when running within HA.

Overview
--------
The Storage class provides a unified interface for persisting JSON-serializable
data. It supports:

- orjson serialization for performance
- ZIP archive loading for backup files
- Version migrations for schema evolution
- Delayed/debounced saves to reduce I/O
- Atomic writes (write to temp, then rename)

Public API
----------
- StorageProtocol: Interface for storage operations
- StorageFactoryProtocol: Interface for creating storage instances
- Storage: Local file-based storage implementation
- LocalStorageFactory: Default factory using local Storage
- StorageError: Exception for storage operation failures

Example:
-------
Using local storage::

    factory = LocalStorageFactory(
        base_directory="/path/to/storage",
        central_name="my-ccu",
    )
    storage = factory.create_storage(key="my_cache", version=1)

    # Save data
    await storage.save({"devices": [...]})

    # Load data
    data = await storage.load()

    # Remove storage
    await storage.remove()

Using delayed save::

    # Schedule save with debouncing
    await storage.delay_save(
        data_func=lambda: cache.get_content(),
        delay=2.0,
    )

    # Flush on shutdown
    await storage.flush()

"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from functools import partial
import glob
import logging
import os
from typing import TYPE_CHECKING, Any, Final, Protocol, cast, runtime_checkable
import zipfile

import orjson
from slugify import slugify

if TYPE_CHECKING:
    from aiohomematic.interfaces import TaskSchedulerProtocol

_LOGGER: Final = logging.getLogger(__name__)

# Type alias for migration function
MigrateFunc = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class StorageError(Exception):
    """Exception raised for storage operation failures."""


@runtime_checkable
class StorageProtocol(Protocol):
    """
    Protocol for storage operations.

    This protocol defines the interface that both local Storage and
    Home Assistant's Store must implement. It provides async methods
    for loading, saving, and removing persisted data.

    The data format is always a serializable dict. Implementations
    must handle serialization internally.

    Supports:
        - Basic CRUD operations (load, save, remove)
        - ZIP archive loading
        - Version migrations
        - Delayed/debounced saves
    """

    @property
    def key(self) -> str:
        """Return the storage key identifier."""

    @property
    def version(self) -> int:
        """Return the storage version for migration support."""

    async def delay_save(
        self,
        *,
        data_func: Callable[[], dict[str, Any]],
        delay: float = 1.0,
    ) -> None:
        """
        Schedule a delayed save operation.

        Multiple calls within the delay period will reset the timer.
        Only the last data_func will be used when the save executes.

        Args:
            data_func: Callable that returns the data to save.
            delay: Delay in seconds before saving (default: 1.0).

        """

    async def flush(self) -> None:
        """
        Flush any pending delayed save immediately.

        Call this during shutdown to ensure data is saved.
        """

    async def load(self) -> dict[str, Any] | None:
        """
        Load data from storage.

        Returns:
            The stored data as dict, or None if no data exists.

        """

    async def remove(self) -> None:
        """Remove storage data."""

    async def save(self, *, data: dict[str, Any]) -> None:
        """
        Save data to storage.

        Args:
            data: Serializable dict to persist.

        Raises:
            StorageError: If data is not serializable or write fails.

        """


@runtime_checkable
class StorageFactoryProtocol(Protocol):
    """
    Protocol for creating storage instances.

    This protocol allows aiohomematic to receive either a local storage
    factory or a Home Assistant store factory, enabling transparent
    substitution of storage backends.

    HomematicIP Local implements this protocol with a factory that
    creates HA Store instances. aiohomematic provides LocalStorageFactory
    as the default implementation.
    """

    def create_storage(
        self,
        *,
        key: str,
        version: int = 1,
        sub_directory: str | None = None,
        migrate_func: MigrateFunc | None = None,
        raw_mode: bool = True,
        formatted: bool = False,
        as_zip: bool = False,
    ) -> StorageProtocol:
        """
        Create a storage instance.

        Args:
            key: Unique identifier for this storage (e.g., "device_cache").
            version: Schema version for migration support.
            sub_directory: Optional subdirectory within base storage.
            migrate_func: Optional async function to migrate old data.
            raw_mode: If True, save data without metadata wrapper (_key, _version).
                Useful for export files that don't need version tracking.
            formatted: If True, write indented JSON for readability.
                Default is False (compact output).
            as_zip: If True, save data as ZIP archive.
                Default is False (plain JSON file).

        Returns:
            A storage instance implementing StorageProtocol.

        """


class Storage:
    """
    Local file-based storage implementation.

    This class provides a local alternative to Home Assistant's Store,
    using orjson for fast serialization. It implements StorageProtocol
    and can be used standalone or substituted with HA Store via the
    factory pattern.

    Features:
        - orjson serialization for performance
        - ZIP archive loading for backup files
        - Automatic version migration
        - Delayed/debounced saves
        - Atomic writes (write to temp, then rename)
        - Serialization validation

    Thread Safety:
        All operations are protected by an asyncio.Lock to prevent
        concurrent read/write conflicts.
    """

    __slots__ = (
        "_as_zip",
        "_base_directory",
        "_delay_handle",
        "_file_path",
        "_formatted",
        "_key",
        "_lock",
        "_migrate_func",
        "_pending_data_func",
        "_raw_mode",
        "_task_scheduler",
        "_version",
    )

    def __init__(
        self,
        *,
        key: str,
        base_directory: str,
        version: int = 1,
        sub_directory: str | None = None,
        task_scheduler: TaskSchedulerProtocol | None = None,
        migrate_func: MigrateFunc | None = None,
        raw_mode: bool = True,
        formatted: bool = False,
        as_zip: bool = False,
    ) -> None:
        """
        Initialize storage.

        Args:
            key: Unique identifier for this storage.
            base_directory: Root directory for storage files.
            version: Schema version.
            sub_directory: Optional subdirectory.
            task_scheduler: Optional scheduler for executor jobs.
            migrate_func: Optional async function to migrate old data.
            raw_mode: If True, save data without metadata wrapper (_key, _version).
                Useful for export files that don't need version tracking.
            formatted: If True, write indented JSON for readability.
                Default is False (compact output).
            as_zip: If True, save data as ZIP archive.
                Default is False (plain JSON file).

        """
        self._key: Final = key
        self._version: Final = version
        self._task_scheduler: Final = task_scheduler
        self._migrate_func: Final = migrate_func
        self._raw_mode: Final = raw_mode
        self._formatted: Final = formatted
        self._as_zip: Final = as_zip
        self._lock: Final = asyncio.Lock()

        # Delayed save state
        self._delay_handle: asyncio.TimerHandle | None = None
        self._pending_data_func: Callable[[], dict[str, Any]] | None = None

        # Build file path
        directory = base_directory
        if sub_directory:
            directory = os.path.join(base_directory, sub_directory)
        self._base_directory: Final = directory
        self._file_path: Final = os.path.join(directory, f"{key}.json")

    @property
    def file_path(self) -> str:
        """Return the full file path."""
        return self._file_path

    @property
    def key(self) -> str:
        """Return the storage key identifier."""
        return self._key

    @property
    def version(self) -> int:
        """Return the storage version."""
        return self._version

    async def delay_save(
        self,
        *,
        data_func: Callable[[], dict[str, Any]],
        delay: float = 1.0,
    ) -> None:
        """
        Schedule a delayed save operation.

        Multiple calls within the delay period will reset the timer.
        Only the last data_func will be used when the save executes.

        Args:
            data_func: Callable that returns the data to save.
            delay: Delay in seconds before saving (default: 1.0).

        """
        # Cancel existing timer if any
        if self._delay_handle is not None:
            self._delay_handle.cancel()
            self._delay_handle = None

        self._pending_data_func = data_func

        # Schedule new save
        loop = asyncio.get_running_loop()
        self._delay_handle = loop.call_later(
            delay,
            lambda: asyncio.create_task(self._execute_delayed_save()),
        )

    async def flush(self) -> None:
        """
        Flush any pending delayed save immediately.

        Call this during shutdown to ensure data is saved.
        """
        if self._delay_handle is not None:
            self._delay_handle.cancel()
            self._delay_handle = None

        if self._pending_data_func is not None:
            await self._execute_delayed_save()

    async def load(self) -> dict[str, Any] | None:
        """
        Load data from storage asynchronously.

        Supports loading from:
        - Regular JSON files
        - ZIP archives containing JSON

        If a migration function was provided and the stored version
        is older than the current version, migration is performed
        automatically.

        Returns:
            The stored data as dict, or None if file doesn't exist.

        Raises:
            StorageError: If file exists but cannot be read/parsed.

        """
        async with self._lock:
            if (raw_data := await self._load_raw()) is None:
                return None

            # Check version and migrate if needed
            stored_version = cast(int, raw_data.get("_version", 1))
            data = cast(dict[str, Any], raw_data.get("data", raw_data))

            if stored_version < self._version and self._migrate_func:
                _LOGGER.debug(
                    "STORAGE: Migrating %s from version %s to %s",
                    self._key,
                    stored_version,
                    self._version,
                )
                data = await self._migrate_func(data)
                # Save migrated data (without holding the lock again)
                await self._save_internal(data=data)

            return data

    async def remove(self) -> None:
        """Remove storage file asynchronously."""
        async with self._lock:
            if self._task_scheduler:
                await self._task_scheduler.async_add_executor_job(self._remove_sync, name="storage-remove")
            else:
                await asyncio.to_thread(self._remove_sync)

    async def save(self, *, data: dict[str, Any] | list[Any]) -> None:
        """
        Save data to storage asynchronously.

        Args:
            data: Data to persist. Must be JSON-serializable.
                In normal mode, must be a dict. In raw_mode, can be dict or list.

        Raises:
            StorageError: If data is not serializable or write fails.

        """
        self._validate_serializable(data=data)

        async with self._lock:
            await self._save_internal(data=data)

    async def _execute_delayed_save(self) -> None:
        """Execute the pending delayed save."""
        if self._pending_data_func is None:
            return

        data = self._pending_data_func()
        self._pending_data_func = None
        self._delay_handle = None

        try:
            await self.save(data=data)
        except StorageError:
            _LOGGER.exception("STORAGE: Delayed save failed for %s", self._key)  # i18n-log: ignore

    def _load_from_zip(self, *, zip_path: str) -> dict[str, Any]:
        """Load data from ZIP archive."""
        try:
            with zipfile.ZipFile(zip_path, mode="r") as zf:
                if not (json_files := [n for n in zf.namelist() if n.lower().endswith(".json")]):
                    raise StorageError(f"No JSON file found in ZIP: {zip_path}")  # i18n-exc: ignore
                raw = zf.read(json_files[0])
                return self._parse_and_unwrap(raw_data=orjson.loads(raw))
        except (zipfile.BadZipFile, OSError) as exc:
            raise StorageError(f"Failed to load ZIP '{zip_path}': {exc}") from exc  # i18n-exc: ignore

    async def _load_raw(self) -> dict[str, Any] | None:
        """Load raw data without migration."""
        if self._task_scheduler:
            return await self._task_scheduler.async_add_executor_job(self._load_sync, name="storage-load")
        return await asyncio.to_thread(self._load_sync)

    def _load_sync(self) -> dict[str, Any] | None:
        """Load data synchronously with ZIP support."""
        # Check if file exists, try ZIP variant if not
        if not os.path.exists(self._file_path):
            zip_path = f"{self._file_path}.zip"
            if os.path.exists(zip_path):
                return self._load_from_zip(zip_path=zip_path)
            return None

        # Check if file is a ZIP archive
        if zipfile.is_zipfile(self._file_path):
            return self._load_from_zip(zip_path=self._file_path)

        # Regular JSON load
        try:
            with open(self._file_path, "rb") as f:
                return self._parse_and_unwrap(raw_data=orjson.loads(f.read()))
        except (orjson.JSONDecodeError, OSError) as exc:
            raise StorageError(f"Failed to load storage '{self._key}': {exc}") from exc  # i18n-exc: ignore

    def _parse_and_unwrap(self, *, raw_data: Any) -> dict[str, Any]:
        """Parse and unwrap metadata if present."""
        if isinstance(raw_data, dict) and "data" in raw_data and "_version" in raw_data:
            # Return full structure for version checking
            return raw_data
        # Legacy format or unwrapped data
        return {"data": raw_data, "_version": 1}

    def _remove_sync(self) -> None:
        """Remove storage file synchronously."""
        if os.path.exists(self._file_path):
            os.remove(self._file_path)

    async def _save_internal(self, *, data: dict[str, Any] | list[Any]) -> None:
        """Save data internally without acquiring lock."""
        if self._task_scheduler:
            await self._task_scheduler.async_add_executor_job(partial(self._save_sync, data=data), name="storage-save")
        else:
            await asyncio.to_thread(self._save_sync, data=data)

    def _save_sync(self, *, data: dict[str, Any] | list[Any]) -> None:
        """Save data synchronously with atomic write."""
        # Ensure directory exists
        os.makedirs(self._base_directory, exist_ok=True)

        # In raw mode, save data directly; otherwise wrap with version metadata
        to_save = data if self._raw_mode else {"_version": self._version, "_key": self._key, "data": data}

        # Serialize (formatted with indentation or compact)
        opts = orjson.OPT_NON_STR_KEYS | (orjson.OPT_INDENT_2 if self._formatted else 0)
        try:
            serialized = orjson.dumps(to_save, option=opts)
        except TypeError as exc:
            raise StorageError(f"Data not serializable for '{self._key}': {exc}") from exc  # i18n-exc: ignore

        # Determine target path and temp path
        target_path = f"{self._file_path}.zip" if self._as_zip else self._file_path
        temp_path = f"{target_path}.tmp"

        try:
            if self._as_zip:
                # Write as ZIP archive
                with zipfile.ZipFile(temp_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
                    zf.writestr(f"{self._key}.json", serialized)
            else:
                # Write as plain JSON
                with open(temp_path, "wb") as f:
                    f.write(serialized)
            os.replace(temp_path, target_path)
        except OSError as exc:
            # Clean up temp file on failure
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise StorageError(f"Failed to save storage '{self._key}': {exc}") from exc  # i18n-exc: ignore

    def _validate_serializable(self, *, data: dict[str, Any] | list[Any]) -> None:
        """
        Validate that data is serializable.

        Args:
            data: Data to validate.

        Raises:
            StorageError: If data is not serializable or (in normal mode) not a dict.

        """
        # In raw_mode, accept both dict and list; otherwise require dict
        if not self._raw_mode and not isinstance(data, dict):
            raise StorageError(  # i18n-exc: ignore
                f"Storage '{self._key}' requires dict, got {type(data).__name__}"
            )

        try:
            orjson.dumps(data, option=orjson.OPT_NON_STR_KEYS)
        except TypeError as exc:
            raise StorageError(  # i18n-exc: ignore
                f"Data for storage '{self._key}' is not JSON-serializable: {exc}"
            ) from exc


class LocalStorageFactory:
    """
    Factory for creating local Storage instances.

    This is the default factory used by aiohomematic when no external
    factory (e.g., from Home Assistant) is provided.

    Example::

        factory = LocalStorageFactory(
            base_directory="/config/aiohomematic",
            central_name="my-ccu",
        )
        device_storage = factory.create_storage(
            key="device_cache",
            version=1,
            sub_directory="cache",
        )
    """

    __slots__ = ("_base_directory", "_central_name", "_task_scheduler")

    def __init__(
        self,
        *,
        base_directory: str,
        central_name: str,
        task_scheduler: TaskSchedulerProtocol | None = None,
    ) -> None:
        """
        Initialize the factory.

        Args:
            base_directory: Root directory for all storage files.
            central_name: Name of the central unit (used in file names).
            task_scheduler: Optional scheduler for async executor jobs.

        """
        self._base_directory: Final = base_directory
        self._central_name: Final = central_name
        self._task_scheduler: Final = task_scheduler

    async def cleanup_files(self, *, sub_directory: str | None = None) -> int:
        """
        Remove all storage files for this central unit.

        Deletes all JSON files matching the central name pattern in the
        specified directory. Useful for clearing caches or resetting state.

        Args:
            sub_directory: Optional subdirectory to clean. If None, cleans
                the base directory.

        Returns:
            Number of files deleted.

        """
        if self._task_scheduler:
            return await self._task_scheduler.async_add_executor_job(
                partial(self._cleanup_files_sync, sub_directory=sub_directory), name="storage-cleanup"
            )
        return await asyncio.to_thread(self._cleanup_files_sync, sub_directory=sub_directory)

    def create_storage(
        self,
        *,
        key: str,
        version: int = 1,
        sub_directory: str | None = None,
        migrate_func: MigrateFunc | None = None,
        raw_mode: bool = True,
        formatted: bool = False,
        as_zip: bool = False,
    ) -> StorageProtocol:
        """
        Create a storage instance.

        The storage key is prefixed with the central name to allow
        multiple central units to coexist.

        Args:
            key: Base key for this storage.
            version: Schema version.
            sub_directory: Optional subdirectory.
            migrate_func: Optional async migration function.
            raw_mode: If True, save data without metadata wrapper (_key, _version).
                Useful for export files that don't need version tracking.
            formatted: If True, write indented JSON for readability.
                Default is False (compact output).
            as_zip: If True, save data as ZIP archive.
                Default is False (plain JSON file).

        Returns:
            Storage instance.

        """
        # Prefix key with central name (slugified)
        full_key = f"{slugify(self._central_name)}_{key}"

        return Storage(
            key=full_key,
            base_directory=self._base_directory,
            version=version,
            sub_directory=sub_directory,
            task_scheduler=self._task_scheduler,
            migrate_func=migrate_func,
            raw_mode=raw_mode,
            formatted=formatted,
            as_zip=as_zip,
        )

    def _cleanup_files_sync(self, *, sub_directory: str | None) -> int:
        """Delete storage files synchronously."""
        directory = self._base_directory
        if sub_directory:
            directory = os.path.join(self._base_directory, sub_directory)

        if not os.path.exists(directory):
            return 0

        # Pattern: {central_name}*.json
        pattern = os.path.join(directory, f"{slugify(self._central_name)}*.json")
        deleted_count = 0

        for file_path in glob.glob(pattern):
            if os.path.isfile(file_path):
                os.remove(file_path)
                deleted_count += 1

        return deleted_count
