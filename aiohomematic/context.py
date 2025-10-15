# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Collection of context variables.

Public API of this module is defined by __all__.
"""

from __future__ import annotations

from contextvars import ContextVar

# context var for storing if call is running within a service
IN_SERVICE_VAR: ContextVar[bool] = ContextVar("in_service_var", default=False)


# Define public API for this module
__all__ = ["IN_SERVICE_VAR"]
