# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Loader for curated device-semantics classifications.

Small, hand-maintained device classifications shared across the stack.
The data is shipped by the
`openccu-data <https://github.com/sukramj/openccu-data>`_ package
(``openccu_data/data/device_semantics.json``) and accessed via its
``device_semantics`` module.

First classification: ``DOORBELL_MODELS`` — devices whose press/ring
channel is a doorbell rather than a generic button. Consumers map the
ring press of these devices onto their platform's doorbell semantics
(e.g. Home Assistant's standard ``ring`` event type).

Public API of this module is defined by __all__.
"""

from __future__ import annotations

from typing import Final

from openccu_data.device_semantics import doorbell_models

__all__ = ["DOORBELL_MODELS"]

DOORBELL_MODELS: Final[frozenset[str]] = doorbell_models()
