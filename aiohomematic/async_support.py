# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Module with support for loop interaction."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Collection
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures._base import CancelledError
import contextlib
from functools import wraps
import logging
from time import monotonic
from typing import Any, Final, cast

from aiohomematic.const import BLOCK_LOG_TIMEOUT
from aiohomematic.exceptions import AioHomematicException
import aiohomematic.support as hms
from aiohomematic.support import extract_exc_args
from aiohomematic.type_aliases import AsyncTaskFactoryAny, CallableAny, CoroutineAny

_LOGGER: Final = logging.getLogger(__name__)


class Looper:
    """Helper class for event loop support."""

    def __init__(self) -> None:
        """Init the loop helper."""
        self._tasks: Final[set[asyncio.Future[Any]]] = set()
        self._loop = asyncio.get_event_loop()

    def async_add_executor_job[T](
        self,
        target: Callable[..., T],
        *args: Any,
        name: str,
        executor: ThreadPoolExecutor | None = None,
    ) -> asyncio.Future[T]:
        """Add an executor job from within the event_loop."""
        try:
            task = self._loop.run_in_executor(executor, target, *args)
            self._tasks.add(task)
            task.add_done_callback(self._tasks.remove)
        except (TimeoutError, CancelledError) as err:  # pragma: no cover
            message = f"async_add_executor_job: task cancelled for {name} [{extract_exc_args(exc=err)}]"
            _LOGGER.debug(message)
            raise AioHomematicException(message) from err
        return task

    async def block_till_done(self, *, wait_time: float | None = None) -> None:
        """
        Block until all pending work is done.

        If wait_time is set, stop waiting after the given number of seconds and log remaining tasks.
        """
        # To flush out any call_soon_threadsafe
        await asyncio.sleep(0)
        start_time: float | None = None
        deadline: float | None = (monotonic() + wait_time) if wait_time is not None else None
        current_task = asyncio.current_task()
        while tasks := [task for task in self._tasks if task is not current_task and not cancelling(task=task)]:
            # If we have a deadline and have exceeded it, log remaining tasks and break
            if deadline is not None and monotonic() >= deadline:
                for task in tasks:
                    _LOGGER.warning(  # i18n-log: ignore
                        "Shutdown timeout reached; task still pending: %s", task
                    )
                break

            pending_after_wait = await self._await_and_log_pending(pending=tasks, deadline=deadline)

            # If deadline has been reached and tasks are still pending, log and break
            if deadline is not None and monotonic() >= deadline and pending_after_wait:
                for task in pending_after_wait:
                    _LOGGER.warning(  # i18n-log: ignore
                        "Shutdown timeout reached; task still pending: %s", task
                    )
                break

            if start_time is None:
                # Avoid calling monotonic() until we know
                # we may need to start logging blocked tasks.
                start_time = 0
            elif start_time == 0:
                # If we have waited twice then we set the start
                # time
                start_time = monotonic()
            elif monotonic() - start_time > BLOCK_LOG_TIMEOUT:
                # We have waited at least three loops and new tasks
                # continue to block. At this point we start
                # logging all waiting tasks.
                for task in tasks:
                    _LOGGER.debug("Waiting for task: %s", task)

    def cancel_tasks(self) -> None:
        """Cancel running tasks."""
        for task in self._tasks.copy():
            if not task.cancelled():
                task.cancel()

    def create_task(self, *, target: CoroutineAny | AsyncTaskFactoryAny, name: str) -> None:
        """
        Schedule a coroutine to run in the loop.

        Accepts either an already-created coroutine object or a zero-argument
        callable that returns a coroutine. The callable form defers coroutine
        creation until inside the event loop, which avoids "was never awaited"
        warnings if callers only inspect the parameters (e.g. in tests).
        """
        try:
            self._loop.call_soon_threadsafe(self._async_create_task, target, name)
        except CancelledError:
            # Scheduling failed; if a coroutine object was provided, close it to
            # avoid 'was never awaited' warnings.
            if asyncio.iscoroutine(target):
                with contextlib.suppress(Exception):
                    getattr(target, "close", lambda: None)()
            _LOGGER.debug("create_task: task cancelled for %s", name)
            return

    def run_coroutine(self, *, coro: CoroutineAny, name: str) -> Any:
        """Call coroutine from sync."""
        try:
            return asyncio.run_coroutine_threadsafe(coro, self._loop).result()
        except CancelledError:  # pragma: no cover
            _LOGGER.debug(
                "run_coroutine: coroutine interrupted for %s",
                name,
            )
            return None

    def _async_create_task(  # kwonly: disable
        self, target: CoroutineAny | AsyncTaskFactoryAny, name: str
    ) -> asyncio.Task[Any]:
        """Create a task from within the event loop. Must be run in the event loop."""
        # If target is a callable, call it here to create the coroutine inside the loop
        coro: CoroutineAny = target if asyncio.iscoroutine(target) else target()
        task = self._loop.create_task(coro, name=name)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.remove)
        return task

    async def _await_and_log_pending(
        self, *, pending: Collection[asyncio.Future[Any]], deadline: float | None
    ) -> set[asyncio.Future[Any]]:
        """
        Await and log tasks that take a long time, respecting an optional deadline.

        Returns the set of pending tasks if the deadline has been reached (or zero timeout),
        allowing the caller to decide about timeout logging. Returns an empty set if no tasks are pending.
        """
        wait_time = 0.0
        pending_set: set[asyncio.Future[Any]] = set(pending)
        while pending_set:
            if deadline is None:
                timeout = BLOCK_LOG_TIMEOUT
            else:
                remaining = int(max(0.0, deadline - monotonic()))
                if (timeout := min(BLOCK_LOG_TIMEOUT, remaining)) == 0.0:
                    # Deadline reached; return current pending to caller for warning log
                    return pending_set
            done, still_pending = await asyncio.wait(pending_set, timeout=timeout)
            if not (pending_set := set(still_pending)):
                return set()
            wait_time += timeout
            for task in pending_set:
                _LOGGER.debug("Waited %s seconds for task: %s", wait_time, task)
            # If the deadline was reached during the wait, let caller handle warning
            if deadline is not None and monotonic() >= deadline:
                return pending_set
        return set()


def cancelling(*, task: asyncio.Future[Any]) -> bool:
    """Return True if task is cancelling."""
    return bool((cancelling_ := getattr(task, "cancelling", None)) and cancelling_())


def loop_check[**P, R](func: Callable[P, R]) -> Callable[P, R]:
    """
    Annotation to mark method that must be run within the event loop.

    Always wraps the function, but only performs loop checks when debug is enabled.
    This allows tests to monkeypatch aiohomematic.support.debug_enabled at runtime.
    """

    _with_loop: set[CallableAny] = set()

    @wraps(func)
    def wrapper_loop_check(*args: P.args, **kwargs: P.kwargs) -> R:
        """Wrap loop check."""
        return_value = func(*args, **kwargs)

        # Only perform the (potentially expensive) loop check when debug is enabled.
        if hms.debug_enabled():
            try:
                asyncio.get_running_loop()
                loop_running = True
            except Exception:
                loop_running = False

            if not loop_running and func not in _with_loop:
                _with_loop.add(func)
                _LOGGER.error(  # i18n-log: ignore
                    "Method %s must run in the event_loop. No loop detected.",
                    func.__name__,
                )

        return return_value

    setattr(func, "_loop_check", True)
    return cast(Callable[P, R], wrapper_loop_check)
