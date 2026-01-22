"""Sensor value transformation mixin."""

from __future__ import annotations

from typing import Any, Protocol

from aiohomematic.model.support import check_length_and_log, get_value_from_value_list


class _ValueConverterProtocol(Protocol):
    """Protocol for value converter functions."""

    def __call__(self, *, value: Any) -> Any:
        """Convert a value."""


class SensorValueMixin:
    """
    Mixin for standardized sensor value transformation.

    Provides common logic for:
    - Value list lookup
    - Converter function application
    - String length validation

    Used by both DpSensor (generic) and SysvarDpSensor (hub).
    """

    __slots__ = ()

    def _get_converter_func(self) -> _ValueConverterProtocol | None:
        """Return optional converter function. Override in subclass if needed."""
        return None

    def _transform_sensor_value(
        self,
        *,
        raw_value: Any,
        value_list: tuple[str, ...] | None,
        check_name: str,
        is_string: bool,
    ) -> Any:
        """
        Transform raw sensor value with standard logic.

        Processing sequence:
        1. Check value list mapping (if provided)
        2. Apply converter function (if registered)
        3. Validate string length (if string type)
        4. Return normalized value

        Args:
            raw_value: The raw value to transform.
            value_list: Optional tuple of valid string values.
            check_name: Name for logging (entity name).
            is_string: Whether the value is expected to be a string.

        Returns:
            Transformed value.

        """
        # Priority 1: Value list lookup
        if value_list and (mapped := get_value_from_value_list(value=raw_value, value_list=value_list)) is not None:
            return mapped

        # Priority 2: Custom converter
        if convert_func := self._get_converter_func():
            return convert_func(value=raw_value)

        # Priority 3: String validation or pass-through
        if is_string:
            return check_length_and_log(name=check_name, value=raw_value)
        return raw_value
