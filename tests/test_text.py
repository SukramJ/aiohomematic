"""Tests for text data points of aiohomematic."""

from __future__ import annotations

from typing import cast
from unittest.mock import Mock, call

import pytest

from aiohomematic.central import CentralUnit
from aiohomematic.client import Client
from aiohomematic.const import DataPointUsage
from aiohomematic.model.generic import DpText
from aiohomematic.model.hub import SysvarDpText

from tests import helper

TEST_DEVICES: dict[str, str] = {}

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
async def no_test_hmtext(central_client: tuple[CentralUnit, Client | Mock]) -> None:
    """Test DpText. There are currently no text data points."""
    central, _ = central_client
    text: DpText = cast(DpText, central.get_generic_data_point("VCU7981740:1", "STATE"))
    assert text.usage == DataPointUsage.DATA_POINT


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
        ({}, True, True, False, None, None),
    ],
)
async def test_sysvardptext(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test SysvarDpText. There are currently no text data points."""
    central, mock_client, _ = central_client_factory
    text: SysvarDpText = cast(SysvarDpText, central.get_sysvar_data_point(legacy_name="string_ext"))
    assert text.usage == DataPointUsage.DATA_POINT

    assert text.unit is None
    assert text.values is None
    assert text.value == "test1"
    await text.send_variable("test23")
    assert mock_client.method_calls[-1] == call.set_system_variable(legacy_name="string_ext", value="test23")
    assert text.value == "test23"
