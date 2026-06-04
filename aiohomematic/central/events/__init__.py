# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Events sub-package for the central event system.

This package contains the EventBus dispatch machinery. The event payload
**types** live in ``aiohomematic.event_types`` (so the domain model and metrics
layers can consume them without importing ``aiohomematic.central``); import
event dataclasses from there, not from here.

Public API of this module is defined by __all__.
"""

from aiohomematic.central.events.bus import (
    AsyncEventHandlerProtocol,
    EventBatch,
    EventBus,
    HandlerStats,
    SubscriptionGroup,
    SyncEventHandlerProtocol,
)

__all__ = [
    # EventBus dispatch machinery
    "AsyncEventHandlerProtocol",
    "EventBatch",
    "EventBus",
    "HandlerStats",
    "SubscriptionGroup",
    "SyncEventHandlerProtocol",
]
