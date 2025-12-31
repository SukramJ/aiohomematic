# ADR 0011: Async XML-RPC Server - Proof of Concept

## Status

Proposed (Experimental)

## Context

ADR 0004 rejected an asyncio implementation of the XML-RPC server. This document describes a Proof of Concept to empirically evaluate the technical feasibility and actual advantages/disadvantages.

### Current Implementation (Thread-based)

```
┌─────────────────────────────────────────────────────────────┐
│                    Homematic Backend (CCU)                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ XML-RPC Callbacks
                              ▼
┌─────────────────────────────────────────────────────────────┐
│               XmlRpcServer (Thread)                          │
│  ┌─────────────────────────────────────────────────────┐    │
│  │         SimpleXMLRPCServer (stdlib)                  │    │
│  │  - serve_forever() in dedicated thread               │    │
│  │  - Blocking I/O                                      │    │
│  └─────────────────────────────────────────────────────┘    │
│                              │                               │
│                              │ run_coroutine_threadsafe()   │
│                              ▼                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │             RpcServerTaskSchedulerProtocol           │    │
│  │  - create_task() → schedules async work              │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Main asyncio Event Loop                    │
│  - EventCoordinator.data_point_event()                      │
│  - DeviceCoordinator.add_new_devices()                      │
│  - DeviceCoordinator.delete_devices()                       │
└─────────────────────────────────────────────────────────────┘
```

### Problems with the Thread-based Solution

1. **Mixed concurrency model**: Threading + asyncio increases complexity
2. **Thread overhead**: Dedicated thread for the server
3. **Context-switch latency**: `run_coroutine_threadsafe()` has overhead (~0.1-1ms)
4. **Debugging complexity**: Stack traces across thread boundaries

---

## Proposed Solution: aiohttp-based Async XML-RPC Server

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Homematic Backend (CCU)                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ XML-RPC over HTTP POST
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              AsyncXmlRpcServer (aiohttp)                     │
│  ┌─────────────────────────────────────────────────────┐    │
│  │           aiohttp.web.Application                    │    │
│  │  - POST / → handle_xmlrpc_request()                  │    │
│  │  - POST /RPC2 → handle_xmlrpc_request()              │    │
│  │  - Non-blocking, runs in main event loop             │    │
│  └─────────────────────────────────────────────────────┘    │
│                              │                               │
│                              │ Direct async call            │
│                              ▼                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              AsyncRPCFunctions                       │    │
│  │  - async def event(...)                              │    │
│  │  - async def newDevices(...)                         │    │
│  │  - Direct access to Coordinators                     │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Main asyncio Event Loop                    │
│  - EventCoordinator.data_point_event()                      │
│  - DeviceCoordinator.add_new_devices()                      │
│  - DeviceCoordinator.delete_devices()                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Detailed Implementation

### 1. XML-RPC Protocol Handler

