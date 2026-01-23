# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Client adapters for communicating with Homematic CCU and compatible backends.

This package provides client implementations that abstract the transport details
of Homematic backends (CCU via JSON-RPC/XML-RPC or Homegear) and expose a
consistent API used by the central module.

Package structure
-----------------
- interface_client.py: InterfaceClient - unified client for all backends
- client_factory.py: ClientConfig for configuration and proxy creation
- config.py: InterfaceConfig for per-interface connection settings
- circuit_breaker.py: CircuitBreaker, CircuitBreakerConfig, CircuitState
- state_machine.py: ClientStateMachine for connection state tracking
- rpc_proxy.py: BaseRpcProxy, AioXmlRpcProxy for XML-RPC transport
- json_rpc.py: AioJsonRpcAioHttpClient for JSON-RPC transport
- request_coalescer.py: RequestCoalescer for deduplicating concurrent requests
- backends/: Backend strategy implementations (CCU, CCU-Jack, Homegear)
- state_change.py: State change tracking utilities

Public API
----------
- Clients: InterfaceClient
- Configuration: ClientConfig, InterfaceConfig
- Circuit breaker: CircuitBreaker, CircuitBreakerConfig, CircuitState
- State machine: ClientStateMachine, InvalidStateTransitionError
- Transport: BaseRpcProxy, AioJsonRpcAioHttpClient
- Coalescing: RequestCoalescer, make_coalesce_key
- Factory functions: create_client, get_client

Notes
-----
- Most users interact with clients via CentralUnit; direct usage is for advanced scenarios
- Clients are created via the create_client() factory function
- XML-RPC is used for device operations; JSON-RPC for metadata/programs/sysvars (CCU only)

"""

from __future__ import annotations

import logging
from typing import Final

from aiohomematic import central as hmcu, i18n
from aiohomematic.client.backends import create_backend
from aiohomematic.client.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from aiohomematic.client.client_factory import ClientConfig
from aiohomematic.client.config import InterfaceConfig
from aiohomematic.client.interface_client import InterfaceClient
from aiohomematic.client.json_rpc import AioJsonRpcAioHttpClient
from aiohomematic.client.request_coalescer import RequestCoalescer, make_coalesce_key
from aiohomematic.client.rpc_proxy import BaseRpcProxy
from aiohomematic.client.state_machine import ClientStateMachine, InvalidStateTransitionError
from aiohomematic.const import CircuitState
from aiohomematic.exceptions import NoConnectionException
from aiohomematic.interfaces.client import ClientDependenciesProtocol, ClientProtocol

_LOGGER: Final = logging.getLogger(__name__)

__all__ = [
    # Circuit breaker
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitState",
    # Clients
    "InterfaceClient",
    # Config
    "ClientConfig",
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
    """
    Create and return a new client for the given interface configuration.

    Uses InterfaceClient with backend strategy pattern to support all
    Homematic backends (CCU, CCU-Jack, Homegear).
    """
    # Get configuration and version
    client_config = ClientConfig(
        client_deps=client_deps,
        interface_config=interface_config,
    )
    version = await client_config.get_version()

    # Create appropriate backend
    backend = await create_backend(
        interface=interface_config.interface,
        interface_id=interface_config.interface_id,
        version=version,
        proxy=await client_config.create_rpc_proxy(
            interface=interface_config.interface,
            auth_enabled=True,
        )
        if client_config.has_rpc_callback
        else None,
        proxy_read=await client_config.create_rpc_proxy(
            interface=interface_config.interface,
            auth_enabled=True,
            max_workers=client_config.max_read_workers,
        )
        if client_config.has_rpc_callback
        else None,
        json_rpc=client_deps.json_rpc_client,
        paramset_provider=client_deps.cache_coordinator.paramset_descriptions,
        device_details_provider=client_deps.cache_coordinator.device_details.device_channel_rega_ids,
        has_push_updates=client_config.has_push_updates,
    )

    _LOGGER.debug(
        "CREATE_CLIENT: Created %s backend for %s",
        backend.model,
        interface_config.interface_id,
    )

    # Create InterfaceClient
    client = InterfaceClient(
        backend=backend,
        central=client_deps,
        interface_config=interface_config,
        version=version,
    )
    await client.init_client()

    if await client.check_connection_availability(handle_ping_pong=False):
        return client

    raise NoConnectionException(
        i18n.tr(key="exception.client.client_config.no_connection", interface_id=interface_config.interface_id)
    )


def get_client(*, interface_id: str) -> ClientProtocol | None:
    """Return client by interface_id."""
    for central in hmcu.CENTRAL_REGISTRY.values():
        if central.client_coordinator.has_client(interface_id=interface_id):
            return central.client_coordinator.get_client(interface_id=interface_id)
    return None
