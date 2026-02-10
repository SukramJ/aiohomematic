# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Mixin classes for log context and payload introspection.

Public API of this module is defined by __all__.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aiohomematic.property_decorators import Kind, get_hm_property_by_kind, get_hm_property_by_log_context, hm_property

__all__ = [
    "LogContextMixin",
    "PayloadMixin",
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


class PayloadMixin:
    """Mixin to add payload methods to class."""

    __slots__ = ()

    @property
    def config_payload(self) -> Mapping[str, Any]:
        """Return the config payload."""
        return {
            key: value
            for key, value in get_hm_property_by_kind(data_object=self, kind=Kind.CONFIG).items()
            if value is not None
        }

    @property
    def info_payload(self) -> Mapping[str, Any]:
        """Return the info payload."""
        return {
            key: value
            for key, value in get_hm_property_by_kind(data_object=self, kind=Kind.INFO).items()
            if value is not None
        }

    @property
    def state_payload(self) -> Mapping[str, Any]:
        """Return the state payload."""
        return {
            key: value
            for key, value in get_hm_property_by_kind(data_object=self, kind=Kind.STATE).items()
            if value is not None
        }
