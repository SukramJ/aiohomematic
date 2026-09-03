# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract tests for custom data point validity gating.

STABILITY GUARANTEE
-------------------
``CustomDataPoint`` validity (``is_refreshed``/``is_valid``/``state_uncertain``) is
gated exclusively by the readable data points of the fields declared in
``_validity_relevant_fields`` (ADR-0025). This contract pins, for every concrete
custom data point class, exactly which fields gate validity. Any change to the sets
below changes Home Assistant entity availability (``value_state``) and must be a
deliberate, changelog-documented decision.

Background: #3255, #3279 — secondary values (activity/direction readbacks,
group-channel readbacks, colors, extra sensors) can stay unrefreshed for hours after
a CCU restart. If they gate validity, entities hang in ``value_state=restored`` until
a device event arrives.
"""

from __future__ import annotations

import inspect

from aiohomematic.const import Field
from aiohomematic.model.custom import CustomDataPoint

# pylint: disable=protected-access

# Effective validity-relevant fields per concrete custom data point class.
EXPECTED_VALIDITY_RELEVANT_FIELDS: dict[str, frozenset[Field]] = {
    "CustomDpBlind": frozenset({Field.LEVEL}),
    "CustomDpButtonLock": frozenset({Field.BUTTON_LOCK}),
    "CustomDpColorDimmer": frozenset({Field.LEVEL}),
    "CustomDpColorDimmerEffect": frozenset({Field.LEVEL}),
    "CustomDpColorTempDimmer": frozenset({Field.LEVEL}),
    "CustomDpCover": frozenset({Field.LEVEL}),
    "CustomDpDimmer": frozenset({Field.LEVEL}),
    "CustomDpGarage": frozenset({Field.DOOR_STATE}),
    "CustomDpIpAccessPermission": frozenset({Field.STATE}),
    "CustomDpIpBlind": frozenset({Field.LEVEL}),
    "CustomDpIpDrgDaliLight": frozenset({Field.LEVEL}),
    "CustomDpIpFixedColorLight": frozenset({Field.LEVEL}),
    "CustomDpIpIrrigationValve": frozenset({Field.STATE}),
    "CustomDpIpLock": frozenset({Field.LOCK_STATE}),
    "CustomDpIpRGBWColorTempLight": frozenset({Field.LEVEL}),
    "CustomDpIpRGBWLight": frozenset({Field.LEVEL}),
    "CustomDpIpSiren": frozenset({Field.ACOUSTIC_ALARM_ACTIVE, Field.OPTICAL_ALARM_ACTIVE}),
    "CustomDpIpSirenSmoke": frozenset({Field.SMOKE_DETECTOR_ALARM_STATUS}),
    "CustomDpIpThermostat": frozenset({Field.TEMPERATURE, Field.SETPOINT}),
    "CustomDpRfLock": frozenset({Field.STATE}),
    "CustomDpRfThermostat": frozenset({Field.TEMPERATURE, Field.SETPOINT}),
    "CustomDpSimpleRfThermostat": frozenset({Field.TEMPERATURE}),
    "CustomDpSoundPlayer": frozenset({Field.DIRECTION}),
    "CustomDpSoundPlayerLed": frozenset({Field.LEVEL}),
    "CustomDpSwitch": frozenset({Field.STATE}),
    "CustomDpTextDisplay": frozenset(),
    "CustomDpWindowDrive": frozenset({Field.LEVEL}),
}


def _all_cdp_classes() -> list[type[CustomDataPoint]]:
    """Return all (direct and indirect) subclasses of CustomDataPoint."""
    result: list[type[CustomDataPoint]] = []

    def _walk(cls: type[CustomDataPoint]) -> None:
        for sub in cls.__subclasses__():
            result.append(sub)
            _walk(sub)

    _walk(CustomDataPoint)
    return result


def _concrete_cdp_classes() -> list[type[CustomDataPoint]]:
    """Return all concrete (instantiable) custom data point classes."""
    return [cls for cls in _all_cdp_classes() if not inspect.isabstract(cls)]


class TestCdpValidityContract:
    """Pin the validity gating of every custom data point class."""

    def test_base_class_has_no_default(self) -> None:
        """CustomDataPoint must not define a default — subclasses must decide explicitly."""
        assert "_validity_relevant_fields" not in vars(CustomDataPoint)

    def test_every_concrete_cdp_class_is_covered(self) -> None:
        """Every concrete CDP class must have an entry in the contract table."""
        concrete = {cls.__name__ for cls in _concrete_cdp_classes()}
        expected = set(EXPECTED_VALIDITY_RELEVANT_FIELDS)
        assert concrete - expected == set(), (
            f"New custom data point class(es) without validity contract: "
            f"{sorted(concrete - expected)}. Add them to EXPECTED_VALIDITY_RELEVANT_FIELDS."
        )
        assert expected - concrete == set(), (
            f"Contract table contains unknown class(es): {sorted(expected - concrete)}."
        )

    def test_no_relevant_data_points_overrides(self) -> None:
        """No subclass may override _relevant_data_points — the frozenset is the only mechanism."""
        for cls in _all_cdp_classes():
            assert "_relevant_data_points" not in vars(cls), (
                f"{cls.__name__} overrides _relevant_data_points. Declare _validity_relevant_fields instead (ADR-0025)."
            )

    def test_validity_relevant_fields_match_contract(self) -> None:
        """The effective field set of every concrete CDP class matches the contract."""
        for cls in _concrete_cdp_classes():
            declared = getattr(cls, "_validity_relevant_fields", None)
            assert declared is not None, (
                f"{cls.__name__} does not resolve _validity_relevant_fields — declare it on the class or a base class."
            )
            assert declared == EXPECTED_VALIDITY_RELEVANT_FIELDS[cls.__name__], (
                f"{cls.__name__}: validity-relevant fields changed. "
                f"Expected {sorted(EXPECTED_VALIDITY_RELEVANT_FIELDS[cls.__name__])}, "
                f"got {sorted(declared)}. If intentional, update the contract and changelog."
            )
