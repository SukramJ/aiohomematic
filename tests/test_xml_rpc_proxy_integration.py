"""Integration test for the XML-RPC proxy using a threaded mock server."""

from __future__ import annotations

import pytest

from aiohomematic import central as hmcu
from aiohomematic.client.xml_rpc import XmlRpcProxy


@pytest.mark.asyncio
async def test_xml_rpc_ping(mock_xml_rpc_server) -> None:
    """Ensure XmlRpcProxy.ping returns 'pong' using the mock server."""
    (_, base_url) = mock_xml_rpc_server
    conn_state = hmcu.CentralConnectionState()

    proxy = XmlRpcProxy(
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
