"""Integration tests for the JSON-RPC client using the local mock server."""

from __future__ import annotations

from aiohttp import ClientSession
import pytest

from aiohomematic import central as hmcu
from aiohomematic.client.json_rpc import JsonRpcAioHttpClient


@pytest.mark.asyncio
async def test_json_rpc_get_system_information(mock_json_rpc_server, aiohttp_session: ClientSession) -> None:
    """Ensure get_system_information returns expected values from the mock JSON-RPC server."""
    (_, base_url) = mock_json_rpc_server
    conn_state = hmcu.CentralConnectionState()

    client = JsonRpcAioHttpClient(
        username="user",
        password="pass",
        device_url=base_url,
        connection_state=conn_state,
        client_session=aiohttp_session,
        tls=False,
    )

    sysinfo = await client.get_system_information()
    # From mock: auth_enabled True, https redirect False, some interfaces
    assert sysinfo.auth_enabled is True
    assert sysinfo.https_redirect_enabled is False
    assert isinstance(sysinfo.available_interfaces, tuple)
    assert set(sysinfo.available_interfaces) == {"BidCos-RF", "HmIP-RF"}

    await client.stop()
