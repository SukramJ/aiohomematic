# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Persistent store used to persist Homematic metadata between runs.

This package provides on-disk caches that complement the short-lived, in-memory
caches from aiohomematic.store.dynamic. The goal is to minimize expensive data
retrieval from the backend by storing stable metadata such as device and
paramset descriptions in JSON files inside a dedicated cache directory.

Package structure
-----------------
- base: BasePersistentFile abstract base class
- device: DeviceDescriptionCache for device/channel metadata
- paramset: ParamsetDescriptionCache for parameter descriptions
- session: SessionRecorder for RPC call/response recording

Key behaviors
-------------
- Saves only if caches are enabled and content has changed (hash comparison)
- Uses orjson for fast binary writes and json for reads
- Save/load/clear operations are synchronized via a semaphore

Public API
----------
- DeviceDescriptionCache: Device and channel description storage
- ParamsetDescriptionCache: Paramset description storage
- SessionRecorder: RPC session recording for testing
- cleanup_files: Clean up cache files for a central unit
"""

from __future__ import annotations

import asyncio
import logging
from typing import Final

from aiohomematic.async_support import loop_check
from aiohomematic.const import SUB_DIRECTORY_CACHE, SUB_DIRECTORY_SESSION
from aiohomematic.store.persistent.base import get_file_path
from aiohomematic.store.persistent.device import DeviceDescriptionCache
from aiohomematic.store.persistent.paramset import ParamsetDescriptionCache
from aiohomematic.store.persistent.session import SessionRecorder
from aiohomematic.support import delete_file

_LOGGER: Final = logging.getLogger(__name__)

__all__ = [
    "DeviceDescriptionCache",
    "ParamsetDescriptionCache",
    "SessionRecorder",
    "cleanup_files",
]


@loop_check
def cleanup_files(*, central_name: str, storage_directory: str) -> None:
    """Clean up the used files."""
    loop = asyncio.get_running_loop()
    cache_dir = get_file_path(storage_directory=storage_directory, sub_directory=SUB_DIRECTORY_CACHE)
    loop.run_in_executor(None, delete_file, cache_dir, f"{central_name}*.json".lower())
    session_dir = get_file_path(storage_directory=storage_directory, sub_directory=SUB_DIRECTORY_SESSION)
    loop.run_in_executor(None, delete_file, session_dir, f"{central_name}*.json".lower())
