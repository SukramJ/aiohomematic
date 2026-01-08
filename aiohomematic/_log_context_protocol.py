# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Log context protocol interface.

This module is intentionally minimal to avoid circular imports.
It's imported by property_decorators.py which is near the bottom of the import chain.
"""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LogContextProtocol(Protocol):
    """
    Protocol for objects providing log context.

    Implemented by LogContextMixin and used by property_decorators.py
    to avoid circular imports.
    """

    @property
    @abstractmethod
    def log_context(self) -> Mapping[str, Any]:
        """Return the log context for this object."""
