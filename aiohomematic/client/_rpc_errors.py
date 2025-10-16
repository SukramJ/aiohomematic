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
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from aiohomematic.exceptions import AuthFailure, ClientException, InternalBackendException, NoConnectionException


@dataclass(slots=True)
class RpcContext:
    protocol: str
    method: str
    host: str | None = None
    interface: str | None = None
    params: Mapping[str, Any] | None = None

    def fmt(self) -> str:
        """Format context for error messages."""
        parts: list[str] = [f"protocol={self.protocol}", f"method={self.method}"]
        if self.interface:
            parts.append(f"interface={self.interface}")
        if self.host:
            parts.append(f"host={self.host}")
        return ", ".join(parts)


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
