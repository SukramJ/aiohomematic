# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Session recorder for persisting RPC method calls and responses.

This module provides SessionRecorder which records RPC method calls and responses
for test playback, enabling deterministic testing without a live CCU backend.

Data structure (4-level nested dict):
    store[rpc_type][method][frozen_params][timestamp_ms] = response

TTL mechanism:
    - Each entry has a timestamp when it was recorded
    - Entries expire after ttl seconds
    - Expiration is lazy: checked on access/update
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import UTC, datetime
import logging
from typing import Any, Final, Self

from aiohomematic import i18n
from aiohomematic.const import FILE_SESSION_RECORDER, SUB_DIRECTORY_SESSION, RPCType
from aiohomematic.interfaces.central import CentralInfoProtocol, ConfigProviderProtocol, DeviceProviderProtocol
from aiohomematic.interfaces.operations import TaskSchedulerProtocol
from aiohomematic.property_decorators import DelegatedProperty
from aiohomematic.store.persistent.base import BasePersistentFile
from aiohomematic.store.serialization import cleanup_params_for_session, freeze_params, unfreeze_params
from aiohomematic.support import extract_exc_args

_LOGGER: Final = logging.getLogger(__name__)


def _now() -> int:
    """Return current UTC time as epoch seconds (int)."""
    return int(datetime.now(tz=UTC).timestamp())


