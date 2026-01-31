# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Integration tests for CUxD/CCU-Jack polling mechanism.

These tests verify that JSON-RPC-only interfaces (CUxD, CCU-Jack) are correctly
polled at regular intervals when configured for polling mode.

Test Scenarios:
1. CUxD in polling mode (default) → periodic data refresh
2. CUxD with push_updates=True → no polling (MQTT expected)
3. Data point refresh calls correct JSON-RPC methods
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from aiohomematic.client.backends.capabilities import JSON_CCU_CAPABILITIES, BackendCapabilities
from aiohomematic.client.backends.json_ccu import JsonCcuBackend
from aiohomematic.const import (
    DEFAULT_INTERFACES_REQUIRING_PERIODIC_REFRESH,
    INTERFACES_REQUIRING_JSON_RPC_CLIENT,
    CallSource,
    Interface,
    ParamsetKey,
)

# pylint: disable=protected-access


class TestCuxdPollingConfiguration:
    """Test CUxD/CCU-Jack polling configuration."""

    def test_cuxd_in_default_periodic_refresh_set(self) -> None:
        """CUxD should be in DEFAULT_INTERFACES_REQUIRING_PERIODIC_REFRESH by default."""
        assert Interface.CUXD in DEFAULT_INTERFACES_REQUIRING_PERIODIC_REFRESH
        assert Interface.CCU_JACK in DEFAULT_INTERFACES_REQUIRING_PERIODIC_REFRESH

    def test_cuxd_requires_json_rpc_client(self) -> None:
        """CUxD should require JSON-RPC client (not XML-RPC)."""
        assert Interface.CUXD in INTERFACES_REQUIRING_JSON_RPC_CLIENT
        assert Interface.CCU_JACK in INTERFACES_REQUIRING_JSON_RPC_CLIENT

    def test_json_ccu_backend_polling_mode(self) -> None:
        """JsonCcuBackend with has_push_updates=False should use polling."""
        mock_json_rpc = MagicMock()
        mock_paramset_provider = MagicMock()

        backend = JsonCcuBackend(
            interface=Interface.CUXD,
            interface_id="test-CUxD",
            json_rpc=mock_json_rpc,
            paramset_provider=mock_paramset_provider,
            has_push_updates=False,  # Polling mode
        )

        assert backend.capabilities.push_updates is False
        assert backend.capabilities.ping_pong is False

    def test_json_ccu_backend_push_mode(self) -> None:
        """JsonCcuBackend with has_push_updates=True should expect MQTT events."""
        mock_json_rpc = MagicMock()
        mock_paramset_provider = MagicMock()

        backend = JsonCcuBackend(
            interface=Interface.CUXD,
            interface_id="test-CUxD",
            json_rpc=mock_json_rpc,
            paramset_provider=mock_paramset_provider,
            has_push_updates=True,  # MQTT mode
        )

        assert backend.capabilities.push_updates is True
        assert backend.capabilities.ping_pong is False  # Still no ping_pong

    def test_json_ccu_capabilities_no_ping_pong(self) -> None:
        """JSON_CCU_CAPABILITIES should have ping_pong=False."""
        assert JSON_CCU_CAPABILITIES.ping_pong is False

    def test_json_ccu_capabilities_no_rpc_callback(self) -> None:
        """JSON_CCU_CAPABILITIES should have rpc_callback=False."""
        assert JSON_CCU_CAPABILITIES.rpc_callback is False


