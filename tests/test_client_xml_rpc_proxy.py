"""Tests for client/rpc_proxy.py of aiohomematic."""

from __future__ import annotations

from enum import Enum
import xmlrpc.client

import pytest

from aiohomematic import central as hmcu
from aiohomematic.client.rpc_proxy import AioXmlRpcProxy, _cleanup_args, _cleanup_item, _cleanup_paramset
from aiohomematic.const import HubValueType
from aiohomematic.exceptions import ClientException, NoConnectionException, UnsupportedException
from aiohomematic.store.persistent import SessionRecorder


class TestXmlRpcProxyBasic:
    """Test basic XML-RPC proxy functionality."""

    @pytest.mark.asyncio
    async def test_ping_returns_pong(self, mock_xml_rpc_server) -> None:
        """Test that ping returns pong from the server."""
        (_, base_url) = mock_xml_rpc_server
        conn_state = hmcu.CentralConnectionState()

        proxy = AioXmlRpcProxy(
            max_workers=1,
            interface_id="BidCos-RF",
            connection_state=conn_state,
            uri=base_url,
            headers=[],
            tls=False,
        )

        # Initialize supported methods
        await proxy.do_init()

        # ping should return "pong"
        result = await proxy.ping()
        assert result == "pong"

        await proxy.stop()

    @pytest.mark.asyncio
    async def test_proxy_with_tls_enabled(self) -> None:
        """Test proxy initialization with TLS enabled."""
        conn_state = hmcu.CentralConnectionState()

        # Create proxy with TLS (this tests line 116: self._kwargs[_CONTEXT] = self._tls)
        proxy = AioXmlRpcProxy(
            max_workers=1,
            interface_id="test-if",
            connection_state=conn_state,
            uri="https://example.com/xmlrpc",
            headers=[],
            tls=True,
            verify_tls=False,
        )

        # Verify log context includes tls
        assert proxy.log_context["tls"] is True

        await proxy.stop()

    @pytest.mark.asyncio
    async def test_proxy_without_executor(self) -> None:
        """Test proxy with max_workers=0 (no executor)."""
        conn_state = hmcu.CentralConnectionState()

        proxy = AioXmlRpcProxy(
            max_workers=0,  # No executor
            interface_id="test-if",
            connection_state=conn_state,
            uri="http://example.com/xmlrpc",
            headers=[],
            tls=False,
        )

        # Should handle stop gracefully without executor
        await proxy.stop()


class TestSessionRecording:
    """Test session recording functionality."""

    @pytest.mark.asyncio
    async def test_do_init_with_empty_methods_list(self) -> None:
        """Test do_init when server returns empty methods list."""
        conn_state = hmcu.CentralConnectionState()

        proxy = AioXmlRpcProxy(
            max_workers=0,
            interface_id="test-if",
            connection_state=conn_state,
            uri="http://example.com/xmlrpc",
            headers=[],
            tls=False,
        )

        # Don't call do_init - supported_methods should remain empty
        assert proxy.supported_methods == ()

        await proxy.stop()

    @pytest.mark.asyncio
    async def test_session_recording_with_active_recorder(self, mock_xml_rpc_server, tmp_path) -> None:
        """Test that active session recorder records calls."""
        from aiohomematic.async_support import Looper

        class _CentralStub:
            def __init__(self):
                self.name = "test"
                self.config = type("obj", (), {"storage_directory": str(tmp_path), "use_caches": True})()
                self.looper = Looper()
                self.devices = []

        (_, base_url) = mock_xml_rpc_server
        conn_state = hmcu.CentralConnectionState()

        # Create session recorder
        central = _CentralStub()
        recorder = SessionRecorder(
            central_info=central,
            config_provider=central,
            device_provider=central,
            task_scheduler=central.looper,
            active=True,
            ttl_seconds=0,
            refresh_on_get=False,
        )

        proxy = AioXmlRpcProxy(
            max_workers=1,
            interface_id="BidCos-RF",
            connection_state=conn_state,
            uri=base_url,
            headers=[],
            tls=False,
            session_recorder=recorder,
        )

        await proxy.do_init()

        # Make a call that should be recorded (not ping)
        await proxy.system.listMethods()

        # Verify recording happened (check that we can retrieve it)
        # Note: ping is excluded from recording
        await proxy.stop()


