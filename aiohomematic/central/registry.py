# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Thread-safe registry for CentralUnit instances.

Provides atomic operations for registration, deregistration, and iteration
that are safe for both GIL-enabled and free-threaded Python builds.

Public API of this module is defined by __all__.
"""

from __future__ import annotations

from collections.abc import Iterator
import threading
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from aiohomematic.central.central_unit import CentralUnit


class CentralRegistry:
    """
    Thread-safe registry for CentralUnit instances.

    Uses copy-on-read pattern for iteration safety:
    - Writers hold lock and modify internal dict
    - Readers get snapshot copy (no lock needed for iteration)

    This pattern is optimal for:
    - Rare writes (init/stop)
    - Frequent reads (signal handler, get_client)
    - Safe iteration during concurrent modification
    """

    __slots__ = ("_instances", "_lock")

    def __init__(self) -> None:
        """Initialize the registry."""
        self._instances: dict[str, CentralUnit] = {}
        self._lock: Final = threading.Lock()

    def __contains__(self, name: str) -> bool:  # kwonly: disable
        """Check if a name is registered."""
        with self._lock:
            return name in self._instances

    def __iter__(self) -> Iterator[str]:
        """Iterate over registered names (snapshot)."""
        with self._lock:
            return iter(list(self._instances.keys()))

    def __len__(self) -> int:
        """Return number of registered instances."""
        with self._lock:
            return len(self._instances)

    def get(self, *, name: str) -> CentralUnit | None:
        """
        Get a CentralUnit by name.

        Args:
            name: Name of the central unit

        Returns:
            CentralUnit instance or None if not found

        """
        with self._lock:
            return self._instances.get(name)

    def register(self, *, name: str, central: CentralUnit) -> None:
        """
        Register a CentralUnit instance.

        Thread-safe. Overwrites existing entry with same name.

        Args:
            name: Unique name for the central unit
            central: CentralUnit instance to register

        """
        with self._lock:
            self._instances[name] = central

    def unregister(self, *, name: str) -> bool:
        """
        Unregister a CentralUnit instance by name.

        Thread-safe. Returns True if instance was removed, False if not found.

        Args:
            name: Name of the central unit to unregister

        Returns:
            True if instance was removed, False if not found

        """
        with self._lock:
            if name in self._instances:
                del self._instances[name]
                return True
            return False

    def values(self) -> list[CentralUnit]:
        """
        Return a snapshot list of all registered CentralUnit instances.

        Returns a copy, safe to iterate even during concurrent modifications.
        This is the recommended way to iterate over instances.

        Returns:
            List of all registered CentralUnit instances

        """
        with self._lock:
            return list(self._instances.values())


# Global singleton instance
CENTRAL_REGISTRY: Final = CentralRegistry()


__all__ = [
    "CENTRAL_REGISTRY",
    "CentralRegistry",
]
