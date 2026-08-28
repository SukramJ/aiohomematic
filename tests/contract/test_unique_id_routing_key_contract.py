# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract tests for the unique_id routing key.

STABILITY GUARANTEE
-------------------
The ``unique_id`` is the routing key for every Home Assistant value-change
subscription. Several implementations rebuild it independently -- ``aiohomematic``,
``py-openccu-loom-client`` and the Go ``openccu-loom`` daemon -- and they MUST produce
bit-identical output, otherwise events route to the wrong entity (or to no entity) and
Home Assistant loses entity history on cutover.

The cases below are the cross-implementation golden set. Any change to them re-keys
existing Home Assistant entities and therefore requires a coordinated release across
every implementation plus a registry migration in the integration.

Rules pinned here:
1. ``:`` and ``-`` fold to ``_`` in the *address*; a ``-`` inside a *parameter*
   survives (hub slugs).
2. An optional parameter is appended, an optional prefix is prepended, and the
   central id is prepended last.
3. The parameter-level key is namespaced by the central for every address family
   that repeats verbatim across CCUs: the hub pseudo-addresses, ``INT000*``,
   the virtual-remote roots, and CUxD (``CUX*``).
4. The channel-level key is namespaced by the central for the virtual-remote roots
   **only** -- not for hub, internal or CUxD addresses.
5. The whole result is lowercased.

See ADR-0018 for architectural context.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from aiohomematic.model.support import generate_channel_unique_id, generate_unique_id

# (central_id, address, parameter, prefix, expected)
UNIQUE_ID_CASES: tuple[tuple[str, str, str | None, str | None, str], ...] = (
    # Plain device addresses are not namespaced.
    ("1234", "VCU1234567:1", "STATE", None, "vcu1234567_1_state"),
    ("1234", "VCU1234567:1", None, None, "vcu1234567_1"),
    ("1234", "VCU1234567:0", None, None, "vcu1234567_0"),
    ("1234", "VCU1234567:3", None, None, "vcu1234567_3"),
    ("1234", "ABC-DEF:2", "LEVEL", None, "abc_def_2_level"),
    # Internal addresses are namespaced.
    ("1234", "INT0001234:1", "LEVEL", None, "1234_int0001234_1_level"),
    ("1234", "INT0001234:2", "LEVEL", None, "1234_int0001234_2_level"),
    ("1234", "INT0001234:1", "X", "event", "1234_event_int0001234_1_x"),
    # Hub pseudo-addresses are namespaced.
    ("ccu3", "hub", "STATUS", None, "ccu3_hub_status"),
    ("ccu3", "install_mode", "ACTIVE", None, "ccu3_install_mode_active"),
    ("ccu3", "program", "RUN", None, "ccu3_program_run"),
    ("ccu3", "program", "my_prog", None, "ccu3_program_my_prog"),
    ("ccu3", "sysvar", "VALUE", None, "ccu3_sysvar_value"),
    ("ccu3", "sysvar", "my_var", None, "ccu3_sysvar_my_var"),
    # A "-" inside the parameter survives the fold.
    ("ccu3", "sysvar", "aussen-temperatur", None, "ccu3_sysvar_aussen-temperatur"),
    # Virtual remotes are namespaced.
    ("ccu3", "BidCoS-RF:1", "PRESS_SHORT", None, "ccu3_bidcos_rf_1_press_short"),
    ("ccu3", "HmIP-RCV-1:2", "PRESS_LONG", None, "ccu3_hmip_rcv_1_2_press_long"),
    # Prefixes.
    ("1234", "VCU1234567:1", "PRESS_SHORT", "event", "event_vcu1234567_1_press_short"),
    ("1234", "VCU1234567:0", "BUTTON", "btn", "btn_vcu1234567_0_button"),
    ("1234", "VCU1234567", "WEEK_PROFILE", "week_profile", "week_profile_vcu1234567_week_profile"),
    (
        "1234",
        "VCU1234567",
        "SCHEDULE_CHANNEL_LOCK_1_1",
        "schedule_channel_switch",
        "schedule_channel_switch_vcu1234567_schedule_channel_lock_1_1",
    ),
    # CUxD hands out the same synthetic addresses on every CCU, so it is namespaced.
    ("1234", "CUX2801001:1", "STATE", None, "1234_cux2801001_1_state"),
    ("ccu3", "CUX0300001:2", "LEVEL", None, "ccu3_cux0300001_2_level"),
    ("1234", "CUX2801001:1", "STATE", "calculated", "1234_calculated_cux2801001_1_state"),
    ("1234", "CUX2801001", None, None, "1234_cux2801001"),
)

