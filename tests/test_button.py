"""Tests for button data points of hahomematic."""

from __future__ import annotations

from typing import cast
from unittest.mock import Mock, call

import pytest

from hahomematic.central import CentralUnit
from hahomematic.client import Client
from hahomematic.const import DataPointUsage, ParamsetKey, ProgramData
from hahomematic.model.generic import DpButton
from hahomematic.model.hub import ProgramDpButton

from tests import helper

TEST_DEVICES: dict[str, str] = {
    "VCU1437294": "HmIP-SMI.json",
}

# pylint: disable=protected-access


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "address_device_translation",
        "do_mock_client",
        "add_sysvars",
        "add_programs",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [
        (TEST_DEVICES, True, False, False, None, None),
    ],
)
async def test_hmbutton(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test HmButton."""
    central, mock_client, _ = central_client_factory
    button: DpButton = cast(
        DpButton,
        central.get_generic_data_point("VCU1437294:1", "RESET_MOTION"),
    )
    assert button.usage == DataPointUsage.DATA_POINT
    assert button.available is True
    assert button.is_readable is False
    assert button.value is None
    assert button.values is None
    assert button.hmtype == "ACTION"
    await button.press()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1437294:1",
        paramset_key=ParamsetKey.VALUES,
        parameter="RESET_MOTION",
        value=True,
    )

    call_count = len(mock_client.method_calls)
    await button.press()
    assert (call_count + 1) == len(mock_client.method_calls)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "address_device_translation",
        "do_mock_client",
        "add_sysvars",
        "add_programs",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [
        ({}, True, False, True, None, None),
    ],
)
async def test_hmprogrambutton(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test HmProgramButton."""
    central, mock_client, _ = central_client_factory
    button: ProgramDpButton = cast(ProgramDpButton, central.get_program_data_point("pid1").button)
    assert button.usage == DataPointUsage.DATA_POINT
    assert button.available is True
    assert button.is_active is True
    assert button.is_internal is False
    assert button.name == "p1"
    await button.press()
    assert mock_client.method_calls[-1] == call.execute_program(pid="pid1")
    updated_program = ProgramData(
        legacy_name="p1",
        description="",
        pid="pid1",
        is_active=False,
        is_internal=True,
        last_execute_time="1900-1-1",
    )
    button.update_data(updated_program)
    assert button.is_active is False
    assert button.is_internal is True

    button2: ProgramDpButton = cast(ProgramDpButton, central.get_program_data_point("pid2").button)
    assert button2.usage == DataPointUsage.DATA_POINT
    assert button2.is_active is False
    assert button2.is_internal is False
    assert button2.name == "p_2"