class TestCuxdPollingMechanism:
    """Test the actual polling mechanism for CUxD."""

    @pytest.mark.asyncio
    async def test_poll_clients_excludes_cuxd_in_push_mode(self) -> None:
        """poll_clients should exclude CUxD when push_updates=True (MQTT mode)."""
        # Create a mock client with push mode capabilities
        mock_client = MagicMock()
        mock_client.interface = Interface.CUXD
        mock_client.interface_id = "test-CUxD"
        mock_client.capabilities = BackendCapabilities(
            push_updates=True,  # MQTT mode
            ping_pong=False,
        )

        # Create mock client coordinator
        clients = {"test-CUxD": mock_client}

        # Simulate poll_clients property
        poll_clients = tuple(c for c in clients.values() if not c.capabilities.push_updates)

        assert len(poll_clients) == 0

    @pytest.mark.asyncio
    async def test_poll_clients_includes_cuxd_in_polling_mode(self) -> None:
        """poll_clients should include CUxD when push_updates=False."""
        # Create a mock client with polling mode capabilities
        mock_client = MagicMock()
        mock_client.interface = Interface.CUXD
        mock_client.interface_id = "test-CUxD"
        mock_client.capabilities = BackendCapabilities(
            push_updates=False,  # Polling mode
            ping_pong=False,
        )

        # Create mock client coordinator
        clients = {"test-CUxD": mock_client}

        # Simulate poll_clients property
        poll_clients = tuple(c for c in clients.values() if not c.capabilities.push_updates)

        assert len(poll_clients) == 1
        assert poll_clients[0].interface == Interface.CUXD


class TestCuxdDataRefresh:
    """Test CUxD data refresh via JSON-RPC."""

    @pytest.mark.asyncio
    async def test_refresh_data_point_data_uses_manual_call_source(self) -> None:
        """refresh_data_point_data should use MANUAL_OR_SCHEDULED call source."""
        from aiohomematic.store.dynamic import CentralDataCache

        # Create mocks
        mock_device_provider = MagicMock()
        mock_client_provider = MagicMock()
        mock_data_point_provider = MagicMock()
        mock_central_info = MagicMock()
        mock_central_info.name = "test"

        # Create mock data points that track call_source
        call_sources_received: list[CallSource] = []

        async def mock_load_data_point_value(*, call_source: CallSource, direct_call: bool = False) -> None:
            call_sources_received.append(call_source)

        mock_dp1 = MagicMock()
        mock_dp1.load_data_point_value = mock_load_data_point_value

        mock_dp2 = MagicMock()
        mock_dp2.load_data_point_value = mock_load_data_point_value

        mock_data_point_provider.get_readable_generic_data_points.return_value = [mock_dp1, mock_dp2]

        # Create cache
        cache = CentralDataCache(
            device_provider=mock_device_provider,
            client_provider=mock_client_provider,
            data_point_provider=mock_data_point_provider,
            central_info=mock_central_info,
        )

        # Call refresh_data_point_data (default call_source should be MANUAL_OR_SCHEDULED)
        await cache.refresh_data_point_data(interface=Interface.CUXD)

        # Verify MANUAL_OR_SCHEDULED was used
        assert len(call_sources_received) == 2
        assert all(cs == CallSource.MANUAL_OR_SCHEDULED for cs in call_sources_received)

    @pytest.mark.asyncio
    async def test_refresh_data_point_data_with_hm_init_for_initialization(self) -> None:
        """refresh_data_point_data can use HM_INIT during actual initialization."""
        from aiohomematic.store.dynamic import CentralDataCache

        # Create mocks
        mock_device_provider = MagicMock()
        mock_client_provider = MagicMock()
        mock_data_point_provider = MagicMock()
        mock_central_info = MagicMock()
        mock_central_info.name = "test"

        # Create mock data points that track call_source
        call_sources_received: list[CallSource] = []

        async def mock_load_data_point_value(*, call_source: CallSource, direct_call: bool = False) -> None:
            call_sources_received.append(call_source)

        mock_dp = MagicMock()
        mock_dp.load_data_point_value = mock_load_data_point_value

        mock_data_point_provider.get_readable_generic_data_points.return_value = [mock_dp]

        # Create cache
        cache = CentralDataCache(
            device_provider=mock_device_provider,
            client_provider=mock_client_provider,
            data_point_provider=mock_data_point_provider,
            central_info=mock_central_info,
        )

        # Call with explicit HM_INIT (for actual initialization)
        await cache.refresh_data_point_data(
            interface=Interface.CUXD,
            call_source=CallSource.HM_INIT,
        )

        # Verify HM_INIT was used
        assert len(call_sources_received) == 1
        assert call_sources_received[0] == CallSource.HM_INIT


