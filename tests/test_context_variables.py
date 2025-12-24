# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Tests for context variables pattern."""

from __future__ import annotations

import asyncio
import logging
import time

import pytest

from aiohomematic.context import (
    RequestContext,
    get_request_context,
    get_request_id,
    request_context,
    reset_request_context,
    set_request_context,
)
from aiohomematic.logging_context import ContextualLoggerAdapter, RequestContextFilter, get_contextual_logger
from aiohomematic.tracing import (
    Span,
    get_current_span,
    get_current_trace_id,
    reset_current_span,
    set_current_span,
    span,
)

# =============================================================================
# REQUEST CONTEXT TESTS
# =============================================================================


class TestRequestContext:
    """Test RequestContext dataclass."""

    def test_custom_request_id(self) -> None:
        """Test custom request_id."""
        ctx = RequestContext(request_id="custom123")
        assert ctx.request_id == "custom123"

    def test_custom_values(self) -> None:
        """Test custom values."""
        ctx = RequestContext(
            operation="set_value",
            device_address="ABC123",
            interface_id="interface-1",
            extra={"key": "value"},
        )
        assert ctx.operation == "set_value"
        assert ctx.device_address == "ABC123"
        assert ctx.interface_id == "interface-1"
        assert ctx.extra == {"key": "value"}

    def test_default_request_id(self) -> None:
        """Test that request_id is auto-generated."""
        ctx = RequestContext()
        assert len(ctx.request_id) == 8
        assert ctx.request_id.isalnum()

    def test_default_values(self) -> None:
        """Test default values."""
        ctx = RequestContext()
        assert ctx.operation == ""
        assert ctx.device_address is None
        assert ctx.interface_id is None
        assert ctx.extra == {}

    def test_elapsed_ms(self) -> None:
        """Test elapsed_ms property."""
        ctx = RequestContext()
        time.sleep(0.01)  # Sleep 10ms
        elapsed = ctx.elapsed_ms
        assert elapsed >= 10  # At least 10ms

    def test_immutable(self) -> None:
        """Test RequestContext is immutable."""
        ctx = RequestContext(operation="test")
        with pytest.raises(AttributeError):
            ctx.operation = "new"  # type: ignore[misc]

    def test_with_device(self) -> None:
        """Test with_device creates new context."""
        ctx = RequestContext(operation="test")
        new_ctx = ctx.with_device(device_address="DEF456")

        assert new_ctx.device_address == "DEF456"
        assert new_ctx.operation == "test"
        assert new_ctx.request_id == ctx.request_id

    def test_with_extra(self) -> None:
        """Test with_extra merges attributes."""
        ctx = RequestContext(extra={"a": 1})
        new_ctx = ctx.with_extra(b=2, c=3)

        assert new_ctx.extra == {"a": 1, "b": 2, "c": 3}
        assert ctx.extra == {"a": 1}  # Original unchanged

    def test_with_operation(self) -> None:
        """Test with_operation creates new context."""
        ctx = RequestContext(operation="old", device_address="ABC123")
        new_ctx = ctx.with_operation(operation="new")

        assert new_ctx.operation == "new"
        assert new_ctx.device_address == "ABC123"
        assert new_ctx.request_id == ctx.request_id
        assert new_ctx is not ctx


class TestRequestContextManager:
    """Test request_context context manager."""

    @pytest.mark.asyncio
    async def test_async_context_manager(self) -> None:
        """Test asynchronous context manager."""
        assert get_request_context() is None

        async with request_context(operation="async_test") as ctx:
            assert get_request_context() is ctx
            assert ctx.operation == "async_test"

        assert get_request_context() is None

    @pytest.mark.asyncio
    async def test_context_propagates_to_coroutines(self) -> None:
        """Test context propagates through async call chain."""

        async def inner_function() -> str:
            ctx = get_request_context()
            return ctx.operation if ctx else "none"

        async with request_context(operation="propagation_test"):
            result = await inner_function()
            assert result == "propagation_test"

    def test_context_with_all_params(self) -> None:
        """Test context with all parameters."""
        with request_context(
            operation="full_test",
            device_address="ABC123",
            interface_id="interface-1",
            custom_key="custom_value",
        ) as ctx:
            assert ctx.operation == "full_test"
            assert ctx.device_address == "ABC123"
            assert ctx.interface_id == "interface-1"
            assert ctx.extra == {"custom_key": "custom_value"}

    def test_nested_contexts(self) -> None:
        """Test nested context managers."""
        with request_context(operation="outer") as outer:
            assert get_request_context() is outer

            with request_context(operation="inner") as inner:
                assert get_request_context() is inner

            assert get_request_context() is outer

        assert get_request_context() is None

    def test_sync_context_manager(self) -> None:
        """Test synchronous context manager."""
        assert get_request_context() is None

        with request_context(operation="test") as ctx:
            assert get_request_context() is ctx
            assert ctx.operation == "test"

        assert get_request_context() is None


