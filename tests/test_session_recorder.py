"""Test the session recorder."""

from __future__ import annotations

import pytest

from aiohomematic.const import RPCType


@pytest.mark.enable_socket
@pytest.mark.asyncio
async def test_session_recorder(session_player_from_full_session_ccu) -> None:
    """Test the session recorder."""
    assert session_player_from_full_session_ccu
    lm_methods = session_player_from_full_session_ccu.get_latest_response_by_method(
        rpc_type=RPCType.XML_RPC, method="system.listMethods"
    )
    assert lm_methods
    assert len(lm_methods) == 1

    assert session_player_from_full_session_ccu
    pd_methods = session_player_from_full_session_ccu.get_latest_response_by_method(
        rpc_type=RPCType.XML_RPC, method="getParamsetDescription"
    )
    assert pd_methods
    assert len(pd_methods) == 3561

    list_methods = session_player_from_full_session_ccu.get_latest_response_by_params(
        rpc_type=RPCType.XML_RPC, method="system.listMethods", params=()
    )
    assert list_methods
    assert len(list_methods) == 62

    dd_mestods = session_player_from_full_session_ccu.get_latest_response_by_params(
        rpc_type=RPCType.JSON_RPC, method="Interface.listInterfaces", params="{'_session_id_': 'DzzhYRjWXr'}"
    )
    assert dd_mestods
    assert len(dd_mestods["result"]) == 3
