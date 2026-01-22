# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Client factory utilities.

Provides configuration and proxy creation for InterfaceClient instances.

Public API
----------
- ClientConfig: Configuration holder for client creation
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, cast

from aiohomematic import i18n
from aiohomematic.client.rpc_proxy import AioXmlRpcProxy
from aiohomematic.const import (
    DEFAULT_MAX_WORKERS,
    INTERFACES_REQUIRING_JSON_RPC_CLIENT,
    INTERFACES_SUPPORTING_FIRMWARE_UPDATES,
    INTERFACES_SUPPORTING_RPC_CALLBACK,
    LINKABLE_INTERFACES,
    Interface,
    SystemInformation,
)
from aiohomematic.exceptions import NoConnectionException
from aiohomematic.support import build_xml_rpc_headers, build_xml_rpc_uri, extract_exc_args

if TYPE_CHECKING:
    from aiohomematic.client.config import InterfaceConfig
    from aiohomematic.client.rpc_proxy import BaseRpcProxy
    from aiohomematic.interfaces.client import ClientDependenciesProtocol

__all__ = ["ClientConfig"]


class ClientConfig:
    """Configuration holder for client creation."""

    def __init__(
        self,
        *,
        client_deps: ClientDependenciesProtocol,
        interface_config: InterfaceConfig,
    ) -> None:
        """Initialize the config."""
        self.client_deps: Final[ClientDependenciesProtocol] = client_deps
        self.version: str = "0"
        self.system_information = SystemInformation()
        self.interface_config: Final = interface_config
        self.interface: Final = interface_config.interface
        self.interface_id: Final = interface_config.interface_id
        self.max_read_workers: Final[int] = client_deps.config.max_read_workers
        self.has_credentials: Final[bool] = (
            client_deps.config.username is not None and client_deps.config.password is not None
        )
        self.has_linking: Final = self.interface in LINKABLE_INTERFACES
        self.has_firmware_updates: Final = self.interface in INTERFACES_SUPPORTING_FIRMWARE_UPDATES
        self.has_ping_pong: Final = self.interface in INTERFACES_SUPPORTING_RPC_CALLBACK
        self.has_push_updates: Final = self.interface not in client_deps.config.interfaces_requiring_periodic_refresh
        self.has_rpc_callback: Final = self.interface in INTERFACES_SUPPORTING_RPC_CALLBACK
        callback_host: Final = (
            client_deps.config.callback_host if client_deps.config.callback_host else client_deps.callback_ip_addr
        )
        callback_port = (
            client_deps.config.callback_port_xml_rpc
            if client_deps.config.callback_port_xml_rpc
            else client_deps.listen_port_xml_rpc
        )
        init_url = f"{callback_host}:{callback_port}"
        self.init_url: Final = f"http://{init_url}"

        self.xml_rpc_uri: Final = build_xml_rpc_uri(
            host=client_deps.config.host,
            port=interface_config.port,
            path=interface_config.remote_path,
            tls=client_deps.config.tls,
        )

    async def create_rpc_proxy(
        self,
        *,
        interface: Interface,
        auth_enabled: bool | None = None,
        max_workers: int = DEFAULT_MAX_WORKERS,
    ) -> BaseRpcProxy:
        """Return a RPC proxy for the backend communication."""
        return await self._create_xml_rpc_proxy(
            auth_enabled=auth_enabled,
            max_workers=max_workers,
        )

    async def get_version(self) -> str:
        """Return the version of the backend."""
        if self.interface in INTERFACES_REQUIRING_JSON_RPC_CLIENT:
            return "0"
        check_proxy = await self._create_simple_rpc_proxy(interface=self.interface)
        try:
            if (methods := check_proxy.supported_methods) and "getVersion" in methods:
                # BidCos-Wired does not support getVersion()
                return cast(str, await check_proxy.getVersion())
        except Exception as exc:
            raise NoConnectionException(
                i18n.tr(
                    key="exception.client.client_config.unable_to_connect",
                    reason=extract_exc_args(exc=exc),
                )
            ) from exc
        return "0"

    async def _create_simple_rpc_proxy(self, *, interface: Interface) -> BaseRpcProxy:
        """Return a RPC proxy for the backend communication."""
        return await self._create_xml_rpc_proxy(auth_enabled=True, max_workers=0)

    async def _create_xml_rpc_proxy(
        self,
        *,
        auth_enabled: bool | None = None,
        max_workers: int = DEFAULT_MAX_WORKERS,
    ) -> AioXmlRpcProxy:
        """Return a XmlRPC proxy for the backend communication."""
        config = self.client_deps.config
        xml_rpc_headers = (
            build_xml_rpc_headers(
                username=config.username,
                password=config.password,
            )
            if auth_enabled
            else []
        )
        xml_proxy = AioXmlRpcProxy(
            max_workers=max_workers,
            interface_id=self.interface_id,
            connection_state=self.client_deps.connection_state,
            uri=self.xml_rpc_uri,
            headers=xml_rpc_headers,
            tls=config.tls,
            verify_tls=config.verify_tls,
            session_recorder=self.client_deps.cache_coordinator.recorder,
            event_bus=self.client_deps.event_bus,
            incident_recorder=self.client_deps.cache_coordinator.incident_store,
        )
        await xml_proxy.do_init()
        return xml_proxy
