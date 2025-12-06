# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Tests for the retry module."""

from __future__ import annotations

import errno
from unittest.mock import AsyncMock

import pytest

from aiohomematic.exceptions import AuthFailure, NoConnectionException, UnsupportedException, ValidationException
from aiohomematic.retry import RetryStrategy, is_retryable_exception, with_retry


class TestIsRetryableException:
    """Test is_retryable_exception function."""

    def test_connection_error_is_retryable(self) -> None:
        """Test that ConnectionError and subclasses are retryable."""
        assert is_retryable_exception(ConnectionError()) is True
        assert is_retryable_exception(ConnectionRefusedError()) is True
        assert is_retryable_exception(ConnectionResetError()) is True

    def test_no_connection_exception_is_retryable(self) -> None:
        """Test that NoConnectionException is retryable."""
        assert is_retryable_exception(NoConnectionException("test")) is True

    def test_non_transient_os_error_not_retryable(self) -> None:
        """Test that non-transient OS errors are not retryable."""
        # ENOENT (No such file or directory) is not a transient network error
        assert is_retryable_exception(OSError(errno.ENOENT, "Not found")) is False

    def test_permanent_exceptions_not_retryable(self) -> None:
        """Test that permanent exceptions are not retryable."""
        assert is_retryable_exception(AuthFailure("test")) is False
        assert is_retryable_exception(UnsupportedException("test")) is False
        assert is_retryable_exception(ValidationException("test")) is False

    def test_timeout_error_is_retryable(self) -> None:
        """Test that TimeoutError is retryable."""
        assert is_retryable_exception(TimeoutError()) is True
        assert is_retryable_exception(TimeoutError()) is True

    def test_transient_os_error_is_retryable(self) -> None:
        """Test that transient OS errors are retryable."""
        assert is_retryable_exception(OSError(errno.ECONNREFUSED, "Connection refused")) is True
        assert is_retryable_exception(OSError(errno.ETIMEDOUT, "Timed out")) is True
        assert is_retryable_exception(OSError(errno.ENETUNREACH, "Network unreachable")) is True
        assert is_retryable_exception(OSError(errno.EHOSTUNREACH, "Host unreachable")) is True


class TestRetryStrategy:
    """Test RetryStrategy class."""

    def test_custom_configuration(self) -> None:
        """Test custom retry configuration."""
        strategy = RetryStrategy(max_attempts=5, initial_backoff=1.0)
        assert strategy.attempts_remaining == 5

    def test_default_configuration(self) -> None:
        """Test default retry configuration."""
        strategy = RetryStrategy()
        assert strategy.attempts_remaining == 3
        assert strategy.current_attempt == 0

    @pytest.mark.asyncio
    async def test_execute_exhausted_retries(self) -> None:
        """Test execute raises after exhausting retries."""
        strategy = RetryStrategy(max_attempts=2, initial_backoff=0.01)
        mock_op = AsyncMock(side_effect=NoConnectionException("fail"))

        with pytest.raises(NoConnectionException):
            await strategy.execute(operation=mock_op, operation_name="test_op")

        assert mock_op.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_permanent_error_no_retry(self) -> None:
        """Test execute does not retry permanent errors."""
        strategy = RetryStrategy()
        mock_op = AsyncMock(side_effect=AuthFailure("auth failed"))

        with pytest.raises(AuthFailure):
            await strategy.execute(operation=mock_op, operation_name="test_op")

        assert mock_op.call_count == 1

    @pytest.mark.asyncio
    async def test_execute_success_after_retry(self) -> None:
        """Test execute succeeds after retry."""
        strategy = RetryStrategy(initial_backoff=0.01)  # Short backoff for tests
        mock_op = AsyncMock(side_effect=[NoConnectionException("fail"), "success"])

        result = await strategy.execute(operation=mock_op, operation_name="test_op")

        assert result == "success"
        assert mock_op.call_count == 2
        assert strategy.current_attempt == 2

    @pytest.mark.asyncio
    async def test_execute_success_first_try(self) -> None:
        """Test execute succeeds on first try."""
        strategy = RetryStrategy()
        mock_op = AsyncMock(return_value="success")

        result = await strategy.execute(operation=mock_op, operation_name="test_op")

        assert result == "success"
        assert mock_op.call_count == 1
        assert strategy.current_attempt == 1

    def test_reset(self) -> None:
        """Test reset clears attempt counter."""
        strategy = RetryStrategy()
        strategy.record_attempt()
        assert strategy.current_attempt == 1

        strategy.reset()
        assert strategy.current_attempt == 0

    def test_should_retry_exhausted(self) -> None:
        """Test should_retry returns False when attempts exhausted."""
        strategy = RetryStrategy(max_attempts=2)
        strategy.record_attempt()
        strategy.record_attempt()
        # Attempts exhausted
        assert strategy.should_retry(exc=NoConnectionException("test")) is False

    def test_should_retry_permanent_error(self) -> None:
        """Test should_retry returns False for permanent errors."""
        strategy = RetryStrategy()
        assert strategy.should_retry(exc=AuthFailure("test")) is False

    def test_should_retry_transient_error(self) -> None:
        """Test should_retry returns True for transient errors."""
        strategy = RetryStrategy()
        assert strategy.should_retry(exc=NoConnectionException("test")) is True


class TestWithRetryDecorator:
    """Test with_retry decorator."""

    @pytest.mark.asyncio
    async def test_decorator_custom_config(self) -> None:
        """Test decorator with custom configuration."""
        call_count = 0

        @with_retry(max_attempts=5, initial_backoff=0.01)
        async def my_operation() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 4:
                raise NoConnectionException("fail")
            return "success"

        result = await my_operation()
        assert result == "success"
        assert call_count == 4

    @pytest.mark.asyncio
    async def test_decorator_retry_then_success(self) -> None:
        """Test decorator retries and eventually succeeds."""
        call_count = 0

        @with_retry(initial_backoff=0.01)
        async def my_operation() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise NoConnectionException("fail")
            return "success"

        result = await my_operation()
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_decorator_success(self) -> None:
        """Test decorator with successful operation."""
        call_count = 0

        @with_retry()
        async def my_operation() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = await my_operation()
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_decorator_with_arguments(self) -> None:
        """Test decorator passes arguments correctly."""

        @with_retry()
        async def my_operation(a: int, b: str, *, c: bool = False) -> tuple[int, str, bool]:
            return (a, b, c)

        result = await my_operation(1, "test", c=True)
        assert result == (1, "test", True)

    @pytest.mark.asyncio
    async def test_decorator_without_parentheses(self) -> None:
        """Test decorator works without parentheses."""
        call_count = 0

        @with_retry
        async def my_operation() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = await my_operation()
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_decorator_without_parentheses_retry(self) -> None:
        """Test decorator without parentheses retries on failure."""
        call_count = 0

        @with_retry
        async def my_operation() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Transient error")
            return "success"

        result = await my_operation()
        assert result == "success"
        assert call_count == 2
