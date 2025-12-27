# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
from __future__ import annotations

import asyncio

import pytest

from aiohomematic import i18n
from aiohomematic.central import CentralConfig


class TestI18nBasicTranslation:
    """Test basic translation functionality."""

    def test_tr_fallback_to_base_catalog(self) -> None:
        """Test fallback to base catalog when key not in active locale."""
        i18n.set_locale(locale="de")
        # Use a key that likely only exists in base
        text = i18n.tr(key="some.nonexistent.key")
        # Should return the key itself as last fallback
        assert text == "some.nonexistent.key"

    def test_tr_german_locale(self) -> None:
        """Test German locale translation."""
        i18n.set_locale(locale="de")
        text = i18n.tr(key="exception.create_central.failed", reason="Fehler")
        assert text == "Zentrale konnte nicht erstellt werden: Fehler"

    def test_tr_key_not_in_any_catalog(self) -> None:
        """Test that unknown keys return the key itself."""
        i18n.set_locale(locale="en")
        key = "totally.unknown.translation.key"
        text = i18n.tr(key=key)
        assert text == key

    def test_tr_uses_base_strings_when_locale_missing_and_formats(self) -> None:
        """Ensure a non-existing locale falls back to base strings.json."""
        i18n.set_locale(locale="xx")
        text = i18n.tr(key="exception.config.invalid", failures="A, B")
        assert text == "Invalid configuration: A, B"

    def test_tr_without_formatting_args(self) -> None:
        """Test translation without formatting arguments."""
        i18n.set_locale(locale="en")
        # Use a key that exists and has no placeholders
        text = i18n.tr(key="exception.config.check.host.invalid")
        assert isinstance(text, str)
        assert len(text) > 0


class TestI18nLocaleManagement:
    """Test locale setting and getting."""

    def test_catalog_caching(self) -> None:
        """Test that catalogs are cached and reused."""
        # Set locale twice to test cache hit path
        i18n.set_locale(locale="de")
        i18n.set_locale(locale="de")
        text = i18n.tr(key="exception.create_central.failed", reason="Test")
        assert "Test" in text

    def test_get_locale(self) -> None:
        """Test getting the current locale."""
        i18n.set_locale(locale="de")
        assert i18n.get_locale() == "de"

        i18n.set_locale(locale="en")
        assert i18n.get_locale() == "en"

    def test_set_locale_empty_string_defaults_to_en(self) -> None:
        """Test that empty string defaults to 'en'."""
        i18n.set_locale(locale="")
        assert i18n.get_locale() == "en"

    def test_set_locale_none_defaults_to_en(self) -> None:
        """Test that set_locale(None) defaults to 'en'."""
        i18n.set_locale(locale=None)
        assert i18n.get_locale() == "en"

    def test_set_locale_updates_active_catalog(self) -> None:
        """Test that set_locale updates the active catalog immediately."""
        i18n.set_locale(locale="en")
        text_en = i18n.tr(key="exception.create_central.failed", reason="Error")

        i18n.set_locale(locale="de")
        text_de = i18n.tr(key="exception.create_central.failed", reason="Fehler")

        # Should be different languages
        assert text_en != text_de

    def test_set_locale_whitespace_defaults_to_en(self) -> None:
        """Test that whitespace-only string defaults to 'en'."""
        i18n.set_locale(locale="   ")
        assert i18n.get_locale() == "en"


class TestI18nAsyncPreloading:
    """Test async locale preloading."""

    @pytest.mark.asyncio
    async def test_preload_locale_async(self) -> None:
        """Test asynchronous locale preloading."""
        await i18n.preload_locale(locale="de")
        # After preload, the locale should be in cache
        i18n.set_locale(locale="de")
        text = i18n.tr(key="exception.create_central.failed", reason="Test")
        assert "Test" in text

    @pytest.mark.asyncio
    async def test_preload_locale_none_defaults_to_en(self) -> None:
        """Test that preload with None defaults to 'en'."""
        await i18n.preload_locale(locale=None)
        # Should preload 'en'
        i18n.set_locale(locale="en")
        text = i18n.tr(key="exception.config.invalid", failures="test")
        assert "test" in text

    @pytest.mark.asyncio
    async def test_schedule_preload_locale_with_running_loop(self) -> None:
        """Test schedule_preload_locale when loop is running."""
        task = i18n.schedule_preload_locale(locale="de")
        assert task is not None
        assert isinstance(task, asyncio.Task)
        await task  # Wait for completion

        # Verify it was loaded
        i18n.set_locale(locale="de")
        text = i18n.tr(key="exception.create_central.failed", reason="Test")
        assert "Zentrale" in text

    def test_schedule_preload_locale_without_running_loop(self) -> None:
        """Test schedule_preload_locale when no loop is running."""
        # This should load synchronously and return None
        result = i18n.schedule_preload_locale(locale="en")
        assert result is None


class TestI18nLocalizedExceptions:
    """Test localized exception messages."""

    @pytest.mark.parametrize(
        ("locale", "expected_substr"),
        [
            ("de", "Ungültige Konfiguration"),
            ("en", "Invalid configuration"),
        ],
    )
    @pytest.mark.asyncio
    async def test_localized_exception_message_from_check_config(self, locale: str, expected_substr: str) -> None:
        """Test that exception messages are properly localized."""
        i18n.set_locale(locale=locale)
        cfg = self._make_invalid_config()
        with pytest.raises(Exception) as excinfo:
            cfg.check_config()
        msg = str(excinfo.value)
        assert expected_substr in msg
        # It should include at least one original failure detail joined in
        # Build expected localized failure messages for current locale
        expected_failures = (
            i18n.tr(key="exception.config.check.host.invalid"),
            i18n.tr(key="exception.config.check.username.empty"),
            i18n.tr(key="exception.config.check.password.required"),
            i18n.tr(key="exception.config.check.password.invalid"),
        )
        assert any(substr in msg for substr in expected_failures)

    def _make_invalid_config(self) -> CentralConfig:
        """Create an invalid config for testing."""
        return CentralConfig(
            central_id="c1",
            host="invalid host??",  # invalid
            interface_configs=frozenset(),
            name="n",
            password="",  # invalid
            username="",  # invalid
        )