```python
# aiohomematic/central/async_rpc_server.py
"""
Async XML-RPC server module.

Provides an asyncio-native XML-RPC server using aiohttp for
receiving callbacks from the Homematic backend.
"""

from __future__ import annotations

import logging
import xmlrpc.client
from typing import TYPE_CHECKING, Any, Final
from xml.parsers.expat import ExpatError

from aiohttp import web

from aiohomematic.const import IP_ANY_V4, PORT_ANY, SystemEventType
from aiohomematic.central.decorators import callback_backend_system
from aiohomematic.interfaces.central import (
    RpcServerCentralProtocol,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

_LOGGER: Final = logging.getLogger(__name__)

# Type alias for async method handlers
AsyncMethodHandler = Callable[..., Awaitable[Any]]


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
        self._introspection_enabled: bool = False

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
        self._introspection_enabled = True
        self._methods["system.listMethods"] = self._system_list_methods
        self._methods["system.methodHelp"] = self._system_method_help
        self._methods["system.methodSignature"] = self._system_method_signature

    async def _system_list_methods(
        self,
        interface_id: str | None = None,
    ) -> list[str]:
        """Return list of available methods."""
        return sorted(self._methods.keys())

    async def _system_method_help(self, method_name: str) -> str:
        """Return help string for a method."""
        if method := self._methods.get(method_name):
            return method.__doc__ or ""
        return ""

    async def _system_method_signature(
        self,
        method_name: str,
    ) -> str:
        """Return signature for a method (not implemented)."""
        return "signatures not supported"

    async def dispatch(self, *, xml_data: bytes) -> bytes:
        """
        Parse XML-RPC request and dispatch to handler.

        Args:
            xml_data: Raw XML-RPC request body

        Returns:
            XML-RPC response as bytes

        Raises:
            XmlRpcProtocolError: If request cannot be parsed
        """
        try:
            params, method_name = xmlrpc.client.loads(
                xml_data,
                use_builtin_types=True,
            )
        except ExpatError as err:
            raise XmlRpcProtocolError(f"Invalid XML: {err}") from err
        except Exception as err:
            raise XmlRpcProtocolError(f"Parse error: {err}") from err

        _LOGGER.debug(
            "XML-RPC dispatch: method=%s, params=%s",
            method_name,
            params[:2] if len(params) > 2 else params,  # Truncate for logging
        )

        # Look up method
        if method_name not in self._methods:
            fault = xmlrpc.client.Fault(
                faultCode=-32601,
                faultString=f"Method not found: {method_name}",
            )
            return xmlrpc.client.dumps(fault, allow_none=True)

        # Execute method
        try:
            handler = self._methods[method_name]
            result = await handler(*params)

            # XML-RPC requires a tuple for response
            if result is None:
                result = True  # Homematic expects acknowledgment

            return xmlrpc.client.dumps(
                (result,),
                methodresponse=True,
                allow_none=True,
            )
        except Exception as err:
            _LOGGER.exception("XML-RPC method %s failed", method_name)
            fault = xmlrpc.client.Fault(
                faultCode=-32603,
                faultString=str(err),
            )
            return xmlrpc.client.dumps(fault, allow_none=True)
```

### 2. Async RPC Functions

```python
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

    async def deleteDevices(
        self,
        interface_id: str,
        addresses: list[str],
        /,
    ) -> None:
        """Delete devices sent from the backend."""
        if entry := self._get_central_entry(interface_id=interface_id):
            await entry.central.device_coordinator.delete_devices(
                interface_id=interface_id,
                addresses=tuple(addresses),
            )

    @callback_backend_system(system_event=SystemEventType.ERROR)
    async def error(
        self,
        interface_id: str,
        error_code: str,
        msg: str,
        /,
    ) -> None:
        """Handle error notification from backend."""
        _LOGGER.error(
            "Backend error: interface_id=%s, code=%s, msg=%s",
            interface_id,
            error_code,
            msg,
        )

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
            await entry.central.event_coordinator.data_point_event(
                interface_id=interface_id,
                channel_address=channel_address,
                parameter=parameter,
                value=value,
            )

    async def listDevices(
        self,
        interface_id: str,
        /,
    ) -> list[dict[str, Any]]:
        """Return existing devices to the backend."""
        if entry := self._get_central_entry(interface_id=interface_id):
            return [
                dict(desc)
                for desc in entry.central.device_coordinator.list_devices(
                    interface_id=interface_id
                )
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
            await entry.central.device_coordinator.add_new_devices(
                interface_id=interface_id,
                device_descriptions=tuple(device_descriptions),
            )

    @callback_backend_system(system_event=SystemEventType.RE_ADDED_DEVICE)
    async def readdedDevice(
        self,
        interface_id: str,
        addresses: list[str],
        /,
    ) -> None:
        """Handle re-added device notification."""
        _LOGGER.debug(
            "READDEDDEVICES: interface_id=%s, addresses=%s",
            interface_id,
            addresses,
        )

    @callback_backend_system(system_event=SystemEventType.REPLACE_DEVICE)
    async def replaceDevice(
        self,
        interface_id: str,
        old_device_address: str,
        new_device_address: str,
        /,
    ) -> None:
        """Handle device replacement notification."""
        _LOGGER.debug(
            "REPLACEDEVICE: interface_id=%s, old=%s, new=%s",
            interface_id,
            old_device_address,
            new_device_address,
        )

    @callback_backend_system(system_event=SystemEventType.UPDATE_DEVICE)
    async def updateDevice(
        self,
        interface_id: str,
        address: str,
        hint: int,
        /,
    ) -> None:
        """Handle device update notification."""
        _LOGGER.debug(
            "UPDATEDEVICE: interface_id=%s, address=%s, hint=%s",
            interface_id,
            address,
            hint,
        )

    def _get_central_entry(
        self,
        *,
        interface_id: str,
    ) -> _AsyncCentralEntry | None:
        """Return central entry by interface_id."""
        return self._rpc_server.get_central_entry(interface_id=interface_id)
```