class SessionRecorder(BasePersistentFile):
    """
    Session recorder for central unit.

    Purpose:
        Records RPC method calls and responses for test playback.
        This enables deterministic testing without a live CCU backend.

    Data structure (4-level nested dict):
        store[rpc_type][method][frozen_params][timestamp_ms] = response

        - rpc_type: "xml" or "json" (the RPC protocol used)
        - method: RPC method name (e.g., "listDevices", "getValue")
        - frozen_params: Parameters frozen to string via freeze_params()
        - timestamp_ms: Integer timestamp in milliseconds (for TTL tracking)
        - response: The actual RPC response to replay

    TTL (Time-To-Live) mechanism:
        - Each entry has a timestamp when it was recorded
        - Entries expire after _ttl seconds
        - Expiration is lazy: checked on access/update, not via background task
        - Optional refresh_on_get: Reading an entry extends its TTL

    Why nested defaultdicts?
        Avoids explicit bucket creation when recording new entries.
        store[rpc_type][method][params] automatically creates intermediate dicts.

    Cleanup strategy:
        _purge_expired_at() removes expired entries and cleans up empty buckets.
        Important: Uses .get() chains to avoid creating buckets as side effect.
    """

    __slots__ = (
        "_active",
        "_is_recording",
        "_refresh_on_get",
        "_store",
        "_ttl",
    )

    _file_postfix = FILE_SESSION_RECORDER
    _sub_directory = SUB_DIRECTORY_SESSION

    def __init__(
        self,
        *,
        central_info: CentralInfoProtocol,
        config_provider: ConfigProviderProtocol,
        device_provider: DeviceProviderProtocol,
        task_scheduler: TaskSchedulerProtocol,
        active: bool,
        ttl_seconds: float,
        refresh_on_get: bool = False,
    ):
        """Initialize the cache."""
        self._active = active
        if ttl_seconds < 0:
            raise ValueError(i18n.tr(key="exception.store.session_recorder.ttl_positive"))
        self._ttl: Final = float(ttl_seconds)
        self._is_recording: bool = False
        self._refresh_on_get: Final = refresh_on_get
        # Nested defaultdicts auto-create intermediate buckets on write.
        # Structure: rpc_type -> method -> frozen_params -> ts(ms) -> response
        self._store: dict[str, dict[str, dict[str, dict[int, Any]]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(dict))
        )
        super().__init__(
            config_provider=config_provider,
            task_scheduler=task_scheduler,
            central_info=central_info,
            device_provider=device_provider,
            persistent_content=self._store,
        )

    def __repr__(self) -> str:
        """Return the representation."""
        self.cleanup()
        return f"{self.__class__.__name__}({self._store})"

    active: Final = DelegatedProperty[bool](path="_active")

    @property
    def _should_save(self) -> bool:
        """Determine if save operation should proceed."""
        self.cleanup()
        return len(self._store.items()) > 0

    async def activate(
        self, *, on_time: int = 0, auto_save: bool, randomize_output: bool, use_ts_in_file_name: bool
    ) -> bool:
        """Activate the session recorder. Disable after on_time(seconds)."""
        if self._is_recording:
            _LOGGER.info(i18n.tr(key="log.store.session_recorder.activate.already_running"))
            return False
        self._store.clear()
        self._active = True
        if on_time > 0:
            self._task_scheduler.create_task(
                target=self._deactivate_after_delay(
                    delay=on_time,
                    auto_save=auto_save,
                    randomize_output=randomize_output,
                    use_ts_in_file_name=use_ts_in_file_name,
                ),
                name=f"session_recorder_{self._central_info.name}",
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
            _LOGGER.info(i18n.tr(key="log.store.session_recorder.deactivate.already_running"))
            return False
        if delay > 0:
            self._task_scheduler.create_task(
                target=self._deactivate_after_delay(
                    delay=delay,
                    auto_save=auto_save,
                    randomize_output=randomize_output,
                    use_ts_in_file_name=use_ts_in_file_name,
                ),
                name=f"session_recorder_{self._central_info.name}",
            )
        else:
            self._active = False
            self._is_recording = False
        return True

    def delete(self, *, rpc_type: str, method: str, params: Any) -> bool:
        """
        Delete an entry if it exists. Return True if removed.

        Avoid creating buckets when the target does not exist.
        Clean up empty parent buckets on successful deletion.
        """
        if not (bucket_by_method := self._store.get(rpc_type)):
            return False
        if not (bucket_by_parameter := bucket_by_method.get(method)):
            return False
        if (frozen_param := freeze_params(params=cleanup_params_for_session(params=params))) not in bucket_by_parameter:
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

        Algorithm:
            1. Purge expired entries for this method (lazy cleanup)
            2. Navigate the nested dict safely using .get() to avoid bucket creation
            3. Find the response at the latest timestamp (most recent recording)
            4. Optionally extend TTL by adding a new timestamp (refresh_on_get)

        Why use .get() chains instead of direct indexing?
            Using self._store[rpc_type][method] would auto-create buckets due to
            defaultdict behavior. This is a read operation, so we must not modify
            the store when the entry doesn't exist. The .get() method returns None
            without creating the missing key.

        Latest timestamp selection:
            Multiple timestamps can exist for the same params (from TTL refresh).
            We always return the response at max(timestamps) to get the most recent.
        """
        # Step 1: Remove expired entries before lookup
        self._purge_expired_at(rpc_type=rpc_type, method=method)

        # Step 2: Navigate safely without creating buckets (read-only access)
        if not (bucket_by_method := self._store.get(rpc_type)):
            return default
        if not (bucket_by_parameter := bucket_by_method.get(method)):
            return default
        frozen_param = freeze_params(params=cleanup_params_for_session(params=params))
        if not (bucket_by_ts := bucket_by_parameter.get(frozen_param)):
            return default

        # Step 3: Get response at latest timestamp
        try:
            latest_ts = max(bucket_by_ts.keys())
        except ValueError:
            # Empty bucket (all entries expired)
            return default
        resp = bucket_by_ts[latest_ts]

        # Step 4: TTL refresh - add new timestamp to extend expiry
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
            params = unfreeze_params(frozen_params=frozen_params)

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
        frozen_params = freeze_params(params=cleanup_params_for_session(params=params))

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
        frozen_param = freeze_params(params=cleanup_params_for_session(params=params))
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
        frozen_param = freeze_params(params=params)
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
        """
        Remove expired entries for a given (rpc_type, method) bucket.

        Multi-level cleanup algorithm:
            This method cleans up the 4-level nested structure from bottom to top:
            1. Remove expired timestamps from each params bucket
            2. Remove empty params buckets from the method bucket
            3. Remove empty method bucket from the rpc_type bucket
            4. Remove empty rpc_type bucket from the store

        Critical: No bucket creation
            Uses .get() instead of direct indexing to avoid defaultdict's
            auto-creation of missing buckets. A read/cleanup operation should
            never modify the structure except to remove entries.

        Two-pass deletion pattern:
            For each level, we first collect items to delete, then delete them.
            This avoids "dictionary changed size during iteration" errors.
        """
        # TTL of 0 means entries never expire
        if self._ttl == 0:
            return

        # Navigate safely without creating buckets
        if not (bucket_by_method := self._store.get(rpc_type)):
            return
        if not (bucket_by_parameter := bucket_by_method.get(method)):
            return

        now = _now()
        empty_params: list[str] = []

        # Level 1: Remove expired timestamps from each params bucket
        for p, bucket_by_ts in bucket_by_parameter.items():
            # Collect expired timestamps (two-pass: collect then delete)
            expired_ts = [ts for ts, _r in list(bucket_by_ts.items()) if self._is_expired(ts=ts, now=now)]
            for ts in expired_ts:
                del bucket_by_ts[ts]
            # Track empty params buckets for cleanup
            if not bucket_by_ts:
                empty_params.append(p)

        # Level 2: Remove empty params buckets
        for p in empty_params:
            bucket_by_parameter.pop(p, None)

        # Level 3 & 4: Cascade cleanup of empty parent buckets
        if not bucket_by_parameter:
            bucket_by_method.pop(method, None)
            if not bucket_by_method:
                self._store.pop(rpc_type, None)
