# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for backend detection module."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aiohomematic.backend_detection import (
    _ABORT_DETECTION,
    BackendDetectionResult,
    DetectionConfig,
    _determine_backend,
    _probe_xml_rpc_port,
    _query_ccu_interfaces,
    detect_backend,
)
from aiohomematic.const import Backend, Interface, SystemInformation, TimeoutConfig


class TestDetermineBackend:
    """Tests for _determine_backend function."""

    def test_determine_backend_ccu(self) -> None:
        """Test detection of CCU backend."""
        assert _determine_backend(version="3.61.345") == Backend.CCU
        assert _determine_backend(version="3.75.6.20240316") == Backend.CCU
        assert _determine_backend(version="2.55.10") == Backend.CCU
        assert _determine_backend(version="") == Backend.CCU

    def test_determine_backend_homegear(self) -> None:
        """Test detection of Homegear backend."""
        assert _determine_backend(version="Homegear 0.8.0") == Backend.HOMEGEAR
        assert _determine_backend(version="homegear 0.7.5") == Backend.HOMEGEAR
        assert _determine_backend(version="HOMEGEAR") == Backend.HOMEGEAR

    def test_determine_backend_pydevccu(self) -> None:
        """Test detection of PyDevCCU backend."""
        assert _determine_backend(version="pydevccu 2.1") == Backend.PYDEVCCU
        assert _determine_backend(version="PyDevCCU 2.0") == Backend.PYDEVCCU
        assert _determine_backend(version="PYDEVCCU") == Backend.PYDEVCCU


class TestProbeXmlRpcPort:
    """Tests for _probe_xml_rpc_port function."""

    @pytest.mark.asyncio
    async def test_probe_xml_rpc_port_connection_error(self) -> None:
        """Test XML-RPC probe with connection error."""
        mock_proxy = MagicMock()
        mock_proxy.do_init = AsyncMock(side_effect=ConnectionRefusedError("Connection refused"))
        mock_proxy.stop = AsyncMock()

        with patch("aiohomematic.backend_detection.AioXmlRpcProxy", return_value=mock_proxy):
            result = await _probe_xml_rpc_port(
                host="192.168.1.100",
                port=2010,
                tls=False,
                username="",
                password="",
                verify_tls=False,
                request_timeout=5.0,
            )

        assert result is None
        mock_proxy.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_probe_xml_rpc_port_no_connection_exception(self) -> None:
        """Test XML-RPC probe with NoConnectionException returns None instead of raising."""
        from aiohomematic.exceptions import NoConnectionException

        mock_proxy = MagicMock()
        mock_proxy.do_init = AsyncMock(side_effect=NoConnectionException("Connection refused"))
        mock_proxy.stop = AsyncMock()

        with patch("aiohomematic.backend_detection.AioXmlRpcProxy", return_value=mock_proxy):
            result = await _probe_xml_rpc_port(
                host="192.168.1.100",
                port=2010,
                tls=False,
                username="",
                password="",
                verify_tls=False,
                request_timeout=5.0,
            )

        # NoConnectionException should not be raised, instead return None to try next port
        assert result is None
        mock_proxy.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_probe_xml_rpc_port_no_getversion(self) -> None:
        """Test XML-RPC probe when getVersion is not available."""
        mock_proxy = MagicMock()
        mock_proxy.do_init = AsyncMock()
        mock_proxy.supported_methods = ("system.listMethods", "ping")
        mock_proxy.stop = AsyncMock()

        with patch("aiohomematic.backend_detection.AioXmlRpcProxy", return_value=mock_proxy):
            result = await _probe_xml_rpc_port(
                host="192.168.1.100",
                port=2010,
                tls=False,
                username="",
                password="",
                verify_tls=False,
                request_timeout=5.0,
            )

        assert result == ""
        mock_proxy.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_probe_xml_rpc_port_success(self) -> None:
        """Test successful XML-RPC probe."""
        mock_proxy = MagicMock()
        mock_proxy.do_init = AsyncMock()
        mock_proxy.supported_methods = ("system.listMethods", "getVersion")
        mock_proxy.getVersion = AsyncMock(return_value="3.61.345")
        mock_proxy.stop = AsyncMock()

        with patch("aiohomematic.backend_detection.AioXmlRpcProxy", return_value=mock_proxy):
            result = await _probe_xml_rpc_port(
                host="192.168.1.100",
                port=2010,
                tls=False,
                username="admin",
                password="secret",
                verify_tls=False,
                request_timeout=5.0,
            )

        assert result == "3.61.345"
        mock_proxy.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_probe_xml_rpc_port_timeout(self) -> None:
        """Test XML-RPC probe with timeout returns abort signal."""
        mock_proxy = MagicMock()

        async def slow_do_init() -> None:
            await asyncio.sleep(10)

        mock_proxy.do_init = slow_do_init
        mock_proxy.stop = AsyncMock()

        with patch("aiohomematic.backend_detection.AioXmlRpcProxy", return_value=mock_proxy):
            result = await _probe_xml_rpc_port(
                host="192.168.1.100",
                port=2010,
                tls=False,
                username="",
                password="",
                verify_tls=False,
                request_timeout=0.1,
            )

        # Timeout should signal abort detection (host likely unreachable)
        assert result is _ABORT_DETECTION
        mock_proxy.stop.assert_called_once()


