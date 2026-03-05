# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract tests for field visibility in profile configurations.

STABILITY GUARANTEE
-------------------
These tests ensure that the unified field visibility model (visible/bare)
correctly represents visibility intentions for all profile configurations.

The contract ensures that:
1. visible() fields resolve to is_visible=True
2. Bare Parameter fields resolve to is_visible=None
3. All profile configs have valid field entries
4. resolve_field_value() correctly extracts parameter and visibility
"""

from __future__ import annotations

from aiohomematic.const import Parameter
from aiohomematic.model.custom import PROFILE_CONFIGS, FieldMapping, resolve_field_value, visible


class TestFieldMappingHelpers:
    """Test visible() helper function."""

    def test_visible_creates_field_mapping_with_true(self) -> None:
        """Test that visible() creates a FieldMapping with is_visible=True."""
        fm = visible(parameter=Parameter.STATE)
        assert isinstance(fm, FieldMapping)
        assert fm.parameter == Parameter.STATE
        assert fm.is_visible is True


class TestResolveFieldValue:
    """Test resolve_field_value() extraction."""

    def test_bare_parameter_resolves_to_none_visibility(self) -> None:
        """Test that a bare Parameter resolves to (parameter, None)."""
        param, vis = resolve_field_value(field_value=Parameter.STATE)
        assert param == Parameter.STATE
        assert vis is None

    def test_visible_resolves_to_true_visibility(self) -> None:
        """Test that visible() resolves to (parameter, True)."""
        param, vis = resolve_field_value(field_value=visible(parameter=Parameter.LEVEL))
        assert param == Parameter.LEVEL
        assert vis is True


class TestProfileConfigsVisibility:
    """Test that all profile configs have valid field entries."""

    def test_all_profile_fields_are_valid(self) -> None:
        """Test that every field value in every profile config is a valid FieldValue."""
        for profile_type, config in PROFILE_CONFIGS.items():
            group = config.channel_group
            # Check fields dict
            for field, fv in group.fields.items():
                param, vis = resolve_field_value(field_value=fv)
                assert isinstance(param, Parameter), f"{profile_type}: fields[{field}] has invalid parameter {param}"
                assert vis in (None, True, False), f"{profile_type}: fields[{field}] has invalid visibility {vis}"

            # Check channel_fields dict
            for ch_no, ch_fields in group.channel_fields.items():
                for field, fv in ch_fields.items():
                    param, vis = resolve_field_value(field_value=fv)
                    assert isinstance(param, Parameter), (
                        f"{profile_type}: channel_fields[{ch_no}][{field}] has invalid parameter"
                    )

            # Check fixed_channel_fields dict
            for ch_no, ch_fields in group.fixed_channel_fields.items():
                for field, fv in ch_fields.items():
                    param, vis = resolve_field_value(field_value=fv)
                    assert isinstance(param, Parameter), (
                        f"{profile_type}: fixed_channel_fields[{ch_no}][{field}] has invalid parameter"
                    )

    def test_visible_fields_have_true_visibility(self) -> None:
        """Test that all FieldMapping entries with is_visible=True use visible()."""
        for profile_type, config in PROFILE_CONFIGS.items():
            group = config.channel_group
            for field, fv in group.fields.items():
                if isinstance(fv, FieldMapping) and fv.is_visible is True:
                    param, vis = resolve_field_value(field_value=fv)
                    assert vis is True, f"{profile_type}: fields[{field}] expected visible but got {vis}"
