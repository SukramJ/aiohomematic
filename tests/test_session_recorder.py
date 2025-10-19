"""Test the session recorder."""

from __future__ import annotations

import pytest

from aiohomematic.const import RPCType


@pytest.mark.enable_socket
@pytest.mark.asyncio
async def test_session_recorder(session_recorder_from_full_session) -> None:
    """Test the session recorder."""
    assert session_recorder_from_full_session
    assert session_recorder_from_full_session.get_latest_response_by_params(
        rpc_type=RPCType.JSON_RPC, method="system.listMethods", params=[]
    )
