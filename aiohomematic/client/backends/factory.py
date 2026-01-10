# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Backend factory for creating appropriate backend instances.

Public API
----------
- create_backend: Factory function to create backend based on interface/version
"""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import TYPE_CHECKING, Final

from aiohomematic.client.backends.ccu import CcuBackend
from aiohomematic.client.backends.homegear import HomegearBackend
from aiohomematic.client.backends.json_ccu import JsonCcuBackend
from aiohomematic.client.backends.protocol import BackendOperationsProtocol
from aiohomematic.const import INTERFACES_REQUIRING_JSON_RPC_CLIENT, Interface

if TYPE_CHECKING:
    from aiohomematic.client.json_rpc import AioJsonRpcAioHttpClient
    from aiohomematic.client.rpc_proxy import BaseRpcProxy
    from aiohomematic.interfaces import ParamsetDescriptionProviderProtocol

__all__ = ["create_backend"]

_LOGGER: Final = logging.getLogger(__name__)


async def create_backend(
    *,
    interface: Interface,
    interface_id: str,
    version: str,
    proxy: BaseRpcProxy | None,
    proxy_read: BaseRpcProxy | None,
    json_rpc: AioJsonRpcAioHttpClient,
    paramset_provider: ParamsetDescriptionProviderProtocol,
    device_details_provider: Mapping[str, int],
    has_push_updates: bool,
) -> BackendOperationsProtocol:
    """
    Create the appropriate backend based on interface and version.

    Args:
        interface: The interface type (HMIP_RF, BIDCOS_RF, etc.)
        interface_id: Unique interface identifier
        version: Backend version string (from getVersion)
        proxy: XML-RPC proxy for write operations (None for JSON-only backends)
        proxy_read: XML-RPC proxy for read operations (None for JSON-only backends)
        json_rpc: JSON-RPC client
        paramset_provider: Provider for paramset descriptions
        device_details_provider: Mapping of address to rega_id for room/function lookup
        has_push_updates: Whether interface supports push updates (from config)

    Returns:
        Appropriate backend implementation.

    """
    backend: BackendOperationsProtocol

    # CCU-Jack: JSON-RPC only
    if interface in INTERFACES_REQUIRING_JSON_RPC_CLIENT:
        _LOGGER.debug(
            "CREATE_BACKEND: Creating JsonCcuBackend for interface %s",
            interface_id,
        )
        backend = JsonCcuBackend(
            interface=interface,
            interface_id=interface_id,
            json_rpc=json_rpc,
            paramset_provider=paramset_provider,
            has_push_updates=has_push_updates,
        )

    # Homegear/pydevccu: XML-RPC with Homegear extensions
    elif interface == Interface.BIDCOS_RF and ("Homegear" in version or "pydevccu" in version):
        if proxy is None or proxy_read is None:
            raise ValueError("Homegear backend requires XML-RPC proxies")  # i18n-exc: ignore
        _LOGGER.debug(
            "CREATE_BACKEND: Creating HomegearBackend for interface %s (version: %s)",
            interface_id,
            version,
        )
        backend = HomegearBackend(
            interface=interface,
            interface_id=interface_id,
            proxy=proxy,
            proxy_read=proxy_read,
            version=version,
            has_push_updates=has_push_updates,
        )

    # CCU: XML-RPC + JSON-RPC
    else:
        if proxy is None or proxy_read is None:
            raise ValueError("CCU backend requires XML-RPC proxies")  # i18n-exc: ignore
        _LOGGER.debug(
            "CREATE_BACKEND: Creating CcuBackend for interface %s",
            interface_id,
        )
        backend = CcuBackend(
            interface=interface,
            interface_id=interface_id,
            proxy=proxy,
            proxy_read=proxy_read,
            json_rpc=json_rpc,
            device_details_provider=device_details_provider,
            has_push_updates=has_push_updates,
        )

    await backend.initialize()
    return backend
