# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Backend detection module for aiohomematic.

Detect Homematic backend type (CCU or Homegear/PyDevCCU) and discover
available interfaces without requiring a fully initialized environment.

Public API of this module is defined by __all__.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import logging
from ssl import SSLContext
from typing import Final, cast
from xmlrpc.client import ServerProxy

from aiohttp import ClientSession

from aiohomematic import i18n
from aiohomematic.client.json_rpc import AioJsonRpcAioHttpClient
from aiohomematic.const import (
    DETECTION_PORT_BIDCOS_RF,
    DETECTION_PORT_BIDCOS_WIRED,
    DETECTION_PORT_HMIP_RF,
    DETECTION_PORT_JSON_RPC,
    ISO_8859_1,
    Backend,
    Interface,
)
from aiohomematic.support import build_xml_rpc_headers, build_xml_rpc_uri, get_tls_context

__all__ = [
    "BackendDetectionResult",
    "DetectionConfig",
    "detect_backend",
]

_LOGGER: Final = logging.getLogger(__name__)

# Detection timeout (shorter than normal operation)
_DETECTION_TIMEOUT: Final = 5.0

# XML-RPC method names
_XML_METHOD_GET_VERSION: Final = "getVersion"


@dataclass(frozen=True, kw_only=True, slots=True)
class DetectionConfig:
    """Configuration for backend detection."""

    host: str
    username: str = ""
    password: str = ""
    request_timeout: float = _DETECTION_TIMEOUT
    verify_tls: bool = False


@dataclass(frozen=True, kw_only=True, slots=True)
class BackendDetectionResult:
    """Result of backend detection."""

    backend: Backend
    available_interfaces: tuple[Interface, ...]
    detected_port: int
    tls: bool
    host: str
    version: str | None = None
    auth_enabled: bool | None = None


async def detect_backend(
    *,
    config: DetectionConfig,
    client_session: ClientSession | None = None,
) -> BackendDetectionResult | None:
    """
    Detect backend type and available interfaces.

    Probe XML-RPC ports to find a working connection, determine if the backend
    is CCU or Homegear/PyDevCCU, and query available interfaces.

    Args:
        config: Detection configuration with host and credentials.
        client_session: Optional aiohttp ClientSession for JSON-RPC requests.

    Returns:
        BackendDetectionResult if a backend was found, None otherwise.

    """
    _LOGGER.info(i18n.tr("log.backend_detection.detect_backend.starting", host=config.host))

    # Define ports to probe: (Interface, port, tls)
    ports_to_probe: list[tuple[Interface, int, bool]] = [
        # Try non-TLS ports first
        (Interface.HMIP_RF, DETECTION_PORT_HMIP_RF[0], False),
        (Interface.BIDCOS_RF, DETECTION_PORT_BIDCOS_RF[0], False),
        (Interface.BIDCOS_WIRED, DETECTION_PORT_BIDCOS_WIRED[0], False),
        # Then TLS ports
        (Interface.HMIP_RF, DETECTION_PORT_HMIP_RF[1], True),
        (Interface.BIDCOS_RF, DETECTION_PORT_BIDCOS_RF[1], True),
        (Interface.BIDCOS_WIRED, DETECTION_PORT_BIDCOS_WIRED[1], True),
    ]

    for interface, port, tls in ports_to_probe:
        _LOGGER.info(
            i18n.tr(
                "log.backend_detection.detect_backend.probing",
                host=config.host,
                port=port,
                tls=tls,
                interface=interface,
            )
        )

        version = await _probe_xml_rpc_port(
            host=config.host,
            port=port,
            tls=tls,
            username=config.username,
            password=config.password,
            verify_tls=config.verify_tls,
            request_timeout=config.request_timeout,
        )

        if version is None:
            continue

        _LOGGER.info(i18n.tr("log.backend_detection.detect_backend.found_version", version=version, port=port))

        # Determine backend type from version string
        backend = _determine_backend(version=version)
        _LOGGER.info(i18n.tr("log.backend_detection.detect_backend.backend_type", backend=backend))

        if backend in (Backend.HOMEGEAR, Backend.PYDEVCCU):
            # Homegear/PyDevCCU only supports BidCos-RF
            return BackendDetectionResult(
                backend=backend,
                available_interfaces=(Interface.BIDCOS_RF,),
                detected_port=port,
                tls=tls,
                host=config.host,
                version=version,
                auth_enabled=None,
            )

        # CCU: Query JSON-RPC for available interfaces
        interfaces, auth_enabled = await _query_ccu_interfaces(
            host=config.host,
            username=config.username,
            password=config.password,
            verify_tls=config.verify_tls,
            client_session=client_session,
        )

        if interfaces:
            _LOGGER.info(i18n.tr("log.backend_detection.detect_backend.found_interfaces", interfaces=interfaces))
        else:
            # Fallback: use the interface we connected to
            _LOGGER.info(i18n.tr("log.backend_detection.detect_backend.json_rpc_fallback"))
            interfaces = (interface,)

        return BackendDetectionResult(
            backend=Backend.CCU,
            available_interfaces=interfaces,
            detected_port=port,
            tls=tls,
            host=config.host,
            version=version,
            auth_enabled=auth_enabled,
        )

    _LOGGER.info(i18n.tr("log.backend_detection.detect_backend.no_backend_found", host=config.host))
    return None


