# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Backend detection module for aiohomematic.

Detect Homematic backend type (CCU or Homegear/PyDevCCU) and discover
available interfaces without requiring a fully initialized environment.

Public API of this module is defined by __all__.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import errno
import logging
from typing import Final

from aiohttp import ClientSession

from aiohomematic import i18n
from aiohomematic.central import CentralConnectionState
from aiohomematic.client import AioJsonRpcAioHttpClient
from aiohomematic.client.rpc_proxy import AioXmlRpcProxy
from aiohomematic.const import (
    DEFAULT_TIMEOUT_CONFIG,
    DETECTION_PORT_BIDCOS_RF,
    DETECTION_PORT_BIDCOS_WIRED,
    DETECTION_PORT_HMIP_RF,
    DETECTION_PORT_JSON_RPC,
    Backend,
    Interface,
    TimeoutConfig,
)
from aiohomematic.exceptions import AuthFailure, BaseHomematicException, NoConnectionException
from aiohomematic.support import build_xml_rpc_headers, build_xml_rpc_uri, validate_host

__all__ = [
    "BackendDetectionResult",
    "DetectionConfig",
    "detect_backend",
]

_LOGGER: Final = logging.getLogger(__name__)

# XML-RPC method names
_XML_METHOD_GET_VERSION: Final = "getVersion"

# Sentinel value to signal that detection should abort (host unreachable)
_ABORT_DETECTION: Final = object()


@dataclass(frozen=True, kw_only=True, slots=True)
class DetectionConfig:
    """Configuration for backend detection."""

    host: str
    username: str = ""
    password: str = ""
    request_timeout: float = DEFAULT_TIMEOUT_CONFIG.backend_detection_request
    total_timeout: float = DEFAULT_TIMEOUT_CONFIG.backend_detection_total
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
    https_redirect_enabled: bool | None = None


async def detect_backend(
    *,
    config: DetectionConfig,
    client_session: ClientSession | None = None,
    timeout_config: TimeoutConfig | None = None,
) -> BackendDetectionResult | None:
    """
    Detect backend type and available interfaces.

    Probe XML-RPC ports to find a working connection, determine if the backend
    is CCU or Homegear/PyDevCCU, and query available interfaces.

    Args:
        config: Detection configuration with host and credentials.
        client_session: Optional aiohttp ClientSession for JSON-RPC requests.
        timeout_config: Optional timeout configuration. If provided, overrides config's timeouts.

    Returns:
        BackendDetectionResult if a backend was found, None otherwise.

    Raises:
        ValidationException: If host format is invalid.
        AuthFailure: If authentication fails with the provided credentials.

    """
    # Apply timeout_config if provided
    if timeout_config is not None:
        effective_config = DetectionConfig(
            host=config.host,
            username=config.username,
            password=config.password,
            request_timeout=timeout_config.backend_detection_request,
            total_timeout=timeout_config.backend_detection_total,
            verify_tls=config.verify_tls,
        )
    else:
        effective_config = config

    # Validate input
    validate_host(host=effective_config.host)

    _LOGGER.info(
        i18n.tr(
            key="log.backend_detection.detect_backend.starting",
            host=effective_config.host,
            total_timeout=effective_config.total_timeout,
        )
    )

    try:
        async with asyncio.timeout(effective_config.total_timeout):
            return await _do_detect_backend(config=effective_config, client_session=client_session)
    except TimeoutError:
        _LOGGER.warning(
            i18n.tr(
                key="log.backend_detection.detect_backend.total_timeout",
                host=effective_config.host,
                total_timeout=effective_config.total_timeout,
            )
        )
        return None


