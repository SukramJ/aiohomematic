# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract tests specifically for CUxD/CCU-Jack special handling.

CRITICAL - REGRESSION PREVENTION
--------------------------------
These tests exist to prevent regressions that have occurred during AI-assisted
refactoring. CUxD and CCU-Jack are special interfaces that:

1. Use JSON-RPC instead of XML-RPC
2. Use HTTP ports (80/443) instead of XML-RPC ports (2001-2011)
3. Have NO ping/pong support
4. Have NO XML-RPC callback server
5. Use polling by default (MQTT via Home Assistant is optional)

BEFORE ANY REFACTORING, ensure these tests pass:

    pytest tests/contract/test_cuxd_ccu_jack_contract.py -v

If any test fails after your changes, you have likely broken CUxD/CCU-Jack
functionality. Review the test docstring to understand what behavior must
be preserved.

See Also
--------
- tests/contract/test_capability_contract.py (broader capability tests)
- CLAUDE.md section "CRITICAL: CUxD/CCU-Jack Special Handling"

"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from aiohomematic.client.backends.capabilities import JSON_CCU_CAPABILITIES
from aiohomematic.client.backends.factory import create_backend
from aiohomematic.client.backends.json_ccu import JsonCcuBackend
from aiohomematic.const import (
    INTERFACES_REQUIRING_JSON_RPC_CLIENT,
    INTERFACES_REQUIRING_XML_RPC,
    INTERFACES_SUPPORTING_RPC_CALLBACK,
    Interface,
    get_json_rpc_default_port,
)

# =============================================================================
# SECTION 1: Interface Classification Contract
# =============================================================================


class TestCuxdCcuJackInterfaceClassification:
    """
    Contract: CUxD and CCU-Jack MUST be classified correctly in interface constants.

    REGRESSION THIS PREVENTS:
    - CUxD/CCU-Jack being accidentally added to XML-RPC interfaces
    - CUxD/CCU-Jack being removed from JSON-RPC interfaces
    - Either would cause connection failures or wrong backend selection
    """

    def test_ccu_jack_does_not_support_rpc_callback(self) -> None:
        """
        CONTRACT: CCU-Jack does not support XML-RPC callbacks.

        CCU-Jack uses polling by default. MQTT via Home Assistant is optional.
        There is no XML-RPC callback server.

        REGRESSION: If CCU-Jack is in INTERFACES_SUPPORTING_RPC_CALLBACK, aiohomematic
        will try to initialize a callback that doesn't exist.
        """
        assert Interface.CCU_JACK not in INTERFACES_SUPPORTING_RPC_CALLBACK, (
            "CCU-Jack MUST NOT be in INTERFACES_SUPPORTING_RPC_CALLBACK"
        )

    def test_ccu_jack_requires_json_rpc_not_xml_rpc(self) -> None:
        """
        CONTRACT: CCU-Jack uses JSON-RPC exclusively, not XML-RPC.

        CCU-Jack is a lightweight JSON-RPC server for Homematic.
        It does NOT support XML-RPC callbacks.

        REGRESSION: If CCU-Jack is in INTERFACES_REQUIRING_XML_RPC, aiohomematic
        will try to create XML-RPC proxies that don't exist, causing failures.
        """
        assert Interface.CCU_JACK in INTERFACES_REQUIRING_JSON_RPC_CLIENT, (
            "CCU-Jack MUST be in INTERFACES_REQUIRING_JSON_RPC_CLIENT"
        )
        assert Interface.CCU_JACK not in INTERFACES_REQUIRING_XML_RPC, (
            "CCU-Jack MUST NOT be in INTERFACES_REQUIRING_XML_RPC"
        )

    def test_cuxd_does_not_support_rpc_callback(self) -> None:
        """
        CONTRACT: CUxD does not support XML-RPC callbacks.

        CUxD uses polling by default. MQTT via Home Assistant is optional.
        There is no XML-RPC callback server.

        REGRESSION: If CUxD is in INTERFACES_SUPPORTING_RPC_CALLBACK, aiohomematic
        will try to initialize a callback that doesn't exist.
        """
        assert Interface.CUXD not in INTERFACES_SUPPORTING_RPC_CALLBACK, (
            "CUxD MUST NOT be in INTERFACES_SUPPORTING_RPC_CALLBACK"
        )

    def test_cuxd_requires_json_rpc_not_xml_rpc(self) -> None:
        """
        CONTRACT: CUxD uses JSON-RPC exclusively, not XML-RPC.

        CUxD communicates via HTTP/HTTPS on port 80/443 using JSON-RPC protocol.
        It does NOT use XML-RPC (BinRPC) on ports 2001-2011.

        REGRESSION: If CUxD is in INTERFACES_REQUIRING_XML_RPC, aiohomematic
        will try to create XML-RPC proxies that don't exist, causing failures.
        """
        assert Interface.CUXD in INTERFACES_REQUIRING_JSON_RPC_CLIENT, (
            "CUxD MUST be in INTERFACES_REQUIRING_JSON_RPC_CLIENT"
        )
        assert Interface.CUXD not in INTERFACES_REQUIRING_XML_RPC, "CUxD MUST NOT be in INTERFACES_REQUIRING_XML_RPC"

    def test_json_rpc_only_interfaces_are_exactly_cuxd_and_ccu_jack(self) -> None:
        """
        CONTRACT: The set of JSON-RPC-only interfaces is exactly {CUxD, CCU-Jack}.

        This set is computed as: INTERFACES_REQUIRING_JSON_RPC_CLIENT - INTERFACES_REQUIRING_XML_RPC

        REGRESSION: Adding other interfaces to this set or removing CUxD/CCU-Jack
        would change connection behavior for those interfaces.
        """
        json_rpc_only = INTERFACES_REQUIRING_JSON_RPC_CLIENT - INTERFACES_REQUIRING_XML_RPC

        assert json_rpc_only == {Interface.CUXD, Interface.CCU_JACK}, (
            f"JSON-RPC-only interfaces MUST be exactly {{CUxD, CCU-Jack}}, got: {json_rpc_only}"
        )


