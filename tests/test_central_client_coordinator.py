# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Tests for aiohomematic.central.client_coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aiohomematic.central.client_coordinator import ClientCoordinator
from aiohomematic.central.event_bus import EventBus
from aiohomematic.const import Interface, ProxyInitState


class _FakeInterfaceConfig:
    """Minimal fake InterfaceConfig for testing."""

    def __init__(self, *, interface_id: str, interface: Interface) -> None:
        """Initialize a fake interface config."""
        self.interface_id = interface_id
        self.interface = interface

    def disable(self) -> None:
        """Disable the interface."""


class _FakeClient:
    """Minimal fake Client for testing."""

    def __init__(
        self,
        *,
        interface_id: str,
        interface: Interface,
        available: bool = True,
    ) -> None:
        """Initialize a fake client."""
        self.interface_id = interface_id
        self.interface = interface
        self.available = available
        self.supports_push_updates = True
        self.system_information = MagicMock()
        self.system_information.available_interfaces = frozenset([interface])

    async def deinitialize_proxy(self) -> bool:
        """Deinitialize proxy."""
        return True

    async def initialize_proxy(self) -> ProxyInitState:
        """Initialize proxy."""
        return ProxyInitState.INIT_SUCCESS

    def is_callback_alive(self) -> bool:
        """Check if callback is alive."""
        return True

    async def stop(self) -> None:
        """Stop the client."""


class _FakeHealthTracker:
    """Minimal fake HealthTracker for testing."""

    def record_failed_request(self, *, interface_id: str) -> None:
        """Record a failed request."""

    def record_successful_request(self, *, interface_id: str) -> None:
        """Record a successful request."""

    def register_client(self, *, interface_id: str, interface: Interface) -> None:
        """Register a client with health tracking."""

    def set_primary_interface(self, *, interface: Interface) -> None:
        """Set the primary interface."""

    def unregister_client(self, *, interface_id: str) -> None:
        """Unregister a client from health tracking."""


class _FakeCentral:
    """Minimal fake CentralUnit for testing."""

    def __init__(self, *, name: str = "test_central") -> None:
        """Initialize a fake central."""
        self.name = name
        self.config = MagicMock()
        self.config.enabled_interface_configs = []
        self.cache_coordinator = MagicMock()
        self.cache_coordinator.load_all = AsyncMock()
        self.hub_coordinator = MagicMock()
        self.hub_coordinator.init_hub = AsyncMock()
        self.system_information = MagicMock()
        self.system_information.available_interfaces = frozenset([Interface.BIDCOS_RF, Interface.HMIP_RF])
        self.health_tracker = _FakeHealthTracker()
        self._event_bus = EventBus()

    @property
    def event_bus(self) -> EventBus:
        """Return the event bus."""
        return self._event_bus

    async def create_client_instance(self, *, interface_config: _FakeInterfaceConfig) -> _FakeClient:
        """Create a client instance (implements ClientFactoryProtocol protocol)."""
        return _FakeClient(
            interface_id=interface_config.interface_id,
            interface=interface_config.interface,
        )