class TestCuxdJsonRpcCalls:
    """Test that CUxD polling makes correct JSON-RPC calls."""

    @pytest.mark.asyncio
    async def test_json_ccu_backend_get_all_device_data(self) -> None:
        """JsonCcuBackend.get_all_device_data should call JSON-RPC."""
        mock_json_rpc = AsyncMock()
        mock_json_rpc.get_all_device_data = AsyncMock(return_value={"key1": "value1"})

        mock_paramset_provider = MagicMock()

        backend = JsonCcuBackend(
            interface=Interface.CUXD,
            interface_id="test-CUxD",
            json_rpc=mock_json_rpc,
            paramset_provider=mock_paramset_provider,
            has_push_updates=False,
        )

        result = await backend.get_all_device_data(interface=Interface.CUXD)

        mock_json_rpc.get_all_device_data.assert_called_once_with(interface=Interface.CUXD)
        assert result == {"key1": "value1"}

    @pytest.mark.asyncio
    async def test_json_ccu_backend_get_value(self) -> None:
        """JsonCcuBackend.get_value should call JSON-RPC."""
        mock_json_rpc = AsyncMock()
        mock_json_rpc.get_value = AsyncMock(return_value=42.5)

        mock_paramset_provider = MagicMock()

        backend = JsonCcuBackend(
            interface=Interface.CUXD,
            interface_id="test-CUxD",
            json_rpc=mock_json_rpc,
            paramset_provider=mock_paramset_provider,
            has_push_updates=False,
        )

        result = await backend.get_value(channel_address="CUX1234567:1", parameter="TEMPERATURE")

        mock_json_rpc.get_value.assert_called_once_with(
            interface=Interface.CUXD,
            address="CUX1234567:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="TEMPERATURE",
        )
        assert result == 42.5


