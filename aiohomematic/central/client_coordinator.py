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
from typing import TYPE_CHECKING, Final

from aiohomematic import client as hmcl, i18n
from aiohomematic.const import (
    PRIMARY_CLIENT_CANDIDATE_INTERFACES,
    EventKey,
    Interface,
    InterfaceEventType,
    ProxyInitState,
)
from aiohomematic.exceptions import AioHomematicException, BaseHomematicException
from aiohomematic.model.interfaces import CentralInfo, ConfigProvider, CoordinatorProvider, SystemInfoProvider
from aiohomematic.support import extract_exc_args

if TYPE_CHECKING:
    from aiohomematic.central import CentralUnit

_LOGGER: Final = logging.getLogger(__name__)


class ClientCoordinator:
    """Coordinator for client lifecycle and operations."""

    __slots__ = (
        "_central",  # Only for factory functions
        "_config_provider",
        "_central_info",
        "_coordinator_provider",
        "_system_info_provider",
        "_clients",
        "_clients_started",
        "_primary_client",
    )

    def __init__(
        self,
        *,
        central: CentralUnit,  # Required for client factory function
        config_provider: ConfigProvider,
        central_info: CentralInfo,
        coordinator_provider: CoordinatorProvider,
        system_info_provider: SystemInfoProvider,
    ) -> None:
        """
        Initialize the client coordinator.

        Args:
        ----
            central: CentralUnit instance (required for client factory)
            config_provider: Provider for configuration access
            central_info: Provider for central system information
            coordinator_provider: Provider for accessing other coordinators
            system_info_provider: Provider for system information

        """
        # Keep central reference only for client factory function
        self._central: Final = central
        self._config_provider: Final = config_provider
        self._central_info: Final = central_info
        self._coordinator_provider: Final = coordinator_provider
        self._system_info_provider: Final = system_info_provider

        # {interface_id, client}
        self._clients: Final[dict[str, hmcl.Client]] = {}
        self._clients_started: bool = False
        self._primary_client: hmcl.Client | None = None

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
    def clients(self) -> tuple[hmcl.Client, ...]:
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
    def poll_clients(self) -> tuple[hmcl.Client, ...]:
        """Return clients that need to poll data."""
        return tuple(client for client in self._clients.values() if not client.supports_push_updates)

    @property
    def primary_client(self) -> hmcl.Client | None:
        """Return the primary client of the backend."""
        if self._primary_client is not None:
            return self._primary_client
        if client := self._get_primary_client():
            self._primary_client = client
        return self._primary_client

    def get_client(self, *, interface_id: str) -> hmcl.Client:
        """
        Return a client by interface_id.

        Args:
        ----
            interface_id: Interface identifier

        Returns:
        -------
            Client instance

        Raises:
        ------
            AioHomematicException: If client not found

        """
        if not self.has_client(interface_id=interface_id):
            raise AioHomematicException(
                i18n.tr(
                    "exception.central.get_client.interface_missing",
                    interface_id=interface_id,
                    name=self._central_info.name,
                )
            )
        return self._clients[interface_id]

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

        # Initialize hub
        await self._coordinator_provider.hub_coordinator.init_hub()

        # Initialize clients
        await self._init_clients()

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
            if client := await hmcl.create_client(
                central=self._central,
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
            self._coordinator_provider.event_coordinator.emit_interface_event(
                interface_id=interface_config.interface_id,
                interface_event_type=InterfaceEventType.PROXY,
                data={EventKey.AVAILABLE: False},
            )

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

    def _get_primary_client(self) -> hmcl.Client | None:
        """
        Get the primary client.

        Returns
        -------
            Primary client or None if not found

        """
        client: hmcl.Client | None = None
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
