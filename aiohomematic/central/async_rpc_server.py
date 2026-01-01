# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Async XML-RPC server module.

Provides an asyncio-native XML-RPC server using aiohttp for
receiving callbacks from the Homematic backend.

This is an experimental alternative to the thread-based XML-RPC server
(see ADR 0011). Enable via OptionalSettings.ASYNC_RPC_SERVER.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any, Final
from xml.parsers.expat import ExpatError
import xmlrpc.client

from aiohttp import web
import orjson

from aiohomematic import client as hmcl, i18n
from aiohomematic.const import IP_ANY_V4, PORT_ANY, SystemEventType
from aiohomematic.interfaces.central import RpcServerCentralProtocol
from aiohomematic.metrics import MetricKeys, emit_counter, emit_gauge, emit_latency
from aiohomematic.support import log_boundary_error

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from aiohomematic.central.events import EventBus

_LOGGER: Final = logging.getLogger(__name__)

# Type alias for async method handlers
type AsyncMethodHandler = Callable[..., Awaitable[Any]]


class XmlRpcProtocolError(Exception):
    """Exception for XML-RPC protocol errors."""


class AsyncXmlRpcDispatcher:
    """
    Dispatcher for async XML-RPC method calls.

    Parses XML-RPC requests and dispatches to registered async handlers.
    Uses stdlib xmlrpc.client for parsing (no external dependencies).
    """

    def __init__(self) -> None:
        """Initialize the dispatcher."""
        self._methods: Final[dict[str, AsyncMethodHandler]] = {}

    async def dispatch(self, *, xml_data: bytes) -> bytes:
        """
        Parse XML-RPC request and dispatch to handler.

        Args:
            xml_data: Raw XML-RPC request body

        Returns:
            XML-RPC response as bytes

        """
        try:
            params, method_name = xmlrpc.client.loads(
                xml_data,
                use_builtin_types=True,
            )
        except ExpatError as err:
            raise XmlRpcProtocolError(i18n.tr(key="exception.central.rpc_server.invalid_xml", error=err)) from err
        except Exception as err:
            raise XmlRpcProtocolError(i18n.tr(key="exception.central.rpc_server.parse_error", error=err)) from err

        _LOGGER.debug(
            "XML-RPC dispatch: method=%s, params=%s",
            method_name,
            params[:2] if len(params) > 2 else params,
        )

        # Look up method
        if method_name not in self._methods:
            fault = xmlrpc.client.Fault(
                faultCode=-32601,
                faultString=f"Method not found: {method_name}",
            )
            return xmlrpc.client.dumps(fault, allow_none=True).encode("utf-8")

        # Execute method
        try:
            handler = self._methods[method_name]
            # XML-RPC requires a tuple for response
            # Homematic expects acknowledgment (True) for None results
            if (result := await handler(*params)) is None:
                result = True

            return xmlrpc.client.dumps(
                (result,),
                methodresponse=True,
                allow_none=True,
            ).encode("utf-8")
        except Exception as err:
            _LOGGER.exception(i18n.tr(key="log.central.rpc_server.method_failed", method_name=method_name))
            fault = xmlrpc.client.Fault(
                faultCode=-32603,
                faultString=str(err),
            )
            return xmlrpc.client.dumps(fault, allow_none=True).encode("utf-8")

    def register_instance(self, *, instance: object) -> None:
        """
        Register all public methods of an instance.

        Methods starting with underscore are ignored.
        camelCase methods are registered as-is (required by Homematic protocol).
        """
        for name in dir(instance):
            if name.startswith("_"):
                continue
            method = getattr(instance, name)
            if callable(method):
                self._methods[name] = method

    def register_introspection_functions(self) -> None:
        """Register XML-RPC introspection methods."""
        self._methods["system.listMethods"] = self._system_list_methods
        self._methods["system.methodHelp"] = self._system_method_help
        self._methods["system.methodSignature"] = self._system_method_signature
        self._methods["system.multicall"] = self._system_multicall

    async def _system_list_methods(
        self,
        interface_id: str | None = None,
        /,
    ) -> list[str]:
        """Return list of available methods."""
        return sorted(self._methods.keys())

    async def _system_method_help(self, method_name: str, /) -> str:
        """Return help string for a method."""
        if method := self._methods.get(method_name):
            return method.__doc__ or ""
        return ""

    async def _system_method_signature(
        self,
        method_name: str,
        /,
    ) -> str:
        """Return signature for a method (not implemented)."""
        return "signatures not supported"

    async def _system_multicall(
        self,
        calls: list[dict[str, Any]],
        /,
    ) -> list[Any]:
        """
        Execute multiple method calls in a single request.

        This is the standard XML-RPC multicall method used by the Homematic
        backend to batch multiple event notifications together.

        Args:
            calls: List of dicts with 'methodName' and 'params' keys

        Returns:
            List of results (each wrapped in a list) or fault dicts.

        """
        results: list[Any] = []
        for call in calls:
            method_name = call.get("methodName", "")
            params = call.get("params", [])

            if method_name not in self._methods:
                results.append({"faultCode": -32601, "faultString": f"Method not found: {method_name}"})
                continue

            try:
                handler = self._methods[method_name]
                result = await handler(*params)
                # XML-RPC multicall wraps each result in a list
                results.append([result if result is not None else True])
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Multicall method %s failed: %s", method_name, err)
                results.append({"faultCode": -32603, "faultString": str(err)})

        return results


