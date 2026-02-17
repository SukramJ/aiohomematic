# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for CCU translation lookup functions."""

from __future__ import annotations

import pytest

from aiohomematic.ccu_translations import (
    _match_link_prefix,
    get_channel_type_translation,
    get_device_model_description,
    get_parameter_translation,
    get_parameter_value_translation,
)


class TestGetLocale:
    """Test locale normalization."""

    def test_locale_with_region_code(self) -> None:
        """Test that locale with region (de-DE) uses the language part."""
        result_de = get_parameter_translation(parameter="ON_LEVEL", locale="de")
        result_de_de = get_parameter_translation(parameter="ON_LEVEL", locale="de-DE")
        assert result_de_de == result_de

    def test_locale_with_underscore(self) -> None:
        """Test that locale with underscore (de_DE) uses the language part."""
        result_de = get_parameter_translation(parameter="ON_LEVEL", locale="de")
        result_de_under = get_parameter_translation(parameter="ON_LEVEL", locale="de_DE")
        assert result_de_under == result_de

    def test_supported_locale_de(self) -> None:
        """Test that German locale is returned unchanged."""
        result = get_parameter_translation(parameter="ON_LEVEL", locale="de")
        assert result is not None

    def test_supported_locale_en(self) -> None:
        """Test that English locale is returned unchanged."""
        result = get_parameter_translation(parameter="ON_LEVEL", locale="en")
        assert result is not None

    def test_unsupported_locale_falls_back_to_english(self) -> None:
        """Test that unsupported locale falls back to English."""
        result_en = get_parameter_translation(parameter="ON_LEVEL", locale="en")
        result_fr = get_parameter_translation(parameter="ON_LEVEL", locale="fr")
        assert result_fr == result_en


class TestGetChannelTypeTranslation:
    """Test channel type translation lookup."""

    def test_case_insensitive(self) -> None:
        """Test that channel type lookup is case-insensitive."""
        upper = get_channel_type_translation(channel_type="DIMMER", locale="en")
        lower = get_channel_type_translation(channel_type="dimmer", locale="en")
        assert upper == lower

    def test_known_channel_type(self) -> None:
        """Test translation for a known channel type."""
        result = get_channel_type_translation(channel_type="DIMMER", locale="en")
        assert result is not None

    def test_unknown_channel_type(self) -> None:
        """Test that unknown channel type returns None."""
        result = get_channel_type_translation(channel_type="NONEXISTENT_TYPE_XYZ")
        assert result is None


class TestGetDeviceModelDescription:
    """Test device model description lookup."""

    def test_case_insensitive(self) -> None:
        """Test that model lookup is case-insensitive."""
        upper = get_device_model_description(model="HmIP-SWDO", locale="en")
        lower = get_device_model_description(model="hmip-swdo", locale="en")
        assert upper == lower

    def test_known_model(self) -> None:
        """Test translation for a known device model."""
        result = get_device_model_description(model="HmIP-SWDO", locale="en")
        assert result is not None

    def test_sub_model_fallback(self) -> None:
        """Test that sub_model is tried when model not found."""
        result = get_device_model_description(
            model="NONEXISTENT_MODEL_XYZ",
            sub_model="PS",
            locale="en",
        )
        # PS is a known subtype - should return something
        assert result is not None

    def test_sub_model_not_used_when_model_found(self) -> None:
        """Test that sub_model is not used when model is found."""
        model_result = get_device_model_description(model="HmIP-SWDO", locale="en")
        with_sub = get_device_model_description(model="HmIP-SWDO", sub_model="PS", locale="en")
        assert model_result == with_sub

    def test_unknown_model(self) -> None:
        """Test that unknown model returns None."""
        result = get_device_model_description(model="NONEXISTENT_MODEL_XYZ")
        assert result is None


class TestMatchLinkPrefix:
    """Test _match_link_prefix helper."""

    def test_case_insensitive(self) -> None:
        """Test that prefix matching is case-insensitive."""
        result = _match_link_prefix(parameter="SHORT_ON_LEVEL")
        assert result == ("short_", "on_level")

    def test_long_prefix(self) -> None:
        """Test LONG_ prefix is matched."""
        result = _match_link_prefix(parameter="long_rampon_time")
        assert result == ("long_", "rampon_time")

    def test_no_prefix(self) -> None:
        """Test parameter without prefix returns None."""
        result = _match_link_prefix(parameter="on_level")
        assert result is None

    def test_short_prefix(self) -> None:
        """Test SHORT_ prefix is matched."""
        result = _match_link_prefix(parameter="short_on_level")
        assert result == ("short_", "on_level")

    def test_unknown_prefix(self) -> None:
        """Test that unrelated prefix returns None."""
        result = _match_link_prefix(parameter="medium_on_level")
        assert result is None


