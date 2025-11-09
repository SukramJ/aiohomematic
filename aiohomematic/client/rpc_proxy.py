# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
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
from enum import Enum, IntEnum, StrEnum
import errno
import logging
from ssl import SSLContext, SSLError
from typing import Any, Final
import xmlrpc.client

from aiohomematic import central as hmcu, i18n
from aiohomematic.async_support import Looper
from aiohomematic.client._rpc_errors import RpcContext, map_xmlrpc_fault
from aiohomematic.const import ISO_8859_1
from aiohomematic.exceptions import (
    AuthFailure,
    BaseHomematicException,
    ClientException,
    NoConnectionException,
    UnsupportedException,
)
from aiohomematic.store import SessionRecorder
from aiohomematic.support import extract_exc_args, get_tls_context, log_boundary_error
from aiohomematic.type_aliases import CallableAny

_LOGGER: Final = logging.getLogger(__name__)

_CONTEXT: Final = "context"
_TLS: Final = "tls"
_VERIFY_TLS: Final = "verify_tls"


class _RpcMethod(StrEnum):
    """Enum for Homematic json rpc methods types."""

    GET_VERSION = "getVersion"
    HOMEGEAR_INIT = "clientServerInitialized"
    INIT = "init"
    PING = "ping"
    SYSTEM_LIST_METHODS = "system.listMethods"


_VALID_RPC_COMMANDS_ON_NO_CONNECTION: Final[tuple[str, ...]] = (
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

    def __getattr__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        """Magic method dispatcher."""
        return self._magic_method(self._async_request, *args, **kwargs)

    @property
    def supported_methods(self) -> tuple[str, ...]:
        """Return the supported methods."""
        return self._supported_methods

    @abstractmethod
    async def do_init(self) -> None:
        """Init the rpc proxy."""

    async def stop(self) -> None:
        """Stop depending services."""
        await self._looper.block_till_done()
        if self._proxy_executor:
            self._proxy_executor.shutdown()

    @abstractmethod
    async def _async_request(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        """Call method on server side."""

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
    ) -> None:
        """Initialize new proxy for server and get local ip."""
        super().__init__(
            max_workers=max_workers,
            interface_id=interface_id,
            connection_state=connection_state,
            magic_method=xmlrpc.client._Method,
            tls=tls,
            verify_tls=verify_tls,
            session_recorder=session_recorder,
        )

        xmlrpc.client.ServerProxy.__init__(
            self,
            uri=uri,
            encoding=ISO_8859_1,
            headers=headers,
            **self._kwargs,
        )

    async def do_init(self) -> None:
        """Init the xml rpc proxy."""
        if supported_methods := await self.system.listMethods():
            # ping is missing in VirtualDevices interface but can be used.
            supported_methods.append(_RpcMethod.PING)
            self._supported_methods = tuple(supported_methods)

    async def _async_request(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        """Call method on server side."""
        parent = xmlrpc.client.ServerProxy
        try:
            method = args[0]
            if self._supported_methods and method not in self._supported_methods:
                raise UnsupportedException(i18n.tr("exception.client.xmlrpc.method_unsupported", method=method))

            if method in _VALID_RPC_COMMANDS_ON_NO_CONNECTION or not self._connection_state.has_issue(
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
                return result
            raise NoConnectionException(
                i18n.tr("exception.client.xmlrpc.no_connection", interface_id=self._interface_id)
            )
        except BaseHomematicException as bhe:
            self._record_session(method=args[0], params=args[1:], exc=bhe)
            raise
        except SSLError as sslerr:  # pragma: no cover - SSL handshake/cert errors are OS/OpenSSL dependent and not reliably reproducible in CI
            message = f"SSLError on {self._interface_id}: {extract_exc_args(exc=sslerr)}"
            level = logging.ERROR
            if sslerr.args[0] in _SSL_ERROR_CODES:
                message = (
                    f"{message} - {sslerr.args[0]}: {sslerr.args[1]}. "
                    f"Please check your configuration for {self._interface_id}."
                )
                if not self._connection_state.add_issue(issuer=self, iid=self._interface_id):
                    level = logging.DEBUG

            log_boundary_error(
                logger=_LOGGER,
                boundary="xml-rpc",
                action=str(args[0]),
                err=sslerr,
                level=level,
                message=message,
                log_context=self.log_context,
            )
            raise NoConnectionException(
                i18n.tr("exception.client.xmlrpc.ssl_error", interface_id=self._interface_id, reason=message)
            ) from sslerr
        except OSError as oserr:  # pragma: no cover - Network/socket errno differences are platform/environment specific; simulating reliably in CI would be flaky
            level = (
                logging.ERROR
                if oserr.args[0] in _OS_ERROR_CODES
                and not self._connection_state.add_issue(issuer=self, iid=self._interface_id)
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
            raise NoConnectionException(
                i18n.tr(
                    "exception.client.xmlrpc.os_error",
                    interface_id=self._interface_id,
                    reason=extract_exc_args(exc=oserr),
                )
            ) from oserr
        except xmlrpc.client.Fault as flt:
            ctx = RpcContext(protocol="xml-rpc", method=str(args[0]), interface=self._interface_id)
            raise map_xmlrpc_fault(code=flt.faultCode, fault_string=flt.faultString, ctx=ctx) from flt
        except TypeError as terr:
            raise ClientException(terr) from terr
        except xmlrpc.client.ProtocolError as perr:
            if not self._connection_state.has_issue(issuer=self, iid=self._interface_id):
                if perr.errmsg == "Unauthorized":
                    raise AuthFailure(perr) from perr
                raise NoConnectionException(
                    i18n.tr(
                        "exception.client.xmlrpc.no_connection_with_reason",
                        context=str(self.log_context),
                        reason=perr.errmsg,
                    )
                ) from perr
        except Exception as exc:
            raise ClientException(exc) from exc


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
