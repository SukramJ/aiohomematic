# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Interface configuration for Homematic client connections.

This module provides configuration for individual Homematic interface
connections (e.g., BidCos-RF, HmIP-RF, VirtualDevices).

Public API
----------
- InterfaceConfig: Configuration for a single interface connection including
  port, remote path, and RPC server type.

Each InterfaceConfig represents one communication channel to the backend,
identified by a unique interface_id derived from the central name and
interface type.
"""

from __future__ import annotations

from typing import Final

from aiohomematic import i18n
from aiohomematic.const import INTERFACE_RPC_SERVER_TYPE, INTERFACES_SUPPORTING_RPC_CALLBACK, Interface, RpcServerType
from aiohomematic.exceptions import ClientException
from aiohomematic.property_decorators import DelegatedProperty


class InterfaceConfig:
    """Configuration for a single Homematic interface connection."""

    def __init__(
        self,
        *,
        central_name: str,
        interface: Interface,
        port: int,
        remote_path: str | None = None,
    ) -> None:
        """Initialize the interface configuration."""
        self.interface: Final[Interface] = interface

        self.rpc_server: Final[RpcServerType] = INTERFACE_RPC_SERVER_TYPE[interface]
        self.interface_id: Final[str] = f"{central_name}-{self.interface}"
        self.port: Final = port
        self.remote_path: Final = remote_path
        self._init_validate()
        self._enabled: bool = True

    enabled: Final = DelegatedProperty[bool](path="_enabled")

    def disable(self) -> None:
        """Disable the interface config."""
        self._enabled = False

    def _init_validate(self) -> None:
        """Validate the client_config."""
        if not self.port and self.interface in INTERFACES_SUPPORTING_RPC_CALLBACK:
            raise ClientException(
                i18n.tr(
                    key="exception.client.interface_config.port_required",
                    interface=self.interface,
                )
            )