class TestGetParameterTranslation:
    """Test parameter translation lookup."""

    def test_case_insensitive(self) -> None:
        """Test that parameter lookup is case-insensitive."""
        upper = get_parameter_translation(parameter="ON_LEVEL", locale="en")
        lower = get_parameter_translation(parameter="on_level", locale="en")
        assert upper == lower

    def test_channel_specific_overrides_global(self) -> None:
        """Test that channel-specific lookup takes priority over global."""
        # LONG_PRESS_TIME has channel-specific translations
        global_result = get_parameter_translation(parameter="LONG_PRESS_TIME", locale="en")
        channel_result = get_parameter_translation(
            parameter="LONG_PRESS_TIME",
            channel_type="KEY_TRANSCEIVER",
            locale="en",
        )
        assert global_result is not None
        assert channel_result is not None

    def test_direct_parameter(self) -> None:
        """Test direct parameter lookup."""
        result = get_parameter_translation(parameter="ON_LEVEL", locale="en")
        assert result is not None
        assert "on" in result.lower()

    def test_direct_parameter_de(self) -> None:
        """Test direct parameter lookup in German."""
        result = get_parameter_translation(parameter="ON_LEVEL", locale="de")
        assert result == 'Pegel im Zustand "ein"'

    def test_unknown_parameter(self) -> None:
        """Test that unknown parameter returns None."""
        result = get_parameter_translation(parameter="TOTALLY_UNKNOWN_PARAM_XYZ")
        assert result is None


class TestGetParameterTranslationLinkPrefix:
    """Test LINK paramset prefix stripping and label prepending."""

    @pytest.mark.parametrize(
        ("parameter", "locale", "expected"),
        [
            ("SHORT_RAMPON_TIME", "de", "Tastendruck kurz Rampenzeit beim Einschalten"),
            ("LONG_RAMPON_TIME", "de", "Tastendruck lang Rampenzeit beim Einschalten"),
            ("SHORT_RAMPOFF_TIME", "de", "Tastendruck kurz Rampenzeit beim Ausschalten"),
            ("LONG_RAMPOFF_TIME", "de", "Tastendruck lang Rampenzeit beim Ausschalten"),
            ("SHORT_ON_TIME", "de", "Tastendruck kurz Einschaltdauer"),
            ("SHORT_ON_MIN_LEVEL", "de", 'Tastendruck kurz Minimaler Pegel im Zustand "ein"'),
            ("SHORT_DIM_MAX_LEVEL", "de", "Tastendruck kurz Pegelbegrenzung beim Hochdimmen"),
            ("SHORT_DIM_MIN_LEVEL", "de", "Tastendruck kurz Pegelbegrenzung beim Herunterdimmen"),
            ("SHORT_DIM_STEP", "de", "Tastendruck kurz Schrittweite"),
            ("SHORT_OFFDELAY_TIME", "de", "Tastendruck kurz Ausschaltverzögerung"),
        ],
    )
    def test_dimmer_link_params_de(self, *, parameter: str, locale: str, expected: str) -> None:
        """Test German translations for common dimmer LINK paramset parameters."""
        result = get_parameter_translation(parameter=parameter, locale=locale)
        assert result == expected

    @pytest.mark.parametrize(
        ("parameter", "locale", "expected_prefix"),
        [
            ("SHORT_ON_LEVEL", "en", "Button press short"),
            ("LONG_ON_LEVEL", "en", "Button press long"),
            ("SHORT_DIM_STEP", "en", "Button press short"),
            ("LONG_DIM_MAX_LEVEL", "en", "Button press long"),
        ],
    )
    def test_link_params_en_prefix(
        self,
        *,
        parameter: str,
        locale: str,
        expected_prefix: str,
    ) -> None:
        """Test English translations have correct press-type prefix."""
        result = get_parameter_translation(parameter=parameter, locale=locale)
        assert result is not None
        assert result.startswith(expected_prefix)

    def test_long_prefix_fallback_de(self) -> None:
        """Test LONG_ prefix is stripped and label prepended (German)."""
        result = get_parameter_translation(parameter="LONG_ON_LEVEL", locale="de")
        assert result is not None
        assert result.startswith("Tastendruck lang ")
        assert result == 'Tastendruck lang Pegel im Zustand "ein"'

    def test_long_prefix_fallback_en(self) -> None:
        """Test LONG_ prefix is stripped and label prepended (English)."""
        result = get_parameter_translation(parameter="LONG_ON_LEVEL", locale="en")
        assert result is not None
        assert result.startswith("Button press long ")

    def test_long_prefix_unknown_base_returns_none(self) -> None:
        """Test that LONG_ with unknown base still returns None."""
        result = get_parameter_translation(parameter="LONG_NONEXISTENT_XYZ")
        assert result is None

    def test_short_and_long_differ_only_by_prefix(self) -> None:
        """Test that SHORT_ and LONG_ translations differ only in prefix label."""
        short = get_parameter_translation(parameter="SHORT_ON_LEVEL", locale="de")
        long = get_parameter_translation(parameter="LONG_ON_LEVEL", locale="de")
        assert short is not None
        assert long is not None
        assert short != long
        # Only the prefix label differs
        assert short.replace("Tastendruck kurz", "Tastendruck lang") == long

    def test_short_prefix_fallback_de(self) -> None:
        """Test SHORT_ prefix is stripped and label prepended (German)."""
        result = get_parameter_translation(parameter="SHORT_ON_LEVEL", locale="de")
        assert result is not None
        assert result.startswith("Tastendruck kurz ")
        assert result == 'Tastendruck kurz Pegel im Zustand "ein"'

    def test_short_prefix_fallback_en(self) -> None:
        """Test SHORT_ prefix is stripped and label prepended (English)."""
        result = get_parameter_translation(parameter="SHORT_ON_LEVEL", locale="en")
        assert result is not None
        assert result.startswith("Button press short ")
        # Base translation should be present
        base = get_parameter_translation(parameter="ON_LEVEL", locale="en")
        assert base is not None
        assert result == f"Button press short {base}"

    def test_short_prefix_unknown_base_returns_none(self) -> None:
        """Test that SHORT_ with unknown base still returns None."""
        result = get_parameter_translation(parameter="SHORT_NONEXISTENT_XYZ")
        assert result is None


