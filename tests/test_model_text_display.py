# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for text display data points of aiohomematic."""

from __future__ import annotations

from typing import cast
from unittest.mock import call

import pytest

from aiohomematic.const import DataPointUsage, ParamsetKey
from aiohomematic.exceptions import ValidationException
from aiohomematic.model.custom import CustomDpTextDisplay
from aiohomematic_test_support.helper import get_prepared_custom_data_point

TEST_DEVICES: set[str] = {"VCU3756007"}

# pylint: disable=protected-access


class TestTextDisplay:
    """Tests for CustomDpTextDisplay data points."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_text_display_properties(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test CustomDpTextDisplay properties and available options."""
        central, _, _ = central_client_factory_with_ccu_client
        display: CustomDpTextDisplay = cast(
            CustomDpTextDisplay, get_prepared_custom_data_point(central, "VCU3756007", 3)
        )
        assert display.usage == DataPointUsage.CDP_PRIMARY
        assert display.service_method_names == (
            "load_data_point_value",
            "send_text",
        )

        # Verify available options are populated
        assert display.available_icons is not None
        assert len(display.available_icons) >= 2  # At least some icons
        assert "NO_ICON" in display.available_icons  # First icon is always NO_ICON

        assert display.available_sounds is not None
        assert len(display.available_sounds) >= 2  # At least some sounds

        assert display.available_background_colors is not None
        assert len(display.available_background_colors) >= 2  # At least WHITE and BLACK
        assert "WHITE" in display.available_background_colors
        assert "BLACK" in display.available_background_colors

        assert display.available_text_colors is not None
        assert len(display.available_text_colors) >= 2  # At least WHITE and BLACK
        assert "WHITE" in display.available_text_colors
        assert "BLACK" in display.available_text_colors

        assert display.available_alignments is not None
        assert len(display.available_alignments) >= 2  # At least some alignments
        assert "CENTER" in display.available_alignments

        # Test support properties
        assert display.supports_icons is True
        assert display.supports_sounds is True


