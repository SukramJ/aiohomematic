# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for context variables pattern."""

import asyncio
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
        token = set_request_context(ctx=ctx)

        assert get_request_context() is ctx

        reset_request_context(token=token)
        assert get_request_context() is None


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
