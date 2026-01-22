"""
Mixins for model classes.

This package provides reusable mixin classes that share common functionality
across different data point implementations.

Public API of this module is defined by __all__.
"""

from __future__ import annotations

from aiohomematic.model.mixins.sensor_value import SensorValueMixin

__all__ = [
    "SensorValueMixin",
]
