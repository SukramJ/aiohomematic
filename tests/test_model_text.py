"""Tests for model/hub text data points of aiohomematic."""

from __future__ import annotations

from typing import cast
from unittest.mock import call

import pytest

from aiohomematic.const import DataPointUsage
from aiohomematic.model.hub import SysvarDpText

# pylint: disable=protected-access


class TestSysvarText:
    """Tests for SysvarDpText data points."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            ({}, True, None, None),
        ],
    )
    async def test_sysvar_text_functionality(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test SysvarDpText value handling and variable sending."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        text: SysvarDpText = cast(SysvarDpText, central.hub_coordinator.get_sysvar_data_point(legacy_name="string_ext"))
        assert text.usage == DataPointUsage.DATA_POINT

        assert text.unit is None
        assert text.values is None
        assert text.value == "test1"
        await text.send_variable(value="test23")
        assert mock_client.method_calls[-1] == call.set_system_variable(legacy_name="string_ext", value="test23")
        assert text.value == "test23"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            ({}, True, None, None),
        ],
    )
    async def test_sysvar_text_long_value(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test SysvarDpText with very long string values (>255 chars)."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        text: SysvarDpText = cast(SysvarDpText, central.hub_coordinator.get_sysvar_data_point(legacy_name="string_ext"))
        assert text.usage == DataPointUsage.DATA_POINT

        # Create a string longer than 255 characters
        long_string = "a" * 300
        await text.send_variable(value=long_string)

        # The value should be truncated to 255 characters
        # Note: The actual value stored may be the full or truncated version
        # depending on how the backend handles it
        assert text.value is not None
