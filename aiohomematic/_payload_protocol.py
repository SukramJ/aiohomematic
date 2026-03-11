# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Payload protocol interface.

This module is intentionally minimal to avoid circular imports.
It's imported by support/mixins.py and interfaces/model.py which are
at different points in the import chain.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class PayloadProtocol(Protocol):
    """
    Protocol for payload introspection.

    Guarantees that config_payload, info_payload, and state_payload
    are available. Implemented via PayloadMixin.

    Note: Properties are defined without @abstractmethod to avoid ABC
    enforcement conflicts with PayloadMixin in multiple inheritance chains.
    Protocol structural subtyping ensures type safety.
    """

    __slots__ = ()

    @property
    def config_payload(self) -> Mapping[str, Any]:
        """Return the config payload."""

    @property
    def info_payload(self) -> Mapping[str, Any]:
        """Return the info payload."""

    @property
    def state_payload(self) -> Mapping[str, Any]:
        """Return the state payload."""