### 3. aiohttp Web Server

```python
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

    _instances: Final[dict[tuple[str, int], AsyncXmlRpcServer]] = {}

    def __init__(
        self,
        *,
        ip_addr: str = IP_ANY_V4,
        port: int = PORT_ANY,
    ) -> None:
        """Initialize the async XML-RPC server."""
        self._ip_addr: Final = ip_addr
        self._requested_port: Final = port
        self._actual_port: int = port

        self._centrals: Final[dict[str, _AsyncCentralEntry]] = {}
        self._dispatcher: Final = AsyncXmlRpcDispatcher()
        self._app: Final = web.Application()
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._started: bool = False

        # Register RPC functions
        self._rpc_functions = AsyncRPCFunctions(rpc_server=self)
        self._dispatcher.register_instance(instance=self._rpc_functions)
        self._dispatcher.register_introspection_functions()

        # Configure routes
        self._app.router.add_post("/", self._handle_request)
        self._app.router.add_post("/RPC2", self._handle_request)

    def __new__(
        cls,
        *,
        ip_addr: str = IP_ANY_V4,
        port: int = PORT_ANY,
    ) -> AsyncXmlRpcServer:
        """Return existing instance or create new one."""
        key = (ip_addr, port)
        if key not in cls._instances:
            instance = super().__new__(cls)
            cls._instances[key] = instance
        return cls._instances[key]

    @property
    def listen_ip_addr(self) -> str:
        """Return the listening IP address."""
        return self._ip_addr

    @property
    def listen_port(self) -> int:
        """Return the actual listening port."""
        return self._actual_port

    @property
    def started(self) -> bool:
        """Return True if server is running."""
        return self._started

    @property
    def no_central_assigned(self) -> bool:
        """Return True if no central is registered."""
        return len(self._centrals) == 0

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
        if self._site._server:  # noqa: SLF001
            sockets = self._site._server.sockets  # noqa: SLF001
            if sockets:
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

        self._started = False

        # Remove from instances
        key = (self._ip_addr, self._requested_port)
        if key in self._instances:
            del self._instances[key]

        _LOGGER.debug("AsyncXmlRpcServer stopped")

    def add_central(
        self,
        *,
        central: RpcServerCentralProtocol,
    ) -> None:
        """Register a central unit."""
        if central.name not in self._centrals:
            self._centrals[central.name] = _AsyncCentralEntry(central=central)

    def remove_central(
        self,
        *,
        central: RpcServerCentralProtocol,
    ) -> None:
        """Unregister a central unit."""
        if central.name in self._centrals:
            del self._centrals[central.name]

    def get_central_entry(
        self,
        *,
        interface_id: str,
    ) -> _AsyncCentralEntry | None:
        """Return central entry by interface_id."""
        for entry in self._centrals.values():
            if entry.central.client_coordinator.has_client(
                interface_id=interface_id
            ):
                return entry
        return None

    async def _handle_request(
        self,
        request: web.Request,
    ) -> web.Response:
        """Handle incoming XML-RPC request."""
        try:
            body = await request.read()
            response_xml = await self._dispatcher.dispatch(xml_data=body)
            return web.Response(
                body=response_xml,
                content_type="text/xml",
                charset="utf-8",
            )
        except XmlRpcProtocolError as err:
            _LOGGER.warning("XML-RPC protocol error: %s", err)
            return web.Response(
                status=400,
                text=str(err),
            )
        except Exception:
            _LOGGER.exception("Unexpected error handling XML-RPC request")
            return web.Response(
                status=500,
                text="Internal Server Error",
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
            "Created AsyncXmlRpcServer on %s:%d",
            server.listen_ip_addr,
            server.listen_port,
        )
    return server
```

