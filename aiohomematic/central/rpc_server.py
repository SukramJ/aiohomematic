# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
XML-RPC server module.

Provides the XML-RPC server which handles communication
with the backend.
"""

from __future__ import annotations

import contextlib
import logging
import threading
from typing import Any, Final, cast
from xmlrpc.server import SimpleXMLRPCRequestHandler, SimpleXMLRPCServer

from aiohomematic import central as hmcu, i18n
from aiohomematic.central.decorators import callback_backend_system
from aiohomematic.const import IP_ANY_V4, PORT_ANY, BackendSystemEvent
from aiohomematic.support import log_boundary_error
from aiohomematic.type_aliases import AsyncTaskFactory

_LOGGER: Final = logging.getLogger(__name__)


# pylint: disable=invalid-name
class RPCFunctions:
    """The RPC functions the backend will expect."""

    # Disable kw-only linter
    __kwonly_check__ = False

    def __init__(self, *, rpc_server: RpcServer) -> None:
        """Init RPCFunctions."""
        self._rpc_server: Final = rpc_server

    def deleteDevices(self, interface_id: str, addresses: list[str], /) -> None:
        """Delete devices send from the backend."""
        central: hmcu.CentralUnit | None
        if central := self.get_central(interface_id=interface_id):
            central.looper.create_task(
                target=lambda: central.delete_devices(interface_id=interface_id, addresses=tuple(addresses)),
                name=f"deleteDevices-{interface_id}",
            )

    @callback_backend_system(system_event=BackendSystemEvent.ERROR)
    def error(self, interface_id: str, error_code: str, msg: str, /) -> None:
        """When some error occurs the backend will send its error message here."""
        # Structured boundary log (warning level). RPC server received error notification.
        try:
            raise RuntimeError(str(msg))
        except RuntimeError as err:
            log_boundary_error(
                logger=_LOGGER,
                boundary="rpc-server",
                action="error",
                err=err,
                level=logging.WARNING,
                log_context={"interface_id": interface_id, "error_code": int(error_code)},
            )
        _LOGGER.error(
            i18n.tr(
                "log.central.rpc_server.error",
                interface_id=interface_id,
                error_code=int(error_code),
                msg=str(msg),
            )
        )

    def event(self, interface_id: str, channel_address: str, parameter: str, value: Any, /) -> None:
        """If a device emits some sort event, we will handle it here."""
        if central := self.get_central(interface_id=interface_id):
            central.looper.create_task(
                target=cast(
                    AsyncTaskFactory,
                    lambda: central.data_point_event(
                        interface_id=interface_id,
                        channel_address=channel_address,
                        parameter=parameter,
                        value=value,
                    ),
                ),
                name=f"event-{interface_id}-{channel_address}-{parameter}",
            )

    def get_central(self, *, interface_id: str) -> hmcu.CentralUnit | None:
        """Return the central by interface_id."""
        return self._rpc_server.get_central(interface_id=interface_id)

    def listDevices(self, interface_id: str, /) -> list[dict[str, Any]]:
        """Return already existing devices to the backend."""
        if central := self.get_central(interface_id=interface_id):
            return [dict(device_description) for device_description in central.list_devices(interface_id=interface_id)]
        return []

    def newDevices(self, interface_id: str, device_descriptions: list[dict[str, Any]], /) -> None:
        """Add new devices send from the backend."""
        central: hmcu.CentralUnit | None
        if central := self.get_central(interface_id=interface_id):
            central.looper.create_task(
                target=central.add_new_devices(
                    interface_id=interface_id, device_descriptions=tuple(device_descriptions)
                ),
                name=f"newDevices-{interface_id}",
            )

    @callback_backend_system(system_event=BackendSystemEvent.RE_ADDED_DEVICE)
    def readdedDevice(self, interface_id: str, addresses: list[str], /) -> None:
        """
        Re-Add device from the backend.

        Probably irrelevant for us.
        Gets called when a known devices is put into learn-mode
        while installation mode is active.
        """
        _LOGGER.debug(
            "READDEDDEVICES: interface_id = %s, addresses = %s",
            interface_id,
            str(addresses),
        )

    @callback_backend_system(system_event=BackendSystemEvent.REPLACE_DEVICE)
    def replaceDevice(self, interface_id: str, old_device_address: str, new_device_address: str, /) -> None:
        """Replace a device. Probably irrelevant for us."""
        _LOGGER.debug(
            "REPLACEDEVICE: interface_id = %s, oldDeviceAddress = %s, newDeviceAddress = %s",
            interface_id,
            old_device_address,
            new_device_address,
        )

    @callback_backend_system(system_event=BackendSystemEvent.UPDATE_DEVICE)
    def updateDevice(self, interface_id: str, address: str, hint: int, /) -> None:
        """
        Update a device.

        Irrelevant, as currently only changes to link
        partners are reported.
        """
        _LOGGER.debug(
            "UPDATEDEVICE: interface_id = %s, address = %s, hint = %s",
            interface_id,
            address,
            str(hint),
        )


# Restrict to specific paths.
class RequestHandler(SimpleXMLRPCRequestHandler):
    """We handle requests to / and /RPC2."""

    rpc_paths = (
        "/",
        "/RPC2",
    )


class HomematicXMLRPCServer(SimpleXMLRPCServer):
    """
    Simple XML-RPC server.

    Simple XML-RPC server that allows functions and a single instance
    to be installed to handle requests. The default implementation
    attempts to dispatch XML-RPC calls to the functions or instance
    installed in the server. Override the _dispatch method inherited
    from SimpleXMLRPCDispatcher to change this behavior.

    This implementation adds an additional method:
    system_listMethods(self, interface_id: str.
    """

    __kwonly_check__ = False

    def system_listMethods(self, interface_id: str | None = None, /) -> list[str]:
        """Return a list of the methods supported by the server."""
        return SimpleXMLRPCServer.system_listMethods(self)


class RpcServer(threading.Thread):
    """RPC server thread to handle messages from the backend."""

    _initialized: bool = False
    _instances: Final[dict[tuple[str, int], RpcServer]] = {}

    def __init__(self, *, server: SimpleXMLRPCServer) -> None:
        """Init XmlRPC server."""
        self._server = server
        self._server.register_introspection_functions()
        self._server.register_multicall_functions()
        self._server.register_instance(RPCFunctions(rpc_server=self), allow_dotted_names=True)
        self._initialized = True
        self._address: Final[tuple[str, int]] = cast(tuple[str, int], server.server_address)
        self._listen_ip_addr: Final = self._address[0]
        self._listen_port: Final = self._address[1]
        self._centrals: Final[dict[str, hmcu.CentralUnit]] = {}
        self._instances[self._address] = self
        threading.Thread.__init__(self, name=f"RpcServer {self._listen_ip_addr}:{self._listen_port}")

    @property
    def listen_ip_addr(self) -> str:
        """Return the local ip address."""
        return self._listen_ip_addr

    @property
    def listen_port(self) -> int:
        """Return the local port."""
        return self._listen_port

    @property
    def no_central_assigned(self) -> bool:
        """Return if no central is assigned."""
        return len(self._centrals) == 0

    @property
    def started(self) -> bool:
        """Return if thread is active."""
        return self._started.is_set() is True  # type: ignore[attr-defined]

    def add_central(self, *, central: hmcu.CentralUnit) -> None:
        """Register a central in the RPC-Server."""
        if not self._centrals.get(central.name):
            self._centrals[central.name] = central

    def get_central(self, *, interface_id: str) -> hmcu.CentralUnit | None:
        """Return a central by interface_id."""
        for central in self._centrals.values():
            if central.has_client(interface_id=interface_id):
                return central
        return None

    def remove_central(self, *, central: hmcu.CentralUnit) -> None:
        """Unregister a central from RPC-Server."""
        if self._centrals.get(central.name):
            del self._centrals[central.name]

    def run(self) -> None:
        """Run the RPC-Server thread."""
        _LOGGER.debug(
            "RUN: Starting RPC-Server listening on %s:%i",
            self._listen_ip_addr,
            self._listen_port,
        )
        if self._server:
            self._server.serve_forever()

    def stop(self) -> None:
        """Stop the RPC-Server."""
        _LOGGER.debug("STOP: Shutting down RPC-Server")
        self._server.shutdown()
        _LOGGER.debug("STOP: Stopping RPC-Server")
        self._server.server_close()
        # Ensure the server thread has actually terminated to avoid slow teardown
        with contextlib.suppress(RuntimeError):
            self.join(timeout=1.0)
        _LOGGER.debug("STOP: RPC-Server stopped")
        if self._address in self._instances:
            del self._instances[self._address]


class XmlRpcServer(RpcServer):
    """XML-RPC server thread to handle messages from the backend."""

    def __init__(
        self,
        *,
        ip_addr: str,
        port: int,
    ) -> None:
        """Init XmlRPC server."""

        if self._initialized:
            return
        super().__init__(
            server=HomematicXMLRPCServer(
                addr=(ip_addr, port),
                requestHandler=RequestHandler,
                logRequests=False,
                allow_none=True,
            )
        )

    def __new__(cls, ip_addr: str, port: int) -> XmlRpcServer:  # noqa: PYI034  # kwonly: disable
        """Create new RPC server."""
        if (rpc := cls._instances.get((ip_addr, port))) is None:
            _LOGGER.debug("Creating XmlRpc server")
            return super().__new__(cls)
        return cast(XmlRpcServer, rpc)


def create_xml_rpc_server(*, ip_addr: str = IP_ANY_V4, port: int = PORT_ANY) -> XmlRpcServer:
    """Register the rpc server."""
    rpc = XmlRpcServer(ip_addr=ip_addr, port=port)
    if not rpc.started:
        rpc.start()
        _LOGGER.debug(
            "CREATE_XML_RPC_SERVER: Starting XmlRPC-Server listening on %s:%i",
            rpc.listen_ip_addr,
            rpc.listen_port,
        )
    return rpc
