# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Descriptor-based field definition for combined timer data points.

Public API of this module is defined by __all__.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, overload

from aiohomematic.const import Field
from aiohomematic.interfaces import ChannelProtocol, GenericDataPointProtocolAny
from aiohomematic.model.combined.timer import CombinedDpTimerAction
from aiohomematic.model.generic import DpDummy
from aiohomematic.property_decorators import DelegatedProperty

if TYPE_CHECKING:
    from typing import Self

    from aiohomematic.model.custom.data_point import CustomDataPoint

__all__ = ["CombinedTimerField"]

# Marker attribute name used to detect CombinedTimerField descriptors
# without requiring isinstance checks or lazy imports
COMBINED_TIMER_FIELD_MARKER: Final = "_is_combined_timer_field"


class CombinedTimerField:
    """Descriptor that creates/returns a CombinedDpTimerAction for custom data points."""

    __slots__ = ("_unit_field", "_value_field", "_visible")

    _is_combined_timer_field: Final = True

    def __init__(
        self,
        *,
        value_field: Field,
        unit_field: Field | None = None,
        visible: bool = False,
    ) -> None:
        """Initialize the combined timer field descriptor."""
        self._value_field: Final = value_field
        self._unit_field: Final = unit_field
        self._visible: Final = visible

    @overload
    def __get__(self, instance: None, owner: type) -> Self: ...  # kwonly: disable

    @overload
    def __get__(self, instance: CustomDataPoint, owner: type) -> CombinedDpTimerAction: ...  # kwonly: disable

    def __get__(self, instance: CustomDataPoint | None, owner: type) -> Self | CombinedDpTimerAction:  # kwonly: disable
        """
        Get the combined DP for this field.

        On class-level access (instance=None), returns the descriptor itself.
        On instance access, returns the cached CombinedDpTimerAction.
        """
        if instance is None:
            return self  # Class-level access returns descriptor

        # Return cached combined DP if already created
        if (combined_dp := instance._combined_data_points.get(self._value_field)) is not None:
            return combined_dp  # type: ignore[return-value]

        # Should not reach here — combined DPs are created during _create_combined_data_points
        msg = f"CombinedDpTimerAction not initialized for {self._value_field}"
        raise RuntimeError(msg)

    unit_field: Final = DelegatedProperty[Field | None](path="_unit_field")
    value_field: Final = DelegatedProperty[Field](path="_value_field")

    def create_combined_dp(
        self,
        *,
        channel: ChannelProtocol,
        data_points: dict[Field, GenericDataPointProtocolAny],
    ) -> CombinedDpTimerAction:
        """Create the CombinedDpTimerAction for the given custom data point instance."""
        # Resolve value DP
        if (value_dp := data_points.get(self._value_field)) is None:
            value_dp = DpDummy(channel=channel, param_field=self._value_field)

        # Resolve unit DP
        if self._unit_field is not None and (unit_dp := data_points.get(self._unit_field)) is not None:
            pass  # unit_dp is set
        else:
            unit_dp = DpDummy(channel=channel, param_field=self._unit_field or self._value_field)

        return CombinedDpTimerAction(
            channel=channel,
            value_field=self._value_field,
            unit_field=self._unit_field,
            value_dp=value_dp,
            unit_dp=unit_dp,
            visible=self._visible,
        )