class TestContextFunctions:
    """Test context utility functions."""

    def test_get_request_id_no_context(self) -> None:
        """Test get_request_id returns anonymous when no context."""
        assert get_request_id() == "anonymous"

    def test_get_request_id_with_context(self) -> None:
        """Test get_request_id returns ID when context set."""
        with request_context() as ctx:
            assert get_request_id() == ctx.request_id

    def test_set_reset_request_context(self) -> None:
        """Test manual set/reset functions."""
        ctx = RequestContext(operation="manual")
        token = set_request_context(ctx)

        assert get_request_context() is ctx

        reset_request_context(token)
        assert get_request_context() is None


# =============================================================================
# LOGGING CONTEXT TESTS
# =============================================================================


class TestContextualLoggerAdapter:
    """Test ContextualLoggerAdapter."""

    def test_context_without_operation(self) -> None:
        """Test prefix format without operation."""
        adapter = get_contextual_logger(__name__)

        ctx = RequestContext(operation="")
        token = set_request_context(ctx)
        try:
            msg, _ = adapter.process("Test", {})
            assert f"[{ctx.request_id}]" in msg
            assert ":" not in msg.split("]")[0]  # No colon in prefix
        finally:
            reset_request_context(token)

    def test_no_context_no_prefix(self) -> None:
        """Test message unchanged when no context."""
        adapter = get_contextual_logger(__name__)
        msg, kwargs = adapter.process("Test message", {})

        assert msg == "Test message"
        assert kwargs == {}

    def test_with_context_adds_prefix(self) -> None:
        """Test message gets prefix when context set."""
        adapter = get_contextual_logger(__name__)

        with request_context(operation="test_op") as ctx:
            msg, kwargs = adapter.process("Test message", {})

            assert f"[{ctx.request_id}:test_op]" in msg
            assert "Test message" in msg


class TestRequestContextFilter:
    """Test RequestContextFilter."""

    def test_filter_no_context(self) -> None:
        """Test filter adds default values when no context."""
        filter_ = RequestContextFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test",
            args=(),
            exc_info=None,
        )

        result = filter_.filter(record)

        assert result is True
        assert record.request_id == "none"  # type: ignore[attr-defined]
        assert record.operation == "none"  # type: ignore[attr-defined]
        assert record.device_address == "none"  # type: ignore[attr-defined]
        assert record.elapsed_ms == 0.0  # type: ignore[attr-defined]

    def test_filter_with_context(self) -> None:
        """Test filter adds context values."""
        filter_ = RequestContextFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test",
            args=(),
            exc_info=None,
        )

        with request_context(
            operation="test_op",
            device_address="ABC123",
        ) as ctx:
            result = filter_.filter(record)

            assert result is True
            assert record.request_id == ctx.request_id  # type: ignore[attr-defined]
            assert record.operation == "test_op"  # type: ignore[attr-defined]
            assert record.device_address == "ABC123"  # type: ignore[attr-defined]
            assert record.elapsed_ms > 0  # type: ignore[attr-defined]


class TestGetContextualLogger:
    """Test get_contextual_logger factory."""

    def test_logger_name(self) -> None:
        """Test underlying logger has correct name."""
        logger = get_contextual_logger("my.module")
        assert logger.logger.name == "my.module"

    def test_returns_adapter(self) -> None:
        """Test returns ContextualLoggerAdapter."""
        logger = get_contextual_logger(__name__)
        assert isinstance(logger, ContextualLoggerAdapter)


# =============================================================================
# TRACING TESTS
# =============================================================================


class TestSpan:
    """Test Span dataclass."""

    def test_add_event(self) -> None:
        """Test adding events to span."""
        s = Span(name="test", trace_id="t", span_id="s", parent_span_id=None)
        s.add_event(name="event1", key="value")
        s.add_event(name="event2")

        assert len(s.events) == 2
        assert s.events[0][1] == "event1"
        assert s.events[0][2] == {"key": "value"}
        assert s.events[1][1] == "event2"
        assert s.events[1][2] == {}

    def test_is_root(self) -> None:
        """Test is_root property."""
        root = Span(name="root", trace_id="t", span_id="s", parent_span_id=None)
        child = Span(name="child", trace_id="t", span_id="s2", parent_span_id="s")

        assert root.is_root is True
        assert child.is_root is False

    def test_set_attribute(self) -> None:
        """Test setting span attributes."""
        s = Span(name="test", trace_id="t", span_id="s", parent_span_id=None)
        s.set_attribute(key="key1", value="value1")
        s.set_attribute(key="key2", value=42)

        assert s.attributes["key1"] == "value1"
        assert s.attributes["key2"] == 42

    def test_span_creation(self) -> None:
        """Test basic span creation."""
        s = Span(
            name="test_span",
            trace_id="trace-123",
            span_id="span-456",
            parent_span_id=None,
        )
        assert s.name == "test_span"
        assert s.trace_id == "trace-123"
        assert s.span_id == "span-456"
        assert s.parent_span_id is None
        assert s.ended_at is None

    def test_span_duration_after_end(self) -> None:
        """Test duration_ms after end."""
        s = Span(name="test", trace_id="t", span_id="s", parent_span_id=None)
        time.sleep(0.01)
        s.end()
        assert s.duration_ms is not None
        assert s.duration_ms >= 10

    def test_span_duration_not_ended(self) -> None:
        """Test duration_ms is None when not ended."""
        s = Span(name="test", trace_id="t", span_id="s", parent_span_id=None)
        assert s.duration_ms is None