class TestClientCoordinatorBasics:
    """Test basic ClientCoordinator functionality."""

    def test_all_clients_active_false_when_no_clients(self) -> None:
        """All clients active should be False when no clients exist."""
        central = _FakeCentral()
        coordinator = ClientCoordinator(
            client_factory=central,
            config_provider=central,
            central_info=central,
            coordinator_provider=central,
            event_bus_provider=central,
            health_tracker=central.health_tracker,
            system_info_provider=central,
        )  # type: ignore[arg-type]

        assert coordinator.all_clients_active is False

    def test_all_clients_active_true_when_all_created(self) -> None:
        """All clients active should be True when all configured clients exist."""
        central = _FakeCentral()
        central.config.enabled_interface_configs = [
            _FakeInterfaceConfig(interface_id="BidCos-RF", interface=Interface.BIDCOS_RF),
        ]

        coordinator = ClientCoordinator(
            client_factory=central,
            config_provider=central,
            central_info=central,
            coordinator_provider=central,
            event_bus_provider=central,
            health_tracker=central.health_tracker,
            system_info_provider=central,
        )  # type: ignore[arg-type]
        client = _FakeClient(interface_id="BidCos-RF", interface=Interface.BIDCOS_RF)
        coordinator._clients["BidCos-RF"] = client  # type: ignore[assignment]

        assert coordinator.all_clients_active is True

    def test_available_property(self) -> None:
        """Available property should return True when all clients are available."""
        central = _FakeCentral()
        coordinator = ClientCoordinator(
            client_factory=central,
            config_provider=central,
            central_info=central,
            coordinator_provider=central,
            event_bus_provider=central,
            health_tracker=central.health_tracker,
            system_info_provider=central,
        )  # type: ignore[arg-type]

        client1 = _FakeClient(interface_id="BidCos-RF", interface=Interface.BIDCOS_RF, available=True)
        client2 = _FakeClient(interface_id="HmIP-RF", interface=Interface.HMIP_RF, available=True)

        coordinator._clients["BidCos-RF"] = client1  # type: ignore[assignment]
        coordinator._clients["HmIP-RF"] = client2  # type: ignore[assignment]

        assert coordinator.available is True

    def test_available_property_false_when_one_unavailable(self) -> None:
        """Available property should return False when any client is unavailable."""
        central = _FakeCentral()
        coordinator = ClientCoordinator(
            client_factory=central,
            config_provider=central,
            central_info=central,
            coordinator_provider=central,
            event_bus_provider=central,
            health_tracker=central.health_tracker,
            system_info_provider=central,
        )  # type: ignore[arg-type]

        client1 = _FakeClient(interface_id="BidCos-RF", interface=Interface.BIDCOS_RF, available=True)
        client2 = _FakeClient(interface_id="HmIP-RF", interface=Interface.HMIP_RF, available=False)

        coordinator._clients["BidCos-RF"] = client1  # type: ignore[assignment]
        coordinator._clients["HmIP-RF"] = client2  # type: ignore[assignment]

        assert coordinator.available is False

    def test_client_coordinator_initialization(self) -> None:
        """ClientCoordinator should initialize with central instance."""
        central = _FakeCentral()
        coordinator = ClientCoordinator(
            client_factory=central,
            config_provider=central,
            central_info=central,
            coordinator_provider=central,
            event_bus_provider=central,
            health_tracker=central.health_tracker,
            system_info_provider=central,
        )  # type: ignore[arg-type]

        assert coordinator._client_factory == central
        assert len(coordinator._clients) == 0
        assert coordinator._clients_started is False
        assert coordinator._primary_client is None

    def test_clients_property(self) -> None:
        """Clients property should return tuple of all clients."""
        central = _FakeCentral()
        coordinator = ClientCoordinator(
            client_factory=central,
            config_provider=central,
            central_info=central,
            coordinator_provider=central,
            event_bus_provider=central,
            health_tracker=central.health_tracker,
            system_info_provider=central,
        )  # type: ignore[arg-type]

        client1 = _FakeClient(interface_id="BidCos-RF", interface=Interface.BIDCOS_RF)
        client2 = _FakeClient(interface_id="HmIP-RF", interface=Interface.HMIP_RF)

        coordinator._clients["BidCos-RF"] = client1  # type: ignore[assignment]
        coordinator._clients["HmIP-RF"] = client2  # type: ignore[assignment]

        clients = coordinator.clients
        assert isinstance(clients, tuple)
        assert len(clients) == 2
        assert client1 in clients  # type: ignore[comparison-overlap]
        assert client2 in clients  # type: ignore[comparison-overlap]

    def test_clients_started_property(self) -> None:
        """Clients started property should track start state."""
        central = _FakeCentral()
        coordinator = ClientCoordinator(
            client_factory=central,
            config_provider=central,
            central_info=central,
            coordinator_provider=central,
            event_bus_provider=central,
            health_tracker=central.health_tracker,
            system_info_provider=central,
        )  # type: ignore[arg-type]

        assert coordinator.clients_started is False

        coordinator._clients_started = True
        assert coordinator.clients_started is True

    def test_has_clients_property(self) -> None:
        """Has clients property should return True when clients exist."""
        central = _FakeCentral()
        coordinator = ClientCoordinator(
            client_factory=central,
            config_provider=central,
            central_info=central,
            coordinator_provider=central,
            event_bus_provider=central,
            health_tracker=central.health_tracker,
            system_info_provider=central,
        )  # type: ignore[arg-type]

        assert coordinator.has_clients is False

        client = _FakeClient(interface_id="BidCos-RF", interface=Interface.BIDCOS_RF)
        coordinator._clients["BidCos-RF"] = client  # type: ignore[assignment]

        assert coordinator.has_clients is True

    def test_interface_ids_property(self) -> None:
        """Interface IDs property should return frozenset of all interface IDs."""
        central = _FakeCentral()
        coordinator = ClientCoordinator(
            client_factory=central,
            config_provider=central,
            central_info=central,
            coordinator_provider=central,
            event_bus_provider=central,
            health_tracker=central.health_tracker,
            system_info_provider=central,
        )  # type: ignore[arg-type]

        client1 = _FakeClient(interface_id="BidCos-RF", interface=Interface.BIDCOS_RF)
        client2 = _FakeClient(interface_id="HmIP-RF", interface=Interface.HMIP_RF)

        coordinator._clients["BidCos-RF"] = client1  # type: ignore[assignment]
        coordinator._clients["HmIP-RF"] = client2  # type: ignore[assignment]

        interface_ids = coordinator.interface_ids
        assert isinstance(interface_ids, frozenset)
        assert "BidCos-RF" in interface_ids
        assert "HmIP-RF" in interface_ids

    def test_interfaces_property(self) -> None:
        """Interfaces property should return frozenset of all interfaces."""
        central = _FakeCentral()
        coordinator = ClientCoordinator(
            client_factory=central,
            config_provider=central,
            central_info=central,
            coordinator_provider=central,
            event_bus_provider=central,
            health_tracker=central.health_tracker,
            system_info_provider=central,
        )  # type: ignore[arg-type]

        client1 = _FakeClient(interface_id="BidCos-RF", interface=Interface.BIDCOS_RF)
        client2 = _FakeClient(interface_id="HmIP-RF", interface=Interface.HMIP_RF)

        coordinator._clients["BidCos-RF"] = client1  # type: ignore[assignment]
        coordinator._clients["HmIP-RF"] = client2  # type: ignore[assignment]

        interfaces = coordinator.interfaces
        assert isinstance(interfaces, frozenset)
        assert Interface.BIDCOS_RF in interfaces
        assert Interface.HMIP_RF in interfaces

    def test_is_alive_property(self) -> None:
        """Is alive property should return True when all callbacks are alive."""
        central = _FakeCentral()
        coordinator = ClientCoordinator(
            client_factory=central,
            config_provider=central,
            central_info=central,
            coordinator_provider=central,
            event_bus_provider=central,
            health_tracker=central.health_tracker,
            system_info_provider=central,
        )  # type: ignore[arg-type]

        client1 = _FakeClient(interface_id="BidCos-RF", interface=Interface.BIDCOS_RF)
        client2 = _FakeClient(interface_id="HmIP-RF", interface=Interface.HMIP_RF)

        coordinator._clients["BidCos-RF"] = client1  # type: ignore[assignment]
        coordinator._clients["HmIP-RF"] = client2  # type: ignore[assignment]

        assert coordinator.is_alive is True

    def test_poll_clients_property(self) -> None:
        """Poll clients property should return clients that need polling."""
        central = _FakeCentral()
        coordinator = ClientCoordinator(
            client_factory=central,
            config_provider=central,
            central_info=central,
            coordinator_provider=central,
            event_bus_provider=central,
            health_tracker=central.health_tracker,
            system_info_provider=central,
        )  # type: ignore[arg-type]

        client1 = _FakeClient(interface_id="BidCos-RF", interface=Interface.BIDCOS_RF)
        client1.supports_push_updates = False  # This client needs polling

        client2 = _FakeClient(interface_id="HmIP-RF", interface=Interface.HMIP_RF)
        client2.supports_push_updates = True  # This client doesn't need polling

        coordinator._clients["BidCos-RF"] = client1  # type: ignore[assignment]
        coordinator._clients["HmIP-RF"] = client2  # type: ignore[assignment]

        poll_clients = coordinator.poll_clients
        assert len(poll_clients) == 1
        assert client1 in poll_clients  # type: ignore[comparison-overlap]
        assert client2 not in poll_clients  # type: ignore[comparison-overlap]


