# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Typed data structures for store caches.

This module provides typed cache entries and type aliases used across
the persistent and dynamic store implementations.

Type Aliases
------------
- ParameterMap: Parameter name to ParameterData mapping
- ParamsetMap: ParamsetKey to ParameterMap mapping
- ChannelParamsetMap: Channel address to ParamsetMap mapping
- InterfaceParamsetMap: Interface ID to ChannelParamsetMap mapping

Cache Entry Types
-----------------
- CachedCommand: Command cache entry with value and timestamp
- PongEntry: Ping/pong tracking entry with token and seen time
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, TypeAlias

if TYPE_CHECKING:
    from aiohomematic.const import ParameterData, ParamsetKey

# =============================================================================
# Type Aliases for Paramset Description Cache
# =============================================================================
# These aliases describe the nested structure of paramset descriptions:
# InterfaceParamsetMap[interface_id][channel_address][paramset_key][parameter] = ParameterData

ParameterMap: TypeAlias = dict[str, "ParameterData"]
ParamsetMap: TypeAlias = dict["ParamsetKey", ParameterMap]
ChannelParamsetMap: TypeAlias = dict[str, ParamsetMap]
InterfaceParamsetMap: TypeAlias = dict[str, ChannelParamsetMap]


# =============================================================================
# Cache Entry Dataclasses
# =============================================================================


@dataclass(frozen=True, slots=True)
class CachedCommand:
    """
    Cached command entry for tracking sent commands.

    Attributes:
        value: The value that was sent with the command.
        sent_at: Timestamp when the command was sent.

    """

    value: Any
    sent_at: datetime


@dataclass(slots=True)
class PongTracker:
    """
    Tracker for pending or unknown pong tokens.

    Used by PingPongCache to track ping/pong events with timestamps
    for TTL expiry and size limit enforcement.

    Attributes:
        tokens: Set of pong tokens being tracked.
        seen_at: Mapping of token to monotonic timestamp when it was seen.
        logged: Whether a warning has been logged for this tracker.

    """

    tokens: set[str]
    seen_at: dict[str, float]
    logged: bool = False

    def __len__(self) -> int:
        """Return the number of tracked tokens."""
        return len(self.tokens)

    def add(self, *, token: str, timestamp: float) -> None:
        """Add a token with its timestamp."""
        self.tokens.add(token)
        self.seen_at[token] = timestamp

    def clear(self) -> None:
        """Clear all tokens and timestamps."""
        self.tokens.clear()
        self.seen_at.clear()
        self.logged = False

    def contains(self, *, token: str) -> bool:
        """Check if a token is being tracked."""
        return token in self.tokens

    def remove(self, *, token: str) -> None:
        """Remove a token and its timestamp."""
        self.tokens.discard(token)
        self.seen_at.pop(token, None)
