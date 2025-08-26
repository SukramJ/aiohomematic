# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025 Daniel Perna, SukramJ
"""Collection of context variables."""

from __future__ import annotations

from contextvars import ContextVar

# context var for storing if call is running within a service
IN_SERVICE_VAR: ContextVar[bool] = ContextVar("in_service_var", default=False)
