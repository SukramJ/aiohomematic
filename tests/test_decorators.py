"""
Tests for aiohomematic.decorators module to raise coverage above 95%.

These tests cover:
- sync and async behavior of @inspector including exception handling, re-raise logic,
  RequestContext handling, performance logging, and lib_service attribute exposure.
- get_service_calls discovery and caching of service methods.
- measure_execution_time for sync and async functions including performance log contents.
All tests include a docstring.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import pytest

from aiohomematic.context import RequestContext, is_in_service, reset_request_context, set_request_context
import aiohomematic.decorators as dec_mod
from aiohomematic.decorators import (
    _LOGGER_PERFORMANCE,  # type: ignore[attr-defined]
    get_service_calls,
    inspector,
    measure_execution_time,
)
from aiohomematic.exceptions import BaseHomematicException


class DummyContext:
    """Simple object providing a string representation and optional LogContextMixin-like attr."""

    def __init__(self, name: str, log_context: Any | None = None) -> None:
        """Initialize with name and optional LogContextMixin-like attr."""
        self.name = name
        # Some code paths check for .log_context attribute via isinstance(LogContextMixin),
        # but presence is sufficient for our tests as we don't assert on logging extras here.
        self.log_context = log_context

    def __str__(self) -> str:
        """Return string representation."""
        return f"Dummy({self.name})"


class TestInspectorDecorator:
    """Test cases for @inspector decorator."""

    @pytest.mark.asyncio
    async def test_inspector_async_success_and_exception_handling(self, caplog: pytest.LogCaptureFixture) -> None:
        """Async wrapper supports return value, performance logging, and suppressed Homematic error."""
        caplog.set_level(logging.INFO)
        _LOGGER_PERFORMANCE.setLevel(logging.DEBUG)

        class MyError(BaseHomematicException):
            pass

        class Service:
            @inspector(measure_performance=True)
            async def add(self, ctx: DummyContext, a: int, b: int) -> int:
                await asyncio.sleep(0)
                return a + b

            @inspector(re_raise=False, no_raise_return=-1)
            async def fail(self, ctx: DummyContext) -> int:
                await asyncio.sleep(0)
                raise MyError("hm")

        svc = Service()
        res = await svc.add(DummyContext("E"), 1, 2)
        assert res == 3

        # Performance message published
        msgs = caplog.text
        assert "ADD" in msgs

        # Homematic error suppressed
        assert await svc.fail(DummyContext("F")) == -1

        # Generic async exception re-raises regardless of re_raise
        class Service2:
            @inspector(re_raise=False)
            async def explode(self, ctx: DummyContext) -> None:
                await asyncio.sleep(0)
                raise RuntimeError("async-boom")

        with pytest.raises(RuntimeError):
            await Service2().explode(DummyContext("E2"))

    def test_inspector_sub_service_generic_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Generic exception inside sub-service should be re-raised and not logged (token None branch)."""

        logged: list[Any] = []

        def fake_log_boundary_error(**kwargs: Any) -> None:  # type: ignore[no-redef]
            logged.append(True)

        monkeypatch.setattr(dec_mod, "log_boundary_error", fake_log_boundary_error)

        class Service:
            @inspector(re_raise=False)
            def inner(self, ctx: DummyContext) -> None:
                raise RuntimeError("boom")

        # Simulate already being in a service call by setting request context
        ctx = RequestContext(operation="service:outer")
        token = set_request_context(ctx)
        try:
            with pytest.raises(RuntimeError):
                Service().inner(DummyContext("D2"))
        finally:
            reset_request_context(token)

        assert not logged

    def test_inspector_sub_service_skips_logging(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When already inside a service call, exceptions should skip logging but still be handled."""

        logged: list[Any] = []

        def fake_log_boundary_error(**kwargs: Any) -> None:  # type: ignore[no-redef]
            logged.append(True)

        monkeypatch.setattr(dec_mod, "log_boundary_error", fake_log_boundary_error)

        class MyError(BaseHomematicException):
            pass

        class Service:
            @inspector(re_raise=False, no_raise_return=None)
            def inner(self, ctx: DummyContext) -> None:
                raise MyError("hm error")

        # Simulate a nested service call by pre-setting request context
        ctx = RequestContext(operation="service:outer")
        token = set_request_context(ctx)
        try:
            Service().inner(DummyContext("D"))
        finally:
            reset_request_context(token)

        # No logging expected because it was a sub-service call
        assert not logged

    def test_inspector_sync_generic_exception_always_reraises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Non-homematic exceptions are re-raised regardless of re_raise flag."""

        class Service:
            @inspector(re_raise=False, no_raise_return="nope")
            def boom(self, ctx: DummyContext) -> str:
                raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            Service().boom(DummyContext("C"))

    def test_inspector_sync_homematic_exception_suppressed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """BaseHomematicException should be suppressed when re_raise=False and return fallback value."""

        calls: list[tuple[Any, ...]] = []

        # Spy on boundary error helper to ensure it is called for top-level service calls
        def fake_log_boundary_error(**kwargs: Any) -> None:  # type: ignore[no-redef]
            calls.append((kwargs.get("boundary"), kwargs.get("action")))

        monkeypatch.setattr(dec_mod, "log_boundary_error", fake_log_boundary_error)

        class MyError(BaseHomematicException):
            pass

        class Service:
            @inspector(re_raise=False, no_raise_return="fallback")
            def will_fail(self, ctx: DummyContext) -> str:
                raise MyError("hm error")

        out = Service().will_fail(DummyContext("B"))
        assert out == "fallback"
        # Logged exactly once at the top level
        assert calls and calls[0][0] == "service" and calls[0][1] == "will_fail"

    def test_inspector_sync_success_and_attribute(self, caplog: pytest.LogCaptureFixture) -> None:
        """@inspector wraps sync call, returns value, exposes lib_service and can log performance."""
        caplog.set_level(logging.INFO)
        # Enable performance path
        _LOGGER_PERFORMANCE.setLevel(logging.DEBUG)

        class Service:
            @inspector(measure_performance=True)
            def do_it(self, ctx: DummyContext, x: int) -> int:
                return x * 2

        svc = Service()
        assert getattr(svc.do_it, "lib_service", False) is True

        # Ensure we're not in a service call to test token handling and logging
        assert is_in_service() is False

        ctx = DummyContext("A")
        result = svc.do_it(ctx, 3)
        assert result == 6

        # Performance logger should emit an INFO line mentioning function name and caller string
        msgs = caplog.text
        assert "DO_IT" in msgs


class TestServiceCalls:
    """Test cases for get_service_calls discovery and caching."""

    def test_get_service_calls_and_cache(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_service_calls should find lib_service-marked methods and use cache on subsequent calls."""

        class Container:
            @inspector
            def first(self) -> str:  # type: ignore[no-redef]
                return "first"

            def second(self) -> str:
                return "second"

        c = Container()

        # First discovery
        mapping1 = get_service_calls(c)
        assert set(mapping1.keys()) == {"first"}

        # Now mutate the class to add another service and ensure the cached result is returned
        def new(self) -> str:
            return "new"

        Container.third = inspector(new)  # type: ignore[attr-defined]

        mapping2 = get_service_calls(c)
        assert set(mapping2.keys()) == {"first"}  # still cached names, 'third' ignored due to cache

        # Clear cache and ensure new method is discovered
        dec_mod._SERVICE_CALLS_CACHE.clear()  # type: ignore[attr-defined]
        mapping3 = get_service_calls(c)
        assert set(mapping3.keys()) == {"first", "third"}


class TestMeasureExecutionTime:
    """Test cases for measure_execution_time decorator."""

    @pytest.mark.asyncio
    async def test_measure_execution_time_async(self, caplog: pytest.LogCaptureFixture) -> None:
        """Async variant of measure_execution_time should log and return correct value."""
        caplog.set_level(logging.INFO)
        _LOGGER_PERFORMANCE.setLevel(logging.DEBUG)

        @measure_execution_time
        async def awork(ctx: DummyContext, *, interface: str) -> int:
            await asyncio.sleep(0)
            return 9

        assert await awork(DummyContext("H"), interface="eth0") == 9

        msgs = caplog.text
        assert "AWORK" in msgs and "interface: eth0" in msgs

    def test_measure_execution_time_sync_and_message(self, caplog: pytest.LogCaptureFixture) -> None:
        """measure_execution_time should log performance message and preserve return value for sync def."""
        caplog.set_level(logging.INFO)
        _LOGGER_PERFORMANCE.setLevel(logging.DEBUG)

        @measure_execution_time
        def work(ctx: DummyContext, *, interface_id: str) -> int:
            return 7

        out = work(DummyContext("G"), interface_id="abc")
        assert out == 7

        # Should include function name and interface_id in message
        msgs = caplog.text
        assert "WORK" in msgs and "interface_id: abc" in msgs
