# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
XML-RPC transport proxy with concurrency control and connection awareness.

Overview
--------
XmlRpcProxy extends xmlrpc.client.ServerProxy to:
- Execute RPC calls in a thread pool to avoid blocking the event loop
- Integrate with CentralConnectionState to mark/report connection issues
- Optionally use TLS with configurable certificate verification
- Filter unsupported methods at runtime via system.listMethods

Notes
-----
- The proxy cleans and normalizes argument encodings for XML-RPC.
- Certain methods are allowed even when the connection is flagged down
  (e.g., ping, init, getVersion) to support recovery.

"""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from enum import Enum, IntEnum, StrEnum, unique
import errno
import http.client
import logging
from ssl import SSLContext, SSLError
from typing import TYPE_CHECKING, Any, Final
import xmlrpc.client

from aiohomematic import central as hmcu, i18n
from aiohomematic.async_support import Looper
from aiohomematic.client._rpc_errors import RpcContext, map_xmlrpc_fault, sanitize_error_message
from aiohomematic.client.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from aiohomematic.const import ISO_8859_1
from aiohomematic.exceptions import (
    AuthFailure,
    BaseHomematicException,
    CircuitBreakerOpenException,
    ClientException,
    NoConnectionException,
    UnsupportedException,
)
from aiohomematic.property_decorators import DelegatedProperty
from aiohomematic.store.persistent import SessionRecorder
from aiohomematic.store.types import IncidentSeverity, IncidentType
from aiohomematic.support import extract_exc_args, get_tls_context, log_boundary_error
from aiohomematic.type_aliases import CallableAny

if TYPE_CHECKING:
    from aiohomematic.central.events import EventBus
    from aiohomematic.interfaces import IncidentRecorderProtocol

_LOGGER: Final = logging.getLogger(__name__)

_CONTEXT: Final = "context"
_TLS: Final = "tls"
_VERIFY_TLS: Final = "verify_tls"


@unique
class _RpcMethod(StrEnum):
    """Enum for Homematic json rpc methods types."""

    GET_VERSION = "getVersion"
    HOMEGEAR_INIT = "clientServerInitialized"
    INIT = "init"
    PING = "ping"
    SYSTEM_LIST_METHODS = "system.listMethods"


_CIRCUIT_BREAKER_BYPASS_METHODS: Final[tuple[str, ...]] = (
    _RpcMethod.GET_VERSION,
    _RpcMethod.HOMEGEAR_INIT,
    _RpcMethod.INIT,
    _RpcMethod.PING,
    _RpcMethod.SYSTEM_LIST_METHODS,
)

_SSL_ERROR_CODES: Final[dict[int, str]] = {
    errno.ENOEXEC: "EOF occurred in violation of protocol",
}

_OS_ERROR_CODES: Final[dict[int, str]] = {
    errno.ECONNREFUSED: "Connection refused",
    errno.EHOSTUNREACH: "No route to host",
    errno.ENETUNREACH: "Network is unreachable",
    errno.ENOEXEC: "Exec",
    errno.ETIMEDOUT: "Operation timed out",
}


@unique
class _XmlRpcFaultCode(IntEnum):
    """
    XML-RPC fault codes from the Homematic backend.

    Reference: CCU documentation for XML-RPC fault codes.
    """

    GENERIC_ERROR = -1
    """General error (often UNREACH - device temporarily unreachable)."""

    UNKNOWN_DEVICE = -2
    """Unknown device or channel."""

    UNKNOWN_PARAMSET = -3
    """Unknown paramset."""

    ADDRESS_EXPECTED = -4
    """Device address was expected."""

    UNKNOWN_PARAMETER = -5
    """Unknown parameter or value."""

    OPERATION_NOT_SUPPORTED = -6
    """Operation not supported by this parameter."""

    UPDATE_NOT_POSSIBLE = -7
    """Interface cannot perform update."""

    INSUFFICIENT_DUTYCYCLE = -8
    """Not enough DutyCycle available."""

    DEVICE_OUT_OF_RANGE = -9
    """Device is not in range."""

    TRANSMISSION_PENDING = -10
    """Transmission to device pending."""


# Fault codes that are expected during initial data loading and normal operation.
# These indicate transient or known conditions, not actual system errors.
_EXPECTED_XMLRPC_FAULT_CODES: Final[frozenset[int]] = frozenset(
    {
        _XmlRpcFaultCode.GENERIC_ERROR,
        _XmlRpcFaultCode.UNKNOWN_DEVICE,
        _XmlRpcFaultCode.UNKNOWN_PARAMSET,
        _XmlRpcFaultCode.UNKNOWN_PARAMETER,
        _XmlRpcFaultCode.DEVICE_OUT_OF_RANGE,
        _XmlRpcFaultCode.TRANSMISSION_PENDING,
    }
)


class _TimeoutTransport(xmlrpc.client.Transport):
    """HTTP Transport with configurable socket timeout and extra headers."""

    def __init__(
        self,
        *,
        timeout: float | None = None,
        headers: list[tuple[str, str]] | None = None,
    ) -> None:
        """Initialize transport with timeout and optional headers."""
        super().__init__(headers=headers or [])
        self._timeout = timeout

    def make_connection(  # kwonly: disable
        self, host: tuple[str, dict[str, str]] | str
    ) -> http.client.HTTPConnection:
        """Create HTTP connection with timeout."""
        conn = super().make_connection(host)
        if self._timeout is not None:
            conn.timeout = self._timeout
        return conn


class _TimeoutSafeTransport(xmlrpc.client.SafeTransport):
    """HTTPS Transport with configurable socket timeout and extra headers."""

    def __init__(
        self,
        *,
        timeout: float | None = None,
        context: SSLContext | None = None,
        headers: list[tuple[str, str]] | None = None,
    ) -> None:
        """Initialize transport with timeout, optional SSL context, and headers."""
        super().__init__(context=context, headers=headers or [])
        self._timeout = timeout

    def make_connection(  # kwonly: disable
        self, host: tuple[str, dict[str, str]] | str
    ) -> http.client.HTTPSConnection:
        """Create HTTPS connection with timeout."""
        conn = super().make_connection(host)
        if self._timeout is not None:
            conn.timeout = self._timeout
        return conn


# noinspection PyProtectedMember,PyUnresolvedReferences
class BaseRpcProxy(ABC):
    """ServerProxy implementation with ThreadPoolExecutor when request is executing."""

    def __init__(
        self,
        *,
        max_workers: int,
        interface_id: str,
        connection_state: hmcu.CentralConnectionState,
        magic_method: CallableAny,
        tls: bool = False,
        verify_tls: bool = False,
        session_recorder: SessionRecorder | None = None,
        circuit_breaker_config: CircuitBreakerConfig | None = None,
        event_bus: EventBus | None = None,
        incident_recorder: IncidentRecorderProtocol | None = None,
    ) -> None:
        """Initialize new proxy for server and get local ip."""
        self._interface_id: Final = interface_id
        self._connection_state: Final = connection_state
        self._session_recorder: Final = session_recorder
        self._magic_method: Final = magic_method
        self._looper: Final = Looper()
        self._proxy_executor: Final = (
            ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix=interface_id) if max_workers > 0 else None
        )
        self._tls: Final[bool | SSLContext] = get_tls_context(verify_tls=verify_tls) if tls else False
        self._supported_methods: tuple[str, ...] = ()
        self._kwargs: dict[str, Any] = {}
        if tls:
            self._kwargs[_CONTEXT] = self._tls
        # Due to magic method the log_context must be defined manually.
        self.log_context: Final[Mapping[str, Any]] = {"interface_id": self._interface_id, "tls": tls}

        # Incident recorder for diagnostic events
        self._incident_recorder = incident_recorder

        # Circuit breaker for preventing retry-storms during backend outages
        self._circuit_breaker: Final = CircuitBreaker(
            config=circuit_breaker_config,
            interface_id=interface_id,
            connection_state=connection_state,
            issuer=self,
            event_bus=event_bus,
            incident_recorder=incident_recorder,
            task_scheduler=self._looper,
        )

    def __getattr__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        """Magic method dispatcher."""
        return self._magic_method(self._async_request, *args, **kwargs)

    circuit_breaker: Final = DelegatedProperty[CircuitBreaker](path="_circuit_breaker")
    supported_methods: Final = DelegatedProperty[tuple[str, ...]](path="_supported_methods")

    def clear_connection_issue(self) -> None:
        """
        Clear the connection issue flag for this interface.

        This should be called after a successful proxy init to ensure
        that subsequent RPC calls are not blocked by stale connection issues
        from previous failed attempts.
        """
        self._connection_state.remove_issue(issuer=self, iid=self._interface_id)

    @abstractmethod
    async def do_init(self) -> None:
        """Initialize the rpc proxy."""

    async def stop(self) -> None:
        """Stop depending services."""
        await self._looper.block_till_done()
        if self._proxy_executor:
            self._proxy_executor.shutdown()

    @abstractmethod
    async def _async_request(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        """Call method on server side."""

    def _record_rpc_error_incident(
        self,
        *,
        method: str,
        error_type: str,
        error_message: str,
        protocol: str = "xml-rpc",
        is_expected: bool = False,
    ) -> None:
        """
        Record an RPC_ERROR incident for diagnostics.

        Args:
            method: RPC method that failed.
            error_type: Type of error (e.g., XMLRPCFault, OSError).
            error_message: Error message from the exception.
            protocol: RPC protocol used (xml-rpc or json-rpc).
            is_expected: If True, use WARNING severity instead of ERROR.
                Expected errors are common during data loading (e.g., unknown
                parameters, unreachable devices) and should not clutter logs.

        """
        if (incident_recorder := self._incident_recorder) is None:
            return

        # Sanitize error message to remove sensitive information
        sanitized_message = sanitize_error_message(message=error_message)

        # Use WARNING for expected errors to reduce log noise
        severity = IncidentSeverity.WARNING if is_expected else IncidentSeverity.ERROR

        context = {
            "protocol": protocol,
            "method": method,
            "error_type": error_type,
            "error_message": sanitized_message,
            "tls_enabled": bool(self._tls),
        }

        async def _record() -> None:
            try:
                await incident_recorder.record_incident(
                    incident_type=IncidentType.RPC_ERROR,
                    severity=severity,
                    message=f"RPC error on {self._interface_id}: {error_type} during {method}",
                    interface_id=self._interface_id,
                    context=context,
                )
            except Exception as err:  # pragma: no cover
                _LOGGER.debug(
                    "RPC_PROXY: Failed to record RPC error incident for %s: %s",
                    self._interface_id,
                    err,
                )

        # Schedule the async recording via looper
        self._looper.create_task(
            target=_record(),
            name=f"record_rpc_error_incident_{self._interface_id}",
        )

    def _record_session(
        self, *, method: str, params: tuple[Any, ...], response: Any | None = None, exc: Exception | None = None
    ) -> bool:
        """Record the session."""
        if method in (_RpcMethod.PING,):
            return False
        if self._session_recorder and self._session_recorder.active:
            self._session_recorder.add_xml_rpc_session(method=method, params=params, response=response, session_exc=exc)
            return True
        return False


# noinspection PyProtectedMember,PyUnresolvedReferences
class AioXmlRpcProxy(BaseRpcProxy, xmlrpc.client.ServerProxy):
    """ServerProxy implementation with ThreadPoolExecutor when request is executing."""

    def __init__(
        self,
        *,
        max_workers: int,
        interface_id: str,
        connection_state: hmcu.CentralConnectionState,
        uri: str,
        headers: list[tuple[str, str]],
        tls: bool = False,
        verify_tls: bool = False,
        session_recorder: SessionRecorder | None = None,
        event_bus: EventBus | None = None,
        incident_recorder: IncidentRecorderProtocol | None = None,
        timeout: float | None = None,
    ) -> None:
        """
        Initialize new proxy for server and get local ip.

        Args:
            max_workers: Number of worker threads.
            interface_id: Interface identifier.
            connection_state: Connection state tracker.
            uri: XML-RPC server URI.
            headers: HTTP headers for authentication.
            tls: Whether to use TLS.
            verify_tls: Whether to verify TLS certificates.
            session_recorder: Optional session recorder.
            event_bus: Optional event bus.
            incident_recorder: Optional incident recorder.
            timeout: Socket timeout in seconds for HTTP connections. If None, uses Python's default (no timeout).

        """
        super().__init__(
            max_workers=max_workers,
            interface_id=interface_id,
            connection_state=connection_state,
            magic_method=xmlrpc.client._Method,
            tls=tls,
            verify_tls=verify_tls,
            session_recorder=session_recorder,
            event_bus=event_bus,
            incident_recorder=incident_recorder,
        )

        # Create transport with timeout support
        # ServerProxy doesn't accept timeout directly - it must be set on the transport
        # IMPORTANT: When using a custom transport, headers must be passed to the transport
        # directly, as ServerProxy won't add them to an existing transport.
        transport: xmlrpc.client.Transport | None = None
        if timeout is not None or tls:
            if tls:
                # Use HTTPS transport with timeout, SSL context, and auth headers
                ssl_context = self._kwargs.get(_CONTEXT)
                transport = _TimeoutSafeTransport(timeout=timeout, context=ssl_context, headers=headers)
            else:
                # Use HTTP transport with timeout and auth headers
                transport = _TimeoutTransport(timeout=timeout, headers=headers)

        xmlrpc.client.ServerProxy.__init__(
            self,
            uri=uri,
            transport=transport,
            encoding=ISO_8859_1,
            headers=headers,
        )

    async def do_init(self) -> None:
        """Initialize the xml rpc proxy."""
        if supported_methods := await self.system.listMethods():
            # ping is missing in VirtualDevices interface but can be used.
            supported_methods.append(_RpcMethod.PING)
            self._supported_methods = tuple(supported_methods)

    async def _async_request(self, *args: Any, **kwargs: Any) -> Any:
        """Call method on server side."""
        parent = xmlrpc.client.ServerProxy
        try:
            method = args[0]
            if self._supported_methods and method not in self._supported_methods:
                raise UnsupportedException(i18n.tr(key="exception.client.xmlrpc.method_unsupported", method=method))

            # Check circuit breaker state (allow recovery commands through)
            if method not in _CIRCUIT_BREAKER_BYPASS_METHODS and not self._circuit_breaker.is_available:
                self._circuit_breaker.record_rejection()
                raise CircuitBreakerOpenException(
                    i18n.tr(key="exception.client.xmlrpc.circuit_open", interface_id=self._interface_id)
                )

            if method in _CIRCUIT_BREAKER_BYPASS_METHODS or not self._connection_state.is_issue(
                issuer=self, iid=self._interface_id
            ):
                args = _cleanup_args(*args)
                _LOGGER.debug("XmlRPC.__ASYNC_REQUEST: %s", args)
                result = await asyncio.shield(
                    self._looper.async_add_executor_job(
                        # pylint: disable=protected-access
                        parent._ServerProxy__request,  # type: ignore[attr-defined]
                        self,
                        *args,
                        name="xmp_rpc_proxy",
                        executor=self._proxy_executor,
                    )
                )
                self._record_session(method=method, params=args[1], response=result)
                self._connection_state.remove_issue(issuer=self, iid=self._interface_id)
                self._circuit_breaker.record_success()
                return result
            raise NoConnectionException(
                i18n.tr(key="exception.client.xmlrpc.no_connection", interface_id=self._interface_id)
            )
        except BaseHomematicException as bhe:
            self._record_session(method=args[0], params=args[1:], exc=bhe)
            # Record failure for circuit breaker (connection-related exceptions)
            # Don't record failure for CircuitBreakerOpenException - circuit is already open
            if isinstance(bhe, NoConnectionException) and not isinstance(bhe, CircuitBreakerOpenException):
                self._circuit_breaker.record_failure()
            raise
        except SSLError as sslerr:  # pragma: no cover - SSL handshake/cert errors are OS/OpenSSL dependent and not reliably reproducible in CI
            message = f"SSLError on {self._interface_id}: {extract_exc_args(exc=sslerr)}"
            # Log ERROR only on first occurrence, DEBUG for subsequent failures
            level = logging.DEBUG
            if sslerr.args[0] in _SSL_ERROR_CODES:
                message = (
                    f"{message} - {sslerr.args[0]}: {sslerr.args[1]}. "
                    f"Please check your configuration for {self._interface_id}."
                )
                if self._connection_state.add_issue(issuer=self, iid=self._interface_id):
                    level = logging.ERROR

            log_boundary_error(
                logger=_LOGGER,
                boundary="xml-rpc",
                action=str(args[0]),
                err=sslerr,
                level=level,
                message=message,
                log_context=self.log_context,
            )
            self._circuit_breaker.record_failure()
            self._record_rpc_error_incident(
                method=str(args[0]),
                error_type="SSLError",
                error_message=message,
            )
            raise NoConnectionException(
                i18n.tr(key="exception.client.xmlrpc.ssl_error", interface_id=self._interface_id, reason=message)
            ) from sslerr
        except OSError as oserr:  # pragma: no cover - Network/socket errno differences are platform/environment specific; simulating reliably in CI would be flaky
            # Log ERROR only on first occurrence, DEBUG for subsequent failures
            level = (
                logging.ERROR
                if oserr.args[0] in _OS_ERROR_CODES
                and self._connection_state.add_issue(issuer=self, iid=self._interface_id)
                else logging.DEBUG
            )

            log_boundary_error(
                logger=_LOGGER,
                boundary="xml-rpc",
                action=str(args[0]),
                err=oserr,
                level=level,
                log_context=self.log_context,
            )
            self._circuit_breaker.record_failure()
            self._record_rpc_error_incident(
                method=str(args[0]),
                error_type="OSError",
                error_message=str(extract_exc_args(exc=oserr)),
            )
            raise NoConnectionException(
                i18n.tr(
                    key="exception.client.xmlrpc.os_error",
                    interface_id=self._interface_id,
                    reason=extract_exc_args(exc=oserr),
                )
            ) from oserr
        except xmlrpc.client.Fault as flt:
            ctx = RpcContext(protocol="xml-rpc", method=str(args[0]), interface=self._interface_id)
            self._record_rpc_error_incident(
                method=str(args[0]),
                error_type="XMLRPCFault",
                error_message=f"Code {flt.faultCode}: {flt.faultString}",
                is_expected=flt.faultCode in _EXPECTED_XMLRPC_FAULT_CODES,
            )
            raise map_xmlrpc_fault(code=flt.faultCode, fault_string=flt.faultString, ctx=ctx) from flt
        except TypeError as terr:
            self._record_rpc_error_incident(
                method=str(args[0]),
                error_type="TypeError",
                error_message=str(extract_exc_args(exc=terr)),
            )
            raise ClientException(terr) from terr
        except xmlrpc.client.ProtocolError as perr:
            if not self._connection_state.is_issue(issuer=self, iid=self._interface_id):
                self._record_rpc_error_incident(
                    method=str(args[0]),
                    error_type="ProtocolError",
                    error_message=perr.errmsg,
                )
                if perr.errmsg == "Unauthorized":
                    raise AuthFailure(perr) from perr
                raise NoConnectionException(
                    i18n.tr(
                        key="exception.client.xmlrpc.no_connection_with_reason",
                        context=str(self.log_context),
                        reason=perr.errmsg,
                    )
                ) from perr
        except http.client.ImproperConnectionState as icserr:
            # HTTP connection state errors (ResponseNotReady, CannotSendRequest, etc.)
            # These indicate the connection is in an inconsistent state and should be retried
            # Log at DEBUG level as this is expected during reconnection scenarios
            log_boundary_error(
                logger=_LOGGER,
                boundary="xml-rpc",
                action=str(args[0]),
                err=icserr,
                level=logging.DEBUG,
                log_context=self.log_context,
            )
            # Note: We do NOT reset the transport here because:
            # 1. transport.close() alone doesn't fix the issue (transport reuses closed connection)
            # 2. setting transport=None causes AttributeError on retry
            # The retry mechanism with backoff should handle transient connection issues.
            # If the issue persists, circuit breaker will open and client will reconnect.
            self._circuit_breaker.record_failure()
            self._record_rpc_error_incident(
                method=str(args[0]),
                error_type="ImproperConnectionState",
                error_message=str(extract_exc_args(exc=icserr)),
            )
            raise NoConnectionException(
                i18n.tr(
                    key="exception.client.xmlrpc.http_connection_state_error",
                    interface_id=self._interface_id,
                    reason=extract_exc_args(exc=icserr),
                )
            ) from icserr
        except Exception as exc:
            self._record_rpc_error_incident(
                method=str(args[0]),
                error_type=type(exc).__name__,
                error_message=str(extract_exc_args(exc=exc)),
            )
            raise ClientException(exc) from exc

    def _reset_transport(self) -> None:
        """
        Reset the XML-RPC transport to force a new connection on next request.

        This is necessary when the underlying HTTP connection gets into an
        inconsistent state (e.g., after ResponseNotReady errors).
        """
        # Close the transport connection, which will force a new connection
        # on the next request. We DO NOT set transport to None because that
        # causes AttributeError - ServerProxy expects the transport to exist.
        if transport := self._ServerProxy__transport:
            with suppress(Exception):  # Best effort cleanup
                transport.close()
                _LOGGER.debug(
                    "XmlRPC._RESET_TRANSPORT: Transport closed for %s",
                    self._interface_id,
                )


class NullRpcProxy(BaseRpcProxy):
    """
    Null RPC proxy for clients that don't use XML-RPC.

    Used by ClientJsonCCU to satisfy handler initialization requirements
    without creating actual XML-RPC connections. All operations raise
    UnsupportedException if called.
    """

    def __init__(
        self,
        *,
        interface_id: str,
        connection_state: hmcu.CentralConnectionState,
        event_bus: EventBus | None = None,
        incident_recorder: IncidentRecorderProtocol | None = None,
    ) -> None:
        """Initialize null proxy."""
        super().__init__(
            max_workers=0,
            interface_id=interface_id,
            connection_state=connection_state,
            magic_method=self._null_method,
            tls=False,
            verify_tls=False,
            session_recorder=None,
            event_bus=event_bus,
            incident_recorder=incident_recorder,
        )

    async def do_init(self) -> None:
        """No-op initialization."""

    async def _async_request(self, *args: Any, **kwargs: Any) -> None:
        """Raise UnsupportedException for any RPC request."""
        raise UnsupportedException(
            i18n.tr(key="exception.client.xmlrpc.null_proxy_unsupported", interface_id=self._interface_id)
        )

    def _null_method(
        self,
        request_func: Any,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Return a callable that raises UnsupportedException."""

        async def _raise(*args: Any, **kwargs: Any) -> None:
            raise UnsupportedException(
                i18n.tr(key="exception.client.xmlrpc.null_proxy_unsupported", interface_id=self._interface_id)
            )

        return _raise


def _cleanup_args(*args: Any) -> Any:
    """Cleanup the type of args."""
    if len(args[1]) == 0:
        return args
    if len(args) == 2:
        new_args: list[Any] = []
        for data in args[1]:
            if isinstance(data, dict):
                new_args.append(_cleanup_paramset(paramset=data))
            else:
                new_args.append(_cleanup_item(item=data))
        return (args[0], tuple(new_args))
    _LOGGER.error("XmlRpcProxy command: Too many arguments")  # i18n-log: ignore
    return args


def _cleanup_item(*, item: Any) -> Any:
    """Cleanup a single item."""
    if isinstance(item, StrEnum):
        return str(item)
    if isinstance(item, IntEnum):
        return int(item)
    if isinstance(item, Enum):
        _LOGGER.error("XmlRpcProxy command: Enum is not supported as parameter value")  # i18n-log: ignore
    return item


def _cleanup_paramset(*, paramset: Mapping[str, Any]) -> Mapping[str, Any]:
    """Cleanup a paramset."""
    new_paramset: dict[str, Any] = {}
    for name, value in paramset.items():
        new_paramset[_cleanup_item(item=name)] = _cleanup_item(item=value)
    return new_paramset