# pylint: disable=invalid-name
class AsyncRPCFunctions:
    """
    Async implementation of RPC callback functions.

    Method names use camelCase as required by Homematic XML-RPC protocol.
    """

    # Disable kw-only linter for protocol compatibility
    __kwonly_check__ = False

    def __init__(self, *, rpc_server: AsyncXmlRpcServer) -> None:
        """Initialize AsyncRPCFunctions."""
        self._rpc_server: Final = rpc_server
        # Store task references to prevent garbage collection (RUF006)
        self._background_tasks: Final[set[asyncio.Task[None]]] = set()

    @property
    def active_tasks_count(self) -> int:
        """Return the number of active background tasks."""
        return len(self._background_tasks)

    async def cancel_background_tasks(self) -> None:
        """Cancel all background tasks and wait for them to complete."""
        if not self._background_tasks:
            return

        _LOGGER.debug(
            "Cancelling %d background tasks",
            len(self._background_tasks),
        )

        # Cancel all tasks
        for task in self._background_tasks:
            task.cancel()

        # Wait for all tasks to complete (with timeout)
        if self._background_tasks:
            await asyncio.wait(
                self._background_tasks,
                timeout=5.0,
            )

    async def deleteDevices(
        self,
        interface_id: str,
        addresses: list[str],
        /,
    ) -> None:
        """Delete devices sent from the backend."""
        if entry := self._get_central_entry(interface_id=interface_id):
            # Fire-and-forget: schedule task and return immediately
            self._create_background_task(
                entry.central.device_coordinator.delete_devices(
                    interface_id=interface_id,
                    addresses=tuple(addresses),
                ),
                name=f"deleteDevices-{interface_id}",
            )

    async def error(
        self,
        interface_id: str,
        error_code: str,
        msg: str,
        /,
    ) -> None:
        """Handle error notification from backend."""
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
                key="log.central.rpc_server.error",
                interface_id=interface_id,
                error_code=int(error_code),
                msg=str(msg),
            )
        )
        self._publish_system_event(interface_id=interface_id, system_event=SystemEventType.ERROR)

    async def event(
        self,
        interface_id: str,
        channel_address: str,
        parameter: str,
        value: Any,
        /,
    ) -> None:
        """Handle data point event from backend."""
        if entry := self._get_central_entry(interface_id=interface_id):
            # Fire-and-forget: schedule task and return immediately
            self._create_background_task(
                entry.central.event_coordinator.data_point_event(
                    interface_id=interface_id,
                    channel_address=channel_address,
                    parameter=parameter,
                    value=value,
                ),
                name=f"event-{interface_id}-{channel_address}-{parameter}",
            )
        else:
            _LOGGER.debug(
                "EVENT: No central found for interface_id=%s, channel=%s, param=%s",
                interface_id,
                channel_address,
                parameter,
            )

    async def listDevices(
        self,
        interface_id: str,
        /,
    ) -> list[dict[str, Any]]:
        """Return existing devices to the backend."""
        if entry := self._get_central_entry(interface_id=interface_id):
            return [
                dict(device_description)
                for device_description in entry.central.device_coordinator.list_devices(interface_id=interface_id)
            ]
        return []

    async def newDevices(
        self,
        interface_id: str,
        device_descriptions: list[dict[str, Any]],
        /,
    ) -> None:
        """Handle new devices from backend."""
        if entry := self._get_central_entry(interface_id=interface_id):
            # Fire-and-forget: schedule task and return immediately
            self._create_background_task(
                entry.central.device_coordinator.add_new_devices(
                    interface_id=interface_id,
                    device_descriptions=tuple(device_descriptions),
                ),
                name=f"newDevices-{interface_id}",
            )

    async def readdedDevice(
        self,
        interface_id: str,
        addresses: list[str],
        /,
    ) -> None:
        """Handle re-added device notification."""
        _LOGGER.debug(
            "READDEDDEVICES: interface_id = %s, addresses = %s",
            interface_id,
            str(addresses),
        )
        self._publish_system_event(interface_id=interface_id, system_event=SystemEventType.RE_ADDED_DEVICE)

    async def replaceDevice(
        self,
        interface_id: str,
        old_device_address: str,
        new_device_address: str,
        /,
    ) -> None:
        """Handle device replacement notification."""
        _LOGGER.debug(
            "REPLACEDEVICE: interface_id = %s, oldDeviceAddress = %s, newDeviceAddress = %s",
            interface_id,
            old_device_address,
            new_device_address,
        )
        self._publish_system_event(interface_id=interface_id, system_event=SystemEventType.REPLACE_DEVICE)

    async def updateDevice(
        self,
        interface_id: str,
        address: str,
        hint: int,
        /,
    ) -> None:
        """Handle device update notification."""
        _LOGGER.debug(
            "UPDATEDEVICE: interface_id = %s, address = %s, hint = %s",
            interface_id,
            address,
            str(hint),
        )
        self._publish_system_event(interface_id=interface_id, system_event=SystemEventType.UPDATE_DEVICE)

    def _create_background_task(self, coro: Any, /, *, name: str) -> None:
        """Create a background task and track it to prevent garbage collection."""
        task: asyncio.Task[None] = asyncio.create_task(coro, name=name)
        self._background_tasks.add(task)
        task.add_done_callback(self._on_background_task_done)

    def _get_central_entry(self, *, interface_id: str) -> _AsyncCentralEntry | None:
        """Return central entry by interface_id."""
        return self._rpc_server.get_central_entry(interface_id=interface_id)

    def _on_background_task_done(self, task: asyncio.Task[None]) -> None:
        """Handle background task completion and log any errors."""
        self._background_tasks.discard(task)
        if task.cancelled():
            return
        if exc := task.exception():
            _LOGGER.warning(
                i18n.tr(
                    key="log.central.rpc_server.background_task_failed",
                    task_name=task.get_name(),
                    error=exc,
                )
            )

    def _publish_system_event(self, *, interface_id: str, system_event: SystemEventType) -> None:
        """Publish a system event to the event coordinator."""
        if client := hmcl.get_client(interface_id=interface_id):
            client.central.event_coordinator.publish_system_event(system_event=system_event)


