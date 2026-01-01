# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for aiohomematic.async_support."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from concurrent.futures import CancelledError as FutCancelledError
import contextlib
import logging
from time import monotonic

import pytest

import aiohomematic.async_support as asupp
from aiohomematic.async_support import Looper, cancelling, loop_check
import aiohomematic.support as hms


class TestLooper:
    """Test Looper task management and execution."""

    @pytest.mark.asyncio
    async def test__async_create_task_tracks_and_removes_tasks(self, caplog: pytest.LogCaptureFixture) -> None:
        """_async_create_task should add the task to tracking and remove it when done."""
        looper = asupp.Looper()

        async def do_work():
            await asyncio.sleep(0)
            return "ok"

        # Create task via internal helper to assert tracking
        t = looper._async_create_task(do_work(), name="work")  # noqa: SLF001
        assert t in looper._tasks  # noqa: SLF001
        assert await t == "ok"
        # After completion the done handler should have removed the task
        assert t not in looper._tasks  # noqa: SLF001

    @pytest.mark.asyncio
    async def test__await_and_log_pending_deadline_crossed_during_loop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Force _await_and_log_pending to hit the branch where deadline is crossed during the wait."""
        looper = asupp.Looper()

        # Create a simple never-ending task to keep it pending
        async def never():
            await asyncio.sleep(10)

        t = looper._async_create_task(never(), name="never")  # noqa: SLF001

        # Prepare a controllable monotonic() that simulates time progression.
        times = [0.0, 0.5, 2.0]  # start, before wait (remaining ~1.5 -> timeout 1), after wait (>= deadline)

        def fake_monotonic() -> float:
            return times.pop(0)

        monkeypatch.setattr(asupp, "monotonic", fake_monotonic)

        # Patch asyncio.wait to return immediately, leaving the task pending
        async def fake_wait(pending: Iterable[asyncio.Future], timeout: float):  # noqa: ARG001
            return set(), set(pending)

        monkeypatch.setattr(asyncio, "wait", fake_wait)

        deadline = asupp.monotonic() + 2.0
        pending = await looper._await_and_log_pending(pending=[t], deadline=deadline)  # noqa: SLF001

        # We should have returned the pending set when deadline crossed during the loop
        assert t in pending

        # Cleanup
        t.cancel()
        with pytest.raises(asyncio.CancelledError):
            await t

    @pytest.mark.asyncio
    async def test__await_and_log_pending_deadline_reached_during_wait_returns_pending(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """_await_and_log_pending should return pending when the deadline is reached during the wait period."""
        looper = asupp.Looper()

        async def long():
            await asyncio.sleep(2)

        t = looper._async_create_task(long(), name="long")  # noqa: SLF001

        dl = monotonic() + 1.0
        with caplog.at_level(logging.DEBUG):
            pending = await looper._await_and_log_pending(pending=[t], deadline=dl)  # noqa: SLF001

        # Deadline should have been reached during the wait, and task still pending
        assert t in pending
        # Cleanup the task
        t.cancel()
        with pytest.raises(asyncio.CancelledError):
            await t

    @pytest.mark.asyncio
    async def test__await_and_log_pending_empty_pending_hits_final_return(self) -> None:
        """Calling _await_and_log_pending with no pending should hit the final return outside the loop."""
        looper = asupp.Looper()
        out = await looper._await_and_log_pending(pending=[], deadline=asupp.monotonic() + 1.0)  # noqa: SLF001
        assert out == set()

    @pytest.mark.asyncio
    async def test_async_add_executor_job_tracks_and_finishes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """async_add_executor_job should track the future and untrack it when done."""
        looper = asupp.Looper()

        def compute(x):
            return x * 2

        future = looper.async_add_executor_job(compute, 5, name="compute")
        # Should be tracked until done
        assert future in looper._tasks  # noqa: SLF001
        assert await future == 10
        # After completion the done handler should have removed it
        assert future not in looper._tasks  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_block_till_done_debug_logging_no_deadline(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """
        block_till_done without deadline should emit debug logs after exceeding BLOCK_LOG_TIMEOUT.

        We monkeypatch BLOCK_LOG_TIMEOUT to a tiny value to avoid waiting; then verify that debug logs
        indicating waiting for tasks are published.
        """
        # Make timeout very small to trigger the debug logging quickly
        monkeypatch.setattr(asupp, "BLOCK_LOG_TIMEOUT", 0.01)
        looper = asupp.Looper()

        # Create a task that outlives a few iterations
        async def sleeper():
            await asyncio.sleep(0.2)

        t = looper._async_create_task(sleeper(), name="sleeper")  # noqa: SLF001

        with caplog.at_level(logging.DEBUG):
            await looper.block_till_done()

        # Expect at least one debug-style message from either outer or inner waiter
        assert any(("Waiting for task" in rec.message) or ("Waited" in rec.message) for rec in caplog.records)
        # Ensure task is done and no longer tracked
        assert t.done()
        assert t not in looper._tasks  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_block_till_done_logs_after_inner_wait(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Hit the branch where block_till_done logs pending tasks after the inner wait call returns pending."""
        looper = asupp.Looper()

        async def never():
            await asyncio.sleep(10)

        t = looper._async_create_task(never(), name="never2")  # noqa: SLF001

        # Control time: initial now=0.0, later 1.0 (<deadline=2.0), after inner wait 2.0 (>=deadline)
        times = [0.0, 1.0, 2.0]

        def fake_monotonic() -> float:
            return times.pop(0)

        monkeypatch.setattr(asupp, "monotonic", fake_monotonic)

        # Force inner awaiter to return the pending set immediately
        async def fake_await_and_log_pending(*, pending, deadline):  # noqa: ARG001
            return set(pending)

        monkeypatch.setattr(looper, "_await_and_log_pending", fake_await_and_log_pending)  # noqa: SLF001

        with caplog.at_level(logging.WARNING):
            await looper.block_till_done(wait_time=2.0)

        assert any("Shutdown timeout reached; task still pending" in rec.message for rec in caplog.records)

        t.cancel()
        with pytest.raises(asyncio.CancelledError):
            await t

    @pytest.mark.asyncio
    async def test_block_till_done_outer_debug_logging_no_deadline(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """
        Trigger the outer debug logging path ("Waiting for task") without a deadline.

        We simulate quick loop iterations by monkeypatching _await_and_log_pending to return
        immediately and manipulate time and BLOCK_LOG_TIMEOUT so the outer loop crosses the
        threshold and publishes the debug logs.
        """
        looper = asupp.Looper()

        async def never():
            await asyncio.sleep(10)

        t = looper._async_create_task(never(), name="never3")  # noqa: SLF001

        # Make BLOCK_LOG_TIMEOUT tiny
        monkeypatch.setattr(asupp, "BLOCK_LOG_TIMEOUT", 0.01)

        # Time progression: first assignment to start_time is non-zero, then exceed threshold
        times = [0.001, 0.02, 0.06]

        def fake_monotonic() -> float:
            # Return last value repeatedly once the scripted timeline is exhausted
            return times.pop(0) if len(times) > 1 else times[0]

        monkeypatch.setattr(asupp, "monotonic", fake_monotonic)

        # Make inner waiter return immediately. First three calls return the pending set
        # to drive the outer-loop timing state machine to the debug-logging branch.
        # On the fourth call, cancel the task and return empty to let the loop exit cleanly.
        call_count = 0

        async def fake_waiter(*, pending, deadline):  # noqa: ARG001
            nonlocal call_count
            call_count += 1
            if call_count < 4:
                return set(pending)
            # After we've crossed the BLOCK_LOG_TIMEOUT and logged, cancel to finish.
            t.cancel()
            return set()

        monkeypatch.setattr(looper, "_await_and_log_pending", fake_waiter)  # noqa: SLF001

        with caplog.at_level(logging.DEBUG):
            await looper.block_till_done()

        assert any("Waiting for task:" in rec.message for rec in caplog.records)

        t.cancel()
        with pytest.raises(asyncio.CancelledError):
            await t

    @pytest.mark.asyncio
    async def test_cancel_tasks_cancels_active_tasks(self) -> None:
        """cancel_tasks should cancel all running tasks tracked by the Looper."""
        looper = asupp.Looper()

        started = asyncio.Event()
        cancelled = asyncio.Event()

        async def never():
            started.set()
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:  # pragma: no cover - behavior validation
                cancelled.set()
                raise

        t = looper._async_create_task(never(), name="never")  # noqa: SLF001
        await asyncio.wait_for(started.wait(), timeout=1)
        looper.cancel_tasks()
        with contextlib.suppress(asyncio.CancelledError):
            await t
        assert cancelled.is_set()

    @pytest.mark.asyncio
    async def test_cancel_tasks_skips_already_cancelled_task(self) -> None:
        """Ensure cancel_tasks checks task.cancelled() and does not call cancel() if already cancelled."""
        looper = asupp.Looper()

        async def sleeper():
            await asyncio.sleep(10)

        t = looper._async_create_task(sleeper(), name="sleep")  # noqa: SLF001
        # Cancel it before calling cancel_tasks
        t.cancel()

        # Should not raise and should leave task in cancelled state
        looper.cancel_tasks()
        # Let cancellation propagate and mark task as cancelled
        with pytest.raises(asyncio.CancelledError):
            await t
        assert t.cancelled()

    @pytest.mark.asyncio
    async def test_create_task_cancelled_error_logs_and_returns(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Looper.create_task should catch CancelledError from call_soon_threadsafe and only log debug."""
        looper = asupp.Looper()

        def raise_cancel(*args, **kwargs):  # noqa: ARG001
            raise FutCancelledError

        monkeypatch.setattr(looper._loop, "call_soon_threadsafe", raise_cancel)  # noqa: SLF001

        async def noop():
            pass

        with caplog.at_level(logging.DEBUG):
            # Should not raise, just log and return None
            looper.create_task(target=noop(), name="x")

        assert any("create_task: task cancelled for x" in rec.message for rec in caplog.records)

    @pytest.mark.asyncio
    async def test_create_task_schedules_from_threadsafe_and_runs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """create_task should call loop.call_soon_threadsafe to schedule _async_create_task."""
        looper = asupp.Looper()
        called: dict[str, int] = {"count": 0}

        # Patch the loop to count call_soon_threadsafe invocations
        real_call_soon_threadsafe = looper._loop.call_soon_threadsafe  # noqa: SLF001

        def wrapper(callback, *args):
            called["count"] += 1
            return real_call_soon_threadsafe(callback, *args)

        monkeypatch.setattr(looper._loop, "call_soon_threadsafe", wrapper)  # noqa: SLF001

        done = asyncio.Event()

        async def do_work():
            done.set()

        looper.create_task(target=do_work(), name="ct")
        await asyncio.wait_for(done.wait(), timeout=1)
        assert called["count"] == 1

    @pytest.mark.asyncio
    async def test_looper_await_and_log_pending_returns_empty_when_done(self, monkeypatch, caplog):
        """_await_and_log_pending should return empty set once tasks complete."""
        looper = Looper()

        async def done_soon():
            await asyncio.sleep(0)
            return 1

        t = asyncio.create_task(done_soon(), name="soon")
        looper._tasks.add(t)  # noqa: SLF001

        # No deadline; should wait and tasks finish; returns empty set
        pending = await looper._await_and_log_pending(pending=[t], deadline=None)  # noqa: SLF001
        assert pending == set()

    @pytest.mark.asyncio
    async def test_looper_block_till_done_deadline_logs(self, monkeypatch, caplog):
        """Looper.block_till_done should log a warning when deadline is reached."""
        loop = asyncio.get_event_loop()
        looper = Looper()

        # Create a never-ending task to ensure it's pending
        async def never():
            await asyncio.sleep(10)

        # Use internal method to add a task directly into tracking
        t = loop.create_task(never(), name="never")
        looper._tasks.add(t)  # noqa: SLF001

        with caplog.at_level(logging.WARNING):
            # wait_time small to trigger deadline path quickly
            await looper.block_till_done(wait_time=0.0)

        # After deadline 0, task should still be pending and a warning published
        assert any("Shutdown timeout reached" in rec.message for rec in caplog.records)

        t.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await t

    @pytest.mark.asyncio
    async def test_run_coroutine_returns_result(self) -> None:
        """run_coroutine should return the coroutine result when loop is running."""
        looper = asupp.Looper()

        async def add(a, b):
            await asyncio.sleep(0)
            return a + b

        # Since Looper stores the current get_event_loop during init, use that loop
        result = await asyncio.get_running_loop().run_in_executor(
            None, lambda: looper.run_coroutine(coro=add(1, 2), name="add")
        )
        assert result == 3


class TestCancellingHelper:
    """Test cancelling helper function."""

    def test_cancelling_helper(self, monkeypatch):
        """cancelling() should use Task.cancelling() when available."""

        # Use a simple dummy object to avoid needing a running event loop (Python 3.14+)
        class Dummy:
            pass

        f = Dummy()

        # Create a fake cancelling method
        class Fake:
            def __call__(self):
                return True

        setattr(f, "cancelling", Fake())
        assert cancelling(task=f) is True

    def test_cancelling_returns_false_when_attribute_missing(self) -> None:
        """cancelling() should return False if the task has no cancelling attribute."""

        class Dummy:
            pass

        dummy = Dummy()
        assert asupp.cancelling(task=dummy) is False


class TestLoopCheckDecorator:
    """Test loop_check decorator warnings."""

    def test_loop_check_decorator_warns_only_when_debug_enabled(self, monkeypatch, caplog):
        """loop_check decorator should warn only once and only in debug mode."""
        # Ensure debug disabled, no warning
        monkeypatch.setattr(hms, "debug_enabled", lambda: False)

        calls = {}

        @loop_check
        def f(x):
            calls["x"] = x
            return x + 1

        with caplog.at_level(logging.WARNING):
            assert f(1) == 2
            assert not any("must run in the event_loop" in rec.message for rec in caplog.records)

        # Enable debug and ensure warning when no loop running
        monkeypatch.setattr(hms, "debug_enabled", lambda: True)

        caplog.clear()
        with caplog.at_level(logging.WARNING):
            assert f(2) == 3
            assert any("must run in the event_loop" in rec.message for rec in caplog.records)

        # Call again to ensure the one-time warning behavior
        caplog.clear()
        with caplog.at_level(logging.WARNING):
            assert f(3) == 4
            # No additional warning for same function
            assert not any("must run in the event_loop" in rec.message for rec in caplog.records)
