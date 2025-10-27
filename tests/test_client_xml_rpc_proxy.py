"""Integration test for the XML-RPC proxy using a threaded mock server."""

from __future__ import annotations

import pytest

from aiohomematic import central as hmcu
from aiohomematic.client.rpc_proxy import AioXmlRpcProxy, _cleanup_args, _cleanup_paramset
from aiohomematic.const import SysvarType


@pytest.mark.asyncio
async def test_xml_rpc_ping(mock_xml_rpc_server) -> None:
    """Ensure XmlRpcProxy.ping returns 'pong' using the mock server."""
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

    # Initialize supported methods by asking server
    await proxy.do_init()

    # ping should be supported and return "pong" from mock
    result = await proxy.ping()
    assert result == "pong"

    await proxy.stop()


@pytest.mark.asyncio
async def test_async_request_typeerror_translates_to_client_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure a TypeError from xmlrpc layer is mapped to ClientException."""

    # Monkeypatch the underlying ServerProxy request to raise TypeError deterministically
    import xmlrpc.client

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
        verify_tls=False,
        session_recorder=None,
    )

    with pytest.raises(Exception) as ei:
        await proxy._async_request("system.listMethods", ())
    # The wrapper should convert TypeError to ClientException
    from aiohomematic.exceptions import ClientException

    assert isinstance(ei.value, ClientException)


@pytest.mark.asyncio
async def test_async_request_unsupported_method(monkeypatch: pytest.MonkeyPatch) -> None:
    """When method is not in supported list, UnsupportedException is raised before calling transport."""
    proxy = AioXmlRpcProxy(
        max_workers=1,
        interface_id="if-test",
        connection_state=hmcu.CentralConnectionState(),
        uri="http://example/xmlrpc",
        headers=[],
        tls=False,
        verify_tls=False,
        session_recorder=None,
    )

    # Limit supported methods to a different one
    proxy._supported_methods = ("system.ping",)  # type: ignore[attr-defined]

    from aiohomematic.exceptions import UnsupportedException

    with pytest.raises(UnsupportedException):
        await proxy._async_request("system.listMethods", ())


def test_cleanup_helpers_convert_enums() -> None:
    """_cleanup_item and _cleanup_paramset should convert StrEnum/IntEnum to primitives; args wrapper should tupleize."""
    # Dict with a StrEnum value should become str
    paramset = {"type": SysvarType.NUMBER}
    cleaned = _cleanup_paramset(paramset=paramset)
    assert cleaned == {"type": str(SysvarType.NUMBER)}

    # Value list with StrEnum becomes str, and args tupleized
    method = "setValue"
    args = (method, [SysvarType.FLOAT, {"k": SysvarType.INTEGER}])
    new_args = _cleanup_args(*args)
    assert isinstance(new_args, tuple) and len(new_args) == 2
    assert new_args[0] == method
    assert isinstance(new_args[1], tuple)
    # Ensure nested enum was converted
    assert new_args[1][0] == str(SysvarType.FLOAT)
    assert new_args[1][1] == {"k": str(SysvarType.INTEGER)}