class TestTextDisplaySendText:
    """Tests for send_text method using individual data points."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_send_text_basic(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test send_text with basic text only (defaults for other params)."""
        central, mock_client, _ = central_client_factory_with_ccu_client
        display: CustomDpTextDisplay = cast(
            CustomDpTextDisplay, get_prepared_custom_data_point(central, "VCU3756007", 3)
        )

        await display.send_text(text="Hello World")

        # Verify put_paramset is called with individual parameters
        # Default: WHITE background, BLACK text, NO_ICON, CENTER, display_id 1
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU3756007:3",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "DISPLAY_DATA_BACKGROUND_COLOR": "WHITE",
                "DISPLAY_DATA_TEXT_COLOR": "BLACK",
                "DISPLAY_DATA_ICON": "NO_ICON",
                "DISPLAY_DATA_ALIGNMENT": "CENTER",
                "DISPLAY_DATA_STRING": "Hello World",
                "DISPLAY_DATA_ID": 1,
                "DISPLAY_DATA_COMMIT": True,
            },
            wait_for_callback=None,
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_send_text_empty_text(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test send_text with empty text clears the display."""
        central, mock_client, _ = central_client_factory_with_ccu_client
        display: CustomDpTextDisplay = cast(
            CustomDpTextDisplay, get_prepared_custom_data_point(central, "VCU3756007", 3)
        )

        await display.send_text(text="")

        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU3756007:3",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "DISPLAY_DATA_BACKGROUND_COLOR": "WHITE",
                "DISPLAY_DATA_TEXT_COLOR": "BLACK",
                "DISPLAY_DATA_ICON": "NO_ICON",
                "DISPLAY_DATA_ALIGNMENT": "CENTER",
                "DISPLAY_DATA_STRING": "",
                "DISPLAY_DATA_ID": 1,
                "DISPLAY_DATA_COMMIT": True,
            },
            wait_for_callback=None,
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_send_text_full_parameters(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test send_text with all parameters specified."""
        central, mock_client, _ = central_client_factory_with_ccu_client
        display: CustomDpTextDisplay = cast(
            CustomDpTextDisplay, get_prepared_custom_data_point(central, "VCU3756007", 3)
        )

        # Use actual available values from the device
        assert display.available_icons is not None
        assert display.available_sounds is not None
        assert display.available_alignments is not None

        # Use third icon
        test_icon = display.available_icons[2]

        # Use third sound
        test_sound = display.available_sounds[2]

        # Find RIGHT alignment or use second available
        alignment = "RIGHT" if "RIGHT" in display.available_alignments else display.available_alignments[1]

        await display.send_text(
            text="Door Open",
            icon=test_icon,
            background_color="BLACK",
            text_color="WHITE",
            alignment=alignment,
            display_id=3,
            sound=test_sound,
            repeat=5,
            interval=2,
        )

        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU3756007:3",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "DISPLAY_DATA_BACKGROUND_COLOR": "BLACK",
                "DISPLAY_DATA_TEXT_COLOR": "WHITE",
                "DISPLAY_DATA_ICON": test_icon,
                "DISPLAY_DATA_ALIGNMENT": alignment,
                "DISPLAY_DATA_STRING": "Door Open",
                "DISPLAY_DATA_ID": 3,
                "ACOUSTIC_NOTIFICATION_SELECTION": test_sound,
                "REPETITIONS": "REPETITIONS_005",
                "INTERVAL": 2,
                "DISPLAY_DATA_COMMIT": True,
            },
            wait_for_callback=None,
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_send_text_no_repetition(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test send_text with repeat=0 sends NO_REPETITION."""
        central, mock_client, _ = central_client_factory_with_ccu_client
        display: CustomDpTextDisplay = cast(
            CustomDpTextDisplay, get_prepared_custom_data_point(central, "VCU3756007", 3)
        )

        assert display.available_sounds is not None
        test_sound = display.available_sounds[1]

        await display.send_text(text="Silent", sound=test_sound, repeat=0)

        values = mock_client.method_calls[-1].kwargs["values"]
        assert values["REPETITIONS"] == "NO_REPETITION"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_send_text_with_sound(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test send_text with sound includes sound parameters."""
        central, mock_client, _ = central_client_factory_with_ccu_client
        display: CustomDpTextDisplay = cast(
            CustomDpTextDisplay, get_prepared_custom_data_point(central, "VCU3756007", 3)
        )

        # Use second available sound
        assert display.available_sounds is not None
        test_sound = display.available_sounds[1]

        await display.send_text(text="Alert", sound=test_sound, repeat=3)

        # With sound, the values include sound parameters
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU3756007:3",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "DISPLAY_DATA_BACKGROUND_COLOR": "WHITE",
                "DISPLAY_DATA_TEXT_COLOR": "BLACK",
                "DISPLAY_DATA_ICON": "NO_ICON",
                "DISPLAY_DATA_ALIGNMENT": "CENTER",
                "DISPLAY_DATA_STRING": "Alert",
                "DISPLAY_DATA_ID": 1,
                "ACOUSTIC_NOTIFICATION_SELECTION": test_sound,
                "REPETITIONS": "REPETITIONS_003",
                "INTERVAL": 1,
                "DISPLAY_DATA_COMMIT": True,
            },
            wait_for_callback=None,
        )


