# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Tests for text display data points of aiohomematic."""

from __future__ import annotations

from typing import cast
from unittest.mock import call

import pytest

from aiohomematic.const import WAIT_FOR_CALLBACK, DataPointUsage, ParamsetKey
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
    """Tests for send_text method and COMBINED_PARAMETER conversion."""

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

        # Verify the COMBINED_PARAMETER format
        # Default: WHITE background, BLACK text, no icon (0), CENTER, display_id 1
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU3756007:3",
            paramset_key=ParamsetKey.VALUES,
            parameter="COMBINED_PARAMETER",
            value="{DDBC=WHITE,DDTC=BLACK,DDI=0,DDA=CENTER,DDS=Hello World,DDID=1,DDC=true}",
            wait_for_callback=WAIT_FOR_CALLBACK,
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

        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU3756007:3",
            paramset_key=ParamsetKey.VALUES,
            parameter="COMBINED_PARAMETER",
            value="{DDBC=WHITE,DDTC=BLACK,DDI=0,DDA=CENTER,DDS=,DDID=1,DDC=true}",
            wait_for_callback=WAIT_FOR_CALLBACK,
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

        # Use third icon (index 2)
        test_icon = display.available_icons[2]
        icon_index = 2

        # Use third sound (index 2)
        test_sound = display.available_sounds[2]
        sound_index = 2

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
        )

        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU3756007:3",
            paramset_key=ParamsetKey.VALUES,
            parameter="COMBINED_PARAMETER",
            value=f"{{DDBC=BLACK,DDTC=WHITE,DDI={icon_index},DDA={alignment},DDS=Door Open,DDID=3,DDC=true}},{{R=5,IN=1,ANS={sound_index}}}",
            wait_for_callback=WAIT_FOR_CALLBACK,
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
    async def test_send_text_with_alignment(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test send_text with different alignments."""
        central, mock_client, _ = central_client_factory_with_ccu_client
        display: CustomDpTextDisplay = cast(
            CustomDpTextDisplay, get_prepared_custom_data_point(central, "VCU3756007", 3)
        )

        await display.send_text(text="Left aligned", alignment="LEFT")

        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU3756007:3",
            paramset_key=ParamsetKey.VALUES,
            parameter="COMBINED_PARAMETER",
            value="{DDBC=WHITE,DDTC=BLACK,DDI=0,DDA=LEFT,DDS=Left aligned,DDID=1,DDC=true}",
            wait_for_callback=WAIT_FOR_CALLBACK,
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
    async def test_send_text_with_colors(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test send_text with custom background and text colors."""
        central, mock_client, _ = central_client_factory_with_ccu_client
        display: CustomDpTextDisplay = cast(
            CustomDpTextDisplay, get_prepared_custom_data_point(central, "VCU3756007", 3)
        )

        # Use BLACK background and WHITE text (inverse of defaults)
        await display.send_text(
            text="Inverted",
            background_color="BLACK",
            text_color="WHITE",
        )

        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU3756007:3",
            paramset_key=ParamsetKey.VALUES,
            parameter="COMBINED_PARAMETER",
            value="{DDBC=BLACK,DDTC=WHITE,DDI=0,DDA=CENTER,DDS=Inverted,DDID=1,DDC=true}",
            wait_for_callback=WAIT_FOR_CALLBACK,
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
    async def test_send_text_with_display_id(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test send_text with different display slots."""
        central, mock_client, _ = central_client_factory_with_ccu_client
        display: CustomDpTextDisplay = cast(
            CustomDpTextDisplay, get_prepared_custom_data_point(central, "VCU3756007", 3)
        )

        await display.send_text(text="Slot 2", display_id=2)

        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU3756007:3",
            paramset_key=ParamsetKey.VALUES,
            parameter="COMBINED_PARAMETER",
            value="{DDBC=WHITE,DDTC=BLACK,DDI=0,DDA=CENTER,DDS=Slot 2,DDID=2,DDC=true}",
            wait_for_callback=WAIT_FOR_CALLBACK,
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
    async def test_send_text_with_icon(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test send_text with icon specified."""
        central, mock_client, _ = central_client_factory_with_ccu_client
        display: CustomDpTextDisplay = cast(
            CustomDpTextDisplay, get_prepared_custom_data_point(central, "VCU3756007", 3)
        )

        # Use the second icon (first is NO_ICON which has index 0)
        assert display.available_icons is not None
        test_icon = display.available_icons[1]  # Second icon
        icon_index = 1

        await display.send_text(text="Light On", icon=test_icon)

        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU3756007:3",
            paramset_key=ParamsetKey.VALUES,
            parameter="COMBINED_PARAMETER",
            value=f"{{DDBC=WHITE,DDTC=BLACK,DDI={icon_index},DDA=CENTER,DDS=Light On,DDID=1,DDC=true}}",
            wait_for_callback=WAIT_FOR_CALLBACK,
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
    async def test_send_text_with_sound(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test send_text with sound adds sound part to COMBINED_PARAMETER."""
        central, mock_client, _ = central_client_factory_with_ccu_client
        display: CustomDpTextDisplay = cast(
            CustomDpTextDisplay, get_prepared_custom_data_point(central, "VCU3756007", 3)
        )

        # Use second available sound (first is DISABLE_ACOUSTIC_SIGNAL)
        assert display.available_sounds is not None
        test_sound = display.available_sounds[1]
        sound_index = 1

        await display.send_text(text="Alert", sound=test_sound, repeat=3)

        # With sound, the format includes the sound part
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU3756007:3",
            paramset_key=ParamsetKey.VALUES,
            parameter="COMBINED_PARAMETER",
            value=f"{{DDBC=WHITE,DDTC=BLACK,DDI=0,DDA=CENTER,DDS=Alert,DDID=1,DDC=true}},{{R=3,IN=1,ANS={sound_index}}}",
            wait_for_callback=WAIT_FOR_CALLBACK,
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
        """Test send_text raises ValidationException for repeat < 0."""
        central, _, _ = central_client_factory_with_ccu_client
        display: CustomDpTextDisplay = cast(
            CustomDpTextDisplay, get_prepared_custom_data_point(central, "VCU3756007", 3)
        )

        with pytest.raises(ValidationException):
            await display.send_text(text="Test", repeat=-1)

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


class TestTextDisplayIndexConversion:
    """Tests for icon and sound index conversion."""

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
    async def test_icon_index_conversion(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test that icons are correctly converted to indices."""
        central, mock_client, _ = central_client_factory_with_ccu_client
        display: CustomDpTextDisplay = cast(
            CustomDpTextDisplay, get_prepared_custom_data_point(central, "VCU3756007", 3)
        )

        # First icon should have index 0
        if display.available_icons:
            first_icon = display.available_icons[0]
            await display.send_text(text="Test", icon=first_icon)

            assert mock_client.method_calls[-1] == call.set_value(
                channel_address="VCU3756007:3",
                paramset_key=ParamsetKey.VALUES,
                parameter="COMBINED_PARAMETER",
                value="{DDBC=WHITE,DDTC=BLACK,DDI=0,DDA=CENTER,DDS=Test,DDID=1,DDC=true}",
                wait_for_callback=WAIT_FOR_CALLBACK,
            )

            # Last icon should have correct index
            last_icon = display.available_icons[-1]
            last_index = len(display.available_icons) - 1
            await display.send_text(text="Test", icon=last_icon)

            assert mock_client.method_calls[-1] == call.set_value(
                channel_address="VCU3756007:3",
                paramset_key=ParamsetKey.VALUES,
                parameter="COMBINED_PARAMETER",
                value=f"{{DDBC=WHITE,DDTC=BLACK,DDI={last_index},DDA=CENTER,DDS=Test,DDID=1,DDC=true}}",
                wait_for_callback=WAIT_FOR_CALLBACK,
            )
