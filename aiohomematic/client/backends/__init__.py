# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Backend implementations for different Homematic systems.

This package provides backend-specific implementations that abstract
the transport layer (XML-RPC, JSON-RPC) from the client business logic.

Public API
----------
- BackendOperationsProtocol: Interface for all backend operations
- BackendCapabilities: Capability flags dataclass
- CcuBackend: CCU backend (XML-RPC + JSON-RPC)
- JsonCcuBackend: CCU-Jack backend (JSON-RPC only)
- HomegearBackend: Homegear backend (XML-RPC with extensions)
- create_backend: Factory function to create appropriate backend

"""

from __future__ import annotations

from aiohomematic.client.backends.capabilities import (
    CCU_CAPABILITIES,
    HOMEGEAR_CAPABILITIES,
    JSON_CCU_CAPABILITIES,
    BackendCapabilities,
)
from aiohomematic.client.backends.ccu import CcuBackend
from aiohomematic.client.backends.factory import create_backend
from aiohomematic.client.backends.homegear import HomegearBackend
from aiohomematic.client.backends.json_ccu import JsonCcuBackend
from aiohomematic.client.backends.protocol import BackendOperationsProtocol

__all__ = [
    # Protocol
    "BackendOperationsProtocol",
    # Capabilities
    "BackendCapabilities",
    "CCU_CAPABILITIES",
    "HOMEGEAR_CAPABILITIES",
    "JSON_CCU_CAPABILITIES",
    # Backends
    "CcuBackend",
    "HomegearBackend",
    "JsonCcuBackend",
    # Factory
    "create_backend",
]
