# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Module for data points implemented using the number category."""

from __future__ import annotations

from typing import cast

from aiohomematic import i18n
from aiohomematic.const import DataPointCategory
from aiohomematic.exceptions import ValidationException
from aiohomematic.model.generic.data_point import GenericDataPoint
from aiohomematic.property_decorators import state_property


class BaseDpNumber[NumberParameterT: int | float | None](GenericDataPoint[NumberParameterT, int | float | str]):
    """
    Implementation of a number.

    This is a default data point that gets automatically generated.
    """

    __slots__ = ()

    _category = DataPointCategory.NUMBER

    def _prepare_number_for_sending(
        self, *, value: int | float | str, type_converter: type, do_validate: bool = True
    ) -> NumberParameterT:
        """Prepare value before sending."""
        if not do_validate or (
            value is not None and isinstance(value, int | float) and self._min <= type_converter(value) <= self._max
        ):
            return cast(NumberParameterT, type_converter(value))
        if self._special and isinstance(value, str) and value in self._special:
            return cast(NumberParameterT, type_converter(self._special[value]))
        raise ValidationException(
            i18n.tr(
                "exception.model.number.invalid_value",
                value=value,
                min=self._min,
                max=self._max,
                special=self._special,
            )
        )


class DpFloat(BaseDpNumber[float | None]):
    """
    Implementation of a Float.

    This is a default data point that gets automatically generated.
    """

    __slots__ = ()

    @state_property
    def value(self) -> float | None:
        """Return the value of the data_point."""
        return self._value

    def _prepare_value_for_sending(self, *, value: int | float | str, do_validate: bool = True) -> float | None:
        """Prepare value before sending."""
        return self._prepare_number_for_sending(value=value, type_converter=float, do_validate=do_validate)


class DpInteger(BaseDpNumber[int | None]):
    """
    Implementation of an Integer.

    This is a default data point that gets automatically generated.
    """

    __slots__ = ()

    @state_property
    def value(self) -> int | None:
        """Return the value of the data_point."""
        return self._value

    def _prepare_value_for_sending(self, *, value: int | float | str, do_validate: bool = True) -> int | None:
        """Prepare value before sending."""
        return self._prepare_number_for_sending(value=value, type_converter=int, do_validate=do_validate)
