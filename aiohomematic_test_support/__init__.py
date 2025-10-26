"""
Module to support aiohomematic testing with a local client.

This support package is version-locked to the main aiohomematic package.
The version is sourced from aiohomematic.const.VERSION, and a matching
runtime dependency is declared dynamically via setuptools.
"""

from __future__ import annotations

from aiohomematic.const import VERSION as _AIOHM_VERSION

# Public version of this package, intentionally identical to aiohomematic
__version__ = _AIOHM_VERSION

# Dynamic dependencies for setuptools (PEP 621 via tool.setuptools.dynamic)
# Ensures we always install the same version of aiohomematic as this support package
__dependencies__ = [f"aiohomematic=={__version__}"]