# (central_id, address, expected)
CHANNEL_UNIQUE_ID_CASES: tuple[tuple[str, str, str], ...] = (
    ("ccu3", "VCU1234567:1", "vcu1234567_1"),
    ("ccu3", "VCU1234567:0", "vcu1234567_0"),
    ("ccu3", "VCU1234567", "vcu1234567"),
    ("ccu3", "ABC-DEF:2", "abc_def_2"),
    # Virtual remotes are the only family namespaced at channel level.
    ("ccu3", "BidCoS-RF:1", "ccu3_bidcos_rf_1"),
    ("ccu3", "HmIP-RCV-1:2", "ccu3_hmip_rcv_1_2"),
    # Hub, internal and CUxD channel ids stay unscoped.
    ("ccu3", "INT0001234:1", "int0001234_1"),
    ("1234", "CUX2801001:1", "cux2801001_1"),
    ("1234", "CUX2801001", "cux2801001"),
)


def _config_provider(*, central_id: str) -> SimpleNamespace:
    """Return a minimal config provider carrying only the central id."""
    return SimpleNamespace(config=SimpleNamespace(central_id=central_id))


# =============================================================================
# Contract: parameter-level routing key
# =============================================================================


class TestUniqueIdRoutingKeyContract:
    """Contract: generate_unique_id matches the cross-implementation golden set."""

    @pytest.mark.parametrize(
        ("central_id", "address", "parameter", "prefix", "expected"),
        UNIQUE_ID_CASES,
        ids=[f"{case[1]}|{case[2]}|{case[3]}" for case in UNIQUE_ID_CASES],
    )
    def test_unique_id_matches_golden(
        self, central_id: str, address: str, parameter: str | None, prefix: str | None, expected: str
    ) -> None:
        """Contract: The parameter-level routing key is byte-identical to the golden set."""
        assert (
            generate_unique_id(
                config_provider=_config_provider(central_id=central_id),  # type: ignore[arg-type]
                address=address,
                parameter=parameter,
                prefix=prefix,
            )
            == expected
        )


# =============================================================================
# Contract: channel-level routing key
# =============================================================================


class TestChannelUniqueIdRoutingKeyContract:
    """Contract: generate_channel_unique_id matches the cross-implementation golden set."""

    @pytest.mark.parametrize(
        ("central_id", "address", "expected"),
        CHANNEL_UNIQUE_ID_CASES,
        ids=[case[1] for case in CHANNEL_UNIQUE_ID_CASES],
    )
    def test_channel_unique_id_matches_golden(self, central_id: str, address: str, expected: str) -> None:
        """Contract: The channel-level routing key is byte-identical to the golden set."""
        assert (
            generate_channel_unique_id(
                config_provider=_config_provider(central_id=central_id),  # type: ignore[arg-type]
                address=address,
            )
            == expected
        )


# =============================================================================
# Contract: central scoping families
# =============================================================================


class TestCentralScopingFamiliesContract:
    """Contract: Exactly the repeating address families are namespaced by the central."""

    @pytest.mark.parametrize("address", ["hub", "install_mode", "program", "sysvar", "INT0001234:1", "CUX2801001:1"])
    def test_only_virtual_remotes_are_scoped_at_channel_level(self, address: str) -> None:
        """Contract: Channel-level keys carry the central id for virtual remotes only."""
        channel_unique_id = generate_channel_unique_id(
            config_provider=_config_provider(central_id="ccu3"),  # type: ignore[arg-type]
            address=address,
        )
        assert not channel_unique_id.startswith("ccu3_"), address

    @pytest.mark.parametrize(
        "address",
        ["hub", "install_mode", "program", "sysvar", "INT0001234:1", "BidCoS-RF:1", "HmIP-RCV-1:2", "CUX2801001:1"],
    )
    def test_scoped_families_carry_the_central_id(self, address: str) -> None:
        """Contract: Repeating address families carry the central id at parameter level."""
        unique_id = generate_unique_id(
            config_provider=_config_provider(central_id="ccu3"),  # type: ignore[arg-type]
            address=address,
            parameter="X",
        )
        assert unique_id.startswith("ccu3_"), address

    @pytest.mark.parametrize("address", ["VCU1234567:1", "ABC-DEF:2", "OEQ1860891:1"])
    def test_unscoped_families_do_not_carry_the_central_id(self, address: str) -> None:
        """Contract: Real device addresses are unique per CCU and stay unscoped."""
        unique_id = generate_unique_id(
            config_provider=_config_provider(central_id="ccu3"),  # type: ignore[arg-type]
            address=address,
            parameter="X",
        )
        assert not unique_id.startswith("ccu3_"), address
