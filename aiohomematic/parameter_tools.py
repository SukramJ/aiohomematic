# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Parameter inspection, validation, and comparison utilities.

This module provides three groups of helper functions for working with
Homematic ``ParameterData`` descriptions:

1. **ParameterHelper** -- flag and operation checks, enum resolution, step size.
2. **ParameterValidator** -- value validation and type coercion.
3. **ParamsetDiff** -- type-aware comparison of two paramset snapshots.

All functions are pure (no I/O, no side-effects) and operate solely on the
``ParameterData`` typed-dict defined in ``aiohomematic.const``.

Public API of this module is defined by __all__.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import inspect
from typing import Any

from aiohomematic.const import Flag, Operations, ParameterData, ParameterType

# ---------------------------------------------------------------------------
# ParameterHelper -- flag / operation queries and enum helpers
# ---------------------------------------------------------------------------


def is_parameter_visible(*, parameter_data: ParameterData) -> bool:
    """Return if a parameter has the VISIBLE flag set."""
    return bool(parameter_data.get("FLAGS", 0) & Flag.VISIBLE)


def is_parameter_internal(*, parameter_data: ParameterData) -> bool:
    """Return if a parameter has the INTERNAL flag set."""
    return bool(parameter_data.get("FLAGS", 0) & Flag.INTERNAL)


def is_parameter_service(*, parameter_data: ParameterData) -> bool:
    """Return if a parameter has the SERVICE flag set."""
    return bool(parameter_data.get("FLAGS", 0) & Flag.SERVICE)


def is_parameter_readable(*, parameter_data: ParameterData) -> bool:
    """Return if a parameter supports READ operations."""
    return bool(parameter_data.get("OPERATIONS", Operations.NONE) & Operations.READ)


def is_parameter_writable(*, parameter_data: ParameterData) -> bool:
    """Return if a parameter supports WRITE operations."""
    return bool(parameter_data.get("OPERATIONS", Operations.NONE) & Operations.WRITE)


def has_parameter_events(*, parameter_data: ParameterData) -> bool:
    """Return if a parameter supports EVENT operations."""
    return bool(parameter_data.get("OPERATIONS", Operations.NONE) & Operations.EVENT)


def resolve_enum_value(*, parameter_data: ParameterData, index: int) -> str | None:
    """
    Resolve an enum index to its string value.

    Returns ``None`` when the parameter has no ``VALUE_LIST`` or the *index*
    is out of range.
    """
    if (value_list := parameter_data.get("VALUE_LIST")) is None:
        return None
    values = tuple(value_list)
    if 0 <= index < len(values):
        return values[index]
    return None


def resolve_enum_index(*, parameter_data: ParameterData, value: str) -> int | None:
    """
    Resolve an enum string value to its index.

    Returns ``None`` when the parameter has no ``VALUE_LIST`` or *value* is
    not found.
    """
    if (value_list := parameter_data.get("VALUE_LIST")) is None:
        return None
    values = tuple(value_list)
    try:
        return values.index(value)
    except ValueError:
        return None


def get_parameter_step(*, parameter_data: ParameterData) -> float | None:
    """
    Return the step size for numeric parameters.

    For ``FLOAT`` parameters the step depends on the effective range:

    * range <= 7   -> 0.5
    * range <= 100 -> 1.0
    * range > 100  -> ``range / 100`` (rounded to one decimal)

    For ``INTEGER`` parameters the step is always ``1``.

    Returns ``None`` for all other parameter types.
    """
    param_type = parameter_data.get("TYPE")
    if param_type == ParameterType.INTEGER:
        return 1

    if param_type == ParameterType.FLOAT:
        p_min = parameter_data.get("MIN")
        p_max = parameter_data.get("MAX")
        if p_min is None or p_max is None:
            return 0.5
        value_range = float(p_max) - float(p_min)
        if value_range <= 7:
            return 0.5
        if value_range <= 100:
            return 1.0
        return round(value_range / 100, 1)

    return None


