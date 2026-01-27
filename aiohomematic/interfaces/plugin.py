# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Protocol definitions for client plugins.

Plugins provide backend implementations for specific Homematic interfaces.
They are discovered via entry points and loaded on demand.
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from aiohttp import ClientSession


class PluginState(StrEnum):
    """Plugin lifecycle states."""

    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class PluginConfig:
    """Configuration passed to plugins during backend creation."""

    # Connection settings
    host: str
    port: int
    username: str
    password: str
    tls: bool
    verify_tls: bool
    device_url: str

    # Session management
    client_session: ClientSession | None

    # Runtime configuration
    has_push_updates: bool


@runtime_checkable
class ClientPluginProtocol(Protocol):
    """Protocol for client plugins that provide backend implementations."""

    @property
    @abstractmethod
    def is_running(self) -> bool:
        """Return True if the plugin is running."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the plugin name."""

    @property
    @abstractmethod
    def state(self) -> PluginState:
        """Return the current plugin state."""

    @property
    @abstractmethod
    def supported_interfaces(self) -> frozenset[str]:
        """Return the interface names this plugin supports."""

    @property
    @abstractmethod
    def version(self) -> str:
        """Return the plugin version."""

    @abstractmethod
    async def create_backend(
        self,
        *,
        interface: str,
        interface_id: str,
        username: str,
        password: str,
        device_url: str,
        client_session: ClientSession | None = None,
        tls: bool = False,
        verify_tls: bool = False,
        has_push_updates: bool = True,
    ) -> Any:
        """Create a backend instance for the given interface."""

    @abstractmethod
    def get_diagnostics(self) -> dict[str, Any]:
        """Return diagnostic information about the plugin."""

    @abstractmethod
    async def start(self) -> None:
        """Start the plugin (initialize resources)."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the plugin (cleanup resources)."""
