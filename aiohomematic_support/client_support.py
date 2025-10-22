"""Helpers for tests."""

from __future__ import annotations

import asyncio
from collections import defaultdict
import json
import logging
import os
from typing import Any
import zipfile

from aiohomematic.const import UTF_8, DataOperationResult
from aiohomematic.store.persistent import _freeze_params, _unfreeze_params

_LOGGER = logging.getLogger(__name__)


async def get_session_player(*, file_path: str) -> SessionPlayer:
    """Provide a SessionPlayer preloaded from the randomized full session JSON file."""
    player = SessionPlayer(file_id=file_path)
    await player.load(file_path=file_path)
    return player


class SessionPlayer:
    """Player for sessions."""

    _store: dict[str, dict[str, dict[str, dict[str, dict[int, Any]]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(dict))))
    )

    def __init__(self, *, file_id: str) -> None:
        """Initialize the session recorder."""
        self._file_id = file_id

    async def load(self, *, file_path: str) -> DataOperationResult:
        """
        Load data from disk into the dictionary.

        Supports plain JSON files and ZIP archives containing a JSON file.
        When a ZIP archive is provided, the first JSON member inside the archive
        will be loaded.
        """

        if self._store[self._file_id]:
            return DataOperationResult.NO_LOAD

        if not os.path.exists(file_path):
            return DataOperationResult.NO_LOAD

        def _perform_load() -> DataOperationResult:
            try:
                if zipfile.is_zipfile(file_path):
                    with zipfile.ZipFile(file_path, mode="r") as zf:
                        # Prefer json files; pick the first .json entry if available
                        if not (json_members := [n for n in zf.namelist() if n.lower().endswith(".json")]):
                            return DataOperationResult.LOAD_FAIL
                        raw = zf.read(json_members[0]).decode(UTF_8)
                        data = json.loads(raw)
                else:
                    with open(file=file_path, encoding=UTF_8) as file_pointer:
                        data = json.loads(file_pointer.read())

                self._store[self._file_id] = data
            except (json.JSONDecodeError, zipfile.BadZipFile, UnicodeDecodeError, OSError):
                return DataOperationResult.LOAD_FAIL
            return DataOperationResult.LOAD_SUCCESS

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _perform_load)

    def get_latest_response_by_method(self, *, rpc_type: str, method: str) -> list[tuple[Any, Any]]:
        """Return latest non-expired responses for a given (rpc_type, method)."""
        result: list[Any] = []
        # Access store safely to avoid side effects from creating buckets.
        if not (bucket_by_method := self._store[self._file_id].get(rpc_type)):
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
        # Access store safely to avoid side effects from creating buckets.
        if not (bucket_by_method := self._store[self._file_id].get(rpc_type)):
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
