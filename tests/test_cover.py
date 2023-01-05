"""Tests for cover entities of hahomematic."""
from __future__ import annotations

from typing import cast
from unittest.mock import call

import const
import helper
from helper import get_hm_custom_entity
import pytest

from hahomematic.const import HmEntityUsage
from hahomematic.custom_platforms.cover import CeBlind, CeCover, CeGarage, CeIpBlind

TEST_DEVICES: dict[str, str] = {
    "VCU8537918": "HmIP-BROLL.json",
    "VCU1223813": "HmIP-FBL.json",
    "VCU0000045": "HM-LC-Bl1-FM.json",
    "VCU3574044": "HmIP-MOD-HO.json",
    "VCU0000145": "HM-LC-JaX.json",
}


@pytest.mark.asyncio
async def test_cecover(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test CeCover."""
    central, mock_client = await central_local_factory.get_central(TEST_DEVICES)
    assert central
    cover: CeCover = cast(CeCover, await get_hm_custom_entity(central, "VCU8537918", 4))
    assert cover.usage == HmEntityUsage.CE_PRIMARY

    assert cover.current_cover_position == 0
    await cover.set_cover_position(81)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU8537918:4",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=0.81,
    )
    assert cover.current_cover_position == 81
    await cover.open_cover()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU8537918:4",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=1.0,
    )
    assert cover.current_cover_position == 100
    await cover.close_cover()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU8537918:4",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=0.0,
    )
    assert cover.current_cover_position == 0


@pytest.mark.asyncio
async def test_ceblind(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test CeBlind."""
    central, mock_client = await central_local_factory.get_central(TEST_DEVICES)
    assert central
    cover: CeBlind = cast(CeBlind, await get_hm_custom_entity(central, "VCU0000145", 1))
    assert cover.usage == HmEntityUsage.CE_PRIMARY

    assert cover.current_cover_position == 0
    assert cover.current_cover_tilt_position == 0
    await cover.set_cover_position(81)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000145:1",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=0.81,
    )
    assert cover.current_cover_position == 81
    assert cover.current_cover_tilt_position == 0
    await cover.open_cover()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000145:1",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=1.0,
    )
    assert cover.current_cover_position == 100
    assert cover.current_cover_tilt_position == 0
    await cover.close_cover()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000145:1",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=0.0,
    )
    assert cover.current_cover_position == 0
    assert cover.current_cover_tilt_position == 0
    await cover.open_cover_tilt()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000145:1",
        paramset_key="VALUES",
        parameter="LEVEL_SLATS",
        value=1.0,
    )
    assert cover.current_cover_position == 0
    assert cover.current_cover_tilt_position == 100
    await cover.set_cover_tilt_position(45)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000145:1",
        paramset_key="VALUES",
        parameter="LEVEL_SLATS",
        value=0.45,
    )
    assert cover.current_cover_position == 0
    assert cover.current_cover_tilt_position == 45
    await cover.close_cover_tilt()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000145:1",
        paramset_key="VALUES",
        parameter="LEVEL_SLATS",
        value=0.0,
    )
    assert cover.current_cover_position == 0
    assert cover.current_cover_tilt_position == 0


@pytest.mark.asyncio
async def test_ceipblind(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test CeIpBlind."""
    central, mock_client = await central_local_factory.get_central(TEST_DEVICES)
    assert central
    cover: CeIpBlind = cast(
        CeIpBlind, await get_hm_custom_entity(central, "VCU1223813", 4)
    )
    assert cover.usage == HmEntityUsage.CE_PRIMARY

    assert cover.current_cover_position == 0
    assert cover.current_cover_tilt_position == 0
    await cover.set_cover_position(81)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1223813:4",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=0.81,
    )
    assert cover.current_cover_position == 81
    assert cover.current_cover_tilt_position == 0
    await cover.open_cover()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1223813:4",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=1.0,
    )
    assert cover.current_cover_position == 100
    assert cover.current_cover_tilt_position == 100
    await cover.close_cover()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1223813:4",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=0.0,
    )
    assert cover.current_cover_position == 0
    assert cover.current_cover_tilt_position == 0
    await cover.open_cover_tilt()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1223813:4",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=0.0,
    )
    assert cover.current_cover_position == 0
    assert cover.current_cover_tilt_position == 100
    await cover.set_cover_tilt_position(45)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1223813:4",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=0.0,
    )
    assert cover.current_cover_position == 0
    assert cover.current_cover_tilt_position == 45
    await cover.close_cover_tilt()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1223813:4",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=0.0,
    )
    assert cover.current_cover_position == 0
    assert cover.current_cover_tilt_position == 0


@pytest.mark.asyncio
async def test_cegarage(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test CeGarage."""
    central, mock_client = await central_local_factory.get_central(TEST_DEVICES)
    assert central
    cover: CeGarage = cast(
        CeGarage, await get_hm_custom_entity(central, "VCU3574044", 1)
    )
    assert cover.usage == HmEntityUsage.CE_PRIMARY

    assert cover.current_cover_position is None
    await cover.set_cover_position(81)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU3574044:1",
        paramset_key="VALUES",
        parameter="DOOR_COMMAND",
        value=1,
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU3574044:1", "DOOR_STATE", 1)
    assert cover.current_cover_position == 100
    await cover.close_cover()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU3574044:1",
        paramset_key="VALUES",
        parameter="DOOR_COMMAND",
        value=3,
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU3574044:1", "DOOR_STATE", 0)
    assert cover.current_cover_position == 0
    await cover.set_cover_position(10)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU3574044:1",
        paramset_key="VALUES",
        parameter="DOOR_COMMAND",
        value=3,
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU3574044:1", "DOOR_STATE", 2)
    assert cover.current_cover_position == 10
    await cover.open_cover()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU3574044:1",
        paramset_key="VALUES",
        parameter="DOOR_COMMAND",
        value=1,
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU3574044:1", "DOOR_STATE", 1)
    assert cover.current_cover_position == 100
