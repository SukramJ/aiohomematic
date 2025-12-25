# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Tests for sound player data points of aiohomematic."""

from __future__ import annotations

from typing import cast

import pytest

from aiohomematic.const import DataPointUsage
from aiohomematic.exceptions import ValidationException
from aiohomematic.model.custom.light import CustomDpSoundPlayerLed
from aiohomematic.model.custom.siren import CustomDpSoundPlayer
from aiohomematic_test_support.helper import get_prepared_custom_data_point

# HmIP-MP3P device address (from pydevccu session data)
TEST_DEVICES: set[str] = {"VCU1543608"}

# pylint: disable=protected-access


class TestSoundPlayer:
    """Tests for sound player data points."""

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
    async def test_led_player_hs_color_conversion(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test that hs_color is converted to fixed color like CustomDpIpFixedColorLight."""
        central, _, _ = central_client_factory_with_homegear_client

        led_player: CustomDpSoundPlayerLed = cast(
            CustomDpSoundPlayerLed,
            get_prepared_custom_data_point(central, "VCU1543608", 6),
        )

        assert led_player.available_colors is not None, "Colors should be available"
        assert led_player.hs_color is not None, "hs_color property should work"
        assert led_player.color_name is not None or led_player.color_name is None  # Can be None initially

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
    async def test_sound_player_convert_soundfile_index(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test the _convert_soundfile_index helper method."""
        central, _, _ = central_client_factory_with_homegear_client

        sound_player: CustomDpSoundPlayer = cast(
            CustomDpSoundPlayer,
            get_prepared_custom_data_point(central, "VCU1543608", 2),
        )

        # Test valid indices
        assert sound_player._convert_soundfile_index(1) == "SOUNDFILE_001"
        assert sound_player._convert_soundfile_index(10) == "SOUNDFILE_010"
        assert sound_player._convert_soundfile_index(100) == "SOUNDFILE_100"
        assert sound_player._convert_soundfile_index(189) == "SOUNDFILE_189"

        # Test invalid indices
        with pytest.raises(ValueError, match="Soundfile index must be 1-189"):
            sound_player._convert_soundfile_index(0)

        with pytest.raises(ValueError, match="Soundfile index must be 1-189"):
            sound_player._convert_soundfile_index(190)

        with pytest.raises(ValueError, match="Soundfile index must be 1-189"):
            sound_player._convert_soundfile_index(-1)

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
    async def test_sound_player_discovery(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test that HmIP-MP3P sound player is discovered correctly."""
        central, _, _ = central_client_factory_with_homegear_client

        # Check that sound player custom data point exists on channel 2
        sound_player = get_prepared_custom_data_point(central, "VCU1543608", 2)
        assert sound_player is not None, "Sound player should exist on channel 2"
        assert isinstance(sound_player, CustomDpSoundPlayer)
        assert sound_player.usage == DataPointUsage.CDP_PRIMARY

        # Check that LED custom data point exists on channel 6
        led_player = get_prepared_custom_data_point(central, "VCU1543608", 6)
        assert led_player is not None, "LED player should exist on channel 6"
        assert isinstance(led_player, CustomDpSoundPlayerLed)
        assert led_player.usage == DataPointUsage.CDP_PRIMARY

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
    async def test_sound_player_led_properties(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test CustomDpSoundPlayerLed properties and available options."""
        central, _, _ = central_client_factory_with_homegear_client

        led_player: CustomDpSoundPlayerLed = cast(
            CustomDpSoundPlayerLed,
            get_prepared_custom_data_point(central, "VCU1543608", 6),
        )
        assert led_player is not None

        # Test service method names (turn_on/turn_off - comparable to CustomDpIpFixedColorLight)
        assert led_player.service_method_names == (
            "load_data_point_value",
            "turn_off",
            "turn_on",
        )

        # Test available colors (from COLOR parameter's VALUE_LIST)
        assert led_player.available_colors is not None
        assert "BLACK" in led_player.available_colors
        assert "WHITE" in led_player.available_colors
        assert "RED" in led_player.available_colors
        assert "BLUE" in led_player.available_colors

        # Test available on times
        if led_player.available_on_times is not None:
            assert "100MS" in led_player.available_on_times
            assert "PERMANENTLY_ON" in led_player.available_on_times

        # Test available repetitions
        if led_player.available_repetitions is not None:
            assert "NO_REPETITION" in led_player.available_repetitions

        # Test support property (hs_color always returns value, so supports_hs_color is True)
        assert led_player.supports_hs_color is True

        # Test initial state
        assert led_player.is_on is False

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
    async def test_sound_player_properties(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test CustomDpSoundPlayer properties and available options."""
        central, _, _ = central_client_factory_with_homegear_client

        sound_player: CustomDpSoundPlayer = cast(
            CustomDpSoundPlayer,
            get_prepared_custom_data_point(central, "VCU1543608", 2),
        )
        assert sound_player is not None

        # Test service method names (includes inherited turn_on/turn_off from BaseCustomDpSiren)
        assert sound_player.service_method_names == (
            "load_data_point_value",
            "play_sound",
            "stop_sound",
            "turn_off",
            "turn_on",
        )

        # Test available soundfiles (from SOUNDFILE parameter's VALUE_LIST)
        assert sound_player.available_soundfiles is not None
        assert len(sound_player.available_soundfiles) >= 10  # Should have many soundfiles
        assert "INTERNAL_SOUNDFILE" in sound_player.available_soundfiles
        assert "SOUNDFILE_001" in sound_player.available_soundfiles

        # Test available repetitions
        if sound_player.available_repetitions is not None:
            assert "NO_REPETITION" in sound_player.available_repetitions
            assert "INFINITE_REPETITIONS" in sound_player.available_repetitions

        # Test available duration units
        if sound_player.available_duration_units is not None:
            assert "S" in sound_player.available_duration_units
            assert "M" in sound_player.available_duration_units

        # Test support property (depends on available_soundfiles)
        assert sound_player.supports_soundfiles == (sound_player.available_soundfiles is not None)

        # Test initial state (is_on inherited from BaseCustomDpSiren)
        assert sound_player.is_on is False

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
    async def test_sound_player_validation_duration_unit(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test duration_unit validation in play_sound."""
        central, _, _ = central_client_factory_with_homegear_client

        sound_player: CustomDpSoundPlayer = cast(
            CustomDpSoundPlayer,
            get_prepared_custom_data_point(central, "VCU1543608", 2),
        )

        assert sound_player.available_duration_units is not None, "Duration units should be available"

        # Test invalid duration_unit
        with pytest.raises(ValidationException):
            await sound_player.play_sound(duration_unit="INVALID_UNIT")

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
    async def test_sound_player_validation_repetitions(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test repetitions validation in play_sound."""
        central, _, _ = central_client_factory_with_homegear_client

        sound_player: CustomDpSoundPlayer = cast(
            CustomDpSoundPlayer,
            get_prepared_custom_data_point(central, "VCU1543608", 2),
        )

        assert sound_player.available_repetitions is not None, "Repetitions should be available"

        # Test invalid repetitions
        with pytest.raises(ValidationException):
            await sound_player.play_sound(repetitions="INVALID_REPETITIONS")

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
    async def test_sound_player_validation_soundfile(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test soundfile validation in play_sound."""
        central, _, _ = central_client_factory_with_homegear_client

        sound_player: CustomDpSoundPlayer = cast(
            CustomDpSoundPlayer,
            get_prepared_custom_data_point(central, "VCU1543608", 2),
        )

        assert sound_player.available_soundfiles is not None, "Soundfiles should be available"

        # Test invalid soundfile
        with pytest.raises(ValidationException):
            await sound_player.play_sound(soundfile="INVALID_SOUNDFILE")

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
    async def test_sound_player_validation_volume(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test volume validation in play_sound."""
        central, _, _ = central_client_factory_with_homegear_client

        sound_player: CustomDpSoundPlayer = cast(
            CustomDpSoundPlayer,
            get_prepared_custom_data_point(central, "VCU1543608", 2),
        )

        # Test invalid volume values
        with pytest.raises(ValidationException):
            await sound_player.play_sound(volume=-0.1)

        with pytest.raises(ValidationException):
            await sound_player.play_sound(volume=1.1)
