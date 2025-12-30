# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
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
    from aiohomematic.central import DeviceRegistry
    from aiohomematic.central.coordinators import (
        CacheCoordinator,
        ClientCoordinator,
        DeviceCoordinator,
        EventCoordinator,
        HubCoordinator,
    )


@runtime_checkable
class CoordinatorProviderProtocol(Protocol):
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
