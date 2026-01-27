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

# Pydantic field_validators require a fixed signature (cls, v) that cannot use keyword-only args
__kwonly_check__ = False


from pydantic import BaseModel, ConfigDict, PrivateAttr, computed_field, model_validator

from aiohomematic import i18n
from aiohomematic.const import INTERFACE_RPC_SERVER_TYPE, INTERFACES_SUPPORTING_RPC_CALLBACK, Interface, RpcServerType
from aiohomematic.exceptions import ClientException


class InterfaceConfig(BaseModel):
    """Configuration for a single Homematic interface connection."""

    model_config = ConfigDict(frozen=False)

    central_name: str
    """Name of the central unit this interface belongs to."""

    interface: Interface
    """The interface type (e.g., HMIP_RF, BIDCOS_RF, CUXD)."""

    port: int | None = None
    """XML-RPC port (required for standard interfaces, ignored for CUxD/CCU-Jack)."""

    remote_path: str | None = None
    """Optional remote path for the interface."""

    _enabled: bool = PrivateAttr(default=True)
    """Whether this interface is enabled."""

    def __eq__(self, other: object) -> bool:
        """Check equality based on interface_id."""
        if not isinstance(other, InterfaceConfig):
            return NotImplemented
        return self.interface_id == other.interface_id

    def __hash__(self) -> int:
        """Return hash based on interface_id."""
        return hash(self.interface_id)

    @property
    def enabled(self) -> bool:
        """Return whether this interface is enabled."""
        return self._enabled

    @computed_field  # type: ignore[prop-decorator]
    @property
    def interface_id(self) -> str:
        """Return the unique interface identifier."""
        return f"{self.central_name}-{self.interface}"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def rpc_server(self) -> RpcServerType:
        """Return the RPC server type for this interface."""
        return INTERFACE_RPC_SERVER_TYPE[self.interface]

    def disable(self) -> None:
        """Disable the interface config."""
        self._enabled = False

    @model_validator(mode="after")
    def _validate_port(self) -> InterfaceConfig:
        """Validate port based on interface type."""
        if self.interface in INTERFACES_SUPPORTING_RPC_CALLBACK:
            # Standard interfaces (HmIP-RF, BidCos-RF, etc.) require a valid port
            if self.port is None or self.port <= 0:
                raise ClientException(
                    i18n.tr(
                        key="exception.client.interface_config.port_required",
                        interface=self.interface,
                    )
                )
        else:
            # CUxD/CCU-Jack: port is ignored (JSON-RPC uses HTTP/HTTPS on 80/443)
            object.__setattr__(self, "port", None)
        return self
