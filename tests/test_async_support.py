"""Tests for the async_support module."""

from __future__ import annotations

import asyncio

import pytest

from aiohomematic.async_support import Looper, cancelling, loop_check


@pytest.mark.asyncio
async def test_block_till_done_waits_for_tasks() -> None:
    """Looper.block_till_done waits for pending tasks to complete."""
    looper = Looper()
    done: list[str] = []

    async def short_job() -> None:
        await asyncio.sleep(0)
        done.append("ok")

    # Create a task directly in the running loop
    looper._async_create_task(short_job(), name="short")  # type: ignore[attr-defined]
    await looper.block_till_done()
    assert done == ["ok"]


@pytest.mark.asyncio
async def test_block_till_done_timeout_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    """Looper.block_till_done logs a warning if wait_time elapses with pending tasks."""
    looper = Looper()

    async def long_job() -> None:
        # Sleep long enough so our explicit wait_time forces timeout and warning
        await asyncio.sleep(10)

    looper._async_create_task(long_job(), name="long")  # type: ignore[attr-defined]

    # Force a very short wait time so we don't actually wait long in tests
    with caplog.at_level("WARNING"):
        await looper.block_till_done(wait_time=0.01)

    # Expect a shutdown timeout warning mentioning a pending task
    assert any("Shutdown timeout reached" in rec.getMessage() for rec in caplog.records)

    # Make sure we clean up the task to not leak between tests
    looper.cancel_tasks()


@pytest.mark.asyncio
async def test_create_task_tracks_and_completes() -> None:
    """Looper.create_task registers tasks and removes them once completed."""
    looper = Looper()

    async def quick() -> str:
        await asyncio.sleep(0)
        return "done"

    # create_task schedules via call_soon_threadsafe; it should add and auto-remove when done
    looper.create_task(target=quick(), name="quick-task")
    await looper.block_till_done()

    # After finishing, internal task set should be empty
    assert len(looper._tasks) == 0  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_async_add_executor_job_returns_result() -> None:
    """async_add_executor_job executes a function in the executor and returns its result."""
    looper = Looper()

    def add(a: int, b: int) -> int:
        return a + b

    fut = looper.async_add_executor_job(add, 2, 3, name="add-job", executor=None)
    result = await fut
    assert result == 5
    await looper.block_till_done()


@pytest.mark.asyncio
async def test_run_coroutine_from_thread() -> None:
    """run_coroutine can be called from a worker thread to execute an async function."""
    looper = Looper()

    async def compute(x: int) -> int:
        await asyncio.sleep(0)
        return x * 2

    # Call run_coroutine from a worker thread to avoid blocking the running loop thread
    def call_sync() -> int:
        return int(looper.run_coroutine(coro=compute(21), name="compute"))

    loop = asyncio.get_running_loop()
    value = await loop.run_in_executor(None, call_sync)
    assert value == 42


@pytest.mark.asyncio
async def test_cancel_tasks_cancels_running() -> None:
    """cancel_tasks cancels all tracked running tasks."""
    looper = Looper()
    cancelled: dict[str, bool] = {"flag": False}

    async def slow() -> None:
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            cancelled["flag"] = True
            raise

    looper._async_create_task(slow(), name="slow")  # type: ignore[attr-defined]
    # Ensure the task has a chance to start
    await asyncio.sleep(0)

    looper.cancel_tasks()
    # Give the loop a chance to process the cancellation
    await looper.block_till_done(wait_time=0.1)
    assert cancelled["flag"] is True


@pytest.mark.asyncio
async def test_cancelling_utility() -> None:
    """cancelling() reports True for a task that has been cancelled."""

    # Create a task and cancel it; cancelling() should then report True
    async def sleeper() -> None:
        await asyncio.sleep(10)

    task = asyncio.create_task(sleeper())
    # Give the task a moment to start
    await asyncio.sleep(0)
    task.cancel()
    # In Py3.11+ Task has .cancelling() which returns number of times cancelled (>0 truthy)
    assert cancelling(task=task) is True
    # Cleanup
    with pytest.raises(asyncio.CancelledError):
        await task


def test_loop_check_warns_when_no_loop_and_debug(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """loop_check warns when called without a running loop if debug is enabled."""
    # Force debug_enabled() to return True so decorator returns the wrapper that checks the loop

    monkeypatch.setattr("aiohomematic.support.debug_enabled", lambda: True)

    # Redefine a function with the decorator under forced debug-enabled environment
    @loop_check
    def my_func() -> str:
        return "x"

    # Call outside of a running event loop
    with caplog.at_level("WARNING"):
        assert my_func() == "x"

    # Should have warned about missing event loop
    assert any("must run in the event_loop" in rec.getMessage() for rec in caplog.records)

    # Now ensure that when debug is disabled, the decorator returns the original function (no warning)
    monkeypatch.setattr("aiohomematic.support.debug_enabled", lambda: False)

    @loop_check
    def my_func2() -> str:
        return "y"

    with caplog.at_level("WARNING"):
        assert my_func2() == "y"
    # No additional warning should be generated for the second function call
    assert not any("my_func2" in rec.getMessage() for rec in caplog.records)
