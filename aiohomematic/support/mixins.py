# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Mixin classes for log context introspection.

Public API of this module is defined by __all__.
"""

from collections.abc import Mapping
from typing import Any

from aiohomematic.property_decorators import get_hm_property_by_log_context, hm_property

__all__ = [
    "LogContextMixin",
]


class LogContextMixin:
    """Mixin to add log context methods to class."""

    __slots__ = ("_cached_log_context",)

    @hm_property(cached=True)
    def log_context(self) -> Mapping[str, Any]:
        """Return the log context for this object."""
        return {
            key: value for key, value in get_hm_property_by_log_context(data_object=self).items() if value is not None
        }
