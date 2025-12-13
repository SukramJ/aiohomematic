# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Client coordinator for managing client lifecycle and operations.

This module provides centralized client management including creation,
initialization, connection management, and lifecycle operations.

The ClientCoordinator provides:
- Client creation and registration
- Client initialization and deinitialization
- Primary client selection
- Client lifecycle management (start/stop)
- Client availability checking
"""

from __future__ import annotations

import logging
from typing import Final

from aiohomematic import client as hmcl, i18n
from aiohomematic.const import PRIMARY_CLIENT_CANDIDATE_INTERFACES, Interface, ProxyInitState
from aiohomematic.exceptions import AioHomematicException, BaseHomematicException
from aiohomematic.interfaces.central import CentralInfo, ConfigProvider, SystemInfoProvider
from aiohomematic.interfaces.client import ClientFactory, ClientProtocol, ClientProvider
from aiohomematic.interfaces.coordinators import CoordinatorProvider
from aiohomematic.support import extract_exc_args

_LOGGER: Final = logging.getLogger(__name__)


class ClientCoordinator(ClientProvider):
    """Coordinator for client lifecycle and operations."""

    __slots__ = (
        "_central_info",
        "_client_factory",
        "_clients",
        "_clients_started",
        "_config_provider",
        "_coordinator_provider",
        "_primary_client",
        "_system_info_provider",
    )

    def __init__(
        self,
        *,
        client_factory: ClientFactory,
        central_info: CentralInfo,
        config_provider: ConfigProvider,
        coordinator_provider: CoordinatorProvider,
        system_info_provider: SystemInfoProvider,
    ) -> None:
        """
        Initialize the client coordinator.

        Args:
        ----
            client_factory: Factory for creating client instances
            central_info: Provider for central system information
            config_provider: Provider for configuration access
            coordinator_provider: Provider for accessing other coordinators
            system_info_provider: Provider for system information

        """
        self._client_factory: Final = client_factory
        self._central_info: Final = central_info
        self._config_provider: Final = config_provider
        self._coordinator_provider: Final = coordinator_provider
        self._system_info_provider: Final = system_info_provider

        # {interface_id, client}
        self._clients: Final[dict[str, ClientProtocol]] = {}
        self._clients_started: bool = False
        self._primary_client: ClientProtocol | None = None

    @property
    def all_clients_active(self) -> bool:
        """Check if all configured clients exist and are active."""
        count_client = len(self._clients)
        return count_client > 0 and count_client == len(self._config_provider.config.enabled_interface_configs)

    @property
    def available(self) -> bool:
        """Return if all clients are available."""
        return all(client.available for client in self._clients.values())

    @property
    def clients(self) -> tuple[ClientProtocol, ...]:
        """Return all clients."""
        return tuple(self._clients.values())

    @property
    def clients_started(self) -> bool:
        """Return if clients have been started."""
        return self._clients_started

    @property
    def has_clients(self) -> bool:
        """Check if any clients exist."""
        return len(self._clients) > 0

    @property
    def interface_ids(self) -> frozenset[str]:
        """Return all associated interface IDs."""
        return frozenset(self._clients)

    @property
    def interfaces(self) -> frozenset[Interface]:
        """Return all associated interfaces."""
        return frozenset(client.interface for client in self._clients.values())

    @property
    def is_alive(self) -> bool:
        """Return if all clients have alive callbacks."""
        return all(client.is_callback_alive() for client in self._clients.values())

    @property
    def poll_clients(self) -> tuple[ClientProtocol, ...]:
        """Return clients that need to poll data."""
        return tuple(client for client in self._clients.values() if not client.supports_push_updates)

    @property
    def primary_client(self) -> ClientProtocol | None:
        """Return the primary client of the backend."""
        if self._primary_client is not None:
            return self._primary_client
        if client := self._get_primary_client():
            self._primary_client = client
        return self._primary_client

    def get_client(self, *, interface_id: str | None = None, interface: Interface | None = None) -> ClientProtocol:
        """
        Return a client by interface_id or interface.

        Args:
        ----
            interface_id: Interface identifier (e.g., "ccu-main-BidCos-RF")
            interface: Interface type (e.g., Interface.BIDCOS_RF)

        Returns:
        -------
            Client instance

        Raises:
        ------
            AioHomematicException: If neither parameter is provided or client not found

        """
        if interface_id is None and interface is None:
            raise AioHomematicException(
                i18n.tr(
                    "exception.central.get_client.no_parameter",
                    name=self._central_info.name,
                )
            )

        # If interface_id is provided, use it directly
        if interface_id is not None:
            if not self.has_client(interface_id=interface_id):
                raise AioHomematicException(
                    i18n.tr(
                        "exception.central.get_client.interface_missing",
                        interface_id=interface_id,
                        name=self._central_info.name,
                    )
                )
            return self._clients[interface_id]

        # If interface is provided, find client by interface type
        for client in self._clients.values():
            if client.interface == interface:
                return client

        raise AioHomematicException(
            i18n.tr(
                "exception.central.get_client.interface_type_missing",
                interface=interface,
                name=self._central_info.name,
            )
        )

    def has_client(self, *, interface_id: str) -> bool:
        """
        Check if client exists.

        Args:
        ----
            interface_id: Interface identifier

        Returns:
        -------
            True if client exists, False otherwise

        """
        return interface_id in self._clients

    async def restart_clients(self) -> None:
        """Restart all clients."""
        _LOGGER.debug("RESTART_CLIENTS: Restarting clients for %s", self._central_info.name)
        await self.stop_clients()
        if await self.start_clients():
            _LOGGER.info(
                i18n.tr(
                    "log.central.restart_clients.restarted",
                    name=self._central_info.name,
                )
            )

    async def start_clients(self) -> bool:
        """
        Start all clients.

        Returns
        -------
            True if all clients started successfully, False otherwise

        """
        if not await self._create_clients():
            return False

        # Load caches after clients are created
        await self._coordinator_provider.cache_coordinator.load_all()

        # Initialize clients (sets them to CONNECTED state)
        await self._init_clients()

        # Initialize hub (requires connected clients to fetch programs/sysvars)
        await self._coordinator_provider.hub_coordinator.init_hub()

        self._clients_started = True
        return True

    async def stop_clients(self) -> None:
        """Stop all clients."""
        _LOGGER.debug("STOP_CLIENTS: Stopping clients for %s", self._central_info.name)
        await self._de_init_clients()

        for client in self._clients.values():
            _LOGGER.debug("STOP_CLIENTS: Stopping %s", client.interface_id)
            await client.stop()

        _LOGGER.debug("STOP_CLIENTS: Clearing existing clients.")
        self._clients.clear()
        self._clients_started = False

    async def _create_client(self, *, interface_config: hmcl.InterfaceConfig) -> bool:
        """
        Create a single client.

        Args:
        ----
            interface_config: Interface configuration

        Returns:
        -------
            True if client was created successfully, False otherwise

        """
        try:
            if client := await self._client_factory.create_client_instance(
                interface_config=interface_config,
            ):
                _LOGGER.debug(
                    "CREATE_CLIENT: Adding client %s to %s",
                    client.interface_id,
                    self._central_info.name,
                )
                self._clients[client.interface_id] = client
                return True
        except BaseHomematicException as bhexc:  # pragma: no cover
            _LOGGER.error(
                i18n.tr(
                    "log.central.create_client.no_connection",
                    interface_id=interface_config.interface_id,
                    reason=extract_exc_args(exc=bhexc),
                )
            )
        return False

    async def _create_clients(self) -> bool:
        """
        Create all configured clients.

        Returns
        -------
            True if all clients were created successfully, False otherwise

        """
        if len(self._clients) > 0:
            _LOGGER.error(
                i18n.tr(
                    "log.central.create_clients.already_created",
                    name=self._central_info.name,
                )
            )
            return False

        if len(self._config_provider.config.enabled_interface_configs) == 0:
            _LOGGER.error(
                i18n.tr(
                    "log.central.create_clients.no_interfaces",
                    name=self._central_info.name,
                )
            )
            return False

        # Create primary clients first
        for interface_config in self._config_provider.config.enabled_interface_configs:
            if interface_config.interface in PRIMARY_CLIENT_CANDIDATE_INTERFACES:
                await self._create_client(interface_config=interface_config)

        # Create secondary clients
        for interface_config in self._config_provider.config.enabled_interface_configs:
            if interface_config.interface not in PRIMARY_CLIENT_CANDIDATE_INTERFACES:
                if (
                    self.primary_client is not None
                    and interface_config.interface not in self.primary_client.system_information.available_interfaces
                ):
                    _LOGGER.error(
                        i18n.tr(
                            "log.central.create_clients.interface_not_available",
                            interface=interface_config.interface,
                            name=self._central_info.name,
                        )
                    )
                    interface_config.disable()
                    continue
                await self._create_client(interface_config=interface_config)

        if not self.all_clients_active:
            _LOGGER.warning(
                i18n.tr(
                    "log.central.create_clients.created_count_failed",
                    created=len(self._clients),
                    total=len(self._config_provider.config.enabled_interface_configs),
                )
            )
            return False

        if self.primary_client is None:
            _LOGGER.warning(
                i18n.tr(
                    "log.central.create_clients.no_primary_identified",
                    name=self._central_info.name,
                )
            )
            return True

        _LOGGER.debug("CREATE_CLIENTS successful for %s", self._central_info.name)
        return True

    async def _de_init_clients(self) -> None:
        """De-initialize all clients."""
        for name, client in self._clients.items():
            if await client.deinitialize_proxy():
                _LOGGER.debug("DE_INIT_CLIENTS: Proxy de-initialized: %s", name)

    def _get_primary_client(self) -> ClientProtocol | None:
        """
        Get the primary client.

        Returns
        -------
            Primary client or None if not found

        """
        client: ClientProtocol | None = None
        for client in self._clients.values():
            if client.interface in PRIMARY_CLIENT_CANDIDATE_INTERFACES and client.available:
                return client
        return client

    async def _init_clients(self) -> None:
        """Initialize all clients."""
        for client in self._clients.copy().values():
            if client.interface not in self._system_info_provider.system_information.available_interfaces:
                _LOGGER.debug(
                    "INIT_CLIENTS failed: Interface: %s is not available for the backend %s",
                    client.interface,
                    self._central_info.name,
                )
                del self._clients[client.interface_id]
                continue

            if await client.initialize_proxy() == ProxyInitState.INIT_SUCCESS:
                _LOGGER.debug(
                    "INIT_CLIENTS: client %s initialized for %s", client.interface_id, self._central_info.name
                )
