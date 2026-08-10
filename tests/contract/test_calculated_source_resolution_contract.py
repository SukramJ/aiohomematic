# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract tests for calculated data point source resolution.

STABILITY GUARANTEE
-------------------
A ``CalculatedDataPoint`` resolves its source data points when it is constructed, not
when its value is first read. Two invariants depend on it:

- ``is_valid`` is gated by the readable VALUES sources, so an unresolved source set
  makes the data point claim to be invalid.
- The update subscription of a calculated data point is created while its source is
  resolved, so an unresolved source never publishes an update.

Background: #3343 — ``CalculatedDataPointField`` resolves lazily on first access. Home
Assistant reads ``is_valid`` before it reads the value and keeps showing the restored
state while the data point reports itself invalid, so the first value read never
happened and the entity stayed frozen on its pre-update value forever.
"""

from typing import Any

from aiohomematic.const import ParamsetKey
from aiohomematic.interfaces import CalculatedDataPointProtocol
from aiohomematic.model.calculated import CalculatedDataPoint, DerivedBinarySensor, DerivedBinarySensorRegistry
from aiohomematic.model.calculated.field import CalculatedDataPointField

from tests.helpers.fake_model import FakeChannel, FakeGenericDP

# pylint: disable=protected-access


def _all_calculated_classes() -> list[type[CalculatedDataPoint[Any]]]:
    """Return all (direct and indirect) subclasses of CalculatedDataPoint."""
    result: list[type[CalculatedDataPoint[Any]]] = []

    def _walk(cls: type[CalculatedDataPoint[Any]]) -> None:
        for sub in cls.__subclasses__():
            result.append(sub)
            _walk(sub)

    _walk(CalculatedDataPoint)
    return result


def _build(cls: type[CalculatedDataPoint[Any]]) -> CalculatedDataPoint[Any]:
    """Return an instance of cls on a channel that provides every declared source."""
    if cls is DerivedBinarySensor:
        mapping = next(iter(DerivedBinarySensorRegistry._registry.values()))
        channel = FakeChannel(model="Any", address=f"ADDR1:{mapping.source_channel_no}")
        channel.add_fake(
            FakeGenericDP(
                parameter=mapping.source_parameter,
                paramset_key=ParamsetKey.VALUES,
                value=next(iter(mapping.on_values)),
            )
        )
        return DerivedBinarySensor(channel=channel, mapping=mapping)  # type: ignore[arg-type]

    channel = FakeChannel(model="Any")
    for field in _declared_source_fields(cls=cls).values():
        channel.add_fake(
            FakeGenericDP(
                parameter=field.parameter,
                paramset_key=field.paramset_key,  # type: ignore[arg-type]
                value=1.0,
            )
        )
    return cls(channel=channel)  # type: ignore[arg-type]


def _concrete_calculated_classes() -> list[type[CalculatedDataPoint[Any]]]:
    """Return the calculated data point classes that are created for a channel."""
    # Only the classes that implement the protocol are instantiated by the factory;
    # intermediate bases (e.g. BaseClimateSensor) carry no calculated parameter.
    return [cls for cls in _all_calculated_classes() if CalculatedDataPointProtocol in cls.__mro__]


def _declared_source_fields(*, cls: type[CalculatedDataPoint[Any]]) -> dict[str, CalculatedDataPointField[Any]]:
    """Return the source fields declared by cls and its bases, keyed by attribute name."""
    fields: dict[str, CalculatedDataPointField[Any]] = {}
    for klass in reversed(cls.__mro__):
        fields.update(
            {
                name: attribute
                for name, attribute in vars(klass).items()
                if isinstance(attribute, CalculatedDataPointField)
            }
        )
    return fields


class TestCalculatedSourceResolutionContract:
    """Pin the source resolution behaviour of every calculated data point class."""

    def test_declared_sources_are_resolved_at_construction(self) -> None:
        """Every declared source field is resolved before the value is ever read."""
        for cls in _concrete_calculated_classes():
            if not (declared := _declared_source_fields(cls=cls)):
                continue
            calculated_data_point = _build(cls)
            expected = {(field.parameter, field.paramset_key) for field in declared.values()}
            resolved = set(calculated_data_point._data_points)
            assert expected <= resolved, (
                f"{cls.__name__} did not resolve {sorted(expected - resolved)} at construction time. "
                f"Source fields must not be resolved lazily (#3343)."
            )

    def test_every_calculated_data_point_has_a_state_carrier(self) -> None:
        """Every calculated data point can report validity without a prior value read."""
        for cls in _concrete_calculated_classes():
            calculated_data_point = _build(cls)
            assert calculated_data_point._relevant_data_points, (
                f"{cls.__name__} has no readable VALUES source after construction and can therefore never become valid."
            )
            assert calculated_data_point.is_valid is True, (
                f"{cls.__name__} reports itself invalid although every source carries a valid value."
            )

    def test_no_subclass_overrides_source_resolution(self) -> None:
        """No subclass may override the resolution of declared source fields."""
        for cls in _all_calculated_classes():
            assert "_resolve_declared_source_data_points" not in vars(cls), (
                f"{cls.__name__} overrides _resolve_declared_source_data_points. "
                f"Declare sources as CalculatedDataPointField instead."
            )

    def test_sources_are_subscribed_at_construction(self) -> None:
        """Every resolved source is subscribed, so source updates reach the data point."""
        for cls in _concrete_calculated_classes():
            calculated_data_point = _build(cls)
            # MASTER sources do not gate validity but still trigger a recalculation.
            assert len(calculated_data_point._unsubscribe_callbacks) == len(
                calculated_data_point._readable_data_points
            ), f"{cls.__name__} resolved sources without subscribing to their updates."
