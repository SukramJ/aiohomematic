# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Validator functions used within aiohomematic.

Public API of this module is defined by __all__.
"""

from __future__ import annotations

import inspect

from aiohomematic import i18n
from aiohomematic.const import BLOCKED_CATEGORIES, CATEGORIES, HUB_CATEGORIES, DataPointCategory
from aiohomematic.exceptions import ValidationException


def validate_startup() -> None:
    """
    Validate enum and mapping exhaustiveness at startup.

    - Ensure DataPointCategory coverage: all categories except UNDEFINED must be present
      in either HUB_CATEGORIES or CATEGORIES. UNDEFINED must not appear in those lists.
    """
    categories_in_lists = set(BLOCKED_CATEGORIES) | set(CATEGORIES) | set(HUB_CATEGORIES)
    all_categories = set(DataPointCategory)
    if DataPointCategory.UNDEFINED in categories_in_lists:
        raise ValidationException(i18n.tr(key="exception.validator.undefined_in_lists"))

    if missing := all_categories - {DataPointCategory.UNDEFINED} - categories_in_lists:
        missing_str = ", ".join(sorted(c.value for c in missing))
        raise ValidationException(
            i18n.tr(
                key="exception.validator.categories.not_exhaustive",
                missing=missing_str,
            )
        )


# Define public API for this module
__all__ = tuple(
    sorted(
        name
        for name, obj in globals().items()
        if not name.startswith("_")
        and (inspect.isfunction(obj) or inspect.isclass(obj))
        and getattr(obj, "__module__", __name__) == __name__
    )
)
