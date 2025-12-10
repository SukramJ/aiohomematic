"""
Link management handler.

Handles device linking operations.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Final, cast

from aiohomematic import i18n
from aiohomematic.client.handlers.base import BaseHandler
from aiohomematic.decorators import inspector
from aiohomematic.exceptions import BaseHomematicException, ClientException
from aiohomematic.interfaces.client import LinkOperations
from aiohomematic.support import extract_exc_args

if TYPE_CHECKING:
    from aiohomematic.client import AioJsonRpcAioHttpClient
    from aiohomematic.client.rpc_proxy import BaseRpcProxy
    from aiohomematic.const import Interface
    from aiohomematic.interfaces.client import ClientDependencies

_LOGGER: Final = logging.getLogger(__name__)


class LinkManagementHandler(BaseHandler, LinkOperations):
    """
    Handler for device linking operations.

    Implements LinkOperations protocol for ISP-compliant client operations.

    Handles:
    - Adding links between devices
    - Removing links between devices
    - Querying link information and peers
    """

    __slots__ = ("_supports_linking",)

    def __init__(
        self,
        *,
        central: ClientDependencies,
        interface: Interface,
        interface_id: str,
        json_rpc_client: AioJsonRpcAioHttpClient,
        proxy: BaseRpcProxy,
        proxy_read: BaseRpcProxy,
        supports_linking: bool,
    ) -> None:
        """Initialize the link management handler."""
        super().__init__(
            central=central,
            interface=interface,
            interface_id=interface_id,
            json_rpc_client=json_rpc_client,
            proxy=proxy,
            proxy_read=proxy_read,
        )
        self._supports_linking: Final = supports_linking

    @property
    def supports_linking(self) -> bool:
        """Return if the backend supports device linking operations."""
        return self._supports_linking

    @inspector
    async def add_link(
        self,
        *,
        sender_address: str,
        receiver_address: str,
        name: str,
        description: str,
    ) -> None:
        """
        Create a direct link between two device channels.

        Direct links allow devices to communicate without the CCU. The sender
        triggers actions on the receiver (e.g., a button press turning on a light).

        Args:
            sender_address: Source channel address (e.g., "VCU0000001:1").
            receiver_address: Target channel address (e.g., "VCU0000002:1").
            name: User-defined link name.
            description: User-defined link description.

        Raises:
            ClientException: If the RPC call fails.

        """
        if not self._supports_linking:
            _LOGGER.debug("ADD_LINK: Not supported by client for %s", self._interface_id)
            return

        try:
            await self._proxy.addLink(sender_address, receiver_address, name, description)
        except BaseHomematicException as bhexc:
            raise ClientException(
                i18n.tr(
                    "exception.client.add_link.failed",
                    sender=sender_address,
                    receiver=receiver_address,
                    name=name,
                    description=description,
                    reason=extract_exc_args(exc=bhexc),
                )
            ) from bhexc

    @inspector
    async def get_link_peers(self, *, address: str) -> tuple[str, ...]:
        """
        Return addresses of all channels linked to the given address.

        Args:
            address: Channel address to query (e.g., "VCU0000001:1").

        Returns:
            Tuple of peer channel addresses that are linked to this channel.

        Raises:
            ClientException: If the RPC call fails.

        """
        if not self._supports_linking:
            _LOGGER.debug("GET_LINK_PEERS: Not supported by client for %s", self._interface_id)
            return ()

        try:
            return tuple(links) if (links := await self._proxy.getLinkPeers(address)) else ()
        except BaseHomematicException as bhexc:
            raise ClientException(
                i18n.tr(
                    "exception.client.get_link_peers.failed",
                    address=address,
                    reason=extract_exc_args(exc=bhexc),
                )
            ) from bhexc

    @inspector
    async def get_links(self, *, address: str, flags: int) -> dict[str, Any]:
        """
        Return detailed link information for a channel.

        Args:
            address: Channel address to query (e.g., "VCU0000001:1").
            flags: Bitmask controlling returned information (backend-specific).

        Returns:
            Dict containing link details including sender, receiver, and paramsets.

        Raises:
            ClientException: If the RPC call fails.

        """
        if not self._supports_linking:
            _LOGGER.debug("GET_LINKS: Not supported by client for %s", self._interface_id)
            return {}

        try:
            return cast(dict[str, Any], await self._proxy.getLinks(address, flags))
        except BaseHomematicException as bhexc:
            raise ClientException(
                i18n.tr(
                    "exception.client.get_links.failed",
                    address=address,
                    reason=extract_exc_args(exc=bhexc),
                )
            ) from bhexc

    @inspector
    async def remove_link(self, *, sender_address: str, receiver_address: str) -> None:
        """
        Remove a direct link between two device channels.

        Args:
            sender_address: Source channel address (e.g., "VCU0000001:1").
            receiver_address: Target channel address (e.g., "VCU0000002:1").

        Raises:
            ClientException: If the RPC call fails.

        """
        if not self._supports_linking:
            _LOGGER.debug("REMOVE_LINK: Not supported by client for %s", self._interface_id)
            return

        try:
            await self._proxy.removeLink(sender_address, receiver_address)
        except BaseHomematicException as bhexc:
            raise ClientException(
                i18n.tr(
                    "exception.client.remove_link.failed",
                    sender=sender_address,
                    receiver=receiver_address,
                    reason=extract_exc_args(exc=bhexc),
                )
            ) from bhexc
