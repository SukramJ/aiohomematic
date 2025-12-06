"""Test the HomematicAPI facade."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aiohomematic.api import HomematicAPI
from aiohomematic.central import CentralConfig


class TestHomematicAPIConnect:
    """Test HomematicAPI.connect() factory method."""

    def test_connect_ccu_default(self) -> None:
        """Test connect with CCU backend (default)."""
        api = HomematicAPI.connect(
            host="192.168.1.100",
            username="Admin",
            password="secret",
        )

        assert isinstance(api, HomematicAPI)
        assert api.config.host == "192.168.1.100"
        assert api.config.username == "Admin"
        assert api.config.password == "secret"

    def test_connect_ccu_explicit(self) -> None:
        """Test connect with explicit CCU backend."""
        api = HomematicAPI.connect(
            host="192.168.1.100",
            username="Admin",
            password="secret",
            backend="ccu",
        )

        assert isinstance(api, HomematicAPI)
        assert api.config.host == "192.168.1.100"

    def test_connect_homegear(self) -> None:
        """Test connect with Homegear backend."""
        api = HomematicAPI.connect(
            host="192.168.1.100",
            username="Admin",
            password="secret",
            backend="homegear",
        )

        assert isinstance(api, HomematicAPI)
        assert api.config.host == "192.168.1.100"

    def test_connect_unknown_backend(self) -> None:
        """Test connect with unknown backend raises ValueError."""
        with pytest.raises(ValueError, match="Unknown backend: unknown"):
            HomematicAPI.connect(
                host="192.168.1.100",
                username="Admin",
                password="secret",
                backend="unknown",
            )

    def test_connect_with_central_id(self) -> None:
        """Test connect with custom central_id."""
        api = HomematicAPI.connect(
            host="192.168.1.100",
            username="Admin",
            password="secret",
            central_id="my-ccu",
        )

        assert isinstance(api, HomematicAPI)
        assert api.config.central_id == "my-ccu"
        assert api.config.name == "my-ccu"

    def test_connect_with_tls(self) -> None:
        """Test connect with TLS enabled."""
        api = HomematicAPI.connect(
            host="192.168.1.100",
            username="Admin",
            password="secret",
            tls=True,
            verify_tls=False,
        )

        assert isinstance(api, HomematicAPI)
        assert api.config.tls is True
        assert api.config.verify_tls is False


class TestHomematicAPIContextManager:
    """Test HomematicAPI async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_calls_start_and_stop(self) -> None:
        """Test that context manager calls start on enter and stop on exit."""
        api = HomematicAPI.connect(
            host="192.168.1.100",
            username="Admin",
            password="secret",
        )

        with (
            patch.object(api, "start", new_callable=AsyncMock) as mock_start,
            patch.object(api, "stop", new_callable=AsyncMock) as mock_stop,
        ):
            async with api as context_api:
                assert context_api is api
                mock_start.assert_called_once()
                mock_stop.assert_not_called()

            mock_stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_calls_stop_on_exception(self) -> None:
        """Test that context manager calls stop even when exception occurs."""
        api = HomematicAPI.connect(
            host="192.168.1.100",
            username="Admin",
            password="secret",
        )

        with (
            patch.object(api, "start", new_callable=AsyncMock),
            patch.object(api, "stop", new_callable=AsyncMock) as mock_stop,
        ):
            with pytest.raises(RuntimeError, match="Test error"):
                async with api:
                    raise RuntimeError("Test error")

            mock_stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_propagates_start_exception(self) -> None:
        """Test that context manager propagates exception from start."""
        api = HomematicAPI.connect(
            host="192.168.1.100",
            username="Admin",
            password="secret",
        )

        with (
            patch.object(api, "start", new_callable=AsyncMock, side_effect=ConnectionError("Failed to connect")),
            patch.object(api, "stop", new_callable=AsyncMock) as mock_stop,
        ):
            with pytest.raises(ConnectionError, match="Failed to connect"):
                async with api:
                    pass

            # stop should not be called if start failed
            mock_stop.assert_not_called()


