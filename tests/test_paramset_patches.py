# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for the paramset description patching system."""

from __future__ import annotations

from aiohomematic.const import Parameter, ParameterData, ParameterType, ParamsetKey
from aiohomematic.store import PARAMSET_PATCHES, ParamsetPatchMatcher


def test_hm_cc_vg_1_set_temperature_bounds_patched() -> None:
    """The HM-CC-VG-1 SET_TEMPERATURE MIN/MAX bounds are corrected."""
    matcher = ParamsetPatchMatcher(device_type="HM-CC-VG-1")
    assert matcher.has_patches is True

    paramset: dict[str, ParameterData] = {
        Parameter.SET_TEMPERATURE: ParameterData(TYPE=ParameterType.FLOAT, MIN=0.0, MAX=0.0, DEFAULT=0.0)
    }
    patched = matcher.apply_patches(
        channel_address="VCU0000001:1",
        paramset_key=ParamsetKey.VALUES,
        paramset_description=paramset,
    )
    assert patched[Parameter.SET_TEMPERATURE]["MIN"] == 4.5
    assert patched[Parameter.SET_TEMPERATURE]["MAX"] == 30.5


def test_hmip_fwi_code_id_max_patched() -> None:
    """
    The HmIP-FWI CODE_ID MAX is widened to the device idle value 31 (#3238).

    The CCU declares MAX=21, but the fingerprint reader reports CODE_ID=31 in
    idle/standby. The too-low MAX dropped the idle value at the HA number
    entity, so number.*_code_id never returned to 31.
    """
    matcher = ParamsetPatchMatcher(device_type="HmIP-FWI")
    assert matcher.has_patches is True

    paramset: dict[str, ParameterData] = {
        Parameter.CODE_ID: ParameterData(TYPE=ParameterType.INTEGER, MIN=1, MAX=21, DEFAULT=1)
    }
    patched = matcher.apply_patches(
        channel_address="VCU4820995:0",
        paramset_key=ParamsetKey.VALUES,
        paramset_description=paramset,
    )
    assert patched[Parameter.CODE_ID]["MAX"] == 31
    # MIN stays untouched.
    assert patched[Parameter.CODE_ID]["MIN"] == 1


def test_hmip_fwi_code_id_patch_is_registered() -> None:
    """The HmIP-FWI CODE_ID patch is present in the central registry."""
    assert any(
        p.device_type == "HmIP-FWI"
        and p.parameter == Parameter.CODE_ID
        and p.channel_no == 0
        and p.paramset_key == ParamsetKey.VALUES
        and p.patches.get("MAX") == 31
        for p in PARAMSET_PATCHES
    )