# ---------------------------------------------------------------------------
# ParameterValidator -- value validation and coercion
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Result of a parameter value validation."""

    valid: bool
    reason: str = ""


def validate_value(*, parameter_data: ParameterData, value: Any) -> ValidationResult:
    """
    Validate a value against its parameter description.

    Checks type compatibility and range constraints.  Returns a
    ``ValidationResult`` with ``valid=True`` when the value is acceptable,
    or ``valid=False`` with a human-readable *reason* otherwise.
    """
    param_type = parameter_data.get("TYPE", ParameterType.EMPTY)

    if param_type == ParameterType.ACTION:
        # Write-only trigger -- any value is acceptable.
        return ValidationResult(valid=True)

    if param_type == ParameterType.BOOL:
        if not isinstance(value, bool):
            return ValidationResult(valid=False, reason=f"Expected bool, got {type(value).__name__}.")
        return ValidationResult(valid=True)

    if param_type in (ParameterType.INTEGER, ParameterType.FLOAT):
        if not isinstance(value, (int, float)):
            return ValidationResult(
                valid=False,
                reason=f"Expected numeric value, got {type(value).__name__}.",
            )
        p_min = parameter_data.get("MIN")
        p_max = parameter_data.get("MAX")
        if p_min is not None and value < p_min:
            return ValidationResult(valid=False, reason=f"Value {value} is below minimum {p_min}.")
        if p_max is not None and value > p_max:
            return ValidationResult(valid=False, reason=f"Value {value} is above maximum {p_max}.")
        return ValidationResult(valid=True)

    if param_type == ParameterType.STRING:
        if not isinstance(value, str):
            return ValidationResult(valid=False, reason=f"Expected str, got {type(value).__name__}.")
        return ValidationResult(valid=True)

    if param_type == ParameterType.ENUM:
        if isinstance(value, int):
            if (value_list := parameter_data.get("VALUE_LIST")) is not None:
                values = tuple(value_list)
                if not (0 <= value < len(values)):
                    return ValidationResult(
                        valid=False,
                        reason=f"Enum index {value} out of range [0, {len(values) - 1}].",
                    )
            return ValidationResult(valid=True)
        if isinstance(value, str):
            if (value_list := parameter_data.get("VALUE_LIST")) is not None and value not in tuple(value_list):
                return ValidationResult(
                    valid=False,
                    reason=f"Value '{value}' not in VALUE_LIST.",
                )
            return ValidationResult(valid=True)
        return ValidationResult(
            valid=False,
            reason=f"Expected int (index) or str (value) for ENUM, got {type(value).__name__}.",
        )

    # DUMMY / EMPTY / unknown -- cannot meaningfully validate.
    return ValidationResult(valid=True)


def validate_paramset(
    *,
    descriptions: Mapping[str, ParameterData],
    values: dict[str, Any],
) -> dict[str, ValidationResult]:
    """
    Validate all values in a paramset against their descriptions.

    Only entries that **fail** validation are returned.  An empty dict
    indicates that every value passed validation.
    """
    failures: dict[str, ValidationResult] = {}
    for parameter, value in values.items():
        if (parameter_data := descriptions.get(parameter)) is None:
            failures[parameter] = ValidationResult(valid=False, reason=f"Unknown parameter '{parameter}'.")
            continue
        result = validate_value(parameter_data=parameter_data, value=value)
        if not result.valid:
            failures[parameter] = result
    return failures


def coerce_value(*, parameter_data: ParameterData, value: Any) -> Any:
    """
    Coerce a value to the correct type for a parameter.

    Performs safe type conversions where possible:

    * ``int`` -> ``float`` for ``FLOAT`` parameters.
    * ``float`` -> ``int`` (truncated) for ``INTEGER`` parameters.
    * ``str`` ``"true"``/``"false"`` -> ``bool`` for ``BOOL`` parameters.
    * ``str`` -> ``int`` index for ``ENUM`` parameters when the string is in
      the ``VALUE_LIST``.

    Returns the original *value* unchanged when no coercion rule applies.
    """
    param_type = parameter_data.get("TYPE", ParameterType.EMPTY)

    if param_type == ParameterType.FLOAT and isinstance(value, int) and not isinstance(value, bool):
        return float(value)

    if param_type == ParameterType.INTEGER and isinstance(value, float):
        return int(value)

    if param_type == ParameterType.BOOL and isinstance(value, str):
        lower = value.lower()
        if lower == "true":
            return True
        if lower == "false":
            return False

    if (
        param_type == ParameterType.ENUM
        and isinstance(value, str)
        and (index := resolve_enum_index(parameter_data=parameter_data, value=value)) is not None
    ):
        return index

    return value


# ---------------------------------------------------------------------------
# ParamsetDiff -- type-aware paramset comparison
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ParamsetChange:
    """A single parameter change in a paramset diff."""

    parameter: str
    old_value: Any
    new_value: Any


def _values_equal(*, param_type: ParameterType, old: Any, new: Any) -> bool:
    """
    Return if two values are equal using type-aware comparison.

    For ``FLOAT`` parameters numeric equality is used so that ``0 == 0.0``
    evaluates to ``True``.  For all other types standard equality is applied.
    """
    if param_type == ParameterType.FLOAT:
        try:
            return float(old) == float(new)
        except TypeError, ValueError:
            return bool(old == new)
    return bool(old == new)


def diff_paramset(
    *,
    descriptions: Mapping[str, ParameterData],
    baseline: Mapping[str, Any],
    current: Mapping[str, Any],
) -> dict[str, ParamsetChange]:
    """
    Compare two paramsets and return the differences.

    Uses type-aware comparison so that, for example, ``0.0`` and ``0`` are
    treated as equal for ``FLOAT`` parameters.

    Only parameters present in **both** *baseline* and *current* are compared.
    """
    changes: dict[str, ParamsetChange] = {}
    common_keys = set(baseline.keys()) & set(current.keys())
    for parameter in sorted(common_keys):
        old_value = baseline[parameter]
        new_value = current[parameter]
        param_data = descriptions.get(parameter)
        param_type = ParameterType(param_data["TYPE"]) if param_data and "TYPE" in param_data else ParameterType.EMPTY
        if not _values_equal(param_type=param_type, old=old_value, new=new_value):
            changes[parameter] = ParamsetChange(
                parameter=parameter,
                old_value=old_value,
                new_value=new_value,
            )
    return changes


# ---------------------------------------------------------------------------
# __all__
# ---------------------------------------------------------------------------

__all__ = tuple(
    sorted(
        name
        for name, obj in globals().items()
        if not name.startswith("_")
        and (name.isupper() or inspect.isfunction(obj) or inspect.isclass(obj))
        and getattr(obj, "__module__", __name__) == __name__
    )
)
