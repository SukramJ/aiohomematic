# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Base handler class for client operations.

Provides common dependencies and shared functionality for all handler classes.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Final

from aiohomematic.const import Interface
from aiohomematic.decorators import inspector
from aiohomematic.property_decorators import DelegatedProperty

if TYPE_CHECKING:
    from aiohomematic.client import AioJsonRpcAioHttpClient
    from aiohomematic.client.rpc_proxy import BaseRpcProxy
    from aiohomematic.interfaces.client import ClientDependenciesProtocol

_LOGGER: Final = logging.getLogger(__name__)


class BaseHandler:
    """
    Base class for all client handler classes.

    Provides access to common dependencies needed by all handlers.
    """

    __slots__ = (
        "_client_deps",
        "_interface",
        "_interface_id",
        "_json_rpc_client",
        "_proxy",
        "_proxy_read",
    )

    def __init__(
        self,
        *,
        client_deps: ClientDependenciesProtocol,
        interface: Interface,
        interface_id: str,
        json_rpc_client: AioJsonRpcAioHttpClient,
        proxy: BaseRpcProxy,
        proxy_read: BaseRpcProxy,
    ) -> None:
        """
        Initialize the base handler.

        Args:
            client_deps: Client dependencies for accessing central functionality.
            interface: The interface type (e.g., HMIP_RF, BIDCOS_RF).
            interface_id: Unique identifier for this interface.
            json_rpc_client: JSON-RPC client for CCU communication.
            proxy: XML-RPC proxy for write operations.
            proxy_read: XML-RPC proxy for read operations (higher concurrency).

        """
        self._client_deps: Final = client_deps
        self._interface: Final = interface
        self._interface_id: Final = interface_id
        self._json_rpc_client: Final = json_rpc_client
        self._proxy: Final = proxy
        self._proxy_read: Final = proxy_read

    client_deps: Final = DelegatedProperty["ClientDependenciesProtocol"](path="_client_deps")
    interface: Final = DelegatedProperty[Interface](path="_interface")
    interface_id: Final = DelegatedProperty[str](path="_interface_id")
    json_rpc_client: Final = DelegatedProperty["AioJsonRpcAioHttpClient"](path="_json_rpc_client")
    proxy: Final = DelegatedProperty["BaseRpcProxy"](path="_proxy")
    proxy_read: Final = DelegatedProperty["BaseRpcProxy"](path="_proxy_read")


# Re-export inspector decorator for use in handlers
__all__ = ["BaseHandler", "inspector"]
