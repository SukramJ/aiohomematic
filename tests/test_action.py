"""Tests for action entities of hahomematic."""
from __future__ import annotations

from typing import cast
from unittest.mock import call

import const
import helper
from helper import get_generic_entity
import pytest

from hahomematic.const import HmEntityUsage
from hahomematic.generic_platforms.action import HmAction

TEST_DEVICES: dict[str, str] = {
    "VCU9724704": "HmIP-DLD.json",
}


@pytest.mark.asyncio
async def test_hmaction(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test HmAction."""
    central, mock_client = await central_local_factory.get_default_central(TEST_DEVICES)
    action: HmAction = cast(
        HmAction,
        await get_generic_entity(central, "VCU9724704:1", "LOCK_TARGET_LEVEL"),
    )
    assert action.usage == HmEntityUsage.ENTITY_NO_CREATE
    assert action.is_readable is False
    assert action.value is None
    assert action.value_list == ("LOCKED", "UNLOCKED", "OPEN")
    assert action.hmtype == "ENUM"
    await action.send_value("OPEN")
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU9724704:1",
        paramset_key="VALUES",
        parameter="LOCK_TARGET_LEVEL",
        value=2,
    )
    await action.send_value(1)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU9724704:1",
        paramset_key="VALUES",
        parameter="LOCK_TARGET_LEVEL",
        value=1,
    )
