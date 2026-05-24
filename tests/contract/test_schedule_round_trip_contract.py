# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract tests for SimpleSchedule round-trip across all supported domains.

STABILITY GUARANTEE
-------------------
A schedule that ``DefaultWeekProfile.convert_raw_to_dict_schedule`` produces for
a given device domain must always pass
``SimpleSchedule.model_validate(..., context={SCHEDULE_DOMAIN_CONTEXT_KEY: domain})``.

This guards against the read/write asymmetry where the CCU MASTER paramset can
include fields that don't apply to the device category (e.g. ``RAMP_TIME_BASE``
on HmIP-PSMCO, a switch). Without the contract, get_schedule populates the
field and the subsequent set_schedule fails domain validation, breaking the
HA schedule editor for affected devices.

See ``aiohomematic/model/schedule_models.py:_DOMAIN_UNSUPPORTED_FIELDS``.
"""

from __future__ import annotations

import pytest

from aiohomematic.const import DataPointCategory
from aiohomematic.model.schedule_models import SCHEDULE_DOMAIN_CONTEXT_KEY, SimpleSchedule
from aiohomematic.model.week_profile import DefaultWeekProfile


def _switch_raw_with_ramp_time() -> dict[str, object]:
    """Raw paramset emulating HmIP-PSMCO: SWITCH with RAMP_TIME_* in MASTER."""
    return {
        # Group 1: active entry, level=1.0 (ON), 5s ramp would be invalid for a switch
        "01_WP_WEEKDAY": 4,  # TUESDAY
        "01_WP_FIXED_HOUR": 7,
        "01_WP_FIXED_MINUTE": 30,
        "01_WP_CONDITION": 0,
        "01_WP_ASTRO_TYPE": 0,
        "01_WP_ASTRO_OFFSET": 0,
        "01_WP_TARGET_CHANNELS": 1,
        "01_WP_LEVEL": 1.0,
        "01_WP_DURATION_BASE": 0,
        "01_WP_DURATION_FACTOR": 0,
        "01_WP_RAMP_TIME_BASE": 1,  # SEC_1
        "01_WP_RAMP_TIME_FACTOR": 5,
        # Group 2: active entry, level=0.0 (OFF), with non-zero ramp_time
        "02_WP_WEEKDAY": 4,
        "02_WP_FIXED_HOUR": 22,
        "02_WP_FIXED_MINUTE": 0,
        "02_WP_CONDITION": 0,
        "02_WP_ASTRO_TYPE": 0,
        "02_WP_ASTRO_OFFSET": 0,
        "02_WP_TARGET_CHANNELS": 1,
        "02_WP_LEVEL": 0.0,
        "02_WP_DURATION_BASE": 0,
        "02_WP_DURATION_FACTOR": 0,
        "02_WP_RAMP_TIME_BASE": 1,
        "02_WP_RAMP_TIME_FACTOR": 10,
    }


def _cover_raw_with_ramp_time_and_duration() -> dict[str, object]:
    """Raw paramset emulating a cover with stray RAMP_TIME and DURATION fields."""
    return {
        "01_WP_WEEKDAY": 2,  # MONDAY
        "01_WP_FIXED_HOUR": 8,
        "01_WP_FIXED_MINUTE": 0,
        "01_WP_CONDITION": 0,
        "01_WP_ASTRO_TYPE": 0,
        "01_WP_ASTRO_OFFSET": 0,
        "01_WP_TARGET_CHANNELS": 1,
        "01_WP_LEVEL": 1.0,
        "01_WP_LEVEL_2": 0.5,  # allowed for cover (slat)
        "01_WP_DURATION_BASE": 1,  # SEC_1
        "01_WP_DURATION_FACTOR": 30,  # would violate cover validator
        "01_WP_RAMP_TIME_BASE": 1,
        "01_WP_RAMP_TIME_FACTOR": 5,  # would violate cover validator
    }


def _valve_raw_with_ramp_time_and_level_2() -> dict[str, object]:
    """Raw paramset emulating a valve with stray RAMP_TIME and LEVEL_2 fields."""
    return {
        "01_WP_WEEKDAY": 2,
        "01_WP_FIXED_HOUR": 6,
        "01_WP_FIXED_MINUTE": 0,
        "01_WP_CONDITION": 0,
        "01_WP_ASTRO_TYPE": 0,
        "01_WP_ASTRO_OFFSET": 0,
        "01_WP_TARGET_CHANNELS": 1,
        "01_WP_LEVEL": 0.75,
        "01_WP_LEVEL_2": 0.5,
        "01_WP_RAMP_TIME_BASE": 1,
        "01_WP_RAMP_TIME_FACTOR": 5,
    }


def _light_raw_with_level_2() -> dict[str, object]:
    """Raw paramset emulating a dimmer (light) with stray LEVEL_2 field."""
    return {
        "01_WP_WEEKDAY": 2,
        "01_WP_FIXED_HOUR": 19,
        "01_WP_FIXED_MINUTE": 0,
        "01_WP_CONDITION": 0,
        "01_WP_ASTRO_TYPE": 0,
        "01_WP_ASTRO_OFFSET": 0,
        "01_WP_TARGET_CHANNELS": 1,
        "01_WP_LEVEL": 0.6,
        "01_WP_LEVEL_2": 0.5,  # not valid for a light
        "01_WP_RAMP_TIME_BASE": 1,
        "01_WP_RAMP_TIME_FACTOR": 5,  # allowed for a light
    }


class TestDomainStripsUnsupportedFieldsOnRead:
    """Contract: convert_raw_to_dict_schedule must null out fields the domain doesn't support."""

    def test_cover_drops_ramp_time_and_duration_keeps_level_2(self) -> None:
        raw = _cover_raw_with_ramp_time_and_duration()
        result = DefaultWeekProfile.convert_raw_to_dict_schedule(raw_schedule=raw, domain=DataPointCategory.COVER)
        entry = result.entries[1]
        assert entry.ramp_time is None
        assert entry.duration is None
        # Cover keeps level_2 (slat position)
        assert entry.level_2 == 0.5

    def test_light_drops_level_2_keeps_ramp_time(self) -> None:
        raw = _light_raw_with_level_2()
        result = DefaultWeekProfile.convert_raw_to_dict_schedule(raw_schedule=raw, domain=DataPointCategory.LIGHT)
        entry = result.entries[1]
        assert entry.level_2 is None
        # Lights are dimmers and may use ramp_time
        assert entry.ramp_time is not None

    def test_switch_drops_ramp_time_and_level_2(self) -> None:
        raw = _switch_raw_with_ramp_time()
        result = DefaultWeekProfile.convert_raw_to_dict_schedule(raw_schedule=raw, domain=DataPointCategory.SWITCH)
        assert set(result.entries) == {1, 2}
        for entry in result.entries.values():
            assert entry.ramp_time is None
            assert entry.level_2 is None

    def test_valve_drops_ramp_time_and_level_2(self) -> None:
        raw = _valve_raw_with_ramp_time_and_level_2()
        result = DefaultWeekProfile.convert_raw_to_dict_schedule(raw_schedule=raw, domain=DataPointCategory.VALVE)
        entry = result.entries[1]
        assert entry.ramp_time is None
        assert entry.level_2 is None