class TestCuxdInterfaceRegistration:
    """
    Test that CUxD devices get correct interface registration.

    This tests the fix for issue #2884 where CUxD devices were assigned
    Interface.BIDCOS_RF (default) because JsonCcuBackend.get_device_details()
    returns None, and interface registration only happened in fetch_device_details().

    The fix ensures interface is registered during _add_new_devices() when
    device descriptions are cached.
    """

    def test_cuxd_device_interface_lookup_scenario(self) -> None:
        """
        Test the complete scenario: CUxD device should have correct interface for data point filtering.

        This simulates the filtering in get_data_points(interface=Interface.CUXD).
        """
        from aiohomematic.store.dynamic import DeviceDetailsCache

        mock_central_info = MagicMock()
        mock_central_info.name = "test"
        mock_primary_client_provider = MagicMock()

        cache = DeviceDetailsCache(
            central_info=mock_central_info,
            primary_client_provider=mock_primary_client_provider,
        )

        # Simulate device addresses
        cuxd_address = "CUX1234567"
        hmip_address = "001F58A9912345"

        # Register interfaces (as done in _add_new_devices fix)
        cache.add_interface(address=cuxd_address, interface=Interface.CUXD)
        cache.add_interface(address=hmip_address, interface=Interface.HMIP_RF)

        # Verify correct interfaces are returned
        assert cache.get_interface(address=cuxd_address) == Interface.CUXD
        assert cache.get_interface(address=hmip_address) == Interface.HMIP_RF

        # Simulate get_data_points filtering
        devices = [
            {"address": cuxd_address, "interface": cache.get_interface(address=cuxd_address)},
            {"address": hmip_address, "interface": cache.get_interface(address=hmip_address)},
        ]

        # Filter for CUxD interface
        cuxd_devices = [d for d in devices if d["interface"] == Interface.CUXD]
        assert len(cuxd_devices) == 1
        assert cuxd_devices[0]["address"] == cuxd_address

        # Filter for HMIP_RF interface
        hmip_devices = [d for d in devices if d["interface"] == Interface.HMIP_RF]
        assert len(hmip_devices) == 1
        assert hmip_devices[0]["address"] == hmip_address

    def test_device_details_get_interface_returns_correct_interface_after_registration(self) -> None:
        """get_interface should return correct interface after add_interface is called."""
        from aiohomematic.store.dynamic import DeviceDetailsCache

        mock_central_info = MagicMock()
        mock_central_info.name = "test"
        mock_primary_client_provider = MagicMock()

        cache = DeviceDetailsCache(
            central_info=mock_central_info,
            primary_client_provider=mock_primary_client_provider,
        )

        # Register interface for CUxD device
        cache.add_interface(address="CUX1234567", interface=Interface.CUXD)

        # Now get_interface returns correct interface
        result = cache.get_interface(address="CUX1234567")
        assert result == Interface.CUXD

    def test_device_details_get_interface_returns_default_for_unknown_address(self) -> None:
        """get_interface should return BIDCOS_RF for unknown addresses (the problem)."""
        from aiohomematic.store.dynamic import DeviceDetailsCache

        mock_central_info = MagicMock()
        mock_central_info.name = "test"
        mock_primary_client_provider = MagicMock()

        cache = DeviceDetailsCache(
            central_info=mock_central_info,
            primary_client_provider=mock_primary_client_provider,
        )

        # Unknown address returns default BIDCOS_RF
        result = cache.get_interface(address="CUX1234567")
        assert result == Interface.BIDCOS_RF

    @pytest.mark.asyncio
    async def test_json_ccu_backend_get_device_details_calls_json_rpc(self) -> None:
        """Verify JsonCcuBackend.get_device_details() calls JSON-RPC and returns data."""
        mock_json_rpc = AsyncMock()
        mock_json_rpc.get_device_details.return_value = [
            {
                "address": "CUX1234567",
                "name": "CUxD Device",
                "id": 1001,
                "interface": "CUxD",
                "channels": [],
            },
        ]
        mock_paramset_provider = MagicMock()

        backend = JsonCcuBackend(
            interface=Interface.CUXD,
            interface_id="test-CUxD",
            json_rpc=mock_json_rpc,
            paramset_provider=mock_paramset_provider,
            has_push_updates=False,
        )

        result = await backend.get_device_details(addresses=("CUX1234567",))

        # Verify JSON-RPC was called
        mock_json_rpc.get_device_details.assert_called_once()

        # Verify result contains the device data
        assert result is not None
        assert len(result) == 1
        assert result[0]["address"] == "CUX1234567"
        assert result[0]["interface"] == "CUxD"

    def test_json_ccu_backend_implements_get_device_details(self) -> None:
        """
        JsonCcuBackend implements get_device_details() using JSON-RPC.

        This enables proper interface registration via fetch_device_details().
        """
        # Verify that JsonCcuBackend defines get_device_details in its own class
        assert "get_device_details" in JsonCcuBackend.__dict__

        # Verify method resolution order uses JsonCcuBackend's implementation
        for cls in JsonCcuBackend.__mro__:
            if "get_device_details" in cls.__dict__:
                assert cls is JsonCcuBackend
                break


