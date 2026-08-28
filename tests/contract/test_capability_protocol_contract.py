# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract tests for the category-specific capability protocols.

STABILITY GUARANTEE
-------------------
``aiohomematic.interfaces.custom`` exposes one ``@runtime_checkable`` protocol per
custom category, carrying that category's ``capabilities`` dataclass plus the public
API shared by every implementation of the category. Consumers (notably the Home
Assistant integration) dispatch on capability flags instead of on concrete class
identity, so both the nominal inheritance and the structural surface are part of the
public contract. Any change that breaks these tests requires a MAJOR version bump.

The contract ensures that:
1. Every category protocol is runtime checkable and carries ``capabilities``.
2. Every concrete custom data point class explicitly inherits its category protocol
   (structural subtyping alone is not enough — see ADR-0002/0003).
3. The protocols discriminate: a class satisfies only its own category's protocols.
4. A capability flag and its sub-protocol agree (``tilt``/``vent``/``soundfiles``).

See ADR-0018 for architectural context.
"""

from __future__ import annotations

import inspect
from typing import Any, Protocol, cast

import pytest

from aiohomematic.interfaces import (
    ClimateDataPointProtocol,
    CoverDataPointProtocol,
    GarageDataPointProtocol,
    LightDataPointProtocol,
    LockDataPointProtocol,
    SirenDataPointProtocol,
    SoundPlayerDataPointProtocol,
    TiltCoverDataPointProtocol,
)
from aiohomematic.model.custom import (
    CustomDataPoint,
    CustomDpBlind,
    CustomDpCover,
    CustomDpGarage,
    CustomDpIpBlind,
    CustomDpIpSiren,
    CustomDpSoundPlayer,
)
from aiohomematic_test_support.helper import get_prepared_custom_data_point

# pylint: disable=protected-access

COVER_TEST_DEVICES: set[str] = {"VCU0000144", "VCU1223813", "VCU3574044", "VCU8537918"}
SIREN_TEST_DEVICES: set[str] = {"VCU1543608", "VCU8249617"}

# All category protocols, base protocols first.
CATEGORY_PROTOCOLS: tuple[type, ...] = (
    ClimateDataPointProtocol,
    CoverDataPointProtocol,
    LightDataPointProtocol,
    LockDataPointProtocol,
    SirenDataPointProtocol,
    GarageDataPointProtocol,
    SoundPlayerDataPointProtocol,
    TiltCoverDataPointProtocol,
)

# Expected explicit protocol inheritance per concrete custom data point class.
# A class listed with a sub-protocol implicitly also carries its base protocol.
EXPECTED_CATEGORY_PROTOCOLS: dict[str, frozenset[type]] = {
    "CustomDpBlind": frozenset({TiltCoverDataPointProtocol}),
    "CustomDpButtonLock": frozenset({LockDataPointProtocol}),
    "CustomDpColorDimmer": frozenset({LightDataPointProtocol}),
    "CustomDpColorDimmerEffect": frozenset({LightDataPointProtocol}),
    "CustomDpColorTempDimmer": frozenset({LightDataPointProtocol}),
    "CustomDpCover": frozenset({CoverDataPointProtocol}),
    "CustomDpDimmer": frozenset({LightDataPointProtocol}),
    "CustomDpGarage": frozenset({GarageDataPointProtocol}),
    "CustomDpIpAccessPermission": frozenset(),
    "CustomDpIpBlind": frozenset({TiltCoverDataPointProtocol}),
    "CustomDpIpDrgDaliLight": frozenset({LightDataPointProtocol}),
    "CustomDpIpFixedColorLight": frozenset({LightDataPointProtocol}),
    "CustomDpIpIrrigationValve": frozenset(),
    "CustomDpIpLock": frozenset({LockDataPointProtocol}),
    "CustomDpIpRGBWColorTempLight": frozenset({LightDataPointProtocol}),
    "CustomDpIpRGBWLight": frozenset({LightDataPointProtocol}),
    "CustomDpIpSiren": frozenset({SirenDataPointProtocol}),
    "CustomDpIpSirenSmoke": frozenset({SirenDataPointProtocol}),
    "CustomDpIpThermostat": frozenset({ClimateDataPointProtocol}),
    "CustomDpRfLock": frozenset({LockDataPointProtocol}),
    "CustomDpRfThermostat": frozenset({ClimateDataPointProtocol}),
    "CustomDpSimpleRfThermostat": frozenset({ClimateDataPointProtocol}),
    "CustomDpSoundPlayer": frozenset({SoundPlayerDataPointProtocol}),
    "CustomDpSoundPlayerLed": frozenset({LightDataPointProtocol}),
    "CustomDpSwitch": frozenset(),
    "CustomDpTextDisplay": frozenset(),
    "CustomDpWindowDrive": frozenset({CoverDataPointProtocol}),
}


def _concrete_cdp_classes() -> dict[str, type[CustomDataPoint]]:
    """Return every concrete custom data point class by name."""
    seen: dict[str, type[CustomDataPoint]] = {}

    def _walk(cls: type[CustomDataPoint]) -> None:
        for sub in cls.__subclasses__():
            if not inspect.isabstract(sub) and not sub.__name__.startswith("_"):
                seen[sub.__name__] = sub
            _walk(sub)

    _walk(CustomDataPoint)
    return seen


def _structurally_satisfies(*, cls: type, protocol: type) -> bool:
    """Return whether a class carries every member a runtime_checkable protocol checks."""
    return all(hasattr(cls, attr) for attr in protocol.__protocol_attrs__)  # type: ignore[attr-defined]


def _expected_protocols(*, name: str) -> frozenset[type]:
    """Return the declared protocols of a class, expanded by their protocol bases."""
    expanded: set[type] = set()
    for protocol in EXPECTED_CATEGORY_PROTOCOLS[name]:
        expanded.add(protocol)
        expanded.update(base for base in protocol.__mro__ if base in CATEGORY_PROTOCOLS)
    return frozenset(expanded)


# =============================================================================
# Contract: Protocol shape
# =============================================================================


class TestCategoryProtocolShapeContract:
    """Contract: Every category protocol is runtime checkable and carries capabilities."""

    @pytest.mark.parametrize("protocol", CATEGORY_PROTOCOLS, ids=lambda p: cast(type, p).__name__)
    def test_protocol_carries_capabilities(self, protocol: type) -> None:
        """Contract: capabilities is reachable on every category protocol."""
        assert "capabilities" in protocol.__protocol_attrs__  # type: ignore[attr-defined]

    @pytest.mark.parametrize("protocol", CATEGORY_PROTOCOLS, ids=lambda p: cast(type, p).__name__)
    def test_protocol_declares_more_than_capabilities(self, protocol: type) -> None:
        """Contract: Category protocols discriminate, so they declare a category surface."""
        own_members = {name for name in vars(protocol) if not name.startswith("_")}
        assert own_members - {"capabilities"}, f"{protocol.__name__} would not discriminate"

    @pytest.mark.parametrize("protocol", CATEGORY_PROTOCOLS, ids=lambda p: cast(type, p).__name__)
    def test_protocol_is_runtime_checkable(self, protocol: type) -> None:
        """Contract: Category protocols are runtime checkable."""
        assert issubclass(protocol, Protocol)  # type: ignore[arg-type]
        assert getattr(protocol, "_is_runtime_protocol", False) is True


# =============================================================================
# Contract: Explicit inheritance and structural completeness
# =============================================================================


class TestCategoryProtocolInheritanceContract:
    """Contract: Concrete custom data points explicitly inherit their category protocol."""

    def test_declared_protocols_are_structurally_complete(self) -> None:
        """Contract: A declared protocol's every member exists on the implementing class."""
        for name, cls in _concrete_cdp_classes().items():
            for protocol in _expected_protocols(name=name):
                missing = [attr for attr in protocol.__protocol_attrs__ if not hasattr(cls, attr)]  # type: ignore[attr-defined]
                assert not missing, f"{name} misses {missing} of {protocol.__name__}"

    def test_every_concrete_cdp_class_is_covered(self) -> None:
        """Contract: The expectation table covers every concrete custom data point class."""
        assert set(_concrete_cdp_classes()) == set(EXPECTED_CATEGORY_PROTOCOLS)

    def test_explicit_inheritance_matches_contract(self) -> None:
        """Contract: The protocols in the MRO are exactly the declared ones."""
        for name, cls in _concrete_cdp_classes().items():
            actual = frozenset(base for base in cls.__mro__ if base in CATEGORY_PROTOCOLS)
            assert actual == _expected_protocols(name=name), f"{name}: unexpected category protocols"

    def test_protocols_discriminate_between_categories(self) -> None:
        """Contract: A class structurally satisfies only its own category's protocols."""
        for name, cls in _concrete_cdp_classes().items():
            declared = _expected_protocols(name=name)
            for protocol in CATEGORY_PROTOCOLS:
                satisfied = _structurally_satisfies(cls=cls, protocol=protocol)
                assert satisfied is (protocol in declared), (
                    f"{name} vs {protocol.__name__}: isinstance would return {satisfied}"
                )