async def _do_detect_backend(
    *,
    config: DetectionConfig,
    client_session: ClientSession | None = None,
) -> BackendDetectionResult | None:
    """Perform the actual backend detection logic."""
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
                key="log.backend_detection.detect_backend.probing",
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

        # Check if detection should abort (host unreachable)
        if version is _ABORT_DETECTION:
            _LOGGER.info(
                i18n.tr(
                    key="log.backend_detection.detect_backend.aborting",
                    host=config.host,
                )
            )
            break

        if version is None:
            continue

        # Type narrowing: version is now str (not _ABORT_DETECTION or None)
        assert isinstance(version, str)

        _LOGGER.info(i18n.tr(key="log.backend_detection.detect_backend.found_version", version=version, port=port))

        # Determine backend type from version string
        backend = _determine_backend(version=version)
        _LOGGER.info(i18n.tr(key="log.backend_detection.detect_backend.backend_type", backend=backend))

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
        # This may raise AuthFailure if authentication fails
        interfaces, auth_enabled, https_redirect_enabled = await _query_ccu_interfaces(
            host=config.host,
            username=config.username,
            password=config.password,
            verify_tls=config.verify_tls,
            client_session=client_session,
        )

        if interfaces:
            _LOGGER.info(i18n.tr(key="log.backend_detection.detect_backend.found_interfaces", interfaces=interfaces))
        else:
            # Fallback: use the interface we connected to
            _LOGGER.info(i18n.tr(key="log.backend_detection.detect_backend.json_rpc_fallback"))
            interfaces = (interface,)

        return BackendDetectionResult(
            backend=Backend.CCU,
            available_interfaces=interfaces,
            detected_port=port,
            tls=tls,
            host=config.host,
            version=version,
            auth_enabled=auth_enabled,
            https_redirect_enabled=https_redirect_enabled,
        )

    _LOGGER.info(i18n.tr(key="log.backend_detection.detect_backend.no_backend_found", host=config.host))
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
) -> str | None | object:
    """
    Probe a single XML-RPC port and return the version string if successful.

    Uses AioXmlRpcProxy for consistent error handling with the rest of the client.

    Returns:
        - Version string if connection successful
        - None if port probe failed but host might be reachable (try next port)
        - _ABORT_DETECTION sentinel if host is unreachable (abort all further probes)

    Raises:
        AuthFailure: If authentication fails with the provided credentials.

    """
    uri = build_xml_rpc_uri(host=host, port=port, path=None, tls=tls)
    headers = build_xml_rpc_headers(username=username, password=password) if username else []
    interface_id = f"detect-{host}:{port}"

    proxy: AioXmlRpcProxy | None = None
    try:
        proxy = AioXmlRpcProxy(
            max_workers=1,
            interface_id=interface_id,
            connection_state=CentralConnectionState(),
            uri=uri,
            headers=headers,
            tls=tls,
            verify_tls=verify_tls,
            timeout=request_timeout,
        )

        # Initialize proxy and get supported methods
        await asyncio.wait_for(proxy.do_init(), timeout=request_timeout)

        # Try to get version if available
        if _XML_METHOD_GET_VERSION in (proxy.supported_methods or ()):
            version = await asyncio.wait_for(proxy.getVersion(), timeout=request_timeout)
            return str(version) if version else ""
        # If getVersion not available, return empty string to indicate connection worked
        return ""  # noqa: TRY300

    except AuthFailure:
        # Re-raise authentication failures - wrong credentials should not try other ports
        raise
    except NoConnectionException as exc:
        # Connection failed on this port - log and try next port
        _LOGGER.info(
            i18n.tr(
                key="log.backend_detection.xml_rpc.probe_failed",
                host=host,
                port=port,
                exc_type=type(exc).__name__,
                reason=exc,
            )
        )
        return None
    except TimeoutError:
        # Timeout likely means host is unreachable - abort detection
        _LOGGER.info(
            i18n.tr(
                key="log.backend_detection.xml_rpc.probe_timeout_abort",
                host=host,
                port=port,
            )
        )
        return _ABORT_DETECTION
    except OSError as oserr:
        # Network-level errors - distinguish between "port closed" and "host unreachable"
        if oserr.errno in (errno.ETIMEDOUT, errno.EHOSTUNREACH, errno.ENETUNREACH):
            # Fatal error: host/network unreachable - abort detection
            _LOGGER.info(
                i18n.tr(
                    key="log.backend_detection.xml_rpc.probe_unreachable",
                    host=host,
                    port=port,
                    errno=oserr.errno,
                    reason=oserr,
                )
            )
            return _ABORT_DETECTION
        # ECONNREFUSED or other - port closed, but host might be reachable
        _LOGGER.info(
            i18n.tr(
                key="log.backend_detection.xml_rpc.probe_failed",
                host=host,
                port=port,
                exc_type=type(oserr).__name__,
                reason=oserr,
            )
        )
        return None
    except BaseHomematicException as exc:
        _LOGGER.info(
            i18n.tr(
                key="log.backend_detection.xml_rpc.probe_failed",
                host=host,
                port=port,
                exc_type=type(exc).__name__,
                reason=exc,
            )
        )
        return None
    except Exception as exc:
        _LOGGER.info(
            i18n.tr(
                key="log.backend_detection.xml_rpc.probe_error",
                host=host,
                port=port,
                exc_type=type(exc).__name__,
                reason=exc,
            )
        )
        return None
    finally:
        if proxy:
            await proxy.stop()