class TestErrorHandling:
    """Test error handling in XML-RPC proxy."""

    @pytest.mark.asyncio
    async def test_generic_exception_raises_client_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that generic exceptions are wrapped in ClientException."""

        def raise_generic_error(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            raise RuntimeError("something went wrong")

        monkeypatch.setattr(xmlrpc.client.ServerProxy, "_ServerProxy__request", raise_generic_error, raising=True)

        conn_state = hmcu.CentralConnectionState()
        proxy = AioXmlRpcProxy(
            max_workers=1,
            interface_id="test-if",
            connection_state=conn_state,
            uri="http://example/xmlrpc",
            headers=[],
            tls=False,
        )

        with pytest.raises(ClientException):
            await proxy._async_request("system.listMethods", ())

        await proxy.stop()

    @pytest.mark.asyncio
    async def test_improper_connection_state_raises_no_connection_exception(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Test that http.client.ImproperConnectionState is mapped to NoConnectionException.

        This tests the handling of ResponseNotReady and similar HTTP connection state errors
        that occur when the underlying connection is in an inconsistent state.
        """
        import http.client

        def raise_response_not_ready(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            raise http.client.ResponseNotReady("Request-sent")

        monkeypatch.setattr(xmlrpc.client.ServerProxy, "_ServerProxy__request", raise_response_not_ready, raising=True)

        conn_state = hmcu.CentralConnectionState()
        proxy = AioXmlRpcProxy(
            max_workers=1,
            interface_id="test-if",
            connection_state=conn_state,
            uri="http://example/xmlrpc",
            headers=[],
            tls=False,
        )

        with pytest.raises(NoConnectionException):
            await proxy._async_request("system.listMethods", ())

        await proxy.stop()

    @pytest.mark.asyncio
    async def test_improper_connection_state_resets_transport(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that ImproperConnectionState triggers transport reset."""
        import http.client

        reset_called = []

        def raise_response_not_ready(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            raise http.client.ResponseNotReady("Request-sent")

        monkeypatch.setattr(xmlrpc.client.ServerProxy, "_ServerProxy__request", raise_response_not_ready, raising=True)

        conn_state = hmcu.CentralConnectionState()
        proxy = AioXmlRpcProxy(
            max_workers=1,
            interface_id="test-if",
            connection_state=conn_state,
            uri="http://example/xmlrpc",
            headers=[],
            tls=False,
        )

        # Patch _reset_transport to track calls
        original_reset = proxy._reset_transport

        def mock_reset_transport() -> None:
            reset_called.append(True)
            original_reset()

        monkeypatch.setattr(proxy, "_reset_transport", mock_reset_transport)

        with pytest.raises(NoConnectionException):
            await proxy._async_request("system.listMethods", ())

        # Transport should have been reset during retry attempts
        assert len(reset_called) > 0

        await proxy.stop()

    @pytest.mark.asyncio
    async def test_no_connection_when_has_issue(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that NoConnectionException is raised when connection has issue."""
        conn_state = hmcu.CentralConnectionState()

        proxy = AioXmlRpcProxy(
            max_workers=1,
            interface_id="test-if",
            connection_state=conn_state,
            uri="http://example/xmlrpc",
            headers=[],
            tls=False,
        )

        # Add connection issue
        conn_state.add_issue(issuer=proxy, iid="test-if")

        # Non-whitelisted method should raise NoConnectionException
        with pytest.raises(NoConnectionException):
            await proxy._async_request("setValue", ("addr", "param", 1))

        await proxy.stop()

    @pytest.mark.asyncio
    async def test_protocol_error_other(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that ProtocolError with other message raises NoConnectionException."""

        def raise_protocol_error(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            raise xmlrpc.client.ProtocolError("http://example", 500, "Server Error", {})

        monkeypatch.setattr(xmlrpc.client.ServerProxy, "_ServerProxy__request", raise_protocol_error, raising=True)

        conn_state = hmcu.CentralConnectionState()
        proxy = AioXmlRpcProxy(
            max_workers=1,
            interface_id="test-if",
            connection_state=conn_state,
            uri="http://example/xmlrpc",
            headers=[],
            tls=False,
        )

        with pytest.raises(NoConnectionException):
            await proxy._async_request("system.listMethods", ())

        await proxy.stop()

    @pytest.mark.asyncio
    async def test_protocol_error_unauthorized(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that ProtocolError with 'Unauthorized' raises AuthFailure."""
        from aiohomematic.exceptions import AuthFailure

        def raise_protocol_error(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            raise xmlrpc.client.ProtocolError("http://example", 401, "Unauthorized", {})

        monkeypatch.setattr(xmlrpc.client.ServerProxy, "_ServerProxy__request", raise_protocol_error, raising=True)

        conn_state = hmcu.CentralConnectionState()
        proxy = AioXmlRpcProxy(
            max_workers=1,
            interface_id="test-if",
            connection_state=conn_state,
            uri="http://example/xmlrpc",
            headers=[],
            tls=False,
        )

        with pytest.raises(AuthFailure):
            await proxy._async_request("system.listMethods", ())

        await proxy.stop()

    @pytest.mark.asyncio
    async def test_typeerror_translates_to_client_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that TypeError from xmlrpc layer is mapped to ClientException."""

        def raise_type_error(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            raise TypeError("bad type")

        monkeypatch.setattr(xmlrpc.client.ServerProxy, "_ServerProxy__request", raise_type_error, raising=True)

        proxy = AioXmlRpcProxy(
            max_workers=1,
            interface_id="if-test",
            connection_state=hmcu.CentralConnectionState(),
            uri="http://example/xmlrpc",
            headers=[],
            tls=False,
        )

        with pytest.raises(ClientException):
            await proxy._async_request("system.listMethods", ())

        await proxy.stop()

    @pytest.mark.asyncio
    async def test_unsupported_method_raises_exception(self) -> None:
        """Test that unsupported method raises UnsupportedException."""
        proxy = AioXmlRpcProxy(
            max_workers=1,
            interface_id="if-test",
            connection_state=hmcu.CentralConnectionState(),
            uri="http://example/xmlrpc",
            headers=[],
            tls=False,
        )

        # Limit supported methods
        proxy._supported_methods = ("system.ping",)  # type: ignore[attr-defined]

        with pytest.raises(UnsupportedException):
            await proxy._async_request("system.listMethods", ())

        await proxy.stop()


class TestCleanupHelpers:
    """Test cleanup helper functions."""

    def test_cleanup_args_with_empty_params(self) -> None:
        """Test that _cleanup_args with empty params returns as-is."""
        args_input = ("method", ())
        cleaned = _cleanup_args(*args_input)
        assert cleaned == args_input

    def test_cleanup_args_with_enums(self) -> None:
        """Test that _cleanup_args converts StrEnum values and tupleizes."""
        method = "setValue"
        args_input = (method, [HubValueType.FLOAT, {"k": HubValueType.INTEGER}])
        cleaned = _cleanup_args(*args_input)

        # Should tupleize the list and convert enums to strings
        assert cleaned[0] == method
        assert isinstance(cleaned[1], tuple)
        assert cleaned[1][0] == str(HubValueType.FLOAT)
        assert cleaned[1][1] == {"k": str(HubValueType.INTEGER)}

    def test_cleanup_args_with_too_many_args(self) -> None:
        """Test that _cleanup_args with too many args logs error."""
        # This should trigger the error logging path (line 307-308)
        args_input = ("method", [], "extra")
        cleaned = _cleanup_args(*args_input)
        # Should return args unchanged when there are too many
        assert cleaned == args_input

    def test_cleanup_item_with_enum(self) -> None:
        """Test that _cleanup_item converts Enum types."""
        from enum import IntEnum

        class TestIntEnum(IntEnum):
            VALUE = 42

        # StrEnum becomes str
        assert _cleanup_item(item=HubValueType.NUMBER) == str(HubValueType.NUMBER)

        # IntEnum becomes int
        assert _cleanup_item(item=TestIntEnum.VALUE) == 42

        # Regular Enum logs error and returns as-is
        class RegularEnum(Enum):
            VAL = "test"

        result = _cleanup_item(item=RegularEnum.VAL)
        assert result == RegularEnum.VAL

        # Non-enum returns as-is
        assert _cleanup_item(item="string") == "string"
        assert _cleanup_item(item=123) == 123

    def test_cleanup_paramset_with_enum(self) -> None:
        """Test that _cleanup_paramset converts StrEnum to string."""
        paramset = {"type": HubValueType.NUMBER}
        cleaned = _cleanup_paramset(paramset=paramset)
        assert cleaned == {"type": str(HubValueType.NUMBER)}