class TestHomematicAPIProperties:
    """Test HomematicAPI properties."""

    def test_central_property_raises_before_start(self) -> None:
        """Test central property raises RuntimeError before start."""
        api = HomematicAPI.connect(
            host="192.168.1.100",
            username="Admin",
            password="secret",
        )

        with pytest.raises(RuntimeError, match="API not started"):
            _ = api.central

    def test_config_property(self) -> None:
        """Test config property returns the configuration."""
        config = CentralConfig.for_ccu(
            name="test",
            host="192.168.1.100",
            username="Admin",
            password="secret",
            central_id="test",
        )
        api = HomematicAPI(config=config)

        assert api.config is config

    def test_is_connected_false_before_start(self) -> None:
        """Test is_connected is False before start."""
        api = HomematicAPI.connect(
            host="192.168.1.100",
            username="Admin",
            password="secret",
        )

        assert api.is_connected is False


class TestHomematicAPIOperations:
    """Test HomematicAPI operations with mocked central."""

    @pytest.fixture
    def api_with_mock_central(self, mock_central: MagicMock) -> HomematicAPI:
        """Create an API instance with mocked central."""
        api = HomematicAPI.connect(
            host="192.168.1.100",
            username="Admin",
            password="secret",
        )
        api._central = mock_central  # noqa: SLF001
        return api

    @pytest.fixture
    def mock_central(self) -> MagicMock:
        """Create a mock CentralUnit."""
        central = MagicMock()
        central.has_clients = True
        central.connection_state.has_any_issue = False
        central.devices = []
        return central

    def test_get_device(self, api_with_mock_central: HomematicAPI, mock_central: MagicMock) -> None:
        """Test get_device calls central.get_device."""
        mock_device = MagicMock()
        mock_central.get_device.return_value = mock_device

        result = api_with_mock_central.get_device(address="VCU0000001")

        assert result is mock_device
        mock_central.get_device.assert_called_once_with(address="VCU0000001")

    def test_is_connected_false_no_clients(self, api_with_mock_central: HomematicAPI, mock_central: MagicMock) -> None:
        """Test is_connected returns False when no clients."""
        mock_central.has_clients = False

        assert api_with_mock_central.is_connected is False

    def test_is_connected_false_with_issues(self, api_with_mock_central: HomematicAPI, mock_central: MagicMock) -> None:
        """Test is_connected returns False when connection issues exist."""
        mock_central.connection_state.has_any_issue = True

        assert api_with_mock_central.is_connected is False

    def test_is_connected_true(self, api_with_mock_central: HomematicAPI) -> None:
        """Test is_connected returns True when connected."""
        assert api_with_mock_central.is_connected is True

    def test_list_devices(self, api_with_mock_central: HomematicAPI, mock_central: MagicMock) -> None:
        """Test list_devices returns devices from central."""
        mock_device = MagicMock()
        mock_device.address = "VCU0000001"
        mock_central.devices = [mock_device]

        devices = list(api_with_mock_central.list_devices())

        assert len(devices) == 1
        assert devices[0].address == "VCU0000001"

    @pytest.mark.asyncio
    async def test_read_value(self, api_with_mock_central: HomematicAPI, mock_central: MagicMock) -> None:
        """Test read_value calls client.get_value."""
        mock_device = MagicMock()
        mock_device.interface_id = "BidCos-RF"
        mock_central.get_device.return_value = mock_device

        mock_client = AsyncMock()
        mock_client.get_value.return_value = True
        mock_central.get_client.return_value = mock_client

        result = await api_with_mock_central.read_value(
            channel_address="VCU0000001:1",
            parameter="STATE",
        )

        assert result is True
        mock_central.get_device.assert_called_once_with(address="VCU0000001")
        mock_central.get_client.assert_called_once_with(interface_id="BidCos-RF")

    @pytest.mark.asyncio
    async def test_read_value_device_not_found(
        self, api_with_mock_central: HomematicAPI, mock_central: MagicMock
    ) -> None:
        """Test read_value raises ValueError when device not found."""
        mock_central.get_device.return_value = None

        with pytest.raises(ValueError, match="Device not found"):
            await api_with_mock_central.read_value(
                channel_address="VCU9999999:1",
                parameter="STATE",
            )

    @pytest.mark.asyncio
    async def test_refresh_data(self, api_with_mock_central: HomematicAPI, mock_central: MagicMock) -> None:
        """Test refresh_data calls fetch_all_device_data on all clients."""
        mock_client1 = AsyncMock()
        mock_client2 = AsyncMock()
        mock_central.clients = [mock_client1, mock_client2]

        await api_with_mock_central.refresh_data()

        mock_client1.fetch_all_device_data.assert_called_once()
        mock_client2.fetch_all_device_data.assert_called_once()

    def test_subscribe_to_updates(self, api_with_mock_central: HomematicAPI, mock_central: MagicMock) -> None:
        """Test subscribe_to_updates calls event_bus.subscribe."""
        mock_unsubscribe = MagicMock()
        mock_central.event_bus.subscribe.return_value = mock_unsubscribe

        received: list[tuple[str, str, Any]] = []

        def callback(address: str, parameter: str, value: Any) -> None:
            received.append((address, parameter, value))

        unsubscribe = api_with_mock_central.subscribe_to_updates(callback=callback)

        assert unsubscribe is mock_unsubscribe
        mock_central.event_bus.subscribe.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_value(self, api_with_mock_central: HomematicAPI, mock_central: MagicMock) -> None:
        """Test write_value calls client.set_value."""
        mock_device = MagicMock()
        mock_device.interface_id = "BidCos-RF"
        mock_central.get_device.return_value = mock_device

        mock_client = AsyncMock()
        mock_central.get_client.return_value = mock_client

        await api_with_mock_central.write_value(
            channel_address="VCU0000001:1",
            parameter="STATE",
            value=True,
        )

        mock_client.set_value.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_value_device_not_found(
        self, api_with_mock_central: HomematicAPI, mock_central: MagicMock
    ) -> None:
        """Test write_value raises ValueError when device not found."""
        mock_central.get_device.return_value = None

        with pytest.raises(ValueError, match="Device not found"):
            await api_with_mock_central.write_value(
                channel_address="VCU9999999:1",
                parameter="STATE",
                value=True,
            )