def _determine_backend(*, version: str) -> Backend:
    """Determine backend type from version string."""
    version_lower = version.lower()
    if "homegear" in version_lower:
        return Backend.HOMEGEAR
    if "pydevccu" in version_lower:
        return Backend.PYDEVCCU
    return Backend.CCU


async def _probe_xml_rpc_port(
    *,
    host: str,
    port: int,
    tls: bool,
    username: str,
    password: str,
    verify_tls: bool,
    request_timeout: float,
) -> str | None:
    """
    Probe a single XML-RPC port and return the version string if successful.

    Returns:
        Version string if connection successful, None otherwise.

    """
    uri = build_xml_rpc_uri(host=host, port=port, path=None, tls=tls)
    headers = build_xml_rpc_headers(username=username, password=password) if username else []
    context: SSLContext | None = get_tls_context(verify_tls=verify_tls) if tls else None

    def _sync_probe() -> str | None:
        """Run synchronous XML-RPC probe in thread pool."""
        try:
            proxy = ServerProxy(
                uri=uri,
                encoding=ISO_8859_1,
                headers=headers,
                context=context,
            )

            # First try to list methods to verify connection
            methods = cast(list[str], proxy.system.listMethods())

            if _XML_METHOD_GET_VERSION in methods:
                return cast(str, proxy.getVersion())

            # If getVersion not available, return empty string to indicate connection worked
            return ""  # noqa: TRY300

        except Exception as exc:  # noqa: BLE001
            _LOGGER.info(
                i18n.tr(
                    "log.backend_detection.xml_rpc.probe_failed",
                    host=host,
                    port=port,
                    exc_type=type(exc).__name__,
                    reason=exc,
                )
            )
            return None

    try:
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="backend_detect") as executor:
            return await asyncio.wait_for(
                loop.run_in_executor(executor, _sync_probe),
                timeout=request_timeout,
            )
    except TimeoutError:
        _LOGGER.info(i18n.tr("log.backend_detection.xml_rpc.probe_timeout", host=host, port=port))
        return None
    except Exception as exc:  # noqa: BLE001
        _LOGGER.info(
            i18n.tr(
                "log.backend_detection.xml_rpc.probe_error",
                host=host,
                port=port,
                exc_type=type(exc).__name__,
                reason=exc,
            )
        )
        return None


async def _query_ccu_interfaces(
    *,
    host: str,
    username: str,
    password: str,
    verify_tls: bool,
    client_session: ClientSession | None,
) -> tuple[tuple[Interface, ...], bool | None]:
    """
    Query CCU for available interfaces via JSON-RPC.

    Uses AioJsonRpcAioHttpClient to query system information.
    Tries both HTTP (port 80) and HTTPS (port 443).

    Returns:
        Tuple of (interfaces, auth_enabled). Returns empty tuple if query fails.

    """
    for port, tls in DETECTION_PORT_JSON_RPC:
        result = await _query_json_rpc_interfaces(
            host=host,
            port=port,
            tls=tls,
            username=username,
            password=password,
            verify_tls=verify_tls,
            client_session=client_session,
        )
        if result is not None:
            return result

    return ((), None)


async def _query_json_rpc_interfaces(
    *,
    host: str,
    port: int,
    tls: bool,
    username: str,
    password: str,
    verify_tls: bool,
    client_session: ClientSession | None,
) -> tuple[tuple[Interface, ...], bool | None] | None:
    """
    Query interfaces via JSON-RPC on a specific port using AioJsonRpcAioHttpClient.

    Returns:
        Tuple of (interfaces, auth_enabled) if successful, None if failed.

    """
    scheme = "https" if tls else "http"
    device_url = f"{scheme}://{host}:{port}"

    _LOGGER.info(i18n.tr("log.backend_detection.json_rpc.querying", url=device_url))

    json_rpc_client: AioJsonRpcAioHttpClient | None = None
    try:
        json_rpc_client = AioJsonRpcAioHttpClient(
            username=username,
            password=password,
            device_url=device_url,
            client_session=client_session,
            tls=tls,
            verify_tls=verify_tls,
        )

        system_info = await json_rpc_client.get_system_information()

        # Convert interface strings to Interface enums
        interfaces: list[Interface] = []
        for iface_name in system_info.available_interfaces:
            try:
                interfaces.append(Interface(iface_name))
            except ValueError:
                _LOGGER.info(i18n.tr("log.backend_detection.json_rpc.unknown_interface", interface=iface_name))

        return (tuple(interfaces), system_info.auth_enabled)  # noqa: TRY300

    except Exception as exc:  # noqa: BLE001
        _LOGGER.info(
            i18n.tr(
                "log.backend_detection.json_rpc.query_failed",
                url=device_url,
                exc_type=type(exc).__name__,
                reason=exc,
            )
        )
        return None
    finally:
        if json_rpc_client:
            await json_rpc_client.logout()