---

## Migration Strategy

### Phase 1: Feature Flag (Parallel Operation)

```python
# aiohomematic/const.py
class OptionalSettings(StrEnum):
    """Optional settings for CentralConfig."""
    # ... existing settings ...
    ASYNC_RPC_SERVER = "async_rpc_server"  # Experimental async XML-RPC
```

```python
# aiohomematic/central/central_unit.py
async def _start_rpc_server(self) -> None:
    """Start the appropriate RPC server based on configuration."""
    if OptionalSettings.ASYNC_RPC_SERVER in self._config.optional_settings:
        from aiohomematic.central.async_rpc_server import (
            create_async_xml_rpc_server,
        )
        self._rpc_server = await create_async_xml_rpc_server(
            ip_addr=self._config.callback_ip_addr,
            port=self._config.callback_port,
        )
        self._rpc_server.add_central(central=self)
    else:
        # Existing thread-based implementation
        self._rpc_server = create_xml_rpc_server(
            ip_addr=self._config.callback_ip_addr,
            port=self._config.callback_port,
        )
        self._rpc_server.add_central(
            central=self,
            looper=self._looper,
        )
```

### Phase 2: Testing and Validation

Testing requires enabling the feature flag programmatically:

```python
# In aiohomematic tests or standalone scripts
from aiohomematic.central import CentralConfig
from aiohomematic.const import OptionalSettings

config = CentralConfig(
    name="test-ccu",
    host="192.168.1.100",
    # ... other config ...
    optional_settings=(OptionalSettings.ASYNC_RPC_SERVER,),
)
```

For Home Assistant integration testing, the `homematicip_local` integration would need to expose this setting via config flow or as an advanced option. This requires a separate PR to the integration repository.

**Validation approach:**

1. Run automated tests with both server implementations
2. Manual testing with real CCU hardware
3. Compare latency and resource usage metrics
4. Stability testing over extended periods (days/weeks)

### Phase 3: Deprecation and Removal

After successful validation:

1. Set async server as default
2. Mark thread-based server as deprecated
3. Remove after 2-3 releases

---

## Testing Strategy

### 1. Unit Tests

```python
# tests/test_async_rpc_server.py
"""Tests for async XML-RPC server."""

from __future__ import annotations

import pytest
import xmlrpc.client

from aiohttp import ClientSession

from aiohomematic.central.async_rpc_server import (
    AsyncXmlRpcDispatcher,
    AsyncXmlRpcServer,
    create_async_xml_rpc_server,
)


class TestAsyncXmlRpcDispatcher:
    """Tests for AsyncXmlRpcDispatcher."""

    @pytest.mark.asyncio
    async def test_dispatch_simple_method(self) -> None:
        """Test dispatching a simple method call."""
        dispatcher = AsyncXmlRpcDispatcher()

        async def echo(value: str) -> str:
            return value

        dispatcher._methods["echo"] = echo

        request = xmlrpc.client.dumps(("hello",), methodname="echo")
        response = await dispatcher.dispatch(xml_data=request.encode())

        result, _ = xmlrpc.client.loads(response)
        assert result[0] == "hello"

    @pytest.mark.asyncio
    async def test_dispatch_unknown_method(self) -> None:
        """Test dispatching to unknown method returns fault."""
        dispatcher = AsyncXmlRpcDispatcher()

        request = xmlrpc.client.dumps((), methodname="unknown")
        response = await dispatcher.dispatch(xml_data=request.encode())

        with pytest.raises(xmlrpc.client.Fault) as exc_info:
            xmlrpc.client.loads(response)
        assert exc_info.value.faultCode == -32601


class TestAsyncXmlRpcServer:
    """Tests for AsyncXmlRpcServer."""

    @pytest.mark.asyncio
    async def test_server_lifecycle(self) -> None:
        """Test server start and stop."""
        server = AsyncXmlRpcServer(ip_addr="127.0.0.1", port=0)

        assert not server.started

        await server.start()
        assert server.started
        assert server.listen_port > 0

        await server.stop()
        assert not server.started

    @pytest.mark.asyncio
    async def test_xmlrpc_over_http(self) -> None:
        """Test XML-RPC request over HTTP."""
        server = await create_async_xml_rpc_server(
            ip_addr="127.0.0.1",
            port=0,
        )

        try:
            url = f"http://127.0.0.1:{server.listen_port}/"

            async with ClientSession() as session:
                request_body = xmlrpc.client.dumps(
                    (None,),
                    methodname="system.listMethods",
                )
                async with session.post(
                    url,
                    data=request_body,
                    headers={"Content-Type": "text/xml"},
                ) as response:
                    assert response.status == 200
                    body = await response.read()
                    result, _ = xmlrpc.client.loads(body)
                    assert "event" in result[0]
        finally:
            await server.stop()
```