class TestSpanContextManager:
    """Test span context manager."""

    @pytest.mark.asyncio
    async def test_async_context_manager(self) -> None:
        """Test asynchronous span context manager."""
        assert get_current_span() is None

        async with span(name="async_span") as s:
            assert get_current_span() is s
            assert s.name == "async_span"

        assert get_current_span() is None

    def test_nested_spans_parent_child(self) -> None:
        """Test nested spans have parent-child relationship."""
        with span(name="parent") as parent_span:
            assert parent_span.parent_span_id is None

            with span(name="child") as child_span:
                assert child_span.parent_span_id == parent_span.span_id
                assert child_span.trace_id == parent_span.trace_id

    def test_span_ended_on_exit(self) -> None:
        """Test span is ended when context exits."""
        with span(name="test") as s:
            assert s.ended_at is None

        assert s.ended_at is not None

    @pytest.mark.asyncio
    async def test_span_propagates_to_coroutines(self) -> None:
        """Test span propagates through async call chain."""

        async def inner_function() -> str:
            current = get_current_span()
            return current.name if current else "none"

        async with span(name="outer"):
            result = await inner_function()
            assert result == "outer"

    def test_span_with_attributes(self) -> None:
        """Test span with initial attributes."""
        with span(name="test", key1="value1", key2=42) as s:
            assert s.attributes["key1"] == "value1"
            assert s.attributes["key2"] == 42

    def test_sync_context_manager(self) -> None:
        """Test synchronous span context manager."""
        assert get_current_span() is None

        with span(name="test_span") as s:
            assert get_current_span() is s
            assert s.name == "test_span"

        assert get_current_span() is None

    def test_trace_id_propagates(self) -> None:
        """Test trace_id propagates through nested spans."""
        with span(name="root") as root:
            trace_id = root.trace_id

            with span(name="child1") as c1:
                assert c1.trace_id == trace_id

                with span(name="grandchild") as gc:
                    assert gc.trace_id == trace_id

            with span(name="child2") as c2:
                assert c2.trace_id == trace_id


class TestSpanFunctions:
    """Test span utility functions."""

    def test_get_current_trace_id_no_span(self) -> None:
        """Test get_current_trace_id returns None when no span."""
        assert get_current_trace_id() is None

    def test_get_current_trace_id_with_span(self) -> None:
        """Test get_current_trace_id returns ID when span active."""
        with span(name="test") as s:
            assert get_current_trace_id() == s.trace_id

    def test_set_reset_current_span(self) -> None:
        """Test manual set/reset functions."""
        s = Span(name="manual", trace_id="t", span_id="s", parent_span_id=None)
        token = set_current_span(s)

        assert get_current_span() is s

        reset_current_span(token)
        assert get_current_span() is None


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestContextIntegration:
    """Test integration between context modules."""

    @pytest.mark.asyncio
    async def test_concurrent_contexts_isolated(self) -> None:
        """Test that concurrent tasks have isolated contexts."""
        results: list[tuple[str, str]] = []

        async def task(name: str) -> None:
            async with request_context(operation=name):
                await asyncio.sleep(0.01)  # Allow interleaving
                ctx = get_request_context()
                assert ctx is not None
                results.append((name, ctx.operation))

        await asyncio.gather(
            task("task1"),
            task("task2"),
            task("task3"),
        )

        # Each task should have seen its own context
        for name, operation in results:
            assert name == operation

    @pytest.mark.asyncio
    async def test_request_context_and_span_together(self) -> None:
        """Test using request context and spans together."""
        async with (
            request_context(operation="integrated_test", device_address="DEV1") as ctx,
            span(name="main_operation") as s,
        ):
            s.set_attribute(key="request_id", value=ctx.request_id)

            # Both contexts should be accessible
            assert get_request_context() is ctx
            assert get_current_span() is s