class TestHomematicAPILifecycle:
    """Test HomematicAPI start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_creates_and_starts_central(self) -> None:
        """Test start creates central and calls start."""
        mock_central = AsyncMock()

        config = CentralConfig.for_ccu(
            name="test",
            host="192.168.1.100",
            username="Admin",
            password="secret",
            central_id="test",
        )

        with patch.object(config, "create_central", return_value=mock_central) as mock_create:
            api = HomematicAPI(config=config)
            await api.start()

            mock_create.assert_called_once()
            mock_central.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_calls_central_stop(self) -> None:
        """Test stop calls central.stop and clears reference."""
        mock_central = AsyncMock()

        api = HomematicAPI.connect(
            host="192.168.1.100",
            username="Admin",
            password="secret",
        )
        api._central = mock_central  # noqa: SLF001

        await api.stop()

        mock_central.stop.assert_called_once()
        assert api._central is None  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_stop_without_start_does_nothing(self) -> None:
        """Test stop without start does nothing."""
        api = HomematicAPI.connect(
            host="192.168.1.100",
            username="Admin",
            password="secret",
        )

        # Should not raise
        await api.stop()


class TestHomematicAPIRetry:
    """Test HomematicAPI retry behavior."""

    @pytest.fixture
    def api_with_mock_central(self, mock_central: MagicMock) -> HomematicAPI:
        """Create an API instance with mocked central."""
        api = HomematicAPI.connect(
            host="192.168.1.100",
            username="Admin",
            password="secret",
        )
        api._central = mock_central  # noqa: SLF001
        return api

    @pytest.fixture
    def mock_central(self) -> MagicMock:
        """Create a mock CentralUnit."""
        central = MagicMock()
        central.has_clients = True
        central.connection_state.has_any_issue = False
        central.devices = []
        return central

    @pytest.mark.asyncio
    async def test_read_value_exhausts_retries(
        self, api_with_mock_central: HomematicAPI, mock_central: MagicMock
    ) -> None:
        """Test read_value raises after exhausting all retries."""
        mock_device = MagicMock()
        mock_device.interface_id = "BidCos-RF"
        mock_central.get_device.return_value = mock_device

        mock_client = AsyncMock()
        # All calls fail with connection error
        mock_client.get_value.side_effect = ConnectionError("Connection refused")
        mock_central.get_client.return_value = mock_client

        with pytest.raises(ConnectionError, match="Connection refused"):
            await api_with_mock_central.read_value(
                channel_address="VCU0000001:1",
                parameter="STATE",
            )

        # Should have tried 3 times (default max_attempts)
        assert mock_client.get_value.call_count == 3

    @pytest.mark.asyncio
    async def test_read_value_no_retry_on_permanent_error(
        self, api_with_mock_central: HomematicAPI, mock_central: MagicMock
    ) -> None:
        """Test read_value does not retry on permanent errors like AuthFailure."""
        from aiohomematic.exceptions import AuthFailure

        mock_device = MagicMock()
        mock_device.interface_id = "BidCos-RF"
        mock_central.get_device.return_value = mock_device

        mock_client = AsyncMock()
        mock_client.get_value.side_effect = AuthFailure("Invalid credentials")
        mock_central.get_client.return_value = mock_client

        with pytest.raises(AuthFailure):
            await api_with_mock_central.read_value(
                channel_address="VCU0000001:1",
                parameter="STATE",
            )

        # Should only be called once - no retry for auth failures
        assert mock_client.get_value.call_count == 1

    @pytest.mark.asyncio
    async def test_read_value_retries_on_connection_error(
        self, api_with_mock_central: HomematicAPI, mock_central: MagicMock
    ) -> None:
        """Test read_value retries on transient connection errors."""
        mock_device = MagicMock()
        mock_device.interface_id = "BidCos-RF"
        mock_central.get_device.return_value = mock_device

        mock_client = AsyncMock()
        # First call fails with ConnectionError, second succeeds
        mock_client.get_value.side_effect = [ConnectionError("Connection refused"), "success"]
        mock_central.get_client.return_value = mock_client

        result = await api_with_mock_central.read_value(
            channel_address="VCU0000001:1",
            parameter="STATE",
        )

        assert result == "success"
        assert mock_client.get_value.call_count == 2

    @pytest.mark.asyncio
    async def test_refresh_data_retries_per_client(
        self, api_with_mock_central: HomematicAPI, mock_central: MagicMock
    ) -> None:
        """Test refresh_data retries each client independently."""
        mock_client1 = AsyncMock()
        mock_client1.interface_id = "HmIP-RF"
        # First call fails, second succeeds
        mock_client1.fetch_all_device_data.side_effect = [ConnectionError("Network error"), None]

        mock_client2 = AsyncMock()
        mock_client2.interface_id = "BidCos-RF"
        # Succeeds on first try
        mock_client2.fetch_all_device_data.return_value = None

        mock_central.clients = [mock_client1, mock_client2]

        await api_with_mock_central.refresh_data()

        # Client 1 should have been called twice (retry)
        assert mock_client1.fetch_all_device_data.call_count == 2
        # Client 2 should have been called once (no retry needed)
        assert mock_client2.fetch_all_device_data.call_count == 1

    @pytest.mark.asyncio
    async def test_write_value_retries_on_timeout(
        self, api_with_mock_central: HomematicAPI, mock_central: MagicMock
    ) -> None:
        """Test write_value retries on timeout errors."""
        mock_device = MagicMock()
        mock_device.interface_id = "BidCos-RF"
        mock_central.get_device.return_value = mock_device

        mock_client = AsyncMock()
        # First call times out, second succeeds
        mock_client.set_value.side_effect = [TimeoutError(), None]
        mock_central.get_client.return_value = mock_client

        await api_with_mock_central.write_value(
            channel_address="VCU0000001:1",
            parameter="STATE",
            value=True,
        )

        assert mock_client.set_value.call_count == 2