class TestClientCoordinatorGetClient:
    """Test get_client functionality."""

    def test_get_client_raises_when_not_found(self) -> None:
        """Get client should raise exception when client doesn't exist."""
        from aiohomematic.exceptions import AioHomematicException

        central = _FakeCentral()
        coordinator = ClientCoordinator(
            client_factory=central,
            config_provider=central,
            central_info=central,
            coordinator_provider=central,
            event_bus_provider=central,
            health_tracker=central.health_tracker,
            system_info_provider=central,
        )  # type: ignore[arg-type]

        with pytest.raises(AioHomematicException):
            coordinator.get_client(interface_id="NonExistent")

    def test_get_client_success(self) -> None:
        """Get client should return the client when it exists."""
        central = _FakeCentral()
        coordinator = ClientCoordinator(
            client_factory=central,
            config_provider=central,
            central_info=central,
            coordinator_provider=central,
            event_bus_provider=central,
            health_tracker=central.health_tracker,
            system_info_provider=central,
        )  # type: ignore[arg-type]

        client = _FakeClient(interface_id="BidCos-RF", interface=Interface.BIDCOS_RF)
        coordinator._clients["BidCos-RF"] = client  # type: ignore[assignment]

        retrieved = coordinator.get_client(interface_id="BidCos-RF")
        assert retrieved == client

    def test_has_client_false(self) -> None:
        """Has client should return False when client doesn't exist."""
        central = _FakeCentral()
        coordinator = ClientCoordinator(
            client_factory=central,
            config_provider=central,
            central_info=central,
            coordinator_provider=central,
            event_bus_provider=central,
            health_tracker=central.health_tracker,
            system_info_provider=central,
        )  # type: ignore[arg-type]

        assert coordinator.has_client(interface_id="NonExistent") is False

    def test_has_client_true(self) -> None:
        """Has client should return True when client exists."""
        central = _FakeCentral()
        coordinator = ClientCoordinator(
            client_factory=central,
            config_provider=central,
            central_info=central,
            coordinator_provider=central,
            event_bus_provider=central,
            health_tracker=central.health_tracker,
            system_info_provider=central,
        )  # type: ignore[arg-type]

        client = _FakeClient(interface_id="BidCos-RF", interface=Interface.BIDCOS_RF)
        coordinator._clients["BidCos-RF"] = client  # type: ignore[assignment]

        assert coordinator.has_client(interface_id="BidCos-RF") is True


