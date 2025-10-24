"""Tests for aiohomematic.async_support helpers and decorators."""

from __future__ import annotations

import asyncio
import contextlib
import logging

import pytest

from aiohomematic.async_support import Looper, cancelling, loop_check
import aiohomematic.support as hms


@pytest.mark.asyncio
async def test_looper_block_till_done_deadline_logs(monkeypatch, caplog):
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

    # After deadline 0, task should still be pending and a warning emitted
    assert any("Shutdown timeout reached" in rec.message for rec in caplog.records)

    t.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await t


@pytest.mark.asyncio
async def test_looper_await_and_log_pending_returns_empty_when_done(monkeypatch, caplog):
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


def test_cancelling_helper(monkeypatch):
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


def test_loop_check_decorator_warns_only_when_debug_enabled(monkeypatch, caplog):
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
