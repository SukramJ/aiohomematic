from __future__ import annotations

import pytest

from aiohomematic import i18n
from aiohomematic.central import CentralConfig


def test_tr_uses_base_strings_when_locale_missing_and_formats() -> None:
    # Ensure a non-existing locale falls back to base strings.json
    i18n.set_locale("xx")
    text = i18n.tr("exception.config.invalid", failures="A, B")
    assert text == "Invalid configuration: A, B"


def test_tr_german_locale() -> None:
    i18n.set_locale("de")
    text = i18n.tr("exception.create_central.failed", reason="Fehler")
    assert text == "Zentrale konnte nicht erstellt werden: Fehler"


def _make_invalid_config() -> CentralConfig:
    return CentralConfig(
        central_id="c1",
        host="invalid host??",  # invalid
        interface_configs=frozenset(),
        name="n",
        password="",  # invalid
        username="",  # invalid
    )


@pytest.mark.parametrize(
    ("locale", "expected_substr"),
    [
        ("de", "Ungültige Konfiguration"),
        ("en", "Invalid configuration"),
    ],
)
@pytest.mark.asyncio
async def test_localized_exception_message_from_check_config(locale: str, expected_substr: str) -> None:
    i18n.set_locale(locale)
    cfg = _make_invalid_config()
    with pytest.raises(Exception) as excinfo:
        cfg.check_config()
    msg = str(excinfo.value)
    assert expected_substr in msg
    # It should include at least one original failure detail joined in
    # Build expected localized failure messages for current locale
    expected_failures = (
        i18n.tr("exception.config.check.host.invalid"),
        i18n.tr("exception.config.check.username.empty"),
        i18n.tr("exception.config.check.password.required"),
        i18n.tr("exception.config.check.password.invalid"),
    )
    assert any(substr in msg for substr in expected_failures)