class TestClientCoordinatorLifecycle:
    """Test client lifecycle management."""

    @pytest.mark.asyncio
    async def test_restart_clients(self) -> None:
        """Restart clients should stop and start clients."""
        central = _FakeCentral()

        # Mock stop and start methods at class level
        with (
            patch.object(ClientCoordinator, "stop_clients", new=AsyncMock()) as mock_stop,
            patch.object(ClientCoordinator, "start_clients", new=AsyncMock(return_value=True)) as mock_start,
        ):
            coordinator = ClientCoordinator(
                client_factory=central,
                config_provider=central,
                central_info=central,
                coordinator_provider=central,
                event_bus_provider=central,
                health_tracker=central.health_tracker,
                system_info_provider=central,
            )  # type: ignore[arg-type]
            await coordinator.restart_clients()

            mock_stop.assert_called_once()
            mock_start.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_clients_fails_when_create_fails(self) -> None:
        """Start clients should return False when client creation fails."""
        central = _FakeCentral()

        # Mock _create_clients to return False
        with patch.object(ClientCoordinator, "_create_clients", new=AsyncMock(return_value=False)):
            coordinator = ClientCoordinator(
                client_factory=central,
                config_provider=central,
                central_info=central,
                coordinator_provider=central,
                event_bus_provider=central,
                health_tracker=central.health_tracker,
                system_info_provider=central,
            )  # type: ignore[arg-type]
            result = await coordinator.start_clients()

            assert result is False
            assert coordinator._clients_started is False

    @pytest.mark.asyncio
    async def test_start_clients_success(self) -> None:
        """Start clients should create and initialize all clients."""
        central = _FakeCentral()
        central.config.enabled_interface_configs = [
            _FakeInterfaceConfig(interface_id="BidCos-RF", interface=Interface.BIDCOS_RF),
        ]

        # Mock _create_clients to return True
        with (
            patch.object(ClientCoordinator, "_create_clients", new=AsyncMock(return_value=True)),
            patch.object(ClientCoordinator, "_init_clients", new=AsyncMock()) as mock_init,
        ):
            coordinator = ClientCoordinator(
                client_factory=central,
                config_provider=central,
                central_info=central,
                coordinator_provider=central,
                event_bus_provider=central,
                health_tracker=central.health_tracker,
                system_info_provider=central,
            )  # type: ignore[arg-type]
            result = await coordinator.start_clients()

            assert result is True
            assert coordinator._clients_started is True
            mock_init.assert_called_once()
            central.cache_coordinator.load_all.assert_called_once()
            central.hub_coordinator.init_hub.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_clients(self) -> None:
        """Stop clients should deinitialize and stop all clients."""
        central = _FakeCentral()
        coordinator = ClientCoordinator(
            client_factory=central,
            config_provider=central,
            central_info=central,
            coordinator_provider=central,
            event_bus_provider=central,
            health_tracker=central.health_tracker,
            system_info_provider=central,
        )  # type: ignore[arg-type]

        client1 = _FakeClient(interface_id="BidCos-RF", interface=Interface.BIDCOS_RF)
        client2 = _FakeClient(interface_id="HmIP-RF", interface=Interface.HMIP_RF)

        # Mock the stop and deinitialize methods
        client1.stop = AsyncMock()  # type: ignore[method-assign]
        client2.stop = AsyncMock()  # type: ignore[method-assign]
        client1.deinitialize_proxy = AsyncMock(return_value=True)  # type: ignore[method-assign]
        client2.deinitialize_proxy = AsyncMock(return_value=True)  # type: ignore[method-assign]

        coordinator._clients["BidCos-RF"] = client1  # type: ignore[assignment]
        coordinator._clients["HmIP-RF"] = client2  # type: ignore[assignment]
        coordinator._clients_started = True

        await coordinator.stop_clients()

        # All clients should be stopped
        client1.stop.assert_called_once()
        client2.stop.assert_called_once()
        client1.deinitialize_proxy.assert_called_once()
        client2.deinitialize_proxy.assert_called_once()

        # Clients should be cleared
        assert len(coordinator._clients) == 0
        assert coordinator._clients_started is False