class TestDomainContextRoundTripDoesNotRaise:
    """Contract: read + re-validate-with-domain-context must never raise."""

    @pytest.mark.parametrize(
        ("domain", "raw_factory"),
        [
            (DataPointCategory.SWITCH, _switch_raw_with_ramp_time),
            (DataPointCategory.COVER, _cover_raw_with_ramp_time_and_duration),
            (DataPointCategory.VALVE, _valve_raw_with_ramp_time_and_level_2),
            (DataPointCategory.LIGHT, _light_raw_with_level_2),
        ],
    )
    def test_full_raw_simple_raw_simple_round_trip(self, domain: DataPointCategory, raw_factory) -> None:
        """Raw -> SimpleSchedule(domain) -> raw -> SimpleSchedule(domain) must converge."""
        raw = raw_factory()
        first = DefaultWeekProfile.convert_raw_to_dict_schedule(raw_schedule=raw, domain=domain)
        round_tripped_raw = DefaultWeekProfile.convert_dict_to_raw_schedule(schedule_data=first)
        second = DefaultWeekProfile.convert_raw_to_dict_schedule(raw_schedule=round_tripped_raw, domain=domain)
        assert first == second

    @pytest.mark.parametrize(
        ("domain", "raw_factory"),
        [
            (DataPointCategory.SWITCH, _switch_raw_with_ramp_time),
            (DataPointCategory.COVER, _cover_raw_with_ramp_time_and_duration),
            (DataPointCategory.VALVE, _valve_raw_with_ramp_time_and_level_2),
            (DataPointCategory.LIGHT, _light_raw_with_level_2),
        ],
    )
    def test_raw_to_simple_passes_domain_validation(self, domain: DataPointCategory, raw_factory) -> None:
        """get_schedule output must pass set_schedule's domain-aware validation."""
        raw = raw_factory()
        result = DefaultWeekProfile.convert_raw_to_dict_schedule(raw_schedule=raw, domain=domain)
        # Mirrors DefaultWeekProfile.set_schedule: re-validate with domain context.
        # If this raises, the HA schedule editor breaks on a simple read/edit cycle.
        SimpleSchedule.model_validate(
            result.model_dump(),
            context={SCHEDULE_DOMAIN_CONTEXT_KEY: domain},
        )
