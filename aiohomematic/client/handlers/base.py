"""
Base handler class for client operations.

Provides common dependencies and shared functionality for all handler classes.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Final

from aiohomematic.const import Interface
from aiohomematic.decorators import inspector

if TYPE_CHECKING:
    from aiohomematic.client import AioJsonRpcAioHttpClient
    from aiohomematic.client.rpc_proxy import BaseRpcProxy
    from aiohomematic.interfaces.client import ClientDependencies

_LOGGER: Final = logging.getLogger(__name__)


class BaseHandler:
    """
    Base class for all client handler classes.

    Provides access to common dependencies needed by all handlers.
    """

    __slots__ = (
        "_central",
        "_interface",
        "_interface_id",
        "_json_rpc_client",
        "_proxy",
        "_proxy_read",
    )

    def __init__(
        self,
        *,
        central: ClientDependencies,
        interface: Interface,
        interface_id: str,
        json_rpc_client: AioJsonRpcAioHttpClient,
        proxy: BaseRpcProxy,
        proxy_read: BaseRpcProxy,
    ) -> None:
        """
        Initialize the base handler.

        Args:
            central: Central dependencies for accessing central functionality.
            interface: The interface type (e.g., HMIP_RF, BIDCOS_RF).
            interface_id: Unique identifier for this interface.
            json_rpc_client: JSON-RPC client for CCU communication.
            proxy: XML-RPC proxy for write operations.
            proxy_read: XML-RPC proxy for read operations (higher concurrency).

        """
        self._central: Final = central
        self._interface: Final = interface
        self._interface_id: Final = interface_id
        self._json_rpc_client: Final = json_rpc_client
        self._proxy: Final = proxy
        self._proxy_read: Final = proxy_read

    @property
    def central(self) -> ClientDependencies:
        """Return the central dependencies."""
        return self._central

    @property
    def interface(self) -> Interface:
        """Return the interface type."""
        return self._interface

    @property
    def interface_id(self) -> str:
        """Return the interface ID."""
        return self._interface_id

    @property
    def json_rpc_client(self) -> AioJsonRpcAioHttpClient:
        """Return the JSON-RPC client."""
        return self._json_rpc_client

    @property
    def proxy(self) -> BaseRpcProxy:
        """Return the XML-RPC proxy for write operations."""
        return self._proxy

    @property
    def proxy_read(self) -> BaseRpcProxy:
        """Return the XML-RPC proxy for read operations."""
        return self._proxy_read


# Re-export inspector decorator for use in handlers
__all__ = ["BaseHandler", "inspector"]