# =============================================================================
# Contract: Capability flag and sub-protocol agree
# =============================================================================


class TestCapabilityDispatchContract:
    """Contract: Capability flags and their sub-protocols agree on live data points."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("address_device_translation", "do_mock_client", "ignore_devices_on_create", "un_ignore_list"),
        [(COVER_TEST_DEVICES, True, None, None)],
    )
    async def test_cover_capability_matches_sub_protocol(
        self,
        central_client_factory_with_homegear_client: Any,
    ) -> None:
        """Contract: capabilities.tilt/vent agree with the tilt/garage protocol."""
        central, _, _ = central_client_factory_with_homegear_client
        data_points = (
            get_prepared_custom_data_point(central, "VCU8537918", 4),  # CustomDpCover
            get_prepared_custom_data_point(central, "VCU0000144", 1),  # CustomDpBlind
            get_prepared_custom_data_point(central, "VCU1223813", 4),  # CustomDpIpBlind
            get_prepared_custom_data_point(central, "VCU3574044", 1),  # CustomDpGarage
        )

        for data_point in data_points:
            assert isinstance(data_point, CoverDataPointProtocol)
            assert data_point.capabilities.tilt is isinstance(data_point, TiltCoverDataPointProtocol)
            assert data_point.capabilities.vent is isinstance(data_point, GarageDataPointProtocol)
            assert not isinstance(data_point, SirenDataPointProtocol)

        assert isinstance(data_points[0], CustomDpCover)
        assert isinstance(data_points[1], CustomDpBlind)
        assert isinstance(data_points[2], CustomDpIpBlind)
        assert isinstance(data_points[3], CustomDpGarage)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("address_device_translation", "do_mock_client", "ignore_devices_on_create", "un_ignore_list"),
        [(SIREN_TEST_DEVICES, True, None, None)],
    )
    async def test_siren_capability_matches_sub_protocol(
        self,
        central_client_factory_with_homegear_client: Any,
    ) -> None:
        """Contract: capabilities.soundfiles agrees with the sound player protocol."""
        central, _, _ = central_client_factory_with_homegear_client
        data_points = (
            get_prepared_custom_data_point(central, "VCU8249617", 3),  # CustomDpIpSiren
            get_prepared_custom_data_point(central, "VCU1543608", 2),  # CustomDpSoundPlayer
        )

        for data_point in data_points:
            assert isinstance(data_point, SirenDataPointProtocol)
            assert data_point.capabilities.soundfiles is isinstance(data_point, SoundPlayerDataPointProtocol)
            assert not isinstance(data_point, CoverDataPointProtocol)

        assert isinstance(data_points[0], CustomDpIpSiren)
        assert isinstance(data_points[1], CustomDpSoundPlayer)