### 2. Integration Tests

```python
# tests/test_async_rpc_integration.py
"""Integration tests comparing thread-based and async RPC servers."""

from __future__ import annotations

import asyncio
import time
import xmlrpc.client

import pytest
from aiohttp import ClientSession

from aiohomematic.central.rpc_server import create_xml_rpc_server
from aiohomematic.central.async_rpc_server import create_async_xml_rpc_server


class TestRpcServerComparison:
    """Compare thread-based and async RPC server behavior."""

    @pytest.mark.asyncio
    async def test_event_handling_latency_async(self) -> None:
        """Measure event handling latency for async server."""
        server = await create_async_xml_rpc_server(
            ip_addr="127.0.0.1",
            port=0,
        )

        # Setup mock central that records event timing
        event_times: list[float] = []

        # ... mock central setup ...

        try:
            latencies = []
            for _ in range(100):
                start = time.perf_counter()
                # Send event via HTTP
                async with ClientSession() as session:
                    request = xmlrpc.client.dumps(
                        ("test-interface", "ABC123:1", "STATE", True),
                        methodname="event",
                    )
                    await session.post(
                        f"http://127.0.0.1:{server.listen_port}/",
                        data=request,
                    )
                end = time.perf_counter()
                latencies.append((end - start) * 1000)  # ms

            avg_latency = sum(latencies) / len(latencies)
            print(f"Async server avg latency: {avg_latency:.2f}ms")

        finally:
            await server.stop()

    def test_event_handling_latency_thread(self) -> None:
        """Measure event handling latency for thread-based server."""
        server = create_xml_rpc_server(
            ip_addr="127.0.0.1",
            port=0,
        )

        try:
            proxy = xmlrpc.client.ServerProxy(
                f"http://127.0.0.1:{server.listen_port}/",
            )

            latencies = []
            for _ in range(100):
                start = time.perf_counter()
                # Event will fail (no central registered) but measures RPC overhead
                try:
                    proxy.event("test-interface", "ABC123:1", "STATE", True)
                except Exception:
                    pass
                end = time.perf_counter()
                latencies.append((end - start) * 1000)  # ms

            avg_latency = sum(latencies) / len(latencies)
            print(f"Thread server avg latency: {avg_latency:.2f}ms")

        finally:
            server.stop()
```

### 3. Stress Tests

