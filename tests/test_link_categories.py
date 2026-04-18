# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Test get_link_source_categories / get_link_target_categories mappers."""

from __future__ import annotations

import pytest

from aiohomematic.const import DataPointCategory, get_link_source_categories, get_link_target_categories


class TestGetLinkSourceCategories:
    """Tests for get_link_source_categories."""

    def test_climate_channel_with_other_role(self) -> None:
        """A climate channel still maps non-climate roles to their category."""
        result = set(get_link_source_categories(source_roles=("SWITCH",), channel_type_name="CLIMATE_TRANSMITTER"))
        assert result == {DataPointCategory.CLIMATE, DataPointCategory.SWITCH}

    def test_climate_role_substring(self) -> None:
        """A role containing CLIMATE counts as CLIMATE."""
        result = get_link_source_categories(source_roles=("CLIMATE_CONTROL",), channel_type_name="UNKNOWN")
        assert result == (DataPointCategory.CLIMATE,)

    def test_climate_transceiver_channel_name(self) -> None:
        """A CLIMATE_TRANSCEIVER channel counts as CLIMATE."""
        result = get_link_source_categories(source_roles=(), channel_type_name="HEATING_CLIMATECONTROL_TRANSCEIVER")
        assert result == (DataPointCategory.CLIMATE,)

    def test_climate_transmitter_channel_name(self) -> None:
        """A CLIMATE_TRANSMITTER channel always counts as CLIMATE."""
        result = get_link_source_categories(source_roles=(), channel_type_name="CLIMATE_TRANSMITTER")
        assert result == (DataPointCategory.CLIMATE,)

    def test_conditional_switch_roles(self) -> None:
        """CONDITIONAL_SWITCH variants map to SWITCH."""
        for role in ("CONDITIONAL_SWITCH", "ALARM_MODE_CONDITIONAL_SWITCH"):
            result = get_link_source_categories(source_roles=(role,), channel_type_name="X")
            assert result == (DataPointCategory.SWITCH,), role

    def test_empty_inputs(self) -> None:
        """Return empty tuple when no roles and no climate channel name."""
        assert get_link_source_categories(source_roles=(), channel_type_name="SWITCH") == ()

    def test_keymatic_role(self) -> None:
        """KEYMATIC maps to LOCK."""
        result = get_link_source_categories(source_roles=("KEYMATIC",), channel_type_name="KEYMATIC")
        assert result == (DataPointCategory.LOCK,)

    def test_level_role(self) -> None:
        """LEVEL maps to LIGHT (dimmer / blind)."""
        result = get_link_source_categories(source_roles=("LEVEL",), channel_type_name="DIMMER")
        assert result == (DataPointCategory.LIGHT,)

    def test_multiple_roles_combined(self) -> None:
        """Multiple roles produce a union of categories."""
        result = set(get_link_source_categories(source_roles=("SWITCH", "REMOTE_CONTROL"), channel_type_name="X"))
        assert result == {DataPointCategory.SWITCH, DataPointCategory.BUTTON}

    def test_remote_control_role(self) -> None:
        """REMOTE_CONTROL maps to BUTTON (HmIP-RCV-50 KEY_TRANSCEIVER channels)."""
        result = get_link_source_categories(source_roles=("REMOTE_CONTROL",), channel_type_name="KEY_TRANSCEIVER")
        assert result == (DataPointCategory.BUTTON,)

    def test_smoke_detector_roles(self) -> None:
        """Smoke detector team roles map to BINARY_SENSOR."""
        for role in ("SMOKE_DETECTOR_TEAM", "SMOKE_DETECTOR_TEAM_V2"):
            result = get_link_source_categories(source_roles=(role,), channel_type_name="X")
            assert result == (DataPointCategory.BINARY_SENSOR,), role

    def test_switch_role(self) -> None:
        """SWITCH maps to SWITCH."""
        result = get_link_source_categories(source_roles=("SWITCH",), channel_type_name="SWITCH")
        assert result == (DataPointCategory.SWITCH,)

    def test_unknown_role_returns_empty(self) -> None:
        """An unknown role is silently skipped (no entry added)."""
        assert get_link_source_categories(source_roles=("TOTALLY_UNKNOWN_ROLE_XYZ",), channel_type_name="X") == ()

    def test_weather_roles(self) -> None:
        """Weather roles map to SENSOR."""
        for role in ("WEATHER_T", "WEATHER_TH", "WEATHER_THP", "WEATHER_CS"):
            result = get_link_source_categories(source_roles=(role,), channel_type_name="X")
            assert result == (DataPointCategory.SENSOR,), role

    def test_window_switch_roles(self) -> None:
        """All WINDOW_SWITCH variants map to BINARY_SENSOR."""
        for role in ("WINDOW_SWITCH", "WINDOW_SWITCH_RECEIVER", "WINDOW_SWITCH_RECEIVER_V2"):
            result = get_link_source_categories(source_roles=(role,), channel_type_name="X")
            assert result == (DataPointCategory.BINARY_SENSOR,), role

    def test_winmatic_role(self) -> None:
        """WINMATIC maps to COVER."""
        result = get_link_source_categories(source_roles=("WINMATIC",), channel_type_name="WINMATIC")
        assert result == (DataPointCategory.COVER,)


