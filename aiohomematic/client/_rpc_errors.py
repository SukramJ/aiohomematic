# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Error mapping helpers for RPC transports.

This module centralizes small, transport-agnostic utilities to turn the backend
errors into domain-specific exceptions with useful context. It is used by both
JSON-RPC and XML-RPC clients.

Key types and functions
- RpcContext: Lightweight context container that formats protocol/method/host
  for readable error messages and logs.
- map_jsonrpc_error: Maps a JSON-RPC error object to an appropriate exception
  (AuthFailure, InternalBackendException, ClientException).
- map_transport_error: Maps generic transport-level exceptions like OSError to
  domain exceptions (NoConnectionException/ClientException).
- map_xmlrpc_fault: Maps XML-RPC faults to domain exceptions with context.
- sanitize_error_message: Sanitizes error messages to remove sensitive data.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import re
from typing import Any, Final

from aiohomematic.exceptions import AuthFailure, ClientException, InternalBackendException, NoConnectionException

# Patterns that may contain sensitive information
_SENSITIVE_PATTERNS: Final[tuple[tuple[str, str], ...]] = (
    # IP addresses (IPv4)
    (r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "<ip-redacted>"),
    # Hostnames with domains
    (r"\b[a-zA-Z0-9][-a-zA-Z0-9]*(\.[a-zA-Z0-9][-a-zA-Z0-9]*)+\b", "<host-redacted>"),
    # Session IDs (common patterns)
    (r"['\"]?session[_-]?id['\"]?\s*[:=]\s*['\"]?[\w-]+['\"]?", "session_id=<redacted>"),
    # Passwords in URLs or params
    (r"['\"]?password['\"]?\s*[:=]\s*['\"][^'\"]*['\"]", "password=<redacted>"),
    (r"['\"]?passwd['\"]?\s*[:=]\s*['\"][^'\"]*['\"]", "passwd=<redacted>"),
)


def sanitize_error_message(message: str) -> str:
    """
    Sanitize error message by removing potentially sensitive information.

    Removes or masks:
    - IP addresses
    - Hostnames
    - Session IDs
    - Passwords

    Args:
        message: The error message to sanitize.

    Returns:
        Sanitized error message.

    """
    result = message
    for pattern, replacement in _SENSITIVE_PATTERNS:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result


@dataclass(slots=True)
class RpcContext:
    """
    Context container for RPC operations.

    Provides formatted output for error messages with optional sanitization
    to protect sensitive information in logs.
    """

    protocol: str
    method: str
    host: str | None = None
    interface: str | None = None
    params: Mapping[str, Any] | None = None

    def fmt(self, *, sanitize: bool = False) -> str:
        """
        Format context for error messages.

        Args:
            sanitize: If True, omit host information for security.

        Returns:
            Formatted context string.

        """
        parts: list[str] = [f"protocol={self.protocol}", f"method={self.method}"]
        if self.interface:
            parts.append(f"interface={self.interface}")
        if self.host and not sanitize:
            parts.append(f"host={self.host}")
        return ", ".join(parts)

    def fmt_sanitized(self) -> str:
        """Format context with sensitive information redacted."""
        return self.fmt(sanitize=True)


def map_jsonrpc_error(*, error: Mapping[str, Any], ctx: RpcContext) -> Exception:
    """Map JSON-RPC error to exception."""
    # JSON-RPC 2.0 like error: {code, message, data?}
    code = int(error.get("code", 0))
    message = str(error.get("message", ""))
    # Enrich message with context
    base_msg = f"{message} ({ctx.fmt()})"

    # Map common codes
    if message.startswith("access denied") or code in (401, -32001):
        return AuthFailure(base_msg)
    if "internal error" in message.lower() or code in (-32603, 500):
        return InternalBackendException(base_msg)
    # Generic client exception for others
    return ClientException(base_msg)


def map_transport_error(*, exc: BaseException, ctx: RpcContext) -> Exception:
    """Map transport error to exception."""
    msg = f"{exc} ({ctx.fmt()})"
    if isinstance(exc, OSError):
        return NoConnectionException(msg)
    return ClientException(msg)


def map_xmlrpc_fault(*, code: int, fault_string: str, ctx: RpcContext) -> Exception:
    """Map XML-RPC fault to exception."""
    # Enrich message with context
    fault_msg = f"XMLRPC Fault {code}: {fault_string} ({ctx.fmt()})"
    # Simple mappings
    if "unauthorized" in fault_string.lower():
        return AuthFailure(fault_msg)
    if "internal" in fault_string.lower():
        return InternalBackendException(fault_msg)
    return ClientException(fault_msg)