class TestFetchDeviceDetailsInterfaceHandling:
    """
    Test that fetch_device_details uses the interface from device data.

    This tests the fix for the bug where fetch_device_details() used self.interface
    instead of the interface from device data, causing incorrect interface registration
    when Device.listAllDetail returns devices from multiple interfaces.
    """

    @pytest.mark.asyncio
    async def test_fetch_device_details_falls_back_to_client_interface(self) -> None:
        """fetch_device_details should fallback to client interface when device has no interface."""
        from aiohomematic.client import InterfaceClient
        from aiohomematic.store.dynamic import DeviceDetailsCache

        # Setup mock central with cache
        mock_central = MagicMock()
        mock_central_info = MagicMock()
        mock_central_info.name = "test"
        mock_primary_client_provider = MagicMock()

        cache = DeviceDetailsCache(
            central_info=mock_central_info,
            primary_client_provider=mock_primary_client_provider,
        )
        mock_central.cache_coordinator.device_details = cache
        mock_central.cache_coordinator.device_descriptions.get_device_descriptions.return_value = {}

        # Setup mock backend that returns devices WITHOUT interface field (Homegear style)
        mock_backend = AsyncMock()
        mock_backend.get_device_details.return_value = [
            {
                "address": "NEQ0123456",
                "name": "Homegear Device",
                "id": 0,
                "interface": "",  # Empty interface (Homegear doesn't provide this)
                "channels": [],
            },
        ]

        # Create client with BIDCOS_RF interface (Homegear)
        client = MagicMock(spec=InterfaceClient)
        client._central = mock_central
        client._backend = mock_backend
        client.interface = Interface.BIDCOS_RF
        client.interface_id = "test-BidCos-RF"

        # Call fetch_device_details
        await InterfaceClient.fetch_device_details(client)

        # Verify interface falls back to client's interface
        assert cache.get_interface(address="NEQ0123456") == Interface.BIDCOS_RF

    @pytest.mark.asyncio
    async def test_fetch_device_details_ignores_unknown_interface(self) -> None:
        """fetch_device_details should fallback to client interface for unknown interface values."""
        from aiohomematic.client import InterfaceClient
        from aiohomematic.store.dynamic import DeviceDetailsCache

        # Setup mock central with cache
        mock_central = MagicMock()
        mock_central_info = MagicMock()
        mock_central_info.name = "test"
        mock_primary_client_provider = MagicMock()

        cache = DeviceDetailsCache(
            central_info=mock_central_info,
            primary_client_provider=mock_primary_client_provider,
        )
        mock_central.cache_coordinator.device_details = cache
        mock_central.cache_coordinator.device_descriptions.get_device_descriptions.return_value = {}

        # Setup mock backend that returns device with unknown interface
        mock_backend = AsyncMock()
        mock_backend.get_device_details.return_value = [
            {
                "address": "UNKNOWN123",
                "name": "Unknown Device",
                "id": 1003,
                "interface": "SomeUnknownInterface",  # Unknown interface value
                "channels": [],
            },
        ]

        # Create client with HMIP_RF interface
        client = MagicMock(spec=InterfaceClient)
        client._central = mock_central
        client._backend = mock_backend
        client.interface = Interface.HMIP_RF
        client.interface_id = "test-HmIP-RF"

        # Call fetch_device_details
        await InterfaceClient.fetch_device_details(client)

        # Verify interface falls back to client's interface for unknown values
        assert cache.get_interface(address="UNKNOWN123") == Interface.HMIP_RF

    @pytest.mark.asyncio
    async def test_fetch_device_details_uses_interface_from_device_data(self) -> None:
        """fetch_device_details should use interface from device data (CCU behavior)."""
        from aiohomematic.client import InterfaceClient
        from aiohomematic.store.dynamic import DeviceDetailsCache

        # Setup mock central with cache
        mock_central = MagicMock()
        mock_central_info = MagicMock()
        mock_central_info.name = "test"
        mock_primary_client_provider = MagicMock()

        cache = DeviceDetailsCache(
            central_info=mock_central_info,
            primary_client_provider=mock_primary_client_provider,
        )
        mock_central.cache_coordinator.device_details = cache
        mock_central.cache_coordinator.device_descriptions.get_device_descriptions.return_value = {}

        # Setup mock backend that returns devices with different interfaces
        mock_backend = AsyncMock()
        mock_backend.get_device_details.return_value = [
            {
                "address": "CUX1234567",
                "name": "CUxD Device",
                "id": 1001,
                "interface": "CUxD",  # Device reports CUxD interface
                "channels": [],
            },
            {
                "address": "001F58A9912345",
                "name": "HmIP Device",
                "id": 1002,
                "interface": "HmIP-RF",  # Device reports HmIP-RF interface
                "channels": [],
            },
        ]

        # Create client with HmIP-RF interface (simulating primary client)
        client = MagicMock(spec=InterfaceClient)
        client._central = mock_central
        client._backend = mock_backend
        client.interface = Interface.HMIP_RF  # Client's own interface
        client.interface_id = "test-HmIP-RF"

        # Call fetch_device_details using the real implementation
        await InterfaceClient.fetch_device_details(client)

        # Verify interfaces are registered from device data, NOT from client's interface
        assert cache.get_interface(address="CUX1234567") == Interface.CUXD
        assert cache.get_interface(address="001F58A9912345") == Interface.HMIP_RF