class TestGetLinkTargetCategories:
    """Tests for get_link_target_categories."""

    def test_climate_receiver_channel_name(self) -> None:
        """A CLIMATE_RECEIVER channel always counts as CLIMATE."""
        result = get_link_target_categories(target_roles=(), channel_type_name="CLIMATE_RECEIVER")
        assert result == (DataPointCategory.CLIMATE,)

    def test_climate_role_target(self) -> None:
        """CLIMATE_CONTROL target maps to CLIMATE."""
        result = get_link_target_categories(target_roles=("CLIMATE_CONTROL",), channel_type_name="X")
        assert result == (DataPointCategory.CLIMATE,)

    def test_climate_via_target_role_substring(self) -> None:
        """SWITCH target role causes CLIMATE classification (legacy behavior)."""
        result = set(get_link_target_categories(target_roles=("SWITCH",), channel_type_name="X"))
        # Legacy behavior: SWITCH/LEVEL targets imply CLIMATE *and* are now also
        # reported as their own category.
        assert DataPointCategory.CLIMATE in result
        assert DataPointCategory.SWITCH in result

    def test_empty_inputs(self) -> None:
        """Return empty tuple when no roles and no climate channel name."""
        assert get_link_target_categories(target_roles=(), channel_type_name="SWITCH") == ()

    def test_keymatic_target(self) -> None:
        """KEYMATIC target maps to LOCK."""
        assert get_link_target_categories(target_roles=("KEYMATIC",), channel_type_name="X") == (
            DataPointCategory.LOCK,
        )

    def test_remote_control_target(self) -> None:
        """REMOTE_CONTROL target maps to BUTTON only."""
        result = get_link_target_categories(target_roles=("REMOTE_CONTROL",), channel_type_name="KEY_TRANSCEIVER")
        assert result == (DataPointCategory.BUTTON,)

    def test_unknown_role_returns_empty(self) -> None:
        """Unknown target role yields no category."""
        assert get_link_target_categories(target_roles=("UNKNOWN_TARGET_ROLE",), channel_type_name="X") == ()

    def test_winmatic_target(self) -> None:
        """WINMATIC target maps to COVER."""
        assert get_link_target_categories(target_roles=("WINMATIC",), channel_type_name="X") == (
            DataPointCategory.COVER,
        )


class TestRcv50RegressionIssue52:
    """
    Regression test for HmIP-RCV-50 not appearing in linkable channels.

    See https://github.com/SukramJ/homematicip-local-frontend/discussions/52
    """

    def test_rcv50_key_transceiver_is_link_capable(self) -> None:
        """HmIP-RCV-50 KEY_TRANSCEIVER channels must produce a non-empty source category list."""
        result = get_link_source_categories(source_roles=("REMOTE_CONTROL",), channel_type_name="KEY_TRANSCEIVER")
        assert result, (
            "REMOTE_CONTROL must yield a non-empty category tuple, otherwise "
            "LinkCoordinator.get_linkable_channels filters HmIP-RCV-50 out."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
