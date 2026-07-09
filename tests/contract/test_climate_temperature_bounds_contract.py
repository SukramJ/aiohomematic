# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract tests for climate schedule temperature-bound handling.

STABILITY GUARANTEE
-------------------
A climate device's temperature bounds (``min_temp`` / ``max_temp``) derive from its
SETPOINT paramset description and can be ``None`` when that description is incomplete
(e.g. after a failed ``getParamsetDescription``). ``ClimateWeekProfile`` MUST fail
schedule conversion with a caught ``ValidationException`` rather than a bare
``TypeError`` on the ``min <= temp <= max`` bound checks.

This guards against regression #3281, where ``max_temp`` returned ``None`` and
``reload_and_cache_schedule`` raised
``TypeError: '<=' not supported between instances of 'float' and 'NoneType'``.
Because ``reload_and_cache_schedule`` only swallows ``ValidationException``, an uncaught
``TypeError`` propagated out and prevented the climate entity from being added to Home
Assistant at all (permanent "unavailable").

See ``ClimateWeekProfile._require_temp_bounds`` and ``BaseCustomDpClimate.max_temp``.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from aiohomematic.exceptions import ValidationException
from aiohomematic.model.week_profile import ClimateWeekProfile


def _make_week_profile(*, min_temp: float | None, max_temp: float | None) -> ClimateWeekProfile:
    """Build a ClimateWeekProfile with the given bounds, bypassing full device setup."""
    week_profile = ClimateWeekProfile.__new__(ClimateWeekProfile)
    week_profile._device = SimpleNamespace(name="TestClimate")
    week_profile._min_temp = min_temp
    week_profile._max_temp = max_temp
    return week_profile


class TestClimateTemperatureBoundsContract:
    """Contract: missing climate temperature bounds degrade gracefully."""

    def test_both_bounds_missing_raises_validation(self) -> None:
        """Both bounds None -> ValidationException."""
        week_profile = _make_week_profile(min_temp=None, max_temp=None)
        with pytest.raises(ValidationException):
            week_profile._require_temp_bounds()

    def test_missing_max_temp_raises_validation_not_type_error(self) -> None:
        """max_temp None (the #3281 case) -> ValidationException, never a raw TypeError."""
        week_profile = _make_week_profile(min_temp=5.0, max_temp=None)
        with pytest.raises(ValidationException):
            week_profile._require_temp_bounds()

    def test_missing_min_temp_raises_validation_not_type_error(self) -> None:
        """min_temp None -> ValidationException, never a raw TypeError."""
        week_profile = _make_week_profile(min_temp=None, max_temp=30.0)
        with pytest.raises(ValidationException):
            week_profile._require_temp_bounds()

    def test_valid_bounds_are_returned_unchanged(self) -> None:
        """Both bounds present -> returned as a (min, max) tuple, no exception."""
        week_profile = _make_week_profile(min_temp=5.0, max_temp=30.0)
        assert week_profile._require_temp_bounds() == (5.0, 30.0)