```python
# tests/test_async_rpc_stress.py
"""Stress tests for async RPC server."""

from __future__ import annotations

import asyncio

import pytest
from aiohttp import ClientSession

from aiohomematic.central.async_rpc_server import create_async_xml_rpc_server


class TestAsyncRpcStress:
    """Stress tests for async server."""

    @pytest.mark.asyncio
    async def test_concurrent_requests(self) -> None:
        """Test handling many concurrent requests."""
        server = await create_async_xml_rpc_server(
            ip_addr="127.0.0.1",
            port=0,
        )

        try:
            async def send_event(session: ClientSession, n: int) -> None:
                import xmlrpc.client
                request = xmlrpc.client.dumps(
                    (f"interface-{n}", f"DEV{n:04d}:1", "STATE", n % 2 == 0),
                    methodname="event",
                )
                async with session.post(
                    f"http://127.0.0.1:{server.listen_port}/",
                    data=request,
                ) as response:
                    assert response.status == 200

            async with ClientSession() as session:
                # Send 1000 concurrent events
                tasks = [send_event(session, i) for i in range(1000)]
                await asyncio.gather(*tasks)

        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_sustained_load(self) -> None:
        """Test sustained load over time."""
        server = await create_async_xml_rpc_server(
            ip_addr="127.0.0.1",
            port=0,
        )

        try:
            import xmlrpc.client

            async with ClientSession() as session:
                for batch in range(10):  # 10 batches
                    tasks = []
                    for i in range(100):  # 100 events per batch
                        request = xmlrpc.client.dumps(
                            ("interface", f"DEV{i:04d}:1", "STATE", True),
                            methodname="event",
                        )
                        tasks.append(
                            session.post(
                                f"http://127.0.0.1:{server.listen_port}/",
                                data=request,
                            )
                        )

                    responses = await asyncio.gather(*tasks)
                    for resp in responses:
                        assert resp.status == 200
                        await resp.release()

                    await asyncio.sleep(0.1)  # Small delay between batches

        finally:
            await server.stop()
```

---

## Performance Comparison

### Expected Improvements

| Metric                | Thread-based          | Async            | Improvement |
| --------------------- | --------------------- | ---------------- | ----------- |
| Request Latency       | ~1-5ms                | ~0.1-1ms         | 5-10x       |
| Memory per Connection | ~8KB (thread stack)   | ~1KB (coroutine) | 8x          |
| Concurrent Requests   | ~100 (thread limit)   | ~10,000+         | 100x        |
| Context Switches      | High (thread→asyncio) | None             | ∞           |

### Measurement Points

1. **Round-trip Latency**: Time from HTTP POST to response
2. **Event Processing Time**: Time until EventCoordinator.data_point_event() completes
3. **Memory Usage**: RSS diff with 1000 concurrent connections
4. **CPU Usage**: Under sustained load

---

## Risk Mitigation

### 1. Fallback Mechanism

```python
class RpcServerFactory:
    """Factory that can create either server type with fallback."""

    @staticmethod
    async def create(
        *,
        ip_addr: str,
        port: int,
        use_async: bool = False,
        fallback_on_error: bool = True,
    ) -> RpcServer | AsyncXmlRpcServer:
        """Create RPC server with optional fallback."""
        if use_async:
            try:
                return await create_async_xml_rpc_server(
                    ip_addr=ip_addr,
                    port=port,
                )
            except Exception as err:
                if fallback_on_error:
                    _LOGGER.warning(
                        "Async RPC server failed, falling back to thread: %s",
                        err,
                    )
                    return create_xml_rpc_server(
                        ip_addr=ip_addr,
                        port=port,
                    )
                raise
        return create_xml_rpc_server(ip_addr=ip_addr, port=port)
```

### 2. Health Monitoring

```python
class AsyncXmlRpcServer:
    """Extended with health monitoring."""

    def __init__(self, ...) -> None:
        # ... existing init ...
        self._request_count: int = 0
        self._error_count: int = 0
        self._last_request_time: datetime | None = None

    @property
    def health_status(self) -> dict[str, Any]:
        """Return server health metrics."""
        return {
            "started": self._started,
            "request_count": self._request_count,
            "error_count": self._error_count,
            "error_rate": (
                self._error_count / self._request_count
                if self._request_count > 0 else 0
            ),
            "last_request": self._last_request_time,
            "centrals_registered": len(self._centrals),
        }
```

### 3. Circuit Breaker

Automatically fall back to thread server on too many errors:

