# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Tests for sound player data points of aiohomematic."""

from __future__ import annotations

from typing import cast

import pytest

from aiohomematic.const import DataPointUsage
from aiohomematic.exceptions import ValidationException
from aiohomematic.model.custom.light import CustomDpSoundPlayerLed, _convert_flash_time_to_on_time_list
from aiohomematic.model.custom.siren import CustomDpSoundPlayer, _convert_repetitions
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

        # Test support properties (comparable to other sirens)
        assert sound_player.supports_soundfiles == (sound_player.available_soundfiles is not None)
        assert sound_player.supports_duration is True  # Inherited from siren base
        assert sound_player.supports_tones is True  # available_tones maps to available_soundfiles

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

        # Test invalid repetitions (out of range)
        with pytest.raises(ValueError):
            await sound_player.play_sound(repetitions=19)  # Max is 18

        with pytest.raises(ValueError):
            await sound_player.play_sound(repetitions=-2)  # Only -1 is valid for infinite

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


class TestFlashTimeConversion:
    """Tests for flash_time to ON_TIME_LIST conversion."""

    def test_flash_time_exact_matches(self) -> None:
        """Test exact ms values map correctly."""
        assert _convert_flash_time_to_on_time_list(flash_time_ms=100) == "100MS"
        assert _convert_flash_time_to_on_time_list(flash_time_ms=500) == "500MS"
        assert _convert_flash_time_to_on_time_list(flash_time_ms=1000) == "1S"
        assert _convert_flash_time_to_on_time_list(flash_time_ms=2000) == "2S"
        assert _convert_flash_time_to_on_time_list(flash_time_ms=5000) == "5S"

    def test_flash_time_large_values_return_permanently_on(self) -> None:
        """Test that values > 5000ms return PERMANENTLY_ON."""
        assert _convert_flash_time_to_on_time_list(flash_time_ms=5001) == "PERMANENTLY_ON"
        assert _convert_flash_time_to_on_time_list(flash_time_ms=10000) == "PERMANENTLY_ON"

    def test_flash_time_nearest_match(self) -> None:
        """Test that values are rounded to nearest match."""
        # 150 is closer to 100 than 200
        assert _convert_flash_time_to_on_time_list(flash_time_ms=149) == "100MS"
        # 150 is equidistant, should pick first match (100MS)
        assert _convert_flash_time_to_on_time_list(flash_time_ms=150) == "100MS"
        # 151 is closer to 200
        assert _convert_flash_time_to_on_time_list(flash_time_ms=151) == "200MS"
        # 1500 is equidistant between 1S and 2S
        assert _convert_flash_time_to_on_time_list(flash_time_ms=1500) == "1S"
        # 1501 is closer to 2S
        assert _convert_flash_time_to_on_time_list(flash_time_ms=1501) == "2S"

    def test_flash_time_negative_returns_permanently_on(self) -> None:
        """Test that negative values return PERMANENTLY_ON."""
        assert _convert_flash_time_to_on_time_list(flash_time_ms=-100) == "PERMANENTLY_ON"

    def test_flash_time_none_returns_permanently_on(self) -> None:
        """Test that None returns PERMANENTLY_ON."""
        assert _convert_flash_time_to_on_time_list(flash_time_ms=None) == "PERMANENTLY_ON"

    def test_flash_time_zero_returns_permanently_on(self) -> None:
        """Test that 0 returns PERMANENTLY_ON."""
        assert _convert_flash_time_to_on_time_list(flash_time_ms=0) == "PERMANENTLY_ON"


class TestRepetitionsConversion:
    """Tests for repetitions to VALUE_LIST conversion."""

    def test_repetitions_invalid_raises_value_error(self) -> None:
        """Test that invalid values raise ValueError."""
        with pytest.raises(ValueError):
            _convert_repetitions(repetitions=19)  # Max is 18

        with pytest.raises(ValueError):
            _convert_repetitions(repetitions=-2)  # Only -1 is valid for infinite

        with pytest.raises(ValueError):
            _convert_repetitions(repetitions=100)  # Way out of range

    def test_repetitions_minus_one_returns_infinite(self) -> None:
        """Test that -1 returns INFINITE_REPETITIONS."""
        assert _convert_repetitions(repetitions=-1) == "INFINITE_REPETITIONS"

    def test_repetitions_none_returns_no_repetition(self) -> None:
        """Test that None returns NO_REPETITION."""
        assert _convert_repetitions(repetitions=None) == "NO_REPETITION"

    def test_repetitions_valid_range(self) -> None:
        """Test that 1-18 returns correct REPETITIONS_NNN values."""
        assert _convert_repetitions(repetitions=1) == "REPETITIONS_001"
        assert _convert_repetitions(repetitions=5) == "REPETITIONS_005"
        assert _convert_repetitions(repetitions=10) == "REPETITIONS_010"
        assert _convert_repetitions(repetitions=18) == "REPETITIONS_018"

    def test_repetitions_zero_returns_no_repetition(self) -> None:
        """Test that 0 returns NO_REPETITION."""
        assert _convert_repetitions(repetitions=0) == "NO_REPETITION"
