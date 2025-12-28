# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Minimal protocol interfaces for metrics aggregation.

This private module defines minimal protocol interfaces used by MetricsAggregator.
Located in metrics/ (not interfaces/) to avoid circular imports during initialization.

Import path: aiohomematic.interfaces (public) or aiohomematic.metrics._protocols (internal)

These protocols are:
- Re-exported via interfaces/__init__.py for public use
- Extended by full protocols (DeviceProviderProtocol, ClientProviderProtocol,
  HubDataPointManagerProtocol) in interfaces/central.py and interfaces/client.py

IMPORTANT: This module must NOT import from interfaces/ to avoid circular imports.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class DeviceProviderForMetricsProtocol(Protocol):
    """
    Minimal protocol for device access in metrics context.

    Provides only the `devices` property needed by MetricsAggregator
    to collect model statistics without requiring the full DeviceProviderProtocol.

    Implemented by CentralUnit.
    """

    @property
    @abstractmethod
    def devices(self) -> tuple[Any, ...]:
        """Return all registered devices."""


@runtime_checkable
class ClientProviderForMetricsProtocol(Protocol):
    """
    Minimal protocol for client access in metrics context.

    Provides only the `clients` property needed by MetricsAggregator
    to collect RPC metrics without requiring the full ClientProviderProtocol.

    Implemented by CentralUnit.
    """

    @property
    @abstractmethod
    def clients(self) -> tuple[Any, ...]:
        """Return all connected clients."""


@runtime_checkable
class HubDataPointManagerForMetricsProtocol(Protocol):
    """
    Minimal protocol for hub data point access in metrics context.

    Provides only the properties needed by MetricsAggregator to collect
    program/sysvar counts without requiring the full HubDataPointManagerProtocol.

    Implemented by HubCoordinator.
    """

    @property
    @abstractmethod
    def program_data_points(self) -> tuple[Any, ...]:
        """Return all program data points."""

    @property
    @abstractmethod
    def sysvar_data_points(self) -> tuple[Any, ...]:
        """Return all system variable data points."""
