# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Additional tests to improve coverage of aiohomematic.central.

These tests focus on CentralConfig helper properties/methods and
CentralConnectionState issue tracking and logging paths.
"""

from __future__ import annotations

import logging

import pytest

from aiohomematic.central import CentralConfig, CentralConnectionState
from aiohomematic.client import BaseRpcProxy, InterfaceConfig
from aiohomematic.client.json_rpc import AioJsonRpcAioHttpClient
from aiohomematic.const import Interface


class _DummyJson(AioJsonRpcAioHttpClient):
    """Lightweight subclass used only for isinstance checks in tests."""

    def __init__(self) -> None:  # noqa: D401 (docstring inherited)
        # Intentionally do not call super().__init__ to avoid heavy setup.
        pass


class _DummyRpc(BaseRpcProxy):
    """Lightweight subclass used only for isinstance checks in tests."""

    def __init__(self, interface_id: str) -> None:  # noqa: D401 (docstring inherited)
        # Intentionally do not call super().__init__ to avoid heavy setup.
        self.interface_id = interface_id

    async def do_init(self) -> None:  # pragma: no cover - trivial stub
        """No-op init for abstract base compliance."""
        return

    async def _async_request(self, *args, **kwargs):  # type: ignore[no-untyped-def]  # pragma: no cover - trivial stub
        """No-op request for abstract base compliance."""
        return


class TestCentralConfigProperties:
    """Test CentralConfig property derivations."""

    @pytest.mark.asyncio
    async def test_central_config_connection_check_port_precedence(self) -> None:
        """connection_check_port uses interface port, else json_port, else scheme default."""
        # 1) With interface port present, it should be returned.
        ic1 = InterfaceConfig(central_name="c1", interface=Interface.BIDCOS_RF, port=2001)
        cfg1 = CentralConfig(
            central_id="c1",
            host="127.0.0.1",
            interface_configs=frozenset({ic1}),
            name="n",
            password="p",
            username="u",
        )
        assert cfg1.connection_check_port == 2001

        # 2) Without interface configs, but with json_port.
        cfg2 = CentralConfig(
            central_id="c2",
            host="127.0.0.1",
            interface_configs=frozenset(),
            name="n",
            password="p",
            username="u",
            json_port=32001,
        )
        assert cfg2.connection_check_port == 32001

        # 3) No interface port, no json_port: tls decides.
        cfg_http = CentralConfig(
            central_id="c3",
            host="127.0.0.1",
            interface_configs=frozenset(),
            name="n",
            password="p",
            username="u",
            tls=False,
        )
        assert cfg_http.connection_check_port == 80

        cfg_https = CentralConfig(
            central_id="c4",
            host="127.0.0.1",
            interface_configs=frozenset(),
            name="n",
            password="p",
            username="u",
            tls=True,
        )
        assert cfg_https.connection_check_port == 443

    @pytest.mark.asyncio
    async def test_central_config_enable_xml_rpc_server_true_false(self) -> None:
        """Enable XML-RPC server depends on requires_xml_rpc_server and start_direct."""
        ic = InterfaceConfig(central_name="c1", interface=Interface.BIDCOS_RF, port=2001)

        cfg = CentralConfig(
            central_id="c1",
            host="127.0.0.1",
            interface_configs=frozenset({ic}),
            name="n",
            password="p",
            username="u",
            start_direct=False,
        )
        assert cfg.enable_xml_rpc_server is True

        cfg_direct = CentralConfig(
            central_id="c1",
            host="127.0.0.1",
            interface_configs=frozenset({ic}),
            name="n",
            password="p",
            username="u",
            start_direct=True,
        )
        assert cfg_direct.enable_xml_rpc_server is False

    @pytest.mark.asyncio
    async def test_central_config_enabled_interface_configs_and_url(self) -> None:
        """Ensure disabled interfaces are filtered and URL is built correctly (with port)."""
        ic1 = InterfaceConfig(central_name="c1", interface=Interface.BIDCOS_RF, port=2001)
        ic2 = InterfaceConfig(central_name="c1", interface=Interface.HMIP_RF, port=2010)
        ic2.disable()

        cfg = CentralConfig(
            central_id="c1",
            host="example.local",
            interface_configs=frozenset({ic1, ic2}),
            name="n",
            password="p",
            username="u",
            json_port=8181,
            tls=True,
        )

        enabled = cfg.enabled_interface_configs
        assert ic1 in enabled and ic2 not in enabled
        assert cfg.create_central_url() == "https://example.local:8181"

    @pytest.mark.asyncio
    async def test_central_config_load_un_ignore_and_use_caches(self) -> None:
        """Both load_un_ignore and use_caches are false when start_direct is True."""
        ic = InterfaceConfig(central_name="c1", interface=Interface.BIDCOS_RF, port=2001)

        cfg_direct = CentralConfig(
            central_id="c1",
            host="127.0.0.1",
            interface_configs=frozenset({ic}),
            name="n",
            password="p",
            username="u",
            start_direct=True,
        )
        assert cfg_direct.load_un_ignore is False
        assert cfg_direct.use_caches is False

        cfg_normal = CentralConfig(
            central_id="c1",
            host="127.0.0.1",
            interface_configs=frozenset({ic}),
            name="n",
            password="p",
            username="u",
            start_direct=False,
        )
        assert cfg_normal.load_un_ignore is True
        assert cfg_normal.use_caches is True


class TestCentralConnectionState:
    """Test CentralConnectionState issue tracking and logging."""

    @pytest.mark.asyncio
    async def test_central_connection_state_issue_tracking_and_logging(self, caplog: pytest.LogCaptureFixture) -> None:
        """Cover add/remove/has_issue and handle_exception_log with multiple_logs toggled."""
        caplog.set_level(logging.DEBUG)
        ccs = CentralConnectionState()

        json_issuer = _DummyJson()
        rpc_issuer = _DummyRpc(interface_id="if-main")

        # Adding an issue should log a debug and return True the first time.
        assert ccs.add_issue(issuer=json_issuer, iid="J1") is True
        assert ccs.has_issue(issuer=json_issuer, iid="J1") is True

        assert ccs.add_issue(issuer=rpc_issuer, iid="if-main") is True
        assert ccs.has_issue(issuer=rpc_issuer, iid="if-main") is True

        # Adding the same again should return False (already present).
        assert ccs.add_issue(issuer=json_issuer, iid="J1") is False
        assert ccs.add_issue(issuer=rpc_issuer, iid="if-main") is False

        # handle_exception_log with multiple_logs=False should log at debug if already tracked
        class _NamedExc(Exception):
            """Custom exception carrying a name attribute to hit that code path."""

            def __init__(self, msg: str) -> None:
                super().__init__(msg)
                self.name = "TestError"

        # First call will add issue and log at ERROR (since not yet present for that iid)
        with caplog.at_level(logging.ERROR):
            ccs.handle_exception_log(
                issuer=json_issuer,
                iid="J2",
                exception=_NamedExc("boom"),
                extra_msg="x",
                multiple_logs=True,
            )
        assert any("J2 failed" in r.message for r in caplog.records)

        # Second call with same iid and multiple_logs=False logs at DEBUG instead of ERROR
        caplog.clear()
        with caplog.at_level(logging.DEBUG):
            ccs.handle_exception_log(
                issuer=json_issuer,
                iid="J2",
                exception=_NamedExc("boom"),
                extra_msg="y",
                multiple_logs=False,
            )
        assert any(r.levelno == logging.DEBUG and "J2 failed" in r.message for r in caplog.records)

        # Now remove issues
        assert ccs.remove_issue(issuer=json_issuer, iid="J1") is True
        assert ccs.remove_issue(issuer=rpc_issuer, iid="if-main") is True
        # Removing again should be False
        assert ccs.remove_issue(issuer=json_issuer, iid="J1") is False
        assert ccs.remove_issue(issuer=rpc_issuer, iid="if-main") is False
        # There should be no issues left
        assert ccs.has_issue(issuer=json_issuer, iid="J1") is False
        assert ccs.has_issue(issuer=rpc_issuer, iid="if-main") is False


class TestCentralUnitStr:
    """Test CentralUnit string representation."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            ({"VCU2128127", "VCU6354483"}, True, None, None),
        ],
    )
    async def test_central_unit_str(self, central_client_factory_with_homegear_client) -> None:
        """Smoke test for CentralUnit.__str__ to touch the method."""
        central, _, _ = central_client_factory_with_homegear_client
        s = str(central)
        assert central.name in s