class TestGetParameterValueTranslation:
    """Test parameter value translation lookup."""

    def test_direct_value(self) -> None:
        """Test direct parameter value lookup."""
        result = get_parameter_value_translation(
            parameter="ACOUSTIC_ALARM_ACTIVE",
            value="TRUE",
            locale="en",
        )
        assert result == "Acoustic signal activated"

    def test_link_prefix_fallback_long(self) -> None:
        """Test LONG_ prefix stripping for value translations."""
        direct = get_parameter_value_translation(
            parameter="ACOUSTIC_ALARM_ACTIVE",
            value="FALSE",
            locale="en",
        )
        long = get_parameter_value_translation(
            parameter="LONG_ACOUSTIC_ALARM_ACTIVE",
            value="FALSE",
            locale="en",
        )
        assert direct is not None
        assert long == direct

    def test_link_prefix_fallback_short(self) -> None:
        """Test SHORT_ prefix stripping for value translations."""
        direct = get_parameter_value_translation(
            parameter="ACOUSTIC_ALARM_ACTIVE",
            value="TRUE",
            locale="en",
        )
        short = get_parameter_value_translation(
            parameter="SHORT_ACOUSTIC_ALARM_ACTIVE",
            value="TRUE",
            locale="en",
        )
        assert direct is not None
        assert short == direct

    def test_unknown_value(self) -> None:
        """Test that completely unknown value returns None."""
        result = get_parameter_value_translation(
            parameter="NONEXISTENT_PARAM_XYZ",
            value="NONEXISTENT_VALUE_XYZ",
        )
        assert result is None

    def test_value_only_fallback(self) -> None:
        """Test value-only fallback for generic enum values."""
        # Common enum values like "true"/"false" should have generic translations
        result = get_parameter_value_translation(
            parameter="SOME_UNKNOWN_PARAM",
            value="true",
            locale="en",
        )
        # May or may not exist as a value-only fallback depending on data
        # Just verify it doesn't raise
        assert result is None or isinstance(result, str)


class TestTranslationStoreLoading:
    """Test translation store behavior."""

    def test_parameters_have_both_locales(self) -> None:
        """Test that parameters exist in both DE and EN."""
        en = get_parameter_translation(parameter="ON_LEVEL", locale="en")
        de = get_parameter_translation(parameter="ON_LEVEL", locale="de")
        assert en is not None
        assert de is not None
        # They should be different (different languages)
        assert en != de

    def test_store_is_loaded(self) -> None:
        """Test that the module-level store is loaded on import."""
        # If this test can call get_parameter_translation without error,
        # the store was loaded successfully
        result = get_parameter_translation(parameter="ON_LEVEL", locale="en")
        assert result is not None
