# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Client adapters for communicating with Homematic CCU and compatible backends.

This package provides client implementations that abstract the transport details
of Homematic backends (CCU via JSON-RPC/XML-RPC or Homegear) and expose a
consistent API used by the central module.

Package structure
-----------------
- ccu.py: Client implementations (ClientCCU, ClientJsonCCU, ClientHomegear, ClientConfig)
- config.py: InterfaceConfig for per-interface connection settings
- circuit_breaker.py: CircuitBreaker, CircuitBreakerConfig, CircuitState
- state_machine.py: ClientStateMachine for connection state tracking
- rpc_proxy.py: BaseRpcProxy, AioXmlRpcProxy for XML-RPC transport
- json_rpc.py: AioJsonRpcAioHttpClient for JSON-RPC transport
- request_coalescer.py: RequestCoalescer for deduplicating concurrent requests
- handlers/: Protocol-specific operation handlers

Public API
----------
- Clients: ClientCCU, ClientJsonCCU, ClientHomegear, ClientConfig
- Configuration: InterfaceConfig
- Circuit breaker: CircuitBreaker, CircuitBreakerConfig, CircuitState
- State machine: ClientStateMachine, InvalidStateTransitionError
- Transport: BaseRpcProxy, AioJsonRpcAioHttpClient
- Coalescing: RequestCoalescer, make_coalesce_key
- Factory functions: create_client, get_client

Notes
-----
- Most users interact with clients via CentralUnit; direct usage is for advanced scenarios
- Clients are created via ClientConfig.create_client() or the create_client() function
- XML-RPC is used for device operations; JSON-RPC for metadata/programs/sysvars (CCU only)

"""

from __future__ import annotations

from aiohomematic import central as hmcu
from aiohomematic.client.ccu import ClientCCU, ClientConfig, ClientHomegear, ClientJsonCCU
from aiohomematic.client.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState
from aiohomematic.client.config import InterfaceConfig
from aiohomematic.client.json_rpc import AioJsonRpcAioHttpClient
from aiohomematic.client.request_coalescer import RequestCoalescer, make_coalesce_key
from aiohomematic.client.rpc_proxy import BaseRpcProxy
from aiohomematic.client.state_machine import ClientStateMachine, InvalidStateTransitionError
from aiohomematic.interfaces.client import ClientDependenciesProtocol, ClientProtocol

__all__ = [
    # CCU clients
    "ClientCCU",
    "ClientConfig",
    "ClientHomegear",
    "ClientJsonCCU",
    # Circuit breaker
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitState",
    # Config
    "InterfaceConfig",
    # Factory functions
    "create_client",
    "get_client",
    # JSON RPC
    "AioJsonRpcAioHttpClient",
    # RPC proxy
    "BaseRpcProxy",
    # Request coalescing
    "RequestCoalescer",
    "make_coalesce_key",
    # State machine
    "ClientStateMachine",
    "InvalidStateTransitionError",
]


async def create_client(
    *,
    client_deps: ClientDependenciesProtocol,
    interface_config: InterfaceConfig,
) -> ClientProtocol:
    """Return a new client for with a given interface_config."""
    return await ClientConfig(
        client_deps=client_deps,
        interface_config=interface_config,
    ).create_client()


def get_client(*, interface_id: str) -> ClientProtocol | None:
    """Return client by interface_id."""
    for central in hmcu.CENTRAL_INSTANCES.values():
        if central.client_coordinator.has_client(interface_id=interface_id):
            return central.client_coordinator.get_client(interface_id=interface_id)
    return None