class TestQueryCcuInterfaces:
    """Tests for _query_ccu_interfaces function."""

    @pytest.mark.asyncio
    async def test_query_ccu_interfaces_connection_error(self) -> None:
        """Test interface query when connection fails."""
        with patch(
            "aiohomematic.backend_detection.AioJsonRpcAioHttpClient",
            side_effect=ConnectionRefusedError("Connection refused"),
        ):
            result = await _query_ccu_interfaces(
                host="192.168.1.100",
                username="admin",
                password="secret",
                verify_tls=False,
                client_session=None,
            )

        assert result == ((), None, None)

    @pytest.mark.asyncio
    async def test_query_ccu_interfaces_no_connection_exception_tries_next_port(self) -> None:
        """Test that NoConnectionException on first port tries second port."""
        from aiohomematic.exceptions import NoConnectionException

        call_count = 0

        def mock_client_factory(**kwargs: Any) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First port (HTTP) fails with NoConnectionException
                mock_client = MagicMock()
                mock_client.get_system_information = AsyncMock(side_effect=NoConnectionException("Connection refused"))
                mock_client.logout = AsyncMock()
                return mock_client
            # Second port (HTTPS) succeeds
            mock_client = MagicMock()
            mock_client.get_system_information = AsyncMock(
                return_value=SystemInformation(
                    available_interfaces=("HmIP-RF",),
                    auth_enabled=True,
                )
            )
            mock_client.is_present = AsyncMock(return_value=True)
            mock_client.logout = AsyncMock()
            return mock_client

        with patch(
            "aiohomematic.backend_detection.AioJsonRpcAioHttpClient",
            side_effect=mock_client_factory,
        ):
            result = await _query_ccu_interfaces(
                host="192.168.1.100",
                username="admin",
                password="secret",
                verify_tls=False,
                client_session=None,
            )

        # Both ports should be tried
        assert call_count == 2
        assert result == ((Interface.HMIP_RF,), True, None)

    @pytest.mark.asyncio
    async def test_query_ccu_interfaces_not_present_skipped(self) -> None:
        """Test that interfaces where is_present returns False are skipped."""
        mock_system_info = SystemInformation(
            available_interfaces=("HmIP-RF", "CUxD", "BidCos-RF"),
            auth_enabled=True,
        )

        async def mock_is_present(*, interface: Interface) -> bool:
            # CUxD is installed but not running
            return interface != Interface.CUXD

        mock_client = MagicMock()
        mock_client.get_system_information = AsyncMock(return_value=mock_system_info)
        mock_client.is_present = mock_is_present
        mock_client.logout = AsyncMock()

        with patch(
            "aiohomematic.backend_detection.AioJsonRpcAioHttpClient",
            return_value=mock_client,
        ):
            result = await _query_ccu_interfaces(
                host="192.168.1.100",
                username="admin",
                password="secret",
                verify_tls=False,
                client_session=None,
            )

        # CUxD should be skipped because is_present returned False
        assert result == ((Interface.HMIP_RF, Interface.BIDCOS_RF), True, None)

    @pytest.mark.asyncio
    async def test_query_ccu_interfaces_success(self) -> None:
        """Test successful interface query using AioJsonRpcAioHttpClient."""
        mock_system_info = SystemInformation(
            available_interfaces=("HmIP-RF", "BidCos-RF", "BidCos-Wired"),
            auth_enabled=True,
        )

        mock_client = MagicMock()
        mock_client.get_system_information = AsyncMock(return_value=mock_system_info)
        mock_client.is_present = AsyncMock(return_value=True)
        mock_client.logout = AsyncMock()

        with patch(
            "aiohomematic.backend_detection.AioJsonRpcAioHttpClient",
            return_value=mock_client,
        ):
            result = await _query_ccu_interfaces(
                host="192.168.1.100",
                username="admin",
                password="secret",
                verify_tls=False,
                client_session=None,
            )

        assert result == ((Interface.HMIP_RF, Interface.BIDCOS_RF, Interface.BIDCOS_WIRED), True, None)
        mock_client.logout.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_ccu_interfaces_tries_both_ports(self) -> None:
        """Test that both HTTP and HTTPS ports are tried."""
        call_count = 0

        def mock_client_factory(**kwargs: Any) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionRefusedError("HTTP failed")
            # Second call (HTTPS) succeeds
            mock_client = MagicMock()
            mock_client.get_system_information = AsyncMock(
                return_value=SystemInformation(
                    available_interfaces=("HmIP-RF",),
                    auth_enabled=True,
                )
            )
            mock_client.is_present = AsyncMock(return_value=True)
            mock_client.logout = AsyncMock()
            return mock_client

        with patch(
            "aiohomematic.backend_detection.AioJsonRpcAioHttpClient",
            side_effect=mock_client_factory,
        ):
            result = await _query_ccu_interfaces(
                host="192.168.1.100",
                username="admin",
                password="secret",
                verify_tls=False,
                client_session=None,
            )

        assert call_count == 2
        assert result == ((Interface.HMIP_RF,), True, None)

    @pytest.mark.asyncio
    async def test_query_ccu_interfaces_with_unknown_interface(self) -> None:
        """Test interface query with unknown interface names."""
        mock_system_info = SystemInformation(
            available_interfaces=("HmIP-RF", "UnknownInterface", "BidCos-RF"),
            auth_enabled=False,
        )

        mock_client = MagicMock()
        mock_client.get_system_information = AsyncMock(return_value=mock_system_info)
        mock_client.is_present = AsyncMock(return_value=True)
        mock_client.logout = AsyncMock()

        with patch(
            "aiohomematic.backend_detection.AioJsonRpcAioHttpClient",
            return_value=mock_client,
        ):
            result = await _query_ccu_interfaces(
                host="192.168.1.100",
                username="admin",
                password="secret",
                verify_tls=False,
                client_session=None,
            )

        # Unknown interface should be skipped
        assert result == ((Interface.HMIP_RF, Interface.BIDCOS_RF), False, None)


