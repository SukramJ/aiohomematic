# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Generic action number data points for write-only numeric parameters.

Public API of this module is defined by __all__.

Action numbers are used for write-only FLOAT/INTEGER parameters that have
numeric ranges (MIN/MAX). They provide a number entity in HA while being
write-only at the protocol level.
"""

from __future__ import annotations

from aiohomematic.const import DataPointCategory
from aiohomematic.model.generic.number import BaseDpNumber


class BaseDpActionNumber[NumberParameterT: int | float | None](BaseDpNumber[NumberParameterT]):
    """
    Implementation of a write-only number.

    This is a data point for write-only FLOAT/INTEGER parameters that provides
    a number entity with MIN/MAX validation. Unlike DpAction, it exposes
    a number input in Home Assistant.
    """

    __slots__ = ()

    _category = DataPointCategory.ACTION_NUMBER
    _validate_state_change = False


class DpActionFloat(BaseDpActionNumber[float | None]):
    """
    Implementation of a write-only Float.

    This is a data point that gets automatically generated for write-only
    FLOAT parameters.
    """

    __slots__ = ()

    def _prepare_value_for_sending(self, *, value: int | float | str, do_validate: bool = True) -> float | None:
        """Prepare value before sending."""
        return self._prepare_number_for_sending(value=value, type_converter=float, do_validate=do_validate)


class DpActionInteger(BaseDpActionNumber[int | None]):
    """
    Implementation of a write-only Integer.

    This is a data point that gets automatically generated for write-only
    INTEGER parameters.
    """

    __slots__ = ()

    def _prepare_value_for_sending(self, *, value: int | float | str, do_validate: bool = True) -> int | None:
        """Prepare value before sending."""
        return self._prepare_number_for_sending(value=value, type_converter=int, do_validate=do_validate)
