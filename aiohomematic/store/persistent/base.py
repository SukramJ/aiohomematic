# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Base class for persistent caches using storage abstraction.

This module provides the foundation for all persistent caches. Instead of
handling file I/O directly, caches now delegate to StorageProtocol instances.

Key behaviors:
- Delegates file I/O to StorageProtocol
- Hash-based change detection for efficient saves
- Optional caching control via config
- Supports delayed saves for batching updates

Migration from old BasePersistentFile
-------------------------------------
The old implementation mixed cache logic with file operations. The new
BasePersistentCache separates concerns:

- Cache logic: Handled by BasePersistentCache and subclasses
- File operations: Delegated to StorageProtocol
- Factory creation: Via StorageFactoryProtocol
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
import logging
from typing import TYPE_CHECKING, Any, Final

from slugify import slugify

from aiohomematic.const import FILE_NAME_TS_PATTERN, INIT_DATETIME, DataOperationResult
from aiohomematic.support import hash_sha256

if TYPE_CHECKING:
    from aiohomematic.interfaces import ConfigProviderProtocol
    from aiohomematic.store.storage import StorageProtocol

_LOGGER: Final = logging.getLogger(__name__)


class BasePersistentCache(ABC):
    """
    Base class for persistent caches.

    This abstract class provides common functionality for caches that need
    to persist their data. Subclasses define the cache structure and logic,
    while actual storage operations are delegated to a StorageProtocol.

    Key differences from old BasePersistentFile:
        - No direct file I/O - uses storage.save/load
        - No semaphore needed - storage handles synchronization
        - Hash-based change detection retained for efficiency
        - Simpler interface - only cache logic, no file path handling

    Subclasses must implement:
        - _create_empty_content(): Define initial data structure
        - _process_loaded_content(): Rebuild indexes after load
    """

    __slots__ = (
        "_config_provider",
        "_content",
        "_last_hash_saved",
        "_storage",
        "last_save_triggered",
    )

    def __init__(
        self,
        *,
        storage: StorageProtocol,
        config_provider: ConfigProviderProtocol,
    ) -> None:
        """
        Initialize the cache.

        Args:
            storage: Storage instance for persistence.
            config_provider: Provider for configuration access.

        """
        self._storage: Final = storage
        self._config_provider: Final = config_provider
        self._content: dict[str, Any] = self._create_empty_content()
        self._last_hash_saved: str = ""
        self.last_save_triggered: datetime = INIT_DATETIME

    @property
    def _should_save(self) -> bool:
        """Determine if save operation should proceed."""
        self.last_save_triggered = datetime.now()
        return self._config_provider.config.use_caches and self.has_unsaved_changes

    @property
    def content_hash(self) -> str:
        """Return hash of current content."""
        return hash_sha256(value=self._content)

    @property
    def has_unsaved_changes(self) -> bool:
        """Return True if content changed since last save."""
        return self.content_hash != self._last_hash_saved

    @property
    def storage_key(self) -> str:
        """Return the storage key."""
        return self._storage.key

    async def clear(self) -> None:
        """Remove storage and clear content."""
        await self._storage.remove()
        self._content.clear()
        self._content.update(self._create_empty_content())
        self._last_hash_saved = ""

    async def flush(self) -> None:
        """Flush any pending delayed saves immediately."""
        await self._storage.flush()

    async def load(self) -> DataOperationResult:
        """
        Load content from storage.

        After loading, calls _process_loaded_content to rebuild any
        derived structures or indexes.

        Returns:
            DataOperationResult indicating success/skip/failure.

        """
        try:
            data = await self._storage.load()
        except Exception:
            _LOGGER.exception("CACHE: Failed to load %s", self.storage_key)  # i18n-log: ignore
            return DataOperationResult.LOAD_FAIL

        if data is None:
            return DataOperationResult.NO_LOAD

        if (loaded_hash := hash_sha256(value=data)) == self._last_hash_saved:
            return DataOperationResult.NO_LOAD

        self._content.clear()
        self._content.update(data)
        self._process_loaded_content(data=data)
        self._last_hash_saved = loaded_hash
        return DataOperationResult.LOAD_SUCCESS

    async def save(self) -> DataOperationResult:
        """
        Save content to storage if changed.

        Only saves if caching is enabled and content has changed since last save.

        Returns:
            DataOperationResult indicating success/skip/failure.

        """
        if not self._should_save:
            return DataOperationResult.NO_SAVE

        try:
            await self._storage.save(data=self._content)
            self._last_hash_saved = self.content_hash
        except Exception:
            _LOGGER.exception("CACHE: Failed to save %s", self.storage_key)  # i18n-log: ignore
            return DataOperationResult.SAVE_FAIL
        else:
            return DataOperationResult.SAVE_SUCCESS

    async def save_delayed(self, *, delay: float = 1.0) -> None:
        """
        Schedule a delayed save.

        Multiple calls within the delay period will reset the timer.
        Useful for batching rapid updates.

        Args:
            delay: Delay in seconds before saving (default: 1.0).

        """
        if not self._config_provider.config.use_caches:
            return

        await self._storage.delay_save(
            data_func=lambda: self._content,
            delay=delay,
        )

    @abstractmethod
    def _create_empty_content(self) -> dict[str, Any]:
        """
        Create empty content structure.

        Subclasses override to define their data structure.

        Returns:
            Empty dict structure for this cache type.

        """

    @abstractmethod
    def _process_loaded_content(self, *, data: dict[str, Any]) -> None:
        """
        Process data after loading from storage.

        Subclasses implement to rebuild internal indexes or derived structures.

        Args:
            data: Raw data loaded from storage.

        """


# Helper functions for path/name generation


def get_file_path(*, storage_directory: str, sub_directory: str) -> str:
    """Return the content path."""
    return f"{storage_directory}/{sub_directory}"


def get_file_name(*, central_name: str, file_name: str, ts: datetime | None = None) -> str:
    """Return the content file name."""
    fn = f"{slugify(central_name)}_{file_name}"
    if ts:
        fn += f"_{ts.strftime(FILE_NAME_TS_PATTERN)}"
    return f"{fn}.json"