class TestTextDisplayValidation:
    """Tests for send_text input validation."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_send_text_invalid_alignment(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test send_text raises ValidationException for invalid alignment."""
        central, _, _ = central_client_factory_with_ccu_client
        display: CustomDpTextDisplay = cast(
            CustomDpTextDisplay, get_prepared_custom_data_point(central, "VCU3756007", 3)
        )

        with pytest.raises(ValidationException):
            await display.send_text(text="Test", alignment="INVALID_ALIGN")

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_send_text_invalid_background_color(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test send_text raises ValidationException for invalid background color."""
        central, _, _ = central_client_factory_with_ccu_client
        display: CustomDpTextDisplay = cast(
            CustomDpTextDisplay, get_prepared_custom_data_point(central, "VCU3756007", 3)
        )

        with pytest.raises(ValidationException):
            await display.send_text(text="Test", background_color="INVALID_COLOR")

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_send_text_invalid_display_id_high(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test send_text raises ValidationException for display_id > 5."""
        central, _, _ = central_client_factory_with_ccu_client
        display: CustomDpTextDisplay = cast(
            CustomDpTextDisplay, get_prepared_custom_data_point(central, "VCU3756007", 3)
        )

        with pytest.raises(ValidationException):
            await display.send_text(text="Test", display_id=6)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_send_text_invalid_display_id_low(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test send_text raises ValidationException for display_id < 1."""
        central, _, _ = central_client_factory_with_ccu_client
        display: CustomDpTextDisplay = cast(
            CustomDpTextDisplay, get_prepared_custom_data_point(central, "VCU3756007", 3)
        )

        with pytest.raises(ValidationException):
            await display.send_text(text="Test", display_id=0)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_send_text_invalid_icon(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test send_text raises ValidationException for invalid icon."""
        central, _, _ = central_client_factory_with_ccu_client
        display: CustomDpTextDisplay = cast(
            CustomDpTextDisplay, get_prepared_custom_data_point(central, "VCU3756007", 3)
        )

        with pytest.raises(ValidationException):
            await display.send_text(text="Test", icon="INVALID_ICON")

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_send_text_invalid_repeat_high(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test send_text raises ValidationException for repeat > 15."""
        central, _, _ = central_client_factory_with_ccu_client
        display: CustomDpTextDisplay = cast(
            CustomDpTextDisplay, get_prepared_custom_data_point(central, "VCU3756007", 3)
        )

        with pytest.raises(ValidationException):
            await display.send_text(text="Test", repeat=16)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_send_text_invalid_repeat_low(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test send_text raises ValidationException for repeat < -1."""
        central, _, _ = central_client_factory_with_ccu_client
        display: CustomDpTextDisplay = cast(
            CustomDpTextDisplay, get_prepared_custom_data_point(central, "VCU3756007", 3)
        )

        # repeat=-1 is valid (INFINITE_REPETITIONS), but -2 is not
        with pytest.raises(ValidationException):
            await display.send_text(text="Test", repeat=-2)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_send_text_invalid_sound(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test send_text raises ValidationException for invalid sound."""
        central, _, _ = central_client_factory_with_ccu_client
        display: CustomDpTextDisplay = cast(
            CustomDpTextDisplay, get_prepared_custom_data_point(central, "VCU3756007", 3)
        )

        with pytest.raises(ValidationException):
            await display.send_text(text="Test", sound="INVALID_SOUND")

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_send_text_invalid_text_color(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test send_text raises ValidationException for invalid text color."""
        central, _, _ = central_client_factory_with_ccu_client
        display: CustomDpTextDisplay = cast(
            CustomDpTextDisplay, get_prepared_custom_data_point(central, "VCU3756007", 3)
        )

        with pytest.raises(ValidationException):
            await display.send_text(text="Test", text_color="INVALID_COLOR")


class TestTextDisplayHelpers:
    """Tests for helper methods."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_get_index_from_value_list(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test _get_index_from_value_list helper method."""
        central, _, _ = central_client_factory_with_ccu_client
        display: CustomDpTextDisplay = cast(
            CustomDpTextDisplay, get_prepared_custom_data_point(central, "VCU3756007", 3)
        )

        # Test with valid value
        value_list = ("A", "B", "C")
        assert display._get_index_from_value_list(value="A", value_list=value_list) == 0
        assert display._get_index_from_value_list(value="B", value_list=value_list) == 1
        assert display._get_index_from_value_list(value="C", value_list=value_list) == 2

        # Test with value not in list
        assert display._get_index_from_value_list(value="D", value_list=value_list) is None

        # Test with None value
        assert display._get_index_from_value_list(value=None, value_list=value_list) is None

        # Test with None value_list
        assert display._get_index_from_value_list(value="A", value_list=None) is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_get_repetition_string(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test _get_repetition_string helper method."""
        central, _, _ = central_client_factory_with_ccu_client
        display: CustomDpTextDisplay = cast(
            CustomDpTextDisplay, get_prepared_custom_data_point(central, "VCU3756007", 3)
        )

        # Test conversion of int to string (format: REPETITIONS_XXX with leading zeros)
        assert display._get_repetition_string(repeat=0) == "NO_REPETITION"
        assert display._get_repetition_string(repeat=1) == "REPETITIONS_001"
        assert display._get_repetition_string(repeat=5) == "REPETITIONS_005"
        assert display._get_repetition_string(repeat=14) == "REPETITIONS_014"
        assert display._get_repetition_string(repeat=-1) == "INFINITE_REPETITIONS"