```python
class AsyncRpcCircuitBreaker:
    """Circuit breaker for async RPC server."""

    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        reset_timeout: float = 60.0,
    ) -> None:
        self._failure_count: int = 0
        self._failure_threshold = failure_threshold
        self._reset_timeout = reset_timeout
        self._last_failure: datetime | None = None
        self._open: bool = False

    def record_failure(self) -> None:
        """Record a failure."""
        self._failure_count += 1
        self._last_failure = datetime.now()
        if self._failure_count >= self._failure_threshold:
            self._open = True
            _LOGGER.error(
                "Circuit breaker opened after %d failures",
                self._failure_count,
            )

    def record_success(self) -> None:
        """Record a success."""
        self._failure_count = 0
        self._open = False

    @property
    def is_open(self) -> bool:
        """Return True if circuit is open."""
        if self._open and self._last_failure:
            elapsed = (datetime.now() - self._last_failure).total_seconds()
            if elapsed > self._reset_timeout:
                self._open = False  # Half-open: allow one request
        return self._open
```

---

## Rollback Plan

### Immediate Rollback

```python
# In CentralUnit
async def switch_to_thread_rpc_server(self) -> None:
    """Emergency switch to thread-based server."""
    if isinstance(self._rpc_server, AsyncXmlRpcServer):
        _LOGGER.warning("Switching to thread-based RPC server")

        # Stop async server
        await self._rpc_server.stop()

        # Start thread server
        self._rpc_server = create_xml_rpc_server(
            ip_addr=self._config.callback_ip_addr,
            port=self._rpc_server.listen_port,  # Keep same port
        )
        self._rpc_server.add_central(
            central=self,
            looper=self._looper,
        )
```

### Feature Flag Deactivation

To disable the async server, simply remove `OptionalSettings.ASYNC_RPC_SERVER` from the `optional_settings` tuple in the `CentralConfig`. The system will then use the default thread-based server.

For Home Assistant, this would require either:

- Removing the option from config flow (if exposed there)
- Restarting the integration without the experimental flag

---

## Implementation Checklist

### Phase 1: Core Implementation (POC)

- [ ] Implement `AsyncXmlRpcDispatcher`
- [ ] Implement `AsyncRPCFunctions`
- [ ] Implement `AsyncXmlRpcServer`
- [ ] Write unit tests
- [ ] Write integration tests

### Phase 2: Integration

- [ ] Add feature flag (`OptionalSettings.ASYNC_RPC_SERVER`)
- [ ] Adapt CentralUnit for feature flag
- [ ] Add health monitoring
- [ ] Implement circuit breaker
- [ ] Run stress tests

### Phase 3: Validation

- [ ] Document performance comparison
- [ ] A/B testing in Home Assistant
- [ ] At least 4 weeks production use
- [ ] Collect feedback

### Phase 4: Rollout

- [ ] Set async as default
- [ ] Mark thread server as deprecated
- [ ] Create migration guide
- [ ] Update ADR 0004

---

## Appendix: XML-RPC Protocol Reference

### Request Format

```xml
<?xml version="1.0"?>
<methodCall>
  <methodName>event</methodName>
  <params>
    <param><value><string>BidCos-RF</string></value></param>
    <param><value><string>MEQ0123456:1</string></value></param>
    <param><value><string>STATE</string></value></param>
    <param><value><boolean>1</boolean></value></param>
  </params>
</methodCall>
```

### Response Format

```xml
<?xml version="1.0"?>
<methodResponse>
  <params>
    <param><value><boolean>1</boolean></value></param>
  </params>
</methodResponse>
```

### Fault Response

```xml
<?xml version="1.0"?>
<methodResponse>
  <fault>
    <value>
      <struct>
        <member>
          <name>faultCode</name>
          <value><int>-32601</int></value>
        </member>
        <member>
          <name>faultString</name>
          <value><string>Method not found</string></value>
        </member>
      </struct>
    </value>
  </fault>
</methodResponse>
```

---

## References

- [ADR 0004: Thread-Based XML-RPC Server](0004-thread-based-xml-rpc-server.md)
- [aiohttp Documentation](https://docs.aiohttp.org/)
- [Python xmlrpc.client](https://docs.python.org/3/library/xmlrpc.client.html)
- [XML-RPC Specification](http://xmlrpc.com/spec.md)

---

_Created: 2025-12-31_
_Author: Architecture Review_
_Status: Proposed (Experimental)_