class TestClientCoordinatorPrimaryClient:
    """Test primary client selection."""

    def test_get_primary_client_none_when_no_clients(self) -> None:
        """Primary client should return None when no clients exist."""
        central = _FakeCentral()
        coordinator = ClientCoordinator(
            client_factory=central,
            config_provider=central,
            central_info=central,
            coordinator_provider=central,
            event_bus_provider=central,
            health_tracker=central.health_tracker,
            system_info_provider=central,
        )  # type: ignore[arg-type]

        primary = coordinator.primary_client
        assert primary is None

    def test_get_primary_client_returns_cached(self) -> None:
        """Primary client should return cached client if available."""

        central = _FakeCentral()
        coordinator = ClientCoordinator(
            client_factory=central,
            config_provider=central,
            central_info=central,
            coordinator_provider=central,
            event_bus_provider=central,
            health_tracker=central.health_tracker,
            system_info_provider=central,
        )  # type: ignore[arg-type]

        # Set a cached primary client
        cached_client = _FakeClient(
            interface_id="HmIP-RF",
            interface=Interface.HMIP_RF,
        )
        coordinator._primary_client = cached_client  # type: ignore[assignment]

        primary = coordinator.primary_client
        assert primary == cached_client

    def test_get_primary_client_selects_from_candidates(self) -> None:
        """Primary client should select from available candidates."""
        from aiohomematic.const import PRIMARY_CLIENT_CANDIDATE_INTERFACES

        central = _FakeCentral()
        coordinator = ClientCoordinator(
            client_factory=central,
            config_provider=central,
            central_info=central,
            coordinator_provider=central,
            event_bus_provider=central,
            health_tracker=central.health_tracker,
            system_info_provider=central,
        )  # type: ignore[arg-type]

        # Add clients
        client1 = _FakeClient(interface_id="BidCos-RF", interface=Interface.BIDCOS_RF)
        client2 = _FakeClient(interface_id="HmIP-RF", interface=Interface.HMIP_RF)

        coordinator._clients["BidCos-RF"] = client1  # type: ignore[assignment]
        coordinator._clients["HmIP-RF"] = client2  # type: ignore[assignment]

        primary = coordinator.primary_client

        # Should be one of the primary candidates
        assert primary in [client1, client2]  # type: ignore[comparison-overlap]
        assert primary.interface in PRIMARY_CLIENT_CANDIDATE_INTERFACES