class TestDetectBackend:
    """Tests for detect_backend function."""

    @pytest.mark.asyncio
    async def test_detect_backend_json_rpc_fails(self) -> None:
        """Test detection when JSON-RPC query fails, fallback to detected interface."""
        config = DetectionConfig(
            host="192.168.1.100",
            username="admin",
            password="secret",
        )

        with (
            patch(
                "aiohomematic.backend_detection._probe_xml_rpc_port",
                new_callable=AsyncMock,
                return_value="3.61.345",
            ),
            patch(
                "aiohomematic.backend_detection._query_ccu_interfaces",
                new_callable=AsyncMock,
                return_value=((), None, None),
            ),
        ):
            result = await detect_backend(config=config)

        assert result is not None
        assert result.backend == Backend.CCU
        # Falls back to the interface we connected to (HmIP-RF is first)
        assert result.available_interfaces == (Interface.HMIP_RF,)

    @pytest.mark.asyncio
    async def test_detect_backend_no_connection(self) -> None:
        """Test detection when no backend responds."""
        config = DetectionConfig(
            host="192.168.1.100",
        )

        with patch(
            "aiohomematic.backend_detection._probe_xml_rpc_port",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await detect_backend(config=config)

        assert result is None

    @pytest.mark.asyncio
    async def test_detect_backend_tls_fallback(self) -> None:
        """Test detection falls back to TLS ports."""
        config = DetectionConfig(
            host="192.168.1.100",
        )

        # First 3 calls (non-TLS) fail, 4th call (TLS HmIP-RF) succeeds
        call_count = 0

        async def mock_probe(**kwargs: Any) -> str | None:
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                return None
            return "3.61.345"

        with (
            patch(
                "aiohomematic.backend_detection._probe_xml_rpc_port",
                side_effect=mock_probe,
            ),
            patch(
                "aiohomematic.backend_detection._query_ccu_interfaces",
                new_callable=AsyncMock,
                return_value=((Interface.HMIP_RF,), None, None),
            ),
        ):
            result = await detect_backend(config=config)

        assert result is not None
        assert result.tls is True
        assert result.detected_port == 42010  # TLS port for HmIP-RF

    @pytest.mark.asyncio
    async def test_detect_ccu_backend(self) -> None:
        """Test detection of CCU backend with multiple interfaces."""
        config = DetectionConfig(
            host="192.168.1.100",
            username="admin",
            password="secret",
        )

        with (
            patch(
                "aiohomematic.backend_detection._probe_xml_rpc_port",
                new_callable=AsyncMock,
                return_value="3.61.345",
            ),
            patch(
                "aiohomematic.backend_detection._query_ccu_interfaces",
                new_callable=AsyncMock,
                return_value=((Interface.HMIP_RF, Interface.BIDCOS_RF), True, False),
            ),
        ):
            result = await detect_backend(config=config)

        assert result is not None
        assert result.backend == Backend.CCU
        assert result.available_interfaces == (Interface.HMIP_RF, Interface.BIDCOS_RF)
        assert result.version == "3.61.345"
        assert result.auth_enabled is True
        assert result.https_redirect_enabled is False

    @pytest.mark.asyncio
    async def test_detect_homegear_backend(self) -> None:
        """Test detection of Homegear backend."""
        config = DetectionConfig(
            host="192.168.1.100",
            username="",
            password="",
        )

        with patch(
            "aiohomematic.backend_detection._probe_xml_rpc_port",
            new_callable=AsyncMock,
            return_value="Homegear 0.8.0",
        ):
            result = await detect_backend(config=config)

        assert result is not None
        assert result.backend == Backend.HOMEGEAR
        assert result.available_interfaces == (Interface.BIDCOS_RF,)
        assert result.version == "Homegear 0.8.0"
        assert result.auth_enabled is None

    @pytest.mark.asyncio
    async def test_detect_pydevccu_backend(self) -> None:
        """Test detection of PyDevCCU backend."""
        config = DetectionConfig(
            host="192.168.1.100",
        )

        with patch(
            "aiohomematic.backend_detection._probe_xml_rpc_port",
            new_callable=AsyncMock,
            return_value="pydevccu 2.1",
        ):
            result = await detect_backend(config=config)

        assert result is not None
        assert result.backend == Backend.PYDEVCCU
        assert result.available_interfaces == (Interface.BIDCOS_RF,)
        assert result.version == "pydevccu 2.1"

    @pytest.mark.asyncio
    async def test_detect_pydevccu_with_hmip_port_refused(self) -> None:
        """
        Test detection of PyDevCCU when HmIP-RF port is refused but BidCos-RF works.

        This simulates the real-world scenario where PyDevCCU only runs on port 2001
        (BidCos-RF) and connection to port 2010 (HmIP-RF) is refused.
        """
        from aiohomematic.const import DETECTION_PORT_BIDCOS_RF, DETECTION_PORT_HMIP_RF

        config = DetectionConfig(
            host="localhost",
        )

        call_count = 0

        async def mock_probe(**kwargs: Any) -> str | None:
            nonlocal call_count
            call_count += 1
            port = kwargs.get("port")
            # HmIP-RF ports (2010, 42010) fail with connection refused
            if port in DETECTION_PORT_HMIP_RF:
                return None
            # BidCos-RF port (2001) succeeds
            if port == DETECTION_PORT_BIDCOS_RF[0]:
                return "pydevccu 2.1"
            return None

        with patch(
            "aiohomematic.backend_detection._probe_xml_rpc_port",
            side_effect=mock_probe,
        ):
            result = await detect_backend(config=config)

        # Should have tried HmIP-RF (port 2010) first, then BidCos-RF (port 2001)
        assert call_count >= 2
        assert result is not None
        assert result.backend == Backend.PYDEVCCU
        assert result.available_interfaces == (Interface.BIDCOS_RF,)
        assert result.detected_port == DETECTION_PORT_BIDCOS_RF[0]  # 2001
        assert result.version == "pydevccu 2.1"


class TestBackendDetectionResult:
    """Tests for BackendDetectionResult dataclass."""

    def test_result_is_frozen(self) -> None:
        """Test that result is immutable."""
        result = BackendDetectionResult(
            backend=Backend.CCU,
            available_interfaces=(Interface.HMIP_RF,),
            detected_port=2010,
            tls=False,
            host="192.168.1.100",
        )

        with pytest.raises(AttributeError):
            result.backend = Backend.HOMEGEAR  # type: ignore[misc]

    def test_result_with_optional_fields(self) -> None:
        """Test result with all optional fields."""
        result = BackendDetectionResult(
            backend=Backend.CCU,
            available_interfaces=(Interface.HMIP_RF, Interface.BIDCOS_RF),
            detected_port=42010,
            tls=True,
            host="192.168.1.100",
            version="3.61.345",
            auth_enabled=True,
        )

        assert result.backend == Backend.CCU
        assert result.available_interfaces == (Interface.HMIP_RF, Interface.BIDCOS_RF)
        assert result.detected_port == 42010
        assert result.tls is True
        assert result.host == "192.168.1.100"
        assert result.version == "3.61.345"
        assert result.auth_enabled is True


class TestDetectionConfig:
    """Tests for DetectionConfig dataclass."""

    def test_config_defaults(self) -> None:
        """Test configuration defaults."""
        from aiohomematic.const import DEFAULT_TIMEOUT_CONFIG

        config = DetectionConfig(host="192.168.1.100")

        assert config.host == "192.168.1.100"
        assert config.username == ""
        assert config.password == ""
        assert config.request_timeout == DEFAULT_TIMEOUT_CONFIG.backend_detection_request
        assert config.total_timeout == DEFAULT_TIMEOUT_CONFIG.backend_detection_total
        assert config.verify_tls is False

    def test_config_with_all_fields(self) -> None:
        """Test configuration with all fields."""
        config = DetectionConfig(
            host="192.168.1.100",
            username="admin",
            password="secret",
            request_timeout=10.0,
            total_timeout=30.0,
            verify_tls=True,
        )

        assert config.host == "192.168.1.100"
        assert config.username == "admin"
        assert config.password == "secret"
        assert config.request_timeout == 10.0
        assert config.total_timeout == 30.0
        assert config.verify_tls is True


class TestDetectBackendTimeout:
    """Tests for detect_backend total timeout behavior."""

    @pytest.mark.asyncio
    async def test_detect_backend_aborts_on_host_unreachable(self) -> None:
        """Test that detection aborts early when host is unreachable (not just port closed)."""
        config = DetectionConfig(host="192.168.1.100")

        probe_count = 0

        async def mock_probe_unreachable(**kwargs: Any) -> object:
            nonlocal probe_count
            probe_count += 1
            # First probe returns ABORT signal (host unreachable)
            return _ABORT_DETECTION

        with patch(
            "aiohomematic.backend_detection._probe_xml_rpc_port",
            side_effect=mock_probe_unreachable,
        ):
            result = await detect_backend(config=config)

        # Should return None (no backend found)
        assert result is None

        # Should have attempted only 1 probe, then aborted
        # (not all 6 ports, because host is unreachable)
        assert probe_count == 1, f"Expected 1 probe attempt before abort, got {probe_count}"

    @pytest.mark.asyncio
    async def test_detect_backend_completes_before_timeout(self) -> None:
        """Test that detection completes successfully before timeout."""
        config = DetectionConfig(
            host="192.168.1.100",
            total_timeout=10.0,
        )

        with patch(
            "aiohomematic.backend_detection._probe_xml_rpc_port",
            new_callable=AsyncMock,
            return_value="pydevccu 2.1",
        ):
            result = await detect_backend(config=config)

        # Should complete successfully
        assert result is not None
        assert result.backend == Backend.PYDEVCCU

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_detect_backend_socket_timeout_on_unreachable_host(self) -> None:
        """Test that socket timeout prevents hanging on unreachable hosts."""
        import time

        # Use a non-routable IP address (RFC 5737 TEST-NET-1)
        # This will cause TCP connect to timeout
        config = DetectionConfig(
            host="192.0.2.1",  # Non-routable test address
            request_timeout=2.0,  # Short socket timeout
            total_timeout=10.0,
        )

        start_time = time.monotonic()
        result = await detect_backend(config=config)
        elapsed_time = time.monotonic() - start_time

        # Should return None (no backend found)
        assert result is None

        # Should complete within reasonable time (socket timeout + some overhead)
        # With socket timeout of 2s and 6 ports to try, should be < 15s
        # (much faster than OS default TCP timeout of 60-120s)
        assert elapsed_time < 15.0, f"Detection took {elapsed_time:.1f}s, expected < 15s"

    @pytest.mark.asyncio
    async def test_detect_backend_timeout_config_overrides_detection_config(self) -> None:
        """Test that timeout_config parameter overrides DetectionConfig timeouts."""
        # Create config with explicit timeouts
        config = DetectionConfig(
            host="192.168.1.100",
            request_timeout=5.0,
            total_timeout=15.0,
        )

        # Create custom timeout config that should override
        custom_timeout_config = TimeoutConfig(
            backend_detection_request=20.0,
            backend_detection_total=60.0,
        )

        with patch(
            "aiohomematic.backend_detection._probe_xml_rpc_port",
            new_callable=AsyncMock,
            return_value="pydevccu 2.1",
        ) as mock_probe:
            result = await detect_backend(config=config, timeout_config=custom_timeout_config)

        assert result is not None
        # Verify custom timeout was used
        call_kwargs = mock_probe.call_args.kwargs
        assert call_kwargs["request_timeout"] == 20.0

    @pytest.mark.asyncio
    async def test_detect_backend_total_timeout(self) -> None:
        """Test that detection aborts after total_timeout is exceeded."""
        config = DetectionConfig(
            host="192.168.1.100",
            total_timeout=0.1,  # Very short timeout
        )

        async def slow_probe(**kwargs: Any) -> str | None:
            await asyncio.sleep(1)  # Longer than total_timeout
            return "3.61.345"

        with patch(
            "aiohomematic.backend_detection._probe_xml_rpc_port",
            side_effect=slow_probe,
        ):
            result = await detect_backend(config=config)

        # Should return None due to timeout, not raise an exception
        assert result is None

    @pytest.mark.asyncio
    async def test_detect_backend_total_timeout_cancels_multiple_probes(self) -> None:
        """Test that total_timeout cancels detection even when multiple ports remain."""
        config = DetectionConfig(
            host="192.168.1.100",
            total_timeout=0.3,  # Very short timeout
        )

        probe_count = 0

        async def slow_probe(**kwargs: Any) -> str | None:
            nonlocal probe_count
            probe_count += 1
            # Each probe takes longer than total_timeout
            await asyncio.sleep(0.5)
            return "3.61.345"

        with patch(
            "aiohomematic.backend_detection._probe_xml_rpc_port",
            side_effect=slow_probe,
        ):
            result = await detect_backend(config=config)

        # Should return None due to timeout
        assert result is None

        # Should have attempted only 1 probe before timeout (not all 6 ports)
        # The first probe takes 0.5s, but total_timeout is 0.3s
        assert probe_count == 1, f"Expected 1 probe attempt, got {probe_count}"

    @pytest.mark.asyncio
    async def test_detect_backend_tries_all_ports_on_connection_refused(self) -> None:
        """Test that detection tries all ports when getting connection refused (port closed)."""
        config = DetectionConfig(host="192.168.1.100")

        probe_count = 0

        async def mock_probe_refused(**kwargs: Any) -> str | None:
            nonlocal probe_count
            probe_count += 1
            # All probes return None (connection refused - port closed but host reachable)
            return None

        with patch(
            "aiohomematic.backend_detection._probe_xml_rpc_port",
            side_effect=mock_probe_refused,
        ):
            result = await detect_backend(config=config)

        # Should return None (no backend found)
        assert result is None

        # Should have attempted all 6 ports (3 non-TLS + 3 TLS)
        assert probe_count == 6, f"Expected 6 probe attempts (all ports), got {probe_count}"

    @pytest.mark.asyncio
    async def test_detect_backend_with_custom_timeout_config(self) -> None:
        """Test detection with custom TimeoutConfig overriding DetectionConfig."""
        # Create config with default timeouts
        config = DetectionConfig(host="192.168.1.100")

        # Create custom timeout config with different values
        custom_timeout_config = TimeoutConfig(
            backend_detection_request=10.0,
            backend_detection_total=30.0,
        )

        with (
            patch(
                "aiohomematic.backend_detection._probe_xml_rpc_port",
                new_callable=AsyncMock,
                return_value="3.61.345",
            ) as mock_probe,
            patch(
                "aiohomematic.backend_detection._query_ccu_interfaces",
                new_callable=AsyncMock,
                return_value=((Interface.HMIP_RF,), True, None),
            ),
        ):
            result = await detect_backend(config=config, timeout_config=custom_timeout_config)

        # Should use timeouts from custom_timeout_config
        assert result is not None
        assert result.backend == Backend.CCU

        # Verify that _probe_xml_rpc_port was called with custom request_timeout
        assert mock_probe.called
        call_kwargs = mock_probe.call_args.kwargs
        assert call_kwargs["request_timeout"] == 10.0
