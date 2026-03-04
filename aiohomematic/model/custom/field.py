# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Descriptor-based field definitions for custom data points.

This module provides a declarative way to define data point fields,
eliminating boilerplate in _init_data_point_fields() methods.

Public API of this module is defined by __all__.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final, cast, overload

from aiohomematic.const import Field
from aiohomematic.interfaces import GenericDataPointProtocolAny
from aiohomematic.model.custom.mixins import recalc_unit_timer
from aiohomematic.model.generic import DpDummy
from aiohomematic.property_decorators import DelegatedProperty

if TYPE_CHECKING:
    from typing import Self

    from aiohomematic.model.custom.data_point import CustomDataPoint
    from aiohomematic.model.data_point import CallParameterCollector

__all__ = ["DataPointField", "TimerAccessor", "TimerField"]


class DataPointField[DataPointT: GenericDataPointProtocolAny]:
    """
    Descriptor for declarative data point field definitions.

    This descriptor eliminates the need for explicit _init_data_point_fields()
    boilerplate by lazily resolving data points on first access.

    Usage:
        class CustomDpSwitch(CustomDataPoint):
            _dp_state: Final = DataPointField(field=Field.STATE, dpt=DpSwitch)
            _dp_on_time: Final = DataPointField(field=Field.ON_TIME_VALUE, dpt=DpActionFloat)

            # No _init_data_point_fields() override needed for these fields!

    The descriptor:
    - Resolves the data point from _data_points dict on each access (O(1) lookup)
    - Returns a DpDummy fallback if the data point doesn't exist
    - Provides correct type information to mypy
    """

    __slots__ = ("_field", "_data_point_type")

    def __init__(self, *, field: Field, dpt: type[DataPointT]) -> None:
        """
        Initialize the data point field descriptor.

        Args:
            field: The Field enum value identifying this data point
            dpt: The expected data point type (e.g., DpSwitch, DpActionFloat)

        """
        self._field: Final = field
        self._data_point_type: Final = dpt

    @overload
    def __get__(self, instance: None, owner: type) -> Self: ...  # kwonly: disable

    @overload
    def __get__(self, instance: CustomDataPoint, owner: type) -> DataPointT: ...  # kwonly: disable

    def __get__(self, instance: CustomDataPoint | None, owner: type) -> Self | DataPointT:  # kwonly: disable
        """
        Get the data point for this field.

        On class-level access (instance=None), returns the descriptor itself.
        On instance access, looks up the data point from _data_points dict.
        """
        if instance is None:
            return self  # Class-level access returns descriptor

        # Resolve from _data_points dict (O(1) lookup)
        if found_dp := instance._data_points.get(self._field):
            return cast(DataPointT, found_dp)

        # Create DpDummy fallback and cache it in _data_points for subsequent accesses
        dummy = DpDummy(channel=instance._channel, param_field=self._field)
        instance._data_points[self._field] = dummy
        return cast(DataPointT, dummy)

    data_point_type: Final = DelegatedProperty[type[DataPointT]](path="_data_point_type")
    field: Final = DelegatedProperty[Field](path="_field")


class TimerAccessor:
    """Accessor that combines a value data point and optional unit data point for timer operations."""

    __slots__ = ("_unit_dp", "_value_dp")

    def __init__(self, *, value_dp: GenericDataPointProtocolAny, unit_dp: GenericDataPointProtocolAny) -> None:
        """Initialize the timer accessor."""
        self._value_dp = value_dp
        self._unit_dp = unit_dp

    @property
    def default(self) -> int | float | None:
        """Return the default value of the underlying value data point."""
        default: Any = self._value_dp.default
        return cast(int | float | None, default)

    @property
    def is_valid(self) -> bool:
        """Return True if the value data point is not a dummy."""
        return not isinstance(self._value_dp, DpDummy)

    @property
    def value(self) -> int | float | None:
        """Return the current value of the underlying value data point."""
        val: Any = self._value_dp.value
        return cast(int | float | None, val)

    async def send_default(self, *, collector: CallParameterCollector | None = None) -> None:
        """Send default values for both unit and value data points."""
        if not isinstance(self._unit_dp, DpDummy) and (unit_default := self._unit_dp.default) is not None:
            await self._unit_dp.send_value(value=unit_default, collector=collector)
        if (value_default := self._value_dp.default) is not None:
            await self._value_dp.send_value(value=value_default, collector=collector)

    async def send_value(
        self,
        *,
        value: float,
        collector: CallParameterCollector | None = None,
    ) -> None:
        """Send timer value in seconds with automatic unit conversion."""
        if isinstance(self._unit_dp, DpDummy):
            # No unit data point — send seconds directly
            await self._value_dp.send_value(value=value, collector=collector, do_validate=False)
        else:
            # Has unit — convert seconds to value+unit
            converted_value, unit = recalc_unit_timer(time=value)
            await self._unit_dp.send_value(value=unit, collector=collector)
            await self._value_dp.send_value(value=converted_value, collector=collector, do_validate=False)


class TimerField:
    """Descriptor for declarative timer field definitions (value + optional unit pair)."""

    __slots__ = ("_unit_field", "_value_field")

    def __init__(self, *, value_field: Field, unit_field: Field | None = None) -> None:
        """Initialize the timer field descriptor."""
        self._value_field: Final = value_field
        self._unit_field: Final = unit_field

    @overload
    def __get__(self, instance: None, owner: type) -> Self: ...  # kwonly: disable

    @overload
    def __get__(self, instance: CustomDataPoint, owner: type) -> TimerAccessor: ...  # kwonly: disable

    def __get__(self, instance: CustomDataPoint | None, owner: type) -> Self | TimerAccessor:  # kwonly: disable
        """
        Get the timer accessor for this field.

        On class-level access (instance=None), returns the descriptor itself.
        On instance access, returns a TimerAccessor wrapping value and unit data points.
        """
        if instance is None:
            return self  # Class-level access returns descriptor

        # Resolve value data point (DpDummy fallback if not mapped)
        if (value_dp := instance._data_points.get(self._value_field)) is None:
            value_dp = DpDummy(channel=instance._channel, param_field=self._value_field)
            instance._data_points[self._value_field] = value_dp

        # Resolve unit data point (DpDummy if no unit_field or not mapped)
        if self._unit_field is not None and (unit_dp := instance._data_points.get(self._unit_field)) is not None:
            pass  # unit_dp is set
        else:
            unit_dp = DpDummy(channel=instance._channel, param_field=self._unit_field or self._value_field)

        return TimerAccessor(value_dp=value_dp, unit_dp=unit_dp)

    unit_field: Final = DelegatedProperty[Field | None](path="_unit_field")
    value_field: Final = DelegatedProperty[Field](path="_value_field")
