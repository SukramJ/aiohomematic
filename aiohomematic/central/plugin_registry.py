# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Plugin registry for managing client plugins.

Plugins are discovered via entry points and registered here for use
by the backend factory when creating clients for specific interfaces.
"""

from __future__ import annotations

import asyncio
import importlib.metadata
import logging
from typing import TYPE_CHECKING, Final

from aiohomematic.central.plugin_validator import validate_and_raise

if TYPE_CHECKING:
    from aiohomematic.interfaces.plugin import ClientPluginProtocol

_LOGGER: Final = logging.getLogger(__name__)

# Entry point group for plugin discovery
PLUGIN_ENTRY_POINT_GROUP: Final = "aiohomematic.plugins"


class PluginRegistry:
    """Registry for client plugins."""

    __slots__ = ("_interface_to_plugin", "_plugins")

    def __init__(self) -> None:
        """Initialize the plugin registry."""
        self._plugins: dict[str, ClientPluginProtocol] = {}
        self._interface_to_plugin: dict[str, ClientPluginProtocol] = {}

    @property
    def handled_interfaces(self) -> frozenset[str]:
        """Return all interfaces handled by plugins."""
        return frozenset(self._interface_to_plugin.keys())

    @property
    def plugins(self) -> dict[str, ClientPluginProtocol]:
        """Return all registered plugins."""
        return dict(self._plugins)

    def get_plugin_for_interface(self, *, interface: str) -> ClientPluginProtocol | None:
        """Return the plugin handling the given interface, or None."""
        return self._interface_to_plugin.get(interface)

    def has_plugin_for_interface(self, *, interface: str) -> bool:
        """Return True if a plugin handles the given interface."""
        return interface in self._interface_to_plugin

    def register(self, *, plugin: ClientPluginProtocol, validate: bool = True) -> None:
        """
        Register a plugin.

        Args:
            plugin: The plugin to register.
            validate: Whether to validate the plugin contract before registration.
                      Set to False only for testing purposes.

        Raises:
            TypeError: If validation is enabled and the plugin fails contract validation.

        """
        if plugin.name in self._plugins:
            _LOGGER.warning("Plugin %s already registered, skipping", plugin.name)  # i18n-log: ignore
            return

        # Validate plugin contract before registration
        if validate:
            validate_and_raise(plugin=plugin)

        self._plugins[plugin.name] = plugin

        for interface in plugin.supported_interfaces:
            if interface in self._interface_to_plugin:
                existing = self._interface_to_plugin[interface]
                _LOGGER.warning(  # i18n-log: ignore
                    "Interface %s already handled by plugin %s, overriding with %s",
                    interface,
                    existing.name,
                    plugin.name,
                )
            self._interface_to_plugin[interface] = plugin

        _LOGGER.info("Registered plugin: %s v%s", plugin.name, plugin.version)  # i18n-log: ignore

    def unregister(self, *, plugin_name: str) -> None:
        """Unregister a plugin."""
        if plugin_name not in self._plugins:
            return

        plugin = self._plugins.pop(plugin_name)
        for interface in plugin.supported_interfaces:
            if self._interface_to_plugin.get(interface) == plugin:
                del self._interface_to_plugin[interface]

        _LOGGER.info("Unregistered plugin: %s", plugin_name)  # i18n-log: ignore


def _discover_plugins_sync() -> list[ClientPluginProtocol]:
    """Discover all installed plugins via entry points (blocking - run in executor)."""
    plugins: list[ClientPluginProtocol] = []

    try:
        entry_points = importlib.metadata.entry_points(group=PLUGIN_ENTRY_POINT_GROUP)
    except TypeError:
        # Python < 3.10 compatibility (should not happen with Python 3.13+)
        _LOGGER.debug("Entry points API not available")
        return plugins

    for ep in entry_points:
        try:
            plugin_factory = ep.load()
            plugin: ClientPluginProtocol = plugin_factory()
            plugins.append(plugin)
            _LOGGER.debug(
                "Discovered plugin: %s v%s from entry point %s",
                plugin.name,
                plugin.version,
                ep.name,
            )
        except Exception as exc:
            _LOGGER.warning(  # i18n-log: ignore
                "Failed to load plugin from entry point %s: %s",
                ep.name,
                exc,
            )

    return plugins


async def discover_plugins_async() -> list[ClientPluginProtocol]:
    """Discover all installed plugins via entry points asynchronously."""
    return await asyncio.to_thread(_discover_plugins_sync)


async def discover_and_register_plugins_async(*, registry: PluginRegistry) -> None:
    """Discover and register all installed plugins asynchronously."""
    for plugin in await discover_plugins_async():
        registry.register(plugin=plugin)


# Synchronous versions (for backwards compatibility - avoid using in async context)
def discover_plugins() -> list[ClientPluginProtocol]:
    """Discover all installed plugins via entry points (blocking)."""
    return _discover_plugins_sync()


def discover_and_register_plugins(*, registry: PluginRegistry) -> None:
    """Discover and register all installed plugins (blocking)."""
    for plugin in discover_plugins():
        registry.register(plugin=plugin)