# =============================================================================
# SECTION 2: Backend Factory Contract
# =============================================================================


class TestCuxdCcuJackBackendFactory:
    """
    Contract: Factory MUST create JsonCcuBackend for CUxD/CCU-Jack.

    REGRESSION THIS PREVENTS:
    - Wrong backend type being created for CUxD/CCU-Jack
    - XML-RPC proxies being required for JSON-RPC-only interfaces
    """

    @pytest.fixture
    def mock_json_rpc(self) -> MagicMock:
        """Create a mock JSON-RPC client."""
        mock = MagicMock()
        mock.is_present = AsyncMock(return_value=True)
        mock.list_devices = AsyncMock(return_value=[])
        mock.circuit_breaker = MagicMock()
        mock.circuit_breaker.state = MagicMock()
        return mock

    @pytest.fixture
    def mock_paramset_provider(self) -> MagicMock:
        """Create a mock paramset provider."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_factory_accepts_none_proxies_for_cuxd(
        self,
        mock_json_rpc: MagicMock,
        mock_paramset_provider: MagicMock,
    ) -> None:
        """
        CONTRACT: create_backend() MUST accept proxy=None for CUxD.

        CUxD does not use XML-RPC, so no proxy should be required.

        REGRESSION: If factory requires proxy for CUxD, it's checking for
        XML-RPC support incorrectly.
        """
        # This should NOT raise ValueError
        backend = await create_backend(
            interface=Interface.CUXD,
            interface_id="test-CUxD",
            version="CUxD",
            proxy=None,
            proxy_read=None,
            json_rpc=mock_json_rpc,
            paramset_provider=mock_paramset_provider,
            device_details_provider={},
            has_push_updates=True,
        )

        assert backend is not None

    @pytest.mark.asyncio
    async def test_factory_creates_json_ccu_backend_for_ccu_jack(
        self,
        mock_json_rpc: MagicMock,
        mock_paramset_provider: MagicMock,
    ) -> None:
        """
        CONTRACT: create_backend() MUST return JsonCcuBackend for Interface.CCU_JACK.

        REGRESSION: If factory returns CcuBackend or HomegearBackend for CCU-Jack,
        it will fail because those backends require XML-RPC proxies.
        """
        backend = await create_backend(
            interface=Interface.CCU_JACK,
            interface_id="test-CCU-Jack",
            version="CCU-Jack",
            proxy=None,  # CCU-Jack does NOT have XML-RPC proxy
            proxy_read=None,  # CCU-Jack does NOT have XML-RPC proxy
            json_rpc=mock_json_rpc,
            paramset_provider=mock_paramset_provider,
            device_details_provider={},
            has_push_updates=True,
        )

        assert isinstance(backend, JsonCcuBackend), (
            f"Factory MUST create JsonCcuBackend for CCU-Jack, got: {type(backend).__name__}"
        )

    @pytest.mark.asyncio
    async def test_factory_creates_json_ccu_backend_for_cuxd(
        self,
        mock_json_rpc: MagicMock,
        mock_paramset_provider: MagicMock,
    ) -> None:
        """
        CONTRACT: create_backend() MUST return JsonCcuBackend for Interface.CUXD.

        REGRESSION: If factory returns CcuBackend or HomegearBackend for CUxD,
        it will fail because those backends require XML-RPC proxies.
        """
        backend = await create_backend(
            interface=Interface.CUXD,
            interface_id="test-CUxD",
            version="CUxD",
            proxy=None,  # CUxD does NOT have XML-RPC proxy
            proxy_read=None,  # CUxD does NOT have XML-RPC proxy
            json_rpc=mock_json_rpc,
            paramset_provider=mock_paramset_provider,
            device_details_provider={},
            has_push_updates=True,
        )

        assert isinstance(backend, JsonCcuBackend), (
            f"Factory MUST create JsonCcuBackend for CUxD, got: {type(backend).__name__}"
        )


# =============================================================================
# SECTION 3: Capabilities Contract
# =============================================================================


class TestCuxdCcuJackCapabilities:
    """
    Contract: JSON_CCU_CAPABILITIES MUST have correct values for CUxD/CCU-Jack.

    REGRESSION THIS PREVENTS:
    - Enabling ping/pong which would cause false disconnections
    - Enabling rpc_callback which would cause proxy init failures
    - Enabling features that CUxD/CCU-Jack don't support
    """

    def test_json_ccu_capabilities_no_ccu_specific_features(self) -> None:
        """
        CONTRACT: JSON_CCU_CAPABILITIES feature flags MUST all be False.

        CUxD/CCU-Jack don't support CCU-specific features like:
        - Programs
        - System variables (sysvars)
        - Firmware updates
        - Service messages
        - Install mode
        - Device linking
        - Backup/restore
        - Room/function assignment
        - Rename operations

        REGRESSION: If any feature flag is True, aiohomematic would try to
        call methods that don't exist on CUxD/CCU-Jack.
        """
        ccu_specific_features = [
            "backup",
            "device_firmware_update",
            "firmware_update_trigger",
            "firmware_updates",
            "functions",
            "inbox_devices",
            "install_mode",
            "linking",
            "metadata",
            "programs",
            "rega_id_lookup",
            "rename",
            "rooms",
            "service_messages",
            "system_update_info",
            "value_usage_reporting",
        ]

        for feature in ccu_specific_features:
            assert getattr(JSON_CCU_CAPABILITIES, feature) is False, f"JSON_CCU_CAPABILITIES.{feature} MUST be False"

    def test_json_ccu_capabilities_ping_pong_disabled(self) -> None:
        """
        CONTRACT: JSON_CCU_CAPABILITIES.ping_pong MUST be False.

        CUxD/CCU-Jack don't support XML-RPC ping/pong for connection health.
        They use polling by default (MQTT via HA is optional).

        REGRESSION: If ping_pong=True, is_callback_alive() would return False
        after 180 seconds without events, triggering unnecessary reconnects.
        """
        assert JSON_CCU_CAPABILITIES.ping_pong is False, (
            "JSON_CCU_CAPABILITIES.ping_pong MUST be False to prevent false disconnections"
        )

    def test_json_ccu_capabilities_push_updates_enabled(self) -> None:
        """
        CONTRACT: JSON_CCU_CAPABILITIES.push_updates MUST be True.

        CUxD/CCU-Jack can receive events via MQTT (when configured in Home Assistant).
        The push_updates flag controls whether the scheduler checks for events.

        REGRESSION: If push_updates=False, the scheduler would skip event checks.
        """
        assert JSON_CCU_CAPABILITIES.push_updates is True, "JSON_CCU_CAPABILITIES.push_updates MUST be True"

    def test_json_ccu_capabilities_rpc_callback_disabled(self) -> None:
        """
        CONTRACT: JSON_CCU_CAPABILITIES.rpc_callback MUST be False.

        CUxD/CCU-Jack don't have XML-RPC callback support.
        They don't call init() on any XML-RPC server.

        REGRESSION: If rpc_callback=True, initialize_proxy() would try to
        call backend.init_proxy() which doesn't make sense for JSON-RPC-only.
        """
        assert JSON_CCU_CAPABILITIES.rpc_callback is False, (
            "JSON_CCU_CAPABILITIES.rpc_callback MUST be False to skip XML-RPC init"
        )


# =============================================================================
# SECTION 4: Port Configuration Contract
# =============================================================================


class TestCuxdCcuJackPortConfiguration:
    """
    Contract: CUxD/CCU-Jack use HTTP/HTTPS ports, not XML-RPC ports.

    REGRESSION THIS PREVENTS:
    - Wrong ports being used for CUxD/CCU-Jack connections
    - Port 2001-2011 being used instead of 80/443
    """

    def test_json_rpc_default_port_http(self) -> None:
        """
        CONTRACT: JSON-RPC default port for HTTP MUST be 80.

        CUxD/CCU-Jack use standard HTTP port when TLS is disabled.

        REGRESSION: Using XML-RPC ports (2001-2011) would fail to connect.
        """
        assert get_json_rpc_default_port(tls=False) == 80

    def test_json_rpc_default_port_https(self) -> None:
        """
        CONTRACT: JSON-RPC default port for HTTPS MUST be 443.

        CUxD/CCU-Jack use standard HTTPS port when TLS is enabled.

        REGRESSION: Using XML-RPC ports (2001-2011) would fail to connect.
        """
        assert get_json_rpc_default_port(tls=True) == 443


# =============================================================================
# SECTION 5: Interface Enum Stability Contract
# =============================================================================


class TestCuxdCcuJackEnumStability:
    """
    Contract: Interface enum values for CUxD/CCU-Jack MUST be stable.

    REGRESSION THIS PREVENTS:
    - Enum value changes breaking configuration and logging
    - String comparisons failing after enum value changes
    """

    def test_ccu_jack_enum_value_is_stable(self) -> None:
        """
        CONTRACT: Interface.CCU_JACK.value MUST be 'CCU-Jack'.

        This string is used in logs, configuration, and comparisons.

        REGRESSION: Changing this value would break existing configurations
        and log filtering.
        """
        assert Interface.CCU_JACK.value == "CCU-Jack", (
            f"Interface.CCU_JACK.value MUST be 'CCU-Jack', got: {Interface.CCU_JACK.value!r}"
        )

    def test_cuxd_enum_value_is_stable(self) -> None:
        """
        CONTRACT: Interface.CUXD.value MUST be 'CUxD'.

        This string is used in logs, configuration, and comparisons.

        REGRESSION: Changing this value would break existing configurations
        and log filtering.
        """
        assert Interface.CUXD.value == "CUxD", f"Interface.CUXD.value MUST be 'CUxD', got: {Interface.CUXD.value!r}"


# =============================================================================
# SECTION 6: Backend Behavior Contract
# =============================================================================


class TestCuxdCcuJackBackendBehavior:
    """
    Contract: JsonCcuBackend MUST behave correctly for CUxD/CCU-Jack.

    REGRESSION THIS PREVENTS:
    - Backend trying to use ping/pong
    - Backend trying to init XML-RPC callback
    - Backend using wrong capabilities
    """

    @pytest.fixture
    def mock_json_rpc(self) -> MagicMock:
        """Create a mock JSON-RPC client."""
        mock = MagicMock()
        mock.is_present = AsyncMock(return_value=True)
        mock.circuit_breaker = MagicMock()
        mock.circuit_breaker.state = MagicMock()
        mock.circuit_breaker.reset = MagicMock()
        return mock

    @pytest.fixture
    def mock_paramset_provider(self) -> MagicMock:
        """Create a mock paramset provider."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_json_ccu_backend_check_connection_uses_is_present(
        self,
        mock_json_rpc: MagicMock,
        mock_paramset_provider: MagicMock,
    ) -> None:
        """
        CONTRACT: JsonCcuBackend.check_connection() MUST use JSON-RPC isPresent.

        Since there's no XML-RPC ping/pong, connection check uses isPresent.

        REGRESSION: If check_connection tries to use ping/pong, it would fail.
        """
        backend = JsonCcuBackend(
            interface=Interface.CUXD,
            interface_id="test-CUxD",
            json_rpc=mock_json_rpc,
            paramset_provider=mock_paramset_provider,
            has_push_updates=True,
        )

        await backend.check_connection(handle_ping_pong=True, caller_id=None)

        # Should call is_present, not ping
        mock_json_rpc.is_present.assert_called_once()

    @pytest.mark.asyncio
    async def test_json_ccu_backend_deinit_proxy_is_noop(
        self,
        mock_json_rpc: MagicMock,
        mock_paramset_provider: MagicMock,
    ) -> None:
        """
        CONTRACT: JsonCcuBackend.deinit_proxy() MUST be a no-op.

        JSON-RPC-only backends don't have XML-RPC proxy to de-initialize.

        REGRESSION: If deinit_proxy tries to do something, it would fail.
        """
        backend = JsonCcuBackend(
            interface=Interface.CUXD,
            interface_id="test-CUxD",
            json_rpc=mock_json_rpc,
            paramset_provider=mock_paramset_provider,
            has_push_updates=True,
        )

        # Should complete without error
        await backend.deinit_proxy(init_url="http://test")

    @pytest.mark.asyncio
    async def test_json_ccu_backend_init_proxy_is_noop(
        self,
        mock_json_rpc: MagicMock,
        mock_paramset_provider: MagicMock,
    ) -> None:
        """
        CONTRACT: JsonCcuBackend.init_proxy() MUST be a no-op.

        JSON-RPC-only backends don't have XML-RPC proxy to initialize.

        REGRESSION: If init_proxy tries to do something, it would fail.
        """
        backend = JsonCcuBackend(
            interface=Interface.CUXD,
            interface_id="test-CUxD",
            json_rpc=mock_json_rpc,
            paramset_provider=mock_paramset_provider,
            has_push_updates=True,
        )

        # Should complete without error and without calling anything
        await backend.init_proxy(init_url="http://test", interface_id="test-CUxD")

    def test_json_ccu_backend_uses_json_ccu_capabilities(
        self,
        mock_json_rpc: MagicMock,
        mock_paramset_provider: MagicMock,
    ) -> None:
        """
        CONTRACT: JsonCcuBackend MUST use JSON_CCU_CAPABILITIES (with push_updates override).

        REGRESSION: If backend uses wrong capabilities, connection health
        checks and feature gating would fail.
        """
        backend = JsonCcuBackend(
            interface=Interface.CUXD,
            interface_id="test-CUxD",
            json_rpc=mock_json_rpc,
            paramset_provider=mock_paramset_provider,
            has_push_updates=True,
        )

        # ping_pong and rpc_callback should match JSON_CCU_CAPABILITIES
        assert backend.capabilities.ping_pong is False
        assert backend.capabilities.rpc_callback is False
