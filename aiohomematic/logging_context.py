# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Logging integration with request context.

This module provides logging utilities that automatically include request context
information in log messages, enabling correlation of logs across async call chains.

Key features:
- ContextualLoggerAdapter: Logger adapter that prefixes messages with request ID
- RequestContextFilter: Logging filter that adds context fields to log records
- get_contextual_logger: Factory function for contextual loggers

Example:
    _LOGGER = get_contextual_logger(name=__name__)
    _LOGGER.info("Processing device")  # → "[abc12345:set_value] Processing device"

Public API of this module is defined by __all__.

"""

from __future__ import annotations

from collections.abc import MutableMapping
import logging
from typing import Any

from aiohomematic.context import get_request_context


class ContextualLoggerAdapter(logging.LoggerAdapter[logging.Logger]):
    """
    Logger adapter that includes request context in log messages.

    Automatically prefixes log messages with request_id and operation
    from the current RequestContext.

    Example:
        _LOGGER = ContextualLoggerAdapter(logging.getLogger(__name__), {})
        # With request context set:
        _LOGGER.info("Processing")  # → "[abc12345:set_value] Processing"
        # Without request context:
        _LOGGER.info("Processing")  # → "Processing"

    """

    def process(  # kwonly: disable
        self,
        msg: str,
        kwargs: MutableMapping[str, Any],
    ) -> tuple[str, MutableMapping[str, Any]]:
        """
        Process log message to include request context.

        Args:
            msg: The log message.
            kwargs: Additional logging keyword arguments.

        Returns:
            Tuple of (processed message, kwargs).

        """
        if ctx := get_request_context():
            prefix = f"[{ctx.request_id}]"
            if ctx.operation:
                prefix = f"[{ctx.request_id}:{ctx.operation}]"
            msg = f"{prefix} {msg}"

        return msg, kwargs


class RequestContextFilter(logging.Filter):
    """
    Logging filter that adds context fields to log records.

    Use with JSON formatters or structured logging to include request context
    as separate fields in log records.

    Example:
        handler = logging.StreamHandler()
        handler.addFilter(RequestContextFilter())
        # Log records will have: request_id, operation, device_address, elapsed_ms

    """

    def filter(self, record: logging.LogRecord) -> bool:  # kwonly: disable
        """
        Add request context fields to log record.

        Args:
            record: The log record to augment.

        Returns:
            Always True (never filters out records).

        """
        ctx = get_request_context()

        record.request_id = ctx.request_id if ctx else "none"
        record.operation = ctx.operation if ctx else "none"
        record.device_address = ctx.device_address if ctx else "none"
        record.elapsed_ms = ctx.elapsed_ms if ctx else 0.0

        return True


def get_contextual_logger(*, name: str) -> ContextualLoggerAdapter:
    """
    Get a logger that includes request context in messages.

    Factory function that creates a ContextualLoggerAdapter wrapping a
    standard logger. Use this instead of logging.getLogger() to get
    automatic request context prefixing.

    Args:
        name: Logger name (typically __name__).

    Returns:
        ContextualLoggerAdapter that prefixes messages with request context.

    Example:
        _LOGGER = get_contextual_logger(name=__name__)
        _LOGGER.info("Processing device")  # → "[abc12345:set_value] Processing device"

    """
    return ContextualLoggerAdapter(logging.getLogger(name), {})


# Define public API for this module
__all__ = [
    "ContextualLoggerAdapter",
    "RequestContextFilter",
    "get_contextual_logger",
]
