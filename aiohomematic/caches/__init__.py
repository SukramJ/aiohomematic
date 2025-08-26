# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025 Daniel Perna, SukramJ
"""
Cache packages for AioHomematic.

This package groups cache implementations used throughout the library:
- persistent: Long-lived on-disk caches for device and paramset descriptions.
- dynamic: Short-lived in-memory caches for runtime values and connection health.
- visibility: Parameter visibility rules to decide which parameters are relevant.
"""

from __future__ import annotations
