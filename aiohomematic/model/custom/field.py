# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Descriptor-based field definitions for custom data points.

This module provides a declarative way to define data point fields,
eliminating boilerplate in _init_data_point_fields() methods.

Public API of this module is defined by __all__.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, cast, overload

from aiohomematic.const import Field
from aiohomematic.interfaces.model import GenericDataPointProtocolAny
from aiohomematic.model.generic import DpDummy
from aiohomematic.property_decorators import DelegatedProperty

if TYPE_CHECKING:
    from typing import Self

    from aiohomematic.model.custom.data_point import CustomDataPoint

__all__ = ["DataPointField"]


class DataPointField[DataPointT: GenericDataPointProtocolAny]:
    """
    Descriptor for declarative data point field definitions.

    This descriptor eliminates the need for explicit _init_data_point_fields()
    boilerplate by lazily resolving data points on first access.

    Usage:
        class CustomDpSwitch(CustomDataPoint):
            _dp_state: Final = DataPointField(field=Field.STATE, dpt=DpSwitch)
            _dp_on_time: Final = DataPointField(field=Field.ON_TIME_VALUE, dpt=DpAction)

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
            dpt: The expected data point type (e.g., DpSwitch, DpAction)

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