class TestClientCoordinatorIntegration:
    """Integration tests for ClientCoordinator."""

    @pytest.mark.asyncio
    async def test_full_client_lifecycle(self) -> None:
        """Test full client lifecycle (start, use, stop)."""
        central = _FakeCentral()
        central.config.enabled_interface_configs = [
            _FakeInterfaceConfig(interface_id="BidCos-RF", interface=Interface.BIDCOS_RF),
        ]

        # Mock _create_clients and _init_clients
        with (
            patch.object(ClientCoordinator, "_create_clients", new=AsyncMock(return_value=True)),
            patch.object(ClientCoordinator, "_init_clients", new=AsyncMock()),
        ):
            coordinator = ClientCoordinator(
                client_factory=central,
                config_provider=central,
                central_info=central,
                coordinator_provider=central,
                event_bus_provider=central,
                health_tracker=central.health_tracker,
                system_info_provider=central,
            )  # type: ignore[arg-type]

            # Start clients
            result = await coordinator.start_clients()
            assert result is True
            assert coordinator.clients_started is True

            # Add a mock client for stop test
            client = _FakeClient(interface_id="BidCos-RF", interface=Interface.BIDCOS_RF)
            client.stop = AsyncMock()  # type: ignore[method-assign]
            client.deinitialize_proxy = AsyncMock(return_value=True)  # type: ignore[method-assign]
            coordinator._clients["BidCos-RF"] = client  # type: ignore[assignment]

            # Stop clients
            await coordinator.stop_clients()
            assert coordinator.clients_started is False
            assert len(coordinator._clients) == 0
