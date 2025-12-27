# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Converters used by aiohomematic.

This module provides two categories of converters:

1. General type converters using singledispatch:
   - to_homematic_value: Convert Python types to Homematic-compatible values
   - from_homematic_value: Convert Homematic values to Python types

2. Combined parameter converters:
   - convert_combined_parameter_to_paramset: Parse combined parameter strings
   - convert_hm_level_to_cpv: Convert level to combined parameter value

The singledispatch converters are extensible - register new type handlers with:
    @to_homematic_value.register(YourType)
    def _(value: YourType) -> Any:
        return converted_value

Public API of this module is defined by __all__.
"""

from __future__ import annotations

import ast
from datetime import datetime, timedelta
from enum import Enum
from functools import lru_cache, singledispatch
import inspect
import logging
from typing import Any, Final, cast

from aiohomematic.const import Parameter
from aiohomematic.support import extract_exc_args

_LOGGER = logging.getLogger(__name__)


# =============================================================================
# SINGLEDISPATCH CONVERTERS: Python → Homematic
# =============================================================================


@singledispatch
def to_homematic_value(value: Any) -> Any:  # kwonly: disable
    """
    Convert Python values to Homematic-compatible values.

    Uses singledispatch for type-based conversion. The function automatically
    selects the appropriate converter based on the input type.

    Default behavior (unregistered types):
        Returns value unchanged.

    Registered conversions:
        - bool → int (True=1, False=0)
        - float → float (rounded to 6 decimal places)
        - datetime → str (ISO format)
        - timedelta → float (total seconds)
        - Enum → value attribute
        - list → list (items converted recursively)
        - dict → dict (values converted recursively)

    Args:
        value: Python value to convert.

    Returns:
        Homematic-compatible value.

    Example:
        >>> to_homematic_value(True)
        1
        >>> to_homematic_value(3.14159265359)
        3.141593
        >>> to_homematic_value(MyEnum.VALUE)
        'VALUE'

    Extensibility:
        Register handlers for custom types:

        @to_homematic_value.register(Color)
        def _(value: Color) -> int:
            return (value.r << 16) | (value.g << 8) | value.b

    """
    return value


@to_homematic_value.register(bool)
def _to_hm_bool(value: bool) -> int:  # kwonly: disable
    """Convert boolean to Homematic integer (1/0)."""
    return 1 if value else 0


@to_homematic_value.register(float)
def _to_hm_float(value: float) -> float:  # kwonly: disable
    """Convert float to Homematic float (6 decimal places max)."""
    return round(value, 6)


@to_homematic_value.register(datetime)
def _to_hm_datetime(value: datetime) -> str:  # kwonly: disable
    """Convert datetime to ISO format string."""
    return value.isoformat()


@to_homematic_value.register(timedelta)
def _to_hm_timedelta(value: timedelta) -> float:  # kwonly: disable
    """Convert timedelta to total seconds."""
    return value.total_seconds()


@to_homematic_value.register(Enum)
def _to_hm_enum(value: Enum) -> Any:  # kwonly: disable
    """Convert Enum to its value."""
    return value.value


@to_homematic_value.register(list)
def _to_hm_list(value: list[Any]) -> list[Any]:  # kwonly: disable
    """Convert list elements recursively."""
    return [to_homematic_value(item) for item in value]


@to_homematic_value.register(dict)
def _to_hm_dict(value: dict[str, Any]) -> dict[str, Any]:  # kwonly: disable
    """Convert dict values recursively."""
    return {k: to_homematic_value(v) for k, v in value.items()}


# =============================================================================
# SINGLEDISPATCH CONVERTERS: Homematic → Python
# =============================================================================


@singledispatch
def from_homematic_value(value: Any, *, target_type: type | None = None) -> Any:  # kwonly: disable
    """
    Convert Homematic values to Python types.

    Uses singledispatch for type-based conversion. Optionally converts
    to a specific target type when provided.

    Default behavior (unregistered types):
        Returns value unchanged.

    Registered conversions:
        - int with target_type=bool → bool
        - str with target_type=datetime → datetime (ISO parse)

    Args:
        value: Homematic value to convert.
        target_type: Optional target Python type for conversion hint.

    Returns:
        Python value.

    Example:
        >>> from_homematic_value(1, target_type=bool)
        True
        >>> from_homematic_value("2025-01-15T10:30:00", target_type=datetime)
        datetime(2025, 1, 15, 10, 30)

    """
    return value


@from_homematic_value.register(int)
def _from_hm_int(value: int, *, target_type: type | None = None) -> int | bool:  # kwonly: disable
    """Convert Homematic integer, optionally to bool."""
    if target_type is bool:
        return bool(value)
    return value


@from_homematic_value.register(str)
def _from_hm_str(value: str, *, target_type: type | None = None) -> str | datetime:  # kwonly: disable
    """Convert Homematic string, optionally to datetime."""
    if target_type is datetime:
        return datetime.fromisoformat(value)
    return value


@lru_cache(maxsize=1024)
def _convert_cpv_to_hm_level(*, value: Any) -> Any:
    """Convert combined parameter value for hm level."""
    if isinstance(value, str) and value.startswith("0x"):
        return ast.literal_eval(value) / 100 / 2
    return value


@lru_cache(maxsize=1024)
def _convert_cpv_to_hmip_level(*, value: Any) -> Any:
    """Convert combined parameter value for hmip level."""
    return int(value) / 100


@lru_cache(maxsize=1024)
def convert_hm_level_to_cpv(*, value: Any) -> Any:
    """Convert hm level to combined parameter value."""
    return format(int(value * 100 * 2), "#04x")


CONVERTABLE_PARAMETERS: Final = (Parameter.COMBINED_PARAMETER, Parameter.LEVEL_COMBINED)

_COMBINED_PARAMETER_TO_HM_CONVERTER: Final = {
    Parameter.LEVEL_COMBINED: _convert_cpv_to_hm_level,
    Parameter.LEVEL: _convert_cpv_to_hmip_level,
    Parameter.LEVEL_2: _convert_cpv_to_hmip_level,
}

_COMBINED_PARAMETER_NAMES: Final = {"L": Parameter.LEVEL, "L2": Parameter.LEVEL_2}


@lru_cache(maxsize=1024)
def _convert_combined_parameter_to_paramset(*, value: str) -> dict[str, Any]:
    """Convert combined parameter to paramset."""
    paramset: dict[str, Any] = {}
    for cp_param_value in value.split(","):
        cp_param, value = cp_param_value.split("=")
        if parameter := _COMBINED_PARAMETER_NAMES.get(cp_param):
            if converter := _COMBINED_PARAMETER_TO_HM_CONVERTER.get(parameter):
                paramset[parameter] = converter(value=value)
            else:
                paramset[parameter] = value
    return paramset


@lru_cache(maxsize=1024)
def _convert_level_combined_to_paramset(*, value: str) -> dict[str, Any]:
    """Convert combined parameter to paramset."""
    if "," in value:
        l1_value, l2_value = value.split(",")
        if converter := _COMBINED_PARAMETER_TO_HM_CONVERTER.get(Parameter.LEVEL_COMBINED):
            return {
                Parameter.LEVEL: converter(value=l1_value),
                Parameter.LEVEL_SLATS: converter(value=l2_value),
            }
    return {}


_COMBINED_PARAMETER_TO_PARAMSET_CONVERTER: Final = {
    Parameter.COMBINED_PARAMETER: _convert_combined_parameter_to_paramset,
    Parameter.LEVEL_COMBINED: _convert_level_combined_to_paramset,
}


@lru_cache(maxsize=1024)
def convert_combined_parameter_to_paramset(*, parameter: str, value: str) -> dict[str, Any]:
    """Convert combined parameter to paramset."""
    try:
        if converter := _COMBINED_PARAMETER_TO_PARAMSET_CONVERTER.get(parameter):  # type: ignore[call-overload]
            return cast(dict[str, Any], converter(value=value))
        _LOGGER.debug("CONVERT_COMBINED_PARAMETER_TO_PARAMSET: No converter found for %s: %s", parameter, value)
    except Exception as exc:
        _LOGGER.debug("CONVERT_COMBINED_PARAMETER_TO_PARAMSET: Convert failed %s", extract_exc_args(exc=exc))
    return {}


# Define public API for this module
__all__ = tuple(
    sorted(
        name
        for name, obj in globals().items()
        if not name.startswith("_")
        and (name.isupper() or inspect.isfunction(obj) or inspect.isclass(obj))
        and getattr(obj, "__module__", __name__) == __name__
    )
)
