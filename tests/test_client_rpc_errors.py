"""Tests for mapping of RPC errors to aiohomematic exceptions."""

from __future__ import annotations

from aiohomematic.client._rpc_errors import RpcContext, map_jsonrpc_error, map_transport_error, map_xmlrpc_fault
from aiohomematic.exceptions import AuthFailure, ClientException, InternalBackendException, NoConnectionException


class TestRpcContext:
    """Test RPC context formatting."""

    def test_rpc_context_fmt_variants(self) -> None:
        """RpcContext.fmt should include all provided fields in stable order."""
        ctx = RpcContext(protocol="jsonrpc", method="system.method")
        assert ctx.fmt() == "protocol=jsonrpc, method=system.method"

        ctx2 = RpcContext(protocol="xmlrpc", method="listDevices", host="127.0.0.1", interface="BidCos-RF")
        assert ctx2.fmt() == "protocol=xmlrpc, method=listDevices, interface=BidCos-RF, host=127.0.0.1"


class TestMapJsonRpcError:
    """Test JSON-RPC error mapping."""

    def test_map_jsonrpc_error_auth_variants(self) -> None:
        """map_jsonrpc_error should return AuthFailure for known auth cases."""
        ctx = RpcContext(protocol="jsonrpc", method="x")

        exc = map_jsonrpc_error(error={"code": 401, "message": "whatever"}, ctx=ctx)
        assert isinstance(exc, AuthFailure)
        assert "protocol=jsonrpc" in str(exc)

        exc2 = map_jsonrpc_error(error={"code": -32001, "message": "whatever"}, ctx=ctx)
        assert isinstance(exc2, AuthFailure)

        exc3 = map_jsonrpc_error(error={"code": 0, "message": "access denied for user"}, ctx=ctx)
        assert isinstance(exc3, AuthFailure)

    def test_map_jsonrpc_error_internal_and_default(self) -> None:
        """map_jsonrpc_error should map internal and default errors appropriately."""
        ctx = RpcContext(protocol="jsonrpc", method="y")
        exc = map_jsonrpc_error(error={"code": -32603, "message": "Internal error"}, ctx=ctx)
        assert isinstance(exc, InternalBackendException)

        exc2 = map_jsonrpc_error(error={"code": 500, "message": "something"}, ctx=ctx)
        assert isinstance(exc2, InternalBackendException)

        exc3 = map_jsonrpc_error(error={"code": 123, "message": "other"}, ctx=ctx)
        assert isinstance(exc3, ClientException)


class TestMapTransportError:
    """Test transport error mapping."""

    def test_map_transport_error(self) -> None:
        """map_transport_error should wrap OSError as NoConnectionException."""
        ctx = RpcContext(protocol="xmlrpc", method="foo")

        os_err = OSError("boom")
        exc = map_transport_error(exc=os_err, ctx=ctx)
        assert isinstance(exc, NoConnectionException)
        assert "boom" in str(exc)

        other = ValueError("x")
        exc2 = map_transport_error(exc=other, ctx=ctx)
        assert isinstance(exc2, ClientException)


class TestMapXmlRpcFault:
    """Test XML-RPC fault mapping."""

    def test_map_xmlrpc_fault_mappings(self) -> None:
        """map_xmlrpc_fault should map codes to specific exception types."""
        ctx = RpcContext(protocol="xmlrpc", method="login")

        exc = map_xmlrpc_fault(code=1, fault_string="Unauthorized", ctx=ctx)
        assert isinstance(exc, AuthFailure)

        exc2 = map_xmlrpc_fault(code=2, fault_string="Internal Server Error", ctx=ctx)
        assert isinstance(exc2, InternalBackendException)

        exc3 = map_xmlrpc_fault(code=3, fault_string="Other", ctx=ctx)
        assert isinstance(exc3, ClientException)