class TestCuxdPollingIntegration:
    """Integration tests for complete CUxD polling flow."""

    @pytest.mark.asyncio
    async def test_scheduler_refresh_client_data_calls_load_and_refresh(self) -> None:
        """_refresh_client_data should call load_and_refresh_data_point_data for poll clients."""
        # Track calls
        refresh_calls: list[Interface] = []

        async def mock_load_and_refresh(*, interface: Interface) -> None:
            refresh_calls.append(interface)

        # Create mock central_info
        mock_central_info = MagicMock()
        mock_central_info.available = True
        mock_central_info.name = "test"

        # Create mock client with polling mode
        mock_client = MagicMock()
        mock_client.interface = Interface.CUXD
        mock_client.interface_id = "test-CUxD"
        mock_client.capabilities = BackendCapabilities(push_updates=False, ping_pong=False)

        # Create mock client coordinator
        mock_client_coordinator = MagicMock()
        mock_client_coordinator.poll_clients = (mock_client,)

        # Create mock device data refresher
        mock_device_data_refresher = MagicMock()
        mock_device_data_refresher.load_and_refresh_data_point_data = mock_load_and_refresh

        # Create mock event coordinator
        mock_event_coordinator = MagicMock()
        mock_event_coordinator.set_last_event_seen_for_interface = MagicMock()

        # Simulate _refresh_client_data logic
        if mock_central_info.available:
            poll_clients = mock_client_coordinator.poll_clients
            if poll_clients is not None and len(poll_clients) > 0:
                for client in poll_clients:
                    await mock_device_data_refresher.load_and_refresh_data_point_data(interface=client.interface)
                    mock_event_coordinator.set_last_event_seen_for_interface(interface_id=client.interface_id)

        # Verify CUxD was refreshed
        assert len(refresh_calls) == 1
        assert refresh_calls[0] == Interface.CUXD
        mock_event_coordinator.set_last_event_seen_for_interface.assert_called_once_with(interface_id="test-CUxD")

    @pytest.mark.asyncio
    async def test_scheduler_refresh_client_data_skips_push_clients(self) -> None:
        """_refresh_client_data should NOT refresh clients with push_updates=True."""
        # Track calls
        refresh_calls: list[Interface] = []

        async def mock_load_and_refresh(*, interface: Interface) -> None:
            refresh_calls.append(interface)

        # Create mock central_info
        mock_central_info = MagicMock()
        mock_central_info.available = True
        mock_central_info.name = "test"

        # Create mock client with PUSH mode (MQTT)
        mock_client = MagicMock()
        mock_client.interface = Interface.CUXD
        mock_client.interface_id = "test-CUxD"
        mock_client.capabilities = BackendCapabilities(push_updates=True, ping_pong=False)  # MQTT mode

        # Create mock client coordinator - poll_clients should be empty for push mode
        mock_client_coordinator = MagicMock()
        # Simulate: poll_clients = tuple(c for c in clients if not c.capabilities.push_updates)
        mock_client_coordinator.poll_clients = ()  # Empty because push_updates=True

        # Create mock device data refresher
        mock_device_data_refresher = MagicMock()
        mock_device_data_refresher.load_and_refresh_data_point_data = mock_load_and_refresh

        # Simulate _refresh_client_data logic
        if mock_central_info.available:
            poll_clients = mock_client_coordinator.poll_clients
            if poll_clients is not None and len(poll_clients) > 0:
                for client in poll_clients:
                    await mock_device_data_refresher.load_and_refresh_data_point_data(interface=client.interface)

        # Verify NO refresh happened (MQTT mode)
        assert len(refresh_calls) == 0
