"""
Coordinator protocol interfaces.

This module defines protocol interfaces for accessing coordinator instances,
allowing components to depend on specific coordinators without coupling
to the full CentralUnit implementation.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from aiohomematic.central.cache_coordinator import CacheCoordinator
    from aiohomematic.central.client_coordinator import ClientCoordinator
    from aiohomematic.central.device_coordinator import DeviceCoordinator
    from aiohomematic.central.device_registry import DeviceRegistry
    from aiohomematic.central.event_coordinator import EventCoordinator
    from aiohomematic.central.hub_coordinator import HubCoordinator


@runtime_checkable
class CoordinatorProvider(Protocol):
    """
    Protocol for accessing coordinator instances.

    Implemented by CentralUnit.
    """

    @property
    @abstractmethod
    def cache_coordinator(self) -> CacheCoordinator:
        """Get cache coordinator."""

    @property
    @abstractmethod
    def client_coordinator(self) -> ClientCoordinator:
        """Get client coordinator."""

    @property
    @abstractmethod
    def device_coordinator(self) -> DeviceCoordinator:
        """Get device coordinator."""

    @property
    @abstractmethod
    def device_registry(self) -> DeviceRegistry:
        """Get device registry."""

    @property
    @abstractmethod
    def event_coordinator(self) -> EventCoordinator:
        """Get event coordinator."""

    @property
    @abstractmethod
    def hub_coordinator(self) -> HubCoordinator:
        """Get hub coordinator."""