async def _query_ccu_interfaces(
    *,
    host: str,
    username: str,
    password: str,
    verify_tls: bool,
    client_session: ClientSession | None,
) -> tuple[tuple[Interface, ...], bool | None, bool | None]:
    """
    Query CCU for available interfaces via JSON-RPC.

    Uses AioJsonRpcAioHttpClient to query system information.
    Tries both HTTP (port 80) and HTTPS (port 443).

    Returns:
        Tuple of (interfaces, auth_enabled, https_redirect_enabled).
        Returns empty tuple if query fails.

    Raises:
        AuthFailure: If authentication fails with the provided credentials.

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

    return (), None, None


async def _query_json_rpc_interfaces(
    *,
    host: str,
    port: int,
    tls: bool,
    username: str,
    password: str,
    verify_tls: bool,
    client_session: ClientSession | None,
) -> tuple[tuple[Interface, ...], bool | None, bool | None] | None:
    """
    Query interfaces via JSON-RPC on a specific port using AioJsonRpcAioHttpClient.

    This function performs two checks:
    1. Queries available_interfaces from system information (installed interfaces)
    2. Verifies each interface is actually running via is_present() check

    Returns:
        Tuple of (interfaces, auth_enabled, https_redirect_enabled) if successful, None if failed.

    Raises:
        AuthFailure: If authentication fails with the provided credentials.

    """
    scheme = "https" if tls else "http"
    device_url = f"{scheme}://{host}:{port}"

    _LOGGER.info(i18n.tr(key="log.backend_detection.json_rpc.querying", url=device_url))

    json_rpc_client: AioJsonRpcAioHttpClient | None = None
    try:
        json_rpc_client = AioJsonRpcAioHttpClient(
            username=username,
            password=password,
            device_url=device_url,
            connection_state=CentralConnectionState(),
            client_session=client_session,
            tls=tls,
            verify_tls=verify_tls,
        )

        system_info = await json_rpc_client.get_system_information()

        # Convert interface strings to Interface enums
        installed_interfaces: list[Interface] = []
        for iface_name in system_info.available_interfaces:
            try:
                installed_interfaces.append(Interface(iface_name))
            except ValueError:
                _LOGGER.info(i18n.tr(key="log.backend_detection.json_rpc.unknown_interface", interface=iface_name))

        # Verify each interface is actually running via is_present check
        present_interfaces: list[Interface] = []
        for interface in installed_interfaces:
            try:
                if await json_rpc_client.is_present(interface=interface):
                    present_interfaces.append(interface)
                    _LOGGER.debug(
                        i18n.tr(
                            key="log.backend_detection.json_rpc.interface_present",
                            interface=interface.value,
                        )
                    )
                else:
                    _LOGGER.warning(
                        i18n.tr(
                            key="log.backend_detection.json_rpc.interface_not_present",
                            interface=interface.value,
                        )
                    )
            except Exception as exc:
                _LOGGER.warning(
                    i18n.tr(
                        key="log.backend_detection.json_rpc.is_present_failed",
                        interface=interface.value,
                        reason=str(exc),
                    )
                )

        return tuple(present_interfaces), system_info.auth_enabled, system_info.https_redirect_enabled

    except AuthFailure:
        # Re-raise authentication failures so they can be handled by the caller
        _LOGGER.warning(i18n.tr(key="log.backend_detection.json_rpc.auth_failed", url=device_url))
        raise
    except NoConnectionException:
        # Connection failed on this port - log and try next port
        _LOGGER.info(i18n.tr(key="log.backend_detection.json_rpc.connection_failed", url=device_url))
        return None
    except Exception as exc:
        _LOGGER.info(
            i18n.tr(
                key="log.backend_detection.json_rpc.query_failed",
                url=device_url,
                exc_type=type(exc).__name__,
                reason=exc,
            )
        )
        return None
    finally:
        if json_rpc_client:
            await json_rpc_client.logout()