class _AsyncCentralEntry:
    """Container for central unit registration."""

    __slots__ = ("central",)

    def __init__(self, *, central: RpcServerCentralProtocol) -> None:
        """Initialize central entry."""
        self.central: Final = central


class AsyncXmlRpcServer:
    """
    Async XML-RPC server using aiohttp.

    Singleton per (ip_addr, port) combination.
    """

    # Disable kw-only linter for aiohttp callback compatibility
    __kwonly_check__ = False

    _initialized: bool = False
    _instances: Final[dict[tuple[str, int], AsyncXmlRpcServer]] = {}

    def __init__(
        self,
        *,
        ip_addr: str = IP_ANY_V4,
        port: int = PORT_ANY,
    ) -> None:
        """Initialize the async XML-RPC server."""
        if self._initialized:
            return

        self._ip_addr: Final = ip_addr
        self._requested_port: Final = port
        self._actual_port: int = port

        self._centrals: Final[dict[str, _AsyncCentralEntry]] = {}
        self._dispatcher: Final = AsyncXmlRpcDispatcher()
        # Set client_max_size to 10MB to handle large XML-RPC requests
        self._app: Final = web.Application(client_max_size=10 * 1024 * 1024)
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._started: bool = False

        # Register RPC functions
        self._rpc_functions: Final = AsyncRPCFunctions(rpc_server=self)
        self._dispatcher.register_instance(instance=self._rpc_functions)
        self._dispatcher.register_introspection_functions()

        # Configure routes
        self._app.router.add_post("/", self._handle_request)
        self._app.router.add_post("/RPC2", self._handle_request)
        self._app.router.add_get("/health", self._handle_health_check)

        # Metrics counters
        self._request_count: int = 0
        self._error_count: int = 0

        self._initialized = True

    def __new__(  # noqa: PYI034
        cls,
        *,
        ip_addr: str = IP_ANY_V4,
        port: int = PORT_ANY,
    ) -> AsyncXmlRpcServer:
        """Return existing instance or create new one."""
        if (key := (ip_addr, port)) not in cls._instances:
            _LOGGER.debug("Creating AsyncXmlRpcServer")
            instance = super().__new__(cls)
            cls._instances[key] = instance
        return cls._instances[key]

    @property
    def _event_bus(self) -> EventBus | None:
        """Return event bus from first registered central (for metrics)."""
        for entry in self._centrals.values():
            return entry.central.event_coordinator.event_bus
        return None

    @property
    def listen_ip_addr(self) -> str:
        """Return the listening IP address."""
        return self._ip_addr

    @property
    def listen_port(self) -> int:
        """Return the actual listening port."""
        return self._actual_port

    @property
    def no_central_assigned(self) -> bool:
        """Return True if no central is registered."""
        return len(self._centrals) == 0

    @property
    def started(self) -> bool:
        """Return True if server is running."""
        return self._started

    def add_central(
        self,
        *,
        central: RpcServerCentralProtocol,
    ) -> None:
        """Register a central unit."""
        if central.name not in self._centrals:
            self._centrals[central.name] = _AsyncCentralEntry(central=central)

    def get_central_entry(
        self,
        *,
        interface_id: str,
    ) -> _AsyncCentralEntry | None:
        """Return central entry by interface_id."""
        for entry in self._centrals.values():
            if entry.central.client_coordinator.has_client(interface_id=interface_id):
                return entry
        return None

    def remove_central(
        self,
        *,
        central: RpcServerCentralProtocol,
    ) -> None:
        """Unregister a central unit."""
        if central.name in self._centrals:
            del self._centrals[central.name]

    async def start(self) -> None:
        """Start the HTTP server."""
        if self._started:
            return

        self._runner = web.AppRunner(
            self._app,
            access_log=None,  # Disable access logging
        )
        await self._runner.setup()

        self._site = web.TCPSite(
            self._runner,
            self._ip_addr,
            self._requested_port,
            reuse_address=True,
        )
        await self._site.start()

        # Get actual port (important when PORT_ANY is used)
        # pylint: disable=protected-access
        if (
            self._site._server  # noqa: SLF001
            and hasattr(self._site._server, "sockets")  # noqa: SLF001
            and (sockets := self._site._server.sockets)  # noqa: SLF001
        ):
            self._actual_port = sockets[0].getsockname()[1]

        self._started = True
        _LOGGER.debug(
            "AsyncXmlRpcServer started on %s:%d",
            self._ip_addr,
            self._actual_port,
        )

    async def stop(self) -> None:
        """Stop the HTTP server."""
        if not self._started:
            return

        _LOGGER.debug("Stopping AsyncXmlRpcServer")

        if self._site:
            await self._site.stop()
            self._site = None

        if self._runner:
            await self._runner.cleanup()
            self._runner = None

        # Cancel and wait for background tasks
        await self._cancel_background_tasks()

        self._started = False

        # Remove from instances
        if (key := (self._ip_addr, self._requested_port)) in self._instances:
            del self._instances[key]

        _LOGGER.debug("AsyncXmlRpcServer stopped")

    async def _cancel_background_tasks(self) -> None:
        """Cancel all background tasks and wait for them to complete."""
        await self._rpc_functions.cancel_background_tasks()

    async def _handle_health_check(
        self,
        request: web.Request,  # noqa: ARG002
    ) -> web.Response:
        """Handle health check request."""
        health_data = {
            "status": "healthy" if self._started else "stopped",
            "started": self._started,
            "centrals_count": len(self._centrals),
            "centrals": list(self._centrals.keys()),
            "active_background_tasks": self._rpc_functions.active_tasks_count,
            "request_count": self._request_count,
            "error_count": self._error_count,
            "listen_address": f"{self._ip_addr}:{self._actual_port}",
        }
        return web.Response(
            body=orjson.dumps(health_data),
            content_type="application/json",
            charset="utf-8",
        )

    async def _handle_request(
        self,
        request: web.Request,
    ) -> web.Response:
        """Handle incoming XML-RPC request."""
        start_time = time.perf_counter()
        self._request_count += 1

        # Emit request counter metric
        if event_bus := self._event_bus:
            emit_counter(event_bus=event_bus, key=MetricKeys.rpc_server_request())
            emit_gauge(
                event_bus=event_bus,
                key=MetricKeys.rpc_server_active_tasks(),
                value=self._rpc_functions.active_tasks_count,
            )

        try:
            body = await request.read()
            response_xml = await self._dispatcher.dispatch(xml_data=body)
            return web.Response(
                body=response_xml,
                content_type="text/xml",
                charset="utf-8",
            )
        except XmlRpcProtocolError as err:
            self._error_count += 1
            if event_bus := self._event_bus:
                emit_counter(event_bus=event_bus, key=MetricKeys.rpc_server_error())
            _LOGGER.warning(i18n.tr(key="log.central.rpc_server.protocol_error", error=err))
            return web.Response(
                status=400,
                text="XML-RPC protocol error",
            )
        except Exception:
            self._error_count += 1
            if event_bus := self._event_bus:
                emit_counter(event_bus=event_bus, key=MetricKeys.rpc_server_error())
            _LOGGER.exception(i18n.tr(key="log.central.rpc_server.unexpected_error"))
            return web.Response(
                status=500,
                text="Internal Server Error",
            )
        finally:
            # Emit latency metric
            if event_bus := self._event_bus:
                duration_ms = (time.perf_counter() - start_time) * 1000
                emit_latency(
                    event_bus=event_bus,
                    key=MetricKeys.rpc_server_request_latency(),
                    duration_ms=duration_ms,
                )


async def create_async_xml_rpc_server(
    *,
    ip_addr: str = IP_ANY_V4,
    port: int = PORT_ANY,
) -> AsyncXmlRpcServer:
    """Create and start an async XML-RPC server."""
    server = AsyncXmlRpcServer(ip_addr=ip_addr, port=port)
    if not server.started:
        await server.start()
        _LOGGER.debug(
            "CREATE_ASYNC_XML_RPC_SERVER: Starting AsyncXmlRpcServer listening on %s:%i",
            server.listen_ip_addr,
            server.listen_port,
        )
    return server
